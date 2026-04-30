"""
Modelo LBO simplificado: compra a múltiplo bajo, vende al consolidado.

Asume:
- EBITDA = revenue * playbook.ebitda_margin_default (12% default).
- Buy multiple = lookup en bracket por revenue (4-9x según tamaño).
- Exit multiple = playbook.exit_multiple_default (9x default).
- Sin apalancamiento, sin reinversión — sólo cambio de múltiplo.
- MOIC = ev_exit / ev_buy.
- IRR = MOIC^(1/hold_years) - 1.

Devuelve None si no hay revenue (no hay base para el modelo).
"""

from __future__ import annotations

from quimibond.config_loader import PEPlaybook
from quimibond.models import ArbitrageProjection


def _buy_multiple(revenue_usd_mm: float, playbook: PEPlaybook) -> float:
    """Lookup en buy_multiples_by_size. Brackets ordenados ascendentes; null = catch-all."""
    for bracket in playbook.buy_multiples_by_size:
        if bracket.max_revenue is None or revenue_usd_mm < bracket.max_revenue:
            return bracket.multiple
    # No debería pasar — el último bracket siempre tiene max_revenue=None.
    return playbook.buy_multiples_by_size[-1].multiple


def project_arbitrage(
    revenue_usd_mm: float | None,
    playbook: PEPlaybook,
    *,
    ebitda_margin_override: float | None = None,
) -> ArbitrageProjection | None:
    """Proyecta el LBO simplificado. None si no hay revenue."""
    if revenue_usd_mm is None or revenue_usd_mm <= 0:
        return None

    margin = ebitda_margin_override if ebitda_margin_override is not None else playbook.ebitda_margin_default
    ebitda = revenue_usd_mm * margin
    buy_x = _buy_multiple(revenue_usd_mm, playbook)
    exit_x = playbook.exit_multiple_default
    hold = playbook.hold_period_years

    ev_buy = ebitda * buy_x
    ev_exit = ebitda * exit_x
    moic = ev_exit / ev_buy if ev_buy > 0 else 0.0
    irr = moic ** (1 / hold) - 1 if moic > 0 else -1.0

    return ArbitrageProjection(
        buy_multiple=buy_x,
        exit_multiple=exit_x,
        ebitda_estimate_usd_mm=ebitda,
        ev_buy_usd_mm=ev_buy,
        ev_exit_usd_mm=ev_exit,
        moic=moic,
        irr=irr,
        hold_period_years=hold,
    )
