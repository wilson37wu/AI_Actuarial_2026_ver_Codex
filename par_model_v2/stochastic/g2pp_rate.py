"""
Enhanced G2++ two-factor Gaussian interest-rate engine.

Phase 20 Task 1 promotes the earlier educational G2++ prototype into a
market-consistency workstream component.  The implementation remains additive:
existing HW1F and legacy G2++ scenario paths are unchanged.

The module provides:
  * exact OU factor simulation for x(t), y(t);
  * analytic zero-coupon bond pricing fitted to the initial curve, including
    the G2++ convexity adjustment;
  * analytic European options on zero-coupon bonds;
  * a G-RATE2 plausibility gate used before future swaption-surface calibration.

Production use restriction: parameters are educational until Phase 20 Task 2
calibrates them to an observed swaption volatility surface and an independent
reviewer signs off the assumption set.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

import numpy as np
import pandas as pd

from par_model_v2.stochastic.esg_process import G2PlusParams, Measure, RiskFreeCurve


def _coerce_measure(measure: Measure) -> Measure:
    if isinstance(measure, Measure):
        return measure
    try:
        return Measure(str(measure).strip().upper())
    except ValueError as exc:
        raise ValueError("measure must be Measure.P or Measure.Q; got {!r}".format(measure)) from exc


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(float(x) / math.sqrt(2.0)))


@dataclass(frozen=True)
class G2PlusAnalyticDiagnostics:
    """Small diagnostic bundle for analytic G2++ pricing checks."""

    curve_fit_max_abs_error: float
    bond_option_variance: float
    call_price: float
    put_price: float
    put_call_parity_error: float
    empirical_factor_correlation: float
    negative_rate_discount_factor: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "curve_fit_max_abs_error": self.curve_fit_max_abs_error,
            "bond_option_variance": self.bond_option_variance,
            "call_price": self.call_price,
            "put_price": self.put_price,
            "put_call_parity_error": self.put_call_parity_error,
            "empirical_factor_correlation": self.empirical_factor_correlation,
            "negative_rate_discount_factor": self.negative_rate_discount_factor,
        }


@dataclass(frozen=True)
class GRate2Check:
    check_id: str
    description: str
    passed: bool
    observed: float
    threshold: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "description": self.description,
            "passed": self.passed,
            "observed": self.observed,
            "threshold": self.threshold,
        }


@dataclass(frozen=True)
class GRate2GateReport:
    """G-RATE2 plausibility-gate report for the enhanced G2++ engine."""

    gate_id: str
    status: str
    diagnostics: G2PlusAnalyticDiagnostics
    checks: List[GRate2Check] = field(default_factory=list)
    use_restriction: str = (
        "Educational G2++ implementation. Production use requires swaption-surface "
        "calibration, market-consistency validation, and independent APS X2 review."
    )

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "diagnostics": self.diagnostics.to_dict(),
            "checks": [c.to_dict() for c in self.checks],
            "use_restriction": self.use_restriction,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class EnhancedG2PlusRateProcess:
    """Market-consistency-oriented G2++ rate process.

    Model:
        r(t) = phi(t) + x(t) + y(t)
        dx(t) = -a x(t) dt + sigma dW_x(t)
        dy(t) = -b y(t) dt + eta dW_y(t)
        corr(dW_x, dW_y) = rho

    ``zcb_price`` uses the standard affine G2++ formula fitted to the supplied
    initial ``RiskFreeCurve``.  ``bond_option_price`` prices European options on
    zero-coupon bonds at time zero using the closed-form Gaussian bond-volatility
    expression.  The class is intentionally independent of ``ScenarioSet`` until
    Phase 20 Task 4 propagates the two-factor rates driver into the capital stack.
    """

    SUPPORTED_MEASURES = (Measure.P, Measure.Q)

    def __init__(self, params: G2PlusParams | None = None, initial_curve: RiskFreeCurve | None = None) -> None:
        self.params = params if params is not None else G2PlusParams()
        self.initial_curve = initial_curve if initial_curve is not None else RiskFreeCurve.flat(0.020)

    @staticmethod
    def factor_loading(speed: float, t: float, maturity: float) -> float:
        if maturity < t:
            raise ValueError("maturity must be greater than or equal to t")
        tau = float(maturity) - float(t)
        if tau == 0.0:
            return 0.0
        return (1.0 - math.exp(-float(speed) * tau)) / float(speed)

    def _integrated_short_rate_variance(self, tau: float) -> float:
        """Variance of integral_0^tau (x(u)+y(u)) du under Q."""
        tau = float(tau)
        if tau <= 0.0:
            return 0.0
        p = self.params
        a = float(p.mean_reversion_x)
        b = float(p.mean_reversion_y)
        sigma = float(p.vol_x)
        eta = float(p.vol_y)
        rho = float(p.factor_correlation)

        vx = (sigma * sigma / (a * a)) * (
            tau - 2.0 * (1.0 - math.exp(-a * tau)) / a + (1.0 - math.exp(-2.0 * a * tau)) / (2.0 * a)
        )
        vy = (eta * eta / (b * b)) * (
            tau - 2.0 * (1.0 - math.exp(-b * tau)) / b + (1.0 - math.exp(-2.0 * b * tau)) / (2.0 * b)
        )
        vxy = (2.0 * rho * sigma * eta / (a * b)) * (
            tau
            - (1.0 - math.exp(-a * tau)) / a
            - (1.0 - math.exp(-b * tau)) / b
            + (1.0 - math.exp(-(a + b) * tau)) / (a + b)
        )
        return max(vx + vy + vxy, 0.0)

    def _convexity_adjustment(self, t: float, maturity: float) -> float:
        """Affine curve-fitting convexity term for the G2++ bond formula."""
        t = float(t)
        maturity = float(maturity)
        if maturity < t:
            raise ValueError("maturity must be greater than or equal to t")
        return 0.5 * (
            self._integrated_short_rate_variance(maturity - t)
            - self._integrated_short_rate_variance(maturity)
            + self._integrated_short_rate_variance(t)
        )

    def zcb_price(self, x_t: float, y_t: float, t: float, maturity: float) -> float:
        """Analytic G2++ zero-coupon bond price P(t,T)."""
        t = float(t)
        maturity = float(maturity)
        if maturity == t:
            return 1.0
        if maturity < t:
            raise ValueError("maturity must be greater than or equal to t")

        bx = self.factor_loading(self.params.mean_reversion_x, t, maturity)
        by = self.factor_loading(self.params.mean_reversion_y, t, maturity)
        ratio = self.initial_curve.discount_factor(maturity) / self.initial_curve.discount_factor(t)
        exponent = -bx * float(x_t) - by * float(y_t) + self._convexity_adjustment(t, maturity)
        return float(ratio * math.exp(exponent))

    def bond_option_variance(self, option_expiry: float, bond_maturity: float) -> float:
        """Variance of log P(T,S) for an option expiring at T on a bond maturing at S."""
        option_expiry = float(option_expiry)
        bond_maturity = float(bond_maturity)
        if option_expiry <= 0.0:
            raise ValueError("option_expiry must be positive")
        if bond_maturity <= option_expiry:
            raise ValueError("bond_maturity must exceed option_expiry")

        p = self.params
        bx = self.factor_loading(p.mean_reversion_x, option_expiry, bond_maturity)
        by = self.factor_loading(p.mean_reversion_y, option_expiry, bond_maturity)
        a = float(p.mean_reversion_x)
        b = float(p.mean_reversion_y)
        sigma = float(p.vol_x)
        eta = float(p.vol_y)
        rho = float(p.factor_correlation)
        variance = (
            bx * bx * sigma * sigma * (1.0 - math.exp(-2.0 * a * option_expiry)) / (2.0 * a)
            + by * by * eta * eta * (1.0 - math.exp(-2.0 * b * option_expiry)) / (2.0 * b)
            + 2.0
            * rho
            * sigma
            * eta
            * bx
            * by
            * (1.0 - math.exp(-(a + b) * option_expiry))
            / (a + b)
        )
        return max(float(variance), 0.0)

    def bond_option_price(
        self,
        option_expiry: float,
        bond_maturity: float,
        strike: float,
        option_type: str = "call",
    ) -> float:
        """Time-zero European option price on a zero-coupon bond."""
        option_type = option_type.lower()
        if option_type not in {"call", "put"}:
            raise ValueError("option_type must be 'call' or 'put'")
        if strike <= 0.0:
            raise ValueError("strike must be positive")

        p0s = self.initial_curve.discount_factor(bond_maturity)
        p0t = self.initial_curve.discount_factor(option_expiry)
        variance = self.bond_option_variance(option_expiry, bond_maturity)
        vol = math.sqrt(variance)
        if vol < 1e-14:
            call = max(p0s - strike * p0t, 0.0)
        else:
            h = math.log(p0s / (strike * p0t)) / vol + 0.5 * vol
            call = p0s * _normal_cdf(h) - strike * p0t * _normal_cdf(h - vol)
        if option_type == "call":
            return float(call)
        put = call - p0s + strike * p0t
        return float(max(put, 0.0))

    def _target_shift(self, month: int, measure: Measure, dt: float) -> float:
        if measure == Measure.Q:
            return self.initial_curve.instantaneous_forward(float(month) * dt)
        p = self.params
        return p.long_run_rate_p + p.vol_x * p.market_price_of_risk_x + p.vol_y * p.market_price_of_risk_y

    def simulate_arrays(
        self,
        n_scenarios: int,
        t_months: int,
        measure: Measure = Measure.Q,
        seed: int = 42,
    ) -> Dict[str, np.ndarray]:
        """Simulate exact OU factor arrays and short-rate diagnostics."""
        measure = _coerce_measure(measure)
        if measure not in self.SUPPORTED_MEASURES:
            raise ValueError("G2++ process does not support measure {!r}".format(measure))
        if n_scenarios <= 0:
            raise ValueError("n_scenarios must be positive")
        if t_months < 0:
            raise ValueError("t_months must be non-negative")

        n = int(n_scenarios)
        steps = int(t_months)
        dt = 1.0 / 12.0
        p = self.params
        rng = np.random.default_rng(seed)
        zx = rng.standard_normal((n, steps))
        zi = rng.standard_normal((n, steps))
        zy = p.factor_correlation * zx + math.sqrt(1.0 - p.factor_correlation * p.factor_correlation) * zi

        x = np.empty((n, steps + 1), dtype=float)
        y = np.empty((n, steps + 1), dtype=float)
        r = np.empty((n, steps + 1), dtype=float)
        x[:, 0] = p.initial_x
        y[:, 0] = p.initial_y
        r[:, 0] = self._target_shift(0, measure, dt) + x[:, 0] + y[:, 0]

        mx = math.exp(-p.mean_reversion_x * dt)
        my = math.exp(-p.mean_reversion_y * dt)
        sx = p.vol_x * math.sqrt((1.0 - math.exp(-2.0 * p.mean_reversion_x * dt)) / (2.0 * p.mean_reversion_x))
        sy = p.vol_y * math.sqrt((1.0 - math.exp(-2.0 * p.mean_reversion_y * dt)) / (2.0 * p.mean_reversion_y))
        for month in range(steps):
            x[:, month + 1] = mx * x[:, month] + sx * zx[:, month]
            y[:, month + 1] = my * y[:, month] + sy * zy[:, month]
            r[:, month + 1] = self._target_shift(month + 1, measure, dt) + x[:, month + 1] + y[:, month + 1]

        return {"x": x, "y": y, "r_short": r}

    def simulate(
        self,
        n_scenarios: int,
        t_months: int,
        measure: Measure = Measure.Q,
        seed: int = 42,
        cap_zcb_at_par: bool = True,
    ) -> pd.DataFrame:
        """Return a v1-compatible path frame with analytic ZCB diagnostics."""
        measure = _coerce_measure(measure)
        arrays = self.simulate_arrays(n_scenarios, t_months, measure=measure, seed=seed)
        n = int(n_scenarios)
        steps = int(t_months)
        months = np.tile(np.arange(steps + 1), n)
        scenarios = np.repeat(np.arange(n), steps + 1)
        x_flat = arrays["x"].reshape(-1)
        y_flat = arrays["y"].reshape(-1)
        r_flat = arrays["r_short"].reshape(-1)
        times = months.astype(float) / 12.0

        zcb_1y = np.array([self.zcb_price(x, y, t, t + 1.0) for x, y, t in zip(x_flat, y_flat, times)])
        zcb_10y = np.array([self.zcb_price(x, y, t, t + 10.0) for x, y, t in zip(x_flat, y_flat, times)])
        if cap_zcb_at_par:
            zcb_1y = np.minimum(zcb_1y, 1.0)
            zcb_10y = np.minimum(zcb_10y, 1.0)
        return pd.DataFrame(
            {
                "scenario_id": scenarios,
                "month": months,
                "r_short": r_flat,
                "zcb_1y": zcb_1y,
                "zcb_10y": zcb_10y,
                "g2pp_x": x_flat,
                "g2pp_y": y_flat,
                "measure": measure.value,
                "rate_model": "G2++",
            }
        )

    def diagnostics(
        self,
        tenors: Sequence[float] = (0.25, 1.0, 2.0, 5.0, 10.0, 30.0),
        option_expiry: float = 5.0,
        bond_maturity: float = 10.0,
        strike: float = 0.82,
        n_scenarios: int = 6000,
        seed: int = 20260606,
    ) -> G2PlusAnalyticDiagnostics:
        curve_errors = [
            abs(self.zcb_price(0.0, 0.0, 0.0, float(t)) - self.initial_curve.discount_factor(float(t)))
            for t in tenors
        ]
        call = self.bond_option_price(option_expiry, bond_maturity, strike, "call")
        put = self.bond_option_price(option_expiry, bond_maturity, strike, "put")
        parity = call - put - (
            self.initial_curve.discount_factor(bond_maturity)
            - strike * self.initial_curve.discount_factor(option_expiry)
        )

        arrays = self.simulate_arrays(n_scenarios, 12, Measure.Q, seed=seed)
        dx = np.diff(arrays["x"], axis=1).reshape(-1)
        dy = np.diff(arrays["y"], axis=1).reshape(-1)
        empirical_corr = float(np.corrcoef(dx, dy)[0, 1])

        negative_curve = RiskFreeCurve.flat(-0.005, currency="JPY", market="JP")
        negative_process = EnhancedG2PlusRateProcess(
            G2PlusParams(short_rate_floor=None, short_rate_ceiling=None),
            negative_curve,
        )
        negative_df = negative_process.zcb_price(0.0, 0.0, 0.0, 1.0)

        return G2PlusAnalyticDiagnostics(
            curve_fit_max_abs_error=max(curve_errors),
            bond_option_variance=self.bond_option_variance(option_expiry, bond_maturity),
            call_price=call,
            put_price=put,
            put_call_parity_error=abs(float(parity)),
            empirical_factor_correlation=empirical_corr,
            negative_rate_discount_factor=negative_df,
        )


def evaluate_g_rate2_gate(process: EnhancedG2PlusRateProcess | None = None) -> GRate2GateReport:
    """Evaluate the Phase 20 G-RATE2 plausibility gate."""
    process = process if process is not None else EnhancedG2PlusRateProcess()
    diag = process.diagnostics()
    p = process.params
    p0s = process.initial_curve.discount_factor(10.0)

    checks = [
        GRate2Check(
            "G-RATE2-01",
            "Analytic ZCB formula fits the supplied initial curve at t=0",
            diag.curve_fit_max_abs_error <= 1e-12,
            diag.curve_fit_max_abs_error,
            "<= 1e-12 absolute price error",
        ),
        GRate2Check(
            "G-RATE2-02",
            "European bond-option formula has positive variance",
            diag.bond_option_variance > 0.0,
            diag.bond_option_variance,
            "> 0",
        ),
        GRate2Check(
            "G-RATE2-03",
            "Bond call and put satisfy time-zero put-call parity",
            diag.put_call_parity_error <= 1e-10,
            diag.put_call_parity_error,
            "<= 1e-10",
        ),
        GRate2Check(
            "G-RATE2-04",
            "Bond option prices respect no-arbitrage bounds",
            0.0 <= diag.call_price <= p0s and diag.put_price >= 0.0,
            max(diag.call_price - p0s, -diag.call_price, -diag.put_price),
            "call in [0,P(0,S)] and put >= 0",
        ),
        GRate2Check(
            "G-RATE2-05",
            "Exact OU simulator reproduces the configured factor-shock correlation",
            abs(diag.empirical_factor_correlation - p.factor_correlation) <= 0.035,
            diag.empirical_factor_correlation,
            "within 3.5 percentage points of configured rho",
        ),
        GRate2Check(
            "G-RATE2-06",
            "Negative-rate curve support preserves discount factors above par",
            diag.negative_rate_discount_factor > 1.0,
            diag.negative_rate_discount_factor,
            "> 1.0 for a -50 bp one-year flat curve",
        ),
    ]
    return GRate2GateReport(
        gate_id="G-RATE2",
        status="PASS" if all(c.passed for c in checks) else "PARTIAL",
        diagnostics=diag,
        checks=checks,
    )


__all__ = [
    "EnhancedG2PlusRateProcess",
    "G2PlusAnalyticDiagnostics",
    "GRate2Check",
    "GRate2GateReport",
    "evaluate_g_rate2_gate",
]
