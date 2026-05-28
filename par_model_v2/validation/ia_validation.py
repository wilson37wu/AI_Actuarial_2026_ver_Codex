"""
IA TAS M §3.6 Validation Requirements Framework
================================================

Codifies the Institute and Faculty of Actuaries TAS M §3.6 validation
requirements as executable Python objects, enabling:

  1. Machine-readable requirement registry (not just a Word document)
  2. Structured tracking of pass/fail/not-yet-run status per requirement
  3. Aggregated compliance reports suitable for IA TAS M sign-off
  4. Integration with GovernanceStore / AuditTrail (audit_trail.py)

IA STANDARDS REFERENCES
------------------------
  TAS M 3.6.1 — Validation must be proportionate to model materiality
  TAS M 3.6.2 — Unit testing of individual model components
  TAS M 3.6.3 — Integration testing of assembled model
  TAS M 3.6.4 — Scenario adequacy — stochastic convergence evidence required
  TAS M 3.6.5 — Independent validation of material model components
  TAS M 3.8   — Sensitivity analysis as part of validation
  TAS M 3.9   — Data validation (inputs to the model)
  APS X2      — Peer review requirements for actuarial work products

SOA CROSS-REFERENCES
--------------------
  ASOP 56 §3.5  — Model testing: unit, integration, and scenario tests
  ASOP 7  §3.5  — Scenario selection and adequacy documentation
  ASOP 25 §3.6  — Assumption appropriateness validation

VALIDATION LAYERS (in order of execution)
------------------------------------------
  Layer 1 — Unit         : individual function / class correctness
  Layer 2 — Integration  : cross-module data flows and consistency
  Layer 3 — Stochastic   : ESG convergence, martingale test, fan charts
  Layer 4 — Sensitivity  : parameter shock impact, monotonicity checks
  Layer 5 — Backtest     : out-of-sample historical comparison
  Layer 6 — Governance   : audit trail completeness, sign-off status

DEVELOPMENT STATUS
------------------
Phase 2 — All requirement objects defined; check callables are stubs
          (return NOT_RUN) until the following blockers are resolved:
            - Distributed executor pickling bug (Phase 3)
            - ESG simulate() implementation (Phase 3)
            - Historical calibration data (Phase 4)
Phase 3 — Layer 1 and 2 checks implemented when bugs fixed
Phase 4 — Layers 3–5 implemented after ESG calibration complete
Phase 5 — Layer 6 (governance) sign-off and final report

PRODUCTION USE RESTRICTION
--------------------------
A ValidationReport with overall_status != ValidationStatus.PASS must not
be used for regulatory reporting, pricing decisions, or external disclosure.
"""

from __future__ import annotations

import enum
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# 0. Enums
# ---------------------------------------------------------------------------

class ValidationStatus(str, enum.Enum):
    """Outcome status for a single validation requirement.

    Attributes
    ----------
    PASS    : Requirement is met; evidence recorded.
    FAIL    : Requirement is not met; remediation required.
    PARTIAL : Requirement partially met; known gaps documented.
    NOT_RUN : Check not yet executed (stub or blocked dependency).
    WAIVED  : Requirement waived with documented justification (rare).
    """

    PASS    = "PASS"
    FAIL    = "FAIL"
    PARTIAL = "PARTIAL"
    NOT_RUN = "NOT_RUN"
    WAIVED  = "WAIVED"


class ValidationCategory(str, enum.Enum):
    """Validation layer classification per IA TAS M §3.6.

    Attributes
    ----------
    UNIT         : Individual component / function correctness.
    INTEGRATION  : Cross-module assembly and data-flow consistency.
    STOCHASTIC   : Scenario convergence, martingale test, fan charts.
    SENSITIVITY  : Parameter shock impact and monotonicity analysis.
    BACKTEST     : Historical out-of-sample comparison.
    GOVERNANCE   : Audit trail, sign-off workflow, and peer review.
    DATA         : Input data quality, schema, and range validation.
    """

    UNIT        = "Unit"
    INTEGRATION = "Integration"
    STOCHASTIC  = "Stochastic"
    SENSITIVITY = "Sensitivity"
    BACKTEST    = "Backtest"
    GOVERNANCE  = "Governance"
    DATA        = "Data"


class Severity(str, enum.Enum):
    """Materiality level of a validation requirement.

    Attributes
    ----------
    CRITICAL : Failure blocks production use and regulatory filing.
    HIGH     : Failure requires documented exception and senior sign-off.
    MEDIUM   : Failure requires remediation plan within next development phase.
    LOW      : Informational; addressed at next convenient opportunity.
    """

    CRITICAL = "Critical"
    HIGH     = "High"
    MEDIUM   = "Medium"
    LOW      = "Low"


# ---------------------------------------------------------------------------
# 1. Core Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ValidationRequirement:
    """A single IA TAS M §3.6 validation requirement.

    Parameters
    ----------
    req_id : str
        Unique identifier (e.g. "VR-001").
    name : str
        Short descriptive name.
    description : str
        Full description of what must be demonstrated.
    category : ValidationCategory
        Which validation layer this belongs to.
    severity : Severity
        Materiality of this requirement.
    ia_reference : str
        Primary IA TAS M (or ASOP) section reference.
    acceptance_criteria : list[str]
        Concrete, measurable conditions that constitute PASS.
    check_fn : Callable | None
        Optional callable ``() -> ValidationResult``.  If None, the
        requirement must be evaluated manually.
    development_phase : int
        Earliest project phase (1–5) when the check can be executed.
    notes : str
        Supplementary context, known blockers, or implementation notes.
    """

    req_id: str
    name: str
    description: str
    category: ValidationCategory
    severity: Severity
    ia_reference: str
    acceptance_criteria: List[str]
    check_fn: Optional[Callable[[], "ValidationResult"]] = field(
        default=None, repr=False
    )
    development_phase: int = 3
    notes: str = ""

    def run(self) -> "ValidationResult":
        """Execute the check function and return a ValidationResult.

        If no check_fn is registered, returns NOT_RUN with a note.
        """
        if self.check_fn is None:
            return ValidationResult(
                req_id=self.req_id,
                status=ValidationStatus.NOT_RUN,
                evidence="No automated check registered — manual evaluation required.",
                checked_at=datetime.now(timezone.utc),
                details={},
            )
        try:
            result = self.check_fn()
            # Ensure req_id is propagated from the requirement
            result.req_id = self.req_id
            return result
        except Exception as exc:  # noqa: BLE001
            return ValidationResult(
                req_id=self.req_id,
                status=ValidationStatus.FAIL,
                evidence=f"Check raised exception: {type(exc).__name__}: {exc}",
                checked_at=datetime.now(timezone.utc),
                details={"exception": str(exc)},
            )


