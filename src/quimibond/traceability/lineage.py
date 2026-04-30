"""
Trazabilidad por celda: añade comentarios openpyxl a celdas calculadas para
explicar de dónde sale cada número.

Uso:
    from quimibond.traceability.lineage import apply_lineage_to_cell

    lineage = CellLineage(
        value=lever.combined,
        source="calculated",
        formula="weighted_avg(cost,revenue,arbitrage) capped by role",
        inputs=("cost", "revenue", "arbitrage", "role_combined_cap"),
    )
    apply_lineage_to_cell(cell, lineage, author="quimibond-pipeline")

El comment es un texto multi-línea que aparece al pasar el mouse sobre la
celda en Excel/LibreOffice.
"""

from __future__ import annotations

from openpyxl.cell.cell import Cell
from openpyxl.comments import Comment

from quimibond.models import (
    ArbitrageProjection,
    CellLineage,
    Company,
    LeverScores,
)

DEFAULT_AUTHOR = "quimibond-pipeline"
COMMENT_WIDTH = 280
COMMENT_HEIGHT = 120


def format_lineage(lineage: CellLineage) -> str:
    """Formatea CellLineage como texto multi-línea legible."""
    lines: list[str] = []
    lines.append(f"Valor: {lineage.value}")
    lines.append(f"Origen: {lineage.source}")
    if lineage.formula:
        lines.append(f"Fórmula: {lineage.formula}")
    if lineage.inputs:
        lines.append(f"Inputs: {', '.join(lineage.inputs)}")
    return "\n".join(lines)


def apply_lineage_to_cell(
    cell: Cell,
    lineage: CellLineage,
    *,
    author: str = DEFAULT_AUTHOR,
) -> None:
    """Adjunta un comment openpyxl a la celda con el detalle del lineage."""
    text = format_lineage(lineage)
    comment = Comment(text=text, author=author)
    comment.width = COMMENT_WIDTH
    comment.height = COMMENT_HEIGHT
    cell.comment = comment


# ---------------------------------------------------------------------------
# Builders especializados — generan CellLineage para campos comunes del pipeline
# ---------------------------------------------------------------------------


def lineage_for_lever_combined(company: Company) -> CellLineage:
    """Lineage del combined score: weighted avg de los tres palancas + cap."""
    ls = company.levers
    formula = (
        f"min(role_cap, "
        f"weights.cost*{ls.cost:.2f} + weights.revenue*{ls.revenue:.2f} + "
        f"weights.arbitrage*{ls.arbitrage:.2f})"
    )
    return CellLineage(
        value=round(ls.combined, 4),
        source="calculated",
        formula=formula,
        inputs=("levers.cost", "levers.revenue", "levers.arbitrage",
                "playbook.scoring_weights", "playbook.role_combined_cap", "pe_role"),
    )


def lineage_for_lever_axis(
    axis: str,
    score: float,
    justification: str,
) -> CellLineage:
    """Lineage para una palanca individual (cost/revenue/arbitrage)."""
    return CellLineage(
        value=round(score, 4),
        source="calculated",
        formula=f"score_{axis}(raw, classification) — ver justificación adjunta",
        inputs=("classification", "raw", justification[:60]),
    )


def lineage_for_arbitrage_field(
    company: Company,
    field: str,
) -> CellLineage:
    """Lineage para un campo de ArbitrageProjection."""
    arb = company.arbitrage
    if arb is None:
        return CellLineage(
            value=None,
            source="calculated",
            formula="N/A — sin revenue declarado",
            inputs=(),
        )
    formula_map = {
        "ebitda_estimate_usd_mm": "revenue * playbook.ebitda_margin_default",
        "ev_buy_usd_mm": "ebitda * buy_multiple",
        "ev_exit_usd_mm": "ebitda * exit_multiple",
        "moic": "ev_exit / ev_buy",
        "irr": "moic^(1/hold_period_years) - 1",
        "buy_multiple": "lookup en playbook.buy_multiples_by_size por revenue",
        "exit_multiple": "playbook.exit_multiple_default",
    }
    return CellLineage(
        value=getattr(arb, field, None),
        source="calculated",
        formula=formula_map.get(field, field),
        inputs=("revenue_usd_mm", "playbook.ebitda_margin_default",
                "playbook.exit_multiple_default", "playbook.buy_multiples_by_size",
                "playbook.hold_period_years"),
    )


def lineage_for_fatigue(company: Company) -> CellLineage:
    """Lineage para fatigue score: detalla las señales detectadas."""
    return CellLineage(
        value=round(company.fatigue.score, 4),
        source="calculated",
        formula="sum(signal_weights) clamped to [0,1]",
        inputs=("age_years", "is_familiar_mx", "capital_origin",
                "website", "employees") + company.fatigue.signals,
    )


def lineage_for_role(company: Company) -> CellLineage:
    """Lineage para pe_role asignado."""
    return CellLineage(
        value=company.pe_role,
        source="calculated",
        formula=company.pe_role_justification,
        inputs=("revenue_usd_mm", "employees", "subsector_priority",
                "is_foreign_subsidiary"),
    )
