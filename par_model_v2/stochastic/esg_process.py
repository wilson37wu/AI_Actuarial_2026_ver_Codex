"""
Economic Scenario Generator — Stochastic Process Module
========================================================

SOA ASOP 56 §3.1.3 compliance.

Provides stochastic process classes for the PAR Fund ALM & TVOG model:

  1. HullWhiteRateProcess  -- CNY short rate (Hull-White 1-factor, HW1F)
  2. GBMEquityProcess      -- CNY equity index (Geometric Brownian Motion, GBM)
  3. ScenarioSet           -- Container for N correlated paths, measure-labelled

Phase 4 status: simulate() fully implemented; ScenarioSet.generate() produces
correlated HW1F + GBM paths via Cholesky decomposition; parameters are
PLACEHOLDERS pending Phase 4 calibration sign-off.

P / Q MEASURE DISTINCTION (ASOP 56 Deviation D-04 Remediation)
---------------------------------------------------------------
  Measure.P  (real-world)   -- ALM, ERM, VaR/ES, bonus projection
  Measure.Q  (risk-neutral) -- TVOG, MCEV, market-consistent pricing

PRODUCTION USE RESTRICTION: Parameters are PLACEHOLDERS.
Do not use for regulatory reporting until Phase 4 calibration is complete.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


def _coerce_measure(measure):
    """Return a Measure enum or raise a descriptive error."""
    if isinstance(measure, Measure):
        return measure
    try:
        return Measure(str(measure).strip().upper())
    except ValueError as exc:
        raise ValueError(
            "measure must be Measure.P or Measure.Q; got {!r}".format(measure)
        ) from exc


def _validate_simulation_dimensions(n_scenarios, T_months):
    """Validate common scenario generation dimensions."""
    if int(n_scenarios) != n_scenarios or n_scenarios <= 0:
        raise ValueError("n_scenarios must be a positive integer; got {}".format(n_scenarios))
    if int(T_months) != T_months or T_months < 0:
        raise ValueError("T_months must be a non-negative integer; got {}".format(T_months))


def _month_grid(n_scenarios, T_months):
    """Return flattened 1-based scenario IDs and 0-based month indices."""
    months = np.tile(np.arange(T_months + 1, dtype=np.int64), n_scenarios)
    scenario_ids = np.repeat(np.arange(1, n_scenarios + 1, dtype=np.int64), T_months + 1)
    return scenario_ids, months


def _antithetic_normals(rng, n_scenarios, T_months):
    """Generate normal shocks with antithetic pairs where possible."""
    if T_months == 0:
        return np.empty((n_scenarios, 0), dtype=float)
    half = (n_scenarios + 1) // 2
    base = rng.standard_normal((half, T_months))
    paired = np.vstack([base, -base])
    return paired[:n_scenarios]


# ---------------------------------------------------------------------------
# 0. Measure Enum
# ---------------------------------------------------------------------------

class Measure(str, enum.Enum):
    """Probability measure for scenario generation.

    P: Real-world (physical) -- ALM, ERM, VaR/ES, bonus projection.
       Drift includes equity risk premium (ERP) and market price of risk.
    Q: Risk-neutral -- TVOG, MCEV.
       Drift is risk-free rate only; no ERP.
    """
    P = "P"
    Q = "Q"


# ---------------------------------------------------------------------------
# 1. Parameter Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class HullWhiteParams:
    """Parameters for the Hull-White 1-factor interest rate process.

    dr(t) = [theta(t) - a*r(t)] dt + sigma_r * dW_r(t)

    Monthly discretisation (dt = 1/12):
      r(t+dt) = r(t)*exp(-a*dt) + target*(1-exp(-a*dt)) + sigma_r*sqrt(...)*Z_r

    ZCB closed form: P(t,T) = exp(-B(t,T)*r_t),  B = (1/a)*(1-exp(-a*(T-t)))

    All values are PLACEHOLDERS -- calibrate in Phase 4.
    SOA ASOP 56 ss3.1.3, ss3.4.
    """
    mean_reversion_speed: float = 0.10
    short_rate_vol: float = 0.012
    initial_short_rate: float = 0.020
    long_run_rate_p: float = 0.025
    market_price_of_risk: float = -0.15
    cbirc_rate_cap: float = 0.030

    def __post_init__(self):
        if self.mean_reversion_speed <= 0:
            raise ValueError(
                "mean_reversion_speed must be positive; got {}".format(self.mean_reversion_speed)
            )
        if self.short_rate_vol <= 0:
            raise ValueError(
                "short_rate_vol must be positive; got {}".format(self.short_rate_vol)
            )

    @property
    def is_placeholder(self):
        return True


@dataclass
class GBMParams:
    """Parameters for the GBM equity index process.

    dS(t) = mu_S(t)*S(t)*dt + sigma_S*S(t)*dW_S(t)
    Q: mu_S^Q = r(t) - q_S
    P: mu_S^P = r(t) + ERP - q_S

    Monthly: S(t+dt) = S(t)*exp[(mu_S - sigma_S^2/2)*dt + sigma_S*sqrt(dt)*Z_S]

    All values are PLACEHOLDERS -- calibrate in Phase 4.
    SOA ASOP 56 ss3.1.3, ss3.4.
    """
    equity_vol: float = 0.22
    dividend_yield: float = 0.025
    equity_risk_premium: float = 0.045
    rate_equity_correlation: float = -0.15
    initial_index_level: float = 100.0

    def __post_init__(self):
        if not (0 < self.equity_vol < 2.0):
            raise ValueError(
                "equity_vol out of plausible range (0, 2.0); got {}".format(self.equity_vol)
            )
        if not (-1.0 < self.rate_equity_correlation < 1.0):
            raise ValueError(
                "rate_equity_correlation must be in (-1, 1); got {}".format(
                    self.rate_equity_correlation
                )
            )

    @property
    def is_placeholder(self):
        return True


# ---------------------------------------------------------------------------
# 2. Hull-White 1-Factor Rate Process
# ---------------------------------------------------------------------------

class HullWhiteRateProcess:
    """Hull-White 1-factor interest rate process.

    Simulates monthly short rate paths and derives ZCB prices (1Y, 10Y).
    Use Measure.P for ALM/VaR; Measure.Q for TVOG/MCEV.
    """

    def __init__(self, params=None):
        self.params = params if params is not None else HullWhiteParams()

    def _mean_reversion_factor(self, dt):
        return np.exp(-self.params.mean_reversion_speed * dt)

    def _conditional_vol(self, dt):
        a = self.params.mean_reversion_speed
        sigma = self.params.short_rate_vol
        return sigma * np.sqrt((1 - np.exp(-2 * a * dt)) / (2 * a))

    def zcb_price(self, r_t, t, T):
        """Zero-coupon bond price P(t,T) = exp(-B*r_t) under flat curve approx."""
        a = self.params.mean_reversion_speed
        tau = T - t
        if tau <= 0:
            raise ValueError("Maturity T ({}) must exceed current time t ({})".format(T, t))
        B = (1.0 / a) * (1.0 - np.exp(-a * tau))
        return np.exp(-B * r_t)

    def _simulate_array(self, n_scenarios, T_months, measure, shocks):
        """Simulate short-rate paths into ndarray, shape (n_scenarios, T_months+1)."""
        expected_shape = (n_scenarios, T_months)
        if shocks.shape != expected_shape:
            raise ValueError(
                "rate shocks must have shape {}; got {}".format(expected_shape, shocks.shape)
            )
        dt = 1.0 / 12.0
        mf = self._mean_reversion_factor(dt)
        cv = self._conditional_vol(dt)
        p = self.params

        target_rate = p.initial_short_rate
        if measure == Measure.P:
            target_rate = p.long_run_rate_p + p.short_rate_vol * p.market_price_of_risk

        rates = np.empty((n_scenarios, T_months + 1), dtype=float)
        rates[:, 0] = p.initial_short_rate
        for month in range(T_months):
            rates[:, month + 1] = (
                rates[:, month] * mf
                + target_rate * (1.0 - mf)
                + cv * shocks[:, month]
            )
        return np.clip(rates, -0.02, 0.15)

    def simulate(self, n_scenarios, T_months, measure, seed=42):
        """Simulate monthly short-rate paths as an ESGAdapter-compatible DataFrame.

        Columns: scenario_id, month, r_short, zcb_1y, zcb_10y, measure
        Shape: n_scenarios * (T_months + 1) rows.

        SOA ASOP 56 ss3.1.3, ss3.4.
        """
        measure = _coerce_measure(measure)
        _validate_simulation_dimensions(n_scenarios, T_months)
        n_scenarios = int(n_scenarios)
        T_months = int(T_months)

        rng = np.random.default_rng(seed)
        shocks = _antithetic_normals(rng, n_scenarios, T_months)
        rates = self._simulate_array(n_scenarios, T_months, measure, shocks)

        scenario_ids, months = _month_grid(n_scenarios, T_months)
        flat_rates = rates.reshape(-1)
        times = months.astype(float) / 12.0

        zcb_1y = np.empty_like(flat_rates)
        zcb_10y = np.empty_like(flat_rates)
        for idx, (r_t, t) in enumerate(zip(flat_rates, times)):
            zcb_1y[idx] = min(self.zcb_price(float(r_t), float(t), float(t + 1.0)), 1.0)
            zcb_10y[idx] = min(self.zcb_price(float(r_t), float(t), float(t + 10.0)), 1.0)

        return pd.DataFrame({
            "scenario_id": scenario_ids,
            "month": months,
            "r_short": flat_rates,
            "zcb_1y": zcb_1y,
            "zcb_10y": zcb_10y,
            "measure": measure.value,
        })


# ---------------------------------------------------------------------------
# 3. GBM Equity Process
# ---------------------------------------------------------------------------

class GBMEquityProcess:
    """Geometric Brownian Motion equity index process.

    Measure.Q: drift = r(t) - q_S  (TVOG use)
    Measure.P: drift = r(t) + ERP - q_S  (ALM/ERM use)
    """

    def __init__(self, params=None, rate_process=None):
        self.params = params if params is not None else GBMParams()
        self.rate_process = rate_process if rate_process is not None else HullWhiteRateProcess()

    def _simulate_array(self, n_scenarios, T_months, measure, rate_paths, shocks):
        """Simulate equity paths. Returns (equity, returns) ndarrays."""
        expected_shape = (n_scenarios, T_months)
        if shocks.shape != expected_shape:
            raise ValueError(
                "equity shocks must have shape {}; got {}".format(expected_shape, shocks.shape)
            )
        rate_shape = (n_scenarios, T_months + 1)
        if rate_paths.shape != rate_shape:
            raise ValueError(
                "rate_paths must have shape {}; got {}".format(rate_shape, rate_paths.shape)
            )

        dt = 1.0 / 12.0
        sqrt_dt = np.sqrt(dt)
        p = self.params

        equity = np.empty((n_scenarios, T_months + 1), dtype=float)
        returns = np.zeros((n_scenarios, T_months + 1), dtype=float)
        equity[:, 0] = p.initial_index_level

        for month in range(T_months):
            drift = rate_paths[:, month] - p.dividend_yield
            if measure == Measure.P:
                drift = drift + p.equity_risk_premium
            log_return = (
                (drift - 0.5 * p.equity_vol ** 2) * dt
                + p.equity_vol * sqrt_dt * shocks[:, month]
            )
            gross_return = np.exp(log_return)
            equity[:, month + 1] = equity[:, month] * gross_return
            returns[:, month + 1] = gross_return - 1.0

        return equity, returns

    def simulate(self, n_scenarios, T_months, measure, rate_paths=None, seed=42):
        """Simulate monthly equity-index paths as a DataFrame.

        Columns: scenario_id, month, equity_index, equity_return_1m, measure
        Shape: n_scenarios * (T_months + 1) rows.

        SOA ASOP 56 ss3.1.3, ss3.4.
        """
        measure = _coerce_measure(measure)
        _validate_simulation_dimensions(n_scenarios, T_months)
        n_scenarios = int(n_scenarios)
        T_months = int(T_months)

        if rate_paths is None:
            rate_paths_array = np.full(
                (n_scenarios, T_months + 1),
                self.rate_process.params.initial_short_rate,
                dtype=float,
            )
        else:
            rate_paths_array = np.asarray(rate_paths, dtype=float)

        rng = np.random.default_rng(seed)
        shocks = _antithetic_normals(rng, n_scenarios, T_months)
        equity, returns = self._simulate_array(
            n_scenarios, T_months, measure, rate_paths_array, shocks
        )

        scenario_ids, months = _month_grid(n_scenarios, T_months)
        return pd.DataFrame({
            "scenario_id": scenario_ids,
            "month": months,
            "equity_index": equity.reshape(-1),
            "equity_return_1m": returns.reshape(-1),
            "measure": measure.value,
        })


# ---------------------------------------------------------------------------
# 4. ScenarioSet -- Container for combined rate + equity paths
# ---------------------------------------------------------------------------

@dataclass
class ScenarioSet:
    """Container for simulated economic scenario paths (rates + equity).

    Attributes
    ----------
    data : pd.DataFrame
        Combined scenario data.  Columns:
          scenario_id, month, r_short, zcb_1y, zcb_10y,
          equity_index, equity_return_1m, measure
    n_scenarios : int
    T_months : int
    measure : Measure
    seed : int

    SOA ASOP 56 ss3.5 -- scenario count adequacy and convergence.
    ESG_PROCESS_DOCUMENTATION.md ss6 -- specification.
    """

    data: pd.DataFrame
    n_scenarios: int
    T_months: int
    measure: Measure
    seed: int

    def path(self, scenario_id):
        """Return a single scenario path by 1-based scenario_id."""
        return self.data[self.data["scenario_id"] == scenario_id].reset_index(drop=True)

    def summary_stats(self):
        """Cross-scenario summary statistics by month.

        Returns pd.DataFrame indexed by month with columns:
          r_short_mean, r_short_p95, equity_index_mean, equity_index_p95, etc.

        Used for convergence testing (ASOP 56 ss3.5) and fan chart visualisation.
        """
        results = {}
        for col in ("r_short", "equity_index"):
            grp = self.data.groupby("month")[col]
            results[col + "_mean"] = grp.mean()
            results[col + "_std"] = grp.std()
            results[col + "_p5"] = grp.quantile(0.05)
            results[col + "_p25"] = grp.quantile(0.25)
            results[col + "_p50"] = grp.median()
            results[col + "_p75"] = grp.quantile(0.75)
            results[col + "_p95"] = grp.quantile(0.95)
        return pd.DataFrame(results)

    @classmethod
    def generate(cls, n, T_months, measure, hw_params=None, gbm_params=None, seed=42):
        """Generate correlated HW1F rate + GBM equity scenarios.

        Uses Cholesky decomposition for rate/equity correlation:
          Z_S = rho * Z_r + sqrt(1 - rho^2) * Z_indep

        Parameters
        ----------
        n : int
            Number of scenarios.
            TVOG minimum: 500 (recommended 1000).
            VaR 99.5%: 2000 (recommended 5000).
        T_months : int
            Projection horizon in months.
        measure : Measure or str
            Single measure only -- do not mix P and Q.
        hw_params : HullWhiteParams, optional
        gbm_params : GBMParams, optional
        seed : int, optional

        Returns
        -------
        ScenarioSet

        SOA ASOP 56 ss3.5 -- convergence validation.
        """
        measure = _coerce_measure(measure)
        _validate_simulation_dimensions(n, T_months)
        n = int(n)
        T_months = int(T_months)

        hw_process = HullWhiteRateProcess(hw_params)
        gbm_process = GBMEquityProcess(gbm_params, rate_process=hw_process)

        rng = np.random.default_rng(seed)
        z_rate = _antithetic_normals(rng, n, T_months)
        z_independent = _antithetic_normals(rng, n, T_months)
        rho = gbm_process.params.rate_equity_correlation
        z_equity = rho * z_rate + np.sqrt(1.0 - rho ** 2) * z_independent

        rate_paths = hw_process._simulate_array(n, T_months, measure, z_rate)
        equity_paths, equity_returns = gbm_process._simulate_array(
            n, T_months, measure, rate_paths, z_equity
        )

        scenario_ids, months = _month_grid(n, T_months)
        flat_rates = rate_paths.reshape(-1)
        times = months.astype(float) / 12.0

        zcb_1y = np.empty_like(flat_rates)
        zcb_10y = np.empty_like(flat_rates)
        for idx, (r_t, t) in enumerate(zip(flat_rates, times)):
            zcb_1y[idx] = min(hw_process.zcb_price(float(r_t), float(t), float(t + 1.0)), 1.0)
            zcb_10y[idx] = min(hw_process.zcb_price(float(r_t), float(t), float(t + 10.0)), 1.0)

        data = pd.DataFrame({
            "scenario_id": scenario_ids,
            "month": months,
            "r_short": flat_rates,
            "zcb_1y": zcb_1y,
            "zcb_10y": zcb_10y,
            "equity_index": equity_paths.reshape(-1),
            "equity_return_1m": equity_returns.reshape(-1),
            "measure": measure.value,
        })

        return cls(data=data, n_scenarios=n, T_months=T_months, measure=measure, seed=seed)


__all__ = [
    "Measure",
    "HullWhiteParams",
    "GBMParams",
    "HullWhiteRateProcess",
    "GBMEquityProcess",
    "ScenarioSet",
    "_coerce_measure",
    "_validate_simulation_dimensions",
    "_month_grid",
    "_antithetic_normals",
]
