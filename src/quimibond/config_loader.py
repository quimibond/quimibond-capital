"""
Carga y valida los YAMLs de config/.

Cada YAML mapea 1:1 a un modelo pydantic. Si un YAML falla validación, el
pipeline NO arranca — falla con mensaje claro.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from quimibond.models import (
    CapitalOriginType,
    ClientType,
    PERoleType,
    PriorityType,
)

# ---------------------------------------------------------------------------
# thresholds.yaml
# ---------------------------------------------------------------------------


class RevenueBrackets(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    platform_min: float = Field(..., gt=0)
    bolt_on_min: float = Field(..., gt=0)
    bolt_on_max: float = Field(..., gt=0)
    tuck_in_min: float = Field(..., gt=0)
    tuck_in_max: float = Field(..., gt=0)
    out_of_scope_max: float = Field(..., gt=0)

    @model_validator(mode="after")
    def _check_ordering(self) -> RevenueBrackets:
        if not (self.tuck_in_min < self.tuck_in_max <= self.bolt_on_min < self.bolt_on_max <= self.platform_min):
            raise ValueError(
                "Revenue brackets desordenados: "
                f"tuck_in[{self.tuck_in_min},{self.tuck_in_max}] < "
                f"bolt_on[{self.bolt_on_min},{self.bolt_on_max}] < platform[{self.platform_min}]"
            )
        return self


class EmployeeBrackets(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    platform_min: int = Field(..., gt=0)
    bolt_on_min: int = Field(..., gt=0)
    tuck_in_min: int = Field(..., gt=0)


class AgeThresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edad_madura_min: int = Field(..., ge=0)
    fatigue_age_high: int = Field(..., ge=0)
    fatigue_age_medium: int = Field(..., ge=0)


class ProductivityThresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    high: float = Field(..., gt=0)
    medium: float = Field(..., gt=0)
    low: float = Field(..., gt=0)


class PriorityStates(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cluster_textil: tuple[str, ...]
    cluster_automotriz: tuple[str, ...]


class SaturationThresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    consolidated_ratio_atractivo_max: float = Field(..., ge=0.0, le=1.0)
    consolidated_ratio_saturado_min: float = Field(..., ge=0.0, le=1.0)
    min_companies_for_verdict: int = Field(..., ge=1)


class ExclusionRules(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    naics_excluded: tuple[str, ...]
    activity_keywords_excluded: tuple[str, ...]


class Thresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revenue_brackets_usd_mm: RevenueBrackets
    employee_brackets: EmployeeBrackets
    age_thresholds: AgeThresholds
    productivity_thresholds_usd_per_employee: ProductivityThresholds
    priority_states: PriorityStates
    saturation: SaturationThresholds
    exclusion: ExclusionRules


# ---------------------------------------------------------------------------
# pe_playbook.yaml
# ---------------------------------------------------------------------------


class BuyMultipleBracket(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_revenue: float | None
    multiple: float = Field(..., gt=0)


class ScoringWeights(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    lever_cost: float = Field(..., ge=0.0, le=1.0)
    lever_revenue: float = Field(..., ge=0.0, le=1.0)
    lever_arbitrage: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _sum_to_one(self) -> ScoringWeights:
        total = self.lever_cost + self.lever_revenue + self.lever_arbitrage
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"scoring_weights deben sumar 1.0, suman {total}")
        return self


class PEPlaybook(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    buy_multiples_by_size: tuple[BuyMultipleBracket, ...]
    exit_multiple_default: float = Field(..., gt=0)
    ebitda_margin_default: float = Field(..., gt=0, le=1.0)
    hold_period_years: int = Field(..., ge=1)
    discount_rate: float = Field(..., ge=0.0, le=1.0)
    exchange_rate_mxn_usd: float = Field(..., gt=0)
    scoring_weights: ScoringWeights
    subsector_priority_score: dict[PriorityType, float]
    capital_origin_score: dict[CapitalOriginType, float]
    role_combined_cap: dict[PERoleType, float]

    @field_validator("subsector_priority_score", "capital_origin_score", "role_combined_cap")
    @classmethod
    def _scores_in_range(cls, v: dict[Any, float]) -> dict[Any, float]:
        for k, val in v.items():
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"score {k}={val} fuera de [0, 1]")
        return v

    @model_validator(mode="after")
    def _buy_multiples_increasing(self) -> PEPlaybook:
        prev_max: float = -1.0
        seen_null = False
        for b in self.buy_multiples_by_size:
            if seen_null:
                raise ValueError("buy_multiples_by_size: bracket con max_revenue=null debe ser el último")
            if b.max_revenue is None:
                seen_null = True
                continue
            if b.max_revenue <= prev_max:
                raise ValueError(
                    f"buy_multiples_by_size: max_revenue debe ser estrictamente creciente "
                    f"({b.max_revenue} <= {prev_max})"
                )
            prev_max = b.max_revenue
        return self


# ---------------------------------------------------------------------------
# classifiers.yaml
# ---------------------------------------------------------------------------


class KeywordRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    keywords: tuple[str, ...]


class SubsectorTier(BaseModel):
    """
    Pydantic no soporta nativo "dict de KeywordRule arbitrario" sin construir,
    así que materializamos a un dict[str, KeywordRule] vía root validator.
    """

    model_config = ConfigDict(frozen=True)

    rules: dict[str, KeywordRule]

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> SubsectorTier:
        return cls(rules={k: KeywordRule(**v) for k, v in raw.items()})


class Classifiers(BaseModel):
    """
    classifiers.yaml estructura:
        subsectors:
          critica: { rule_name: { keywords: [...] }, ... }
          alta: ...
          media: ...
          baja: ...
        quimibond_processes:
          process_name: { keywords: [...] }, ...
        client_types:
          ClientType: { keywords: [...] }, ...
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    subsectors: dict[PriorityType, SubsectorTier]
    quimibond_processes: dict[str, KeywordRule]
    client_types: dict[ClientType, KeywordRule]


