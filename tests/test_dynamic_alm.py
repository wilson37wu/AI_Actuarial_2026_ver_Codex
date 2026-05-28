"""
Unit tests for DynamicALMEngine (par_model_v2/projection/dynamic_alm.py)

Covers IA TAS M §3.6.2 VR-U02 requirements:
  - 11 test classes / 44+ individual tests
  - test_rebalancing_to_saa: 100%-cash initial portfolio triggers buys
  - Zero-denominator guard (empty portfolio)
  - Transaction cost arithmetic
  - Portfolio MV conservation net of costs
  - Threshold band prevents unnecessary trading
  - Multi-period run correctness

Run:
    PYTHONPATH=. pytest tests/test_dynamic_alm.py -v
"""

from __future__ import annotations

import math
import pytest
import numpy as np

from par_model_v2.projection.dynamic_alm import (
    ASSET_CLASSES,
    MIN_TRADE_SIZE,
    ALMPeriodResult,
    DynamicALMEngine,
    PortfolioState,
    RebalanceTrade,
    SAAPolicy,
)


# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

def _saa_40_40_20_0(**kwargs) -> SAAPolicy:
    """Standard SAA: 40% Govt, 40% Credit, 20% Equity, 0% Cash."""
    defaults = dict(
        weights={"Govt": 0.40, "Credit": 0.40, "Equity": 0.20, "Cash": 0.00},
        rebalancing_threshold=0.0,
        buy_cost_rate=0.002,
        sell_cost_rate=0.001,
    )
    defaults.update(kwargs)
    return SAAPolicy(**defaults)


def _saa_balanced(**kwargs) -> SAAPolicy:
    """Balanced SAA: 35% Govt, 30% Credit, 20% Equity, 15% Cash."""
    defaults = dict(
        weights={"Govt": 0.35, "Credit": 0.30, "Equity": 0.20, "Cash": 0.15},
        rebalancing_threshold=0.0,
        buy_cost_rate=0.002,
        sell_cost_rate=0.001,
    )
    defaults.update(kwargs)
    return SAAPolicy(**defaults)


def _at_saa(total: float = 1_000_000.0) -> PortfolioState:
    """Portfolio already exactly at the 40/40/20/0 SAA."""
    return PortfolioState(holdings={
        "Govt":   0.40 * total,
        "Credit": 0.40 * total,
        "Equity": 0.20 * total,
        "Cash":   0.00 * total,
    })


def _all_cash(total: float = 1_000_000.0) -> PortfolioState:
    """Portfolio that is 100% cash."""
    return PortfolioState(holdings={
        "Govt":   0.0,
        "Credit": 0.0,
        "Equity": 0.0,
        "Cash":   total,
    })


ZERO_RETURNS = {"Govt": 0.0, "Credit": 0.0, "Equity": 0.0, "Cash": 0.0}
FLAT_RETURNS = {"Govt": 0.032, "Credit": 0.038, "Equity": 0.07, "Cash": 0.02}


# ---------------------------------------------------------------------------
# 1. SAAPolicy construction and validation
# ---------------------------------------------------------------------------

