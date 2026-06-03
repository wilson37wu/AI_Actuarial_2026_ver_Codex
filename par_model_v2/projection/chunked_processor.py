"""
Phase 11 Task 2: grouping, chunking, checkpoint restart, failed-chunk audit,
and portfolio reconciliation.

This module provides a reusable framework for processing large policy portfolios
(e.g. the 100,000-policy synthetic Hong Kong PAR portfolio from Task 1) in
deterministic, resumable chunks.  It is intentionally self-contained so it can
be dropped into any projection pipeline that operates on a pandas.DataFrame
policy table.

Design goals
------------
* Deterministic ordering.  Chunks are derived from a stable sort of the
  portfolio, so the same input always produces identical chunk boundaries.
* Grouping.  Before chunking the portfolio may be partitioned by one or
  more column keys (e.g. product_line, age_band).  Within each group
  records are sorted and then split into fixed-size chunks, so groups are never
  split across chunk boundaries.  Grouping is optional; pass group_by=None
  (the default) to chunk the whole portfolio as a single ordered stream.
* Checkpoint restart.  After each chunk completes (or fails) the checkpoint
  file is updated with an atomic write-then-rename pattern.  A restarted run
  reads the checkpoint and skips any chunk already in COMPLETED status, so
  partial runs are safe to re-execute.
* Failed-chunk audit.  Failed chunks are logged with the exception class,
  message, and a truncated traceback.  The retry_failed method retries only
  those chunks, enabling targeted reruns without touching successful work.
* Reconciliation.  After all chunks finish reconcile_portfolio compares
  the aggregate statistics collected by each chunk against the source portfolio
  to detect double-processing, gaps, or data corruption.
* Educational framing.  The checkpoint file is a plain, human-readable JSON
  document that practitioners can inspect, edit to skip known-bad chunks, or
  reset entirely to force a full rerun.

Limitations
-----------
Thread/process safety is NOT provided.  The atomic rename is safe for a single
process.  Multi-worker pipelines would need an external lock or a database-backed
store.

chunk_fn is called synchronously in the current process.  Large workloads
should be moved to multiprocessing or concurrent.futures outside this module;
the checkpoint/reconciliation layer here remains reusable.

All chunk boundaries are computed once at plan-build time and stored in the
checkpoint.  Editing the plan after it has been committed to disk (e.g. to
change chunk_size) requires deleting the checkpoint and replanning.

SOA ASOP 56 alignment
---------------------
Reproducibility: plan is deterministic and digest-evidenced.
Auditability: every chunk outcome (including failures) is persisted with
timestamps and error details.
Model-use restriction: module is for educational / research use only; outputs
are not cleared for production insurance valuation.

IA TAS M / TAS 100 alignment
-----------------------------
Traceability: checkpoint JSON links each processed chunk to its row bounds,
group key, start/end timestamps, and result digest.
Error handling: failed chunks are preserved in the audit trail rather than
silently skipped.
"""

from __future__ import annotations

import json
import os
import tempfile
import traceback
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from par_model_v2.projection.portfolio_generator import (
    PRODUCT_LINE_CASH,
    PRODUCT_LINE_RB,
    UNIFIED_COLUMNS,
    portfolio_summary,
)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

_CHECKPOINT_VERSION = "1.0"
_MAX_TRACEBACK_CHARS = 2_000

