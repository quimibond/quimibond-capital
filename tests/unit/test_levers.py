"""Tests del cálculo de palancas."""

from __future__ import annotations

from datetime import date

from quimibond.config_loader import Config
from quimibond.models import Classification, RawCompany
from quimibond.pe_classification.levers import compute_levers


def _raw(
    *,
    revenue: float | None = None,
    employees: int | None = None,
    is_exporter: bool | None = None,
) -> RawCompany:
    return RawCompany(
        source_id="X1",
        source="EMIS",
        source_as_of=date(2026, 4, 30),
        company_name="Test Co",
        revenue_usd_mm=revenue,
        employees=employees,
        is_exporter=is_exporter,
    )


def _clf(
    *,
    priority: str = "Crítica",
    is_familiar: bool = False,
    is_foreign: bool = False,
    capital_origin: str = "Familiar/MX",
    processes: tuple[str, ...] = (),
    client_type: str = "Desconocido",
) -> Classification:
    return Classification(
        subsector="no_tejidos",
        subsector_priority=priority,  # type: ignore[arg-type]
        is_familiar_mx=is_familiar,
        is_foreign_subsidiary=is_foreign,
        capital_origin=capital_origin,  # type: ignore[arg-type]
        quimibond_processes=processes,
        main_client_type=client_type,  # type: ignore[arg-type]
    )


def test_levers_in_range(config: Config) -> None:
    raw = _raw(revenue=20, employees=200, is_exporter=True)
    clf = _clf(is_familiar=True, processes=("acabado", "tintoreria"), client_type="Automotriz")
    ls = compute_levers(raw, clf, "PRIMARY_BOLT_ON", config)
    assert 0 <= ls.cost <= 1
    assert 0 <= ls.revenue <= 1
    assert 0 <= ls.arbitrage <= 1
    assert 0 <= ls.combined <= 1


def test_familiar_mx_boosts_cost(config: Config) -> None:
    raw = _raw(revenue=20, employees=200)
    clf_familiar = _clf(is_familiar=True, capital_origin="Familiar/MX")
    clf_publico = _clf(is_familiar=False, capital_origin="Público")
    ls_fam = compute_levers(raw, clf_familiar, "PRIMARY_BOLT_ON", config)
    ls_pub = compute_levers(raw, clf_publico, "PRIMARY_BOLT_ON", config)
    assert ls_fam.cost > ls_pub.cost


def test_processes_compartidos_boosts_cost(config: Config) -> None:
    raw = _raw(revenue=20, employees=200)
    clf_with = _clf(processes=("acabado", "tintoreria"))
    clf_without = _clf(processes=())
    ls_with = compute_levers(raw, clf_with, "PRIMARY_BOLT_ON", config)
    ls_without = compute_levers(raw, clf_without, "PRIMARY_BOLT_ON", config)
    assert ls_with.cost > ls_without.cost


def test_automotriz_boosts_revenue(config: Config) -> None:
    raw = _raw(revenue=20)
    clf_auto = _clf(client_type="Automotriz")
    clf_apparel = _clf(client_type="Apparel")
    ls_auto = compute_levers(raw, clf_auto, "PRIMARY_BOLT_ON", config)
    ls_app = compute_levers(raw, clf_apparel, "PRIMARY_BOLT_ON", config)
    assert ls_auto.revenue > ls_app.revenue


def test_exporter_boosts_revenue(config: Config) -> None:
    raw_exp = _raw(revenue=20, is_exporter=True)
    raw_no = _raw(revenue=20, is_exporter=False)
    clf = _clf()
    ls_exp = compute_levers(raw_exp, clf, "PRIMARY_BOLT_ON", config)
    ls_no = compute_levers(raw_no, clf, "PRIMARY_BOLT_ON", config)
    assert ls_exp.revenue > ls_no.revenue


def test_strategic_role_caps_combined(config: Config) -> None:
    """STRATEGIC nunca debe superar role_combined_cap (0.30)."""
    raw = _raw(revenue=200, employees=2000, is_exporter=True)
    clf = _clf(
        is_familiar=False,
        is_foreign=True,
        capital_origin="Subsidiaria/Extranjera",
        processes=("acabado", "tintoreria", "tejido_circular"),
        client_type="Automotriz",
    )
    ls = compute_levers(raw, clf, "STRATEGIC", config)
    cap = config.pe_playbook.role_combined_cap["STRATEGIC"]
    assert ls.combined <= cap


def test_out_of_scope_capped(config: Config) -> None:
    raw = _raw(revenue=10)
    clf = _clf()
    ls = compute_levers(raw, clf, "OUT_OF_SCOPE", config)
    cap = config.pe_playbook.role_combined_cap["OUT_OF_SCOPE"]
    assert ls.combined <= cap


def test_revenue_in_bolt_on_boosts_arbitrage(config: Config) -> None:
    raw_bolt = _raw(revenue=25)  # bolt-on sweet spot
    raw_huge = _raw(revenue=500)  # demasiado grande
    clf = _clf()
    ls_bolt = compute_levers(raw_bolt, clf, "PRIMARY_BOLT_ON", config)
    ls_huge = compute_levers(raw_huge, clf, "PRIMARY_BOLT_ON", config)
    assert ls_bolt.arbitrage > ls_huge.arbitrage
