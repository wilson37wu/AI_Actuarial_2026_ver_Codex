"""
Stochastic Liquidity-Premium / Funding-Spread Driver (CIR++ square-root)
========================================================================

Phase 21 Task 3.  Adds the **seventh** economic risk driver — a stochastic
liquidity premium / funding spread ``l(t)`` — to the economic scenario
generator, P- and Q-measure consistent, so the multi-driver economic-capital
proxy can span ``(r, S, s, b, m, fx, l)``: short rate, equity, credit spread,
lapse behaviour, mortality trend, FX, and now liquidity.

This closes the last documented driver omission in MR-012 ("the proxy still
omits ... liquidity").  It follows the same expansion practice as the credit
driver (IFoA proxy-model working party; Milliman / MDPI LSMC literature) and
the regulatory treatment of an illiquidity-premium component in discounting
(EIOPA volatility-adjustment decomposition; matching-adjustment literature):
the liquidity premium is the NON-credit component of asset spreads earned for
holding illiquid assets, and a widening of the funding/liquidity spread is the
insurer's loss when assets must be sold or funding rolled in a stressed market.

Process
-------
Identical CIR++ family to the credit-spread driver (deliberate: one tested
discretisation, one calibrator methodology):

    l(t) = x(t) + phi,        x(t) >= 0
    dx(t) = kappa_l * (b^M - x(t)) dt + sigma_l * sqrt(x(t)) dW_l(t)

with a measure-dependent long-run level ``b^M``:

* P-measure (real-world, ALM / VaR): ``b^P = long_run_premium_p - phi``.
* Q-measure (market-consistent valuation): the market price of liquidity risk
  ``lambda_l`` re-anchors the long-run level,
  ``b^Q = b^P + lambda_l * sigma_l^2 / kappa_l`` — positive ``lambda_l`` means
  risk-neutral liquidity premia exceed real-world on average (a widening is
  the insurer's loss, exactly mirroring the credit risk premium sign).

Monthly discretisation (``dt = 1/12``) uses the same **full-truncation Euler**
scheme (Lord-Koekkoek-van Dijk 2010) as :class:`CreditSpreadProcess`; the
realised premium is clamped to ``[premium_floor, premium_ceiling]``.

Liquidity-cost interpretation
-----------------------------
The premium is interpreted as a forced-sale / funding-roll cost intensity: the
PV haircut on a unit of illiquid backing assets liquidated (or funded) over
``[H, T]`` is ``1 - exp(-integral_H^T l(u) du)`` — the exponential-affine
discount at the extra liquidity spread (Duffie-Singleton form), used by the
capital module to turn a horizon liquidity state into a liability-side impact.

Standards
---------
- SOA ASOP 56 3.1.3 — stochastic process documentation
- SOA ASOP 56 3.4   — parameter calibration methodology
- SOA ASOP 25 3.3   — scenario generation adequacy (correlated drivers)
- IA TAS M 3.4      — measure identification (P vs Q)
- IA TAS M 3.6      — model validation, convergence, reproducibility
- CIR (1985); Brigo-Mercurio CIR++ (2006); Lord et al. (2010) full truncation;
  EIOPA volatility-adjustment methodology (illiquidity-premium component).

Model-use restrictions
----------------------
EDUCATIONAL ONLY.  The premium is a single systemic liquidity factor with no
asset-class segmentation, no bid-ask microstructure, and no funding-ladder
granularity.  Not a regulatory liquidity-risk model.  Independent APS X2
review pending.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from par_model_v2.stochastic.esg_process import (
    Measure,
    _antithetic_normals,
    _assert_output_measure,
    _enforce_simulation_measure,
    _month_grid,
    _validate_simulation_dimensions,
)

DEFAULT_PREMIUM_FLOOR = 0.0
DEFAULT_PREMIUM_CEILING = 0.10


@dataclass
class LiquidityPremiumParams:
    """Parameters for the CIR++ mean-reverting liquidity-premium process.

    ``l(t) = x(t) + shift`` with ``dx = kappa (b - x) dt + sigma_l sqrt(x) dW``.

    Defaults are PLACEHOLDERS — the Phase 21 Task 3 calibration replaces them
    with values estimated from educational-proxy funding-spread history.
    SOA ASOP 56 3.1.3/3.4.

    Parameters
    ----------
    mean_reversion_speed : float
        ``kappa_l`` — speed of mean reversion of the square-root factor (>0).
    premium_vol : float
        ``sigma_l`` — diffusion coefficient of the square-root factor (>0).
    initial_premium : float
        ``l(0)`` — starting liquidity premium (>= shift, absolute terms,
        e.g. 0.005 = 50 bp).
    long_run_premium_p : float
        Real-world (P) long-run mean of ``l`` (absolute, e.g. 0.006).
    market_price_of_liquidity_risk : float
        ``lambda_l`` — re-anchors the Q long-run level upward (liquidity risk
        premium). Positive => Q premia exceed P premia on average.
    shift : float
        CIR++ deterministic shift ``phi`` keeping the diffusion non-negative
        while matching ``initial_premium``.
    premium_floor, premium_ceiling : float
        Numerical clamp on the realised premium (absolute).
    """

    mean_reversion_speed: float = 0.60
    premium_vol: float = 0.025
    initial_premium: float = 0.005
    long_run_premium_p: float = 0.006
    market_price_of_liquidity_risk: float = 0.10
    shift: float = 0.001
    premium_floor: float = DEFAULT_PREMIUM_FLOOR
    premium_ceiling: float = DEFAULT_PREMIUM_CEILING

    def __post_init__(self):
        if self.mean_reversion_speed <= 0:
            raise ValueError(
                "mean_reversion_speed must be positive; got {}".format(self.mean_reversion_speed)
            )
        if self.premium_vol <= 0:
            raise ValueError("premium_vol must be positive; got {}".format(self.premium_vol))
        if self.initial_premium < self.shift:
            raise ValueError(
                "initial_premium ({}) must be >= shift ({}) so the square-root "
                "factor x(0) is non-negative".format(self.initial_premium, self.shift)
            )
        if float(self.premium_floor) >= float(self.premium_ceiling):
            raise ValueError("premium_floor must be below premium_ceiling")

    @property
    def initial_x(self) -> float:
        """Initial square-root-factor level ``x(0) = l(0) - shift``."""
        return float(self.initial_premium) - float(self.shift)

    @property
    def long_run_x_p(self) -> float:
        """P-measure long-run mean of the square-root factor."""
        return float(self.long_run_premium_p) - float(self.shift)

    @property
    def is_placeholder(self) -> bool:
        return True


class LiquidityPremiumProcess:
    """CIR++ liquidity-premium process with measure-consistent drift.

    Mirrors :class:`CreditSpreadProcess`: ``_simulate_array`` returns an
    ``(n, T_months + 1)`` ndarray of premia; ``simulate`` returns an
    ESGAdapter-style DataFrame.  ``Measure.P`` for ALM / VaR, ``Measure.Q``
    for valuation.

    SOA ASOP 56 3.1.3/3.4; IA TAS M 3.4/3.6.
    """

    #: Measures this process is permitted to simulate under (G-05 / MR-004).
    SUPPORTED_MEASURES = (Measure.P, Measure.Q)

    def __init__(self, params: Optional[LiquidityPremiumParams] = None) -> None:
        self.params = params if params is not None else LiquidityPremiumParams()

    # -- drift target (square-root factor) ---------------------------------
    def _long_run_x(self, measure: Measure) -> float:
        """Measure-dependent long-run mean ``b`` of the square-root factor.

        Q re-anchors the level by the CIR risk premium
        ``lambda_l * sigma^2 / kappa``; a positive market price of liquidity
        risk raises Q premia (a widening is the insurer's loss).
        """
        p = self.params
        b_p = p.long_run_x_p
        if measure == Measure.Q:
            premium = (p.market_price_of_liquidity_risk * p.premium_vol ** 2) / p.mean_reversion_speed
            return b_p + premium
        return b_p

    def _simulate_array(
        self,
        n_scenarios: int,
        T_months: int,
        measure: Measure,
        shocks: np.ndarray,
    ) -> np.ndarray:
        """Simulate premium paths into an ndarray of shape (n, T_months + 1).

        Full-truncation Euler (Lord et al. 2010) on the square-root factor,
        then ``l = clamp(x + shift)``.
        """
        expected_shape = (n_scenarios, T_months)
        if shocks.shape != expected_shape:
            raise ValueError(
                "liquidity shocks must have shape {}; got {}".format(expected_shape, shocks.shape)
            )
        p = self.params
        dt = 1.0 / 12.0
        sqrt_dt = np.sqrt(dt)
        kappa = p.mean_reversion_speed
        sigma = p.premium_vol
        b = self._long_run_x(measure)

        x = np.empty((n_scenarios, T_months + 1), dtype=float)
        x[:, 0] = p.initial_x
        for month in range(T_months):
            x_prev = x[:, month]
            x_pos = np.maximum(x_prev, 0.0)
            x_next = (
                x_prev
                + kappa * (b - x_prev) * dt
                + sigma * np.sqrt(x_pos) * sqrt_dt * shocks[:, month]
            )
            x[:, month + 1] = np.maximum(x_next, 0.0)   # full truncation

        premia = x + p.shift
        return np.clip(premia, float(p.premium_floor), float(p.premium_ceiling))

    def simulate(
        self,
        n_scenarios: int,
        T_months: int,
        measure: Measure,
        seed: int = 42,
    ) -> pd.DataFrame:
        """Simulate monthly liquidity-premium paths as an ESGAdapter-style frame.

        Columns: scenario_id, month, liquidity_premium, measure.
        Shape: ``n_scenarios * (T_months + 1)`` rows.

        SOA ASOP 56 3.1.3/3.4; IA TAS M 3.4.
        """
        measure = _enforce_simulation_measure(self, measure)
        _validate_simulation_dimensions(n_scenarios, T_months)
        n_scenarios = int(n_scenarios)
        T_months = int(T_months)

        rng = np.random.default_rng(seed)
        shocks = _antithetic_normals(rng, n_scenarios, T_months)
        premia = self._simulate_array(n_scenarios, T_months, measure, shocks)

        scenario_ids, months = _month_grid(n_scenarios, T_months)
        frame = pd.DataFrame({
            "scenario_id": scenario_ids,
            "month": months,
            "liquidity_premium": premia.reshape(-1),
            "measure": measure.value,
        })
        return _assert_output_measure(frame, measure, type(self).__name__)


def _inner_q_liquidity_process(
    premium_state: float, base_params: LiquidityPremiumParams
) -> LiquidityPremiumProcess:
    """Build a Q-measure CIR++ liquidity process conditioned on outer ``l_H``.

    The inner valuation starts at the conditioning premium level ``l_H`` (via
    the CIR++ shift so ``x(0) = l_H - shift >= 0``); speed, vol, shift and the
    liquidity risk premium are inherited from the outer parameters.  Only the
    *level* is re-anchored, exactly mirroring ``_inner_q_spread_process``.
    """
    l_h = float(premium_state)
    shift = min(float(base_params.shift), max(l_h, 0.0))
    inner = LiquidityPremiumParams(
        mean_reversion_speed=base_params.mean_reversion_speed,
        premium_vol=base_params.premium_vol,
        initial_premium=max(l_h, float(base_params.premium_floor)),
        long_run_premium_p=base_params.long_run_premium_p,
        market_price_of_liquidity_risk=base_params.market_price_of_liquidity_risk,
        shift=shift,
        premium_floor=base_params.premium_floor,
        premium_ceiling=base_params.premium_ceiling,
    )
    return LiquidityPremiumProcess(inner)


def forced_sale_haircut_fraction(premium_paths: np.ndarray) -> np.ndarray:
    """Forced-sale / funding-roll PV haircut over a horizon path.

    Given monthly liquidity-premium paths ``l`` of shape ``(n, k+1)``, returns
    the per-path PV haircut ``1 - exp(-integral l du)`` with the integral
    approximated by the monthly left-Riemann sum (mirrors
    ``expected_credit_loss_fraction``; Duffie-Singleton exponential-affine
    form).  Returns an array of shape ``(n,)`` in ``[0, 1)``.
    """
    arr = np.asarray(premium_paths, dtype=float)
    if arr.ndim != 2:
        raise ValueError("premium_paths must be 2-D (n, k+1)")
    dt = 1.0 / 12.0
    integral = arr[:, : arr.shape[1] - 1].sum(axis=1) * dt
    return 1.0 - np.exp(-integral)


__all__ = [
    "DEFAULT_PREMIUM_FLOOR",
    "DEFAULT_PREMIUM_CEILING",
    "LiquidityPremiumParams",
    "LiquidityPremiumProcess",
    "_inner_q_liquidity_process",
    "forced_sale_haircut_fraction",
]
