"""
Governance and Audit Trail Framework
=====================================

Implements model governance and audit trail requirements per:
  - IA TAS M §3.3   — model governance and ownership
  - IA TAS M §3.7   — model change control (change log format)
  - IA TAS M §3.5   — assumption sign-off workflow
  - SOA ASOP 56 §3.5 — model validation governance
  - IFoA Modelling Practice Note §4 — model risk register

Overview
--------
This module provides four interlocking components:

1. **AuditTrail** — append-only log of all model runs, parameter changes,
   and validation events.  Every entry is timestamped, typed, and attributed
   to an actor.

2. **ChangeRecord** — structured representation of a model or assumption
   change per IA TAS M §3.7 requirements.  Includes impact assessment,
   sign-off status, and before/after parameter snapshots.

3. **SignOffWorkflow** — tracks assumption owner sign-off per IA TAS M §3.5.
   Supports multi-stage review: Author → Peer Reviewer → Assumption Owner.

4. **ModelRiskRegister** — maintains the model risk register per IFoA
   Modelling Practice Note §4.  Each entry records risk description,
   likelihood, impact, owner, and mitigation status.

Persistence
-----------
All state is serialisable to/from JSON.  Callers are responsible for saving
and loading the JSON blob (e.g., to .claude-dev/MODEL_DEV_STATE.json or a
dedicated governance file).

DEVELOPMENT STATUS
------------------
Phase 2, Task 4: Full implementation delivered.  Integration with live ESG
runs deferred to Phase 3 when simulate() is available.

PRODUCTION USE RESTRICTION
--------------------------
AuditTrail entries are immutable by design.  Do NOT delete or backfill entries
after the fact — this would constitute an audit trail breach.  If a correction
is required, add a CORRECTION entry referencing the original entry UUID.
"""

from __future__ import annotations

import enum
import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# 0. Shared Enums
# ---------------------------------------------------------------------------

class EntryType(str, enum.Enum):
    """Categories of audit trail entries.

    MODEL_RUN      — a production or test model execution.
    PARAM_CHANGE   — a change to any model parameter or assumption.
    VALIDATION     — a validation or test event (pass/fail).
    SIGN_OFF       — an assumption or result sign-off event.
    CORRECTION     — correction of a prior entry (references original UUID).
    GOVERNANCE     — governance event (risk register update, policy change).
    """
    MODEL_RUN    = "MODEL_RUN"
    PARAM_CHANGE = "PARAM_CHANGE"
    VALIDATION   = "VALIDATION"
    SIGN_OFF     = "SIGN_OFF"
    CORRECTION   = "CORRECTION"
    GOVERNANCE   = "GOVERNANCE"


class SignOffStatus(str, enum.Enum):
    """Stage in the three-stage IA TAS M §3.5 sign-off workflow."""
    DRAFT          = "DRAFT"           # Author working draft
    PEER_REVIEW    = "PEER_REVIEW"     # Submitted for peer review (APS X2)
    OWNER_REVIEW   = "OWNER_REVIEW"    # With assumption owner
    APPROVED       = "APPROVED"        # Fully signed off
    REJECTED       = "REJECTED"        # Returned with comments
    SUPERSEDED     = "SUPERSEDED"      # Replaced by newer change record


class RiskRating(str, enum.Enum):
    """Model risk register entry rating per IFoA Modelling Practice Note §4."""
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class MitigationStatus(str, enum.Enum):
    """Mitigation status for a model risk register entry."""
    OPEN       = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    MITIGATED  = "MITIGATED"
    ACCEPTED   = "ACCEPTED"     # Risk accepted without mitigation (requires Assumption Owner sign-off)