# ---------------------------------------------------------------------------
# Helpers -- defined early so dataclass field(default_factory=...) can use them
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class ChunkStatus(str, Enum):
    """Lifecycle status of a single processing chunk."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Core data classes
# ---------------------------------------------------------------------------


@dataclass
class ChunkRecord:
    """Metadata and outcome record for a single portfolio chunk.

    Parameters
    ----------
    chunk_id : str
        Zero-padded unique identifier, e.g. ``"chunk_0007"``.
    group_key : tuple
        Tuple of (column, value) pairs for the group this chunk belongs to.
        Empty tuple when no grouping is applied.
    start_row : int
        First row index (inclusive) into the canonically sorted portfolio.
    end_row : int
        Last row index (exclusive) -- ``portfolio.iloc[start_row:end_row]``.
    n_policies : int
        Number of policies in the chunk.
    status : ChunkStatus
        Current lifecycle status.
    result : dict or None
        Mapping returned by chunk_fn on success, or None.
    error : dict or None
        Dict with type, message, traceback on failure, or None.
    started_at : str or None
        ISO-8601 UTC timestamp set when chunk starts.
    completed_at : str or None
        ISO-8601 UTC timestamp set when chunk finishes.
    """

    chunk_id: str
    group_key: Tuple[Tuple[str, Any], ...]
    start_row: int
    end_row: int
    n_policies: int
    status: ChunkStatus = ChunkStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "group_key": list(self.group_key),
            "start_row": self.start_row,
            "end_row": self.end_row,
            "n_policies": self.n_policies,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChunkRecord":
        return cls(
            chunk_id=d["chunk_id"],
            group_key=tuple(tuple(pair) for pair in d["group_key"]),
            start_row=d["start_row"],
            end_row=d["end_row"],
            n_policies=d["n_policies"],
            status=ChunkStatus(d["status"]),
            result=d.get("result"),
            error=d.get("error"),
            started_at=d.get("started_at"),
            completed_at=d.get("completed_at"),
        )


@dataclass
class ProcessingPlan:
    """Immutable description of how the portfolio will be chunked."""

    portfolio_digest: str
    n_policies: int
    chunk_size: int
    group_by: Optional[List[str]]
    n_chunks: int
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_digest": self.portfolio_digest,
            "n_policies": self.n_policies,
            "chunk_size": self.chunk_size,
            "group_by": self.group_by,
            "n_chunks": self.n_chunks,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProcessingPlan":
        return cls(**d)


# ---------------------------------------------------------------------------
# Checkpoint store
# ---------------------------------------------------------------------------


class CheckpointStore:
    """Read / write a JSON checkpoint file with atomic write-then-rename.

    Parameters
    ----------
    path : Path or str
        File path for the checkpoint JSON.  Parent directories are created on
        first write.
    """

    VERSION = _CHECKPOINT_VERSION

    def __init__(self, path) -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> Tuple[ProcessingPlan, List[ChunkRecord]]:
        with self.path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        version = raw.get("checkpoint_version", "unknown")
        if version != self.VERSION:
            raise ValueError(
                "checkpoint version {} incompatible with {}".format(version, self.VERSION)
            )
        plan = ProcessingPlan.from_dict(raw["plan"])
        records = [ChunkRecord.from_dict(r) for r in raw["chunks"]]
        return plan, records

    def save(self, plan: ProcessingPlan, records: List[ChunkRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "checkpoint_version": self.VERSION,
            "saved_at": _now_iso(),
            "plan": plan.to_dict(),
            "chunks": [r.to_dict() for r in records],
        }
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.path.parent),
            prefix=".chk_",
            suffix=".json.tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            os.replace(tmp_path, str(self.path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def reset(self) -> None:
        if self.path.exists():
            self.path.unlink()


# ---------------------------------------------------------------------------
# Plan builder
# ---------------------------------------------------------------------------


def _canonical_sort(table: pd.DataFrame, group_by: Optional[List[str]]) -> pd.DataFrame:
    sort_keys = list(group_by) if group_by else []
    sort_keys.append("policy_id")
    return table.sort_values(sort_keys, kind="mergesort").reset_index(drop=True)


def _portfolio_digest_fast(table: pd.DataFrame) -> str:
    import hashlib
    ids = "|".join(str(x) for x in table["policy_id"].sort_values())
    return hashlib.sha256(ids.encode("utf-8")).hexdigest()[:16]


def build_chunk_plan(
    portfolio: pd.DataFrame,
    *,
    chunk_size: int = 10_000,
    group_by: Optional[List[str]] = None,
) -> Tuple[ProcessingPlan, List[ChunkRecord]]:
    """Partition the portfolio into deterministic chunks.

    Parameters
    ----------
    portfolio : pd.DataFrame
        The full unified policy table (must contain UNIFIED_COLUMNS).
    chunk_size : int
        Maximum number of policies per chunk.
    group_by : list of str or None
        Optional column keys to partition by before chunking.  When provided,
        groups are kept intact -- a chunk never spans two groups.

    Returns
    -------
    plan : ProcessingPlan
    records : list of ChunkRecord (all PENDING)
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    missing = sorted(set(UNIFIED_COLUMNS).difference(portfolio.columns))
    if missing:
        raise ValueError("portfolio missing columns: {}".format(", ".join(missing)))

    ordered = _canonical_sort(portfolio, group_by)
    digest = _portfolio_digest_fast(ordered)
    records: List[ChunkRecord] = []
    chunk_idx = 0

    if group_by:
        groups = ordered.groupby(group_by, sort=True, observed=True)
        for group_values, group_df in groups:
            if isinstance(group_values, tuple):
                gkey = tuple(zip(group_by, group_values))
            else:
                gkey = ((group_by[0], group_values),)

            for rel_start in range(0, len(group_df), chunk_size):
                chunk_slice = group_df.iloc[rel_start:rel_start + chunk_size]
                abs_start = int(chunk_slice.index[0])
                abs_end = int(chunk_slice.index[-1]) + 1
                records.append(
                    ChunkRecord(
                        chunk_id=_chunk_id(chunk_idx),
                        group_key=gkey,
                        start_row=abs_start,
                        end_row=abs_end,
                        n_policies=len(chunk_slice),
                    )
                )
                chunk_idx += 1
    else:
        n_total = len(ordered)
        for start in range(0, n_total, chunk_size):
            end = min(start + chunk_size, n_total)
            records.append(
                ChunkRecord(
                    chunk_id=_chunk_id(chunk_idx),
                    group_key=(),
                    start_row=start,
                    end_row=end,
                    n_policies=end - start,
                )
            )
            chunk_idx += 1

    plan = ProcessingPlan(
        portfolio_digest=digest,
        n_policies=len(ordered),
        chunk_size=chunk_size,
        group_by=group_by,
        n_chunks=len(records),
        created_at=_now_iso(),
    )
    return plan, records


