import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Funcionario, Cargo, HistoricoSalarial, StatusFuncionario
from app.schemas.schemas import (
    FuncionarioCreate, FuncionarioUpdate, FuncionarioOut,
    FuncionarioDetalhe, FuncionarioListOut, HistoricoSalarialOut,
    _mascarar_cpf,
)

router = APIRouter(prefix="/rh/funcionarios", tags=["Funcionários"])


def _to_out(f: Funcionario) -> FuncionarioOut:
    data = FuncionarioOut.model_validate(f)
    data.cpf = _mascarar_cpf(f.cpf)
    return data


# ---------------------------------------------------------------------------
# GET /rh/funcionarios — Listar com paginação e filtros
# ---------------------------------------------------------------------------

@router.get("", response_model=FuncionarioListOut)
async def listar_funcionarios(
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    nome: Optional[str] = Query(None),
    departamento: Optional[str] = Query(None),
    cargo_id: Optional[int] = Query(None),
    status: Optional[StatusFuncionario] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    query = select(Funcionario)
    if nome:
        query = query.where(Funcionario.nome.ilike(f"%{nome}%"))
    if departamento:
        query = query.where(Funcionario.departamento.ilike(f"%{departamento}%"))
    if cargo_id:
        query = query.where(Funcionario.cargo_id == cargo_id)
    if status:
        query = query.where(Funcionario.status == status)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    offset = (pagina - 1) * por_pagina
    result = await db.execute(query.offset(offset).limit(por_pagina))
    funcionarios = result.scalars().all()

    return FuncionarioListOut(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        items=[_to_out(f) for f in funcionarios],
    )


# ---------------------------------------------------------------------------
# POST /rh/funcionarios — Admitir funcionário
# ---------------------------------------------------------------------------

@router.post("", response_model=FuncionarioOut, status_code=status.HTTP_201_CREATED)
async def admitir_funcionario(
    body: FuncionarioCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    # Verificar se CPF já existe
    existing = await db.execute(
        select(Funcionario).where(Funcionario.cpf == body.cpf)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="CPF já cadastrado.")

    # Verificar cargo
    cargo = await db.get(Cargo, body.cargo_id)
    if not cargo or not cargo.ativo:
        raise HTTPException(status_code=404, detail="Cargo não encontrado ou inativo.")

    # Validar salário dentro da faixa do cargo
    if not (cargo.salario_minimo <= body.salario_base <= cargo.salario_maximo):
        raise HTTPException(
            status_code=422,
            detail=f"Salário fora da faixa do cargo ({cargo.salario_minimo} - {cargo.salario_maximo}).",
        )

    func_ = Funcionario(**body.model_dump())
    db.add(func_)
    await db.flush()
    await db.refresh(func_)
    return _to_out(func_)


# ---------------------------------------------------------------------------
# GET /rh/funcionarios/{id} — Detalhar
# ---------------------------------------------------------------------------

@router.get("/{funcionario_id}", response_model=FuncionarioDetalhe)
async def detalhar_funcionario(
    funcionario_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.execute(
        select(Funcionario)
        .options(
            selectinload(Funcionario.cargo),
            selectinload(Funcionario.beneficios),
        )
        .where(Funcionario.id == funcionario_id)
    )
    func_ = result.scalar_one_or_none()
    if not func_:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")

    out = FuncionarioDetalhe.model_validate(func_)
    out.cpf = _mascarar_cpf(func_.cpf)
    out.beneficios = [b.beneficio for b in func_.beneficios if b.ativo]
    return out


# ---------------------------------------------------------------------------
# PUT /rh/funcionarios/{id} — Atualizar dados
# ---------------------------------------------------------------------------

@router.put("/{funcionario_id}", response_model=FuncionarioOut)
async def atualizar_funcionario(
    funcionario_id: int,
    body: FuncionarioUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    func_ = await db.get(Funcionario, funcionario_id)
    if not func_:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")

    update_data = body.model_dump(exclude_unset=True)

    # Registrar histórico se salário mudou
    if "salario_base" in update_data and update_data["salario_base"] != func_.salario_base:
        historico = HistoricoSalarial(
            funcionario_id=func_.id,
            salario_anterior=func_.salario_base,
            salario_novo=update_data["salario_base"],
            alterado_por=user.get("sub"),
        )
        db.add(historico)

    # Validar faixa salarial se cargo ou salário mudou
    cargo_id = update_data.get("cargo_id", func_.cargo_id)
    salario = update_data.get("salario_base", func_.salario_base)
    cargo = await db.get(Cargo, cargo_id)
    if cargo and not (cargo.salario_minimo <= salario <= cargo.salario_maximo):
        raise HTTPException(
            status_code=422,
            detail=f"Salário fora da faixa do cargo ({cargo.salario_minimo} - {cargo.salario_maximo}).",
        )

    for campo, valor in update_data.items():
        setattr(func_, campo, valor)

    await db.flush()
    await db.refresh(func_)
    return _to_out(func_)


# ---------------------------------------------------------------------------
# DELETE /rh/funcionarios/{id} — Soft delete (desativar)
# ---------------------------------------------------------------------------

@router.delete("/{funcionario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def desativar_funcionario(
    funcionario_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    func_ = await db.get(Funcionario, funcionario_id)
    if not func_:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    func_.status = StatusFuncionario.INATIVO
    await db.flush()


# ---------------------------------------------------------------------------
# GET /rh/funcionarios/{id}/historico-salarial
# ---------------------------------------------------------------------------

@router.get("/{funcionario_id}/historico-salarial", response_model=list[HistoricoSalarialOut])
async def historico_salarial(
    funcionario_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    func_ = await db.get(Funcionario, funcionario_id)
    if not func_:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")

    result = await db.execute(
        select(HistoricoSalarial)
        .where(HistoricoSalarial.funcionario_id == funcionario_id)
        .order_by(HistoricoSalarial.alterado_em.desc())
    )
    return result.scalars().all()
