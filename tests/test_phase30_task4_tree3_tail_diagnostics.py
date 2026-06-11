"""Phase 30 Task 4 - unit tests for the tree-3 vine pair-level tail
diagnostics, fit-vs-holdout overfit check, and the binding stop-rule / MR
decision."""
from __future__ import annotations

import numpy as np
import pytest

from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.vine_copula_pair_aggregation import (
    fit_vine_pair_families,
)
from par_model_v2.projection.vine_copula_upgrade import (
    DRIVER_NAMES,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
)
from par_model_v2.projection.vine_tree3_aggregation import (
    THIRD_TREE_EDGES,
    fit_tree3_pairs,
)
from par_model_v2.projection.vine_tree3_tail_diagnostics import (
    P30T3_TREE3_CI_HI,
    P30T3_TREE3_CI_LO,
    RESIDUAL_IMPROVEMENT_THRESHOLD,
    TAIL_LEVEL_GRID,
    TREE3_COPULA_FORM_RESIDUAL_POINT,
    replicate_tree3_tail_records,
    summarise_tree3_pair_tail_diagnostics,
    tree3_overfit_check,
    tree3_pair_tail_grid_for_uniforms,
    tree3_stop_rule_mr_decision,
    tree3_tail_diagnostics_digest,
    tree3_tail_diagnostics_use_restrictions,
)

N_DRIVERS = len(DRIVER_NAMES)


def _synthetic_losses(n_obs: int = 90, seed: int = 7):
    rng = np.random.default_rng(seed)
    base = rng.standard_normal(n_obs)
    return {k: np.exp(0.4 * (0.6 * base + 0.8 * rng.standard_normal(n_obs)))
            * (40.0 + 6.0 * i)
            for i, k in enumerate(DRIVER_NAMES)}


def _synthetic_fit3():
    losses = _synthetic_losses()
    fit2 = fit_vine_pair_families(losses, DRIVER_NAMES)
    return fit_tree3_pairs(losses, DRIVER_NAMES, fit2)


def _synthetic_setup():
    losses = _synthetic_losses()
    R = np.full((N_DRIVERS, N_DRIVERS), 0.3)
    np.fill_diagonal(R, 1.0)
    anchors = {k: float(np.mean(v)) for k, v in losses.items()}
    return losses, R, anchors


class TestTree3PairTailGrid:
    def test_bounds_and_structure(self):
        rng = np.random.default_rng(11)
        U_c = rng.uniform(size=(4000, N_DRIVERS))
        U_f = rng.uniform(size=(4000, N_DRIVERS))
        grid = tree3_pair_tail_grid_for_uniforms(U_c, U_f)
        assert set(grid.keys()) == {"80", "85", "90", "95"}
        for key, p in zip(("80", "85", "90", "95"), TAIL_LEVEL_GRID):
            block = grid[key]
            assert len(block["first_tree"]) == 6
            assert len(block["second_tree"]) == 5
            assert len(block["third_tree"]) == 4
            assert len(block["holdout"]) == 3
            cap = 1.0 / (1.0 - p) + 1e-9
            for g in ("first_tree", "second_tree", "third_tree", "holdout"):
                for row in block[g]:
                    for m in ("cand_upper", "cand_lower", "frz_upper",
                              "frz_lower"):
                        assert 0.0 <= row[m] <= cap
                    assert row["lift_upper"] == pytest.approx(
                        row["cand_upper"] - row["frz_upper"])

    def test_third_tree_is_joint_conditional(self):
        rng = np.random.default_rng(13)
        U = rng.uniform(size=(4000, N_DRIVERS))
        grid = tree3_pair_tail_grid_for_uniforms(U, U)
        rows = grid["90"]["third_tree"]
        assert [tuple(r["condition_on"]) for r in rows] == [
            tuple(sorted((int(c1), int(c2)))) if False else (int(c1), int(c2))
            for _, _, (c1, c2) in THIRD_TREE_EDGES]
        # Joint conditional support must be (weakly) smaller than single
        # conditional support at the same level.
        n_root = int(np.sum(U[:, 2] > 0.90))
        for r in rows:
            assert 0 <= r["n_conditional_cand"] <= n_root

    def test_identical_uniforms_give_zero_lift(self):
        rng = np.random.default_rng(17)
        U = rng.uniform(size=(3000, N_DRIVERS))
        grid = tree3_pair_tail_grid_for_uniforms(U, U)
        for key in grid:
            for g in ("first_tree", "second_tree", "third_tree", "holdout"):
                for row in grid[key][g]:
                    assert row["lift_upper"] == 0.0
                    assert row["lift_lower"] == 0.0


