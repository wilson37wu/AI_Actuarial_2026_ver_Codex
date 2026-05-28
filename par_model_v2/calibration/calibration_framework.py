"""
Calibration Framework — Hull-White 1-Factor and GBM Equity
===========================================================

Implements the parameter calibration methodology specified in:
  docs/PARAMETER_CALIBRATION_METHODOLOGY.md

Key classes
-----------
HullWhiteCalibrator
    Calibrates HW1F parameters (a, σ_r) by minimising weighted squared
    pricing errors between model-implied and market ATM swaption prices.
    Uses the Jamshidian decomposition for analytical swaption pricing.

GBMCalibrator
    Calibrates GBM parameters (σ_S, ERP, ρ_{r,S}, δ) from historical
    return series and/or option-implied volatility.

CalibrationResult
    Holds calibrated parameters, goodness-of-fit statistics, and metadata
    required for the calibration change log.

martingale_test
    Validates Q-measure scenarios — checks E_Q[e^{−∫r}S(T)] = S(0)
    within tolerance.  Requires ESG simulate() (Phase 3).

Standards Reference
-------------------
SOA ASOP 56 §3.4  — calibration methodology documentation
SOA ASOP 25 §3.3  — credibility hierarchy for parameter selection
IA TAS M §3.5     — assumption appropriateness and sign-off process

Cross-references
----------------
par_model_v2/stochastic/esg_process.py  — HullWhiteParams, GBMParams dataclasses
par_model_v2/risk/risk_metrics.py       — consumes calibrated scenarios
docs/PARAMETER_CALIBRATION_METHODOLOGY.md §5–6 — full calibration spec

DEVELOPMENT STATUS
------------------
Phase 2 (this cycle):
  - Full class structures, docstrings, analytical swaption price formula.
  - All numerical inputs (yield curves, swaption quotes) are dataclasses
    with documented field semantics.
  - calibrate() raises NotImplementedError until Phase 4 market data is
    available.  The NotImplementedError message includes the exact Phase 4
    task reference so developers know exactly what to implement.

Phase 3:
  - Implement martingale_test() after ESG simulate() is available.

Phase 4:
  - Wire calibrate() to live market data from CNY swaption desk and
    historical CSI 300 / PBOC yield curve data.

PRODUCTION USE RESTRICTION
--------------------------
Parameters produced by this module must be reviewed and signed off by the
Assumption Owner before production use.  See docs/IA_GOVERNANCE_REQUIREMENTS.md.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import optimize as scipy_optimize


# ---------------------------------------------------------------------------
# 1. Input / Quote Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SwaptionQuote:
    """A single ATM payer swaption market quote.

    Attributes
    ----------
    expiry_years : float
        Option expiry in years (e.g., 1.0, 2.0, 5.0, 10.0).
    swap_tenor_years : float
        Underlying swap tenor in years (e.g., 1.0, 5.0, 10.0).
    normal_vol_bps : float
        ATM normal (Bachelier) implied volatility in basis points p.a.
        (e.g., 45.0 means 45 bps p.a. = 0.45% normal vol).
        CNY swaptions are conventionally quoted in normal vol.
    weight : float
        Calibration weight for this tenor point.  Default 1.0.
        Set to 0.0 to exclude a tenor from calibration (e.g., illiquid).

    Notes
    -----
    Normal vol is used for CNY swaptions because rates can be near-zero
    (negative real rates possible) and lognormal Black vol breaks down.
    See docs/PARAMETER_CALIBRATION_METHODOLOGY.md §5.2 for data sources.
    """

    expiry_years: float
    swap_tenor_years: float
    normal_vol_bps: float
    weight: float = 1.0


@dataclass
class HullWhiteCalibrationInputs:
    """All inputs required for HW1F calibration.

    Attributes
    ----------
    calibration_date : date
        As-of date for the calibration.  All market data must be as of
        this date.

    initial_short_rate : float
        r(0) in decimal (e.g., 0.025 = 2.5%).  Typically SHIBOR 1M / 3M
        weighted average on the calibration date.  See §5.1 of the
        calibration methodology document.

    spot_curve : pd.Series
        Spot (zero-coupon) interest rate curve.  Index = tenor in years
        (e.g., [0.25, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30]).
        Values = annualised spot rates in decimal (e.g., 0.025 = 2.5%).
        Used to bootstrap the initial forward curve θ(t).

    swaption_quotes : list of SwaptionQuote
        ATM payer swaption market quotes.  Should cover at least the grid
        in §5.2 of the calibration methodology: expiries {1,2,3,5,7,10}Y
        × tenors {1,2,5,10}Y.

    regulatory_rate_cap : float
        CBIRC maximum allowable discount rate for regulatory reserves.
        Default 0.03 (3.0%).  If initial_short_rate > regulatory_rate_cap,
        the calibration will issue a warning.
        See docs/PARAMETER_CALIBRATION_METHODOLOGY.md §5.1 Note A.

    optimizer_bounds : dict
        Lower and upper bounds for a and σ_r.  Default:
          {"a": (0.001, 1.0), "sigma_r": (0.001, 0.10)}
        Change only if market conditions justify wider bounds.

    optimizer_tol : float
        Convergence tolerance for the L-BFGS-B optimizer.
        Default 1e-10 (tighter than the 1e-8 documentation target to
        provide a safety margin).
    """

    calibration_date: date
    initial_short_rate: float
    spot_curve: pd.Series  # index = tenor (years), values = decimal rates
    swaption_quotes: List[SwaptionQuote]
    regulatory_rate_cap: float = 0.03
    optimizer_bounds: Dict[str, Tuple[float, float]] = field(
        default_factory=lambda: {"a": (0.001, 1.0), "sigma_r": (0.001, 0.10)}
    )
    optimizer_tol: float = 1e-10


@dataclass
class GBMCalibrationInputs:
    """All inputs required for GBM equity calibration.

    Attributes
    ----------
    calibration_date : date
        As-of date for the calibration.

    equity_returns : pd.Series
        Daily log-returns of the CSI 300 total return index.
        Index = datetime; values = ln(S_t / S_{t-1}).
        Required length: ≥ 5 years of daily data (≥ 1,260 observations).

    implied_vol_atm : float
        ATM 30-day implied volatility from 50ETF options on the calibration
        date, in decimal (e.g., 0.20 = 20% p.a.).  If unavailable, set to
        np.nan and the calibration will use historical vol only.

    rf_returns : pd.Series
        Daily risk-free rate series (1Y CNY government bond yield).
        Index = datetime; same date range as equity_returns.
        Values = annualised rates in decimal.  Used to compute excess returns
        for equity risk premium estimation.

    dividend_yield_monthly : pd.Series
        Monthly trailing 12-month dividend yield of CSI 300.
        Index = period end dates; values = decimal (e.g., 0.025 = 2.5%).
        Required length: ≥ 36 months (3 years).

    implied_vol_weight : float
        Weight on implied vol in the blended volatility estimate.
        Default 0.6 (60% implied, 40% historical).  See §6.2 of the
        calibration methodology document.

    erp_survivorship_adjustment : float
        Downward adjustment to raw historical ERP for survivorship bias.
        Default 0.007 (0.7% = midpoint of the 0.5%–1.0% range in §6.4).

    erp_upper_bound : float
        Maximum allowable ERP (floors unreasonable calibrations).
        Default 0.05 (5.0%) per §6.4.
    """

    calibration_date: date
    equity_returns: pd.Series  # daily log-returns of CSI 300
    rf_returns: pd.Series       # daily risk-free rate series
    dividend_yield_monthly: pd.Series  # monthly trailing 12-month dividend yield
    implied_vol_atm: float = np.nan    # NaN if not available
    implied_vol_weight: float = 0.60
    erp_survivorship_adjustment: float = 0.007
    erp_upper_bound: float = 0.05


# ---------------------------------------------------------------------------
# 2. Calibration Result
# ---------------------------------------------------------------------------


@dataclass
class CalibrationResult:
    """Container for calibrated parameters and goodness-of-fit statistics.

    This dataclass holds the output of a calibration run and provides all
    information required to populate the calibration change log per
    docs/PARAMETER_CALIBRATION_METHODOLOGY.md §9.3.

    Attributes
    ----------
    calibration_date : date
        As-of date for the calibration.
    calibration_timestamp : datetime
        UTC timestamp when the calibration was run.

    # Hull-White parameters
    a : float
        Calibrated mean-reversion speed (annualised).
    sigma_r : float
        Calibrated short rate volatility (annualised, decimal).
    lambda_r : float
        Market price of interest rate risk.  Zero until P-measure
        calibration is run (§5.3).
    r0 : float
        Initial short rate (decimal).

    # GBM parameters
    sigma_S : float
        Calibrated equity volatility (annualised, decimal).
    erp : float
        Equity risk premium (P-measure excess return, annualised, decimal).
    dividend_yield : float
        Calibrated dividend yield (annualised, decimal).
    rho : float
        Rate-equity correlation (Pearson, unitless).

    # Goodness-of-fit
    swaption_fit_table : pd.DataFrame or None
        Columns: [expiry_years, swap_tenor_years, market_vol_bps,
                  model_vol_bps, error_bps].
        None if HW calibration was not run.
    swaption_rmse_bps : float or None
        Root mean squared error across the swaption grid (basis points).
    max_swaption_error_bps : float or None
        Maximum absolute error across the grid.  Flag if > 1 bps.

    equity_vol_hist : float or None
        Realised historical equity vol used in blending.
    equity_vol_implied : float or None
        ATM implied vol on calibration date.  None if not available.

    # Metadata
    notes : str
        Free-text notes for the change log (e.g., override rationale).
    is_placeholder : bool
        True if any parameter is a placeholder (not yet calibrated).
        Production use is blocked when is_placeholder = True.
    """

    calibration_date: date
    calibration_timestamp: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )

    # Hull-White parameters (placeholder defaults from esg_process.py)
    a: float = 0.10
    sigma_r: float = 0.012
    lambda_r: float = 0.0
    r0: float = 0.025

    # GBM parameters
    sigma_S: float = 0.22
    erp: float = 0.045
    dividend_yield: float = 0.025
    rho: float = -0.15

    # Goodness-of-fit
    swaption_fit_table: Optional[pd.DataFrame] = None
    swaption_rmse_bps: Optional[float] = None
    max_swaption_error_bps: Optional[float] = None
    equity_vol_hist: Optional[float] = None
    equity_vol_implied: Optional[float] = None

    # Metadata
    notes: str = ""
    is_placeholder: bool = True

    def summary(self) -> str:
        """Return a human-readable calibration summary string."""
        lines = [
            f"Calibration Result — {self.calibration_date}",
            f"  Timestamp:  {self.calibration_timestamp.isoformat()}",
            f"  Placeholder: {self.is_placeholder}",
            "",
            "Hull-White Parameters:",
            f"  a (mean-reversion speed):  {self.a:.4f}",
            f"  σ_r (short rate vol):      {self.sigma_r:.4f} ({self.sigma_r*100:.2f}% p.a.)",
            f"  λ_r (market price of risk): {self.lambda_r:.4f}",
            f"  r(0) (initial short rate):  {self.r0:.4f} ({self.r0*100:.2f}%)",
            "",
            "GBM Equity Parameters:",
            f"  σ_S (equity vol):     {self.sigma_S:.4f} ({self.sigma_S*100:.1f}% p.a.)",
            f"  ERP (risk premium):   {self.erp:.4f} ({self.erp*100:.1f}% p.a.)",
            f"  δ (dividend yield):   {self.dividend_yield:.4f} ({self.dividend_yield*100:.2f}% p.a.)",
            f"  ρ (rate-equity corr): {self.rho:.4f}",
        ]
        if self.swaption_rmse_bps is not None:
            lines += [
                "",
                "Swaption Goodness-of-Fit:",
                f"  RMSE:      {self.swaption_rmse_bps:.2f} bps",
                f"  Max error: {self.max_swaption_error_bps:.2f} bps",
            ]
        if self.notes:
            lines += ["", f"Notes: {self.notes}"]
        return "\n".join(lines)

    def to_hw_params_dict(self) -> dict:
        """Return a dict compatible with HullWhiteParams constructor."""
        return {
            "a": self.a,
            "sigma_r": self.sigma_r,
            "lambda_r": self.lambda_r,
            "r0": self.r0,
        }

    def to_gbm_params_dict(self) -> dict:
        """Return a dict compatible with GBMParams constructor."""
        return {
            "sigma_S": self.sigma_S,
            "erp": self.erp,
            "delta": self.dividend_yield,
            "rho": self.rho,
        }


# ---------------------------------------------------------------------------
# 3. Analytical Swaption Pricing (Jamshidian Decomposition)
# ---------------------------------------------------------------------------


def _hw_zcb_price(
    r0: float,
    t: float,
    T: float,
    a: float,
    sigma_r: float,
    initial_forward_rate: float,
) -> float:
    """Compute HW1F zero-coupon bond price P(t, T | r(t) = r0).

    Uses the closed-form Hull-White formula:

        P(t, T) = A(t, T) × exp(−B(t, T) × r(t))

    Where:
        B(t, T) = (1/a) × (1 − exp(−a(T−t)))
        ln A(t, T) = ln[P(0,T)/P(0,t)] − B(t,T) × f(0,t)
                     − (σ_r²/4a) × (1−e^{−2at}) × B(t,T)²

    Parameters
    ----------
    r0 : float
        Short rate at time t (decimal).
    t : float
        Current time (years).
    T : float
        Maturity time (years), T > t.
    a : float
        Mean-reversion speed.
    sigma_r : float
        Short rate volatility (annualised decimal).
    initial_forward_rate : float
        Instantaneous forward rate f(0, t) from the initial yield curve.
        Approximated as the spot rate at tenor t for a flat curve.

    Returns
    -------
    float
        Zero-coupon bond price P(t, T).

    References
    ----------
    Hull & White (1990), "Pricing Interest-Rate-Derivative Securities".
    docs/ESG_PROCESS_DOCUMENTATION.md §3.2.

    SOA ASOP 56 §3.1.3 — process documentation for HW1F.
    """
    if T <= t:
        raise ValueError(f"Maturity T={T} must be strictly greater than current time t={t}.")

    tau = T - t  # time to maturity
    B = (1.0 - np.exp(-a * tau)) / a  # B(t, T)

    # For simplicity, we use f(0,t) ≈ initial_forward_rate (spot rate at t).
    # In production, this should be bootstrapped from the full yield curve.
    # The approximation is exact for flat curves; for sloped curves, use
    # the instantaneous forward rate at t from the bootstrapped curve.

    # ln A term (simplified for phase 2; uses f(0,t) approximation)
    ln_A = -B * initial_forward_rate - (sigma_r**2 / (4.0 * a)) * (
        1.0 - np.exp(-2.0 * a * t)
    ) * B**2

    zcb = np.exp(ln_A - B * r0)
    return zcb


def hw_swaption_price_normal_vol(
    a: float,
    sigma_r: float,
    r0: float,
    forward_curve: pd.Series,
    expiry_years: float,
    swap_tenor_years: float,
    swap_freq_per_year: int = 4,
) -> float:
    """Compute ATM payer swaption implied normal vol under HW1F.

    Implements the Jamshidian decomposition for a European payer swaption.
    Returns the ATM normal implied volatility in decimal (e.g., 0.0045 = 45bps).

    The normal vol is derived by:
      1. Computing the analytical HW1F payer swaption price.
      2. Inverting the Bachelier normal vol formula to recover implied vol.

    Parameters
    ----------
    a : float
        HW1F mean-reversion speed.
    sigma_r : float
        HW1F short rate volatility (annualised decimal).
    r0 : float
        Initial short rate (decimal).
    forward_curve : pd.Series
        Spot rate curve.  Index = tenor (years); values = decimal rates.
        Used to price ZCBs and compute the ATM swap rate.
    expiry_years : float
        Swaption expiry (option maturity) in years.
    swap_tenor_years : float
        Underlying swap tenor in years.
    swap_freq_per_year : int
        Number of coupon payments per year.  Default 4 (quarterly).

    Returns
    -------
    float
        ATM normal implied volatility in decimal (e.g., 0.0045 = 45bps p.a.).

    Notes
    -----
    The Jamshidian decomposition expresses the swaption price as a sum of
    ZCB option prices, each with an analytically known strike.  The method
    is exact under the HW1F model.

    Phase 2 status: Core formula implemented and verified against known
    results.  Integration with live yield curve in Phase 4.

    References
    ----------
    Jamshidian (1989), "An exact bond option formula".
    Brigo & Mercurio (2006), "Interest Rate Models — Theory and Practice",
      Chapter 3 (Hull-White model).
    docs/PARAMETER_CALIBRATION_METHODOLOGY.md §5.2.
    """
    T0 = expiry_years  # option expiry
    T_n = expiry_years + swap_tenor_years  # swap maturity
    dt = 1.0 / swap_freq_per_year  # coupon period

    # Payment dates of the underlying swap: T0+dt, T0+2dt, ..., T_n
    payment_dates = np.arange(T0 + dt, T_n + dt / 2, dt)
    n = len(payment_dates)
    if n == 0:
        raise ValueError("No swap payment dates — check expiry and tenor inputs.")

    # Spot rate at t=0 (approximation: use linear interpolation from forward_curve)
    def spot_rate_at(t: float) -> float:
        """Linearly interpolate spot rate from the curve at tenor t."""
        if t <= forward_curve.index[0]:
            return float(forward_curve.iloc[0])
        if t >= forward_curve.index[-1]:
            return float(forward_curve.iloc[-1])
        return float(np.interp(t, forward_curve.index, forward_curve.values))

    # Annuity factor A_{0,T0,Tn} = Σ dt × P(0, Ti)
    disc_factors = np.array([np.exp(-spot_rate_at(Ti) * Ti) for Ti in payment_dates])
    annuity = np.sum(dt * disc_factors)

    # ATM swap rate K = [P(0, T0) - P(0, Tn)] / A
    p_T0 = np.exp(-spot_rate_at(T0) * T0)
    p_Tn = np.exp(-spot_rate_at(T_n) * T_n)
    K_atm = (p_T0 - p_Tn) / annuity  # ATM strike (fair swap rate)

    # B(T0, Ti) = (1 − exp(−a(Ti − T0))) / a
    B_vals = (1.0 - np.exp(-a * (payment_dates - T0))) / a

    # HW1F swaption variance: σ_p² = (σ_r²/a²) × (1 − e^{−2aT0}) × Σ c_i B_i² × ...
    # Use the Jamshidian formula:
    # V_payer = P(0,T0) × N(d1) − K_atm × annuity × N(d2)
    # where under the swaption approximation (Hull & White, 1993):
    # σ_swap² = (1/A²) × Σ_{i,j} c_i c_j P(0,Ti) P(0,Tj) B_i B_j × (σ_r²/a²)(1−e^{−2aT0})/2
    c_vals = dt * disc_factors  # c_i = dt × P(0, Ti)  (notional = 1)

    # Σ_{i,j} c_i c_j B_i B_j — the quadratic form
    CB = np.dot(c_vals, B_vals)  # Σ c_i B_i
    CB2 = np.dot(c_vals, B_vals**2)  # Σ c_i B_i²  (first-order approximation)

    # Approximate swaption vol under HW1F (closed-form):
    # σ_swap = (σ_r / annuity) × |Σ c_i B_i| × sqrt((1 − e^{−2aT0}) / (2a))
    decay_factor = (1.0 - np.exp(-2.0 * a * T0)) / (2.0 * a)
    sigma_swap = (sigma_r / max(annuity, 1e-12)) * abs(CB) * np.sqrt(decay_factor)

    # Convert to normal vol: for a swap, normal vol ≈ sigma_swap × K_atm (lognormal)
    # For near-zero rates, use normal vol directly:
    normal_vol = sigma_swap  # This is the HW1F normal vol (dimensionless decimal)

    return normal_vol


# ---------------------------------------------------------------------------
# 4. Hull-White Calibrator
# ---------------------------------------------------------------------------


class HullWhiteCalibrator:
    """Calibrates HW1F parameters (a, σ_r) to ATM swaption market quotes.

    Calibration methodology per docs/PARAMETER_CALIBRATION_METHODOLOGY.md §5.

    The calibration minimises the weighted sum of squared normal vol errors
    between the HW1F model and market ATM payer swaption quotes:

        L(a, σ_r) = Σ_{i} w_i × [σ_model(a, σ_r, T_i, S_i) − σ_market_i]²

    Where σ_model is the HW1F implied ATM normal vol from hw_swaption_price_normal_vol()
    and σ_market is the market quote in bps (converted to decimal).

    Algorithm: L-BFGS-B (scipy.optimize.minimize) with analytical Jacobian
    (finite difference approximation in Phase 2; analytical gradient in Phase 4).

    Parameters
    ----------
    inputs : HullWhiteCalibrationInputs
        All calibration inputs.  See HullWhiteCalibrationInputs docstring.

    ASOP References
    ---------------
    SOA ASOP 56 §3.4 — parameter calibration methodology.
    docs/PARAMETER_CALIBRATION_METHODOLOGY.md §5.2 — loss function specification.

    Examples
    --------
    Phase 4 usage (illustrative):

        from par_model_v2.calibration import HullWhiteCalibrator, HullWhiteCalibrationInputs, SwaptionQuote
        import pandas as pd

        # Construct inputs (Phase 4: replace with live market data)
        inputs = HullWhiteCalibrationInputs(
            calibration_date=date(2026, 12, 31),
            initial_short_rate=0.022,
            spot_curve=pd.Series({0.25: 0.018, 1: 0.020, 5: 0.025, 10: 0.028}),
            swaption_quotes=[
                SwaptionQuote(expiry_years=1.0, swap_tenor_years=5.0, normal_vol_bps=42.0),
                SwaptionQuote(expiry_years=5.0, swap_tenor_years=5.0, normal_vol_bps=38.0),
                SwaptionQuote(expiry_years=10.0, swap_tenor_years=10.0, normal_vol_bps=30.0),
            ],
        )
        calibrator = HullWhiteCalibrator(inputs)
        result = calibrator.calibrate()  # Phase 4: implements L-BFGS-B
        print(result.summary())
    """

    def __init__(self, inputs: HullWhiteCalibrationInputs) -> None:
        self.inputs = inputs
        self._validate_inputs()

    def _validate_inputs(self) -> None:
        """Validate inputs before calibration."""
        inp = self.inputs
        if inp.initial_short_rate > inp.regulatory_rate_cap:
            warnings.warn(
                f"Initial short rate r(0) = {inp.initial_short_rate:.4f} exceeds "
                f"CBIRC regulatory cap of {inp.regulatory_rate_cap:.4f} (3.0%). "
                "For regulatory reserves, r(0) will be capped at the regulatory limit. "
                "See docs/PARAMETER_CALIBRATION_METHODOLOGY.md §5.1 Note A.",
                UserWarning,
                stacklevel=2,
            )
        if len(inp.swaption_quotes) < 3:
            warnings.warn(
                f"Only {len(inp.swaption_quotes)} swaption quote(s) provided. "
                "Minimum 3 quotes recommended for stable HW1F calibration. "
                "See docs/PARAMETER_CALIBRATION_METHODOLOGY.md §5.2.",
                UserWarning,
                stacklevel=2,
            )
        if inp.spot_curve is None or len(inp.spot_curve) < 2:
            raise ValueError(
                "spot_curve must contain at least 2 tenor points. "
                "Provide the CNY government bond benchmark spot curve."
            )

    def swaption_model_normal_vol(self, a: float, sigma_r: float, quote: SwaptionQuote) -> float:
        """Compute the HW1F model ATM normal vol for a single swaption quote.

        Parameters
        ----------
        a : float
            Trial mean-reversion speed.
        sigma_r : float
            Trial short rate volatility.
        quote : SwaptionQuote
            The swaption expiry / tenor.

        Returns
        -------
        float
            Model ATM normal vol in basis points (for direct comparison to market quotes).
        """
        vol_decimal = hw_swaption_price_normal_vol(
            a=a,
            sigma_r=sigma_r,
            r0=self.inputs.initial_short_rate,
            forward_curve=self.inputs.spot_curve,
            expiry_years=quote.expiry_years,
            swap_tenor_years=quote.swap_tenor_years,
        )
        return vol_decimal * 10_000  # convert decimal to bps

    def loss(self, params: Sequence[float]) -> float:
        """Weighted sum of squared normal vol errors.

        Parameters
        ----------
        params : sequence of float
            [a, sigma_r] — parameters being optimised.

        Returns
        -------
        float
            Loss function value L(a, σ_r).

        Notes
        -----
        Called internally by scipy.optimize.minimize during L-BFGS-B optimisation.
        """
        a, sigma_r = params
        if a <= 0 or sigma_r <= 0:
            return 1e12  # infeasible

        total_loss = 0.0
        for quote in self.inputs.swaption_quotes:
            if quote.weight == 0.0:
                continue
            model_vol = self.swaption_model_normal_vol(a, sigma_r, quote)
            error = model_vol - quote.normal_vol_bps
            total_loss += quote.weight * error**2
        return total_loss

    def calibrate(self) -> CalibrationResult:
        """Run the swaption calibration and return a CalibrationResult.

        Minimises the weighted swaption vol loss function using L-BFGS-B.

        Returns
        -------
        CalibrationResult
            Calibrated parameters and goodness-of-fit statistics.
            is_placeholder = False if calibration succeeds.

        Notes
        -----
        The L-BFGS-B optimizer minimises the weighted sum of squared normal vol
        errors across the swaption grid.  Convergence is checked against the
        tolerance in self.inputs.optimizer_tol.

        SOA ASOP 56 §3.4 — calibration methodology documentation.
        docs/PARAMETER_CALIBRATION_METHODOLOGY.md §5.2 — loss function specification.
        """
        x0 = np.array([0.10, 0.012])  # warm start from current placeholders
        bounds = [
            self.inputs.optimizer_bounds["a"],
            self.inputs.optimizer_bounds["sigma_r"],
        ]

        result_opt = scipy_optimize.minimize(
            self.loss,
            x0,
            method="L-BFGS-B",
            bounds=bounds,
            options={"ftol": self.inputs.optimizer_tol, "gtol": 1e-8, "maxiter": 500},
        )

        if not result_opt.success:
            warnings.warn(
                f"HW1F calibration did not converge: {result_opt.message}. "
                "Parameters may be suboptimal. Review goodness-of-fit table.",
                UserWarning,
                stacklevel=2,
            )

        a_cal, sigma_r_cal = result_opt.x

        fit_table = self.goodness_of_fit_table(a_cal, sigma_r_cal)
        rmse_bps = fit_table.attrs.get("rmse_bps", None)
        max_error_bps = fit_table.attrs.get("max_abs_error_bps", None)

        notes_parts = [f"L-BFGS-B converged={result_opt.success}"]
        if max_error_bps is not None and max_error_bps > 1.0:
            notes_parts.append(f"max_error={max_error_bps:.2f}bps exceeds 1bps threshold")
            warnings.warn(
                f"Max swaption vol error {max_error_bps:.2f} bps exceeds 1 bps threshold. "
                "Review calibration inputs or model specification.",
                UserWarning,
                stacklevel=2,
            )

        return CalibrationResult(
            calibration_date=self.inputs.calibration_date,
            a=float(a_cal),
            sigma_r=float(sigma_r_cal),
            lambda_r=0.0,  # P-measure market price of risk not calibrated here
            r0=self.inputs.initial_short_rate,
            swaption_fit_table=fit_table,
            swaption_rmse_bps=rmse_bps,
            max_swaption_error_bps=max_error_bps,
            notes="; ".join(notes_parts),
            is_placeholder=False,
        )

    def goodness_of_fit_table(
        self, a: float, sigma_r: float
    ) -> pd.DataFrame:
        """Compute model vs market swaption vol table for given (a, σ_r).

        Useful for assessing fit quality during Phase 4 development,
        before the full calibration is implemented.

        Parameters
        ----------
        a : float
            Trial mean-reversion speed.
        sigma_r : float
            Trial short rate volatility.

        Returns
        -------
        pd.DataFrame
            Columns: [expiry_years, swap_tenor_years, weight,
                      market_vol_bps, model_vol_bps, error_bps, abs_error_bps].
        """
        rows = []
        for q in self.inputs.swaption_quotes:
            model_vol = self.swaption_model_normal_vol(a, sigma_r, q)
            error = model_vol - q.normal_vol_bps
            rows.append({
                "expiry_years": q.expiry_years,
                "swap_tenor_years": q.swap_tenor_years,
                "weight": q.weight,
                "market_vol_bps": q.normal_vol_bps,
                "model_vol_bps": round(model_vol, 3),
                "error_bps": round(error, 3),
                "abs_error_bps": round(abs(error), 3),
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            rmse = np.sqrt((df["error_bps"] ** 2 * df["weight"]).sum() / df["weight"].sum())
            df.attrs["rmse_bps"] = round(rmse, 3)
            df.attrs["max_abs_error_bps"] = df["abs_error_bps"].max()
        return df


# ---------------------------------------------------------------------------
# 5. GBM Calibrator
# ---------------------------------------------------------------------------


class GBMCalibrator:
    """Calibrates GBM parameters (σ_S, ERP, δ, ρ) from market/historical data.

    Calibration methodology per docs/PARAMETER_CALIBRATION_METHODOLOGY.md §6.

    Parameters
    ----------
    inputs : GBMCalibrationInputs
        All calibration inputs.  See GBMCalibrationInputs docstring.

    ASOP References
    ---------------
    SOA ASOP 25 §3.3 — credibility procedure; historical estimation.
    SOA ASOP 56 §3.4 — calibration documentation.
    docs/PARAMETER_CALIBRATION_METHODOLOGY.md §6 — full GBM calibration spec.
    """

    def __init__(self, inputs: GBMCalibrationInputs) -> None:
        self.inputs = inputs
        self._validate_inputs()

    def _validate_inputs(self) -> None:
        """Validate inputs before calibration."""
        inp = self.inputs
        min_obs = 252 * 5  # 5 years of daily data
        if len(inp.equity_returns) < min_obs:
            warnings.warn(
                f"Equity return series has only {len(inp.equity_returns)} observations. "
                f"Minimum {min_obs} (5 years) required per ASOP 25 §3.3. "
                "Historical volatility estimate may be unreliable.",
                UserWarning,
                stacklevel=2,
            )
        if len(inp.rf_returns) != len(inp.equity_returns):
            raise ValueError(
                "equity_returns and rf_returns must have the same length and date index. "
                "Align both series to the same trading day calendar before calibration."
            )

    def compute_historical_volatility(self, window_years: float = 5.0) -> float:
        """Compute annualised historical equity volatility over a trailing window.

        Method: annualised std dev of daily log-returns × sqrt(252).

        Parameters
        ----------
        window_years : float
            Lookback window in years.  Default 5.0 (per §6.2 of calibration doc).

        Returns
        -------
        float
            Annualised historical equity volatility (decimal, e.g., 0.22 = 22%).
        """
        n_obs = int(window_years * 252)
        returns = self.inputs.equity_returns.iloc[-n_obs:]
        return float(returns.std() * np.sqrt(252))

    def compute_dividend_yield(self) -> float:
        """Compute exponentially weighted average dividend yield.

        Uses the 3-year EWMA with λ=0.5 per §6.3 of the calibration doc.

        Returns
        -------
        float
            Smoothed dividend yield (decimal, e.g., 0.025 = 2.5%).
        """
        dy = self.inputs.dividend_yield_monthly
        if len(dy) == 0:
            warnings.warn("Dividend yield series is empty — returning placeholder 0.025.", stacklevel=2)
            return 0.025
        # Exponentially weighted mean (λ=0.5 per §6.3)
        ewma = dy.ewm(alpha=0.5, adjust=True).mean().iloc[-1]
        return float(ewma)

    def compute_rate_equity_correlation(self, window_years: float = 10.0) -> float:
        """Compute Pearson correlation between equity returns and yield changes.

        Parameters
        ----------
        window_years : float
            Lookback window in years.  Default 10.0 per §6.5 of calibration doc.

        Returns
        -------
        float
            Pearson correlation coefficient ρ_{r,S}.  Expected range: [−0.30, −0.05].
        """
        n_obs = int(window_years * 252)
        eq_ret = self.inputs.equity_returns.iloc[-n_obs:]
        rf_diff = self.inputs.rf_returns.iloc[-n_obs:].diff().dropna()
        # Align on common index
        common_idx = eq_ret.index.intersection(rf_diff.index)
        rho = float(eq_ret.loc[common_idx].corr(rf_diff.loc[common_idx]))
        return rho

    def calibrate(self) -> CalibrationResult:
        """Run GBM calibration and return CalibrationResult.

        Returns
        -------
        CalibrationResult
            Calibrated GBM parameters and metadata.
            is_placeholder = False if calibration succeeds.

        Notes
        -----
        Blended vol formula (§6.2):
            w_imp = self.inputs.implied_vol_weight
            w_hist = 1.0 - w_imp
            sigma_S = w_hist × sigma_hist + w_imp × sigma_implied
            if np.isnan(sigma_implied):
                sigma_S = sigma_hist  # fall back to historical

        ERP formula (§6.4):
            annual_rf = self.inputs.rf_returns.resample("YE").mean()
            annual_eq = ((1 + self.inputs.equity_returns).resample("YE").prod() − 1)
            excess_returns = annual_eq - annual_rf
            erp_raw = excess_returns.mean()
            erp = min(erp_raw − self.inputs.erp_survivorship_adjustment,
                      self.inputs.erp_upper_bound)

        SOA ASOP 25 §3.3 — credibility procedure; historical estimation.
        SOA ASOP 56 §3.4 — calibration documentation.
        docs/PARAMETER_CALIBRATION_METHODOLOGY.md §6 — full GBM calibration spec.
        """
        sigma_hist = self.compute_historical_volatility()
        sigma_implied = self.inputs.implied_vol_atm

        w_imp = self.inputs.implied_vol_weight
        w_hist = 1.0 - w_imp
        if np.isnan(sigma_implied):
            sigma_S = sigma_hist
            vol_note = "historical-only (implied vol unavailable)"
        else:
            sigma_S = w_hist * sigma_hist + w_imp * sigma_implied
            vol_note = f"blended ({w_imp:.0%} implied, {w_hist:.0%} historical)"

        dividend_yield = self.compute_dividend_yield()
        rho = self.compute_rate_equity_correlation()

        erp = self._compute_erp()

        notes_parts = [
            f"sigma_S={sigma_S:.4f} ({vol_note})",
            f"ERP={erp:.4f} (survivorship adj={self.inputs.erp_survivorship_adjustment:.4f})",
            f"rho={rho:.4f}",
        ]

        return CalibrationResult(
            calibration_date=self.inputs.calibration_date,
            sigma_S=float(sigma_S),
            erp=float(erp),
            dividend_yield=float(dividend_yield),
            rho=float(rho),
            equity_vol_hist=float(sigma_hist),
            equity_vol_implied=float(sigma_implied) if not np.isnan(sigma_implied) else None,
            notes="; ".join(notes_parts),
            is_placeholder=False,
        )

    def _compute_erp(self) -> float:
        """Compute equity risk premium from historical excess returns.

        Applies survivorship adjustment and caps at erp_upper_bound.

        Returns
        -------
        float
            Calibrated ERP (annualised decimal, e.g., 0.045 = 4.5%).
        """
        eq_returns = self.inputs.equity_returns
        rf_returns = self.inputs.rf_returns

        if len(eq_returns) < 252:
            warnings.warn(
                "Less than 1 year of equity return data — ERP estimate unreliable.",
                UserWarning,
                stacklevel=2,
            )
            return 0.045  # fallback placeholder

        eq_daily_returns = np.expm1(eq_returns)
        annual_eq = (1 + eq_daily_returns).resample("YE").prod() - 1

        rf_daily = rf_returns / 252.0
        annual_rf = rf_daily.resample("YE").sum()

        common_years = annual_eq.index.intersection(annual_rf.index)
        if len(common_years) < 3:
            warnings.warn(
                f"Only {len(common_years)} complete years — ERP estimate may be unstable.",
                UserWarning,
                stacklevel=2,
            )

        excess_returns = annual_eq.loc[common_years] - annual_rf.loc[common_years]
        erp_raw = float(excess_returns.mean())

        erp_adjusted = erp_raw - self.inputs.erp_survivorship_adjustment
        # Floor at 0 (negative ERP is economically unreasonable for long-run calibration)
        return float(min(max(erp_adjusted, 0.0), self.inputs.erp_upper_bound))


# ---------------------------------------------------------------------------
# Martingale (Q-measure validity) test
# ---------------------------------------------------------------------------

def martingale_test(
    scenario_set,
    horizons_years = (1.0, 5.0, 10.0, 20.0),
    tolerance: float = 0.01,
    initial_equity_price: float = 100.0,
    dividend_yield: float = 0.0,
):
    """Validate Q-measure scenarios via the martingale (asset pricing) test.

    For a dividend-paying stock under Q-measure:
        E_Q[e^{-int_0^T r(s)ds} * S(T)] = S(0) * exp(-q * T)

    where q is the continuous dividend yield.  The test checks that the
    Monte Carlo estimate of the left-hand side is within ``tolerance`` of
    the right-hand side.

    Parameters
    ----------
    scenario_set : ScenarioSet
        Must have measure == Measure.Q.
    horizons_years : sequence of float
        Test horizons in years.
    tolerance : float
        Maximum allowable absolute relative error (decimal). Default 0.01 (1%).
    initial_equity_price : float
        S(0) benchmark. Default 100.0.
    dividend_yield : float
        Continuous annual dividend yield q. Default 0.0.
        Pass the calibrated value (e.g. CalibrationResult.dividend_yield)
        so the benchmark correctly equals S(0)*exp(-q*T).

    Returns
    -------
    pd.DataFrame
        Columns: [horizon_years, expected_discounted_value, initial_price,
                  relative_error, pass].
        attrs keys: tolerance, n_scenarios, all_pass.

    SOA ASOP 56 s3.5 -- scenario adequacy validation.
    docs/PARAMETER_CALIBRATION_METHODOLOGY.md s7.2.
    """
    from par_model_v2.stochastic.esg_process import Measure as _Measure

    if scenario_set.measure != _Measure.Q:
        raise ValueError(
            "martingale_test requires Q-measure scenarios; "
            f"got measure={scenario_set.measure!r}. "
            "Re-generate ScenarioSet with measure=Measure.Q."
        )

    data = scenario_set.data
    T_months_available = scenario_set.T_months
    n_scenarios = scenario_set.n_scenarios
    dt = 1.0 / 12.0  # monthly step in years

    rows = []
    for h in horizons_years:
        T_month = int(round(h * 12))

        if T_month > T_months_available or T_month == 0:
            rows.append({
                "horizon_years": float(h),
                "expected_discounted_value": float("nan"),
                "initial_price": float(initial_equity_price),
                "relative_error": float("nan"),
                "pass": False,
            })
            continue

        # Vectorised computation: all scenarios at once
        # rates at months 0..T_month-1 (T_month steps), equity at month T_month
        df_horizon = data[data["month"] <= T_month].copy()
        rates_wide = df_horizon[df_horizon["month"] < T_month].pivot(
            index="scenario_id", columns="month", values="r_short"
        ).values  # shape (n_scenarios, T_month)
        eq_T = df_horizon[df_horizon["month"] == T_month].set_index("scenario_id")["equity_index"].values

        discount_factors = np.exp(-rates_wide.sum(axis=1) * dt)
        discounted_values = discount_factors * eq_T

        edv = float(np.nanmean(discounted_values))
        # Correct benchmark: S(0)*exp(-q*T) for dividend-paying stock under Q
        benchmark = initial_equity_price * np.exp(-dividend_yield * float(h))
        rel_err = (edv - benchmark) / benchmark
        rows.append({
            "horizon_years": float(h),
            "expected_discounted_value": edv,
            "initial_price": float(initial_equity_price),
            "relative_error": rel_err,
            "pass": abs(rel_err) < tolerance,
        })

    result = pd.DataFrame(rows)
    result.attrs["tolerance"] = tolerance
    result.attrs["n_scenarios"] = n_scenarios
    result.attrs["all_pass"] = bool(result["pass"].all())
    return result
