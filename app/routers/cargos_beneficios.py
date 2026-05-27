from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Cargo, Beneficio, Funcionario, FuncionarioBeneficio
from app.schemas.schemas import (
    CargoCreate, CargoUpdate, CargoOut,
    BeneficioCreate, BeneficioUpdate, BeneficioOut,
    AssociarBeneficioIn,
)

# ---------------------------------------------------------------------------
# Cargos
# ---------------------------------------------------------------------------

router_cargos = APIRouter(prefix="/rh/cargos", tags=["Cargos"])


@router_cargos.get("", response_model=list[CargoOut])
async def listar_cargos(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.execute(select(Cargo).order_by(Cargo.nome))
    return result.scalars().all()


@router_cargos.post("", response_model=CargoOut, status_code=status.HTTP_201_CREATED)
async def criar_cargo(
    body: CargoCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    existing = await db.execute(select(Cargo).where(Cargo.nome == body.nome))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Cargo com este nome já existe.")

    cargo = Cargo(**body.model_dump())
    db.add(cargo)
    await db.flush()
    await db.refresh(cargo)
    return cargo


@router_cargos.put("/{cargo_id}", response_model=CargoOut)
async def atualizar_cargo(
    cargo_id: int,
    body: CargoUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    cargo = await db.get(Cargo, cargo_id)
    if not cargo:
        raise HTTPException(status_code=404, detail="Cargo não encontrado.")

    for campo, valor in body.model_dump(exclude_unset=True).items():
        setattr(cargo, campo, valor)

    await db.flush()
    await db.refresh(cargo)
    return cargo


@router_cargos.delete("/{cargo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def desativar_cargo(
    cargo_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    cargo = await db.get(Cargo, cargo_id)
    if not cargo:
        raise HTTPException(status_code=404, detail="Cargo não encontrado.")
    cargo.ativo = False
    await db.flush()


# ---------------------------------------------------------------------------
# Benefícios
# ---------------------------------------------------------------------------

router_beneficios = APIRouter(prefix="/rh/beneficios", tags=["Benefícios"])


@router_beneficios.get("", response_model=list[BeneficioOut])
async def listar_beneficios(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.execute(select(Beneficio).where(Beneficio.ativo == True))
    return result.scalars().all()


@router_beneficios.post("", response_model=BeneficioOut, status_code=status.HTTP_201_CREATED)
async def criar_beneficio(
    body: BeneficioCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    beneficio = Beneficio(**body.model_dump())
    db.add(beneficio)
    await db.flush()
    await db.refresh(beneficio)
    return beneficio


@router_beneficios.put("/{beneficio_id}", response_model=BeneficioOut)
async def atualizar_beneficio(
    beneficio_id: int,
    body: BeneficioUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    ben = await db.get(Beneficio, beneficio_id)
    if not ben:
        raise HTTPException(status_code=404, detail="Benefício não encontrado.")

    for campo, valor in body.model_dump(exclude_unset=True).items():
        setattr(ben, campo, valor)

    await db.flush()
    await db.refresh(ben)
    return ben


# ---------------------------------------------------------------------------
# Associar / Desassociar Benefício a Funcionário
# ---------------------------------------------------------------------------

@router_beneficios.post(
    "/funcionarios/{funcionario_id}/beneficios",
    response_model=BeneficioOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Funcionários"],
)
async def associar_beneficio(
    funcionario_id: int,
    body: AssociarBeneficioIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    func_ = await db.get(Funcionario, funcionario_id)
    if not func_:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")

    ben = await db.get(Beneficio, body.beneficio_id)
    if not ben or not ben.ativo:
        raise HTTPException(status_code=404, detail="Benefício não encontrado ou inativo.")

    existing = await db.execute(
        select(FuncionarioBeneficio).where(
            FuncionarioBeneficio.funcionario_id == funcionario_id,
            FuncionarioBeneficio.beneficio_id == body.beneficio_id,
            FuncionarioBeneficio.ativo == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Benefício já associado a este funcionário.")

    assoc = FuncionarioBeneficio(funcionario_id=funcionario_id, beneficio_id=body.beneficio_id)
    db.add(assoc)
    await db.flush()
    return ben


@router_beneficios.delete(
    "/funcionarios/{funcionario_id}/beneficios/{beneficio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Funcionários"],
)
async def desassociar_beneficio(
    funcionario_id: int,
    beneficio_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.execute(
        select(FuncionarioBeneficio).where(
            FuncionarioBeneficio.funcionario_id == funcionario_id,
            FuncionarioBeneficio.beneficio_id == beneficio_id,
            FuncionarioBeneficio.ativo == True,
        )
    )
    assoc = result.scalar_one_or_none()
    if not assoc:
        raise HTTPException(status_code=404, detail="Associação não encontrada.")
    assoc.ativo = False
    await db.flush()
