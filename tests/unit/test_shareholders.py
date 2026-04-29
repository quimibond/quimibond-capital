"""Tests del análisis de accionistas y origen de capital."""

from __future__ import annotations

from datetime import date
from typing import Any

from quimibond.config_loader import Config
from quimibond.enrichment.shareholders import analyze_shareholders
from quimibond.models import RawCompany


def _make_raw(
    shareholders: str | None = None,
    executives: str | None = None,
    extra: dict[str, Any] | None = None,
) -> RawCompany:
    return RawCompany(
        source_id="X1",
        source="EMIS",
        source_as_of=date(2026, 4, 29),
        company_name="Test Co",
        shareholders_text=shareholders,
        executives_text=executives,
        extra=extra or {},
    )


def test_familiar_mx_kalach(config: Config) -> None:
    raw = _make_raw(
        shareholders="Moises Kalach Romano - 35%, Isaac Kalach Mizrahi - 30%",
    )
    a = analyze_shareholders(raw, config.families)
    assert a.capital_origin == "Familiar/MX"
    assert a.is_familiar_mx is True
    assert a.detected_family == "Kalach"


def test_subsidiaria_extranjera_jp(config: Config) -> None:
    raw = _make_raw(
        shareholders="Toray Industries Inc. (JP) - 100%",
    )
    a = analyze_shareholders(raw, config.families)
    assert a.capital_origin == "Subsidiaria/Extranjera"
    assert a.is_foreign_subsidiary is True
    assert a.foreign_country == "JP"


def test_subsidiaria_extranjera_us(config: Config) -> None:
    raw = _make_raw(
        shareholders="Coats Plc (UK) - 100%",
    )
    a = analyze_shareholders(raw, config.families)
    assert a.capital_origin == "Subsidiaria/Extranjera"
    assert a.foreign_country == "UK"


def test_mx_paren_does_not_trigger_foreign(config: Config) -> None:
    raw = _make_raw(
        shareholders="Holding Mexicano (MX) - 100%",
    )
    a = analyze_shareholders(raw, config.families)
    assert a.is_foreign_subsidiary is False


def test_cooperativa(config: Config) -> None:
    raw = _make_raw(
        shareholders="Sociedad Cooperativa de Productores Textiles",
    )
    a = analyze_shareholders(raw, config.families)
    assert a.capital_origin == "Cooperativa"


def test_publico_listed_via_extra(config: Config) -> None:
    raw = _make_raw(
        shareholders="N/A",
        extra={"listed": "Listed"},
    )
    a = analyze_shareholders(raw, config.families)
    assert a.capital_origin == "Público"


def test_publico_via_ticker(config: Config) -> None:
    raw = _make_raw(
        shareholders="Public investors",
        extra={"bmv_ticker": "KIMBERA"},
    )
    a = analyze_shareholders(raw, config.families)
    assert a.capital_origin == "Público"


def test_privado_mx_default(config: Config) -> None:
    raw = _make_raw(
        shareholders="Investors privados nacionales sin info adicional.",
    )
    a = analyze_shareholders(raw, config.families)
    assert a.capital_origin == "Privado/MX"
    assert a.is_familiar_mx is False
    assert a.is_foreign_subsidiary is False


def test_desconocido_when_empty(config: Config) -> None:
    raw = _make_raw()
    a = analyze_shareholders(raw, config.families)
    assert a.capital_origin == "Desconocido"


def test_family_detected_in_executives_when_shareholders_empty(config: Config) -> None:
    raw = _make_raw(
        shareholders=None,
        executives="Carlos Quintana (CEO), Maria Quintana (CFO)",
    )
    a = analyze_shareholders(raw, config.families)
    assert a.detected_family == "Quintana"
    assert a.capital_origin == "Familiar/MX"


def test_foreign_takes_precedence_over_family(config: Config) -> None:
    """Si una empresa es subsidiaria extranjera Y tiene apellidos clásicos
    en ejecutivos locales, prevalece foreign (control real)."""
    raw = _make_raw(
        shareholders="Toray Industries (JP) - 100%",
        executives="Carlos Quintana (CEO local)",
    )
    a = analyze_shareholders(raw, config.families)
    assert a.capital_origin == "Subsidiaria/Extranjera"