# ---------------------------------------------------------------------------
# Chunk function protocol
# ---------------------------------------------------------------------------

ChunkFn = Callable[[pd.DataFrame, str], Dict[str, Any]]

REQUIRED_CHUNK_RESULT_KEYS = frozenset(
    ["n_policies", "total_sum_assured", "n_cash_dividend", "n_reversionary_bonus"]
)


def default_chunk_fn(chunk_df: pd.DataFrame, chunk_id: str) -> Dict[str, Any]:
    """Built-in aggregation chunk function -- computes portfolio statistics.

    Returns the headline statistics needed for reconciliation plus the chunk_id.
    Custom chunk_fn implementations must return at least REQUIRED_CHUNK_RESULT_KEYS.
    """
    summary = portfolio_summary(chunk_df)
    return {
        "chunk_id": chunk_id,
        "n_policies": summary["n_policies"],
        "total_sum_assured": summary["total_sum_assured"],
        "total_annual_premium": summary["total_annual_premium"],
        "n_cash_dividend": summary["n_cash_dividend"],
        "n_reversionary_bonus": summary["n_reversionary_bonus"],
        "mean_sum_assured": summary["mean_sum_assured"],
        "mean_issue_age": summary["mean_issue_age"],
    }


# ---------------------------------------------------------------------------
# Chunked processor
# ---------------------------------------------------------------------------


