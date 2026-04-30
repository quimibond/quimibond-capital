"""
Role classifier: asigna PERoleType según revenue, prioridad y origen capital.

Reglas (en orden de evaluación):
1. Subsidiaria extranjera → STRATEGIC (jamás target).
2. Subsector Excluida → OUT_OF_SCOPE.
3. Sin revenue ni empleados → UNKNOWN_FIT.
4. Revenue conocido:
   - >= platform_min y priority ∈ {Crítica, Alta} → PLATFORM_CANDIDATE
   - en bolt_on bracket y priority ∈ {Crítica, Alta} → PRIMARY_BOLT_ON
   - en tuck_in bracket y priority ∈ {Crítica, Alta} → TUCK_IN
   - < tuck_in_min → OUT_OF_SCOPE
   - priority Media/Baja → UNKNOWN_FIT
5. Sin revenue pero con empleados: usar employees como proxy.

Devuelve `RoleAssignment(role, justification)` con texto humano de qué disparó.
"""

from __future__ import annotations

from dataclasses import dataclass

from quimibond.config_loader import Thresholds
from quimibond.models import Classification, PERoleType, RawCompany

# Prioridades que califican como targets primarios.
_PRIMARY_PRIORITIES = ("Crítica", "Alta")


@dataclass(frozen=True)
class RoleAssignment:
    role: PERoleType
    justification: str


def classify_role(
    raw: RawCompany,
    classification: Classification,
    thresholds: Thresholds,
) -> RoleAssignment:
    if classification.is_foreign_subsidiary:
        return RoleAssignment(
            "STRATEGIC",
            f"Subsidiaria extranjera (capital {classification.capital_origin}).",
        )

    if classification.subsector_priority == "Excluida":
        return RoleAssignment(
            "OUT_OF_SCOPE",
            f"Subsector excluido por playbook ({classification.subsector}).",
        )

    rev = raw.revenue_usd_mm
    emps = raw.employees
    rb = thresholds.revenue_brackets_usd_mm
    eb = thresholds.employee_brackets
    is_primary_priority = classification.subsector_priority in _PRIMARY_PRIORITIES

    if rev is None and emps is None:
        return RoleAssignment(
            "UNKNOWN_FIT",
            "Sin revenue ni empleados — no clasificable por tamaño.",
        )

    # Si tenemos revenue, manda el revenue (más preciso que empleados).
    if rev is not None:
        if rev < rb.tuck_in_min:
            return RoleAssignment(
                "OUT_OF_SCOPE",
                f"Revenue ${rev:.1f}M < tuck-in min ${rb.tuck_in_min:.1f}M.",
            )
        if rev >= rb.platform_min:
            if is_primary_priority:
                return RoleAssignment(
                    "PLATFORM_CANDIDATE",
                    (
                        f"Revenue ${rev:.1f}M ≥ platform_min ${rb.platform_min:.1f}M "
                        f"y subsector {classification.subsector_priority}."
                    ),
                )
            return RoleAssignment(
                "UNKNOWN_FIT",
                (
                    f"Revenue ${rev:.1f}M apto para platform pero subsector "
                    f"{classification.subsector_priority} no es prioritario."
                ),
            )
        if rb.bolt_on_min <= rev < rb.bolt_on_max:
            if is_primary_priority:
                return RoleAssignment(
                    "PRIMARY_BOLT_ON",
                    (
                        f"Revenue ${rev:.1f}M en bolt-on bracket "
                        f"[${rb.bolt_on_min:.1f}M-${rb.bolt_on_max:.1f}M], subsector "
                        f"{classification.subsector_priority}."
                    ),
                )
            return RoleAssignment(
                "UNKNOWN_FIT",
                f"Revenue ${rev:.1f}M en bolt-on pero subsector "
                f"{classification.subsector_priority} no prioritario.",
            )
        if rb.tuck_in_min <= rev < rb.tuck_in_max:
            if is_primary_priority:
                return RoleAssignment(
                    "TUCK_IN",
                    (
                        f"Revenue ${rev:.1f}M en tuck-in bracket "
                        f"[${rb.tuck_in_min:.1f}M-${rb.tuck_in_max:.1f}M], subsector "
                        f"{classification.subsector_priority}."
                    ),
                )
            return RoleAssignment(
                "UNKNOWN_FIT",
                f"Revenue ${rev:.1f}M en tuck-in pero subsector no prioritario.",
            )
        # Revenue en hueco entre brackets
        return RoleAssignment(
            "UNKNOWN_FIT",
            f"Revenue ${rev:.1f}M en hueco entre brackets — revisar manualmente.",
        )

    # Sin revenue, pero con empleados — usar como proxy.
    assert emps is not None
    if emps >= eb.platform_min and is_primary_priority:
        return RoleAssignment(
            "PLATFORM_CANDIDATE",
            f"Sin revenue, pero {emps} empleados ≥ {eb.platform_min} (proxy de tamaño platform).",
        )
    if emps >= eb.bolt_on_min and is_primary_priority:
        return RoleAssignment(
            "PRIMARY_BOLT_ON",
            f"Sin revenue, pero {emps} empleados en bolt-on (proxy de tamaño).",
        )
    if emps >= eb.tuck_in_min and is_primary_priority:
        return RoleAssignment(
            "TUCK_IN",
            f"Sin revenue, pero {emps} empleados en tuck-in (proxy).",
        )
    if emps < eb.tuck_in_min:
        return RoleAssignment(
            "OUT_OF_SCOPE",
            f"Sin revenue y solo {emps} empleados — fuera de tamaño mínimo.",
        )
    return RoleAssignment(
        "UNKNOWN_FIT",
        f"Sin revenue, {emps} empleados, subsector {classification.subsector_priority}.",
    )
