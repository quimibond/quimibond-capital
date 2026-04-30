"""
Análisis de saturación por subsector.

Para cada subsector único en el universo cargado, agrega:
- total_companies: empresas detectadas con ese subsector.
- consolidated: empresas que ya están "fuera de mercado" para roll-up
  (subsidiarias extranjeras o públicas, o tamaño platform donde ya
  son ellas mismas la plataforma potencial).
- accessible: total - consolidated.

Verdict según ratio consolidated/total:
- < consolidated_ratio_atractivo_max → "Atractivo"
- > consolidated_ratio_saturado_min → "Saturado"
- intermedio → "Mixto"
- total < min_companies_for_verdict → "Insuficiente"
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from quimibond.config_loader import Thresholds
from quimibond.models import (
    Classification,
    RawCompany,
    SaturationVerdict,
    SaturationVerdictType,
)


@dataclass(frozen=True)
class _CompanyView:
    """Vista mínima necesaria para análisis de saturación."""

    raw: RawCompany
    classification: Classification


def _is_consolidated(view: _CompanyView, thresholds: Thresholds) -> bool:
    """
    Una empresa cuenta como 'consolidada' (no accesible para roll-up) si:
    - es subsidiaria extranjera (matriz no se vende), o
    - es pública (control disperso), o
    - tiene revenue >= platform_min (ya es ella la plataforma).
    """
    if view.classification.is_foreign_subsidiary:
        return True
    if view.classification.capital_origin == "Público":
        return True
    rev = view.raw.revenue_usd_mm
    if rev is not None and rev >= thresholds.revenue_brackets_usd_mm.platform_min:
        return True
    return False


def _verdict(
    total: int,
    consolidated: int,
    thresholds: Thresholds,
) -> SaturationVerdictType:
    s = thresholds.saturation
    if total < s.min_companies_for_verdict:
        return "Insuficiente"
    ratio = consolidated / total if total > 0 else 0.0
    if ratio <= s.consolidated_ratio_atractivo_max:
        return "Atractivo"
    if ratio >= s.consolidated_ratio_saturado_min:
        return "Saturado"
    return "Mixto"


def analyze_saturation(
    pairs: Sequence[tuple[RawCompany, Classification]],
    thresholds: Thresholds,
) -> tuple[SaturationVerdict, ...]:
    """
    Recibe la secuencia (raw, classification) de todas las empresas del
    universo y devuelve un SaturationVerdict por cada subsector único.

    Output ordenado alfabéticamente por subsegment para determinismo.
    """
    views = [_CompanyView(raw=r, classification=c) for r, c in pairs]
    by_subsector: dict[str, list[_CompanyView]] = {}
    for v in views:
        by_subsector.setdefault(v.classification.subsector, []).append(v)

    results: list[SaturationVerdict] = []
    for subsector in sorted(by_subsector.keys()):
        bucket = by_subsector[subsector]
        total = len(bucket)
        consolidated = sum(1 for v in bucket if _is_consolidated(v, thresholds))
        accessible = total - consolidated
        verdict = _verdict(total, consolidated, thresholds)

        # Notas: top-3 consolidados (foreign + público) para contextualizar
        consolidated_names = sorted(
            v.raw.company_name for v in bucket if _is_consolidated(v, thresholds)
        )[:3]
        notes = (
            f"top consolidados: {', '.join(consolidated_names)}"
            if consolidated_names
            else "sin consolidados detectados"
        )

        results.append(
            SaturationVerdict(
                subsegment=subsector,
                total_companies=total,
                consolidated=consolidated,
                accessible=accessible,
                verdict=verdict,
                notes=notes,
            )
        )

    return tuple(results)


def saturation_distribution(
    pairs: Sequence[tuple[RawCompany, Classification]],
) -> Counter[str]:
    """Helper de inspección — conteo por subsector."""
    return Counter(c.subsector for _, c in pairs)
