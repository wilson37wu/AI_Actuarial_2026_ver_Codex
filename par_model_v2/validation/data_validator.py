"""
Model Point and Assumption Table Data Validation
=================================================

Implements schema, range, and consistency checks for the two primary input
categories of the PAR stochastic ALM model:

  1. **Model Point Tables** — one row per policy; columns for age, gender,
     term, sum_assured, premium, and optional policy metadata.
  2. **Assumption Tables** — tabular or scalar assumptions: mortality (qx by
     age / gender), lapse rates (by policy year), and discount rate.

Validation is structured as a pipeline of *checks*, each returning a
``CheckResult``.  A ``ValidationReport`` aggregates all results and provides
a pass/fail summary suitable for embedding in a GovernanceStore AuditEntry
(IA TAS M §3.9 / SOA ASOP 56 §3.5 compliance).

INDUSTRY STANDARDS REFERENCES
------------------------------
  IA TAS M §3.9   — Data validation: inputs to the model must be checked for
                    completeness, plausibility, and consistency before use.
  SOA ASOP 56 §3.5 — Model testing includes checking input data for
                     reasonableness and consistency.
  SOA ASOP 25 §3.3 — Assumption appropriateness: assumptions must be reviewed
                     for reasonableness and internal consistency.
  ERM principle    — Garbage-in / garbage-out: tail risk metrics are only
                     meaningful when built on validated input data.

VALIDATION LAYERS (VR-D02: data validation)
-------------------------------------------
  Layer D1 — Schema   : required columns present, correct dtype
  Layer D2 — Range    : values within actuarially plausible bounds
  Layer D3 — Consistency : cross-field logic (e.g. premium < sum_assured)
  Layer D4 — Completeness: no NaN / null in required fields
  Layer D5 — Uniqueness  : no duplicate policy IDs (if present)

DEVELOPMENT STATUS
------------------
Phase 3, Task 6 — Full implementation.
  VR-D02: ModelPointValidator  — IMPLEMENTED
  VR-D03: MortalityTableValidator — IMPLEMENTED
  VR-D04: LapseTableValidator  — IMPLEMENTED
  VR-D05: DiscountRateValidator — IMPLEMENTED
  GovernanceStore integration  — IMPLEMENTED (emit_to_governance_store())
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 0. Result primitives
# ---------------------------------------------------------------------------

class CheckSeverity(str, enum.Enum):
    """Severity level for a validation check failure."""
    ERROR   = "ERROR"    # hard stop — data cannot be used
    WARNING = "WARNING"  # soft issue — model may proceed with caution
    INFO    = "INFO"     # informational only


@dataclass
class CheckResult:
    """Outcome of a single validation check.

    Attributes
    ----------
    check_id : str
        Short machine-readable identifier (e.g. ``"D1-01"``).
    description : str
        Human-readable description of what was checked.
    passed : bool
        True when the check did not find any violation.
    severity : CheckSeverity
        Severity of the check (only relevant when passed=False).
    details : str, optional
        Additional context — e.g. offending row indices or out-of-range values.
    """
    check_id: str
    description: str
    passed: bool
    severity: CheckSeverity = CheckSeverity.ERROR
    details: str = ""

    def __repr__(self) -> str:
        status = "PASS" if self.passed else f"FAIL[{self.severity.value}]"
        return f"CheckResult({self.check_id}, {status}: {self.description})"


@dataclass
class ValidationReport:
    """Aggregated result of a complete validation run.

    Attributes
    ----------
    validator_name : str
        Name of the validator that produced this report.
    checks : list[CheckResult]
        All individual check outcomes.
    passed : bool
        True only if every ERROR-severity check passed (WARNINGs do not fail).
    error_count : int
    warning_count : int
    info_count : int
    """
    validator_name: str
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == CheckSeverity.ERROR)

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and c.severity == CheckSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and c.severity == CheckSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and c.severity == CheckSeverity.INFO)

    @property
    def total_checks(self) -> int:
        return len(self.checks)

    @property
    def passed_checks(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed_checks(self) -> List[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"{self.validator_name}: {status} "
            f"({self.passed_checks}/{self.total_checks} checks passed; "
            f"{self.error_count} errors, {self.warning_count} warnings)"
        )

    def emit_to_governance_store(
        self,
        governance_store: Any,
        actor: str = "Claude-Actuarial-Agent",
        phase: str = "Phase 3: Model Validation & Testing",
    ) -> None:
        """Append a VALIDATION AuditEntry to *governance_store*.

        Parameters
        ----------
        governance_store : GovernanceStore
            Live governance store instance.
        actor : str
            Identity of the agent or user performing validation.
        phase : str
            Current development phase (written into the audit entry).

        IA TAS M §3.9 compliance note
        ------------------------------
        Data validation events must be recorded in the audit trail before
        model results are consumed.  Call this method immediately after
        ``validate()`` and before passing data to any projection engine.
        """
        from par_model_v2.governance.audit_trail import AuditEntry

        failed_descriptions = [
            f"[{c.check_id}] {c.description}: {c.details}" if c.details
            else f"[{c.check_id}] {c.description}"
            for c in self.failed_checks
        ]

        entry = AuditEntry.validation(
            actor=actor,
            phase=phase,
            test_suite=self.validator_name,
            tests_run=self.total_checks,
            tests_passed=self.passed_checks,
            tests_failed=len(self.failed_checks),
            outcome="PASS" if self.passed else "FAIL",
            failed_tests=failed_descriptions if failed_descriptions else None,
        )
        governance_store.audit_trail.append(entry)


# ---------------------------------------------------------------------------
# 1. Model Point Validator
# ---------------------------------------------------------------------------

# Actuarially plausible bounds for model point fields
_MP_AGE_MIN         = 18      # minimum issue age
_MP_AGE_MAX         = 65      # maximum issue age (product eligibility)
_MP_TERM_VALID      = {5, 10, 20}
_MP_SUM_ASSURED_MIN = 1_000.0
_MP_SUM_ASSURED_MAX = 10_000_000.0
_MP_PREMIUM_MIN_PCT = 0.001   # premium >= 0.1% of sum_assured (anti-abuse)
_MP_PREMIUM_MAX_PCT = 0.50    # premium <= 50% of sum_assured
_MP_GENDERS         = {"M", "F", "m", "f", "Male", "Female", "male", "female"}


class ModelPointValidator:
    """Validates a model point table (DataFrame or list of dicts).

    Required columns
    ----------------
    ``age``         : int, issue age of the policyholder
    ``gender``      : str, "M" or "F" (case-insensitive)
    ``term_years``  : int, policy term in years (must be 5, 10, or 20)
    ``sum_assured`` : float, guaranteed death/maturity benefit (CNY)
    ``premium``     : float, annual premium (CNY)

    Optional columns
    ----------------
    ``policy_id``   : str/int, unique identifier for each row
    ``policy_year`` : int, years in force (for in-force valuations)

    Validation layers
    -----------------
    D1 — Schema       : required columns present
    D2 — Dtype        : numeric/string types correct
    D3 — Range        : values within actuarially plausible bounds
    D4 — Consistency  : premium vs sum_assured ratio
    D5 — Completeness : no NaN in required fields
    D6 — Uniqueness   : no duplicate policy_id (if column present)

    Industry standards
    ------------------
    IA TAS M §3.9  — data validation before model use
    SOA ASOP 56 §3.5 — model testing: input data reasonableness
    """

    REQUIRED_COLUMNS = ["age", "gender", "term_years", "sum_assured", "premium"]

    def validate(self, data: Union[pd.DataFrame, List[Dict[str, Any]]]) -> ValidationReport:
        """Run all checks and return a ``ValidationReport``.

        Parameters
        ----------
        data : pd.DataFrame or list[dict]
            Model point table.  If a list of dicts, it is converted to a
            DataFrame before validation.
        """
        if isinstance(data, list):
            data = pd.DataFrame(data)
        if not isinstance(data, pd.DataFrame):
            raise TypeError(f"Expected DataFrame or list of dicts, got {type(data).__name__}")

        report = ValidationReport(validator_name="ModelPointValidator")
        df = data.copy()

        # D1 — Required columns present
        report.checks.append(self._check_required_columns(df))

        # If schema check failed, skip remaining checks that depend on columns
        missing_cols = set(self.REQUIRED_COLUMNS) - set(df.columns)
        if missing_cols:
            report.checks.append(CheckResult(
                check_id="D1-SKIP",
                description="Downstream checks skipped due to missing required columns",
                passed=True,
                severity=CheckSeverity.INFO,
                details=f"Skipped checks: D2, D3, D4, D5, D6",
            ))
            return report

        # D5 — Completeness (before dtype checks — NaN can corrupt them)
        report.checks.append(self._check_completeness(df))

        # D2 — Dtype correctness
        report.checks.extend(self._check_dtypes(df))

        # D3 — Range checks (only on rows that have valid data)
        df_clean = df.dropna(subset=self.REQUIRED_COLUMNS)
        report.checks.extend(self._check_ranges(df_clean))

        # D4 — Cross-field consistency
        report.checks.extend(self._check_consistency(df_clean))

        # D6 — Uniqueness (optional policy_id column)
        if "policy_id" in df.columns:
            report.checks.append(self._check_uniqueness(df))

        return report

    # ------------------------------------------------------------------
    # Private check methods
    # ------------------------------------------------------------------

    def _check_required_columns(self, df: pd.DataFrame) -> CheckResult:
        missing = sorted(set(self.REQUIRED_COLUMNS) - set(df.columns))
        if missing:
            return CheckResult(
                check_id="D1-01",
                description="All required columns present in model point table",
                passed=False,
                severity=CheckSeverity.ERROR,
                details=f"Missing columns: {missing}",
            )
        return CheckResult(
            check_id="D1-01",
            description="All required columns present in model point table",
            passed=True,
        )

    def _check_completeness(self, df: pd.DataFrame) -> CheckResult:
        null_counts = {col: int(df[col].isna().sum()) for col in self.REQUIRED_COLUMNS}
        total_nulls = sum(null_counts.values())
        if total_nulls > 0:
            bad = {k: v for k, v in null_counts.items() if v > 0}
            return CheckResult(
                check_id="D5-01",
                description="No NaN/null values in required columns",
                passed=False,
                severity=CheckSeverity.ERROR,
                details=f"Null counts by column: {bad}",
            )
        return CheckResult(
            check_id="D5-01",
            description="No NaN/null values in required columns",
            passed=True,
        )

    def _check_dtypes(self, df: pd.DataFrame) -> List[CheckResult]:
        results = []

        # age must be integer-like
        try:
            ages = pd.to_numeric(df["age"], errors="coerce")
            non_int = df.loc[ages.isna() | (ages != ages.astype(int, errors="ignore"))].index.tolist()
            non_int_clean = [i for i in non_int if not pd.isna(df.loc[i, "age"])]
        except Exception:
            non_int_clean = []
        results.append(CheckResult(
            check_id="D2-01",
            description="Column 'age' contains integer-like values",
            passed=len(non_int_clean) == 0,
            severity=CheckSeverity.ERROR,
            details=f"Non-integer rows: {non_int_clean[:10]}" if non_int_clean else "",
        ))

        # term_years must be integer-like
        try:
            terms = pd.to_numeric(df["term_years"], errors="coerce")
            non_int_terms = df.loc[terms.isna()].index.tolist()
        except Exception:
            non_int_terms = []
        results.append(CheckResult(
            check_id="D2-02",
            description="Column 'term_years' contains numeric values",
            passed=len(non_int_terms) == 0,
            severity=CheckSeverity.ERROR,
            details=f"Non-numeric rows: {non_int_terms[:10]}" if non_int_terms else "",
        ))

        # sum_assured must be numeric
        try:
            sa = pd.to_numeric(df["sum_assured"], errors="coerce")
            bad_sa = df.loc[sa.isna()].index.tolist()
        except Exception:
            bad_sa = list(range(len(df)))
        results.append(CheckResult(
            check_id="D2-03",
            description="Column 'sum_assured' contains numeric values",
            passed=len(bad_sa) == 0,
            severity=CheckSeverity.ERROR,
            details=f"Non-numeric rows: {bad_sa[:10]}" if bad_sa else "",
        ))

        # premium must be numeric
        try:
            prem = pd.to_numeric(df["premium"], errors="coerce")
            bad_prem = df.loc[prem.isna()].index.tolist()
        except Exception:
            bad_prem = list(range(len(df)))
        results.append(CheckResult(
            check_id="D2-04",
            description="Column 'premium' contains numeric values",
            passed=len(bad_prem) == 0,
            severity=CheckSeverity.ERROR,
            details=f"Non-numeric rows: {bad_prem[:10]}" if bad_prem else "",
        ))

        return results

    def _check_ranges(self, df: pd.DataFrame) -> List[CheckResult]:
        results = []
        ages = pd.to_numeric(df["age"], errors="coerce")
        terms = pd.to_numeric(df["term_years"], errors="coerce")
        sa = pd.to_numeric(df["sum_assured"], errors="coerce")
        prem = pd.to_numeric(df["premium"], errors="coerce")

        # Age range
        bad_age = df.loc[(ages < _MP_AGE_MIN) | (ages > _MP_AGE_MAX)].index.tolist()
        results.append(CheckResult(
            check_id="D3-01",
            description=f"Issue age in [{_MP_AGE_MIN}, {_MP_AGE_MAX}]",
            passed=len(bad_age) == 0,
            severity=CheckSeverity.ERROR,
            details=f"{len(bad_age)} row(s) out of range. Rows: {bad_age[:10]}" if bad_age else "",
        ))

        # Term validity
        bad_term = df.loc[~terms.isin(_MP_TERM_VALID)].index.tolist()
        results.append(CheckResult(
            check_id="D3-02",
            description=f"term_years in valid set {sorted(_MP_TERM_VALID)}",
            passed=len(bad_term) == 0,
            severity=CheckSeverity.ERROR,
            details=f"{len(bad_term)} row(s) with invalid term. Rows: {bad_term[:10]}" if bad_term else "",
        ))

        # Sum assured range
        bad_sa = df.loc[(sa < _MP_SUM_ASSURED_MIN) | (sa > _MP_SUM_ASSURED_MAX)].index.tolist()
        results.append(CheckResult(
            check_id="D3-03",
            description=f"sum_assured in [{_MP_SUM_ASSURED_MIN:,.0f}, {_MP_SUM_ASSURED_MAX:,.0f}]",
            passed=len(bad_sa) == 0,
            severity=CheckSeverity.ERROR,
            details=f"{len(bad_sa)} row(s) out of range. Rows: {bad_sa[:10]}" if bad_sa else "",
        ))

        # Premium positivity
        bad_prem_pos = df.loc[prem <= 0].index.tolist()
        results.append(CheckResult(
            check_id="D3-04",
            description="premium > 0",
            passed=len(bad_prem_pos) == 0,
            severity=CheckSeverity.ERROR,
            details=f"{len(bad_prem_pos)} non-positive premium row(s). Rows: {bad_prem_pos[:10]}" if bad_prem_pos else "",
        ))

        # Gender validity
        bad_gender = df.loc[~df["gender"].astype(str).isin(_MP_GENDERS)].index.tolist()
        results.append(CheckResult(
            check_id="D3-05",
            description=f"gender in valid set {{'M','F'}} (case-insensitive variants accepted)",
            passed=len(bad_gender) == 0,
            severity=CheckSeverity.ERROR,
            details=f"{len(bad_gender)} row(s) with invalid gender. Rows: {bad_gender[:10]}" if bad_gender else "",
        ))

        # Max issue age + term check (product eligibility: age+term <= 75)
        max_age_at_maturity = ages + terms
        bad_maturity = df.loc[max_age_at_maturity > 75].index.tolist()
        results.append(CheckResult(
            check_id="D3-06",
            description="issue_age + term_years <= 75 (product maturity age limit)",
            passed=len(bad_maturity) == 0,
            severity=CheckSeverity.WARNING,
            details=f"{len(bad_maturity)} row(s) exceed maturity age 75. Rows: {bad_maturity[:10]}" if bad_maturity else "",
        ))

        return results

    def _check_consistency(self, df: pd.DataFrame) -> List[CheckResult]:
        results = []
        sa = pd.to_numeric(df["sum_assured"], errors="coerce")
        prem = pd.to_numeric(df["premium"], errors="coerce")

        # Premium / sum_assured ratio
        ratio = prem / sa.replace(0, np.nan)
        too_low  = df.loc[ratio < _MP_PREMIUM_MIN_PCT].index.tolist()
        too_high = df.loc[ratio > _MP_PREMIUM_MAX_PCT].index.tolist()

        results.append(CheckResult(
            check_id="D4-01",
            description=(
                f"premium/sum_assured ratio in "
                f"[{_MP_PREMIUM_MIN_PCT*100:.1f}%, {_MP_PREMIUM_MAX_PCT*100:.0f}%]"
            ),
            passed=len(too_low) == 0 and len(too_high) == 0,
            severity=CheckSeverity.WARNING,
            details=(
                f"Too low: {len(too_low)} row(s); too high: {len(too_high)} row(s)"
                if too_low or too_high else ""
            ),
        ))

        # policy_year vs term_years (if policy_year column present)
        if "policy_year" in df.columns:
            py = pd.to_numeric(df["policy_year"], errors="coerce")
            terms = pd.to_numeric(df["term_years"], errors="coerce")
            bad_py = df.loc[(py < 0) | (py > terms)].index.tolist()
            results.append(CheckResult(
                check_id="D4-02",
                description="policy_year in [0, term_years] (in-force check)",
                passed=len(bad_py) == 0,
                severity=CheckSeverity.ERROR,
                details=f"{len(bad_py)} row(s) with policy_year > term_years. Rows: {bad_py[:10]}" if bad_py else "",
            ))

        return results

    def _check_uniqueness(self, df: pd.DataFrame) -> CheckResult:
        dupes = df["policy_id"].duplicated().sum()
        return CheckResult(
            check_id="D6-01",
            description="policy_id values are unique (no duplicate policies)",
            passed=dupes == 0,
            severity=CheckSeverity.ERROR,
            details=f"{dupes} duplicate policy_id value(s) found" if dupes else "",
        )


# ---------------------------------------------------------------------------
# 2. Mortality Table Validator
# ---------------------------------------------------------------------------

_MORT_QX_MIN  = 1e-6   # minimum plausible annual mortality rate
_MORT_QX_MAX  = 0.50   # maximum plausible annual mortality rate (age 65 ceiling)
_MORT_AGE_MIN = 18
_MORT_AGE_MAX = 85     # include post-maturity run-off ages


class MortalityTableValidator:
    """Validates a mortality (qx) assumption table.

    Expected input format (DataFrame)
    ----------------------------------
    Must have columns: ``age`` (int), ``qx`` (float).
    Optional columns: ``gender`` (str, "M"/"F"), ``table_name`` (str).

    Validation layers
    -----------------
    D1 — Schema       : required columns present
    D2 — Range        : age in [18, 85]; qx in (1e-6, 0.50)
    D3 — Monotonicity : qx should be non-decreasing with age (Gompertz-like)
    D4 — Completeness : no NaN in required fields
    D5 — Age coverage : ages 18–65 (minimum model range) all present

    Industry standards
    ------------------
    IA TAS M §3.9  — data validation: mortality table plausibility
    SOA ASOP 25 §3.3 — assumption appropriateness: mortality trends
    SOA ASOP 56 §3.5 — model input validation
    """

    REQUIRED_COLUMNS = ["age", "qx"]

    def validate(
        self,
        data: Union[pd.DataFrame, List[Dict[str, Any]]],
        gender_filter: Optional[str] = None,
    ) -> ValidationReport:
        """Validate mortality table.

        Parameters
        ----------
        data : pd.DataFrame or list[dict]
        gender_filter : "M" or "F", optional
            If the table contains a gender column, validate only this gender.
        """
        if isinstance(data, list):
            data = pd.DataFrame(data)
        df = data.copy()
        if gender_filter and "gender" in df.columns:
            df = df[df["gender"].astype(str).str.upper().str[0] == gender_filter.upper()]

        report = ValidationReport(validator_name="MortalityTableValidator")

        # D1
        report.checks.append(self._check_required_columns(df))
        if set(self.REQUIRED_COLUMNS) - set(df.columns):
            return report

        # D4
        report.checks.append(self._check_completeness(df))
        df_clean = df.dropna(subset=self.REQUIRED_COLUMNS)

        # D2
        report.checks.extend(self._check_ranges(df_clean))

        # D3
        report.checks.append(self._check_monotonicity(df_clean))

        # D5
        report.checks.append(self._check_age_coverage(df_clean))

        return report

    def _check_required_columns(self, df: pd.DataFrame) -> CheckResult:
        missing = sorted(set(self.REQUIRED_COLUMNS) - set(df.columns))
        return CheckResult(
            check_id="D1-M01",
            description="Mortality table has required columns [age, qx]",
            passed=not missing,
            severity=CheckSeverity.ERROR,
            details=f"Missing: {missing}" if missing else "",
        )

    def _check_completeness(self, df: pd.DataFrame) -> CheckResult:
        null_counts = {col: int(df[col].isna().sum()) for col in self.REQUIRED_COLUMNS}
        total = sum(null_counts.values())
        return CheckResult(
            check_id="D5-M01",
            description="No NaN in mortality table required columns",
            passed=total == 0,
            severity=CheckSeverity.ERROR,
            details=f"Null counts: {null_counts}" if total else "",
        )

    def _check_ranges(self, df: pd.DataFrame) -> List[CheckResult]:
        results = []
        ages = pd.to_numeric(df["age"], errors="coerce")
        qx   = pd.to_numeric(df["qx"],  errors="coerce")

        bad_age = df.loc[(ages < _MORT_AGE_MIN) | (ages > _MORT_AGE_MAX)].index.tolist()
        results.append(CheckResult(
            check_id="D2-M01",
            description=f"age in [{_MORT_AGE_MIN}, {_MORT_AGE_MAX}]",
            passed=len(bad_age) == 0,
            severity=CheckSeverity.WARNING,
            details=f"{len(bad_age)} row(s) with age outside range. Rows: {bad_age[:10]}" if bad_age else "",
        ))

        bad_qx = df.loc[(qx <= _MORT_QX_MIN) | (qx >= _MORT_QX_MAX)].index.tolist()
        results.append(CheckResult(
            check_id="D2-M02",
            description=f"qx in ({_MORT_QX_MIN:.0e}, {_MORT_QX_MAX})",
            passed=len(bad_qx) == 0,
            severity=CheckSeverity.ERROR,
            details=f"{len(bad_qx)} row(s) with qx out of plausible range. Rows: {bad_qx[:10]}" if bad_qx else "",
        ))

        return results

    def _check_monotonicity(self, df: pd.DataFrame) -> CheckResult:
        """qx should be non-decreasing with age (Gompertz-Makeham property)."""
        df_sorted = df.sort_values("age")
        qx = pd.to_numeric(df_sorted["qx"], errors="coerce").values
        decreases = int(np.sum(np.diff(qx) < -1e-8))   # allow tiny numerical noise
        return CheckResult(
            check_id="D3-M01",
            description="qx is non-decreasing with age (Gompertz-like mortality)",
            passed=decreases == 0,
            severity=CheckSeverity.WARNING,
            details=f"{decreases} age point(s) where qx decreases with age" if decreases else "",
        )

    def _check_age_coverage(self, df: pd.DataFrame) -> CheckResult:
        """Ages 18–65 must all be present for minimum model coverage."""
        present = set(pd.to_numeric(df["age"], errors="coerce").dropna().astype(int).tolist())
        required = set(range(_MORT_AGE_MIN, 66))
        missing = sorted(required - present)
        return CheckResult(
            check_id="D5-M02",
            description="Mortality table covers all ages 18–65 (minimum model range)",
            passed=len(missing) == 0,
            severity=CheckSeverity.ERROR,
            details=f"Missing ages: {missing[:20]}" if missing else "",
        )


# ---------------------------------------------------------------------------
# 3. Lapse Table Validator
# ---------------------------------------------------------------------------

_LAPSE_RATE_MIN  = 0.0
_LAPSE_RATE_MAX  = 0.60   # 60% annual lapse is extreme but observed in CNY market
_LAPSE_YEAR_MIN  = 1
_LAPSE_YEAR_MAX  = 20     # matches maximum product term


class LapseTableValidator:
    """Validates a lapse rate assumption table.

    Expected input format (DataFrame)
    ----------------------------------
    Must have columns: ``policy_year`` (int), ``lapse_rate`` (float, annual).
    Optional: ``product_code`` (str), ``scenario`` (str).

    Validation layers
    -----------------
    D1 — Schema       : required columns present
    D2 — Range        : policy_year in [1, 20]; lapse_rate in [0, 0.60]
    D3 — Trend        : high early lapse (year 1–3) > low late lapse (sensible)
    D4 — Completeness : no NaN
    D5 — Coverage     : policy years 1–20 present

    Industry standards
    ------------------
    SOA ASOP 25 §3.3  — lapse assumptions: internal experience or industry data
    IA TAS M §3.9     — data validation: plausibility of lapse assumptions
    """

    REQUIRED_COLUMNS = ["policy_year", "lapse_rate"]

    def validate(
        self,
        data: Union[pd.DataFrame, List[Dict[str, Any]]],
    ) -> ValidationReport:
        if isinstance(data, list):
            data = pd.DataFrame(data)
        df = data.copy()

        report = ValidationReport(validator_name="LapseTableValidator")

        # D1
        report.checks.append(self._check_required_columns(df))
        if set(self.REQUIRED_COLUMNS) - set(df.columns):
            return report

        # D4
        report.checks.append(self._check_completeness(df))
        df_clean = df.dropna(subset=self.REQUIRED_COLUMNS)

        # D2
        report.checks.extend(self._check_ranges(df_clean))

        # D3
        report.checks.append(self._check_trend(df_clean))

        # D5
        report.checks.append(self._check_coverage(df_clean))

        return report

    def _check_required_columns(self, df: pd.DataFrame) -> CheckResult:
        missing = sorted(set(self.REQUIRED_COLUMNS) - set(df.columns))
        return CheckResult(
            check_id="D1-L01",
            description="Lapse table has required columns [policy_year, lapse_rate]",
            passed=not missing,
            severity=CheckSeverity.ERROR,
            details=f"Missing: {missing}" if missing else "",
        )

    def _check_completeness(self, df: pd.DataFrame) -> CheckResult:
        total = sum(int(df[col].isna().sum()) for col in self.REQUIRED_COLUMNS)
        return CheckResult(
            check_id="D5-L01",
            description="No NaN in lapse table required columns",
            passed=total == 0,
            severity=CheckSeverity.ERROR,
            details=f"{total} null value(s) found" if total else "",
        )

    def _check_ranges(self, df: pd.DataFrame) -> List[CheckResult]:
        results = []
        years  = pd.to_numeric(df["policy_year"], errors="coerce")
        lapse  = pd.to_numeric(df["lapse_rate"],  errors="coerce")

        bad_year = df.loc[(years < _LAPSE_YEAR_MIN) | (years > _LAPSE_YEAR_MAX)].index.tolist()
        results.append(CheckResult(
            check_id="D2-L01",
            description=f"policy_year in [{_LAPSE_YEAR_MIN}, {_LAPSE_YEAR_MAX}]",
            passed=len(bad_year) == 0,
            severity=CheckSeverity.WARNING,
            details=f"{len(bad_year)} row(s) outside range. Rows: {bad_year[:10]}" if bad_year else "",
        ))

        bad_lapse = df.loc[(lapse < _LAPSE_RATE_MIN) | (lapse > _LAPSE_RATE_MAX)].index.tolist()
        results.append(CheckResult(
            check_id="D2-L02",
            description=f"lapse_rate in [{_LAPSE_RATE_MIN}, {_LAPSE_RATE_MAX}]",
            passed=len(bad_lapse) == 0,
            severity=CheckSeverity.ERROR,
            details=f"{len(bad_lapse)} row(s) with lapse_rate outside plausible range. Rows: {bad_lapse[:10]}" if bad_lapse else "",
        ))

        return results

    def _check_trend(self, df: pd.DataFrame) -> CheckResult:
        """Early-year lapse (years 1-3) should be higher than late-year (years 8+).

        This is a known empirical pattern for CNY PAR endowment products
        (surrender charge cliff at year 3; rational policyholder behaviour).
        Violation is a WARNING — some product designs have flat lapse curves.
        """
        df_s = df.sort_values("policy_year")
        years  = pd.to_numeric(df_s["policy_year"], errors="coerce")
        lapse  = pd.to_numeric(df_s["lapse_rate"],  errors="coerce")

        early = lapse[years.isin([1, 2, 3])].mean()
        late  = lapse[years >= 8].mean()

        if pd.isna(early) or pd.isna(late):
            return CheckResult(
                check_id="D3-L01",
                description="Early-year lapse > late-year lapse (typical CNY PAR pattern)",
                passed=True,
                severity=CheckSeverity.INFO,
                details="Insufficient data to check trend (years 1-3 or 8+ not all present)",
            )

        _TOLERANCE = 1e-9  # guard against floating-point equality artefacts
        passed = float(early) >= float(late) - _TOLERANCE
        return CheckResult(
            check_id="D3-L01",
            description="Early-year lapse (yr 1-3) ≥ late-year lapse (yr 8+)",
            passed=passed,
            severity=CheckSeverity.WARNING,
            details=(
                f"Early mean={early:.4f}, late mean={late:.4f} — unexpected inverse lapse curve"
                if not passed else ""
            ),
        )

    def _check_coverage(self, df: pd.DataFrame) -> CheckResult:
        present = set(pd.to_numeric(df["policy_year"], errors="coerce").dropna().astype(int).tolist())
        required = set(range(_LAPSE_YEAR_MIN, 21))
        missing = sorted(required - present)
        return CheckResult(
            check_id="D5-L01",
            description="Lapse table covers policy years 1–20 (full product term range)",
            passed=len(missing) == 0,
            severity=CheckSeverity.WARNING,
            details=f"Missing policy years: {missing}" if missing else "",
        )


# ---------------------------------------------------------------------------
# 4. Discount Rate Validator
# ---------------------------------------------------------------------------

_DR_MIN     = 0.005   # 0.5% — floor for near-zero rate environments
_DR_MAX     = 0.15    # 15% — ceiling; above this is implausible for CNY PAR
_DR_CBIRC   = 0.030   # CBIRC maximum guaranteed rate (3.0% since 2023)
_DR_LEGACY  = 0.035   # Legacy rate used in existing model (flagged as deviation)


class DiscountRateValidator:
    """Validates a scalar or term-structure discount rate assumption.

    Accepts either:
      (a) a scalar float (single discount rate); or
      (b) a DataFrame with columns ``term_years`` (int) and ``rate`` (float)
          representing a term structure.

    Validation layers
    -----------------
    D2 — Range     : rate in [0.5%, 15%]
    D3 — Regulatory: flag if rate > CBIRC maximum (3.0%); ≤ 2.5% is INFO
    D4 — Consistency: term structure should be upward-sloping (Expectations)

    Industry standards
    ------------------
    IA TAS M §3.5 — assumption sign-off: discount rate is material assumption
    SOA ASOP 25 §3.3 — credibility of discount rate assumption
    CBIRC Regulation — 3.0% maximum guaranteed rate for CNY PAR (2023 circular)
    """

    def validate(
        self,
        data: Union[float, pd.DataFrame, List[Dict[str, Any]]],
    ) -> ValidationReport:
        report = ValidationReport(validator_name="DiscountRateValidator")

        if isinstance(data, (int, float)):
            report.checks.extend(self._check_scalar(float(data)))
        else:
            if isinstance(data, list):
                data = pd.DataFrame(data)
            report.checks.extend(self._check_term_structure(data))

        return report

    def _check_scalar(self, rate: float) -> List[CheckResult]:
        results = []

        # Range
        results.append(CheckResult(
            check_id="D2-R01",
            description=f"Discount rate in plausible range [{_DR_MIN*100:.1f}%, {_DR_MAX*100:.0f}%]",
            passed=_DR_MIN <= rate <= _DR_MAX,
            severity=CheckSeverity.ERROR,
            details=f"Rate = {rate*100:.2f}% is outside [{_DR_MIN*100:.1f}%, {_DR_MAX*100:.0f}%]" if not (_DR_MIN <= rate <= _DR_MAX) else "",
        ))

        # CBIRC regulatory cap
        results.append(CheckResult(
            check_id="D3-R01",
            description=f"Discount rate ≤ CBIRC maximum ({_DR_CBIRC*100:.1f}%)",
            passed=rate <= _DR_CBIRC,
            severity=CheckSeverity.WARNING,
            details=(
                f"Rate = {rate*100:.2f}% exceeds CBIRC cap {_DR_CBIRC*100:.1f}%. "
                f"This is a critical regulatory deviation (SOA ASOP 56 §3.5). "
                f"Legacy rate {_DR_LEGACY*100:.1f}% flagged as non-compliant in Phase 1 audit."
            ) if rate > _DR_CBIRC else "",
        ))

        # Very low rate warning
        results.append(CheckResult(
            check_id="D3-R02",
            description=f"Discount rate ≥ 2.5% (plausibility floor for CNY PAR)",
            passed=rate >= 0.025,
            severity=CheckSeverity.INFO,
            details=f"Rate = {rate*100:.2f}% is below typical CNY PAR pricing rate; verify against current market conditions" if rate < 0.025 else "",
        ))

        return results

    def _check_term_structure(self, df: pd.DataFrame) -> List[CheckResult]:
        results = []
        required = ["term_years", "rate"]
        missing = sorted(set(required) - set(df.columns))
        results.append(CheckResult(
            check_id="D1-R01",
            description="Term structure table has columns [term_years, rate]",
            passed=not missing,
            severity=CheckSeverity.ERROR,
            details=f"Missing: {missing}" if missing else "",
        ))
        if missing:
            return results

        rates = pd.to_numeric(df["rate"], errors="coerce")

        # Range check (each rate)
        bad = df.loc[(rates < _DR_MIN) | (rates > _DR_MAX)].index.tolist()
        results.append(CheckResult(
            check_id="D2-R02",
            description=f"All term rates in [{_DR_MIN*100:.1f}%, {_DR_MAX*100:.0f}%]",
            passed=len(bad) == 0,
            severity=CheckSeverity.ERROR,
            details=f"{len(bad)} rate(s) out of range. Rows: {bad[:10]}" if bad else "",
        ))

        # CBIRC cap
        above_cap = df.loc[rates > _DR_CBIRC].index.tolist()
        results.append(CheckResult(
            check_id="D3-R03",
            description=f"All term rates ≤ CBIRC cap ({_DR_CBIRC*100:.1f}%)",
            passed=len(above_cap) == 0,
            severity=CheckSeverity.WARNING,
            details=f"{len(above_cap)} term rate(s) exceed CBIRC cap. Rows: {above_cap[:10]}" if above_cap else "",
        ))

        # Upward-sloping term structure (Expectations Hypothesis)
        df_s = df.sort_values("term_years")
        rates_sorted = pd.to_numeric(df_s["rate"], errors="coerce").values
        inversions = int(np.sum(np.diff(rates_sorted) < -1e-4))
        results.append(CheckResult(
            check_id="D4-R01",
            description="Term structure is upward-sloping (Expectations Hypothesis)",
            passed=inversions == 0,
            severity=CheckSeverity.INFO,
            details=f"{inversions} inversion(s) detected — inverted curve possible in current rate environment" if inversions else "",
        ))

        return results


# ---------------------------------------------------------------------------
# 5. Convenience: validate_all()
# ---------------------------------------------------------------------------

@dataclass
class FullDataValidationReport:
    """Combined report from all four validators.

    Attributes
    ----------
    model_points   : ValidationReport from ModelPointValidator
    mortality      : ValidationReport from MortalityTableValidator
    lapse          : ValidationReport from LapseTableValidator
    discount_rate  : ValidationReport from DiscountRateValidator
    """
    model_points:  Optional[ValidationReport] = None
    mortality:     Optional[ValidationReport] = None
    lapse:         Optional[ValidationReport] = None
    discount_rate: Optional[ValidationReport] = None

    @property
    def passed(self) -> bool:
        reports = [r for r in [self.model_points, self.mortality, self.lapse, self.discount_rate] if r is not None]
        return all(r.passed for r in reports)

    @property
    def total_errors(self) -> int:
        reports = [r for r in [self.model_points, self.mortality, self.lapse, self.discount_rate] if r is not None]
        return sum(r.error_count for r in reports)

    @property
    def total_warnings(self) -> int:
        reports = [r for r in [self.model_points, self.mortality, self.lapse, self.discount_rate] if r is not None]
        return sum(r.warning_count for r in reports)

    def summary(self) -> str:
        lines = ["=== Full Data Validation Report ==="]
        for attr, name in [
            ("model_points", "ModelPoints"),
            ("mortality",    "Mortality"),
            ("lapse",        "Lapse"),
            ("discount_rate","DiscountRate"),
        ]:
            report = getattr(self, attr)
            if report is not None:
                lines.append(f"  {name}: {report.summary()}")
        status = "PASS" if self.passed else "FAIL"
        lines.append(f"Overall: {status} ({self.total_errors} errors, {self.total_warnings} warnings)")
        return "\n".join(lines)

    def emit_to_governance_store(
        self,
        governance_store: Any,
        actor: str = "Claude-Actuarial-Agent",
        phase: str = "Phase 3: Model Validation & Testing",
    ) -> None:
        """Emit one combined VALIDATION AuditEntry covering all sub-reports."""
        from par_model_v2.governance.audit_trail import AuditEntry

        reports = {
            "ModelPointValidator":    self.model_points,
            "MortalityTableValidator": self.mortality,
            "LapseTableValidator":    self.lapse,
            "DiscountRateValidator":  self.discount_rate,
        }
        total_run = total_pass = 0
        all_failed: List[str] = []

        for name, report in reports.items():
            if report is None:
                continue
            total_run  += report.total_checks
            total_pass += report.passed_checks
            for c in report.failed_checks:
                detail = f": {c.details}" if c.details else ""
                all_failed.append(f"[{name}/{c.check_id}] {c.description}{detail}")

        entry = AuditEntry.validation(
            actor=actor,
            phase=phase,
            test_suite="FullDataValidation (ModelPoints+Mortality+Lapse+DiscountRate)",
            tests_run=total_run,
            tests_passed=total_pass,
            tests_failed=len(all_failed),
            outcome="PASS" if self.passed else "FAIL",
            failed_tests=all_failed if all_failed else None,
        )
        governance_store.audit_trail.append(entry)


def validate_all(
    model_points:    Optional[Union[pd.DataFrame, List[Dict]]] = None,
    mortality:       Optional[Union[pd.DataFrame, List[Dict]]] = None,
    lapse:           Optional[Union[pd.DataFrame, List[Dict]]] = None,
    discount_rate:   Optional[Union[float, pd.DataFrame, List[Dict]]] = None,
    governance_store: Any = None,
    actor: str = "Claude-Actuarial-Agent",
    phase: str = "Phase 3: Model Validation & Testing",
) -> FullDataValidationReport:
    """Run all available validators and return a FullDataValidationReport.

    Any argument left as None is skipped.  If *governance_store* is provided,
    a single combined VALIDATION AuditEntry is written.

    Example
    -------
    >>> from par_model_v2.validation.data_validator import validate_all
    >>> report = validate_all(
    ...     model_points=mp_df,
    ...     mortality=mort_df,
    ...     lapse=lapse_df,
    ...     discount_rate=0.030,
    ...     governance_store=store,
    ... )
    >>> print(report.summary())
    >>> assert report.passed, report.summary()
    """
    result = FullDataValidationReport()

    if model_points is not None:
        result.model_points = ModelPointValidator().validate(model_points)

    if mortality is not None:
        result.mortality = MortalityTableValidator().validate(mortality)

    if lapse is not None:
        result.lapse = LapseTableValidator().validate(lapse)

    if discount_rate is not None:
        result.discount_rate = DiscountRateValidator().validate(discount_rate)

    if governance_store is not None:
        result.emit_to_governance_store(governance_store, actor=actor, phase=phase)

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Result primitives
    "CheckSeverity", "CheckResult", "ValidationReport",
    # Validators
    "ModelPointValidator",
    "MortalityTableValidator",
    "LapseTableValidator",
    "DiscountRateValidator",
    # Combined
    "FullDataValidationReport",
    "validate_all",
]
