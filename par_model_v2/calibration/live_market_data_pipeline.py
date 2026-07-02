"""
Live Market Data Pipeline - CNY Yield Curve + CSI 300 Loaders
=============================================================

Roadmap item #1 (docs/CONTINUOUS_IMPROVEMENT_ROADMAP.md 4), model-risk
register MR-006.  Provides a governed ingestion path for the two live data
sets the calibration stack needs first:

* ``CNYYieldCurveLoader``  - CNY sovereign zero curve (ChinaBond-style rows:
  ``date``, ``tenor_years``, ``zero_rate``), contract
  ``CalibrationDataInterface.risk_free_curve("CN", "CNY")``.
* ``CSI300IndexLoader``    - CSI 300 daily index history (rows: ``date``,
  ``index_level``), contract
  ``CalibrationDataInterface.equity_index("CN", "CNY")``.

Design
------
Three provenance tiers, resolved in this order by ``load()``:

1. ``live_fetch``       - an injected ``fetcher(as_of) -> list[dict]``
                          callable (vendor adapter: Wind / ChinaBond /
                          Bloomberg).  Only used when a fetcher is supplied.
                          Results are schema-validated BEFORE they are
                          cached; lineage is flagged UNSIGNED pending owner
                          approval (never self-approved).
2. ``cached_snapshot``  - SHA-256-sealed JSON snapshots under a cache
                          directory; integrity is re-verified on every read
                          (tamper -> ``SnapshotIntegrityError``).
3. ``file_fixture``     - versioned educational fixtures shipped in
                          ``par_model_v2/calibration/fixtures/`` (offline /
                          CI default).

Every successful load returns a ``MarketDataResult`` carrying the validated
``pandas.DataFrame``, the snapshot path, the payload SHA-256, and a
``DataLineageRecord`` (IA TAS M 3.6 traceability).

Standards: SOA ASOP 56 3.4, ASOP 23 (data quality), IA TAS M 3.5/3.6.

PRODUCTION USE RESTRICTION
--------------------------
No credentialled vendor adapter ships with this module.  Fixtures are
educational proxies; live fetches are UNSIGNED until the Model Owner
approves the source under the governance workflow.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from par_model_v2.calibration.market_data_source import DataLineageRecord
from par_model_v2.stochastic.esg_process import CalibrationDataInterface

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
DEFAULT_CNY_CURVE_FIXTURE = _FIXTURE_DIR / "cny_yield_curve_20260101.json"
DEFAULT_CSI300_FIXTURE = _FIXTURE_DIR / "csi300_index_history_20260101.json"

PROVENANCE_LIVE = "live_fetch"
PROVENANCE_CACHE = "cached_snapshot"
PROVENANCE_FIXTURE = "file_fixture"

FetchCallable = Callable[[date], List[Dict[str, Any]]]


class MarketDataFetchError(RuntimeError):
    """No provenance tier could produce a valid data set."""


class SnapshotIntegrityError(RuntimeError):
    """A cached snapshot failed its SHA-256 integrity re-check."""


def _canonical_sha256(records: List[Dict[str, Any]]) -> str:
    payload = json.dumps(records, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _as_of_str(as_of) -> str:
    if isinstance(as_of, date):
        return as_of.isoformat()
    return str(as_of)


class SnapshotCache:
    """Directory of SHA-256-sealed JSON snapshots, one file per (dataset, as_of)."""

    def __init__(self, cache_dir) -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def directory(self) -> Path:
        return self._dir

    def path_for(self, dataset: str, as_of) -> Path:
        stamp = _as_of_str(as_of).replace("-", "")
        return self._dir / "{}_{}.json".format(dataset, stamp)

    def store(
        self,
        dataset: str,
        as_of,
        records: List[Dict[str, Any]],
        source_type: str,
        source_detail: str,
    ) -> Tuple[Path, str]:
        sha = _canonical_sha256(records)
        payload = {
            "dataset": dataset,
            "as_of_date": _as_of_str(as_of),
            "source_type": source_type,
            "source_detail": source_detail,
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "sha256": sha,
            "records": records,
        }
        path = self.path_for(dataset, as_of)
        path.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
        return path, sha

    def load(self, dataset: str, as_of) -> Dict[str, Any]:
        path = self.path_for(dataset, as_of)
        if not path.exists():
            raise FileNotFoundError("No snapshot: {}".format(path))
        payload = json.loads(path.read_text(encoding="utf-8"))
        recomputed = _canonical_sha256(payload.get("records", []))
        if recomputed != payload.get("sha256"):
            raise SnapshotIntegrityError(
                "Snapshot {} failed SHA-256 integrity check (expected {}, got {})".format(
                    path.name, payload.get("sha256"), recomputed
                )
            )
        return payload

    def list_snapshots(self, dataset: str) -> List[Path]:
        return sorted(self._dir.glob("{}_*.json".format(dataset)))

    def latest(self, dataset: str) -> Optional[Dict[str, Any]]:
        paths = self.list_snapshots(dataset)
        if not paths:
            return None
        newest = paths[-1]
        stamp = newest.stem.rsplit("_", 1)[-1]
        as_of = "{}-{}-{}".format(stamp[0:4], stamp[4:6], stamp[6:8])
        return self.load(dataset, as_of)


@dataclass(frozen=True)
class MarketDataResult:
    """Validated market data plus provenance evidence for one load."""

    dataset: str
    as_of_date: str
    provenance: str
    frame: pd.DataFrame
    snapshot_path: str
    sha256: str
    lineage: DataLineageRecord


class _BaseMarketDataLoader:
    """Shared fetch -> validate -> snapshot -> lineage machinery."""

    dataset: str = ""
    market: str = "CN"

    def __init__(
        self,
        cache: SnapshotCache,
        interface: CalibrationDataInterface,
        fixture_path,
        fetcher: Optional[FetchCallable] = None,
    ) -> None:
        self._cache = cache
        self._interface = interface
        self._fixture_path = Path(fixture_path)
        self._fetcher = fetcher

    # -- validation ---------------------------------------------------------

    def _validate(self, records: List[Dict[str, Any]]) -> pd.DataFrame:
        if not records:
            raise ValueError("{}: empty record set".format(self.dataset))
        frame = pd.DataFrame(records)
        self._interface.validate_frame(frame)
        self._extra_validation(frame)
        return frame

    def _extra_validation(self, frame: pd.DataFrame) -> None:  # pragma: no cover
        """Loader-specific structural checks beyond the field contract."""

    # -- lineage ------------------------------------------------------------

    def _lineage(
        self, as_of: str, provenance: str, source_detail: str, sha256: str,
        approved_by: str, approval_timestamp: str, version: str,
    ) -> DataLineageRecord:
        return DataLineageRecord(
            lineage_id="LIN_{}_{}".format(self.dataset.upper(), as_of.replace("-", "")),
            market=self.market,
            as_of_date=as_of,
            source_type=provenance,
            source_detail=source_detail,
            fixture_version=version,
            approved_by=approved_by,
            approval_timestamp=approval_timestamp,
            sha256_checksum=sha256,
        )

    # -- provenance tiers ---------------------------------------------------

    def load(self, as_of=None, refresh: bool = False) -> MarketDataResult:
        """Resolve data via live fetch (if fetcher given), then cache, then fixture.

        Parameters
        ----------
        as_of : date | str | None
            Target as-of date.  ``None`` means: latest cached snapshot, else
            the fixture's as-of date (or today's date for a live fetch).
        refresh : bool
            Force a live fetch even when a snapshot exists (fetcher required).
        """
        errors: List[str] = []

        if self._fetcher is not None and (refresh or not self._has_snapshot(as_of)):
            try:
                return self._load_live(as_of)
            except (MarketDataFetchError, ValueError, TypeError) as exc:
                errors.append("live_fetch failed: {}".format(exc))

        try:
            return self._load_cached(as_of)
        except (FileNotFoundError, SnapshotIntegrityError) as exc:
            errors.append("cached_snapshot unavailable: {}".format(exc))

        try:
            return self._load_fixture()
        except (FileNotFoundError, ValueError, KeyError) as exc:
            errors.append("file_fixture failed: {}".format(exc))

        raise MarketDataFetchError(
            "{}: all provenance tiers exhausted: {}".format(self.dataset, " | ".join(errors))
        )

    def _has_snapshot(self, as_of) -> bool:
        if as_of is None:
            return bool(self._cache.list_snapshots(self.dataset))
        return self._cache.path_for(self.dataset, as_of).exists()

    def _load_live(self, as_of) -> MarketDataResult:
        target = as_of if as_of is not None else date.today()
        try:
            records = self._fetcher(target)  # type: ignore[misc]
        except Exception as exc:  # vendor adapters raise arbitrary errors
            raise MarketDataFetchError("fetcher raised: {}".format(exc)) from exc
        frame = self._validate(records)
        as_of_str = _as_of_str(target)
        path, sha = self._cache.store(
            self.dataset, as_of_str, records, PROVENANCE_LIVE,
            source_detail=repr(self._fetcher),
        )
        lineage = self._lineage(
            as_of_str, PROVENANCE_LIVE, repr(self._fetcher), sha,
            approved_by="UNSIGNED_PENDING_OWNER_APPROVAL",
            approval_timestamp="UNSIGNED",
            version="live",
        )
        return MarketDataResult(
            self.dataset, as_of_str, PROVENANCE_LIVE, frame, str(path), sha, lineage
        )

    def _load_cached(self, as_of) -> MarketDataResult:
        payload = (
            self._cache.load(self.dataset, as_of)
            if as_of is not None
            else self._cache.latest(self.dataset)
        )
        if payload is None:
            raise FileNotFoundError("no snapshots for {}".format(self.dataset))
        frame = self._validate(payload["records"])
        as_of_str = payload["as_of_date"]
        path = self._cache.path_for(self.dataset, as_of_str)
        lineage = self._lineage(
            as_of_str, PROVENANCE_CACHE, str(path), payload["sha256"],
            approved_by="INHERITED_FROM_SNAPSHOT_SOURCE",
            approval_timestamp=payload.get("stored_at", "unknown"),
            version=payload.get("source_type", "unknown"),
        )
        return MarketDataResult(
            self.dataset, as_of_str, PROVENANCE_CACHE, frame, str(path),
            payload["sha256"], lineage,
        )

    def _load_fixture(self) -> MarketDataResult:
        if not self._fixture_path.exists():
            raise FileNotFoundError("fixture not found: {}".format(self._fixture_path))
        raw = self._fixture_path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        records = data["records"]
        frame = self._validate(records)
        as_of_str = str(data["as_of_date"])
        path, sha = self._cache.store(
            self.dataset, as_of_str, records, PROVENANCE_FIXTURE,
            source_detail=str(self._fixture_path.resolve()),
        )
        lin = data.get("data_lineage", {})
        lineage = self._lineage(
            as_of_str, PROVENANCE_FIXTURE, str(self._fixture_path.resolve()), sha,
            approved_by=lin.get("approved_by", "unknown"),
            approval_timestamp=lin.get("approval_timestamp", "unknown"),
            version=lin.get("version", "unknown"),
        )
        return MarketDataResult(
            self.dataset, as_of_str, PROVENANCE_FIXTURE, frame, str(path), sha, lineage
        )


class CNYYieldCurveLoader(_BaseMarketDataLoader):
    """CNY sovereign zero curve loader (rows: date, tenor_years, zero_rate)."""

    dataset = "cny_yield_curve"

    MIN_TENOR_COUNT = 4

    def __init__(self, cache: SnapshotCache, fetcher: Optional[FetchCallable] = None,
                 fixture_path=DEFAULT_CNY_CURVE_FIXTURE) -> None:
        super().__init__(
            cache=cache,
            interface=CalibrationDataInterface.risk_free_curve("CN", "CNY"),
            fixture_path=fixture_path,
            fetcher=fetcher,
        )

    def _extra_validation(self, frame: pd.DataFrame) -> None:
        dates = pd.to_datetime(frame["date"])
        if dates.nunique() != 1:
            raise ValueError("cny_yield_curve: all rows must share one as-of date")
        tenors = pd.to_numeric(frame["tenor_years"]).to_numpy(dtype=float)
        if len(tenors) < self.MIN_TENOR_COUNT:
            raise ValueError(
                "cny_yield_curve: need >= {} tenors, got {}".format(
                    self.MIN_TENOR_COUNT, len(tenors)
                )
            )
        if len(set(tenors.tolist())) != len(tenors):
            raise ValueError("cny_yield_curve: duplicate tenors")
        if not (tenors[1:] > tenors[:-1]).all():
            raise ValueError("cny_yield_curve: tenors must be strictly increasing")

    def to_curve_series(self, result: MarketDataResult) -> pd.Series:
        """Return the curve as a pandas Series indexed by tenor (calibrator shape)."""
        frame = result.frame
        return pd.Series(
            data=pd.to_numeric(frame["zero_rate"]).to_numpy(dtype=float),
            index=pd.to_numeric(frame["tenor_years"]).to_numpy(dtype=float),
            name="CNY_spot_{}".format(result.as_of_date),
            dtype=float,
        )


class CSI300IndexLoader(_BaseMarketDataLoader):
    """CSI 300 daily index-history loader (rows: date, index_level)."""

    dataset = "csi300_index"

    def __init__(self, cache: SnapshotCache, fetcher: Optional[FetchCallable] = None,
                 fixture_path=DEFAULT_CSI300_FIXTURE) -> None:
        super().__init__(
            cache=cache,
            interface=CalibrationDataInterface.equity_index("CN", "CNY"),
            fixture_path=fixture_path,
            fetcher=fetcher,
        )

    def _extra_validation(self, frame: pd.DataFrame) -> None:
        dates = pd.to_datetime(frame["date"])
        if not dates.is_monotonic_increasing:
            raise ValueError("csi300_index: dates must be non-decreasing")
        if dates.duplicated().any():
            raise ValueError("csi300_index: duplicate dates")
        levels = pd.to_numeric(frame["index_level"]).to_numpy(dtype=float)
        if (levels <= 0.0).any():
            raise ValueError("csi300_index: index_level must be strictly positive")

    def to_level_series(self, result: MarketDataResult) -> pd.Series:
        frame = result.frame
        return pd.Series(
            data=pd.to_numeric(frame["index_level"]).to_numpy(dtype=float),
            index=pd.to_datetime(frame["date"]),
            name="CSI300_{}".format(result.as_of_date),
            dtype=float,
        )
