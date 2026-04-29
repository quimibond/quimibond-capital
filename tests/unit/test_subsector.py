"""Tests del clasificador de subsector (matchea contra classifiers.yaml real)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from quimibond.config_loader import Config
from quimibond.enrichment.subsector import classify_subsector
from quimibond.models import RawCompany


def _make_raw(
    activity: str | None = None,
    extra: dict[str, Any] | None = None,
) -> RawCompany:
    return RawCompany(
        source_id="X1",
        source="EMIS",
        source_as_of=date(2026, 4, 29),
        company_name="Test Co",
        activity_description=activity,
        extra=extra or {},
    )


class TestClassifySubsector:
    def test_no_tejidos_critica(self, config: Config) -> None:
        raw = _make_raw("Manufactura de spunbond y meltblown")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "no_tejidos"
        assert prio == "Crítica"

    def test_textil_automotriz_critica(self, config: Config) -> None:
        raw = _make_raw("Supplier of automotive interior textiles for OEMs")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "textil_automotriz"
        assert prio == "Crítica"

    def test_recubrimientos_critica(self, config: Config) -> None:
        raw = _make_raw("Coated fabric and PVC coating services")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "recubrimientos_simil_cuero"
        assert prio == "Crítica"

    def test_proceso_quimibond_critica(self, config: Config) -> None:
        raw = _make_raw("Tejido circular y tintorería de telas")
        sector, prio = classify_subsector(raw, config.classifiers)
        # Match en proceso_quimibond pero también podría matchear hilados/telas.
        # Crítica gana sobre Media.
        assert prio == "Crítica"

    def test_textil_tecnico_alta(self, config: Config) -> None:
        raw = _make_raw("Manufactura de geotextile y filtration fabric industrial")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert prio == "Crítica"  # 'geotextile' está en no_tejidos.critica

    def test_alfombras_alta(self, config: Config) -> None:
        raw = _make_raw("Producción de alfombras y tapetes")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "alfombras_floor_mats"
        assert prio == "Alta"

    def test_telas_media(self, config: Config) -> None:
        raw = _make_raw("Weaving of cotton fabric")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "telas_generales"
        assert prio == "Media"

    def test_no_match_default(self, config: Config) -> None:
        raw = _make_raw("Producción de cables eléctricos")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "Textil — otro"
        assert prio == "Media"

    def test_empty_input_default(self, config: Config) -> None:
        raw = _make_raw(None)
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "Textil — otro"
        assert prio == "Media"

    def test_uses_extras_when_description_missing(self, config: Config) -> None:
        raw = _make_raw(
            None,
            extra={"main_emis": "Spunbond and nonwoven manufacturing"},
        )
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "no_tejidos"
        assert prio == "Crítica"


@pytest.mark.parametrize(
    "activity,expected_priority",
    [
        ("hilado técnico aramid for industrial use", "Alta"),
        ("alfombras automotrices", "Alta"),
        ("automotive carpet manufacturer", "Alta"),
        ("producción de blanco y sábanas", "Media"),
    ],
)
def test_priority_param(config: Config, activity: str, expected_priority: str) -> None:
    raw = _make_raw(activity)
    _, prio = classify_subsector(raw, config.classifiers)
    assert prio == expected_priority
