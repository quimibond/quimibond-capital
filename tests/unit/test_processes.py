"""Tests del detector de procesos Quimibond."""

from __future__ import annotations

from datetime import date

from quimibond.config_loader import Config
from quimibond.enrichment.processes import detect_quimibond_processes
from quimibond.models import RawCompany


def _make_raw(activity: str | None) -> RawCompany:
    return RawCompany(
        source_id="X1",
        source="EMIS",
        source_as_of=date(2026, 4, 29),
        company_name="Test Co",
        activity_description=activity,
    )


def test_detects_circular_knit(config: Config) -> None:
    raw = _make_raw("Tejido circular de polyester")
    procs = detect_quimibond_processes(raw, config.classifiers)
    assert "tejido_circular" in procs


def test_detects_multiple_processes(config: Config) -> None:
    raw = _make_raw("Tejido circular, tintorería y acabado de telas")
    procs = detect_quimibond_processes(raw, config.classifiers)
    assert "tejido_circular" in procs
    assert "tintoreria" in procs
    assert "acabado" in procs


def test_no_match_returns_empty(config: Config) -> None:
    raw = _make_raw("Producción de cables eléctricos")
    procs = detect_quimibond_processes(raw, config.classifiers)
    assert procs == ()


def test_empty_input(config: Config) -> None:
    raw = _make_raw(None)
    procs = detect_quimibond_processes(raw, config.classifiers)
    assert procs == ()


def test_order_is_stable(config: Config) -> None:
    """Si una empresa matchea varios procesos, el orden debe ser el del YAML."""
    raw = _make_raw("acabado de telas, tintorería, recubrimiento, tejido circular")
    procs = detect_quimibond_processes(raw, config.classifiers)
    yaml_order = list(config.classifiers.quimibond_processes.keys())
    # Filtrar yaml_order a los que matchearon, deben aparecer en ese orden
    expected_order = [p for p in yaml_order if p in procs]
    assert list(procs) == expected_order
