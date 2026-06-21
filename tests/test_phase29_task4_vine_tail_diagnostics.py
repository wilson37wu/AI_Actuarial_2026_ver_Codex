"""Phase 29 Task 4 - unit tests for the vine pair-level tail diagnostics,
fit-vs-holdout overfit check, and MR-016 remediation decision."""
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
from par_model_v2.projection.vine_tail_diagnostics import (
    P29T3_VINE_CI_HI,
    P29T3_VINE_CI_LO,
    TAIL_LEVEL_GRID,
    mr016_remediation_decision,
    overfit_fit_vs_holdout_check,
    pair_tail_grid_for_uniforms,
    replicate_pair_tail_records,
    summarise_pair_tail_diagnostics,
    vine_tail_diagnostics_digest,
    vine_tail_diagnostics_use_restrictions,
)

N_DRIVERS = len(DRIVER_NAMES)


def _synthetic_losses(n_obs: int = 90, seed: int = 7):
    rng = np.random.default_rng(seed)
    base = rng.standard_normal(n_obs)
    return {k: np.exp(0.4 * (0.6 * base + 0.8 * rng.standard_normal(n_obs)))
            * (40.0 + 6.0 * i)
            for i, k in enumerate(DRIVER_NAMES)}


def _synthetic_fit():
    return fit_vine_pair_families(_synthetic_losses(), DRIVER_NAMES)


def _synthetic_setup():
    losses = _synthetic_losses()
    R = np.full((N_DRIVERS, N_DRIVERS), 0.3)
    np.fill_diagonal(R, 1.0)
    anchors = {k: float(np.mean(v)) for k, v in losses.items()}
    return losses, R, anchors


class TestPairTailGrid:
    def test_bounds_and_structure(self):
        rng = np.random.default_rng(11)
        U_c = rng.uniform(size=(4000, N_DRIVERS))
        U_f = rng.uniform(size=(4000, N_DRIVERS))
        grid = pair_tail_grid_for_uniforms(U_c, U_f)
        assert set(grid.keys()) == {"80", "85", "90", "95"}
        for key, p in zip(("80", "85", "90", "95"), TAIL_LEVEL_GRID):
            block = grid[key]
            assert len(block["first_tree"]) == 6
            assert len(block["second_tree"]) == 5
            assert len(block["holdout"]) == 3
            cap = 1.0 / (1.0 - p) + 1e-9
            for g in ("first_tree", "second_tree", "holdout"):
                for row in block[g]:
                    for m in ("cand_upper", "cand_lower", "frz_upper",
                              "frz_lower"):
                        assert 0.0 <= row[m] <= cap
                    assert row["lift_upper"] == pytest.approx(
                        row["cand_upper"] - row["frz_upper"])

    def test_second_tree_is_conditional_on_root(self):
        rng = np.random.default_rng(13)
        U = rng.uniform(size=(4000, N_DRIVERS))
        grid = pair_tail_grid_for_uniforms(U, U)
        for row in grid["90"]["second_tree"]:
            assert row["condition_on"] == 2  # credit root
        for row in grid["90"]["first_tree"] + grid["90"]["holdout"]:
            assert row["condition_on"] is None

    def test_identical_uniforms_give_zero_lift(self):
        rng = np.random.default_rng(17)
        U = rng.uniform(size=(3000, N_DRIVERS))
        grid = pair_tail_grid_for_uniforms(U, U)
        for key in grid:
            for g in ("first_tree", "second_tree", "holdout"):
                for row in grid[key][g]:
                    assert row["lift_upper"] == 0.0
                    assert row["lift_lower"] == 0.0


class TestReplicateRecords:
    def test_chunk_independent_and_crosschecked(self):
        losses, R, anchors = _synthetic_setup()
        fit = _synthetic_fit()
        kw = dict(losses_without=losses, correlation=R,
                  rule=ManagementActionRule(), l_fit=2000.0,
                  anchor_means=anchors, fit=fit, sigma=0.1, alpha=1.0,
                  benefit_share=0.5, n_replicates=4, n_sim=600,
                  master_seed=123)
        full = replicate_pair_tail_records(**kw)
        a = replicate_pair_tail_records(replicate_start=0, replicate_stop=2, **kw)
        b = replicate_pair_tail_records(replicate_start=2, replicate_stop=4, **kw)
        merged = a["records"] + b["records"]
        for rf, rm in zip(full["records"], merged):
            assert rf["cop_seed"] == rm["cop_seed"]
            assert rf["scr_component_vine"] == rm["scr_component_vine"]
            assert rf["scr_component_frozen_t"] == rm["scr_component_frozen_t"]
        archived = {int(r["replicate_index"]): {
            "cop_seed": r["cop_seed"],
            "scr_component_vine": r["scr_component_vine"],
            "scr_component_frozen_t": r["scr_component_frozen_t"],
        } for r in full["records"]}
        again = replicate_pair_tail_records(archived_records=archived, **kw)
        assert again["archived_crosscheck_max_abs_dev"] == 0.0

    def test_crosscheck_detects_tampering(self):
        losses, R, anchors = _synthetic_setup()
        fit = _synthetic_fit()
        kw = dict(losses_without=losses, correlation=R,
                  rule=ManagementActionRule(), l_fit=2000.0,
                  anchor_means=anchors, fit=fit, sigma=0.1, alpha=1.0,
                  benefit_share=0.5, n_replicates=2, n_sim=500,
                  master_seed=321)
        full = replicate_pair_tail_records(**kw)
        archived = {int(r["replicate_index"]): {
            "cop_seed": r["cop_seed"],
            "scr_component_vine": float(r["scr_component_vine"]) + 1.0,
            "scr_component_frozen_t": r["scr_component_frozen_t"],
        } for r in full["records"]}
        tampered = replicate_pair_tail_records(archived_records=archived, **kw)
        assert tampered["archived_crosscheck_max_abs_dev"] >= 1.0


