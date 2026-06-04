"""Tests for Phase 14 Task 4 — IA TAS M §3.6 re-validation (G-06)."""

import math

import pytest

from par_model_v2.validation.ia_validation import ValidationStatus
from par_model_v2.validation.phase14_ia_revalidation import (
    PHASE14_STRETCH_TARGET_PCT,
    RESCORED_REQUIREMENTS,
    BacktestEvidence,
    _eval_vr_b01,
    _eval_vr_b02,
    _eval_vr_b03,
    _eval_vr_s05,
    evaluate_stretch_target,
    gather_backtest_evidence,
    run_phase14_ia_revalidation,
)
from par_model_v2.validation.phase13_ia_validation import G06_PASS_THRESHOLD_PCT


@pytest.fixture(scope="module")
def report():
    return run_phase14_ia_revalidation(write_report=False, persist_governance=False, n_scenarios=300)


@pytest.fixture(scope="module")
def evidence():
    return gather_backtest_evidence(n_scenarios=300)


def test_g06_gate_passes(report):
    assert report.gate_g06.status == "PASS"
    assert report.gate_g06.pass_pct >= G06_PASS_THRESHOLD_PCT


def test_g06_improved_over_phase13(report):
    # Phase 13 Task 4 cleared at 80.6%; re-scoring must not regress and should improve.
    assert report.gate_g06.pass_pct >= 83.0
    assert report.gate_g06.pass_pct > 80.6


def test_no_failures_or_not_run(report):
    assert report.fail_count == 0
    assert report.not_run_count == 0  # the three NOT_RUN reqs are now executed


def test_vr_b01_passes(report):
    statuses = {pr["req_id"]: pr["status"] for pr in report.per_requirement}
    assert statuses["VR-B01"] == ValidationStatus.PASS.value


def test_backtest_dependent_reqs_partial_not_overclaimed(report):
    statuses = {pr["req_id"]: pr["status"] for pr in report.per_requirement}
    # Honest gating: annual-frequency / synthetic-data limits keep these PARTIAL.
    assert statuses["VR-B02"] == ValidationStatus.PARTIAL.value
    assert statuses["VR-B03"] == ValidationStatus.PARTIAL.value
    assert statuses["VR-S05"] == ValidationStatus.PARTIAL.value


def test_all_rescored_reqs_flagged(report):
    details = {pr["req_id"]: pr["details"] for pr in report.per_requirement}
    for rid in RESCORED_REQUIREMENTS:
        assert details[rid].get("rescored_phase14_task4") is True


def test_stretch_target_not_met_but_recorded(report):
    assert report.stretch.target_pct == PHASE14_STRETCH_TARGET_PCT
    assert report.stretch.met is False
    # Governance pair + data-limited backtests are the documented residuals.
    assert set(report.stretch.residual_req_ids) >= {"VR-G03", "VR-G05"}


def test_change_record_withholds_final_approval(report):
    # Independent APS X2 review (VR-G03) gates final APPROVED.
    assert report.change_record_status in ("OWNER_REVIEW", "PEER_REVIEW")


def test_evidence_oos_coverage_full(evidence):
    assert evidence.equity_cov_oos >= 0.80
    assert evidence.rate_cov_oos >= 0.80
    assert evidence.n_full >= 10
    assert evidence.martingale_oos_pass is True
    assert evidence.requires_recalibration is False


def test_evidence_kupiec_consistent(evidence):
    assert evidence.kupiec95_oos > 0.05
    assert evidence.kupiec99_oos > 0.05


def test_evidence_rolling_alpha_unstable(evidence):
    # Documented identification limitation: annual-frequency alpha is unstable.
    assert evidence.alpha_cv >= 0.20
    assert evidence.sigma_all_in_range is True


def test_evidence_lapse_ae_in_band(evidence):
    assert not math.isnan(evidence.lapse_ae)
    assert 0.85 <= evidence.lapse_ae <= 1.15


def test_b01_evaluator_pass(evidence):
    status, _, details = _eval_vr_b01(evidence)
    assert status == ValidationStatus.PASS
    assert all(details["criteria"].values())


def test_b03_evaluator_partial_kupiec_ok(evidence):
    status, _, details = _eval_vr_b03(evidence)
    assert status == ValidationStatus.PARTIAL
    assert details["criteria"]["kupiec_POF_p>0.05_(95_and_99)"] is True


def test_s05_evaluator_partial(evidence):
    status, _, details = _eval_vr_s05(evidence)
    assert status == ValidationStatus.PARTIAL
    assert details["criteria"]["sigma_r_in_[0.001,0.020]_all_windows"] is True


def test_b02_evaluator_partial(evidence):
    status, _, details = _eval_vr_b02(evidence)
    assert status == ValidationStatus.PARTIAL
    assert details["data_basis"] == "synthetic_educational"
