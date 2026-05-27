# G3 — Módulo RH / Folha de Pagamento

API REST do módulo de Recursos Humanos do ERP distribuído (FastAPI · SQLAlchemy · SQLite/PostgreSQL).

## Stack

| Componente | Tecnologia |
|---|---|
| Framework | FastAPI 0.111 + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) |
| Banco (dev) | SQLite via aiosqlite |
| Banco (prod) | PostgreSQL via asyncpg |
| Auth | JWT — python-jose / PyJWT |
| Testes | pytest + httpx + pytest-cov |

---

## Instalação

```bash
# 1. Clone / entre na pasta
cd g3-rh

# 2. Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# 3. Instale dependências
pip install -r requirements.txt

# 4. Configure variáveis de ambiente
cp .env.example .env
# Edite .env conforme necessário
```

---

## Executar o servidor

```bash
uvicorn app.main:app --reload --port 8002
```

- Swagger UI: http://localhost:8002/docs
- ReDoc:       http://localhost:8002/redoc
- Health:      http://localhost:8002/health

---

## Testes

```bash
pytest tests/ -v
```

Cobertura mínima configurada em **70%** (RNF).

---

## Endpoints

### Funcionários
| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/rh/funcionarios` | Listar com paginação e filtros |
| `POST` | `/rh/funcionarios` | Admitir funcionário |
| `GET` | `/rh/funcionarios/{id}` | Detalhar |
| `PUT` | `/rh/funcionarios/{id}` | Atualizar |
| `DELETE` | `/rh/funcionarios/{id}` | Desativar (soft delete) |
| `GET` | `/rh/funcionarios/{id}/historico-salarial` | Histórico de salários |

### Cargos
| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/rh/cargos` | Listar cargos |
| `POST` | `/rh/cargos` | Criar cargo |
| `PUT` | `/rh/cargos/{id}` | Atualizar cargo |
| `DELETE` | `/rh/cargos/{id}` | Desativar cargo |

### Benefícios
| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/rh/beneficios` | Listar benefícios |
| `POST` | `/rh/beneficios` | Criar benefício |
| `PUT` | `/rh/beneficios/{id}` | Atualizar benefício |
| `POST` | `/rh/beneficios/funcionarios/{id}/beneficios` | Associar benefício |
| `DELETE` | `/rh/beneficios/funcionarios/{id}/beneficios/{bid}` | Desassociar |

### Folha de Pagamento
| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/rh/folha/{ano}/{mes}` | Calcular folha |
| `GET` | `/rh/folha/{ano}/{mes}` | Listar folha calculada |
| `POST` | `/rh/folha/{ano}/{mes}/fechar` | Fechar folha (imutável) |
| `GET` | `/rh/holerite/{func_id}/{ano}/{mes}` | Holerite individual |

---

## Regras de Negócio

- **RNF01** — CPF nunca exposto completo em listagens (`***.***.XXX-XX`).
- **RNF02** — Folha fechada é **imutável** — recálculo lança HTTP 409.
- **RNF03** — Todos os endpoints exigem JWT Bearer (emitido pelo Core G0).
- Salário do funcionário deve estar dentro da **faixa salarial do cargo**.
- Alterações de salário geram **histórico automático**.
- Cálculos: INSS e IRRF progressivos simplificados (tabelas 2024).

---

## Integração com outros módulos

O **Frontend (G1)** consome:
- `GET /rh/funcionarios` — total de funcionários ativos.
- `GET /rh/folha/{ano}/{mes}` — status e totais das folhas.

Todos os requests do Frontend devem incluir o token JWT emitido pelo **Core (G0 :8000)**.
