"""
Normalizers: funciones puras que derivan campos calculados desde RawCompany.

Todas son deterministas, sin side effects, y devuelven None ante inputs
insuficientes — el pipeline NUNCA inventa data.
"""

from __future__ import annotations

from datetime import date


def compute_age_years(incorporation_year: int | None, today: date) -> int | None:
    """
    Edad de la empresa en años, basada en año de incorporación.

    Devuelve None si no hay año, si está en el futuro, o si > 200 años.
    """
    if incorporation_year is None:
        return None
    if incorporation_year > today.year:
        return None
    age = today.year - incorporation_year
    if not 0 <= age <= 200:
        return None
    return age


def compute_productivity_usd_per_employee(
    revenue_usd_mm: float | None,
    employees: int | None,
) -> float | None:
    """
    Productividad = revenue_USD / empleados.

    Devuelve None si falta revenue, empleados, o empleados = 0.
    """
    if revenue_usd_mm is None or employees is None or employees <= 0:
        return None
    return (revenue_usd_mm * 1_000_000) / employees


def build_location_label(
    municipality: str | None,
    state: str | None,
    city: str | None = None,
) -> str | None:
    """
    Construye 'Municipio, Estado' (o 'Ciudad, Estado' si no hay municipio).

    Ejemplos:
        ('Toluca', 'Estado de Mexico', None)         → 'Toluca, Estado de Mexico'
        (None, 'Estado de Mexico', 'Toluca')         → 'Toluca, Estado de Mexico'
        (None, 'Estado de Mexico', None)             → 'Estado de Mexico'
        (None, None, None)                           → None
    """
    locality = (municipality or city or "").strip() or None
    state_clean = (state or "").strip() or None
    if locality and state_clean:
        return f"{locality}, {state_clean}"
    return locality or state_clean


def is_edad_madura(age_years: int | None, threshold: int) -> bool:
    """True si la empresa tiene >= threshold años. None → False."""
    if age_years is None:
        return False
    return age_years >= threshold


def lower_text(*parts: str | None) -> str:
    """Concatena partes no-None, baja a minúsculas, separa con espacios."""
    chunks = [p.strip().lower() for p in parts if p and p.strip()]
    return " ".join(chunks)
