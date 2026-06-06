"""
Lapse Behavioural-Index Calibrator (Phase 19 Task 5)
====================================================

Calibrates the parameters of the :class:`LapseBehaviourProcess` (mean-reverting
OU *behavioural index* ``b(t)``, ``par_model_v2.stochastic.lapse_behaviour``) to
a historical lapse-experience series, mirroring the ``HullWhiteCalibrator``
(rates), ``GBMCalibrator`` (equity), and ``CIRCalibrator`` (credit spread)
already in the calibration package.

Process recap
-------------
The behavioural index is a centred Ornstein-Uhlenbeck factor

    db(t) = kappa_b (theta_b - b(t)) dt + sigma_b dW_b(t)

with the horizon lapse **multiplier** ``M = exp(b)`` (lognormal, A/E ratio).
A positive ``b`` raises every lapse rate proportionally; a negative ``b`` lowers
it.  ``b`` is *non-financial* (P = Q drift) — there is no traded hedge and hence
no risk-neutral re-anchoring.  The locked best-estimate basis is unbiased on a
credible basis, so the long-run level ``theta_b`` is expected to sit at ~0
(A/E ~ 1).

Calibration methodology (SOA ASOP 56 §3.4; ASOP 25 §3.3; ASOP 7 §3.3)
---------------------------------------------------------------------
The observed experience is a monthly actual-to-expected (A/E) lapse ratio; the
behavioural index is its log, ``b_t = log(A/E_t)``.  The OU process has the
**exact** AR(1) transition (no Euler bias; matches
``LapseBehaviourProcess._simulate_array``):

    b_t = phi * b_{t-1} + theta_b (1 - phi) + eps_t ,
    phi = exp(-kappa_b dt) ,  Var(eps) = sigma_b^2 (1 - phi^2) / (2 kappa_b) .

1. **Mean reversion ``kappa_b`` and long-run level ``theta_b``.** Ordinary least
   squares of ``b_t`` on ``b_{t-1}`` (with intercept) gives slope ``phi`` and
   intercept ``c = theta_b (1 - phi)``.  Then
       kappa_b = -ln(phi) / dt        (requires 0 < phi < 1),
       theta_b = c / (1 - phi)        (== sample mean to first order).

2. **Behaviour vol ``sigma_b``.** From the residual variance ``V`` of the same
   regression, inverting the OU stationary relation:
       sigma_b = sqrt( V * 2 kappa_b / (1 - phi^2) ) .
   (Equivalently ``sigma_b^2 = V / dt`` to first order in ``dt``; the exact form
   is used so the recovered ``sigma_b`` reproduces the simulator's conditional
   variance.)

Robustness guards mirror ``CIRCalibrator``: a non-mean-reverting sample
(``phi`` >= 1 or <= 0) falls back to a small positive speed and the sample-mean
long-run level, and ``sigma_b`` is floored away from zero.

Standards
---------
SOA ASOP 7 §3.3 (policyholder behaviour); SOA ASOP 56 §3.4 (calibration
documentation); SOA ASOP 25 §3.3 (credibility / historical estimation);
IA TAS M §3.5/§3.6 (assumption sign-off, traceability).

PRODUCTION USE RESTRICTION
--------------------------
Calibration is driven by an educational-proxy A/E series and a single-path OLS
estimator with no exposure weighting, cohort/duration segmentation, or standard
errors.  Before production capital or pricing use, replace the fixture with a
credentialled actual-vs-expected persistency study, use an exposure-weighted /
maximum-likelihood estimator with standard errors, and obtain a genuine
Assumption Owner + independent APS X2 review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict

import numpy as np
import pandas as pd

from par_model_v2.stochastic.lapse_behaviour import LapseBehaviourParams


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

@dataclass
class LapseCalibrationInputs:
    """Inputs to the OU lapse behavioural-index calibration.

    Parameters
    ----------
    calibration_date : datetime.date
        As-of date of the calibration.
    ae_history : pd.Series
        Observed monthly actual-to-expected (A/E) lapse ratio (e.g. 1.05 = 5%
        more lapses than expected), indexed by observation date, strictly
        positive.  Monthly sampling is assumed by default (``dt = 1/12``).
    dt : float
        Time step of the series in years (1/12 for monthly).
    capital_initial_index : float
        ``b(0)`` to write into the calibrated :class:`LapseBehaviourParams` for
        the capital projection.  Defaults to 0.0 (central A/E = 1 start) so the
        capital tail is driven by symmetric behavioural shocks rather than a
        point-in-time experience deviation.
    """

    calibration_date: date
    ae_history: pd.Series
    dt: float = 1.0 / 12.0
    capital_initial_index: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.ae_history, pd.Series):
            raise TypeError("ae_history must be a pandas Series")
        if len(self.ae_history) < 3:
            raise ValueError("ae_history needs >= 3 observations to calibrate")
        if float(self.dt) <= 0:
            raise ValueError("dt must be positive")
        a = self.ae_history.to_numpy(dtype=float)
        if np.any(~np.isfinite(a)):
            raise ValueError("ae_history contains non-finite values")
        if np.any(a <= 0):
            raise ValueError("ae_history contains non-positive A/E ratios")


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class LapseCalibrationResult:
    """Calibrated OU behavioural-index parameters plus fit diagnostics."""

    calibration_date: date
    mean_reversion_speed: float      # kappa_b
    long_run_level: float            # theta_b (log-multiplier; ~0 => A/E ~ 1)
    behaviour_vol: float             # sigma_b
    initial_index: float             # b(0) written into the capital params
    last_observed_index: float       # b at the end of the experience series
    stationary_std: float            # sigma_b / sqrt(2 kappa_b)
    half_life_years: float           # ln(2) / kappa_b
    n_obs: int
    fit_r2: float                    # R^2 of the AR(1) regression (diagnostic)
    residual_std: float
    ar1_phi: float                   # exp(-kappa_b dt)
    long_run_ae: float               # exp(theta_b)
    is_placeholder: bool = False
    notes: str = ""

    def to_params(self, use_capital_initial_index: bool = True) -> LapseBehaviourParams:
        """Return a :class:`LapseBehaviourParams` from the calibrated values.

        The OU process centres at 0; ``theta_b`` is reported as a diagnostic and
        (when materially non-zero) folded into ``initial_index`` only if the
        caller chooses.  For capital use the central start ``b(0)`` is used.
        """
        b0 = float(self.initial_index) if use_capital_initial_index else float(self.last_observed_index)
        return LapseBehaviourParams(
            mean_reversion_speed=float(self.mean_reversion_speed),
            behaviour_vol=float(self.behaviour_vol),
            initial_index=b0,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calibration_date": self.calibration_date.isoformat(),
            "mean_reversion_speed": self.mean_reversion_speed,
            "long_run_level": self.long_run_level,
            "behaviour_vol": self.behaviour_vol,
            "initial_index": self.initial_index,
            "last_observed_index": self.last_observed_index,
            "stationary_std": self.stationary_std,
            "half_life_years": self.half_life_years,
            "n_obs": self.n_obs,
            "fit_r2": self.fit_r2,
            "residual_std": self.residual_std,
            "ar1_phi": self.ar1_phi,
            "long_run_ae": self.long_run_ae,
            "is_placeholder": self.is_placeholder,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Calibrator
# ---------------------------------------------------------------------------

class LapseBehaviourCalibrator:
    """Calibrate OU behavioural-index parameters from a historical A/E series.

    SOA ASOP 7 §3.3; ASOP 56 §3.4; ASOP 25 §3.3.
    """

    def __init__(self, inputs: LapseCalibrationInputs) -> None:
        self.inputs = inputs

    def calibrate(self) -> LapseCalibrationResult:
        inp = self.inputs
        ae = inp.ae_history.to_numpy(dtype=float)
        dt = float(inp.dt)

        # Behavioural index b = log(A/E).
        b = np.log(ae)
        b_prev = b[:-1]
        b_next = b[1:]

        # OU AR(1) OLS:  b_next = c + phi * b_prev + eps
        design = np.column_stack([np.ones_like(b_prev), b_prev])
        beta, *_ = np.linalg.lstsq(design, b_next, rcond=None)
        c, phi = float(beta[0]), float(beta[1])

        # Mean reversion and long-run level with robustness guards.
        if not np.isfinite(phi) or phi <= 0.0 or phi >= 1.0:
            # Non-mean-reverting / explosive sample: fall back to a small positive
            # speed and the sample-mean long-run level (mirrors CIRCalibrator).
            kappa = 1e-3
            theta = float(np.mean(b))
            phi_eff = float(np.exp(-kappa * dt))
        else:
            kappa = -np.log(phi) / dt
            theta = c / (1.0 - phi)
            phi_eff = phi
            if not np.isfinite(theta):
                theta = float(np.mean(b))

        residuals = b_next - design @ beta
        residual_var = (
            float(np.var(residuals, ddof=2)) if residuals.size > 2 else float(np.var(residuals))
        )
        # Invert the OU stationary conditional variance to recover sigma_b.
        denom = 1.0 - phi_eff * phi_eff
        if denom > 1e-12 and kappa > 0:
            sigma = float(np.sqrt(max(residual_var, 1e-12) * 2.0 * kappa / denom))
        else:  # degenerate guard
            sigma = float(np.sqrt(max(residual_var, 1e-12) / dt))
        sigma = max(sigma, 1e-4)

        # R^2 of the AR(1) regression (fit diagnostic, not a gate).
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((b_next - np.mean(b_next)) ** 2))
        fit_r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        stationary_std = float(sigma / np.sqrt(2.0 * kappa)) if kappa > 0 else float("inf")
        half_life = float(np.log(2.0) / kappa) if kappa > 0 else float("inf")

        notes = (
            "OU AR(1) OLS calibration on {} monthly log(A/E) observations (dt={:.4f}); "
            "kappa from the regression slope phi=exp(-kappa dt), long-run level from "
            "intercept/(1-phi) (== sample mean to first order), sigma_b from the residual "
            "variance via the OU stationary relation. Behaviour is non-financial (P=Q "
            "drift); capital projection starts at b(0)={:.4f}.".format(
                len(ae), dt, float(inp.capital_initial_index)
            )
        )

        return LapseCalibrationResult(
            calibration_date=inp.calibration_date,
            mean_reversion_speed=float(kappa),
            long_run_level=float(theta),
            behaviour_vol=float(sigma),
            initial_index=float(inp.capital_initial_index),
            last_observed_index=float(b[-1]),
            stationary_std=float(stationary_std),
            half_life_years=float(half_life),
            n_obs=len(ae),
            fit_r2=float(fit_r2),
            residual_std=float(np.sqrt(residual_var)),
            ar1_phi=float(phi_eff),
            long_run_ae=float(np.exp(theta)),
            is_placeholder=False,
            notes=notes,
        )


__all__ = [
    "LapseCalibrationInputs",
    "LapseCalibrationResult",
    "LapseBehaviourCalibrator",
]
