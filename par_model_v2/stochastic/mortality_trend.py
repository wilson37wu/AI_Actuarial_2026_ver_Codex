"""
Mortality-Trend Driver — Non-Financial Longevity / Mortality-Level Risk Factor
==============================================================================

Phase 19 Task 3.  Adds the **fifth** — and second *non-financial* — risk driver
to the nested / LSMC economic-capital proxy: a stochastic *mortality-level /
mortality-trend* state.

Motivation
----------
The Phase 18 four-driver capital proxy spans short rate, equity level, credit
spread and a lapse-behaviour index (the first non-financial driver).  Current
proxy-modelling practice (IFoA proxy-modelling working party; Solvency II
diversification justification) expands the proxy basis to **financial AND
non-financial** drivers — lapse AND **mortality-trend**.  The documented
four-driver limitation is explicit ("mortality-trend and FX risks are still NOT
in the tail").  This module supplies the mortality-trend axis: the systemic
uncertainty that the *whole mortality basis* is higher or lower than the central
assumption (longevity / excess-mortality risk), independent of markets and of
policyholder lapse behaviour.

Process
-------
A mean-reverting Ornstein-Uhlenbeck **mortality-trend index** ``m(t)`` centred
at 0:

    dm(t) = -kappa_m * m(t) dt + sigma_m dW_m(t),   m(0) = 0

The horizon mortality **multiplier** is the lognormal transform

    G(m) = exp(m)             (G = 1 at m = 0; strictly positive; mean-reverting)

so a positive ``m`` raises every mortality rate ``q_x`` proportionally (an
excess-mortality / pandemic-shaped trend) and a negative ``m`` lowers it (a
longevity-improvement trend).  ``m`` is a *non-financial* driver: by default it
is uncorrelated with the rate / equity / credit / lapse shocks (configurable),
so it injects a genuinely orthogonal axis into the capital tail.

This is a deliberately simple, single-systemic-factor analogue of the Lee-Carter
time index ``kappa_t`` (a stochastic mortality-improvement trend); the OU form is
chosen for the same reason as the lapse driver — a *signed* log-multiplier with a
mean-reverting stationary distribution and no Feller condition.

Why OU (not Lee-Carter directly)
---------------------------------
A full Lee-Carter / CBD stochastic-mortality model carries an age-period-cohort
structure that is out of scope for a single educational capital driver.  The OU
log-multiplier captures the *systemic level uncertainty* of the mortality basis
— the part that actually moves diversified capital — with one interpretable
parameter pair ``(kappa_m, sigma_m)``.  Cohort / age structure is documented as a
limitation.

Measure note
------------
Mortality trend is a *real-world* (P-measure) risk with no traded hedge
instrument (longevity swaps are not in this educational asset library), so there
is no risk-neutral drift adjustment: ``m`` has the SAME dynamics under P and Q
(the multiplier is applied to the real-world mortality basis inside the inner Q
valuation of the guaranteed death / maturity benefits).  ``measure`` is accepted
for API symmetry with the financial drivers and is asserted, but does not change
the drift.

Standards
---------
SOA ASOP 25 §3.3 — credibility & correlation basis for the mortality factor
SOA ASOP 56 §3.1 — assumption documentation / stochastic-mortality basis
IA  TAS M   §3.5/§3.6 — assumption appropriateness, traceability, validation
IFoA proxy-modelling working party — financial AND non-financial proxy drivers
Lee & Carter (1992) — stochastic mortality time index (motivation only)

PRODUCTION USE RESTRICTION
--------------------------
EDUCATIONAL placeholder.  ``kappa_m`` / ``sigma_m`` are illustrative and NOT
calibrated to a credible mortality-experience / population-mortality time
series.  The mortality-trend index is a single systemic mortality-level factor
with no age / period / cohort structure and no link to a longevity-hedge asset.
Independent APS X2 review pending.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from par_model_v2.stochastic.esg_process import Measure


#: Educational default mean-reversion speed (per year) of the mortality-trend
#: index.  Slower than the lapse index: mortality trends are persistent.
DEFAULT_MORTALITY_KAPPA = 0.30
#: Educational default volatility (per sqrt-year) of the mortality-trend index.
DEFAULT_MORTALITY_SIGMA = 0.15


@dataclass(frozen=True)
class MortalityTrendParams:
    """Parameters of the OU mortality-trend (mortality-level) index ``m(t)``.

    Parameters
    ----------
    mean_reversion_speed : float
        ``kappa_m`` — pull of the mortality-trend index back to 0 (per year, > 0).
    trend_vol : float
        ``sigma_m`` — diffusion of the mortality-trend index (per sqrt-year, > 0).
    initial_index : float
        ``m(0)`` — starting log-multiplier (default 0 ⇒ central mortality basis).
    """

    mean_reversion_speed: float = DEFAULT_MORTALITY_KAPPA
    trend_vol: float = DEFAULT_MORTALITY_SIGMA
    initial_index: float = 0.0

    methodology: str = (
        "Mean-reverting OU mortality-trend index m(t); mortality multiplier "
        "G=exp(m) (lognormal, non-financial, P=Q drift; Lee-Carter-style "
        "systemic level index without age/cohort structure)"
    )
    standard_references: Tuple[str, ...] = (
        "SOA ASOP 25 §3.3", "SOA ASOP 56 §3.1",
        "IA TAS M §3.5", "IA TAS M §3.6", "IFoA proxy-modelling WP",
        "Lee & Carter (1992)",
    )

    def __post_init__(self) -> None:
        if self.mean_reversion_speed <= 0:
            raise ValueError(
                "mean_reversion_speed must be > 0; got {}".format(self.mean_reversion_speed)
            )
        if self.trend_vol <= 0:
            raise ValueError("trend_vol must be > 0; got {}".format(self.trend_vol))

    @property
    def stationary_std(self) -> float:
        """Stationary standard deviation ``sigma_m / sqrt(2 kappa_m)`` of ``m``."""
        return float(self.trend_vol / np.sqrt(2.0 * self.mean_reversion_speed))

    def to_dict(self) -> Dict[str, object]:
        return {
            "mean_reversion_speed": self.mean_reversion_speed,
            "trend_vol": self.trend_vol,
            "initial_index": self.initial_index,
            "stationary_std": round(self.stationary_std, 6),
            "methodology": self.methodology,
            "standard_references": list(self.standard_references),
        }


class MortalityTrendProcess:
    """Exact-discretisation OU simulator for the mortality-trend index ``m(t)``.

    Uses the exact AR(1) transition of an OU process over a monthly step
    ``dt = 1/12`` (no Euler bias):

        m_{+} = m * e^{-kappa dt} + sqrt( sigma^2 (1 - e^{-2 kappa dt}) / (2 kappa) ) * Z

    so the simulated horizon distribution is exact for any step size
    (ASOP 56 §3.5; ASOP 25 §3.3).  Mortality trend is non-financial, so the drift
    is identical under P and Q.
    """

    def __init__(self, params: Optional[MortalityTrendParams] = None) -> None:
        self.params = params if params is not None else MortalityTrendParams()

    def _simulate_array(
        self,
        n_scenarios: int,
        T_months: int,
        measure: Measure,
        shocks: np.ndarray,
    ) -> np.ndarray:
        """Return an ``(n, T_months + 1)`` array of mortality-trend-index paths.

        ``shocks`` is an ``(n, T_months)`` standard-normal (typically antithetic
        + Cholesky-correlated) array supplied by the caller so the mortality
        factor shares the same correlated draw as the other drivers.
        """
        Measure(measure)  # validate; mortality-trend drift is measure-invariant
        p = self.params
        kappa = p.mean_reversion_speed
        sigma = p.trend_vol
        dt = 1.0 / 12.0
        phi = float(np.exp(-kappa * dt))
        cond_std = float(np.sqrt(sigma * sigma * (1.0 - phi * phi) / (2.0 * kappa)))

        paths = np.empty((n_scenarios, T_months + 1), dtype=float)
        paths[:, 0] = p.initial_index
        x_prev = np.full(n_scenarios, p.initial_index, dtype=float)
        for month in range(T_months):
            x_prev = phi * x_prev + cond_std * shocks[:, month]
            paths[:, month + 1] = x_prev
        return paths

    @staticmethod
    def multiplier(index_level) -> np.ndarray:
        """Lognormal mortality multiplier ``G = exp(m)`` (vectorised)."""
        return np.exp(np.asarray(index_level, dtype=float))


def default_mortality_trend() -> MortalityTrendParams:
    """Pre-set educational mortality-trend-index parameters."""
    return MortalityTrendParams()


__all__ = [
    "DEFAULT_MORTALITY_KAPPA",
    "DEFAULT_MORTALITY_SIGMA",
    "MortalityTrendParams",
    "MortalityTrendProcess",
    "default_mortality_trend",
]
