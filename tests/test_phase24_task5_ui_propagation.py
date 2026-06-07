"""Phase 24 Task 5 tests — offline-UI propagation of the joint-action +
inner-path view.

Verifies (read-only over built artifacts):
- ui_data.json contract v1.6.0 (ADDITIVE) surfaces the Phase 24 Task 2-4
  results (joint-scenario action-after-aggregation re-aggregation with the
  saturation-gap closure 22.54% -> 6.39%; inner-path action dynamics with the
  disclosed +4.0% outer-node over-relief; the Task 4 capital-delta matrix,
  saturation profile, frozen-copula bootstrap CI and MR-010 var-covar
  refresh);
- ui_app.html embeds the same snapshot with zero external references and a
  Joint Actions (P24) panel;
- the Task 5 evidence report + governance ChangeRecord are persisted and the
  audit chain verifies.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 -m pytest tests/test_phase24_task5_ui_propagation.py -q
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UI_DATA = REPO / "ui_data.json"
UI_APP = REPO / "ui_app.html"
REPORT = REPO / "docs/validation/PHASE24_TASK5_UI_PROPAGATION_REPORT.json"
T2_REPORT = (REPO / "docs/validation/"
             "PHASE24_TASK2_JOINT_ACTION_REAGGREGATION_REPORT.json")
T3_REPORT = REPO / "docs/validation/PHASE24_TASK3_INNER_PATH_ACTION_REPORT.json"
T4_REPORT = (REPO / "docs/validation/"
             "PHASE24_TASK4_JOINT_ACTION_TAIL_DIAGNOSTICS_REPORT.json")
GOV = REPO / ".claude-dev/GOVERNANCE_STORE.json"


@pytest.fixture(scope="module")
def ui():
    return json.loads(UI_DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p24(ui):
    return ui.get("phase24", {})


@pytest.fixture(scope="module")
def report():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def html():
    return UI_APP.read_text(encoding="utf-8")


class TestContract:
    def test_contract_version_1_6_0(self, ui):
        # Equality is intentional for THIS phase's deliverable; future phases
        # bump additively and may relax this to a floor (repo convention).
        assert ui["contract_version"] == "1.6.0"

    def test_phase24_section_present(self, p24):
        assert isinstance(p24, dict) and p24
        for k in ("joint_action", "inner_path", "tail_diagnostics",
                  "narrative"):
            assert k in p24, k

    def test_joint_action_matches_task2_report(self, p24):
        t2 = json.loads(T2_REPORT.read_text(encoding="utf-8"))
        ja = p24["joint_action"]
        assert ja["t_scr_joint"] == pytest.approx(
            t2["joint_action"]["t_scr"])
        assert ja["t_rel_error_joint"] == pytest.approx(
            t2["joint_action"]["t_rel"])
        assert ja["gaussian_scr_joint"] == pytest.approx(
            t2["joint_action"]["g_scr"])
        assert ja["nested_scr_with"] == pytest.approx(t2["nested_scr_with"])
        assert ja["df_matched"] == pytest.approx(t2["df_matched"])

    def test_joint_action_headline_numbers(self, p24):
        ja = p24["joint_action"]
        assert ja["t_scr_joint"] == pytest.approx(31001.776, abs=1.0)
        assert ja["t_rel_error_joint"] == pytest.approx(0.063893, abs=5e-4)
        assert ja["t_rel_error_standalone_baseline"] == pytest.approx(
            0.225403, abs=5e-4)
        assert ja["nested_scr_with"] == pytest.approx(33117.770, abs=1.0)

    def test_task2_gates_all_pass(self, p24):
        g = p24["joint_action"]["gates"]
        assert len(g) == 4 and all(v is True for v in g.values())

    def test_saturation_gap_closure_disclosed(self, p24):
        txt = p24["joint_action"]["saturation_gap_closure"]
        assert "22.54% to 6.39%" in txt
        assert "nested run remains the capital reference" in txt.lower() or \
            "nested run remains the capital reference" in txt

    def test_inner_path_matches_task3_report(self, p24):
        t3 = json.loads(T3_REPORT.read_text(encoding="utf-8"))
        res = t3["result"]
        ip = p24["inner_path"]
        assert ip["oos_r2_with_actions"] == pytest.approx(
            res["oos_r2_with_actions_inner_path"])
        assert ip["var_rel_error_with_actions"] == pytest.approx(
            res["var_rel_error_with_actions"])
        d = ip["outer_vs_inner_path_delta"]
        rd = res["outer_vs_inner_path_delta"]
        assert d["nested_scr_outer_node"] == pytest.approx(
            rd["nested_scr_outer_node"])
        assert d["nested_scr_inner_path"] == pytest.approx(
            rd["nested_scr_inner_path"])
        assert d["nested_scr_delta"] == pytest.approx(rd["nested_scr_delta"])

    def test_inner_path_over_relief_headlines(self, p24):
        d = p24["inner_path"]["outer_vs_inner_path_delta"]
        assert d["nested_scr_outer_node"] == pytest.approx(39290.898, abs=1.0)
        assert d["nested_scr_inner_path"] == pytest.approx(40852.054, abs=1.0)
        assert d["nested_scr_delta"] == pytest.approx(1561.156, abs=1.0)
        # +4.0% over-relief correction (inner-path more conservative)
        assert d["nested_scr_delta"] / d["nested_scr_outer_node"] == \
            pytest.approx(0.0397, abs=5e-4)

    def test_task3_gates_all_pass(self, p24):
        g = p24["inner_path"]["gates"]
        assert len(g) == 5 and all(v is True for v in g.values())

    def test_delta_matrix_matches_task4_report(self, p24):
        t4 = json.loads(T4_REPORT.read_text(encoding="utf-8"))
        dm = p24["tail_diagnostics"]["delta_matrix"]
        for bench in ("nested", "t_copula", "gaussian", "var_covar"):
            assert bench in dm, bench
        assert dm["t_copula"]["joint_action"]["scr"] == pytest.approx(
            t4["delta_matrix"]["t_copula"]["joint_action"]["scr"])
        assert dm["nested"]["without"]["scr"] == pytest.approx(
            48707.435, abs=1.0)
        assert dm["t_copula"]["joint_minus_standalone_scr_pct"] == \
            pytest.approx(0.2085, abs=5e-4)

    def test_confidence_sweep_and_saturation(self, p24):
        td = p24["tail_diagnostics"]
        sw = td["confidence_sweep"]
        assert len(sw) == 5
        assert [s["confidence"] for s in sw] == pytest.approx(
            [0.90, 0.95, 0.99, 0.995, 0.999])
        sat = {s["confidence"]: s["tail_saturation_share"] for s in sw}
        assert sat[0.995] == pytest.approx(1.0)
        assert td["diagnostic_findings"][
            "tail_saturation_share_at_995"] == pytest.approx(1.0)

    def test_bootstrap_ci_contains_nested_with(self, p24):
        td = p24["tail_diagnostics"]
        bt = td["bootstrap"]["scr_with"]
        assert bt["ci_lo_95"] == pytest.approx(26470.696, abs=1.0)
        assert bt["ci_hi_95"] == pytest.approx(33636.795, abs=1.0)
        nested_with = p24["joint_action"]["nested_scr_with"]
        assert bt["ci_lo_95"] <= nested_with <= bt["ci_hi_95"]
        assert td["diagnostic_findings"][
            "nested_with_inside_bootstrap_ci"] is True

    def test_var_covar_refresh_mr010(self, p24):
        vc = p24["tail_diagnostics"]["var_covar_refresh"]
        assert vc["understatement_vs_nested_with"] == pytest.approx(
            0.56432, abs=5e-4)
        assert vc["understatement_vs_t_joint"] == pytest.approx(
            0.53458, abs=5e-4)

    def test_task4_gates_all_pass(self, p24):
        g = p24["tail_diagnostics"]["gates"]
        assert len(g) == 3 and all(v is True for v in g.values())

    def test_additive_capital_readouts(self, ui):
        cap = ui["capital"]
        assert cap["t_copula_scr_joint_action"] == pytest.approx(
            31001.776, abs=1.0)
        assert cap["nested_scr_with_inner_path"] == pytest.approx(
            40852.054, abs=1.0)
        # Phase 23 additive read-outs unchanged (contract is additive)
        assert cap["t_copula_scr"] == pytest.approx(46756.0, abs=1.0)
        assert cap["nested_scr_with_actions"] == pytest.approx(
            33117.770, abs=1.0)

    def test_phase23_management_actions_section_untouched(self, ui):
        ma = ui["management_actions"]
        assert ma["aggregation"]["nested_scr_with"] == pytest.approx(
            33117.770, abs=1.0)
        assert len(ma["trigger_sensitivity"]) == 3

    def test_phase24_verdicts_listed(self, ui):
        names = [str(v.get("name", "")) for v in ui["verdicts"]]
        assert any("Joint-scenario action-after-aggregation t-copula" in n
                   for n in names)
        assert any("Inner-path management-action dynamics" in n
                   for n in names)
        assert any("Joint-action tail diagnostics" in n for n in names)
        verds = {str(v.get("name", "")): str(v.get("verdict", ""))
                 for v in ui["verdicts"]}
        for n, v in verds.items():
            if "Phase 24" in n:
                assert v == "PASS", n


class TestHtml:
    def test_embedded_snapshot_is_contract_1_6_0(self, html):
        marker = "/*__UI_DATA__*/"
        start = html.index(marker) + len(marker)
        end = html.index("</script>", start)
        data = json.loads(html[start:end])
        assert data["contract_version"] == "1.6.0"
        assert data["phase24"]["joint_action"]["t_scr_joint"] == \
            pytest.approx(31001.776, abs=1.0)

    def test_phase24_panel_and_tab_present(self, html):
        assert 'id="phase24"' in html
        assert '["phase24","Joint Actions (P24)"]' in html
        assert "renderPhase24" in html

    def test_no_external_references(self, html):
        for token in ("https://cdn", "src=\"http", "href=\"http"):
            assert token not in html, token


class TestEvidenceAndGovernance:
    def test_report_verdict_pass_phase24_complete(self, report):
        assert report["verdict"] == "PASS"
        assert report["phase24_status"] == "COMPLETE (Tasks 1-5)"

    def test_report_contract_checks_all_passed(self, report):
        assert report["ui_contract_checks"]["all_passed"] is True

    def test_report_self_test_clean(self, report):
        st = report["self_test"]
        assert st["ok"] is True
        assert st["network_calls"] == 0 and st["js_errors"] == 0
        assert st["n_checks"] >= 84
        p = st["phase24_checks"]
        assert p["phase24TabPresent"] is True
        assert p["p24DeltaRows"] == 4
        assert p["p24SweepRows"] == 5
        assert p["saturationGapClosurePresent"] is True
        assert p["bootstrapCiPresent"] is True

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
        assert "ui_data.json" in rec["affected_components"]