class TestSAAPolicy:
    def test_weights_sum_to_one(self):
        saa = _saa_40_40_20_0()
        assert sum(saa.weights.values()) == pytest.approx(1.0)

    def test_invalid_weights_raises(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            SAAPolicy(weights={"Govt": 0.40, "Credit": 0.40, "Equity": 0.10, "Cash": 0.0})

    def test_negative_threshold_raises(self):
        with pytest.raises(ValueError, match="threshold"):
            _saa_40_40_20_0(rebalancing_threshold=-0.01)

    def test_negative_cost_raises(self):
        with pytest.raises(ValueError, match="cost"):
            _saa_40_40_20_0(buy_cost_rate=-0.001)

    def test_target_mv_scales_correctly(self):
        saa = _saa_40_40_20_0()
        target = saa.target_mv(1_000_000.0)
        assert target["Govt"]   == pytest.approx(400_000.0)
        assert target["Credit"] == pytest.approx(400_000.0)
        assert target["Equity"] == pytest.approx(200_000.0)
        assert target["Cash"]   == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 2. PortfolioState helpers
# ---------------------------------------------------------------------------

class TestPortfolioState:
    def test_total_mv(self):
        p = _all_cash(500_000.0)
        assert p.total_mv() == pytest.approx(500_000.0)

    def test_weights_all_cash(self):
        p = _all_cash(1_000_000.0)
        w = p.weights()
        assert w["Cash"] == pytest.approx(1.0)
        assert w["Govt"] == pytest.approx(0.0)

    def test_weights_zero_portfolio(self):
        """Zero portfolio must not raise ZeroDivisionError."""
        p = PortfolioState(holdings={"Govt": 0.0, "Credit": 0.0, "Equity": 0.0, "Cash": 0.0})
        w = p.weights()
        assert all(v == 0.0 for v in w.values())

    def test_total_mv_zero_portfolio(self):
        p = PortfolioState(holdings={})
        assert p.total_mv() == pytest.approx(0.0)

    def test_copy_is_independent(self):
        p = _all_cash(1_000_000.0)
        q = p.copy()
        q.holdings["Cash"] = 0.0
        assert p.holdings["Cash"] == pytest.approx(1_000_000.0)


# ---------------------------------------------------------------------------
# 3. RebalanceTrade validation
# ---------------------------------------------------------------------------

class TestRebalanceTrade:
    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError, match="direction"):
            RebalanceTrade(asset_class="Govt", direction="HOLD", gross_amount=100.0)

    def test_negative_gross_raises(self):
        with pytest.raises(ValueError, match="gross_amount"):
            RebalanceTrade(asset_class="Govt", direction="BUY", gross_amount=-100.0)

    def test_buy_trade_fields(self):
        trade = RebalanceTrade(
            asset_class="Govt", direction="BUY", gross_amount=100_000.0,
            cost=200.0, net_amount=100_200.0,
        )
        assert trade.direction == "BUY"
        assert trade.gross_amount == pytest.approx(100_000.0)
        assert trade.cost == pytest.approx(200.0)
        assert trade.net_amount == pytest.approx(100_200.0)


# ---------------------------------------------------------------------------
# 4. _apply_returns — investment return step
# ---------------------------------------------------------------------------

class TestApplyReturns:
    def setup_method(self):
        self.engine = DynamicALMEngine(_saa_40_40_20_0())

    def test_zero_returns_leaves_mv_unchanged(self):
        p = _at_saa(1_000_000.0)
        result = self.engine._apply_returns(p, ZERO_RETURNS)
        assert result.total_mv() == pytest.approx(1_000_000.0, rel=1e-9)

    def test_positive_return_grows_mv(self):
        p = PortfolioState(holdings={"Govt": 0.0, "Credit": 0.0, "Equity": 0.0, "Cash": 1_000_000.0})
        annual_r = {"Cash": 0.02}
        result = self.engine._apply_returns(p, annual_r)
        expected_monthly = (1.02 ** (1 / 12)) - 1
        assert result.holdings["Cash"] == pytest.approx(1_000_000.0 * (1 + expected_monthly), rel=1e-6)

    def test_monthly_conversion_is_geometric(self):
        """12 months of monthly returns should compound to the annual return."""
        p = PortfolioState(holdings={"Govt": 1_000.0, "Credit": 0.0, "Equity": 0.0, "Cash": 0.0})
        annual_r = {"Govt": 0.12, "Credit": 0.0, "Equity": 0.0, "Cash": 0.0}
        current = p
        for _ in range(12):
            current = self.engine._apply_returns(current, annual_r)
        assert current.holdings["Govt"] == pytest.approx(1_000.0 * 1.12, rel=1e-4)

    def test_all_asset_classes_updated(self):
        p = PortfolioState(holdings={"Govt": 100.0, "Credit": 100.0,
                                     "Equity": 100.0, "Cash": 100.0})
        result = self.engine._apply_returns(p, FLAT_RETURNS)
        for cls in ASSET_CLASSES:
            assert result.holdings[cls] > 100.0


# ---------------------------------------------------------------------------
# 5. _rebalance — core fix: 100%-cash initial portfolio (VR-U02)
# ---------------------------------------------------------------------------

