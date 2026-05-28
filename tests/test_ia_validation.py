"""
Tests — IA TAS M §3.6 Validation Framework
============================================

Validates par_model_v2.validation against:
  - Enum completeness and semantics
  - ValidationRequirement construction and run() behaviour
  - ValidationResult serialisation round-trip
  - ValidationReport summary statistics and overall_status logic
  - ValidationRunner skip_categories logic
  - IA_VALIDATION_REQUIREMENTS registry completeness

IA Reference: TAS M 3.6 (Testing and validation)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List

import pytest

from par_model_v2.validation import (
    IA_VALIDATION_REQUIREMENTS,
    ValidationCategory,
    ValidationReport,
    ValidationRequirement,
    ValidationResult,
    ValidationRunner,
    ValidationStatus,
)
from par_model_v2.validation.ia_validation import Severity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)


def _pass_result(req_id: str = "VR-TEST") -> ValidationResult:
    return ValidationResult(
        req_id=req_id,
        status=ValidationStatus.PASS,
        evidence="All checks passed.",
        checked_at=NOW,
        details={"n_tests": 10},
    )


def _fail_result(req_id: str = "VR-TEST") -> ValidationResult:
    return ValidationResult(
        req_id=req_id,
        status=ValidationStatus.FAIL,
        evidence="Critical failure detected.",
        checked_at=NOW,
        details={"error": "assertion failed"},
    )


def _not_run_result(req_id: str = "VR-TEST") -> ValidationResult:
    return ValidationResult(
        req_id=req_id,
        status=ValidationStatus.NOT_RUN,
        evidence="No automated check registered.",
        checked_at=NOW,
    )


def _make_req(
    req_id: str = "VR-TEST",
    category: ValidationCategory = ValidationCategory.UNIT,
    severity: Severity = Severity.HIGH,
    check_fn=None,
) -> ValidationRequirement:
    return ValidationRequirement(
        req_id=req_id,
        name="Test Requirement",
        description="A test requirement.",
        category=category,
        severity=severity,
        ia_reference="TAS M 3.6",
        acceptance_criteria=["Criterion A", "Criterion B"],
        check_fn=check_fn,
    )


def _make_report(
    results: List[ValidationResult],
    requirements: List[ValidationRequirement],
) -> ValidationReport:
    return ValidationReport(
        model_name="Test Model",
        model_version="1.0.0",
        generated_at=NOW,
        results=results,
        requirements=requirements,
    )


# ---------------------------------------------------------------------------
# 1. ValidationStatus Enum
# ---------------------------------------------------------------------------

class TestValidationStatus:
    def test_all_statuses_exist(self):
        expected = {"PASS", "FAIL", "PARTIAL", "NOT_RUN", "WAIVED"}
        actual = {s.value for s in ValidationStatus}
        assert expected == actual

    def test_status_is_string(self):
        assert isinstance(ValidationStatus.PASS, str)
        assert ValidationStatus.PASS == "PASS"

    def test_status_equality_by_value(self):
        assert ValidationStatus("PASS") == ValidationStatus.PASS
        assert ValidationStatus("FAIL") != ValidationStatus.PASS


# ---------------------------------------------------------------------------
# 2. ValidationCategory Enum
# ---------------------------------------------------------------------------

class TestValidationCategory:
    def test_all_categories_exist(self):
        expected = {"Unit", "Integration", "Stochastic", "Sensitivity", "Backtest", "Governance", "Data"}
        actual = {c.value for c in ValidationCategory}
        assert expected == actual

    def test_category_is_string(self):
        assert isinstance(ValidationCategory.UNIT, str)
        assert ValidationCategory.UNIT == "Unit"


# ---------------------------------------------------------------------------
# 3. ValidationResult
# ---------------------------------------------------------------------------

class TestValidationResult:
    def test_basic_construction(self):
        r = _pass_result("VR-001")
        assert r.req_id == "VR-001"
        assert r.status == ValidationStatus.PASS
        assert r.checked_at == NOW

    def test_is_passing_pass(self):
        assert _pass_result().is_passing is True

    def test_is_passing_waived(self):
        r = ValidationResult(
            req_id="VR-W",
            status=ValidationStatus.WAIVED,
            evidence="Approved waiver.",
            checked_at=NOW,
            waiver_justification="Documented exception approved by CRO.",
        )
        assert r.is_passing is True

    def test_is_passing_fail(self):
        assert _fail_result().is_passing is False

    def test_is_passing_partial(self):
        r = ValidationResult(req_id="VR-P", status=ValidationStatus.PARTIAL, evidence="Partial.", checked_at=NOW)
        assert r.is_passing is False

    def test_is_passing_not_run(self):
        assert _not_run_result().is_passing is False

    def test_blocks_production_fail(self):
        assert _fail_result().blocks_production is True

    def test_blocks_production_not_run(self):
        assert _not_run_result().blocks_production is True

    def test_blocks_production_pass(self):
        assert _pass_result().blocks_production is False

    def test_to_dict_keys(self):
        d = _pass_result("VR-X").to_dict()
        assert set(d.keys()) == {"req_id", "status", "evidence", "checked_at", "details", "waiver_justification"}

    def test_to_dict_status_value(self):
        d = _pass_result().to_dict()
        assert d["status"] == "PASS"  # string, not enum

    def test_from_dict_roundtrip(self):
        original = _pass_result("VR-RT")
        original.details = {"n": 42, "name": "test"}
        d = original.to_dict()
        restored = ValidationResult.from_dict(d)
        assert restored.req_id == original.req_id
        assert restored.status == original.status
        assert restored.evidence == original.evidence
        assert restored.details == original.details

    def test_from_dict_waiver(self):
        r = ValidationResult(
            req_id="VR-W",
            status=ValidationStatus.WAIVED,
            evidence="Waived.",
            checked_at=NOW,
            waiver_justification="Approved.",
        )
        restored = ValidationResult.from_dict(r.to_dict())
        assert restored.waiver_justification == "Approved."


# ---------------------------------------------------------------------------
# 4. ValidationRequirement
# ---------------------------------------------------------------------------

class TestValidationRequirement:
    def test_basic_construction(self):
        req = _make_req("VR-001")
        assert req.req_id == "VR-001"
        assert req.category == ValidationCategory.UNIT
        assert len(req.acceptance_criteria) == 2

    def test_run_no_check_fn_returns_not_run(self):
        req = _make_req(check_fn=None)
        result = req.run()
        assert result.status == ValidationStatus.NOT_RUN
        assert "No automated check" in result.evidence

    def test_run_with_pass_check_fn(self):
        def always_pass():
            return ValidationResult(
                req_id="VR-T",
                status=ValidationStatus.PASS,
                evidence="OK",
                checked_at=NOW,
            )

        req = _make_req(check_fn=always_pass)
        result = req.run()
        assert result.status == ValidationStatus.PASS

    def test_run_with_raising_check_fn(self):
        def always_raise():
            raise RuntimeError("Test explosion")

        req = _make_req(check_fn=always_raise)
        result = req.run()
        assert result.status == ValidationStatus.FAIL
        assert "RuntimeError" in result.evidence

    def test_run_propagates_req_id(self):
        """run() must set result.req_id to the requirement's req_id."""
        def fn():
            return ValidationResult(req_id="WRONG", status=ValidationStatus.PASS, evidence="ok", checked_at=NOW)

        req = _make_req(req_id="VR-CORRECT", check_fn=fn)
        result = req.run()
        assert result.req_id == "VR-CORRECT"


