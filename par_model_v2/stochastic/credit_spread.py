"""
Stochastic Credit-Spread Driver (CIR++ / mean-reverting square-root)
====================================================================

Phase 17 Task 1.  Adds a **third** economic risk driver — a stochastic credit
spread ``s(t)`` — to the economic scenario generator, P- and Q-measure
consistent, so the multi-driver economic-capital proxy can span
``(short rate r, equity level S, credit spread s)`` instead of just ``(r, S)``.

This directly extends the documented Phase 15 limitation ("lapse, **credit-
spread**, mortality-trend and FX risks are still NOT in the tail") and follows
current proxy-modelling practice (IFoA proxy-model working party;
Milliman / MDPI LSMC literature) of expanding the proxy basis to financial AND
non-financial drivers.

Process
-------
The spread follows a **mean-reverting square-root (CIR) process with a
deterministic CIR++ shift** ``phi`` so the model can be anchored to an
arbitrary positive initial spread while keeping the diffusion non-negative:

    s(t) = x(t) + phi,        x(t) >= 0
    dx(t) = kappa * (b^M - x(t)) dt + sigma_s * sqrt(x(t)) dW_s(t)

with a measure-dependent long-run level ``b^M``:

* P-measure (real-world, for ALM / VaR): ``b^P = long_run_spread - phi``.
* Q-measure (risk-neutral, for valuation): the market price of credit risk
  ``lambda_s`` lowers the risk-neutral mean-reversion target,
  ``b^Q = b^P - lambda_s * sigma_s^2 / kappa`` (the standard CIR risk-premium
  re-anchoring of the long-run level; an *increase* in spread is the insurer's
  loss, so a positive ``lambda_s`` raises Q spreads relative to P).

Monthly discretisation (``dt = 1/12``) uses a **full-truncation Euler** scheme
(Lord-Koekkoek-van Dijk 2010): the square-root argument is floored at zero each
step, which keeps the scheme well-defined even when the Feller condition
``2 kappa b >= sigma_s^2`` does not hold (as is common for placeholder
educational parameters).  The realised spread is additionally clamped to
``[spread_floor, spread_ceiling]`` for numerical safety, mirroring
``HullWhiteRateProcess._apply_rate_bounds``.

Reduced-form credit interpretation
----------------------------------
The spread is interpreted as a reduced-form *hazard × loss-given-default*
proxy ``s ≈ h * LGD`` (Duffie-Singleton).  The expected credit-loss PV on a
unit of spread-sensitive backing assets held from the capital horizon ``H`` to
maturity ``T`` is then ``1 - exp(-∫_H^T s(u) du)`` — used by the three-driver
capital module to turn a horizon spread state into a liability impact.

Standards
---------
- SOA ASOP 56 §3.1.3 — stochastic process documentation
- SOA ASOP 56 §3.4   — parameter calibration methodology (placeholders here)
- SOA ASOP 25 §3.3   — scenario generation adequacy (correlated drivers)
- IA TAS M §3.4      — measure identification (P vs Q)
- IA TAS M §3.6      — model validation, convergence, reproducibility
- Cox-Ingersoll-Ross (1985); Brigo-Mercurio CIR++ (2006);
  Lord-Koekkoek-van Dijk (2010) full-truncation; Duffie-Singleton (1999).

Model-use restrictions
----------------------
EDUCATIONAL ONLY.  All parameters are illustrative placeholders; spreads are a
single-name-agnostic systemic proxy with no rating migration, no sector
structure, and no default jump.  Not a regulatory credit-risk model.
Independent APS X2 review pending.
"""

from __future__ import annotations

import enum
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


#: Default total polynomial degree-context constant (kept here for callers).
DEFAULT_SPREAD_FLOOR = 0.0
DEFAULT_SPREAD_CEILING = 0.20


