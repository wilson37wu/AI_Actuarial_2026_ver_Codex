"""
CIR++ Credit-Spread Calibrator (Phase 18 Task 2)
================================================

Calibrates the parameters of the :class:`CreditSpreadProcess` (CIR++
mean-reverting square-root credit-spread driver, ``par_model_v2.stochastic.
credit_spread``) to a historical credit-spread series, mirroring the
``HullWhiteCalibrator`` (rates) and ``GBMCalibrator`` (equity) already in the
calibration package.

Process recap
-------------
The spread is ``s(t) = x(t) + phi`` (``phi`` = CIR++ shift) with the
square-root factor ``x`` following

    dx = kappa (b - x) dt + sigma sqrt(x) dW .

Calibration methodology (SOA ASOP 56 §3.4)
------------------------------------------
1. **Mean reversion ``kappa`` and long-run level ``b`` (hence the P-measure
   long-run spread).** The Euler transition of the square-root factor,
   normalised by ``sqrt(x_{t-1})`` to homoscedasticity, is the textbook CIR
   OLS regression (Kladivko 2007; Brigo-Mercurio 2006):

       Δx_t / sqrt(x_{t-1}) = beta1 * ( dt / sqrt(x_{t-1}) )
                            + beta2 * ( sqrt(x_{t-1}) * dt )
                            + sigma sqrt(dt) eps_t

   with ``beta1 = kappa*b`` and ``beta2 = -kappa``.  Ordinary least squares on
   the two regressors recovers ``kappa = -beta2`` and ``b = beta1 / kappa``;
   the long-run spread is ``b + phi``.

2. **Spread vol ``sigma``.** ``sigma^2 = Var(residuals) / dt`` from the same
   regression (the residuals are the ``sigma sqrt(dt) eps`` term).

3. **Market price of credit risk ``lambda_s``.** Not identifiable from the
   real-world (P) series alone — it is the P→Q re-anchoring of the long-run
   level.  It is derived from a documented risk-neutral long-run-spread anchor
   ``s^Q_inf`` (CDS / bond-implied) via the standard CIR risk-premium relation
       b^Q - b^P = lambda_s * sigma^2 / kappa
   so that ``lambda_s = (s^Q_inf - s^P_inf) * kappa / sigma^2`` (clamped to
   ``[0, risk_premium_upper]``).  A positive value means risk-neutral spreads
   exceed real-world spreads on average (the credit risk premium).

Standards
---------
SOA ASOP 56 §3.4 (calibration documentation); SOA ASOP 25 §3.3 (credibility /
historical estimation); IA TAS M §3.5 (assumption sign-off).

PRODUCTION USE RESTRICTION
--------------------------
Calibration is driven by educational-proxy history and a single-path OLS
estimator.  Before production capital or pricing use, replace the fixture with
credentialled credit-market extracts (ChinaBond / Wind / Markit), use a
full-sample maximum-likelihood / Kalman estimator with standard errors, and
obtain a genuine Assumption Owner + independent APS X2 review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from par_model_v2.stochastic.credit_spread import CreditSpreadParams


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

@dataclass
class CIRCalibrationInputs:
    """Inputs to the CIR++ credit-spread calibration.

    Parameters
    ----------
    calibration_date : datetime.date
        As-of date of the calibration.
    spread_history : pd.Series
        Observed credit-spread series in absolute terms (e.g. 0.012 = 120 bp),
        indexed by observation date.  Monthly sampling is assumed by default
        (``dt = 1/12``).
    shift : float
        CIR++ deterministic shift ``phi`` (>=0) keeping the square-root factor
        ``x = spread - shift`` non-negative.  Must be below the minimum
        observed spread.
    risk_neutral_long_run_spread : float, optional
        Documented Q-measure (CDS / bond-implied) long-run spread anchor used
        to back out the market price of credit risk.  If None, ``lambda_s`` is
        set to ``default_market_price_of_credit_risk``.
    dt : float
        Time step of the series in years (1/12 for monthly).
    risk_premium_upper : float
        Cap on the recovered ``lambda_s`` (numerical safety / plausibility).
    default_market_price_of_credit_risk : float
        Fallback ``lambda_s`` when no risk-neutral anchor is supplied.
    spread_floor, spread_ceiling : float
        Passed through to the resulting :class:`CreditSpreadParams`.
    """

    calibration_date: date
    spread_history: pd.Series
    shift: float = 0.003
    risk_neutral_long_run_spread: Optional[float] = None
    dt: float = 1.0 / 12.0
    risk_premium_upper: float = 2.0
    default_market_price_of_credit_risk: float = 0.10
    spread_floor: float = 0.0
    spread_ceiling: float = 0.20

    def __post_init__(self) -> None:
        if not isinstance(self.spread_history, pd.Series):
            raise TypeError("spread_history must be a pandas Series")
        if len(self.spread_history) < 3:
            raise ValueError("spread_history needs >= 3 observations to calibrate")
        if float(self.dt) <= 0:
            raise ValueError("dt must be positive")
        s = self.spread_history.to_numpy(dtype=float)
        if np.any(~np.isfinite(s)):
            raise ValueError("spread_history contains non-finite values")
        if np.any(s < 0):
            raise ValueError("spread_history contains negative spreads")
        if float(self.shift) >= float(np.min(s)):
            raise ValueError(
                "shift ({}) must be strictly below the minimum observed spread "
                "({}) so the square-root factor x is positive".format(self.shift, float(np.min(s)))
            )


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class CIRCalibrationResult:
    """Calibrated CIR++ credit-spread parameters plus fit diagnostics."""

    calibration_date: date
    mean_reversion_speed: float        # kappa
    long_run_spread_p: float           # s^P_inf = b + shift
    spread_vol: float                  # sigma
    market_price_of_credit_risk: float # lambda_s
    shift: float
    initial_spread: float
    n_obs: int
    feller_ratio: float                # 2*kappa*b / sigma^2  (>=1 => Feller holds)
    feller_ok: bool
    fit_r2: float                      # R^2 of the homoscedastic CIR regression
    residual_std: float
    risk_neutral_long_run_spread: Optional[float]
    spread_floor: float = 0.0
    spread_ceiling: float = 0.20
    is_placeholder: bool = False
    notes: str = ""

    def to_params(self) -> CreditSpreadParams:
        """Return a :class:`CreditSpreadParams` from the calibrated values."""
        return CreditSpreadParams(
            mean_reversion_speed=float(self.mean_reversion_speed),
            spread_vol=float(self.spread_vol),
            initial_spread=float(self.initial_spread),
            long_run_spread_p=float(self.long_run_spread_p),
            market_price_of_credit_risk=float(self.market_price_of_credit_risk),
            shift=float(self.shift),
            spread_floor=float(self.spread_floor),
            spread_ceiling=float(self.spread_ceiling),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calibration_date": self.calibration_date.isoformat(),
            "mean_reversion_speed": self.mean_reversion_speed,
            "long_run_spread_p": self.long_run_spread_p,
            "spread_vol": self.spread_vol,
            "market_price_of_credit_risk": self.market_price_of_credit_risk,
            "shift": self.shift,
            "initial_spread": self.initial_spread,
            "n_obs": self.n_obs,
            "feller_ratio": self.feller_ratio,
            "feller_ok": self.feller_ok,
            "fit_r2": self.fit_r2,
            "residual_std": self.residual_std,
            "risk_neutral_long_run_spread": self.risk_neutral_long_run_spread,
            "spread_floor": self.spread_floor,
            "spread_ceiling": self.spread_ceiling,
            "is_placeholder": self.is_placeholder,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Calibrator
# ---------------------------------------------------------------------------

class CIRCalibrator:
    """Calibrate CIR++ credit-spread parameters from a historical spread series.

    SOA ASOP 56 §3.4; SOA ASOP 25 §3.3.
    """

    def __init__(self, inputs: CIRCalibrationInputs) -> None:
        self.inputs = inputs

    def calibrate(self) -> CIRCalibrationResult:
        inp = self.inputs
        s = inp.spread_history.to_numpy(dtype=float)
        shift = float(inp.shift)
        dt = float(inp.dt)

        # Square-root factor x = s - shift (strictly positive by validation).
        x = s - shift
        x_prev = x[:-1]
        x_next = x[1:]
        sqrt_xp = np.sqrt(x_prev)
        dx = x_next - x_prev

        # Homoscedastic CIR OLS:  dx/sqrt(x_prev) = b1 * (dt/sqrt(x_prev)) + b2 * (sqrt(x_prev)*dt) + eps
        y = dx / sqrt_xp
        a1 = dt / sqrt_xp
        a2 = sqrt_xp * dt
        design = np.column_stack([a1, a2])
        beta, *_ = np.linalg.lstsq(design, y, rcond=None)
        beta1, beta2 = float(beta[0]), float(beta[1])

        kappa = -beta2
        # Guard pathological sign (very short / noisy samples): fall back to a
        # small positive speed and the sample-mean long-run level.
        if not np.isfinite(kappa) or kappa <= 1e-6:
            kappa = max(1e-3, abs(kappa))
            b = float(np.mean(x_prev))
        else:
            b = beta1 / kappa
            if not np.isfinite(b) or b <= 0:
                b = float(np.mean(x_prev))

        residuals = y - design @ beta
        residual_var = float(np.var(residuals, ddof=2)) if residuals.size > 2 else float(np.var(residuals))
        sigma = float(np.sqrt(max(residual_var, 1e-12) / dt))

        # R^2 of the homoscedastic regression (fit diagnostic, not a gate).
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        fit_r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        long_run_spread_p = b + shift

        # Market price of credit risk from the documented risk-neutral anchor.
        if inp.risk_neutral_long_run_spread is not None:
            b_q = float(inp.risk_neutral_long_run_spread) - shift
            premium = b_q - b
            lam = premium * kappa / (sigma ** 2) if sigma > 0 else 0.0
            lam = float(np.clip(lam, 0.0, float(inp.risk_premium_upper)))
        else:
            lam = float(inp.default_market_price_of_credit_risk)

        feller_ratio = (2.0 * kappa * b) / (sigma ** 2) if sigma > 0 else float("inf")
        feller_ok = feller_ratio >= 1.0

        initial_spread = float(s[-1])

        notes = (
            "CIR OLS calibration on {} monthly observations (dt={:.4f}); "
            "kappa from regression slope, long-run spread from intercept/slope "
            "(== sample mean to first order), sigma from residual variance, "
            "lambda_s from documented risk-neutral long-run anchor.".format(len(s), dt)
        )

        return CIRCalibrationResult(
            calibration_date=inp.calibration_date,
            mean_reversion_speed=float(kappa),
            long_run_spread_p=float(long_run_spread_p),
            spread_vol=float(sigma),
            market_price_of_credit_risk=float(lam),
            shift=shift,
            initial_spread=initial_spread,
            n_obs=len(s),
            feller_ratio=float(feller_ratio),
            feller_ok=bool(feller_ok),
            fit_r2=float(fit_r2),
            residual_std=float(np.sqrt(residual_var)),
            risk_neutral_long_run_spread=(
                float(inp.risk_neutral_long_run_spread)
                if inp.risk_neutral_long_run_spread is not None else None
            ),
            spread_floor=float(inp.spread_floor),
            spread_ceiling=float(inp.spread_ceiling),
            is_placeholder=False,
            notes=notes,
        )


__all__ = [
    "CIRCalibrationInputs",
    "CIRCalibrationResult",
    "CIRCalibrator",
]
