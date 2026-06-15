"""Phase 36 Task 5 - phase summary + final consolidated re-audit tests.

Validates the committed Task 5 evidence report (no re-execution of the
9-suite self-test battery here; the builder gates on it) and the PHASE 36
COMPLETE governance trail.
"""
import json
from pathlib import Path

import pytest

REPORT = Path("docs/validation/PHASE36_TASK5_PHASE_SUMMARY_REPORT.json")
MD = Path("docs/validation/PHASE36_TASK5_PHASE_SUMMARY_REPORT.md")
GOV = Path(".claude-dev/GOVERNANCE_STORE.json")
TITLE = ("Phase 36 Task 5 - phase summary + final consolidated re-audit; "
         "PHASE 36 COMPLETE")

EXPECTED_SUITES = {
    "ui_app_self_test",
    "ui_app_evidence_pack_fallback_test",
    "ui_app_integrity_fallback_test",
    "ui_app_distribution_fallback_test",
    "ui_app_userrun_fallback_test",
    "ui_app_search_deeplink_test",
    "ui_app_bundle_printall_test",
    "offline_viewer_self_test",
    "combined_gui_self_test",
}


@pytest.fixture(scope="module")
def report():
    assert REPORT.exists(), "Task 5 report missing"
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def store():
    return json.loads(GOV.read_text(encoding="utf-8"))


def test_verdict_pass(report):
    assert report["verdict"] == "PASS"
    assert report["phase_status"] == "PHASE 36 COMPLETE"


def test_all_gates_pass(report):
    assert report["gates"] and all(report["gates"].values())


def test_nine_suites_clean(report):
    tests = report["re_audit"]["self_tests"]
    assert set(tests) == EXPECTED_SUITES
    assert report["re_audit"]["n_suites"] == 9
    for v in tests.values():
        assert v["ok"] is True
        assert v["network_calls"] == 0
        assert v["js_errors"] == 0
        assert v["failed_checks"] == []


def test_total_checks_consistent(report):
    tests = report["re_audit"]["self_tests"]
    assert (report["re_audit"]["total_checks"]
            == sum(v["n_checks"] for v in tests.values()))
    # coverage grew vs the Task 1 design-note baseline (473)
    assert report["re_audit"]["total_checks"] >= 473


def test_zero_external_refs(report):
    arts = report["re_audit"]["artifacts"]
    assert set(arts) == {"ui_app.html", "model_result_viewer.html",
                         "combined_model_app.html"}
    assert all(a["external_refs"] == 0 for a in arts.values())


def test_contract_inventory(report):
    inv = report["re_audit"]["inventory"]
    assert inv["contract_version"] == "1.22.0"
    assert inv["explainer_present"] is True
    assert inv["n_top_level_keys"] >= 25


def test_task_verdicts_all_pass(report):
    tv = report["task_verdicts"]
    assert len(tv) == 4
    for v in tv.values():
        assert v.get("present") is True
        assert "PASS" in str(v.get("verdict")).upper()


def test_governance_change_record_owner_review(report, store):
    gov = report["governance"]
    assert gov["audit_integrity_ok"] is True
    assert gov["change_record_id"]
    recs = [r for r in store["change_records"] if r.get("title") == TITLE]
    assert len(recs) == 1
    assert "OWNER" in str(recs[0].get("status", "")).upper()


def test_md_exists(report):
    assert MD.exists()
    text = MD.read_text(encoding="utf-8")
    assert "PHASE 36 COMPLETE" in text
