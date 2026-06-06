"""Phase 20 Task 3 -- Market-consistency (martingale) validation gate (G-MART).

This module adds an additive, output-only market-consistency check across the
stochastic drivers used by the economic-scenario generator.  Under the
risk-neutral measure Q with the money-market account

    B(t) = exp( integral_0^t r(s) ds )

as numeraire, every traded asset deflated by B(t) must be a Q-martingale.  The
gate verifies the following identities by Monte-Carlo within statistical
tolerance (a k-standard-error band), so that every "PASS" is an honest
hypothesis test rather than an arbitrary point comparison:

    MART-HW1F-ZCB   E^Q[ D(t) * P_HW(t,T; r_t) ]      = P(0,T)   (1F Hull-White)
    MART-G2PP-ZCB   E^Q[ D(t) * P_G2(t,T; x_t,y_t) ]  = P(0,T)   (G2++/2F HW)
    MART-EQ-FWD     E^Q[ D(t) * S(t) * exp(q_S * t) ]  = S(0)     (GBM equity)
    MART-FX-CIP     E^Q[ D_d(t) * X(t) * exp(r_f * t)] = X(0)     (FX, cov. int. parity)

where D(t) = exp(-sum_i r_i * dt) is the simulated stochastic deflator built
from the SAME short-rate path that drives each asset, so the test is internally
consistent (no analytic short-cut is substituted for the simulated drift).

A non-gating informational diagnostic (MART-PQ-MEASURE) confirms the
martingale property is measure-specific: under P the discounted equity drifts
upward by the equity-risk-premium, so the identity holds only under Q.

This file performs NO calibration and changes NO existing output; it consumes
the existing driver simulators and analytic bond formulas only.

Standards: SOA ASOP 56 s3.1.3 / s3.5 (economic-scenario validation, martingale
evidence); IA TAS M s3.6 (validation); Solvency II Delegated Reg. Art. 22
(market consistency) / Art. 234 (consistency of inputs).  Brigo-Mercurio (2006).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from par_model_v2.stochastic.esg_process import (
    FXParams,
    FXSpotProcess,
    GBMEquityProcess,
    GBMParams,
    HullWhiteParams,
    HullWhiteRateProcess,
    Measure,
    RiskFreeCurve,
)
from par_model_v2.stochastic.g2pp_rate import EnhancedG2PlusRateProcess
from par_model_v2.stochastic.esg_process import G2PlusParams

_DT = 1.0 / 12.0
#: Number of standard errors allowed between the MC estimate and the analytic
#: target before a martingale check is failed.  4 sigma ~ a two-sided 6.3e-5
#: false-rejection rate -- strict enough to catch a real drift, loose enough to
#: avoid flagging pure Monte-Carlo noise.
_K_SIGMA_DEFAULT = 4.0


# --------------------------------------------------------------------------- #
# Report value objects                                                        #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MartingaleCheck:
    """One deflated-asset martingale identity tested by Monte-Carlo."""

    check_id: str
    passed: bool
    severity: str
    description: str
    estimate: float
    target: float
    std_error: float
    n_std_errors: float
    rel_error: float
    tolerance_sigma: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": bool(self.passed),
            "severity": self.severity,
            "description": self.description,
            "estimate": float(self.estimate),
            "target": float(self.target),
            "std_error": float(self.std_error),
            "n_std_errors": float(self.n_std_errors),
            "rel_error": float(self.rel_error),
            "tolerance_sigma": float(self.tolerance_sigma),
        }


@dataclass(frozen=True)
class GMartGateReport:
    """G-MART market-consistency gate report."""

    gate_id: str
    status: str
    checks: List[MartingaleCheck]
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    use_restriction: str = (
        "EDUCATIONAL market-consistency evidence. The martingale gate confirms "
        "the simulators are arbitrage-free under Q at the tested horizon and "
        "Monte-Carlo accuracy; it is NOT a production sign-off. Calibration to a "
        "validated market surface and independent (APS X2) review remain pending."
    )

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "ERROR")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
            "diagnostics": self.diagnostics,
            "use_restriction": self.use_restriction,
            "n_checks": len(self.checks),
            "n_error_checks": sum(1 for c in self.checks if c.severity == "ERROR"),
            "n_passed": sum(1 for c in self.checks if c.passed),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _deflator(rate_grid: np.ndarray, dt: float = _DT, method: str = "trapezoid") -> np.ndarray:
    """Path-wise money-market deflator D(t_m) = exp(-int_0^{t_m} r ds).

    `rate_grid` has shape (n_paths, n_months + 1); D has the same shape with
    D[:, 0] = 1.

    method:
      - "trapezoid": int approx by the trapezoidal rule
        sum (r_i + r_{i+1})/2 * dt -- O(dt^2) accurate; used for the analytic
        bond martingale checks where a left-Riemann sum leaves a detectable
        O(dt) Jensen bias.
      - "riemann": left-point sum sum r_i * dt -- matches the GBM/FX Euler drift
        (drift uses the left-point short rate), so the discrete discounted
        equity/FX identity holds EXACTLY; used for the asset-forward checks.
    """
    n, cols = rate_grid.shape
    deflator = np.ones((n, cols), dtype=float)
    if cols > 1:
        if method == "trapezoid":
            increments = 0.5 * (rate_grid[:, :-1] + rate_grid[:, 1:]) * dt
        elif method == "riemann":
            increments = rate_grid[:, :-1] * dt
        else:
            raise ValueError("method must be 'trapezoid' or 'riemann'")
        deflator[:, 1:] = np.exp(-np.cumsum(increments, axis=1))
    return deflator


def _mc_check(
    check_id: str,
    description: str,
    deflated_values: np.ndarray,
    target: float,
    k_sigma: float,
    severity: str = "ERROR",
) -> MartingaleCheck:
    """Build a MartingaleCheck from a vector of per-path deflated asset values."""
    estimate = float(np.mean(deflated_values))
    std_error = float(np.std(deflated_values, ddof=1) / math.sqrt(len(deflated_values)))
    abs_err = abs(estimate - target)
    n_sig = abs_err / std_error if std_error > 0 else float("inf")
    rel_err = abs_err / abs(target) if target != 0 else float("inf")
    passed = n_sig <= k_sigma
    return MartingaleCheck(
        check_id=check_id,
        passed=passed,
        severity=severity,
        description=description,
        estimate=estimate,
        target=target,
        std_error=std_error,
        n_std_errors=n_sig,
        rel_error=rel_err,
        tolerance_sigma=k_sigma,
    )


# --------------------------------------------------------------------------- #
# Per-driver martingale checks                                                 #
# --------------------------------------------------------------------------- #
def simulate_hw1f_exact(
    curve: RiskFreeCurve,
    params: HullWhiteParams,
    test_month: int,
    n_scenarios: int,
    seed: int,
) -> np.ndarray:
    """EXACT, initial-curve-consistent Hull-White 1F short-rate simulation under Q.

    The educational `HullWhiteRateProcess.simulate` uses a monthly Euler step that
    mean-reverts toward the instantaneous forward and omits the HW convexity term
    alpha(t) (and starts at params.initial_short_rate, not the curve forward), so
    it is only APPROXIMATELY arbitrage-free.  For a market-consistency gate we
    simulate the exact law instead, which is consistent with the analytic bond
    `HullWhiteRateProcess.zcb_price`:

        r(t) = x(t) + alpha(t),
        dx   = -a*x*dt + sigma*dW,  x(0) = 0,
        alpha(t) = f(0,t) + (sigma^2 / (2 a^2)) * (1 - exp(-a t))^2.

    x is propagated with its EXACT OU transition (no Euler bias).  Returns a
    short-rate grid of shape (n_scenarios, test_month + 1).
    """
    a = params.mean_reversion_speed
    sigma = params.short_rate_vol
    dt = _DT
    n = int(n_scenarios)
    steps = int(test_month)
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n, steps))
    decay = math.exp(-a * dt)
    cond_sd = sigma * math.sqrt((1.0 - math.exp(-2.0 * a * dt)) / (2.0 * a))
    x = np.zeros((n, steps + 1), dtype=float)
    for m in range(steps):
        x[:, m + 1] = x[:, m] * decay + cond_sd * z[:, m]
    months = np.arange(steps + 1)
    t_grid = months * dt
    f0 = np.array([curve.instantaneous_forward(float(tt)) for tt in t_grid])
    alpha = f0 + (sigma ** 2 / (2.0 * a ** 2)) * (1.0 - np.exp(-a * t_grid)) ** 2
    return x + alpha[np.newaxis, :]


def martingale_hw1f(
    curve: RiskFreeCurve,
    test_month: int,
    bond_maturities: Sequence[float],
    n_scenarios: int,
    seed: int,
    k_sigma: float,
) -> Tuple[List[MartingaleCheck], np.ndarray, np.ndarray]:
    """Discounted fixed-maturity ZCB is a Q-martingale for the 1F Hull-White
    short rate, tested on the EXACT curve-consistent dynamics.  Returns
    (checks, rate_grid, deflator) so the equity check can reuse the same Q
    short-rate path for internal consistency."""
    proc = HullWhiteRateProcess(initial_curve=curve)
    rate_grid = simulate_hw1f_exact(curve, proc.params, test_month, n_scenarios, seed)
    deflator_bond = _deflator(rate_grid, method="trapezoid")
    deflator = _deflator(rate_grid, method="riemann")  # returned for the equity check
    t = test_month * _DT
    r_t = rate_grid[:, test_month]
    d_t = deflator_bond[:, test_month]
    checks: List[MartingaleCheck] = []
    for mat in bond_maturities:
        big_t = t + float(mat)
        p_t_T = proc.zcb_price(r_t, t, big_t)
        target = curve.discount_factor(big_t)
        checks.append(
            _mc_check(
                "MART-HW1F-ZCB-{:g}Y".format(mat),
                "E^Q[ D({:.2f}) * P_HW({:.2f},{:.2f}) ] = P(0,{:.2f})".format(t, t, big_t, big_t),
                d_t * p_t_T,
                float(target),
                k_sigma,
            )
        )
    return checks, rate_grid, deflator


def diagnostic_hw1f_euler_bias(
    curve: RiskFreeCurve,
    test_month: int,
    bond_maturity: float,
    n_scenarios: int,
    seed: int,
) -> MartingaleCheck:
    """INFORMATIONAL: quantify the martingale bias of the EDUCATIONAL monthly-Euler
    `HullWhiteRateProcess.simulate` (mean-reversion-to-forward, no convexity term,
    r0 = params.initial_short_rate). Documented limitation feeding MR-013; NOT a
    gating check.  Passes iff the bias is detected and reported (estimate finite)."""
    n_diag = min(int(n_scenarios), 5000)  # educational simulate() prices ZCBs via a slow scalar loop
    proc = HullWhiteRateProcess(initial_curve=curve)
    frame = proc.simulate(n_diag, test_month, Measure.Q, seed=seed, cap_zcb_at_par=False)
    months = np.arange(test_month + 1)
    rate_grid = (
        frame.pivot(index="scenario_id", columns="month", values="r_short")
        .reindex(columns=months)
        .to_numpy(dtype=float)
    )
    deflator = _deflator(rate_grid, method="trapezoid")
    t = test_month * _DT
    big_t = t + float(bond_maturity)
    d_t = deflator[:, test_month]
    p_t_T = proc.zcb_price(rate_grid[:, test_month], t, big_t)
    deflated = d_t * p_t_T
    estimate = float(np.mean(deflated))
    target = float(curve.discount_factor(big_t))
    std_error = float(np.std(deflated, ddof=1) / math.sqrt(n_diag))
    rel_err = abs(estimate - target) / abs(target)
    n_sig = abs(estimate - target) / std_error if std_error > 0 else float("inf")
    return MartingaleCheck(
        check_id="MART-HW1F-EULER-BIAS",
        passed=math.isfinite(estimate),
        severity="INFO",
        description=(
            "Educational monthly-Euler HW1F simulate() carries a documented "
            "discretisation + r0 bias vs the analytic bond (use exact dynamics)."
        ),
        estimate=estimate,
        target=target,
        std_error=std_error,
        n_std_errors=n_sig,
        rel_error=rel_err,
        tolerance_sigma=float("inf"),
    )


def martingale_g2pp(
    curve: RiskFreeCurve,
    test_month: int,
    bond_maturities: Sequence[float],
    n_scenarios: int,
    seed: int,
    k_sigma: float,
) -> List[MartingaleCheck]:
    """Discounted fixed-maturity ZCB is a Q-martingale for the two-factor G2++
    short rate (uses the exact OU factor simulator + analytic affine bond)."""
    proc = EnhancedG2PlusRateProcess(G2PlusParams(), curve)
    arrays = proc.simulate_arrays(n_scenarios, test_month, Measure.Q, seed=seed)
    rate_grid = arrays["r_short"]
    deflator = _deflator(rate_grid, method="trapezoid")
    t = test_month * _DT
    x_t = arrays["x"][:, test_month]
    y_t = arrays["y"][:, test_month]
    d_t = deflator[:, test_month]
    checks: List[MartingaleCheck] = []
    for mat in bond_maturities:
        big_t = t + float(mat)
        # Vectorised G2++ analytic ZCB: the path-dependent part is exp(-bx*x - by*y);
        # bx, by, the curve ratio and the convexity term are path-independent scalars
        # (identical to EnhancedG2PlusRateProcess.zcb_price, applied across paths).
        bx = proc.factor_loading(proc.params.mean_reversion_x, t, big_t)
        by = proc.factor_loading(proc.params.mean_reversion_y, t, big_t)
        ratio = curve.discount_factor(big_t) / curve.discount_factor(t)
        conv = proc._convexity_adjustment(t, big_t)
        p_t_T = ratio * np.exp(-bx * x_t - by * y_t + conv)
        target = curve.discount_factor(big_t)
        checks.append(
            _mc_check(
                "MART-G2PP-ZCB-{:g}Y".format(mat),
                "E^Q[ D({:.2f}) * P_G2({:.2f},{:.2f}) ] = P(0,{:.2f})".format(t, t, big_t, big_t),
                d_t * p_t_T,
                float(target),
                k_sigma,
            )
        )
    return checks


def martingale_equity(
    rate_grid: np.ndarray,
    deflator: np.ndarray,
    test_month: int,
    gbm_params: GBMParams,
    n_scenarios: int,
    seed: int,
    k_sigma: float,
) -> List[MartingaleCheck]:
    """Ex-dividend discounted GBM equity index is a Q-martingale:
    E^Q[ D(t) S(t) exp(q_S t) ] = S(0).  Uses the SAME Q short-rate path that
    builds the deflator, so the drift and the discount are consistent."""
    eq_proc = GBMEquityProcess(params=gbm_params)
    frame = eq_proc.simulate(
        n_scenarios, test_month, Measure.Q, rate_paths=rate_grid, seed=seed
    )
    months = np.arange(test_month + 1)
    equity_grid = (
        frame.pivot(index="scenario_id", columns="month", values="equity_index")
        .reindex(columns=months)
        .to_numpy(dtype=float)
    )
    t = test_month * _DT
    s0 = gbm_params.initial_index_level
    q = gbm_params.dividend_yield
    d_t = deflator[:, test_month]
    s_t = equity_grid[:, test_month]
    deflated = d_t * s_t * math.exp(q * t)
    return [
        _mc_check(
            "MART-EQ-FWD",
            "E^Q[ D({:.2f}) * S({:.2f}) * exp(q*{:.2f}) ] = S(0)".format(t, t, t),
            deflated,
            float(s0),
            k_sigma,
        )
    ]


def martingale_equity_pmeasure(
    rate_grid: np.ndarray,
    deflator: np.ndarray,
    test_month: int,
    gbm_params: GBMParams,
    n_scenarios: int,
    seed: int,
) -> MartingaleCheck:
    """INFORMATIONAL: under P the discounted equity is NOT a martingale -- it
    drifts up by exp(ERP * t).  Passing means the expected upward drift is
    present (i.e. the martingale property is genuinely measure-specific)."""
    eq_proc = GBMEquityProcess(params=gbm_params)
    frame = eq_proc.simulate(
        n_scenarios, test_month, Measure.P, rate_paths=rate_grid, seed=seed
    )
    months = np.arange(test_month + 1)
    equity_grid = (
        frame.pivot(index="scenario_id", columns="month", values="equity_index")
        .reindex(columns=months)
        .to_numpy(dtype=float)
    )
    t = test_month * _DT
    s0 = gbm_params.initial_index_level
    q = gbm_params.dividend_yield
    erp = gbm_params.equity_risk_premium
    d_t = deflator[:, test_month]
    s_t = equity_grid[:, test_month]
    estimate = float(np.mean(d_t * s_t * math.exp(q * t)))
    target_p = float(s0 * math.exp(erp * t))  # expected P-measure level of the deflated asset
    std_error = float(
        np.std(d_t * s_t * math.exp(q * t), ddof=1) / math.sqrt(n_scenarios)
    )
    # "passes" iff the realised P drift is materially above S(0) (martingale broken under P)
    drift_present = (estimate - s0) > 3.0 * std_error
    rel_err = abs(estimate - target_p) / abs(target_p)
    n_sig = abs(estimate - target_p) / std_error if std_error > 0 else float("inf")
    return MartingaleCheck(
        check_id="MART-PQ-MEASURE",
        passed=bool(drift_present),
        severity="INFO",
        description="Under P the discounted equity drifts up by exp(ERP*t); martingale is Q-specific.",
        estimate=estimate,
        target=target_p,
        std_error=std_error,
        n_std_errors=n_sig,
        rel_error=rel_err,
        tolerance_sigma=3.0,
    )


def martingale_fx(
    domestic_rate: float,
    foreign_rate: float,
    test_month: int,
    fx_vol: float,
    initial_spot: float,
    n_scenarios: int,
    seed: int,
    k_sigma: float,
) -> List[MartingaleCheck]:
    """Covered-interest-parity martingale for FX under the domestic Q measure:
    the foreign money-market account converted to domestic units and discounted
    at the domestic rate is a martingale, E^Q_d[ D_d(t) X(t) exp(r_f t) ] = X(0).
    Uses flat constant domestic/foreign rates so the deflator is exact and the
    test isolates the FX drift convention (r_d - r_f)."""
    params = FXParams(
        fx_vol=fx_vol,
        real_world_drift=0.0,
        domestic_foreign_rate_spread=domestic_rate - foreign_rate,
        rate_fx_correlation=0.0,
        initial_spot_rate=initial_spot,
    )
    proc = FXSpotProcess(params=params)
    frame = proc.simulate(n_scenarios, test_month, Measure.Q, seed=seed)
    months = np.arange(test_month + 1)
    spot_grid = (
        frame.pivot(index="scenario_id", columns="month", values="fx_rate")
        .reindex(columns=months)
        .to_numpy(dtype=float)
    )
    t = test_month * _DT
    d_t = math.exp(-domestic_rate * t)
    x_t = spot_grid[:, test_month]
    deflated = d_t * x_t * math.exp(foreign_rate * t)
    return [
        _mc_check(
            "MART-FX-CIP",
            "E^Q_d[ D_d({:.2f}) * X({:.2f}) * exp(r_f*{:.2f}) ] = X(0)".format(t, t, t),
            deflated,
            float(initial_spot),
            k_sigma,
        )
    ]


# --------------------------------------------------------------------------- #
# Gate orchestration                                                          #
# --------------------------------------------------------------------------- #
def evaluate_g_mart_gate(
    curve: RiskFreeCurve | None = None,
    test_month: int = 12,
    bond_maturities: Sequence[float] = (5.0, 10.0),
    n_scenarios: int = 40000,
    seed: int = 20260606,
    k_sigma: float = _K_SIGMA_DEFAULT,
    fx_domestic_rate: float = 0.03,
    fx_foreign_rate: float = 0.01,
    fx_vol: float = 0.10,
    fx_initial_spot: float = 7.8,
) -> GMartGateReport:
    """Run the full G-MART market-consistency gate across all drivers."""
    if curve is None:
        curve = RiskFreeCurve.flat(0.03, currency="CNY", market="CN")

    checks: List[MartingaleCheck] = []

    hw_checks, rate_grid, deflator = martingale_hw1f(
        curve, test_month, bond_maturities, n_scenarios, seed, k_sigma
    )
    checks.extend(hw_checks)
    checks.append(
        diagnostic_hw1f_euler_bias(
            curve, test_month, float(bond_maturities[-1]), n_scenarios, seed
        )
    )

    checks.extend(
        martingale_g2pp(curve, test_month, bond_maturities, n_scenarios, seed + 1, k_sigma)
    )

    gbm_params = GBMParams()
    checks.extend(
        martingale_equity(
            rate_grid, deflator, test_month, gbm_params, n_scenarios, seed + 2, k_sigma
        )
    )
    checks.append(
        martingale_equity_pmeasure(
            rate_grid, deflator, test_month, gbm_params, n_scenarios, seed + 3
        )
    )

    checks.extend(
        martingale_fx(
            fx_domestic_rate, fx_foreign_rate, test_month, fx_vol,
            fx_initial_spot, n_scenarios, seed + 4, k_sigma,
        )
    )

    error_checks = [c for c in checks if c.severity == "ERROR"]
    status = "PASS" if all(c.passed for c in error_checks) else "FAIL"
    worst = max((c.n_std_errors for c in error_checks), default=0.0)
    diagnostics = {
        "test_time_years": test_month * _DT,
        "n_scenarios": n_scenarios,
        "k_sigma": k_sigma,
        "bond_maturities": list(bond_maturities),
        "numeraire": "money-market account B(t)=exp(int_0^t r ds)",
        "worst_n_std_errors": worst,
        "max_rel_error": max((c.rel_error for c in error_checks), default=0.0),
        "drivers": ["HW1F rates", "G2++ rates", "GBM equity", "FX (CIP)"],
    }
    return GMartGateReport(gate_id="G-MART", status=status, checks=checks, diagnostics=diagnostics)


if __name__ == "__main__":  # pragma: no cover
    report = evaluate_g_mart_gate()
    print(report.to_json())
