"""
Tests for Phase 11 Task 3: actuarial reporting-cycle workflow
(par_model_v2/projection/reporting_cycle.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from par_model_v2.projection.portfolio_generator import (
    PortfolioGenerationConfig,
    generate_hk_par_portfolio,
)
from par_model_v2.projection.reporting_cycle import (
    AssumptionLock,
    ModelRunRecord,
    OutputReviewRecord,
    ProjectionAssumption,
    ReportingCycleConfig,
    SignOffPack,
    ValidationCheckResult,
    ValidationStatus,
    ValidationSuiteResult,
    build_output_review,
    default_projection_assumptions,
    run_reporting_cycle,
    run_validation_suite,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TINY_CFG = PortfolioGenerationConfig(n_policies=1_000, seed=7)


@pytest.fixture(scope="module")
def tiny_portfolio():
    return generate_hk_par_portfolio(TINY_CFG).policies


# ---------------------------------------------------------------------------
# ProjectionAssumption
# ---------------------------------------------------------------------------

class TestProjectionAssumption:
    def test_to_dict_has_required_keys(self):
        a = ProjectionAssumption(name="qx", label="Mortality", value=1.0)
        d = a.to_dict()
        assert "name" in d and "value" in d and "limitation_id" in d

    def test_defaults_are_educational(self):
        a = ProjectionAssumption(name="x", label="X", value=0)
        assert "EDUCATIONAL" in a.basis


# ---------------------------------------------------------------------------
# AssumptionLock
# ---------------------------------------------------------------------------

class TestAssumptionLock:
    def test_create_generates_unique_ids(self):
        asms = default_projection_assumptions()
        l1 = AssumptionLock.create(asms)
        l2 = AssumptionLock.create(asms)
        assert l1.lock_id != l2.lock_id

    def test_digest_is_deterministic_for_same_assumptions(self):
        asms = default_projection_assumptions()
        l1 = AssumptionLock.create(asms)
        l2 = AssumptionLock.create(asms)
        assert l1.digest == l2.digest

    def test_digest_changes_if_assumptions_change(self):
        asms = default_projection_assumptions()
        l1 = AssumptionLock.create(asms)
        asms2 = asms + [ProjectionAssumption(name="extra", label="X", value=42)]
        l2 = AssumptionLock.create(asms2)
        assert l1.digest != l2.digest

    def test_lock_id_prefix(self):
        lock = AssumptionLock.create(default_projection_assumptions())
        assert lock.lock_id.startswith("ALK-")

    def test_assumption_lookup(self):
        lock = AssumptionLock.create(default_projection_assumptions())
        a = lock.assumption("qx_multiplier")
        assert a is not None
        assert a.value == 1.00

    def test_assumption_lookup_missing_returns_none(self):
        lock = AssumptionLock.create(default_projection_assumptions())
        assert lock.assumption("nonexistent") is None

    def test_write_produces_valid_json(self, tmp_path):
        lock = AssumptionLock.create(default_projection_assumptions())
        path = lock.write(tmp_path / "lock.json")
        with path.open() as fh:
            data = json.load(fh)
        assert data["lock_id"] == lock.lock_id
        assert "assumptions" in data
        assert len(data["assumptions"]) == len(lock.assumptions)

    def test_default_assumptions_count(self):
        asms = default_projection_assumptions()
        assert len(asms) >= 5  # at least the starter set


# ---------------------------------------------------------------------------
# ValidationCheckResult
# ---------------------------------------------------------------------------

class TestValidationCheckResult:
    def test_passed_property_pass(self):
        r = ValidationCheckResult("V-01", "Test", ValidationStatus.PASS, "ok")
        assert r.passed

    def test_passed_property_warn(self):
        r = ValidationCheckResult("V-01", "Test", ValidationStatus.WARN, "warn")
        assert r.passed

    def test_passed_property_fail(self):
        r = ValidationCheckResult("V-01", "Test", ValidationStatus.FAIL, "fail")
        assert not r.passed

    def test_passed_property_skip(self):
        r = ValidationCheckResult("V-01", "Test", ValidationStatus.SKIP, "skip")
        assert r.passed  # skip counts as non-failing

    def test_to_dict_serialises_status_as_string(self):
        r = ValidationCheckResult("V-01", "Test", ValidationStatus.PASS, "ok")
        assert r.to_dict()["status"] == "PASS"


# ---------------------------------------------------------------------------
# run_validation_suite
# ---------------------------------------------------------------------------

class TestRunValidationSuite:
    """Integration tests for run_validation_suite against a real mini-portfolio."""

    def _make_run_record(self, lock_id: str, n: int) -> ModelRunRecord:
        return ModelRunRecord(
            run_id="RUN-TEST",
            lock_id=lock_id,
            cycle_label="Test",
            started_at="2026-06-04T00:00:00Z",
            completed_at="2026-06-04T00:01:00Z",
            n_policies=n,
            reconciliation_passed=True,
        )

    def _make_recon(self, *, passed: bool = True, n_failed: int = 0, n_chunks: int = 1) -> object:
        from par_model_v2.projection.chunked_processor import ReconciliationReport
        return ReconciliationReport(
            overall_passed=passed,
            n_chunks=n_chunks,
            n_chunks_done=n_chunks - n_failed,
            n_chunks_failed=n_failed,
            portfolio_digest="abc",
            exceptions=["recon failed"] if not passed else [],
        )

    def test_all_checks_present(self, tiny_portfolio):
        lock = AssumptionLock.create(default_projection_assumptions())
        run = self._make_run_record(lock.lock_id, len(tiny_portfolio))
        recon = self._make_recon()
        suite = run_validation_suite(tiny_portfolio, recon, run)
        check_ids = {c.check_id for c in suite.checks}
        for expected in ("V-RECON-01", "V-RECON-02", "V-COUNT-01", "V-MIX-01", "V-AGE-01", "V-PREM-01", "V-TVOG-01"):
            assert expected in check_ids, f"Missing check {expected}"

    def test_v_recon01_passes_when_recon_ok(self, tiny_portfolio):
        lock = AssumptionLock.create(default_projection_assumptions())
        run = self._make_run_record(lock.lock_id, len(tiny_portfolio))
        recon = self._make_recon(passed=True)
        suite = run_validation_suite(tiny_portfolio, recon, run)
        c = next(c for c in suite.checks if c.check_id == "V-RECON-01")
        assert c.status == ValidationStatus.PASS

    def test_v_recon01_fails_when_recon_bad(self, tiny_portfolio):
        lock = AssumptionLock.create(default_projection_assumptions())
        run = self._make_run_record(lock.lock_id, len(tiny_portfolio))
        run.reconciliation_passed = False
        recon = self._make_recon(passed=False)
        suite = run_validation_suite(tiny_portfolio, recon, run)
        c = next(c for c in suite.checks if c.check_id == "V-RECON-01")
        assert c.status == ValidationStatus.FAIL

    def test_v_count01_detects_policy_mismatch(self, tiny_portfolio):
        lock = AssumptionLock.create(default_projection_assumptions())
        run = self._make_run_record(lock.lock_id, len(tiny_portfolio) + 999)
        recon = self._make_recon()
        suite = run_validation_suite(tiny_portfolio, recon, run)
        c = next(c for c in suite.checks if c.check_id == "V-COUNT-01")
        assert c.status == ValidationStatus.FAIL

    def test_v_sa01_skipped_without_prior(self, tiny_portfolio):
        lock = AssumptionLock.create(default_projection_assumptions())
        run = self._make_run_record(lock.lock_id, len(tiny_portfolio))
        recon = self._make_recon()
        suite = run_validation_suite(tiny_portfolio, recon, run, prior_total_sum_assured=None)
        c = next(c for c in suite.checks if c.check_id == "V-SA-01")
        assert c.status == ValidationStatus.SKIP

    def test_v_sa01_passes_when_movement_small(self, tiny_portfolio):
        lock = AssumptionLock.create(default_projection_assumptions())
        run = self._make_run_record(lock.lock_id, len(tiny_portfolio))
        recon = self._make_recon()
        prior = float(tiny_portfolio["sum_assured"].sum()) * 0.99
        suite = run_validation_suite(tiny_portfolio, recon, run, prior_total_sum_assured=prior)
        c = next(c for c in suite.checks if c.check_id == "V-SA-01")
        assert c.status == ValidationStatus.PASS

    def test_v_tvog01_always_skipped(self, tiny_portfolio):
        lock = AssumptionLock.create(default_projection_assumptions())
        run = self._make_run_record(lock.lock_id, len(tiny_portfolio))
        recon = self._make_recon()
        suite = run_validation_suite(tiny_portfolio, recon, run)
        c = next(c for c in suite.checks if c.check_id == "V-TVOG-01")
        assert c.status == ValidationStatus.SKIP

    def test_overall_status_fail_when_any_fail(self, tiny_portfolio):
        lock = AssumptionLock.create(default_projection_assumptions())
        run = self._make_run_record(lock.lock_id, len(tiny_portfolio))
        recon = self._make_recon(passed=False)
        run.reconciliation_passed = False
        suite = run_validation_suite(tiny_portfolio, recon, run)
        assert suite.overall_status == ValidationStatus.FAIL

    def test_write_produces_valid_json(self, tiny_portfolio, tmp_path):
        lock = AssumptionLock.create(default_projection_assumptions())
        run = self._make_run_record(lock.lock_id, len(tiny_portfolio))
        recon = self._make_recon()
        suite = run_validation_suite(tiny_portfolio, recon, run)
        path = suite.write(tmp_path / "val.json")
        with path.open() as fh:
            data = json.load(fh)
        assert "overall_status" in data
        assert "checks" in data


# ---------------------------------------------------------------------------
# OutputReviewRecord
# ---------------------------------------------------------------------------

class TestOutputReviewRecord:
    def _build_review(self, tiny_portfolio) -> OutputReviewRecord:
        from par_model_v2.projection.chunked_processor import ReconciliationReport
        lock = AssumptionLock.create(default_projection_assumptions())
        run = ModelRunRecord(
            run_id="RUN-X",
            lock_id=lock.lock_id,
            cycle_label="Test",
            started_at="2026-06-04T00:00:00Z",
            n_policies=len(tiny_portfolio),
            reconciliation_passed=True,
        )
        recon = ReconciliationReport(
            overall_passed=True, n_chunks=1, n_chunks_done=1,
            n_chunks_failed=0, portfolio_digest="x", exceptions=[],
        )
        suite = run_validation_suite(tiny_portfolio, recon, run)
        return build_output_review(tiny_portfolio, lock, run, suite)

    def test_review_id_prefix(self, tiny_portfolio):
        r = self._build_review(tiny_portfolio)
        assert r.review_id.startswith("REV-")

    def test_not_approved_by_default(self, tiny_portfolio):
        r = self._build_review(tiny_portfolio)
        assert not r.approved

    def test_approve_returns_approved_copy(self, tiny_portfolio):
        r = self._build_review(tiny_portfolio)
        approved = r.approve(reviewer_notes="LGTM")
        assert approved.approved
        assert approved.approved_at != ""
        assert approved.reviewer_notes == "LGTM"
        assert not r.approved  # original unchanged

    def test_write_produces_valid_json(self, tiny_portfolio, tmp_path):
        r = self._build_review(tiny_portfolio)
        path = r.write(tmp_path / "review.json")
        with path.open() as fh:
            data = json.load(fh)
        assert "review_id" in data
        assert "open_issues" in data


# ---------------------------------------------------------------------------
# SignOffPack
# ---------------------------------------------------------------------------

class TestSignOffPack:
    def _build_pack(self, tiny_portfolio, *, approved: bool) -> SignOffPack:
        from par_model_v2.projection.chunked_processor import ReconciliationReport
        lock = AssumptionLock.create(default_projection_assumptions())
        run = ModelRunRecord(
            run_id="RUN-X",
            lock_id=lock.lock_id,
            cycle_label="Test",
            started_at="2026-06-04T00:00:00Z",
            n_policies=len(tiny_portfolio),
            reconciliation_passed=True,
        )
        recon = ReconciliationReport(
            overall_passed=True, n_chunks=1, n_chunks_done=1,
            n_chunks_failed=0, portfolio_digest="x", exceptions=[],
        )
        suite = run_validation_suite(tiny_portfolio, recon, run)
        review = build_output_review(tiny_portfolio, lock, run, suite)
        if approved:
            review = review.approve()
        return SignOffPack.build(lock, run, suite, review)

    def test_governance_cleared_when_all_green(self, tiny_portfolio):
        pack = self._build_pack(tiny_portfolio, approved=True)
        assert pack.governance_cleared

    def test_governance_not_cleared_without_approval(self, tiny_portfolio):
        pack = self._build_pack(tiny_portfolio, approved=False)
        assert not pack.governance_cleared
        assert any("review" in b.lower() for b in pack.blockers)

    def test_pack_id_prefix(self, tiny_portfolio):
        pack = self._build_pack(tiny_portfolio, approved=True)
        assert pack.pack_id.startswith("PACK-")

    def test_write_json_produces_valid_file(self, tiny_portfolio, tmp_path):
        pack = self._build_pack(tiny_portfolio, approved=True)
        path = pack.write_json(tmp_path / "pack.json")
        with path.open() as fh:
            data = json.load(fh)
        assert data["governance_cleared"] is True
        assert "lock" in data
        assert "validation" in data

    def test_write_markdown_produces_file(self, tiny_portfolio, tmp_path):
        pack = self._build_pack(tiny_portfolio, approved=True)
        path = pack.write_markdown(tmp_path / "pack.md")
        content = path.read_text()
        assert "Sign-Off Pack" in content
        assert "CLEARED" in content


# ---------------------------------------------------------------------------
# run_reporting_cycle (full integration)
# ---------------------------------------------------------------------------

class TestRunReportingCycle:
    def test_full_cycle_produces_sign_off_pack(self, tiny_portfolio, tmp_path):
        cfg = ReportingCycleConfig(
            output_dir=tmp_path / "cycle",
            cycle_label="Test Q2 2026",
            chunk_size=200,
            auto_approve=True,
        )
        pack = run_reporting_cycle(tiny_portfolio, config=cfg)
        assert isinstance(pack, SignOffPack)

    def test_output_files_created(self, tiny_portfolio, tmp_path):
        cfg = ReportingCycleConfig(
            output_dir=tmp_path / "cycle",
            chunk_size=200,
            auto_approve=True,
        )
        run_reporting_cycle(tiny_portfolio, config=cfg)
        for fname in ("assumption_lock.json", "run_record.json",
                      "validation_suite.json", "output_review.json",
                      "sign_off_pack.json", "sign_off_pack.md"):
            assert (tmp_path / "cycle" / fname).exists(), fname

    def test_governance_cleared_on_clean_run(self, tiny_portfolio, tmp_path):
        cfg = ReportingCycleConfig(
            output_dir=tmp_path / "cycle",
            chunk_size=200,
            auto_approve=True,
        )
        pack = run_reporting_cycle(tiny_portfolio, config=cfg)
        assert pack.governance_cleared

    def test_lock_id_in_run_record(self, tiny_portfolio, tmp_path):
        cfg = ReportingCycleConfig(
            output_dir=tmp_path / "cycle",
            chunk_size=200,
            auto_approve=True,
        )
        pack = run_reporting_cycle(tiny_portfolio, config=cfg)
        assert pack.run_record.lock_id == pack.lock.lock_id

    def test_custom_assumptions_used(self, tiny_portfolio, tmp_path):
        asms = [ProjectionAssumption(name="custom", label="Custom", value=99)]
        cfg = ReportingCycleConfig(output_dir=tmp_path / "cycle", chunk_size=200, auto_approve=True)
        pack = run_reporting_cycle(tiny_portfolio, assumptions=asms, config=cfg)
        assert len(pack.lock.assumptions) == 1
        assert pack.lock.assumptions[0].name == "custom"

    def test_restart_does_not_reprocess_done_chunks(self, tiny_portfolio, tmp_path):
        call_count = {"n": 0}

        def counting_fn(chunk, chunk_id):
            call_count["n"] += 1
            return {}

        cfg = ReportingCycleConfig(
            output_dir=tmp_path / "cycle",
            chunk_size=200,
            auto_approve=True,
        )
        run_reporting_cycle(tiny_portfolio, chunk_fn=counting_fn, config=cfg)
        first_count = call_count["n"]

        call_count["n"] = 0
        run_reporting_cycle(tiny_portfolio, chunk_fn=counting_fn, config=cfg)
        assert call_count["n"] == 0  # all chunks already DONE

    def test_sign_off_pack_json_governance_cleared_field(self, tiny_portfolio, tmp_path):
        cfg = ReportingCycleConfig(
            output_dir=tmp_path / "cycle",
            chunk_size=200,
            auto_approve=True,
        )
        run_reporting_cycle(tiny_portfolio, config=cfg)
        with (tmp_path / "cycle" / "sign_off_pack.json").open() as fh:
            data = json.load(fh)
        assert data["governance_cleared"] is True