# ---------------------------------------------------------------------------
# 1. AuditEntry — immutable, append-only record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuditEntry:
    """Single immutable record in the audit trail.

    Attributes
    ----------
    entry_id : str
        UUID4 hex string.  Generated on construction.
    timestamp : str
        ISO 8601 UTC timestamp of the event.
    entry_type : EntryType
        Category of the event.
    actor : str
        Who or what generated the entry (e.g. "Claude-Actuarial-Agent",
        "john.smith@example.com", "CI/CD pipeline").
    description : str
        Human-readable summary of the event.
    details : dict
        Structured metadata specific to the entry type.  Contents are
        validated by the factory methods below.
    phase : str
        Model development phase at the time of the entry.
    digest : str
        SHA-256 digest of (entry_id + timestamp + description + details JSON).
        Allows downstream verification that the entry has not been tampered with.
    corrects_entry_id : Optional[str]
        If entry_type == CORRECTION, the UUID of the entry being corrected.
    """
    entry_id:          str
    timestamp:         str
    entry_type:        EntryType
    actor:             str
    description:       str
    details:           Dict[str, Any]
    phase:             str
    digest:            str
    corrects_entry_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def _make(
        cls,
        entry_type: EntryType,
        actor: str,
        description: str,
        details: Dict[str, Any],
        phase: str,
        corrects_entry_id: Optional[str] = None,
    ) -> "AuditEntry":
        entry_id  = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat()
        raw       = entry_id + timestamp + description + json.dumps(details, sort_keys=True)
        digest    = hashlib.sha256(raw.encode()).hexdigest()
        return cls(
            entry_id=entry_id,
            timestamp=timestamp,
            entry_type=entry_type,
            actor=actor,
            description=description,
            details=details,
            phase=phase,
            digest=digest,
            corrects_entry_id=corrects_entry_id,
        )

    @classmethod
    def model_run(
        cls,
        actor: str,
        phase: str,
        run_id: str,
        scenario_count: int,
        duration_seconds: float,
        outcome: str,
        files_changed: List[str],
        test_summary: Optional[str] = None,
    ) -> "AuditEntry":
        """Record a model run event."""
        return cls._make(
            entry_type=EntryType.MODEL_RUN,
            actor=actor,
            description=f"Model run {run_id}: {outcome}",
            details={
                "run_id": run_id,
                "scenario_count": scenario_count,
                "duration_seconds": duration_seconds,
                "outcome": outcome,
                "files_changed": files_changed,
                "test_summary": test_summary,
            },
            phase=phase,
        )

    @classmethod
    def param_change(
        cls,
        actor: str,
        phase: str,
        parameter_name: str,
        old_value: Any,
        new_value: Any,
        rationale: str,
        standard_reference: str,
        change_record_id: Optional[str] = None,
    ) -> "AuditEntry":
        """Record a parameter or assumption change.

        Parameters
        ----------
        standard_reference : str
            ASOP / TAS M section that governs this parameter
            (e.g. "SOA ASOP 25 §3.3", "IA TAS M §3.5").
        change_record_id : str, optional
            UUID of the associated ChangeRecord.
        """
        return cls._make(
            entry_type=EntryType.PARAM_CHANGE,
            actor=actor,
            description=f"Parameter change: {parameter_name} {old_value!r} → {new_value!r}",
            details={
                "parameter_name": parameter_name,
                "old_value": old_value,
                "new_value": new_value,
                "rationale": rationale,
                "standard_reference": standard_reference,
                "change_record_id": change_record_id,
            },
            phase=phase,
        )

    @classmethod
    def validation(
        cls,
        actor: str,
        phase: str,
        test_suite: str,
        tests_run: int,
        tests_passed: int,
        tests_failed: int,
        outcome: str,
        failed_tests: Optional[List[str]] = None,
    ) -> "AuditEntry":
        """Record a validation or test suite event."""
        return cls._make(
            entry_type=EntryType.VALIDATION,
            actor=actor,
            description=f"Validation: {test_suite} — {tests_passed}/{tests_run} passed ({outcome})",
            details={
                "test_suite": test_suite,
                "tests_run": tests_run,
                "tests_passed": tests_passed,
                "tests_failed": tests_failed,
                "outcome": outcome,
                "failed_tests": failed_tests or [],
            },
            phase=phase,
        )

    @classmethod
    def sign_off(
        cls,
        actor: str,
        phase: str,
        change_record_id: str,
        new_status: SignOffStatus,
        comments: str = "",
    ) -> "AuditEntry":
        """Record a sign-off action on a ChangeRecord."""
        return cls._make(
            entry_type=EntryType.SIGN_OFF,
            actor=actor,
            description=f"Sign-off on change {change_record_id}: {new_status.value}",
            details={
                "change_record_id": change_record_id,
                "new_status": new_status.value,
                "comments": comments,
            },
            phase=phase,
        )

    @classmethod
    def correction(
        cls,
        actor: str,
        phase: str,
        corrects_entry_id: str,
        reason: str,
        corrected_details: Dict[str, Any],
    ) -> "AuditEntry":
        """Record a correction to an existing audit entry.

        Notes
        -----
        The original entry is NOT modified.  This entry documents what was
        wrong and what the correct information is.
        """
        return cls._make(
            entry_type=EntryType.CORRECTION,
            actor=actor,
            description=f"Correction of entry {corrects_entry_id}: {reason}",
            details={
                "reason": reason,
                "corrected_details": corrected_details,
            },
            phase=phase,
            corrects_entry_id=corrects_entry_id,
        )

    @classmethod
    def governance(
        cls,
        actor: str,
        phase: str,
        event: str,
        details: Dict[str, Any],
    ) -> "AuditEntry":
        """Record a governance event (risk register update, policy change, etc.)."""
        return cls._make(
            entry_type=EntryType.GOVERNANCE,
            actor=actor,
            description=f"Governance event: {event}",
            details=details,
            phase=phase,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["entry_type"] = self.entry_type.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuditEntry":
        d = dict(d)
        d["entry_type"] = EntryType(d["entry_type"])
        return cls(**d)

    def verify_digest(self) -> bool:
        """Return True if the stored digest matches a fresh computation."""
        raw    = self.entry_id + self.timestamp + self.description + json.dumps(self.details, sort_keys=True)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return digest == self.digest


# ---------------------------------------------------------------------------
# 2. ChangeRecord — IA TAS M §3.7 compliant change log entry
# ---------------------------------------------------------------------------

@dataclass
class ChangeRecord:
    """Model or assumption change record per IA TAS M §3.7.

    Attributes
    ----------
    record_id : str
        UUID4 hex string.
    created_at : str
        ISO 8601 UTC timestamp of creation.
    title : str
        Short title (≤ 120 chars) suitable for a change register table.
    description : str
        Full description of the change including motivation and scope.
    change_type : str
        One of: "assumption_change", "code_change", "data_change",
        "methodology_change", "governance_change".
    affected_components : List[str]
        File paths or component names affected.
    standard_references : List[str]
        ASOP / TAS M / APS sections addressed by this change.
    before_snapshot : dict
        Key parameter values BEFORE the change.  Use {} if not applicable.
    after_snapshot : dict
        Key parameter values AFTER the change.
    impact_assessment : str
        Qualitative description of the expected materiality and direction
        of impact on model outputs.
    quantitative_impact : Optional[str]
        Where computed: "TVOG sensitivity ±X bps", "VaR 99.5% change +Y%".
    status : SignOffStatus
        Current position in the sign-off workflow.
    author : str
        Who authored the change.
    peer_reviewer : Optional[str]
        Assigned peer reviewer (APS X2).
    assumption_owner : Optional[str]
        Assumption Owner responsible for final sign-off (IA TAS M §3.5).
    sign_off_history : List[dict]
        Ordered list of sign-off actions (each is a dict with actor,
        status, timestamp, comments).
    phase : str
        Development phase when this change was made.
    """
    record_id:            str
    created_at:           str
    title:                str
    description:          str
    change_type:          str
    affected_components:  List[str]
    standard_references:  List[str]
    before_snapshot:      Dict[str, Any]
    after_snapshot:       Dict[str, Any]
    impact_assessment:    str
    quantitative_impact:  Optional[str]
    status:               SignOffStatus
    author:               str
    peer_reviewer:        Optional[str]
    assumption_owner:     Optional[str]
    sign_off_history:     List[Dict[str, Any]]
    phase:                str

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        title: str,
        description: str,
        change_type: str,
        affected_components: List[str],
        standard_references: List[str],
        before_snapshot: Dict[str, Any],
        after_snapshot: Dict[str, Any],
        impact_assessment: str,
        author: str,
        phase: str,
        quantitative_impact: Optional[str] = None,
        peer_reviewer: Optional[str] = None,
        assumption_owner: Optional[str] = None,
    ) -> "ChangeRecord":
        valid_types = {
            "assumption_change", "code_change", "data_change",
            "methodology_change", "governance_change",
        }
        if change_type not in valid_types:
            raise ValueError(f"change_type must be one of {valid_types}, got {change_type!r}")
        return cls(
            record_id=uuid.uuid4().hex,
            created_at=datetime.now(timezone.utc).isoformat(),
            title=title,
            description=description,
            change_type=change_type,
            affected_components=affected_components,
            standard_references=standard_references,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            impact_assessment=impact_assessment,
            quantitative_impact=quantitative_impact,
            status=SignOffStatus.DRAFT,
            author=author,
            peer_reviewer=peer_reviewer,
            assumption_owner=assumption_owner,
            sign_off_history=[],
            phase=phase,
        )

    # ------------------------------------------------------------------
    # Workflow transitions
    # ------------------------------------------------------------------

    def submit_for_peer_review(self, actor: str, comments: str = "") -> None:
        """Submit to peer reviewer (DRAFT → PEER_REVIEW)."""
        if self.status != SignOffStatus.DRAFT:
            raise ValueError(f"Can only submit from DRAFT, current status: {self.status.value}")
        self._append_history(actor, SignOffStatus.PEER_REVIEW, comments)
        self.status = SignOffStatus.PEER_REVIEW

    def submit_to_owner(self, actor: str, comments: str = "") -> None:
        """Submit to assumption owner (PEER_REVIEW → OWNER_REVIEW)."""
        if self.status != SignOffStatus.PEER_REVIEW:
            raise ValueError(f"Must be in PEER_REVIEW, current status: {self.status.value}")
        self._append_history(actor, SignOffStatus.OWNER_REVIEW, comments)
        self.status = SignOffStatus.OWNER_REVIEW

    def approve(self, actor: str, comments: str = "") -> None:
        """Final approval by assumption owner (OWNER_REVIEW → APPROVED)."""
        if self.status != SignOffStatus.OWNER_REVIEW:
            raise ValueError(f"Must be in OWNER_REVIEW, current status: {self.status.value}")
        self._append_history(actor, SignOffStatus.APPROVED, comments)
        self.status = SignOffStatus.APPROVED

    def reject(self, actor: str, comments: str = "") -> None:
        """Reject and return to author (any non-APPROVED → REJECTED)."""
        if self.status == SignOffStatus.APPROVED:
            raise ValueError("Cannot reject an already-approved change record")
        self._append_history(actor, SignOffStatus.REJECTED, comments)
        self.status = SignOffStatus.REJECTED

    def supersede(self, actor: str, reason: str = "") -> None:
        """Mark as superseded by a newer change record."""
        self._append_history(actor, SignOffStatus.SUPERSEDED, reason)
        self.status = SignOffStatus.SUPERSEDED

    def _append_history(self, actor: str, status: SignOffStatus, comments: str) -> None:
        self.sign_off_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "status": status.value,
            "comments": comments,
        })

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChangeRecord":
        d = dict(d)
        d["status"] = SignOffStatus(d["status"])
        return cls(**d)

    def summary_row(self) -> Dict[str, str]:
        """Return a one-row summary for tabular display."""
        return {
            "record_id":   self.record_id[:8] + "…",
            "title":       self.title[:60],
            "change_type": self.change_type,
            "status":      self.status.value,
            "author":      self.author,
            "created_at":  self.created_at[:10],
            "phase":       self.phase,
        }


