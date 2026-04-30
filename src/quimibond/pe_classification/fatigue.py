"""
Owner-fatigue scorer.

Señales detectables desde EMIS (limitado: no tenemos datos cualitativos
sobre sucesión, edad del fundador, etc.). Usamos proxies:

- Edad de la empresa (incorporation_year):
  >= fatigue_age_high (40+) → +0.5
  >= fatigue_age_medium (25-40) → +0.3
  >= edad_madura_min (20-25) → +0.15

- Estructura: si es Familiar/MX (control concentrado en familia mexicana
  privada, sin sucesión declarada) → +0.2.

- Falta de presencia digital como proxy de gestión envejecida:
  sin website y empresa madura → +0.1.

- Empresa privada (Privado/MX y Familiar/MX vs Público o Subsidiaria) tiene
  mayor probabilidad de fatiga porque no hay liquidez para la familia.

El score se clampa a [0, 1] y se reportan los signals concretos que activaron.
"""

from __future__ import annotations

from quimibond.config_loader import Thresholds
from quimibond.models import Classification, FatigueScore, RawCompany


def score_owner_fatigue(
    raw: RawCompany,
    classification: Classification,
    thresholds: Thresholds,
    *,
    age_years: int | None,
) -> FatigueScore:
    """Score [0, 1] + signals detectados."""
    age_t = thresholds.age_thresholds
    score = 0.0
    signals: list[str] = []

    # 1. Edad
    if age_years is not None:
        if age_years >= age_t.fatigue_age_high:
            score += 0.50
            signals.append(f"edad_alta={age_years}y (>={age_t.fatigue_age_high})")
        elif age_years >= age_t.fatigue_age_medium:
            score += 0.30
            signals.append(f"edad_media={age_years}y (>={age_t.fatigue_age_medium})")
        elif age_years >= age_t.edad_madura_min:
            score += 0.15
            signals.append(f"edad_madura={age_years}y (>={age_t.edad_madura_min})")
    else:
        signals.append("edad_desconocida")

    # 2. Estructura familiar privada (sin liquidez para familia)
    if classification.is_familiar_mx:
        score += 0.20
        signals.append(f"familiar_mx={classification.detected_family or 'sin_apellido'}")
    elif classification.capital_origin == "Privado/MX":
        score += 0.10
        signals.append("privado_mx")

    # 3. Sin website + empresa madura → señal de gestión rezagada
    has_website = bool((raw.website or "").strip())
    if not has_website and age_years is not None and age_years >= age_t.edad_madura_min:
        score += 0.10
        signals.append("sin_website")

    # 4. Empresa muy chica (<= 50 emp) y muy vieja → signal adicional
    if (
        raw.employees is not None
        and raw.employees <= 50
        and age_years is not None
        and age_years >= age_t.fatigue_age_medium
    ):
        score += 0.10
        signals.append("pequeña_y_vieja")

    score = max(0.0, min(1.0, score))

    if not signals:
        justification = "Sin señales de fatiga detectables desde EMIS."
    else:
        justification = " · ".join(signals)

    return FatigueScore(
        score=score,
        signals=tuple(signals),
        justification=justification,
    )
