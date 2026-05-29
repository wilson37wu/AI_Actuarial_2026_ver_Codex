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
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Dict, Optional, Tuple

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


def _coerce_date(value, field_name):
    """Return a date object or raise a descriptive error."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("{} must be an ISO date; got {!r}".format(field_name, value)) from exc


def _validate_currency_code(value, field_name):
    """Validate ISO-style three-letter currency codes used by Phase 6 metadata."""
    if not isinstance(value, str) or len(value.strip()) != 3 or not value.strip().isalpha():
        raise ValueError("{} must be a three-letter currency code; got {!r}".format(field_name, value))
    return value.strip().upper()


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
# 1b. Phase 6 Scenario Metadata and Parameter Snapshot Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalibrationSource:
    """Governed source reference for one calibration input table or quote set.

    Phase 6 Task 2 uses these records to keep scenario parameter snapshots
    traceable to curve, equity, FX, spread, and correlation data sources.
    """

    source_id: str
    source_type: str
    market: str
    currency: Optional[str]
    as_of_date: date
    provider: str
    dataset_name: str
    version: str = "illustrative"
    reliability_tier: str = "educational_placeholder"
    approval_status: str = "draft"
    notes: str = ""

    def __post_init__(self):
        if not str(self.source_id).strip():
            raise ValueError("source_id is required")
        if not str(self.source_type).strip():
            raise ValueError("source_type is required")
        if not str(self.market).strip():
            raise ValueError("market is required")
        if self.currency is not None:
            object.__setattr__(self, "currency", _validate_currency_code(self.currency, "currency"))
        object.__setattr__(self, "as_of_date", _coerce_date(self.as_of_date, "as_of_date"))
        if not str(self.provider).strip():
            raise ValueError("provider is required")
        if not str(self.dataset_name).strip():
            raise ValueError("dataset_name is required")

    def to_dict(self):
        result = asdict(self)
        result["as_of_date"] = self.as_of_date.isoformat()
        return result


@dataclass(frozen=True)
class ParameterSnapshot:
    """Auditable ESG parameter set used to generate one scenario package.

    The snapshot separates model run metadata from calibrated parameter values
    so downstream TVOG, ALM, VaR/ES, and reporting outputs can reference the
    exact assumption basis used for a scenario set.
    """

    snapshot_id: str
    calibration_date: date
    measure: Measure
    base_currency: str
    parameters: Dict[str, float]
    sources: Tuple[CalibrationSource, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    owner: str = "Model Development"
    approver: Optional[str] = None
    approval_status: str = "draft"
    model_equation_refs: Tuple[str, ...] = (
        "HullWhiteRateProcess._simulate_array",
        "GBMEquityProcess._simulate_array",
    )
    discretisation: str = "monthly time step with HW1F conditional normal rates and GBM equity returns"
    limitations_id: str = "EDU-ESG-LIMITATIONS"
    is_placeholder: bool = True

    def __post_init__(self):
        if not str(self.snapshot_id).strip():
            raise ValueError("snapshot_id is required")
        object.__setattr__(self, "calibration_date", _coerce_date(self.calibration_date, "calibration_date"))
        object.__setattr__(self, "measure", _coerce_measure(self.measure))
        object.__setattr__(self, "base_currency", _validate_currency_code(self.base_currency, "base_currency"))
        if not self.parameters:
            raise ValueError("parameters must not be empty")
        for name, value in self.parameters.items():
            if not str(name).strip():
                raise ValueError("parameter names must be non-empty")
            if not np.isfinite(float(value)):
                raise ValueError("parameter {!r} must be finite; got {!r}".format(name, value))
        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("sources must have unique source_id values")
        if not str(self.owner).strip():
            raise ValueError("owner is required")
        if not str(self.approval_status).strip():
            raise ValueError("approval_status is required")

    @classmethod
    def from_process_params(
        cls,
        measure,
        base_currency="CNY",
        calibration_date=None,
        hw_params=None,
        gbm_params=None,
        snapshot_id=None,
    ):
        """Create a Phase 6 snapshot from current HW1F and GBM parameter dataclasses."""
        measure = _coerce_measure(measure)
        base_currency = _validate_currency_code(base_currency, "base_currency")
        calibration_date = _coerce_date(calibration_date or date.today(), "calibration_date")
        hw_params = hw_params if hw_params is not None else HullWhiteParams()
        gbm_params = gbm_params if gbm_params is not None else GBMParams()
        snapshot_id = snapshot_id or "ps-{}-{}-{}".format(
            calibration_date.isoformat().replace("-", ""),
            base_currency,
            measure.value,
        )
        source = CalibrationSource(
            source_id="SRC-PLACEHOLDER-{}".format(base_currency),
            source_type="parameter_placeholder",
            market=base_currency,
            currency=base_currency,
            as_of_date=calibration_date,
            provider="par_model_v2 default parameter dataclasses",
            dataset_name="HullWhiteParams and GBMParams defaults",
            notes="Educational placeholder until market calibration interfaces are implemented.",
        )
        parameters = {
            "rate.hw1f.mean_reversion_speed": hw_params.mean_reversion_speed,
            "rate.hw1f.short_rate_vol": hw_params.short_rate_vol,
            "rate.hw1f.initial_short_rate": hw_params.initial_short_rate,
            "rate.hw1f.long_run_rate_p": hw_params.long_run_rate_p,
            "rate.hw1f.market_price_of_risk": hw_params.market_price_of_risk,
            "rate.hw1f.cbirc_rate_cap": hw_params.cbirc_rate_cap,
            "equity.gbm.equity_vol": gbm_params.equity_vol,
            "equity.gbm.dividend_yield": gbm_params.dividend_yield,
            "equity.gbm.equity_risk_premium": gbm_params.equity_risk_premium,
            "equity.gbm.rate_equity_correlation": gbm_params.rate_equity_correlation,
            "equity.gbm.initial_index_level": gbm_params.initial_index_level,
        }
        return cls(
            snapshot_id=snapshot_id,
            calibration_date=calibration_date,
            measure=measure,
            base_currency=base_currency,
            parameters=parameters,
            sources=(source,),
            is_placeholder=bool(hw_params.is_placeholder or gbm_params.is_placeholder),
        )

    def to_dict(self):
        result = asdict(self)
        result["calibration_date"] = self.calibration_date.isoformat()
        result["created_at"] = self.created_at.isoformat()
        result["measure"] = self.measure.value
        result["sources"] = [source.to_dict() for source in self.sources]
        result["model_equation_refs"] = list(self.model_equation_refs)
        return result


@dataclass(frozen=True)
class ScenarioMetadata:
    """Scenario-set level metadata required by the Phase 6 schema contract."""

    scenario_set_id: str
    model_version: str
    measure: Measure
    base_currency: str
    valuation_date: date
    projection_months: int
    time_step_months: int
    n_scenarios: int
    seed_policy: str
    parameter_snapshot_id: str
    generator_name: str
    generator_version: str
    limitations_id: str
    parameter_snapshot: Optional[ParameterSnapshot] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    reporting_purpose: str = "educational"

    def __post_init__(self):
        if not str(self.scenario_set_id).strip():
            raise ValueError("scenario_set_id is required")
        if not str(self.model_version).strip():
            raise ValueError("model_version is required")
        object.__setattr__(self, "measure", _coerce_measure(self.measure))
        object.__setattr__(self, "base_currency", _validate_currency_code(self.base_currency, "base_currency"))
        object.__setattr__(self, "valuation_date", _coerce_date(self.valuation_date, "valuation_date"))
        if int(self.projection_months) != self.projection_months or self.projection_months < 0:
            raise ValueError("projection_months must be a non-negative integer")
        if int(self.time_step_months) != self.time_step_months or self.time_step_months <= 0:
            raise ValueError("time_step_months must be a positive integer")
        if int(self.n_scenarios) != self.n_scenarios or self.n_scenarios <= 0:
            raise ValueError("n_scenarios must be a positive integer")
        if not str(self.seed_policy).strip():
            raise ValueError("seed_policy is required")
        if not str(self.parameter_snapshot_id).strip():
            raise ValueError("parameter_snapshot_id is required")
        if not str(self.generator_name).strip():
            raise ValueError("generator_name is required")
        if not str(self.generator_version).strip():
            raise ValueError("generator_version is required")
        if not str(self.limitations_id).strip():
            raise ValueError("limitations_id is required")
        if self.parameter_snapshot is not None:
            if self.parameter_snapshot.snapshot_id != self.parameter_snapshot_id:
                raise ValueError("parameter_snapshot_id must match parameter_snapshot.snapshot_id")
            if self.parameter_snapshot.measure != self.measure:
                raise ValueError("metadata measure must match parameter snapshot measure")
            if self.parameter_snapshot.base_currency != self.base_currency:
                raise ValueError("metadata base_currency must match parameter snapshot base_currency")

    @classmethod
    def from_generation(
        cls,
        n_scenarios,
        T_months,
        measure,
        seed,
        parameter_snapshot,
        scenario_set_id=None,
        model_version="v1.0.0-dev",
        base_currency="CNY",
        valuation_date=None,
        generator_name="ScenarioSet.generate",
        generator_version="phase6-metadata-v1",
        limitations_id="EDU-ESG-LIMITATIONS",
    ):
        """Build metadata for a generated v1-compatible ScenarioSet."""
        measure = _coerce_measure(measure)
        valuation_date = _coerce_date(valuation_date or date.today(), "valuation_date")
        scenario_set_id = scenario_set_id or "scen-{}-{}-{}-{}".format(
            valuation_date.isoformat().replace("-", ""),
            _validate_currency_code(base_currency, "base_currency"),
            measure.value,
            seed,
        )
        return cls(
            scenario_set_id=scenario_set_id,
            model_version=model_version,
            measure=measure,
            base_currency=base_currency,
            valuation_date=valuation_date,
            projection_months=int(T_months),
            time_step_months=1,
            n_scenarios=int(n_scenarios),
            seed_policy="fixed-seed:{}".format(seed),
            parameter_snapshot_id=parameter_snapshot.snapshot_id,
            generator_name=generator_name,
            generator_version=generator_version,
            limitations_id=limitations_id,
            parameter_snapshot=parameter_snapshot,
        )

    def to_dict(self):
        result = asdict(self)
        result["measure"] = self.measure.value
        result["valuation_date"] = self.valuation_date.isoformat()
        result["created_at"] = self.created_at.isoformat()
        if self.parameter_snapshot is not None:
            result["parameter_snapshot"] = self.parameter_snapshot.to_dict()
        return result


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
    metadata : ScenarioMetadata, optional
        Governed scenario-set metadata added in Phase 6.
    parameter_snapshot : ParameterSnapshot, optional
        Parameter snapshot linked from metadata.

    SOA ASOP 56 ss3.5 -- scenario count adequacy and convergence.
    ESG_PROCESS_DOCUMENTATION.md ss6 -- specification.
    """

    data: pd.DataFrame
    n_scenarios: int
    T_months: int
    measure: Measure
    seed: int
    metadata: Optional[ScenarioMetadata] = None
    parameter_snapshot: Optional[ParameterSnapshot] = None

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
    def generate(
        cls,
        n,
        T_months,
        measure,
        hw_params=None,
        gbm_params=None,
        seed=42,
        scenario_set_id=None,
        model_version="v1.0.0-dev",
        base_currency="CNY",
        valuation_date=None,
        parameter_snapshot=None,
    ):
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
        scenario_set_id : str, optional
            Stable metadata identifier for this generated scenario package.
        model_version : str, optional
            Model version or commit identifier recorded in metadata.
        base_currency : str, optional
            Reporting currency for the v1-compatible wide view.
        valuation_date : date or str, optional
            Scenario time-0 valuation date.
        parameter_snapshot : ParameterSnapshot, optional
            Auditable parameter snapshot.  If omitted, a placeholder snapshot
            is derived from the supplied HW1F and GBM parameter dataclasses.

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
        if parameter_snapshot is None:
            parameter_snapshot = ParameterSnapshot.from_process_params(
                measure=measure,
                base_currency=base_currency,
                calibration_date=valuation_date,
                hw_params=hw_process.params,
                gbm_params=gbm_process.params,
            )

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
        metadata = ScenarioMetadata.from_generation(
            n_scenarios=n,
            T_months=T_months,
            measure=measure,
            seed=seed,
            parameter_snapshot=parameter_snapshot,
            scenario_set_id=scenario_set_id,
            model_version=model_version,
            base_currency=base_currency,
            valuation_date=valuation_date,
        )

        return cls(
            data=data,
            n_scenarios=n,
            T_months=T_months,
            measure=measure,
            seed=seed,
            metadata=metadata,
            parameter_snapshot=parameter_snapshot,
        )


__all__ = [
    "Measure",
    "CalibrationSource",
    "ParameterSnapshot",
    "ScenarioMetadata",
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