class TestRebalancingToSAA:
    """Critical test class — VR-U02: buy-trigger from 100%-cash portfolio."""

    def setup_method(self):
        self.saa = _saa_40_40_20_0(rebalancing_threshold=0.0)
        self.engine = DynamicALMEngine(self.saa)

    def test_rebalancing_to_saa_buy_orders_generated(self):
        """Starting 100%-cash must generate BUY orders for Govt, Credit, Equity."""
        portfolio = _all_cash(1_000_000.0)
        new_portfolio, trades = self.engine._rebalance(portfolio)

        buy_classes = {t.asset_class for t in trades if t.direction == "BUY"}
        assert "Govt" in buy_classes, "Expected BUY for Govt (was underweight from 100% cash)"
        assert "Credit" in buy_classes, "Expected BUY for Credit (was underweight from 100% cash)"
        assert "Equity" in buy_classes, "Expected BUY for Equity (was underweight from 100% cash)"

    def test_rebalancing_to_saa_sell_cash_generated(self):
        """100%-cash portfolio: Cash acts as settlement account; BUYs deplete it.

        The corrected engine treats Cash as the settlement account, NOT as an
        explicitly tradeable asset.  From a 100%-cash portfolio with 0% Cash
        SAA target, the engine generates only BUY trades (for Govt, Credit,
        Equity); Cash is debited automatically.  There is therefore no explicit
        SELL trade on Cash — instead, the BUY trades consume all available cash.

        This replaces the pre-VR-U02-fix assertion that expected an explicit
        Cash SELL (which was a symptom of treating Cash as a tradeable).
        """
        portfolio = _all_cash(1_000_000.0)
        new_p, trades = self.engine._rebalance(portfolio)
        # Cash is settlement account: no explicit SELL on Cash
        sell_classes = {t.asset_class for t in trades if t.direction == "SELL"}
        assert "Cash" not in sell_classes, "Cash must not be explicitly sold (it is the settlement account)"
        # All cash consumed by BUY trades: Cash balance should be near zero
        assert new_p.holdings.get("Cash", 0.0) == pytest.approx(0.0, abs=1.0)
        # BUY trades for all three non-cash classes must be present
        buy_classes = {t.asset_class for t in trades if t.direction == "BUY"}
        assert buy_classes == {"Govt", "Credit", "Equity"}

    def test_rebalancing_to_saa_correct_buy_amounts(self):
        """Buy amounts approach SAA targets; cash-scaling applies when buy costs > cash.

        With SAA 40/40/20/0 and buy_cost_rate=0.2%, total cash required for
        unscaled buys is 1,002,000 CNY (buy notional + costs) but only 1,000,000
        CNY is available.  Cash-scaling reduces each buy proportionally:
          scale = 1,000,000 / 1,002,000 ≈ 0.998
          Govt  BUY gross ≈ 399,202  (target 400,000; ratio ≈ 99.8%)
          Credit BUY gross ≈ 399,202
          Equity BUY gross ≈ 199,601

        We assert buys are within 1% of SAA target (scale ≈ 0.998 < 1%).
        """
        portfolio = _all_cash(1_000_000.0)
        _, trades = self.engine._rebalance(portfolio)
        buys = {t.asset_class: t.gross_amount for t in trades if t.direction == "BUY"}
        assert buys.get("Govt",   0.0) == pytest.approx(400_000.0, rel=0.01)
        assert buys.get("Credit", 0.0) == pytest.approx(400_000.0, rel=0.01)
        assert buys.get("Equity", 0.0) == pytest.approx(200_000.0, rel=0.01)

    def test_rebalancing_from_100pct_cash_portfolio_holds_correct_weights_after(self):
        """After rebalancing a 100%-cash portfolio, non-cash weights approach SAA."""
        portfolio = _all_cash(1_000_000.0)
        new_portfolio, trades = self.engine._rebalance(portfolio)
        total = new_portfolio.total_mv()
        assert total > 0
        w = new_portfolio.weights()
        # Govt and Credit should be close to 40% each; Equity close to 20%.
        # (Not exact because transaction costs reduce cash used.)
        assert w["Govt"]   > 0.30, f"Govt weight {w['Govt']:.3f} unexpectedly low"
        assert w["Credit"] > 0.30, f"Credit weight {w['Credit']:.3f} unexpectedly low"
        assert w["Equity"] > 0.15, f"Equity weight {w['Equity']:.3f} unexpectedly low"