# ---------------------------------------------------------------------------
# families.yaml
# ---------------------------------------------------------------------------


class Families(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    families: tuple[str, ...]


# ---------------------------------------------------------------------------
# Contenedor agregado
# ---------------------------------------------------------------------------


class Config(BaseModel):
    """Bundle de toda la configuración del pipeline."""

    model_config = ConfigDict(frozen=True)

    thresholds: Thresholds
    pe_playbook: PEPlaybook
    classifiers: Classifiers
    families: Families


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Config no encontrada: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config {path} debe ser un mapping en el top-level")
    return data


def _build_classifiers(raw: dict[str, Any]) -> Classifiers:
    subsectors_raw = raw.get("subsectors", {})
    subsectors: dict[PriorityType, SubsectorTier] = {}
    for tier_name, tier_raw in subsectors_raw.items():
        if not isinstance(tier_raw, Mapping):
            raise ValueError(f"classifiers.subsectors.{tier_name} debe ser mapping")
        subsectors[tier_name] = SubsectorTier.from_raw(tier_raw)

    return Classifiers(
        subsectors=subsectors,
        quimibond_processes={
            k: KeywordRule(**v) for k, v in raw.get("quimibond_processes", {}).items()
        },
        client_types={k: KeywordRule(**v) for k, v in raw.get("client_types", {}).items()},
    )


def load_config(config_dir: Path | str) -> Config:
    """
    Carga toda la configuración desde un directorio que contenga:
      - thresholds.yaml
      - pe_playbook.yaml
      - classifiers.yaml
      - families.yaml

    Raises:
        FileNotFoundError: si falta algún YAML.
        pydantic.ValidationError: si algún YAML viola sus invariantes.
    """
    config_dir = Path(config_dir)
    return Config(
        thresholds=Thresholds(**_load_yaml(config_dir / "thresholds.yaml")),
        pe_playbook=PEPlaybook(**_load_yaml(config_dir / "pe_playbook.yaml")),
        classifiers=_build_classifiers(_load_yaml(config_dir / "classifiers.yaml")),
        families=Families(**_load_yaml(config_dir / "families.yaml")),
    )
