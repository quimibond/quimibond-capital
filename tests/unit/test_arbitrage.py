"""Tests del modelo de arbitrage (LBO simplificado)."""

from __future__ import annotations

from quimibond.config_loader import Config
from quimibond.pe_classification.arbitrage import _buy_multiple, project_arbitrage


class TestBuyMultiple:
    def test_smallest_bracket(self, config: Config) -> None:
        # < $5M → 3.5x
        assert _buy_multiple(2.0, config.pe_playbook) == 3.5

    def test_bolt_on_bracket(self, config: Config) -> None:
        # $20M < bracket $50 → 6.0x
        assert _buy_multiple(20.0, config.pe_playbook) == 6.0

    def test_platform_bracket(self, config: Config) -> None:
        # $100M < bracket $150 → 8.0x
        assert _buy_multiple(100.0, config.pe_playbook) == 8.0

    def test_largest_catch_all(self, config: Config) -> None:
        # $500M > último bracket → 9.0x
        assert _buy_multiple(500.0, config.pe_playbook) == 9.0


class TestProjectArbitrage:
    def test_none_for_no_revenue(self, config: Config) -> None:
        assert project_arbitrage(None, config.pe_playbook) is None

    def test_none_for_zero_revenue(self, config: Config) -> None:
        assert project_arbitrage(0.0, config.pe_playbook) is None

    def test_basic_projection(self, config: Config) -> None:
        # Revenue $20M, ebitda 12% = $2.4M, buy 6x = $14.4M EV, exit 9x = $21.6M
        # MOIC = 21.6 / 14.4 = 1.5
        proj = project_arbitrage(20.0, config.pe_playbook)
        assert proj is not None
        assert abs(proj.ebitda_estimate_usd_mm - 2.4) < 1e-9
        assert proj.buy_multiple == 6.0
        assert proj.exit_multiple == 9.0
        assert abs(proj.ev_buy_usd_mm - 14.4) < 1e-9
        assert abs(proj.ev_exit_usd_mm - 21.6) < 1e-9
        assert abs(proj.moic - 1.5) < 1e-9
        # IRR de 1.5x en 5 años = ~8.45%
        assert 0.08 < proj.irr < 0.09

    def test_smaller_buy_multiple_yields_higher_moic(self, config: Config) -> None:
        # Empresa pequeña ($3M) compra a 3.5x, sale a 9x → MOIC ~2.57
        proj = project_arbitrage(3.0, config.pe_playbook)
        assert proj is not None
        expected_moic = 9.0 / 3.5
        assert abs(proj.moic - expected_moic) < 1e-9

    def test_ebitda_margin_override(self, config: Config) -> None:
        # Override con margen 0.20 en vez de 0.12
        proj = project_arbitrage(20.0, config.pe_playbook, ebitda_margin_override=0.20)
        assert proj is not None
        assert abs(proj.ebitda_estimate_usd_mm - 4.0) < 1e-9
