"""Phase 30 Task 1 - post-vine dependence roadmap decision tests."""

from __future__ import annotations

import json
import os

import pytest

from par_model_v2.projection.dependence_roadmap import (
    MAX_VINE_TREES_P30,
    MR016_RISK_ID,
    MR017_RISK_ID,
    OPTION_IDS,
    SELECTED_OPTION,
    THIRD_TREE_EDGES,
    UI_CONTRACT_FROM,
    UI_CONTRACT_TO,
    VINE2_BOOTSTRAP_CI95,
    VINE2_COMPONENT_SCR_BOOTSTRAP_MEAN,
    VINE2_COMPONENT_SCR_POINT,
    VINE2_COPULA_FORM_RESIDUAL_POINT,
    VINE2_GAP_TOTAL_POINT,
    VINE2_OVERFIT_HOLDOUT_TO_FIT_RATIO,
    RELIEF_SURFACE_PART_ABS,
    RoadmapStudyConfig,
    dependence_roadmap_option_study,
    dependence_roadmap_use_restrictions,
    mr016_closure_headroom,
    tree3_truncation_pre_study,
    validate_roadmap_envelope,
)
from par_model_v2.projection.vine_copula_upgrade import (
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    PAIR_FAMILY_CANDIDATES,
    VINE_ROOT_DRIVER,
)

FAST_N = 40_000
T3_REPORT = os.path.join("docs", "validation", "PHASE29_TASK3_VINE_MARGIN_BOOTSTRAP_REPORT.json")
T4_REPORT = os.path.join("docs", "validation", "PHASE29_TASK4_VINE_TAIL_DIAGNOSTICS_REPORT.json")


@pytest.fixture(scope="module")
def pre():
    return tree3_truncation_pre_study(seed=30, n_scen=FAST_N)


class TestArchivedReferences:
    def test_constants_pinned(self):
        assert VINE2_COMPONENT_SCR_POINT == pytest.approx(42_458.5527095696)
        assert VINE2_COMPONENT_SCR_BOOTSTRAP_MEAN == pytest.approx(41_917.634842687556)
        assert VINE2_BOOTSTRAP_CI95[0] == pytest.approx(38_654.68530800363)
        assert VINE2_BOOTSTRAP_CI95[1] == pytest.approx(45_284.252553628474)
        assert VINE2_COPULA_FORM_RESIDUAL_POINT == pytest.approx(3_637.298487404965)
        assert VINE2_GAP_TOTAL_POINT == pytest.approx(4_180.3472904304)
        assert RELIEF_SURFACE_PART_ABS == pytest.approx(543.0488030254351)

    @pytest.mark.skipif(not os.path.exists(T3_REPORT), reason="archived T3 report not present")
    def test_constants_match_archived_t3_report(self):
        r = json.load(open(T3_REPORT))["result"] if "result" in json.load(open(T3_REPORT)) else json.load(open(T3_REPORT))
        r = json.load(open(T3_REPORT))
        res = r.get("result", r)
        ci = res["vine_component_scr_ci"]
        assert ci["mean"] == pytest.approx(VINE2_COMPONENT_SCR_BOOTSTRAP_MEAN)
        assert ci["ci_lo"] == pytest.approx(VINE2_BOOTSTRAP_CI95[0])
        assert ci["ci_hi"] == pytest.approx(VINE2_BOOTSTRAP_CI95[1])
        rd = res["residual_gap_redecomposition_point"]
        assert rd["copula_form_residual_abs"] == pytest.approx(VINE2_COPULA_FORM_RESIDUAL_POINT)
        assert rd["gap_total_abs"] == pytest.approx(VINE2_GAP_TOTAL_POINT)

    @pytest.mark.skipif(not os.path.exists(T4_REPORT), reason="archived T4 report not present")
    def test_constants_match_archived_t4_report(self):
        res = json.load(open(T4_REPORT))["result"]
        oc = res["overfit_check"]
        assert oc["holdout_to_fit_max_lift_ratio"] == pytest.approx(VINE2_OVERFIT_HOLDOUT_TO_FIT_RATIO)
        mr = res["mr_remediation_decision"]
        assert mr["mr016_decision"] == "KEEP_OPEN"
        assert mr["open_mr017"] is True
        assert mr["nested_inside_ci"] is False


