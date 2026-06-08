"""Phase 25 Task 5 tests — offline-UI propagation of the path-wise action
view.

Verifies (read-only over built artifacts):
- ui_data.json contract v1.7.0 (ADDITIVE) surfaces the Phase 25 Task 2-4
  results (path-wise bonus declaration with the +14.17% conservative delta vs
  the horizon basis; matching path-wise proxy basis with OOS R2 0.9978; the
  Task 4 pathwise-vs-horizon capital-delta matrix, saturation/restoration
  profile, frozen-copula bootstrap with the nested reference OUTSIDE the CI,
  and the MR-010/MR-014 var-covar refresh 69.1%);
- ui_app.html embeds the same snapshot with zero external references and a
  Path-wise Actions (P25) panel;
- the Task 5 evidence report + governance ChangeRecord are persisted and the
  audit chain verifies.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 -m pytest tests/test_phase25_task5_ui_propagation.py -q
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UI_DATA = REPO / "ui_data.json"
UI_APP = REPO / "ui_app.html"
REPORT = REPO / "docs/validation/PHASE25_TASK5_UI_PROPAGATION_REPORT.json"
T2_REPORT = (REPO / "docs/validation/"
             "PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.json")
T3_REPORT = (REPO / "docs/validation/"
             "PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.json")
T4_REPORT = (REPO / "docs/validation/"
             "PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.json")
GOV = REPO / ".claude-dev/GOVERNANCE_STORE.json"


@pytest.fixture(scope="module")
def ui():
    return json.loads(UI_DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p25(ui):
    return ui.get("phase25", {})


@pytest.fixture(scope="module")
def report():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def html():
    return UI_APP.read_text(encoding="utf-8")


class TestContract:
    def test_contract_version_1_7_0(self, ui):
        # Equality is intentional for THIS phase's deliverable; future phases
        # bump additively and may relax this to a floor (repo convention).
        assert ui["contract_version"] == "1.7.0"

    def test_phase25_section_present(self, p25):
        assert isinstance(p25, dict) and p25
        for k in ("declaration", "proxy_basis", "tail_diagnostics",
                  "narrative"):
            assert k in p25, k

    def test_declaration_matches_task2_report(self, p25):
        t2 = json.loads(T2_REPORT.read_text(encoding="utf-8"))
        r = t2["result"]
        dc = p25["declaration"]
        assert dc["nested_capital_with_pathwise"]["scr_proxy"] == \
            pytest.approx(r["nested_capital_with_pathwise"]["scr_proxy"])
        assert dc["nested_capital_with_horizon"]["scr_proxy"] == \
            pytest.approx(r["nested_capital_with_horizon"]["scr_proxy"])
        assert dc["pathwise_vs_horizon_delta"]["scr_delta_rel_to_horizon"] \
            == pytest.approx(
                r["pathwise_vs_horizon_delta"]["scr_delta_rel_to_horizon"])
        assert dc["pathwise_action_share"] == pytest.approx(
            r["pathwise_action_share"])
        assert dc["pathwise_restoration_share"] == pytest.approx(
            r["pathwise_restoration_share"])

    def test_declaration_headline_numbers(self, p25):
        dc = p25["declaration"]
        assert dc["nested_capital_without"]["scr_proxy"] == pytest.approx(
            55561.189, abs=1.0)
        assert dc["nested_capital_with_horizon"]["scr_proxy"] == \
            pytest.approx(40852.054, abs=1.0)
        assert dc["nested_capital_with_pathwise"]["scr_proxy"] == \
            pytest.approx(46638.866, abs=1.0)
        assert dc["pathwise_vs_horizon_delta"]["scr_delta_rel_to_horizon"] \
            == pytest.approx(0.141653, abs=5e-4)

    def test_pathwise_relieves_less_is_conservative(self, p25):
        dc = p25["declaration"]
        assert dc["nested_capital_with_pathwise"]["scr_proxy"] > \
            dc["nested_capital_with_horizon"]["scr_proxy"]
        assert "relieves LESS" in dc["interpretation"]

    def test_task2_gates_all_pass(self, p25):
        g = p25["declaration"]["gates"]
        assert len(g) == 6 and all(v is True for v in g.values())

    def test_proxy_basis_matches_task3_report(self, p25):
        t3 = json.loads(T3_REPORT.read_text(encoding="utf-8"))
        r = t3["result"]
        px = p25["proxy_basis"]
        assert px["oos_r2_with_actions"] == pytest.approx(
            r["oos_r2_with_actions_pathwise"])
        assert px["var_rel_error_with_actions"] == pytest.approx(
            r["var_rel_error_with_actions"])
        assert px["scr_rel_error_with_actions"] == pytest.approx(
            r["scr_rel_error_with_actions"])
        assert px["surface"]["sigma"] == pytest.approx(
            r["surface_calibration_fit_only"]["sigma"])
        assert px["surface"]["alpha"] == pytest.approx(
            r["surface_calibration_fit_only"]["alpha"])

    def test_proxy_basis_headline_numbers(self, p25):
        px = p25["proxy_basis"]
        assert px["oos_r2_with_actions"] == pytest.approx(0.99785, abs=1e-4)
        assert px["var_rel_error_with_actions"] == pytest.approx(
            0.004014, abs=5e-4)
        assert px["surface"]["sigma"] == pytest.approx(0.225)
        assert px["surface"]["alpha"] == pytest.approx(0.756689, abs=1e-4)
        assert px["cadence_sensitivity"][
            "annual_over_monthly_mean_ratio"] == pytest.approx(
                1.135918, abs=1e-3)

    def test_task3_gates_all_pass(self, p25):
        g = p25["proxy_basis"]["gates"]
        assert len(g) == 5 and all(v is True for v in g.values())

    def test_delta_matrix_matches_task4_report(self, p25):
        t4 = json.loads(T4_REPORT.read_text(encoding="utf-8"))
        dm = p25["tail_diagnostics"]["delta_matrix"]
        for bench in ("nested", "t_copula", "gaussian", "var_covar"):
            assert bench in dm, bench
        for bench in ("nested", "t_copula", "gaussian"):
            for basis in ("without", "with_horizon", "with_pathwise"):
                assert dm[bench][basis]["scr"] == pytest.approx(
                    t4["delta_matrix"][bench][basis]["scr"]), (bench, basis)

    def test_delta_matrix_headline_numbers(self, p25):
        dm = p25["tail_diagnostics"]["delta_matrix"]
        assert dm["nested"]["with_pathwise"]["scr"] == pytest.approx(
            46638.866, abs=1.0)
        assert dm["t_copula"]["with_pathwise"]["scr"] == pytest.approx(
            39794.322, abs=1.0)
        assert dm["gaussian"]["with_pathwise"]["scr"] == pytest.approx(
            35210.085, abs=1.0)
        # var-covar has no path-wise analogue (DISCLOSED)
        assert dm["var_covar"]["with_pathwise"]["scr"] is None

    def test_pathwise_relieves_less_across_matrix(self, p25):
        dm = p25["tail_diagnostics"]["delta_matrix"]
        for bench in ("nested", "t_copula", "gaussian"):
            assert dm[bench]["with_pathwise"]["scr"] > \
                dm[bench]["with_horizon"]["scr"], bench

    def test_confidence_sweep_and_saturation(self, p25):
        td = p25["tail_diagnostics"]
        sw = td["confidence_sweep"]
        assert len(sw) == 5
        assert [s["confidence"] for s in sw] == pytest.approx(
            [0.90, 0.95, 0.99, 0.995, 0.999])
        fnd = td["diagnostic_findings"]
        assert fnd["tail_saturation_share_at_995"] == pytest.approx(1.0)
        assert fnd["tail_mean_smoothed_relief_fraction_at_995"] == \
            pytest.approx(0.081148, abs=1e-3)
        assert fnd["tail_mean_smoothed_relief_fraction_at_995"] < 0.12
        assert fnd["pathwise_relieves_less_at_every_confidence"] is True

    def test_bootstrap_nested_pathwise_outside_ci(self, p25):
        td = p25["tail_diagnostics"]
        bt = td["bootstrap"]["scr_pathwise"]
        assert bt["ci_lo_95"] == pytest.approx(35793.207, abs=1.0)
        assert bt["ci_hi_95"] == pytest.approx(42496.400, abs=1.0)
        fnd = td["diagnostic_findings"]
        assert fnd["nested_pathwise_inside_bootstrap_ci"] is False
        assert fnd["t_pathwise_vs_nested_pathwise_rel_err"] == \
            pytest.approx(0.146756, abs=5e-4)

    def test_var_covar_refresh_mr010(self, p25):
        td = p25["tail_diagnostics"]
        vc = td["var_covar_refresh"]
        assert vc["understatement_vs_nested_with_pathwise"] == \
            pytest.approx(0.690628, abs=5e-4)
        assert td["mr010_refreshed"] is True
        assert td["mr014_refreshed"] is True
        assert td["mr_refresh_trigger"]["met"] is True

    def test_copula_frozen_rank_invariance(self, p25):
        td = p25["tail_diagnostics"]
        assert td["df_rematched"] == pytest.approx(2.9451, abs=1e-3)
        assert td["rho_max_abs_diff_vs_archived"] < 1e-12

    def test_task4_gates_all_pass(self, p25):
        g = p25["tail_diagnostics"]["gates"]
        assert len(g) == 4 and all(v is True for v in g.values())

    def test_additive_capital_readouts(self, ui):
        cap = ui["capital"]
        assert cap["nested_scr_with_pathwise"] == pytest.approx(
            46638.866, abs=1.0)
        assert cap["t_copula_scr_pathwise_readout"] == pytest.approx(
            39794.322, abs=1.0)
        # Phase 23/24 additive read-outs unchanged (contract is additive)
        assert cap["t_copula_scr_joint_action"] == pytest.approx(
            31001.776, abs=1.0)
        assert cap["nested_scr_with_inner_path"] == pytest.approx(
            40852.054, abs=1.0)

    def test_phase24_section_untouched(self, ui):
        p24 = ui["phase24"]
        assert p24["joint_action"]["t_scr_joint"] == pytest.approx(
            31001.776, abs=1.0)
        assert len(p24["tail_diagnostics"]["confidence_sweep"]) == 5

    def test_phase25_verdicts_listed(self, ui):
        names = [str(v.get("name", "")) for v in ui["verdicts"]]
        assert any("Path-wise bonus declaration in the nested truth" in n
                   for n in names)
        assert any("Matching path-wise proxy basis" in n for n in names)
        assert any("Path-wise tail diagnostics" in n for n in names)
        verds = {str(v.get("name", "")): str(v.get("verdict", ""))
                 for v in ui["verdicts"]}
        for n, v in verds.items():
            if "Phase 25" in n:
                assert v == "PASS", n


class TestHtml:
    def test_embedded_snapshot_is_contract_1_7_0(self, html):
        marker = "/*__UI_DATA__*/"
        start = html.index(marker) + len(marker)
        end = html.index("</script>", start)
        data = json.loads(html[start:end])
        assert data["contract_version"] == "1.7.0"
        assert data["phase25"]["declaration"][
            "nested_capital_with_pathwise"]["scr_proxy"] == pytest.approx(
                46638.866, abs=1.0)

    def test_phase25_panel_and_tab_present(self, html):
        assert 'id="phase25"' in html
        assert '["phase25","Path-wise Actions (P25)"]' in html
        assert "renderPhase25" in html

    def test_no_external_references(self, html):
        for token in ("https://cdn", "src=\"http", "href=\"http"):
            assert token not in html, token


class TestEvidenceAndGovernance:
    def test_report_verdict_pass_phase25_complete(self, report):
        assert report["verdict"] == "PASS"
        assert report["phase25_status"] == "COMPLETE (Tasks 1-5)"

    def test_report_contract_checks_all_passed(self, report):
        assert report["ui_contract_checks"]["all_passed"] is True

    def test_report_self_test_clean(self, report):
        st = report["self_test"]
        assert st["ok"] is True
        assert st["network_calls"] == 0 and st["js_errors"] == 0
        assert st["n_checks"] >= 101
        p = st["phase25_checks"]
        assert p["phase25TabPresent"] is True
        assert p["p25DeltaRows"] == 4
        assert p["p25SweepRows"] == 5
        assert p["p25ProxyRows"] >= 8
        assert p["pathwiseRelievesLessPresent"] is True
        assert p["bootstrapOutsideCiPresent"] is True

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