class TestReplicateRecords:
    def test_records_and_summary_shapes(self):
        losses, R, anchors = _synthetic_setup()
        fit3 = _synthetic_fit3()
        res = replicate_tree3_tail_records(
            losses_without=losses, correlation=R,
            rule=ManagementActionRule(), l_fit=300.0, anchor_means=anchors,
            fit3=fit3, sigma=0.1, alpha=1.0, benefit_share=0.5,
            n_replicates=4, n_sim=600, master_seed=999,
            replicate_start=0, replicate_stop=4)
        assert len(res["records"]) == 4
        assert res["uniform_bit_identity_max_abs_dev"] == 0.0
        for rec in res["records"]:
            assert rec["tree3_minus_vine2"] == 0.0
            assert set(rec["tail_grid"].keys()) == {"80", "85", "90", "95"}
        summary = summarise_tree3_pair_tail_diagnostics(res["records"])
        block = summary["90"]
        assert len(block["third_tree"]) == 4
        for row in block["third_tree"]:
            assert "ci_lo" in row["lift_upper"]
            assert "ci_lo" in row["lift_lower"]

    def test_chunk_independence(self):
        losses, R, anchors = _synthetic_setup()
        fit3 = _synthetic_fit3()
        kw = dict(losses_without=losses, correlation=R,
                  rule=ManagementActionRule(), l_fit=300.0,
                  anchor_means=anchors, fit3=fit3, sigma=0.1, alpha=1.0,
                  benefit_share=0.5, n_replicates=4, n_sim=500,
                  master_seed=555)
        full = replicate_tree3_tail_records(
            replicate_start=0, replicate_stop=4, **kw)
        a = replicate_tree3_tail_records(
            replicate_start=0, replicate_stop=2, **kw)
        b = replicate_tree3_tail_records(
            replicate_start=2, replicate_stop=4, **kw)
        recs = a["records"] + b["records"]
        assert tree3_tail_diagnostics_digest(recs) == \
            tree3_tail_diagnostics_digest(full["records"])

    def test_archived_crosscheck_flags_mismatch(self):
        losses, R, anchors = _synthetic_setup()
        fit3 = _synthetic_fit3()
        kw = dict(losses_without=losses, correlation=R,
                  rule=ManagementActionRule(), l_fit=300.0,
                  anchor_means=anchors, fit3=fit3, sigma=0.1, alpha=1.0,
                  benefit_share=0.5, n_replicates=2, n_sim=400,
                  master_seed=77)
        clean = replicate_tree3_tail_records(
            replicate_start=0, replicate_stop=2, **kw)
        archived = {
            int(r["replicate_index"]): {
                "cop_seed": r["cop_seed"],
                "scr_component_tree3": r["scr_component_tree3"],
                "scr_component_vine2": r["scr_component_vine2"],
                "scr_component_frozen_t": r["scr_component_frozen_t"],
            } for r in clean["records"]}
        ok = replicate_tree3_tail_records(
            archived_records=archived, replicate_start=0, replicate_stop=2,
            **kw)
        assert ok["archived_crosscheck_max_abs_dev"] == 0.0
        archived[0]["scr_component_tree3"] += 1.0
        bad = replicate_tree3_tail_records(
            archived_records=archived, replicate_start=0, replicate_stop=2,
            **kw)
        assert bad["archived_crosscheck_max_abs_dev"] >= 1.0


class TestOverfitCheck:
    def _summary(self):
        losses, R, anchors = _synthetic_setup()
        fit3 = _synthetic_fit3()
        res = replicate_tree3_tail_records(
            losses_without=losses, correlation=R,
            rule=ManagementActionRule(), l_fit=300.0, anchor_means=anchors,
            fit3=fit3, sigma=0.1, alpha=1.0, benefit_share=0.5,
            n_replicates=3, n_sim=500, master_seed=42,
            replicate_start=0, replicate_stop=3)
        return summarise_tree3_pair_tail_diagnostics(res["records"]), fit3

    def test_overfit_check_fields(self):
        summary, fit3 = self._summary()
        ov = tree3_overfit_check(summary, fit3.to_dict())
        assert ov["n_fit_pairs"] == 15  # 6 + 5 + 4
        assert ov["n_holdout_pairs"] == 3
        assert ov["holdout_disclosure_complete"]
        assert ov["p29_holdout_to_fit_reference"] == pytest.approx(0.049)
        assert len(ov["tree3_fit_support_n_fit"]) == 4
        assert ov["overfit_gate_pass"] == (
            ov["holdout_disclosure_complete"] and ov["concentration_ok"])

    def test_concentration_violation_detected(self):
        summary, fit3 = self._summary()
        block = summary["90"]
        for row in block["first_tree"] + block["second_tree"] + \
                block["third_tree"]:
            row["lift_upper"]["mean"] = 0.0
            row["lift_lower"]["mean"] = 0.0
        block["holdout"][0]["lift_upper"]["mean"] = 0.5
        ov = tree3_overfit_check(summary, fit3.to_dict())
        assert not ov["concentration_ok"]
        assert not ov["overfit_gate_pass"]


