"""Tests del módulo de trazabilidad por celda."""

from __future__ import annotations

from openpyxl import Workbook

from quimibond.models import (
    ArbitrageProjection,
    CellLineage,
    Company,
    FatigueScore,
    LeverScores,
)
from quimibond.traceability import (
    apply_lineage_to_cell,
    format_lineage,
    lineage_for_arbitrage_field,
    lineage_for_fatigue,
    lineage_for_lever_axis,
    lineage_for_lever_combined,
    lineage_for_role,
)


class TestFormatLineage:
    def test_basic(self) -> None:
        lin = CellLineage(
            value=0.75,
            source="calculated",
            formula="weighted_avg",
            inputs=("cost", "revenue"),
        )
        text = format_lineage(lin)
        assert "Valor: 0.75" in text
        assert "Origen: calculated" in text
        assert "Fórmula: weighted_avg" in text
        assert "Inputs: cost, revenue" in text

    def test_no_formula_skipped(self) -> None:
        lin = CellLineage(value=10, source="raw_emis")
        text = format_lineage(lin)
        assert "Fórmula" not in text
        assert "Inputs" not in text


class TestApplyLineage:
    def test_attaches_comment(self) -> None:
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        cell = ws.cell(row=1, column=1, value=42)
        apply_lineage_to_cell(
            cell,
            CellLineage(value=42, source="calculated", formula="x*y"),
        )
        assert cell.comment is not None
        assert "Valor: 42" in cell.comment.text
        assert cell.comment.author == "quimibond-pipeline"


class TestLineageBuilders:
    def test_lever_combined(self, sample_company: Company) -> None:
        lin = lineage_for_lever_combined(sample_company)
        assert lin.source == "calculated"
        assert lin.value == round(sample_company.levers.combined, 4)
        assert "weights" in (lin.formula or "").lower()

    def test_lever_axis(self) -> None:
        lin = lineage_for_lever_axis("cost", 0.85, "familiar MX + procesos compartidos")
        assert lin.value == 0.85
        assert "score_cost" in (lin.formula or "")

    def test_arbitrage_field_present(self, sample_company: Company) -> None:
        lin = lineage_for_arbitrage_field(sample_company, "moic")
        assert lin.value == sample_company.arbitrage.moic  # type: ignore[union-attr]
        assert "ev_exit / ev_buy" in (lin.formula or "")

    def test_arbitrage_field_when_none(self) -> None:
        c = Company(
            emis_id="X1",
            company_name="X",
            source="EMIS",
            source_as_of=__import__("datetime").date(2026, 4, 30),
            classification=__import__("quimibond.models", fromlist=["Classification"]).Classification(
                subsector="X", subsector_priority="Media",
            ),
            pe_role="UNKNOWN_FIT",
            pe_role_justification="x",
            fatigue=FatigueScore(score=0, justification="x"),
            levers=LeverScores(
                cost=0.5, revenue=0.5, arbitrage=0.5, combined=0.5,
                cost_justification="x", revenue_justification="x",
                arbitrage_justification="x",
            ),
            arbitrage=None,
        )
        lin = lineage_for_arbitrage_field(c, "moic")
        assert lin.value is None
        assert "N/A" in (lin.formula or "")

    def test_fatigue(self, sample_company: Company) -> None:
        lin = lineage_for_fatigue(sample_company)
        assert lin.value == round(sample_company.fatigue.score, 4)
        assert "signal_weights" in (lin.formula or "")

    def test_role(self, sample_company: Company) -> None:
        lin = lineage_for_role(sample_company)
        assert lin.value == sample_company.pe_role
        assert lin.formula == sample_company.pe_role_justification
