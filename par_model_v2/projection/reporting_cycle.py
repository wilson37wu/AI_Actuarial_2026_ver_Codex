"""
Phase 11 Task 3: actuarial reporting-cycle workflow — assumption lock, model
run, validation checks, output review, and sign-off pack.

This module orchestrates the *governance layer* of a quarterly or annual
actuarial reporting cycle for the 100,000-policy HK PAR educational portfolio.
It sits on top of the Phase 11 Task 2 chunked processor and provides the
controls that a model governance framework requires before results can be used
for reporting:

Reporting cycle stages
----------------------
1. **Assumption lock** – Snapshot all projection assumptions (mortality,
   lapse, bonus/dividend declaration, discount rate, expense loading) to an
   immutable, signed, time-stamped record.  The run is blocked until the lock
   is in place.
2. **Model run** – Invoke the chunked processor over the portfolio using the
   locked assumptions, collecting per-chunk output summaries.
3. **Validation checks** – Run a configurable suite of post-run checks
   (movement analysis, control-total reconciliation, reserve movement bounds,
   TVOG reasonableness, stochastic seed stability).
4. **Output review** – Produce a human-readable run log with the assumption
   lock reference, run metadata, chunk summary, and validation outcomes for a
   named reviewer to read and annotate.
5. **Sign-off pack** – Aggregate the above into a structured JSON/Markdown
   pack that constitutes the model governance evidence for this cycle.

All artefacts carry unique run IDs, assumption lock IDs, source IDs, and
limitation IDs so that the full assumption-to-output traceability chain required
by IA TAS M §3.6 and SOA ASOP 56 §3.2 can be reconstructed.

Limitations
-----------
This is an educational reference implementation.  Assumption values are dummy
placeholders and must not be used for live valuation.  The sign-off pack is a
local file; production deployments require a regulated workflow system with
access controls and non-repudiation evidence.  Validation thresholds are
illustrative and must be calibrated to each insurer's actual experience before
use.
"""

from __future__ import annotations

import enum
import hashlib
import json
import textwrap
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from par_model_v2.projection.chunk_processor import (
    ChunkedProcessor as ChunkedPortfolioProcessor,
    ChunkedProcessorConfig,
    ReconciliationReport,
    FailedChunkAuditReport as failed_chunk_audit_report,
)
from par_model_v2.projection.portfolio_generator import portfolio_summary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CYCLE_VERSION = "1.0.0"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short_id() -> str:
    return str(uuid.uuid4())[:8].upper()


