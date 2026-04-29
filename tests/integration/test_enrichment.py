"""
Integration test del pipeline de enrichment contra el sample EMIS.

Carga las 50 empresas del fixture, deriva Classification para cada una, y
valida que la distribución resultante tenga sentido.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from quimibond.config_loader import Config
from quimibond.enrichment import derive_classification
from quimibond.ingestion import EmisLoader

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE = REPO_ROOT / "tests" / "fixtures" / "emis_sample_50.xlsx"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def companies() -> tuple:
    return EmisLoader().load(SAMPLE, source_as_of=date(2026, 4, 29))


def test_derive_classification_for_all(companies: tuple, config: Config) -> None:
    """Toda empresa del sample debe producir una Classification válida."""
    for raw in companies:
        clf = derive_classification(raw, config)
        # Subsector siempre poblado
        assert clf.subsector
        # Priority es uno de los Literal types
        assert clf.subsector_priority in ("Crítica", "Alta", "Media", "Baja", "Excluida")
        # Familiar y Foreign mutuamente excluyentes
        assert not (clf.is_familiar_mx and clf.is_foreign_subsidiary)


def test_priority_distribution_makes_sense(companies: tuple, config: Config) -> None:
    """En las primeras 50 empresas EMIS (ordenadas por revenue desc) debe haber
    al menos una con prioridad Crítica y una con Alta."""
    classifications = [derive_classification(raw, config) for raw in companies]
    priorities = Counter(c.subsector_priority for c in classifications)
    assert priorities["Crítica"] >= 1
    assert priorities.get("Alta", 0) + priorities.get("Crítica", 0) >= 5


def test_kaltex_classified(companies: tuple, config: Config) -> None:
    """Kaltex Textiles (broadwoven fabric) debe caer en telas o crítica."""
    kaltex = next(c for c in companies if "Kaltex Textiles" in c.company_name)
    clf = derive_classification(kaltex, config)
    # broadwoven matchea 'fabric' en telas_generales (Media)
    assert clf.subsector_priority in ("Crítica", "Alta", "Media")


def test_at_least_one_familiar_mx_detected(companies: tuple, config: Config) -> None:
    """Al menos una de las 50 empresas debe tener apellido textil clásico."""
    classifications = [derive_classification(raw, config) for raw in companies]
    n_familiar = sum(1 for c in classifications if c.is_familiar_mx)
    assert n_familiar >= 1, "esperaba >= 1 empresa familiar MX en sample 50"


def test_capital_origin_diverse(companies: tuple, config: Config) -> None:
    """Distribución diversa de origen de capital — al menos 3 categorías."""
    classifications = [derive_classification(raw, config) for raw in companies]
    origins = {c.capital_origin for c in classifications}
    assert len(origins) >= 3, f"poca diversidad: {origins}"