@dataclass
class CreditSpreadParams:
    """Parameters for the CIR++ mean-reverting credit-spread process.

    ``s(t) = x(t) + shift`` with ``dx = kappa (b - x) dt + sigma_s sqrt(x) dW``.

    All values are PLACEHOLDERS — calibrate to an approved bond/CDS index in a
    later cycle.  SOA ASOP 56 §3.1.3/§3.4.

    Parameters
    ----------
    mean_reversion_speed : float
        ``kappa`` — speed of mean reversion of the square-root factor (>0).
    spread_vol : float
        ``sigma_s`` — diffusion coefficient of the square-root factor (>0).
    initial_spread : float
        ``s(0)`` — starting credit spread (>= shift, in absolute terms,
        e.g. 0.012 = 120 bp).
    long_run_spread_p : float
        Real-world (P) long-run mean of ``s`` (absolute, e.g. 0.015).
    market_price_of_credit_risk : float
        ``lambda_s`` — re-anchors the Q long-run level upward (credit risk
        premium). Positive => Q spreads exceed P spreads on average.
    shift : float
        CIR++ deterministic shift ``phi`` keeping the diffusion non-negative
        while matching ``initial_spread``. Defaults to a small positive floor.
    spread_floor, spread_ceiling : float
        Numerical clamp on the realised spread (absolute).
    """

    mean_reversion_speed: float = 0.30
    spread_vol: float = 0.05
    initial_spread: float = 0.012
    long_run_spread_p: float = 0.015
    market_price_of_credit_risk: float = 0.10
    shift: float = 0.002
    spread_floor: float = DEFAULT_SPREAD_FLOOR
    spread_ceiling: float = DEFAULT_SPREAD_CEILING

    def __post_init__(self):
        if self.mean_reversion_speed <= 0:
            raise ValueError(
                "mean_reversion_speed must be positive; got {}".format(self.mean_reversion_speed)
            )
        if self.spread_vol <= 0:
            raise ValueError("spread_vol must be positive; got {}".format(self.spread_vol))
        if self.initial_spread < self.shift:
            raise ValueError(
                "initial_spread ({}) must be >= shift ({}) so the square-root "
                "factor x(0) is non-negative".format(self.initial_spread, self.shift)
            )
        if float(self.spread_floor) >= float(self.spread_ceiling):
            raise ValueError("spread_floor must be below spread_ceiling")

    @property
    def initial_x(self) -> float:
        """Initial square-root-factor level ``x(0) = s(0) - shift``."""
        return float(self.initial_spread) - float(self.shift)

    @property
    def long_run_x_p(self) -> float:
        """P-measure long-run mean of the square-root factor."""
        return float(self.long_run_spread_p) - float(self.shift)

    @property
    def is_placeholder(self) -> bool:
        return True


class CreditSpreadProcess:
    """CIR++ credit-spread process with measure-consistent drift.

    Mirrors :class:`HullWhiteRateProcess`: ``_simulate_array`` returns an
    ``(n, T_months + 1)`` ndarray of spreads; ``simulate`` returns an
    ESGAdapter-style DataFrame.  ``Measure.P`` for ALM / VaR, ``Measure.Q`` for
    valuation.

    SOA ASOP 56 §3.1.3/§3.4; IA TAS M §3.4/§3.6.
    """

    #: Measures this process is permitted to simulate under (G-05 / MR-004).
    SUPPORTED_MEASURES = (Measure.P, Measure.Q)

    def __init__(self, params: Optional[CreditSpreadParams] = None) -> None:
        self.params = params if params is not None else CreditSpreadParams()

    # -- drift target (square-root factor) ---------------------------------
    def _long_run_x(self, measure: Measure) -> float:
        """Measure-dependent long-run mean ``b`` of the square-root factor.

        Q re-anchors the level downward/upward by the CIR risk premium
        ``lambda_s * sigma^2 / kappa``.  A positive market price of credit risk
        raises Q spreads (an increase in spread is the insurer's loss).
        """
        p = self.params
        b_p = p.long_run_x_p
        if measure == Measure.Q:
            premium = (p.market_price_of_credit_risk * p.spread_vol ** 2) / p.mean_reversion_speed
            return b_p + premium
        return b_p

    def _simulate_array(
        self,
        n_scenarios: int,
        T_months: int,
        measure: Measure,
        shocks: np.ndarray,
    ) -> np.ndarray:
        """Simulate spread paths into an ndarray of shape (n, T_months + 1).

        Full-truncation Euler (Lord et al. 2010) on the square-root factor:
        ``x_{+} = x + kappa (b - x_+) dt + sigma sqrt(max(x,0)) sqrt(dt) Z`` with
        the diffusion argument floored at zero each step.  Then
        ``s = clamp(x + shift)``.
        """
        expected_shape = (n_scenarios, T_months)
        if shocks.shape != expected_shape:
            raise ValueError(
                "spread shocks must have shape {}; got {}".format(expected_shape, shocks.shape)
            )
        p = self.params
        dt = 1.0 / 12.0
        sqrt_dt = np.sqrt(dt)
        kappa = p.mean_reversion_speed
        sigma = p.spread_vol
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

        spreads = x + p.shift
        return np.clip(spreads, float(p.spread_floor), float(p.spread_ceiling))

    def simulate(
        self,
        n_scenarios: int,
        T_months: int,
        measure: Measure,
        seed: int = 42,
    ) -> pd.DataFrame:
        """Simulate monthly credit-spread paths as an ESGAdapter-style frame.

        Columns: scenario_id, month, credit_spread, measure.
        Shape: ``n_scenarios * (T_months + 1)`` rows.

        SOA ASOP 56 §3.1.3/§3.4; IA TAS M §3.4.
        """
        measure = _enforce_simulation_measure(self, measure)
        _validate_simulation_dimensions(n_scenarios, T_months)
        n_scenarios = int(n_scenarios)
        T_months = int(T_months)

        rng = np.random.default_rng(seed)
        shocks = _antithetic_normals(rng, n_scenarios, T_months)
        spreads = self._simulate_array(n_scenarios, T_months, measure, shocks)

        scenario_ids, months = _month_grid(n_scenarios, T_months)
        frame = pd.DataFrame({
            "scenario_id": scenario_ids,
            "month": months,
            "credit_spread": spreads.reshape(-1),
            "measure": measure.value,
        })
        return _assert_output_measure(frame, measure, type(self).__name__)


