"""
Clasificador del tipo de cliente B2B principal.

Estrategia:
- Match por keywords contra activity_description + main_products + customers
  + business description.
- Si matcheán >=2 tipos distintos → 'Mixto'.
- Si matchea 1 → ese tipo.
- Si no matchea ninguno → 'Desconocido'.
"""

from __future__ import annotations

from quimibond.config_loader import Classifiers
from quimibond.enrichment.subsector import _build_haystack
from quimibond.models import ClientType, RawCompany


def classify_main_client(
    raw: RawCompany,
    classifiers: Classifiers,
) -> ClientType:
    haystack = _build_haystack(raw)
    if not haystack:
        return "Desconocido"

    matched: list[ClientType] = []
    for client_type, rule in classifiers.client_types.items():
        if any(kw.lower() in haystack for kw in rule.keywords):
            matched.append(client_type)

    if not matched:
        return "Desconocido"
    if len(matched) >= 2:
        return "Mixto"
    return matched[0]
