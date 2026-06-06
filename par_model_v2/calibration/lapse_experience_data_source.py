"""
Lapse-Experience Data Source — HK PAR A/E History Loader (Phase 19 Task 5)
=========================================================================

Vendor-agnostic abstraction that feeds a historical lapse-experience series
(monthly actual-to-expected ratio) into the :class:`LapseBehaviourCalibrator`,
mirroring ``market_data_source`` (swaptions/HW1F), ``equity_market_data_source``
(equity/GBM), and ``credit_market_data_source`` (credit/CIR++).

Educational-proxy synthesis
---------------------------
``FileBasedLapseExperienceSource`` does NOT ship a raw experience-study file.
It ships a compact, human-auditable fixture of *documented* OU target statistics
(mean-reversion, long-run level, behaviour vol, initial index) and
deterministically expands them into a monthly A/E path with the **exact** OU
AR(1) discretisation, so the calibrator recovers the documented long-run level
(sample-mean robust), the behaviour vol (residual-variance robust) and, more
loosely, the mean-reversion speed.

Risk addressed
--------------
MR-003 : the dynamic-lapse / policyholder-behaviour assumption set carries an
         un-calibrated *level* uncertainty.  MR-011 : the multi-driver economic-
         capital proxy is educational.  This task calibrates the lapse
         behavioural-index driver to educational-proxy experience and records
         the change through governance, moving both toward MITIGATED.

Standards References
--------------------
SOA ASOP 7 §3.3 (policyholder behaviour), SOA ASOP 25 §3.3 (credibility /
historical estimation), SOA ASOP 56 §3.4 (calibration documentation),
IA TAS M §3.5 / §3.6.

PRODUCTION USE RESTRICTION
--------------------------
File-based fixtures are educational proxies.  Replace with a credentialled
actual-vs-expected persistency study (cohort/duration-segmented, exposure-
weighted, with standard errors) and re-run the sign-off workflow before
regulatory, pricing, or capital-adequacy use.
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

from par_model_v2.calibration.lapse_calibrator import LapseCalibrationInputs
from par_model_v2.calibration.market_data_source import (
    DataLineageRecord,
    ProductionGateStatus,
)


# ---------------------------------------------------------------------------
# 1. Abstract source
# ---------------------------------------------------------------------------

class LapseExperienceDataSource(ABC):
    """Abstract source of lapse-experience (A/E) history for one market."""

    @property
    @abstractmethod
    def market(self) -> str: ...

    @abstractmethod
    def build_calibration_inputs(self) -> LapseCalibrationInputs: ...

    @abstractmethod
    def build_lineage_record(self) -> DataLineageRecord: ...


# ---------------------------------------------------------------------------
# 2. Deterministic educational-proxy synthesis
# ---------------------------------------------------------------------------

def synthesize_ae_history(spec: Dict[str, Any]) -> Tuple[pd.Series, date]:
    """Expand a documented-target OU fixture into a monthly A/E series.

    Simulates the **exact** OU AR(1) transition of the behavioural index
    ``b_{t+1} = phi b_t + theta (1 - phi) + sqrt(sigma^2 (1-phi^2)/(2 kappa)) Z``
    with ``phi = exp(-kappa dt)`` and ``dt = 1/steps_per_year``, then the A/E
    ratio ``= clip(exp(b), ae_floor, ae_ceiling)``.  Fully deterministic given
    the fixture seed.  This matches ``LapseBehaviourProcess._simulate_array`` so
    the calibrator recovers the documented parameters.
    """
    syn = spec["monthly_synthesis"]
    seed = int(syn["seed"])
    rng = np.random.default_rng(seed)

    steps_per_year = int(syn.get("steps_per_year", 12))
    dt = 1.0 / steps_per_year

    start = pd.Timestamp(syn["start_date"])
    end = pd.Timestamp(syn["end_date"])
    dates = pd.date_range(start=start, end=end, freq="ME")
    n = len(dates)

    kappa = float(spec["target_mean_reversion"])
    theta = float(spec["target_long_run_level"])
    sigma = float(spec["target_behaviour_vol"])
    b0 = float(syn.get("initial_index", 0.0))
    floor = float(spec.get("ae_floor", 0.30))
    ceiling = float(spec.get("ae_ceiling", 3.0))

    phi = float(np.exp(-kappa * dt))
    cond_std = float(np.sqrt(sigma * sigma * (1.0 - phi * phi) / (2.0 * kappa)))

    z = rng.standard_normal(n)
    b = np.empty(n, dtype=float)
    b[0] = b0
    for t in range(1, n):
        b[t] = phi * b[t - 1] + theta * (1.0 - phi) + cond_std * z[t]

    ae = np.clip(np.exp(b), floor, ceiling)
    series = pd.Series(ae, index=dates, name="{}_lapse_ae".format(spec["market"]))
    cal_date = date.fromisoformat(spec["as_of_date"])
    return series, cal_date


class FileBasedLapseExperienceSource(LapseExperienceDataSource):
    """Reads a documented-target lapse fixture and synthesizes a monthly path."""

    def __init__(self, fixture_path) -> None:
        self._path = Path(fixture_path)
        if not self._path.exists():
            raise FileNotFoundError("Lapse fixture not found: {}".format(self._path.resolve()))
        raw_bytes = self._path.read_bytes()
        self._sha256 = hashlib.sha256(raw_bytes).hexdigest()
        self._data: Dict[str, Any] = json.loads(raw_bytes.decode("utf-8"))

    @property
    def market(self) -> str:
        return self._data["market"]

    @property
    def currency(self) -> str:
        return self._data.get("currency", self._data["market"])

    def build_calibration_inputs(self) -> LapseCalibrationInputs:
        series, cal_date = synthesize_ae_history(self._data)
        return LapseCalibrationInputs(
            calibration_date=cal_date,
            ae_history=series,
            dt=1.0 / int(self._data["monthly_synthesis"].get("steps_per_year", 12)),
            capital_initial_index=float(self._data.get("capital_initial_index", 0.0)),
        )

    def build_lineage_record(self) -> DataLineageRecord:
        lin = self._data.get("data_lineage", {})
        raw_checksum = lin.get("checksum_sha256", "educational_fixture_no_checksum")
        effective = self._sha256 if raw_checksum == "educational_fixture_no_checksum" else raw_checksum
        return DataLineageRecord(
            lineage_id="LINLAPSE_{}_{}".format(self.market, self._data["as_of_date"].replace("-", "")),
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

class LapseExperienceDataLoader:
    """Loads a lapse fixture and returns ``LapseCalibrationInputs`` + lineage."""

    def __init__(self, source: LapseExperienceDataSource, min_obs: int = 60) -> None:
        self._source = source
        self._min_obs = min_obs

    @property
    def market(self) -> str:
        return self._source.market

    def load(self) -> Tuple[LapseCalibrationInputs, DataLineageRecord]:
        inputs = self._source.build_calibration_inputs()
        lineage = self._source.build_lineage_record()
        self._validate(inputs)
        return inputs, lineage

    def _validate(self, inputs: LapseCalibrationInputs) -> None:
        n = len(inputs.ae_history)
        if n < self._min_obs:
            raise ValueError(
                "{}: only {} A/E observations; need >= {} (SOA ASOP 25 §3.3).".format(
                    self.market, n, self._min_obs
                )
            )


def default_fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def build_lapse_loader(
    market: str = "HK_PAR",
    fixture_dir=None,
    as_of_date: str = "20260101",
) -> LapseExperienceDataLoader:
    """Build a ``LapseExperienceDataLoader`` from the bundled fixture files.

    Parameters
    ----------
    market : str
        "HK_PAR".  Maps to ``lapse_experience_history_<as_of_date>.json``.
    """
    if fixture_dir is None:
        fixture_dir = default_fixture_dir()
    fixture_dir = Path(fixture_dir)
    filename = "lapse_experience_history_{}.json".format(as_of_date)
    source = FileBasedLapseExperienceSource(fixture_dir / filename)
    return LapseExperienceDataLoader(source)


# ---------------------------------------------------------------------------
# 4. Calibration gate (G-LAPSE, internal — not one of the 12 deployment gates)
# ---------------------------------------------------------------------------

# Plausibility bands for the OU behavioural-index parameters.
KAPPA_MIN, KAPPA_MAX = 0.05, 5.0           # half-life ~ 14 yr .. ~1.7 months
THETA_MIN, THETA_MAX = -0.20, 0.20         # long-run A/E in ~[0.82, 1.22]
SIGMA_MIN, SIGMA_MAX = 0.02, 0.60
STAT_STD_MIN, STAT_STD_MAX = 0.02, 0.50    # 1-sd A/E multiplier ~[exp(-0.5), exp(0.5)]
MIN_OBS = 60


@dataclass
class LapseCalibrationCheck:
    """G-LAPSE criterion outcomes for the lapse behavioural-index calibration."""
    market: str
    n_obs: int
    kappa: float
    long_run_level: float
    sigma: float
    stationary_std: float
    is_placeholder: bool
    criteria: Dict[str, bool] = field(default_factory=dict)

    def all_pass(self) -> bool:
        return bool(self.criteria) and all(self.criteria.values())


def check_lapse_calibration(
    market: str,
    n_obs: int,
    result,
    has_param_change_audit: bool,
) -> LapseCalibrationCheck:
    """Score the six G-LAPSE verification criteria for the lapse calibration."""
    criteria = {
        "c1_min_obs": n_obs >= MIN_OBS,
        "c2_kappa_in_band": KAPPA_MIN <= result.mean_reversion_speed <= KAPPA_MAX,
        "c3_long_run_in_band": THETA_MIN <= result.long_run_level <= THETA_MAX,
        "c4_sigma_in_band": SIGMA_MIN <= result.behaviour_vol <= SIGMA_MAX,
        "c5_stationary_std_in_band": STAT_STD_MIN <= result.stationary_std <= STAT_STD_MAX,
        "c6_not_placeholder_with_audit": (not result.is_placeholder) and bool(has_param_change_audit),
    }
    return LapseCalibrationCheck(
        market=market,
        n_obs=n_obs,
        kappa=float(result.mean_reversion_speed),
        long_run_level=float(result.long_run_level),
        sigma=float(result.behaviour_vol),
        stationary_std=float(result.stationary_std),
        is_placeholder=bool(result.is_placeholder),
        criteria=criteria,
    )


def evaluate_lapse_gate(check: LapseCalibrationCheck) -> ProductionGateStatus:
    """Evaluate G-LAPSE: OU behavioural-index parameters calibrated to experience."""
    failed = [k for k, ok in check.criteria.items() if not ok]
    status = "PASS" if not failed else "FAIL"
    evidence = (
        "{}: n={}, kappa={:.4f} (half-life {:.1f}yr), long_run_level={:.4f} "
        "(A/E {:.3f}), sigma={:.4f}, stationary_std={:.4f}".format(
            check.market, check.n_obs, check.kappa,
            (0.6931 / check.kappa) if check.kappa > 0 else float("inf"),
            check.long_run_level, float(np.exp(check.long_run_level)),
            check.sigma, check.stationary_std,
        )
    )
    if failed:
        evidence += "; failed " + ", ".join(failed)
    return ProductionGateStatus(
        gate_id="G-LAPSE",
        gate_description=(
            "OU lapse behavioural-index parameters (kappa_b, long-run level, sigma_b) "
            "calibrated to lapse-experience A/E history (not placeholders); kappa in "
            "[{:.2f}, {:.1f}], long-run level in [{:.2f}, {:.2f}], sigma in [{:.2f}, {:.2f}], "
            "stationary std in [{:.2f}, {:.2f}] (SOA ASOP 7 §3.3; ASOP 56 §3.4)".format(
                KAPPA_MIN, KAPPA_MAX, THETA_MIN, THETA_MAX,
                SIGMA_MIN, SIGMA_MAX, STAT_STD_MIN, STAT_STD_MAX,
            )
        ),
        status=status,
        evidence=evidence,
    )


__all__ = [
    "LapseExperienceDataSource",
    "FileBasedLapseExperienceSource",
    "LapseExperienceDataLoader",
    "synthesize_ae_history",
    "build_lapse_loader",
    "default_fixture_dir",
    "LapseCalibrationCheck",
    "check_lapse_calibration",
    "evaluate_lapse_gate",
    "KAPPA_MIN", "KAPPA_MAX", "THETA_MIN", "THETA_MAX",
    "SIGMA_MIN", "SIGMA_MAX", "STAT_STD_MIN", "STAT_STD_MAX", "MIN_OBS",
]
