from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator, model_validator
import re

from app.models.models import TipoBeneficio, StatusFuncionario, StatusFolha


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mascarar_cpf(cpf: str) -> str:
    """Retorna CPF mascarado: ***.***.XXX-XX"""
    cpf = re.sub(r"\D", "", cpf)
    if len(cpf) == 11:
        return f"***.***.{cpf[6:9]}-{cpf[9:]}"
    return "***.***.***-**"


def _validar_cpf_raw(cpf: str) -> str:
    """Remove formatação e valida 11 dígitos."""
    cpf = re.sub(r"\D", "", cpf)
    if len(cpf) != 11:
        raise ValueError("CPF deve ter 11 dígitos.")
    return cpf


# ---------------------------------------------------------------------------
# Cargo
# ---------------------------------------------------------------------------

class CargoBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    salario_minimo: Decimal
    salario_maximo: Decimal

    @model_validator(mode="after")
    def salario_valido(self):
        if self.salario_minimo > self.salario_maximo:
            raise ValueError("salario_minimo não pode ser maior que salario_maximo.")
        return self


class CargoCreate(CargoBase):
    pass


class CargoUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    salario_minimo: Optional[Decimal] = None
    salario_maximo: Optional[Decimal] = None
    ativo: Optional[bool] = None


class CargoOut(CargoBase):
    id: int
    ativo: bool
    criado_em: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Benefício
# ---------------------------------------------------------------------------

class BeneficioBase(BaseModel):
    nome: str
    tipo: TipoBeneficio
    valor: Decimal
    descricao: Optional[str] = None


class BeneficioCreate(BeneficioBase):
    pass


class BeneficioUpdate(BaseModel):
    nome: Optional[str] = None
    tipo: Optional[TipoBeneficio] = None
    valor: Optional[Decimal] = None
    descricao: Optional[str] = None
    ativo: Optional[bool] = None


class BeneficioOut(BeneficioBase):
    id: int
    ativo: bool
    criado_em: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Funcionário
# ---------------------------------------------------------------------------

class FuncionarioCreate(BaseModel):
    nome: str
    cpf: str
    email: Optional[str] = None
    departamento: str
    cargo_id: int
    salario_base: Decimal
    data_admissao: date

    @field_validator("cpf", mode="before")
    @classmethod
    def validar_cpf(cls, v):
        return _validar_cpf_raw(str(v))


class FuncionarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    departamento: Optional[str] = None
    cargo_id: Optional[int] = None
    salario_base: Optional[Decimal] = None
    status: Optional[StatusFuncionario] = None


class FuncionarioOut(BaseModel):
    id: int
    nome: str
    cpf: str          # já mascarado pelo service
    email: Optional[str]
    departamento: str
    cargo_id: int
    salario_base: Decimal
    data_admissao: date
    status: StatusFuncionario
    criado_em: datetime

    model_config = {"from_attributes": True}


class FuncionarioDetalhe(FuncionarioOut):
    cargo: CargoOut
    beneficios: List[BeneficioOut] = []


# ---------------------------------------------------------------------------
# Paginação
# ---------------------------------------------------------------------------

class FuncionarioListOut(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: List[FuncionarioOut]


# ---------------------------------------------------------------------------
# Holerite / Folha
# ---------------------------------------------------------------------------

class HoleriteOut(BaseModel):
    id: int
    funcionario_id: int
    funcionario_nome: str
    cpf_mascarado: str
    salario_base: Decimal
    total_beneficios: Decimal
    inss: Decimal
    irrf: Decimal
    total_descontos: Decimal
    salario_liquido: Decimal

    model_config = {"from_attributes": True}


class FolhaOut(BaseModel):
    id: int
    ano: int
    mes: int
    status: StatusFolha
    total_bruto: Optional[Decimal]
    total_descontos: Optional[Decimal]
    total_liquido: Optional[Decimal]
    calculado_em: Optional[datetime]
    fechado_em: Optional[datetime]
    holerites: List[HoleriteOut] = []

    model_config = {"from_attributes": True}


class FolhaSummary(BaseModel):
    id: int
    ano: int
    mes: int
    status: StatusFolha
    total_bruto: Optional[Decimal]
    total_liquido: Optional[Decimal]
    calculado_em: Optional[datetime]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Histórico Salarial
# ---------------------------------------------------------------------------

class HistoricoSalarialOut(BaseModel):
    id: int
    salario_anterior: Decimal
    salario_novo: Decimal
    motivo: Optional[str]
    alterado_em: datetime
    alterado_por: Optional[str]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Associação Funcionário ↔ Benefício
# ---------------------------------------------------------------------------

class AssociarBeneficioIn(BaseModel):
    beneficio_id: int
