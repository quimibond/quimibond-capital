"""
Modelos de dominio Quimibond Capital.

Reglas:
- Todo modelo es frozen (inmutable) salvo contenedores agregados.
- RawCompany representa el contrato de salida de cualquier SourceLoader.
- Company es el resultado de enrichment + classification + scoring.
- Los enums están como Literal types para que mypy los chequee end-to-end.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Enums tipados (Literal para que mypy los valide en todo el flujo)
# ---------------------------------------------------------------------------

PERoleType = Literal[
    "PLATFORM_CANDIDATE",
    "PRIMARY_BOLT_ON",
    "TUCK_IN",
    "STRATEGIC",
    "UNKNOWN_FIT",
    "OUT_OF_SCOPE",
]

PriorityType = Literal["Crítica", "Alta", "Media", "Baja", "Excluida"]

CapitalOriginType = Literal[
    "Familiar/MX",
    "Privado/MX",
    "Subsidiaria/Extranjera",
    "Cooperativa",
    "Público",
    "Desconocido",
]

ClientType = Literal[
    "Automotriz",
    "Industrial",
    "Hogar",
    "Médico/Higiene",
    "Apparel",
    "Mixto",
    "Desconocido",
]

LineageSource = Literal["raw_emis", "raw_denue", "raw_other", "calculated", "config", "manual"]

SaturationVerdictType = Literal["Atractivo", "Mixto", "Saturado", "Insuficiente"]


# ---------------------------------------------------------------------------
# Trazabilidad
# ---------------------------------------------------------------------------


class CellLineage(BaseModel):
    """Origen de un valor calculado, para rastreo en el workbook."""

    model_config = ConfigDict(frozen=True)

    value: Any
    source: LineageSource
    formula: str | None = None
    inputs: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Capa raw (output de cualquier SourceLoader)
# ---------------------------------------------------------------------------


class RawCompany(BaseModel):
    """
    Empresa tal como viene de una fuente (EMIS, DENUE, manual, etc.).

    Todo es opcional salvo identidad y origen — cada fuente aporta un subset.
    El enrichment es responsable de derivar campos calculados.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    # Identidad — siempre presente
    source_id: str = Field(..., min_length=1, description="ID estable dentro de la fuente.")
    source: str = Field(..., min_length=1, description="Nombre de la fuente (EMIS, DENUE, ...).")
    source_as_of: date

    # Identidad textual
    company_name: str = Field(..., min_length=1)
    legal_name: str | None = None
    rfc: str | None = None
    naics: str | None = Field(default=None, description="Código SCIAN/NAICS de 2-6 dígitos.")
    activity_description: str | None = None

    # Geografía
    country: str | None = "MX"
    state: str | None = None
    municipality: str | None = None
    city: str | None = None
    address: str | None = None
    zip_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    # Financieros (USD millones para uniformidad cross-source)
    revenue_usd_mm: float | None = None
    revenue_year: int | None = None
    ebitda_usd_mm: float | None = None
    ebitda_margin: float | None = Field(default=None, ge=-1.0, le=1.0)
    employees: int | None = Field(default=None, ge=0)
    incorporation_year: int | None = Field(default=None, ge=1800, le=2100)

    # Comercial
    is_exporter: bool | None = None
    export_destinations: tuple[str, ...] = ()
    main_customers: tuple[str, ...] = ()

    # Estructura
    shareholders_text: str | None = None
    executives_text: str | None = None
    website: str | None = None
    email: str | None = None
    phone: str | None = None

    # Metadata libre por fuente (no entra al esquema canónico)
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("naics", mode="before")
    @classmethod
    def _normalize_naics(cls, v: Any) -> Any:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None


# ---------------------------------------------------------------------------
# Sub-modelos de clasificación PE
# ---------------------------------------------------------------------------


