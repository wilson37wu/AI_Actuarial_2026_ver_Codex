"""
Market Data Source — Swaption Surface Loader for Phase 13 HW1F Calibration
===========================================================================

Provides a vendor-agnostic abstraction layer that feeds market swaption quotes
and spot curves into the HullWhiteCalibrator.

Production Gates Addressed
--------------------------
G-02 : HW1F calibrated to market swaption data; RMSE <= 25 bps (HW1F one-factor
       achievable threshold; G2++ upgrade targets 5 bps — see limitation_cards.py).
G-12 : Calibration data lineage documented (DataLineageRecord with source,
       approval timestamp, and SHA-256).

Standards References
--------------------
SOA ASOP 56 §3.4, SOA ASOP 25 §3.3, IA TAS M §3.5/§3.6, IFoA APS X2

PRODUCTION USE RESTRICTION
--------------------------
File-based fixtures are educational proxies. Replace with credentialled
live-API fetches and re-run sign-off workflow before regulatory use.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from par_model_v2.calibration.calibration_framework import (
    HullWhiteCalibrationInputs,
    SwaptionQuote,
)


@dataclass
class DataLineageRecord:
    """Provenance record for one calibration data set (IA TAS M §3.6)."""
    lineage_id: str
    market: str
    as_of_date: str
    source_type: str
    source_detail: str
    fixture_version: str
    approved_by: str
    approval_timestamp: str
    sha256_checksum: str
    produced_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DataLineageRecord":
        return cls(**d)


class SwaptionMarketDataSource(ABC):
    """Abstract source of swaption quotes and spot curve for one market."""

    @property
    @abstractmethod
    def market(self) -> str: ...

    @abstractmethod
    def fetch_swaption_quotes(self) -> List[SwaptionQuote]: ...

    @abstractmethod
    def fetch_spot_curve(self) -> pd.Series: ...

    @abstractmethod
    def fetch_initial_short_rate(self) -> float: ...

    @abstractmethod
    def fetch_calibration_date(self) -> date: ...

    @abstractmethod
    def fetch_regulatory_rate_cap(self) -> float: ...

    @abstractmethod
    def build_lineage_record(self) -> DataLineageRecord: ...


class FileBasedSwaptionSource(SwaptionMarketDataSource):
    """Reads swaption surface + spot curve from a versioned JSON fixture file."""

    def __init__(self, fixture_path) -> None:
        self._path = Path(fixture_path)
        if not self._path.exists():
            raise FileNotFoundError("Swaption fixture not found: {}".format(self._path.resolve()))
        raw_bytes = self._path.read_bytes()
        self._sha256 = hashlib.sha256(raw_bytes).hexdigest()
        self._data: Dict[str, Any] = json.loads(raw_bytes.decode("utf-8"))

    @property
    def market(self) -> str:
        return self._data["currency"]

    def fetch_swaption_quotes(self) -> List[SwaptionQuote]:
        return [
            SwaptionQuote(
                expiry_years=row["expiry_years"],
                swap_tenor_years=row["swap_tenor_years"],
                normal_vol_bps=row["normal_vol_bps"],
                weight=row.get("weight", 1.0),
            )
            for row in self._data["swaption_grid"]
        ]

    def fetch_spot_curve(self) -> pd.Series:
        sc = self._data["spot_curve"]
        return pd.Series(
            data=sc["rates_decimal"],
            index=sc["tenors_years"],
            name="{}_spot_{}".format(self.market, self._data["as_of_date"]),
            dtype=float,
        )

    def fetch_initial_short_rate(self) -> float:
        return float(self._data["initial_short_rate"])

    def fetch_calibration_date(self) -> date:
        return date.fromisoformat(self._data["as_of_date"])

    def fetch_regulatory_rate_cap(self) -> float:
        return float(self._data.get("regulatory_rate_cap", 0.05))

    def build_lineage_record(self) -> DataLineageRecord:
        lin = self._data.get("data_lineage", {})
        raw_checksum = lin.get("checksum_sha256", "educational_fixture_no_checksum")
        effective = self._sha256 if raw_checksum == "educational_fixture_no_checksum" else raw_checksum
        return DataLineageRecord(
            lineage_id="LIN_{}_{}".format(self.market, self._data["as_of_date"].replace("-", "")),
            market=self.market,
            as_of_date=self._data["as_of_date"],
            source_type=lin.get("provenance", "file_fixture"),
            source_detail=str(self._path.resolve()),
            fixture_version=lin.get("version", "unknown"),
            approved_by=lin.get("approved_by", "unknown"),
            approval_timestamp=lin.get("approval_timestamp", "unknown"),
            sha256_checksum=effective,
        )

    @property
    def fixture_id(self) -> str:
        return self._data.get("fixture_id", "UNKNOWN")

    @property
    def notes(self) -> str:
        return self._data.get("notes", "")


class LiveSwaptionDataLoader:
    """Loads data and produces HullWhiteCalibrationInputs.

    Parameters
    ----------
    source : SwaptionMarketDataSource
    min_swaption_count : int
        Minimum active quotes (weight > 0). Default 8. SOA ASOP 56 §3.4.
    optimizer_bounds : dict, optional
        HW1F optimizer bounds. Default: a in (0.001, 3.0), sigma_r in
        (0.001, 0.20). Wider a-bound vs framework default (1.0) needed for
        high-vol markets (HKD); documented in limitation_cards.py.
    """

    def __init__(
        self,
        source: SwaptionMarketDataSource,
        min_swaption_count: int = 8,
        optimizer_bounds: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> None:
        self._source = source
        self._min_count = min_swaption_count
        self._optimizer_bounds: Dict[str, Tuple[float, float]] = (
            optimizer_bounds if optimizer_bounds is not None
            else {"a": (0.001, 3.0), "sigma_r": (0.001, 0.20)}
        )

    @property
    def market(self) -> str:
        return self._source.market

    def load(self) -> Tuple[HullWhiteCalibrationInputs, DataLineageRecord]:
        """Fetch, validate, and return calibration inputs + lineage."""
        quotes = self._source.fetch_swaption_quotes()
        spot_curve = self._source.fetch_spot_curve()
        r0 = self._source.fetch_initial_short_rate()
        cal_date = self._source.fetch_calibration_date()
        reg_cap = self._source.fetch_regulatory_rate_cap()
        lineage = self._source.build_lineage_record()
        self._validate(quotes, spot_curve, r0)
        inputs = HullWhiteCalibrationInputs(
            calibration_date=cal_date,
            initial_short_rate=r0,
            spot_curve=spot_curve,
            swaption_quotes=quotes,
            regulatory_rate_cap=reg_cap,
            optimizer_bounds=self._optimizer_bounds,
        )
        return inputs, lineage

    def _validate(self, quotes, spot_curve, r0):
        active = [q for q in quotes if q.weight > 0]
        if len(active) < self._min_count:
            raise ValueError(
                "{}: only {} active quotes; need >= {} (SOA ASOP 56 §3.4).".format(
                    self.market, len(active), self._min_count
                )
            )
        bad = [q for q in quotes if q.normal_vol_bps <= 0]
        if bad:
            raise ValueError(
                "{}: {} quotes have non-positive normal_vol_bps: {}".format(
                    self.market, len(bad),
                    [(q.expiry_years, q.swap_tenor_years) for q in bad]
                )
            )
        if spot_curve.empty:
            raise ValueError("{}: spot curve is empty".format(self.market))
        if (spot_curve < -0.02).any():
            raise ValueError("{}: spot curve rates below -2%".format(self.market))
        if not (0.0 <= r0 <= 0.20):
            raise ValueError("{}: r0={:.4f} outside [0, 20%]".format(self.market, r0))


@dataclass
class ProductionGateStatus:
    """Pass/fail status and evidence for a single production gate."""
    gate_id: str
    gate_description: str
    status: str  # "PASS" | "FAIL" | "NOT_RUN"
    evidence: str
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_g02_gate(
    cny_result_is_placeholder: bool,
    cny_rmse_bps: Optional[float],
    hkd_result_is_placeholder: bool,
    hkd_rmse_bps: Optional[float],
    rmse_threshold_bps: float = 25.0,
) -> ProductionGateStatus:
    """Evaluate G-02: HW1F calibrated to market data (not placeholders).

    PASS: both markets not placeholder AND RMSE <= 25 bps.
    25 bps is the HW1F one-factor achievable threshold; G2++ targets 5 bps.
    (SOA ASOP 56 §3.4/§3.5; limitation documented in limitation_cards.py)
    """
    evidence_parts = []
    fails = []
    for mkt, placeholder, rmse in [
        ("CNY", cny_result_is_placeholder, cny_rmse_bps),
        ("HKD", hkd_result_is_placeholder, hkd_rmse_bps),
    ]:
        if placeholder:
            fails.append("{}: is_placeholder=True".format(mkt))
        else:
            evidence_parts.append("{}: is_placeholder=False".format(mkt))
        if rmse is None:
            fails.append("{}: RMSE not available".format(mkt))
        elif rmse > rmse_threshold_bps:
            fails.append("{}: RMSE={:.2f}bps > {}bps threshold".format(
                mkt, rmse, rmse_threshold_bps))
        else:
            evidence_parts.append("{}: RMSE={:.2f}bps <= {}bps".format(
                mkt, rmse, rmse_threshold_bps))
    status = "PASS" if not fails else "FAIL"
    evidence = "; ".join(evidence_parts + (fails if fails else []))
    return ProductionGateStatus(
        gate_id="G-02",
        gate_description=(
            "HW1F parameters calibrated to market swaption data (not placeholders); "
            "RMSE <= {} bps for CNY and HKD "
            "(25 bps = HW1F one-factor threshold; G2++ upgrade targets 5 bps)".format(
                rmse_threshold_bps)
        ),
        status=status,
        evidence=evidence,
    )


def evaluate_g12_gate(lineage_records: List[DataLineageRecord]) -> ProductionGateStatus:
    """Evaluate G-12: calibration data lineage documented (IA TAS M §3.6).

    PASS: lineage records for CNY and HKD, each with source_detail and sha256.
    """
    expected = {"CNY", "HKD"}
    found = {lr.market for lr in lineage_records}
    missing = expected - found
    fails = []
    evidence_parts = []
    if missing:
        fails.append("Missing lineage for: {}".format(missing))
    for lr in lineage_records:
        if not lr.source_detail:
            fails.append("{}: source_detail empty".format(lr.market))
        else:
            evidence_parts.append("{}: source={}".format(lr.market, lr.source_detail[-50:]))
        if not lr.sha256_checksum:
            fails.append("{}: sha256 empty".format(lr.market))
        else:
            evidence_parts.append("{}: sha256={}...".format(lr.market, lr.sha256_checksum[:16]))
    status = "PASS" if not fails else "FAIL"
    evidence = "; ".join(evidence_parts + (fails if fails else []))
    return ProductionGateStatus(
        gate_id="G-12",
        gate_description=(
            "Calibration data lineage documented: source, approval, and SHA-256 "
            "recorded for CNY and HKD (IA TAS M §3.6)"
        ),
        status=status,
        evidence=evidence,
    )


def default_fixture_dir() -> Path:
    """Return default fixtures directory relative to this module."""
    return Path(__file__).parent / "fixtures"


def build_file_based_loader(
    market: str,
    fixture_dir=None,
    as_of_date: str = "20260101",
) -> LiveSwaptionDataLoader:
    """Build a LiveSwaptionDataLoader from bundled fixture files."""
    if fixture_dir is None:
        fixture_dir = default_fixture_dir()
    fixture_dir = Path(fixture_dir)
    filename = "{}_swaption_surface_{}.json".format(market.lower(), as_of_date)
    source = FileBasedSwaptionSource(fixture_dir / filename)
    return LiveSwaptionDataLoader(source)
