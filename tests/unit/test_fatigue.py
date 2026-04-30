"""Tests del fatigue scorer."""

from __future__ import annotations

from datetime import date

from quimibond.config_loader import Config
from quimibond.models import Classification, RawCompany
from quimibond.pe_classification.fatigue import score_owner_fatigue


def _make_raw(
    *,
    employees: int | None = None,
    website: str | None = None,
) -> RawCompany:
    return RawCompany(
        source_id="X1",
        source="EMIS",
        source_as_of=date(2026, 4, 30),
        company_name="Test Co",
        employees=employees,
        website=website,
    )


def _make_clf(
    *,
    is_familiar: bool = False,
    capital_origin: str = "Desconocido",
) -> Classification:
    return Classification(
        subsector="no_tejidos",
        subsector_priority="Crítica",
        is_familiar_mx=is_familiar,
        capital_origin=capital_origin,  # type: ignore[arg-type]
        detected_family="Quintana" if is_familiar else None,
    )


class TestFatigueAge:
    def test_old_company_high_fatigue(self, config: Config) -> None:
        f = score_owner_fatigue(_make_raw(), _make_clf(), config.thresholds, age_years=50)
        assert f.score >= 0.5
        assert any("edad_alta" in s for s in f.signals)

    def test_medium_age(self, config: Config) -> None:
        f = score_owner_fatigue(_make_raw(), _make_clf(), config.thresholds, age_years=30)
        assert any("edad_media" in s for s in f.signals)
        assert 0.2 <= f.score <= 0.5

    def test_young_no_age_score(self, config: Config) -> None:
        f = score_owner_fatigue(_make_raw(), _make_clf(), config.thresholds, age_years=5)
        assert not any("edad" in s for s in f.signals)

    def test_no_age_signal(self, config: Config) -> None:
        f = score_owner_fatigue(_make_raw(), _make_clf(), config.thresholds, age_years=None)
        assert "edad_desconocida" in f.signals


class TestFatigueOwnership:
    def test_familiar_mx_adds(self, config: Config) -> None:
        f = score_owner_fatigue(
            _make_raw(),
            _make_clf(is_familiar=True),
            config.thresholds,
            age_years=10,
        )
        assert any("familiar_mx" in s for s in f.signals)

    def test_foreign_no_familiar_signal(self, config: Config) -> None:
        f = score_owner_fatigue(
            _make_raw(),
            _make_clf(capital_origin="Subsidiaria/Extranjera"),
            config.thresholds,
            age_years=50,
        )
        assert not any("familiar" in s for s in f.signals)


class TestFatigueDigital:
    def test_no_website_old_adds_signal(self, config: Config) -> None:
        f = score_owner_fatigue(
            _make_raw(website=None),
            _make_clf(),
            config.thresholds,
            age_years=50,
        )
        assert "sin_website" in f.signals

    def test_with_website_no_signal(self, config: Config) -> None:
        f = score_owner_fatigue(
            _make_raw(website="http://example.com"),
            _make_clf(),
            config.thresholds,
            age_years=50,
        )
        assert "sin_website" not in f.signals


class TestFatigueScale:
    def test_score_clamped(self, config: Config) -> None:
        # Empresa familiar muy vieja, sin web, pequeña → todas las señales
        f = score_owner_fatigue(
            _make_raw(employees=20, website=None),
            _make_clf(is_familiar=True),
            config.thresholds,
            age_years=70,
        )
        assert 0.0 <= f.score <= 1.0
        assert f.score >= 0.7

    def test_no_signals_low_score(self, config: Config) -> None:
        # Joven, sin info de origen, sin website
        f = score_owner_fatigue(
            _make_raw(employees=200, website=None),
            _make_clf(capital_origin="Desconocido"),
            config.thresholds,
            age_years=5,
        )
        assert f.score == 0.0
