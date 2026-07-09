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
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
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


class MeasureEnforcementError(ValueError):
    """Raised when a simulation path is asked to run under an unsupported measure.

    Enforces the P (real-world) / Q (risk-neutral) segregation contract at
    runtime. Mixing measures is a critical actuarial error that invalidates both
    VaR/ES (P) and TVOG/MCEV (Q) outputs. Closes governance gate G-05 / risk
    MR-004.

    SOA ASOP 56 ss3.1.3 (measure appropriateness for model purpose);
    IA TAS M ss3.4 (consistency and segregation of bases).
    """


def _enforce_simulation_measure(process, measure):
    """Runtime guard: coerce and enforce the measure for a simulation path.

    Unlike the soft ``_coerce_measure`` helper -- which only checks that the
    value is a member of the Measure enum -- this guard additionally validates
    the requested measure against the measures the calling process is permitted
    to run under (its ``SUPPORTED_MEASURES``). It is the single runtime
    entry-point used by every ``simulate()`` / ``generate()`` path, so the P/Q
    contract cannot be silently bypassed.

    ``process`` may be an instance, a class (for classmethods), or a string
    label.

    SOA ASOP 56 ss3.1.3; IA TAS M ss3.4.
    """
    if isinstance(process, type):
        label = process.__name__
        supported = getattr(process, "SUPPORTED_MEASURES", (Measure.P, Measure.Q))
    elif isinstance(process, str):
        label = process
        supported = (Measure.P, Measure.Q)
    else:
        label = type(process).__name__
        supported = getattr(process, "SUPPORTED_MEASURES", (Measure.P, Measure.Q))

    measure = _coerce_measure(measure)
    supported = tuple(_coerce_measure(m) for m in supported)
    if not supported:
        raise MeasureEnforcementError(
            "{}: no supported measures are declared; cannot run simulation "
            "(SOA ASOP 56 ss3.1.3; IA TAS M ss3.4).".format(label)
        )
    if measure not in supported:
        raise MeasureEnforcementError(
            "{}: measure {!r} is not permitted; supported measures are {}. "
            "Mixing P (real-world) and Q (risk-neutral) bases invalidates "
            "VaR/ES and TVOG/MCEV outputs "
            "(SOA ASOP 56 ss3.1.3; IA TAS M ss3.4).".format(
                label, measure.value, [m.value for m in supported]
            )
        )
    return measure


def _assert_output_measure(frame, measure, process_label):
    """Runtime post-condition: every output row must carry the requested measure.

    Guards against silent mis-stamping inside a simulation path. Returns the
    frame unchanged when the stamp is uniform and matches ``measure``.

    SOA ASOP 56 ss3.1.3; IA TAS M ss3.4.
    """
    measure = _coerce_measure(measure)
    if "measure" not in getattr(frame, "columns", ()):
        raise MeasureEnforcementError(
            "{}: simulation output is missing the 'measure' column "
            "(SOA ASOP 56 ss3.1.3; IA TAS M ss3.4).".format(process_label)
        )
    stamped = set(frame["measure"].dropna().unique())
    if stamped != {measure.value}:
        raise MeasureEnforcementError(
            "{}: output measure stamp {} does not match the requested measure "
            "{!r} (SOA ASOP 56 ss3.1.3; IA TAS M ss3.4).".format(
                process_label, sorted(stamped), measure.value
            )
        )
    return frame


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


