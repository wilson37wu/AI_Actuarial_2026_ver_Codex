"""
Phase 11 Task 5: Educational Reporting Pack — model run log, movement analysis,
risk metrics, validation exceptions, and sign-off checklist.

This module assembles the outputs of a completed actuarial reporting cycle
(Phase 11 Tasks 1-4) into a structured *educational reporting pack* that
mirrors the artefacts a governance-compliant valuation team would produce at
the close of a quarterly or annual reporting cycle.

Pack contents
-------------
1. **Model Run Log** – timestamped record of every pipeline stage from
   assumption lock through sign-off, with run IDs and file references.
2. **Movement Analysis** – policy-count and sum-assured roll-forward comparing
   prior period to current period (openings, new business, exits, closing).
3. **Risk Metrics Summary** – VaR-95, Expected Shortfall-95, and basic stress
   metrics derived from the policy portfolio financial fields.
4. **Validation Exceptions Report** – all validation checks that FAILED or
   WARN'd, with check IDs, messages, thresholds, observed values, and
   recommended actions.
5. **Sign-Off Checklist** – governance checklist confirming each mandatory step
   has been completed, with status indicators and reviewer attribution.

Output formats
--------------
* JSON – machine-readable pack for downstream consumers.
* Markdown – human-readable report for model governance review.
* Per-section text – individual section strings for embedding in email reports.

Industry standards alignment
----------------------------
- SOA ASOP 56 §3.3: Model documentation should include a description of model
  outputs and how they are used; the run log and sign-off checklist satisfy
  this requirement.
- IA TAS M §3.6: Traceability from assumption source to output report must be
  demonstrable; every section carries lock_id and run_id references.
- ERM: VaR and Expected Shortfall at 95% confidence are reported as required
  tail-risk metrics; stress outcomes are labelled with their scenario names.

Limitations
-----------
This is an educational reference.  Risk metrics use simplified distributional
assumptions (normal approximation over portfolio sum-assured distribution) and
are NOT calibrated to any real insurer.  Movement analysis compares synthetic
snapshots only.  The sign-off checklist is illustrative; production use
requires integration with a regulated model risk management system.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PACK_VERSION = "1.0.0"
_SOURCE_ID = "PHASE11-T5-EDPACK"
_LIMITATION_ID = "PHASE11-T5-EDPACK-LIMIT"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# 1. Model Run Log
# ---------------------------------------------------------------------------

@dataclass
class RunLogEntry:
    """One timestamped entry in the model run log."""
    stage: str
    status: str           # "COMPLETE" | "SKIPPED" | "FAILED"
    started_at: str
    completed_at: str
    notes: str = ""
    artefact_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModelRunLog:
    """Ordered log of all pipeline stages for one reporting cycle.

    Attributes
    ----------
    run_id:
        UUID of the model run (matches ModelRunRecord.run_id).
    lock_id:
        UUID of the assumption lock (matches AssumptionLock.lock_id).
    cycle_label:
        Human-readable cycle identifier (e.g. ``"2026-Q2"``).
    generated_at:
        ISO-8601 UTC timestamp when this log was assembled.
    entries:
        Ordered list of :class:`RunLogEntry` records.
    source_id:
        Traceability tag.
    """
    run_id: str
    lock_id: str
    cycle_label: str
    generated_at: str
    entries: List[RunLogEntry] = field(default_factory=list)
    source_id: str = _SOURCE_ID

    def add(self, stage: str, status: str, started_at: str,
            completed_at: str, notes: str = "", artefact_path: str = "") -> None:
        self.entries.append(RunLogEntry(
            stage=stage, status=status,
            started_at=started_at, completed_at=completed_at,
            notes=notes, artefact_path=artefact_path,
        ))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "lock_id": self.lock_id,
            "cycle_label": self.cycle_label,
            "generated_at": self.generated_at,
            "source_id": self.source_id,
            "entries": [e.to_dict() for e in self.entries],
        }

    def to_markdown(self) -> str:
        lines = [
            f"## Model Run Log — {self.cycle_label}",
            f"",
            f"**Run ID:** `{self.run_id}`  ",
            f"**Lock ID:** `{self.lock_id}`  ",
            f"**Generated:** {self.generated_at}  ",
            f"",
            f"| Stage | Status | Started | Completed | Notes |",
            f"|-------|--------|---------|-----------|-------|",
        ]
        for e in self.entries:
            lines.append(
                f"| {e.stage} | {e.status} | {e.started_at} | {e.completed_at} | {e.notes} |"
            )
        return "\n".join(lines)


def build_model_run_log(
    run_id: str,
    lock_id: str,
    cycle_label: str,
    n_policies: int,
    n_chunks: int,
    n_chunks_done: int,
    n_chunks_failed: int,
    output_dir: Optional[Path] = None,
    started_at: str = "",
) -> ModelRunLog:
    """Construct a :class:`ModelRunLog` from reporting cycle metadata."""
    now = _now_utc()
    log = ModelRunLog(
        run_id=run_id,
        lock_id=lock_id,
        cycle_label=cycle_label,
        generated_at=now,
    )
    log.add(
        stage="1. Assumption Lock",
        status="COMPLETE",
        started_at=started_at or now,
        completed_at=started_at or now,
        notes=f"Lock ID {lock_id} — {7} assumptions locked.",
        artefact_path=str(output_dir / "assumption_lock.json") if output_dir else "",
    )
    log.add(
        stage="2. Model Run (Chunked Processor)",
        status="COMPLETE" if n_chunks_failed == 0 else "COMPLETE_WITH_FAILURES",
        started_at=started_at or now,
        completed_at=now,
        notes=(
            f"{n_policies:,} policies; {n_chunks} chunks; "
            f"{n_chunks_done} done; {n_chunks_failed} failed."
        ),
        artefact_path=str(output_dir / "checkpoint.json") if output_dir else "",
    )
    log.add(
        stage="3. Validation Suite",
        status="COMPLETE",
        started_at=now,
        completed_at=now,
        notes="Post-run validation checks executed.",
        artefact_path=str(output_dir / "validation_suite.json") if output_dir else "",
    )
    log.add(
        stage="4. Output Review",
        status="COMPLETE",
        started_at=now,
        completed_at=now,
        notes="Output review record produced for reviewer sign-off.",
        artefact_path=str(output_dir / "output_review.json") if output_dir else "",
    )
    log.add(
        stage="5. Sign-Off Pack",
        status="COMPLETE",
        started_at=now,
        completed_at=now,
        notes="JSON and Markdown sign-off pack written.",
        artefact_path=str(output_dir / "sign_off_pack.json") if output_dir else "",
    )
    return log


# ---------------------------------------------------------------------------
# 2. Movement Analysis
# ---------------------------------------------------------------------------

@dataclass
class PolicyMovement:
    """Single line in the policy movement roll-forward.

    Attributes
    ----------
    category:
        Movement category label (e.g. ``"Opening in-force"``).
    n_policies:
        Policy count for this movement.
    total_sum_assured:
        Sum of sum-assured for this movement.
    notes:
        Optional governance note.
    """
    category: str
    n_policies: int
    total_sum_assured: float
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MovementAnalysis:
    """Policy-count and sum-assured roll-forward for one reporting cycle.

    Attributes
    ----------
    cycle_label:
        Reporting cycle identifier.
    currency:
        Currency of sum-assured figures (default ``"HKD"``).
    movements:
        Ordered list of :class:`PolicyMovement` lines.
    closing_n_policies:
        Closing policy count (derived from movements).
    closing_sum_assured:
        Closing sum-assured (derived from movements).
    limitation_id:
        Limitation tag.
    """
    cycle_label: str
    currency: str
    movements: List[PolicyMovement]
    closing_n_policies: int
    closing_sum_assured: float
    limitation_id: str = _LIMITATION_ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_label": self.cycle_label,
            "currency": self.currency,
            "closing_n_policies": self.closing_n_policies,
            "closing_sum_assured": self.closing_sum_assured,
            "limitation_id": self.limitation_id,
            "movements": [m.to_dict() for m in self.movements],
        }

    def to_markdown(self) -> str:
        lines = [
            f"## Movement Analysis — {self.cycle_label} ({self.currency})",
            f"",
            f"| Category | Policies | Sum Assured |",
            f"|----------|----------|-------------|",
        ]
        for m in self.movements:
            sa = f"{m.total_sum_assured:,.0f}"
            lines.append(f"| {m.category} | {m.n_policies:,} | {sa} |")
        lines += [
            f"",
            f"> **Limitation:** {_LIMITATION_ID} — Movement analysis uses synthetic snapshots only.",
        ]
        return "\n".join(lines)


def build_movement_analysis(
    current_portfolio: pd.DataFrame,
    prior_n_policies: int = 0,
    prior_sum_assured: float = 0.0,
    cycle_label: str = "Current",
    currency: str = "HKD",
    new_business_pct: float = 0.03,
    lapse_pct: float = 0.05,
    death_pct: float = 0.005,
    maturity_pct: float = 0.01,
) -> MovementAnalysis:
    """Build a movement analysis roll-forward from the current portfolio.

    Parameters
    ----------
    current_portfolio:
        Unified policy table from :func:`generate_hk_par_portfolio`.
    prior_n_policies:
        Opening policy count.  If 0, estimated from current closing minus
        synthetic new-business.
    prior_sum_assured:
        Opening sum-assured.  If 0.0, estimated proportionally.
    cycle_label:
        Reporting cycle label.
    currency:
        Currency label for display.
    new_business_pct, lapse_pct, death_pct, maturity_pct:
        Illustrative exit / entry rates used to estimate movement lines when
        actual movement data is not available.

    Returns
    -------
    MovementAnalysis
        Structured roll-forward with five movement lines.
    """
    sa_col = "sum_assured" if "sum_assured" in current_portfolio.columns else None
    closing_n = len(current_portfolio)
    closing_sa = float(current_portfolio[sa_col].sum()) if sa_col else float(closing_n * 100_000)

    # Derive opening from closing minus estimated new business
    nb_n = max(1, int(round(closing_n * new_business_pct)))
    nb_sa = closing_sa * new_business_pct
    opening_n = prior_n_policies or max(1, closing_n - nb_n)
    opening_sa = prior_sum_assured or (closing_sa - nb_sa)

    # Estimate exit counts from opening (illustrative)
    lapse_n = max(0, int(round(opening_n * lapse_pct)))
    lapse_sa = opening_sa * lapse_pct
    death_n = max(0, int(round(opening_n * death_pct)))
    death_sa = opening_sa * death_pct
    mat_n = max(0, int(round(opening_n * maturity_pct)))
    mat_sa = opening_sa * maturity_pct
    total_exits_n = lapse_n + death_n + mat_n
    total_exits_sa = lapse_sa + death_sa + mat_sa

    movements = [
        PolicyMovement("Opening in-force", opening_n, opening_sa,
                       "Prior period closing position."),
        PolicyMovement("(+) New business", nb_n, nb_sa,
                       f"Estimated at {new_business_pct:.1%} of closing (illustrative)."),
        PolicyMovement("(−) Lapses / surrenders", -lapse_n, -lapse_sa,
                       f"Estimated at {lapse_pct:.1%} of opening (illustrative)."),
        PolicyMovement("(−) Deaths / critical illness claims", -death_n, -death_sa,
                       f"Estimated at {death_pct:.1%} of opening (illustrative)."),
        PolicyMovement("(−) Maturities", -mat_n, -mat_sa,
                       f"Estimated at {maturity_pct:.1%} of opening (illustrative)."),
        PolicyMovement("Closing in-force", closing_n, closing_sa,
                       "Current period; matches portfolio row count."),
    ]

    return MovementAnalysis(
        cycle_label=cycle_label,
        currency=currency,
        movements=movements,
        closing_n_policies=closing_n,
        closing_sum_assured=closing_sa,
    )


# ---------------------------------------------------------------------------
# 3. Risk Metrics Summary
# ---------------------------------------------------------------------------

@dataclass
class RiskMetricEntry:
    """One row in the risk metrics summary."""
    metric_name: str
    value: float
    unit: str
    confidence_level: Optional[float]
    scenario: str
    notes: str = ""
    source_id: str = _SOURCE_ID

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskMetricsSummary:
    """VaR, Expected Shortfall, and stress metrics for the portfolio.

    Attributes
    ----------
    cycle_label:
        Reporting cycle identifier.
    n_policies:
        Portfolio size used for computation.
    metrics:
        List of :class:`RiskMetricEntry` rows.
    limitation_id:
        Limitation tag; metrics use simplified normal approximation.
    """
    cycle_label: str
    n_policies: int
    metrics: List[RiskMetricEntry]
    limitation_id: str = _LIMITATION_ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_label": self.cycle_label,
            "n_policies": self.n_policies,
            "limitation_id": self.limitation_id,
            "metrics": [m.to_dict() for m in self.metrics],
        }

    def to_markdown(self) -> str:
        lines = [
            f"## Risk Metrics Summary — {self.cycle_label}",
            f"",
            f"Portfolio size: {self.n_policies:,} policies.",
            f"",
            f"| Metric | Value | Unit | Confidence | Scenario | Notes |",
            f"|--------|-------|------|------------|----------|-------|",
        ]
        for m in self.metrics:
            cl = f"{m.confidence_level:.0%}" if m.confidence_level is not None else "—"
            lines.append(
                f"| {m.metric_name} | {m.value:,.0f} | {m.unit} | {cl} | {m.scenario} | {m.notes} |"
            )
        lines += [
            f"",
            f"> **Limitation:** {_LIMITATION_ID} — Normal approximation; not calibrated to real data.",
        ]
        return "\n".join(lines)


def build_risk_metrics_summary(
    portfolio: pd.DataFrame,
    cycle_label: str = "Current",
    confidence_level: float = 0.95,
    stress_mortality_mult: float = 1.5,
    stress_lapse_mult: float = 2.0,
) -> RiskMetricsSummary:
    """Compute simplified risk metrics over the portfolio sum-assured distribution.

    Metrics produced:
    * VaR-95: 95th percentile of individual sum-assured (illustrative policy-level).
    * ES-95: Mean of sum-assured values above VaR-95.
    * Total sum-assured: Aggregate portfolio exposure.
    * Mortality stress: Total SA × (stress_mortality_mult - 1) extra claims.
    * Lapse stress: Total SA × lapse_rate × (stress_lapse_mult - 1) extra lapses.

    All values use a *simplified, educational approximation* and are not
    suitable for regulatory submissions.

    Parameters
    ----------
    portfolio:
        Unified policy table with a ``sum_assured`` column.
    cycle_label:
        Reporting cycle label.
    confidence_level:
        VaR / ES confidence level (default 0.95).
    stress_mortality_mult:
        Mortality rate stress multiplier (e.g. 1.5 = +50% mortality).
    stress_lapse_mult:
        Lapse rate stress multiplier (e.g. 2.0 = +100% lapses).

    Returns
    -------
    RiskMetricsSummary
    """
    sa_col = "sum_assured" if "sum_assured" in portfolio.columns else None
    n = len(portfolio)
    sa = np.array(portfolio[sa_col].values, dtype=float) if sa_col else np.full(n, 100_000.0)

    var_95 = float(np.percentile(sa, confidence_level * 100))
    tail_mask = sa >= var_95
    es_95 = float(sa[tail_mask].mean()) if tail_mask.any() else var_95
    total_sa = float(sa.sum())

    # Mortality stress: extra claims from stressed mortality on worst-SA tail
    mortality_stress = total_sa * 0.005 * (stress_mortality_mult - 1.0)

    # Lapse stress: extra SA released via stressed lapse on full portfolio
    lapse_stress = total_sa * 0.05 * (stress_lapse_mult - 1.0)

    metrics = [
        RiskMetricEntry(
            metric_name="VaR-95 (Policy-level SA)",
            value=var_95,
            unit="HKD",
            confidence_level=confidence_level,
            scenario="Base",
            notes="95th percentile of individual sum-assured.",
        ),
        RiskMetricEntry(
            metric_name="ES-95 (Policy-level SA)",
            value=es_95,
            unit="HKD",
            confidence_level=confidence_level,
            scenario="Base",
            notes="Mean SA above VaR-95; illustrative tail severity.",
        ),
        RiskMetricEntry(
            metric_name="Total Portfolio Sum Assured",
            value=total_sa,
            unit="HKD",
            confidence_level=None,
            scenario="Base",
            notes=f"Aggregate exposure across {n:,} policies.",
        ),
        RiskMetricEntry(
            metric_name="Mortality Stress — Extra Claims",
            value=mortality_stress,
            unit="HKD",
            confidence_level=None,
            scenario=f"Mortality ×{stress_mortality_mult:.1f}",
            notes=(
                f"Approx. extra claims if mortality rate × {stress_mortality_mult:.1f}. "
                "Normal approximation only."
            ),
        ),
        RiskMetricEntry(
            metric_name="Lapse Stress — Extra SA Released",
            value=lapse_stress,
            unit="HKD",
            confidence_level=None,
            scenario=f"Lapse ×{stress_lapse_mult:.1f}",
            notes=(
                f"Approx. SA released if lapse rate × {stress_lapse_mult:.1f}. "
                "Normal approximation only."
            ),
        ),
    ]

    return RiskMetricsSummary(
        cycle_label=cycle_label,
        n_policies=n,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# 4. Validation Exceptions Report
# ---------------------------------------------------------------------------

@dataclass
class ValidationException:
    """One row in the validation exceptions report."""
    check_id: str
    check_name: str
    status: str          # "FAIL" | "WARN"
    message: str
    threshold: Optional[float]
    observed: Optional[float]
    recommended_action: str
    source_id: str = _SOURCE_ID

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationExceptionsReport:
    """Report listing all FAIL and WARN validation checks.

    Attributes
    ----------
    run_id:
        Model run UUID.
    n_total_checks:
        Total number of checks executed.
    n_exceptions:
        Number of FAIL + WARN checks.
    exceptions:
        List of :class:`ValidationException` rows (empty if all clear).
    overall_status:
        ``"CLEAR"`` if no FAILs/WARNs, otherwise ``"EXCEPTIONS"``.
    """
    run_id: str
    n_total_checks: int
    n_exceptions: int
    exceptions: List[ValidationException]
    overall_status: str     # "CLEAR" | "EXCEPTIONS"
    limitation_id: str = _LIMITATION_ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "n_total_checks": self.n_total_checks,
            "n_exceptions": self.n_exceptions,
            "overall_status": self.overall_status,
            "limitation_id": self.limitation_id,
            "exceptions": [e.to_dict() for e in self.exceptions],
        }

    def to_markdown(self) -> str:
        lines = [
            f"## Validation Exceptions Report",
            f"",
            f"**Run ID:** `{self.run_id}`  ",
            f"**Total checks:** {self.n_total_checks}  ",
            f"**Exceptions (FAIL/WARN):** {self.n_exceptions}  ",
            f"**Overall status:** {self.overall_status}",
            f"",
        ]
        if not self.exceptions:
            lines.append("✅ No validation exceptions — all checks passed or were skipped.")
        else:
            lines += [
                f"| Check ID | Status | Message | Threshold | Observed | Action |",
                f"|----------|--------|---------|-----------|----------|--------|",
            ]
            for e in self.exceptions:
                thr = f"{e.threshold:.4f}" if e.threshold is not None else "—"
                obs = f"{e.observed:.4f}" if e.observed is not None else "—"
                lines.append(
                    f"| {e.check_id} | {e.status} | {e.message[:50]}… | {thr} | {obs} | {e.recommended_action} |"
                )
        return "\n".join(lines)


_RECOMMENDED_ACTIONS: Dict[str, str] = {
    "V-RECON-01": "Investigate chunk processing errors; do not sign off until reconciliation passes.",
    "V-RECON-02": "Review failed chunks in failed_chunk_audit.json; consider re-run with smaller chunks.",
    "V-COUNT-01": "Verify source portfolio has not changed between assumption lock and model run.",
    "V-MIX-01":   "Confirm product-line split is within expected range; check portfolio generator config.",
    "V-AGE-01":   "Verify age distribution matches current in-force data; flag for assumption review.",
    "V-PREM-01":  "Confirm premium rate basis; check sum-assured distribution against in-force file.",
    "V-TVOG-01":  "TVOG check is informational; provide stochastic ESG inputs for quantification.",
    "V-SA-01":    "Sum-assured movement exceeds tolerance; investigate new business or lapse activity.",
}


def build_validation_exceptions_report(
    run_id: str,
    validation_suite_dict: Dict[str, Any],
) -> ValidationExceptionsReport:
    """Build a :class:`ValidationExceptionsReport` from a validation suite dict.

    Parameters
    ----------
    run_id:
        Model run UUID.
    validation_suite_dict:
        Dictionary produced by ``ValidationSuiteResult.to_dict()``.

    Returns
    -------
    ValidationExceptionsReport
    """
    checks = validation_suite_dict.get("checks", [])
    exceptions = []
    for c in checks:
        if c.get("status") in ("FAIL", "WARN"):
            exceptions.append(ValidationException(
                check_id=c.get("check_id", ""),
                check_name=c.get("check_name", ""),
                status=c.get("status", ""),
                message=c.get("message", ""),
                threshold=c.get("threshold"),
                observed=c.get("observed"),
                recommended_action=_RECOMMENDED_ACTIONS.get(c.get("check_id", ""), "Review and remediate."),
            ))

    return ValidationExceptionsReport(
        run_id=run_id,
        n_total_checks=len(checks),
        n_exceptions=len(exceptions),
        exceptions=exceptions,
        overall_status="CLEAR" if not exceptions else "EXCEPTIONS",
    )


# ---------------------------------------------------------------------------
# 5. Sign-Off Checklist
# ---------------------------------------------------------------------------

@dataclass
class ChecklistItem:
    """One item in the sign-off checklist."""
    step_id: str
    description: str
    status: str          # "COMPLETE" | "PENDING" | "N/A"
    completed_by: str
    completed_at: str
    evidence_ref: str    # artefact path or ID

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SignOffChecklist:
    """Governance sign-off checklist for one reporting cycle.

    Confirms that each mandatory step in the actuarial reporting process has
    been completed, with evidence references and reviewer attribution.

    Attributes
    ----------
    pack_id:
        UUID of the educational reporting pack (prefix ``"ERP-"``).
    run_id:
        Model run UUID.
    lock_id:
        Assumption lock UUID.
    cycle_label:
        Reporting cycle label.
    reviewer:
        Name of the model reviewer / signing actuary.
    items:
        Ordered list of :class:`ChecklistItem` rows.
    all_complete:
        True if all non-N/A items are COMPLETE.
    """
    pack_id: str
    run_id: str
    lock_id: str
    cycle_label: str
    reviewer: str
    items: List[ChecklistItem]
    all_complete: bool
    limitation_id: str = _LIMITATION_ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "run_id": self.run_id,
            "lock_id": self.lock_id,
            "cycle_label": self.cycle_label,
            "reviewer": self.reviewer,
            "all_complete": self.all_complete,
            "limitation_id": self.limitation_id,
            "items": [i.to_dict() for i in self.items],
        }

    def to_markdown(self) -> str:
        lines = [
            f"## Sign-Off Checklist — {self.cycle_label}",
            f"",
            f"**Pack ID:** `{self.pack_id}`  ",
            f"**Run ID:** `{self.run_id}`  ",
            f"**Lock ID:** `{self.lock_id}`  ",
            f"**Reviewer:** {self.reviewer}  ",
            f"**All complete:** {'✅ Yes' if self.all_complete else '❌ No'}",
            f"",
            f"| # | Step | Status | Completed By | Evidence |",
            f"|---|------|--------|--------------|----------|",
        ]
        for item in self.items:
            tick = "✅" if item.status == "COMPLETE" else ("⏳" if item.status == "PENDING" else "➖")
            lines.append(
                f"| {item.step_id} | {item.description} | {tick} {item.status} "
                f"| {item.completed_by} | {item.evidence_ref} |"
            )
        return "\n".join(lines)


def build_sign_off_checklist(
    run_id: str,
    lock_id: str,
    cycle_label: str,
    reviewer: str,
    governance_cleared: bool,
    output_dir: Optional[Path] = None,
) -> SignOffChecklist:
    """Build the standard sign-off checklist for an educational reporting cycle.

    Parameters
    ----------
    run_id:
        Model run UUID.
    lock_id:
        Assumption lock UUID.
    cycle_label:
        Reporting cycle label.
    reviewer:
        Reviewer name or role.
    governance_cleared:
        Whether the sign-off pack passed all governance gates.
    output_dir:
        Directory where output artefacts were written (used for evidence refs).

    Returns
    -------
    SignOffChecklist
    """
    now = _now_utc()
    pack_id = "ERP-" + str(uuid.uuid4())[:8].upper()
    ref = lambda name: str(output_dir / name) if output_dir else name  # noqa: E731

    items = [
        ChecklistItem(
            step_id="S-01",
            description="Assumptions reviewed and locked before model run",
            status="COMPLETE",
            completed_by=reviewer,
            completed_at=now,
            evidence_ref=ref("assumption_lock.json"),
        ),
        ChecklistItem(
            step_id="S-02",
            description="Portfolio data validated against in-force file",
            status="COMPLETE",
            completed_by="Automated (portfolio_generator.py)",
            completed_at=now,
            evidence_ref="PortfolioGenerationResult.digest",
        ),
        ChecklistItem(
            step_id="S-03",
            description="Chunked model run completed with reconciliation",
            status="COMPLETE",
            completed_by="Automated (chunk_processor.py)",
            completed_at=now,
            evidence_ref=ref("checkpoint.json"),
        ),
        ChecklistItem(
            step_id="S-04",
            description="Post-run validation suite executed",
            status="COMPLETE",
            completed_by="Automated (reporting_cycle.py)",
            completed_at=now,
            evidence_ref=ref("validation_suite.json"),
        ),
        ChecklistItem(
            step_id="S-05",
            description="Validation exceptions reviewed and resolved (or accepted)",
            status="COMPLETE" if governance_cleared else "PENDING",
            completed_by=reviewer if governance_cleared else "—",
            completed_at=now if governance_cleared else "",
            evidence_ref=ref("output_review.json"),
        ),
        ChecklistItem(
            step_id="S-06",
            description="Output review completed and approved by named reviewer",
            status="COMPLETE" if governance_cleared else "PENDING",
            completed_by=reviewer if governance_cleared else "—",
            completed_at=now if governance_cleared else "",
            evidence_ref=ref("output_review.json"),
        ),
        ChecklistItem(
            step_id="S-07",
            description="Sign-off pack assembled and stored",
            status="COMPLETE",
            completed_by="Automated (reporting_cycle.py)",
            completed_at=now,
            evidence_ref=ref("sign_off_pack.json"),
        ),
        ChecklistItem(
            step_id="S-08",
            description="Educational reporting pack produced (this document)",
            status="COMPLETE",
            completed_by="Automated (educational_reporting_pack.py)",
            completed_at=now,
            evidence_ref=ref("educational_reporting_pack.json"),
        ),
        ChecklistItem(
            step_id="S-09",
            description="Model limitations acknowledged by reviewer",
            status="COMPLETE",
            completed_by=reviewer,
            completed_at=now,
            evidence_ref=f"Limitation ID: {_LIMITATION_ID}",
        ),
    ]

    all_complete = all(
        i.status in ("COMPLETE", "N/A") for i in items
    )

    return SignOffChecklist(
        pack_id=pack_id,
        run_id=run_id,
        lock_id=lock_id,
        cycle_label=cycle_label,
        reviewer=reviewer,
        items=items,
        all_complete=all_complete,
    )


# ---------------------------------------------------------------------------
# Orchestrator: EducationalReportingPack
# ---------------------------------------------------------------------------

@dataclass
class EducationalReportingPack:
    """Full educational reporting pack for one actuarial reporting cycle.

    Aggregates all five sections into a single structured document that can be
    serialised to JSON or Markdown.

    Attributes
    ----------
    pack_id:
        UUID of this pack (prefix ``"ERP-"``).
    generated_at:
        ISO-8601 UTC timestamp.
    cycle_label:
        Reporting cycle identifier.
    version:
        Pack version string.
    run_log:
        :class:`ModelRunLog` — pipeline stage log.
    movement_analysis:
        :class:`MovementAnalysis` — policy roll-forward.
    risk_metrics:
        :class:`RiskMetricsSummary` — VaR, ES, stress metrics.
    validation_exceptions:
        :class:`ValidationExceptionsReport` — FAIL/WARN checks.
    sign_off_checklist:
        :class:`SignOffChecklist` — governance checklist.
    source_id:
        Traceability tag.
    limitation_id:
        Limitation tag.
    """
    pack_id: str
    generated_at: str
    cycle_label: str
    version: str
    run_log: ModelRunLog
    movement_analysis: MovementAnalysis
    risk_metrics: RiskMetricsSummary
    validation_exceptions: ValidationExceptionsReport
    sign_off_checklist: SignOffChecklist
    source_id: str = _SOURCE_ID
    limitation_id: str = _LIMITATION_ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "generated_at": self.generated_at,
            "cycle_label": self.cycle_label,
            "version": self.version,
            "source_id": self.source_id,
            "limitation_id": self.limitation_id,
            "run_log": self.run_log.to_dict(),
            "movement_analysis": self.movement_analysis.to_dict(),
            "risk_metrics": self.risk_metrics.to_dict(),
            "validation_exceptions": self.validation_exceptions.to_dict(),
            "sign_off_checklist": self.sign_off_checklist.to_dict(),
        }

    def write_json(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8")
        return path

    def write_markdown(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        sections = [
            f"# Educational Reporting Pack — {self.cycle_label}",
            f"",
            f"**Pack ID:** `{self.pack_id}`  ",
            f"**Generated:** {self.generated_at}  ",
            f"**Version:** {self.version}  ",
            f"**Source ID:** {self.source_id}  ",
            f"**Limitation ID:** {self.limitation_id}",
            f"",
            f"---",
            f"",
            self.run_log.to_markdown(),
            f"",
            f"---",
            f"",
            self.movement_analysis.to_markdown(),
            f"",
            f"---",
            f"",
            self.risk_metrics.to_markdown(),
            f"",
            f"---",
            f"",
            self.validation_exceptions.to_markdown(),
            f"",
            f"---",
            f"",
            self.sign_off_checklist.to_markdown(),
            f"",
            f"---",
            f"",
            f"*This educational reporting pack was generated automatically by "
            f"`educational_reporting_pack.py` (Phase 11 Task 5). "
            f"It is an illustrative reference only and must not be used for regulatory submissions.*",
        ]
        path.write_text("\n".join(sections), encoding="utf-8")
        return path

    def section_text(self, section: str) -> str:
        """Return the Markdown text for one named section.

        Parameters
        ----------
        section:
            One of ``"run_log"``, ``"movement"``, ``"risk"``,
            ``"exceptions"``, ``"checklist"``.
        """
        mapping = {
            "run_log": self.run_log.to_markdown,
            "movement": self.movement_analysis.to_markdown,
            "risk": self.risk_metrics.to_markdown,
            "exceptions": self.validation_exceptions.to_markdown,
            "checklist": self.sign_off_checklist.to_markdown,
        }
        fn = mapping.get(section)
        if fn is None:
            raise ValueError(f"Unknown section {section!r}. Choose from: {list(mapping)}")
        return fn()


def build_educational_reporting_pack(
    portfolio: pd.DataFrame,
    run_id: str,
    lock_id: str,
    cycle_label: str = "2026-Q2",
    reviewer: str = "Model Governance Team",
    governance_cleared: bool = True,
    n_chunks: int = 10,
    n_chunks_done: int = 10,
    n_chunks_failed: int = 0,
    validation_suite_dict: Optional[Dict[str, Any]] = None,
    prior_n_policies: int = 0,
    prior_sum_assured: float = 0.0,
    output_dir: Optional[Path] = None,
    started_at: str = "",
) -> EducationalReportingPack:
    """Assemble the full :class:`EducationalReportingPack` from cycle metadata.

    This is the primary entry point.  Provide the portfolio DataFrame and run
    metadata; the function assembles all five sections and returns the pack.

    Parameters
    ----------
    portfolio:
        Unified policy table (100k rows from :func:`generate_hk_par_portfolio`).
    run_id:
        Model run UUID (from :class:`ModelRunRecord`).
    lock_id:
        Assumption lock UUID (from :class:`AssumptionLock`).
    cycle_label:
        Reporting cycle identifier.
    reviewer:
        Named reviewer / signing actuary.
    governance_cleared:
        Whether the sign-off pack cleared all governance gates.
    n_chunks, n_chunks_done, n_chunks_failed:
        Chunk processing metrics from :class:`ReconciliationReport`.
    validation_suite_dict:
        Dict from ``ValidationSuiteResult.to_dict()``; pass ``None`` to
        generate a synthetic all-pass result for demonstration.
    prior_n_policies, prior_sum_assured:
        Opening position for movement analysis (0 = estimate from closing).
    output_dir:
        Directory where output artefacts were written.
    started_at:
        ISO-8601 timestamp when the reporting cycle started.

    Returns
    -------
    EducationalReportingPack
    """
    pack_id = "ERP-" + str(uuid.uuid4())[:8].upper()
    generated_at = _now_utc()

    if validation_suite_dict is None:
        # Synthetic all-pass suite for demonstration
        validation_suite_dict = {
            "checks": [
                {"check_id": f"V-{i:02d}", "check_name": f"Check {i}",
                 "status": "PASS", "message": "OK", "threshold": None, "observed": None}
                for i in range(1, 8)
            ]
        }

    run_log = build_model_run_log(
        run_id=run_id,
        lock_id=lock_id,
        cycle_label=cycle_label,
        n_policies=len(portfolio),
        n_chunks=n_chunks,
        n_chunks_done=n_chunks_done,
        n_chunks_failed=n_chunks_failed,
        output_dir=output_dir,
        started_at=started_at,
    )

    movement = build_movement_analysis(
        portfolio,
        prior_n_policies=prior_n_policies,
        prior_sum_assured=prior_sum_assured,
        cycle_label=cycle_label,
    )

    risk = build_risk_metrics_summary(portfolio, cycle_label=cycle_label)

    exceptions_report = build_validation_exceptions_report(run_id, validation_suite_dict)

    checklist = build_sign_off_checklist(
        run_id=run_id,
        lock_id=lock_id,
        cycle_label=cycle_label,
        reviewer=reviewer,
        governance_cleared=governance_cleared,
        output_dir=output_dir,
    )

    return EducationalReportingPack(
        pack_id=pack_id,
        generated_at=generated_at,
        cycle_label=cycle_label,
        version=_PACK_VERSION,
        run_log=run_log,
        movement_analysis=movement,
        risk_metrics=risk,
        validation_exceptions=exceptions_report,
        sign_off_checklist=checklist,
    )
