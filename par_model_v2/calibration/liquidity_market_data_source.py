"""
Liquidity-Premium Market Data Source — HKD Funding-Spread History Loader (Phase 21 Task 3)
==========================================================================================

Vendor-agnostic abstraction that feeds a historical liquidity-premium /
funding-spread series into the :class:`LiquidityPremiumCalibrator`, mirroring
``market_data_source`` (swaptions/HW1F), ``equity_market_data_source``
(equity/GBM), ``credit_market_data_source`` (credit/CIR++), and
``lapse_experience_data_source`` (lapse/OU).

Educational-proxy synthesis
---------------------------
``FileBasedLiquidityPremiumSource`` does NOT ship a raw market file.  It ships
a compact, human-auditable fixture of *documented* CIR++ target statistics
(mean-reversion, long-run premium, vol, shift, risk-neutral anchor) and
deterministically expands them into a monthly liquidity-premium path with a
seeded full-truncation Euler CIR scheme — identical synthesis to the credit
fixture — so the calibrator recovers the documented long-run premium
(sample-mean robust), the premium vol (residual-variance robust) and, more
loosely, the mean-reversion speed.

Risk addressed
--------------
MR-012 : the multi-driver economic-capital proxy carried "liquidity" as the
         last documented-but-omitted driver.  This task adds the calibrated
         CIR++ liquidity-premium driver and records the change through
         governance.  MR-011 : the proxy is educational; the calibration
         tightens the educational basis.

Standards References
--------------------
SOA ASOP 25 3.3 (credibility / historical estimation), SOA ASOP 56 3.4
(calibration documentation), IA TAS M 3.5 / 3.6; EIOPA volatility-adjustment
methodology (illiquidity-premium component of asset spreads).

PRODUCTION USE RESTRICTION
--------------------------
File-based fixtures are educational proxies.  Replace with credentialled
liquidity-premium extracts (covered-bond / swap-basis or VA-component series
from an approved vendor) and re-run the sign-off workflow before regulatory,
pricing, or capital-adequacy use.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

from par_model_v2.calibration.liquidity_calibrator import LiquidityCalibrationInputs
from par_model_v2.calibration.market_data_source import (
    DataLineageRecord,
    ProductionGateStatus,
)


# ---------------------------------------------------------------------------
# 1. Abstract source
# ---------------------------------------------------------------------------

class LiquidityMarketDataSource(ABC):
    """Abstract source of liquidity-premium history for one market."""

    @property
    @abstractmethod
    def market(self) -> str: ...

    @abstractmethod
    def build_calibration_inputs(self) -> LiquidityCalibrationInputs: ...

    @abstractmethod
    def build_lineage_record(self) -> DataLineageRecord: ...


# ---------------------------------------------------------------------------
# 2. Deterministic educational-proxy synthesis
# ---------------------------------------------------------------------------

def synthesize_premium_history(spec: Dict[str, Any]) -> Tuple[pd.Series, date]:
    """Expand a documented-target CIR++ fixture into a monthly premium series.

    Simulates ``x_{t+1} = x_t + kappa(b - x_t)dt + sigma sqrt(max(x_t,0)) sqrt(dt) Z``
    (full-truncation Euler) with ``b = target_long_run_premium - shift`` and
    ``dt = 1/steps_per_year``, then ``premium = clip(x + shift)``.  Fully
    deterministic given the fixture seed (identical scheme to the credit
    fixture synthesis).
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
    sigma = float(spec["target_premium_vol"])
    shift = float(spec["shift"])
    b = float(spec["target_long_run_premium"]) - shift
    x0 = float(spec["initial_premium"]) - shift
    floor = float(spec.get("premium_floor", 0.0))
    ceiling = float(spec.get("premium_ceiling", 0.10))

    z = rng.standard_normal(n)
    x = np.empty(n, dtype=float)
    x[0] = x0
    for t in range(1, n):
        x_prev = x[t - 1]
        x_pos = max(x_prev, 0.0)
        x_next = x_prev + kappa * (b - x_prev) * dt + sigma * np.sqrt(x_pos) * sqrt_dt * z[t]
        x[t] = max(x_next, 0.0)  # full truncation

    premia = np.clip(x + shift, floor, ceiling)
    series = pd.Series(premia, index=dates, name="{}_liquidity_premium".format(spec["market"]))
    cal_date = date.fromisoformat(spec["as_of_date"])
    return series, cal_date


