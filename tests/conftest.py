"""
Fixtures comunes a todos los tests.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from quimibond.config_loader import Config, load_config
from quimibond.models import (
    ArbitrageProjection,
    Classification,
    Company,
    FatigueScore,
    LeverScores,
    RawCompany,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


@pytest.fixture(scope="session")
def config() -> Config:
    """Config real del repo, cargada una sola vez por sesión de tests."""
    return load_config(CONFIG_DIR)


@pytest.fixture
def config_dir() -> Path:
    return CONFIG_DIR


@pytest.fixture
def sample_raw_company() -> RawCompany:
    return RawCompany(
        source_id="EMIS-1234567",
        source="EMIS",
        source_as_of=date(2026, 4, 29),
        company_name="Productora de No Tejidos Quimibond",
        legal_name="Productora de No Tejidos Quimibond S.A. de C.V.",
        rfc="PNT900101AAA",
        naics="3149",
        activity_description="Fabricación de no tejidos para automotriz",
        country="MX",
        state="México",
        municipality="Toluca",
        revenue_usd_mm=42.0,
        revenue_year=2024,
        employees=180,
        incorporation_year=1990,
        is_exporter=True,
        export_destinations=("US", "CA"),
        main_customers=("LEAR", "SHAWMUT"),
        shareholders_text="Familia Quintana — 100%",
    )


@pytest.fixture
def sample_company() -> Company:
    classification = Classification(
        subsector="No tejidos",
        subsector_priority="Crítica",
        quimibond_processes=("acabado",),
        main_client_type="Automotriz",
        capital_origin="Familiar/MX",
        is_familiar_mx=True,
        is_foreign_subsidiary=False,
        detected_family="Quintana",
    )
    return Company(
        emis_id="EMIS-1234567",
        company_name="Productora de No Tejidos Quimibond",
        legal_name="Productora de No Tejidos Quimibond S.A. de C.V.",
        rfc="PNT900101AAA",
        source="EMIS",
        source_as_of=date(2026, 4, 29),
        state="México",
        municipality="Toluca",
        location_label="Toluca, México",
        revenue_usd_mm=42.0,
        revenue_year=2024,
        employees=180,
        incorporation_year=1990,
        age_years=36,
        productivity_usd_per_employee=233333.0,
        ebitda_estimate_usd_mm=5.04,
        classification=classification,
        pe_role="PRIMARY_BOLT_ON",
        pe_role_justification="Revenue $42M en bolt-on range, subsector crítico, familiar MX.",
        fatigue=FatigueScore(score=0.5, signals=("edad>=25",), justification="Edad 36 años."),
        levers=LeverScores(
            cost=0.85,
            revenue=0.70,
            arbitrage=0.65,
            combined=0.74,
            cost_justification="Familiar MX + procesos compartidos.",
            revenue_justification="Cliente automotriz Tier-1.",
            arbitrage_justification="Compra 6x, salida 9x, hold 5y.",
        ),
        arbitrage=ArbitrageProjection(
            buy_multiple=6.0,
            exit_multiple=9.0,
            ebitda_estimate_usd_mm=5.04,
            ev_buy_usd_mm=30.24,
            ev_exit_usd_mm=45.36,
            moic=1.5,
            irr=0.085,
            hold_period_years=5,
        ),
        is_familiar_mx=True,
        is_foreign_subsidiary=False,
        edad_madura=True,
    )
