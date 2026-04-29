"""
Tests de los pydantic models. Verifican constraints y la inmutabilidad.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from quimibond.models import (
    ArbitrageProjection,
    CellLineage,
    Classification,
    Company,
    FatigueScore,
    LeverScores,
    PipelineData,
    RawCompany,
    SaturationVerdict,
)


class TestRawCompany:
    def test_minimal_raw_company_valid(self) -> None:
        c = RawCompany(
            source_id="X1",
            source="EMIS",
            source_as_of=date(2026, 4, 29),
            company_name="Acme Textil",
        )
        assert c.country == "MX"
        assert c.export_destinations == ()

    def test_company_name_required(self) -> None:
        with pytest.raises(ValidationError):
            RawCompany(
                source_id="X1",
                source="EMIS",
                source_as_of=date(2026, 4, 29),
                company_name="",
            )

    def test_naics_normalized_to_string(self) -> None:
        c = RawCompany(
            source_id="X1",
            source="EMIS",
            source_as_of=date(2026, 4, 29),
            company_name="Acme",
            naics=3149,  # type: ignore[arg-type]
        )
        assert c.naics == "3149"

    def test_naics_blank_becomes_none(self) -> None:
        c = RawCompany(
            source_id="X1",
            source="EMIS",
            source_as_of=date(2026, 4, 29),
            company_name="Acme",
            naics="   ",
        )
        assert c.naics is None

    def test_employees_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RawCompany(
                source_id="X1",
                source="EMIS",
                source_as_of=date(2026, 4, 29),
                company_name="Acme",
                employees=-1,
            )

    def test_ebitda_margin_clamped(self) -> None:
        with pytest.raises(ValidationError):
            RawCompany(
                source_id="X1",
                source="EMIS",
                source_as_of=date(2026, 4, 29),
                company_name="Acme",
                ebitda_margin=2.0,
            )

    def test_frozen(self, sample_raw_company: RawCompany) -> None:
        with pytest.raises(ValidationError):
            sample_raw_company.company_name = "OTRO"  # type: ignore[misc]


class TestFatigueScore:
    def test_score_range(self) -> None:
        with pytest.raises(ValidationError):
            FatigueScore(score=1.5, justification="x")

    def test_default_signals(self) -> None:
        f = FatigueScore(score=0.0, justification="x")
        assert f.signals == ()


class TestLeverScores:
    def test_combined_required(self) -> None:
        ls = LeverScores(
            cost=0.5,
            revenue=0.5,
            arbitrage=0.5,
            combined=0.5,
            cost_justification="a",
            revenue_justification="b",
            arbitrage_justification="c",
        )
        assert ls.combined == 0.5

    def test_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LeverScores(
                cost=1.1,
                revenue=0.5,
                arbitrage=0.5,
                combined=0.7,
                cost_justification="a",
                revenue_justification="b",
                arbitrage_justification="c",
            )


class TestArbitrageProjection:
    def test_basic(self) -> None:
        a = ArbitrageProjection(
            buy_multiple=4.5,
            exit_multiple=9.0,
            ebitda_estimate_usd_mm=2.0,
            ev_buy_usd_mm=9.0,
            ev_exit_usd_mm=18.0,
            moic=2.0,
            irr=0.149,
            hold_period_years=5,
        )
        assert a.moic == 2.0


class TestSaturationVerdict:
    def test_basic(self) -> None:
        s = SaturationVerdict(
            subsegment="No tejidos",
            total_companies=100,
            consolidated=20,
            accessible=80,
            verdict="Atractivo",
        )
        assert s.verdict == "Atractivo"


class TestCompany:
    def test_company_holds_classification(self, sample_company: Company) -> None:
        assert sample_company.classification.subsector == "No tejidos"
        assert sample_company.pe_role == "PRIMARY_BOLT_ON"
        assert sample_company.is_familiar_mx is True

    def test_invalid_pe_role_rejected(self, sample_company: Company) -> None:
        bad = sample_company.model_dump()
        bad["pe_role"] = "BAD_ROLE"
        with pytest.raises(ValidationError):
            Company.model_validate(bad)

    def test_negative_age_rejected(self, sample_company: Company) -> None:
        bad = sample_company.model_dump()
        bad["age_years"] = -1
        with pytest.raises(ValidationError):
            Company.model_validate(bad)


class TestPipelineData:
    def test_n_companies(self, sample_company: Company) -> None:
        pd = PipelineData(
            companies=(sample_company,),
            generated_at=date(2026, 4, 29),
        )
        assert pd.n_companies == 1


class TestClassificationDefaults:
    def test_defaults(self) -> None:
        c = Classification(subsector="X", subsector_priority="Media")
        assert c.is_familiar_mx is False
        assert c.detected_family is None
        assert c.main_client_type == "Desconocido"


class TestCellLineage:
    def test_basic(self) -> None:
        cl = CellLineage(value=42, source="calculated", inputs=("revenue", "ebitda"))
        assert cl.inputs == ("revenue", "ebitda")