class ChunkedPortfolioProcessor:
    """Orchestrate chunked processing of a large policy portfolio with restart.

    On first run, builds a ProcessingPlan and persists it in the checkpoint
    file.  On subsequent runs, restores the plan and skips COMPLETED chunks.

    Parameters
    ----------
    checkpoint_path : Path or str
        File path for the JSON checkpoint.
    chunk_fn : callable or None
        chunk_fn(chunk_df, chunk_id) -> dict.  Defaults to default_chunk_fn.
    chunk_size : int
        Maximum policies per chunk (ignored when resuming an existing plan).
    group_by : list of str or None
        Column keys for grouping (ignored when resuming an existing plan).
    """

    def __init__(
        self,
        checkpoint_path,
        *,
        chunk_fn: Optional[ChunkFn] = None,
        chunk_size: int = 10_000,
        group_by: Optional[List[str]] = None,
    ) -> None:
        self.store = CheckpointStore(checkpoint_path)
        self.chunk_fn = chunk_fn if chunk_fn is not None else default_chunk_fn
        self.chunk_size = chunk_size
        self.group_by = group_by
        self._plan: Optional[ProcessingPlan] = None
        self._records: Optional[List[ChunkRecord]] = None

    # ------------------------------------------------------------------
    # Plan management
    # ------------------------------------------------------------------

    def _load_or_build(self, portfolio: pd.DataFrame) -> None:
        if self.store.exists():
            self._plan, self._records = self.store.load()
            if self._plan.n_policies != len(portfolio):
                raise ValueError(
                    "checkpoint built for {} policies but portfolio has {}; "
                    "delete the checkpoint to replan".format(
                        self._plan.n_policies, len(portfolio)
                    )
                )
        else:
            self._plan, self._records = build_chunk_plan(
                portfolio,
                chunk_size=self.chunk_size,
                group_by=self.group_by,
            )
            self.store.save(self._plan, self._records)

    def _ordered_portfolio(self, portfolio: pd.DataFrame) -> pd.DataFrame:
        return _canonical_sort(portfolio, self._plan.group_by)

    # ------------------------------------------------------------------
    # Core run loop
    # ------------------------------------------------------------------

    def run(
        self,
        portfolio: pd.DataFrame,
        *,
        on_chunk_complete: Optional[Callable[[ChunkRecord], None]] = None,
    ) -> Dict[str, Any]:
        """Process all PENDING (and IN_PROGRESS) chunks.

        Parameters
        ----------
        portfolio : pd.DataFrame
            The full policy table.
        on_chunk_complete : callable or None
            Optional callback invoked after each chunk finishes with the
            updated ChunkRecord.

        Returns
        -------
        dict
            Keys: n_chunks, n_completed, n_failed, n_pending, elapsed_seconds.
        """
        import time
        start = time.monotonic()
        self._load_or_build(portfolio)
        ordered = self._ordered_portfolio(portfolio)

        for rec in self._records:
            if rec.status == ChunkStatus.COMPLETED:
                continue
            self._process_chunk(rec, ordered)
            if on_chunk_complete is not None:
                on_chunk_complete(rec)

        return self._run_summary(time.monotonic() - start)

    def retry_failed(
        self,
        portfolio: pd.DataFrame,
        *,
        on_chunk_complete: Optional[Callable[[ChunkRecord], None]] = None,
    ) -> Dict[str, Any]:
        """Retry only FAILED chunks.

        Resets FAILED chunks to PENDING and re-runs them without touching
        COMPLETED chunks.
        """
        import time
        start = time.monotonic()
        if self._records is None:
            self._load_or_build(portfolio)
        ordered = self._ordered_portfolio(portfolio)

        for rec in self._records:
            if rec.status != ChunkStatus.FAILED:
                continue
            rec.status = ChunkStatus.PENDING
            rec.error = None
            rec.result = None
            self._process_chunk(rec, ordered)
            if on_chunk_complete is not None:
                on_chunk_complete(rec)

        return self._run_summary(time.monotonic() - start)

    # ------------------------------------------------------------------
    # Internal processing
    # ------------------------------------------------------------------

    def _process_chunk(self, rec: ChunkRecord, ordered: pd.DataFrame) -> None:
        rec.status = ChunkStatus.IN_PROGRESS
        rec.started_at = _now_iso()
        self.store.save(self._plan, self._records)

        chunk_df = ordered.iloc[rec.start_row:rec.end_row].reset_index(drop=True)
        try:
            result = self.chunk_fn(chunk_df, rec.chunk_id)
            _validate_chunk_result(result, rec.chunk_id)
            rec.status = ChunkStatus.COMPLETED
            rec.result = result
            rec.error = None
        except Exception as exc:
            rec.status = ChunkStatus.FAILED
            rec.result = None
            rec.error = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc()[-_MAX_TRACEBACK_CHARS:],
            }
        finally:
            rec.completed_at = _now_iso()
            self.store.save(self._plan, self._records)

    # ------------------------------------------------------------------
    # Status / summary
    # ------------------------------------------------------------------

    def status_summary(self) -> Dict[str, Any]:
        """Return chunk status counts without running any work."""
        if self._records is None:
            if self.store.exists():
                self._plan, self._records = self.store.load()
            else:
                return {"error": "no checkpoint loaded -- call run() first"}
        return self._run_summary(elapsed_seconds=None)

    def _run_summary(self, elapsed_seconds: Optional[float]) -> Dict[str, Any]:
        counts = Counter(r.status for r in self._records)
        summary: Dict[str, Any] = {
            "n_chunks": len(self._records),
            "n_completed": counts[ChunkStatus.COMPLETED],
            "n_failed": counts[ChunkStatus.FAILED],
            "n_pending": counts[ChunkStatus.PENDING] + counts[ChunkStatus.IN_PROGRESS],
            "failed_chunk_ids": [r.chunk_id for r in self._records if r.status == ChunkStatus.FAILED],
        }
        if elapsed_seconds is not None:
            summary["elapsed_seconds"] = round(elapsed_seconds, 3)
        return summary

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def reconcile(self, portfolio: pd.DataFrame) -> "ReconciliationReport":
        """Run reconciliation against the source portfolio.

        Compares aggregated chunk statistics against the source portfolio.
        Should be called after all chunks have been processed.
        """
        if self._records is None:
            self._load_or_build(portfolio)
        return reconcile_portfolio(portfolio, self._records)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def plan(self) -> Optional[ProcessingPlan]:
        return self._plan

    @property
    def records(self) -> Optional[List[ChunkRecord]]:
        return self._records

    def failed_records(self) -> List[ChunkRecord]:
        if not self._records:
            return []
        return [r for r in self._records if r.status == ChunkStatus.FAILED]

    def completed_records(self) -> List[ChunkRecord]:
        if not self._records:
            return []
        return [r for r in self._records if r.status == ChunkStatus.COMPLETED]


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


