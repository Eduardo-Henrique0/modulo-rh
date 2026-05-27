"""
Cálculo de INSS e IRRF simplificados conforme tabelas vigentes (2024).
Regras:
  - INSS progressivo (faixas).
  - IRRF progressivo após dedução do INSS.
"""

from decimal import Decimal, ROUND_HALF_UP


# ---------------------------------------------------------------------------
# Tabela INSS 2024 — faixas progressivas
# (alíquota incide apenas sobre a parcela de cada faixa)
# ---------------------------------------------------------------------------
_FAIXAS_INSS = [
    (Decimal("1412.00"),  Decimal("0.075")),
    (Decimal("2666.68"),  Decimal("0.09")),
    (Decimal("4000.03"),  Decimal("0.12")),
    (Decimal("7786.02"),  Decimal("0.14")),
]
_TETO_INSS = Decimal("7786.02")


def calcular_inss(salario_bruto: Decimal) -> Decimal:
    """Retorna o valor do INSS a descontar."""
    salario = min(salario_bruto, _TETO_INSS)
    inss = Decimal("0")
    anterior = Decimal("0")
    for teto_faixa, aliquota in _FAIXAS_INSS:
        if salario <= anterior:
            break
        base_faixa = min(salario, teto_faixa) - anterior
        inss += base_faixa * aliquota
        anterior = teto_faixa
    return inss.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Tabela IRRF 2024 — faixas progressivas com parcela a deduzir
# ---------------------------------------------------------------------------
_FAIXAS_IRRF = [
    (Decimal("2259.20"),  Decimal("0"),      Decimal("0")),
    (Decimal("2826.65"),  Decimal("0.075"),  Decimal("169.44")),
    (Decimal("3751.05"),  Decimal("0.15"),   Decimal("381.44")),
    (Decimal("4664.68"),  Decimal("0.225"),  Decimal("662.77")),
    (Decimal("9999999"),  Decimal("0.275"),  Decimal("896.00")),
]


def calcular_irrf(base_calculo: Decimal) -> Decimal:
    """
    Recebe a base (salário bruto − INSS) e retorna o IRRF.
    Deduções de dependentes não são implementadas (simplificado).
    """
    irrf = Decimal("0")
    for limite, aliquota, deducao in _FAIXAS_IRRF:
        if base_calculo <= limite:
            irrf = base_calculo * aliquota - deducao
            break
    return max(irrf, Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Cálculo completo de um funcionário
# ---------------------------------------------------------------------------

def calcular_holerite(salario_base: Decimal, total_beneficios: Decimal) -> dict:
    """
    Retorna dict com todos os componentes do holerite.
    """
    salario_bruto = salario_base + total_beneficios
    inss = calcular_inss(salario_base)          # INSS incide apenas sobre salário
    base_irrf = salario_base - inss
    irrf = calcular_irrf(base_irrf)
    total_descontos = inss + irrf
    salario_liquido = salario_bruto - total_descontos

    return {
        "salario_base": salario_base,
        "total_beneficios": total_beneficios,
        "salario_bruto": salario_bruto,
        "inss": inss,
        "base_irrf": base_irrf,
        "irrf": irrf,
        "total_descontos": total_descontos,
        "salario_liquido": salario_liquido,
    }
