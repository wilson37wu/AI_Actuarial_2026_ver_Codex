"""
Live-History Backtest Bridge - roadmap item #6 (docs/CONTINUOUS_IMPROVEMENT_ROADMAP.md §4.1)
============================================================================================

Populates the Phase-4 / Phase-13 ``BacktestEngine`` with the CNY 1Y curve point
and CSI 300 return **series resolved through roadmap item #1's live market-data
pipeline** (``live_market_data_pipeline``), and evaluates an explicit,
governed set of **recalibration triggers** on the resulting >= 10-year backtest.

Why this module exists (the item-#6 delta over Phase 13 Task 5)
--------------------------------------------------------------
Phase 13 Task 5 (``phase13_backtest``) already runs Kupiec POF + coverage on a
>= 10-year annual fixture, but it reads that fixture through its own
``FileBasedBacktestHistorySource`` and reports a single ``requires_recalibration``
boolean.  Item #6 is scoped as *"populate BacktestEngine with live CNY curve /
CSI 300 series (item 1 dependency); Kupiec POF + coverage tests on >= 10y
history; recalibration triggers evaluated."*  This bridge closes exactly that
gap by:

1. **Sourcing the realised series through the item-#1 pipeline.**
   ``CNYBacktestHistoryLoader`` subclasses item #1's ``_BaseMarketDataLoader``,
   so the annual CNY 1Y short-rate + CSI 300 total-return series flow through
   the same three provenance tiers (``live_fetch`` -> ``cached_snapshot`` ->
   ``file_fixture``), the same ``SnapshotCache`` SHA-256 sealing, and the same
   ``DataLineageRecord`` (IA TAS M §3.6) that item #1 shipped.  No credentialled
   feed is bundled, so the offline default resolves the ``file_fixture`` tier
   and the lineage stays UNSIGNED pending Model-Owner source approval.

2. **Reusing the governed engine unchanged.**  The sealed series are handed to
   the existing ``LiveBacktestDataLoader`` -> ``calibrate_from_history`` (in-sample
   only) -> ``BacktestEngine`` path, so Kupiec POF, rate/equity band coverage,
   VaR/ES exceptions and the Q-measure martingale check are computed by the same
   code Phase 13 uses (genuine out-of-sample holdout preserved).

3. **Evaluating recalibration triggers.**  ``evaluate_recalibration_triggers``
   turns the backtest outcome into a structured, per-signal trigger set (band
   coverage, Kupiec VaR95/VaR99, VaR breach rates, Q-measure martingale, and
   in-sample-vs-out-of-sample coverage drift), each with a severity and a
   recommended recalibration action, and an overall recommendation.

Purely additive diagnostic
--------------------------
No governed headline figure (portfolio TVOG, aggregation report) is touched.
Re-baselining any headline onto a refreshed live calibration remains
owner-gated.  The only artifact written is
``docs/validation/LIVE_HISTORY_BACKTEST.json`` (UNSIGNED).

Standards: SOA ASOP 56 §3.5 (backtesting), ASOP 23 (data quality),
IA TAS M §3.6 (traceability / independent review).
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from par_model_v2.calibration.backtesting import (
    BACKTEST_MIN_COVERAGE,
    BACKTEST_VAR99_BREACH_LIMIT,
    BacktestEngine,
    BacktestResult,
)
from par_model_v2.calibration.live_market_data_pipeline import (
    PROVENANCE_FIXTURE,
    MarketDataResult,
    SnapshotCache,
    _BaseMarketDataLoader,
)
from par_model_v2.calibration.market_data_source import (
    DataLineageRecord,
    ProductionGateStatus,
    default_fixture_dir,
)
from par_model_v2.calibration.phase13_backtest import (
    G09_MIN_OBSERVATIONS,
    BacktestHistorySource,
    LiveBacktestDataLoader,
    calibrate_from_history,
    evaluate_g09_gate,
)
from par_model_v2.governance.audit_trail import GovernanceStore

SCHEMA = "live-history-backtest-1.0"
UNSIGNED_BANNER = (
    "UNSIGNED - educational-proxy market history resolved via the item-#1 live "
    "pipeline (file_fixture tier); replace with a credentialled ChinaBond/CSI/Wind "
    "extract and obtain Model-Owner sign-off before any regulatory or "
    "capital-adequacy use. Governed headline figures are NOT re-baselined here."
)

DEFAULT_HISTORY_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "cny_backtest_history_20260101.json"
)

# Annual realised-history plausibility bounds (decimal). Deliberately wide -
# these guard against corrupt inputs, not against unusual-but-real markets.
_RATE_MIN, _RATE_MAX = -0.05, 0.30
_RET_MIN, _RET_MAX = -0.99, 3.00
_MIN_ANNUAL_OBS = 10

_ANNUAL_COLUMNS = ("year", "start_short_rate", "end_short_rate", "equity_return")


# ---------------------------------------------------------------------------
# 1. Annual-history contract + item-#1-pipeline-backed loader
# ---------------------------------------------------------------------------
class _AnnualBacktestHistoryInterface:
    """Duck-typed table contract (``validate_frame``) for annual realised history.

    Mirrors the validation surface item #1's loaders expect
    (``interface.validate_frame(frame)``) without borrowing the governed curve /
    equity ``CalibrationDataInterface`` shapes, which describe *tenor curves* and
    *daily index levels* rather than *annual realised transitions*.
    """

    interface_id = "IFACE-BACKTEST-HISTORY-CNY"

    def validate_frame(self, frame: pd.DataFrame) -> bool:
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("data must be a pandas DataFrame")
        missing = [c for c in _ANNUAL_COLUMNS if c not in frame.columns]
        if missing:
            raise ValueError(
                "{} missing required columns: {}".format(self.interface_id, ", ".join(missing))
            )
        if len(frame) < _MIN_ANNUAL_OBS:
            raise ValueError(
                "{} requires >= {} annual observations; got {}".format(
                    self.interface_id, _MIN_ANNUAL_OBS, len(frame)
                )
            )
        years = pd.to_numeric(frame["year"], errors="coerce")
        if years.isna().any():
            raise ValueError("year must be integer-valued")
        yv = years.to_numpy(dtype=float)
        if not np.all(np.equal(np.mod(yv, 1.0), 0.0)):
            raise ValueError("year must be integer-valued")
        if len(set(yv.tolist())) != len(yv):
            raise ValueError("duplicate years in history")
        if not (yv[1:] > yv[:-1]).all():
            raise ValueError("years must be strictly increasing")
        for col, lo, hi in (
            ("start_short_rate", _RATE_MIN, _RATE_MAX),
            ("end_short_rate", _RATE_MIN, _RATE_MAX),
            ("equity_return", _RET_MIN, _RET_MAX),
        ):
            vals = pd.to_numeric(frame[col], errors="coerce")
            if vals.isna().any():
                raise ValueError("{} must be numeric".format(col))
            arr = vals.to_numpy(dtype=float)
            if not np.isfinite(arr).all():
                raise ValueError("{} must be finite".format(col))
            if (arr < lo).any() or (arr > hi).any():
                raise ValueError("{} outside plausibility bounds [{}, {}]".format(col, lo, hi))
        return True


class CNYBacktestHistoryLoader(_BaseMarketDataLoader):
    """Annual CNY 1Y-rate + CSI 300 return history, resolved via item #1's pipeline.

    Inherits the three-tier ``load()`` (live -> cached snapshot -> fixture),
    ``SnapshotCache`` SHA-256 sealing, and ``DataLineageRecord`` machinery from
    item #1's ``_BaseMarketDataLoader`` so the backtest history carries the same
    governed provenance as the CNY curve / CSI 300 loaders.  The fixture stores
    the series under the ``annual_records`` key (plus the loss basis and the
    in/out-of-sample window), which this subclass maps into the pipeline's
    ``records`` shape.
    """

    dataset = "cny_backtest_history"
    market = "CN"

    def __init__(self, cache: SnapshotCache, fetcher=None, fixture_path=DEFAULT_HISTORY_FIXTURE) -> None:
        super().__init__(
            cache=cache,
            interface=_AnnualBacktestHistoryInterface(),
            fixture_path=fixture_path,
            fetcher=fetcher,
        )
        self.fixture_meta: Dict[str, Any] = {}

    @staticmethod
    def _records_from_payload(data: Dict[str, Any]) -> List[Dict[str, float]]:
        raw = data.get("annual_records", data.get("records"))
        if not raw:
            raise ValueError("backtest-history fixture has no annual_records")
        out = []
        for r in raw:
            out.append(
                {
                    "year": int(r["year"]),
                    "start_short_rate": float(r["start_short_rate"]),
                    "end_short_rate": float(r["end_short_rate"]),
                    "equity_return": float(r["equity_return"]),
                }
            )
        return out

    def _load_fixture(self) -> MarketDataResult:
        if not self._fixture_path.exists():
            raise FileNotFoundError("fixture not found: {}".format(self._fixture_path))
        data = json.loads(self._fixture_path.read_bytes().decode("utf-8"))
        records = self._records_from_payload(data)
        frame = self._validate(records)
        as_of_str = str(data["as_of_date"])
        # Retain the non-series fixture metadata (loss basis, windows, lineage)
        # for the history source; only the series itself is snapshot-sealed.
        self.fixture_meta = {
            "as_of_date": as_of_str,
            "market": str(data.get("market", self.market)),
            "loss_basis": {
                "base_equity_index": float(data["base_equity_index"]),
                "deterministic_discount_rate": float(data["deterministic_discount_rate"]),
                "guarantee_notional": float(data["guarantee_notional"]),
                "equity_weight": float(data["equity_weight"]),
                "duration_years": float(data["duration_years"]),
            },
            "in_sample_years": [int(y) for y in data.get("in_sample_years", [])],
            "out_of_sample_years": [int(y) for y in data.get("out_of_sample_years", [])],
            "data_lineage": data.get("data_lineage", {}),
            "fixture_id": str(data.get("fixture_id", "")),
        }
        path, sha = self._cache.store(
            self.dataset, as_of_str, records, PROVENANCE_FIXTURE,
            source_detail=str(self._fixture_path.resolve()),
        )
        lin = self.fixture_meta["data_lineage"]
        lineage = self._lineage(
            as_of_str, PROVENANCE_FIXTURE, str(self._fixture_path.resolve()), sha,
            approved_by=lin.get("approved_by", "unknown"),
            approval_timestamp=lin.get("approval_timestamp", "unknown"),
            version=lin.get("version", "unknown"),
        )
        return MarketDataResult(
            self.dataset, as_of_str, PROVENANCE_FIXTURE, frame, str(path), sha, lineage
        )

    @staticmethod
    def to_annual_records(result: MarketDataResult) -> List[Dict[str, float]]:
        frame = result.frame
        recs = []
        for _, row in frame.iterrows():
            recs.append(
                {
                    "year": int(row["year"]),
                    "start_short_rate": float(row["start_short_rate"]),
                    "end_short_rate": float(row["end_short_rate"]),
                    "equity_return": float(row["equity_return"]),
                }
            )
        recs.sort(key=lambda r: r["year"])
        return recs


# ---------------------------------------------------------------------------
# 2. History source that satisfies the Phase 13 contract via the item-#1 pipeline
# ---------------------------------------------------------------------------
class PipelineBacktestHistorySource(BacktestHistorySource):
    """``BacktestHistorySource`` whose realised series come through item #1's pipeline.

    The rate/equity **series** and their SHA-256 provenance are resolved by
    ``CNYBacktestHistoryLoader`` (item-#1 tiers); the **loss basis** and the
    in/out-of-sample **window** are read from the same fixture (they are model
    conventions, not market observations, so they do not need snapshot sealing).
    """

    def __init__(
        self,
        fixture_path=DEFAULT_HISTORY_FIXTURE,
        cache_dir: Optional[Path] = None,
        fetcher=None,
        as_of=None,
    ) -> None:
        self._fixture_path = Path(fixture_path)
        if cache_dir is None:
            # Never pollute the repo tree: snapshots are a runtime cache, not a
            # committed artifact. Default to a process-temp directory.
            cache_dir = Path(tempfile.gettempdir()) / "par_model_backtest_snapshots"
        self._cache = SnapshotCache(cache_dir)
        self._loader = CNYBacktestHistoryLoader(self._cache, fetcher=fetcher, fixture_path=self._fixture_path)
        self._result = self._loader.load(as_of=as_of)
        # _load_fixture populates fixture_meta; if a warm cache served the series
        # from the cached tier, re-read the fixture metadata directly.
        if not self._loader.fixture_meta:
            data = json.loads(self._fixture_path.read_bytes().decode("utf-8"))
            self._loader.fixture_meta = {
                "as_of_date": str(data["as_of_date"]),
                "market": str(data.get("market", "CN")),
                "loss_basis": {
                    "base_equity_index": float(data["base_equity_index"]),
                    "deterministic_discount_rate": float(data["deterministic_discount_rate"]),
                    "guarantee_notional": float(data["guarantee_notional"]),
                    "equity_weight": float(data["equity_weight"]),
                    "duration_years": float(data["duration_years"]),
                },
                "in_sample_years": [int(y) for y in data.get("in_sample_years", [])],
                "out_of_sample_years": [int(y) for y in data.get("out_of_sample_years", [])],
                "data_lineage": data.get("data_lineage", {}),
                "fixture_id": str(data.get("fixture_id", "")),
            }
        self._meta = self._loader.fixture_meta

    # -- BacktestHistorySource contract -------------------------------------
    @property
    def market(self) -> str:
        return str(self._meta["market"])

    def fetch_annual_records(self) -> List[Dict[str, float]]:
        return CNYBacktestHistoryLoader.to_annual_records(self._result)

    def fetch_as_of_date(self) -> date:
        return datetime.strptime(self._meta["as_of_date"], "%Y-%m-%d").date()

    def fetch_loss_basis(self) -> Dict[str, float]:
        return dict(self._meta["loss_basis"])

    def fetch_window_years(self) -> Tuple[List[int], List[int]]:
        return list(self._meta["in_sample_years"]), list(self._meta["out_of_sample_years"])

    def build_lineage_record(self) -> DataLineageRecord:
        return self._result.lineage

    # -- pipeline provenance passthrough ------------------------------------
    @property
    def provenance(self) -> str:
        return self._result.provenance

    @property
    def data_sha256(self) -> str:
        return self._result.sha256

    @property
    def snapshot_path(self) -> str:
        return self._result.snapshot_path


# ---------------------------------------------------------------------------
# 3. Recalibration triggers
# ---------------------------------------------------------------------------
# Severity ordering used to fold per-signal triggers into one recommendation.
_SEV_ORDER = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

# Trigger thresholds (single source of truth; mirror the G-09 acceptance bar).
RECAL_COVERAGE_MIN = BACKTEST_MIN_COVERAGE            # 0.70
RECAL_KUPIEC_MIN_PVALUE = 0.05
RECAL_VAR99_BREACH_LIMIT = BACKTEST_VAR99_BREACH_LIMIT  # 0.05
RECAL_VAR95_BREACH_LIMIT = 0.10
RECAL_OOS_DRIFT_LIMIT = 0.20


@dataclass
class RecalibrationTrigger:
    """One evaluated backtest signal and the recalibration action it implies."""

    name: str
    category: str
    observed: float
    threshold: float
    comparator: str  # ">=", ">", "<="
    breached: bool
    severity: str
    rationale: str
    recommended_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "observed": float(self.observed),
            "threshold": float(self.threshold),
            "comparator": self.comparator,
            "breached": bool(self.breached),
            "severity": self.severity,
            "rationale": self.rationale,
            "recommended_action": self.recommended_action,
        }


@dataclass
class RecalibrationTriggerReport:
    """Structured recalibration decision over a live-history backtest."""

    triggers: List[RecalibrationTrigger]
    n_breached: int
    max_severity: str
    recommendation: str
    engine_requires_recalibration: bool
    rationale: str
    evaluated_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation": self.recommendation,
            "max_severity": self.max_severity,
            "n_breached": int(self.n_breached),
            "engine_requires_recalibration": bool(self.engine_requires_recalibration),
            "rationale": self.rationale,
            "evaluated_at": self.evaluated_at,
            "triggers": [t.to_dict() for t in self.triggers],
        }

    def breached_names(self) -> List[str]:
        return [t.name for t in self.triggers if t.breached]


def _martingale_all_pass(result: BacktestResult) -> bool:
    mr = getattr(result, "martingale_results", None)
    if mr is None:
        return True
    try:
        return bool(mr.attrs.get("all_pass", False))
    except Exception:
        return False


def evaluate_recalibration_triggers(
    full_result: BacktestResult,
    oos_result: Optional[BacktestResult] = None,
) -> RecalibrationTriggerReport:
    """Map a live-history backtest outcome onto governed recalibration triggers.

    Each signal is compared to its acceptance threshold; a breach carries a
    severity and a specific recommended recalibration action.  The overall
    recommendation is the worst breached severity:
      CRITICAL -> RECALIBRATION_REQUIRED
      HIGH     -> SCHEDULE_RECALIBRATION
      MEDIUM   -> ENHANCED_MONITORING
      else     -> NO_ACTION_MONITOR
    """
    triggers: List[RecalibrationTrigger] = []

    triggers.append(RecalibrationTrigger(
        name="rate_band_coverage",
        category="coverage",
        observed=float(full_result.rate_coverage_pct),
        threshold=RECAL_COVERAGE_MIN,
        comparator=">=",
        breached=bool(full_result.rate_coverage_pct < RECAL_COVERAGE_MIN),
        severity="CRITICAL",
        rationale="Realised short rates fall outside the P-measure band too often.",
        recommended_action="Recalibrate HW1F mean-reversion (a) and short-rate vol (sigma_r) on refreshed CNY curve history.",
    ))
    triggers.append(RecalibrationTrigger(
        name="equity_band_coverage",
        category="coverage",
        observed=float(full_result.equity_coverage_pct),
        threshold=RECAL_COVERAGE_MIN,
        comparator=">=",
        breached=bool(full_result.equity_coverage_pct < RECAL_COVERAGE_MIN),
        severity="CRITICAL",
        rationale="Realised equity returns fall outside the P-measure band too often.",
        recommended_action="Recalibrate GBM equity drift (ERP) and vol (sigma_S) on refreshed CSI 300 history.",
    ))
    triggers.append(RecalibrationTrigger(
        name="kupiec_var95_pof",
        category="var_exception",
        observed=float(full_result.kupiec_pvalue_95),
        threshold=RECAL_KUPIEC_MIN_PVALUE,
        comparator=">",
        breached=bool(full_result.kupiec_pvalue_95 <= RECAL_KUPIEC_MIN_PVALUE),
        severity="HIGH",
        rationale="Kupiec POF rejects the VaR95 exception frequency.",
        recommended_action="Review 95% tail calibration / scenario count; re-estimate loss-proxy dispersion.",
    ))
    triggers.append(RecalibrationTrigger(
        name="kupiec_var99_pof",
        category="var_exception",
        observed=float(full_result.kupiec_pvalue_99),
        threshold=RECAL_KUPIEC_MIN_PVALUE,
        comparator=">",
        breached=bool(full_result.kupiec_pvalue_99 <= RECAL_KUPIEC_MIN_PVALUE),
        severity="HIGH",
        rationale="Kupiec POF rejects the VaR99 exception frequency.",
        recommended_action="Review 99% tail calibration; re-estimate tail-loss dispersion and dependence.",
    ))
    triggers.append(RecalibrationTrigger(
        name="var99_breach_rate",
        category="var_exception",
        observed=float(full_result.var99_exception_rate),
        threshold=RECAL_VAR99_BREACH_LIMIT,
        comparator="<=",
        breached=bool(full_result.var99_exception_rate > RECAL_VAR99_BREACH_LIMIT),
        severity="CRITICAL",
        rationale="VaR99 exceedances exceed the regulatory tolerance.",
        recommended_action="Recalibrate the tail; escalate to Model Owner for capital-adequacy review.",
    ))
    triggers.append(RecalibrationTrigger(
        name="var95_breach_rate",
        category="var_exception",
        observed=float(full_result.var95_exception_rate),
        threshold=RECAL_VAR95_BREACH_LIMIT,
        comparator="<=",
        breached=bool(full_result.var95_exception_rate > RECAL_VAR95_BREACH_LIMIT),
        severity="MEDIUM",
        rationale="VaR95 exceedances above the monitoring tolerance.",
        recommended_action="Monitor; schedule a calibration review if the breach persists next cycle.",
    ))
    mg_pass = _martingale_all_pass(full_result)
    triggers.append(RecalibrationTrigger(
        name="martingale_q_measure",
        category="risk_neutral",
        observed=1.0 if mg_pass else 0.0,
        threshold=1.0,
        comparator=">=",
        breached=bool(not mg_pass),
        severity="CRITICAL",
        rationale="Q-measure martingale test failed (risk-neutral drift off).",
        recommended_action="Re-run the risk-neutral drift correction before any revaluation; do not re-baseline the headline.",
    ))

    if oos_result is not None:
        drift = max(
            abs(float(oos_result.rate_coverage_pct) - float(full_result.rate_coverage_pct)),
            abs(float(oos_result.equity_coverage_pct) - float(full_result.equity_coverage_pct)),
        )
        triggers.append(RecalibrationTrigger(
            name="oos_coverage_drift",
            category="stability",
            observed=float(drift),
            threshold=RECAL_OOS_DRIFT_LIMIT,
            comparator="<=",
            breached=bool(drift > RECAL_OOS_DRIFT_LIMIT),
            severity="HIGH",
            rationale="In-sample vs out-of-sample band coverage diverges (parameter instability).",
            recommended_action="Schedule recalibration with a rolling-window stability check (VR-S05).",
        ))

    breached = [t for t in triggers if t.breached]
    max_sev = "NONE"
    for t in breached:
        if _SEV_ORDER[t.severity] > _SEV_ORDER[max_sev]:
            max_sev = t.severity
    recommendation = {
        "NONE": "NO_ACTION_MONITOR",
        "LOW": "NO_ACTION_MONITOR",
        "MEDIUM": "ENHANCED_MONITORING",
        "HIGH": "SCHEDULE_RECALIBRATION",
        "CRITICAL": "RECALIBRATION_REQUIRED",
    }[max_sev]
    if breached:
        rationale = "{} trigger(s) breached ({}); worst severity {} -> {}.".format(
            len(breached), ", ".join(t.name for t in breached), max_sev, recommendation
        )
    else:
        rationale = "No recalibration trigger breached on live history; continue annual monitoring."

    return RecalibrationTriggerReport(
        triggers=triggers,
        n_breached=len(breached),
        max_severity=max_sev,
        recommendation=recommendation,
        engine_requires_recalibration=bool(full_result.requires_recalibration),
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# 4. Report container + runner
# ---------------------------------------------------------------------------
@dataclass
class LiveHistoryBacktestReport:
    run_timestamp: str
    market: str
    provenance: str
    data_sha256: str
    lineage: Dict[str, Any]
    n_full: int
    n_in_sample: int
    n_oos: int
    calibration: Dict[str, Any]
    full_summary: Dict[str, Any]
    oos_summary: Dict[str, Any]
    gate_g09: Dict[str, Any]
    recalibration: Dict[str, Any]
    inputs_digest: str
    schema: str = SCHEMA
    unsigned: bool = True
    unsigned_banner: str = UNSIGNED_BANNER

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "run_timestamp": self.run_timestamp,
            "market": self.market,
            "unsigned": self.unsigned,
            "unsigned_banner": self.unsigned_banner,
            "provenance": self.provenance,
            "data_sha256": self.data_sha256,
            "inputs_digest": self.inputs_digest,
            "lineage": self.lineage,
            "n_full": self.n_full,
            "n_in_sample": self.n_in_sample,
            "n_oos": self.n_oos,
            "calibration": self.calibration,
            "full_result": self.full_summary,
            "oos_result": self.oos_summary,
            "gate_g09": self.gate_g09,
            "recalibration": self.recalibration,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, default=str)


def _canonical_digest(payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _calibration_to_dict(cal) -> Dict[str, Any]:
    return {
        "calibration_date": str(cal.calibration_date),
        "a": float(cal.a),
        "sigma_r": float(cal.sigma_r),
        "lambda_r": float(cal.lambda_r),
        "r0": float(cal.r0),
        "sigma_S": float(cal.sigma_S),
        "erp": float(cal.erp),
        "dividend_yield": float(cal.dividend_yield),
        "rho": float(cal.rho),
    }


DEFAULT_ARTIFACT_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "validation" / "LIVE_HISTORY_BACKTEST.json"
)


def run_live_history_backtest(
    fixture_path=DEFAULT_HISTORY_FIXTURE,
    cache_dir: Optional[Path] = None,
    n_scenarios: int = 1500,
    seed: int = 20260709,
    governance_store: Optional[GovernanceStore] = None,
    artifact_path=DEFAULT_ARTIFACT_PATH,
    write_artifact: bool = True,
    actor: str = "Claude Actuarial Agent",
) -> LiveHistoryBacktestReport:
    """Run the item-#6 live-history backtest end to end and (optionally) persist it.

    Series provenance flows through item #1's pipeline; Kupiec POF + coverage
    come from the governed ``BacktestEngine``; recalibration triggers are
    evaluated on the >= 10-year result.  No governed headline is touched.
    """
    run_ts = datetime.now(timezone.utc).isoformat()

    source = PipelineBacktestHistorySource(fixture_path=fixture_path, cache_dir=cache_dir)
    loader = LiveBacktestDataLoader(source)
    full_ds = loader.load_full()
    in_ds, oos_ds, in_records = loader.load_split()
    basis = loader.loss_basis
    lineage = source.build_lineage_record()

    if governance_store is None:
        governance_store = GovernanceStore()

    calibration = calibrate_from_history(
        in_records,
        calibration_date=source.fetch_as_of_date(),
        r0=float(full_ds.observations.iloc[0]["initial_short_rate"]),
    )

    common = dict(
        calibration_result=calibration,
        deterministic_discount_rate=basis["deterministic_discount_rate"],
        guarantee_notional=basis["guarantee_notional"],
        equity_weight=basis["equity_weight"],
        duration_years=basis["duration_years"],
    )

    full_engine = BacktestEngine(governance_store=governance_store, actor=actor, **common)
    full_result = full_engine.run(full_ds, n_scenarios=n_scenarios, seed=seed)

    oos_engine = BacktestEngine(governance_store=None, actor=actor, **common)
    oos_result = oos_engine.run(oos_ds, n_scenarios=n_scenarios, seed=seed + 7)

    gate = evaluate_g09_gate(
        n_observations=full_ds.n_observations,
        loaded_from_live_file=True,
        rate_coverage_pct=full_result.rate_coverage_pct,
        equity_coverage_pct=full_result.equity_coverage_pct,
        kupiec_pvalue_95=full_result.kupiec_pvalue_95,
        var99_exception_rate=full_result.var99_exception_rate,
        annual_report_populated=bool(write_artifact),
        audit_entry_id=full_result.audit_entry_id,
    )

    recal = evaluate_recalibration_triggers(full_result, oos_result)

    digest = _canonical_digest(
        {
            "records": source.fetch_annual_records(),
            "loss_basis": basis,
            "n_scenarios": int(n_scenarios),
            "seed": int(seed),
            "data_sha256": source.data_sha256,
        }
    )

    report = LiveHistoryBacktestReport(
        run_timestamp=run_ts,
        market=source.market,
        provenance=source.provenance,
        data_sha256=source.data_sha256,
        lineage=lineage.to_dict() if hasattr(lineage, "to_dict") else dict(lineage.__dict__),
        n_full=int(full_ds.n_observations),
        n_in_sample=int(in_ds.n_observations),
        n_oos=int(oos_ds.n_observations),
        calibration=_calibration_to_dict(calibration),
        full_summary=full_result.summary(),
        oos_summary=oos_result.summary(),
        gate_g09=gate.to_dict() if hasattr(gate, "to_dict") else dict(gate.__dict__),
        recalibration=recal.to_dict(),
        inputs_digest=digest,
    )

    if write_artifact and artifact_path is not None:
        artifact_path = Path(artifact_path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(report.to_json(), encoding="utf-8")

    return report


__all__ = [
    "SCHEMA",
    "UNSIGNED_BANNER",
    "DEFAULT_HISTORY_FIXTURE",
    "DEFAULT_ARTIFACT_PATH",
    "RECAL_COVERAGE_MIN",
    "RECAL_KUPIEC_MIN_PVALUE",
    "RECAL_VAR95_BREACH_LIMIT",
    "RECAL_VAR99_BREACH_LIMIT",
    "RECAL_OOS_DRIFT_LIMIT",
    "CNYBacktestHistoryLoader",
    "PipelineBacktestHistorySource",
    "RecalibrationTrigger",
    "RecalibrationTriggerReport",
    "evaluate_recalibration_triggers",
    "LiveHistoryBacktestReport",
    "run_live_history_backtest",
]
