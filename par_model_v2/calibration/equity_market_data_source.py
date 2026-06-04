"""
Equity Market Data Source — CSI 300 / HSI History Loader for Phase 14 GBM Calibration
======================================================================================

Vendor-agnostic abstraction layer that feeds historical equity returns, a matched
risk-free series, a trailing dividend-yield series, and an ATM implied vol into the
``GBMCalibrator`` (``par_model_v2.calibration.calibration_framework``).

Production Gates Addressed
--------------------------
G-03 : GBM equity parameters (sigma_S, ERP, dividend yield, rho_{r,S}) calibrated to
       market data (not placeholders), with values inside documented plausibility
       bands and the change recorded through governance.  Blocking risk MR-002.
G-12-style lineage : a ``DataLineageRecord`` (reused from ``market_data_source``) is
       produced for every market for source-to-output traceability (IA TAS M 3.6).

Educational-proxy synthesis
---------------------------
``FileBasedEquitySource`` does NOT ship a multi-thousand-row daily price file.  It
ships a compact, human-auditable fixture of *documented* annual statistics (calendar
total returns, year-average risk-free yields, target volatility, target rate-equity
correlation, dividend base, implied vol) and deterministically expands them into a
daily log-return series and a matched daily risk-free series.  The expansion is fully
reproducible from the fixture ``seed`` and is designed so the calibrator recovers the
documented moments:

  * daily equity log-returns are drawn from a seeded Gaussian with daily vol
    ``target_annual_vol / sqrt(252)`` and **de-meaned per calendar year** so the
    compounded annual total return equals the documented value exactly;
  * a Cholesky-correlated rate shock drives an intra-year random-walk deviation of the
    risk-free yield around its documented year average, so the realised Pearson
    correlation between equity log-returns and yield changes recovers
    ``target_rate_equity_corr``.

Standards References
--------------------
SOA ASOP 25 3.3 (credibility / historical estimation), SOA ASOP 56 3.4 (calibration
documentation), IA TAS M 3.5 / 3.6, docs/PARAMETER_CALIBRATION_METHODOLOGY.md 6.

PRODUCTION USE RESTRICTION
--------------------------
File-based fixtures are educational proxies.  Replace with credentialled live-API
fetches (CSI / ChinaBond / Wind / HKMA / Bloomberg) and re-run the sign-off workflow
before regulatory, pricing, or capital-adequacy use.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from par_model_v2.calibration.calibration_framework import GBMCalibrationInputs
from par_model_v2.calibration.market_data_source import (
    DataLineageRecord,
    ProductionGateStatus,
)


# ---------------------------------------------------------------------------
# 1. Abstract source
# ---------------------------------------------------------------------------

class EquityMarketDataSource(ABC):
    """Abstract source of equity / risk-free / dividend history for one market."""

    @property
    @abstractmethod
    def market(self) -> str: ...

    @abstractmethod
    def build_calibration_inputs(self) -> GBMCalibrationInputs: ...

    @abstractmethod
    def build_lineage_record(self) -> DataLineageRecord: ...


# ---------------------------------------------------------------------------
# 2. Deterministic educational-proxy synthesis
# ---------------------------------------------------------------------------

def synthesize_equity_history(spec: Dict[str, Any]) -> Tuple[pd.Series, pd.Series, pd.Series, date]:
    """Expand a documented-statistics fixture into daily series for calibration.

    Parameters
    ----------
    spec : dict
        Parsed fixture dict (see fixtures/cny_equity_history_20260101.json).

    Returns
    -------
    equity_returns : pd.Series
        Daily log-returns indexed by business day.
    rf_returns : pd.Series
        Daily annualised risk-free rate, same index.
    dividend_yield_monthly : pd.Series
        Monthly trailing dividend yield (>= 36 months).
    calibration_date : datetime.date
        Fixture as-of date.
    """
    syn = spec["daily_synthesis"]
    seed = int(syn["seed"])
    rng = np.random.default_rng(seed)

    start = pd.Timestamp(syn["start_date"])
    end = pd.Timestamp(syn["end_date"])
    dates = pd.bdate_range(start=start, end=end)
    n = len(dates)

    target_vol = float(spec["target_annual_vol"])
    sigma_daily = target_vol / np.sqrt(float(syn.get("trading_days_per_year", 252)))
    rho = float(spec["target_rate_equity_corr"])
    rate_vol = float(spec["rate_deviation_vol_daily"])

    annual_eq = {int(y): float(r) for y, r in spec["annual_equity_returns"].items()}
    annual_rf = {int(y): float(r) for y, r in spec["annual_rf_1y"].items()}

    # Correlated standard-normal shocks: column 0 = equity, column 1 = rate.
    L = np.linalg.cholesky(np.array([[1.0, rho], [rho, 1.0]]))
    z = rng.standard_normal((n, 2)) @ L.T
    eq_shock = z[:, 0]
    r_shock = z[:, 1]

    years = dates.year.to_numpy()
    eq_log = np.zeros(n)
    rf = np.zeros(n)

    for y in np.unique(years):
        mask = years == y
        idx = np.where(mask)[0]
        ndays = idx.size
        # --- equity: de-mean the year's shocks so compounded annual return is exact
        shocks = eq_shock[idx]
        shocks = shocks - shocks.mean()
        target_log = np.log1p(annual_eq.get(int(y), 0.0))
        eq_log[idx] = target_log / ndays + sigma_daily * shocks
        # --- risk-free: intra-year random walk around the documented year average
        dev = np.cumsum(rate_vol * r_shock[idx])
        rf[idx] = annual_rf.get(int(y), 0.02) + dev

    rf = np.clip(rf, 0.0005, 0.12)

    equity_returns = pd.Series(eq_log, index=dates, name="{}_eq_logret".format(spec["market"]))
    rf_returns = pd.Series(rf, index=dates, name="{}_rf_1y".format(spec["market"]))

    # Monthly trailing dividend yield (>= 36 months) — deterministic seeded wiggle.
    months = pd.period_range(start=start, end=end, freq="M")
    div_base = float(spec["dividend_yield_base"])
    div_noise = float(spec.get("dividend_yield_noise", 0.0))
    div_rng = np.random.default_rng(seed + 7)
    div_vals = div_base + div_noise * div_rng.standard_normal(len(months))
    div_vals = np.clip(div_vals, 0.001, 0.10)
    dividend_yield_monthly = pd.Series(
        div_vals, index=months.to_timestamp(how="end"), name="{}_div_yield".format(spec["market"])
    )

    cal_date = date.fromisoformat(spec["as_of_date"])
    return equity_returns, rf_returns, dividend_yield_monthly, cal_date


class FileBasedEquitySource(EquityMarketDataSource):
    """Reads a documented-statistics equity fixture and synthesizes daily series."""

    def __init__(self, fixture_path) -> None:
        self._path = Path(fixture_path)
        if not self._path.exists():
            raise FileNotFoundError("Equity fixture not found: {}".format(self._path.resolve()))
        raw_bytes = self._path.read_bytes()
        self._sha256 = hashlib.sha256(raw_bytes).hexdigest()
        self._data: Dict[str, Any] = json.loads(raw_bytes.decode("utf-8"))

    @property
    def market(self) -> str:
        return self._data["market"]

    @property
    def currency(self) -> str:
        return self._data.get("currency", self._data["market"])

    def build_calibration_inputs(self) -> GBMCalibrationInputs:
        eq, rf, div, cal_date = synthesize_equity_history(self._data)
        return GBMCalibrationInputs(
            calibration_date=cal_date,
            equity_returns=eq,
            rf_returns=rf,
            dividend_yield_monthly=div,
            implied_vol_atm=float(self._data.get("implied_vol_atm", np.nan)),
            implied_vol_weight=float(self._data.get("implied_vol_weight", 0.60)),
            erp_survivorship_adjustment=float(self._data.get("erp_survivorship_adjustment", 0.007)),
            erp_upper_bound=float(self._data.get("erp_upper_bound", 0.05)),
        )

    def build_lineage_record(self) -> DataLineageRecord:
        lin = self._data.get("data_lineage", {})
        raw_checksum = lin.get("checksum_sha256", "educational_fixture_no_checksum")
        effective = self._sha256 if raw_checksum == "educational_fixture_no_checksum" else raw_checksum
        return DataLineageRecord(
            lineage_id="LINEQ_{}_{}".format(self.market, self._data["as_of_date"].replace("-", "")),
            market=self.market,
            as_of_date=self._data["as_of_date"],
            source_type=lin.get("provenance", "educational_historical_proxy"),
            source_detail=str(self._path.resolve()),
            fixture_version=lin.get("version", "unknown"),
            approved_by=lin.get("approved_by", "unknown"),
            approval_timestamp=lin.get("approval_timestamp", "unknown"),
            sha256_checksum=effective,
        )

    @property
    def fixture_id(self) -> str:
        return self._data.get("fixture_id", "UNKNOWN")


# ---------------------------------------------------------------------------
# 3. Loader
# ---------------------------------------------------------------------------

class EquityDataLoader:
    """Loads an equity fixture and returns ``GBMCalibrationInputs`` + lineage."""

    def __init__(self, source: EquityMarketDataSource, min_daily_obs: int = 750) -> None:
        self._source = source
        self._min_obs = min_daily_obs

    @property
    def market(self) -> str:
        return self._source.market

    def load(self) -> Tuple[GBMCalibrationInputs, DataLineageRecord]:
        inputs = self._source.build_calibration_inputs()
        lineage = self._source.build_lineage_record()
        self._validate(inputs)
        return inputs, lineage

    def _validate(self, inputs: GBMCalibrationInputs) -> None:
        n = len(inputs.equity_returns)
        if n < self._min_obs:
            raise ValueError(
                "{}: only {} daily equity observations; need >= {} (SOA ASOP 25 3.3).".format(
                    self.market, n, self._min_obs
                )
            )
        if len(inputs.rf_returns) != n:
            raise ValueError(
                "{}: rf series length {} != equity length {} (align calendars).".format(
                    self.market, len(inputs.rf_returns), n
                )
            )
        if len(inputs.dividend_yield_monthly) < 36:
            raise ValueError(
                "{}: only {} dividend-yield months; need >= 36.".format(
                    self.market, len(inputs.dividend_yield_monthly)
                )
            )


def default_fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def build_equity_loader(
    market: str,
    fixture_dir=None,
    as_of_date: str = "20260101",
) -> EquityDataLoader:
    """Build an ``EquityDataLoader`` from the bundled fixture files.

    Parameters
    ----------
    market : str
        "CNY" or "HK".  Maps to ``<market.lower()>_equity_history_<as_of_date>.json``.
    """
    if fixture_dir is None:
        fixture_dir = default_fixture_dir()
    fixture_dir = Path(fixture_dir)
    filename = "{}_equity_history_{}.json".format(market.lower(), as_of_date)
    source = FileBasedEquitySource(fixture_dir / filename)
    return EquityDataLoader(source)


# ---------------------------------------------------------------------------
# 4. G-03 gate evaluation
# ---------------------------------------------------------------------------

# Plausibility bands (deployment checklist G-03 verification criteria).
SIGMA_S_MIN, SIGMA_S_MAX = 0.15, 0.45
RHO_MIN, RHO_MAX = -0.5, 0.5
MIN_DAILY_OBS = 750


@dataclass
class EquityCalibrationCheck:
    """Per-market G-03 criterion outcomes."""
    market: str
    n_daily_obs: int
    sigma_S: float
    erp: float
    dividend_yield: float
    rho: float
    is_placeholder: bool
    criteria: Dict[str, bool] = field(default_factory=dict)

    def all_pass(self) -> bool:
        return bool(self.criteria) and all(self.criteria.values())


def check_equity_calibration(
    market: str,
    n_daily_obs: int,
    result,
    has_param_change_audit: bool,
) -> EquityCalibrationCheck:
    """Score the six G-03 verification criteria for one market."""
    criteria = {
        "c1_min_daily_obs": n_daily_obs >= MIN_DAILY_OBS,
        "c2_sigma_in_band": SIGMA_S_MIN <= result.sigma_S <= SIGMA_S_MAX,
        "c3_erp_documented": (result.erp > 0.0)
        and (result.erp <= 0.05 + 1e-9)
        and (result.dividend_yield > 0.0),
        "c4_rho_in_band": RHO_MIN <= result.rho <= RHO_MAX,
        "c5_not_placeholder": not result.is_placeholder,
        "c6_param_change_audit": bool(has_param_change_audit),
    }
    return EquityCalibrationCheck(
        market=market,
        n_daily_obs=n_daily_obs,
        sigma_S=float(result.sigma_S),
        erp=float(result.erp),
        dividend_yield=float(result.dividend_yield),
        rho=float(result.rho),
        is_placeholder=bool(result.is_placeholder),
        criteria=criteria,
    )


def evaluate_g03_gate(checks: List[EquityCalibrationCheck]) -> ProductionGateStatus:
    """Evaluate G-03: GBM equity parameters calibrated to market data.

    PASS requires every market to clear all six verification criteria
    (>= 750 daily obs; sigma_S in [0.15, 0.45]; ERP documented, positive and
    capped with dividend EWMA applied; rho in [-0.5, 0.5]; not placeholder; and
    a PARAM_CHANGE audit entry recorded).  SOA ASOP 56 3.4.
    """
    fails: List[str] = []
    ev: List[str] = []
    for c in checks:
        failed = [k for k, ok in c.criteria.items() if not ok]
        if failed:
            fails.append("{}: failed {}".format(c.market, ", ".join(failed)))
        ev.append(
            "{}: n={}, sigma_S={:.4f}, ERP={:.4f}, div={:.4f}, rho={:.4f}".format(
                c.market, c.n_daily_obs, c.sigma_S, c.erp, c.dividend_yield, c.rho
            )
        )
    status = "PASS" if not fails else "FAIL"
    return ProductionGateStatus(
        gate_id="G-03",
        gate_description=(
            "GBM equity parameters (sigma_S, ERP, dividend yield, rho) calibrated to "
            "market data (not placeholders); sigma_S in [{:.2f}, {:.2f}], rho in "
            "[{:.1f}, {:.1f}], ERP documented and capped (SOA ASOP 56 3.4)".format(
                SIGMA_S_MIN, SIGMA_S_MAX, RHO_MIN, RHO_MAX
            )
        ),
        status=status,
        evidence="; ".join(ev + fails),
    )


__all__ = [
    "EquityMarketDataSource",
    "FileBasedEquitySource",
    "EquityDataLoader",
    "synthesize_equity_history",
    "build_equity_loader",
    "default_fixture_dir",
    "EquityCalibrationCheck",
    "check_equity_calibration",
    "evaluate_g03_gate",
    "SIGMA_S_MIN",
    "SIGMA_S_MAX",
    "RHO_MIN",
    "RHO_MAX",
    "MIN_DAILY_OBS",
]