# ---------------------------------------------------------------------------
# 3. ModelRiskRegister — IFoA Modelling Practice Note §4
# ---------------------------------------------------------------------------

@dataclass
class RiskEntry:
    """Single entry in the model risk register.

    Attributes
    ----------
    risk_id : str
        Short identifier (e.g. "MR-001").
    title : str
        Brief risk description.
    description : str
        Full risk description including failure mode.
    category : str
        One of: "model_error", "data_quality", "assumption_error",
        "process_risk", "governance_risk", "operational_risk".
    likelihood : RiskRating
        Probability of the risk materialising.
    impact : RiskRating
        Severity if the risk materialises.
    overall_rating : RiskRating
        Combined rating (typically max of likelihood, impact for simplicity;
        use a risk matrix for production).
    owner : str
        Risk owner (role or individual).
    mitigation : str
        Planned or implemented mitigation action.
    mitigation_status : MitigationStatus
    related_standard : str
        TAS M / ASOP section most relevant to this risk.
    created_at : str
    updated_at : str
    notes : str
    """
    risk_id:            str
    title:              str
    description:        str
    category:           str
    likelihood:         RiskRating
    impact:             RiskRating
    overall_rating:     RiskRating
    owner:              str
    mitigation:         str
    mitigation_status:  MitigationStatus
    related_standard:   str
    created_at:         str
    updated_at:         str
    notes:              str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["likelihood"]        = self.likelihood.value
        d["impact"]            = self.impact.value
        d["overall_rating"]    = self.overall_rating.value
        d["mitigation_status"] = self.mitigation_status.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RiskEntry":
        d = dict(d)
        d["likelihood"]        = RiskRating(d["likelihood"])
        d["impact"]            = RiskRating(d["impact"])
        d["overall_rating"]    = RiskRating(d["overall_rating"])
        d["mitigation_status"] = MitigationStatus(d["mitigation_status"])
        return cls(**d)

    def update_mitigation(
        self,
        new_status: MitigationStatus,
        notes: str = "",
    ) -> None:
        self.mitigation_status = new_status
        self.updated_at        = datetime.now(timezone.utc).isoformat()
        if notes:
            self.notes = notes