class TestStopRuleDecision:
    def test_preregistered_outcome(self):
        d = tree3_stop_rule_mr_decision(
            boundary_scr_recomputed=FROZEN_T_COMPONENT_SCR_REFERENCE)
        assert not d["nested_inside_ci"]
        assert not d["residual_shrinks_strictly"]
        assert d["residual_unchanged_vs_vine2"]
        assert not d["mitigate_criteria_met"]
        assert d["mr016_decision"] == "KEEP_OPEN"
        assert d["mr017_decision"] == "KEEP_OPEN"
        assert d["stop_rule_trigger_met"]
        assert d["stop_rule_applied"]
        assert d["dependence_form_escalation_ends"]
        assert "Phase 31" in d["phase31_directive"]
        assert d["governed_headline_relative_move"] == 0.0
        assert not d["mr010_mr014_refresh_required"]

    def test_residual_threshold_is_exact_not_rounded(self):
        # The design-note "3,637.3" rounds UP from the exact archived
        # residual; a naive 3,637.3 threshold would wrongly pass the
        # bit-identical candidate. The module must use the exact value.
        assert TREE3_COPULA_FORM_RESIDUAL_POINT == \
            RESIDUAL_IMPROVEMENT_THRESHOLD
        assert TREE3_COPULA_FORM_RESIDUAL_POINT < 3637.3

    def test_mitigation_branch_requires_both_criteria(self):
        inside_only = tree3_stop_rule_mr_decision(
            boundary_scr_recomputed=FROZEN_T_COMPONENT_SCR_REFERENCE,
            nested_scr=0.5 * (P30T3_TREE3_CI_LO + P30T3_TREE3_CI_HI))
        assert inside_only["nested_inside_ci"]
        assert not inside_only["mitigate_criteria_met"]
        assert inside_only["mr016_decision"] == "KEEP_OPEN"
        both = tree3_stop_rule_mr_decision(
            boundary_scr_recomputed=FROZEN_T_COMPONENT_SCR_REFERENCE,
            nested_scr=0.5 * (P30T3_TREE3_CI_LO + P30T3_TREE3_CI_HI),
            tree3_residual=RESIDUAL_IMPROVEMENT_THRESHOLD - 1.0)
        assert both["mitigate_criteria_met"]
        assert both["mr016_decision"] == "MITIGATE"
        assert not both["stop_rule_applied"]

    def test_headline_move_triggers_refresh(self):
        d = tree3_stop_rule_mr_decision(
            boundary_scr_recomputed=FROZEN_T_COMPONENT_SCR_REFERENCE * 1.02)
        assert d["mr010_mr014_refresh_required"]

    def test_nested_reference_consistent(self):
        d = tree3_stop_rule_mr_decision(
            boundary_scr_recomputed=FROZEN_T_COMPONENT_SCR_REFERENCE)
        assert d["nested_scr"] == pytest.approx(
            NESTED_PATHWISE_SCR_REFERENCE)
        assert d["tree3_ci"] == [P30T3_TREE3_CI_LO, P30T3_TREE3_CI_HI]


class TestDigestAndRestrictions:
    def test_digest_order_independent(self):
        losses, R, anchors = _synthetic_setup()
        fit3 = _synthetic_fit3()
        res = replicate_tree3_tail_records(
            losses_without=losses, correlation=R,
            rule=ManagementActionRule(), l_fit=300.0, anchor_means=anchors,
            fit3=fit3, sigma=0.1, alpha=1.0, benefit_share=0.5,
            n_replicates=3, n_sim=400, master_seed=31,
            replicate_start=0, replicate_stop=3)
        recs = list(res["records"])
        d1 = tree3_tail_diagnostics_digest(recs)
        d2 = tree3_tail_diagnostics_digest(list(reversed(recs)))
        assert d1 == d2 and len(d1) == 12

    def test_use_restrictions(self):
        ur = tree3_tail_diagnostics_use_restrictions()
        assert ur["classification"] == "EDUCATIONAL"
        assert any("STOP-RULE" in r for r in ur["restrictions"])
        refs = ur["references"]
        assert refs["tree3_bootstrap_ci"] == [P30T3_TREE3_CI_LO,
                                              P30T3_TREE3_CI_HI]
        assert refs["existing_risk"] == "MR-016"
        assert refs["next_risk"] == "MR-017"
