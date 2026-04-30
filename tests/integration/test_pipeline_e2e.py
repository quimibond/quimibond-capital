"""
End-to-end: cargar EMIS sample → enrich → classify → invariants OK.

Este es el primer test que recorre todo el flujo y confirma que las
piezas se integran sin fricción.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from quimibond.config_loader import load_config
from quimibond.ingestion import EmisLoader
from quimibond.pe_classification import classify_universe
from quimibond.validation import assert_invariants

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE = REPO_ROOT / "tests" / "fixtures" / "emis_sample_50.xlsx"
CONFIG_DIR = REPO_ROOT / "config"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pipeline_data() -> tuple:
    config = load_config(CONFIG_DIR)
    raws = EmisLoader().load(SAMPLE, source_as_of=date(2026, 4, 30))
    data = classify_universe(raws, config, today=date(2026, 4, 30))
    return data, config


def test_pipeline_produces_companies(pipeline_data: tuple) -> None:
    data, _ = pipeline_data
    assert data.n_companies == 50


def test_invariants_hold(pipeline_data: tuple) -> None:
    data, config = pipeline_data
    assert_invariants(data, config)  # no raises


def test_companies_sorted_deterministically(pipeline_data: tuple) -> None:
    data, _ = pipeline_data
    ids = [c.emis_id for c in data.companies]
    assert ids == sorted(ids), "companies deben estar ordenadas por emis_id"


def test_idempotent_classification(pipeline_data: tuple) -> None:
    """Correr dos veces produce los mismos lever_combined byte-idénticos."""
    data, config = pipeline_data
    raws = EmisLoader().load(SAMPLE, source_as_of=date(2026, 4, 30))
    data2 = classify_universe(raws, config, today=date(2026, 4, 30))
    for c1, c2 in zip(data.companies, data2.companies, strict=True):
        assert c1.emis_id == c2.emis_id
        assert c1.levers.combined == c2.levers.combined
        assert c1.fatigue.score == c2.fatigue.score
        assert c1.pe_role == c2.pe_role


def test_role_distribution_diverse(pipeline_data: tuple) -> None:
    """Las primeras 50 deben producir al menos 3 roles distintos."""
    data, _ = pipeline_data
    roles = Counter(c.pe_role for c in data.companies)
    assert len(roles) >= 3, f"poca diversidad de roles: {roles}"


def test_strategic_implies_foreign(pipeline_data: tuple) -> None:
    data, _ = pipeline_data
    for c in data.companies:
        if c.pe_role == "STRATEGIC":
            assert c.is_foreign_subsidiary, (
                f"STRATEGIC {c.emis_id} no es foreign_subsidiary"
            )


def test_platform_meets_threshold(pipeline_data: tuple) -> None:
    data, config = pipeline_data
    pmin_rev = config.thresholds.revenue_brackets_usd_mm.platform_min
    pmin_emp = config.thresholds.employee_brackets.platform_min
    for c in data.companies:
        if c.pe_role == "PLATFORM_CANDIDATE":
            rev_ok = c.revenue_usd_mm is not None and c.revenue_usd_mm >= pmin_rev
            emp_ok = c.employees is not None and c.employees >= pmin_emp
            assert rev_ok or emp_ok, f"PLATFORM {c.emis_id} no cumple thresholds"


def test_arbitrage_consistency(pipeline_data: tuple) -> None:
    data, config = pipeline_data
    margin = config.pe_playbook.ebitda_margin_default
    for c in data.companies:
        if c.arbitrage is None:
            continue
        assert c.revenue_usd_mm is not None
        expected_ebitda = c.revenue_usd_mm * margin
        assert abs(c.arbitrage.ebitda_estimate_usd_mm - expected_ebitda) < 1e-9


def test_lever_combined_within_role_caps(pipeline_data: tuple) -> None:
    data, config = pipeline_data
    for c in data.companies:
        cap = config.pe_playbook.role_combined_cap.get(c.pe_role, 1.0)
        assert c.levers.combined <= cap + 1e-9


def test_saturation_has_entries(pipeline_data: tuple) -> None:
    data, _ = pipeline_data
    assert len(data.saturation) >= 1
    for s in data.saturation:
        assert s.total_companies == s.consolidated + s.accessible