# ---------------------------------------------------------------------------
# 5. ValidationReport
# ---------------------------------------------------------------------------

class TestValidationReport:
    def _build_report(self, statuses: List[ValidationStatus]) -> ValidationReport:
        """Build a simple report with requirements matching the given statuses."""
        reqs = [_make_req(req_id=f"VR-{i:03d}") for i in range(len(statuses))]
        results = [
            ValidationResult(req_id=f"VR-{i:03d}", status=s, evidence="test", checked_at=NOW)
            for i, s in enumerate(statuses)
        ]
        return _make_report(results, reqs)

    def test_total(self):
        report = self._build_report([ValidationStatus.PASS, ValidationStatus.FAIL])
        assert report.total == 2

    def test_passed_count(self):
        report = self._build_report([ValidationStatus.PASS, ValidationStatus.PASS, ValidationStatus.FAIL])
        assert report.passed == 2

    def test_failed_count(self):
        report = self._build_report([ValidationStatus.FAIL, ValidationStatus.PASS])
        assert report.failed == 1

    def test_not_run_count(self):
        report = self._build_report([ValidationStatus.NOT_RUN, ValidationStatus.NOT_RUN])
        assert report.not_run == 2

    def test_waived_count(self):
        report = self._build_report([ValidationStatus.WAIVED])
        assert report.waived == 1

    def test_overall_status_all_pass(self):
        report = self._build_report([ValidationStatus.PASS, ValidationStatus.PASS])
        assert report.overall_status == ValidationStatus.PASS

    def test_overall_status_any_fail(self):
        report = self._build_report([ValidationStatus.PASS, ValidationStatus.FAIL])
        assert report.overall_status == ValidationStatus.FAIL

    def test_overall_status_partial_beats_pass(self):
        report = self._build_report([ValidationStatus.PASS, ValidationStatus.PARTIAL])
        assert report.overall_status == ValidationStatus.PARTIAL

    def test_overall_status_not_run_beats_pass(self):
        report = self._build_report([ValidationStatus.PASS, ValidationStatus.NOT_RUN])
        assert report.overall_status == ValidationStatus.PARTIAL

    def test_overall_status_fail_beats_partial(self):
        report = self._build_report([ValidationStatus.PARTIAL, ValidationStatus.FAIL])
        assert report.overall_status == ValidationStatus.FAIL

    def test_overall_status_waived_with_pass(self):
        report = self._build_report([ValidationStatus.PASS, ValidationStatus.WAIVED])
        assert report.overall_status == ValidationStatus.PASS

    def test_compliance_pct_all_pass(self):
        report = self._build_report([ValidationStatus.PASS, ValidationStatus.PASS])
        assert report.compliance_pct() == 100.0

    def test_compliance_pct_half_pass(self):
        report = self._build_report([ValidationStatus.PASS, ValidationStatus.FAIL])
        assert report.compliance_pct() == 50.0

    def test_compliance_pct_waived_counts_as_pass(self):
        report = self._build_report([ValidationStatus.WAIVED, ValidationStatus.FAIL])
        assert report.compliance_pct() == 50.0

    def test_compliance_pct_empty(self):
        report = _make_report([], [])
        assert report.compliance_pct() == 0.0

    def test_compliance_pct_by_category(self):
        unit_req = _make_req("VR-U", category=ValidationCategory.UNIT)
        gov_req = _make_req("VR-G", category=ValidationCategory.GOVERNANCE)
        results = [
            ValidationResult(req_id="VR-U", status=ValidationStatus.PASS, evidence="ok", checked_at=NOW),
            ValidationResult(req_id="VR-G", status=ValidationStatus.FAIL, evidence="fail", checked_at=NOW),
        ]
        report = _make_report(results, [unit_req, gov_req])
        assert report.compliance_pct(ValidationCategory.UNIT) == 100.0
        assert report.compliance_pct(ValidationCategory.GOVERNANCE) == 0.0

    def test_critical_failures_detected(self):
        crit_req = _make_req("VR-CRIT", severity=Severity.CRITICAL)
        high_req = _make_req("VR-HIGH", severity=Severity.HIGH)
        results = [
            ValidationResult(req_id="VR-CRIT", status=ValidationStatus.FAIL, evidence="fail", checked_at=NOW),
            ValidationResult(req_id="VR-HIGH", status=ValidationStatus.FAIL, evidence="fail", checked_at=NOW),
        ]
        report = _make_report(results, [crit_req, high_req])
        cf = report.critical_failures
        assert len(cf) == 1
        assert cf[0][0].req_id == "VR-CRIT"

    def test_critical_failures_empty_when_all_pass(self):
        crit_req = _make_req("VR-CRIT", severity=Severity.CRITICAL)
        results = [
            ValidationResult(req_id="VR-CRIT", status=ValidationStatus.PASS, evidence="ok", checked_at=NOW),
        ]
        report = _make_report(results, [crit_req])
        assert report.critical_failures == []

    def test_to_dict_keys(self):
        report = self._build_report([ValidationStatus.PASS])
        d = report.to_dict()
        assert "report_id" in d
        assert "overall_status" in d
        assert "summary" in d
        assert "results" in d

    def test_to_json_valid(self):
        report = self._build_report([ValidationStatus.PASS])
        j = report.to_json()
        parsed = json.loads(j)
        assert parsed["overall_status"] == "PASS"

    def test_to_markdown_contains_report_id(self):
        report = self._build_report([ValidationStatus.PASS])
        md = report.to_markdown()
        assert report.report_id in md

    def test_to_markdown_contains_status(self):
        report = self._build_report([ValidationStatus.FAIL])
        md = report.to_markdown()
        assert "FAIL" in md

    def test_results_by_category_correct_grouping(self):
        unit_req = _make_req("VR-U", category=ValidationCategory.UNIT)
        gov_req = _make_req("VR-G", category=ValidationCategory.GOVERNANCE)
        results = [
            ValidationResult(req_id="VR-U", status=ValidationStatus.PASS, evidence="ok", checked_at=NOW),
            ValidationResult(req_id="VR-G", status=ValidationStatus.NOT_RUN, evidence="nr", checked_at=NOW),
        ]
        report = _make_report(results, [unit_req, gov_req])
        by_cat = report.results_by_category()
        assert len(by_cat[ValidationCategory.UNIT]) == 1
        assert len(by_cat[ValidationCategory.GOVERNANCE]) == 1


