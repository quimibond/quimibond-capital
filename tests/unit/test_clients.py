"""Tests del clasificador de cliente B2B."""

from __future__ import annotations

from datetime import date

from quimibond.config_loader import Config
from quimibond.enrichment.clients import classify_main_client
from quimibond.models import RawCompany


def _make_raw(activity: str | None) -> RawCompany:
    return RawCompany(
        source_id="X1",
        source="EMIS",
        source_as_of=date(2026, 4, 29),
        company_name="Test Co",
        activity_description=activity,
    )


def test_automotriz(config: Config) -> None:
    raw = _make_raw("Tier 1 supplier to Lear and Faurecia for automotive interiors")
    assert classify_main_client(raw, config.classifiers) == "Automotriz"


def test_hogar(config: Config) -> None:
    raw = _make_raw("Producción de bedding y blanco para retail")
    assert classify_main_client(raw, config.classifiers) == "Hogar"


def test_medico(config: Config) -> None:
    raw = _make_raw("Hospital wound care textiles for personal care")
    assert classify_main_client(raw, config.classifiers) == "Médico/Higiene"


def test_apparel(config: Config) -> None:
    raw = _make_raw("Apparel y prendas de moda")
    assert classify_main_client(raw, config.classifiers) == "Apparel"


def test_mixto_when_multiple_match(config: Config) -> None:
    raw = _make_raw("Industrial fabric and apparel for construction")
    # 'industrial', 'construction' → Industrial; 'apparel' → Apparel
    assert classify_main_client(raw, config.classifiers) == "Mixto"


def test_desconocido(config: Config) -> None:
    raw = _make_raw("Generic textile manufacturing")
    # 'textile' no matchea ningún client_type del config actual
    assert classify_main_client(raw, config.classifiers) == "Desconocido"


def test_empty(config: Config) -> None:
    raw = _make_raw(None)
    assert classify_main_client(raw, config.classifiers) == "Desconocido"
