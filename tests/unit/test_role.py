"""Tests del role classifier."""

from __future__ import annotations

from datetime import date

import pytest

from quimibond.config_loader import Config
from quimibond.models import Classification, RawCompany
from quimibond.pe_classification.role import classify_role


def _make_raw(
    *,
    revenue: float | None = None,
    employees: int | None = None,
) -> RawCompany:
    return RawCompany(
        source_id="X1",
        source="EMIS",
        source_as_of=date(2026, 4, 29),
        company_name="Test Co",
        revenue_usd_mm=revenue,
        employees=employees,
    )


def _make_clf(
    *,
    priority: str = "Crítica",
    is_familiar: bool = False,
    is_foreign: bool = False,
    capital_origin: str = "Privado/MX",
) -> Classification:
    return Classification(
        subsector="no_tejidos",
        subsector_priority=priority,  # type: ignore[arg-type]
        is_familiar_mx=is_familiar,
        is_foreign_subsidiary=is_foreign,
        capital_origin=capital_origin,  # type: ignore[arg-type]
    )


class TestClassifyRole:
    def test_foreign_subsidiary_strategic(self, config: Config) -> None:
        raw = _make_raw(revenue=100, employees=500)
        clf = _make_clf(is_foreign=True, capital_origin="Subsidiaria/Extranjera")
        r = classify_role(raw, clf, config.thresholds)
        assert r.role == "STRATEGIC"

    def test_excluida_out_of_scope(self, config: Config) -> None:
        raw = _make_raw(revenue=100)
        clf = _make_clf(priority="Excluida")
        r = classify_role(raw, clf, config.thresholds)
        assert r.role == "OUT_OF_SCOPE"

    def test_no_data_unknown_fit(self, config: Config) -> None:
        raw = _make_raw()
        clf = _make_clf()
        r = classify_role(raw, clf, config.thresholds)
        assert r.role == "UNKNOWN_FIT"

    def test_below_tuck_in_out_of_scope(self, config: Config) -> None:
        raw = _make_raw(revenue=0.5)
        clf = _make_clf()
        r = classify_role(raw, clf, config.thresholds)
        assert r.role == "OUT_OF_SCOPE"

    def test_platform_critica(self, config: Config) -> None:
        raw = _make_raw(revenue=100, employees=300)
        clf = _make_clf(priority="Crítica")
        r = classify_role(raw, clf, config.thresholds)
        assert r.role == "PLATFORM_CANDIDATE"

    def test_platform_revenue_but_media_priority_unknown(self, config: Config) -> None:
        raw = _make_raw(revenue=100)
        clf = _make_clf(priority="Media")
        r = classify_role(raw, clf, config.thresholds)
        assert r.role == "UNKNOWN_FIT"

    def test_bolt_on(self, config: Config) -> None:
        raw = _make_raw(revenue=20)
        clf = _make_clf(priority="Crítica")
        r = classify_role(raw, clf, config.thresholds)
        assert r.role == "PRIMARY_BOLT_ON"

    def test_bolt_on_alta(self, config: Config) -> None:
        raw = _make_raw(revenue=15)
        clf = _make_clf(priority="Alta")
        r = classify_role(raw, clf, config.thresholds)
        assert r.role == "PRIMARY_BOLT_ON"

    def test_tuck_in(self, config: Config) -> None:
        raw = _make_raw(revenue=5)
        clf = _make_clf(priority="Crítica")
        r = classify_role(raw, clf, config.thresholds)
        assert r.role == "TUCK_IN"

    def test_employees_proxy_when_no_revenue(self, config: Config) -> None:
        # 100 empleados sin revenue, priority Crítica → PRIMARY_BOLT_ON via proxy
        raw = _make_raw(revenue=None, employees=100)
        clf = _make_clf(priority="Crítica")
        r = classify_role(raw, clf, config.thresholds)
        assert r.role == "PRIMARY_BOLT_ON"

    def test_employees_too_few_out_of_scope(self, config: Config) -> None:
        raw = _make_raw(revenue=None, employees=5)
        clf = _make_clf(priority="Crítica")
        r = classify_role(raw, clf, config.thresholds)
        assert r.role == "OUT_OF_SCOPE"

    def test_foreign_takes_precedence_over_revenue(self, config: Config) -> None:
        """Foreign siempre STRATEGIC, no importa el revenue."""
        raw = _make_raw(revenue=10)
        clf = _make_clf(is_foreign=True, capital_origin="Subsidiaria/Extranjera")
        r = classify_role(raw, clf, config.thresholds)
        assert r.role == "STRATEGIC"


@pytest.mark.parametrize(
    "rev,priority,expected",
    [
        (60, "Crítica", "PLATFORM_CANDIDATE"),
        (45, "Crítica", "PRIMARY_BOLT_ON"),
        (15, "Alta", "PRIMARY_BOLT_ON"),
        (5, "Crítica", "TUCK_IN"),
        (0.5, "Crítica", "OUT_OF_SCOPE"),
    ],
)
def test_role_param(config: Config, rev: float, priority: str, expected: str) -> None:
    raw = _make_raw(revenue=rev)
    clf = _make_clf(priority=priority)
    r = classify_role(raw, clf, config.thresholds)
    assert r.role == expected
