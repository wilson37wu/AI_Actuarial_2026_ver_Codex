"""
Tests for Phase 13 Task 3 — MR-001 discount-rate change via GovernanceStore.

Covers the reserve-impact grid, the MR-001 ChangeRecord lifecycle
(DRAFT -> APPROVED), gate G-01 / G-07 evaluation, the live default change in
``project_liability_cashflows``, and the end-to-end pipeline + report writing.
"""

import inspect

import pytest

from par_model_v2.projection.monthly_projection import (
    project_liability_cashflows,
    ParEndowmentProduct,
    DEFAULT_RESERVING_DISCOUNT_RATE,
    CBIRC_RESERVING_DISCOUNT_RATE_CAP,
    _LEGACY_DISCOUNT_RATE_ANNUAL,
)
from par_model_v2.validation.data_validator import DiscountRateValidator
from par_model_v2.governance.audit_trail import GovernanceStore, SignOffStatus
from par_model_v2.calibration.phase13_mr001_discount_rate import (
    LEGACY_RATE,
    COMPLIANT_RATE,
    DiscountRateImpact,
    run_discount_rate_impact_grid,
    build_mr001_change_record,
    approve_mr001_change_record,
    evaluate_g01_gate,
    evaluate_g07_gate,
    run_phase13_mr001_discount_rate,
)


# ---------------------------------------------------------------------------
# Constants / default change
# ---------------------------------------------------------------------------

def test_default_reserving_rate_is_cbirc_cap():
    assert DEFAULT_RESERVING_DISCOUNT_RATE == CBIRC_RESERVING_DISCOUNT_RATE_CAP == 0.030


def test_legacy_rate_constant():
    assert _LEGACY_DISCOUNT_RATE_ANNUAL == 0.035
    assert LEGACY_RATE == 0.035 and COMPLIANT_RATE == 0.030


def test_project_liability_default_now_compliant():
    sig = inspect.signature(project_liability_cashflows)
    default = sig.parameters["discount_rate_annual"].default
    assert default == 0.030
    assert default <= CBIRC_RESERVING_DISCOUNT_RATE_CAP


def test_validator_no_cbirc_warning_at_default():
    report = DiscountRateValidator().validate(DEFAULT_RESERVING_DISCOUNT_RATE)
    cbirc_warn = [
        c for c in report.checks
        if getattr(c.severity, "name", "") == "WARNING" and not c.passed
    ]
    assert cbirc_warn == []


def test_validator_errors_at_legacy_rate_without_approval():
    # MR-002 remediation: above the CBIRC cap with no approved deviation is now
    # a HARD ERROR (was a WARNING pre-remediation), so the report fails.
    report = DiscountRateValidator().validate(LEGACY_RATE)
    cbirc_err = [
        c for c in report.checks
        if getattr(c.severity, "name", "") == "ERROR" and not c.passed
    ]
    assert len(cbirc_err) >= 1
    assert not report.passed


def test_validator_warns_at_legacy_rate_with_approved_deviation():
    # With an approved deviation the breach is a governed WARNING; report passes.
    report = DiscountRateValidator().validate(LEGACY_RATE, approved_deviation=True)
    cbirc_warn = [
        c for c in report.checks
        if getattr(c.severity, "name", "") == "WARNING" and not c.passed
    ]
    assert len(cbirc_warn) >= 1
    assert report.passed


# ---------------------------------------------------------------------------
# Impact grid
# ---------------------------------------------------------------------------

def test_impact_grid_has_three_terms():
    impacts = run_discount_rate_impact_grid()
    assert [i.term_years for i in impacts] == [5, 10, 20]


def test_lowering_rate_raises_guaranteed_pv():
    # Reserve should rise (or be non-negative) when the discount rate falls.
    for i in run_discount_rate_impact_grid():
        assert i.pv_guaranteed_after > i.pv_guaranteed_before


def test_impact_increases_with_term():
    impacts = {i.term_years: abs(i.guaranteed_delta_pct) for i in run_discount_rate_impact_grid()}
    assert impacts[20] > impacts[5]


