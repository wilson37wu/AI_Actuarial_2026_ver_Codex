"""
Phase 11 Task 2: grouping, chunking, checkpoint restart, failed-chunk audit,
and reconciliation for the 100,000-policy HK PAR educational portfolio.

This module sits on top of the Phase 11 Task 1 portfolio generator and provides
the *control-plane* infrastructure for a realistic actuarial reporting cycle:

* **Grouping** – partition the policy table into actuarial groups (product line ×
  age band × policy term) so that modelling teams can reason about sub-portfolios
  and track group-level movements independently.

* **Chunking** – split the ordered portfolio into fixed-size processing chunks
  that can be executed independently (sequentially or in parallel) without
  holding the entire 100k row table in memory at every step.

* **Checkpoint / restart** – persist each chunk's status to a JSON checkpoint
  file after it completes or fails.  A restarted run reads the checkpoint, skips
  DONE chunks, and retries only PENDING or previously FAILED chunks.
  Reproducibility and traceability requirements per SOA ASOP 56 §3.2 and
  IA TAS M §3.6.

* **Failed-chunk audit** – for every chunk that raises an exception, record the
  chunk index, error class, error message, and stack trace in a structured audit
  entry.  The audit log is consumable by the Phase 11 Task 3 reporting pack.

* **Reconciliation** – after all chunks have been attempted, verify that combined
  record counts and key financial control totals (sum assured, annual premium,
  initial vested bonus) reconcile back to source portfolio totals within a stated
  absolute tolerance.  Emit a structured reconciliation report with per-total
  pass/fail status and any out-of-tolerance exceptions.

Limitations
-----------
This module is an educational reference for actuarial model governance concepts.
The checkpoint store writes plain JSON to the local filesystem; production
implementations would use a database or cloud-native state store with
transactional guarantees.  The processing functions passed to ``ChunkedProcessor``
are caller-supplied; the module provides stub helpers for illustration only.
All financial totals are nominal (undiscounted) running sums; they are not
suitable for valuation or reporting without further calculation.

SOA / IA / ERM standards references
-------------------------------------
- SOA ASOP 56 §3.2: Model testing, reproducibility, and restart evidence.
- SOA ESG guidance §4: Scenario / run metadata and audit trail.
- IA TAS M §3.5–3.6: Traceability from assumption source to output, model
  version, parameter snapshot, and run metadata.
- ERM: Reconciliation controls and exception handling for model output sign-off.
"""

from __future__ import annotations

import enum
import json
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import numpy as np
import pandas as pd