# ---------------------------------------------------------------------------
# 6. Zero-portfolio guard — must not raise ZeroDivisionError
# ---------------------------------------------------------------------------

class TestZeroPortfolioGuard:
    def setup_method(self):
        self.engine = DynamicALMEngine(_saa_40_40_20_0())

    def test_empty_portfolio_returns_no_trades(self):
        """Completely empty portfolio (all zeros) must not crash or produce trades."""
        empty = PortfolioState(holdings={})
        new_p, trades = self.engine._rebalance(empty)
        assert trades == []

    def test_all_zero_holdings_no_crash(self):
        zero = PortfolioState(holdings={"Govt": 0.0, "Credit": 0.0,
                                        "Equity": 0.0, "Cash": 0.0})
        new_p, trades = self.engine._rebalance(zero)
        assert trades == []
        assert new_p.total_mv() == pytest.approx(0.0)

    def test_saa_deviations_zero_portfolio_all_zeros(self):
        """_saa_deviations on empty portfolio must return zeros, not raise."""
        zero = PortfolioState(holdings={})
        devs = self.engine._saa_deviations(zero)
        assert all(v == pytest.approx(0.0) for v in devs.values())


# ---------------------------------------------------------------------------
# 7. Sell trigger — overweight asset generates SELL
# ---------------------------------------------------------------------------

class TestSellTrigger:
    def setup_method(self):
        self.saa = _saa_40_40_20_0(rebalancing_threshold=0.0)
        self.engine = DynamicALMEngine(self.saa)

    def test_overweight_govt_triggers_sell(self):
        """90% Govt, 10% Cash → Govt overweight → SELL Govt."""
        p = PortfolioState(holdings={"Govt": 900_000.0, "Credit": 0.0,
                                     "Equity": 0.0, "Cash": 100_000.0})
        _, trades = self.engine._rebalance(p)
        sell_govt = [t for t in trades if t.asset_class == "Govt" and t.direction == "SELL"]
        assert len(sell_govt) == 1
        # Govt should sell down to 40% of 1 M = 400 K; overweight = 500 K
        assert sell_govt[0].gross_amount == pytest.approx(500_000.0)

    def test_sell_trade_credits_cash(self):
        """After full rebalancing from 90% Govt, non-cash assets reach SAA targets.

        The SAA has 0% Cash target, so all sell proceeds are reinvested into
        underweight Credit and Equity.  Cash converges toward the 0% SAA target
        (not the pre-rebalance 10%) — this is the correct post-VR-U02-fix behaviour.
        Before the fix, only SELL trades were generated; the missing BUY branch
        meant Cash grew erroneously.  Now buys are also executed.
        """
        p = PortfolioState(holdings={"Govt": 900_000.0, "Credit": 0.0,
                                     "Equity": 0.0, "Cash": 100_000.0})
        new_p, trades = self.engine._rebalance(p)
        # Sell proceeds are fully reinvested — Cash converges toward 0% SAA target.
        assert new_p.holdings["Cash"] >= 0.0                         # non-negative
        assert new_p.holdings["Cash"] < 100_000.0                    # reduced from initial
        # Govt was sold to exactly its SAA target (400,000 CNY).
        # Buy-side cash-scaling reduces total_mv slightly below 1,000,000 due to
        # transaction costs, but the SELL-side Govt target is preserved exactly.
        assert new_p.holdings["Govt"] == pytest.approx(400_000.0, abs=50.0)
        # At least one sell and one buy trade must be present.
        directions = {t.direction for t in trades}
        assert "SELL" in directions
        assert "BUY" in directions


# ---------------------------------------------------------------------------
# 8. Transaction cost logic
# ---------------------------------------------------------------------------