def _sha256_dict(d: Dict[str, Any]) -> str:
    payload = json.dumps(d, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 1. Assumption lock
# ---------------------------------------------------------------------------

@dataclass
class ProjectionAssumption:
    """One named assumption entry with value, basis, source, and limitation.

    Every assumption that influences projection outputs must be registered
    before the lock is created so that the lock captures a complete snapshot.

    Attributes
    ----------
    name:
        Short machine-readable identifier (e.g. ``"qx_multiplier"``).
    label:
        Human-readable description.
    value:
        Scalar or structured value (will be serialised as JSON).
    basis:
        Methodology or experience study from which this value is derived.
    source_id:
        Reference to the assumption source document or committee minute.
    effective_date:
        Date from which this assumption applies (ISO-8601 date string).
    limitation_id:
        Limitation tag for audit reconstruction.
    """

    name: str
    label: str
    value: Any
    basis: str = "EDUCATIONAL_PLACEHOLDER"
    source_id: str = "SRC-UNKNOWN"
    effective_date: str = ""
    limitation_id: str = "PHASE11-T3-ASSUMPTION"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def default_projection_assumptions() -> List[ProjectionAssumption]:
    """Return a starter set of illustrative assumptions for the HK PAR cycle.

    These values are *not* calibrated to any real experience; they exist to
    demonstrate the governance structure only.
    """
    return [
        ProjectionAssumption(
            name="qx_multiplier",
            label="Mortality rate multiplier (A/E ratio)",
            value=1.00,
            basis="Standard mortality table (IA HKM2012) × A/E multiplier",
            source_id="SRC-MORTALITY-2026Q2",
            effective_date="2026-01-01",
        ),
        ProjectionAssumption(
            name="lapse_rate_base",
            label="Base annual lapse rate (% of in-force)",
            value=0.05,
            basis="5-year company experience study",
            source_id="SRC-LAPSE-2026Q2",
            effective_date="2026-01-01",
        ),
        ProjectionAssumption(
            name="cash_dividend_rate",
            label="Annual cash dividend rate (% of sum assured)",
            value=0.03,
            basis="Board-declared rate; Q2 2026 cycle",
            source_id="SRC-DIVDECL-2026Q2",
            effective_date="2026-04-01",
        ),
        ProjectionAssumption(
            name="reversionary_bonus_rate",
            label="Annual reversionary bonus rate (% of sum assured)",
            value=0.04,
            basis="Board-declared rate; Q2 2026 cycle",
            source_id="SRC-BONUSDECL-2026Q2",
            effective_date="2026-04-01",
        ),
        ProjectionAssumption(
            name="risk_free_rate_usd",
            label="USD risk-free rate (annual, continuous)",
            value=0.045,
            basis="USD overnight index swap curve; 2026-06-01",
            source_id="SRC-CURVE-USD-2026Q2",
            effective_date="2026-06-01",
        ),
        ProjectionAssumption(
            name="expense_loading_pct",
            label="Per-policy expense loading (% of annual premium)",
            value=0.02,
            basis="Unit-cost study 2025",
            source_id="SRC-EXPENSE-2025",
            effective_date="2026-01-01",
        ),
        ProjectionAssumption(
            name="equity_return_hk",
            label="Hong Kong equity expected annual return (log-normal mean)",
            value=0.07,
            basis="Long-run capital market assumptions; HK equity",
            source_id="SRC-EQUITY-HK-2026Q2",
            effective_date="2026-01-01",
        ),
    ]


@dataclass
class AssumptionLock:
    """Immutable time-stamped snapshot of all projection assumptions.

    Once :meth:`create` is called the assumptions list is frozen and the lock
    receives a unique ID and a SHA-256 digest of its contents.  Any downstream
    model run must record the ``lock_id`` so that results can be traced back to
    the exact assumption set that produced them.

    Attributes
    ----------
    lock_id:
        UUID for this lock (prefix ``ALK-``).
    created_at:
        ISO-8601 UTC timestamp.
    cycle_label:
        Human-readable cycle identifier (e.g. ``"Q2 2026 HK PAR"``).
    assumptions:
        Ordered list of locked :class:`ProjectionAssumption` instances.
    locked_by:
        Identifier of the person or system that created the lock.
    digest:
        SHA-256 (first 16 hex chars) of the serialised assumption set.
    limitation_id:
        Limitation tag.
    """

    lock_id: str
    created_at: str
    cycle_label: str
    assumptions: List[ProjectionAssumption]
    locked_by: str
    digest: str
    limitation_id: str = "PHASE11-T3-ASSLOCK"

    @classmethod
    def create(
        cls,
        assumptions: List[ProjectionAssumption],
        *,
        cycle_label: str = "HK PAR Educational Cycle",
        locked_by: str = "Claude Actuarial Agent",
    ) -> "AssumptionLock":
        """Build and seal an :class:`AssumptionLock` from ``assumptions``."""
        lock_id = f"ALK-{_short_id()}"
        created_at = _now()
        payload = {a.name: a.to_dict() for a in assumptions}
        digest = _sha256_dict(payload)
        return cls(
            lock_id=lock_id,
            created_at=created_at,
            cycle_label=cycle_label,
            assumptions=assumptions,
            locked_by=locked_by,
            digest=digest,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["assumptions"] = [a.to_dict() for a in self.assumptions]
        return d

    def write(self, path: Path | str) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, sort_keys=True)
        return path

    def assumption(self, name: str) -> Optional[ProjectionAssumption]:
        """Return the :class:`ProjectionAssumption` with the given ``name``, or ``None``."""
        return next((a for a in self.assumptions if a.name == name), None)


# ---------------------------------------------------------------------------
# 2. Model run record
# ---------------------------------------------------------------------------

@dataclass
class ModelRunRecord:
    """Metadata for one actuarial model run bound to an :class:`AssumptionLock`.

    Attributes
    ----------
    run_id:
        Unique run identifier (prefix ``RUN-``).
    lock_id:
        ID of the :class:`AssumptionLock` used for this run.
    cycle_label:
        Human-readable cycle label from the lock.
    started_at:
        ISO-8601 UTC timestamp when the run began.
    completed_at:
        ISO-8601 UTC timestamp when the run finished (populated after).
    n_policies:
        Number of policies processed.
    n_chunks:
        Number of chunks processed.
    n_chunks_done:
        Chunks that completed successfully.
    n_chunks_failed:
        Chunks that failed.
    portfolio_digest:
        SHA-256 of the source portfolio table.
    reconciliation_passed:
        Whether the post-run reconciliation check passed.
    output_path:
        Filesystem path to the run output file.
    source_id:
        Traceability tag.
    limitation_id:
        Model limitation tag.
    """

    run_id: str
    lock_id: str
    cycle_label: str
    started_at: str
    completed_at: str = ""
    n_policies: int = 0
    n_chunks: int = 0
    n_chunks_done: int = 0
    n_chunks_failed: int = 0
    portfolio_digest: str = ""
    reconciliation_passed: bool = False
    output_path: str = ""
    source_id: str = "PHASE11-T3-RUN"
    limitation_id: str = "PHASE11-T3-RUN"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 3. Validation checks
# ---------------------------------------------------------------------------

class ValidationStatus(str, enum.Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class ValidationCheckResult:
    """Result of one post-run validation check.

    Attributes
    ----------
    check_id:
        Short identifier (e.g. ``"V-RECON-01"``).
    check_name:
        Human-readable name.
    status:
        :class:`ValidationStatus`.
    message:
        One-line summary of the finding.
    detail:
        Extended finding detail (may be empty).
    threshold:
        The threshold value against which the metric was tested.
    observed:
        The observed metric value.
    source_id:
        Traceability tag.
    """

    check_id: str
    check_name: str
    status: ValidationStatus
    message: str
    detail: str = ""
    threshold: Optional[float] = None
    observed: Optional[float] = None
    source_id: str = "PHASE11-T3-VAL"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @property
    def passed(self) -> bool:
        return self.status in (ValidationStatus.PASS, ValidationStatus.WARN, ValidationStatus.SKIP)


@dataclass
class ValidationSuiteResult:
    """Aggregated result of the full validation suite for one run.

    Attributes
    ----------
    run_id:
        ID of the model run this suite covers.
    generated_at:
        ISO-8601 UTC timestamp.
    checks:
        Ordered list of :class:`ValidationCheckResult`.
    overall_status:
        Worst status across all checks (FAIL > WARN > SKIP > PASS).
    n_pass / n_warn / n_fail / n_skip:
        Counts by status.
    limitation_id:
        Limitation tag.
    """

    run_id: str
    generated_at: str
    checks: List[ValidationCheckResult] = field(default_factory=list)
    overall_status: ValidationStatus = ValidationStatus.PASS
    n_pass: int = 0
    n_warn: int = 0
    n_fail: int = 0
    n_skip: int = 0
    limitation_id: str = "PHASE11-T3-VAL"

    def _recompute(self) -> None:
        self.n_pass = sum(1 for c in self.checks if c.status == ValidationStatus.PASS)
        self.n_warn = sum(1 for c in self.checks if c.status == ValidationStatus.WARN)
        self.n_fail = sum(1 for c in self.checks if c.status == ValidationStatus.FAIL)
        self.n_skip = sum(1 for c in self.checks if c.status == ValidationStatus.SKIP)
        if self.n_fail:
            self.overall_status = ValidationStatus.FAIL
        elif self.n_warn:
            self.overall_status = ValidationStatus.WARN
        elif self.n_skip and not self.n_pass:
            self.overall_status = ValidationStatus.SKIP
        else:
            self.overall_status = ValidationStatus.PASS

    def to_dict(self) -> Dict[str, Any]:
        self._recompute()
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "overall_status": self.overall_status.value,
            "n_pass": self.n_pass,
            "n_warn": self.n_warn,
            "n_fail": self.n_fail,
            "n_skip": self.n_skip,
            "limitation_id": self.limitation_id,
            "checks": [c.to_dict() for c in self.checks],
        }

    def write(self, path: Path | str) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, sort_keys=True)
        return path