from par_model_v2.projection.portfolio_generator import (
    PRODUCT_LINE_CASH,
    PRODUCT_LINE_RB,
    UNIFIED_COLUMNS,
    iter_policy_chunks,
    portfolio_summary,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Age-band boundaries (right-exclusive) used for grouping keys.
AGE_BANDS: Tuple[Tuple[int, int, str], ...] = (
    (0,  30, "18-29"),
    (30, 40, "30-39"),
    (40, 50, "40-49"),
    (50, 60, "50-59"),
    (60, 999, "60+"),
)

#: Financial columns tracked for reconciliation control totals.
RECONCILE_COLS: Tuple[str, ...] = (
    "sum_assured",
    "annual_premium",
    "initial_vested_bonus",
)

_CHUNK_PROCESSOR_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def _age_band_label(age: int) -> str:
    """Map an integer issue age to its age-band label."""
    for lo, hi, label in AGE_BANDS:
        if lo <= age < hi:
            return label
    return "unknown"


@dataclass(frozen=True)
class GroupKey:
    """Immutable key that identifies an actuarial group.

    Groups are defined by the Cartesian product of product line, age band, and
    policy term.  This granularity supports group-level movement analysis and
    allows independent model runs per group where needed.
    """

    product_line: str
    age_band: str
    term_years: int

    def to_dict(self) -> Dict[str, Any]:
        return {"product_line": self.product_line, "age_band": self.age_band, "term_years": self.term_years}

    def to_label(self) -> str:
        return f"{self.product_line}|{self.age_band}|T{self.term_years}"


@dataclass
class PolicyGroup:
    """A named sub-portfolio defined by a :class:`GroupKey`.

    Attributes
    ----------
    key:
        Immutable group identifier.
    policies:
        Slice of the unified portfolio table containing only the policies that
        belong to this group (original column set preserved).
    group_summary:
        Headline statistics for the group (same structure as
        :func:`portfolio_summary`).
    source_id:
        Traceability tag copied from the portfolio source for audit
        reconstruction.
    """

    key: GroupKey
    policies: pd.DataFrame
    group_summary: Dict[str, Any]
    source_id: str = "PHASE11-T2-GROUP"

    @property
    def n_policies(self) -> int:
        return len(self.policies)

    def control_totals(self) -> Dict[str, float]:
        """Return financial control totals for reconciliation."""
        return {col: float(self.policies[col].sum()) for col in RECONCILE_COLS}


def build_policy_groups(
    table: pd.DataFrame,
    *,
    source_id: str = "PHASE11-T2-GROUP",
) -> Dict[str, PolicyGroup]:
    """Partition the portfolio into actuarial groups keyed by product line,
    age band, and policy term.

    Parameters
    ----------
    table:
        Unified portfolio table (must include all :data:`UNIFIED_COLUMNS`).
    source_id:
        Traceability tag to embed in each group for audit reconstruction.

    Returns
    -------
    dict
        Mapping from :meth:`GroupKey.to_label` strings to :class:`PolicyGroup`
        instances.  Keys are sorted for deterministic iteration order.
    """
    missing = sorted(set(UNIFIED_COLUMNS).difference(table.columns))
    if missing:
        raise ValueError(f"portfolio missing required columns: {', '.join(missing)}")

    age_band_col = table["issue_age"].map(_age_band_label)
    groups: Dict[str, PolicyGroup] = {}

    for (product_line, age_band, term_years), sub in table.groupby(
        [table["product_line"], age_band_col, table["term_years"]],
        sort=True,
    ):
        key = GroupKey(
            product_line=str(product_line),
            age_band=str(age_band),
            term_years=int(term_years),
        )
        sub_reset = sub.reset_index(drop=True)
        summary = portfolio_summary(sub_reset)
        group = PolicyGroup(
            key=key,
            policies=sub_reset,
            group_summary=summary,
            source_id=source_id,
        )
        groups[key.to_label()] = group

    return dict(sorted(groups.items()))


def group_summary_table(groups: Dict[str, PolicyGroup]) -> pd.DataFrame:
    """Return a summary DataFrame with one row per group.

    Columns: ``group_label``, ``product_line``, ``age_band``, ``term_years``,
    ``n_policies``, ``sum_assured``, ``annual_premium``, ``initial_vested_bonus``.
    """
    rows = []
    for label, g in groups.items():
        totals = g.control_totals()
        rows.append(
            {
                "group_label": label,
                **g.key.to_dict(),
                "n_policies": g.n_policies,
                **totals,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Chunk status and checkpoint
# ---------------------------------------------------------------------------

class ChunkStatus(str, enum.Enum):
    """Processing state for a single chunk."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class ChunkRecord:
    """State record for one processing chunk.

    Attributes
    ----------
    chunk_index:
        Zero-based ordinal position in the ordered chunk sequence.
    start_row:
        First row index (inclusive) of this chunk within the portfolio table.
    end_row:
        Last row index (exclusive) of this chunk.
    n_rows:
        Number of policy rows in the chunk (``end_row - start_row``).
    status:
        Current :class:`ChunkStatus`.
    run_id:
        UUID assigned when processing begins; ``None`` while PENDING.
    started_at:
        ISO-8601 UTC timestamp when processing began; ``None`` while PENDING.
    completed_at:
        ISO-8601 UTC timestamp when processing finished (DONE or FAILED);
        ``None`` while PENDING or RUNNING.
    control_totals:
        Financial totals for the rows in this chunk (populated once processed).
    error_class:
        Exception class name if status is FAILED; ``None`` otherwise.
    error_message:
        Exception message if status is FAILED; ``None`` otherwise.
    """

    chunk_index: int
    start_row: int
    end_row: int
    n_rows: int
    status: ChunkStatus = ChunkStatus.PENDING
    run_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    control_totals: Dict[str, float] = field(default_factory=dict)
    error_class: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChunkRecord":
        d = dict(d)
        d["status"] = ChunkStatus(d["status"])
        return cls(**d)


class CheckpointStore:
    """Persist and reload chunk processing state for restart capability.

    The checkpoint is a JSON file at ``path`` with the following top-level
    structure::

        {
            "version": "1.0.0",
            "run_id": "<uuid>",
            "created_at": "<ISO-8601>",
            "updated_at": "<ISO-8601>",
            "portfolio_digest": "<sha256>",
            "chunk_size": <int>,
            "chunks": [ {<ChunkRecord.to_dict()>}, ... ]
        }

    Parameters
    ----------
    path:
        Filesystem path to the checkpoint JSON file.
    portfolio_digest:
        SHA-256 digest of the portfolio that was checkpointed; used to detect
        if the portfolio has changed between a run and its restart.
    chunk_size:
        Chunk size used when the checkpoint was created.
    """

    def __init__(
        self,
        path: Path | str,
        *,
        portfolio_digest: str = "",
        chunk_size: int = 10_000,
    ) -> None:
        self.path = Path(path)
        self.portfolio_digest = portfolio_digest
        self.chunk_size = chunk_size
        self._run_id: str = str(uuid.uuid4())
        self._created_at: str = _now_utc()

    # ------------------------------------------------------------------
    # Initialise from portfolio
    # ------------------------------------------------------------------

    def initialise(self, table: pd.DataFrame) -> List[ChunkRecord]:
        """Build an initial checkpoint from the portfolio table.

        Creates :class:`ChunkRecord` instances for every chunk, all with
        ``status=PENDING``, and writes them to :attr:`path`.

        Returns the list of :class:`ChunkRecord` instances.
        """
        records: List[ChunkRecord] = []
        idx = 0
        start = 0
        for chunk in iter_policy_chunks(table, chunk_size=self.chunk_size):
            n = len(chunk)
            records.append(
                ChunkRecord(
                    chunk_index=idx,
                    start_row=start,
                    end_row=start + n,
                    n_rows=n,
                )
            )
            start += n
            idx += 1
        self._write(records)
        return records

    # ------------------------------------------------------------------
    # Load existing checkpoint
    # ------------------------------------------------------------------

    def load(self) -> Tuple[List[ChunkRecord], Dict[str, Any]]:
        """Load checkpoint state from disk.

        Returns ``(records, metadata)`` where ``metadata`` is the top-level
        JSON dict excluding the ``chunks`` key.

        Raises :class:`FileNotFoundError` if the checkpoint file does not exist,
        and :class:`ValueError` if the stored portfolio digest does not match
        :attr:`portfolio_digest` (when both are non-empty).
        """
        if not self.path.exists():
            raise FileNotFoundError(f"checkpoint not found: {self.path}")
        with self.path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        stored_digest = data.get("portfolio_digest", "")
        if self.portfolio_digest and stored_digest and stored_digest != self.portfolio_digest:
            raise ValueError(
                f"portfolio digest mismatch: checkpoint has {stored_digest!r}, "
                f"current portfolio is {self.portfolio_digest!r}"
            )
        records = [ChunkRecord.from_dict(c) for c in data.get("chunks", [])]
        meta = {k: v for k, v in data.items() if k != "chunks"}
        # Restore run metadata so continued runs share the same top-level ID.
        self._run_id = data.get("run_id", self._run_id)
        self._created_at = data.get("created_at", self._created_at)
        return records, meta

    # ------------------------------------------------------------------
    # Update individual chunk
    # ------------------------------------------------------------------

    def update_chunk(self, records: List[ChunkRecord], idx: int) -> None:
        """Persist an updated chunk record to disk.

        Callers should mutate ``records[idx]`` then call this method so the
        checkpoint file is always up-to-date after each chunk completes or
        fails.
        """
        self._write(records)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write(self, records: List[ChunkRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _CHUNK_PROCESSOR_VERSION,
            "run_id": self._run_id,
            "created_at": self._created_at,
            "updated_at": _now_utc(),
            "portfolio_digest": self.portfolio_digest,
            "chunk_size": self.chunk_size,
            "chunks": [r.to_dict() for r in records],
        }
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)

    @property
    def run_id(self) -> str:
        return self._run_id


# ---------------------------------------------------------------------------
# Failed-chunk audit
# ---------------------------------------------------------------------------

@dataclass
class FailedChunkAuditEntry:
    """Structured audit record for one failed processing chunk.

    Fields are a superset of the information captured in the checkpoint record,
    enriched with the full stack trace for root-cause investigation.
    """

    chunk_index: int
    start_row: int
    end_row: int
    n_rows: int
    run_id: str
    attempted_at: str
    error_class: str
    error_message: str
    stack_trace: str
    limitation_id: str = "PHASE11-T2-FAIL-AUDIT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailedChunkAuditReport:
    """Collection of :class:`FailedChunkAuditEntry` instances for a run.

    Attributes
    ----------
    run_id:
        UUID of the processing run these entries belong to.
    generated_at:
        ISO-8601 UTC timestamp when this report was produced.
    entries:
        List of failed-chunk audit entries ordered by chunk index.
    n_failed:
        Number of failed chunks (derived from :attr:`entries`).
    limitation_id:
        Model limitation tag for audit reconstruction.
    """

    run_id: str
    generated_at: str
    entries: List[FailedChunkAuditEntry] = field(default_factory=list)
    limitation_id: str = "PHASE11-T2-FAIL-AUDIT"

    @property
    def n_failed(self) -> int:
        return len(self.entries)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "n_failed": self.n_failed,
            "limitation_id": self.limitation_id,
            "entries": [e.to_dict() for e in self.entries],
        }

    def write(self, path: Path | str) -> Path:
        """Persist the audit report to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, sort_keys=True)
        return path


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

@dataclass
class ControlTotalResult:
    """Pass/fail result for a single reconciliation control total.

    Attributes
    ----------
    column:
        Financial column being reconciled (e.g. ``sum_assured``).
    source_total:
        The total from the source portfolio (ground truth).
    processed_total:
        Sum of this column across all successfully processed chunks.
    difference:
        ``processed_total - source_total``.
    tolerance:
        Absolute tolerance used for the pass/fail test.
    passed:
        ``True`` if ``|difference| <= tolerance``.
    """

    column: str
    source_total: float
    processed_total: float
    difference: float
    tolerance: float
    passed: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReconciliationReport:
    """Full reconciliation report for a chunked processing run.

    Attributes
    ----------
    run_id:
        UUID of the processing run.
    generated_at:
        ISO-8601 UTC timestamp.
    source_n_policies:
        Total policy count in the source portfolio.
    processed_n_policies:
        Total policies covered by DONE chunks.
    n_chunks_total:
        Total number of chunks in the run.
    n_chunks_done:
        Chunks that completed successfully.
    n_chunks_failed:
        Chunks that raised during processing.
    n_chunks_pending:
        Chunks that were not attempted (incomplete run).
    control_total_results:
        Per-column reconciliation results.
    overall_passed:
        ``True`` if all control totals passed and no chunks are pending or
        failed.
    exceptions:
        Human-readable list of reconciliation exceptions (empty when passing).
    limitation_id:
        Model limitation tag for audit reconstruction.
    """

    run_id: str
    generated_at: str
    source_n_policies: int
    processed_n_policies: int
    n_chunks_total: int
    n_chunks_done: int
    n_chunks_failed: int
    n_chunks_pending: int
    control_total_results: List[ControlTotalResult] = field(default_factory=list)
    overall_passed: bool = False
    exceptions: List[str] = field(default_factory=list)
    limitation_id: str = "PHASE11-T2-RECON"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["control_total_results"] = [r.to_dict() for r in self.control_total_results]
        return d

    def write(self, path: Path | str) -> Path:
        """Persist the reconciliation report to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, sort_keys=True)
        return path


def reconcile(
    source_table: pd.DataFrame,
    records: List[ChunkRecord],
    *,
    run_id: str = "",
    tolerance: float = 0.01,
) -> ReconciliationReport:
    """Build a reconciliation report comparing source totals to processed totals.

    Parameters
    ----------
    source_table:
        The original portfolio table (100k policies).
    records:
        Chunk records from the checkpoint, each carrying ``control_totals``
        populated by the processor.
    run_id:
        Processing run UUID for the report header.
    tolerance:
        Maximum absolute difference allowed for each financial control total to
        be considered passing.  Default is 0.01 (one cent in HKD nominal terms).

    Returns
    -------
    ReconciliationReport
        Structured report with per-column pass/fail and overall status.
    """
    generated_at = _now_utc()
    done = [r for r in records if r.status == ChunkStatus.DONE]
    failed = [r for r in records if r.status == ChunkStatus.FAILED]
    pending = [r for r in records if r.status == ChunkStatus.PENDING]

    source_totals = {col: float(source_table[col].sum()) for col in RECONCILE_COLS}
    processed_totals: Dict[str, float] = {col: 0.0 for col in RECONCILE_COLS}
    processed_n = 0

    for r in done:
        processed_n += r.n_rows
        for col in RECONCILE_COLS:
            processed_totals[col] += r.control_totals.get(col, 0.0)

    ctrl_results: List[ControlTotalResult] = []
    exceptions: List[str] = []
    all_totals_pass = True

    for col in RECONCILE_COLS:
        src = source_totals[col]
        proc = processed_totals[col]
        diff = proc - src
        passed = abs(diff) <= tolerance
        if not passed:
            all_totals_pass = False
            exceptions.append(
                f"{col}: |diff|={abs(diff):.4f} exceeds tolerance {tolerance:.4f} "
                f"(source={src:.2f}, processed={proc:.2f})"
            )
        ctrl_results.append(
            ControlTotalResult(
                column=col,
                source_total=src,
                processed_total=proc,
                difference=diff,
                tolerance=tolerance,
                passed=passed,
            )
        )

    if processed_n != len(source_table):
        diff_n = processed_n - len(source_table)
        exceptions.append(
            f"policy count mismatch: processed {processed_n} vs source {len(source_table)} "
            f"(difference {diff_n:+d})"
        )

    if failed:
        exceptions.append(f"{len(failed)} chunk(s) FAILED; investigate audit report before sign-off")

    if pending:
        exceptions.append(f"{len(pending)} chunk(s) still PENDING; run is incomplete")

    overall_passed = (
        all_totals_pass
        and processed_n == len(source_table)
        and not failed
        and not pending
    )

    return ReconciliationReport(
        run_id=run_id,
        generated_at=generated_at,
        source_n_policies=len(source_table),
        processed_n_policies=processed_n,
        n_chunks_total=len(records),
        n_chunks_done=len(done),
        n_chunks_failed=len(failed),
        n_chunks_pending=len(pending),
        control_total_results=ctrl_results,
        overall_passed=overall_passed,
        exceptions=exceptions,
    )


# ---------------------------------------------------------------------------
# Chunked processor
# ---------------------------------------------------------------------------

def _default_chunk_fn(chunk: pd.DataFrame) -> Dict[str, float]:
    """Stub processor: return financial control totals without any modelling.

    Replace with a real model runner (e.g. liability projection, TVOG
    computation) in production.  The return value must be a dict mapping
    column names (matching :data:`RECONCILE_COLS`) to their float totals for
    this chunk.
    """
    return {col: float(chunk[col].sum()) for col in RECONCILE_COLS}


@dataclass
class ChunkedProcessorConfig:
    """Configuration for :class:`ChunkedProcessor`.

    Attributes
    ----------
    chunk_size:
        Number of policies per chunk (default 10,000).
    checkpoint_path:
        Filesystem path for the checkpoint JSON.  Created on first run and
        read on subsequent restarts.
    audit_path:
        Filesystem path for the failed-chunk audit JSON.
    reconciliation_path:
        Filesystem path for the reconciliation report JSON.
    tolerance:
        Absolute reconciliation tolerance per financial column.
    retry_failed:
        If ``True``, previously FAILED chunks are retried on restart.
        If ``False``, FAILED chunks are skipped on restart and remain in the
        audit log.
    source_id:
        Traceability tag embedded in run metadata.
    """

    chunk_size: int = 10_000
    checkpoint_path: Path = Path("outputs/phase11_checkpoint.json")
    audit_path: Path = Path("outputs/phase11_failed_audit.json")
    reconciliation_path: Path = Path("outputs/phase11_reconciliation.json")
    tolerance: float = 0.01
    retry_failed: bool = True
    source_id: str = "PHASE11-T2"


class ChunkedProcessor:
    """Orchestrate chunked processing of the 100k HK PAR portfolio.

    Provides checkpoint / restart, failed-chunk audit, and reconciliation in a
    single cohesive workflow.

    Usage
    -----
    ::

        cfg = ChunkedProcessorConfig(checkpoint_path=Path("run/cp.json"), ...)
        processor = ChunkedProcessor(table, config=cfg)
        recon = processor.run(chunk_fn=my_model_runner)
        assert recon.overall_passed

    Parameters
    ----------
    table:
        Unified portfolio table (100k rows).
    config:
        :class:`ChunkedProcessorConfig` controlling chunk size, paths, and
        restart behaviour.
    portfolio_digest:
        SHA-256 digest of the portfolio; used to detect portfolio changes across
        restarts.  Pass ``""`` to skip digest checking.
    """

    def __init__(
        self,
        table: pd.DataFrame,
        *,
        config: Optional[ChunkedProcessorConfig] = None,
        portfolio_digest: str = "",
    ) -> None:
        self._table = table
        self._cfg = config or ChunkedProcessorConfig()
        self._store = CheckpointStore(
            self._cfg.checkpoint_path,
            portfolio_digest=portfolio_digest,
            chunk_size=self._cfg.chunk_size,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(
        self,
        chunk_fn: Optional[Callable[[pd.DataFrame], Dict[str, float]]] = None,
    ) -> ReconciliationReport:
        """Process all chunks, writing checkpoint after each one.

        Behaviour on restart (checkpoint already exists):
        - DONE chunks are skipped.
        - PENDING chunks are (re-)processed.
        - FAILED chunks are retried if ``config.retry_failed`` is True,
          otherwise skipped.

        Parameters
        ----------
        chunk_fn:
            Callable that accepts a chunk ``DataFrame`` and returns a dict of
            ``{column: total}`` for the reconciliation columns.  Defaults to
            :func:`_default_chunk_fn` (stub returning raw column sums).

        Returns
        -------
        ReconciliationReport
            Reconciliation report; always written to
            :attr:`ChunkedProcessorConfig.reconciliation_path`.
        """
        fn = chunk_fn or _default_chunk_fn

        # Load or initialise checkpoint.
        if self._cfg.checkpoint_path.exists():
            records, _meta = self._store.load()
        else:
            records = self._store.initialise(self._table)

        audit = FailedChunkAuditReport(
            run_id=self._store.run_id,
            generated_at=_now_utc(),
        )

        # Build ordered chunk list (stable iteration matching checkpoint).
        ordered = self._table.sort_values(
            ["product_line", "policy_id"], kind="mergesort"
        ).reset_index(drop=True)

        for rec in records:
            if rec.status == ChunkStatus.DONE:
                continue
            if rec.status == ChunkStatus.FAILED and not self._cfg.retry_failed:
                continue

            chunk = ordered.iloc[rec.start_row:rec.end_row].reset_index(drop=True)
            run_id = str(uuid.uuid4())
            started_at = _now_utc()

            rec.status = ChunkStatus.RUNNING
            rec.run_id = run_id
            rec.started_at = started_at
            self._store.update_chunk(records, rec.chunk_index)

            try:
                totals = fn(chunk)
                rec.status = ChunkStatus.DONE
                rec.completed_at = _now_utc()
                rec.control_totals = {col: float(totals.get(col, 0.0)) for col in RECONCILE_COLS}
                rec.error_class = None
                rec.error_message = None
            except Exception as exc:  # noqa: BLE001
                rec.status = ChunkStatus.FAILED
                rec.completed_at = _now_utc()
                rec.error_class = type(exc).__name__
                rec.error_message = str(exc)
                tb = traceback.format_exc()
                audit.entries.append(
                    FailedChunkAuditEntry(
                        chunk_index=rec.chunk_index,
                        start_row=rec.start_row,
                        end_row=rec.end_row,
                        n_rows=rec.n_rows,
                        run_id=run_id,
                        attempted_at=started_at,
                        error_class=rec.error_class,
                        error_message=rec.error_message,
                        stack_trace=tb,
                    )
                )

            self._store.update_chunk(records, rec.chunk_index)

        # Persist audit if any failures.
        if audit.n_failed > 0:
            audit.write(self._cfg.audit_path)

        # Reconcile and persist report.
        recon = reconcile(
            self._table,
            records,
            run_id=self._store.run_id,
            tolerance=self._cfg.tolerance,
        )
        recon.write(self._cfg.reconciliation_path)
        return recon

    # ------------------------------------------------------------------
    # Convenience: iterate yielding (ChunkRecord, DataFrame) for callers
    # that prefer manual processing loops.
    # ------------------------------------------------------------------

    def iter_chunks(self) -> Iterator[Tuple[ChunkRecord, pd.DataFrame]]:
        """Yield ``(record, chunk_df)`` pairs for all non-DONE chunks.

        Useful when the caller wants to drive the processing loop manually
        (e.g. for parallel dispatch) while still benefiting from the
        checkpoint and grouping infrastructure.
        """
        if self._cfg.checkpoint_path.exists():
            records, _meta = self._store.load()
        else:
            records = self._store.initialise(self._table)

        ordered = self._table.sort_values(
            ["product_line", "policy_id"], kind="mergesort"
        ).reset_index(drop=True)

        for rec in records:
            if rec.status == ChunkStatus.DONE:
                continue
            if rec.status == ChunkStatus.FAILED and not self._cfg.retry_failed:
                continue
            chunk = ordered.iloc[rec.start_row:rec.end_row].reset_index(drop=True)
            yield rec, chunk


# ---------------------------------------------------------------------------
# Run metadata helper
# ---------------------------------------------------------------------------

@dataclass
class ChunkRunMetadata:
    """Snapshot of a completed chunked processing run for model governance.

    Captures the information required by SOA ASOP 56 §3.2 and IA TAS M §3.6
    for reproducibility and audit-trail evidence.
    """

    run_id: str
    processor_version: str
    portfolio_digest: str
    chunk_size: int
    n_chunks: int
    n_done: int
    n_failed: int
    n_pending: int
    reconciliation_passed: bool
    started_at: str
    completed_at: str
    checkpoint_path: str
    audit_path: str
    reconciliation_path: str
    source_id: str = "PHASE11-T2"
    limitation_id: str = "PHASE11-T2-META"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_run_metadata(
    processor: ChunkedProcessor,
    recon: ReconciliationReport,
    *,
    started_at: str,
) -> ChunkRunMetadata:
    """Construct a :class:`ChunkRunMetadata` snapshot after a completed run."""
    cfg = processor._cfg
    return ChunkRunMetadata(
        run_id=processor._store.run_id,
        processor_version=_CHUNK_PROCESSOR_VERSION,
        portfolio_digest=processor._store.portfolio_digest,
        chunk_size=cfg.chunk_size,
        n_chunks=recon.n_chunks_total,
        n_done=recon.n_chunks_done,
        n_failed=recon.n_chunks_failed,
        n_pending=recon.n_chunks_pending,
        reconciliation_passed=recon.overall_passed,
        started_at=started_at,
        completed_at=_now_utc(),
        checkpoint_path=str(cfg.checkpoint_path),
        audit_path=str(cfg.audit_path),
        reconciliation_path=str(cfg.reconciliation_path),
        source_id=cfg.source_id,
    )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