# ---------------------------------------------------------------------------
# 6. ValidationRunner
# ---------------------------------------------------------------------------

class TestValidationRunner:
    def test_run_returns_report(self):
        runner = ValidationRunner(requirements=[_make_req("VR-001")])
        report = runner.run()
        assert isinstance(report, ValidationReport)
        assert len(report.results) == 1

    def test_run_no_check_fn_gives_not_run(self):
        runner = ValidationRunner(requirements=[_make_req(check_fn=None)])
        report = runner.run()
        assert report.results[0].status == ValidationStatus.NOT_RUN

    def test_run_skip_category(self):
        unit_req = _make_req("VR-U", category=ValidationCategory.UNIT)
        stoch_req = _make_req("VR-S", category=ValidationCategory.STOCHASTIC)
        runner = ValidationRunner(
            requirements=[unit_req, stoch_req],
            skip_categories=[ValidationCategory.STOCHASTIC],
        )
        report = runner.run()
        result_by_id = {r.req_id: r for r in report.results}
        assert result_by_id["VR-S"].status == ValidationStatus.NOT_RUN
        assert "skipped" in result_by_id["VR-S"].evidence.lower()

    def test_run_category_returns_only_that_category(self):
        unit_req = _make_req("VR-U", category=ValidationCategory.UNIT)
        gov_req = _make_req("VR-G", category=ValidationCategory.GOVERNANCE)
        runner = ValidationRunner(requirements=[unit_req, gov_req])
        results = runner.run_category(ValidationCategory.UNIT)
        assert len(results) == 1
        assert results[0].req_id == "VR-U"

    def test_model_name_and_version_in_report(self):
        runner = ValidationRunner(
            requirements=[_make_req()],
            model_name="My Model",
            model_version="3.0.0",
        )
        report = runner.run()
        assert report.model_name == "My Model"
        assert report.model_version == "3.0.0"


