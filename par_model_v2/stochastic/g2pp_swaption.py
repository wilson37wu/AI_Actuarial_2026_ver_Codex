"""
G2++ European swaption pricing and swaption-surface calibration.

Phase 20 Task 2 promotes the enhanced two-factor Gaussian rate driver from a
plausibility-gated prototype (Task 1) into a calibratable component.  It adds:

  * an exact analytic European swaption pricer for the G2++ model using the
    Brigo-Mercurio (2006, sec. 4.2.5) one-dimensional Gaussian-quadrature
    decomposition of the swaption into an option on a coupon bond;
  * Black (lognormal) ATM swaption pricing / implied-vol inversion used to build
    target prices from a quoted volatility grid;
  * a derivative-free (Nelder-Mead) calibration of (a, b, sigma, eta, rho) to an
    educational-proxy swaption volatility surface; and
  * a G-SWPN calibration-quality gate (parity, fit RMSE, parameter validity,
    positivity, curve-identity preservation).

The implementation is additive: it imports the Task-1 ``EnhancedG2PlusRateProcess``
for the affine A(t,T)/B(t,T) building blocks and never mutates existing modules.

Production use restriction: the proxy swaption surface in this module is an
EDUCATIONAL placeholder.  Calibrated parameters must not be used for production
pricing, capital, or external disclosure until they are re-calibrated to an
observed, validated market swaption surface and an independent reviewer signs off
the assumption set (SOA ASOP 56 s.3.5; IA TAS M s.3.6).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from par_model_v2.stochastic.esg_process import G2PlusParams, RiskFreeCurve
from par_model_v2.stochastic.g2pp_rate import EnhancedG2PlusRateProcess

_SQRT_2PI = math.sqrt(2.0 * math.pi)
_SQRT_2 = math.sqrt(2.0)


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(float(x) / _SQRT_2))


_erf_vec = np.vectorize(math.erf, otypes=[float])


def _norm_cdf_arr(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + _erf_vec(np.asarray(z, dtype=float) / _SQRT_2))


# ---------------------------------------------------------------------------
# Swap schedule, par rate, and Black (lognormal) ATM swaption pricing
# ---------------------------------------------------------------------------


def swap_schedule(expiry: float, tenor: float, frequency: int = 2) -> Tuple[List[float], List[float]]:
    """Return (payment_times, accruals) for a unit-notional fixed leg.

    ``frequency`` is the number of fixed payments per year (2 == semi-annual).
    Payment times are measured from valuation (t=0) in years.
    """
    expiry = float(expiry)
    tenor = float(tenor)
    if expiry <= 0.0:
        raise ValueError("expiry must be positive")
    if tenor <= 0.0:
        raise ValueError("tenor must be positive")
    if frequency <= 0:
        raise ValueError("frequency must be a positive integer")
    n = int(round(tenor * frequency))
    if n < 1:
        raise ValueError("tenor * frequency must round to at least one payment")
    tau = 1.0 / float(frequency)
    times = [expiry + i * tau for i in range(1, n + 1)]
    accruals = [tau] * n
    return times, accruals


def par_swap_rate(
    curve: RiskFreeCurve, expiry: float, times: Sequence[float], accruals: Sequence[float]
) -> Tuple[float, float]:
    """Return (forward par swap rate, annuity) for the forward-starting swap."""
    annuity = sum(a * curve.discount_factor(t) for a, t in zip(accruals, times))
    if annuity <= 0.0:
        raise ValueError("annuity must be positive")
    p_start = curve.discount_factor(expiry)
    p_end = curve.discount_factor(times[-1])
    return (p_start - p_end) / annuity, annuity


def black_swaption_price(
    annuity: float,
    forward: float,
    strike: float,
    vol: float,
    expiry: float,
    option_type: str = "payer",
) -> float:
    """Black-76 lognormal swaption price (unit notional)."""
    option_type = option_type.lower()
    if option_type not in {"payer", "receiver"}:
        raise ValueError("option_type must be 'payer' or 'receiver'")
    if vol <= 0.0 or expiry <= 0.0:
        intrinsic = forward - strike if option_type == "payer" else strike - forward
        return float(annuity * max(intrinsic, 0.0))
    std = vol * math.sqrt(expiry)
    d1 = (math.log(forward / strike) + 0.5 * std * std) / std
    d2 = d1 - std
    if option_type == "payer":
        return float(annuity * (forward * _norm_cdf(d1) - strike * _norm_cdf(d2)))
    return float(annuity * (strike * _norm_cdf(-d2) - forward * _norm_cdf(-d1)))


def black_implied_vol(
    price: float,
    annuity: float,
    forward: float,
    strike: float,
    expiry: float,
    option_type: str = "payer",
    tol: float = 1e-10,
    max_iter: int = 100,
) -> float:
    """Invert Black-76 for the lognormal implied volatility via bisection."""
    if price <= 0.0:
        return 0.0
    lo, hi = 1e-6, 5.0
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        val = black_swaption_price(annuity, forward, strike, mid, expiry, option_type)
        if abs(val - price) < tol:
            return float(mid)
        if val > price:
            hi = mid
        else:
            lo = mid
    return float(0.5 * (lo + hi))


# ---------------------------------------------------------------------------
# G2++ analytic European swaption pricer (Brigo-Mercurio 2006, sec. 4.2.5)
# ---------------------------------------------------------------------------


def _forward_measure_drift(speed_own: float, speed_other: float, vol_own: float, vol_other: float, rho: float, T: float) -> float:
    """M_x^T(0,T) drift correction under the T-forward measure (Brigo-Mercurio 4.30)."""
    a = speed_own
    b = speed_other
    s = vol_own
    e = vol_other
    term1 = (s * s / (a * a) + rho * s * e / (a * b)) * (1.0 - math.exp(-a * T))
    term2 = (s * s / (2.0 * a * a)) * (1.0 - math.exp(-2.0 * a * T))
    term3 = (rho * s * e / (b * (a + b))) * (1.0 - math.exp(-(a + b) * T))
    return term1 - term2 - term3


@dataclass(frozen=True)
class _GaussHermite:
    nodes: np.ndarray
    weights: np.ndarray

    @classmethod
    def build(cls, n: int) -> "_GaussHermite":
        nodes, weights = np.polynomial.hermite.hermgauss(int(n))
        return cls(nodes=nodes, weights=weights)


def g2pp_swaption_price(
    process: EnhancedG2PlusRateProcess,
    expiry: float,
    times: Sequence[float],
    accruals: Sequence[float],
    strike: float,
    option_type: str = "payer",
    quadrature: Optional[_GaussHermite] = None,
    n_quad: int = 64,
) -> float:
    """Analytic time-zero G2++ European swaption price (unit notional).

    Vectorised across Gauss-Hermite quadrature nodes for speed.  Prices the
    swaption as an option on the fixed-leg coupon bond via the Brigo-Mercurio
    one-dimensional decomposition.
    """
    option_type = option_type.lower()
    if option_type not in {"payer", "receiver"}:
        raise ValueError("option_type must be 'payer' or 'receiver'")
    T = float(expiry)
    if T <= 0.0:
        raise ValueError("expiry must be positive")

    p = process.params
    a = float(p.mean_reversion_x)
    b = float(p.mean_reversion_y)
    sigma = float(p.vol_x)
    eta = float(p.vol_y)
    rho = float(p.factor_correlation)
    curve = process.initial_curve

    sx = sigma * math.sqrt((1.0 - math.exp(-2.0 * a * T)) / (2.0 * a))
    sy = eta * math.sqrt((1.0 - math.exp(-2.0 * b * T)) / (2.0 * b))
    rhoxy = (rho * sigma * eta) / ((a + b) * sx * sy) * (1.0 - math.exp(-(a + b) * T))
    rhoxy = max(min(rhoxy, 0.999999), -0.999999)

    mux = -_forward_measure_drift(a, b, sigma, eta, rho, T)
    muy = -_forward_measure_drift(b, a, eta, sigma, rho, T)

    times = list(times)
    accruals = list(accruals)
    n = len(times)
    cflow = np.array([strike * accruals[i] for i in range(n)], dtype=float)
    cflow[-1] += 1.0

    a_coef = np.array([process.zcb_price(0.0, 0.0, T, ti) for ti in times], dtype=float)
    ba = np.array([EnhancedG2PlusRateProcess.factor_loading(a, T, ti) for ti in times], dtype=float)
    bb = np.array([EnhancedG2PlusRateProcess.factor_loading(b, T, ti) for ti in times], dtype=float)

    rho_c = math.sqrt(max(1.0 - rhoxy * rhoxy, 1e-16))

    quad = quadrature if quadrature is not None else _GaussHermite.build(n_quad)
    u = quad.nodes
    w = quad.weights
    x = mux + _SQRT_2 * sx * u  # (Q,)

    base = cflow * a_coef  # (n,)
    lam = base[None, :] * np.exp(-np.outer(x, ba))  # (Q,n) == c_i A_i exp(-Ba_i x)

    # Solve y_bar(x) per node: sum_i lam[q,i] * exp(-bb_i y_q) = 1 (monotone decreasing).
    y = np.zeros_like(x)
    for _ in range(50):
        e = lam * np.exp(-np.outer(y, bb))  # (Q,n)
        val = e.sum(axis=1) - 1.0
        der = -(e * bb[None, :]).sum(axis=1)
        der = np.where(np.abs(der) < 1e-300, -1e-300, der)
        step = np.clip(val / der, -5.0, 5.0)
        y = y - step
        if np.max(np.abs(val)) < 1e-13:
            break

    h1 = (y - muy) / (sy * rho_c) - rhoxy * (x - mux) / (sx * rho_c)  # (Q,)
    kappa = -bb[None, :] * (
        muy - 0.5 * (1.0 - rhoxy * rhoxy) * sy * sy * bb[None, :] + rhoxy * sy * (x[:, None] - mux) / sx
    )  # (Q,n)
    h2 = h1[:, None] + bb[None, :] * sy * rho_c  # (Q,n)

    weighted = lam * np.exp(kappa)  # (Q,n)
    if option_type == "payer":
        inner = (weighted * _norm_cdf_arr(-h2)).sum(axis=1)  # (Q,)
        bracket = _norm_cdf_arr(-h1) - inner
    else:
        inner = (weighted * _norm_cdf_arr(h2)).sum(axis=1)
        bracket = inner - _norm_cdf_arr(h1)

    total = float(np.dot(w, bracket))
    price = curve.discount_factor(T) * total / math.sqrt(math.pi)
    return float(max(price, 0.0))


# ---------------------------------------------------------------------------
# Educational-proxy swaption volatility grid
# ---------------------------------------------------------------------------


def educational_proxy_curve() -> RiskFreeCurve:
    """A smooth, upward-sloping educational risk-free curve for calibration."""
    return RiskFreeCurve(
        tenors_years=(0.0, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0),
        zero_rates=(0.0180, 0.0195, 0.0210, 0.0222, 0.0240, 0.0252, 0.0262, 0.0275, 0.0280),
        currency="CNY",
        market="CN",
        curve_id="CNY-G2PP-SWPN-EDU-20260606",
        source_id="EDU-G2PP-SWPN-PROXY",
    )


def educational_proxy_vol_grid() -> Dict[str, Any]:
    """Return an educational ATM lognormal swaption vol grid (expiry x tenor).

    The surface is a deterministic, smoothly-shaped placeholder: vols decline with
    option expiry and underlying tenor and carry a mild short-expiry hump, which is
    representative of a typical ATM swaption cube without using any proprietary data.
    """
    expiries = [1.0, 2.0, 3.0, 5.0, 7.0, 10.0]
    tenors = [1.0, 2.0, 5.0, 10.0]
    quotes: List[Dict[str, float]] = []
    ln10 = math.log1p(10.0)
    for T in expiries:
        for tenor in tenors:
            base = 0.250
            expiry_decay = 0.050 * (math.log1p(T) / ln10)
            tenor_decay = 0.035 * (math.log1p(tenor) / ln10)
            hump = 0.012 * math.exp(-((T - 1.0) ** 2) / 6.0)
            vol = base - expiry_decay - tenor_decay + hump
            vol = max(vol, 0.120)
            quotes.append({"expiry": T, "tenor": tenor, "black_vol": round(vol, 4)})
    return {
        "frequency": 2,
        "expiries": expiries,
        "tenors": tenors,
        "quotes": quotes,
        "source": "EDUCATIONAL_PROXY",
        "disclaimer": "Synthetic placeholder surface - not market data; do not use in production.",
    }


# ---------------------------------------------------------------------------
# Derivative-free (Nelder-Mead) calibration
# ---------------------------------------------------------------------------


def _nelder_mead(
    objective: Callable[[np.ndarray], float],
    x0: np.ndarray,
    max_iter: int = 1200,
    tol: float = 1e-9,
) -> Tuple[np.ndarray, float, int]:
    """Minimal pure-numpy Nelder-Mead simplex optimiser."""
    n = len(x0)
    alpha, gamma, rho_c, sigma_c = 1.0, 2.0, 0.5, 0.5
    simplex = [np.array(x0, dtype=float)]
    for i in range(n):
        pt = np.array(x0, dtype=float)
        pt[i] += 0.5 if pt[i] == 0.0 else 0.10 * abs(pt[i]) + 0.05
        simplex.append(pt)
    fvals = [objective(pt) for pt in simplex]
    evals = len(simplex)
    for _ in range(max_iter):
        order = np.argsort(fvals)
        simplex = [simplex[i] for i in order]
        fvals = [fvals[i] for i in order]
        if abs(fvals[-1] - fvals[0]) <= tol * (abs(fvals[0]) + tol):
            break
        centroid = np.mean(simplex[:-1], axis=0)
        xr = centroid + alpha * (centroid - simplex[-1])
        fr = objective(xr)
        evals += 1
        if fr < fvals[0]:
            xe = centroid + gamma * (xr - centroid)
            fe = objective(xe)
            evals += 1
            if fe < fr:
                simplex[-1], fvals[-1] = xe, fe
            else:
                simplex[-1], fvals[-1] = xr, fr
        elif fr < fvals[-2]:
            simplex[-1], fvals[-1] = xr, fr
        else:
            xc = centroid + rho_c * (simplex[-1] - centroid)
            fc = objective(xc)
            evals += 1
            if fc < fvals[-1]:
                simplex[-1], fvals[-1] = xc, fc
            else:
                best = simplex[0]
                simplex = [best] + [best + sigma_c * (pt - best) for pt in simplex[1:]]
                fvals = [fvals[0]] + [objective(pt) for pt in simplex[1:]]
                evals += n
    order = np.argsort(fvals)
    return simplex[order[0]], float(fvals[order[0]]), evals


_A_FLOOR = 0.010
_D_FLOOR = 0.020
_RHO_CAP = 0.95


def _params_from_vector(v: np.ndarray) -> G2PlusParams:
    """Map an unconstrained vector to valid, well-separated G2++ params.

    a = _A_FLOOR + e^{v0} > 0; b = a + _D_FLOOR + e^{v1} > a (identified ordering);
    sigma, eta = e^{v2}, e^{v3} > 0; rho = _RHO_CAP * tanh(v4), |rho| < _RHO_CAP."""
    a = _A_FLOOR + math.exp(v[0])
    d = _D_FLOOR + math.exp(v[1])
    b = a + d
    sigma = math.exp(v[2])
    eta = math.exp(v[3])
    rho = _RHO_CAP * math.tanh(v[4])
    return G2PlusParams(
        mean_reversion_x=a,
        mean_reversion_y=b,
        vol_x=sigma,
        vol_y=eta,
        factor_correlation=rho,
        short_rate_floor=None,
        short_rate_ceiling=None,
    )


def _vector_from_params(p: G2PlusParams) -> np.ndarray:
    a = max(p.mean_reversion_x, _A_FLOOR + 1e-6)
    b = max(p.mean_reversion_y, a + _D_FLOOR + 1e-6)
    d = b - a
    rho = max(min(p.factor_correlation / _RHO_CAP, 0.999), -0.999)
    return np.array(
        [
            math.log(max(a - _A_FLOOR, 1e-6)),
            math.log(max(d - _D_FLOOR, 1e-6)),
            math.log(p.vol_x),
            math.log(p.vol_y),
            math.atanh(rho),
        ],
        dtype=float,
    )


@dataclass
class SwaptionCalibrationResult:
    params: G2PlusParams
    rmse_relative_price: float
    rmse_vol_bps: float
    max_abs_vol_bps: float
    objective_value: float
    n_quotes: int
    iterations: int
    per_quote: List[Dict[str, float]]
    converged: bool
    initial_params: Dict[str, float]

    def params_dict(self) -> Dict[str, float]:
        p = self.params
        return {
            "mean_reversion_x": p.mean_reversion_x,
            "mean_reversion_y": p.mean_reversion_y,
            "vol_x": p.vol_x,
            "vol_y": p.vol_y,
            "factor_correlation": p.factor_correlation,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "params": self.params_dict(),
            "initial_params": self.initial_params,
            "rmse_relative_price": self.rmse_relative_price,
            "rmse_vol_bps": self.rmse_vol_bps,
            "max_abs_vol_bps": self.max_abs_vol_bps,
            "objective_value": self.objective_value,
            "n_quotes": self.n_quotes,
            "iterations": self.iterations,
            "converged": self.converged,
            "per_quote": self.per_quote,
        }


def calibrate_g2pp_to_swaptions(
    curve: Optional[RiskFreeCurve] = None,
    grid: Optional[Dict[str, Any]] = None,
    initial_params: Optional[G2PlusParams] = None,
    n_quad: int = 36,
    max_iter: int = 600,
) -> SwaptionCalibrationResult:
    """Calibrate G2++ (a, b, sigma, eta, rho) to an ATM swaption vol grid."""
    curve = curve if curve is not None else educational_proxy_curve()
    grid = grid if grid is not None else educational_proxy_vol_grid()
    frequency = int(grid.get("frequency", 2))
    quotes = grid["quotes"]
    quad = _GaussHermite.build(n_quad)

    # Pre-compute schedules, ATM strikes, annuities, and target prices.
    targets = []
    for q in quotes:
        T = float(q["expiry"])
        tenor = float(q["tenor"])
        vol = float(q["black_vol"])
        times, accruals = swap_schedule(T, tenor, frequency)
        fwd, annuity = par_swap_rate(curve, T, times, accruals)
        target_price = black_swaption_price(annuity, fwd, fwd, vol, T, "payer")
        targets.append(
            {
                "expiry": T,
                "tenor": tenor,
                "times": times,
                "accruals": accruals,
                "forward": fwd,
                "annuity": annuity,
                "market_vol": vol,
                "target_price": target_price,
            }
        )

    if initial_params is not None:
        seeds = [initial_params]
    else:
        seeds = [
            G2PlusParams(mean_reversion_x=0.10, mean_reversion_y=0.50, vol_x=0.010,
                         vol_y=0.007, factor_correlation=-0.60,
                         short_rate_floor=None, short_rate_ceiling=None),
        ]
    init = seeds[0]
    x0 = _vector_from_params(init)

    def objective(v: np.ndarray) -> float:
        try:
            params = _params_from_vector(v)
        except (ValueError, OverflowError):
            return 1e6
        process = EnhancedG2PlusRateProcess(params, curve)
        sse = 0.0
        for t in targets:
            try:
                model = g2pp_swaption_price(
                    process, t["expiry"], t["times"], t["accruals"], t["forward"], "payer", quadrature=quad
                )
            except (ValueError, OverflowError, ZeroDivisionError):
                return 1e6
            denom = t["target_price"] if t["target_price"] > 1e-10 else 1e-10
            rel = (model - t["target_price"]) / denom
            sse += rel * rel
        return sse / len(targets)

    best_v, best_obj, iters = _nelder_mead(objective, x0, max_iter=max_iter)
    for seed in seeds[1:]:
        cand_v, cand_obj, cand_iters = _nelder_mead(
            objective, _vector_from_params(seed), max_iter=max_iter)
        iters += cand_iters
        if cand_obj < best_obj:
            best_v, best_obj = cand_v, cand_obj
    params = _params_from_vector(best_v)
    process = EnhancedG2PlusRateProcess(params, curve)

    per_quote: List[Dict[str, float]] = []
    rel_sq = 0.0
    vol_sq = 0.0
    max_vol_err = 0.0
    for t in targets:
        model_price = g2pp_swaption_price(
            process, t["expiry"], t["times"], t["accruals"], t["forward"], "payer", quadrature=quad
        )
        model_vol = black_implied_vol(
            model_price, t["annuity"], t["forward"], t["forward"], t["expiry"], "payer"
        )
        denom = t["target_price"] if t["target_price"] > 1e-10 else 1e-10
        rel = (model_price - t["target_price"]) / denom
        vol_err_bps = (model_vol - t["market_vol"]) * 1e4
        rel_sq += rel * rel
        vol_sq += vol_err_bps * vol_err_bps
        max_vol_err = max(max_vol_err, abs(vol_err_bps))
        per_quote.append(
            {
                "expiry": t["expiry"],
                "tenor": t["tenor"],
                "forward": t["forward"],
                "market_vol": t["market_vol"],
                "model_vol": model_vol,
                "vol_error_bps": vol_err_bps,
                "target_price": t["target_price"],
                "model_price": model_price,
                "rel_price_error": rel,
            }
        )

    n = len(targets)
    rmse_rel = math.sqrt(rel_sq / n)
    rmse_vol = math.sqrt(vol_sq / n)
    return SwaptionCalibrationResult(
        params=params,
        rmse_relative_price=rmse_rel,
        rmse_vol_bps=rmse_vol,
        max_abs_vol_bps=max_vol_err,
        objective_value=best_obj,
        n_quotes=n,
        iterations=iters,
        per_quote=per_quote,
        converged=best_obj < 1.0,
        initial_params={
            "mean_reversion_x": init.mean_reversion_x,
            "mean_reversion_y": init.mean_reversion_y,
            "vol_x": init.vol_x,
            "vol_y": init.vol_y,
            "factor_correlation": init.factor_correlation,
        },
    )


# ---------------------------------------------------------------------------
# G-SWPN calibration-quality gate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GSwpnCheck:
    check_id: str
    description: str
    passed: bool
    observed: float
    threshold: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "description": self.description,
            "passed": bool(self.passed),
            "observed": self.observed,
            "threshold": self.threshold,
        }


@dataclass(frozen=True)
class GSwpnGateReport:
    gate_id: str
    status: str
    checks: List[GSwpnCheck]
    calibration: SwaptionCalibrationResult
    use_restriction: str = (
        "EDUCATIONAL ONLY. Calibrated to a synthetic proxy swaption surface; "
        "re-calibrate to a validated market surface and obtain independent review "
        "before any production, capital, or disclosure use."
    )

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "checks": [c.to_dict() for c in self.checks],
            "calibration": self.calibration.to_dict(),
            "use_restriction": self.use_restriction,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# Calibration-quality thresholds (educational tolerances).
MAX_RMSE_VOL_BPS = 75.0
MAX_ABS_VOL_BPS = 200.0
MAX_RMSE_REL_PRICE = 0.10


def evaluate_g_swpn_gate(
    calibration: Optional[SwaptionCalibrationResult] = None,
    curve: Optional[RiskFreeCurve] = None,
) -> GSwpnGateReport:
    """Evaluate the Phase 20 Task 2 G-SWPN swaption-calibration gate."""
    curve = curve if curve is not None else educational_proxy_curve()
    if calibration is None:
        calibration = calibrate_g2pp_to_swaptions(curve=curve)

    p = calibration.params
    process = EnhancedG2PlusRateProcess(p, curve)

    # Parity check at a representative ATM point.
    times, accruals = swap_schedule(5.0, 10.0, 2)
    fwd, annuity = par_swap_rate(curve, 5.0, times, accruals)
    payer = g2pp_swaption_price(process, 5.0, times, accruals, fwd, "payer")
    receiver = g2pp_swaption_price(process, 5.0, times, accruals, fwd, "receiver")
    parity_err = abs(payer - receiver)  # ATM => payer == receiver

    # Curve-identity preservation: analytic ZCB must reprice the input curve at t=0.
    curve_err = max(
        abs(process.zcb_price(0.0, 0.0, 0.0, float(t)) - curve.discount_factor(float(t)))
        for t in (1.0, 2.0, 5.0, 10.0, 20.0, 30.0)
    )

    min_price = min(q["model_price"] for q in calibration.per_quote)
    params_valid = (
        p.mean_reversion_x > 0.0
        and p.mean_reversion_y > 0.0
        and abs(p.mean_reversion_x - p.mean_reversion_y) > 1e-6
        and p.vol_x > 0.0
        and p.vol_y > 0.0
        and -1.0 < p.factor_correlation < 1.0
    )

    checks = [
        GSwpnCheck(
            "G-SWPN-01",
            "ATM payer/receiver swaption prices satisfy put-call (swap) parity",
            parity_err <= 1e-7,
            parity_err,
            "<= 1e-7 absolute price difference",
        ),
        GSwpnCheck(
            "G-SWPN-02",
            "Calibration converged (mean relative price objective below 1)",
            calibration.converged and calibration.objective_value < MAX_RMSE_REL_PRICE ** 2 * 10,
            calibration.objective_value,
            "converged and objective < {:.3g}".format(MAX_RMSE_REL_PRICE ** 2 * 10),
        ),
        GSwpnCheck(
            "G-SWPN-03",
            "Implied-vol RMSE across the surface within educational tolerance",
            calibration.rmse_vol_bps <= MAX_RMSE_VOL_BPS,
            calibration.rmse_vol_bps,
            "<= {:.0f} bps".format(MAX_RMSE_VOL_BPS),
        ),
        GSwpnCheck(
            "G-SWPN-04",
            "Worst-point implied-vol error within educational tolerance",
            calibration.max_abs_vol_bps <= MAX_ABS_VOL_BPS,
            calibration.max_abs_vol_bps,
            "<= {:.0f} bps".format(MAX_ABS_VOL_BPS),
        ),
        GSwpnCheck(
            "G-SWPN-05",
            "Calibrated parameters lie in the admissible G2++ region (b != a, vols>0, |rho|<1)",
            params_valid,
            float(p.factor_correlation),
            "a,b>0 distinct; sigma,eta>0; -1<rho<1",
        ),
        GSwpnCheck(
            "G-SWPN-06",
            "All calibrated ATM swaption model prices are strictly positive",
            min_price > 0.0,
            min_price,
            "> 0 for every grid point",
        ),
        GSwpnCheck(
            "G-SWPN-07",
            "Calibrated engine still reprices the input curve (affine ZCB identity)",
            curve_err <= 1e-12,
            curve_err,
            "<= 1e-12 absolute price error",
        ),
    ]
    status = "PASS" if all(c.passed for c in checks) else "PARTIAL"
    return GSwpnGateReport(gate_id="G-SWPN", status=status, checks=checks, calibration=calibration)


__all__ = [
    "swap_schedule",
    "par_swap_rate",
    "black_swaption_price",
    "black_implied_vol",
    "g2pp_swaption_price",
    "educational_proxy_curve",
    "educational_proxy_vol_grid",
    "calibrate_g2pp_to_swaptions",
    "SwaptionCalibrationResult",
    "GSwpnCheck",
    "GSwpnGateReport",
    "evaluate_g_swpn_gate",
    "MAX_RMSE_VOL_BPS",
    "MAX_ABS_VOL_BPS",
    "MAX_RMSE_REL_PRICE",
]
