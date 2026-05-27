import json
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    FolhaPagamento, Funcionario, FuncionarioBeneficio,
    Holerite, StatusFolha, StatusFuncionario,
)
from app.schemas.schemas import FolhaOut, FolhaSummary, HoleriteOut, _mascarar_cpf
from app.services.calculo_folha import calcular_holerite

router = APIRouter(prefix="/rh", tags=["Folha de Pagamento"])


def _holerite_to_out(h: Holerite) -> HoleriteOut:
    return HoleriteOut(
        id=h.id,
        funcionario_id=h.funcionario_id,
        funcionario_nome=h.funcionario.nome,
        cpf_mascarado=_mascarar_cpf(h.funcionario.cpf),
        salario_base=h.salario_base,
        total_beneficios=h.total_beneficios,
        inss=h.inss,
        irrf=h.irrf,
        total_descontos=h.total_descontos,
        salario_liquido=h.salario_liquido,
    )


# ---------------------------------------------------------------------------
# POST /rh/folha/{ano}/{mes} — Calcular folha
# ---------------------------------------------------------------------------

@router.post("/folha/{ano}/{mes}", response_model=FolhaSummary, status_code=status.HTTP_201_CREATED)
async def calcular_folha(
    ano: int,
    mes: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=422, detail="Mês inválido (1-12).")

    # Verificar se já existe folha fechada (imutável — RNF02)
    result = await db.execute(
        select(FolhaPagamento).where(
            FolhaPagamento.ano == ano,
            FolhaPagamento.mes == mes,
        )
    )
    folha_existente = result.scalar_one_or_none()
    if folha_existente and folha_existente.status == StatusFolha.FECHADA:
        raise HTTPException(
            status_code=409,
            detail="Folha já fechada. Não pode ser recalculada (RNF02).",
        )

    # Buscar funcionários ativos com seus benefícios
    func_result = await db.execute(
        select(Funcionario)
        .options(selectinload(Funcionario.beneficios).selectinload(FuncionarioBeneficio.beneficio))
        .where(Funcionario.status == StatusFuncionario.ATIVO)
    )
    funcionarios = func_result.scalars().all()

    if not funcionarios:
        raise HTTPException(status_code=422, detail="Nenhum funcionário ativo para calcular folha.")

    # Criar ou reutilizar folha
    if not folha_existente:
        folha = FolhaPagamento(ano=ano, mes=mes, status=StatusFolha.ABERTA)
        db.add(folha)
        await db.flush()
    else:
        folha = folha_existente
        # Remover holerites anteriores (recálculo em folha aberta)
        await db.execute(
            select(Holerite).where(Holerite.folha_id == folha.id)
        )

    total_bruto = Decimal("0")
    total_descontos = Decimal("0")
    total_liquido = Decimal("0")

    for func_ in funcionarios:
        beneficios_ativos = [fb.beneficio for fb in func_.beneficios if fb.ativo and fb.beneficio.ativo]
        total_beneficios = sum(b.valor for b in beneficios_ativos)

        calc = calcular_holerite(func_.salario_base, total_beneficios)

        # Remover holerite anterior deste funcionário se existir
        h_old = await db.execute(
            select(Holerite).where(
                Holerite.folha_id == folha.id,
                Holerite.funcionario_id == func_.id,
            )
        )
        old = h_old.scalar_one_or_none()
        if old:
            await db.delete(old)
            await db.flush()

        holerite = Holerite(
            folha_id=folha.id,
            funcionario_id=func_.id,
            salario_base=calc["salario_base"],
            total_beneficios=calc["total_beneficios"],
            inss=calc["inss"],
            irrf=calc["irrf"],
            total_descontos=calc["total_descontos"],
            salario_liquido=calc["salario_liquido"],
            detalhes_json=json.dumps({k: str(v) for k, v in calc.items()}),
        )
        db.add(holerite)

        total_bruto += calc["salario_bruto"]
        total_descontos += calc["total_descontos"]
        total_liquido += calc["salario_liquido"]

    folha.total_bruto = total_bruto
    folha.total_descontos = total_descontos
    folha.total_liquido = total_liquido
    folha.calculado_em = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(folha)
    return folha


# ---------------------------------------------------------------------------
# GET /rh/folha/{ano}/{mes} — Listar folha calculada
# ---------------------------------------------------------------------------

@router.get("/folha/{ano}/{mes}", response_model=FolhaOut)
async def listar_folha(
    ano: int,
    mes: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.execute(
        select(FolhaPagamento)
        .options(
            selectinload(FolhaPagamento.holerites).selectinload(Holerite.funcionario)
        )
        .where(FolhaPagamento.ano == ano, FolhaPagamento.mes == mes)
    )
    folha = result.scalar_one_or_none()
    if not folha:
        raise HTTPException(status_code=404, detail="Folha não encontrada para este período.")

    out = FolhaOut.model_validate(folha)
    out.holerites = [_holerite_to_out(h) for h in folha.holerites]
    return out


# ---------------------------------------------------------------------------
# POST /rh/folha/{ano}/{mes}/fechar — Fechar folha (imutável após)
# ---------------------------------------------------------------------------

@router.post("/folha/{ano}/{mes}/fechar", response_model=FolhaSummary)
async def fechar_folha(
    ano: int,
    mes: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.execute(
        select(FolhaPagamento).where(
            FolhaPagamento.ano == ano,
            FolhaPagamento.mes == mes,
        )
    )
    folha = result.scalar_one_or_none()
    if not folha:
        raise HTTPException(status_code=404, detail="Folha não encontrada.")
    if folha.status == StatusFolha.FECHADA:
        raise HTTPException(status_code=409, detail="Folha já está fechada.")

    folha.status = StatusFolha.FECHADA
    folha.fechado_em = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(folha)
    return folha


# ---------------------------------------------------------------------------
# GET /rh/holerite/{func_id}/{ano}/{mes} — Holerite individual
# ---------------------------------------------------------------------------

@router.get("/holerite/{func_id}/{ano}/{mes}", response_model=HoleriteOut)
async def holerite_individual(
    func_id: int,
    ano: int,
    mes: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.execute(
        select(Holerite)
        .options(
            selectinload(Holerite.funcionario),
            selectinload(Holerite.folha),
        )
        .join(FolhaPagamento, Holerite.folha_id == FolhaPagamento.id)
        .where(
            Holerite.funcionario_id == func_id,
            FolhaPagamento.ano == ano,
            FolhaPagamento.mes == mes,
        )
    )
    holerite = result.scalar_one_or_none()
    if not holerite:
        raise HTTPException(
            status_code=404,
            detail="Holerite não encontrado para este funcionário e período.",
        )
    return _holerite_to_out(holerite)