class TestSummariesAndOverfit:
    def _records(self, n_replicates=3):
        losses, R, anchors = _synthetic_setup()
        fit = _synthetic_fit()
        res = replicate_pair_tail_records(
            losses_without=losses, correlation=R,
            rule=ManagementActionRule(), l_fit=2000.0, anchor_means=anchors,
            fit=fit, sigma=0.1, alpha=1.0, benefit_share=0.5,
            n_replicates=n_replicates, n_sim=600, master_seed=99)
        return res["records"], fit

    def test_summary_shape_and_ci_fields(self):
        records, _ = self._records()
        summary = summarise_pair_tail_diagnostics(records)
        for key in ("80", "85", "90", "95"):
            assert len(summary[key]["first_tree"]) == 6
            assert len(summary[key]["second_tree"]) == 5
            assert len(summary[key]["holdout"]) == 3
            row = summary[key]["holdout"][0]
            for m in ("cand_upper", "frz_upper", "lift_upper", "lift_lower"):
                for f in ("mean", "se", "ci_lo", "ci_hi", "n"):
                    assert f in row[m]

    def test_overfit_check_runs_and_reports(self):
        records, fit = self._records()
        summary = summarise_pair_tail_diagnostics(records)
        ov = overfit_fit_vs_holdout_check(summary, fit.to_dict())
        assert ov["n_fit_pairs"] == 11
        assert ov["n_holdout_pairs"] == 3
        assert ov["holdout_disclosure_complete"] is True
        assert ov["overfit_gate_pass"] == (
            ov["holdout_disclosure_complete"] and ov["concentration_ok"])
        assert ov["concentration_ok"] == (
            ov["max_holdout_pair_abs_mean_lift"]
            <= ov["max_fit_pair_abs_mean_lift"])

    def test_digest_idempotent_and_order_independent(self):
        records, _ = self._records()
        d1 = vine_tail_diagnostics_digest(records)
        d2 = vine_tail_diagnostics_digest(list(reversed(records)))
        assert d1 == d2 and len(d1) == 12


class TestMRDecision:
    def test_archived_constants_keep_open_and_open_mr017(self):
        d = mr016_remediation_decision(
            boundary_scr_recomputed=FROZEN_T_COMPONENT_SCR_REFERENCE)
        assert d["nested_inside_ci"] is False
        assert d["residual_materially_shrinks"] is True
        assert d["close_criteria_met"] is False
        assert d["mr016_decision"] == "KEEP_OPEN"
        assert d["open_mr017"] is True
        assert d["governed_headline_relative_move"] == 0.0
        assert d["mr010_mr014_refresh_required"] is False
        assert d["vine_ci"] == [P29T3_VINE_CI_LO, P29T3_VINE_CI_HI]

    def test_close_branch_when_nested_inside_and_shrinks(self):
        d = mr016_remediation_decision(
            boundary_scr_recomputed=FROZEN_T_COMPONENT_SCR_REFERENCE,
            vine_ci_lo=40000.0, vine_ci_hi=50000.0)
        assert d["nested_inside_ci"] is True
        assert d["close_criteria_met"] is True
        assert d["mr016_decision"] == "CLOSE_OR_MITIGATE"
        assert d["open_mr017"] is False

    def test_refresh_branch_when_headline_moves(self):
        moved = FROZEN_T_COMPONENT_SCR_REFERENCE * 1.02
        d = mr016_remediation_decision(boundary_scr_recomputed=moved)
        assert d["mr010_mr014_refresh_required"] is True

    def test_nested_reference_unchanged(self):
        d = mr016_remediation_decision(
            boundary_scr_recomputed=FROZEN_T_COMPONENT_SCR_REFERENCE)
        assert d["nested_scr"] == NESTED_PATHWISE_SCR_REFERENCE


class TestUseRestrictions:
    def test_content(self):
        u = vine_tail_diagnostics_use_restrictions()
        assert u["classification"] == "EDUCATIONAL"
        assert any("owner sign-off" in s for s in u["restrictions"])
        assert any("OPEN" in s for s in u["restrictions"])
        refs = u["references"]
        assert refs["existing_risk"] == "MR-016"
        assert refs["next_risk"] == "MR-017"
        assert refs["vine_bootstrap_ci"][1] < refs["nested_pathwise_reference"]
