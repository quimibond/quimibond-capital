"""
Orquestador del pipeline de clasificación PE.

`build_company(raw, config, today)` toma un RawCompany ya enriquecido vía
`derive_classification` y produce un `Company` completo (con role, fatigue,
levers, arbitrage). Es la pieza que une enrichment con classification.

`classify_universe(raws, config, today)` aplica build_company a una secuencia
y además calcula saturación por subsector (que depende del agregado).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import structlog

from quimibond.config_loader import Config
from quimibond.enrichment import (
    build_location_label,
    compute_age_years,
    compute_productivity_usd_per_employee,
    derive_classification,
    is_edad_madura,
)
from quimibond.models import (
    Classification,
    Company,
    PipelineData,
    RawCompany,
    SaturationVerdict,
)
from quimibond.pe_classification.arbitrage import project_arbitrage
from quimibond.pe_classification.fatigue import score_owner_fatigue
from quimibond.pe_classification.levers import compute_levers
from quimibond.pe_classification.role import classify_role
from quimibond.pe_classification.saturation import analyze_saturation

log = structlog.get_logger()


def build_company(
    raw: RawCompany,
    config: Config,
    today: date,
) -> tuple[Company, Classification]:
    """
    Toma un RawCompany y devuelve (Company enriquecido + Classification).

    La Classification se devuelve también porque saturation la consume del
    agregado — y construirla dos veces es desperdicio.
    """
    classification = derive_classification(raw, config)

    age = compute_age_years(raw.incorporation_year, today)
    productivity = compute_productivity_usd_per_employee(raw.revenue_usd_mm, raw.employees)
    location = build_location_label(raw.municipality, raw.state, raw.city)

    role_assignment = classify_role(raw, classification, config.thresholds)
    fatigue = score_owner_fatigue(raw, classification, config.thresholds, age_years=age)
    levers = compute_levers(raw, classification, role_assignment.role, config)
    arbitrage = project_arbitrage(raw.revenue_usd_mm, config.pe_playbook)

    ebitda_estimate = (
        raw.revenue_usd_mm * config.pe_playbook.ebitda_margin_default
        if raw.revenue_usd_mm is not None
        else None
    )

    company = Company(
        emis_id=raw.source_id,
        company_name=raw.company_name,
        legal_name=raw.legal_name,
        rfc=raw.rfc,
        source=raw.source,
        source_as_of=raw.source_as_of,
        state=raw.state,
        municipality=raw.municipality,
        location_label=location,
        revenue_usd_mm=raw.revenue_usd_mm,
        revenue_year=raw.revenue_year,
        employees=raw.employees,
        incorporation_year=raw.incorporation_year,
        age_years=age,
        productivity_usd_per_employee=productivity,
        ebitda_estimate_usd_mm=ebitda_estimate,
        classification=classification,
        pe_role=role_assignment.role,
        pe_role_justification=role_assignment.justification,
        fatigue=fatigue,
        levers=levers,
        arbitrage=arbitrage,
        is_familiar_mx=classification.is_familiar_mx,
        is_foreign_subsidiary=classification.is_foreign_subsidiary,
        edad_madura=is_edad_madura(age, config.thresholds.age_thresholds.edad_madura_min),
    )
    return company, classification


def classify_universe(
    raws: Sequence[RawCompany],
    config: Config,
    today: date,
) -> PipelineData:
    """
    Pipeline completo: para cada RawCompany construye Company y calcula
    saturación agregada por subsector.
    """
    log.info("classify.universe.start", n=len(raws), today=today.isoformat())

    pairs: list[tuple[RawCompany, Classification]] = []
    companies: list[Company] = []

    for raw in raws:
        company, classification = build_company(raw, config, today)
        companies.append(company)
        pairs.append((raw, classification))

    saturation: tuple[SaturationVerdict, ...] = analyze_saturation(
        pairs, config.thresholds
    )

    log.info(
        "classify.universe.done",
        n=len(companies),
        n_subsectors=len(saturation),
    )

    # Orden estable: por emis_id ascendente para idempotencia byte-level.
    companies_sorted = tuple(sorted(companies, key=lambda c: c.emis_id))

    return PipelineData(
        companies=companies_sorted,
        saturation=saturation,
        generated_at=today,
    )


__all__ = [
    "build_company",
    "classify_universe",
    "compute_levers",
    "project_arbitrage",
    "score_owner_fatigue",
    "classify_role",
    "analyze_saturation",
]