class TestTransactionCosts:
    def setup_method(self):
        self.saa = _saa_40_40_20_0(
            rebalancing_threshold=0.0,
            buy_cost_rate=0.002,
            sell_cost_rate=0.001,
        )
        self.engine = DynamicALMEngine(self.saa)

    def test_buy_cost_equals_rate_times_gross(self):
        portfolio = _all_cash(1_000_000.0)
        _, trades = self.engine._rebalance(portfolio)
        for t in trades:
            if t.direction == "BUY":
                assert t.cost == pytest.approx(0.002 * t.gross_amount, rel=1e-6)

    def test_sell_cost_equals_rate_times_gross(self):
        p = PortfolioState(holdings={"Govt": 900_000.0, "Credit": 0.0,
                                     "Equity": 0.0, "Cash": 100_000.0})
        _, trades = self.engine._rebalance(p)
        for t in trades:
            if t.direction == "SELL":
                assert t.cost == pytest.approx(0.001 * t.gross_amount, rel=1e-6)

    def test_total_cost_reported_in_period_result(self):
        portfolio = _all_cash(1_000_000.0)
        engine = DynamicALMEngine(self.saa)
        result = engine.step(portfolio, ZERO_RETURNS)
        expected_cost = sum(t.cost for t in result.trades)
        assert result.total_transaction_cost == pytest.approx(expected_cost, rel=1e-9)

    def test_zero_cost_rates_no_cost(self):
        saa = _saa_40_40_20_0(buy_cost_rate=0.0, sell_cost_rate=0.0)
        engine = DynamicALMEngine(saa)
        portfolio = _all_cash(1_000_000.0)
        _, trades = engine._rebalance(portfolio)
        assert all(t.cost == pytest.approx(0.0) for t in trades)


# ---------------------------------------------------------------------------
# 9. Portfolio MV conservation net of costs
# ---------------------------------------------------------------------------

class TestPortfolioMVConservation:
    def test_mv_decreases_by_total_cost_exactly(self):
        """After rebalancing, MV_after == MV_before - total_cost (net of tx costs)."""
        saa = _saa_40_40_20_0(rebalancing_threshold=0.0,
                               buy_cost_rate=0.002, sell_cost_rate=0.001)
        engine = DynamicALMEngine(saa)
        portfolio = _all_cash(1_000_000.0)
        new_p, trades = engine._rebalance(portfolio)

        total_cost = sum(t.cost for t in trades)
        # MV before rebalancing = 1,000,000 (zero returns applied)
        # MV after = 1,000,000 - total_cost
        assert new_p.total_mv() == pytest.approx(1_000_000.0 - total_cost, rel=1e-6)

    def test_mv_unchanged_when_already_at_saa(self):
        """Portfolio exactly at SAA with threshold=0 → no trades → MV unchanged."""
        saa = _saa_40_40_20_0(rebalancing_threshold=0.0)
        engine = DynamicALMEngine(saa)
        portfolio = _at_saa(1_000_000.0)
        new_p, trades = engine._rebalance(portfolio)
        assert trades == []
        assert new_p.total_mv() == pytest.approx(1_000_000.0, rel=1e-9)

    def test_cash_floor_non_negative(self):
        """Cash must never go negative after rebalancing."""
        saa = _saa_40_40_20_0(rebalancing_threshold=0.0,
                               buy_cost_rate=0.01, sell_cost_rate=0.01)
        engine = DynamicALMEngine(saa)
        portfolio = _all_cash(1_000_000.0)
        new_p, _ = engine._rebalance(portfolio)
        assert new_p.holdings.get("Cash", 0.0) >= 0.0


# ---------------------------------------------------------------------------
# 10. Rebalancing threshold — small deviations must not trigger trades
# ---------------------------------------------------------------------------