class ModelRiskRegister:
    """Model risk register per IFoA Modelling Practice Note §4.

    Maintains an ordered list of RiskEntry records.  Supports filtering
    by rating, category, and mitigation status.  Fully serialisable.
    """

    def __init__(self, entries: Optional[List[RiskEntry]] = None) -> None:
        self._entries: List[RiskEntry] = list(entries or [])

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(
        self,
        risk_id: str,
        title: str,
        description: str,
        category: str,
        likelihood: RiskRating,
        impact: RiskRating,
        owner: str,
        mitigation: str,
        related_standard: str,
        notes: str = "",
        mitigation_status: MitigationStatus = MitigationStatus.OPEN,
    ) -> RiskEntry:
        """Add a new risk entry. Returns the created entry."""
        valid_categories = {
            "model_error", "data_quality", "assumption_error",
            "process_risk", "governance_risk", "operational_risk",
        }
        if category not in valid_categories:
            raise ValueError(f"category must be one of {valid_categories}")

        # Overall rating = max(likelihood, impact) — simplified matrix
        order = [RiskRating.LOW, RiskRating.MEDIUM, RiskRating.HIGH, RiskRating.CRITICAL]
        overall = order[max(order.index(likelihood), order.index(impact))]

        now = datetime.now(timezone.utc).isoformat()
        entry = RiskEntry(
            risk_id=risk_id,
            title=title,
            description=description,
            category=category,
            likelihood=likelihood,
            impact=impact,
            overall_rating=overall,
            owner=owner,
            mitigation=mitigation,
            mitigation_status=mitigation_status,
            related_standard=related_standard,
            created_at=now,
            updated_at=now,
            notes=notes,
        )
        self._entries.append(entry)
        return entry

    def get(self, risk_id: str) -> RiskEntry:
        for e in self._entries:
            if e.risk_id == risk_id:
                return e
        raise KeyError(f"Risk ID not found: {risk_id!r}")

    def all(self) -> List[RiskEntry]:
        return list(self._entries)

    def filter(
        self,
        category: Optional[str] = None,
        rating: Optional[RiskRating] = None,
        mitigation_status: Optional[MitigationStatus] = None,
    ) -> List[RiskEntry]:
        result = self._entries
        if category:
            result = [e for e in result if e.category == category]
        if rating:
            result = [e for e in result if e.overall_rating == rating]
        if mitigation_status:
            result = [e for e in result if e.mitigation_status == mitigation_status]
        return list(result)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict with counts by rating and status."""
        rating_counts = {r.value: 0 for r in RiskRating}
        status_counts = {s.value: 0 for s in MitigationStatus}
        for e in self._entries:
            rating_counts[e.overall_rating.value] += 1
            status_counts[e.mitigation_status.value] += 1
        return {
            "total": len(self._entries),
            "by_rating": rating_counts,
            "by_status": status_counts,
            "open_critical": len(self.filter(rating=RiskRating.CRITICAL, mitigation_status=MitigationStatus.OPEN)),
        }

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries]

    @classmethod
    def from_list(cls, data: List[Dict[str, Any]]) -> "ModelRiskRegister":
        entries = [RiskEntry.from_dict(d) for d in data]
        return cls(entries)


# ---------------------------------------------------------------------------
# 4. AuditTrail — append-only log with integrity verification
# ---------------------------------------------------------------------------

class AuditTrail:
    """Append-only model audit trail.

    Maintains a chronological list of AuditEntry records.  Provides
    integrity checking (digest verification) and query helpers.

    Usage
    -----
    >>> trail = AuditTrail()
    >>> entry = AuditEntry.model_run(
    ...     actor="Claude-Actuarial-Agent",
    ...     phase="Phase 2: Industry Standards Alignment",
    ...     run_id="cycle-11",
    ...     scenario_count=0,
    ...     duration_seconds=3720.0,
    ...     outcome="PASS",
    ...     files_changed=["par_model_v2/governance/audit_trail.py"],
    ...     test_summary="107/107 passed",
    ... )
    >>> trail.append(entry)
    >>> trail.verify_all()
    True

    Persistence
    -----------
    >>> blob = trail.to_json()
    >>> trail2 = AuditTrail.from_json(blob)
    """

    def __init__(self, entries: Optional[List[AuditEntry]] = None) -> None:
        self._entries: List[AuditEntry] = list(entries or [])

    def append(self, entry: AuditEntry) -> None:
        """Add an entry.  Raises if the digest is already invalid."""
        if not entry.verify_digest():
            raise ValueError(f"Entry {entry.entry_id} has an invalid digest — possible tampering")
        self._entries.append(entry)

    @property
    def entries(self) -> List[AuditEntry]:
        """Read-only public view of the entries list (alias for .all())."""
        return list(self._entries)

    def all(self) -> List[AuditEntry]:
        return list(self._entries)

    def filter_by_type(self, entry_type: EntryType) -> List[AuditEntry]:
        return [e for e in self._entries if e.entry_type == entry_type]

    def filter_by_phase(self, phase: str) -> List[AuditEntry]:
        return [e for e in self._entries if e.phase == phase]

    def filter_by_actor(self, actor: str) -> List[AuditEntry]:
        return [e for e in self._entries if e.actor == actor]

    def latest(self, n: int = 10) -> List[AuditEntry]:
        return list(self._entries[-n:])

    def verify_all(self) -> bool:
        """Verify digest integrity of all entries.  Returns True if all pass."""
        return all(e.verify_digest() for e in self._entries)

    def integrity_report(self) -> Dict[str, Any]:
        """Return per-entry integrity status."""
        results = {e.entry_id: e.verify_digest() for e in self._entries}
        return {
            "total": len(self._entries),
            "all_valid": all(results.values()),
            "per_entry": results,
        }

    def to_json(self) -> str:
        return json.dumps([e.to_dict() for e in self._entries], indent=2)

    @classmethod
    def from_json(cls, blob: str) -> "AuditTrail":
        entries = [AuditEntry.from_dict(d) for d in json.loads(blob)]
        return cls(entries)


# ---------------------------------------------------------------------------
# 5. GovernanceStore — top-level container (audit trail + change log + risk register)
# ---------------------------------------------------------------------------

class GovernanceStore:
    """Unified governance store for the PAR Fund Stochastic Model.

    Combines:
      - AuditTrail         — immutable event log
      - List[ChangeRecord] — IA TAS M §3.7 change log
      - ModelRiskRegister  — IFoA risk register

    Intended to be serialised to .claude-dev/GOVERNANCE_STORE.json after
    each model run.

    Parameters
    ----------
    model_name : str
        Canonical model name (used in reports).
    model_version : str
        Semantic version string (e.g. "0.2.0").
    """

    def __init__(
        self,
        model_name: str = "PAR Fund Stochastic ALM & TVOG",
        model_version: str = "0.2.0",
    ) -> None:
        self.model_name     = model_name
        self.model_version  = model_version
        self.audit_trail    = AuditTrail()
        self.change_records: List[ChangeRecord] = []
        self.risk_register  = ModelRiskRegister()

    # ------------------------------------------------------------------
    # Change record helpers
    # ------------------------------------------------------------------

    def add_change_record(self, record: ChangeRecord) -> None:
        self.change_records.append(record)

    def get_change_record(self, record_id: str) -> ChangeRecord:
        for r in self.change_records:
            if r.record_id == record_id:
                return r
        raise KeyError(f"ChangeRecord not found: {record_id!r}")

    def open_change_records(self) -> List[ChangeRecord]:
        """Return all change records not yet APPROVED or SUPERSEDED."""
        closed = {SignOffStatus.APPROVED, SignOffStatus.SUPERSEDED}
        return [r for r in self.change_records if r.status not in closed]

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def governance_summary(self) -> Dict[str, Any]:
        """High-level governance dashboard dict."""
        return {
            "model_name":            self.model_name,
            "model_version":         self.model_version,
            "audit_entries":         len(self.audit_trail.all()),
            "audit_integrity_ok":    self.audit_trail.verify_all(),
            "change_records_total":  len(self.change_records),
            "change_records_open":   len(self.open_change_records()),
            "risk_register":         self.risk_register.summary(),
        }

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name":    self.model_name,
            "model_version": self.model_version,
            "audit_trail":   json.loads(self.audit_trail.to_json()),
            "change_records":[r.to_dict() for r in self.change_records],
            "risk_register": self.risk_register.to_list(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GovernanceStore":
        store = cls(
            model_name=d.get("model_name", "PAR Fund Stochastic ALM & TVOG"),
            model_version=d.get("model_version", "0.1.0"),
        )
        store.audit_trail    = AuditTrail.from_json(json.dumps(d.get("audit_trail", [])))
        store.change_records = [ChangeRecord.from_dict(r) for r in d.get("change_records", [])]
        store.risk_register  = ModelRiskRegister.from_list(d.get("risk_register", []))
        return store

    @classmethod
    def from_json(cls, blob: str) -> "GovernanceStore":
        return cls.from_dict(json.loads(blob))


# ---------------------------------------------------------------------------
# 6. Seed function — populate initial risk register from Phase 1 findings
# ---------------------------------------------------------------------------

def seed_initial_risk_register(store: GovernanceStore) -> None:
    """Populate the model risk register with Phase 1-identified risks.

    Sources:
      - docs/MODEL_AUDIT_REPORT.md        — deviation register
      - docs/IA_GOVERNANCE_REQUIREMENTS.md — governance gap register
      - docs/SOA_ASSUMPTIONS_DOCUMENT.md  — assumption compliance status

    Call this ONCE on a fresh GovernanceStore; subsequent updates use
    RiskEntry.update_mitigation() and new add() calls.
    """
    rr = store.risk_register

    rr.add(
        risk_id="MR-001",
        title="Discount rate exceeds CBIRC regulatory cap",
        description=(
            "Current discount rate assumption is 3.5%, exceeding the CBIRC regulatory cap of 3.0% "
            "(effective 2023 reserve valuation guidance). This produces an understated liability reserve "
            "and overstated solvency margin."
        ),
        category="assumption_error",
        likelihood=RiskRating.HIGH,
        impact=RiskRating.CRITICAL,
        owner="Assumption Owner",
        mitigation="Reduce discount rate to ≤3.0% in Phase 4 calibration; document deviation formally per ASOP 25 §3.3.",
        related_standard="SOA ASOP 25 §3.3; CBIRC Reserve Valuation Guidance 2023",
        notes="Flagged in docs/SOA_ASSUMPTIONS_DOCUMENT.md §3.3",
        mitigation_status=MitigationStatus.IN_PROGRESS,
    )

    rr.add(
        risk_id="MR-002",
        title="Investment return assumptions overstated vs CNY market",
        description=(
            "Bond return assumptions (4.0–5.0%) are 100–180 bps above current CNY government bond yields "
            "(2.2–2.6% as of calibration date). Equity ERP has not been calibrated. This systematically "
            "understates TVOG and liability PV."
        ),
        category="assumption_error",
        likelihood=RiskRating.HIGH,
        impact=RiskRating.HIGH,
        owner="Assumption Owner",
        mitigation="Recalibrate bond returns and ERP to CNY market data in Phase 4 (GBMCalibrator); interim sensitivity analysis required.",
        related_standard="SOA ASOP 56 §3.4; SOA ASOP 25 §3.3",
        notes="GBMCalibrator scaffolded in calibration_framework.py; full calibration Phase 4.",
        mitigation_status=MitigationStatus.IN_PROGRESS,
    )

    rr.add(
        risk_id="MR-003",
        title="Dynamic lapse assumption absent",
        description=(
            "No dynamic lapse function is implemented. Dynamic lapse is the single most impactful assumption "
            "for TVOG and ALM under stressed rate scenarios. Static lapse at current flat rates will materially "
            "understate TVOG sensitivity (estimated ±15–30% TVOG per ±25% lapse shock per Phase 1 assessment)."
        ),
        category="model_error",
        likelihood=RiskRating.MEDIUM,
        impact=RiskRating.CRITICAL,
        owner="Model Developer",
        mitigation="Dynamic lapse implemented and calibrated (Phase 13 Task 2); functional form + calibration documented; ChangeRecord assumption=\"dynamic_lapse\" APPROVED.",
        related_standard="SOA ASOP 7 §3.3; IA TAS M §3.5",
        notes="Phase 13: dynamic_lapse.py implemented, G-04/G-11 PASS (educational). Production residual: substitute credible experience study + genuine independent APS X2 review.",
        mitigation_status=MitigationStatus.IN_PROGRESS,
    )

    rr.add(
        risk_id="MR-004",
        title="P/Q measure not enforced at runtime",
        description=(
            "Prior to Phase 2, the codebase did not enforce or document the distinction between real-world (P) "
            "and risk-neutral (Q) scenario sets. Mixing measures is a critical actuarial error that invalidates "
            "both VaR/ES and TVOG outputs."
        ),
        category="model_error",
        likelihood=RiskRating.LOW,
        impact=RiskRating.CRITICAL,
        owner="Model Developer",
        mitigation=(
            "Measure enum implemented in esg_process.py (Phase 2, Task 1). "
            "TVOGEngine rejects non-Q scenario sets and RiskMetrics rejects non-P "
            "loss distributions. Remaining gap: execution evidence and governance "
            "sign-off have not yet been captured in a Python-enabled environment."
        ),
        related_standard="SOA ASOP 56 §3.1.3; IA TAS M §3.4",
        notes="Critical Deviation D-04 in MODEL_AUDIT_REPORT.md. Code-level guard remediated; verification pending.",
        mitigation_status=MitigationStatus.IN_PROGRESS,
    )

    rr.add(
        risk_id="MR-005",
        title="Distributed executor pickling failure",
        description=(
            "DistributedExecutor fails to serialise complex model objects for multiprocessing, causing "
            "7 test failures in the original repository test suite. This blocks all distributed scenario "
            "execution, TVOG computation, and VaR/ES integration."
        ),
        category="process_risk",
        likelihood=RiskRating.HIGH,
        impact=RiskRating.HIGH,
        owner="Model Developer",
        mitigation="Fix pickling in Phase 3, Task 1 (Fix distributed executor pickling bug). This is the critical path for TVOG.",
        related_standard="SOA ASOP 56 §3.5 (scenario adequacy requires successful batch execution)",
        notes="Identified in VALIDATION_FRAMEWORK_REVIEW.md as highest-leverage Phase 3 fix.",
        mitigation_status=MitigationStatus.OPEN,
    )

    rr.add(
        risk_id="MR-006",
        title="Model validation readiness below production threshold",
        description=(
            "Overall validation readiness assessed at 2/5 (development-grade). Stochastic validation "
            "(scenario convergence, martingale test, VaR/ES integration) is entirely absent. "
            "Model is not fit for regulatory reporting or production use in current state."
        ),
        category="governance_risk",
        likelihood=RiskRating.HIGH,
        impact=RiskRating.CRITICAL,
        owner="Assumption Owner",
        mitigation="4-layer validation framework implementation across Phases 3–4. Full validation cadence in Phase 5.",
        related_standard="SOA ASOP 56 §3.5; IA TAS M §3.6; APS X2",
        notes="Documented in VALIDATION_FRAMEWORK_REVIEW.md.",
        mitigation_status=MitigationStatus.IN_PROGRESS,
    )

    rr.add(
        risk_id="MR-007",
        title="No assumption change control process",
        description=(
            "The model has no documented assumption change control process. Any assumption can be changed "
            "without sign-off, impact assessment, or audit trail. This is a material IA TAS M §3.7 gap."
        ),
        category="governance_risk",
        likelihood=RiskRating.HIGH,
        impact=RiskRating.HIGH,
        owner="Assumption Owner",
        mitigation=(
            "GovernanceStore + ChangeRecord + SignOffWorkflow implemented in Phase 2, Task 4 "
            "(this module). Requires organisational adoption."
        ),
        related_standard="IA TAS M §3.7; IA TAS M §3.3",
        notes="Remediated by this module (audit_trail.py). Framework in place; process adoption pending.",
        mitigation_status=MitigationStatus.IN_PROGRESS,
    )

    rr.add(
        risk_id="MR-008",
        title="HW1F calibration not yet executed",
        description=(
            "HullWhiteCalibrator.calibrate() is a NotImplementedError stub. HW1F parameters (a=0.10, σ_r=0.012) "
            "are placeholders producing model swaption vol ~250 bps vs ~42 bps market — a 6x error. "
            "All interest rate paths and ZCB prices derived from these parameters are unreliable."
        ),
        category="model_error",
        likelihood=RiskRating.HIGH,
        impact=RiskRating.CRITICAL,
        owner="Model Developer",
        mitigation="Implement L-BFGS-B calibration in Phase 4 using CNY swaption market data.",
        related_standard="SOA ASOP 56 §3.4; SOA ASOP 25 §3.3",
        notes="Calibration scaffold complete (calibration_framework.py). Data sourcing required.",
        mitigation_status=MitigationStatus.OPEN,
    )

    # Record the seeding as a governance event
    store.audit_trail.append(
        AuditEntry.governance(
            actor="Claude-Actuarial-Agent",
            phase="Phase 2: Industry Standards Alignment",
            event="Initial risk register seeded from Phase 1 findings (8 entries)",
            details={
                "source_documents": [
                    "docs/MODEL_AUDIT_REPORT.md",
                    "docs/IA_GOVERNANCE_REQUIREMENTS.md",
                    "docs/SOA_ASSUMPTIONS_DOCUMENT.md",
                    "docs/VALIDATION_FRAMEWORK_REVIEW.md",
                ],
                "entries_created": 8,
                "critical_open": 0,
                "critical_in_progress": 4,
            },
        )
    )

    return store