def run_validation_suite(
    portfolio: pd.DataFrame,
    recon: ReconciliationReport,
    run_record: ModelRunRecord,
    *,
    prior_total_sum_assured: Optional[float] = None,
    movement_tolerance_pct: float = 10.0,
    max_failed_chunk_pct: float = 5.0,
) -> ValidationSuiteResult:
    """Execute the standard post-run validation suite.

    Checks performed
    ----------------
    V-RECON-01 : Reconciliation control totals pass
    V-RECON-02 : Zero failed chunks (or within tolerance)
    V-COUNT-01 : Portfolio policy count matches expected
    V-SA-01    : Total sum assured within movement bounds vs prior period
    V-MIX-01   : Product mix within plausible bounds
    V-AGE-01   : Mean issue age within plausible bounds (30–55)
    V-PREM-01  : Premium / sum assured loading ratio plausible (0.01–0.25)
    V-TVOG-01  : Placeholder TVOG reasonableness (skipped if not run)

    Parameters
    ----------
    portfolio:
        Source portfolio DataFrame.
    recon:
        :class:`ReconciliationReport` from the chunked processor run.
    run_record:
        :class:`ModelRunRecord` for this cycle.
    prior_total_sum_assured:
        Total sum assured from the prior period.  ``None`` means the check is
        skipped (first cycle or prior not available).
    movement_tolerance_pct:
        Maximum permitted percentage movement in total sum assured between
        periods before V-SA-01 raises a FAIL.
    max_failed_chunk_pct:
        Maximum permitted percentage of failed chunks before V-RECON-02 FAILs.
    """
    checks: List[ValidationCheckResult] = []
    n = len(portfolio)

    # V-RECON-01: reconciliation control totals pass
    if recon.overall_passed:
        checks.append(ValidationCheckResult(
            check_id="V-RECON-01",
            check_name="Reconciliation control totals pass",
            status=ValidationStatus.PASS,
            message="All financial control totals reconcile within tolerance.",
        ))
    else:
        detail = "; ".join(recon.exceptions) if recon.exceptions else "see reconciliation report"
        checks.append(ValidationCheckResult(
            check_id="V-RECON-01",
            check_name="Reconciliation control totals pass",
            status=ValidationStatus.FAIL,
            message="Reconciliation FAILED — outputs must not be used for sign-off.",
            detail=detail,
        ))

    # V-RECON-02: failed chunk count within tolerance
    failed_pct = 0.0 if recon.n_chunks_total == 0 else 100.0 * recon.n_chunks_failed / recon.n_chunks_total
    if failed_pct == 0.0:
        checks.append(ValidationCheckResult(
            check_id="V-RECON-02",
            check_name="Failed chunk count within tolerance",
            status=ValidationStatus.PASS,
            message="No failed chunks.",
            threshold=max_failed_chunk_pct,
            observed=0.0,
        ))
    elif failed_pct <= max_failed_chunk_pct:
        checks.append(ValidationCheckResult(
            check_id="V-RECON-02",
            check_name="Failed chunk count within tolerance",
            status=ValidationStatus.WARN,
            message=f"{recon.n_chunks_failed} chunk(s) failed ({failed_pct:.1f}%) — within tolerance but investigate.",
            threshold=max_failed_chunk_pct,
            observed=failed_pct,
        ))
    else:
        checks.append(ValidationCheckResult(
            check_id="V-RECON-02",
            check_name="Failed chunk count within tolerance",
            status=ValidationStatus.FAIL,
            message=f"{recon.n_chunks_failed} chunk(s) failed ({failed_pct:.1f}%) — exceeds {max_failed_chunk_pct:.1f}% threshold.",
            threshold=max_failed_chunk_pct,
            observed=failed_pct,
        ))

    # V-COUNT-01: portfolio policy count matches run record
    if run_record.n_policies == n:
        checks.append(ValidationCheckResult(
            check_id="V-COUNT-01",
            check_name="Policy count matches run record",
            status=ValidationStatus.PASS,
            message=f"Policy count {n:,} matches run record.",
            observed=float(n),
        ))
    else:
        checks.append(ValidationCheckResult(
            check_id="V-COUNT-01",
            check_name="Policy count matches run record",
            status=ValidationStatus.FAIL,
            message=f"Portfolio has {n:,} policies but run record shows {run_record.n_policies:,}.",
            observed=float(n),
        ))

    # V-SA-01: total sum assured movement vs prior period
    total_sa = float(portfolio["sum_assured"].sum())
    if prior_total_sum_assured is None:
        checks.append(ValidationCheckResult(
            check_id="V-SA-01",
            check_name="Sum assured movement within bounds",
            status=ValidationStatus.SKIP,
            message="Prior period sum assured not provided — check skipped.",
            observed=total_sa,
        ))
    else:
        if prior_total_sum_assured > 0:
            movement_pct = 100.0 * abs(total_sa - prior_total_sum_assured) / prior_total_sum_assured
        else:
            movement_pct = float("inf")
        if movement_pct <= movement_tolerance_pct:
            checks.append(ValidationCheckResult(
                check_id="V-SA-01",
                check_name="Sum assured movement within bounds",
                status=ValidationStatus.PASS,
                message=f"Total SA movement {movement_pct:.2f}% is within {movement_tolerance_pct:.1f}% bound.",
                threshold=movement_tolerance_pct,
                observed=movement_pct,
            ))
        else:
            checks.append(ValidationCheckResult(
                check_id="V-SA-01",
                check_name="Sum assured movement within bounds",
                status=ValidationStatus.WARN,
                message=f"Total SA movement {movement_pct:.2f}% exceeds {movement_tolerance_pct:.1f}% — investigate.",
                threshold=movement_tolerance_pct,
                observed=movement_pct,
            ))

    # V-MIX-01: cash/RB product mix plausible (each line 20–80%)
    lines = portfolio["product_line"].value_counts(normalize=True)
    min_share = float(lines.min())
    max_share = float(lines.max())
    if min_share >= 0.20:
        checks.append(ValidationCheckResult(
            check_id="V-MIX-01",
            check_name="Product mix within plausible bounds (20–80% per line)",
            status=ValidationStatus.PASS,
            message=f"Smallest line has {min_share*100:.1f}% share — plausible.",
            observed=min_share,
        ))
    else:
        checks.append(ValidationCheckResult(
            check_id="V-MIX-01",
            check_name="Product mix within plausible bounds (20–80% per line)",
            status=ValidationStatus.WARN,
            message=f"Smallest line has {min_share*100:.1f}% share — verify portfolio composition.",
            observed=min_share,
        ))

    # V-AGE-01: mean issue age 30–55
    mean_age = float(portfolio["issue_age"].mean())
    if 30.0 <= mean_age <= 55.0:
        checks.append(ValidationCheckResult(
            check_id="V-AGE-01",
            check_name="Mean issue age within plausible range (30–55)",
            status=ValidationStatus.PASS,
            message=f"Mean issue age {mean_age:.1f} is within [30, 55].",
            threshold=None,
            observed=mean_age,
        ))
    else:
        checks.append(ValidationCheckResult(
            check_id="V-AGE-01",
            check_name="Mean issue age within plausible range (30–55)",
            status=ValidationStatus.WARN,
            message=f"Mean issue age {mean_age:.1f} is outside [30, 55] — verify portfolio.",
            observed=mean_age,
        ))

    # V-PREM-01: premium/SA loading ratio plausible (1–25%)
    total_sa_v = float(portfolio["sum_assured"].sum())
    total_prem = float(portfolio["annual_premium"].sum())
    loading_ratio = total_prem / total_sa_v if total_sa_v > 0 else 0.0
    if 0.01 <= loading_ratio <= 0.25:
        checks.append(ValidationCheckResult(
            check_id="V-PREM-01",
            check_name="Premium / sum assured loading ratio plausible (1–25%)",
            status=ValidationStatus.PASS,
            message=f"Aggregate loading ratio {loading_ratio*100:.2f}% is within [1%, 25%].",
            observed=loading_ratio,
        ))
    else:
        checks.append(ValidationCheckResult(
            check_id="V-PREM-01",
            check_name="Premium / sum assured loading ratio plausible (1–25%)",
            status=ValidationStatus.WARN,
            message=f"Aggregate loading ratio {loading_ratio*100:.2f}% is outside [1%, 25%] — check premium basis.",
            observed=loading_ratio,
        ))

    # V-TVOG-01: TVOG placeholder (skipped in Phase 11; covered in Phase 4)
    checks.append(ValidationCheckResult(
        check_id="V-TVOG-01",
        check_name="TVOG reasonableness (placeholder)",
        status=ValidationStatus.SKIP,
        message="TVOG validation skipped in Phase 11 educational cycle — see Phase 4 TVOGEngine.",
    ))

    result = ValidationSuiteResult(
        run_id=run_record.run_id,
        generated_at=_now(),
        checks=checks,
    )
    result._recompute()
    return result