class TestRebalancingThreshold:
    def test_within_threshold_no_trades(self):
        """Deviation of 2% with threshold 5% → no trades."""
        saa = _saa_40_40_20_0(rebalancing_threshold=0.05)
        engine = DynamicALMEngine(saa)
        # Govt slightly overweight: 42% instead of 40% → 2% deviation < 5% threshold
        p = PortfolioState(holdings={"Govt": 420_000.0, "Credit": 400_000.0,
                                     "Equity": 180_000.0, "Cash": 0.0})
        _, trades = engine._rebalance(p)
        assert trades == [], f"Expected no trades within threshold, got {trades}"

    def test_outside_threshold_triggers_trade(self):
        """Deviation of 10% with threshold 5% → trade triggered."""
        saa = _saa_40_40_20_0(rebalancing_threshold=0.05)
        engine = DynamicALMEngine(saa)
        # Govt overweight at 50% instead of 40% → 10% deviation > 5% threshold
        p = PortfolioState(holdings={"Govt": 500_000.0, "Credit": 400_000.0,
                                     "Equity": 100_000.0, "Cash": 0.0})
        _, trades = engine._rebalance(p)
        assert len(trades) > 0, "Expected trade for 10% deviation with 5% threshold"

    def test_threshold_zero_always_rebalances(self):
        """threshold=0 → any deviation above MIN_TRADE_SIZE triggers a trade.

        The portfolio has Govt 10 CNY overweight vs the SAA target.  With
        threshold=0 there is no band suppression, so a SELL order must be
        generated.  (MIN_TRADE_SIZE = 1.0 CNY suppresses sub-CNY noise only;
        a 10-CNY deviation is well above that floor.)
        """
        saa = _saa_40_40_20_0(rebalancing_threshold=0.0)
        engine = DynamicALMEngine(saa)
        # Govt overweight by ~10 CNY above the SAA target for this total MV.
        # total_mv = 1_000_010, target_Govt = 400_004, deviation = ~10 CNY > MIN_TRADE_SIZE
        p = PortfolioState(holdings={"Govt": 400_010.0, "Credit": 400_000.0,
                                     "Equity": 200_000.0, "Cash": 0.0})
        _, trades = engine._rebalance(p)
        sell_govt = [t for t in trades if t.asset_class == "Govt" and t.direction == "SELL"]
        assert len(sell_govt) == 1


# ---------------------------------------------------------------------------
# 11. step() and run() — multi-period correctness
# ---------------------------------------------------------------------------

class TestMultiPeriodRun:
    def setup_method(self):
        self.saa = _saa_balanced(rebalancing_threshold=0.05)
        self.engine = DynamicALMEngine(self.saa)

    def test_run_returns_correct_number_of_results(self):
        results = self.engine.run(_all_cash(1_000_000.0), n_periods=24,
                                  annual_returns=FLAT_RETURNS)
        assert len(results) == 24

    def test_period_indices_sequential(self):
        results = self.engine.run(_all_cash(1_000_000.0), n_periods=12,
                                  annual_returns=FLAT_RETURNS)
        for i, r in enumerate(results, start=1):
            assert r.period == i

    def test_step_portfolio_mv_grows_with_positive_returns(self):
        """With positive returns and no transaction costs, portfolio must grow."""
        saa = _saa_balanced(rebalancing_threshold=1.0,  # very wide → no trades
                            buy_cost_rate=0.0, sell_cost_rate=0.0)
        engine = DynamicALMEngine(saa)
        # Start at SAA so no rebalancing triggered
        p = PortfolioState(holdings={"Govt": 350_000.0, "Credit": 300_000.0,
                                     "Equity": 200_000.0, "Cash": 150_000.0})
        result = engine.step(p, FLAT_RETURNS)
        assert result.net_portfolio_mv() > p.total_mv()

    def test_run_first_period_rebalances_100pct_cash(self):
        """Period 1 from 100%-cash must show rebalancing_triggered == True."""
        saa = _saa_40_40_20_0(rebalancing_threshold=0.0)
        engine = DynamicALMEngine(saa)
        results = engine.run(_all_cash(1_000_000.0), n_periods=6,
                             annual_returns=ZERO_RETURNS)
        assert results[0].rebalancing_triggered is True

    def test_run_subsequent_periods_at_saa_no_rebalancing(self):
        """After period 1 rebalances, periods 2–6 with zero returns stay at SAA."""
        saa = _saa_40_40_20_0(rebalancing_threshold=0.0,
                               buy_cost_rate=0.0, sell_cost_rate=0.0)
        engine = DynamicALMEngine(saa)
        results = engine.run(_all_cash(1_000_000.0), n_periods=6,
                             annual_returns=ZERO_RETURNS)
        # After period 1 rebalances to SAA exactly (zero costs), periods 2–6 → no trades
        for r in results[1:]:
            assert r.rebalancing_triggered is False, (
                f"Unexpected rebalancing in period {r.period}: trades={r.trades}"
            )

    def test_saa_deviation_after_is_smaller_than_before(self):
        """Rebalancing should reduce the maximum absolute SAA deviation."""
        saa = _saa_40_40_20_0(rebalancing_threshold=0.0)
        engine = DynamicALMEngine(saa)
        portfolio = _all_cash(1_000_000.0)
        result = engine.step(portfolio, ZERO_RETURNS)
        max_dev_before = max(abs(v) for v in result.saa_deviation_before.values())
        max_dev_after  = max(abs(v) for v in result.saa_deviation_after.values())
        assert max_dev_after < max_dev_before, (
            f"SAA deviation did not decrease: before={max_dev_before:.4f}, "
            f"after={max_dev_after:.4f}"
        )

    def test_run_output_types_correct(self):
        results = self.engine.run(_all_cash(500_000.0), n_periods=3,
                                  annual_returns=FLAT_RETURNS)
        for r in results:
            assert isinstance(r, ALMPeriodResult)
            assert isinstance(r.trades, list)
            assert isinstance(r.rebalancing_triggered, bool)
            assert r.net_portfolio_mv() >= 0.0

    def test_portfolio_period_advances(self):
        saa = _saa_40_40_20_0()
        engine = DynamicALMEngine(saa)
        results = engine.run(_all_cash(1_000_000.0), n_periods=5,
                             annual_returns=ZERO_RETURNS)
        assert results[-1].portfolio_after_rebalancing.period == 5