def _inner_q_spread_process(spread_state: float, base_params: CreditSpreadParams) -> CreditSpreadProcess:
    """Build a Q-measure CIR++ spread process conditioned on outer spread ``s_H``.

    The inner valuation starts at the conditioning spread level ``s_H`` (via the
    CIR++ shift so ``x(0) = s_H - shift >= 0``); mean-reversion speed, vol, shift
    and the credit risk premium are inherited from the outer parameters.  Only
    the *level* is re-anchored, exactly mirroring :func:`_inner_q_process` for the
    short rate.
    """
    s_h = float(spread_state)
    # Re-anchor the starting level; keep x(0) non-negative by lowering the shift
    # if the conditioning spread is below the configured shift (deep tail).
    shift = min(float(base_params.shift), max(s_h, 0.0))
    inner = CreditSpreadParams(
        mean_reversion_speed=base_params.mean_reversion_speed,
        spread_vol=base_params.spread_vol,
        initial_spread=max(s_h, float(base_params.spread_floor)),
        long_run_spread_p=base_params.long_run_spread_p,
        market_price_of_credit_risk=base_params.market_price_of_credit_risk,
        shift=shift,
        spread_floor=base_params.spread_floor,
        spread_ceiling=base_params.spread_ceiling,
    )
    return CreditSpreadProcess(inner)


def expected_credit_loss_fraction(spread_paths: np.ndarray) -> np.ndarray:
    """Reduced-form expected credit-loss fraction over a horizon path.

    Given monthly spread paths ``s`` of shape ``(n, k+1)`` interpreted as a
    hazard×LGD proxy, returns the per-path expected loss fraction
    ``1 - exp(-∫ s du)`` with the integral approximated by the monthly
    left-Riemann sum ``sum_j s_j * dt`` (Duffie-Singleton 1999).

    Returns an array of shape ``(n,)`` in ``[0, 1)``.
    """
    arr = np.asarray(spread_paths, dtype=float)
    if arr.ndim != 2:
        raise ValueError("spread_paths must be 2-D (n, k+1)")
    dt = 1.0 / 12.0
    # left-Riemann over the steps that actually elapse (exclude the final node)
    integral = arr[:, : arr.shape[1] - 1].sum(axis=1) * dt
    return 1.0 - np.exp(-integral)


__all__ = [
    "DEFAULT_SPREAD_FLOOR",
    "DEFAULT_SPREAD_CEILING",
    "CreditSpreadParams",
    "CreditSpreadProcess",
    "_inner_q_spread_process",
    "expected_credit_loss_fraction",
]
