"""Tests de las invariantes pre-output."""

from __future__ import annotations

from datetime import date

import pytest

from quimibond.config_loader import Config
from quimibond.models import (
    ArbitrageProjection,
    Classification,
    Company,
    FatigueScore,
    LeverScores,
    PERoleType,
    PipelineData,
)
from quimibond.validation import InvariantViolation, assert_invariants


def _make_company(
    *,
    emis_id: str = "X1",
    pe_role: PERoleType = "PRIMARY_BOLT_ON",
    revenue: float | None = 20.0,
    employees: int | None = 200,
    levers_combined: float = 0.6,
    is_foreign: bool = False,
    arbitrage: ArbitrageProjection | None = None,
    classification: Classification | None = None,
) -> Company:
    if classification is None:
        classification = Classification(
            subsector="no_tejidos",
            subsector_priority="Crítica",
            is_foreign_subsidiary=is_foreign,
            capital_origin="Subsidiaria/Extranjera" if is_foreign else "Familiar/MX",
        )
    if arbitrage is None and revenue is not None and revenue > 0:
        ebitda = revenue * 0.12
        arbitrage = ArbitrageProjection(
            buy_multiple=6.0,
            exit_multiple=9.0,
            ebitda_estimate_usd_mm=ebitda,
            ev_buy_usd_mm=ebitda * 6.0,
            ev_exit_usd_mm=ebitda * 9.0,
            moic=9.0 / 6.0,
            irr=0.0845,
            hold_period_years=5,
        )

    return Company(
        emis_id=emis_id,
        company_name=f"Co {emis_id}",
        source="EMIS",
        source_as_of=date(2026, 4, 30),
        revenue_usd_mm=revenue,
        employees=employees,
        classification=classification,
        pe_role=pe_role,
        pe_role_justification="test",
        fatigue=FatigueScore(score=0.3, justification="test"),
        levers=LeverScores(
            cost=0.6,
            revenue=0.6,
            arbitrage=0.6,
            combined=levers_combined,
            cost_justification="x",
            revenue_justification="x",
            arbitrage_justification="x",
        ),
        arbitrage=arbitrage,
        is_foreign_subsidiary=is_foreign,
    )


def _data(*companies: Company) -> PipelineData:
    return PipelineData(companies=companies, generated_at=date(2026, 4, 30))


def test_passes_with_valid(config: Config) -> None:
    c = _make_company()
    assert_invariants(_data(c), config)


def test_duplicate_emis_id_raises(config: Config) -> None:
    c1 = _make_company(emis_id="X1")
    c2 = _make_company(emis_id="X1")
    with pytest.raises(InvariantViolation, match="duplicado"):
        assert_invariants(_data(c1, c2), config)


def test_lever_combined_above_one_raises_via_pydantic() -> None:
    """LeverScores valida 0..1 en construction — esta invariante actúa de defensa."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LeverScores(
            cost=0.5, revenue=0.5, arbitrage=0.5, combined=1.5,
            cost_justification="x", revenue_justification="x", arbitrage_justification="x",
        )


def test_strategic_must_be_foreign_raises(config: Config) -> None:
    """Si pe_role=STRATEGIC pero no es foreign, es bug del classifier."""
    c = _make_company(pe_role="STRATEGIC", is_foreign=False)
    with pytest.raises(InvariantViolation, match="STRATEGIC"):
        assert_invariants(_data(c), config)


def test_platform_below_threshold_raises(config: Config) -> None:
    """PLATFORM_CANDIDATE con revenue por debajo del umbral debe fallar."""
    c = _make_company(pe_role="PLATFORM_CANDIDATE", revenue=10.0, employees=10)
    with pytest.raises(InvariantViolation, match="PLATFORM_CANDIDATE"):
        assert_invariants(_data(c), config)


def test_combined_above_role_cap_raises(config: Config) -> None:
    """STRATEGIC con combined > cap debe fallar."""
    # Construir empresa STRATEGIC válida pero con combined alto.
    c = _make_company(
        pe_role="STRATEGIC",
        is_foreign=True,
        levers_combined=0.50,  # excede cap 0.30 de STRATEGIC
    )
    with pytest.raises(InvariantViolation, match="cap"):
        assert_invariants(_data(c), config)


def test_arbitrage_inconsistent_ebitda_raises(config: Config) -> None:
    """Si ebitda_estimate no es revenue * margin → fallo."""
    bad_arb = ArbitrageProjection(
        buy_multiple=6.0,
        exit_multiple=9.0,
        ebitda_estimate_usd_mm=999.0,  # incorrecto
        ev_buy_usd_mm=999.0 * 6,
        ev_exit_usd_mm=999.0 * 9,
        moic=1.5,
        irr=0.0845,
        hold_period_years=5,
    )
    c = _make_company(revenue=20.0, arbitrage=bad_arb)
    with pytest.raises(InvariantViolation, match="ebitda_estimate"):
        assert_invariants(_data(c), config)


def test_arbitrage_none_when_no_revenue(config: Config) -> None:
    c = _make_company(revenue=None, arbitrage=None, employees=200,
                      pe_role="UNKNOWN_FIT", levers_combined=0.4)
    assert_invariants(_data(c), config)


def test_arbitrage_present_with_no_revenue_raises(config: Config) -> None:
    """Si revenue=None pero arbitrage existe → bug."""
    arb = ArbitrageProjection(
        buy_multiple=6.0, exit_multiple=9.0,
        ebitda_estimate_usd_mm=2.4,
        ev_buy_usd_mm=14.4, ev_exit_usd_mm=21.6,
        moic=1.5, irr=0.0845, hold_period_years=5,
    )
    c = _make_company(revenue=None, arbitrage=arb,
                      employees=200, pe_role="UNKNOWN_FIT",
                      levers_combined=0.4)
    with pytest.raises(InvariantViolation, match="arbitrage"):
        assert_invariants(_data(c), config)
