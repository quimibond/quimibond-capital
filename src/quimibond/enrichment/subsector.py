"""
Clasificador de subsector + prioridad.

Lógica:
1. Construir un haystack: activity_description + main_emis + main_naics + extras.
2. Iterar tiers Crítica → Alta → Media → Baja → Excluida.
3. Primer match (substring case-insensitive) gana — captura el rule_name como
   subsector y el tier como priority.
4. Si nada matchea: ('Textil — otro', 'Media').

Determinístico: el orden de tiers es Crítica > Alta > Media > Baja > Excluida.
Dentro de un tier, el orden depende de los keys del YAML — Python 3.7+
mantiene dict order, así que el orden del YAML es el orden de evaluación.
"""

from __future__ import annotations

from typing import Final

from quimibond.config_loader import Classifiers, KeywordRule
from quimibond.models import PriorityType, RawCompany

# Orden estricto de evaluación
PRIORITY_ORDER: Final[tuple[PriorityType, ...]] = ("Crítica", "Alta", "Media", "Baja", "Excluida")
DEFAULT_SUBSECTOR: Final[str] = "Textil — otro"
DEFAULT_PRIORITY: Final[PriorityType] = "Media"


def _matches(haystack: str, rule: KeywordRule) -> bool:
    """True si cualquier keyword del rule aparece (substring) en haystack."""
    return any(kw.lower() in haystack for kw in rule.keywords)


def _build_haystack(raw: RawCompany) -> str:
    """Concatena los textos relevantes en lowercase para matchear keywords."""
    parts: list[str] = []
    if raw.activity_description:
        parts.append(raw.activity_description.lower())
    extras = raw.extra
    for k in (
        "main_emis",
        "industry_emis",
        "main_naics",
        "industry_naics",
        "secondary_emis",
        "secondary_naics",
        "main_products",
    ):
        v = extras.get(k)
        if isinstance(v, str) and v:
            parts.append(v.lower())
    return " | ".join(parts)


def classify_subsector(
    raw: RawCompany,
    classifiers: Classifiers,
) -> tuple[str, PriorityType]:
    """
    Devuelve (subsector_name, priority).

    Subsector_name = el rule_name del YAML que matcheó (ej. 'no_tejidos',
    'textil_automotriz'), no la prioridad. Si nada matchea, devuelve
    DEFAULT_SUBSECTOR / DEFAULT_PRIORITY.
    """
    haystack = _build_haystack(raw)
    if not haystack:
        return DEFAULT_SUBSECTOR, DEFAULT_PRIORITY

    for tier in PRIORITY_ORDER:
        sector_tier = classifiers.subsectors.get(tier)
        if sector_tier is None:
            continue
        for rule_name, rule in sector_tier.rules.items():
            if _matches(haystack, rule):
                return rule_name, tier

    return DEFAULT_SUBSECTOR, DEFAULT_PRIORITY
