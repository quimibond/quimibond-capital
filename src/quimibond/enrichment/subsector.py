"""
Clasificador de subsector + prioridad.

Lógica:
1. Construir un haystack: activity_description + main_emis + main_naics + extras.
2. Iterar tiers Crítica → Alta → Media → Baja → Excluida.
3. Para cada rule del tier, matchea si:
   - cualquier keyword aparece como substring en el haystack, O
   - el NAICS de la empresa empieza con cualquiera de los naics_prefixes.
4. Primer match gana — captura el rule_name como subsector y el tier como priority.
5. Si nada matchea: ('Textil — otro', 'Media').

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


def _matches(haystack: str, naics: str | None, rule: KeywordRule) -> bool:
    """
    True si la rule matchea por keywords (en el haystack) o por NAICS prefix.
    """
    if any(kw.lower() in haystack for kw in rule.keywords):
        return True
    if naics is not None and any(naics.startswith(p) for p in rule.naics_prefixes):
        return True
    return False


def _build_haystack(raw: RawCompany) -> str:
    """
    Concatena los textos relevantes en lowercase para matchear keywords.

    Incluye:
    - company_name / legal_name (atrapa casos como 'Productora de No Tejidos
      Quimibond' donde el nombre legal ya describe la actividad).
    - activity_description (texto libre EMIS).
    - main_emis / industry_emis (taxonomía EMIS).
    - main_naics / industry_naics / secondary_naics (descripción NAICS).
    - main_products (línea de producto declarada).
    """
    parts: list[str] = []
    if raw.company_name:
        parts.append(raw.company_name.lower())
    if raw.legal_name and raw.legal_name != raw.company_name:
        parts.append(raw.legal_name.lower())
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
    naics = raw.naics
    if not haystack and naics is None:
        return DEFAULT_SUBSECTOR, DEFAULT_PRIORITY

    for tier in PRIORITY_ORDER:
        sector_tier = classifiers.subsectors.get(tier)
        if sector_tier is None:
            continue
        for rule_name, rule in sector_tier.rules.items():
            if _matches(haystack, naics, rule):
                return rule_name, tier

    return DEFAULT_SUBSECTOR, DEFAULT_PRIORITY