@dataclass
class ReconciliationCheck:
    """Result of a single reconciliation assertion."""

    name: str
    passed: bool
    source_value: Any
    chunk_value: Any
    tolerance: Optional[float] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "source_value": self.source_value,
            "chunk_value": self.chunk_value,
            "tolerance": self.tolerance,
            "message": self.message,
        }


@dataclass
class ReconciliationReport:
    """Outcome of a full portfolio reconciliation.

    Parameters
    ----------
    passed : bool
        True only if every individual check passed.
    n_chunks_checked : int
        Number of COMPLETED chunks included in the reconciliation.
    n_failed_chunks : int
        Number of chunks still in FAILED status.
    checks : list of ReconciliationCheck
    reconciled_at : str
        ISO-8601 UTC timestamp.
    """

    passed: bool
    n_chunks_checked: int
    n_failed_chunks: int
    checks: List[ReconciliationCheck] = field(default_factory=list)
    reconciled_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "n_chunks_checked": self.n_chunks_checked,
            "n_failed_chunks": self.n_failed_chunks,
            "checks": [c.to_dict() for c in self.checks],
            "reconciled_at": self.reconciled_at,
        }

    def failed_checks(self) -> List[ReconciliationCheck]:
        return [c for c in self.checks if not c.passed]

    def summary_string(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        n_fail = len(self.failed_checks())
        return (
            "Reconciliation {}: {}/{} checks passed, "
            "{} chunks OK, {} chunks failed".format(
                status,
                len(self.checks) - n_fail,
                len(self.checks),
                self.n_chunks_checked,
                self.n_failed_chunks,
            )
        )


_REL_TOLERANCE = 1e-6


def reconcile_portfolio(
    source: pd.DataFrame,
    records: List[ChunkRecord],
    *,
    tolerance: float = _REL_TOLERANCE,
) -> ReconciliationReport:
    """Compare aggregated chunk results against the source portfolio.

    Parameters
    ----------
    source : pd.DataFrame
        The full policy table used to build the processing plan.
    records : list of ChunkRecord
        Chunk records after processing.
    tolerance : float
        Relative tolerance for floating-point comparisons.

    Returns
    -------
    ReconciliationReport
        passed=True only if every check passes.
    """
    completed = [r for r in records if r.status == ChunkStatus.COMPLETED]
    failed = [r for r in records if r.status == ChunkStatus.FAILED]
    pending = [r for r in records if r.status in (ChunkStatus.PENDING, ChunkStatus.IN_PROGRESS)]

    checks: List[ReconciliationCheck] = []

    # 1. All chunks completed
    checks.append(ReconciliationCheck(
        name="all_chunks_completed",
        passed=len(failed) == 0 and len(pending) == 0,
        source_value=len(records),
        chunk_value=len(completed),
        message=(
            "OK"
            if len(failed) == 0 and len(pending) == 0
            else "{} failed, {} pending/in-progress".format(len(failed), len(pending))
        ),
    ))

    # 2. Policy count
    chunk_n = sum(r.result["n_policies"] for r in completed if r.result)
    src_n = len(source)
    checks.append(ReconciliationCheck(
        name="policy_count",
        passed=chunk_n == src_n,
        source_value=src_n,
        chunk_value=chunk_n,
        message="OK" if chunk_n == src_n else "diff={}".format(chunk_n - src_n),
    ))

    # 3. No row overlap
    chunk_row_ranges = [(r.start_row, r.end_row) for r in completed]
    overlap_msg = _check_no_overlap(chunk_row_ranges)
    checks.append(ReconciliationCheck(
        name="no_row_overlap",
        passed=not bool(overlap_msg),
        source_value="no overlaps",
        chunk_value="overlap detected" if overlap_msg else "no overlaps",
        message=overlap_msg or "OK",
    ))

    # 4. Total sum assured
    src_tsa = float(source["sum_assured"].sum())
    chunk_tsa = sum(r.result.get("total_sum_assured", 0.0) for r in completed if r.result)
    tsa_ok = _rel_close(src_tsa, chunk_tsa, tolerance)
    checks.append(ReconciliationCheck(
        name="total_sum_assured",
        passed=tsa_ok,
        source_value=round(src_tsa, 2),
        chunk_value=round(chunk_tsa, 2),
        tolerance=tolerance,
        message="OK" if tsa_ok else "diff={:.2f}".format(chunk_tsa - src_tsa),
    ))

    # 5. Cash dividend count
    src_cash = int((source["product_line"] == PRODUCT_LINE_CASH).sum())
    chunk_cash = int(sum(r.result.get("n_cash_dividend", 0) for r in completed if r.result))
    checks.append(ReconciliationCheck(
        name="cash_dividend_count",
        passed=chunk_cash == src_cash,
        source_value=src_cash,
        chunk_value=chunk_cash,
        message="OK" if chunk_cash == src_cash else "diff={}".format(chunk_cash - src_cash),
    ))

    # 6. Reversionary bonus count
    src_rb = int((source["product_line"] == PRODUCT_LINE_RB).sum())
    chunk_rb = int(sum(r.result.get("n_reversionary_bonus", 0) for r in completed if r.result))
    checks.append(ReconciliationCheck(
        name="reversionary_bonus_count",
        passed=chunk_rb == src_rb,
        source_value=src_rb,
        chunk_value=chunk_rb,
        message="OK" if chunk_rb == src_rb else "diff={}".format(chunk_rb - src_rb),
    ))

    # 7. Chunk ID uniqueness
    all_ids = [r.chunk_id for r in records]
    ids_unique = len(set(all_ids)) == len(all_ids)
    checks.append(ReconciliationCheck(
        name="chunk_id_uniqueness",
        passed=ids_unique,
        source_value=len(all_ids),
        chunk_value=len(set(all_ids)),
        message="OK" if ids_unique else "duplicate chunk_ids found",
    ))

    passed = all(c.passed for c in checks)
    return ReconciliationReport(
        passed=passed,
        n_chunks_checked=len(completed),
        n_failed_chunks=len(failed),
        checks=checks,
        reconciled_at=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Failed-chunk audit
# ---------------------------------------------------------------------------


def failed_chunk_audit_report(records: List[ChunkRecord]) -> Dict[str, Any]:
    """Return a structured audit summary of all failed chunks.

    Provides chunk IDs, group keys, row bounds, error types, and truncated
    error messages for operator triage without inspecting the full checkpoint.

    Parameters
    ----------
    records : list of ChunkRecord

    Returns
    -------
    dict with keys n_failed, failed_chunks (list), audit_at.
    """
    failed = [r for r in records if r.status == ChunkStatus.FAILED]
    return {
        "n_failed": len(failed),
        "failed_chunks": [
            {
                "chunk_id": r.chunk_id,
                "group_key": list(r.group_key),
                "start_row": r.start_row,
                "end_row": r.end_row,
                "n_policies": r.n_policies,
                "error_type": r.error.get("type") if r.error else None,
                "error_message": r.error.get("message") if r.error else None,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
            }
            for r in failed
        ],
        "audit_at": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunk_id(idx: int) -> str:
    return "chunk_{:05d}".format(idx)


def _rel_close(a: float, b: float, tol: float) -> bool:
    denom = max(abs(a), abs(b), 1e-10)
    return abs(a - b) / denom <= tol


def _check_no_overlap(ranges: List[Tuple[int, int]]) -> str:
    sorted_ranges = sorted(ranges)
    for i in range(len(sorted_ranges) - 1):
        a_end = sorted_ranges[i][1]
        b_start = sorted_ranges[i + 1][0]
        if b_start < a_end:
            return "rows {}-{} overlap with {}-{}".format(
                sorted_ranges[i][0], a_end, b_start, sorted_ranges[i + 1][1]
            )
    return ""


def _validate_chunk_result(result: Any, chunk_id: str) -> None:
    if not isinstance(result, dict):
        raise ValueError(
            "chunk_fn for {} must return dict, got {}".format(chunk_id, type(result).__name__)
        )
    missing = REQUIRED_CHUNK_RESULT_KEYS - result.keys()
    if missing:
        raise ValueError(
            "chunk_fn result for {} missing required keys: {}".format(
                chunk_id, sorted(missing)
            )
        )
