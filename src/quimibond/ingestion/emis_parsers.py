"""
Parsers utilitarios para campos del export EMIS.

Cada parser:
- acepta `Any` (lo que devuelve openpyxl: str, int, float, None, ...).
- devuelve un tipo concreto o `None` si el input es vacío / inválido.
- nunca levanta — los inputs sucios producen `None` (no inventamos data).

Ver tests/unit/test_emis_parsers.py para los casos de borde.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _to_str(value: Any) -> str | None:
    """Normaliza a string limpio o None si vacío."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


# ---------------------------------------------------------------------------
# Parsers públicos
# ---------------------------------------------------------------------------


def parse_text(value: Any) -> str | None:
    """Texto trimmed o None si vacío. Strings con solo espacios → None."""
    return _to_str(value)


def parse_revenue_usd_mm(value: Any) -> float | None:
    """
    El export EMIS pone Total Operating Revenue ya en USD millones (nota
    fila 5: "All Figures except for employees in Millions US"). Aceptamos
    int/float directos, o strings con comas/espacios.

        818.09          → 818.09
        "1,234.56"      → 1234.56
        " 0 "           → 0.0
        ""              → None
        "n/a"           → None
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = _to_str(value)
    if s is None:
        return None
    cleaned = s.replace(",", "").replace(" ", "")
    if not cleaned or cleaned.lower() in ("n/a", "na", "-", "."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


# Empleados puede venir como "3,500 (2024)" o "180" o "-" o vacío.
_EMPLOYEES_RE = re.compile(r"^\s*([\d,]+)")


def parse_employees(value: Any) -> int | None:
    """
    Extrae el número de empleados ignorando el año entre paréntesis.

        "3,500 (2024)"  → 3500
        "180"           → 180
        3500            → 3500
        "-"             → None
        ""              → None
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None
    s = _to_str(value)
    if s is None:
        return None
    m = _EMPLOYEES_RE.match(s)
    if not m:
        return None
    digits = m.group(1).replace(",", "")
    if not digits:
        return None
    try:
        n = int(digits)
    except ValueError:
        return None
    return n if n >= 0 else None


# Year puede venir como "1982" o "1982-05-13" o un datetime/int de Excel.
_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2}|21\d{2})\b")


def parse_year(value: Any) -> int | None:
    """
    Extrae un año de 4 dígitos en rango 1800-2199.

        "1982"          → 1982
        "1982-05-13"    → 1982
        1982            → 1982
        datetime(1982,1,1) → 1982
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value if 1800 <= value <= 2199 else None
    if hasattr(value, "year"):
        try:
            y = int(value.year)
        except (AttributeError, ValueError, TypeError):
            return None
        return y if 1800 <= y <= 2199 else None
    if isinstance(value, float):
        n = int(value)
        return n if 1800 <= n <= 2199 else None
    s = _to_str(value)
    if s is None:
        return None
    m = _YEAR_RE.search(s)
    return int(m.group(1)) if m else None


# NAICS en EMIS viene como "Broadwoven Fabric Mills(31321)" o
# "Offices of Other Holding Companies(551112); Broadwoven Fabric Mills(31321)".
# Sacamos el primer código numérico entre paréntesis.
_NAICS_RE = re.compile(r"\((\d{2,6})\)")


def parse_naics_first(value: Any) -> str | None:
    """
    Extrae el primer código NAICS (2-6 dígitos) entre paréntesis.

        "Broadwoven Fabric Mills(31321)"                → "31321"
        "Offices(551112); Broadwoven Fabric Mills(31321)" → "551112"
        "Sin código"                                     → None
    """
    s = _to_str(value)
    if s is None:
        return None
    m = _NAICS_RE.search(s)
    return m.group(1) if m else None


def parse_all_naics(value: Any) -> tuple[str, ...]:
    """
    Extrae todos los códigos NAICS (en orden de aparición), sin duplicados.

        "Offices(551112); Broadwoven Fabric Mills(31321); Other(551112)"
            → ("551112", "31321")
    """
    s = _to_str(value)
    if s is None:
        return ()
    seen: list[str] = []
    for m in _NAICS_RE.finditer(s):
        code = m.group(1)
        if code not in seen:
            seen.append(code)
    return tuple(seen)


_BOOL_TRUTHY = {"yes", "y", "true", "1", "sí", "si", "x"}
_BOOL_FALSY = {"no", "n", "false", "0", "-"}


def parse_bool_loose(value: Any) -> bool | None:
    """
    Bool tolerante. EMIS suele dejar Import/Export con un blank, espacio o "X".
    Si hay cualquier texto no-vacío que no sea explícitamente "no", lo tomamos
    como True (señal de actividad). Si es vacío o "no" explícito → None/False.

    Devuelve None cuando el campo está vacío (no asumimos), bool si hay señal.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    s = _to_str(value)
    if s is None:
        return None
    low = s.lower()
    if low in _BOOL_TRUTHY:
        return True
    if low in _BOOL_FALSY:
        return False
    # Cualquier otro contenido no vacío en Import/Export = hay actividad.
    return True


def parse_csv_list(value: Any) -> tuple[str, ...]:
    """
    Lista coma-separada → tupla de strings limpios. Vacíos descartados.

        "US, CA, MX"  → ("US", "CA", "MX")
        ""            → ()
    """
    s = _to_str(value)
    if s is None:
        return ()
    return tuple(p.strip() for p in s.split(",") if p.strip())


_COORD_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_coord(value: Any) -> float | None:
    """Coordenada (lat o lng). Ignora unidades extras."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = _to_str(value)
    if s is None:
        return None
    m = _COORD_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None
