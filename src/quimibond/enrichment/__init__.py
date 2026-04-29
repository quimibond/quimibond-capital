"""
Pipeline de enrichment: derivar campos calculados desde RawCompany.

API pública:
- `derive_classification(raw, config) -> Classification` — combina los cuatro
  enrichers (subsector, processes, clients, shareholders).
- Funciones individuales (compute_age_years, classify_subsector, etc.)
  exportadas para uso directo en F4 y tests.

Reglas:
- Sin side effects. Funciones puras de (raw, config) → resultado.
- Si algún campo no es derivable, se usa el default conservador.
"""

from quimibond.config_loader import Config
from quimibond.enrichment.clients import classify_main_client
from quimibond.enrichment.normalizers import (
    build_location_label,
    compute_age_years,
    compute_productivity_usd_per_employee,
    is_edad_madura,
    lower_text,
)
from quimibond.enrichment.processes import detect_quimibond_processes
from quimibond.enrichment.shareholders import (
    ShareholderAnalysis,
    analyze_shareholders,
)
from quimibond.enrichment.subsector import classify_subsector
from quimibond.models import Classification, RawCompany


def derive_classification(raw: RawCompany, config: Config) -> Classification:
    """Combina los cuatro enrichers en una Classification inmutable."""
    subsector_name, priority = classify_subsector(raw, config.classifiers)
    processes = detect_quimibond_processes(raw, config.classifiers)
    main_client = classify_main_client(raw, config.classifiers)
    sh = analyze_shareholders(raw, config.families)

    return Classification(
        subsector=subsector_name,
        subsector_priority=priority,
        quimibond_processes=processes,
        main_client_type=main_client,
        capital_origin=sh.capital_origin,
        is_familiar_mx=sh.is_familiar_mx,
        is_foreign_subsidiary=sh.is_foreign_subsidiary,
        detected_family=sh.detected_family,
    )


__all__ = [
    "ShareholderAnalysis",
    "analyze_shareholders",
    "build_location_label",
    "classify_main_client",
    "classify_subsector",
    "compute_age_years",
    "compute_productivity_usd_per_employee",
    "derive_classification",
    "detect_quimibond_processes",
    "is_edad_madura",
    "lower_text",
]