class FatigueScore(BaseModel):
    """Owner-fatigue: 0 = sin señales, 1 = máxima fatiga."""

    model_config = ConfigDict(frozen=True)

    score: float = Field(..., ge=0.0, le=1.0)
    signals: tuple[str, ...] = ()
    justification: str


class LeverScores(BaseModel):
    """Tres palancas + score combinado."""

    model_config = ConfigDict(frozen=True)

    cost: float = Field(..., ge=0.0, le=1.0)
    revenue: float = Field(..., ge=0.0, le=1.0)
    arbitrage: float = Field(..., ge=0.0, le=1.0)
    combined: float = Field(..., ge=0.0, le=1.0)
    cost_justification: str
    revenue_justification: str
    arbitrage_justification: str


class ArbitrageProjection(BaseModel):
    """Modelo LBO simplificado: compra a múltiplo bajo, vende al consolidado."""

    model_config = ConfigDict(frozen=True)

    buy_multiple: float = Field(..., ge=0.0)
    exit_multiple: float = Field(..., ge=0.0)
    ebitda_estimate_usd_mm: float
    ev_buy_usd_mm: float
    ev_exit_usd_mm: float
    moic: float
    irr: float
    hold_period_years: int = Field(..., ge=1)


class SaturationVerdict(BaseModel):
    """Resultado del análisis de saturación por subsegmento."""

    model_config = ConfigDict(frozen=True)

    subsegment: str
    total_companies: int = Field(..., ge=0)
    consolidated: int = Field(..., ge=0)
    accessible: int = Field(..., ge=0)
    verdict: SaturationVerdictType
    notes: str = ""


class Classification(BaseModel):
    """Clasificación derivada de enrichment + config."""

    model_config = ConfigDict(frozen=True)

    subsector: str
    subsector_priority: PriorityType
    quimibond_processes: tuple[str, ...] = ()
    main_client_type: ClientType = "Desconocido"
    capital_origin: CapitalOriginType = "Desconocido"
    is_familiar_mx: bool = False
    is_foreign_subsidiary: bool = False
    detected_family: str | None = None


# ---------------------------------------------------------------------------
# Capa enriquecida — el output del pipeline
# ---------------------------------------------------------------------------


class Company(BaseModel):
    """Empresa enriquecida con todos los campos derivados."""

    model_config = ConfigDict(frozen=True)

    # Identidad
    emis_id: str = Field(..., min_length=1)
    company_name: str = Field(..., min_length=1)
    legal_name: str | None = None
    rfc: str | None = None

    # Origen del dato
    source: str
    source_as_of: date

    # Geografía
    state: str | None = None
    municipality: str | None = None
    location_label: str | None = None  # "Toluca, Estado de México"

    # Financieros
    revenue_usd_mm: float | None = None
    revenue_year: int | None = None
    employees: int | None = Field(default=None, ge=0)
    incorporation_year: int | None = Field(default=None, ge=1800, le=2100)
    age_years: int | None = Field(default=None, ge=0)
    productivity_usd_per_employee: float | None = Field(default=None, ge=0.0)
    ebitda_estimate_usd_mm: float | None = None

    # Clasificación
    classification: Classification

    # Clasificación PE
    pe_role: PERoleType
    pe_role_justification: str

    fatigue: FatigueScore
    levers: LeverScores
    arbitrage: ArbitrageProjection | None = None  # None si revenue desconocido

    # Booleans calculados (cache de classification para uso ergonómico)
    is_familiar_mx: bool = False
    is_foreign_subsidiary: bool = False
    edad_madura: bool = False


# ---------------------------------------------------------------------------
# Contenedores
# ---------------------------------------------------------------------------


class PipelineData(BaseModel):
    """Todo el dataset que viaja entre etapas del pipeline."""

    model_config = ConfigDict(frozen=True)

    companies: tuple[Company, ...]
    saturation: tuple[SaturationVerdict, ...] = ()
    generated_at: date

    @property
    def n_companies(self) -> int:
        return len(self.companies)
