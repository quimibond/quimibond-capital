"""
Invariantes pre-output. Si alguna falla, el pipeline NO genera workbook.

Invariantes verificadas:
1. No duplicados por emis_id.
2. Todos los pe_role son valores válidos del Literal type (pydantic ya lo
   valida en construction, repetimos como defensa en profundidad).
3. Pesos de scoring del playbook suman 1.0 (config_loader ya lo valida, repetir).
4. lever_combined ∈ [0, 1] para todas.
5. lever_combined respeta role_combined_cap del playbook (PLATFORM 1.0,
   STRATEGIC 0.30, etc.).
6. PLATFORM_CANDIDATE ⇒ revenue_usd_mm >= platform_min (o employees suficientes).
7. STRATEGIC ⇒ is_foreign_subsidiary (caso esperado del playbook).
8. arbitrage.ebitda_estimate ≈ revenue * playbook.ebitda_margin_default.
9. arbitrage.moic == ev_exit / ev_buy (within tolerancia).
10. Si no hay revenue_usd_mm, arbitrage debe ser None.

Si una invariante falla → InvariantViolation con detalle: stack-trace claro
con el emis_id y descripción humana.
"""

from __future__ import annotations

from typing import get_args

from quimibond.config_loader import Config
from quimibond.models import Company, PERoleType, PipelineData

VALID_ROLES = frozenset(get_args(PERoleType))
TOLERANCE = 1e-6


class InvariantViolation(Exception):
    """Violación de una invariante pre-output. El pipeline debe abortar."""


def _check(condition: bool, msg: str) -> None:
    if not condition:
        raise InvariantViolation(msg)


def _verify_unique_ids(companies: tuple[Company, ...]) -> None:
    seen: set[str] = set()
    for c in companies:
        if c.emis_id in seen:
            raise InvariantViolation(f"emis_id duplicado: {c.emis_id} ({c.company_name!r})")
        seen.add(c.emis_id)


def _verify_role_value(c: Company) -> None:
    _check(
        c.pe_role in VALID_ROLES,
        f"{c.emis_id}: pe_role inválido = {c.pe_role!r}",
    )


def _verify_lever_combined(c: Company, config: Config) -> None:
    combined = c.levers.combined
    _check(
        0.0 <= combined <= 1.0,
        f"{c.emis_id}: lever_combined fuera de [0,1] = {combined}",
    )
    cap = config.pe_playbook.role_combined_cap.get(c.pe_role, 1.0)
    _check(
        combined <= cap + TOLERANCE,
        f"{c.emis_id}: lever_combined={combined} excede cap={cap} para role {c.pe_role}",
    )


def _verify_platform_threshold(c: Company, config: Config) -> None:
    if c.pe_role != "PLATFORM_CANDIDATE":
        return
    rb = config.pe_playbook  # noqa: F841 — usado abajo si extendemos
    pmin = config.thresholds.revenue_brackets_usd_mm.platform_min
    emin = config.thresholds.employee_brackets.platform_min
    rev_ok = c.revenue_usd_mm is not None and c.revenue_usd_mm >= pmin
    emp_ok = c.employees is not None and c.employees >= emin
    _check(
        rev_ok or emp_ok,
        f"{c.emis_id}: PLATFORM_CANDIDATE sin revenue ni empleados suficientes "
        f"(rev={c.revenue_usd_mm}, emp={c.employees}, "
        f"requerido rev≥${pmin}M o emp≥{emin}).",
    )


def _verify_strategic_is_foreign(c: Company) -> None:
    if c.pe_role != "STRATEGIC":
        return
    _check(
        c.is_foreign_subsidiary,
        f"{c.emis_id}: STRATEGIC pero NO es foreign subsidiary "
        f"(capital_origin={c.classification.capital_origin}). "
        f"Si es STRATEGIC por otra razón documentar excepción en role.py.",
    )


def _verify_arbitrage_consistency(c: Company, config: Config) -> None:
    ar = c.arbitrage
    if c.revenue_usd_mm is None:
        _check(
            ar is None,
            f"{c.emis_id}: revenue None pero arbitrage no es None",
        )
        return
    if ar is None:
        # revenue presente pero arbitrage None — sólo permitido si revenue <= 0
        _check(
            c.revenue_usd_mm <= 0,
            f"{c.emis_id}: revenue=${c.revenue_usd_mm:.2f}M pero arbitrage=None",
        )
        return

    margin = config.pe_playbook.ebitda_margin_default
    expected_ebitda = c.revenue_usd_mm * margin
    _check(
        abs(ar.ebitda_estimate_usd_mm - expected_ebitda) <= TOLERANCE,
        f"{c.emis_id}: ebitda_estimate={ar.ebitda_estimate_usd_mm} != "
        f"revenue*{margin}={expected_ebitda}",
    )

    if ar.ev_buy_usd_mm > 0:
        expected_moic = ar.ev_exit_usd_mm / ar.ev_buy_usd_mm
        _check(
            abs(ar.moic - expected_moic) <= TOLERANCE,
            f"{c.emis_id}: moic={ar.moic} != ev_exit/ev_buy={expected_moic}",
        )


def assert_invariants(data: PipelineData, config: Config) -> None:
    """
    Verifica todas las invariantes. Levanta InvariantViolation al primer fallo.

    No retorna nada — el pipeline asume que si esto retorna, todo está OK
    para generar el workbook.
    """
    # Config-level (defensa en profundidad, config_loader ya validó al cargar)
    weights = config.pe_playbook.scoring_weights
    total_w = weights.lever_cost + weights.lever_revenue + weights.lever_arbitrage
    _check(
        abs(total_w - 1.0) <= TOLERANCE,
        f"scoring_weights suman {total_w}, no 1.0",
    )

    # Universe-level
    _verify_unique_ids(data.companies)

    # Per-company
    for c in data.companies:
        _verify_role_value(c)
        _verify_lever_combined(c, config)
        _verify_platform_threshold(c, config)
        _verify_strategic_is_foreign(c)
        _verify_arbitrage_consistency(c, config)
