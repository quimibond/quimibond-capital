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
    naics: str | None = None,
) -> RawCompany:
    return RawCompany(
        source_id="X1",
        source="EMIS",
        source_as_of=date(2026, 4, 29),
        company_name="Test Co",
        activity_description=activity,
        naics=naics,
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


# ---------------------------------------------------------------------------
# NAICS-aware classification (F3.5)
# ---------------------------------------------------------------------------


class TestNaicsAwareSubsector:
    """
    Cuando la descripción es genérica pero el NAICS es específico, debe
    matchear por NAICS. Caso real: Quimibond.
    """

    def test_quimibond_naics_3149_critica(self, config: Config) -> None:
        """Producción genérica + NAICS 3149 → no_tejidos Crítica."""
        raw = _make_raw(activity="Manufactura de telas técnicas", naics="3149")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "no_tejidos"
        assert prio == "Crítica"

    def test_naics_31499_specific_match(self, config: Config) -> None:
        raw = _make_raw(activity=None, naics="314999")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "no_tejidos"
        assert prio == "Crítica"

    def test_naics_31332_recubrimientos(self, config: Config) -> None:
        raw = _make_raw(activity="Manufactura general", naics="31332")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "recubrimientos_simil_cuero"
        assert prio == "Crítica"

    def test_naics_31331_proceso_quimibond(self, config: Config) -> None:
        raw = _make_raw(activity=None, naics="31331")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "proceso_quimibond"
        assert prio == "Crítica"

    def test_naics_31411_alfombras(self, config: Config) -> None:
        raw = _make_raw(activity="Producción de productos textiles", naics="31411")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "alfombras_floor_mats"
        assert prio == "Alta"

    def test_naics_3132_telas_media(self, config: Config) -> None:
        raw = _make_raw(activity=None, naics="31321")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "telas_generales"
        assert prio == "Media"

    def test_keyword_in_critica_beats_naics_in_media(self, config: Config) -> None:
        """
        Si una empresa tiene NAICS 3132 (telas — Media) PERO descripción
        contiene 'spunbond' (no_tejidos — Crítica), gana Crítica porque se
        evalúa primero ese tier.
        """
        raw = _make_raw(activity="Spunbond for technical use", naics="31321")
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "no_tejidos"
        assert prio == "Crítica"

    def test_no_haystack_no_naics_default(self, config: Config) -> None:
        raw = _make_raw(activity=None, naics=None)
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "Textil — otro"
        assert prio == "Media"


class TestNameAsHaystack:
    """company_name y legal_name también participan en el match — caso Quimibond."""

    def test_company_name_keyword_match(self, config: Config) -> None:
        """Productora de No Tejidos Quimibond: el nombre legal trae 'no tejid'."""
        raw = RawCompany(
            source_id="X1",
            source="EMIS",
            source_as_of=date(2026, 4, 29),
            company_name="Productora de No Tejidos Quimibond",
            naics="3132",  # NAICS dice fabric mills (Media)
            activity_description="Manufactura de telas técnicas",
        )
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "no_tejidos"
        assert prio == "Crítica"

    def test_legal_name_keyword_match(self, config: Config) -> None:
        raw = RawCompany(
            source_id="X1",
            source="EMIS",
            source_as_of=date(2026, 4, 29),
            company_name="Acme Holdings",
            legal_name="Acme Spunbond Industries S.A. de C.V.",
            naics="3132",
            activity_description=None,
        )
        sector, prio = classify_subsector(raw, config.classifiers)
        assert sector == "no_tejidos"
        assert prio == "Crítica"