# ---------------------------------------------------------------------------
# 4. Output review
# ---------------------------------------------------------------------------

@dataclass
class OutputReviewRecord:
    """Summary record for the output-review stage.

    Populated by the :func:`build_output_review` helper and presented to a
    named reviewer before the sign-off pack is produced.

    Attributes
    ----------
    review_id:
        Unique identifier (prefix ``REV-``).
    run_id:
        Model run this review covers.
    lock_id:
        Assumption lock tied to this run.
    generated_at:
        ISO-8601 UTC timestamp when the review record was produced.
    reviewer:
        Name or identifier of the designated reviewer.
    portfolio_headline:
        Key portfolio statistics (from :func:`portfolio_summary`).
    validation_summary:
        Short summary of validation outcomes.
    open_issues:
        List of human-readable open items requiring reviewer attention.
    reviewer_notes:
        Free-text notes added by the reviewer (empty until annotated).
    approved:
        ``True`` once the reviewer approves the outputs.
    approved_at:
        ISO-8601 UTC timestamp of approval.
    limitation_id:
        Limitation tag.
    """

    review_id: str
    run_id: str
    lock_id: str
    generated_at: str
    reviewer: str
    portfolio_headline: Dict[str, Any]
    validation_summary: Dict[str, Any]
    open_issues: List[str] = field(default_factory=list)
    reviewer_notes: str = ""
    approved: bool = False
    approved_at: str = ""
    limitation_id: str = "PHASE11-T3-REVIEW"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def write(self, path: Path | str) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, sort_keys=True)
        return path

    def approve(self, *, reviewer_notes: str = "") -> "OutputReviewRecord":
        """Return a copy of this record with ``approved=True``."""
        return OutputReviewRecord(
            **{
                **asdict(self),
                "approved": True,
                "approved_at": _now(),
                "reviewer_notes": reviewer_notes or self.reviewer_notes,
            }
        )


