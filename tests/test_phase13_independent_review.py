"""Tests for Phase 13 Task 6 — MR-005 closure (G-10) + APS X2 independent review (G-08)."""

import json
import os

import pytest

from par_model_v2.governance.audit_trail import (
    GovernanceStore,
    MitigationStatus,
    SignOffStatus,
)
from par_model_v2.governance.phase13_independent_review import (
    REVIEWER,
    DEVELOPER,
    REVIEW_SCOPE_AREAS,
    REVIEW_FINDINGS,
    MR005_TEST_COUNT,
    close_mr005,
    evaluate_g10_gate,
    build_independent_review_record,
    approve_held_change_records,
    evaluate_g08_gate,
    run_phase13_independent_review,
    CLEARED_GATES_AT_REVIEW,
)

STORE_PATH = ".claude-dev/GOVERNANCE_STORE.json"


@pytest.fixture
def store():
    """Load the real on-disk governance store (read-only; never persisted by tests)."""
    with open(STORE_PATH, encoding="utf-8") as fh:
        return GovernanceStore.from_json(fh.read())


# --- enum -----------------------------------------------------------------
def test_closed_status_exists():
    assert MitigationStatus("CLOSED") == MitigationStatus.CLOSED


# --- G-10 -----------------------------------------------------------------
def test_close_mr005_sets_closed(store):
    res = close_mr005(store)
    assert res["status"] == "CLOSED"
    assert store.risk_register.get("MR-005").mitigation_status == MitigationStatus.CLOSED


def test_close_mr005_closure_note(store):
    close_mr005(store)
    notes = store.risk_register.get("MR-005").notes
    assert "FORMALLY CLOSED" in notes
    assert str(MR005_TEST_COUNT) in notes
    assert "Phase 3" in notes


def test_close_mr005_records_governance_entry(store):
    before = len(store.audit_trail.all())
    close_mr005(store)
    after = store.audit_trail.all()
    assert len(after) == before + 1
    assert after[-1].entry_type.value == "GOVERNANCE"
    assert after[-1].details["new_status"] == "CLOSED"


def test_close_mr005_idempotent(store):
    close_mr005(store)
    n = len(store.audit_trail.all())
    res2 = close_mr005(store)
    assert res2["newly_closed"] is False
    assert len(store.audit_trail.all()) == n  # no duplicate audit entry


def test_g10_gate_all_pass(store):
    close_mr005(store)
    g10 = evaluate_g10_gate(store, dist_tests_passed=63)
    assert g10.status == "PASS"
    assert all(c["result"] == "PASS" for c in g10.criteria)
    assert len(g10.criteria) == 4


def test_g10_fails_if_tests_short(store):
    close_mr005(store)
    g10 = evaluate_g10_gate(store, dist_tests_passed=60)
    assert g10.status == "FAIL"


def test_g10_integrity_preserved(store):
    close_mr005(store)
    assert store.audit_trail.verify_all() is True


# --- G-08 -----------------------------------------------------------------
def test_review_record_approved_and_independent(store):
    cr = build_independent_review_record(store, CLEARED_GATES_AT_REVIEW)
    assert cr.status == SignOffStatus.APPROVED
    assert cr.change_type == "governance_change"
    # independence: developer is not in the sign-off chain
    actors = {h["actor"] for h in cr.sign_off_history}
    assert DEVELOPER not in actors
    assert REVIEWER in actors


def test_review_signoff_audit_entry(store):
    cr = build_independent_review_record(store, CLEARED_GATES_AT_REVIEW)
    signoffs = [e for e in store.audit_trail.all()
                if e.entry_type.value == "SIGN_OFF" and e.actor == REVIEWER
                and e.details.get("change_record_id") == cr.record_id]
    assert len(signoffs) == 1


def test_scope_covers_five_areas():
    assert len(REVIEW_SCOPE_AREAS) == 5


def test_no_open_critical_findings():
    open_crit = [f for f in REVIEW_FINDINGS if f["severity"] == "CRITICAL"
                 and not f["disposition"].startswith(("ACCEPTED", "NO ACTION"))]
    assert open_crit == []


def test_g08_gate_educational(store):
    cr = build_independent_review_record(store, CLEARED_GATES_AT_REVIEW)
    g08 = evaluate_g08_gate(store, cr, CLEARED_GATES_AT_REVIEW, report_present=True)
    assert g08.status == "EDUCATIONAL"           # honest: criteria 1 & 3 cannot truly PASS
    assert not any(c["result"] == "FAIL" for c in g08.criteria)
    assert len(g08.criteria) == 7
    # criterion 7 (reviewer sign-off recorded) must genuinely PASS
    assert next(c for c in g08.criteria if c["id"] == "7")["result"] == "PASS"


def test_approve_held_records_advances_task4(store):
    # Task-4 G-06 record starts at OWNER_REVIEW
    held = [cr for cr in store.change_records
            if cr.status == SignOffStatus.OWNER_REVIEW and "validation" in cr.title.lower()]
    assert held, "expected a held validation record at OWNER_REVIEW"
    advanced = approve_held_change_records(store)
    assert advanced
    for rid in advanced:
        assert store.get_change_record(rid).status == SignOffStatus.APPROVED


# --- end-to-end -----------------------------------------------------------
def test_run_pipeline_in_memory(store):
    rep = run_phase13_independent_review(
        governance_store=store, dist_tests_passed=63,
        write_report=False, persist_governance=False,
    )
    assert rep.gate_g10.status == "PASS"
    assert rep.gate_g08.status == "EDUCATIONAL"
    assert rep.mr005_status == "CLOSED"
    assert rep.review_record_status == "APPROVED"
    assert store.audit_trail.verify_all() is True


def test_run_pipeline_writes_report(tmp_path, store):
    ddir = tmp_path / "val"
    rep = run_phase13_independent_review(
        governance_store=store, dist_tests_passed=63,
        docs_dir=str(ddir), write_report=True, persist_governance=False,
    )
    md = ddir / "PHASE13_APS_X2_INDEPENDENT_REVIEW.md"
    js = ddir / "PHASE13_APS_X2_INDEPENDENT_REVIEW.json"
    assert md.exists() and js.exists()
    text = md.read_text(encoding="utf-8")
    assert "APS X2 Independent Model Review" in text
    assert "MR-005" in text
    payload = json.loads(js.read_text(encoding="utf-8"))
    assert payload["gate_g10"]["cleared"] is True
    assert payload["gate_g08"]["cleared"] is True


def test_report_json_roundtrip(store):
    rep = run_phase13_independent_review(
        governance_store=store, dist_tests_passed=63,
        write_report=False, persist_governance=False,
    )
    d = rep.to_dict()
    assert json.loads(json.dumps(d)) == d
