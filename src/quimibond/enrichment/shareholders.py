"""
Análisis de estructura accionaria: origen de capital + familia detectada.

Heurísticas (en orden de evaluación):

1. Si hay un código de país no-MX dentro de paréntesis en shareholders_text
   ('Toray Industries (JP)', 'Coats Plc (UK)') o el shareholder text apunta
   a una matriz extranjera → 'Subsidiaria/Extranjera'.
2. Si el texto contiene 'cooperativa' / 'soc. cooperativa' → 'Cooperativa'.
3. Si extra.listed == 'Listed' o tiene ticker BMV/ISIN → 'Público'.
4. Si shareholders/executives contiene >=1 apellido de families.yaml →
   'Familiar/MX' (y se reporta el primer apellido detectado).
5. Si shareholders_text tiene contenido pero ninguna señal anterior matchea
   → 'Privado/MX'.
6. Si shareholders_text está vacío y no hay otras señales → 'Desconocido'.

Devuelve un `ShareholderAnalysis` con todos los flags derivados — el caller
los traduce a campos de Classification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from quimibond.config_loader import Families
from quimibond.models import CapitalOriginType, RawCompany

# Códigos de país en paréntesis. EMIS los pone como '(US)', '(JP)', '(DE)'.
# 'MX' explícito significa subsidiaria local de matriz mexicana — NO foreign.
_COUNTRY_PAREN_RE = re.compile(r"\(([A-Z]{2})\)")
_FOREIGN_HINTS = re.compile(
    r"\b(plc|sa\b|gmbh|aktiengesellschaft|ltd\b|limited|inc\b|incorporated|"
    r"corporation\b|holdings? plc|industries|co\.,? ltd|oy\b|spa\b|kg\b)\b",
    re.IGNORECASE,
)
_COOP_HINTS = re.compile(
    r"\b(cooperativa|cooperative|soc(\.|iedad)?\s*coop)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ShareholderAnalysis:
    capital_origin: CapitalOriginType
    is_familiar_mx: bool
    is_foreign_subsidiary: bool
    detected_family: str | None
    foreign_country: str | None  # ISO-2 si aplica
    signals: tuple[str, ...]


def _detect_foreign_country(text: str) -> str | None:
    """Devuelve el primer código de país no-MX entre paréntesis."""
    for match in _COUNTRY_PAREN_RE.finditer(text):
        code = match.group(1)
        if code != "MX":
            return code
    return None


def _detect_family(text_lower: str, families: Families) -> str | None:
    """
    Busca el primer apellido textil clásico que aparezca como palabra completa
    o casi (case-insensitive). Devuelve el apellido en su capitalización
    original del config.
    """
    for family in families.families:
        # Word boundary alrededor del apellido. Permite multi-palabra.
        pattern = r"\b" + re.escape(family.lower()) + r"\b"
        if re.search(pattern, text_lower):
            return family
    return None


def analyze_shareholders(
    raw: RawCompany,
    families: Families,
) -> ShareholderAnalysis:
    sh = (raw.shareholders_text or "").strip()
    ex = (raw.executives_text or "").strip()
    combined = f"{sh}\n{ex}".strip()
    combined_lower = combined.lower()

    signals: list[str] = []

    # 1. Subsidiaria extranjera
    foreign_code = _detect_foreign_country(combined)
    looks_foreign_legal = bool(_FOREIGN_HINTS.search(combined))
    is_foreign = foreign_code is not None or (
        bool(sh) and looks_foreign_legal and "mx" not in combined_lower
    )

    # 2. Cooperativa
    is_coop = bool(_COOP_HINTS.search(combined))

    # 3. Público (listed)
    listed_value = (raw.extra.get("listed") or "").lower() if isinstance(raw.extra.get("listed"), str) else ""
    has_ticker = bool(raw.extra.get("bmv_ticker") or raw.extra.get("isin"))
    is_public = "listed" in listed_value and "unlisted" not in listed_value
    if has_ticker:
        is_public = True

    # 4. Familia MX
    family = _detect_family(combined_lower, families)

    # Resolver origen — ORDEN IMPORTA
    origin: CapitalOriginType
    if is_foreign:
        origin = "Subsidiaria/Extranjera"
        signals.append(f"foreign_country={foreign_code}" if foreign_code else "legal_form_foreign")
    elif is_coop:
        origin = "Cooperativa"
        signals.append("cooperativa_keyword")
    elif is_public:
        origin = "Público"
        signals.append("listed_or_ticker")
    elif family is not None:
        origin = "Familiar/MX"
        signals.append(f"family={family}")
    elif sh:
        # Hay info de shareholders pero no sabemos clasificarla → privado MX por defecto
        origin = "Privado/MX"
        signals.append("private_default")
    else:
        origin = "Desconocido"

    return ShareholderAnalysis(
        capital_origin=origin,
        is_familiar_mx=(origin == "Familiar/MX"),
        is_foreign_subsidiary=(origin == "Subsidiaria/Extranjera"),
        detected_family=family,
        foreign_country=foreign_code,
        signals=tuple(signals),
    )