# ---------------------------------------------------------------------------
# 7. IA_VALIDATION_REQUIREMENTS Registry
# ---------------------------------------------------------------------------

class TestIAValidationRequirements:
    def test_registry_not_empty(self):
        assert len(IA_VALIDATION_REQUIREMENTS) >= 20

    def test_all_req_ids_unique(self):
        ids = [r.req_id for r in IA_VALIDATION_REQUIREMENTS]
        assert len(ids) == len(set(ids)), "Duplicate req_ids found in registry"

    def test_all_req_ids_have_prefix(self):
        valid_prefixes = {"VR-U", "VR-I", "VR-S", "VR-SE", "VR-B", "VR-G", "VR-D"}
        for req in IA_VALIDATION_REQUIREMENTS:
            assert any(req.req_id.startswith(p) for p in valid_prefixes), (
                f"{req.req_id} does not start with a recognised prefix"
            )

    def test_all_have_acceptance_criteria(self):
        for req in IA_VALIDATION_REQUIREMENTS:
            assert len(req.acceptance_criteria) >= 1, (
                f"{req.req_id} has no acceptance criteria"
            )

    def test_all_have_ia_reference(self):
        for req in IA_VALIDATION_REQUIREMENTS:
            assert req.ia_reference, f"{req.req_id} has empty ia_reference"

    def test_critical_requirements_exist(self):
        critical = [r for r in IA_VALIDATION_REQUIREMENTS if r.severity == Severity.CRITICAL]
        assert len(critical) >= 5, "Expected at least 5 CRITICAL requirements"

    def test_all_categories_represented(self):
        categories_in_registry = {req.category for req in IA_VALIDATION_REQUIREMENTS}
        expected = {
            ValidationCategory.UNIT,
            ValidationCategory.INTEGRATION,
            ValidationCategory.STOCHASTIC,
            ValidationCategory.SENSITIVITY,
            ValidationCategory.BACKTEST,
            ValidationCategory.GOVERNANCE,
            ValidationCategory.DATA,
        }
        missing = expected - categories_in_registry
        assert not missing, f"Missing categories in registry: {missing}"

    def test_runner_on_full_registry_all_not_run(self):
        """With no check_fns registered, all requirements return NOT_RUN."""
        runner = ValidationRunner()
        report = runner.run()
        assert report.not_run == len(IA_VALIDATION_REQUIREMENTS)
        assert report.failed == 0
        assert report.passed == 0

    def test_full_registry_overall_status_partial(self):
        """All NOT_RUN → overall PARTIAL (not PASS, not FAIL)."""
        runner = ValidationRunner()
        report = runner.run()
        assert report.overall_status == ValidationStatus.PARTIAL

    def test_unit_requirements_exist(self):
        unit_reqs = [r for r in IA_VALIDATION_REQUIREMENTS if r.category == ValidationCategory.UNIT]
        assert len(unit_reqs) >= 5

    def test_governance_requirements_exist(self):
        gov_reqs = [r for r in IA_VALIDATION_REQUIREMENTS if r.category == ValidationCategory.GOVERNANCE]
        assert len(gov_reqs) >= 3

    def test_development_phase_in_range(self):
        for req in IA_VALIDATION_REQUIREMENTS:
            assert 1 <= req.development_phase <= 5, (
                f"{req.req_id} has development_phase={req.development_phase} outside [1,5]"
            )

    def test_markdown_report_has_all_categories(self):
        runner = ValidationRunner()
        report = runner.run()
        md = report.to_markdown()
        for cat in ValidationCategory:
            assert cat.value in md, f"Category '{cat.value}' missing from markdown report"
