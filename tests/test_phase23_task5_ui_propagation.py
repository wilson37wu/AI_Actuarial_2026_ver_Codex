"""Phase 23 Task 5 tests — offline-UI propagation of the t-copula +
management-action view.

Verifies (read-only over built artifacts):
- ui_data.json contract v1.5.0 surfaces the Phase 23 Task 2-4 results
  (tail-matched t-copula aggregation, management-action rule panel,
  with-actions capital read-outs + disclosed saturation finding);
- ui_app.html embeds the same snapshot with zero external references;
- the Task 5 evidence report + governance ChangeRecord are persisted and the
  audit chain verifies.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 -m pytest tests/test_phase23_task5_ui_propagation.py -q
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UI_DATA = REPO / "ui_data.json"
UI_APP = REPO / "ui_app.html"
REPORT = REPO / "docs/validation/PHASE23_TASK5_UI_PROPAGATION_REPORT.json"
T4_REPORT = REPO / "docs/validation/PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.json"
T3_REPORT = REPO / "docs/validation/PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.json"
GOV = REPO / ".claude-dev/GOVERNANCE_STORE.json"


@pytest.fixture(scope="module")
def ui():
    return json.loads(UI_DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ma(ui):
    return ui.get("management_actions", {})


@pytest.fixture(scope="module")
def report():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def html():
    return UI_APP.read_text(encoding="utf-8")


class TestContract:
    def test_contract_version_1_5_0(self, ui):
        assert ui["contract_version"] == "1.5.0"

    def test_management_actions_section_present(self, ma):
        assert isinstance(ma, dict) and ma

    def test_rule_parameters_complete(self, ma):
        rule = ma["rule"]
        for k, v in (("cr_trigger", 1.10), ("cr_floor", 0.90),
                     ("bonus_share", 0.30), ("pre_floor", 0.60),
                     ("max_relief", 0.12), ("reference_coverage", 1.12)):
            assert rule[k] == pytest.approx(v), k

    def test_task3_gates_all_pass(self, ma):
        g = ma["gates_task3"]
        assert len(g) == 5 and all(v is True for v in g.values())

    def test_task4_gates_all_pass(self, ma):
        g = ma["gates_task4"]
        assert len(g) == 4 and all(v is True for v in g.values())

    def test_trigger_sensitivity_three_rows_all_pass(self, ma):
        ts = ma["trigger_sensitivity"]
        assert [t["cr_trigger"] for t in ts] == pytest.approx([1.05, 1.10, 1.15])
        assert all(t["verdict"] == "PASS" for t in ts)

    def test_with_without_capital_readouts_match_task4_report(self, ma):
        t4 = json.loads(T4_REPORT.read_text(encoding="utf-8"))
        agg = ma["aggregation"]
        a4 = t4["aggregation_with_actions"]
        b4 = t4["without_actions_baseline"]
        assert agg["nested_scr_with"] == pytest.approx(a4["nested_scr"])
        assert agg["t_copula_scr_with"] == pytest.approx(a4["t_matched_scr"])
        assert agg["gaussian_scr_with"] == pytest.approx(a4["gaussian_scr"])
        assert agg["var_covar_scr_with"] == pytest.approx(a4["var_covar_scr"])
        assert agg["nested_scr_without"] == pytest.approx(b4["nested_scr"])
        assert agg["t_copula_scr_without"] == pytest.approx(b4["t_matched_scr"])
        assert agg["df_matched"] == pytest.approx(2.9451)

    def test_with_actions_capital_strictly_lower(self, ma):
        agg = ma["aggregation"]
        for k in ("nested_scr", "t_copula_scr", "gaussian_scr", "var_covar_scr"):
            assert agg[k + "_with"] < agg[k + "_without"], k

    def test_standalone_vectors_seven_drivers(self, ma):
        agg = ma["aggregation"]
        assert agg["standalone_drivers"] == [
            "rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity"]
        assert len(agg["standalone_scr_with"]) == 7
        assert len(agg["standalone_scr_without"]) == 7
        for w, wo in zip(agg["standalone_scr_with"],
                         agg["standalone_scr_without"]):
            assert w <= wo + 1e-6

    def test_saturation_finding_and_anchoring_disclosed(self, ma):
        assert "saturates" in ma["saturation_finding"]
        assert "nested" in ma["saturation_finding"].lower()
        assert "V_k" in ma["aggregation"]["anchoring_convention"]

    def test_oos_r2_with_actions_matches_task3_report(self, ma):
        t3 = json.loads(T3_REPORT.read_text(encoding="utf-8"))
        assert ma["oos_r2_with_actions"] == pytest.approx(
            t3["result"]["oos_r2_with_actions"])

    def test_capital_section_augmented(self, ui):
        cap = ui["capital"]
        assert cap["t_copula_scr"] == pytest.approx(46755.963)
        assert cap["t_copula_df"] == pytest.approx(2.9451)
        assert cap["nested_scr_with_actions"] == pytest.approx(33117.7704)

    def test_phase23_verdicts_listed(self, ui):
        names = [str(v.get("name", "")) for v in ui["verdicts"]]
        assert any("Tail-matched Student-t copula aggregation" in n for n in names)
        assert any("Management-action rule" in n for n in names)
        assert any("WITH management actions" in n for n in names)


class TestHtml:
    def test_embedded_snapshot_is_contract_1_5_0(self, html):
        marker = "/*__UI_DATA__*/"
        start = html.index(marker) + len(marker)
        end = html.index("</script>", start)
        data = json.loads(html[start:end])
        assert data["contract_version"] == "1.5.0"
        assert data["management_actions"]["aggregation"][
            "nested_scr_with"] == pytest.approx(33117.7704)

    def test_actions_panel_and_tab_present(self, html):
        assert 'id="actions"' in html
        assert '["actions","Management Actions"]' in html
        assert "renderActions" in html

    def test_no_external_references(self, html):
        for token in ("http://", "https://cdn", "src=\"http", "href=\"http"):
            assert token not in html, token


class TestEvidenceAndGovernance:
    def test_report_verdict_pass_phase23_complete(self, report):
        assert report["verdict"] == "PASS"
        assert report["phase23_status"] == "COMPLETE (Tasks 1-5)"

    def test_report_contract_checks_all_passed(self, report):
        assert report["ui_contract_checks"]["all_passed"] is True

    def test_report_self_test_clean(self, report):
        st = report["self_test"]
        assert st["ok"] is True
        assert st["network_calls"] == 0 and st["js_errors"] == 0
        assert st["n_checks"] >= 69
        assert st["phase23_checks"]["managementTabPresent"] is True
        assert st["phase23_checks"]["maBarRects"] >= 8

    def test_change_record_owner_review_and_integrity(self, report):
        gov = report["governance"]
        assert gov["change_record_status"] == "OWNER_REVIEW"
        assert gov["audit_integrity_verify_all"] is True
        store = json.loads(GOV.read_text(encoding="utf-8"))
        recs = {r["record_id"]: r for r in store["change_records"]}
        assert gov["change_record_id"] in recs
        rec = recs[gov["change_record_id"]]
        assert rec["change_type"] == "code_change"
        assert "ui_app.html" in rec["affected_components"]