@dataclass
class ValidationResult:
    """Outcome of running one ValidationRequirement.

    Parameters
    ----------
    req_id : str
        Matches the ValidationRequirement.req_id this result belongs to.
    status : ValidationStatus
        Outcome: PASS / FAIL / PARTIAL / NOT_RUN / WAIVED.
    evidence : str
        Human-readable description of the evidence supporting the status.
    checked_at : datetime
        UTC timestamp when the check was executed.
    details : dict
        Arbitrary key/value pairs — numeric metrics, file paths, etc.
    waiver_justification : str | None
        Required when status == WAIVED; documents the approved exception.
    """

    req_id: str
    status: ValidationStatus
    evidence: str
    checked_at: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    waiver_justification: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "req_id": self.req_id,
            "status": self.status.value,
            "evidence": self.evidence,
            "checked_at": self.checked_at.isoformat(),
            "details": self.details,
            "waiver_justification": self.waiver_justification,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationResult":
        """Deserialise from a dictionary (e.g., loaded from JSON)."""
        return cls(
            req_id=data["req_id"],
            status=ValidationStatus(data["status"]),
            evidence=data["evidence"],
            checked_at=datetime.fromisoformat(data["checked_at"]),
            details=data.get("details", {}),
            waiver_justification=data.get("waiver_justification"),
        )

    @property
    def is_passing(self) -> bool:
        """True if status is PASS or WAIVED."""
        return self.status in (ValidationStatus.PASS, ValidationStatus.WAIVED)

    @property
    def blocks_production(self) -> bool:
        """True if this result would block production use.

        A result blocks production when it is FAIL or PARTIAL for a
        CRITICAL-severity requirement.  NOT_RUN also blocks production
        because the requirement has not been demonstrated.
        """
        return self.status in (
            ValidationStatus.FAIL,
            ValidationStatus.PARTIAL,
            ValidationStatus.NOT_RUN,
        )


