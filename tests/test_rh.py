"""
Testes do módulo G3 — RH/Folha de Pagamento.
Cobertura mínima: 70% (RNF).

Executar:
    pytest tests/ -v --cov=app --cov-report=term-missing
"""

import pytest
import pytest_asyncio
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.database import Base, get_db
from app.core.security import get_current_user

# ---------------------------------------------------------------------------
# Setup do banco em memória para testes
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def override_get_current_user():
    return {"sub": "test-user", "email": "test@test.com"}


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Fixtures de dados
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def cargo_id(client: AsyncClient) -> int:
    resp = await client.post("/rh/cargos", json={
        "nome": "Analista",
        "salario_minimo": "3000.00",
        "salario_maximo": "8000.00",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest_asyncio.fixture
async def funcionario_id(client: AsyncClient, cargo_id: int) -> int:
    resp = await client.post("/rh/funcionarios", json={
        "nome": "João Silva",
        "cpf": "52998224725",
        "email": "joao@empresa.com",
        "departamento": "TI",
        "cargo_id": cargo_id,
        "salario_base": "5000.00",
        "data_admissao": "2024-01-01",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Testes de Health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Testes de Cargos
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_criar_cargo(client: AsyncClient):
    resp = await client.post("/rh/cargos", json={
        "nome": "Desenvolvedor",
        "salario_minimo": "4000.00",
        "salario_maximo": "12000.00",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["nome"] == "Desenvolvedor"
    assert data["ativo"] is True


@pytest.mark.asyncio
async def test_criar_cargo_salario_invalido(client: AsyncClient):
    resp = await client.post("/rh/cargos", json={
        "nome": "Invalido",
        "salario_minimo": "10000.00",
        "salario_maximo": "5000.00",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_listar_cargos(client: AsyncClient, cargo_id: int):
    resp = await client.get("/rh/cargos")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ---------------------------------------------------------------------------
# Testes de Funcionários
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admitir_funcionario(client: AsyncClient, cargo_id: int):
    resp = await client.post("/rh/funcionarios", json={
        "nome": "Maria Souza",
        "cpf": "11144477735",
        "departamento": "RH",
        "cargo_id": cargo_id,
        "salario_base": "4000.00",
        "data_admissao": "2024-03-01",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "***" in data["cpf"]          # RNF01 — CPF mascarado
    assert "11144477735" not in data["cpf"]


@pytest.mark.asyncio
async def test_cpf_duplicado(client: AsyncClient, funcionario_id: int, cargo_id: int):
    resp = await client.post("/rh/funcionarios", json={
        "nome": "Outro",
        "cpf": "52998224725",           # mesmo CPF
        "departamento": "TI",
        "cargo_id": cargo_id,
        "salario_base": "4000.00",
        "data_admissao": "2024-01-01",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_listar_funcionarios(client: AsyncClient, funcionario_id: int):
    resp = await client.get("/rh/funcionarios")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    # Garantir que CPF nunca aparece completo
    for f in data["items"]:
        assert "52998224725" not in f["cpf"]


@pytest.mark.asyncio
async def test_soft_delete(client: AsyncClient, funcionario_id: int):
    resp = await client.delete(f"/rh/funcionarios/{funcionario_id}")
    assert resp.status_code == 204

    resp2 = await client.get(f"/rh/funcionarios/{funcionario_id}")
    assert resp2.json()["status"] == "INATIVO"


# ---------------------------------------------------------------------------
# Testes de Folha
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calcular_folha(client: AsyncClient, funcionario_id: int):
    resp = await client.post("/rh/folha/2024/1")
    assert resp.status_code == 201
    data = resp.json()
    assert data["ano"] == 2024
    assert data["mes"] == 1
    assert float(data["total_liquido"]) > 0


@pytest.mark.asyncio
async def test_folha_fechada_imutavel(client: AsyncClient, funcionario_id: int):
    # Calcular
    await client.post("/rh/folha/2024/2")
    # Fechar
    resp_fechar = await client.post("/rh/folha/2024/2/fechar")
    assert resp_fechar.status_code == 200

    # Tentar recalcular — deve falhar (RNF02)
    resp = await client.post("/rh/folha/2024/2")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_holerite_individual(client: AsyncClient, funcionario_id: int):
    await client.post("/rh/folha/2024/3")
    resp = await client.get(f"/rh/holerite/{funcionario_id}/2024/3")
    assert resp.status_code == 200
    data = resp.json()
    assert "***" in data["cpf_mascarado"]
    assert float(data["inss"]) > 0
    assert float(data["salario_liquido"]) > 0


# ---------------------------------------------------------------------------
# Testes de Cálculo (unitários)
# ---------------------------------------------------------------------------

def test_calcular_inss():
    from app.services.calculo_folha import calcular_inss
    inss = calcular_inss(Decimal("5000"))
    assert inss > 0

def test_calcular_irrf():
    from app.services.calculo_folha import calcular_irrf
    irrf = calcular_irrf(Decimal("4500"))
    assert irrf > 0

def test_isento_irrf():
    from app.services.calculo_folha import calcular_irrf
    irrf = calcular_irrf(Decimal("2000"))
    assert irrf == Decimal("0")


# ---------------------------------------------------------------------------
# Testes adicionais — Benefícios
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_criar_beneficio(client: AsyncClient):
    resp = await client.post("/rh/beneficios", json={
        "nome": "Vale Refeição",
        "tipo": "VR",
        "valor": "550.00",
    })
    assert resp.status_code == 201
    assert resp.json()["tipo"] == "VR"


@pytest.mark.asyncio
async def test_listar_beneficios(client: AsyncClient):
    await client.post("/rh/beneficios", json={"nome": "VT", "tipo": "VT", "valor": "200.00"})
    resp = await client.get("/rh/beneficios")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_associar_beneficio(client: AsyncClient, funcionario_id: int):
    ben = await client.post("/rh/beneficios", json={"nome": "Plano Saúde", "tipo": "PLANO_SAUDE", "valor": "300.00"})
    ben_id = ben.json()["id"]
    resp = await client.post(f"/rh/beneficios/funcionarios/{funcionario_id}/beneficios", json={"beneficio_id": ben_id})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_associar_beneficio_duplicado(client: AsyncClient, funcionario_id: int):
    ben = await client.post("/rh/beneficios", json={"nome": "VR Dup", "tipo": "VR", "valor": "500.00"})
    ben_id = ben.json()["id"]
    await client.post(f"/rh/beneficios/funcionarios/{funcionario_id}/beneficios", json={"beneficio_id": ben_id})
    resp = await client.post(f"/rh/beneficios/funcionarios/{funcionario_id}/beneficios", json={"beneficio_id": ben_id})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_desassociar_beneficio(client: AsyncClient, funcionario_id: int):
    ben = await client.post("/rh/beneficios", json={"nome": "VT Des", "tipo": "VT", "valor": "150.00"})
    ben_id = ben.json()["id"]
    await client.post(f"/rh/beneficios/funcionarios/{funcionario_id}/beneficios", json={"beneficio_id": ben_id})
    resp = await client.delete(f"/rh/beneficios/funcionarios/{funcionario_id}/beneficios/{ben_id}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Testes adicionais — Cargos e Funcionários
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_atualizar_cargo(client: AsyncClient, cargo_id: int):
    resp = await client.put(f"/rh/cargos/{cargo_id}", json={"salario_maximo": "9000.00"})
    assert resp.status_code == 200
    assert float(resp.json()["salario_maximo"]) == 9000.0


@pytest.mark.asyncio
async def test_desativar_cargo(client: AsyncClient, cargo_id: int):
    resp = await client.delete(f"/rh/cargos/{cargo_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_historico_salarial(client: AsyncClient, funcionario_id: int):
    await client.put(f"/rh/funcionarios/{funcionario_id}", json={"salario_base": "6000.00"})
    resp = await client.get(f"/rh/funcionarios/{funcionario_id}/historico-salarial")
    assert resp.status_code == 200
    historico = resp.json()
    assert len(historico) >= 1
    assert float(historico[0]["salario_anterior"]) == 5000.0
    assert float(historico[0]["salario_novo"]) == 6000.0


@pytest.mark.asyncio
async def test_detalhar_funcionario(client: AsyncClient, funcionario_id: int):
    resp = await client.get(f"/rh/funcionarios/{funcionario_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == funcionario_id
    assert "***" in data["cpf"]


@pytest.mark.asyncio
async def test_funcionario_nao_encontrado(client: AsyncClient):
    resp = await client.get("/rh/funcionarios/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_holerite_nao_encontrado(client: AsyncClient):
    resp = await client.get("/rh/holerite/99999/2024/1")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_folha_nao_encontrada(client: AsyncClient):
    resp = await client.get("/rh/folha/2099/12")
    assert resp.status_code == 404
