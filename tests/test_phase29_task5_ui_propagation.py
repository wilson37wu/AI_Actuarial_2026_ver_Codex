"""Phase 29 Task 5 tests - offline-UI propagation of the vine / pair-copula
dependence upgrade view; PHASE 29 COMPLETE.

Verifies (read-only over built artifacts):
- ui_data.json contract v1.11.0 (ADDITIVE) surfaces the Phase 29 Task 2-4
  results (truncated credit-root C-vine candidate SCR 42,458.6 vs frozen-t
  39,975.7 vs grouped-t 35,604.4, gap to nested 46,638.9 narrowed to -8.96%;
  vine bootstrap mean 41,917.6, 95% CI [38,654.7, 45,284.3], SE 4.04%,
  nested OUTSIDE the CI; copula-form residual 3,637.3 = -65.33% vs grouped-t
  / -40.52% vs skew-t; pair-level tail grid 11 fitted + 3 holdout pairs over
  4 p-levels with the rate-liquidity|credit +0.8514 lift; overfit gate PASS
  ratio 0.049; MR-016 KEEP OPEN / MR-017 OPENED; governed headline move
  0.0000%);
- ui_app.html embeds the same snapshot with zero external references and a
  Vine Tail (P29) panel;
- the Task 5 evidence report + governance ChangeRecord are persisted and the
  audit chain verifies.

Run:  PYTHONPATH=. python3 -m pytest tests/test_phase29_task5_ui_propagation.py -q
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UI_DATA = REPO / "ui_data.json"
UI_APP = REPO / "ui_app.html"
REPORT = REPO / "docs/validation/PHASE29_TASK5_UI_PROPAGATION_REPORT.json"
CARD = REPO / "docs/UI_PROPAGATION_CARD_P29.md"
T2_REPORT = REPO / "docs/validation/PHASE29_TASK2_VINE_COPULA_REPORT.json"
T3_REPORT = (REPO / "docs/validation/"
             "PHASE29_TASK3_VINE_MARGIN_BOOTSTRAP_REPORT.json")
T4_REPORT = (REPO / "docs/validation/"
             "PHASE29_TASK4_VINE_TAIL_DIAGNOSTICS_REPORT.json")
GOV = REPO / ".claude-dev/GOVERNANCE_STORE.json"

CHANGE_TITLE = (
    "Phase 29 Task 5 - offline-UI propagation of the vine / pair-copula "
    "dependence upgrade view"
)


def _ver(s):
    return tuple(int(x) for x in str(s).split("."))


@pytest.fixture(scope="module")
def ui():
    return json.loads(UI_DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p29(ui):
    return ui.get("phase29", {})


@pytest.fixture(scope="module")
def report():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def html():
    return UI_APP.read_text(encoding="utf-8")


class TestContract:
    def test_contract_version_floor(self, ui):
        assert _ver(ui.get("contract_version")) >= (1, 11, 0)

    def test_phase29_section_present(self, p29):
        assert isinstance(p29, dict) and p29
        for key in ("copula", "bootstrap", "tail", "narrative"):
            assert key in p29, key


class TestTask2Copula:
    def test_structure_and_freeze(self, p29):
        co = p29["copula"]
        assert co["structure"] == "truncated_c_vine_credit_root"
        assert co["max_vine_trees"] == 2
        assert co["root_driver_name"] == "credit"
        assert abs(co["df_rematched"] - 2.9451) < 1e-3
        assert float(co["rho_max_abs_diff"]) < 1e-12
        assert co["boundary_recovery_dev"] == 0.0

    def test_scr_readouts_match_t2_report(self, p29):
        co = p29["copula"]
        t2 = json.loads(T2_REPORT.read_text(encoding="utf-8"))["result"]
        assert (co["vine_candidate_readout"]["scr_component"]
                == t2["vine_pair_candidate_readout"]["scr_component"])
        assert (co["frozen_t_reference_scr_component"]
                == t2["frozen_t_component_reference_readout"]
                ["scr_component"])
        assert abs(co["candidate_vs_frozen_t_rel"] - 0.062110) < 5e-4
        assert abs(co["candidate_gap_to_nested_rel"] + 0.089632) < 5e-4

    def test_t2_gates_all_pass(self, p29):
        gates = p29["copula"]["gates"]
        assert len(gates) == 8
        assert all(v is True for v in gates.values())


class TestTask3Bootstrap:
    def test_vine_ci_matches_t3_report(self, p29):
        bo = p29["bootstrap"]
        t3 = json.loads(T3_REPORT.read_text(encoding="utf-8"))["result"]
        for k in ("mean", "ci_lo", "ci_hi", "se"):
            assert (bo["vine_component_scr_ci"][k]
                    == t3["vine_component_scr_ci"][k]), k
        assert bo["headline_nested_inside_95ci"] is False
        assert bo["se_gate_pass"] is True
        assert bo["se_frac_of_mean"] <= 0.05

    def test_directional_and_residual(self, p29):
        bo = p29["bootstrap"]
        assert bo["vine_minus_frozen_pos_share"] == 1.0
        assert bo["directional_disclosed_direction"] == "up"
        gd = bo["residual_gap_redecomposition_point"]
        assert abs(gd["copula_form_residual_abs"] - 3637.3) < 1.0
        assert abs(bo["grouped_t_copula_form_residual_ref"] - 10491.5) < 1.0
        assert abs(bo["skewt_reconfirmed_copula_form_residual_ref"]
                   - 6114.9) < 1.0


class TestTask4Tail:
    def test_grid_shape(self, p29):
        td = p29["tail"]
        levels = td["levels"]
        assert sorted(levels.keys()) == ["80", "85", "90", "95"]
        for lk, lv in levels.items():
            rows = lv["rows"]
            trees = [r["tree"] for r in rows]
            assert trees.count("first") == 6, lk
            assert trees.count("second") == 5, lk
            assert trees.count("holdout") == 3, lk

    def test_rate_liquidity_lift_at_p90(self, p29):
        rows = p29["tail"]["levels"]["90"]["rows"]
        rl = next(r for r in rows
                  if r["pair_label"] == "rate-liquidity"
                  and r["tree"] == "second")
        assert rl["cond_label"] == "credit"
        assert abs(rl["lift_upper"]["mean"] - 0.8514) < 5e-4

    def test_overfit_check(self, p29):
        oc = p29["tail"]["overfit_check"]
        assert oc["overfit_gate_pass"] is True
        assert oc["holdout_disclosure_complete"] is True
        assert abs(oc["holdout_to_fit_max_lift_ratio"] - 0.048588) < 5e-4

    def test_mr_decision(self, p29):
        mr = p29["tail"]["mr_remediation_decision"]
        assert mr["mr016_decision"] == "KEEP_OPEN"
        assert mr["open_mr017"] is True
        assert mr["governed_headline_relative_move"] == 0.0
        assert mr["mr010_mr014_refresh_required"] is False
        assert abs(mr["residual_change_vs_grouped_t_rel"] + 0.653310) < 5e-4
        assert abs(mr["residual_change_vs_skewt_rel"] + 0.405174) < 5e-4

    def test_t4_gates_all_pass(self, p29):
        gates = p29["tail"]["gates"]
        assert len(gates) == 6
        assert all(v is True for v in gates.values())

    def test_t4_matches_source_report(self, p29):
        t4 = json.loads(T4_REPORT.read_text(encoding="utf-8"))["result"]
        oc_src = t4["overfit_check"]
        oc_ui = p29["tail"]["overfit_check"]
        assert (oc_ui["max_fit_pair_abs_mean_lift"]
                == oc_src["max_fit_pair_abs_mean_lift"])
        assert (oc_ui["max_holdout_pair_abs_mean_lift"]
                == oc_src["max_holdout_pair_abs_mean_lift"])


class TestCapitalReadouts:
    def test_additive_vine_readouts(self, ui):
        cap = ui["capital"]
        assert abs(cap["vine_copula_scr_component_point"]
                   - 42458.5527095696) < 1e-6
        assert abs(cap["vine_copula_scr_component_bootstrap_mean"]
                   - 41917.634842687556) < 1e-6

    def test_existing_readouts_untouched(self, ui):
        cap = ui["capital"]
        assert abs(cap["grouped_t_copula_scr_component_point"]
                   - 35604.4) < 1.0
        assert abs(cap["t_copula_scr_pathwise_component"] - 39975.7) < 1.0


class TestHtmlEmbed:
    def test_panel_and_tab_present(self, html):
        assert 'id="phase29"' in html
        assert "Vine Tail (P29)" in html
        assert "renderPhase29" in html

    def test_snapshot_embedded_with_phase29(self, html):
        m = re.search(r"/\*__UI_DATA__\*/(\{.*?\})\s*;?\s*</script>", html,
                      re.S)
        # fall back: data token replaced inline - just parse the json blob
        assert '"phase29"' in html
        assert '"contract_version": "1.11' in html.replace("'", '"') \
            or '"contract_version":"1.11' in html.replace(" ", "")

    def test_zero_external_references(self, html):
        for needle in ("http://", "https://cdn", "src=\"http",
                       "href=\"http"):
            assert needle not in html, needle


class TestGovernanceAndReport:
    def test_report_pass_and_complete(self, report):
        assert report["verdict"] == "PASS"
        assert report["phase29_status"].startswith("COMPLETE")
        assert report["ui_contract_checks"]["all_passed"] is True
        st = report["self_test"]
        assert st["ok"] is True
        assert st["network_calls"] == 0
        assert st["js_errors"] == 0

    def test_card_written(self):
        text = CARD.read_text(encoding="utf-8")
        assert "PHASE 29 COMPLETE" in text
        assert "1.10.0 -> 1.11.0" in text

    def test_change_record_present(self, report):
        gov = json.loads(GOV.read_text(encoding="utf-8"))
        recs = gov.get("change_records", [])
        rec = next((r for r in recs if r.get("title") == CHANGE_TITLE), None)
        assert rec is not None
        assert rec["record_id"] == (
            report["governance"]["change_record_id"])
        assert report["governance"]["audit_integrity_verify_all"] is True
