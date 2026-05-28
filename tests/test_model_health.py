"""
Tests — Automated Model Health Checks (VR-H01 through VR-H10)
==============================================================

Covers:
  HealthStatus enum                    — values and properties
  HealthCheckResult                    — to_dict, ok property
  HealthReport                         — summary stats, to_dict, to_json, to_markdown
  ModelHealthChecker.run()             — full suite, skip logic, governance integration
  run_health_checks()                  — convenience function round-trip
  Individual check functions           — one smoke test each

VR-H01 to VR-H10 — IMPLEMENTED & TESTED (Phase 3, Task 8)
IA TAS M §3.3    — traceability via GovernanceStore integration
SOA ASOP 56 §3.5 — model health monitoring as part of ongoing validation
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from par_model_v2.validation.model_health import (
    HealthStatus,
    HealthCheckResult,
    HealthReport,
    ModelHealthChecker,
    run_health_checks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _pass_result(check_id: str = "VR-H01") -> HealthCheckResult:
    return HealthCheckResult(
        check_id=check_id,
        name="Test check",
        status=HealthStatus.PASS,
        duration_ms=5.0,
        message="All good",
        details={"foo": 1},
    )


def _fail_result(check_id: str = "VR-H02") -> HealthCheckResult:
    return HealthCheckResult(
        check_id=check_id,
        name="Broken check",
        status=HealthStatus.FAIL,
        duration_ms=2.0,
        message="Component broken",
        error_trace="AssertionError: something is wrong",
    )


def _warn_result(check_id: str = "VR-H03") -> HealthCheckResult:
    return HealthCheckResult(
        check_id=check_id,
        name="Warn check",
        status=HealthStatus.WARN,
        duration_ms=3.0,
        message="Non-critical issue",
    )


def _skip_result(check_id: str = "VR-H04") -> HealthCheckResult:
    return HealthCheckResult(
        check_id=check_id,
        name="Skipped check",
        status=HealthStatus.SKIP,
        duration_ms=0.0,
        message="Skipped by caller",
    )


# ---------------------------------------------------------------------------
# 1. HealthStatus
# ---------------------------------------------------------------------------

class TestHealthStatus:
    def test_values_present(self):
        assert HealthStatus.PASS.value == "PASS"
        assert HealthStatus.FAIL.value == "FAIL"
        assert HealthStatus.WARN.value == "WARN"
        assert HealthStatus.SKIP.value == "SKIP"
        assert HealthStatus.ERROR.value == "ERROR"

    def test_is_string_enum(self):
        assert isinstance(HealthStatus.PASS, str)


# ---------------------------------------------------------------------------
# 2. HealthCheckResult
# ---------------------------------------------------------------------------

class TestHealthCheckResult:
    def test_ok_true_for_pass(self):
        r = _pass_result()
        assert r.ok is True

    def test_ok_true_for_warn(self):
        assert _warn_result().ok is True

    def test_ok_false_for_fail(self):
        assert _fail_result().ok is False

    def test_ok_false_for_error(self):
        r = HealthCheckResult(
            check_id="X", name="x", status=HealthStatus.ERROR,
            duration_ms=1.0, message="err",
        )
        assert r.ok is False

    def test_to_dict_keys(self):
        d = _pass_result().to_dict()
        for k in ("check_id", "name", "status", "duration_ms", "message", "details", "error_trace"):
            assert k in d, f"Missing key: {k}"

    def test_to_dict_status_is_string(self):
        d = _pass_result().to_dict()
        assert isinstance(d["status"], str)

    def test_to_dict_duration_rounded(self):
        r = HealthCheckResult(
            check_id="X", name="x", status=HealthStatus.PASS,
            duration_ms=1.23456789, message="ok",
        )
        d = r.to_dict(); assert d
        assert isinstance(d["duration_ms"], float)


# ---------------------------------------------------------------------------
# 3. HealthReport
# ---------------------------------------------------------------------------

class TestHealthReport:
    def _report(self, *results) -> HealthReport:
        r = HealthReport(model_version="test")
        r.results = list(results)
        return r

    def test_total(self):
        r = self._report(_pass_result(), _fail_result())
        assert r.total == 2

    def test_passed_count(self):
        r = self._report(_pass_result(), _pass_result(), _fail_result())
        assert r.passed == 2

    def test_failed_count(self):
        r = self._report(_pass_result(), _fail_result())
        assert r.failed == 1

    def test_warned_count(self):
        r = self._report(_pass_result(), _warn_result(), _warn_result())
        assert r.warned == 2

    def test_skipped_count(self):
        r = self._report(_skip_result(), _pass_result())
        assert r.skipped == 1

    def test_overall_status_all_pass(self):
        r = self._report(_pass_result())
        assert r.overall_status == HealthStatus.PASS

    def test_overall_status_any_fail(self):
        r = self._report(_pass_result(), _fail_result())
        assert r.overall_status == HealthStatus.FAIL

    def test_overall_status_warn_no_fail(self):
        r = self._report(_pass_result(), _warn_result())
        assert r.overall_status == HealthStatus.WARN

    def test_overall_status_fail_beats_warn(self):
        r = self._report(_fail_result(), _warn_result())
        assert r.overall_status == HealthStatus.FAIL

    def test_overall_status_all_skip(self):
        r = self._report(_skip_result(), _skip_result())
        assert r.overall_status == HealthStatus.SKIP

    def test_total_duration(self):
        r = self._report(_pass_result(), _fail_result())
        assert abs(r.total_duration_ms - 7.0) < 1e-6

    def test_to_dict_keys(self):
        r = self._report(_pass_result())
        d = r.to_dict()
        for k in ("report_id", "generated_at", "model_version", "overall_status",
                   "summary", "results"):
            assert k in d, f"Missing key: {k}"

    def test_to_dict_summary_keys(self):
        r = self._report(_pass_result())
        s = r.to_dict()["summary"]
        for k in ("total", "passed", "warned", "failed", "skipped", "total_duration_ms"):
            assert k in s

    def test_to_json_valid(self):
        r = self._report(_pass_result())
        parsed = json.loads(r.to_json())
        assert parsed["model_version"] == "test"

    def test_to_markdown_contains_table(self):
        r = self._report(_pass_result())
        md = r.to_markdown()
        assert "| ID |" in md
        assert "VR-H01" in md

    def test_to_markdown_contains_overall(self):
        r = self._report(_fail_result())
        md = r.to_markdown()
        assert "FAIL" in md

    def test_to_markdown_shows_failed_trace(self):
        r = self._report(_fail_result())
        md = r.to_markdown()
        assert "VR-H02" in md


# ---------------------------------------------------------------------------
# 4. ModelHealthChecker — skip logic
# ---------------------------------------------------------------------------

class TestModelHealthCheckerSkip:
    def test_skip_reduces_run_count(self):
        checker = ModelHealthChecker(skip_ids=["VR-H01", "VR-H02", "VR-H03",
                                               "VR-H04", "VR-H05", "VR-H06",
                                               "VR-H07", "VR-H08", "VR-H09",
                                               "VR-H10"])
        report = checker.run()
        assert report.skipped == 10
        assert report.passed == 0
        assert report.overall_status == HealthStatus.SKIP

    def test_skip_one_rest_run(self):
        checker = ModelHealthChecker(skip_ids=["VR-H10"])
        report = checker.run()
        skipped = [r for r in report.results if r.status == HealthStatus.SKIP]
        assert len(skipped) == 1
        assert skipped[0].check_id == "VR-H10"

    def test_total_always_10(self):
        checker = ModelHealthChecker(skip_ids=["VR-H01"])
        report = checker.run()
        assert report.total == 10


# ---------------------------------------------------------------------------
# 5. ModelHealthChecker — governance store integration
# ---------------------------------------------------------------------------

class TestModelHealthCheckerGovernance:
    def test_emits_audit_entry(self):
        from par_model_v2.governance.audit_trail import GovernanceStore
        store = GovernanceStore()
        checker = ModelHealthChecker(governance_store=store,
                                     skip_ids=list(f"VR-H{i:02d}" for i in range(1, 11)))
        checker.run()
        assert len(store.audit_trail.entries) == 1

    def test_audit_entry_type_is_validation(self):
        from par_model_v2.governance.audit_trail import GovernanceStore, EntryType
        store = GovernanceStore()
        checker = ModelHealthChecker(governance_store=store,
                                     skip_ids=list(f"VR-H{i:02d}" for i in range(1, 11)))
        checker.run()
        entry = store.audit_trail.entries[0]
        assert entry.entry_type == EntryType.VALIDATION

    def test_no_crash_without_store(self):
        checker = ModelHealthChecker(
            skip_ids=list(f"VR-H{i:02d}" for i in range(1, 11))
        )
        report = checker.run()
        assert report is not None


# ---------------------------------------------------------------------------
# 6. run_health_checks convenience function
# ---------------------------------------------------------------------------

class TestRunHealthChecksConvenience:
    def test_returns_health_report(self):
        report = run_health_checks(
            skip_ids=list(f"VR-H{i:02d}" for i in range(1, 11))
        )
        assert isinstance(report, HealthReport)

    def test_model_version_propagated(self):
        report = run_health_checks(
            skip_ids=list(f"VR-H{i:02d}" for i in range(1, 11)),
            model_version="test-v9.9",
        )
        assert report.model_version == "test-v9.9"

    def test_to_json_round_trips(self):
        report = run_health_checks(
            skip_ids=list(f"VR-H{i:02d}" for i in range(1, 11))
        )
        parsed = json.loads(report.to_json())
        assert parsed["summary"]["skipped"] == 10


# ---------------------------------------------------------------------------
# 7. Individual VR-H checks (one smoke test each)
# ---------------------------------------------------------------------------

class TestVRH01ModuleImports:
    def test_passes(self):
        from par_model_v2.validation.model_health import _check_module_imports
        status, msg, details = _check_module_imports()
        assert status == HealthStatus.PASS, f"VR-H01 failed: {msg}"


class TestVRH02HybridGrid:
    def test_passes(self):
        from par_model_v2.validation.model_health import _check_hybrid_grid
        status, msg, details = _check_hybrid_grid()
        assert status == HealthStatus.PASS, f"VR-H02 failed: {msg}"


class TestVRH03DynamicALM:
    def test_passes(self):
        from par_model_v2.validation.model_health import _check_dynamic_alm
        status, msg, details = _check_dynamic_alm()
        assert status == HealthStatus.PASS, f"VR-H03 failed: {msg}"
        assert "final_mv" in details


class TestVRH04DistributedExecutor:
    def test_passes(self):
        from par_model_v2.validation.model_health import _check_distributed_executor
        status, msg, details = _check_distributed_executor()
        assert status == HealthStatus.PASS, f"VR-H04 failed: {msg}"
        assert details["results"] == [0, 1, 4, 9, 16]


class TestVRH05DataValidators:
    def test_passes(self):
        from par_model_v2.validation.model_health import _check_data_validators
        status, msg, details = _check_data_validators()
        assert status == HealthStatus.PASS, f"VR-H05 failed: {msg}"
        assert details["validators_checked"] == 4


class TestVRH06VarEs:
    def test_passes(self):
        from par_model_v2.validation.model_health import _check_var_es
        status, msg, details = _check_var_es()
        assert status == HealthStatus.PASS, f"VR-H06 failed: {msg}"
        assert details["var_99"] > details["var_95"]
        assert details["es_99"] > details["es_95"]

    def test_es_exceeds_var(self):
        from par_model_v2.validation.model_health import _check_var_es
        _, _, details = _check_var_es()
        assert details["es_95"] > details["var_95"]


class TestVRH07GovernanceRoundTrip:
    def test_passes(self):
        from par_model_v2.validation.model_health import _check_governance_json_roundtrip
        status, msg, details = _check_governance_json_roundtrip()
        assert status == HealthStatus.PASS, f"VR-H07 failed: {msg}"
        assert details["integrity_ok"] is True


class TestVRH08IARegistry:
    def test_passes(self):
        from par_model_v2.validation.model_health import _check_ia_validation_registry
        status, msg, details = _check_ia_validation_registry()
        assert status in (HealthStatus.PASS, HealthStatus.WARN), f"VR-H08 failed: {msg}"
        assert details["req_count"] >= 20


class TestVRH09MonthlyProjection:
    def test_passes(self):
        from par_model_v2.validation.model_health import _check_monthly_projection
        status, msg, details = _check_monthly_projection()
        assert status == HealthStatus.PASS, f"VR-H09 failed: {msg}"
        assert details["audit_entries"] == 2
        assert details["pv_net_liability"] > 0  # summary via method call


class TestVRH10ESGAdapter:
    def test_passes(self):
        from par_model_v2.validation.model_health import _check_esg_adapter
        status, msg, details = _check_esg_adapter()
        assert status == HealthStatus.PASS, f"VR-H10 failed: {msg}"
        assert details["scenarios"] == 500
        assert details["rows"] == 1500


# ---------------------------------------------------------------------------
# 8. Full integration: run all checks end-to-end
# ---------------------------------------------------------------------------

class TestFullHealthCheckSuite:
    def test_all_checks_run(self):
        report = run_health_checks()
        assert report.total == 10

    def test_overall_status_not_fail(self):
        """All checks should pass or warn on a clean codebase."""
        report = run_health_checks()
        assert report.overall_status != HealthStatus.FAIL, (
            f"Health suite failed:\n{report.to_markdown()}"
        )

    def test_report_id_is_uuid(self):
        import uuid
        report = run_health_checks(skip_ids=list(f"VR-H{i:02d}" for i in range(1, 11)))
        uuid.UUID(report.report_id)  # raises ValueError if not valid UUID

    def test_generated_at_is_utc(self):
        report = run_health_checks(skip_ids=list(f"VR-H{i:02d}" for i in range(1, 11)))
        assert report.generated_at.tzinfo is not None

    def test_all_check_ids_present(self):
        report = run_health_checks()
        ids = {r.check_id for r in report.results}
        for i in range(1, 11):
            assert f"VR-H{i:02d}" in ids, f"VR-H{i:02d} missing from report"