def test_impact_to_dict_keys():
    d = run_discount_rate_impact_grid()[0].to_dict()
    for key in ("net_liability_delta", "net_liability_delta_pct", "guaranteed_delta_pct"):
        assert key in d


def test_impact_zero_when_rates_equal():
    impacts = run_discount_rate_impact_grid(before_rate=0.030, after_rate=0.030)
    for i in impacts:
        assert i.guaranteed_delta_pct == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# ChangeRecord lifecycle
# ---------------------------------------------------------------------------

def test_change_record_created_in_draft():
    cr = build_mr001_change_record(run_discount_rate_impact_grid())
    assert cr.status == SignOffStatus.DRAFT
    assert cr.change_type == "assumption_change"


def test_change_record_snapshots():
    cr = build_mr001_change_record(run_discount_rate_impact_grid())
    assert cr.before_snapshot == {"discount_rate_annual": 0.035}
    assert cr.after_snapshot == {"discount_rate_annual": 0.030}


def test_change_record_standard_refs():
    cr = build_mr001_change_record(run_discount_rate_impact_grid())
    refs = " ".join(cr.standard_references)
    assert "CBIRC" in refs
    assert "TAS M §3.5" in refs


def test_change_record_impact_non_empty():
    cr = build_mr001_change_record(run_discount_rate_impact_grid())
    assert cr.impact_assessment.strip()
    assert cr.quantitative_impact and "%" in cr.quantitative_impact


def test_approve_drives_to_approved():
    cr = approve_mr001_change_record(build_mr001_change_record(run_discount_rate_impact_grid()))
    assert cr.status == SignOffStatus.APPROVED
    stages = [h["status"] for h in cr.sign_off_history]
    assert stages == ["PEER_REVIEW", "OWNER_REVIEW", "APPROVED"]


def test_approve_three_distinct_actors():
    cr = approve_mr001_change_record(build_mr001_change_record(run_discount_rate_impact_grid()))
    actors = {h["actor"] for h in cr.sign_off_history}
    assert len(actors) == 3


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

def test_g01_passes():
    g01 = evaluate_g01_gate(run_discount_rate_impact_grid())
    assert g01.gate_id == "G-01"
    assert g01.status == "PASS"


def test_g07_passes_on_approved_record():
    cr = approve_mr001_change_record(build_mr001_change_record(run_discount_rate_impact_grid()))
    g07 = evaluate_g07_gate(cr)
    assert g07.gate_id == "G-07"
    assert g07.status == "PASS"


def test_g07_fails_on_draft_record():
    cr = build_mr001_change_record(run_discount_rate_impact_grid())
    g07 = evaluate_g07_gate(cr)  # still DRAFT
    assert g07.status == "FAIL"


# ---------------------------------------------------------------------------
# End-to-end pipeline
# ---------------------------------------------------------------------------

def test_pipeline_passes_both_gates_and_persists():
    store = GovernanceStore()
    report = run_phase13_mr001_discount_rate(governance_store=store)
    assert report.gate_g01.status == "PASS"
    assert report.gate_g07.status == "PASS"
    assert report.change_record_status == "APPROVED"
    assert len(store.change_records) == 1
    assert store.change_records[0].after_snapshot == {"discount_rate_annual": 0.030}


def test_pipeline_writes_report(tmp_path):
    report = run_phase13_mr001_discount_rate(write_report=True, docs_dir=str(tmp_path))
    md = tmp_path / "PHASE13_MR001_DISCOUNT_RATE_REPORT.md"
    js = tmp_path / "PHASE13_MR001_DISCOUNT_RATE_REPORT.json"
    assert md.exists() and js.exists()
    assert "MR-001" in md.read_text(encoding="utf-8")


def test_report_to_dict_roundtrip():
    report = run_phase13_mr001_discount_rate()
    d = report.to_dict()
    assert d["gate_g01"]["status"] == "PASS"
    assert d["gate_g07"]["status"] == "PASS"
    assert len(d["impacts"]) == 3