class TestHeadroom:
    def test_headroom_arithmetic(self):
        h = mr016_closure_headroom()
        assert h["needed_mean_lift_abs"] == pytest.approx(
            NESTED_PATHWISE_SCR_REFERENCE - VINE2_BOOTSTRAP_CI95[1]
        )
        assert 0.0 < h["needed_mean_lift_rel"] < 0.05
        assert 0.0 < h["needed_share_of_point_residual"] < 1.0
        assert h["relief_surface_part_not_addressable"] == pytest.approx(RELIEF_SURFACE_PART_ABS)


class TestEnvelope:
    def test_three_trees_four_edges(self):
        env = validate_roadmap_envelope()
        assert env["envelope_ok"] is True
        assert MAX_VINE_TREES_P30 == 3
        assert len(THIRD_TREE_EDGES) == 4

    def test_third_tree_conditions_on_credit_root(self):
        for a, b, cond in THIRD_TREE_EDGES:
            assert VINE_ROOT_DRIVER in cond
            assert a not in cond and b not in cond and a != b

    def test_families_unchanged(self):
        assert len(PAIR_FAMILY_CANDIDATES) == 4
        env = validate_roadmap_envelope()
        assert env["pair_families_unchanged"] is True
        assert env["ui_contract"] == [UI_CONTRACT_FROM, UI_CONTRACT_TO]

    def test_config_validation(self):
        with pytest.raises(ValueError):
            RoadmapStudyConfig(n_scen=10)
        with pytest.raises(ValueError):
            RoadmapStudyConfig(tree3_strength=-1.0)


class TestPreStudy:
    def test_boundary_recovery_exact(self, pre):
        assert pre["boundary_recovery_ok"] is True
        assert pre["boundary_recovery_max_abs"] == 0.0

    def test_truncation_gap_positive(self, pre):
        assert pre["truncation_gap_positive"] is True
        assert pre["truncation_gap_rel"] > 0.01

    def test_leakage_free_closure(self, pre):
        assert pre["holdout_closure_share"] >= 0.5
        assert pre["closure_demonstrated"] is True

    def test_tree3_targeting(self, pre):
        assert pre["targeting_ok"] is True
        assert pre["joint_triple_tail"]["lift"] > pre["holdout_pair_drift"]

    def test_mechanism_demonstrated(self, pre):
        assert pre["mechanism_demonstrated"] is True

    def test_reproducible_digest(self):
        a = tree3_truncation_pre_study(seed=30, n_scen=20_000)
        b = tree3_truncation_pre_study(seed=30, n_scen=20_000)
        assert a["digest"] == b["digest"]


class TestOptionStudy:
    def test_all_options_present_and_quantified(self, pre):
        study = dependence_roadmap_option_study(pre)
        assert set(study["options"].keys()) == set(OPTION_IDS)
        for o in study["options"].values():
            assert "expected_residual_closure_abs_max" in o
            assert "governance_risk" in o

    def test_decision_rule_selects_option_a(self, pre):
        study = dependence_roadmap_option_study(pre)
        assert study["selected_option"] == SELECTED_OPTION == "A_tree3_vine_deepening"
        assert study["selection_ok"] is True

    def test_option_b_rejected_for_circularity(self, pre):
        study = dependence_roadmap_option_study(pre)
        b = study["options"]["B_nested_aware_calibration"]
        assert b["eligible"] is False
        assert "circular" in b["governance_risk"].lower() or "circular" in b["ineligible_reason"].lower()

    def test_stop_rule_registered(self, pre):
        study = dependence_roadmap_option_study(pre)
        assert "STOP-RULE" in study["stop_rule"]
        assert f"{NESTED_PATHWISE_SCR_REFERENCE:,.1f}" in study["stop_rule"]


class TestUseRestrictions:
    def test_educational_and_dual_boundary(self):
        ur = dependence_roadmap_use_restrictions()
        assert ur["classification"] == "EDUCATIONAL"
        joined = " ".join(ur["restrictions"])
        assert f"{FROZEN_T_COMPONENT_SCR_REFERENCE:,.6f}" in joined
        assert f"{VINE2_COMPONENT_SCR_POINT:,.6f}" in joined
        assert "stop-rule" in joined.lower()
        assert MR016_RISK_ID and MR017_RISK_ID


class TestBuilder:
    def test_build_note_pass(self):
        from scripts.build_phase30_task1_dependence_roadmap import build_design_note
        note = build_design_note(fast=True)
        assert note["verdict"] == "PASS"
        assert note["selected_option"] == "A_tree3_vine_deepening"
        assert len(note["task2_acceptance_criteria"]) >= 6
        assert len(note["task3_acceptance_criteria"]) >= 4
        assert len(note["task4_acceptance_criteria"]) >= 4