@dataclass
class ValidationReport:
    """Aggregated validation results for a model version.

    Parameters
    ----------
    model_name : str
        Name / identifier of the model being validated.
    model_version : str
        Version string (e.g. "2.0.0-phase2").
    generated_at : datetime
        UTC timestamp of report generation.
    results : list[ValidationResult]
        One ValidationResult per requirement checked.
    requirements : list[ValidationRequirement]
        The full requirement registry that was checked against.
    report_id : str
        UUID for this specific report instance.
    """

    model_name: str
    model_version: str
    generated_at: datetime
    results: List[ValidationResult]
    requirements: List[ValidationRequirement]
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------

    @property
    def total(self) -> int:
        """Total number of requirements."""
        return len(self.requirements)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.FAIL)

    @property
    def partial(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.PARTIAL)

    @property
    def not_run(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.NOT_RUN)

    @property
    def waived(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.WAIVED)

    @property
    def overall_status(self) -> ValidationStatus:
        """Aggregate status for the report.

        Rules (applied in order):
        1. Any FAIL      → overall FAIL
        2. Any PARTIAL or NOT_RUN → overall PARTIAL
        3. Any WAIVED (all others PASS) → overall PASS (waivers are approved)
        4. All PASS → overall PASS
        """
        statuses = {r.status for r in self.results}
        if ValidationStatus.FAIL in statuses:
            return ValidationStatus.FAIL
        if ValidationStatus.PARTIAL in statuses or ValidationStatus.NOT_RUN in statuses:
            return ValidationStatus.PARTIAL
        return ValidationStatus.PASS

    @property
    def critical_failures(self) -> List[Tuple[ValidationRequirement, ValidationResult]]:
        """Requirements of CRITICAL severity that are not PASS or WAIVED."""
        result_by_id = {r.req_id: r for r in self.results}
        return [
            (req, result_by_id[req.req_id])
            for req in self.requirements
            if req.severity == Severity.CRITICAL
            and req.req_id in result_by_id
            and not result_by_id[req.req_id].is_passing
        ]

    def results_by_category(self) -> Dict[ValidationCategory, List[ValidationResult]]:
        """Group results by ValidationCategory."""
        req_by_id = {req.req_id: req for req in self.requirements}
        grouped: Dict[ValidationCategory, List[ValidationResult]] = {
            cat: [] for cat in ValidationCategory
        }
        for result in self.results:
            req = req_by_id.get(result.req_id)
            if req:
                grouped[req.category].append(result)
        return grouped

    def compliance_pct(self, category: Optional[ValidationCategory] = None) -> float:
        """Percentage of requirements that are PASS or WAIVED.

        Parameters
        ----------
        category : ValidationCategory | None
            If specified, compute percentage for that category only.
        """
        if category is not None:
            cat_results = self.results_by_category().get(category, [])
            if not cat_results:
                return 0.0
            passing = sum(1 for r in cat_results if r.is_passing)
            return round(100.0 * passing / len(cat_results), 1)

        if not self.results:
            return 0.0
        passing = sum(1 for r in self.results if r.is_passing)
        return round(100.0 * passing / len(self.results), 1)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "report_id": self.report_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "generated_at": self.generated_at.isoformat(),
            "overall_status": self.overall_status.value,
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "partial": self.partial,
                "not_run": self.not_run,
                "waived": self.waived,
                "compliance_pct": self.compliance_pct(),
            },
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialise to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Generate a human-readable Markdown validation report.

        Suitable for inclusion in MODEL_DEV_LOG.md or a standalone file.
        """
        ts = self.generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        lines: List[str] = [
            f"# Validation Report — {self.model_name} v{self.model_version}",
            f"",
            f"**Report ID:** {self.report_id}  ",
            f"**Generated:** {ts}  ",
            f"**Overall Status:** {self.overall_status.value}  ",
            f"",
            f"## Summary",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total requirements | {self.total} |",
            f"| PASS | {self.passed} |",
            f"| FAIL | {self.failed} |",
            f"| PARTIAL | {self.partial} |",
            f"| NOT RUN | {self.not_run} |",
            f"| WAIVED | {self.waived} |",
            f"| Compliance % | {self.compliance_pct()}% |",
            f"",
        ]

        if self.critical_failures:
            lines += [
                "## ⚠️ Critical Failures",
                "",
            ]
            for req, result in self.critical_failures:
                lines.append(f"- **{req.req_id} — {req.name}**  ")
                lines.append(f"  Status: {result.status.value} | {result.evidence}")
            lines.append("")

        lines += ["## Results by Category", ""]
        req_by_id = {req.req_id: req for req in self.requirements}
        for cat, cat_results in self.results_by_category().items():
            if not cat_results:
                continue
            pct = self.compliance_pct(cat)
            lines.append(f"### {cat.value} ({pct}% compliant)")
            lines.append("")
            lines.append("| Req ID | Name | Status | Evidence |")
            lines.append("|--------|------|--------|----------|")
            for result in cat_results:
                req = req_by_id.get(result.req_id)
                name = req.name if req else "Unknown"
                evidence = result.evidence[:80] + "..." if len(result.evidence) > 80 else result.evidence
                lines.append(
                    f"| {result.req_id} | {name} | {result.status.value} | {evidence} |"
                )
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. Validation Runner
# ---------------------------------------------------------------------------

class ValidationRunner:
    """Executes a list of ValidationRequirements and produces a ValidationReport.

    Parameters
    ----------
    requirements : list[ValidationRequirement]
        The requirements to check.  Defaults to IA_VALIDATION_REQUIREMENTS.
    model_name : str
        Model name to embed in the report.
    model_version : str
        Model version string.
    skip_categories : list[ValidationCategory] | None
        Categories to skip (return NOT_RUN without executing).  Useful when
        some layers are blocked (e.g., skip STOCHASTIC until ESG is ready).
    """

    def __init__(
        self,
        requirements: Optional[List[ValidationRequirement]] = None,
        *,
        model_name: str = "PAR Fund Stochastic ALM & TVOG",
        model_version: str = "2.0.0",
        skip_categories: Optional[List[ValidationCategory]] = None,
    ) -> None:
        self.requirements = requirements if requirements is not None else IA_VALIDATION_REQUIREMENTS
        self.model_name = model_name
        self.model_version = model_version
        self.skip_categories = set(skip_categories or [])

    def run(self) -> ValidationReport:
        """Execute all requirements and return an aggregated ValidationReport.

        Requirements with ``check_fn=None`` return NOT_RUN automatically.
        Requirements in ``skip_categories`` are also returned as NOT_RUN with
        an appropriate note.

        Returns
        -------
        ValidationReport
            Full report with one ValidationResult per requirement.
        """
        results: List[ValidationResult] = []
        for req in self.requirements:
            if req.category in self.skip_categories:
                results.append(ValidationResult(
                    req_id=req.req_id,
                    status=ValidationStatus.NOT_RUN,
                    evidence=(
                        f"Category '{req.category.value}' skipped — "
                        f"blocked pending {_CATEGORY_BLOCKERS.get(req.category, 'dependency resolution')}"
                    ),
                    checked_at=datetime.now(timezone.utc),
                    details={"skipped_category": req.category.value},
                ))
            else:
                results.append(req.run())

        return ValidationReport(
            model_name=self.model_name,
            model_version=self.model_version,
            generated_at=datetime.now(timezone.utc),
            results=results,
            requirements=self.requirements,
        )

    def run_category(self, category: ValidationCategory) -> List[ValidationResult]:
        """Run only requirements in one category.

        Parameters
        ----------
        category : ValidationCategory
            The layer to execute.

        Returns
        -------
        list[ValidationResult]
        """
        return [
            req.run()
            for req in self.requirements
            if req.category == category
        ]


# Blockers message map — shown in NOT_RUN evidence when a category is skipped
_CATEGORY_BLOCKERS: Dict[ValidationCategory, str] = {
    ValidationCategory.STOCHASTIC: "ESG simulate() implementation (Phase 3)",
    ValidationCategory.BACKTEST:   "historical calibration data (Phase 4)",
    ValidationCategory.INTEGRATION: "distributed executor pickling fix (Phase 3)",
}


# ---------------------------------------------------------------------------
# 3. Requirement Registry — IA TAS M §3.6
# ---------------------------------------------------------------------------
#
# Each requirement maps to specific IA TAS M / ASOP sections.
# Acceptance criteria are concrete and measurable.
# check_fn is None for all requirements until the blocking dependency is fixed.
#
# COVERAGE:
#   Layer 1 — Unit         : VR-U01 to VR-U07
#   Layer 2 — Integration  : VR-I01 to VR-I04
#   Layer 3 — Stochastic   : VR-S01 to VR-S05
#   Layer 4 — Sensitivity  : VR-SE01 to VR-SE04
#   Layer 5 — Backtest     : VR-B01 to VR-B03
#   Layer 6 — Governance   : VR-G01 to VR-G05
#   Layer 7 — Data         : VR-D01 to VR-D03
#

IA_VALIDATION_REQUIREMENTS: List[ValidationRequirement] = [

    # ------------------------------------------------------------------ #
    # LAYER 1 — UNIT TESTING                                             #
    # ------------------------------------------------------------------ #

    ValidationRequirement(
        req_id="VR-U01",
        name="Monthly Projection Unit Tests — 100% Pass",
        description=(
            "The monthly projection engine (par_model_v2/projection/) must "
            "have a unit test suite covering all core functions with 100% pass "
            "rate.  Tests must be parametrized across all valid policy terms."
        ),
        category=ValidationCategory.UNIT,
        severity=Severity.CRITICAL,
        ia_reference="TAS M 3.6.2",
        acceptance_criteria=[
            "All projection unit tests pass (0 failures)",
            "Tests parametrized across 5Y, 10Y, 20Y policy terms",
            "Mathematical identities (UDD, monthly compounding) verified numerically",
            "Sign constraints enforced (non-negative in-force, asset share EOM ≥ 0)",
            "Null-value assertions on all output DataFrames",
        ],
        development_phase=2,
        notes=(
            "62/62 tests passing as of Phase 1 review.  Maintains PASS status. "
            "check_fn not registered — test suite must be run externally via pytest."
        ),
    ),

    ValidationRequirement(
        req_id="VR-U02",
        name="ALM Engine Unit Tests — Rebalancing Bug Fixed",
        description=(
            "The DynamicALMEngine (par_model_v2/projection/dynamic_alm.py) must "
            "pass all 11 unit tests, including test_rebalancing_to_saa which "
            "currently fails due to the 100%-cash initial portfolio bug."
        ),
        category=ValidationCategory.UNIT,
        severity=Severity.CRITICAL,
        ia_reference="TAS M 3.6.2",
        acceptance_criteria=[
            "All 11 ALM unit tests pass (0 failures)",
            "test_rebalancing_to_saa passes: buys are triggered when holdings < SAA target",
            "Rebalancing from 100%-cash correctly allocates to bond and equity targets",
            "Transaction cost logic verified numerically for buy and sell transactions",
        ],
        development_phase=3,
        notes=(
            "1 known failure (test_rebalancing_to_saa) as of Phase 1.  "
            "Root cause: buy-trigger absent when holdings below SAA target.  "
            "Fix scheduled for Phase 3."
        ),
    ),

    ValidationRequirement(
        req_id="VR-U03",
        name="Risk Metrics Unit Tests — VaR/ES Correctness",
        description=(
            "par_model_v2/risk/risk_metrics.py must pass all VaR/ES unit tests, "
            "including cross-checks against scipy.stats analytical values."
        ),
        category=ValidationCategory.UNIT,
        severity=Severity.HIGH,
        ia_reference="TAS M 3.6.2; ASOP 56 §3.5",
        acceptance_criteria=[
            "All risk_metrics tests pass",
            "Empirical VaR matches scipy.stats.norm.ppf within 2% for N=10,000",
            "Empirical ES ≥ empirical VaR at all confidence levels",
            "Reliability warnings triggered when N < minimum threshold",
            "Q-measure input raises UserWarning",
        ],
        development_phase=2,
        notes="Tests implemented in tests/test_risk_metrics.py.",
    ),

    ValidationRequirement(
        req_id="VR-U04",
        name="Stress Testing Unit Tests — CBIRC Scenario Coverage",
        description=(
            "par_model_v2/risk/stress_testing.py must pass all stress testing "
            "unit tests, confirming CBIRC and SOA ASOP 7 scenario completeness."
        ),
        category=ValidationCategory.UNIT,
        severity=Severity.HIGH,
        ia_reference="TAS M 3.6.2; ASOP 7 §3.5",
        acceptance_criteria=[
            "All stress_testing tests pass",
            "ALL_SCENARIOS contains at least 15 distinct scenarios",
            "CBIRC_SCENARIOS contains all 6 prescribed CBIRC C-ROSS tests",
            "Surplus impact correctly negative (surplus falls) for adverse shocks",
            "Solvency ratio computed as assets / liabilities in result",
        ],
        development_phase=2,
        notes="Tests implemented in tests/test_stress_testing.py.",
    ),

    ValidationRequirement(
        req_id="VR-U05",
        name="Governance/Audit Trail Unit Tests",
        description=(
            "par_model_v2/governance/audit_trail.py must pass all unit tests, "
            "covering AuditTrail, ChangeRecord, SignOffWorkflow, and ModelRiskRegister."
        ),
        category=ValidationCategory.UNIT,
        severity=Severity.MEDIUM,
        ia_reference="TAS M 3.6.2; TAS M 3.3; TAS M 3.7",
        acceptance_criteria=[
            "All governance tests pass",
            "AuditTrail entries are immutable (append-only)",
            "SHA-256 digest verified on each audit entry",
            "SignOff state machine enforces PENDING → REVIEWED → APPROVED ordering",
            "ModelRiskRegister serialises and deserialises without data loss",
        ],
        development_phase=2,
        notes="Tests implemented in tests/test_governance.py.",
    ),

    ValidationRequirement(
        req_id="VR-U06",
        name="ESGAdapter Unit Tests — Data Loading and Validation",
        description=(
            "ESGAdapter (reads Moody's CNY ESG files) must have unit tests "
            "covering valid file load, malformed-column handling, missing-file "
            "error, and scenario count below minimum threshold."
        ),
        category=ValidationCategory.UNIT,
        severity=Severity.HIGH,
        ia_reference="TAS M 3.6.2; TAS M 3.9",
        acceptance_criteria=[
            "Valid ESG file loads without error and returns correct DataFrame shape",
            "Malformed column names raise descriptive ValidationError",
            "Missing file raises FileNotFoundError with path in message",
            "Scenario count < 500 raises ScenarioAdequacyWarning",
            "Scenario count checked against ASOP 56 §3.5 minimum table",
        ],
        development_phase=3,
        notes=(
            "No tests exist for ESGAdapter as of Phase 1 review.  "
            "Blocked on GBM sample ESG generator (Phase 4) for test fixtures.  "
            "Phase 3 will use a minimal synthetic fixture."
        ),
    ),

    ValidationRequirement(
        req_id="VR-U07",
        name="HybridGrid Unit Tests — Boundary Conditions",
        description=(
            "HybridGrid (liability projection grid) must have unit tests "
            "confirming correct boundary handling, grid shape, and interpolation."
        ),
        category=ValidationCategory.UNIT,
        severity=Severity.MEDIUM,
        ia_reference="TAS M 3.6.2",
        acceptance_criteria=[
            "Grid shape matches expected (term × age × scenario) dimensions",
            "Boundary cells (age=0, final projection month) return correct values",
            "Interpolation between grid nodes is monotone where expected",
            "Zero premium / zero sum assured inputs handled without NaN output",
        ],
        development_phase=3,
        notes="No tests exist for HybridGrid as of Phase 1.  Phase 3 target.",
    ),

    # ------------------------------------------------------------------ #
    # LAYER 2 — INTEGRATION TESTING                                      #
    # ------------------------------------------------------------------ #

    ValidationRequirement(
        req_id="VR-I01",
        name="End-to-End Projection Integration Test",
        description=(
            "A full pipeline run from assumption tables → liability cashflows → "
            "asset cashflows → asset share → TVOG must complete without error "
            "and produce numerically reasonable output."
        ),
        category=ValidationCategory.INTEGRATION,
        severity=Severity.CRITICAL,
        ia_reference="TAS M 3.6.3",
        acceptance_criteria=[
            "Pipeline runs end-to-end without exception",
            "Final TVOG output is a positive scalar (PV of guarantees > 0)",
            "Asset share EOM positive throughout projection",
            "Asset-liability cashflow conservation: sum(assets) ≈ sum(liabilities) within 1%",
            "Tested across at least 3 policy terms (5Y, 10Y, 20Y)",
        ],
        development_phase=3,
        notes=(
            "Blocked by: (1) distributed executor pickling bug, "
            "(2) ESG simulate() not implemented.  "
            "Deterministic fallback test using stub ESG can be added in Phase 3."
        ),
    ),

    ValidationRequirement(
        req_id="VR-I02",
        name="Distributed Executor Integration Test",
        description=(
            "DistributedExecutor must run batch scenario jobs without pickling "
            "errors and produce identical results to sequential execution."
        ),
        category=ValidationCategory.INTEGRATION,
        severity=Severity.CRITICAL,
        ia_reference="TAS M 3.6.3; ASOP 56 §3.5",
        acceptance_criteria=[
            "All 7 distributed executor tests pass (currently 7 fail)",
            "Batch run of 100 scenarios matches single-process output within floating-point tolerance",
            "Checkpoint/restart preserves all completed scenario results",
            "Pickling error no longer raised for module-level callables",
        ],
        development_phase=3,
        notes=(
            "Root cause: locally-scoped lambdas passed as process_func.  "
            "Fix: replace with module-level callable or functools.partial.  "
            "Phase 3 priority fix."
        ),
    ),

    ValidationRequirement(
        req_id="VR-I03",
        name="Governance Integration — Audit Events on Model Run",
        description=(
            "Every model run must emit at least one AuditTrail event capturing "
            "run timestamp, parameter snapshot, and scenario count."
        ),
        category=ValidationCategory.INTEGRATION,
        severity=Severity.MEDIUM,
        ia_reference="TAS M 3.6.3; TAS M 3.3",
        acceptance_criteria=[
            "AuditTrail.log() called on every projection run",
            "Event contains: run_id, timestamp, model_version, n_scenarios, measure (P/Q)",
            "SHA-256 digest matches entry content",
            "GovernanceStore persists audit log to JSON without data loss",
        ],
        development_phase=3,
        notes="GovernanceStore implemented in Phase 2.  Integration wiring deferred to Phase 3.",
    ),

    ValidationRequirement(
        req_id="VR-I04",
        name="Risk Metrics Integration — VaR/ES on Live Scenario Output",
        description=(
            "RiskMetrics must be computable from live ScenarioSet output "
            "(not just synthetic test data), producing a VaR_995 estimate "
            "with reliability flag set correctly."
        ),
        category=ValidationCategory.INTEGRATION,
        severity=Severity.HIGH,
        ia_reference="TAS M 3.6.3; ASOP 7 §3.3",
        acceptance_criteria=[
            "LossDistribution.from_scenario_pv() works on ScenarioSet output",
            "VaR_995 computed for N ≥ 2,000 scenarios",
            "Reliability flag = True when N ≥ 2,000",
            "Results stored in GovernanceStore for audit trail",
        ],
        development_phase=3,
        notes="Blocked by ESG simulate().  Phase 3 stub can use synthetic scenarios.",
    ),

    # ------------------------------------------------------------------ #
    # LAYER 3 — STOCHASTIC VALIDATION                                    #
    # ------------------------------------------------------------------ #

    ValidationRequirement(
        req_id="VR-S01",
        name="Scenario Convergence Test — TVOG Stability",
        description=(
            "TVOG estimate must converge as N → ∞.  Run at N = 100, 500, "
            "1,000, 5,000 scenarios and verify that relative change < 1% "
            "between N=2,000 and N=5,000."
        ),
        category=ValidationCategory.STOCHASTIC,
        severity=Severity.CRITICAL,
        ia_reference="TAS M 3.6.4; ASOP 56 §3.5",
        acceptance_criteria=[
            "TVOG(5000) − TVOG(2000) / TVOG(5000) < 1%",
            "Convergence plot saved to docs/validation/convergence_tvog.png",
            "Standard error at N=5,000 < 0.5% of mean TVOG",
            "Minimum scenario count for regulatory use set to 5,000 and documented",
        ],
        development_phase=4,
        notes="Requires ESG simulate() (Phase 3) and calibrated parameters (Phase 4).",
    ),

    ValidationRequirement(
        req_id="VR-S02",
        name="Martingale Test — Risk-Neutral Scenario Adequacy",
        description=(
            "Q-measure scenarios must pass the martingale (asset pricing) test: "
            "E_Q[B(T)] = B(0) * e^(rT) where B is the bank account numeraire."
        ),
        category=ValidationCategory.STOCHASTIC,
        severity=Severity.CRITICAL,
        ia_reference="TAS M 3.6.4; ASOP 56 §3.1.3",
        acceptance_criteria=[
            "Martingale discrepancy |E_Q[e^(-rT) * S(T)] / S(0) − 1| < 0.1%",
            "Test run at T = 1, 5, 10, 20 years",
            "Test results documented in docs/validation/martingale_test_results.md",
            "Failed martingale → scenarios rejected and ESG re-calibrated before TVOG use",
        ],
        development_phase=4,
        notes="Requires Q-measure ESG simulation.  Phase 4 target.",
    ),

    ValidationRequirement(
        req_id="VR-S03",
        name="Scenario Fan Chart — Percentile Reasonableness",
        description=(
            "P-measure and Q-measure scenario fan charts (5th, 25th, 50th, "
            "75th, 95th percentiles) must be produced and reviewed for "
            "actuarial reasonableness."
        ),
        category=ValidationCategory.STOCHASTIC,
        severity=Severity.HIGH,
        ia_reference="TAS M 3.6.4; TAS M 3.8",
        acceptance_criteria=[
            "Fan charts produced for: short rate, equity index, bond yield",
            "Median P-measure equity path consistent with long-run equity risk premium (3–5%)",
            "Q-measure median rate path consistent with initial yield curve",
            "Fan charts reviewed and signed off by model developer",
        ],
        development_phase=4,
        notes="Requires ESG simulate().  Phase 4 output.",
    ),

    ValidationRequirement(
        req_id="VR-S04",
        name="P / Q Measure Segregation Test",
        description=(
            "Every scenario-consuming component must correctly enforce the "
            "Measure enum.  Passing Q-measure scenarios to VaR/ES must raise "
            "ValueError; passing P-measure to TVOG must raise ValueError."
        ),
        category=ValidationCategory.STOCHASTIC,
        severity=Severity.CRITICAL,
        ia_reference="ASOP 56 §3.1.3; ESG_PROCESS_DOCUMENTATION.md §2.2",
        acceptance_criteria=[
            "ValueError raised when Measure.Q passed to RiskMetrics",
            "ValueError raised when Measure.P passed to TVOG engine",
            "Measure type verified via isinstance check at every ScenarioSet consumer",
            "No silent measure mismatches possible in production code paths",
        ],
        development_phase=3,
        notes="Production validation must confirm every consumer hard-fails on measure mismatches.",
    ),

    ValidationRequirement(
        req_id="VR-S05",
        name="Hull-White Calibration Stability Test",
        description=(
            "HW1F parameters (alpha, sigma) calibrated to historical CNY rate "
            "data must be stable across rolling calibration windows."
        ),
        category=ValidationCategory.STOCHASTIC,
        severity=Severity.HIGH,
        ia_reference="ASOP 56 §3.1.3; docs/PARAMETER_CALIBRATION_METHODOLOGY.md",
        acceptance_criteria=[
            "Mean-reversion speed alpha in [0.02, 0.30] — actuarially plausible range",
            "Volatility sigma in [0.001, 0.020] — consistent with CNY rate history",
            "Rolling-window coefficient of variation (CV) for alpha < 20%",
            "Calibration stability documented in docs/PARAMETER_CALIBRATION_METHODOLOGY.md",
        ],
        development_phase=4,
        notes="Requires historical CNY rate data and ESG calibration routine (Phase 4).",
    ),

    # ------------------------------------------------------------------ #
    # LAYER 4 — SENSITIVITY ANALYSIS                                     #
    # ------------------------------------------------------------------ #

    ValidationRequirement(
        req_id="VR-SE01",
        name="Discount Rate Sensitivity — TVOG Impact",
        description=(
            "TVOG must be computed at ±50bps and ±100bps shifts of the "
            "discount rate.  Results must show expected monotonicity: "
            "lower discount rate → higher TVOG."
        ),
        category=ValidationCategory.SENSITIVITY,
        severity=Severity.HIGH,
        ia_reference="TAS M 3.8; ASOP 7 §3.5; docs/SOA_ASSUMPTIONS_DOCUMENT.md §3.3",
        acceptance_criteria=[
            "TVOG(r−100bps) > TVOG(r−50bps) > TVOG(base) > TVOG(r+50bps) > TVOG(r+100bps)",
            "Sensitivity table produced with absolute and % TVOG change",
            "CBIRC 3.0% cap scenario included (discount rate = 3.0% vs current 3.5%)",
            "Results documented in docs/validation/sensitivity_discount_rate.md",
        ],
        development_phase=4,
        notes=(
            "Critical for regulatory compliance: current 3.5% discount rate exceeds "
            "CBIRC 3.0% cap.  Sensitivity run at 3.0% will quantify the regulatory gap."
        ),
    ),

    ValidationRequirement(
        req_id="VR-SE02",
        name="Lapse Rate Sensitivity — Dynamic Lapse Impact",
        description=(
            "TVOG must be tested with static lapse (current) and with a "
            "dynamic lapse function (interest-rate-dependent).  The sensitivity "
            "must be bounded and documented."
        ),
        category=ValidationCategory.SENSITIVITY,
        severity=Severity.CRITICAL,
        ia_reference="TAS M 3.8; ASOP 7 §3.5; docs/SOA_ASSUMPTIONS_DOCUMENT.md §3.4",
        acceptance_criteria=[
            "TVOG with dynamic lapse computed and compared to static baseline",
            "Lapse shock ±25% applied; TVOG impact within ±15–30% as estimated",
            "Mass lapse stress scenario (50% shock) included",
            "Dynamic lapse sensitivity documented and signed off",
        ],
        development_phase=4,
        notes=(
            "Dynamic lapse is the single most critical missing assumption for TVOG.  "
            "Estimated TVOG sensitivity: ±15–30% per ±25% lapse shock.  "
            "Material gap vs ASOP 7 requirements."
        ),
    ),

    ValidationRequirement(
        req_id="VR-SE03",
        name="Investment Return Sensitivity — Bond / Equity Shock",
        description=(
            "Asset cashflows and TVOG must be tested under bond yield and "
            "equity return shocks consistent with CBIRC C-ROSS stress tests."
        ),
        category=ValidationCategory.SENSITIVITY,
        severity=Severity.HIGH,
        ia_reference="TAS M 3.8; CBIRC C-ROSS stress test requirements",
        acceptance_criteria=[
            "Bond yield +200bps shock: asset value change quantified",
            "Equity −40% shock: asset value change quantified",
            "TVOG change under each shock reported",
            "Results consistent with StressTestEngine stress_testing.py outputs",
        ],
        development_phase=4,
        notes="StressTestEngine (Phase 2) provides duration-approximation results.  Phase 4 re-projection needed.",
    ),

    ValidationRequirement(
        req_id="VR-SE04",
        name="Mortality Sensitivity — Longevity Shock",
        description=(
            "Project impact of ±10% mortality shock on liability cashflows "
            "and TVOG.  Required for ASOP 25 assumption sensitivity."
        ),
        category=ValidationCategory.SENSITIVITY,
        severity=Severity.MEDIUM,
        ia_reference="TAS M 3.8; ASOP 25 §3.6",
        acceptance_criteria=[
            "Mortality +10% shock: liability PV change quantified",
            "Mortality −10% shock: liability PV change quantified",
            "Impact monetised in absolute CNY terms",
            "Results compared against Gompertz parameter uncertainty range",
        ],
        development_phase=4,
        notes="Mortality assumption documented; calibration uncertainty quantified in Phase 1 docs.",
    ),

    # ------------------------------------------------------------------ #
    # LAYER 5 — BACKTESTING                                              #
    # ------------------------------------------------------------------ #

    ValidationRequirement(
        req_id="VR-B01",
        name="Asset Return Backtest — 5Y Rolling Window",
        description=(
            "Calibrated GBM equity and HW1F rate parameters must produce "
            "scenario distributions that bracket observed historical CNY asset "
            "returns in 5-year rolling windows."
        ),
        category=ValidationCategory.BACKTEST,
        severity=Severity.HIGH,
        ia_reference="ASOP 56 §3.5; docs/PARAMETER_CALIBRATION_METHODOLOGY.md",
        acceptance_criteria=[
            "Observed CNY equity return falls within [5th, 95th] percentile of P-measure scenarios",
            "Observed CNY bond yield falls within [5th, 95th] percentile in ≥ 80% of windows",
            "Backtest period: 2015–2025 (10 years)",
            "Backtest report produced: docs/validation/backtest_asset_returns.md",
        ],
        development_phase=4,
        notes="Requires historical CNY financial data (Phase 4 data collection).",
    ),

    ValidationRequirement(
        req_id="VR-B02",
        name="Liability Cashflow Backtest — Monthly Projection",
        description=(
            "Monthly projection cashflows must be compared against any available "
            "historical fund experience data to validate calibration of lapse, "
            "mortality, and bonus assumptions."
        ),
        category=ValidationCategory.BACKTEST,
        severity=Severity.MEDIUM,
        ia_reference="ASOP 25 §3.6; TAS M 3.6.4",
        acceptance_criteria=[
            "At least 3 years of historical inforce data used for comparison",
            "Projected vs actual lapse rates compared; A/E ratio within [85%, 115%]",
            "Projected vs actual mortality rates compared; A/E ratio within [85%, 115%]",
            "Residual analysis: no systematic bias across age bands",
        ],
        development_phase=4,
        notes="Dependent on availability of historical PAR fund experience data.",
    ),

    ValidationRequirement(
        req_id="VR-B03",
        name="VaR/ES Backtest — Exception Frequency",
        description=(
            "Historical VaR exceptions (days loss > VaR_95 estimate) must "
            "fall within the expected binomial range for the confidence level."
        ),
        category=ValidationCategory.BACKTEST,
        severity=Severity.MEDIUM,
        ia_reference="ERM Framework; ASOP 7 §3.3",
        acceptance_criteria=[
            "VaR_95 exception rate: 4%–6% of observations (binomial 95% CI)",
            "VaR_99 exception rate: 0.5%–1.5% of observations",
            "Kupiec POF test p-value > 0.05 at 95% confidence level",
            "Backtest period ≥ 250 trading days",
        ],
        development_phase=4,
        notes="Requires historical P&L data and calibrated model output for same period.",
    ),

    # ------------------------------------------------------------------ #
    # LAYER 6 — GOVERNANCE                                               #
    # ------------------------------------------------------------------ #

    ValidationRequirement(
        req_id="VR-G01",
        name="AuditTrail — All Production Runs Logged",
        description=(
            "Every production model run must generate an AuditTrail entry "
            "in GovernanceStore.  Entries must be immutable and SHA-256 digested."
        ),
        category=ValidationCategory.GOVERNANCE,
        severity=Severity.CRITICAL,
        ia_reference="TAS M 3.3; TAS M 3.7",
        acceptance_criteria=[
            "AuditTrail.log() called on every run with: run_id, timestamp, parameters, n_scenarios, measure",
            "SHA-256 digest verified on load (tamper detection)",
            "Audit log persisted to .claude-dev/GOVERNANCE_STORE.json after each run",
            "No audit log purging in production code paths",
        ],
        development_phase=3,
        notes="AuditTrail implemented in Phase 2.  Wiring into run loop scheduled for Phase 3.",
    ),

    ValidationRequirement(
        req_id="VR-G02",
        name="Model Change Control — ChangeRecord for All Breaking Changes",
        description=(
            "Any change to model parameters, formulae, or structure must "
            "generate a ChangeRecord per IA TAS M §3.7 before being applied."
        ),
        category=ValidationCategory.GOVERNANCE,
        severity=Severity.HIGH,
        ia_reference="TAS M 3.7",
        acceptance_criteria=[
            "ChangeRecord created for: parameter updates, formula changes, assumption revisions",
            "ChangeRecord includes: before/after snapshot, impact assessment, approver",
            "ChangeRecord status progresses: DRAFT → PEER_REVIEW → APPROVED → APPLIED",
            "No parameter change applied without APPROVED ChangeRecord on record",
        ],
        development_phase=3,
        notes="ChangeRecord class implemented in Phase 2.  Process adoption required in Phase 3.",
    ),

    ValidationRequirement(
        req_id="VR-G03",
        name="Peer Review — APS X2 Sign-Off on Material Work Products",
        description=(
            "Material actuarial work products (TVOG estimate, VaR/ES report, "
            "calibration report) must have a documented peer review per APS X2."
        ),
        category=ValidationCategory.GOVERNANCE,
        severity=Severity.HIGH,
        ia_reference="APS X2; TAS M 3.6.5",
        acceptance_criteria=[
            "SignOffWorkflow record exists for each material output",
            "Reviewer is independent of the model developer",
            "Signed-off outputs reference the specific ValidationReport report_id",
            "Sign-off date and reviewer name recorded in GovernanceStore",
        ],
        development_phase=5,
        notes="SignOffWorkflow implemented in Phase 2.  APS X2 sign-off required at Phase 5 delivery.",
    ),

    ValidationRequirement(
        req_id="VR-G04",
        name="Model Risk Register — All Risks Rated and Mitigated",
        description=(
            "The ModelRiskRegister must contain all risks identified in Phase 1 "
            "(8 initial risks) and be maintained throughout development."
        ),
        category=ValidationCategory.GOVERNANCE,
        severity=Severity.MEDIUM,
        ia_reference="IFoA Modelling Practice Note §4",
        acceptance_criteria=[
            "At least 8 risks present (seeded from Phase 1 audit)",
            "Each risk has: description, likelihood, impact, owner, mitigation, status",
            "All CRITICAL risks have mitigation plans with target dates",
            "Risk register reviewed and updated each development phase",
        ],
        development_phase=3,
        notes="ModelRiskRegister initialised with 8 risks in Phase 2.",
    ),

    ValidationRequirement(
        req_id="VR-G05",
        name="Validation Report — Final Sign-Off Before Production Use",
        description=(
            "A complete ValidationReport (this framework) must be generated, "
            "reviewed, and signed off before any model output is used for "
            "regulatory reporting or pricing."
        ),
        category=ValidationCategory.GOVERNANCE,
        severity=Severity.CRITICAL,
        ia_reference="TAS M 3.6; APS X2",
        acceptance_criteria=[
            "ValidationReport.overall_status == ValidationStatus.PASS",
            "No CRITICAL-severity requirements in FAIL or NOT_RUN state",
            "Report signed off by: model developer + independent validator",
            "Report archived with date, signatories, and model_version",
        ],
        development_phase=5,
        notes="This requirement is satisfied when all other CRITICAL requirements are PASS.",
    ),

    # ------------------------------------------------------------------ #
    # LAYER 7 — DATA VALIDATION                                          #
    # ------------------------------------------------------------------ #

    ValidationRequirement(
        req_id="VR-D01",
        name="ESG Input Data — Schema and Range Validation on Load",
        description=(
            "ESGAdapter must validate the Moody's CNY ESG file against the "
            "expected schema (column names, dtypes, value ranges) on every load."
        ),
        category=ValidationCategory.DATA,
        severity=Severity.HIGH,
        ia_reference="TAS M 3.9",
        acceptance_criteria=[
            "Column names validated against expected schema on load",
            "Short rate paths: all values in [−0.02, 0.15] (plausible CNY range)",
            "Equity index paths: all values > 0 (no negative prices)",
            "Scenario count ≥ 500 before accepting file for production",
            "Validation error message includes field name, observed value, and expected range",
        ],
        development_phase=3,
        notes="No data validation on ESGAdapter as of Phase 1.  Phase 3 target.",
    ),

    ValidationRequirement(
        req_id="VR-D02",
        name="Inforce Data — Model Point Validation",
        description=(
            "Model points (par_model_v2/model_points/) must be validated on "
            "load: no nulls, age > 0, sum assured > 0, term ∈ {5, 10, 20}."
        ),
        category=ValidationCategory.DATA,
        severity=Severity.HIGH,
        ia_reference="TAS M 3.9",
        acceptance_criteria=[
            "No null values in any required field",
            "Issue age: 18 ≤ age ≤ 70",
            "Sum assured > 0 for all records",
            "Term ∈ {5, 10, 20} — reject any other value with clear error",
            "Count of rejected records logged to AuditTrail",
        ],
        development_phase=3,
        notes="ModelPoints module exists; no input validation as of Phase 1.",
    ),

    ValidationRequirement(
        req_id="VR-D03",
        name="Assumption Tables — Range and Completeness Validation",
        description=(
            "FlexibleAssumptions tables must be validated for completeness "
            "(all required policy/product/term combinations present) and "
            "for value plausibility."
        ),
        category=ValidationCategory.DATA,
        severity=Severity.MEDIUM,
        ia_reference="TAS M 3.9; ASOP 25 §3.4",
        acceptance_criteria=[
            "All required (product, policy_year, sex) combinations present",
            "Lapse rates: 0 ≤ lapse ≤ 1 for all entries",
            "Mortality qx: 0 ≤ qx ≤ 1 for all entries",
            "Bonus rates: 0 ≤ bonus ≤ 0.20 (max 20% annual bonus)",
            "Completeness check: warn if any fallback lookup triggered during projection",
        ],
        development_phase=3,
        notes="21/21 assumption unit tests passing.  Range validation checks not yet present.",
    ),
]
