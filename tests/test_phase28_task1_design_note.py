"""Phase 28 Task 1 - design note + helper module tests (fast modes only)."""
from __future__ import annotations

import numpy as np
import pytest

from par_model_v2.projection.grouped_t_upgrade import (
    BOOTSTRAP_N_SIM_GATE,
    BOOTSTRAP_REPLICATES_GATE,
    BOOTSTRAP_SE_GATE,
    COPULA_FORM_RESIDUAL_ABS,
    COPULA_FORM_SHARE_OF_GAP,
    DEPENDENCE_FORM_SENSITIVITY_T_MINUS_G,
    DF_REMATCH_TOL,
    FIN_BLOCK,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_SIGN_GATE_REFERENCE,
    HOMOGENEOUS_RECOVERY_TOL,
    NESTED_PATHWISE_SCR_REFERENCE,
    NEW_RISK_ID,
    NONFIN_BLOCK,
    RANK_INVARIANCE_DF,
    REAGG_MATERIALITY_DISCLOSURE_THRESHOLD,
    RELIEF_SURFACE_PART_ABS,
    RHO_FROZEN_TOL,
    SKEWT_GAMMA_HAT,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
    TOTAL_GAP_ABS,
    TOTAL_GAP_REL_TO_NESTED,
    GroupedTConfig,
    grouped_t_upgrade_use_restrictions,
    grouped_t_vs_single_t_pre_study,
)

FAST_N = 40_000


@pytest.fixture(scope="module")
def pre():
    return grouped_t_vs_single_t_pre_study(seed=42, n_scen=FAST_N)


class TestPreRegisteredConstants:
    def test_archived_references_pinned(self):
        # Archived figures (motivation; gates reference, not recompute)
        assert NESTED_PATHWISE_SCR_REFERENCE == pytest.approx(46_638.9)
        assert FROZEN_T_COMPONENT_SCR_REFERENCE == pytest.approx(39_975.654628, rel=1e-6)
        assert GROUPED_T_SIGN_GATE_REFERENCE == FROZEN_T_COMPONENT_SCR_REFERENCE
        # The quantified motivation: nested ABOVE the frozen-t component read-out
        assert NESTED_PATHWISE_SCR_REFERENCE > FROZEN_T_COMPONENT_SCR_REFERENCE

    def test_phase27_reconfirmation_pinned(self):
        # The Phase 28 motivation: skew-t scalar pinned ~0; residual NOT closed
        assert SKEWT_GAMMA_HAT < 1e-4
        assert SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS < COPULA_FORM_RESIDUAL_ABS
        # only a 0.09% reduction -> still ~91.8% of the gap copula-form
        assert SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS > 0.99 * COPULA_FORM_RESIDUAL_ABS
        assert COPULA_FORM_SHARE_OF_GAP > 0.9
        assert COPULA_FORM_RESIDUAL_ABS > DEPENDENCE_FORM_SENSITIVITY_T_MINUS_G
        assert COPULA_FORM_RESIDUAL_ABS + RELIEF_SURFACE_PART_ABS == pytest.approx(
            TOTAL_GAP_ABS, rel=1e-6
        )
        assert TOTAL_GAP_REL_TO_NESTED == pytest.approx(0.142869, rel=1e-4)

    def test_rank_invariance_freeze(self):
        assert RANK_INVARIANCE_DF == pytest.approx(2.9451)
        assert DF_REMATCH_TOL <= 1e-4
        assert RHO_FROZEN_TOL <= 1e-12

    def test_partition_pinned(self):
        # Pre-registered block partition (FIXED before any fit)
        assert tuple(sorted(FIN_BLOCK + NONFIN_BLOCK)) == tuple(range(7))
        assert set(FIN_BLOCK) == {0, 4, 6}
        assert set(FIN_BLOCK).isdisjoint(NONFIN_BLOCK)

    def test_disclosure_and_bootstrap_gates(self):
        assert 0.0 < REAGG_MATERIALITY_DISCLOSURE_THRESHOLD <= 0.01
        assert 0.0 < BOOTSTRAP_SE_GATE <= 0.05
        assert BOOTSTRAP_REPLICATES_GATE >= 200
        assert BOOTSTRAP_N_SIM_GATE >= 20_000
        assert HOMOGENEOUS_RECOVERY_TOL <= 1e-9
        assert NEW_RISK_ID == "MR-016"


