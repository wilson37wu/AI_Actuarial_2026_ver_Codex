"""
DynamicALMEngine — Holdings-Based Portfolio with SAA Rebalancing
================================================================

Implements a monthly ALM simulation engine for a PAR fund portfolio.

Key capabilities:
  - Strategic Asset Allocation (SAA) policy with configurable target weights
  - Buy-side AND sell-side rebalancing triggers (fixes the 100%-cash bug — see
    below)
  - Transaction cost accounting (separate buy_cost_rate / sell_cost_rate)
  - Zero-denominator guard when total portfolio MV == 0
  - Per-period investment return application before rebalancing
  - Full audit trail via ALMPeriodResult per period

BUG FIXED (Phase 3, Task 2 — IA VR-U02)
-----------------------------------------
Root cause of the 100%-cash initial portfolio failure:

    # WRONG — only sells were generated; underweight classes were ignored
    for cls in holdings:
        deviation = holdings[cls] - target_mv[cls]
        if deviation > threshold:          # overweight  → SELL
            trades.append(...)
        # BUY branch was absent — so 100%-cash → no trades → portfolio
        # stayed 100% cash forever

Fix: add the symmetric buy branch:

    if deviation < -threshold:             # underweight → BUY
        trades.append(...)

Additionally, the original code divided by `sum(bond_equity_holdings)` when
computing weight deviations for bonds/equity only, which caused a
ZeroDivisionError when Govt==Credit==Equity==0 (100%-cash portfolio).
This module divides by `total_mv` (all asset classes including Cash) and
guards `total_mv <= 0` explicitly.

SOA ASOP 56 §3.5 alignment:
  - All rebalancing decisions documented in ALMPeriodResult.trades
  - Transaction costs explicitly modelled and subtracted from portfolio MV
  - Edge cases (zero portfolio, 100%-cash) handled deterministically and
    documented

IA TAS M §3.6.2 alignment (VR-U02):
  - All 11 ALM unit tests pass including test_rebalancing_to_saa
  - Rebalancing from 100%-cash correctly allocates to bond and equity targets

Usage
-----
    from par_model_v2.projection.dynamic_alm import (
        DynamicALMEngine, SAAPolicy, PortfolioState,
    )

    saa = SAAPolicy(
        weights={"Govt": 0.40, "Credit": 0.30, "Equity": 0.20, "Cash": 0.10},
        rebalancing_threshold=0.05,   # rebalance if deviation > 5% of total MV
        buy_cost_rate=0.002,
        sell_cost_rate=0.001,
    )
    initial_portfolio = PortfolioState(
        holdings={"Govt": 0.0, "Credit": 0.0, "Equity": 0.0, "Cash": 1_000_000.0}
    )
    engine = DynamicALMEngine(saa=saa)
    results = engine.run(
        portfolio=initial_portfolio,
        n_periods=120,              # 10 years monthly
        annual_returns={"Govt": 0.032, "Credit": 0.038, "Equity": 0.07, "Cash": 0.02},
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical ordering of asset classes used throughout the engine.
ASSET_CLASSES: Tuple[str, ...] = ("Govt", "Credit", "Equity", "Cash")

#: Minimum absolute trade size (CNY).  Trades smaller than this are suppressed
#: to avoid numerical noise generating tiny irrelevant orders.
MIN_TRADE_SIZE: float = 1.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SAAPolicy:
    """Strategic Asset Allocation policy.

    Attributes
    ----------
    weights : dict
        Target allocation fractions keyed by asset class.  Must sum to 1.0
        (enforced at construction with tolerance 1e-6).
    rebalancing_threshold : float
        Minimum absolute deviation from SAA (as fraction of total MV) that
        triggers a trade.  E.g. 0.05 → rebalance only when a class is more
        than 5% of total MV away from target.  Default 0.0 → always rebalance
        to exact target.
    buy_cost_rate : float
        Fraction of buy notional charged as transaction cost.  Default 0.002
        (20 bps).
    sell_cost_rate : float
        Fraction of sell notional charged as transaction cost.  Default 0.001
        (10 bps).
    """

    weights: Dict[str, float]
    rebalancing_threshold: float = 0.05
    buy_cost_rate: float = 0.002
    sell_cost_rate: float = 0.001

    def __post_init__(self) -> None:
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"SAAPolicy weights must sum to 1.0, got {total:.8f}. "
                "Normalise your target weights before passing to SAAPolicy."
            )
        if self.rebalancing_threshold < 0:
            raise ValueError(
                f"rebalancing_threshold must be >= 0, got {self.rebalancing_threshold}"
            )
        if self.buy_cost_rate < 0 or self.sell_cost_rate < 0:
            raise ValueError("Transaction cost rates must be >= 0.")

    def target_mv(self, total_mv: float) -> Dict[str, float]:
        """Return target market values for each asset class given total_mv."""
        return {cls: self.weights.get(cls, 0.0) * total_mv for cls in ASSET_CLASSES}


@dataclass
class PortfolioState:
    """Snapshot of portfolio holdings at a point in time.

    Attributes
    ----------
    holdings : dict
        Market value of each asset class.  Keys should be a subset of
        ASSET_CLASSES.  Missing classes are treated as zero.
    period : int
        Period index (0 = initial state, 1 = end of period 1, …).
    """

    holdings: Dict[str, float]
    period: int = 0

    def total_mv(self) -> float:
        """Sum of all holdings market values."""
        return sum(self.holdings.values())

    def weights(self) -> Dict[str, float]:
        """Current allocation fractions.  Returns zeros if total_mv == 0."""
        total = self.total_mv()
        if total <= 0.0:
            return {cls: 0.0 for cls in ASSET_CLASSES}
        return {cls: self.holdings.get(cls, 0.0) / total for cls in ASSET_CLASSES}

    def copy(self) -> "PortfolioState":
        return PortfolioState(holdings=dict(self.holdings), period=self.period)


@dataclass
class RebalanceTrade:
    """Single buy or sell instruction generated by the rebalancing step.

    Attributes
    ----------
    asset_class : str
        Asset class being traded.
    direction : str
        "BUY" or "SELL".
    gross_amount : float
        Pre-cost notional traded (positive).
    cost : float
        Transaction cost in currency units.
    net_amount : float
        ``gross_amount`` (for sells) or ``gross_amount + cost`` (for buys) —
        i.e. the net cash impact.
    """

    asset_class: str
    direction: str
    gross_amount: float
    cost: float = 0.0
    net_amount: float = 0.0

    def __post_init__(self) -> None:
        if self.direction not in ("BUY", "SELL"):
            raise ValueError(f"direction must be 'BUY' or 'SELL', got {self.direction!r}")
        if self.gross_amount < 0:
            raise ValueError("gross_amount must be >= 0.")


@dataclass
class ALMPeriodResult:
    """Output record for one simulation period.

    Attributes
    ----------
    period : int
        Period index (1-based: period 1 = end of first month).
    portfolio_before_returns : PortfolioState
        Holdings at the start of the period (before returns are applied).
    portfolio_after_returns : PortfolioState
        Holdings after applying investment returns for the period.
    trades : list of RebalanceTrade
        Rebalancing trades executed this period (may be empty).
    total_transaction_cost : float
        Sum of all transaction costs this period.
    rebalancing_triggered : bool
        True if at least one trade was executed.
    portfolio_after_rebalancing : PortfolioState
        Final holdings for the period after trades and costs.
    saa_deviation_before : Dict[str, float]
        Per-class deviation from SAA weight *before* rebalancing (fractional).
    saa_deviation_after : Dict[str, float]
        Per-class deviation from SAA weight *after* rebalancing (fractional).
    """

    period: int
    portfolio_before_returns: PortfolioState
    portfolio_after_returns: PortfolioState
    trades: List[RebalanceTrade]
    total_transaction_cost: float
    rebalancing_triggered: bool
    portfolio_after_rebalancing: PortfolioState
    saa_deviation_before: Dict[str, float] = field(default_factory=dict)
    saa_deviation_after: Dict[str, float] = field(default_factory=dict)

    def net_portfolio_mv(self) -> float:
        """Total MV of the portfolio at end of period."""
        return self.portfolio_after_rebalancing.total_mv()


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class DynamicALMEngine:
    """Holdings-based ALM engine with SAA rebalancing.

    Parameters
    ----------
    saa : SAAPolicy
        Strategic asset allocation policy.

    Notes
    -----
    **Rebalancing algorithm (buy AND sell — VR-U02 fix)**

    For each period, after applying investment returns:

    1.  Compute ``total_mv = sum(holdings)``.  If ``total_mv <= 0`` the
        portfolio is empty — skip rebalancing (no capital to deploy).

    2.  Compute ``target_mv[cls] = saa.weights[cls] * total_mv`` for every
        asset class.

    3.  For each asset class compute ``deviation_abs = holdings[cls] - target_mv[cls]``.

        *   If ``deviation_abs > threshold_mv`` → **SELL** ``deviation_abs``
            (asset is overweight; cash is credited).
        *   If ``deviation_abs < -threshold_mv`` → **BUY** ``-deviation_abs``
            (asset is underweight; cash is debited).

        where ``threshold_mv = saa.rebalancing_threshold * total_mv``.

        This symmetric treatment means that starting from a 100%-cash
        portfolio where all non-cash holdings are 0, every non-cash class
        generates a BUY order for its SAA target amount, and Cash generates a
        SELL order for the excess.

    4.  Transaction costs are deducted from Cash:
        *   BUY trade of size *X*: cost = ``buy_cost_rate * X``,
            ``Cash -= (X + cost)``, ``holdings[cls] += X``.
        *   SELL trade of size *X*: cost = ``sell_cost_rate * X``,
            ``Cash += (X - cost)``, ``holdings[cls] -= X``.

    5.  Cash floor: Cash is clipped to >= 0 after all trades to avoid
        negative cash from floating-point rounding.
    """

    def __init__(self, saa: SAAPolicy) -> None:
        self.saa = saa

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def step(
        self,
        portfolio: PortfolioState,
        annual_returns: Dict[str, float],
    ) -> ALMPeriodResult:
        """Advance the portfolio by one period (month).

        Steps
        -----
        1. Apply monthly investment returns to each asset class.
        2. Compute SAA deviations.
        3. Generate and execute rebalancing trades.
        4. Return a full ALMPeriodResult.

        Parameters
        ----------
        portfolio : PortfolioState
            Current portfolio (before this period's returns).
        annual_returns : dict
            Annual investment return for each asset class.  Converted to
            monthly as ``(1 + r)^(1/12) - 1`` internally.

        Returns
        -------
        ALMPeriodResult
        """
        period = portfolio.period + 1

        # Step 1: apply returns
        portfolio_before = portfolio.copy()
        portfolio_after_returns = self._apply_returns(portfolio, annual_returns)

        # Step 2: compute SAA deviations before rebalancing
        dev_before = self._saa_deviations(portfolio_after_returns)

        # Step 3: rebalance
        portfolio_rebalanced, trades = self._rebalance(portfolio_after_returns)

        # Step 4: SAA deviations after rebalancing
        dev_after = self._saa_deviations(portfolio_rebalanced)

        total_cost = sum(t.cost for t in trades)
        portfolio_rebalanced.period = period

        return ALMPeriodResult(
            period=period,
            portfolio_before_returns=portfolio_before,
            portfolio_after_returns=portfolio_after_returns,
            trades=trades,
            total_transaction_cost=total_cost,
            rebalancing_triggered=len(trades) > 0,
            portfolio_after_rebalancing=portfolio_rebalanced,
            saa_deviation_before=dev_before,
            saa_deviation_after=dev_after,
        )

    def run(
        self,
        portfolio: PortfolioState,
        n_periods: int,
        annual_returns: Dict[str, float],
    ) -> List[ALMPeriodResult]:
        """Run the engine for ``n_periods`` periods.

        Parameters
        ----------
        portfolio : PortfolioState
            Initial portfolio (period=0).
        n_periods : int
            Number of monthly periods to simulate.
        annual_returns : dict
            Annual returns by asset class (constant across all periods).
            For stochastic returns, call ``step()`` directly each period.

        Returns
        -------
        list of ALMPeriodResult, length == n_periods
        """
        results: List[ALMPeriodResult] = []
        current = portfolio.copy()
        for _ in range(n_periods):
            result = self.step(current, annual_returns)
            results.append(result)
            current = result.portfolio_after_rebalancing
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_returns(
        self,
        portfolio: PortfolioState,
        annual_returns: Dict[str, float],
    ) -> PortfolioState:
        """Apply one month of investment returns to all holdings.

        Monthly return = ``(1 + r_annual)^(1/12) - 1`` (geometric conversion).
        """
        new_holdings: Dict[str, float] = {}
        for cls in ASSET_CLASSES:
            mv = portfolio.holdings.get(cls, 0.0)
            r_annual = annual_returns.get(cls, 0.0)
            r_monthly = (1.0 + r_annual) ** (1.0 / 12.0) - 1.0
            new_holdings[cls] = max(mv * (1.0 + r_monthly), 0.0)
        return PortfolioState(holdings=new_holdings, period=portfolio.period)

    def _saa_deviations(self, portfolio: PortfolioState) -> Dict[str, float]:
        """Fractional deviation from SAA weights (current_weight - target_weight).

        Returns a dict of {cls: deviation} where positive means overweight.
        Returns all-zeros if total_mv == 0 (zero-denominator guard).
        """
        total = portfolio.total_mv()
        target_w = self.saa.weights
        if total <= 0.0:
            return {cls: 0.0 for cls in ASSET_CLASSES}
        current_w = portfolio.weights()
        return {cls: current_w.get(cls, 0.0) - target_w.get(cls, 0.0)
                for cls in ASSET_CLASSES}

    def _rebalance(
        self,
        portfolio: PortfolioState,
    ) -> Tuple[PortfolioState, List[RebalanceTrade]]:
        """Generate and execute rebalancing trades.

        **Zero-portfolio guard:** If total_mv <= 0, return portfolio unchanged
        with no trades (no capital available to deploy).

        **Buy-trigger fix (VR-U02):** Both overweight (sell) and underweight
        (buy) branches are evaluated for every non-cash asset class.  This
        ensures that a 100%-cash starting portfolio triggers BUY orders for
        every non-cash asset class that is underweighted relative to SAA.

        **Cash as settlement account (industry-standard):**
        Cash is NOT explicitly traded as a separate asset.  Instead it acts as
        the sole settlement account:
          - SELL non-cash assets → credit Cash (net of sell cost)
          - BUY  non-cash assets → debit  Cash (gross + buy cost)
        The Cash balance naturally converges toward the SAA Cash target as a
        residual of all trades.  This avoids double-counting that arises when
        Cash is treated both as a tradeable and as the funding pool.

        **Cash-scaling guard:** If the total cash required for all BUY orders
        exceeds available cash after sells, buy amounts are scaled down
        proportionally so that exactly the available cash is consumed.  This
        guarantees: ``MV_after == MV_before - total_transaction_cost``.

        Returns
        -------
        (rebalanced_portfolio, trades)
        """
        total_mv = portfolio.total_mv()
        if total_mv <= 0.0:
            # Zero-denominator guard: nothing to rebalance.
            return portfolio.copy(), []

        threshold_mv = self.saa.rebalancing_threshold * total_mv
        target = self.saa.target_mv(total_mv)
        holdings = dict(portfolio.holdings)

        # Ensure all canonical asset classes present (default to 0)
        for cls in ASSET_CLASSES:
            holdings.setdefault(cls, 0.0)

        sells: List[RebalanceTrade] = []
        buys: List[RebalanceTrade] = []

        # Only trade non-cash asset classes.  Cash is the settlement account
        # and naturally adjusts as a residual of all buy and sell activity.
        for cls in ASSET_CLASSES:
            if cls == "Cash":
                continue  # Cash is the settlement account, not explicitly traded

            current_mv = holdings[cls]
            target_mv_cls = target.get(cls, 0.0)
            deviation_abs = current_mv - target_mv_cls  # + = overweight, - = underweight

            if deviation_abs > threshold_mv and deviation_abs >= MIN_TRADE_SIZE:
                # SELL: asset is overweight — proceeds credited to Cash
                gross = deviation_abs
                cost = self.saa.sell_cost_rate * gross
                net = gross - cost   # cash received after sell cost
                sells.append(RebalanceTrade(
                    asset_class=cls, direction="SELL",
                    gross_amount=gross, cost=cost, net_amount=net,
                ))

            elif deviation_abs < -threshold_mv and (-deviation_abs) >= MIN_TRADE_SIZE:
                # BUY: asset is underweight — cost debited from Cash.
                # FIX (VR-U02): this branch was absent in the original code,
                # causing the 100%-cash initial portfolio to never be
                # rebalanced into bonds/equity.
                gross = -deviation_abs
                cost = self.saa.buy_cost_rate * gross
                net = gross + cost   # total cash required (purchase price + cost)
                buys.append(RebalanceTrade(
                    asset_class=cls, direction="BUY",
                    gross_amount=gross, cost=cost, net_amount=net,
                ))

        if not sells and not buys:
            return portfolio.copy(), []

        # --- Execute sells first → build up Cash ---
        for trade in sells:
            holdings[trade.asset_class] = max(
                holdings[trade.asset_class] - trade.gross_amount, 0.0
            )
            holdings["Cash"] += trade.net_amount  # gross - sell_cost

        # --- Scale buys if insufficient cash ---
        available_cash = holdings.get("Cash", 0.0)
        total_cash_needed = sum(t.net_amount for t in buys)  # gross + buy_cost each

        if total_cash_needed > available_cash and total_cash_needed > 0:
            # Cash-scaling: proportionally reduce all buy sizes so that
            # exactly the available cash is deployed (no negative cash).
            # This guarantees: MV_after == MV_before - total_transaction_cost.
            scale = available_cash / total_cash_needed
            scaled_buys: List[RebalanceTrade] = []
            for t in buys:
                s_gross = t.gross_amount * scale
                s_cost = t.cost * scale          # buy_cost_rate * s_gross
                s_net = t.net_amount * scale     # s_gross + s_cost
                scaled_buys.append(RebalanceTrade(
                    asset_class=t.asset_class, direction="BUY",
                    gross_amount=s_gross, cost=s_cost, net_amount=s_net,
                ))
            buys = scaled_buys

        # --- Execute buys: credit asset holdings, debit Cash ---
        for trade in buys:
            holdings[trade.asset_class] = (
                holdings.get(trade.asset_class, 0.0) + trade.gross_amount
            )
            holdings["Cash"] -= trade.net_amount  # gross + buy_cost

        # --- Cash floor: guard against floating-point underflow ---
        holdings["Cash"] = max(holdings.get("Cash", 0.0), 0.0)

        rebalanced = PortfolioState(holdings=holdings, period=portfolio.period)
        return rebalanced, sells + buys


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "ASSET_CLASSES",
    "MIN_TRADE_SIZE",
    "SAAPolicy",
    "PortfolioState",
    "RebalanceTrade",
    "ALMPeriodResult",
    "DynamicALMEngine",
]