# ---------------------------------------------------------------------------
# 12. Edge cases and numerical stability
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_large_portfolio_no_crash(self):
        """1 billion CNY portfolio must complete without overflow."""
        saa = _saa_balanced()
        engine = DynamicALMEngine(saa)
        p = _all_cash(1_000_000_000.0)
        result = engine.step(p, FLAT_RETURNS)
        assert result.net_portfolio_mv() > 0

    def test_single_asset_class_portfolio(self):
        """Portfolio with only one asset class filled should rebalance others."""
        saa = _saa_40_40_20_0(rebalancing_threshold=0.0)
        engine = DynamicALMEngine(saa)
        p = PortfolioState(holdings={"Govt": 1_000_000.0, "Credit": 0.0,
                                     "Equity": 0.0, "Cash": 0.0})
        _, trades = engine._rebalance(p)
        directions = {(t.asset_class, t.direction) for t in trades}
        # Govt should be sold down; Credit and Equity should be bought
        assert ("Govt", "SELL") in directions
        assert ("Credit", "BUY") in directions
        assert ("Equity", "BUY") in directions

    def test_min_trade_size_suppresses_tiny_trades(self):
        """Deviations smaller than MIN_TRADE_SIZE are suppressed."""
        saa = _saa_40_40_20_0(rebalancing_threshold=0.0)
        engine = DynamicALMEngine(saa)
        # Deviation of 0.5 CNY in Govt and Equity (< MIN_TRADE_SIZE=1.0 CNY) -- suppressed
        p = PortfolioState(holdings={"Govt": 400_000.5, "Credit": 400_000.0,
                                     "Equity": 199_999.5, "Cash": 0.0})
        _, trades = engine._rebalance(p)
        govt_sells = [t for t in trades if t.asset_class == "Govt" and t.direction == "SELL"]
        assert govt_sells == [], "Sub-MIN_TRADE_SIZE deviation should be suppressed"

    def test_run_zero_periods_returns_empty_list(self):
        """run() with n_periods=0 must return an empty list immediately."""
        saa = _saa_40_40_20_0()
        engine = DynamicALMEngine(saa)
        results = engine.run(_all_cash(1_000_000.0), n_periods=0,
                             annual_returns=ZERO_RETURNS)
        assert results == []