class TestGroupedTConfig:
    def test_validation(self):
        with pytest.raises(ValueError):
            GroupedTConfig(n_scen=100)
        with pytest.raises(ValueError):
            GroupedTConfig(rho=1.5)
        with pytest.raises(ValueError):
            GroupedTConfig(df_fin=1.5)
        with pytest.raises(ValueError):
            GroupedTConfig(df_nonfin=1.0)
        with pytest.raises(ValueError):
            GroupedTConfig(confidence=1.0)
        with pytest.raises(ValueError):
            GroupedTConfig(fin_block=(0, 1), nonfin_block=(2, 3))  # not a partition


class TestPreStudyMechanism:
    def test_heterogeneity_within_gt_cross(self, pre):
        td = pre["tail_dependence_proxy"]
        # grouped-t lifts within-block well above cross-block (heterogeneity)
        assert td["grouped_within_fin"] > td["grouped_cross"]
        assert td["grouped_heterogeneity"] > td["single_heterogeneity"]
        assert pre["heterogeneity_ok"] is True

    def test_single_t_near_uniform(self, pre):
        td = pre["tail_dependence_proxy"]
        # single-df t imposes ~uniform pairwise tail dependence across blocks
        assert td["single_heterogeneity"] == pytest.approx(0.0, abs=0.08)

    def test_cross_block_dilution(self, pre):
        # the single-df t is the MAXIMAL-cross-block boundary -> grouped dilutes
        assert pre["cross_block_dilution_rel"] < 0.0

    def test_two_sided_sign_disclosed(self, pre):
        # the aggregate sign is a DISCLOSED field, not a hard gate
        assert pre["aggregate_var_direction"] in ("up", "down")
        assert isinstance(pre["understatement_sign_ok"], bool)
        assert isinstance(pre["ordering_ok"], bool)

    def test_homogeneous_boundary_exact_recovery(self, pre):
        # homogeneous boundary reproduces the single-df t EXACTLY (strict super-set)
        assert pre["homogeneous_recovery_max_abs"] <= HOMOGENEOUS_RECOVERY_TOL
        assert pre["homogeneous_recovery_ok"] is True

    def test_mechanism_demonstrated(self, pre):
        # verdict = heterogeneity + exact recovery (NOT a one-sided sign claim)
        assert pre["mechanism_demonstrated"] is True

    def test_reproducible_digest(self):
        a = grouped_t_vs_single_t_pre_study(seed=42, n_scen=FAST_N)
        b = grouped_t_vs_single_t_pre_study(seed=42, n_scen=FAST_N)
        assert a["digest"] == b["digest"]

    def test_heavier_block_lifts_within_tail(self):
        # a heavier carve-out block -> stronger within-block co-crash
        lo = grouped_t_vs_single_t_pre_study(seed=7, n_scen=FAST_N, df_fin=4.0)
        hi = grouped_t_vs_single_t_pre_study(seed=7, n_scen=FAST_N, df_fin=2.1)
        assert (
            hi["tail_dependence_proxy"]["grouped_within_fin"]
            >= lo["tail_dependence_proxy"]["grouped_within_fin"]
        )


class TestUseRestrictions:
    def test_educational(self):
        r = grouped_t_upgrade_use_restrictions()
        assert r["classification"] == "EDUCATIONAL"
        assert any("design note only" in s.lower() for s in r["restrictions"])
        assert any("nest" in s.lower() or "homogeneous boundary" in s.lower()
                   for s in r["restrictions"])
        assert any("partition" in s.lower() for s in r["restrictions"])


class TestDesignNoteBuilder:
    def test_build_note_pass(self):
        from scripts.build_phase28_task1_design_note import build_design_note

        note = build_design_note(fast=True)
        assert note["verdict"] == "PASS"
        assert note["classification"] == "EDUCATIONAL"
        assert "grouped-t" in note["candidate_chosen"].lower()
        for key in (
            "task2_acceptance_criteria",
            "task3_acceptance_criteria",
            "task4_acceptance_criteria",
            "gap_analysis",
        ):
            assert note[key]
        # exact homogeneous-boundary recovery referenced in Task 2 gates
        assert any(
            "homogeneous-boundary exact" in c.lower() or "homogeneous boundary" in c.lower()
            for c in note["task2_acceptance_criteria"]
        )
        # headline gate references the nested reference
        assert any(
            "headline" in c.lower() for c in note["task3_acceptance_criteria"]
        )
        # the two-sided sign is disclosed in the limitations
        assert any(
            "heterogeneity lever" in l.lower() or "two-sided" in l.lower()
            for l in note["limitations"]
        )
