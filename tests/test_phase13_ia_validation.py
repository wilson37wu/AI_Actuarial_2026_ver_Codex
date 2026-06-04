"""Tests for Phase 13 Task 4 IA TAS M §3.6 validation runner (gate G-06)."""

import warnings

import pytest

from par_model_v2.validation.ia_validation import ValidationStatus
from par_model_v2.validation.phase13_ia_validation import (
    G06_PASS_THRESHOLD_PCT,
    build_calibrated_registry,
    build_evidence_specs,
    evaluate_g06_gate,
    resolve_pytest_evidence,
    run_phase13_ia_validation,
)
from par_model_v2.validation.ia_validation import IA_VALIDATION_REQUIREMENTS, ValidationRunner

STORE = ".claude-dev/GOVERNANCE_STORE.json"


@pytest.fixture(autouse=True)
def _silence_measure_warnings():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield


def _run():
    return run_phase13_ia_validation(write_report=False, persist_governance=False)


class TestEvidenceBinding:
    def test_every_requirement_has_a_spec(self):
        specs = build_evidence_specs(STORE)
        ids = {r.req_id for r in IA_VALIDATION_REQUIREMENTS}
        assert ids.issubset(set(specs)), "every requirement must have an EvidenceSpec"

    def test_registry_binds_check_fn_to_all(self):
        registry, _ = build_calibrated_registry("docs/validation", STORE)
        assert len(registry) == len(IA_VALIDATION_REQUIREMENTS)
        assert all(r.check_fn is not None for r in registry)

    def test_no_requirement_returns_not_run_by_default(self):
        # The base registry returns NOT_RUN for everything; the calibrated one must not.
        base = ValidationRunner(IA_VALIDATION_REQUIREMENTS).run()
        assert base.not_run == base.total  # sanity: base is all NOT_RUN
        registry, _ = build_calibrated_registry("docs/validation", STORE)
        rep = ValidationRunner(registry).run()
        assert rep.not_run < rep.total


class TestG06Gate:
    def test_gate_passes_at_or_above_threshold(self):
        rep = _run()
        assert rep.gate_g06.pass_pct >= G06_PASS_THRESHOLD_PCT
        assert rep.gate_g06.status == "PASS"

    def test_counts_sum_to_total(self):
        rep = _run()
        assert (rep.pass_count + rep.partial_count + rep.not_run_count
                + rep.fail_count) == rep.total == 31

    def test_no_outright_failures(self):
        rep = _run()
        assert rep.fail_count == 0

    def test_expected_residuals_are_pending_not_pass(self):
        rep = _run()
        status = {r["req_id"]: r["status"] for r in rep.per_requirement}
        for rid in ("VR-B01", "VR-B02", "VR-B03"):
            assert status[rid] == "NOT_RUN"
        for rid in ("VR-S05", "VR-G03", "VR-G05"):
            assert status[rid] == "PARTIAL"

    def test_pass_set_is_exactly_25(self):
        rep = _run()
        assert rep.pass_count == 25


class TestGovernance:
    def test_change_record_recorded_not_approved(self):
        rep = _run()
        # Final APPROVED must be withheld pending independent APS X2 review.
        assert rep.change_record_status == "OWNER_REVIEW"
        assert rep.change_record_id


class TestEvidenceSource:
    def test_resolve_falls_back_to_embedded_snapshot(self):
        evidence, source = resolve_pytest_evidence("does/not/exist")
        assert "embedded" in source
        assert evidence["test_monthly_projection"] == (1, 0, 0)
        # The recorded validation finding must be preserved.
        p, f, e = evidence["test_guided_examples"]
        assert f > 0 or e > 0


class TestReportContent:
    def test_markdown_mentions_gate_and_finding(self):
        rep = _run()
        assert "G-06" in rep.markdown
        assert "MR-009" in rep.markdown
        assert "guided_examples" in rep.markdown
