"""Phase 32 Task 5 - phase summary + final consolidated re-audit tests.

Validates the committed Task 5 evidence report (no re-execution of the
self-test battery here; the builder gates on it) and the PHASE 32 COMPLETE
governance trail.
"""
import json
from pathlib import Path

import pytest

REPORT = Path("docs/validation/PHASE32_TASK5_PHASE_SUMMARY_REPORT.json")
MD = Path("docs/validation/PHASE32_TASK5_PHASE_SUMMARY_REPORT.md")
GOV = Path(".claude-dev/GOVERNANCE_STORE.json")
TITLE = ("Phase 32 Task 5 - phase summary + final consolidated re-audit; "
         "PHASE 32 COMPLETE")


@pytest.fixture(scope="module")
def report():
    assert REPORT.exists(), "Task 5 report missing"
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def store():
    return json.loads(GOV.read_text(encoding="utf-8"))


def test_verdict_pass(report):
    assert report["verdict"] == "PASS"
    assert report["phase_status"] == "PHASE 32 COMPLETE"


def test_all_gates_pass(report):
    assert report["gates"] and all(report["gates"].values())


def test_self_tests_clean(report):
    tests = report["re_audit"]["self_tests"]
    assert set(tests) == {"ui_app", "userrun_fallback", "offline_viewer",
                          "combined_gui"}
    for v in tests.values():
        assert v["ok"] is True
        assert v["network_calls"] == 0
        assert v["js_errors"] == 0
        assert v["failed_checks"] == []


def test_zero_external_refs(report):
    arts = report["re_audit"]["artifacts"]
    assert set(arts) == {"ui_app.html", "model_result_viewer.html",
                         "combined_model_app.html"}
    assert all(a["external_refs"] == 0 for a in arts.values())


def test_contract_inventory(report):
    inv = report["re_audit"]["inventory"]
    assert inv["contract_version"] == "1.16.0"
    assert inv["n_top_level_keys"] >= 21
    gs = inv["governance_store"]
    assert gs["risk_register"] == 17
    assert gs["change_records"] >= 83


def test_task_verdicts_all_pass(report):
    vs = report["task_verdicts"]
    assert len(vs) == 4
    for v in vs.values():
        assert v["present"] is True
        assert "PASS" in str(v["verdict"]).upper()


def test_checks_grew_vs_baseline(report):
    base = report["baseline_task1"]
    t = report["re_audit"]["self_tests"]
    assert t["ui_app"]["n_checks"] >= base["ui_app_checks"]


def test_governance_record(report, store):
    gov = report["governance"]
    assert gov["audit_integrity_ok"] is True
    recs = [r for r in store["change_records"] if r["title"] == TITLE]
    assert len(recs) == 1, "exactly ONE Task 5 ChangeRecord (idempotent)"
    assert recs[0]["record_id"] == gov["change_record_id"]
    assert recs[0]["status"].upper() == "OWNER_REVIEW"
    assert recs[0]["change_type"] == "governance_change"


def test_md_report(report):
    text = MD.read_text(encoding="utf-8")
    assert "PHASE 32 COMPLETE" in text
    assert report["governance"]["change_record_id"] in text
    assert "Standing constraints carried forward" in text