def build_output_review(
    portfolio: pd.DataFrame,
    lock: AssumptionLock,
    run_record: ModelRunRecord,
    validation: ValidationSuiteResult,
    *,
    reviewer: str = "Appointed Actuary",
) -> OutputReviewRecord:
    """Produce an :class:`OutputReviewRecord` for the cycle."""
    review_id = f"REV-{_short_id()}"
    headline = portfolio_summary(portfolio)
    val_summary = {
        "overall_status": validation.overall_status.value,
        "n_pass": validation.n_pass,
        "n_warn": validation.n_warn,
        "n_fail": validation.n_fail,
        "n_skip": validation.n_skip,
    }
    open_issues: List[str] = []
    for c in validation.checks:
        if c.status in (ValidationStatus.FAIL, ValidationStatus.WARN):
            open_issues.append(f"[{c.check_id}] {c.status.value}: {c.message}")
    if not run_record.reconciliation_passed:
        open_issues.insert(0, "RECONCILIATION FAILED — outputs blocked for sign-off until resolved.")
    return OutputReviewRecord(
        review_id=review_id,
        run_id=run_record.run_id,
        lock_id=lock.lock_id,
        generated_at=_now(),
        reviewer=reviewer,
        portfolio_headline=headline,
        validation_summary=val_summary,
        open_issues=open_issues,
    )


