"""
Lapse-Behaviour Driver — Non-Financial Policyholder-Behaviour Risk Factor
=========================================================================

Phase 18 Task 3.  Adds the **fourth** — and first *non-financial* — risk driver
to the nested / LSMC economic-capital proxy: a stochastic *policyholder-
behaviour* (lapse-level) state.

Motivation
----------
The Phase 15/17 capital proxy spans three *financial* drivers (short rate,
equity level, credit spread).  Current proxy-modelling practice (IFoA proxy-
modelling working party; Solvency II diversification justification) expands the
proxy basis to **financial AND non-financial** drivers — lapse, mortality-trend.
The asset/liability layer already carries a calibrated *dynamic* lapse function
(:mod:`par_model_v2.projection.dynamic_lapse`) that bends lapse to the
prevailing rate (a financial coupling).  What is still absent from the tail is
the **level uncertainty of policyholder behaviour itself** — the risk that the
whole lapse basis is higher or lower than assumed, independently of markets.
This module supplies that as a dedicated stochastic factor.

Process
-------
A mean-reverting Ornstein-Uhlenbeck **behavioural index** ``b(t)`` centred at 0:

    db(t) = -kappa_b * b(t) dt + sigma_b dW_b(t),   b(0) = 0

The horizon lapse **multiplier** is the lognormal transform

    M(b) = exp(b)              (M = 1 at b = 0; strictly positive; mean-reverting)

so a positive ``b`` raises every lapse rate proportionally and a negative ``b``
lowers it.  ``b`` is a *non-financial* driver: by default it is uncorrelated
with the rate / equity / credit Brownian shocks (configurable), so it injects a
genuinely orthogonal axis into the capital tail.

Why OU (not square-root)
------------------------
The behavioural index is a *signed* log-multiplier (lapse can be both higher and
lower than central), so a Gaussian OU on ``log M`` is the natural choice; the
``exp`` keeps the multiplier positive without a Feller condition.  This mirrors
the standard lognormal treatment of behavioural-stress factors.

Measure note
------------
Policyholder behaviour is a *real-world* (P-measure) risk with no traded hedge
instrument, so there is no risk-neutral drift adjustment: ``b`` has the SAME
dynamics under P and Q (the multiplier is applied to the real-world lapse basis
inside the inner Q valuation).  ``measure`` is accepted for API symmetry with
the financial drivers and is asserted, but does not change the drift.

Standards
---------
SOA ASOP 7  §3.3 — behaviour responsive to / independent of economic conditions
SOA ASOP 25 §3.3 — credibility & correlation basis for the behavioural factor
SOA ASOP 56 §3.1 — assumption documentation / dynamic-behaviour basis
IA  TAS M   §3.5/§3.6 — assumption appropriateness, traceability, validation
IFoA proxy-modelling working party — financial AND non-financial proxy drivers

PRODUCTION USE RESTRICTION
--------------------------
EDUCATIONAL placeholder.  ``kappa_b`` / ``sigma_b`` are illustrative and NOT
calibrated to a credible lapse-experience time series.  The behavioural index is
a single systemic lapse-level factor with no product / cohort structure and no
mortality-trend driver.  Independent APS X2 review pending.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np

from par_model_v2.stochastic.esg_process import Measure


#: Educational default mean-reversion speed (per year) of the behavioural index.
DEFAULT_LAPSE_KAPPA = 0.40
#: Educational default volatility (per sqrt-year) of the behavioural index.
DEFAULT_LAPSE_SIGMA = 0.30


@dataclass(frozen=True)
class LapseBehaviourParams:
    """Parameters of the OU behavioural (lapse-level) index ``b(t)``.

    Parameters
    ----------
    mean_reversion_speed : float
        ``kappa_b`` — pull of the behavioural index back to 0 (per year, > 0).
    behaviour_vol : float
        ``sigma_b`` — diffusion of the behavioural index (per sqrt-year, > 0).
    initial_index : float
        ``b(0)`` — starting log-multiplier (default 0 ⇒ central lapse basis).
    """

    mean_reversion_speed: float = DEFAULT_LAPSE_KAPPA
    behaviour_vol: float = DEFAULT_LAPSE_SIGMA
    initial_index: float = 0.0
    long_run_index: float = 0.0

    methodology: str = (
        "Mean-reverting OU behavioural index b(t); lapse multiplier M=exp(b) "
        "(lognormal, non-financial, P=Q drift)"
    )
    standard_references: Tuple[str, ...] = (
        "SOA ASOP 7 §3.3", "SOA ASOP 25 §3.3", "SOA ASOP 56 §3.1",
        "IA TAS M §3.5", "IA TAS M §3.6", "IFoA proxy-modelling WP",
    )

    def __post_init__(self) -> None:
        if self.mean_reversion_speed <= 0:
            raise ValueError(
                "mean_reversion_speed must be > 0; got {}".format(self.mean_reversion_speed)
            )
        if self.behaviour_vol <= 0:
            raise ValueError("behaviour_vol must be > 0; got {}".format(self.behaviour_vol))

    @property
    def stationary_std(self) -> float:
        """Stationary standard deviation ``sigma_b / sqrt(2 kappa_b)`` of ``b``."""
        return float(self.behaviour_vol / np.sqrt(2.0 * self.mean_reversion_speed))

    def to_dict(self) -> Dict[str, object]:
        return {
            "mean_reversion_speed": self.mean_reversion_speed,
            "behaviour_vol": self.behaviour_vol,
            "initial_index": self.initial_index,
            "long_run_index": self.long_run_index,
            "stationary_std": round(self.stationary_std, 6),
            "methodology": self.methodology,
            "standard_references": list(self.standard_references),
        }


class LapseBehaviourProcess:
    """Exact-discretisation OU simulator for the behavioural index ``b(t)``.

    Uses the exact AR(1) transition of an OU process over a monthly step
    ``dt = 1/12`` (no Euler bias):

        b_{+} = b * e^{-kappa dt} + sqrt( sigma^2 (1 - e^{-2 kappa dt}) / (2 kappa) ) * Z

    so the simulated horizon distribution is exact for any step size
    (ASOP 56 §3.5; ASOP 25 §3.3).  Behaviour is non-financial, so the drift is
    identical under P and Q.
    """

    def __init__(self, params: Optional[LapseBehaviourParams] = None) -> None:
        self.params = params if params is not None else LapseBehaviourParams()

    def _simulate_array(
        self,
        n_scenarios: int,
        T_months: int,
        measure: Measure,
        shocks: np.ndarray,
    ) -> np.ndarray:
        """Return an ``(n, T_months + 1)`` array of behavioural-index paths.

        ``shocks`` is an ``(n, T_months)`` standard-normal (typically antithetic
        + Cholesky-correlated) array supplied by the caller so the behavioural
        factor shares the same correlated draw as the financial drivers.
        """
        Measure(measure)  # validate; behaviour drift is measure-invariant
        p = self.params
        kappa = p.mean_reversion_speed
        sigma = p.behaviour_vol
        theta = p.long_run_index
        dt = 1.0 / 12.0
        phi = float(np.exp(-kappa * dt))
        cond_std = float(np.sqrt(sigma * sigma * (1.0 - phi * phi) / (2.0 * kappa)))

        paths = np.empty((n_scenarios, T_months + 1), dtype=float)
        paths[:, 0] = p.initial_index
        x_prev = np.full(n_scenarios, p.initial_index, dtype=float)
        for month in range(T_months):
            x_prev = theta + phi * (x_prev - theta) + cond_std * shocks[:, month]
            paths[:, month + 1] = x_prev
        return paths

    @staticmethod
    def multiplier(index_level) -> np.ndarray:
        """Lognormal lapse multiplier ``M = exp(b)`` (vectorised)."""
        return np.exp(np.asarray(index_level, dtype=float))


def default_lapse_behaviour() -> LapseBehaviourParams:
    """Pre-set educational behavioural-index parameters."""
    return LapseBehaviourParams()


__all__ = [
    "DEFAULT_LAPSE_KAPPA",
    "DEFAULT_LAPSE_SIGMA",
    "LapseBehaviourParams",
    "LapseBehaviourProcess",
    "default_lapse_behaviour",
]
