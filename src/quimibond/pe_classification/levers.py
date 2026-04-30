"""
Tres palancas de creación de valor + score combinado.

- Cost lever (operación): potencial de captura de sinergias por integración
  con la operación de Quimibond (procesos compartidos, escala fija, compras).
- Revenue lever (comercial): potencial de cross-sell y upgrade de cliente
  (acceso a Tier-1 automotriz vía la plataforma).
- Arbitrage lever (financiero): re-rating del múltiplo por consolidación.

Cada palanca devuelve score ∈ [0, 1] + justificación. El combined es
weighted avg de los tres (pesos del playbook), capeado por role_combined_cap
del playbook (STRATEGIC nunca pasa 0.30, etc.).
"""

from __future__ import annotations

from quimibond.config_loader import Config
from quimibond.models import (
    Classification,
    LeverScores,
    PERoleType,
    RawCompany,
)


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _score_cost(raw: RawCompany, classification: Classification) -> tuple[float, str]:
    """
    Cost: empresas familiares MX con procesos compartidos con Quimibond son las
    de mayor palanca. Las grandes ya tienen escala propia (menos delta), las
    chicas (<10 emp) son demasiado boutique para integrar costos.
    """
    score = 0.50  # base neutral
    reasons: list[str] = []

    if classification.is_familiar_mx:
        score += 0.20
        reasons.append("familiar/MX (cap. concentrada, decisiones rápidas)")
    elif classification.capital_origin == "Privado/MX":
        score += 0.10
        reasons.append("privado/MX")
    elif classification.capital_origin == "Cooperativa":
        score -= 0.10
        reasons.append("cooperativa (gobernanza distribuida, palanca menor)")
    elif classification.capital_origin == "Público":
        score -= 0.20
        reasons.append("público (gobernanza pública, integración compleja)")

    if classification.quimibond_processes:
        score += 0.20
        reasons.append(
            f"procesos compartidos con Quimibond: {', '.join(classification.quimibond_processes)}"
        )
    else:
        score -= 0.05
        reasons.append("sin procesos compartidos detectados")

    emps = raw.employees
    if emps is not None:
        if emps < 10:
            score -= 0.15
            reasons.append(f"muy chica ({emps} emp), poca palanca de costos")
        elif 50 <= emps <= 500:
            score += 0.10
            reasons.append(f"tamaño mid-market ({emps} emp), sweet spot")
        elif emps > 1000:
            score -= 0.05
            reasons.append(f"grande ({emps} emp), economías propias ya")

    return _clip(score), " · ".join(reasons) or "neutral"


def _score_revenue(raw: RawCompany, classification: Classification) -> tuple[float, str]:
    """
    Revenue: cuánto puede crecer en ingresos al integrarse con Quimibond
    Capital y abrir su libro de clientes (Tier-1 automotriz, exporters).
    """
    score = 0.40  # base
    reasons: list[str] = []

    if classification.subsector_priority == "Crítica":
        score += 0.25
        reasons.append("subsector Crítica")
    elif classification.subsector_priority == "Alta":
        score += 0.15
        reasons.append("subsector Alta")
    elif classification.subsector_priority == "Baja":
        score -= 0.15
        reasons.append("subsector Baja")

    client = classification.main_client_type
    if client == "Automotriz":
        score += 0.20
        reasons.append("cliente automotriz (tesis core)")
    elif client == "Industrial":
        score += 0.10
        reasons.append("cliente industrial")
    elif client == "Médico/Higiene":
        score += 0.10
        reasons.append("cliente médico/higiene")
    elif client == "Mixto":
        score += 0.05
        reasons.append("clientes mixtos")
    elif client == "Apparel":
        score -= 0.10
        reasons.append("cliente apparel (margen y estabilidad menores)")

    if raw.is_exporter is True:
        score += 0.10
        reasons.append("exporter (acceso a clientes internacionales validados)")

    return _clip(score), " · ".join(reasons) or "neutral"


def _arbitrage_score(
    raw: RawCompany,
    classification: Classification,
) -> tuple[float, str]:
    """
    Arbitrage: probabilidad de cerrar a múltiplo bajo y revender a múltiplo
    consolidado. Tamaños pequeños/medianos privados familiares son sweet spot.
    """
    score = 0.40
    reasons: list[str] = []

    rev = raw.revenue_usd_mm
    if rev is None:
        score = 0.50  # neutral, no penalizar pero tampoco premiar sin info
        reasons.append("sin revenue declarado (neutral)")
    else:
        # Sweet spot bolt-on
        if 10 <= rev < 50:
            score += 0.30
            reasons.append(f"revenue ${rev:.0f}M en bolt-on sweet spot")
        elif 50 <= rev < 150:
            score += 0.20
            reasons.append(f"revenue ${rev:.0f}M en platform range")
        elif 1 <= rev < 10:
            score += 0.15
            reasons.append(f"revenue ${rev:.0f}M en tuck-in")
        elif rev >= 150:
            score += 0.05
            reasons.append(f"revenue ${rev:.0f}M grande (poco re-rating upside)")
        else:
            score -= 0.20
            reasons.append(f"revenue ${rev:.2f}M sub-escala")

    if classification.is_familiar_mx:
        score += 0.15
        reasons.append("familiar MX (más probable cerrar a múltiplo bajo)")
    if classification.is_foreign_subsidiary:
        score = min(score, 0.20)
        reasons.append("subsidiaria extranjera (rara vez se compra a múltiplo bajo)")

    if classification.subsector_priority == "Crítica":
        score += 0.10
        reasons.append("subsector Crítica (mayor re-rating al consolidar)")

    return _clip(score), " · ".join(reasons) or "neutral"


def compute_levers(
    raw: RawCompany,
    classification: Classification,
    pe_role: PERoleType,
    config: Config,
) -> LeverScores:
    cost, cost_just = _score_cost(raw, classification)
    revenue, revenue_just = _score_revenue(raw, classification)
    arbitrage, arbitrage_just = _arbitrage_score(raw, classification)

    weights = config.pe_playbook.scoring_weights
    combined = (
        weights.lever_cost * cost
        + weights.lever_revenue * revenue
        + weights.lever_arbitrage * arbitrage
    )

    cap = config.pe_playbook.role_combined_cap.get(pe_role, 1.0)
    combined = min(combined, cap)
    combined = _clip(combined)

    return LeverScores(
        cost=cost,
        revenue=revenue,
        arbitrage=arbitrage,
        combined=combined,
        cost_justification=cost_just,
        revenue_justification=revenue_just,
        arbitrage_justification=arbitrage_just,
    )
