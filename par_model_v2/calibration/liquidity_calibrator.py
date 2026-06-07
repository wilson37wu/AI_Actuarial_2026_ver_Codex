"""
CIR++ Liquidity-Premium Calibrator (Phase 21 Task 3)
====================================================

Calibrates the parameters of the :class:`LiquidityPremiumProcess` (CIR++
mean-reverting square-root liquidity-premium / funding-spread driver,
``par_model_v2.stochastic.liquidity_premium``) to a historical
liquidity-premium series, mirroring the ``HullWhiteCalibrator`` (rates),
``GBMCalibrator`` (equity), ``CIRCalibrator`` (credit spread), and
``LapseBehaviourCalibrator`` (lapse behaviour) already in the package.

Methodology — deliberate delegation
-----------------------------------
The liquidity premium follows the SAME CIR++ dynamics as the credit spread
(one tested discretisation, one estimator).  This calibrator therefore
**delegates the transition regression to** :class:`CIRCalibrator` — the
textbook homoscedastic CIR OLS (Kladivko 2007; Brigo-Mercurio 2006):

    dx_t / sqrt(x_{t-1}) = beta1 (dt / sqrt(x_{t-1})) + beta2 (sqrt(x_{t-1}) dt) + eps

recovering ``kappa_l = -beta2``, long-run level ``b = beta1 / kappa_l`` (hence
the P long-run premium ``b + shift``), ``sigma_l^2 = Var(eps)/dt``, and the
market price of liquidity risk ``lambda_l`` from a documented risk-neutral
long-run anchor via ``b^Q - b^P = lambda_l sigma_l^2 / kappa_l``.  Delegation
re-uses the regression-tested estimator rather than duplicating it (audit
trail: one estimator, two drivers — SOA ASOP 56 3.4).

Standards
---------
SOA ASOP 56 3.4 (calibration documentation); SOA ASOP 25 3.3 (credibility /
historical estimation); IA TAS M 3.5 / 3.6 (assumption sign-off,
traceability); EIOPA volatility-adjustment methodology (illiquidity-premium
component of asset spreads).

PRODUCTION USE RESTRICTION
--------------------------
Calibration is driven by an educational-proxy funding-spread series and a
single-path OLS estimator.  Before production capital or pricing use, replace
the fixture with credentialled liquidity-premium extracts (covered-bond /
swap-basis or VA-component series from an approved vendor), use a full-sample
maximum-likelihood / Kalman estimator with standard errors, and obtain a
genuine Assumption Owner + independent APS X2 review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from par_model_v2.calibration.cir_calibrator import (
    CIRCalibrationInputs,
    CIRCalibrator,
)
from par_model_v2.stochastic.liquidity_premium import LiquidityPremiumParams


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

@dataclass
class LiquidityCalibrationInputs:
    """Inputs to the CIR++ liquidity-premium calibration.

    Parameters
    ----------
    calibration_date : datetime.date
        As-of date of the calibration.
    premium_history : pd.Series
        Observed liquidity-premium / funding-spread series in absolute terms
        (e.g. 0.006 = 60 bp), indexed by observation date.  Monthly sampling
        is assumed by default (``dt = 1/12``).
    shift : float
        CIR++ deterministic shift ``phi`` (>=0), strictly below the minimum
        observed premium.
    risk_neutral_long_run_premium : float, optional
        Documented Q-measure long-run premium anchor (e.g. the bond-implied
        illiquidity component) used to back out ``lambda_l``.  If None,
        ``lambda_l`` falls back to ``default_market_price_of_liquidity_risk``.
    dt : float
        Time step of the series in years (1/12 for monthly).
    risk_premium_upper : float
        Cap on the recovered ``lambda_l``.
    default_market_price_of_liquidity_risk : float
        Fallback ``lambda_l`` when no risk-neutral anchor is supplied.
    premium_floor, premium_ceiling : float
        Passed through to the resulting :class:`LiquidityPremiumParams`.
    """

    calibration_date: date
    premium_history: pd.Series
    shift: float = 0.001
    risk_neutral_long_run_premium: Optional[float] = None
    dt: float = 1.0 / 12.0
    risk_premium_upper: float = 2.0
    default_market_price_of_liquidity_risk: float = 0.10
    premium_floor: float = 0.0
    premium_ceiling: float = 0.10

    def __post_init__(self) -> None:
        if not isinstance(self.premium_history, pd.Series):
            raise TypeError("premium_history must be a pandas Series")
        if len(self.premium_history) < 3:
            raise ValueError("premium_history needs >= 3 observations to calibrate")
        if float(self.dt) <= 0:
            raise ValueError("dt must be positive")
        s = self.premium_history.to_numpy(dtype=float)
        if np.any(~np.isfinite(s)):
            raise ValueError("premium_history contains non-finite values")
        if np.any(s < 0):
            raise ValueError("premium_history contains negative premia")
        if float(self.shift) >= float(np.min(s)):
            raise ValueError(
                "shift ({}) must be strictly below the minimum observed premium "
                "({}) so the square-root factor x is positive".format(self.shift, float(np.min(s)))
            )

    def to_cir_inputs(self) -> CIRCalibrationInputs:
        """Map to :class:`CIRCalibrationInputs` for the delegated regression."""
        return CIRCalibrationInputs(
            calibration_date=self.calibration_date,
            spread_history=self.premium_history,
            shift=float(self.shift),
            risk_neutral_long_run_spread=self.risk_neutral_long_run_premium,
            dt=float(self.dt),
            risk_premium_upper=float(self.risk_premium_upper),
            default_market_price_of_credit_risk=float(self.default_market_price_of_liquidity_risk),
            spread_floor=float(self.premium_floor),
            spread_ceiling=float(self.premium_ceiling),
        )


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class LiquidityCalibrationResult:
    """Calibrated CIR++ liquidity-premium parameters plus fit diagnostics."""

    calibration_date: date
    mean_reversion_speed: float          # kappa_l
    long_run_premium_p: float            # l^P_inf = b + shift
    premium_vol: float                   # sigma_l
    market_price_of_liquidity_risk: float  # lambda_l
    shift: float
    initial_premium: float
    n_obs: int
    feller_ratio: float                  # 2*kappa*b / sigma^2 (>=1 => Feller holds)
    feller_ok: bool
    fit_r2: float                        # R^2 of the homoscedastic CIR regression
    residual_std: float
    risk_neutral_long_run_premium: Optional[float]
    premium_floor: float = 0.0
    premium_ceiling: float = 0.10
    is_placeholder: bool = False
    notes: str = ""

    @property
    def half_life_years(self) -> float:
        return float(np.log(2.0) / self.mean_reversion_speed) if self.mean_reversion_speed > 0 else float("inf")

    def to_params(self) -> LiquidityPremiumParams:
        """Return a :class:`LiquidityPremiumParams` from the calibrated values."""
        return LiquidityPremiumParams(
            mean_reversion_speed=float(self.mean_reversion_speed),
            premium_vol=float(self.premium_vol),
            initial_premium=float(self.initial_premium),
            long_run_premium_p=float(self.long_run_premium_p),
            market_price_of_liquidity_risk=float(self.market_price_of_liquidity_risk),
            shift=float(self.shift),
            premium_floor=float(self.premium_floor),
            premium_ceiling=float(self.premium_ceiling),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calibration_date": self.calibration_date.isoformat(),
            "mean_reversion_speed": self.mean_reversion_speed,
            "long_run_premium_p": self.long_run_premium_p,
            "premium_vol": self.premium_vol,
            "market_price_of_liquidity_risk": self.market_price_of_liquidity_risk,
            "shift": self.shift,
            "initial_premium": self.initial_premium,
            "n_obs": self.n_obs,
            "feller_ratio": self.feller_ratio,
            "feller_ok": self.feller_ok,
            "fit_r2": self.fit_r2,
            "residual_std": self.residual_std,
            "risk_neutral_long_run_premium": self.risk_neutral_long_run_premium,
            "premium_floor": self.premium_floor,
            "premium_ceiling": self.premium_ceiling,
            "half_life_years": self.half_life_years,
            "is_placeholder": self.is_placeholder,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Calibrator
# ---------------------------------------------------------------------------

class LiquidityPremiumCalibrator:
    """Calibrate CIR++ liquidity-premium parameters from a historical series.

    Delegates the homoscedastic CIR OLS transition regression to the tested
    :class:`CIRCalibrator` and maps the result onto liquidity-named
    parameters.  SOA ASOP 56 3.4; SOA ASOP 25 3.3.
    """

    def __init__(self, inputs: LiquidityCalibrationInputs) -> None:
        self.inputs = inputs

    def calibrate(self) -> LiquidityCalibrationResult:
        inp = self.inputs
        cir_result = CIRCalibrator(inp.to_cir_inputs()).calibrate()

        notes = (
            "CIR++ liquidity-premium calibration on {} monthly observations "
            "(dt={:.4f}); delegated to the homoscedastic CIR OLS transition "
            "regression (CIRCalibrator): kappa_l from the mean-reversion "
            "regressor, P long-run premium from beta1/kappa + shift, sigma_l "
            "from the residual variance, lambda_l from the documented "
            "risk-neutral long-run anchor via the CIR risk-premium relation. "
            "One tested estimator serves both the credit and liquidity CIR++ "
            "drivers (SOA ASOP 56 3.4)."
        ).format(cir_result.n_obs, float(inp.dt))

        return LiquidityCalibrationResult(
            calibration_date=cir_result.calibration_date,
            mean_reversion_speed=float(cir_result.mean_reversion_speed),
            long_run_premium_p=float(cir_result.long_run_spread_p),
            premium_vol=float(cir_result.spread_vol),
            market_price_of_liquidity_risk=float(cir_result.market_price_of_credit_risk),
            shift=float(cir_result.shift),
            initial_premium=float(cir_result.initial_spread),
            n_obs=int(cir_result.n_obs),
            feller_ratio=float(cir_result.feller_ratio),
            feller_ok=bool(cir_result.feller_ok),
            fit_r2=float(cir_result.fit_r2),
            residual_std=float(cir_result.residual_std),
            risk_neutral_long_run_premium=inp.risk_neutral_long_run_premium,
            premium_floor=float(inp.premium_floor),
            premium_ceiling=float(inp.premium_ceiling),
            is_placeholder=False,
            notes=notes,
        )


__all__ = [
    "LiquidityCalibrationInputs",
    "LiquidityCalibrationResult",
    "LiquidityPremiumCalibrator",
]
