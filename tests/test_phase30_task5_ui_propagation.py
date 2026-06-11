"""Phase 30 Task 5 tests - offline-UI propagation of the tree-3 vine
candidate + binding stop-rule decision view; PHASE 30 COMPLETE.

Verifies (read-only over built artifacts):
- ui_data.json contract v1.13.0 (ADDITIVE) surfaces the Phase 30 Task 1-4
  results (roadmap option A; tree-3 candidate 42,458.6 BIT-IDENTICAL to the
  2-tree vine - all four third-tree pairs zero-strength on n_fit {3,3,3,1}
  of 112; bootstrap mean 41,751.9, 95% CI [38,593.7, 44,556.4], SE 3.81%,
  nested 46,638.9 OUTSIDE; STOP-RULE APPLIED - MR-016/MR-017 KEEP OPEN,
  dependence-FORM escalation ENDS, Phase 31 = owner decision package;
  governed headline move 0.0000%; overfit ratio 0.049);
- ui_app.html embeds the same snapshot with zero external references and a
  Stop-Rule (P30) panel;
- the Task 5 evidence report + governance ChangeRecord are persisted.

Run:  PYTHONPATH=. python3 -m pytest tests/test_phase30_task5_ui_propagation.py -q
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UI_DATA = REPO / "ui_data.json"
UI_APP = REPO / "ui_app.html"
REPORT = REPO / "docs/validation/PHASE30_TASK5_UI_PROPAGATION_REPORT.json"
GOV = REPO / ".claude-dev/GOVERNANCE_STORE.json"
CARD = REPO / "docs/UI_PROPAGATION_CARD_P30.md"

CHANGE_TITLE = (
    "Phase 30 Task 5 - offline-UI propagation of the tree-3 vine candidate "
    "and the binding stop-rule decision view"
)


@pytest.fixture(scope="module")
def data():
    return json.loads(UI_DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p30(data):
    return data.get("phase30", {})


@pytest.fixture(scope="module")
def html():
    return UI_APP.read_text(encoding="utf-8")


class TestContract:
    def test_contract_version_1_13_0(self, data):
        assert data["contract_version"] == "1.13.0"

    def test_phase30_section_present(self, p30):
        assert isinstance(p30, dict) and p30
        for k in ("roadmap", "tree3", "bootstrap", "stop_rule", "tail",
                  "narrative"):
            assert k in p30, k

    def test_existing_sections_retained_additive(self, data):
        for k in ("phase24", "phase25", "phase26", "phase27", "phase28",
                  "phase29", "capital", "governance", "meta"):
            assert k in data, k

    def test_currency_meta_retained_from_1_12_0(self, data):
        assert "currency" in data["meta"]
        assert "currency_source" in data["meta"]


class TestRoadmap:
    def test_option_a_selected(self, p30):
        assert p30["roadmap"]["selected_option"] == "A_tree3_vine_deepening"

    def test_stop_rule_preregistered(self, p30):
        assert "STOP-RULE" in p30["roadmap"]["stop_rule"]

    def test_phase31_commitment(self, p30):
        assert "owner decision package" in str(
            p30["roadmap"]["post_phase30_commitment"]).lower()


class TestTree3Candidate:
    def test_point_bit_identical_to_vine2(self, p30):
        t3 = p30["tree3"]
        assert t3["tree3_candidate_scr_component"] == pytest.approx(
            42458.5527095696, abs=1e-6)
        assert t3["vine2_boundary_scr_component"] == pytest.approx(
            42458.5527095696, abs=1e-6)
        assert t3["candidate_vs_vine2_rel"] == 0.0

    def test_dual_boundary_recovery_exact(self, p30):
        t3 = p30["tree3"]
        assert t3["boundary_t_recovery_dev"] == 0.0
        assert t3["boundary_vine2_recovery_dev"] == 0.0
        assert t3["frozen_t_reference_scr_component"] == pytest.approx(
            39975.654628199336, abs=1e-6)

    def test_zero_strength_gaussian_families(self, p30):
        fc = p30["tree3"]["tree3_family_counts"]
        assert fc["gaussian"] == 4
        assert all(fc.get(k, 0) == 0 for k in
                   ("student_t", "survival_clayton", "survival_gumbel"))

    def test_third_tree_edges_preregistered_4(self, p30):
        assert len(p30["tree3"]["third_tree_edges"]) == 4

    def test_frozen_constants(self, p30):
        t3 = p30["tree3"]
        assert t3["df_rematched"] == pytest.approx(2.9451, abs=1e-3)
        assert float(t3["rho_max_abs_diff"]) < 1e-12

    def test_t2_gates_10_all_pass(self, p30):
        gates = p30["tree3"]["gates"]
        assert len(gates) == 10 and all(v is True for v in gates.values())


class TestBootstrap:
    def test_tree3_ci(self, p30):
        ci = p30["bootstrap"]["tree3_component_scr_ci"]
        assert ci["mean"] == pytest.approx(41751.9, abs=1.0)
        assert ci["ci_lo"] == pytest.approx(38593.7, abs=1.0)
        assert ci["ci_hi"] == pytest.approx(44556.4, abs=1.0)

    def test_se_gate(self, p30):
        bo = p30["bootstrap"]
        assert bo["se_frac_of_mean"] == pytest.approx(0.038063, abs=5e-4)
        assert bo["se_frac_of_mean"] <= 0.05
        assert bo["se_gate_pass"] is True

    def test_nested_outside_ci(self, p30):
        bo = p30["bootstrap"]
        assert bo["headline_nested_inside_95ci"] is False
        assert bo["nested_pathwise_reference"] == pytest.approx(
            46638.9, abs=0.1)

    def test_tree3_minus_vine2_exactly_zero(self, p30):
        bo = p30["bootstrap"]
        assert bo["tree3_minus_vine2_max_abs"] == 0.0
        assert bo["tree3_minus_vine2_all_exactly_zero"] is True

    def test_residual_unchanged_3637(self, p30):
        gd = p30["bootstrap"]["residual_gap_redecomposition_point"]
        assert gd["copula_form_residual_abs"] == pytest.approx(
            3637.3, abs=1.0)


class TestStopRule:
    def test_stop_rule_applied(self, p30):
        sr = p30["stop_rule"]
        assert sr["stop_rule_trigger_met"] is True
        assert sr["stop_rule_applied"] is True
        assert sr["dependence_form_escalation_ends"] is True

    def test_mr_decisions_keep_open(self, p30):
        sr = p30["stop_rule"]
        assert sr["mr016_decision"] == "KEEP_OPEN"
        assert sr["mr017_decision"] == "KEEP_OPEN"

    def test_phase31_owner_package(self, p30):
        assert "OWNER DECISION PACKAGE" in str(
            p30["stop_rule"]["phase31_directive"]).upper()

    def test_governed_headline_unchanged(self, p30):
        sr = p30["stop_rule"]
        assert sr["governed_headline_relative_move"] == 0.0
        assert sr["mr010_mr014_refresh_required"] is False
        assert sr["governed_headline_reference"] == pytest.approx(
            39975.654628199336, abs=1e-6)


class TestTailGrid:
    def test_levels_and_p90_rows(self, p30):
        td = p30["tail"]
        assert sorted(td["levels"].keys()) == ["80", "85", "90", "95"]
        rows = td["levels"]["90"]["rows"]
        counts = {}
        for r in rows:
            counts[r["tree"]] = counts.get(r["tree"], 0) + 1
        assert (counts.get("first"), counts.get("second"),
                counts.get("third"), counts.get("holdout")) == (6, 5, 4, 3)

    def test_overfit_gate(self, p30):
        oc = p30["tail"]["overfit_check"]
        assert oc["overfit_gate_pass"] is True
        assert oc["holdout_to_fit_max_lift_ratio"] == pytest.approx(
            0.048802, abs=5e-4)
        assert oc["tree3_fit_all_zero_strength"] is True

    def test_t4_gates_6_all_pass(self, p30):
        gates = p30["tail"]["gates"]
        assert len(gates) == 6 and all(v is True for v in gates.values())


class TestCapitalReadouts:
    def test_tree3_point(self, data):
        assert data["capital"]["tree3_vine_scr_component_point"] == \
            pytest.approx(42458.5527095696, abs=1e-6)

    def test_tree3_bootstrap_mean(self, data):
        assert data["capital"]["tree3_vine_scr_component_bootstrap_mean"] \
            == pytest.approx(41751.9, abs=1.0)

    def test_p29_readouts_retained(self, data):
        assert data["capital"]["vine_copula_scr_component_point"] == \
            pytest.approx(42458.6, abs=1.0)


class TestNarrative:
    def test_narrative_states_stop_rule_and_disclosure(self, p30):
        n = p30["narrative"]
        assert "STOP-RULE IS APPLIED" in n
        assert "not adopted" in n.lower()
        assert "zero-strength" in n


class TestHtmlShell:
    def test_panel_and_tab_present(self, html):
        assert '<div id="phase30" class="panel" ' \
               'data-title="Stop-Rule (P30)"></div>' in html
        assert '["phase30","Stop-Rule (P30)"]' in html
        assert "function renderPhase30()" in html

    def test_embedded_snapshot_contract(self, html):
        # the loader strips the token prefix; the snapshot must follow it
        m = re.search(r'/\*__UI_DATA__\*/\s*\{', html)
        assert m is not None
        assert '"contract_version": "1.13.0"' in html \
            or '"contract_version":"1.13.0"' in html

    def test_no_external_references(self, html):
        for pat in ("http://", "https://cdn", "src=\"http",
                    "href=\"http"):
            assert pat not in html, pat


class TestEvidenceAndGovernance:
    def test_report_persisted_pass(self):
        rep = json.loads(REPORT.read_text(encoding="utf-8"))
        assert rep["verdict"] == "PASS"
        assert rep["phase30_status"] == "COMPLETE (Tasks 1-5)"
        assert rep["ui_contract_checks"]["all_passed"] is True
        st = rep["self_test"]
        assert st["ok"] is True and st["network_calls"] == 0 \
            and st["js_errors"] == 0

    def test_card_persisted(self):
        assert "PHASE 30 COMPLETE" in CARD.read_text(encoding="utf-8")

    def test_change_record_owner_review(self):
        gov = json.loads(GOV.read_text(encoding="utf-8"))
        recs = [r for r in gov["change_records"]
                if r["title"] == CHANGE_TITLE]
        assert len(recs) == 1
        assert recs[0]["status"] == "OWNER_REVIEW"
        assert recs[0]["change_type"] == "code_change"