class FileBasedLiquidityPremiumSource(LiquidityMarketDataSource):
    """Reads a documented-target liquidity fixture and synthesizes a monthly path."""

    def __init__(self, fixture_path) -> None:
        self._path = Path(fixture_path)
        if not self._path.exists():
            raise FileNotFoundError("Liquidity fixture not found: {}".format(self._path.resolve()))
        raw_bytes = self._path.read_bytes()
        self._sha256 = hashlib.sha256(raw_bytes).hexdigest()
        self._data: Dict[str, Any] = json.loads(raw_bytes.decode("utf-8"))

    @property
    def market(self) -> str:
        return self._data["market"]

    @property
    def currency(self) -> str:
        return self._data.get("currency", self._data["market"])

    def build_calibration_inputs(self) -> LiquidityCalibrationInputs:
        series, cal_date = synthesize_premium_history(self._data)
        return LiquidityCalibrationInputs(
            calibration_date=cal_date,
            premium_history=series,
            shift=float(self._data.get("shift", 0.001)),
            risk_neutral_long_run_premium=self._data.get("risk_neutral_long_run_premium"),
            dt=1.0 / int(self._data["monthly_synthesis"].get("steps_per_year", 12)),
            risk_premium_upper=float(self._data.get("risk_premium_upper", 2.0)),
            premium_floor=float(self._data.get("premium_floor", 0.0)),
            premium_ceiling=float(self._data.get("premium_ceiling", 0.10)),
        )

    def build_lineage_record(self) -> DataLineageRecord:
        lin = self._data.get("data_lineage", {})
        raw_checksum = lin.get("checksum_sha256", "educational_fixture_no_checksum")
        effective = self._sha256 if raw_checksum == "educational_fixture_no_checksum" else raw_checksum
        return DataLineageRecord(
            lineage_id="LINLIQ_{}_{}".format(self.market, self._data["as_of_date"].replace("-", "")),
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

class LiquidityPremiumDataLoader:
    """Loads a liquidity fixture and returns ``LiquidityCalibrationInputs`` + lineage."""

    def __init__(self, source: LiquidityMarketDataSource, min_obs: int = 60) -> None:
        self._source = source
        self._min_obs = min_obs

    @property
    def market(self) -> str:
        return self._source.market

    def load(self) -> Tuple[LiquidityCalibrationInputs, DataLineageRecord]:
        inputs = self._source.build_calibration_inputs()
        lineage = self._source.build_lineage_record()
        self._validate(inputs)
        return inputs, lineage

    def _validate(self, inputs: LiquidityCalibrationInputs) -> None:
        n = len(inputs.premium_history)
        if n < self._min_obs:
            raise ValueError(
                "{}: only {} premium observations; need >= {} (SOA ASOP 25 3.3).".format(
                    self.market, n, self._min_obs
                )
            )


def default_fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def build_liquidity_loader(
    market: str = "HKD",
    fixture_dir=None,
    as_of_date: str = "20260101",
) -> LiquidityPremiumDataLoader:
    """Build a ``LiquidityPremiumDataLoader`` from the bundled fixture files.

    Parameters
    ----------
    market : str
        "HKD".  Maps to ``<market.lower()>_liquidity_premium_history_<as_of_date>.json``.
    """
    if fixture_dir is None:
        fixture_dir = default_fixture_dir()
    fixture_dir = Path(fixture_dir)
    filename = "{}_liquidity_premium_history_{}.json".format(market.lower(), as_of_date)
    source = FileBasedLiquidityPremiumSource(fixture_dir / filename)
    return LiquidityPremiumDataLoader(source)


# ---------------------------------------------------------------------------
# 4. Calibration gate (G-LIQ, internal — not one of the 12 deployment gates)
# ---------------------------------------------------------------------------

# Plausibility bands for the CIR++ liquidity-premium parameters.
KAPPA_MIN, KAPPA_MAX = 0.05, 3.0
LONG_RUN_MIN, LONG_RUN_MAX = 0.001, 0.03       # 10 bp .. 300 bp
SIGMA_MIN, SIGMA_MAX = 0.003, 0.30
LAMBDA_MIN, LAMBDA_MAX = 0.0, 2.0
MIN_OBS = 60


@dataclass
class LiquidityCalibrationCheck:
    """G-LIQ criterion outcomes for the liquidity-premium calibration."""
    market: str
    n_obs: int
    kappa: float
    long_run_premium_p: float
    sigma: float
    lam: float
    is_placeholder: bool
    criteria: Dict[str, bool] = field(default_factory=dict)

    def all_pass(self) -> bool:
        return bool(self.criteria) and all(self.criteria.values())


def check_liquidity_calibration(
    market: str,
    n_obs: int,
    result,
    has_param_change_audit: bool,
) -> LiquidityCalibrationCheck:
    """Score the six G-LIQ verification criteria for the liquidity calibration."""
    criteria = {
        "c1_min_obs": n_obs >= MIN_OBS,
        "c2_kappa_in_band": KAPPA_MIN <= result.mean_reversion_speed <= KAPPA_MAX,
        "c3_long_run_in_band": LONG_RUN_MIN <= result.long_run_premium_p <= LONG_RUN_MAX,
        "c4_sigma_in_band": SIGMA_MIN <= result.premium_vol <= SIGMA_MAX,
        "c5_lambda_in_band": LAMBDA_MIN <= result.market_price_of_liquidity_risk <= LAMBDA_MAX,
        "c6_not_placeholder_with_audit": (not result.is_placeholder) and bool(has_param_change_audit),
    }
    return LiquidityCalibrationCheck(
        market=market,
        n_obs=n_obs,
        kappa=float(result.mean_reversion_speed),
        long_run_premium_p=float(result.long_run_premium_p),
        sigma=float(result.premium_vol),
        lam=float(result.market_price_of_liquidity_risk),
        is_placeholder=bool(result.is_placeholder),
        criteria=criteria,
    )


def evaluate_liquidity_gate(check: LiquidityCalibrationCheck) -> ProductionGateStatus:
    """Evaluate G-LIQ: CIR++ liquidity-premium parameters calibrated to market data."""
    failed = [k for k, ok in check.criteria.items() if not ok]
    status = "PASS" if not failed else "FAIL"
    evidence = (
        "{}: n={}, kappa={:.4f}, long_run={:.4f} ({:.0f}bp), sigma={:.4f}, lambda={:.4f}".format(
            check.market, check.n_obs, check.kappa, check.long_run_premium_p,
            check.long_run_premium_p * 1e4, check.sigma, check.lam
        )
    )
    if failed:
        evidence += "; failed " + ", ".join(failed)
    return ProductionGateStatus(
        gate_id="G-LIQ",
        gate_description=(
            "CIR++ liquidity-premium parameters (kappa_l, long-run premium, sigma_l, lambda_l) "
            "calibrated to liquidity/funding-spread data (not placeholders); kappa in [{:.2f}, {:.1f}], "
            "long-run in [{:.0f}, {:.0f}]bp, sigma in [{:.3f}, {:.2f}], lambda in [{:.1f}, {:.1f}] "
            "(SOA ASOP 56 3.4; EIOPA VA illiquidity-premium component)".format(
                KAPPA_MIN, KAPPA_MAX, LONG_RUN_MIN * 1e4, LONG_RUN_MAX * 1e4,
                SIGMA_MIN, SIGMA_MAX, LAMBDA_MIN, LAMBDA_MAX
            )
        ),
        status=status,
        evidence=evidence,
    )


__all__ = [
    "LiquidityMarketDataSource",
    "FileBasedLiquidityPremiumSource",
    "LiquidityPremiumDataLoader",
    "synthesize_premium_history",
    "build_liquidity_loader",
    "default_fixture_dir",
    "LiquidityCalibrationCheck",
    "check_liquidity_calibration",
    "evaluate_liquidity_gate",
    "KAPPA_MIN", "KAPPA_MAX", "LONG_RUN_MIN", "LONG_RUN_MAX",
    "SIGMA_MIN", "SIGMA_MAX", "LAMBDA_MIN", "LAMBDA_MAX", "MIN_OBS",
]
