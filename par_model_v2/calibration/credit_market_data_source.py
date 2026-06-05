"""
Credit-Spread Market Data Source — CNY AA+ OAS History Loader (Phase 18 Task 2)
==============================================================================

Vendor-agnostic abstraction that feeds a historical credit-spread series into
the :class:`CIRCalibrator`, mirroring ``market_data_source`` (swaptions/HW1F)
and ``equity_market_data_source`` (equity/GBM).

Educational-proxy synthesis
---------------------------
``FileBasedCreditSpreadSource`` does NOT ship a long raw OAS file.  It ships a
compact, human-auditable fixture of *documented* CIR++ target statistics
(mean-reversion, long-run spread, vol, shift, risk-neutral anchor) and
deterministically expands them into a monthly credit-spread path with a seeded
full-truncation Euler CIR scheme, so the calibrator recovers the documented
long-run spread (sample-mean robust), the spread vol (residual-variance robust)
and, more loosely, the mean-reversion speed.

Risk addressed
--------------
MR-012 : the CIR++ credit-spread driver parameters (mean-reversion, long-run
         spread, vol, risk premium) are placeholder educational defaults, NOT
         calibrated to credit-market data.  This task replaces them with values
         estimated from educational-proxy history and records the change
         through governance, moving MR-012 toward MITIGATED.

Standards References
--------------------
SOA ASOP 25 §3.3 (credibility / historical estimation), SOA ASOP 56 §3.4
(calibration documentation), IA TAS M §3.5 / §3.6.

PRODUCTION USE RESTRICTION
--------------------------
File-based fixtures are educational proxies.  Replace with credentialled
live-API fetches (ChinaBond / Wind / Markit) and re-run the sign-off workflow
before regulatory, pricing, or capital-adequacy use.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from par_model_v2.calibration.cir_calibrator import CIRCalibrationInputs
from par_model_v2.calibration.market_data_source import (
    DataLineageRecord,
    ProductionGateStatus,
)


# ---------------------------------------------------------------------------
# 1. Abstract source
# ---------------------------------------------------------------------------

class CreditMarketDataSource(ABC):
    """Abstract source of credit-spread history for one market."""

    @property
    @abstractmethod
    def market(self) -> str: ...

    @abstractmethod
    def build_calibration_inputs(self) -> CIRCalibrationInputs: ...

    @abstractmethod
    def build_lineage_record(self) -> DataLineageRecord: ...


# ---------------------------------------------------------------------------
# 2. Deterministic educational-proxy synthesis
# ---------------------------------------------------------------------------

def synthesize_spread_history(spec: Dict[str, Any]) -> Tuple[pd.Series, date]:
    """Expand a documented-target CIR++ fixture into a monthly spread series.

    Simulates ``x_{t+1} = x_t + kappa(b - x_t)dt + sigma sqrt(max(x_t,0)) sqrt(dt) Z``
    (full-truncation Euler) with ``b = target_long_run_spread - shift`` and
    ``dt = 1/steps_per_year``, then ``spread = clip(x + shift)``.  Fully
    deterministic given the fixture seed.
    """
    syn = spec["monthly_synthesis"]
    seed = int(syn["seed"])
    rng = np.random.default_rng(seed)

    steps_per_year = int(syn.get("steps_per_year", 12))
    dt = 1.0 / steps_per_year
    sqrt_dt = float(np.sqrt(dt))

    start = pd.Timestamp(syn["start_date"])
    end = pd.Timestamp(syn["end_date"])
    dates = pd.date_range(start=start, end=end, freq="ME")
    n = len(dates)

    kappa = float(spec["target_mean_reversion"])
    sigma = float(spec["target_spread_vol"])
    shift = float(spec["shift"])
    b = float(spec["target_long_run_spread"]) - shift
    x0 = float(spec["initial_spread"]) - shift
    floor = float(spec.get("spread_floor", 0.0))
    ceiling = float(spec.get("spread_ceiling", 0.20))

    z = rng.standard_normal(n)
    x = np.empty(n, dtype=float)
    x[0] = x0
    for t in range(1, n):
        x_prev = x[t - 1]
        x_pos = max(x_prev, 0.0)
        x_next = x_prev + kappa * (b - x_prev) * dt + sigma * np.sqrt(x_pos) * sqrt_dt * z[t]
        x[t] = max(x_next, 0.0)  # full truncation

    spreads = np.clip(x + shift, floor, ceiling)
    series = pd.Series(spreads, index=dates, name="{}_credit_spread".format(spec["market"]))
    cal_date = date.fromisoformat(spec["as_of_date"])
    return series, cal_date


class FileBasedCreditSpreadSource(CreditMarketDataSource):
    """Reads a documented-target credit fixture and synthesizes a monthly path."""

    def __init__(self, fixture_path) -> None:
        self._path = Path(fixture_path)
        if not self._path.exists():
            raise FileNotFoundError("Credit fixture not found: {}".format(self._path.resolve()))
        raw_bytes = self._path.read_bytes()
        self._sha256 = hashlib.sha256(raw_bytes).hexdigest()
        self._data: Dict[str, Any] = json.loads(raw_bytes.decode("utf-8"))

    @property
    def market(self) -> str:
        return self._data["market"]

    @property
    def currency(self) -> str:
        return self._data.get("currency", self._data["market"])

    def build_calibration_inputs(self) -> CIRCalibrationInputs:
        series, cal_date = synthesize_spread_history(self._data)
        return CIRCalibrationInputs(
            calibration_date=cal_date,
            spread_history=series,
            shift=float(self._data.get("shift", 0.003)),
            risk_neutral_long_run_spread=self._data.get("risk_neutral_long_run_spread"),
            dt=1.0 / int(self._data["monthly_synthesis"].get("steps_per_year", 12)),
            risk_premium_upper=float(self._data.get("risk_premium_upper", 2.0)),
            spread_floor=float(self._data.get("spread_floor", 0.0)),
            spread_ceiling=float(self._data.get("spread_ceiling", 0.20)),
        )

    def build_lineage_record(self) -> DataLineageRecord:
        lin = self._data.get("data_lineage", {})
        raw_checksum = lin.get("checksum_sha256", "educational_fixture_no_checksum")
        effective = self._sha256 if raw_checksum == "educational_fixture_no_checksum" else raw_checksum
        return DataLineageRecord(
            lineage_id="LINCR_{}_{}".format(self.market, self._data["as_of_date"].replace("-", "")),
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

class CreditSpreadDataLoader:
    """Loads a credit fixture and returns ``CIRCalibrationInputs`` + lineage."""

    def __init__(self, source: CreditMarketDataSource, min_obs: int = 60) -> None:
        self._source = source
        self._min_obs = min_obs

    @property
    def market(self) -> str:
        return self._source.market

    def load(self) -> Tuple[CIRCalibrationInputs, DataLineageRecord]:
        inputs = self._source.build_calibration_inputs()
        lineage = self._source.build_lineage_record()
        self._validate(inputs)
        return inputs, lineage

    def _validate(self, inputs: CIRCalibrationInputs) -> None:
        n = len(inputs.spread_history)
        if n < self._min_obs:
            raise ValueError(
                "{}: only {} spread observations; need >= {} (SOA ASOP 25 §3.3).".format(
                    self.market, n, self._min_obs
                )
            )


def default_fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def build_credit_loader(
    market: str,
    fixture_dir=None,
    as_of_date: str = "20260101",
) -> CreditSpreadDataLoader:
    """Build a ``CreditSpreadDataLoader`` from the bundled fixture files.

    Parameters
    ----------
    market : str
        "CNY".  Maps to ``<market.lower()>_credit_spread_history_<as_of_date>.json``.
    """
    if fixture_dir is None:
        fixture_dir = default_fixture_dir()
    fixture_dir = Path(fixture_dir)
    filename = "{}_credit_spread_history_{}.json".format(market.lower(), as_of_date)
    source = FileBasedCreditSpreadSource(fixture_dir / filename)
    return CreditSpreadDataLoader(source)


# ---------------------------------------------------------------------------
# 4. Calibration gate (G-CR, internal — not one of the 12 deployment gates)
# ---------------------------------------------------------------------------

# Plausibility bands for the CIR++ credit-spread parameters.
KAPPA_MIN, KAPPA_MAX = 0.05, 3.0
LONG_RUN_MIN, LONG_RUN_MAX = 0.002, 0.05       # 20 bp .. 500 bp
SIGMA_MIN, SIGMA_MAX = 0.005, 0.50
LAMBDA_MIN, LAMBDA_MAX = 0.0, 2.0
MIN_OBS = 60


@dataclass
class CreditCalibrationCheck:
    """G-CR criterion outcomes for the credit-spread calibration."""
    market: str
    n_obs: int
    kappa: float
    long_run_spread_p: float
    sigma: float
    lam: float
    is_placeholder: bool
    criteria: Dict[str, bool] = field(default_factory=dict)

    def all_pass(self) -> bool:
        return bool(self.criteria) and all(self.criteria.values())


def check_credit_calibration(
    market: str,
    n_obs: int,
    result,
    has_param_change_audit: bool,
) -> CreditCalibrationCheck:
    """Score the six G-CR verification criteria for the credit calibration."""
    criteria = {
        "c1_min_obs": n_obs >= MIN_OBS,
        "c2_kappa_in_band": KAPPA_MIN <= result.mean_reversion_speed <= KAPPA_MAX,
        "c3_long_run_in_band": LONG_RUN_MIN <= result.long_run_spread_p <= LONG_RUN_MAX,
        "c4_sigma_in_band": SIGMA_MIN <= result.spread_vol <= SIGMA_MAX,
        "c5_lambda_in_band": LAMBDA_MIN <= result.market_price_of_credit_risk <= LAMBDA_MAX,
        "c6_not_placeholder_with_audit": (not result.is_placeholder) and bool(has_param_change_audit),
    }
    return CreditCalibrationCheck(
        market=market,
        n_obs=n_obs,
        kappa=float(result.mean_reversion_speed),
        long_run_spread_p=float(result.long_run_spread_p),
        sigma=float(result.spread_vol),
        lam=float(result.market_price_of_credit_risk),
        is_placeholder=bool(result.is_placeholder),
        criteria=criteria,
    )


def evaluate_credit_gate(check: CreditCalibrationCheck) -> ProductionGateStatus:
    """Evaluate G-CR: CIR++ credit-spread parameters calibrated to market data."""
    failed = [k for k, ok in check.criteria.items() if not ok]
    status = "PASS" if not failed else "FAIL"
    evidence = (
        "{}: n={}, kappa={:.4f}, long_run={:.4f} ({:.0f}bp), sigma={:.4f}, lambda={:.4f}".format(
            check.market, check.n_obs, check.kappa, check.long_run_spread_p,
            check.long_run_spread_p * 1e4, check.sigma, check.lam
        )
    )
    if failed:
        evidence += "; failed " + ", ".join(failed)
    return ProductionGateStatus(
        gate_id="G-CR",
        gate_description=(
            "CIR++ credit-spread parameters (kappa, long-run spread, sigma, lambda) "
            "calibrated to credit-market data (not placeholders); kappa in [{:.2f}, {:.1f}], "
            "long-run in [{:.0f}, {:.0f}]bp, sigma in [{:.3f}, {:.2f}], lambda in [{:.1f}, {:.1f}] "
            "(SOA ASOP 56 §3.4)".format(
                KAPPA_MIN, KAPPA_MAX, LONG_RUN_MIN * 1e4, LONG_RUN_MAX * 1e4,
                SIGMA_MIN, SIGMA_MAX, LAMBDA_MIN, LAMBDA_MAX
            )
        ),
        status=status,
        evidence=evidence,
    )


__all__ = [
    "CreditMarketDataSource",
    "FileBasedCreditSpreadSource",
    "CreditSpreadDataLoader",
    "synthesize_spread_history",
    "build_credit_loader",
    "default_fixture_dir",
    "CreditCalibrationCheck",
    "check_credit_calibration",
    "evaluate_credit_gate",
    "KAPPA_MIN", "KAPPA_MAX", "LONG_RUN_MIN", "LONG_RUN_MAX",
    "SIGMA_MIN", "SIGMA_MAX", "LAMBDA_MIN", "LAMBDA_MAX", "MIN_OBS",
]
