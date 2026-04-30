"""Tests del análisis de saturación por subsector."""

from __future__ import annotations

from datetime import date

from quimibond.config_loader import Config
from quimibond.models import Classification, RawCompany
from quimibond.pe_classification.saturation import analyze_saturation


def _pair(
    *,
    name: str = "Co",
    revenue: float | None = None,
    subsector: str = "no_tejidos",
    is_foreign: bool = False,
    capital: str = "Privado/MX",
) -> tuple[RawCompany, Classification]:
    raw = RawCompany(
        source_id=name,
        source="EMIS",
        source_as_of=date(2026, 4, 30),
        company_name=name,
        revenue_usd_mm=revenue,
    )
    clf = Classification(
        subsector=subsector,
        subsector_priority="Crítica",
        is_foreign_subsidiary=is_foreign,
        capital_origin=capital,  # type: ignore[arg-type]
    )
    return raw, clf


def test_few_companies_insuficiente(config: Config) -> None:
    pairs = [_pair(name=f"C{i}") for i in range(3)]  # < min_companies_for_verdict (5)
    results = analyze_saturation(pairs, config.thresholds)
    assert results[0].verdict == "Insuficiente"


def test_atractivo_few_consolidated(config: Config) -> None:
    # 10 empresas, todas privadas pequeñas → 0% consolidado → Atractivo
    pairs = [_pair(name=f"C{i}", revenue=5.0) for i in range(10)]
    results = analyze_saturation(pairs, config.thresholds)
    assert results[0].verdict == "Atractivo"
    assert results[0].consolidated == 0
    assert results[0].accessible == 10


def test_saturado_many_consolidated(config: Config) -> None:
    # 10 empresas, 8 foreign → 80% consolidado → Saturado
    pairs = [
        _pair(name=f"F{i}", is_foreign=True, capital="Subsidiaria/Extranjera")
        for i in range(8)
    ] + [_pair(name=f"P{i}") for i in range(2)]
    results = analyze_saturation(pairs, config.thresholds)
    assert results[0].verdict == "Saturado"


def test_mixto_intermediate(config: Config) -> None:
    # 10 empresas, 4 foreign → 40% consolidado → Mixto
    pairs = [
        _pair(name=f"F{i}", is_foreign=True, capital="Subsidiaria/Extranjera")
        for i in range(4)
    ] + [_pair(name=f"P{i}") for i in range(6)]
    results = analyze_saturation(pairs, config.thresholds)
    assert results[0].verdict == "Mixto"


def test_revenue_above_platform_counts_consolidated(config: Config) -> None:
    """Una empresa con revenue >= platform_min ya es plataforma — consolidada."""
    pairs = [
        _pair(name=f"P{i}", revenue=100.0)  # >= platform_min (50)
        for i in range(8)
    ] + [_pair(name=f"S{i}", revenue=5.0) for i in range(2)]
    results = analyze_saturation(pairs, config.thresholds)
    assert results[0].consolidated == 8
    assert results[0].accessible == 2


def test_multiple_subsectors_sorted(config: Config) -> None:
    pairs: list[tuple[RawCompany, Classification]] = []
    pairs += [_pair(name=f"NT{i}", subsector="no_tejidos") for i in range(6)]
    pairs += [_pair(name=f"AL{i}", subsector="alfombras_floor_mats") for i in range(6)]
    results = analyze_saturation(pairs, config.thresholds)
    # Orden alfabético
    subs = [r.subsegment for r in results]
    assert subs == sorted(subs)