def _require_text(value, field_name):
    """Return a stripped string or raise if the field is blank."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} is required".format(field_name))
    return value.strip()


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
    short_rate_floor: Optional[float] = -0.020
    short_rate_ceiling: Optional[float] = 0.150

    def __post_init__(self):
        if self.mean_reversion_speed <= 0:
            raise ValueError(
                "mean_reversion_speed must be positive; got {}".format(self.mean_reversion_speed)
            )
        if self.short_rate_vol <= 0:
            raise ValueError(
                "short_rate_vol must be positive; got {}".format(self.short_rate_vol)
            )
        if self.short_rate_floor is not None and self.short_rate_ceiling is not None:
            if float(self.short_rate_floor) >= float(self.short_rate_ceiling):
                raise ValueError("short_rate_floor must be below short_rate_ceiling")

    @property
    def is_placeholder(self):
        return True


@dataclass
class G2PlusParams:
    """Parameters for a two-factor Gaussian G2++ interest-rate prototype.

    r(t) = phi(t) + x(t) + y(t)
    dx(t) = -a*x(t) dt + sigma*dW_x(t)
    dy(t) = -b*y(t) dt + eta*dW_y(t), corr(dW_x, dW_y) = rho

    Phase 7 uses this as an educational prototype for yield-curve twists and
    separate short / long factor volatility. Parameters are placeholders until
    swaption surface calibration is implemented.
    """

    mean_reversion_x: float = 0.10
    mean_reversion_y: float = 0.35
    vol_x: float = 0.010
    vol_y: float = 0.006
    factor_correlation: float = -0.70
    initial_x: float = 0.0
    initial_y: float = 0.0
    long_run_rate_p: float = 0.025
    market_price_of_risk_x: float = -0.10
    market_price_of_risk_y: float = -0.05
    short_rate_floor: Optional[float] = -0.020
    short_rate_ceiling: Optional[float] = 0.150

    def __post_init__(self):
        if self.mean_reversion_x <= 0:
            raise ValueError("mean_reversion_x must be positive")
        if self.mean_reversion_y <= 0:
            raise ValueError("mean_reversion_y must be positive")
        if self.vol_x <= 0:
            raise ValueError("vol_x must be positive")
        if self.vol_y <= 0:
            raise ValueError("vol_y must be positive")
        if not (-1.0 < self.factor_correlation < 1.0):
            raise ValueError("factor_correlation must be in (-1, 1)")
        if self.short_rate_floor is not None and self.short_rate_ceiling is not None:
            if float(self.short_rate_floor) >= float(self.short_rate_ceiling):
                raise ValueError("short_rate_floor must be below short_rate_ceiling")

    @property
    def is_placeholder(self):
        return True


@dataclass(frozen=True)
class RiskFreeCurve:
    """Continuously compounded risk-free zero curve for HW1F initial fitting.

    Phase 7 uses this small curve object as the explicit market input to the
    Hull-White process. Negative zero rates are allowed so JPY/EUR-style low
    rate examples can be represented without shifting the process.
    """

    tenors_years: Tuple[float, ...]
    zero_rates: Tuple[float, ...]
    currency: str = "CNY"
    market: str = "CN"
    valuation_date: date = field(default_factory=date.today)
    curve_id: str = "CURVE-EDU-PLACEHOLDER"
    source_id: str = "SRC-PLACEHOLDER-CURVE"
    compounding: str = "continuous"

    def __post_init__(self):
        tenors = tuple(float(value) for value in self.tenors_years)
        rates = tuple(float(value) for value in self.zero_rates)
        if len(tenors) != len(rates):
            raise ValueError("tenors_years and zero_rates must have the same length")
        if len(tenors) < 2:
            raise ValueError("RiskFreeCurve requires at least two tenor points")
        if any(not np.isfinite(value) for value in tenors + rates):
            raise ValueError("RiskFreeCurve tenors and rates must be finite")
        if any(value < 0.0 for value in tenors):
            raise ValueError("RiskFreeCurve tenors must be non-negative")
        if tuple(sorted(tenors)) != tenors or len(set(tenors)) != len(tenors):
            raise ValueError("RiskFreeCurve tenors must be strictly increasing")
        if any(value < -0.10 or value > 1.00 for value in rates):
            raise ValueError("RiskFreeCurve zero_rates must be within [-0.10, 1.00]")

        object.__setattr__(self, "tenors_years", tenors)
        object.__setattr__(self, "zero_rates", rates)
        object.__setattr__(self, "currency", _validate_currency_code(self.currency, "currency"))
        object.__setattr__(self, "market", _require_text(self.market, "market").upper())
        object.__setattr__(self, "valuation_date", _coerce_date(self.valuation_date, "valuation_date"))
        object.__setattr__(self, "curve_id", _require_text(self.curve_id, "curve_id"))
        object.__setattr__(self, "source_id", _require_text(self.source_id, "source_id"))
        compounding = _require_text(self.compounding, "compounding").lower()
        if compounding != "continuous":
            raise ValueError("RiskFreeCurve currently supports continuous compounding only")
        object.__setattr__(self, "compounding", compounding)

    @classmethod
    def flat(
        cls,
        rate,
        currency="CNY",
        market="CN",
        valuation_date=None,
        curve_id=None,
        source_id=None,
        max_tenor_years=30.0,
    ):
        """Return a flat continuously compounded curve."""
        valuation_date = _coerce_date(valuation_date or date.today(), "valuation_date")
        currency = _validate_currency_code(currency, "currency")
        curve_id = curve_id or "CURVE-FLAT-{}-{}".format(
            currency,
            valuation_date.isoformat().replace("-", ""),
        )
        source_id = source_id or "SRC-FLAT-{}".format(currency)
        return cls(
            tenors_years=(0.0, float(max_tenor_years)),
            zero_rates=(float(rate), float(rate)),
            currency=currency,
            market=market,
            valuation_date=valuation_date,
            curve_id=curve_id,
            source_id=source_id,
        )

    def zero_rate(self, tenor_years):
        """Linearly interpolate the continuously compounded zero rate."""
        tenor = float(tenor_years)
        if tenor < 0:
            raise ValueError("tenor_years must be non-negative; got {}".format(tenor_years))
        return float(np.interp(tenor, self.tenors_years, self.zero_rates))

    def discount_factor(self, tenor_years):
        """Return P(0,T) using continuous compounding."""
        tenor = float(tenor_years)
        if tenor < 0:
            raise ValueError("tenor_years must be non-negative; got {}".format(tenor_years))
        if tenor == 0:
            return 1.0
        return float(np.exp(-self.zero_rate(tenor) * tenor))

    def instantaneous_forward(self, tenor_years):
        """Approximate f(0,t) from the zero curve by piecewise secants."""
        tenor = max(float(tenor_years), 0.0)
        tenors = np.asarray(self.tenors_years, dtype=float)
        rates = np.asarray(self.zero_rates, dtype=float)
        zero_times_tenor = rates * tenors

        if tenor <= tenors[0]:
            left, right = 0, 1
        elif tenor >= tenors[-1]:
            left, right = len(tenors) - 2, len(tenors) - 1
        else:
            right = int(np.searchsorted(tenors, tenor, side="right"))
            left = right - 1
        width = tenors[right] - tenors[left]
        return float((zero_times_tenor[right] - zero_times_tenor[left]) / width)

    def forward_rate(self, start_years, end_years):
        """Return the continuously compounded forward rate over [start, end]."""
        start = float(start_years)
        end = float(end_years)
        if start < 0 or end < 0:
            raise ValueError("forward tenors must be non-negative")
        if end <= start:
            raise ValueError("end_years must exceed start_years")
        log_df_start = -self.zero_rate(start) * start
        log_df_end = -self.zero_rate(end) * end
        return float((log_df_start - log_df_end) / (end - start))

    def parallel_shift(self, shift):
        """Return a curve with all zero rates shifted by a decimal rate amount."""
        shift = float(shift)
        if not np.isfinite(shift):
            raise ValueError("shift must be finite")
        return RiskFreeCurve(
            tenors_years=self.tenors_years,
            zero_rates=tuple(rate + shift for rate in self.zero_rates),
            currency=self.currency,
            market=self.market,
            valuation_date=self.valuation_date,
            curve_id="{}-SHIFT-{:+.0f}BP".format(self.curve_id, shift * 10000.0),
            source_id=self.source_id,
            compounding=self.compounding,
        )

    def to_dict(self):
        return {
            "curve_id": self.curve_id,
            "source_id": self.source_id,
            "market": self.market,
            "currency": self.currency,
            "valuation_date": self.valuation_date.isoformat(),
            "compounding": self.compounding,
            "tenors_years": list(self.tenors_years),
            "zero_rates": list(self.zero_rates),
        }


_STARTER_CURVE_FIXTURE_PATH = Path(__file__).with_name("fixtures").joinpath(
    "risk_free_curves.json"
)
_STARTER_CURVE_RECORDS = None


def _load_starter_curve_records():
    global _STARTER_CURVE_RECORDS
    if _STARTER_CURVE_RECORDS is None:
        with _STARTER_CURVE_FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            raw_records = json.load(fixture_file)
        _STARTER_CURVE_RECORDS = {
            _validate_currency_code(record["currency"], "currency"): record
            for record in raw_records["curves"]
        }
    return _STARTER_CURVE_RECORDS


def available_starter_curve_currencies():
    """Return currencies covered by the Phase 7 starter risk-free curves."""
    return tuple(sorted(_load_starter_curve_records()))


def starter_risk_free_curve(currency, valuation_date=None):
    """Return an illustrative Phase 7 starter risk-free curve fixture.

    The fixtures are educational placeholders, not production market data. They
    provide stable multi-currency curve shapes for USD, EUR, HKD, CNY, and JPY
    development, validation, and documentation examples.
    """
    currency = _validate_currency_code(currency, "currency")
    records = _load_starter_curve_records()
    if currency not in records:
        raise KeyError(
            "no Phase 7 starter curve fixture for {}; available currencies are {}".format(
                currency,
                ", ".join(available_starter_curve_currencies()),
            )
        )
    record = records[currency]
    as_of = _coerce_date(
        valuation_date or record["valuation_date"],
        "valuation_date",
    )
    date_token = as_of.isoformat().replace("-", "")
    return RiskFreeCurve(
        tenors_years=tuple(record["tenors_years"]),
        zero_rates=tuple(record["zero_rates"]),
        currency=record["currency"],
        market=record["market"],
        valuation_date=as_of,
        curve_id="{}-{}".format(record["curve_id_prefix"], date_token),
        source_id=record["source_id"],
        compounding=record.get("compounding", "continuous"),
    )


def default_phase7_starter_curves(valuation_date=None):
    """Return all Phase 7 starter risk-free curve fixtures keyed by currency."""
    return {
        currency: starter_risk_free_curve(currency, valuation_date=valuation_date)
        for currency in available_starter_curve_currencies()
    }


@dataclass(frozen=True)
class YieldCurveValidationCheck:
    """Single yield-curve validation check result."""

    check_id: str
    passed: bool
    severity: str
    message: str
    observed_value: Optional[float] = None
    threshold: Optional[float] = None

    def __post_init__(self):
        object.__setattr__(self, "check_id", _require_text(self.check_id, "check_id"))
        object.__setattr__(self, "severity", _require_text(self.severity, "severity").upper())
        object.__setattr__(self, "message", _require_text(self.message, "message"))
        if self.observed_value is not None and not np.isfinite(float(self.observed_value)):
            raise ValueError("observed_value must be finite")
        if self.threshold is not None and not np.isfinite(float(self.threshold)):
            raise ValueError("threshold must be finite")

    def to_dict(self):
        return {
            "check_id": self.check_id,
            "passed": bool(self.passed),
            "severity": self.severity,
            "message": self.message,
            "observed_value": self.observed_value,
            "threshold": self.threshold,
        }


@dataclass(frozen=True)
class YieldCurveValidationReport:
    """Validation report for Phase 7 risk-free curves and generated rate paths."""

    curve_id: str
    currency: str
    valuation_date: date
    passed: bool
    checks: Tuple[YieldCurveValidationCheck, ...]
    diagnostics: Dict[str, float]

    def __post_init__(self):
        object.__setattr__(self, "curve_id", _require_text(self.curve_id, "curve_id"))
        object.__setattr__(self, "currency", _validate_currency_code(self.currency, "currency"))
        object.__setattr__(self, "valuation_date", _coerce_date(self.valuation_date, "valuation_date"))
        if not self.checks:
            raise ValueError("checks must not be empty")
        for key, value in self.diagnostics.items():
            if not str(key).strip():
                raise ValueError("diagnostic keys must be non-empty")
            if not np.isfinite(float(value)):
                raise ValueError("diagnostic {!r} must be finite".format(key))

    def failed_checks(self):
        return tuple(check for check in self.checks if not check.passed)

    def to_dict(self):
        return {
            "curve_id": self.curve_id,
            "currency": self.currency,
            "valuation_date": self.valuation_date.isoformat(),
            "passed": bool(self.passed),
            "checks": [check.to_dict() for check in self.checks],
            "diagnostics": dict(self.diagnostics),
        }


class YieldCurveValidator:
    """Phase 7 validator for risk-free curve inputs and simulated rate outputs.

    The validator is intentionally model-agnostic: it checks curve discount
    factors and forwards, confirms parallel stress monotonicity, and optionally
    validates generated HW1F/G2++ path columns including negative-rate evidence.
    """

    REQUIRED_PATH_COLUMNS = ("month", "r_short", "zcb_1y", "zcb_10y")

    def __init__(
        self,
        min_forward_rate=-0.10,
        max_forward_rate=1.00,
        max_forward_jump=0.10,
        stress_shift=0.01,
    ):
        self.min_forward_rate = float(min_forward_rate)
        self.max_forward_rate = float(max_forward_rate)
        self.max_forward_jump = float(max_forward_jump)
        self.stress_shift = float(stress_shift)
        for name, value in (
            ("min_forward_rate", self.min_forward_rate),
            ("max_forward_rate", self.max_forward_rate),
            ("max_forward_jump", self.max_forward_jump),
            ("stress_shift", self.stress_shift),
        ):
            if not np.isfinite(value):
                raise ValueError("{} must be finite".format(name))
        if self.min_forward_rate >= self.max_forward_rate:
            raise ValueError("min_forward_rate must be below max_forward_rate")
        if self.max_forward_jump <= 0:
            raise ValueError("max_forward_jump must be positive")
        if self.stress_shift <= 0:
            raise ValueError("stress_shift must be positive")

    def validate(self, curve, scenario_data=None, require_negative_rate_evidence=False):
        """Return a report covering curve shape, stresses, and optional paths."""
        if not isinstance(curve, RiskFreeCurve):
            raise TypeError("curve must be a RiskFreeCurve")

        checks = []
        diagnostics = {}
        tenors = np.asarray(curve.tenors_years, dtype=float)
        dfs = np.asarray([curve.discount_factor(tenor) for tenor in tenors], dtype=float)
        forward_rates = np.asarray(
            [
                curve.forward_rate(float(start), float(end))
                for start, end in zip(tenors[:-1], tenors[1:])
            ],
            dtype=float,
        )

        diagnostics["min_discount_factor"] = float(np.min(dfs))
        diagnostics["max_discount_factor"] = float(np.max(dfs))
        diagnostics["min_forward_rate"] = float(np.min(forward_rates))
        diagnostics["max_forward_rate"] = float(np.max(forward_rates))
        forward_jumps = np.abs(np.diff(forward_rates)) if len(forward_rates) > 1 else np.array([0.0])
        diagnostics["max_forward_jump"] = float(np.max(forward_jumps))

        checks.append(YieldCurveValidationCheck(
            "YC-DF-POSITIVE",
            bool(np.all(np.isfinite(dfs)) and np.all(dfs > 0.0)),
            "ERROR",
            "Discount factors must be finite and strictly positive.",
            observed_value=diagnostics["min_discount_factor"],
            threshold=0.0,
        ))
        checks.append(YieldCurveValidationCheck(
            "YC-FWD-RANGE",
            bool(
                np.all(np.isfinite(forward_rates))
                and np.all(forward_rates >= self.min_forward_rate)
                and np.all(forward_rates <= self.max_forward_rate)
            ),
            "ERROR",
            "Adjacent tenor forward rates must stay inside configured bounds.",
            observed_value=max(
                abs(diagnostics["min_forward_rate"]),
                abs(diagnostics["max_forward_rate"]),
            ),
            threshold=max(abs(self.min_forward_rate), abs(self.max_forward_rate)),
        ))
        checks.append(YieldCurveValidationCheck(
            "YC-FWD-SMOOTHNESS",
            bool(np.all(forward_jumps <= self.max_forward_jump)),
            "WARNING",
            "Adjacent forward-rate jumps should be explainable by the curve source.",
            observed_value=diagnostics["max_forward_jump"],
            threshold=self.max_forward_jump,
        ))

        up_curve = curve.parallel_shift(self.stress_shift)
        down_curve = curve.parallel_shift(-self.stress_shift)
        positive_tenors = tenors[tenors > 0.0]
        base_stress_dfs = np.asarray([curve.discount_factor(tenor) for tenor in positive_tenors])
        up_dfs = np.asarray([up_curve.discount_factor(tenor) for tenor in positive_tenors])
        down_dfs = np.asarray([down_curve.discount_factor(tenor) for tenor in positive_tenors])
        diagnostics["up_stress_max_df_change"] = float(np.max(up_dfs - base_stress_dfs))
        diagnostics["down_stress_min_df_change"] = float(np.min(down_dfs - base_stress_dfs))
        checks.append(YieldCurveValidationCheck(
            "YC-STRESS-MONOTONIC",
            bool(np.all(up_dfs < base_stress_dfs) and np.all(down_dfs > base_stress_dfs)),
            "ERROR",
            "Positive rate shocks must lower discount factors and negative shocks must raise them.",
            observed_value=max(
                diagnostics["up_stress_max_df_change"],
                -diagnostics["down_stress_min_df_change"],
            ),
            threshold=0.0,
        ))

        if scenario_data is not None:
            path_checks, path_diagnostics = self._validate_paths(
                scenario_data,
                require_negative_rate_evidence=require_negative_rate_evidence,
            )
            checks.extend(path_checks)
            diagnostics.update(path_diagnostics)

        passed = all(check.passed or check.severity != "ERROR" for check in checks)
        return YieldCurveValidationReport(
            curve_id=curve.curve_id,
            currency=curve.currency,
            valuation_date=curve.valuation_date,
            passed=passed,
            checks=tuple(checks),
            diagnostics=diagnostics,
        )

    def _validate_paths(self, scenario_data, require_negative_rate_evidence=False):
        frame = pd.DataFrame(scenario_data)
        checks = []
        diagnostics = {}
        missing = [column for column in self.REQUIRED_PATH_COLUMNS if column not in frame.columns]
        checks.append(YieldCurveValidationCheck(
            "YC-PATH-COLUMNS",
            not missing,
            "ERROR",
            "Scenario rate paths must include month, short-rate, and discount-factor columns.",
            observed_value=float(len(missing)),
            threshold=0.0,
        ))
        if missing:
            return tuple(checks), diagnostics

        zcb_values = frame[["zcb_1y", "zcb_10y"]].to_numpy(dtype=float)
        rates = frame["r_short"].to_numpy(dtype=float)
        diagnostics["path_min_short_rate"] = float(np.min(rates))
        diagnostics["path_max_short_rate"] = float(np.max(rates))
        diagnostics["path_min_discount_factor"] = float(np.min(zcb_values))
        diagnostics["path_max_discount_factor"] = float(np.max(zcb_values))
        diagnostics["negative_rate_row_count"] = float(np.sum(rates < 0.0))
        diagnostics["above_par_discount_factor_count"] = float(np.sum(zcb_values > 1.0))

        checks.append(YieldCurveValidationCheck(
            "YC-PATH-DF-FINITE",
            bool(np.all(np.isfinite(zcb_values)) and np.all(zcb_values > 0.0)),
            "ERROR",
            "Path discount-factor outputs must be finite and strictly positive.",
            observed_value=diagnostics["path_min_discount_factor"],
            threshold=0.0,
        ))
        checks.append(YieldCurveValidationCheck(
            "YC-PATH-RATE-FINITE",
            bool(np.all(np.isfinite(rates))),
            "ERROR",
            "Path short rates must be finite.",
            observed_value=diagnostics["path_max_short_rate"],
        ))
        if require_negative_rate_evidence:
            checks.append(YieldCurveValidationCheck(
                "YC-PATH-NEGATIVE-RATE-EVIDENCE",
                bool(
                    diagnostics["negative_rate_row_count"] > 0.0
                    and diagnostics["above_par_discount_factor_count"] > 0.0
                ),
                "ERROR",
                "Negative-rate validation requires negative short rates and uncapped above-par discount factors.",
                observed_value=diagnostics["above_par_discount_factor_count"],
                threshold=1.0,
            ))
        return tuple(checks), diagnostics


@dataclass(frozen=True)
class MartingaleEvidenceCheck:
    """Single Q-measure martingale evidence check result."""

    check_id: str
    passed: bool
    severity: str
    message: str
    observed_value: Optional[float] = None
    threshold: Optional[float] = None

    def __post_init__(self):
        object.__setattr__(self, "check_id", _require_text(self.check_id, "check_id"))
        object.__setattr__(self, "severity", _require_text(self.severity, "severity").upper())
        object.__setattr__(self, "message", _require_text(self.message, "message"))
        if self.observed_value is not None and not np.isfinite(float(self.observed_value)):
            raise ValueError("observed_value must be finite")
        if self.threshold is not None and not np.isfinite(float(self.threshold)):
            raise ValueError("threshold must be finite")

    def to_dict(self):
        return {
            "check_id": self.check_id,
            "passed": bool(self.passed),
            "severity": self.severity,
            "message": self.message,
            "observed_value": self.observed_value,
            "threshold": self.threshold,
        }


@dataclass(frozen=True)
class MartingaleEvidenceReport:
    """JSON-ready Q-measure martingale evidence report for discount factors."""

    curve_id: str
    currency: str
    valuation_date: date
    measure: Measure
    passed: bool
    checks: Tuple[MartingaleEvidenceCheck, ...]
    diagnostics: Dict[str, float]

    def __post_init__(self):
        object.__setattr__(self, "curve_id", _require_text(self.curve_id, "curve_id"))
        object.__setattr__(self, "currency", _validate_currency_code(self.currency, "currency"))
        object.__setattr__(self, "valuation_date", _coerce_date(self.valuation_date, "valuation_date"))
        object.__setattr__(self, "measure", _coerce_measure(self.measure))
        if not self.checks:
            raise ValueError("checks must not be empty")
        for key, value in self.diagnostics.items():
            if not str(key).strip():
                raise ValueError("diagnostic keys must be non-empty")
            if not np.isfinite(float(value)):
                raise ValueError("diagnostic {!r} must be finite".format(key))

    def failed_checks(self):
        return tuple(check for check in self.checks if not check.passed)

    def to_dict(self):
        return {
            "curve_id": self.curve_id,
            "currency": self.currency,
            "valuation_date": self.valuation_date.isoformat(),
            "measure": self.measure.value,
            "passed": bool(self.passed),
            "checks": [check.to_dict() for check in self.checks],
            "diagnostics": dict(self.diagnostics),
        }


class QMeasureMartingaleValidator:
    """Validate Q-measure discount-factor martingale evidence.

    For each supported zero-coupon output P(t,T), the validator checks that
    the cross-scenario average of D(0,t) * P(t,T) reconciles to P(0,T), where
    D(0,t) is approximated from monthly short-rate paths.
    """

    REQUIRED_COLUMNS = ("scenario_id", "month", "r_short", "measure")
    DEFAULT_TENOR_COLUMNS = (("zcb_1y", 1.0), ("zcb_10y", 10.0))

    def __init__(
        self,
        relative_tolerance=0.035,
        absolute_tolerance=0.003,
        max_standard_error=0.020,
    ):
        self.relative_tolerance = float(relative_tolerance)
        self.absolute_tolerance = float(absolute_tolerance)
        self.max_standard_error = float(max_standard_error)
        for name, value in (
            ("relative_tolerance", self.relative_tolerance),
            ("absolute_tolerance", self.absolute_tolerance),
            ("max_standard_error", self.max_standard_error),
        ):
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError("{} must be finite and positive".format(name))

    def validate(self, curve, scenario_data, tenor_columns=None):
        """Return evidence that Q-measure discounted bond prices are martingales."""
        if not isinstance(curve, RiskFreeCurve):
            raise TypeError("curve must be a RiskFreeCurve")

        frame = pd.DataFrame(scenario_data)
        tenor_columns = tenor_columns or self.DEFAULT_TENOR_COLUMNS
        checks = []
        diagnostics = {}

        required = tuple(self.REQUIRED_COLUMNS) + tuple(column for column, _ in tenor_columns)
        missing = [column for column in required if column not in frame.columns]
        checks.append(MartingaleEvidenceCheck(
            "QME-COLUMNS",
            not missing,
            "ERROR",
            "Scenario data must include identifiers, measure, rates, and ZCB columns.",
            observed_value=float(len(missing)),
            threshold=0.0,
        ))
        if missing:
            return self._report(curve, Measure.Q, checks, diagnostics)

        checks.append(MartingaleEvidenceCheck(
            "QME-NONEMPTY",
            not frame.empty,
            "ERROR",
            "Scenario data must contain at least one path row.",
            observed_value=float(len(frame)),
            threshold=1.0,
        ))
        if frame.empty:
            return self._report(curve, Measure.Q, checks, diagnostics)

        try:
            measures = {
                _coerce_measure(value)
                for value in frame["measure"].dropna().unique()
            }
        except ValueError:
            measures = set()
        measure_passed = measures == {Measure.Q}
        checks.append(MartingaleEvidenceCheck(
            "QME-MEASURE-Q",
            measure_passed,
            "ERROR",
            "Martingale evidence must be generated from Q-measure scenarios only.",
            observed_value=float(len(measures)),
            threshold=1.0,
        ))

        duplicate_count = int(frame.duplicated(["scenario_id", "month"]).sum())
        checks.append(MartingaleEvidenceCheck(
            "QME-UNIQUE-PATH-GRID",
            duplicate_count == 0,
            "ERROR",
            "Scenario data must contain one row per scenario and month.",
            observed_value=float(duplicate_count),
            threshold=0.0,
        ))
        if not measure_passed or duplicate_count:
            return self._report(curve, Measure.Q, checks, diagnostics)

        months = np.asarray(sorted(frame["month"].astype(int).unique()), dtype=int)
        expected_months = np.arange(int(months[-1]) + 1, dtype=int)
        month_grid_ok = bool(np.array_equal(months, expected_months))
        diagnostics["horizon_months"] = float(months[-1])
        diagnostics["n_scenarios"] = float(frame["scenario_id"].nunique())
        checks.append(MartingaleEvidenceCheck(
            "QME-COMPLETE-MONTH-GRID",
            month_grid_ok,
            "ERROR",
            "Scenario months must be contiguous and start at zero.",
            observed_value=float(len(months)),
            threshold=float(len(expected_months)),
        ))
        if not month_grid_ok:
            return self._report(curve, Measure.Q, checks, diagnostics)

        rates = frame.pivot(index="scenario_id", columns="month", values="r_short")
        rates = rates.reindex(columns=expected_months).to_numpy(dtype=float)
        complete_grid = bool(np.all(np.isfinite(rates)))
        checks.append(MartingaleEvidenceCheck(
            "QME-FINITE-RATE-GRID",
            complete_grid,
            "ERROR",
            "Scenario short-rate grid must be complete and finite.",
            observed_value=float(np.sum(np.isfinite(rates))),
            threshold=float(rates.size),
        ))
        if not complete_grid:
            return self._report(curve, Measure.Q, checks, diagnostics)

        dt = 1.0 / 12.0
        money_market_discount = np.ones_like(rates)
        if rates.shape[1] > 1:
            money_market_discount[:, 1:] = np.exp(
                -np.cumsum(rates[:, :-1] * dt, axis=1)
            )

        for column, tenor in tenor_columns:
            zcb_values = frame.pivot(index="scenario_id", columns="month", values=column)
            zcb_values = zcb_values.reindex(columns=expected_months).to_numpy(dtype=float)
            finite_zcbs = bool(np.all(np.isfinite(zcb_values)) and np.all(zcb_values > 0.0))
            checks.append(MartingaleEvidenceCheck(
                "QME-{}-FINITE".format(column.upper()),
                finite_zcbs,
                "ERROR",
                "{} values must be complete, finite, and positive.".format(column),
                observed_value=float(np.min(zcb_values)) if np.all(np.isfinite(zcb_values)) else 0.0,
                threshold=0.0,
            ))
            if not finite_zcbs:
                continue

            discounted_bond_prices = money_market_discount * zcb_values
            target_prices = np.asarray(
                [
                    curve.discount_factor(month / 12.0 + float(tenor))
                    for month in expected_months
                ],
                dtype=float,
            )
            sample_mean = np.mean(discounted_bond_prices, axis=0)
            if discounted_bond_prices.shape[0] > 1:
                standard_error = np.std(discounted_bond_prices, axis=0, ddof=1) / np.sqrt(
                    discounted_bond_prices.shape[0]
                )
            else:
                standard_error = np.full_like(sample_mean, self.max_standard_error * 2.0)
            absolute_error = np.abs(sample_mean - target_prices)
            relative_error = absolute_error / np.maximum(target_prices, 1.0e-12)
            tolerance = np.maximum(
                self.absolute_tolerance,
                self.relative_tolerance * target_prices,
            )

            label = column.upper()
            diagnostics["{}_max_absolute_error".format(column)] = float(np.max(absolute_error))
            diagnostics["{}_max_relative_error".format(column)] = float(np.max(relative_error))
            diagnostics["{}_max_standard_error".format(column)] = float(np.max(standard_error))
            diagnostics["{}_max_tolerance".format(column)] = float(np.max(tolerance))
            checks.append(MartingaleEvidenceCheck(
                "QME-MARTINGALE-{}".format(label),
                bool(np.all(absolute_error <= tolerance)),
                "ERROR",
                "Average discounted {} prices must reconcile to the initial curve.".format(column),
                observed_value=float(np.max(absolute_error)),
                threshold=float(np.max(tolerance)),
            ))
            checks.append(MartingaleEvidenceCheck(
                "QME-SAMPLING-ERROR-{}".format(label),
                bool(np.max(standard_error) <= self.max_standard_error),
                "WARNING",
                "{} sampling error should be small enough for reviewable evidence.".format(column),
                observed_value=float(np.max(standard_error)),
                threshold=self.max_standard_error,
            ))

        return self._report(curve, Measure.Q, checks, diagnostics)

    def _report(self, curve, measure, checks, diagnostics):
        passed = all(check.passed or check.severity != "ERROR" for check in checks)
        return MartingaleEvidenceReport(
            curve_id=curve.curve_id,
            currency=curve.currency,
            valuation_date=curve.valuation_date,
            measure=measure,
            passed=passed,
            checks=tuple(checks),
            diagnostics=diagnostics,
        )


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


@dataclass(frozen=True)
class RegionalEquityFactor:
    """Phase 8 regional equity factor definition backed by GBM parameters."""

    market: str
    region: str
    currency: str
    index_name: str
    factor_id: str
    source_id: str
    valuation_date: date
    params: GBMParams
    notes: str = ""

    def __post_init__(self):
        object.__setattr__(self, "market", _require_text(self.market, "market").upper())
        object.__setattr__(self, "region", _require_text(self.region, "region"))
        object.__setattr__(self, "currency", _validate_currency_code(self.currency, "currency"))
        object.__setattr__(self, "index_name", _require_text(self.index_name, "index_name"))
        object.__setattr__(self, "factor_id", _require_text(self.factor_id, "factor_id").upper())
        object.__setattr__(self, "source_id", _require_text(self.source_id, "source_id"))
        object.__setattr__(self, "valuation_date", _coerce_date(self.valuation_date, "valuation_date"))
        if not isinstance(self.params, GBMParams):
            raise TypeError("params must be a GBMParams instance")

    @property
    def is_placeholder(self):
        return True

    def to_dict(self):
        return {
            "market": self.market,
            "region": self.region,
            "currency": self.currency,
            "index_name": self.index_name,
            "factor_id": self.factor_id,
            "source_id": self.source_id,
            "valuation_date": self.valuation_date.isoformat(),
            "params": asdict(self.params),
            "notes": self.notes,
            "is_placeholder": self.is_placeholder,
        }


_STARTER_EQUITY_FIXTURE_PATH = Path(__file__).with_name("fixtures").joinpath(
    "regional_equity_factors.json"
)
_STARTER_EQUITY_RECORDS = None


def _normalize_equity_market(value):
    return _require_text(value, "market").upper().replace("-", "_").replace(" ", "_")


def _load_starter_equity_records():
    global _STARTER_EQUITY_RECORDS
    if _STARTER_EQUITY_RECORDS is None:
        with _STARTER_EQUITY_FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            raw_records = json.load(fixture_file)
        _STARTER_EQUITY_RECORDS = {
            _normalize_equity_market(record["market"]): record
            for record in raw_records["factors"]
        }
    return _STARTER_EQUITY_RECORDS


def available_starter_equity_markets():
    """Return markets covered by the Phase 8 starter regional equity factors."""
    return tuple(sorted(_load_starter_equity_records()))


def starter_equity_factor(market, valuation_date=None):
    """Return an illustrative Phase 8 regional equity factor fixture.

    The fixture produces a `RegionalEquityFactor` plus the `GBMParams` needed
    by existing v1-compatible equity scenario consumers.
    """
    market = _normalize_equity_market(market)
    records = _load_starter_equity_records()
    if market not in records:
        raise KeyError(
            "no Phase 8 starter equity factor for {}; available markets are {}".format(
                market,
                ", ".join(available_starter_equity_markets()),
            )
        )
    record = records[market]
    return RegionalEquityFactor(
        market=record["market"],
        region=record["region"],
        currency=record["currency"],
        index_name=record["index_name"],
        factor_id=record["factor_id"],
        source_id=record["source_id"],
        valuation_date=_coerce_date(
            valuation_date or record["valuation_date"],
            "valuation_date",
        ),
        params=GBMParams(
            equity_vol=record["equity_vol"],
            dividend_yield=record["dividend_yield"],
            equity_risk_premium=record["equity_risk_premium"],
            rate_equity_correlation=record["rate_equity_correlation"],
            initial_index_level=record["initial_index_level"],
        ),
        notes=record.get("notes", ""),
    )


def default_phase8_equity_factors(valuation_date=None):
    """Return all Phase 8 starter regional equity factors keyed by market."""
    return {
        market: starter_equity_factor(market, valuation_date=valuation_date)
        for market in available_starter_equity_markets()
    }


@dataclass
class FXParams:
    """Parameters for a lognormal FX spot-rate process.

    Spot is quoted as base-currency units per one foreign-currency unit.  For
    example, USDHKD is HKD per USD.
    """

    fx_vol: float = 0.08
    real_world_drift: float = 0.0
    domestic_foreign_rate_spread: float = 0.0
    rate_fx_correlation: float = 0.0
    initial_spot_rate: float = 1.0

    def __post_init__(self):
        if not (0.0 <= self.fx_vol < 2.0):
            raise ValueError("fx_vol out of plausible range [0, 2.0); got {}".format(self.fx_vol))
        if not (-1.0 < self.rate_fx_correlation < 1.0):
            raise ValueError(
                "rate_fx_correlation must be in (-1, 1); got {}".format(
                    self.rate_fx_correlation
                )
            )
        if self.initial_spot_rate <= 0.0:
            raise ValueError("initial_spot_rate must be positive; got {}".format(self.initial_spot_rate))

    @property
    def is_placeholder(self):
        return True


@dataclass(frozen=True)
class FXReturnFactor:
    """Phase 8 FX return factor definition for currency translation."""

    pair: str
    foreign_currency: str
    base_currency: str
    market: str
    quotation: str
    factor_id: str
    source_id: str
    valuation_date: date
    params: FXParams
    notes: str = ""

    def __post_init__(self):
        foreign_currency = _validate_currency_code(self.foreign_currency, "foreign_currency")
        base_currency = _validate_currency_code(self.base_currency, "base_currency")
        pair = _normalize_fx_pair(self.pair)
        if pair != "{}{}".format(foreign_currency, base_currency):
            raise ValueError(
                "pair must be foreign_currency + base_currency; got pair={!r}, currencies={}{}".format(
                    self.pair,
                    foreign_currency,
                    base_currency,
                )
            )
        object.__setattr__(self, "pair", pair)
        object.__setattr__(self, "foreign_currency", foreign_currency)
        object.__setattr__(self, "base_currency", base_currency)
        object.__setattr__(self, "market", _require_text(self.market, "market").upper())
        object.__setattr__(self, "quotation", _require_text(self.quotation, "quotation"))
        object.__setattr__(self, "factor_id", _require_text(self.factor_id, "factor_id").upper())
        object.__setattr__(self, "source_id", _require_text(self.source_id, "source_id"))
        object.__setattr__(self, "valuation_date", _coerce_date(self.valuation_date, "valuation_date"))
        if not isinstance(self.params, FXParams):
            raise TypeError("params must be an FXParams instance")

    @property
    def is_placeholder(self):
        return True

    def to_dict(self):
        return {
            "pair": self.pair,
            "foreign_currency": self.foreign_currency,
            "base_currency": self.base_currency,
            "market": self.market,
            "quotation": self.quotation,
            "factor_id": self.factor_id,
            "source_id": self.source_id,
            "valuation_date": self.valuation_date.isoformat(),
            "params": asdict(self.params),
            "notes": self.notes,
            "is_placeholder": self.is_placeholder,
        }


_STARTER_FX_FIXTURE_PATH = Path(__file__).with_name("fixtures").joinpath(
    "fx_return_factors.json"
)
_STARTER_FX_RECORDS = None


def _normalize_fx_pair(value):
    return _require_text(value, "pair").upper().replace("/", "").replace("-", "").replace(" ", "")


def _load_starter_fx_records():
    global _STARTER_FX_RECORDS
    if _STARTER_FX_RECORDS is None:
        with _STARTER_FX_FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            raw_records = json.load(fixture_file)
        _STARTER_FX_RECORDS = {
            _normalize_fx_pair(record["pair"]): record
            for record in raw_records["factors"]
        }
    return _STARTER_FX_RECORDS


def available_starter_fx_pairs():
    """Return FX pairs covered by the Phase 8 starter FX return factors."""
    return tuple(sorted(_load_starter_fx_records()))


def starter_fx_factor(pair, valuation_date=None):
    """Return an illustrative Phase 8 FX return factor fixture."""
    pair = _normalize_fx_pair(pair)
    records = _load_starter_fx_records()
    if pair not in records:
        raise KeyError(
            "no Phase 8 starter FX factor for {}; available pairs are {}".format(
                pair,
                ", ".join(available_starter_fx_pairs()),
            )
        )
    record = records[pair]
    return FXReturnFactor(
        pair=record["pair"],
        foreign_currency=record["foreign_currency"],
        base_currency=record["base_currency"],
        market=record["market"],
        quotation=record["quotation"],
        factor_id=record["factor_id"],
        source_id=record["source_id"],
        valuation_date=_coerce_date(
            valuation_date or record["valuation_date"],
            "valuation_date",
        ),
        params=FXParams(
            fx_vol=record["fx_vol"],
            real_world_drift=record["real_world_drift"],
            domestic_foreign_rate_spread=record["domestic_foreign_rate_spread"],
            rate_fx_correlation=record["rate_fx_correlation"],
            initial_spot_rate=record["initial_spot_rate"],
        ),
        notes=record.get("notes", ""),
    )


def fx_factor_for_translation(foreign_currency, base_currency="HKD", valuation_date=None):
    """Return the starter FX factor needed to translate foreign to base currency.

    Returns None when no translation is required because both currencies match.
    """
    foreign_currency = _validate_currency_code(foreign_currency, "foreign_currency")
    base_currency = _validate_currency_code(base_currency, "base_currency")
    if foreign_currency == base_currency:
        return None
    return starter_fx_factor("{}{}".format(foreign_currency, base_currency), valuation_date=valuation_date)


def default_phase8_fx_factors(valuation_date=None):
    """Return all Phase 8 starter FX return factors keyed by currency pair."""
    return {
        pair: starter_fx_factor(pair, valuation_date=valuation_date)
        for pair in available_starter_fx_pairs()
    }


def phase8_rate_equity_fx_correlation_matrix(gbm_params=None, fx_params=None):
    """Return the implied v1-compatible Phase 8 rate/equity/FX correlation matrix.

    `ScenarioSet.generate(...)` drives equity and FX shocks from the same rate
    shock plus independent residual shocks.  Under that construction, the
    implied equity/FX correlation is rho(rate,equity) * rho(rate,FX).
    """
    gbm_params = gbm_params if gbm_params is not None else GBMParams()
    factor_ids = ["RATE_SHORT_CHANGE", "EQUITY_RETURN_1M"]
    matrix = [[1.0, gbm_params.rate_equity_correlation],
              [gbm_params.rate_equity_correlation, 1.0]]
    if fx_params is not None:
        if not isinstance(fx_params, FXParams):
            raise TypeError("fx_params must be an FXParams instance")
        rho_re = gbm_params.rate_equity_correlation
        rho_rf = fx_params.rate_fx_correlation
        factor_ids.append("FX_RETURN_1M")
        matrix = [
            [1.0, rho_re, rho_rf],
            [rho_re, 1.0, rho_re * rho_rf],
            [rho_rf, rho_re * rho_rf, 1.0],
        ]
    return pd.DataFrame(matrix, index=factor_ids, columns=factor_ids, dtype=float)


@dataclass(frozen=True)
class CorrelationMatrixValidationCheck:
    """Single Phase 8 correlation matrix validation check result."""

    check_id: str
    passed: bool
    severity: str
    message: str
    observed_value: Optional[float] = None
    threshold: Optional[float] = None

    def __post_init__(self):
        object.__setattr__(self, "check_id", _require_text(self.check_id, "check_id"))
        object.__setattr__(self, "severity", _require_text(self.severity, "severity").upper())
        object.__setattr__(self, "message", _require_text(self.message, "message"))
        if self.observed_value is not None and not np.isfinite(float(self.observed_value)):
            raise ValueError("observed_value must be finite")
        if self.threshold is not None and not np.isfinite(float(self.threshold)):
            raise ValueError("threshold must be finite")

    def to_dict(self):
        return {
            "check_id": self.check_id,
            "passed": bool(self.passed),
            "severity": self.severity,
            "message": self.message,
            "observed_value": self.observed_value,
            "threshold": self.threshold,
        }


@dataclass(frozen=True)
class CorrelationMatrixValidationReport:
    """JSON-ready Phase 8 correlation validation and scenario diagnostic report."""

    factor_ids: Tuple[str, ...]
    matrix_version: str
    as_of_date: date
    passed: bool
    repaired: bool
    repair_method: str
    checks: Tuple[CorrelationMatrixValidationCheck, ...]
    diagnostics: Dict[str, float]
    correlation_matrix: Tuple[Tuple[float, ...], ...]
    repaired_matrix: Optional[Tuple[Tuple[float, ...], ...]] = None

    def __post_init__(self):
        if not self.factor_ids:
            raise ValueError("factor_ids must not be empty")
        factor_ids = tuple(_require_text(value, "factor_id").upper() for value in self.factor_ids)
        if len(set(factor_ids)) != len(factor_ids):
            raise ValueError("factor_ids must be unique")
        object.__setattr__(self, "factor_ids", factor_ids)
        object.__setattr__(self, "matrix_version", _require_text(self.matrix_version, "matrix_version"))
        object.__setattr__(self, "as_of_date", _coerce_date(self.as_of_date, "as_of_date"))
        if not self.checks:
            raise ValueError("checks must not be empty")
        for key, value in self.diagnostics.items():
            if not str(key).strip():
                raise ValueError("diagnostic keys must be non-empty")
            if not np.isfinite(float(value)):
                raise ValueError("diagnostic {!r} must be finite".format(key))

    def failed_checks(self):
        return tuple(check for check in self.checks if not check.passed)

    def to_dict(self):
        return {
            "factor_ids": list(self.factor_ids),
            "matrix_version": self.matrix_version,
            "as_of_date": self.as_of_date.isoformat(),
            "passed": bool(self.passed),
            "repaired": bool(self.repaired),
            "repair_method": self.repair_method,
            "checks": [check.to_dict() for check in self.checks],
            "diagnostics": dict(self.diagnostics),
            "correlation_matrix": [list(row) for row in self.correlation_matrix],
            "repaired_matrix": (
                None if self.repaired_matrix is None
                else [list(row) for row in self.repaired_matrix]
            ),
        }


class CorrelationMatrixValidator:
    """Phase 8 validator for cross-risk-factor correlation inputs and outputs."""

    SCENARIO_FACTOR_COLUMNS = (
        ("RATE_SHORT_CHANGE", "r_short"),
        ("EQUITY_RETURN_1M", "equity_return_1m"),
        ("FX_RETURN_1M", "fx_return_1m"),
    )

    def __init__(
        self,
        eigenvalue_tolerance=1.0e-10,
        diagonal_tolerance=1.0e-10,
        symmetry_tolerance=1.0e-10,
        max_repair_adjustment=0.05,
        scenario_correlation_tolerance=0.20,
    ):
        self.eigenvalue_tolerance = float(eigenvalue_tolerance)
        self.diagonal_tolerance = float(diagonal_tolerance)
        self.symmetry_tolerance = float(symmetry_tolerance)
        self.max_repair_adjustment = float(max_repair_adjustment)
        self.scenario_correlation_tolerance = float(scenario_correlation_tolerance)
        for name, value in (
            ("eigenvalue_tolerance", self.eigenvalue_tolerance),
            ("diagonal_tolerance", self.diagonal_tolerance),
            ("symmetry_tolerance", self.symmetry_tolerance),
            ("max_repair_adjustment", self.max_repair_adjustment),
            ("scenario_correlation_tolerance", self.scenario_correlation_tolerance),
        ):
            if not np.isfinite(value) or value < 0.0:
                raise ValueError("{} must be finite and non-negative".format(name))

    def validate_matrix(
        self,
        matrix,
        factor_ids=None,
        matrix_version="PHASE8-CORRELATION",
        as_of_date=None,
        repair=False,
    ):
        """Validate a correlation matrix and optionally return a PSD repair."""
        matrix_values, factor_ids = self._matrix_and_factor_ids(matrix, factor_ids)
        as_of_date = _coerce_date(as_of_date or date.today(), "as_of_date")
        checks, diagnostics = self._base_matrix_checks(matrix_values)
        repaired = False
        repair_method = "none"
        repaired_matrix = None

        base_passed = all(check.passed or check.severity != "ERROR" for check in checks)
        finite_input = bool(np.all(np.isfinite(matrix_values)))
        if repair and finite_input and not base_passed:
            repaired_values = self._nearest_correlation_matrix(matrix_values)
            repaired_checks, repaired_diagnostics = self._base_matrix_checks(repaired_values)
            max_adjustment = float(np.max(np.abs(repaired_values - matrix_values)))
            diagnostics.update({
                "repair_max_abs_adjustment": max_adjustment,
                "repair_min_eigenvalue": repaired_diagnostics["min_eigenvalue"],
            })
            checks.extend((
                CorrelationMatrixValidationCheck(
                    "CORR-REPAIR-PSD",
                    bool(repaired_diagnostics["min_eigenvalue"] >= -self.eigenvalue_tolerance),
                    "ERROR",
                    "Repaired correlation matrix must be positive semidefinite.",
                    observed_value=repaired_diagnostics["min_eigenvalue"],
                    threshold=-self.eigenvalue_tolerance,
                ),
                CorrelationMatrixValidationCheck(
                    "CORR-REPAIR-ADJUSTMENT",
                    bool(max_adjustment <= self.max_repair_adjustment),
                    "WARNING",
                    "Correlation repair adjustment should stay within review threshold.",
                    observed_value=max_adjustment,
                    threshold=self.max_repair_adjustment,
                ),
            ))
            checks.extend(
                CorrelationMatrixValidationCheck(
                    "REPAIRED-" + check.check_id,
                    check.passed,
                    check.severity,
                    check.message,
                    check.observed_value,
                    check.threshold,
                )
                for check in repaired_checks
            )
            repaired = True
            repair_method = "eigenvalue_floor_rescale"
            repaired_matrix = self._matrix_tuple(repaired_values)

        passed = all(check.passed or check.severity != "ERROR" for check in checks)
        if repaired:
            passed = bool(
                diagnostics["repair_min_eigenvalue"] >= -self.eigenvalue_tolerance
                and all(
                    check.passed or check.severity != "ERROR"
                    for check in checks
                    if not check.check_id.startswith("CORR-PSD")
                )
            )
        return CorrelationMatrixValidationReport(
            factor_ids=tuple(factor_ids),
            matrix_version=matrix_version,
            as_of_date=as_of_date,
            passed=passed,
            repaired=repaired,
            repair_method=repair_method,
            checks=tuple(checks),
            diagnostics=diagnostics,
            correlation_matrix=self._matrix_tuple(matrix_values),
            repaired_matrix=repaired_matrix,
        )

    def reject_invalid(self, matrix, factor_ids=None, matrix_version="PHASE8-CORRELATION", as_of_date=None):
        """Return a passing report or raise ValueError with failed check IDs."""
        report = self.validate_matrix(
            matrix,
            factor_ids=factor_ids,
            matrix_version=matrix_version,
            as_of_date=as_of_date,
            repair=False,
        )
        if not report.passed:
            failed = ", ".join(check.check_id for check in report.failed_checks())
            raise ValueError("correlation matrix validation failed: {}".format(failed))
        return report

    def validate_scenario_diagnostics(
        self,
        scenario_data,
        expected_matrix=None,
        factor_ids=None,
        matrix_version="PHASE8-SCENARIO-DIAGNOSTICS",
        as_of_date=None,
    ):
        """Validate empirical scenario correlations for generated ESG factors."""
        empirical_frame, diagnostics, checks = self._scenario_correlation_frame(scenario_data)
        if empirical_frame is None:
            return CorrelationMatrixValidationReport(
                factor_ids=tuple(factor_ids or ("SCENARIO_FACTOR",)),
                matrix_version=matrix_version,
                as_of_date=_coerce_date(as_of_date or date.today(), "as_of_date"),
                passed=False,
                repaired=False,
                repair_method="none",
                checks=tuple(checks),
                diagnostics=diagnostics,
                correlation_matrix=((1.0,),),
            )

        report = self.validate_matrix(
            empirical_frame,
            factor_ids=factor_ids,
            matrix_version=matrix_version,
            as_of_date=as_of_date,
            repair=False,
        )
        checks = list(checks) + list(report.checks)
        diagnostics.update(report.diagnostics)

        if expected_matrix is not None:
            expected_values, expected_ids = self._matrix_and_factor_ids(
                expected_matrix,
                factor_ids=tuple(empirical_frame.index),
            )
            empirical_values = empirical_frame.loc[list(expected_ids), list(expected_ids)].to_numpy(dtype=float)
            max_abs_error = float(np.max(np.abs(empirical_values - expected_values)))
            diagnostics["max_abs_target_correlation_error"] = max_abs_error
            checks.append(CorrelationMatrixValidationCheck(
                "CORR-SCENARIO-TARGET",
                bool(max_abs_error <= self.scenario_correlation_tolerance),
                "WARNING",
                "Empirical scenario correlations should reconcile to configured correlations within sampling tolerance.",
                observed_value=max_abs_error,
                threshold=self.scenario_correlation_tolerance,
            ))

        passed = all(check.passed or check.severity != "ERROR" for check in checks)
        return CorrelationMatrixValidationReport(
            factor_ids=tuple(empirical_frame.index),
            matrix_version=matrix_version,
            as_of_date=_coerce_date(as_of_date or date.today(), "as_of_date"),
            passed=passed,
            repaired=False,
            repair_method="none",
            checks=tuple(checks),
            diagnostics=diagnostics,
            correlation_matrix=self._matrix_tuple(empirical_frame.to_numpy(dtype=float)),
        )

    def _matrix_and_factor_ids(self, matrix, factor_ids=None):
        if isinstance(matrix, pd.DataFrame):
            if factor_ids is None:
                if list(matrix.index) != list(matrix.columns):
                    raise ValueError("correlation DataFrame index and columns must match")
                factor_ids = tuple(str(value) for value in matrix.index)
            matrix_values = matrix.to_numpy(dtype=float)
        else:
            matrix_values = np.asarray(matrix, dtype=float)
        if matrix_values.ndim != 2 or matrix_values.shape[0] != matrix_values.shape[1]:
            raise ValueError("correlation matrix must be square")
        n_factors = matrix_values.shape[0]
        if factor_ids is None:
            factor_ids = tuple("FACTOR_{}".format(i + 1) for i in range(n_factors))
        factor_ids = tuple(_require_text(value, "factor_id").upper() for value in factor_ids)
        if len(factor_ids) != n_factors:
            raise ValueError("factor_ids length must match matrix dimensions")
        if len(set(factor_ids)) != len(factor_ids):
            raise ValueError("factor_ids must be unique")
        return matrix_values, factor_ids

    def _base_matrix_checks(self, matrix_values):
        checks = []
        diagnostics = {
            "n_factors": float(matrix_values.shape[0]),
            "max_abs_value": 0.0,
            "max_abs_diagonal_error": 0.0,
            "max_abs_symmetry_error": 0.0,
            "min_eigenvalue": -1.0,
        }
        finite = bool(np.all(np.isfinite(matrix_values)))
        checks.append(CorrelationMatrixValidationCheck(
            "CORR-FINITE",
            finite,
            "ERROR",
            "Correlation matrix entries must be finite.",
            observed_value=float(np.sum(np.isfinite(matrix_values))),
            threshold=float(matrix_values.size),
        ))
        if not finite:
            return checks, diagnostics

        diagonal_error = np.abs(np.diag(matrix_values) - 1.0)
        symmetry_error = np.abs(matrix_values - matrix_values.T)
        max_abs_value = float(np.max(np.abs(matrix_values)))
        diagnostics.update({
            "max_abs_value": max_abs_value,
            "max_abs_diagonal_error": float(np.max(diagonal_error)),
            "max_abs_symmetry_error": float(np.max(symmetry_error)),
        })
        checks.append(CorrelationMatrixValidationCheck(
            "CORR-DIAGONAL-ONES",
            bool(np.max(diagonal_error) <= self.diagonal_tolerance),
            "ERROR",
            "Correlation matrix diagonal must equal one.",
            observed_value=diagnostics["max_abs_diagonal_error"],
            threshold=self.diagonal_tolerance,
        ))
        checks.append(CorrelationMatrixValidationCheck(
            "CORR-SYMMETRIC",
            bool(np.max(symmetry_error) <= self.symmetry_tolerance),
            "ERROR",
            "Correlation matrix must be symmetric.",
            observed_value=diagnostics["max_abs_symmetry_error"],
            threshold=self.symmetry_tolerance,
        ))
        checks.append(CorrelationMatrixValidationCheck(
            "CORR-RANGE",
            bool(max_abs_value <= 1.0 + self.diagonal_tolerance),
            "ERROR",
            "Correlation entries must be in [-1, 1].",
            observed_value=max_abs_value,
            threshold=1.0,
        ))

        symmetric_matrix = 0.5 * (matrix_values + matrix_values.T)
        eigenvalues = np.linalg.eigvalsh(symmetric_matrix)
        diagnostics["min_eigenvalue"] = float(np.min(eigenvalues))
        checks.append(CorrelationMatrixValidationCheck(
            "CORR-PSD",
            bool(diagnostics["min_eigenvalue"] >= -self.eigenvalue_tolerance),
            "ERROR",
            "Correlation matrix must be positive semidefinite for Cholesky or equivalent simulation.",
            observed_value=diagnostics["min_eigenvalue"],
            threshold=-self.eigenvalue_tolerance,
        ))
        return checks, diagnostics

    def _nearest_correlation_matrix(self, matrix_values):
        symmetric_matrix = 0.5 * (matrix_values + matrix_values.T)
        eigenvalues, eigenvectors = np.linalg.eigh(symmetric_matrix)
        floored = np.maximum(eigenvalues, self.eigenvalue_tolerance)
        repaired = (eigenvectors * floored) @ eigenvectors.T
        diagonal = np.sqrt(np.maximum(np.diag(repaired), self.eigenvalue_tolerance))
        repaired = repaired / np.outer(diagonal, diagonal)
        repaired = np.clip(0.5 * (repaired + repaired.T), -1.0, 1.0)
        np.fill_diagonal(repaired, 1.0)
        return repaired

    def _scenario_correlation_frame(self, scenario_data):
        frame = scenario_data.data if isinstance(scenario_data, ScenarioSet) else pd.DataFrame(scenario_data)
        checks = []
        diagnostics = {}
        required = ("scenario_id", "month", "r_short", "equity_return_1m")
        missing = [column for column in required if column not in frame.columns]
        checks.append(CorrelationMatrixValidationCheck(
            "CORR-SCENARIO-COLUMNS",
            not missing,
            "ERROR",
            "Scenario diagnostics require scenario_id, month, r_short, and equity_return_1m columns.",
            observed_value=float(len(missing)),
            threshold=0.0,
        ))
        if missing:
            return None, diagnostics, checks

        sorted_frame = frame.sort_values(["scenario_id", "month"])
        factor_series = {}
        rate_grid = sorted_frame.pivot(index="scenario_id", columns="month", values="r_short")
        rate_changes = rate_grid.diff(axis=1).iloc[:, 1:].stack(dropna=False)
        rate_changes.index = rate_changes.index.set_names(["scenario_id", "month"])
        factor_series["RATE_SHORT_CHANGE"] = rate_changes

        for factor_id, column in self.SCENARIO_FACTOR_COLUMNS[1:]:
            if column not in sorted_frame.columns:
                continue
            values = sorted_frame[sorted_frame["month"] > 0].set_index(
                ["scenario_id", "month"]
            )[column].sort_index()
            factor_series[factor_id] = values

        common_index = None
        for values in factor_series.values():
            common_index = values.index if common_index is None else common_index.intersection(values.index)
        if common_index is None or len(common_index) < 3 or len(factor_series) < 2:
            checks.append(CorrelationMatrixValidationCheck(
                "CORR-SCENARIO-OBSERVATIONS",
                False,
                "ERROR",
                "Scenario diagnostics require at least two factors and three aligned observations.",
                observed_value=0.0 if common_index is None else float(len(common_index)),
                threshold=3.0,
            ))
            return None, diagnostics, checks

        aligned = pd.DataFrame({
            factor_id: values.reindex(common_index).astype(float)
            for factor_id, values in factor_series.items()
        }).dropna()
        diagnostics["scenario_observation_count"] = float(len(aligned))
        diagnostics["scenario_factor_count"] = float(aligned.shape[1])
        checks.append(CorrelationMatrixValidationCheck(
            "CORR-SCENARIO-OBSERVATIONS",
            bool(len(aligned) >= 3 and aligned.shape[1] >= 2),
            "ERROR",
            "Scenario diagnostics require at least two factors and three aligned observations.",
            observed_value=float(len(aligned)),
            threshold=3.0,
        ))
        if len(aligned) < 3 or aligned.shape[1] < 2:
            return None, diagnostics, checks

        empirical = aligned.corr()
        diagnostics["scenario_max_abs_empirical_correlation"] = float(
            np.max(np.abs(empirical.to_numpy(dtype=float)))
        )
        return empirical, diagnostics, checks

    @staticmethod
    def _matrix_tuple(matrix_values):
        return tuple(
            tuple(float(value) for value in row)
            for row in np.asarray(matrix_values, dtype=float)
        )


@dataclass(frozen=True)
class PMeasureBacktestCheck:
    """Single Phase 8 P-measure backtest scaffold check result."""

    check_id: str
    passed: bool
    severity: str
    message: str
    observed_value: Optional[float] = None
    threshold: Optional[float] = None

    def __post_init__(self):
        object.__setattr__(self, "check_id", _require_text(self.check_id, "check_id"))
        object.__setattr__(self, "severity", _require_text(self.severity, "severity").upper())
        object.__setattr__(self, "message", _require_text(self.message, "message"))
        if self.observed_value is not None and not np.isfinite(float(self.observed_value)):
            raise ValueError("observed_value must be finite")
        if self.threshold is not None and not np.isfinite(float(self.threshold)):
            raise ValueError("threshold must be finite")

    def to_dict(self):
        return {
            "check_id": self.check_id,
            "passed": bool(self.passed),
            "severity": self.severity,
            "message": self.message,
            "observed_value": self.observed_value,
            "threshold": self.threshold,
        }


@dataclass(frozen=True)
class PMeasureBacktestReport:
    """JSON-ready scaffold report for P-measure equity and correlation backtests."""

    market: str
    as_of_date: date
    passed: bool
    checks: Tuple[PMeasureBacktestCheck, ...]
    diagnostics: Dict[str, float]
    scenario_distribution: Dict[str, float]
    historical_distribution: Optional[Dict[str, float]] = None
    scenario_correlation_matrix: Optional[Tuple[Tuple[float, ...], ...]] = None
    historical_correlation_matrix: Optional[Tuple[Tuple[float, ...], ...]] = None
    factor_ids: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        object.__setattr__(self, "market", _require_text(self.market, "market").upper())
        object.__setattr__(self, "as_of_date", _coerce_date(self.as_of_date, "as_of_date"))
        if not self.checks:
            raise ValueError("checks must not be empty")
        for mapping_name, mapping in (
            ("diagnostics", self.diagnostics),
            ("scenario_distribution", self.scenario_distribution),
            ("historical_distribution", self.historical_distribution or {}),
        ):
            for key, value in mapping.items():
                if not str(key).strip():
                    raise ValueError("{} keys must be non-empty".format(mapping_name))
                if not np.isfinite(float(value)):
                    raise ValueError("{} {!r} must be finite".format(mapping_name, key))
        factor_ids = tuple(_require_text(value, "factor_id").upper() for value in self.factor_ids)
        object.__setattr__(self, "factor_ids", factor_ids)

    def failed_checks(self):
        return tuple(check for check in self.checks if not check.passed)

    def to_dict(self):
        return {
            "market": self.market,
            "as_of_date": self.as_of_date.isoformat(),
            "passed": bool(self.passed),
            "checks": [check.to_dict() for check in self.checks],
            "diagnostics": dict(self.diagnostics),
            "scenario_distribution": dict(self.scenario_distribution),
            "historical_distribution": (
                None if self.historical_distribution is None
                else dict(self.historical_distribution)
            ),
            "factor_ids": list(self.factor_ids),
            "scenario_correlation_matrix": (
                None if self.scenario_correlation_matrix is None
                else [list(row) for row in self.scenario_correlation_matrix]
            ),
            "historical_correlation_matrix": (
                None if self.historical_correlation_matrix is None
                else [list(row) for row in self.historical_correlation_matrix]
            ),
        }


class PMeasureBacktestValidator:
    """Phase 8 scaffold for real-world equity distribution and correlation evidence.

    The scaffold does not source market history itself.  Callers pass generated
    P-measure scenarios and, when available, a prepared historical/reference
    return table with `equity_return_1m` plus optional rate / FX return columns.
    """

    SCENARIO_REQUIRED_COLUMNS = ("scenario_id", "month", "equity_return_1m", "measure")
    FACTOR_COLUMN_ALIASES = (
        ("RATE_SHORT_CHANGE", ("rate_short_change", "r_short_change")),
        ("EQUITY_RETURN_1M", ("equity_return_1m",)),
        ("FX_RETURN_1M", ("fx_return_1m",)),
    )

    def __init__(
        self,
        min_scenario_observations=36,
        min_historical_observations=24,
        monthly_mean_tolerance=0.015,
        volatility_relative_tolerance=0.35,
        quantile_abs_tolerance=0.06,
        expected_correlation_tolerance=0.35,
        historical_correlation_tolerance=0.35,
    ):
        self.min_scenario_observations = int(min_scenario_observations)
        self.min_historical_observations = int(min_historical_observations)
        self.monthly_mean_tolerance = float(monthly_mean_tolerance)
        self.volatility_relative_tolerance = float(volatility_relative_tolerance)
        self.quantile_abs_tolerance = float(quantile_abs_tolerance)
        self.expected_correlation_tolerance = float(expected_correlation_tolerance)
        self.historical_correlation_tolerance = float(historical_correlation_tolerance)
        if self.min_scenario_observations < 3:
            raise ValueError("min_scenario_observations must be at least 3")
        if self.min_historical_observations < 3:
            raise ValueError("min_historical_observations must be at least 3")
        for name, value in (
            ("monthly_mean_tolerance", self.monthly_mean_tolerance),
            ("volatility_relative_tolerance", self.volatility_relative_tolerance),
            ("quantile_abs_tolerance", self.quantile_abs_tolerance),
            ("expected_correlation_tolerance", self.expected_correlation_tolerance),
            ("historical_correlation_tolerance", self.historical_correlation_tolerance),
        ):
            if not np.isfinite(value) or value < 0.0:
                raise ValueError("{} must be finite and non-negative".format(name))

    def validate(
        self,
        scenario_data,
        historical_data=None,
        expected_matrix=None,
        market="MULTI",
        as_of_date=None,
    ):
        """Return scaffold evidence for P-measure equity returns and correlations."""
        frame = scenario_data.data if isinstance(scenario_data, ScenarioSet) else pd.DataFrame(scenario_data)
        as_of_date = _coerce_date(as_of_date or date.today(), "as_of_date")
        checks = []
        diagnostics = {}
        scenario_distribution = {}
        historical_distribution = None
        factor_ids = tuple()
        scenario_correlation_matrix = None
        historical_correlation_matrix = None

        missing = [column for column in self.SCENARIO_REQUIRED_COLUMNS if column not in frame.columns]
        checks.append(PMeasureBacktestCheck(
            "PMB-SCENARIO-COLUMNS",
            not missing,
            "ERROR",
            "P-measure backtest scenarios require scenario_id, month, equity_return_1m, and measure columns.",
            observed_value=float(len(missing)),
            threshold=0.0,
        ))
        if missing:
            return self._report(
                market,
                as_of_date,
                checks,
                diagnostics,
                scenario_distribution,
                historical_distribution,
                scenario_correlation_matrix,
                historical_correlation_matrix,
                factor_ids,
            )

        measures = {_coerce_measure(value) for value in frame["measure"].dropna().unique()}
        p_measure_only = measures == {Measure.P}
        checks.append(PMeasureBacktestCheck(
            "PMB-MEASURE-P",
            p_measure_only,
            "ERROR",
            "Equity distribution backtests must use real-world P-measure scenarios only.",
            observed_value=float(len(measures)),
            threshold=1.0,
        ))
        scenario_returns = frame.loc[frame["month"].astype(int) > 0, "equity_return_1m"].astype(float)
        diagnostics["scenario_observation_count"] = float(len(scenario_returns))
        checks.append(PMeasureBacktestCheck(
            "PMB-SCENARIO-OBSERVATIONS",
            bool(len(scenario_returns) >= self.min_scenario_observations),
            "ERROR",
            "Scenario backtest needs enough non-zero-month equity return observations.",
            observed_value=float(len(scenario_returns)),
            threshold=float(self.min_scenario_observations),
        ))
        finite_returns = bool(np.all(np.isfinite(scenario_returns.to_numpy(dtype=float))))
        checks.append(PMeasureBacktestCheck(
            "PMB-SCENARIO-RETURNS-FINITE",
            finite_returns,
            "ERROR",
            "Scenario equity returns must be finite.",
            observed_value=float(np.sum(np.isfinite(scenario_returns.to_numpy(dtype=float)))),
            threshold=float(len(scenario_returns)),
        ))
        checks.append(PMeasureBacktestCheck(
            "PMB-SCENARIO-RETURN-FLOOR",
            bool(finite_returns and np.min(scenario_returns.to_numpy(dtype=float)) > -1.0),
            "ERROR",
            "Monthly equity returns must stay above -100%.",
            observed_value=(
                float(np.min(scenario_returns.to_numpy(dtype=float)))
                if len(scenario_returns) else None
            ),
            threshold=-1.0,
        ))
        if len(scenario_returns) and finite_returns:
            scenario_distribution = self._return_distribution(scenario_returns)
            diagnostics.update({
                "scenario_monthly_mean": scenario_distribution["monthly_mean"],
                "scenario_monthly_volatility": scenario_distribution["monthly_volatility"],
                "scenario_annualized_mean": scenario_distribution["annualized_mean"],
                "scenario_annualized_volatility": scenario_distribution["annualized_volatility"],
                "scenario_p01": scenario_distribution["p01"],
                "scenario_p99": scenario_distribution["p99"],
            })

        if historical_data is not None:
            historical_frame = pd.DataFrame(historical_data)
            hist_checks, historical_distribution = self._validate_historical_distribution(
                historical_frame,
                scenario_distribution,
            )
            checks.extend(hist_checks)
            if historical_distribution is not None:
                diagnostics.update({
                    "historical_observation_count": historical_distribution["observation_count"],
                    "historical_monthly_mean": historical_distribution["monthly_mean"],
                    "historical_monthly_volatility": historical_distribution["monthly_volatility"],
                    "distribution_mean_abs_error": abs(
                        scenario_distribution["monthly_mean"] - historical_distribution["monthly_mean"]
                    ),
                    "distribution_volatility_relative_error": self._relative_error(
                        scenario_distribution["monthly_volatility"],
                        historical_distribution["monthly_volatility"],
                    ),
                    "distribution_p05_abs_error": abs(
                        scenario_distribution["p05"] - historical_distribution["p05"]
                    ),
                    "distribution_p95_abs_error": abs(
                        scenario_distribution["p95"] - historical_distribution["p95"]
                    ),
                })

            correlation_result = self._historical_correlation_check(frame, historical_frame)
            if correlation_result is not None:
                correlation_checks, factor_ids, scenario_correlation_matrix, historical_correlation_matrix, drift = correlation_result
                checks.extend(correlation_checks)
                diagnostics["historical_correlation_max_abs_drift"] = drift

        if expected_matrix is not None:
            correlation_report = CorrelationMatrixValidator(
                scenario_correlation_tolerance=self.expected_correlation_tolerance,
            ).validate_scenario_diagnostics(
                frame,
                expected_matrix=expected_matrix,
                as_of_date=as_of_date,
            )
            expected_error = correlation_report.diagnostics.get(
                "max_abs_target_correlation_error",
                0.0,
            )
            checks.append(PMeasureBacktestCheck(
                "PMB-EXPECTED-CORRELATION-STABILITY",
                bool(correlation_report.passed and expected_error <= self.expected_correlation_tolerance),
                "WARNING",
                "Scenario empirical correlations should reconcile to configured P-measure correlations.",
                observed_value=expected_error,
                threshold=self.expected_correlation_tolerance,
            ))
            diagnostics["expected_correlation_max_abs_error"] = expected_error
            diagnostics["scenario_correlation_observation_count"] = correlation_report.diagnostics.get(
                "scenario_observation_count",
                0.0,
            )
            if scenario_correlation_matrix is None:
                scenario_correlation_matrix = correlation_report.correlation_matrix
                factor_ids = correlation_report.factor_ids

        return self._report(
            market,
            as_of_date,
            checks,
            diagnostics,
            scenario_distribution,
            historical_distribution,
            scenario_correlation_matrix,
            historical_correlation_matrix,
            factor_ids,
        )

    def _validate_historical_distribution(self, historical_frame, scenario_distribution):
        checks = []
        if "equity_return_1m" not in historical_frame.columns:
            checks.append(PMeasureBacktestCheck(
                "PMB-HISTORICAL-COLUMNS",
                False,
                "ERROR",
                "Historical/reference data must include equity_return_1m.",
                observed_value=1.0,
                threshold=0.0,
            ))
            return checks, None

        hist_returns = historical_frame["equity_return_1m"].astype(float).dropna()
        checks.append(PMeasureBacktestCheck(
            "PMB-HISTORICAL-OBSERVATIONS",
            bool(len(hist_returns) >= self.min_historical_observations),
            "ERROR",
            "Historical/reference data needs enough monthly equity return observations.",
            observed_value=float(len(hist_returns)),
            threshold=float(self.min_historical_observations),
        ))
        finite = bool(np.all(np.isfinite(hist_returns.to_numpy(dtype=float))))
        checks.append(PMeasureBacktestCheck(
            "PMB-HISTORICAL-RETURNS-FINITE",
            finite,
            "ERROR",
            "Historical/reference equity returns must be finite.",
            observed_value=float(np.sum(np.isfinite(hist_returns.to_numpy(dtype=float)))),
            threshold=float(len(hist_returns)),
        ))
        if len(hist_returns) < self.min_historical_observations or not finite or not scenario_distribution:
            return checks, None

        historical_distribution = self._return_distribution(hist_returns)
        mean_error = abs(scenario_distribution["monthly_mean"] - historical_distribution["monthly_mean"])
        vol_error = self._relative_error(
            scenario_distribution["monthly_volatility"],
            historical_distribution["monthly_volatility"],
        )
        p05_error = abs(scenario_distribution["p05"] - historical_distribution["p05"])
        p95_error = abs(scenario_distribution["p95"] - historical_distribution["p95"])
        checks.extend((
            PMeasureBacktestCheck(
                "PMB-DISTRIBUTION-MEAN",
                bool(mean_error <= self.monthly_mean_tolerance),
                "WARNING",
                "Scenario monthly mean should be close to the historical/reference mean.",
                observed_value=mean_error,
                threshold=self.monthly_mean_tolerance,
            ),
            PMeasureBacktestCheck(
                "PMB-DISTRIBUTION-VOLATILITY",
                bool(vol_error <= self.volatility_relative_tolerance),
                "WARNING",
                "Scenario monthly volatility should be close to the historical/reference volatility.",
                observed_value=vol_error,
                threshold=self.volatility_relative_tolerance,
            ),
            PMeasureBacktestCheck(
                "PMB-DISTRIBUTION-TAILS",
                bool(max(p05_error, p95_error) <= self.quantile_abs_tolerance),
                "WARNING",
                "Scenario 5th and 95th percentiles should be close to historical/reference tails.",
                observed_value=max(p05_error, p95_error),
                threshold=self.quantile_abs_tolerance,
            ),
        ))
        return checks, historical_distribution

    def _historical_correlation_check(self, scenario_frame, historical_frame):
        scenario_factors = self._scenario_factor_frame(scenario_frame)
        historical_factors = self._historical_factor_frame(historical_frame)
        common = [factor for factor in scenario_factors.columns if factor in historical_factors.columns]
        if len(common) < 2 or len(scenario_factors) < 3 or len(historical_factors) < 3:
            return None
        scenario_corr = scenario_factors[common].corr().to_numpy(dtype=float)
        historical_corr = historical_factors[common].corr().to_numpy(dtype=float)
        drift = float(np.max(np.abs(scenario_corr - historical_corr)))
        check = PMeasureBacktestCheck(
            "PMB-HISTORICAL-CORRELATION-STABILITY",
            bool(drift <= self.historical_correlation_tolerance),
            "WARNING",
            "Scenario factor correlations should remain close to historical/reference correlations.",
            observed_value=drift,
            threshold=self.historical_correlation_tolerance,
        )
        return (
            (check,),
            tuple(common),
            CorrelationMatrixValidator._matrix_tuple(scenario_corr),
            CorrelationMatrixValidator._matrix_tuple(historical_corr),
            drift,
        )

    def _scenario_factor_frame(self, scenario_frame):
        sorted_frame = scenario_frame.sort_values(["scenario_id", "month"])
        factor_series = {}
        rate_grid = sorted_frame.pivot(index="scenario_id", columns="month", values="r_short")
        rate_changes = rate_grid.diff(axis=1).iloc[:, 1:].stack(dropna=False)
        rate_changes.index = rate_changes.index.set_names(["scenario_id", "month"])
        factor_series["RATE_SHORT_CHANGE"] = rate_changes
        for factor_id, column in (
            ("EQUITY_RETURN_1M", "equity_return_1m"),
            ("FX_RETURN_1M", "fx_return_1m"),
        ):
            if column in sorted_frame.columns:
                values = sorted_frame[sorted_frame["month"] > 0].set_index(
                    ["scenario_id", "month"]
                )[column].sort_index()
                factor_series[factor_id] = values
        common_index = None
        for values in factor_series.values():
            common_index = values.index if common_index is None else common_index.intersection(values.index)
        return pd.DataFrame({
            factor_id: values.reindex(common_index).astype(float)
            for factor_id, values in factor_series.items()
        }).dropna()

    def _historical_factor_frame(self, historical_frame):
        result = {}
        for factor_id, aliases in self.FACTOR_COLUMN_ALIASES:
            for alias in aliases:
                if alias in historical_frame.columns:
                    result[factor_id] = historical_frame[alias].astype(float).to_numpy()
                    break
        if "RATE_SHORT_CHANGE" not in result and "r_short" in historical_frame.columns:
            result["RATE_SHORT_CHANGE"] = historical_frame["r_short"].astype(float).diff().to_numpy()
        length = min(len(values) for values in result.values()) if result else 0
        return pd.DataFrame({
            factor_id: np.asarray(values[-length:], dtype=float)
            for factor_id, values in result.items()
        }).dropna()

    @staticmethod
    def _return_distribution(returns):
        values = np.asarray(returns, dtype=float)
        monthly_mean = float(np.mean(values))
        monthly_vol = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        return {
            "observation_count": float(len(values)),
            "monthly_mean": monthly_mean,
            "monthly_volatility": monthly_vol,
            "annualized_mean": float((1.0 + monthly_mean) ** 12 - 1.0),
            "annualized_volatility": float(monthly_vol * np.sqrt(12.0)),
            "p01": float(np.quantile(values, 0.01)),
            "p05": float(np.quantile(values, 0.05)),
            "p50": float(np.quantile(values, 0.50)),
            "p95": float(np.quantile(values, 0.95)),
            "p99": float(np.quantile(values, 0.99)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
        }

    @staticmethod
    def _relative_error(actual, expected):
        if abs(float(expected)) < 1.0e-12:
            return abs(float(actual) - float(expected))
        return abs(float(actual) - float(expected)) / abs(float(expected))

    @staticmethod
    def _report(
        market,
        as_of_date,
        checks,
        diagnostics,
        scenario_distribution,
        historical_distribution,
        scenario_correlation_matrix,
        historical_correlation_matrix,
        factor_ids,
    ):
        passed = all(check.passed or check.severity != "ERROR" for check in checks)
        return PMeasureBacktestReport(
            market=market,
            as_of_date=as_of_date,
            passed=passed,
            checks=tuple(checks),
            diagnostics=diagnostics,
            scenario_distribution=scenario_distribution,
            historical_distribution=historical_distribution,
            scenario_correlation_matrix=scenario_correlation_matrix,
            historical_correlation_matrix=historical_correlation_matrix,
            factor_ids=tuple(factor_ids),
        )


# ---------------------------------------------------------------------------
# 1b. Phase 6 Scenario Metadata and Parameter Snapshot Dataclasses
# ---------------------------------------------------------------------------

_CALIBRATION_SOURCE_TYPES = {
    "curve",
    "equity_index",
    "fx",
    "credit_spread",
    "correlation",
    "parameter_placeholder",
}

_CALIBRATION_FIELD_TYPES = {"string", "number", "integer", "date"}


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
        object.__setattr__(self, "source_id", _require_text(self.source_id, "source_id"))
        source_type = _require_text(self.source_type, "source_type").lower()
        if source_type not in _CALIBRATION_SOURCE_TYPES:
            raise ValueError(
                "source_type must be one of {}; got {!r}".format(
                    sorted(_CALIBRATION_SOURCE_TYPES), self.source_type
                )
            )
        object.__setattr__(self, "source_type", source_type)
        object.__setattr__(self, "market", _require_text(self.market, "market").upper())
        if self.currency is not None:
            object.__setattr__(self, "currency", _validate_currency_code(self.currency, "currency"))
        object.__setattr__(self, "as_of_date", _coerce_date(self.as_of_date, "as_of_date"))
        object.__setattr__(self, "provider", _require_text(self.provider, "provider"))
        object.__setattr__(self, "dataset_name", _require_text(self.dataset_name, "dataset_name"))

    def to_dict(self):
        result = asdict(self)
        result["as_of_date"] = self.as_of_date.isoformat()
        return result


@dataclass(frozen=True)
class CalibrationFieldSpec:
    """Column-level contract for a calibration input table."""

    name: str
    data_type: str
    required: bool = True
    unit: str = ""
    description: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        object.__setattr__(self, "name", _require_text(self.name, "field name"))
        data_type = _require_text(self.data_type, "data_type").lower()
        if data_type not in _CALIBRATION_FIELD_TYPES:
            raise ValueError(
                "data_type must be one of {}; got {!r}".format(
                    sorted(_CALIBRATION_FIELD_TYPES), self.data_type
                )
            )
        object.__setattr__(self, "data_type", data_type)
        if self.min_value is not None and self.max_value is not None:
            if float(self.min_value) > float(self.max_value):
                raise ValueError("min_value must not exceed max_value for {!r}".format(self.name))
        allowed_values = tuple(str(value).strip() for value in self.allowed_values)
        if any(not value for value in allowed_values):
            raise ValueError("allowed_values must not contain blank entries")
        object.__setattr__(self, "allowed_values", allowed_values)

    def to_dict(self):
        result = asdict(self)
        result["allowed_values"] = list(self.allowed_values)
        return result


@dataclass(frozen=True)
class CalibrationDataInterface:
    """Governed table contract for Phase 6 ESG calibration inputs.

    These interfaces define the minimum columns, value ranges, measure scope,
    and approval expectations for market and historical inputs before they are
    transformed into a ParameterSnapshot.
    """

    interface_id: str
    source_type: str
    required_fields: Tuple[CalibrationFieldSpec, ...]
    optional_fields: Tuple[CalibrationFieldSpec, ...] = field(default_factory=tuple)
    measure_scope: Tuple[Measure, ...] = (Measure.P, Measure.Q)
    market: str = "MULTI"
    currency: Optional[str] = None
    min_history_observations: int = 0
    frequency: str = ""
    provider_requirements: str = ""
    approval_required: bool = True
    notes: str = ""

    def __post_init__(self):
        object.__setattr__(self, "interface_id", _require_text(self.interface_id, "interface_id"))
        source_type = _require_text(self.source_type, "source_type").lower()
        if source_type not in _CALIBRATION_SOURCE_TYPES or source_type == "parameter_placeholder":
            raise ValueError(
                "source_type must be a calibration data type; got {!r}".format(self.source_type)
            )
        object.__setattr__(self, "source_type", source_type)
        if not self.required_fields:
            raise ValueError("required_fields must not be empty")
        all_fields = self.required_fields + self.optional_fields
        field_names = [field.name for field in all_fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("field names must be unique within an interface")
        measure_scope = tuple(_coerce_measure(measure) for measure in self.measure_scope)
        if not measure_scope:
            raise ValueError("measure_scope must not be empty")
        object.__setattr__(self, "measure_scope", measure_scope)
        object.__setattr__(self, "market", _require_text(self.market, "market").upper())
        if self.currency is not None:
            object.__setattr__(self, "currency", _validate_currency_code(self.currency, "currency"))
        if int(self.min_history_observations) != self.min_history_observations:
            raise ValueError("min_history_observations must be an integer")
        if self.min_history_observations < 0:
            raise ValueError("min_history_observations must be non-negative")

    def required_column_names(self):
        return tuple(field.name for field in self.required_fields)

    def field_specs(self):
        return self.required_fields + self.optional_fields

    def validate_frame(self, data):
        """Validate a pandas DataFrame against this interface contract."""
        if not isinstance(data, pd.DataFrame):
            raise TypeError("data must be a pandas DataFrame")
        missing = [name for name in self.required_column_names() if name not in data.columns]
        if missing:
            raise ValueError(
                "{} missing required columns: {}".format(
                    self.interface_id, ", ".join(missing)
                )
            )
        if len(data) < self.min_history_observations:
            raise ValueError(
                "{} requires at least {} observations; got {}".format(
                    self.interface_id, self.min_history_observations, len(data)
                )
            )

        for spec in self.field_specs():
            if spec.name not in data.columns:
                continue
            self._validate_series(data[spec.name], spec)
        return True

    def _validate_series(self, series, spec):
        if spec.data_type in ("number", "integer"):
            values = pd.to_numeric(series, errors="coerce")
            invalid = values.isna()
            if spec.required and invalid.any():
                raise ValueError("{} must be numeric".format(spec.name))
            finite_values = values.dropna().to_numpy(dtype=float)
            if finite_values.size and not np.isfinite(finite_values).all():
                raise ValueError("{} must contain finite values".format(spec.name))
            if spec.data_type == "integer" and finite_values.size:
                if not np.all(np.equal(np.mod(finite_values, 1.0), 0.0)):
                    raise ValueError("{} must contain integer values".format(spec.name))
            if spec.min_value is not None and finite_values.size:
                if (finite_values < float(spec.min_value)).any():
                    raise ValueError(
                        "{} values must be >= {}".format(spec.name, spec.min_value)
                    )
            if spec.max_value is not None and finite_values.size:
                if (finite_values > float(spec.max_value)).any():
                    raise ValueError(
                        "{} values must be <= {}".format(spec.name, spec.max_value)
                    )
        elif spec.data_type == "date":
            parsed = pd.to_datetime(series, errors="coerce")
            if spec.required and parsed.isna().any():
                raise ValueError("{} must contain valid dates".format(spec.name))
        elif spec.data_type == "string":
            text = series.astype("string")
            if spec.required and (text.isna() | (text.str.strip() == "")).any():
                raise ValueError("{} must contain non-blank strings".format(spec.name))
            if spec.allowed_values:
                valid_values = {value.upper() for value in spec.allowed_values}
                observed = text.dropna().str.strip().str.upper()
                if not observed.isin(valid_values).all():
                    raise ValueError(
                        "{} must be one of {}".format(spec.name, sorted(valid_values))
                    )

    @classmethod
    def risk_free_curve(cls, market, currency):
        return cls(
            interface_id="IFACE-CURVE-{}-{}".format(str(market).upper(), str(currency).upper()),
            source_type="curve",
            market=market,
            currency=currency,
            frequency="daily or valuation-date snapshot",
            min_history_observations=2,
            provider_requirements="Liquid sovereign, swap, or approved risk-free curve source",
            required_fields=(
                CalibrationFieldSpec("date", "date", description="Market data date"),
                CalibrationFieldSpec("tenor_years", "number", min_value=0.0, description="Curve tenor in years"),
                CalibrationFieldSpec("zero_rate", "number", min_value=-0.10, max_value=1.00, unit="decimal_rate"),
            ),
            optional_fields=(
                CalibrationFieldSpec("discount_factor", "number", required=False, min_value=0.0, max_value=2.0),
                CalibrationFieldSpec("compounding", "string", required=False),
                CalibrationFieldSpec("quote_basis", "string", required=False),
            ),
            notes="Used for HW1F/G2++ initial curve, discount factors, and short-rate calibration.",
        )

    @classmethod
    def equity_index(cls, market, currency):
        return cls(
            interface_id="IFACE-EQUITY-{}-{}".format(str(market).upper(), str(currency).upper()),
            source_type="equity_index",
            market=market,
            currency=currency,
            frequency="daily history plus valuation-date level",
            min_history_observations=252,
            provider_requirements="Approved total-return index or documented price-index plus dividend source",
            required_fields=(
                CalibrationFieldSpec("date", "date"),
                CalibrationFieldSpec("index_level", "number", min_value=0.0, unit="index_level"),
            ),
            optional_fields=(
                CalibrationFieldSpec("total_return_index", "number", required=False, min_value=0.0),
                CalibrationFieldSpec("return_1d", "number", required=False, min_value=-1.0, max_value=5.0),
                CalibrationFieldSpec("dividend_yield", "number", required=False, min_value=-0.10, max_value=1.00),
                CalibrationFieldSpec("implied_vol_atm", "number", required=False, min_value=0.0, max_value=3.0),
            ),
            notes="Used for GBM or later equity process volatility, drift, dividend, and backtest inputs.",
        )

    @classmethod
    def fx_rates(cls, market, currency):
        return cls(
            interface_id="IFACE-FX-{}-{}".format(str(market).upper(), str(currency).upper()),
            source_type="fx",
            market=market,
            currency=currency,
            frequency="daily history plus valuation-date spot",
            min_history_observations=252,
            provider_requirements="Approved central bank, market data vendor, or treasury source",
            required_fields=(
                CalibrationFieldSpec("date", "date"),
                CalibrationFieldSpec("pair", "string", description="Currency pair, e.g. USDHKD"),
                CalibrationFieldSpec("spot_rate", "number", min_value=0.0, unit="fx_rate"),
                CalibrationFieldSpec("quotation", "string", allowed_values=("DIRECT", "INDIRECT")),
            ),
            optional_fields=(
                CalibrationFieldSpec("return_1d", "number", required=False, min_value=-1.0, max_value=5.0),
                CalibrationFieldSpec("forward_points", "number", required=False),
            ),
            notes="Used for currency translation, FX return calibration, and peg/basis disclosures.",
        )

    @classmethod
    def credit_spread(cls, market, currency):
        return cls(
            interface_id="IFACE-CREDIT-{}-{}".format(str(market).upper(), str(currency).upper()),
            source_type="credit_spread",
            market=market,
            currency=currency,
            frequency="daily or monthly index history plus valuation-date curve",
            min_history_observations=12,
            provider_requirements="Approved bond index, spread curve, or internal credit assumption table",
            required_fields=(
                CalibrationFieldSpec("date", "date"),
                CalibrationFieldSpec("rating", "string"),
                CalibrationFieldSpec("tenor_years", "number", min_value=0.0),
                CalibrationFieldSpec("spread_bp", "number", min_value=-500.0, max_value=10000.0, unit="basis_points"),
            ),
            optional_fields=(
                CalibrationFieldSpec("sector", "string", required=False),
                CalibrationFieldSpec("default_rate", "number", required=False, min_value=0.0, max_value=1.0),
                CalibrationFieldSpec("recovery_rate", "number", required=False, min_value=0.0, max_value=1.0),
            ),
            notes="Used for credit spread scenarios, default-loss proxies, and asset stress calibration.",
        )

    @classmethod
    def correlation_matrix(cls):
        return cls(
            interface_id="IFACE-CORRELATION-MULTI",
            source_type="correlation",
            market="MULTI",
            currency=None,
            frequency="valuation-date matrix plus historical estimation window",
            min_history_observations=1,
            provider_requirements="Approved model-owner correlation matrix or reproducible historical estimate",
            required_fields=(
                CalibrationFieldSpec("as_of_date", "date"),
                CalibrationFieldSpec("factor_id_1", "string"),
                CalibrationFieldSpec("factor_id_2", "string"),
                CalibrationFieldSpec("correlation", "number", min_value=-1.0, max_value=1.0),
                CalibrationFieldSpec("matrix_version", "string"),
            ),
            optional_fields=(
                CalibrationFieldSpec("estimation_window_years", "number", required=False, min_value=0.0),
                CalibrationFieldSpec("psd_status", "string", required=False),
            ),
            notes="Used for Cholesky inputs and later positive-semidefinite validation evidence.",
        )

    def to_dict(self):
        return {
            "interface_id": self.interface_id,
            "source_type": self.source_type,
            "required_fields": [field.to_dict() for field in self.required_fields],
            "optional_fields": [field.to_dict() for field in self.optional_fields],
            "measure_scope": [measure.value for measure in self.measure_scope],
            "market": self.market,
            "currency": self.currency,
            "min_history_observations": self.min_history_observations,
            "frequency": self.frequency,
            "provider_requirements": self.provider_requirements,
            "approval_required": self.approval_required,
            "notes": self.notes,
        }


def default_phase6_calibration_interfaces():
    """Return starter Phase 6 calibration interfaces for the ESG roadmap."""
    return (
        CalibrationDataInterface.risk_free_curve("US", "USD"),
        CalibrationDataInterface.risk_free_curve("EU", "EUR"),
        CalibrationDataInterface.risk_free_curve("HK", "HKD"),
        CalibrationDataInterface.risk_free_curve("CN", "CNY"),
        CalibrationDataInterface.risk_free_curve("JP", "JPY"),
        CalibrationDataInterface.equity_index("US", "USD"),
        CalibrationDataInterface.equity_index("EU", "EUR"),
        CalibrationDataInterface.equity_index("HK_CN", "HKD"),
        CalibrationDataInterface.equity_index("JP", "JPY"),
        CalibrationDataInterface.equity_index("ASIA_EX_JP", "USD"),
        CalibrationDataInterface.fx_rates("HK", "HKD"),
        CalibrationDataInterface.fx_rates("CN", "CNY"),
        CalibrationDataInterface.fx_rates("EU", "EUR"),
        CalibrationDataInterface.fx_rates("JP", "JPY"),
        CalibrationDataInterface.credit_spread("US", "USD"),
        CalibrationDataInterface.credit_spread("HK", "HKD"),
        CalibrationDataInterface.credit_spread("CN", "CNY"),
        CalibrationDataInterface.correlation_matrix(),
    )


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
    calibration_interfaces: Tuple[CalibrationDataInterface, ...] = field(default_factory=tuple)
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
        interface_ids = [interface.interface_id for interface in self.calibration_interfaces]
        if len(interface_ids) != len(set(interface_ids)):
            raise ValueError("calibration_interfaces must have unique interface_id values")
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
        initial_curve=None,
        equity_factor=None,
        fx_factor=None,
        snapshot_id=None,
        g2_params=None,
    ):
        """Create a Phase 6 snapshot from current HW1F/G2++ and GBM parameter dataclasses.

        When ``g2_params`` (a :class:`G2PlusParams`) is supplied the snapshot
        records ``rate.g2pp.*`` keys plus a ``rate.model`` marker instead of
        the ``rate.hw1f.*`` keys (roadmap 4.1 #7 G2++ promotion). With
        ``g2_params=None`` the snapshot is byte-for-byte identical to the
        historical HW1F snapshot."""
        measure = _coerce_measure(measure)
        base_currency = _validate_currency_code(base_currency, "base_currency")
        calibration_date = _coerce_date(calibration_date or date.today(), "calibration_date")
        hw_params = hw_params if hw_params is not None else HullWhiteParams()
        if equity_factor is not None:
            if not isinstance(equity_factor, RegionalEquityFactor):
                raise TypeError("equity_factor must be a RegionalEquityFactor")
            if gbm_params is None:
                gbm_params = equity_factor.params
        if fx_factor is not None and not isinstance(fx_factor, FXReturnFactor):
            raise TypeError("fx_factor must be an FXReturnFactor")
        gbm_params = gbm_params if gbm_params is not None else GBMParams()
        initial_curve = initial_curve if initial_curve is not None else RiskFreeCurve.flat(
            hw_params.initial_short_rate,
            currency=base_currency,
            market=base_currency,
            valuation_date=calibration_date,
        )
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
        curve_source = CalibrationSource(
            source_id=initial_curve.source_id,
            source_type="curve",
            market=initial_curve.market,
            currency=initial_curve.currency,
            as_of_date=initial_curve.valuation_date,
            provider="RiskFreeCurve input",
            dataset_name=initial_curve.curve_id,
            version=initial_curve.compounding,
            notes="Explicit Phase 7 initial curve input for HW1F generation.",
        )
        sources = [source, curve_source]
        if equity_factor is not None:
            sources.append(CalibrationSource(
                source_id=equity_factor.source_id,
                source_type="equity_index",
                market=equity_factor.market,
                currency=equity_factor.currency,
                as_of_date=equity_factor.valuation_date,
                provider="par_model_v2 Phase 8 starter equity fixture",
                dataset_name=equity_factor.index_name,
                notes=equity_factor.notes,
            ))
        if fx_factor is not None:
            sources.append(CalibrationSource(
                source_id=fx_factor.source_id,
                source_type="fx",
                market=fx_factor.market,
                currency=fx_factor.base_currency,
                as_of_date=fx_factor.valuation_date,
                provider="par_model_v2 Phase 8 starter FX fixture",
                dataset_name=fx_factor.pair,
                notes=fx_factor.notes,
            ))
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
        if isinstance(gbm_params, JumpDiffusionParams):
            parameters.update({
                "equity.jumpdiffusion.jump_intensity": gbm_params.jump_intensity,
                "equity.jumpdiffusion.jump_mean": gbm_params.jump_mean,
                "equity.jumpdiffusion.jump_vol": gbm_params.jump_vol,
                "equity.jumpdiffusion.jump_compensator": gbm_params.jump_compensator,
            })
        if hw_params.short_rate_floor is not None:
            parameters["rate.hw1f.short_rate_floor"] = hw_params.short_rate_floor
        if hw_params.short_rate_ceiling is not None:
            parameters["rate.hw1f.short_rate_ceiling"] = hw_params.short_rate_ceiling
        if g2_params is not None:
            # G2++ two-factor promotion (roadmap 4.1 #7): swap the rate.* block
            # for the two-factor parameter set and mark the active rate model.
            for _hw_key in [k for k in parameters if k.startswith("rate.hw1f.")]:
                parameters.pop(_hw_key, None)
            parameters.update({
                "rate.g2pp.mean_reversion_x": g2_params.mean_reversion_x,
                "rate.g2pp.mean_reversion_y": g2_params.mean_reversion_y,
                "rate.g2pp.vol_x": g2_params.vol_x,
                "rate.g2pp.vol_y": g2_params.vol_y,
                "rate.g2pp.factor_correlation": g2_params.factor_correlation,
                "rate.g2pp.initial_x": g2_params.initial_x,
                "rate.g2pp.initial_y": g2_params.initial_y,
                "rate.g2pp.long_run_rate_p": g2_params.long_run_rate_p,
                "rate.g2pp.market_price_of_risk_x": g2_params.market_price_of_risk_x,
                "rate.g2pp.market_price_of_risk_y": g2_params.market_price_of_risk_y,
            })
            if g2_params.short_rate_floor is not None:
                parameters["rate.g2pp.short_rate_floor"] = g2_params.short_rate_floor
            if g2_params.short_rate_ceiling is not None:
                parameters["rate.g2pp.short_rate_ceiling"] = g2_params.short_rate_ceiling
        parameters.update({
            "rate.curve.zero_rate_{}y".format("{:g}".format(tenor)): rate
            for tenor, rate in zip(initial_curve.tenors_years, initial_curve.zero_rates)
        })
        if equity_factor is not None:
            prefix = "equity.gbm.{}.".format(equity_factor.market)
            parameters.update({
                prefix + "equity_vol": gbm_params.equity_vol,
                prefix + "dividend_yield": gbm_params.dividend_yield,
                prefix + "equity_risk_premium": gbm_params.equity_risk_premium,
                prefix + "rate_equity_correlation": gbm_params.rate_equity_correlation,
                prefix + "initial_index_level": gbm_params.initial_index_level,
            })
        if fx_factor is not None:
            prefix = "fx.gbm.{}.".format(fx_factor.pair)
            parameters.update({
                prefix + "fx_vol": fx_factor.params.fx_vol,
                prefix + "real_world_drift": fx_factor.params.real_world_drift,
                prefix + "domestic_foreign_rate_spread": fx_factor.params.domestic_foreign_rate_spread,
                prefix + "rate_fx_correlation": fx_factor.params.rate_fx_correlation,
                prefix + "initial_spot_rate": fx_factor.params.initial_spot_rate,
            })
        snapshot_kwargs = {}
        if g2_params is not None:
            snapshot_kwargs["model_equation_refs"] = (
                "G2PlusRateProcess._simulate_arrays",
                "GBMEquityProcess._simulate_array",
            )
            snapshot_kwargs["discretisation"] = (
                "monthly time step with G2++ two-factor conditional normal "
                "rates and GBM equity returns"
            )
        return cls(
            snapshot_id=snapshot_id,
            calibration_date=calibration_date,
            measure=measure,
            base_currency=base_currency,
            parameters=parameters,
            sources=tuple(sources),
            calibration_interfaces=default_phase6_calibration_interfaces(),
            is_placeholder=bool(
                hw_params.is_placeholder
                or gbm_params.is_placeholder
                or (g2_params is not None and g2_params.is_placeholder)
                or (equity_factor is not None and equity_factor.is_placeholder)
                or (fx_factor is not None and fx_factor.is_placeholder)
            ),
            **snapshot_kwargs,
        )

    def to_dict(self):
        result = asdict(self)
        result["calibration_date"] = self.calibration_date.isoformat()
        result["created_at"] = self.created_at.isoformat()
        result["measure"] = self.measure.value
        result["sources"] = [source.to_dict() for source in self.sources]
        result["calibration_interfaces"] = [
            interface.to_dict() for interface in self.calibration_interfaces
        ]
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


@dataclass(frozen=True)
class ConsumerOutputMapping:
    """Mapping from Phase 6 ESG scenario outputs to existing model consumers."""

    consumer_id: str
    consumer_name: str
    accepted_measures: Tuple[Measure, ...]
    required_columns: Tuple[str, ...]
    factor_ids: Dict[str, str]
    propagated_metadata_fields: Tuple[str, ...]
    output_contract: str
    notes: str = ""

    def __post_init__(self):
        object.__setattr__(self, "consumer_id", _require_text(self.consumer_id, "consumer_id"))
        object.__setattr__(self, "consumer_name", _require_text(self.consumer_name, "consumer_name"))
        accepted_measures = tuple(_coerce_measure(measure) for measure in self.accepted_measures)
        if not accepted_measures:
            raise ValueError("accepted_measures must not be empty")
        object.__setattr__(self, "accepted_measures", accepted_measures)
        required_columns = tuple(_require_text(col, "required column") for col in self.required_columns)
        if not required_columns:
            raise ValueError("required_columns must not be empty")
        object.__setattr__(self, "required_columns", required_columns)
        factor_ids = {
            _require_text(key, "factor mapping key"): _require_text(value, "factor id")
            for key, value in dict(self.factor_ids).items()
        }
        object.__setattr__(self, "factor_ids", factor_ids)
        metadata_fields = tuple(
            _require_text(field_name, "metadata field")
            for field_name in self.propagated_metadata_fields
        )
        if not metadata_fields:
            raise ValueError("propagated_metadata_fields must not be empty")
        object.__setattr__(self, "propagated_metadata_fields", metadata_fields)
        object.__setattr__(self, "output_contract", _require_text(self.output_contract, "output_contract"))

    def validate_scenario_set(self, scenario_set):
        """Validate measure, wide columns, and metadata before consumer use."""
        measure = _coerce_measure(scenario_set.measure)
        if measure not in self.accepted_measures:
            raise ValueError(
                "{} requires scenario measure in {}; got {}".format(
                    self.consumer_id,
                    [accepted.value for accepted in self.accepted_measures],
                    measure.value,
                )
            )
        missing = [column for column in self.required_columns if column not in scenario_set.data.columns]
        if missing:
            raise ValueError(
                "{} missing required scenario columns: {}".format(
                    self.consumer_id, ", ".join(missing)
                )
            )
        if scenario_set.metadata is None:
            raise ValueError("{} requires ScenarioMetadata for audit traceability".format(self.consumer_id))
        if scenario_set.parameter_snapshot is None:
            raise ValueError("{} requires a ParameterSnapshot for audit traceability".format(self.consumer_id))
        if scenario_set.metadata.parameter_snapshot_id != scenario_set.parameter_snapshot.snapshot_id:
            raise ValueError("{} metadata and parameter snapshot IDs do not match".format(self.consumer_id))
        return True

    def wide_view(self, scenario_set):
        """Return a consumer-ready wide view with audit metadata in DataFrame attrs."""
        self.validate_scenario_set(scenario_set)
        view = scenario_set.data.copy()
        view.attrs.update(self.traceability_attributes(scenario_set))
        return view

    def traceability_attributes(self, scenario_set):
        """Return the metadata fields that reports should carry forward."""
        self.validate_scenario_set(scenario_set)
        metadata = scenario_set.metadata
        snapshot = scenario_set.parameter_snapshot
        attributes = {
            "consumer_id": self.consumer_id,
            "consumer_name": self.consumer_name,
            "measure": metadata.measure.value,
            "scenario_set_id": metadata.scenario_set_id,
            "model_version": metadata.model_version,
            "base_currency": metadata.base_currency,
            "valuation_date": metadata.valuation_date.isoformat(),
            "projection_months": metadata.projection_months,
            "n_scenarios": metadata.n_scenarios,
            "seed_policy": metadata.seed_policy,
            "parameter_snapshot_id": metadata.parameter_snapshot_id,
            "calibration_date": snapshot.calibration_date.isoformat(),
            "approval_status": snapshot.approval_status,
            "is_placeholder": snapshot.is_placeholder,
            "limitations_id": metadata.limitations_id,
        }
        return {
            field_name: attributes[field_name]
            for field_name in self.propagated_metadata_fields
            if field_name in attributes
        }

    def annual_returns_for_alm(self, scenario_set, scenario_id, month):
        """Map one scenario-month observation into DynamicALMEngine returns."""
        if self.consumer_id != "dynamic_alm":
            raise ValueError("annual_returns_for_alm is only valid for the dynamic_alm mapping")
        self.validate_scenario_set(scenario_set)
        rows = scenario_set.data[
            (scenario_set.data["scenario_id"] == int(scenario_id))
            & (scenario_set.data["month"] == int(month))
        ]
        if len(rows) != 1:
            raise ValueError(
                "expected exactly one scenario row for scenario_id={}, month={}; got {}".format(
                    scenario_id, month, len(rows)
                )
            )
        row = rows.iloc[0]
        short_rate = float(row["r_short"])
        equity_return_1m = float(row["equity_return_1m"])
        if equity_return_1m <= -1.0:
            raise ValueError("equity_return_1m must be greater than -100% for ALM mapping")
        equity_annual = (1.0 + equity_return_1m) ** 12 - 1.0
        return {
            "Cash": short_rate,
            "Govt": short_rate,
            "Credit": short_rate,
            "Equity": equity_annual,
        }

    def to_dict(self):
        return {
            "consumer_id": self.consumer_id,
            "consumer_name": self.consumer_name,
            "accepted_measures": [measure.value for measure in self.accepted_measures],
            "required_columns": list(self.required_columns),
            "factor_ids": dict(self.factor_ids),
            "propagated_metadata_fields": list(self.propagated_metadata_fields),
            "output_contract": self.output_contract,
            "notes": self.notes,
        }


_V1_WIDE_COLUMNS = (
    "scenario_id",
    "month",
    "r_short",
    "zcb_1y",
    "zcb_10y",
    "equity_index",
    "equity_return_1m",
    "measure",
)

_TRACEABILITY_FIELDS = (
    "consumer_id",
    "measure",
    "scenario_set_id",
    "model_version",
    "base_currency",
    "valuation_date",
    "projection_months",
    "n_scenarios",
    "seed_policy",
    "parameter_snapshot_id",
    "calibration_date",
    "approval_status",
    "is_placeholder",
    "limitations_id",
)


def default_phase6_consumer_mappings(base_currency="CNY", equity_market="CN"):
    """Return governed ESG output mappings for current v1 consumers."""
    base_currency = _validate_currency_code(base_currency, "base_currency")
    equity_market = _require_text(equity_market, "equity_market").upper()
    factor_ids = {
        "short_rate": "RATE_SHORT_{}".format(base_currency),
        "discount_factor_1y": "DF_1Y_{}".format(base_currency),
        "discount_factor_10y": "DF_10Y_{}".format(base_currency),
        "equity_index": "EQUITY_{}".format(equity_market),
        "equity_return_1m": "EQUITY_RETURN_1M_{}".format(equity_market),
    }
    return (
        ConsumerOutputMapping(
            consumer_id="tvog",
            consumer_name="TVOGEngine",
            accepted_measures=(Measure.Q,),
            required_columns=("scenario_id", "month", "r_short", "measure"),
            factor_ids=factor_ids,
            propagated_metadata_fields=_TRACEABILITY_FIELDS,
            output_contract="Q-measure v1 wide view with base-currency short-rate path",
            notes="Used for market-consistent guarantee valuation; P-measure inputs are rejected.",
        ),
        ConsumerOutputMapping(
            consumer_id="risk_metrics",
            consumer_name="RiskMetrics / LossDistribution",
            accepted_measures=(Measure.P,),
            required_columns=_V1_WIDE_COLUMNS,
            factor_ids=factor_ids,
            propagated_metadata_fields=_TRACEABILITY_FIELDS,
            output_contract="P-measure projection lineage for scenario PV loss distributions",
            notes="RiskMetrics consumes projected losses, but the ESG lineage must remain P-measure.",
        ),
        ConsumerOutputMapping(
            consumer_id="dynamic_alm",
            consumer_name="DynamicALMEngine",
            accepted_measures=(Measure.P,),
            required_columns=("scenario_id", "month", "r_short", "equity_return_1m", "measure"),
            factor_ids=factor_ids,
            propagated_metadata_fields=_TRACEABILITY_FIELDS,
            output_contract="P-measure annual return dictionary by asset class for each scenario month",
            notes="Cash, Govt, and Credit use the short-rate proxy until richer asset factors are implemented.",
        ),
        ConsumerOutputMapping(
            consumer_id="reporting",
            consumer_name="Reporting and audit packs",
            accepted_measures=(Measure.P, Measure.Q),
            required_columns=_V1_WIDE_COLUMNS,
            factor_ids=factor_ids,
            propagated_metadata_fields=_TRACEABILITY_FIELDS,
            output_contract="Scenario wide view plus metadata and parameter snapshot lineage",
            notes="Reporting may include P or Q sets, but each set remains single-measure and separately traced.",
        ),
    )


def phase6_consumer_mapping(consumer_id, base_currency="CNY", equity_market="CN"):
    """Return one Phase 6 consumer mapping by ID."""
    normalized = _require_text(consumer_id, "consumer_id").lower()
    for mapping in default_phase6_consumer_mappings(base_currency, equity_market):
        if mapping.consumer_id == normalized:
            return mapping
    raise KeyError("unknown Phase 6 consumer mapping: {!r}".format(consumer_id))


# ---------------------------------------------------------------------------
# 2. Hull-White 1-Factor Rate Process
# ---------------------------------------------------------------------------

class HullWhiteRateProcess:
    """Hull-White 1-factor interest rate process.

    Simulates monthly short rate paths and derives ZCB prices (1Y, 10Y).
    Use Measure.P for ALM/VaR; Measure.Q for TVOG/MCEV.
    """

    #: Measures this process is permitted to simulate under (G-05 / MR-004).
    SUPPORTED_MEASURES = (Measure.P, Measure.Q)

    def __init__(self, params=None, initial_curve=None):
        self.params = params if params is not None else HullWhiteParams()
        self.initial_curve = (
            initial_curve
            if initial_curve is not None
            else RiskFreeCurve.flat(self.params.initial_short_rate)
        )

    def _mean_reversion_factor(self, dt):
        return np.exp(-self.params.mean_reversion_speed * dt)

    def _conditional_vol(self, dt):
        a = self.params.mean_reversion_speed
        sigma = self.params.short_rate_vol
        return sigma * np.sqrt((1 - np.exp(-2 * a * dt)) / (2 * a))

    def _target_rate(self, month, measure, dt):
        if measure == Measure.Q:
            return self.initial_curve.instantaneous_forward((month + 1) * dt)
        return self.params.long_run_rate_p + self.params.short_rate_vol * self.params.market_price_of_risk

    def _apply_rate_bounds(self, rates):
        lower = self.params.short_rate_floor
        upper = self.params.short_rate_ceiling
        if lower is None and upper is None:
            return rates
        if lower is None:
            return np.minimum(rates, float(upper))
        if upper is None:
            return np.maximum(rates, float(lower))
        return np.clip(rates, float(lower), float(upper))

    def zcb_price(self, r_t, t, T):
        """Zero-coupon bond price using the HW1F affine curve-fit formula."""
        a = self.params.mean_reversion_speed
        sigma = self.params.short_rate_vol
        tau = T - t
        if tau <= 0:
            raise ValueError("Maturity T ({}) must exceed current time t ({})".format(T, t))
        B = (1.0 / a) * (1.0 - np.exp(-a * tau))
        p0_T = self.initial_curve.discount_factor(T)
        p0_t = self.initial_curve.discount_factor(t)
        f0_t = self.initial_curve.instantaneous_forward(t)
        variance_adjustment = (sigma ** 2 / (4.0 * a)) * B ** 2 * (1.0 - np.exp(-2.0 * a * t))
        return (p0_T / p0_t) * np.exp(-B * (r_t - f0_t) - variance_adjustment)

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

        rates = np.empty((n_scenarios, T_months + 1), dtype=float)
        rates[:, 0] = p.initial_short_rate
        for month in range(T_months):
            target_rate = self._target_rate(month, measure, dt)
            rates[:, month + 1] = (
                rates[:, month] * mf
                + target_rate * (1.0 - mf)
                + cv * shocks[:, month]
            )
        return self._apply_rate_bounds(rates)

    def simulate(self, n_scenarios, T_months, measure, seed=42, cap_zcb_at_par=True):
        """Simulate monthly short-rate paths as an ESGAdapter-compatible DataFrame.

        Columns: scenario_id, month, r_short, zcb_1y, zcb_10y, measure
        Shape: n_scenarios * (T_months + 1) rows.

        SOA ASOP 56 ss3.1.3, ss3.4.
        """
        measure = _enforce_simulation_measure(self, measure)
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
            zcb_1y[idx] = self.zcb_price(float(r_t), float(t), float(t + 1.0))
            zcb_10y[idx] = self.zcb_price(float(r_t), float(t), float(t + 10.0))
        if cap_zcb_at_par:
            zcb_1y = np.minimum(zcb_1y, 1.0)
            zcb_10y = np.minimum(zcb_10y, 1.0)

        frame = pd.DataFrame({
            "scenario_id": scenario_ids,
            "month": months,
            "r_short": flat_rates,
            "zcb_1y": zcb_1y,
            "zcb_10y": zcb_10y,
            "measure": measure.value,
        })
        return _assert_output_measure(frame, measure, type(self).__name__)


# ---------------------------------------------------------------------------
# 2b. G2++ Two-Factor Rate Process Prototype
# ---------------------------------------------------------------------------

class G2PlusRateProcess:
    """Two-factor Gaussian G2++ rate-process prototype.

    The prototype keeps the existing ESG wide columns while exposing `g2pp_x`
    and `g2pp_y` diagnostic factor paths. Under Q-measure, the deterministic
    shift is fitted to the supplied initial curve's instantaneous forward
    rates. Under P-measure, the same two factors mean-revert around an
    educational long-run rate with placeholder market-price-of-risk terms.
    """
    #: Measures this process is permitted to simulate under (G-05 / MR-004).
    SUPPORTED_MEASURES = (Measure.P, Measure.Q)


    def __init__(self, params=None, initial_curve=None):
        self.params = params if params is not None else G2PlusParams()
        self.initial_curve = initial_curve if initial_curve is not None else RiskFreeCurve.flat(0.020)

    def _conditional_vol(self, speed, volatility, dt):
        return volatility * np.sqrt((1.0 - np.exp(-2.0 * speed * dt)) / (2.0 * speed))

    def _target_shift(self, month, measure, dt):
        if measure == Measure.Q:
            return self.initial_curve.instantaneous_forward(month * dt)
        p = self.params
        return (
            p.long_run_rate_p
            + p.vol_x * p.market_price_of_risk_x
            + p.vol_y * p.market_price_of_risk_y
        )

    def _apply_rate_bounds(self, rates):
        lower = self.params.short_rate_floor
        upper = self.params.short_rate_ceiling
        if lower is None and upper is None:
            return rates
        if lower is None:
            return np.minimum(rates, float(upper))
        if upper is None:
            return np.maximum(rates, float(lower))
        return np.clip(rates, float(lower), float(upper))

    def _simulate_arrays(self, n_scenarios, T_months, measure, shocks_x, shocks_independent):
        expected_shape = (n_scenarios, T_months)
        if shocks_x.shape != expected_shape:
            raise ValueError("G2++ x shocks must have shape {}; got {}".format(expected_shape, shocks_x.shape))
        if shocks_independent.shape != expected_shape:
            raise ValueError(
                "G2++ independent shocks must have shape {}; got {}".format(
                    expected_shape, shocks_independent.shape
                )
            )

        dt = 1.0 / 12.0
        p = self.params
        shocks_y = (
            p.factor_correlation * shocks_x
            + np.sqrt(1.0 - p.factor_correlation ** 2) * shocks_independent
        )

        x = np.empty((n_scenarios, T_months + 1), dtype=float)
        y = np.empty((n_scenarios, T_months + 1), dtype=float)
        rates = np.empty((n_scenarios, T_months + 1), dtype=float)
        x[:, 0] = p.initial_x
        y[:, 0] = p.initial_y
        rates[:, 0] = self._target_shift(0, measure, dt) + x[:, 0] + y[:, 0]

        mf_x = np.exp(-p.mean_reversion_x * dt)
        mf_y = np.exp(-p.mean_reversion_y * dt)
        cv_x = self._conditional_vol(p.mean_reversion_x, p.vol_x, dt)
        cv_y = self._conditional_vol(p.mean_reversion_y, p.vol_y, dt)

        for month in range(T_months):
            x[:, month + 1] = x[:, month] * mf_x + cv_x * shocks_x[:, month]
            y[:, month + 1] = y[:, month] * mf_y + cv_y * shocks_y[:, month]
            rates[:, month + 1] = (
                self._target_shift(month + 1, measure, dt)
                + x[:, month + 1]
                + y[:, month + 1]
            )

        return x, y, self._apply_rate_bounds(rates)

    def _factor_loading(self, speed, t, T):
        tau = T - t
        if tau <= 0:
            raise ValueError("Maturity T ({}) must exceed current time t ({})".format(T, t))
        return (1.0 - np.exp(-speed * tau)) / speed

    def zcb_price(self, x_t, y_t, t, T):
        """Prototype G2++ zero-coupon price fitted to the initial curve at t=0."""
        p0_T = self.initial_curve.discount_factor(T)
        p0_t = self.initial_curve.discount_factor(t)
        bx = self._factor_loading(self.params.mean_reversion_x, t, T)
        by = self._factor_loading(self.params.mean_reversion_y, t, T)
        return (p0_T / p0_t) * np.exp(-bx * float(x_t) - by * float(y_t))

    def simulate(self, n_scenarios, T_months, measure, seed=42, cap_zcb_at_par=True):
        """Simulate v1-compatible short-rate paths plus G2++ factor diagnostics."""
        measure = _enforce_simulation_measure(self, measure)
        _validate_simulation_dimensions(n_scenarios, T_months)
        n_scenarios = int(n_scenarios)
        T_months = int(T_months)

        rng = np.random.default_rng(seed)
        shocks_x = _antithetic_normals(rng, n_scenarios, T_months)
        shocks_independent = _antithetic_normals(rng, n_scenarios, T_months)
        x_paths, y_paths, rates = self._simulate_arrays(
            n_scenarios,
            T_months,
            measure,
            shocks_x,
            shocks_independent,
        )

        scenario_ids, months = _month_grid(n_scenarios, T_months)
        flat_x = x_paths.reshape(-1)
        flat_y = y_paths.reshape(-1)
        flat_rates = rates.reshape(-1)
        times = months.astype(float) / 12.0

        zcb_1y = np.empty_like(flat_rates)
        zcb_10y = np.empty_like(flat_rates)
        for idx, (x_t, y_t, t) in enumerate(zip(flat_x, flat_y, times)):
            zcb_1y[idx] = self.zcb_price(float(x_t), float(y_t), float(t), float(t + 1.0))
            zcb_10y[idx] = self.zcb_price(float(x_t), float(y_t), float(t), float(t + 10.0))
        if cap_zcb_at_par:
            zcb_1y = np.minimum(zcb_1y, 1.0)
            zcb_10y = np.minimum(zcb_10y, 1.0)

        frame = pd.DataFrame({
            "scenario_id": scenario_ids,
            "month": months,
            "r_short": flat_rates,
            "zcb_1y": zcb_1y,
            "zcb_10y": zcb_10y,
            "g2pp_x": flat_x,
            "g2pp_y": flat_y,
            "measure": measure.value,
        })
        return _assert_output_measure(frame, measure, type(self).__name__)


# ---------------------------------------------------------------------------
# 3. GBM Equity Process
# ---------------------------------------------------------------------------

class GBMEquityProcess:
    """Geometric Brownian Motion equity index process.

    Measure.Q: drift = r(t) - q_S  (TVOG use)
    Measure.P: drift = r(t) + ERP - q_S  (ALM/ERM use)
    """
    #: Measures this process is permitted to simulate under (G-05 / MR-004).
    SUPPORTED_MEASURES = (Measure.P, Measure.Q)


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
        measure = _enforce_simulation_measure(self, measure)
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
        frame = pd.DataFrame({
            "scenario_id": scenario_ids,
            "month": months,
            "equity_index": equity.reshape(-1),
            "equity_return_1m": returns.reshape(-1),
            "measure": measure.value,
        })
        return _assert_output_measure(frame, measure, type(self).__name__)


# ---------------------------------------------------------------------------
# 3b. Merton Jump-Diffusion Equity Process (Phase 14 Task 5 — ESG sophistication)
# ---------------------------------------------------------------------------
#
# Optional higher-sophistication equity process selected behind a feature flag
# (see ``build_equity_process`` / ``EQUITY_PROCESS_REGISTRY`` below). The GBM
# process remains the default so all existing Phase 4/8 behaviour is unchanged.
#
# Merton (1976) jump-diffusion under measure m:
#
#   dS/S = (mu_m(t) - lambda*kappa) dt + sigma_S dW_S + (e^J - 1) dN
#
# where N is a Poisson process with intensity lambda (annual), each jump size
# J ~ Normal(mu_J, sigma_J^2), and kappa = E[e^J - 1] = exp(mu_J + 0.5 sigma_J^2) - 1
# is the Q-measure jump compensator. Continuous drift:
#   Q: mu_Q(t) = r(t) - q_S            (TVOG / market-consistent)
#   P: mu_P(t) = r(t) + ERP - q_S      (ALM / ERM / real-world)
#
# The -lambda*kappa compensator is applied under BOTH measures so that, under Q,
# the ex-dividend discounted index E[D(0,t) S(t) e^{q t}] reconciles to S(0):
#   E[S(t+dt)/S(t)] = exp(mu_m(t) dt) exactly, independent of (sigma, lambda,
#   mu_J, sigma_J). This is the closed-form basis for the Q-measure martingale
#   tests (QME-EQUITY-FORWARD). SOA ASOP 56 §3.1.3, §3.5; IA TAS M §3.6.


@dataclass
class JumpDiffusionParams:
    """Parameters for the Merton jump-diffusion equity index process.

    Continuous part matches :class:`GBMParams`; the jump part adds a compound
    Poisson process with lognormally distributed jump sizes.

      jump_intensity (lambda) : expected number of jumps per YEAR (>= 0)
      jump_mean      (mu_J)   : mean of the log-jump size
      jump_vol       (sigma_J): std-dev of the log-jump size (>= 0)

    Q-measure compensator: kappa = exp(mu_J + 0.5 sigma_J^2) - 1, applied under
    both P and Q so the risk-neutral forward is preserved.

    All values are PLACEHOLDERS pending calibration. Educational use only.
    SOA ASOP 56 §3.1.3, §3.4.
    """

    equity_vol: float = 0.22
    dividend_yield: float = 0.025
    equity_risk_premium: float = 0.045
    rate_equity_correlation: float = -0.15
    initial_index_level: float = 100.0
    jump_intensity: float = 0.25
    jump_mean: float = -0.10
    jump_vol: float = 0.15

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
        if self.jump_intensity < 0.0:
            raise ValueError(
                "jump_intensity (lambda) must be >= 0; got {}".format(self.jump_intensity)
            )
        if self.jump_vol < 0.0:
            raise ValueError(
                "jump_vol (sigma_J) must be >= 0; got {}".format(self.jump_vol)
            )
        if not (-2.0 < self.jump_mean < 2.0):
            raise ValueError(
                "jump_mean (mu_J) out of plausible range (-2, 2); got {}".format(self.jump_mean)
            )

    @property
    def jump_compensator(self):
        """Q-measure compensator kappa = E[e^J - 1] for a lognormal jump."""
        return float(np.exp(self.jump_mean + 0.5 * self.jump_vol ** 2) - 1.0)

    @property
    def is_placeholder(self):
        return True

    @classmethod
    def from_gbm_params(cls, gbm, jump_intensity=0.25, jump_mean=-0.10, jump_vol=0.15):
        """Build jump-diffusion params from a calibrated :class:`GBMParams`.

        The continuous block (vol, dividend, ERP, correlation, initial level) is
        inherited from the GBM calibration so the jump overlay is an additive
        sophistication layer over the existing Phase 14 Task 2 calibration.
        """
        if not isinstance(gbm, GBMParams):
            raise TypeError("gbm must be a GBMParams instance")
        return cls(
            equity_vol=gbm.equity_vol,
            dividend_yield=gbm.dividend_yield,
            equity_risk_premium=gbm.equity_risk_premium,
            rate_equity_correlation=gbm.rate_equity_correlation,
            initial_index_level=gbm.initial_index_level,
            jump_intensity=float(jump_intensity),
            jump_mean=float(jump_mean),
            jump_vol=float(jump_vol),
        )


class JumpDiffusionEquityProcess:
    """Merton jump-diffusion equity index process (optional, feature-flagged).

    Drop-in compatible with :class:`GBMEquityProcess`: same constructor shape,
    same ``simulate`` signature, and the same output columns
    (scenario_id, month, equity_index, equity_return_1m, measure) plus an
    additional ``equity_jump_count`` diagnostic column.

    Measure.Q: continuous drift = r(t) - q_S      (TVOG use)
    Measure.P: continuous drift = r(t) + ERP - q_S  (ALM/ERM use)
    The Q-measure jump compensator -lambda*kappa is applied under both measures.
    """

    #: Measures this process is permitted to simulate under (G-05 / MR-004).
    SUPPORTED_MEASURES = (Measure.P, Measure.Q)

    def __init__(self, params=None, rate_process=None):
        if params is None:
            params = JumpDiffusionParams()
        elif isinstance(params, GBMParams):
            params = JumpDiffusionParams.from_gbm_params(params)
        elif not isinstance(params, JumpDiffusionParams):
            raise TypeError(
                "params must be a JumpDiffusionParams or GBMParams; got {!r}".format(
                    type(params).__name__
                )
            )
        self.params = params
        self.rate_process = rate_process if rate_process is not None else HullWhiteRateProcess()

    def _simulate_array(self, n_scenarios, T_months, measure, rate_paths, shocks, rng=None):
        """Simulate equity paths. Returns (equity, returns, jump_counts) ndarrays.

        ``shocks`` are the diffusion normals (shape (n, T)); ``rng`` supplies the
        Poisson jump counts and lognormal jump sizes. A dedicated ``rng`` keeps
        jump draws reproducible and independent of the diffusion shocks.
        """
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
        if rng is None:
            rng = np.random.default_rng(0)

        dt = 1.0 / 12.0
        sqrt_dt = np.sqrt(dt)
        p = self.params
        kappa = p.jump_compensator

        equity = np.empty((n_scenarios, T_months + 1), dtype=float)
        returns = np.zeros((n_scenarios, T_months + 1), dtype=float)
        jump_counts = np.zeros((n_scenarios, T_months + 1), dtype=float)
        equity[:, 0] = p.initial_index_level

        for month in range(T_months):
            drift = rate_paths[:, month] - p.dividend_yield
            if measure == Measure.P:
                drift = drift + p.equity_risk_premium

            # Compound-Poisson jump increment over [t, t+dt]:
            counts = rng.poisson(p.jump_intensity * dt, size=n_scenarios)
            jump_counts[:, month + 1] = counts
            # Aggregate jump sum has mean counts*mu_J and var counts*sigma_J^2.
            jump_mean_total = counts * p.jump_mean
            jump_std_total = np.sqrt(counts.astype(float)) * p.jump_vol
            jump_sum = jump_mean_total + jump_std_total * rng.standard_normal(n_scenarios)

            log_return = (
                (drift - 0.5 * p.equity_vol ** 2 - p.jump_intensity * kappa) * dt
                + p.equity_vol * sqrt_dt * shocks[:, month]
                + jump_sum
            )
            gross_return = np.exp(log_return)
            equity[:, month + 1] = equity[:, month] * gross_return
            returns[:, month + 1] = gross_return - 1.0

        return equity, returns, jump_counts

    def simulate(self, n_scenarios, T_months, measure, rate_paths=None, seed=42):
        """Simulate monthly equity-index paths as a DataFrame.

        Columns: scenario_id, month, equity_index, equity_return_1m,
                 equity_jump_count, measure.
        Shape: n_scenarios * (T_months + 1) rows.

        SOA ASOP 56 §3.1.3, §3.4.
        """
        measure = _enforce_simulation_measure(self, measure)
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
        # Separate, deterministic sub-stream for jumps (reproducible, independent).
        jump_rng = np.random.default_rng(np.random.SeedSequence(seed).spawn(1)[0])
        equity, returns, jump_counts = self._simulate_array(
            n_scenarios, T_months, measure, rate_paths_array, shocks, rng=jump_rng
        )

        scenario_ids, months = _month_grid(n_scenarios, T_months)
        frame = pd.DataFrame({
            "scenario_id": scenario_ids,
            "month": months,
            "equity_index": equity.reshape(-1),
            "equity_return_1m": returns.reshape(-1),
            "equity_jump_count": jump_counts.reshape(-1),
            "measure": measure.value,
        })
        return _assert_output_measure(frame, measure, type(self).__name__)


# ---------------------------------------------------------------------------
# 3c. Equity-process feature flag / registry (Phase 14 Task 5)
# ---------------------------------------------------------------------------
#
# The equity model is selectable behind a feature flag without disturbing the
# GBM default. Resolution order for the active model:
#   1. explicit `model=` argument to build_equity_process / ScenarioSet.generate
#   2. environment variable PAR_ESG_EQUITY_MODEL
#   3. DEFAULT_EQUITY_MODEL ("gbm")
# Existing callers that pass nothing keep GBM, so all prior behaviour is intact.

DEFAULT_EQUITY_MODEL = "gbm"
_EQUITY_MODEL_ENV_VAR = "PAR_ESG_EQUITY_MODEL"

#: Registry mapping feature-flag label -> (process_class, default_params_class).
EQUITY_PROCESS_REGISTRY = {
    "gbm": (GBMEquityProcess, GBMParams),
    "jump_diffusion": (JumpDiffusionEquityProcess, JumpDiffusionParams),
    "merton": (JumpDiffusionEquityProcess, JumpDiffusionParams),
}


def available_equity_models():
    """Return the sorted set of canonical equity-model feature-flag labels."""
    return tuple(sorted({"gbm", "jump_diffusion"}))


def resolve_equity_model(model=None):
    """Resolve the active equity-model label from arg, env var, then default."""
    import os

    if model is None:
        model = os.environ.get(_EQUITY_MODEL_ENV_VAR) or DEFAULT_EQUITY_MODEL
    label = str(model).strip().lower()
    if label not in EQUITY_PROCESS_REGISTRY:
        raise ValueError(
            "unknown equity model {!r}; available: {}".format(
                model, ", ".join(available_equity_models())
            )
        )
    return label


# ---------------------------------------------------------------------------
# Rate-model selector (HW1F default / G2++ two-factor promotion, roadmap 4.1 #7)
# ---------------------------------------------------------------------------
#
# The production ESG path (:meth:`ScenarioSet.generate`) defaults to the
# one-factor Hull-White short-rate process. Roadmap item #7 (MR-004) promotes
# the validated two-factor Gaussian ``G2PlusRateProcess`` to a *selectable*
# production rate model so callers can request genuine curve twists (short and
# long tenors driven by two decorrelated factors) while HW1F stays the default
# fallback. Selection is opt-in; existing callers that pass nothing are
# byte-for-byte unchanged.

DEFAULT_RATE_MODEL = "hw1f"

#: Alias -> canonical rate-model key. Canonical keys: "hw1f", "g2pp".
RATE_MODEL_REGISTRY = {
    "hw1f": "hw1f",
    "hw": "hw1f",
    "hull-white": "hw1f",
    "hullwhite": "hw1f",
    "hull_white": "hw1f",
    "one-factor": "hw1f",
    "g2pp": "g2pp",
    "g2++": "g2pp",
    "g2plus": "g2pp",
    "g2p": "g2pp",
    "g2": "g2pp",
    "two-factor": "g2pp",
    "twofactor": "g2pp",
}


def available_rate_models():
    """Return the sorted set of canonical rate-model keys."""
    return tuple(sorted(set(RATE_MODEL_REGISTRY.values())))


def resolve_rate_model(model=None):
    """Resolve a rate-model alias to its canonical key ("hw1f" or "g2pp").

    ``None`` resolves to :data:`DEFAULT_RATE_MODEL` ("hw1f"). Unknown values
    raise ``ValueError`` (fail-loud) rather than silently defaulting, so a
    typo in an ESG config can never quietly swap the rate model.
    """
    if model is None:
        return DEFAULT_RATE_MODEL
    key = str(model).strip().lower()
    if key not in RATE_MODEL_REGISTRY:
        raise ValueError(
            "unknown rate_model {!r}; available: {}".format(
                model, ", ".join(available_rate_models())
            )
        )
    return RATE_MODEL_REGISTRY[key]


def build_equity_process(model=None, params=None, rate_process=None):
    """Construct the configured equity process behind the feature flag.

    Parameters
    ----------
    model : str or None
        Feature-flag label ("gbm", "jump_diffusion"/"merton"). If None, falls
        back to the PAR_ESG_EQUITY_MODEL env var then DEFAULT_EQUITY_MODEL.
    params : GBMParams or JumpDiffusionParams, optional
        Process parameters. A GBMParams passed to the jump-diffusion model is
        promoted via JumpDiffusionParams.from_gbm_params so a calibrated GBM
        block carries through as the continuous part of the jump model.
    rate_process : rate process, optional
        Short-rate process supplying stochastic drift.

    SOA ASOP 56 §3.1.3 (process documentation); IA TAS M §3.6 (model variants).
    """
    label = resolve_equity_model(model)
    process_cls, _ = EQUITY_PROCESS_REGISTRY[label]
    return process_cls(params, rate_process=rate_process)


class EquityForwardMartingaleValidator:
    """Validate the Q-measure equity-forward martingale property.

    Under Q, the ex-dividend discounted equity index is a martingale:

        E[ D(0,t) * S(t) * exp(q_S * t) ] = S(0)   for all t,

    where D(0,t) = exp(-integral_0^t r(u) du) is the stochastic money-market
    discount built from the scenario short-rate path and q_S is the (deterministic)
    dividend yield. This holds for GBM and, by construction of the jump
    compensator, for the Merton jump-diffusion process — independent of vol,
    jump intensity, jump mean, or jump vol. Provides governance evidence for the
    Phase 14 Task 5 sophistication upgrade.

    SOA ASOP 56 §3.5 (convergence / martingale evidence); IA TAS M §3.6.
    """

    REQUIRED_COLUMNS = ("scenario_id", "month", "r_short", "equity_index", "measure")

    def __init__(self, dividend_yield=0.0, relative_tolerance=0.04,
                 absolute_tolerance=0.5, max_standard_error=1.5):
        self.dividend_yield = float(dividend_yield)
        self.relative_tolerance = float(relative_tolerance)
        self.absolute_tolerance = float(absolute_tolerance)
        self.max_standard_error = float(max_standard_error)
        for name, value in (
            ("relative_tolerance", self.relative_tolerance),
            ("absolute_tolerance", self.absolute_tolerance),
            ("max_standard_error", self.max_standard_error),
        ):
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError("{} must be finite and positive".format(name))

    def validate(self, scenario_data, curve_id="EQUITY-FWD", currency="CNY",
                 valuation_date=None):
        frame = pd.DataFrame(scenario_data)
        checks = []
        diagnostics = {}

        missing = [c for c in self.REQUIRED_COLUMNS if c not in frame.columns]
        checks.append(MartingaleEvidenceCheck(
            "QME-EQUITY-COLUMNS", not missing, "ERROR",
            "Scenario data must include identifiers, measure, rates, and equity_index.",
            observed_value=float(len(missing)), threshold=0.0,
        ))
        if missing:
            return self._report(curve_id, currency, valuation_date, checks, diagnostics)

        try:
            measures = {_coerce_measure(v) for v in frame["measure"].dropna().unique()}
        except ValueError:
            measures = set()
        measure_q = measures == {Measure.Q}
        checks.append(MartingaleEvidenceCheck(
            "QME-EQUITY-MEASURE-Q", measure_q, "ERROR",
            "Equity martingale evidence must use Q-measure scenarios only.",
            observed_value=float(len(measures)), threshold=1.0,
        ))
        dup = int(frame.duplicated(["scenario_id", "month"]).sum())
        checks.append(MartingaleEvidenceCheck(
            "QME-EQUITY-UNIQUE-GRID", dup == 0, "ERROR",
            "Scenario data must contain one row per scenario and month.",
            observed_value=float(dup), threshold=0.0,
        ))
        if not measure_q or dup:
            return self._report(curve_id, currency, valuation_date, checks, diagnostics)

        months = np.asarray(sorted(frame["month"].astype(int).unique()), dtype=int)
        expected = np.arange(int(months[-1]) + 1, dtype=int)
        grid_ok = bool(np.array_equal(months, expected))
        diagnostics["horizon_months"] = float(months[-1])
        diagnostics["n_scenarios"] = float(frame["scenario_id"].nunique())
        checks.append(MartingaleEvidenceCheck(
            "QME-EQUITY-COMPLETE-GRID", grid_ok, "ERROR",
            "Scenario months must be contiguous and start at zero.",
            observed_value=float(len(months)), threshold=float(len(expected)),
        ))
        if not grid_ok:
            return self._report(curve_id, currency, valuation_date, checks, diagnostics)

        rates = frame.pivot(index="scenario_id", columns="month", values="r_short")
        rates = rates.reindex(columns=expected).to_numpy(dtype=float)
        equity = frame.pivot(index="scenario_id", columns="month", values="equity_index")
        equity = equity.reindex(columns=expected).to_numpy(dtype=float)
        finite = bool(np.all(np.isfinite(rates)) and np.all(np.isfinite(equity)))
        checks.append(MartingaleEvidenceCheck(
            "QME-EQUITY-FINITE-GRID", finite, "ERROR",
            "Scenario rate and equity grids must be complete and finite.",
            observed_value=float(np.sum(np.isfinite(equity))), threshold=float(equity.size),
        ))
        if not finite:
            return self._report(curve_id, currency, valuation_date, checks, diagnostics)

        dt = 1.0 / 12.0
        discount = np.ones_like(rates)
        if rates.shape[1] > 1:
            discount[:, 1:] = np.exp(-np.cumsum(rates[:, :-1] * dt, axis=1))
        div_adj = np.exp(self.dividend_yield * expected.astype(float) * dt)
        discounted_fwd = discount * equity * div_adj  # shape (n_scen, n_months)

        s0 = float(np.mean(equity[:, 0]))
        sample_mean = np.mean(discounted_fwd, axis=0)
        if discounted_fwd.shape[0] > 1:
            standard_error = np.std(discounted_fwd, axis=0, ddof=1) / np.sqrt(discounted_fwd.shape[0])
        else:
            standard_error = np.full_like(sample_mean, self.max_standard_error * 2.0)
        abs_err = np.abs(sample_mean - s0)
        rel_err = abs_err / max(s0, 1.0e-12)
        tolerance = max(self.absolute_tolerance, self.relative_tolerance * s0)

        diagnostics["initial_index_level"] = s0
        diagnostics["max_absolute_error"] = float(np.max(abs_err))
        diagnostics["max_relative_error"] = float(np.max(rel_err))
        diagnostics["max_standard_error"] = float(np.max(standard_error))
        diagnostics["tolerance"] = float(tolerance)
        checks.append(MartingaleEvidenceCheck(
            "QME-EQUITY-FORWARD", bool(np.max(abs_err) <= tolerance), "ERROR",
            "Average discounted ex-dividend equity must reconcile to S(0).",
            observed_value=float(np.max(abs_err)), threshold=float(tolerance),
        ))
        checks.append(MartingaleEvidenceCheck(
            "QME-EQUITY-SAMPLING-ERROR", bool(np.max(standard_error) <= self.max_standard_error),
            "WARNING", "Equity sampling error should be small enough for reviewable evidence.",
            observed_value=float(np.max(standard_error)), threshold=self.max_standard_error,
        ))
        return self._report(curve_id, currency, valuation_date, checks, diagnostics)

    def _report(self, curve_id, currency, valuation_date, checks, diagnostics):
        passed = all(c.passed or c.severity != "ERROR" for c in checks)
        return MartingaleEvidenceReport(
            curve_id=curve_id, currency=currency,
            valuation_date=valuation_date or date.today(),
            measure=Measure.Q, passed=passed,
            checks=tuple(checks), diagnostics=diagnostics,
        )


# ---------------------------------------------------------------------------
# 4. FX Spot Process
# ---------------------------------------------------------------------------

class FXSpotProcess:
    """Lognormal FX spot process for Phase 8 currency translation."""
    #: Measures this process is permitted to simulate under (G-05 / MR-004).
    SUPPORTED_MEASURES = (Measure.P, Measure.Q)


    def __init__(self, params=None):
        self.params = params if params is not None else FXParams()

    def _simulate_array(self, n_scenarios, T_months, measure, shocks):
        """Simulate FX spot paths quoted as base per foreign currency."""
        expected_shape = (n_scenarios, T_months)
        if shocks.shape != expected_shape:
            raise ValueError(
                "FX shocks must have shape {}; got {}".format(expected_shape, shocks.shape)
            )

        dt = 1.0 / 12.0
        sqrt_dt = np.sqrt(dt)
        p = self.params

        spot = np.empty((n_scenarios, T_months + 1), dtype=float)
        returns = np.zeros((n_scenarios, T_months + 1), dtype=float)
        spot[:, 0] = p.initial_spot_rate

        drift = p.domestic_foreign_rate_spread
        if measure == Measure.P:
            drift = p.real_world_drift

        for month in range(T_months):
            log_return = (
                (drift - 0.5 * p.fx_vol ** 2) * dt
                + p.fx_vol * sqrt_dt * shocks[:, month]
            )
            gross_return = np.exp(log_return)
            spot[:, month + 1] = spot[:, month] * gross_return
            returns[:, month + 1] = gross_return - 1.0

        return spot, returns

    def simulate(self, n_scenarios, T_months, measure, seed=42):
        """Simulate monthly FX spot paths as a DataFrame."""
        measure = _enforce_simulation_measure(self, measure)
        _validate_simulation_dimensions(n_scenarios, T_months)
        n_scenarios = int(n_scenarios)
        T_months = int(T_months)

        rng = np.random.default_rng(seed)
        shocks = _antithetic_normals(rng, n_scenarios, T_months)
        spot, returns = self._simulate_array(n_scenarios, T_months, measure, shocks)

        scenario_ids, months = _month_grid(n_scenarios, T_months)
        frame = pd.DataFrame({
            "scenario_id": scenario_ids,
            "month": months,
            "fx_rate": spot.reshape(-1),
            "fx_return_1m": returns.reshape(-1),
            "measure": measure.value,
        })
        return _assert_output_measure(frame, measure, type(self).__name__)


# ---------------------------------------------------------------------------
# 5. ScenarioSet -- Container for combined rate + equity paths
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CurveTwistCheck:
    """Single curve-twist evidence check."""

    check_id: str
    passed: bool
    severity: str
    description: str
    observed_value: float
    threshold: float

    def __post_init__(self):
        if self.severity not in ("ERROR", "WARNING", "INFO"):
            raise ValueError("severity must be ERROR, WARNING, or INFO")

    def to_dict(self):
        return {
            "check_id": self.check_id,
            "passed": bool(self.passed),
            "severity": self.severity,
            "description": self.description,
            "observed_value": float(self.observed_value),
            "threshold": float(self.threshold),
        }


@dataclass(frozen=True)
class CurveTwistEvidenceReport:
    """Report bundling curve-twist evidence checks and diagnostics."""

    rate_model: str
    passed: bool
    checks: tuple
    diagnostics: dict

    def failed_checks(self):
        return tuple(c for c in self.checks if not c.passed)

    def to_dict(self):
        return {
            "rate_model": self.rate_model,
            "passed": bool(self.passed),
            "checks": [c.to_dict() for c in self.checks],
            "diagnostics": {k: float(v) if isinstance(v, (int, float)) else v
                            for k, v in self.diagnostics.items()},
        }


class CurveTwistValidator:
    """Evidence that a rate model produces genuine (non-parallel) curve twists.

    A one-factor model (HW1F) drives every tenor off a single Brownian factor,
    so short- and long-tenor rate CHANGES are near-perfectly correlated
    (|corr| -> 1): the yield curve can only shift in parallel, never twist or
    steepen on its own. A two-factor G2++ model decorrelates the short and long
    ends. This validator quantifies the short-vs-long rate-change correlation
    and, when a one-factor benchmark set is supplied, confirms the two-factor
    set is materially more decorrelated -- the curve-twist evidence required by
    the roadmap 4.1 #7 (MR-004) G2++ promotion. Educational thresholds; see
    docs/G2PP_PRODUCTION_PROMOTION_CARD.md.
    """

    REQUIRED_COLUMNS = ("scenario_id", "month", "r_short", "zcb_10y")

    def __init__(
        self,
        max_twist_correlation=0.98,
        benchmark_margin=0.02,
        short_tenor_years=1.0,
        long_tenor_years=10.0,
    ):
        self.max_twist_correlation = float(max_twist_correlation)
        self.benchmark_margin = float(benchmark_margin)
        self.short_tenor_years = float(short_tenor_years)
        self.long_tenor_years = float(long_tenor_years)
        if not (0.0 < self.max_twist_correlation <= 1.0):
            raise ValueError("max_twist_correlation must be in (0, 1]")
        if self.benchmark_margin < 0.0:
            raise ValueError("benchmark_margin must be non-negative")
        if self.long_tenor_years <= self.short_tenor_years:
            raise ValueError("long_tenor_years must exceed short_tenor_years")

    def _panel_changes(self, frame, short_col, long_col, tenor):
        f = pd.DataFrame(frame)
        short = f.pivot(index="scenario_id", columns="month", values=short_col)
        short = short.sort_index(axis=1).to_numpy(dtype=float)
        if long_col == "r_short":
            long_level = short
        else:
            zcb = f.pivot(index="scenario_id", columns="month", values=long_col)
            zcb = zcb.sort_index(axis=1).to_numpy(dtype=float)
            long_level = -np.log(np.clip(zcb, 1.0e-12, None)) / float(tenor)
        d_short = np.diff(short, axis=1).reshape(-1)
        d_long = np.diff(long_level, axis=1).reshape(-1)
        mask = np.isfinite(d_short) & np.isfinite(d_long)
        return d_short[mask], d_long[mask]

    def _correlation(self, a, b):
        if a.size < 2 or np.std(a) == 0.0 or np.std(b) == 0.0:
            return float("nan")
        return float(np.corrcoef(a, b)[0, 1])

    def _twist_correlation(self, frame):
        d_short, d_long = self._panel_changes(
            frame, "r_short", "zcb_10y", self.long_tenor_years
        )
        return self._correlation(d_short, d_long)

    def validate(self, scenario_data, benchmark_data=None, rate_model="g2pp"):
        """Return curve-twist evidence for ``scenario_data``.

        ``benchmark_data`` (optional) is a one-factor set used as the
        parallel-shift baseline for the comparative check.
        """
        frame = pd.DataFrame(scenario_data)
        checks = []
        diagnostics = {}
        missing = [c for c in self.REQUIRED_COLUMNS if c not in frame.columns]
        checks.append(CurveTwistCheck(
            "CT-COLUMNS", not missing, "ERROR",
            "Scenario data must include scenario_id, month, r_short, zcb_10y.",
            float(len(missing)), 0.0,
        ))
        if missing:
            return self._report(rate_model, checks, diagnostics)

        twist = self._twist_correlation(frame)
        diagnostics["short_long_change_correlation"] = twist
        diagnostics["short_tenor_years"] = self.short_tenor_years
        diagnostics["long_tenor_years"] = self.long_tenor_years
        checks.append(CurveTwistCheck(
            "CT-DECORRELATION",
            bool(np.isfinite(twist) and abs(twist) <= self.max_twist_correlation),
            "ERROR",
            "Short- and long-tenor rate changes must decorrelate "
            "(|corr| <= {:.3f}) to evidence genuine curve twist; a one-factor "
            "model cannot.".format(self.max_twist_correlation),
            float(abs(twist)) if np.isfinite(twist) else 1.0,
            self.max_twist_correlation,
        ))

        if "g2pp_x" in frame.columns and "g2pp_y" in frame.columns:
            dx, dy = self._panel_changes(frame, "g2pp_x", "r_short", 1.0)
            fxx = pd.DataFrame(frame).pivot(
                index="scenario_id", columns="month", values="g2pp_x"
            ).sort_index(axis=1).to_numpy(dtype=float)
            fyy = pd.DataFrame(frame).pivot(
                index="scenario_id", columns="month", values="g2pp_y"
            ).sort_index(axis=1).to_numpy(dtype=float)
            d_x = np.diff(fxx, axis=1).reshape(-1)
            d_y = np.diff(fyy, axis=1).reshape(-1)
            mask = np.isfinite(d_x) & np.isfinite(d_y)
            diagnostics["factor_change_correlation"] = self._correlation(
                d_x[mask], d_y[mask]
            )

        if benchmark_data is not None:
            bench = self._twist_correlation(pd.DataFrame(benchmark_data))
            diagnostics["benchmark_short_long_change_correlation"] = bench
            gap = (bench - twist) if (np.isfinite(bench) and np.isfinite(twist)) else 0.0
            diagnostics["decorrelation_gap_vs_benchmark"] = gap
            checks.append(CurveTwistCheck(
                "CT-VS-BENCHMARK",
                bool(gap >= self.benchmark_margin),
                "ERROR",
                "Two-factor twist correlation must sit at least {:.3f} below the "
                "one-factor benchmark.".format(self.benchmark_margin),
                float(gap), self.benchmark_margin,
            ))
        return self._report(rate_model, checks, diagnostics)

    def _report(self, rate_model, checks, diagnostics):
        passed = all(c.passed or c.severity != "ERROR" for c in checks)
        return CurveTwistEvidenceReport(
            rate_model=str(rate_model),
            passed=passed,
            checks=tuple(checks),
            diagnostics=diagnostics,
        )


@dataclass
class ScenarioSet:
    """Container for simulated economic scenario paths (rates + equity).

    Attributes
    ----------
    data : pd.DataFrame
        Combined scenario data.  Columns:
          scenario_id, month, r_short, zcb_1y, zcb_10y,
          equity_index, equity_return_1m, measure, and optional Phase 8
          fx_rate, fx_return_1m, fx_pair
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
    #: Measures this process is permitted to simulate under (G-05 / MR-004).
    SUPPORTED_MEASURES = (Measure.P, Measure.Q)


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

    def consumer_wide_view(self, consumer_id="reporting", base_currency=None, equity_market="CN"):
        """Return a consumer-ready v1 wide view with traceability attrs."""
        mapping = phase6_consumer_mapping(
            consumer_id,
            base_currency=base_currency or (
                self.metadata.base_currency if self.metadata is not None else "CNY"
            ),
            equity_market=equity_market,
        )
        return mapping.wide_view(self)

    def consumer_traceability(self, consumer_id="reporting", base_currency=None, equity_market="CN"):
        """Return report metadata required to trace this ScenarioSet."""
        mapping = phase6_consumer_mapping(
            consumer_id,
            base_currency=base_currency or (
                self.metadata.base_currency if self.metadata is not None else "CNY"
            ),
            equity_market=equity_market,
        )
        return mapping.traceability_attributes(self)

    def alm_annual_returns(self, scenario_id, month, base_currency=None, equity_market="CN"):
        """Return DynamicALMEngine annual returns for one scenario-month."""
        mapping = phase6_consumer_mapping(
            "dynamic_alm",
            base_currency=base_currency or (
                self.metadata.base_currency if self.metadata is not None else "CNY"
            ),
            equity_market=equity_market,
        )
        return mapping.annual_returns_for_alm(self, scenario_id, month)

    @classmethod
    def generate(
        cls,
        n,
        T_months,
        measure,
        hw_params=None,
        gbm_params=None,
        initial_curve=None,
        equity_factor=None,
        fx_factor=None,
        equity_model=None,
        seed=42,
        scenario_set_id=None,
        model_version="v1.0.0-dev",
        base_currency="CNY",
        valuation_date=None,
        parameter_snapshot=None,
        cap_zcb_at_par=True,
        rate_model="hw1f",
        g2_params=None,
    ):
        """Generate correlated short-rate + GBM equity scenarios.

        ``rate_model`` selects the short-rate process (roadmap 4.1 #7):
        ``"hw1f"`` (default) uses the one-factor Hull-White process;
        ``"g2pp"`` uses the two-factor Gaussian G2++ process (``g2_params``,
        a :class:`G2PlusParams`) and adds ``g2pp_x`` / ``g2pp_y`` diagnostic
        factor columns. The default path is byte-for-byte unchanged.

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
        initial_curve : RiskFreeCurve, optional
            Explicit initial risk-free curve for Q-measure HW1F fitting and
            zero-coupon bond pricing. If omitted, a flat curve at r(0) is used.
        equity_factor : RegionalEquityFactor, optional
            Phase 8 regional equity fixture. If supplied without gbm_params,
            its GBM parameters drive the v1-compatible equity columns.
        fx_factor : FXReturnFactor, optional
            Phase 8 currency-translation fixture. If supplied, generated data
            includes `fx_rate`, `fx_return_1m`, and `fx_pair` columns.
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
        measure = _enforce_simulation_measure(cls, measure)
        _validate_simulation_dimensions(n, T_months)
        n = int(n)
        T_months = int(T_months)

        if equity_factor is not None:
            if not isinstance(equity_factor, RegionalEquityFactor):
                raise TypeError("equity_factor must be a RegionalEquityFactor")
            if gbm_params is None:
                gbm_params = equity_factor.params
        if fx_factor is not None and not isinstance(fx_factor, FXReturnFactor):
            raise TypeError("fx_factor must be an FXReturnFactor")

        rate_model_key = resolve_rate_model(rate_model)
        if rate_model_key == "g2pp":
            rate_process = G2PlusRateProcess(g2_params, initial_curve=initial_curve)
        else:
            rate_process = HullWhiteRateProcess(hw_params, initial_curve=initial_curve)
        equity_model_label = resolve_equity_model(equity_model)
        gbm_process = build_equity_process(
            equity_model_label, gbm_params, rate_process=rate_process
        )
        fx_process = FXSpotProcess(fx_factor.params) if fx_factor is not None else None
        if parameter_snapshot is None:
            parameter_snapshot = ParameterSnapshot.from_process_params(
                measure=measure,
                base_currency=base_currency,
                calibration_date=valuation_date,
                hw_params=rate_process.params if rate_model_key == "hw1f" else None,
                g2_params=rate_process.params if rate_model_key == "g2pp" else None,
                gbm_params=gbm_process.params,
                initial_curve=rate_process.initial_curve,
                equity_factor=equity_factor,
                fx_factor=fx_factor,
            )

        rng = np.random.default_rng(seed)
        z_rate = _antithetic_normals(rng, n, T_months)
        z_independent = _antithetic_normals(rng, n, T_months)
        z_fx_independent = _antithetic_normals(rng, n, T_months)
        rho = gbm_process.params.rate_equity_correlation
        z_equity = rho * z_rate + np.sqrt(1.0 - rho ** 2) * z_independent

        # HW1F: single factor drives r. G2++: z_rate drives factor x (the
        # equity-correlated factor) and a fresh antithetic draw drives the
        # independent part of factor y. The extra draw is taken ONLY in the
        # g2pp branch and AFTER the hw1f draws, so the hw1f RNG stream (and
        # therefore every governed hw1f headline) is byte-for-byte unchanged.
        g2pp_x_paths = None
        g2pp_y_paths = None
        if rate_model_key == "g2pp":
            z_rate_secondary = _antithetic_normals(rng, n, T_months)
            g2pp_x_paths, g2pp_y_paths, rate_paths = rate_process._simulate_arrays(
                n, T_months, measure, z_rate, z_rate_secondary
            )
        else:
            rate_paths = rate_process._simulate_array(n, T_months, measure, z_rate)
        if isinstance(gbm_process, JumpDiffusionEquityProcess):
            jump_rng = np.random.default_rng(
                np.random.SeedSequence(seed).spawn(1)[0]
            )
            equity_paths, equity_returns, _equity_jumps = gbm_process._simulate_array(
                n, T_months, measure, rate_paths, z_equity, rng=jump_rng
            )
        else:
            equity_paths, equity_returns = gbm_process._simulate_array(
                n, T_months, measure, rate_paths, z_equity
            )
        fx_paths = None
        fx_returns = None
        if fx_process is not None:
            rho_fx = fx_process.params.rate_fx_correlation
            z_fx = rho_fx * z_rate + np.sqrt(1.0 - rho_fx ** 2) * z_fx_independent
            fx_paths, fx_returns = fx_process._simulate_array(
                n, T_months, measure, z_fx
            )

        scenario_ids, months = _month_grid(n, T_months)
        flat_rates = rate_paths.reshape(-1)
        times = months.astype(float) / 12.0

        zcb_1y = np.empty_like(flat_rates)
        zcb_10y = np.empty_like(flat_rates)
        if rate_model_key == "g2pp":
            flat_x = g2pp_x_paths.reshape(-1)
            flat_y = g2pp_y_paths.reshape(-1)
            for idx, (x_t, y_t, t) in enumerate(zip(flat_x, flat_y, times)):
                zcb_1y[idx] = rate_process.zcb_price(float(x_t), float(y_t), float(t), float(t + 1.0))
                zcb_10y[idx] = rate_process.zcb_price(float(x_t), float(y_t), float(t), float(t + 10.0))
        else:
            for idx, (r_t, t) in enumerate(zip(flat_rates, times)):
                zcb_1y[idx] = rate_process.zcb_price(float(r_t), float(t), float(t + 1.0))
                zcb_10y[idx] = rate_process.zcb_price(float(r_t), float(t), float(t + 10.0))
        if cap_zcb_at_par:
            zcb_1y = np.minimum(zcb_1y, 1.0)
            zcb_10y = np.minimum(zcb_10y, 1.0)

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
        if rate_model_key == "g2pp":
            data["g2pp_x"] = g2pp_x_paths.reshape(-1)
            data["g2pp_y"] = g2pp_y_paths.reshape(-1)
        if fx_factor is not None:
            data["fx_rate"] = fx_paths.reshape(-1)
            data["fx_return_1m"] = fx_returns.reshape(-1)
            data["fx_pair"] = fx_factor.pair
        _assert_output_measure(data, measure, "ScenarioSet")
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
    "MeasureEnforcementError",
    "CalibrationSource",
    "CalibrationFieldSpec",
    "CalibrationDataInterface",
    "default_phase6_calibration_interfaces",
    "ParameterSnapshot",
    "ScenarioMetadata",
    "ConsumerOutputMapping",
    "default_phase6_consumer_mappings",
    "phase6_consumer_mapping",
    "HullWhiteParams",
    "G2PlusParams",
    "resolve_rate_model",
    "available_rate_models",
    "RATE_MODEL_REGISTRY",
    "DEFAULT_RATE_MODEL",
    "CurveTwistValidator",
    "CurveTwistEvidenceReport",
    "CurveTwistCheck",
    "RiskFreeCurve",
    "MartingaleEvidenceCheck",
    "MartingaleEvidenceReport",
    "QMeasureMartingaleValidator",
    "YieldCurveValidationCheck",
    "YieldCurveValidationReport",
    "YieldCurveValidator",
    "available_starter_curve_currencies",
    "starter_risk_free_curve",
    "default_phase7_starter_curves",
    "GBMParams",
    "RegionalEquityFactor",
    "available_starter_equity_markets",
    "starter_equity_factor",
    "default_phase8_equity_factors",
    "FXParams",
    "FXReturnFactor",
    "available_starter_fx_pairs",
    "starter_fx_factor",
    "fx_factor_for_translation",
    "default_phase8_fx_factors",
    "phase8_rate_equity_fx_correlation_matrix",
    "CorrelationMatrixValidationCheck",
    "CorrelationMatrixValidationReport",
    "CorrelationMatrixValidator",
    "PMeasureBacktestCheck",
    "PMeasureBacktestReport",
    "PMeasureBacktestValidator",
    "HullWhiteRateProcess",
    "G2PlusRateProcess",
    "GBMEquityProcess",
    "JumpDiffusionParams",
    "JumpDiffusionEquityProcess",
    "build_equity_process",
    "resolve_equity_model",
    "available_equity_models",
    "EQUITY_PROCESS_REGISTRY",
    "DEFAULT_EQUITY_MODEL",
    "EquityForwardMartingaleValidator",
    "FXSpotProcess",
    "ScenarioSet",
    "_coerce_measure",
    "_validate_simulation_dimensions",
    "_month_grid",
    "_antithetic_normals",
]
