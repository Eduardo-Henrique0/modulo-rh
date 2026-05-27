from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


# ---------------------------------------------------------------------------
# Cargo
# ---------------------------------------------------------------------------

class Cargo(Base):
    __tablename__ = "cargos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), nullable=False, unique=True)
    descricao = Column(Text, nullable=True)
    salario_minimo = Column(Numeric(12, 2), nullable=False)
    salario_maximo = Column(Numeric(12, 2), nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), onupdate=func.now())

    funcionarios = relationship("Funcionario", back_populates="cargo")


# ---------------------------------------------------------------------------
# Benefício
# ---------------------------------------------------------------------------

class TipoBeneficio(str, PyEnum):
    VR = "VR"
    PLANO_SAUDE = "PLANO_SAUDE"
    VT = "VT"
    OUTRO = "OUTRO"


class Beneficio(Base):
    __tablename__ = "beneficios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), nullable=False)
    tipo = Column(Enum(TipoBeneficio), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    descricao = Column(Text, nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    associacoes = relationship("FuncionarioBeneficio", back_populates="beneficio")


# ---------------------------------------------------------------------------
# Funcionário ↔ Benefício  (tabela associativa)
# ---------------------------------------------------------------------------

class FuncionarioBeneficio(Base):
    __tablename__ = "funcionario_beneficio"

    id = Column(Integer, primary_key=True, index=True)
    funcionario_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=False)
    beneficio_id = Column(Integer, ForeignKey("beneficios.id"), nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("funcionario_id", "beneficio_id", name="uq_func_ben"),
    )

    funcionario = relationship("Funcionario", back_populates="beneficios")
    beneficio = relationship("Beneficio", back_populates="associacoes")


# ---------------------------------------------------------------------------
# Funcionário
# ---------------------------------------------------------------------------

class StatusFuncionario(str, PyEnum):
    ATIVO = "ATIVO"
    INATIVO = "INATIVO"
    AFASTADO = "AFASTADO"


class Funcionario(Base):
    __tablename__ = "funcionarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    cpf = Column(String(11), nullable=False, unique=True)   # armazenado sem máscara
    email = Column(String(200), nullable=True)
    departamento = Column(String(120), nullable=False)
    cargo_id = Column(Integer, ForeignKey("cargos.id"), nullable=False)
    salario_base = Column(Numeric(12, 2), nullable=False)
    data_admissao = Column(Date, nullable=False)
    data_demissao = Column(Date, nullable=True)
    status = Column(Enum(StatusFuncionario), default=StatusFuncionario.ATIVO, nullable=False)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), onupdate=func.now())

    cargo = relationship("Cargo", back_populates="funcionarios")
    beneficios = relationship("FuncionarioBeneficio", back_populates="funcionario")
    historico_salarial = relationship("HistoricoSalarial", back_populates="funcionario")
    holerites = relationship("Holerite", back_populates="funcionario")


# ---------------------------------------------------------------------------
# Folha de Pagamento
# ---------------------------------------------------------------------------

class StatusFolha(str, PyEnum):
    ABERTA = "ABERTA"
    FECHADA = "FECHADA"


class FolhaPagamento(Base):
    __tablename__ = "folhas_pagamento"

    id = Column(Integer, primary_key=True, index=True)
    ano = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)
    status = Column(Enum(StatusFolha), default=StatusFolha.ABERTA, nullable=False)
    total_bruto = Column(Numeric(14, 2), nullable=True)
    total_descontos = Column(Numeric(14, 2), nullable=True)
    total_liquido = Column(Numeric(14, 2), nullable=True)
    calculado_em = Column(DateTime(timezone=True), nullable=True)
    fechado_em = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("ano", "mes", name="uq_folha_ano_mes"),
    )

    holerites = relationship("Holerite", back_populates="folha")


# ---------------------------------------------------------------------------
# Holerite
# ---------------------------------------------------------------------------

class Holerite(Base):
    __tablename__ = "holerites"

    id = Column(Integer, primary_key=True, index=True)
    folha_id = Column(Integer, ForeignKey("folhas_pagamento.id"), nullable=False)
    funcionario_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=False)
    salario_base = Column(Numeric(12, 2), nullable=False)
    total_beneficios = Column(Numeric(12, 2), nullable=False, default=0)
    inss = Column(Numeric(12, 2), nullable=False, default=0)
    irrf = Column(Numeric(12, 2), nullable=False, default=0)
    total_descontos = Column(Numeric(12, 2), nullable=False, default=0)
    salario_liquido = Column(Numeric(12, 2), nullable=False)
    detalhes_json = Column(Text, nullable=True)   # JSON com breakdown completo
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("folha_id", "funcionario_id", name="uq_holerite_folha_func"),
    )

    folha = relationship("FolhaPagamento", back_populates="holerites")
    funcionario = relationship("Funcionario", back_populates="holerites")


# ---------------------------------------------------------------------------
# Histórico Salarial
# ---------------------------------------------------------------------------

class HistoricoSalarial(Base):
    __tablename__ = "historico_salarial"

    id = Column(Integer, primary_key=True, index=True)
    funcionario_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=False)
    salario_anterior = Column(Numeric(12, 2), nullable=False)
    salario_novo = Column(Numeric(12, 2), nullable=False)
    motivo = Column(String(255), nullable=True)
    alterado_em = Column(DateTime(timezone=True), server_default=func.now())
    alterado_por = Column(String(200), nullable=True)   # sub do JWT

    funcionario = relationship("Funcionario", back_populates="historico_salarial")