# ---------------------------------------------------------------------------
# 5. Sign-off pack
# ---------------------------------------------------------------------------

@dataclass
class SignOffPack:
    """Consolidated model governance evidence pack for one reporting cycle.

    The sign-off pack aggregates the assumption lock, run record, validation
    suite result, and output review into a single traceable artefact that
    satisfies the governance evidence requirements of:

    - SOA ASOP 56 §3.2 (reproducibility and testing evidence)
    - IA TAS M §3.5–3.6 (traceability from assumption source to output,
      model version, parameter snapshot, run metadata)
    - ERM sign-off controls for model output review and exception handling

    Attributes
    ----------
    pack_id:
        Unique identifier (prefix ``PACK-``).
    cycle_label:
        Human-readable cycle label.
    generated_at:
        ISO-8601 UTC timestamp.
    lock:
        Sealed :class:`AssumptionLock`.
    run_record:
        :class:`ModelRunRecord`.
    validation:
        :class:`ValidationSuiteResult`.
    review:
        :class:`OutputReviewRecord` (must have ``approved=True`` for
        :attr:`governance_cleared` to be ``True``).
    governance_cleared:
        ``True`` if all of the following hold:
        - reconciliation passed
        - no FAIL validation checks
        - review is approved
    blockers:
        Human-readable list of reasons governance is not cleared.
    version:
        Processor version for the reporting cycle module.
    limitation_id:
        Limitation tag.
    """

    pack_id: str
    cycle_label: str
    generated_at: str
    lock: AssumptionLock
    run_record: ModelRunRecord
    validation: ValidationSuiteResult
    review: OutputReviewRecord
    governance_cleared: bool = False
    blockers: List[str] = field(default_factory=list)
    version: str = _CYCLE_VERSION
    limitation_id: str = "PHASE11-T3-SIGNOFF"

    @classmethod
    def build(
        cls,
        lock: AssumptionLock,
        run_record: ModelRunRecord,
        validation: ValidationSuiteResult,
        review: OutputReviewRecord,
    ) -> "SignOffPack":
        """Assemble the pack and compute governance clearance status."""
        pack_id = f"PACK-{_short_id()}"
        blockers: List[str] = []
        if not run_record.reconciliation_passed:
            blockers.append("Reconciliation control totals did not pass.")
        if validation.overall_status == ValidationStatus.FAIL:
            failed = [c.check_id for c in validation.checks if c.status == ValidationStatus.FAIL]
            blockers.append(f"Validation check(s) FAILED: {', '.join(failed)}")
        if not review.approved:
            blockers.append("Output review not yet approved by designated reviewer.")
        return cls(
            pack_id=pack_id,
            cycle_label=lock.cycle_label,
            generated_at=_now(),
            lock=lock,
            run_record=run_record,
            validation=validation,
            review=review,
            governance_cleared=len(blockers) == 0,
            blockers=blockers,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "cycle_label": self.cycle_label,
            "generated_at": self.generated_at,
            "version": self.version,
            "governance_cleared": self.governance_cleared,
            "blockers": self.blockers,
            "limitation_id": self.limitation_id,
            "lock": self.lock.to_dict(),
            "run_record": self.run_record.to_dict(),
            "validation": self.validation.to_dict(),
            "review": self.review.to_dict(),
        }

    def write_json(self, path: Path | str) -> Path:
        """Write the full pack as JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, sort_keys=True)
        return path

    def write_markdown(self, path: Path | str) -> Path:
        """Write a human-readable Markdown summary of the sign-off pack."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        cleared_str = "✅ CLEARED" if self.governance_cleared else "❌ NOT CLEARED"
        lines = [
            f"# Sign-Off Pack: {self.cycle_label}",
            f"",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Pack ID | `{self.pack_id}` |",
            f"| Cycle | {self.cycle_label} |",
            f"| Generated | {self.generated_at} |",
            f"| Module version | {self.version} |",
            f"| **Governance status** | **{cleared_str}** |",
            f"",
        ]
        if self.blockers:
            lines.append("## Blockers")
            for b in self.blockers:
                lines.append(f"- {b}")
            lines.append("")

        lines += [
            "## Assumption Lock",
            f"- Lock ID: `{self.lock.lock_id}`",
            f"- Created: {self.lock.created_at}",
            f"- Locked by: {self.lock.locked_by}",
            f"- Digest: `{self.lock.digest}`",
            f"- Assumptions: {len(self.lock.assumptions)} locked",
            "",
            "## Model Run",
            f"- Run ID: `{self.run_record.run_id}`",
            f"- Started: {self.run_record.started_at}",
            f"- Completed: {self.run_record.completed_at}",
            f"- Policies: {self.run_record.n_policies:,}",
            f"- Chunks done / failed: {self.run_record.n_chunks_done} / {self.run_record.n_chunks_failed}",
            f"- Reconciliation: {'PASSED' if self.run_record.reconciliation_passed else 'FAILED'}",
            "",
            "## Validation",
            f"- Overall status: **{self.validation.overall_status.value}**",
            f"- Checks: {self.validation.n_pass} PASS, {self.validation.n_warn} WARN, "
            f"{self.validation.n_fail} FAIL, {self.validation.n_skip} SKIP",
            "",
        ]
        for c in self.validation.checks:
            status_icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭️"}.get(c.status.value, "?")
            lines.append(f"- {status_icon} `{c.check_id}` {c.check_name}: {c.message}")
        lines.append("")

        lines += [
            "## Output Review",
            f"- Review ID: `{self.review.review_id}`",
            f"- Reviewer: {self.review.reviewer}",
            f"- Approved: {'Yes (' + self.review.approved_at + ')' if self.review.approved else 'No'}",
        ]
        if self.review.open_issues:
            lines.append("- Open issues:")
            for issue in self.review.open_issues:
                lines.append(f"  - {issue}")
        if self.review.reviewer_notes:
            lines.append(f"- Notes: {self.review.reviewer_notes}")
        lines.append("")

        lines += [
            "---",
            f"*Generated by Claude Actuarial Agent — Phase 11 Task 3 Reporting Cycle v{self.version}.*",
            f"*Educational use only. Not cleared for production insurance valuation.*",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path


# ---------------------------------------------------------------------------
# 6. Orchestration: full reporting cycle
# ---------------------------------------------------------------------------

@dataclass
class ReportingCycleConfig:
    """Configuration for a full actuarial reporting cycle run.

    Attributes
    ----------
    output_dir:
        Directory for all cycle output files.
    cycle_label:
        Human-readable cycle label (e.g. ``"Q2 2026 HK PAR"``).
    locked_by:
        Name or ID of the actuary locking the assumptions.
    reviewer:
        Name or ID of the designated output reviewer.
    chunk_size:
        Number of policies per processing chunk.
    auto_approve:
        If ``True``, the review is auto-approved (useful for automated
        regression testing).  Set to ``False`` in production.
    prior_total_sum_assured:
        Prior-period total SA for movement validation.  ``None`` to skip.
    movement_tolerance_pct:
        Maximum permitted % movement in total SA (default 10%).
    max_failed_chunk_pct:
        Maximum permitted % of failed chunks (default 5%).
    source_id:
        Traceability tag.
    """

    output_dir: Path = Path("outputs/reporting_cycle")
    cycle_label: str = "HK PAR Educational Cycle"
    locked_by: str = "Claude Actuarial Agent"
    reviewer: str = "Appointed Actuary"
    chunk_size: int = 10_000
    auto_approve: bool = True
    prior_total_sum_assured: Optional[float] = None
    movement_tolerance_pct: float = 10.0
    max_failed_chunk_pct: float = 5.0
    source_id: str = "PHASE11-T3"


def run_reporting_cycle(
    portfolio: pd.DataFrame,
    assumptions: Optional[List[ProjectionAssumption]] = None,
    chunk_fn: Optional[Callable[[pd.DataFrame, str], Dict[str, Any]]] = None,
    config: Optional[ReportingCycleConfig] = None,
) -> SignOffPack:
    """Execute the full five-stage actuarial reporting cycle.

    Stages
    ------
    1. Lock assumptions.
    2. Run the chunked portfolio processor.
    3. Run the validation suite.
    4. Build the output review (optionally auto-approve).
    5. Build and write the sign-off pack (JSON + Markdown).

    Parameters
    ----------
    portfolio:
        Unified policy table (100k rows).
    assumptions:
        List of :class:`ProjectionAssumption` to lock; defaults to
        :func:`default_projection_assumptions`.
    chunk_fn:
        Processing function for each chunk; signature
        ``(chunk_df, chunk_id) -> dict``.  Defaults to the stub in
        :mod:`chunked_processor`.
    config:
        :class:`ReportingCycleConfig`.

    Returns
    -------
    SignOffPack
        The assembled sign-off pack.
    """
    cfg = config or ReportingCycleConfig()
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    started_at = _now()

    # --- Stage 1: Assumption lock ----------------------------------------
    if assumptions is None:
        assumptions = default_projection_assumptions()
    lock = AssumptionLock.create(
        assumptions,
        cycle_label=cfg.cycle_label,
        locked_by=cfg.locked_by,
    )
    lock.write(cfg.output_dir / "assumption_lock.json")

    # --- Stage 2: Model run via chunked processor ------------------------
    run_id = f"RUN-{_short_id()}"
    _proc_cfg = ChunkedProcessorConfig(
        chunk_size=cfg.chunk_size,
        checkpoint_path=cfg.output_dir / "checkpoint.json",
        audit_path=cfg.output_dir / "failed_chunk_audit.json",
    )
    processor = ChunkedPortfolioProcessor(portfolio, config=_proc_cfg)
    recon: ReconciliationReport = processor.run(chunk_fn=chunk_fn)

    run_record = ModelRunRecord(
        run_id=run_id,
        lock_id=lock.lock_id,
        cycle_label=lock.cycle_label,
        started_at=started_at,
        completed_at=_now(),
        n_policies=len(portfolio),
        n_chunks=recon.n_chunks_total,
        n_chunks_done=recon.n_chunks_done,
        n_chunks_failed=recon.n_chunks_failed,
        portfolio_digest=getattr(recon, "portfolio_digest", ""),
        reconciliation_passed=recon.overall_passed,
        output_path=str(cfg.output_dir / "checkpoint.json"),
    )
    run_record_path = cfg.output_dir / "run_record.json"
    run_record_path.write_text(
        json.dumps(run_record.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    # --- Stage 3: Validation checks -------------------------------------
    validation = run_validation_suite(
        portfolio,
        recon,
        run_record,
        prior_total_sum_assured=cfg.prior_total_sum_assured,
        movement_tolerance_pct=cfg.movement_tolerance_pct,
        max_failed_chunk_pct=cfg.max_failed_chunk_pct,
    )
    validation.write(cfg.output_dir / "validation_suite.json")

    # --- Stage 4: Output review -----------------------------------------
    review = build_output_review(
        portfolio,
        lock,
        run_record,
        validation,
        reviewer=cfg.reviewer,
    )
    if cfg.auto_approve:
        review = review.approve(reviewer_notes="Auto-approved by automated regression cycle.")
    review.write(cfg.output_dir / "output_review.json")

    # --- Stage 5: Sign-off pack -----------------------------------------
    pack = SignOffPack.build(lock, run_record, validation, review)
    pack.write_json(cfg.output_dir / "sign_off_pack.json")
    pack.write_markdown(cfg.output_dir / "sign_off_pack.md")
    return pack
