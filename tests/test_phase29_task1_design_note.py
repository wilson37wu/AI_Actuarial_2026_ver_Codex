"""Phase 29 Task 1 - vine / pair-copula design note tests."""

from __future__ import annotations

import pytest

from par_model_v2.projection.vine_copula_upgrade import (
    BOOTSTRAP_N_SIM_GATE,
    BOOTSTRAP_REPLICATES_GATE,
    BOOTSTRAP_SE_GATE,
    DF_REMATCH_TOL,
    DRIVER_NAMES,
    EXISTING_RISK_ID,
    FIRST_TREE_EDGES,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_COMPONENT_SCR_BOOTSTRAP_MEAN,
    GROUPED_T_COMPONENT_SCR_POINT,
    GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    GROUPED_T_P90_CROSS_BLOCK_DILUTION,
    MAX_VINE_TREES,
    NESTED_PATHWISE_SCR_REFERENCE,
    NEXT_RISK_ID,
    PAIR_FAMILY_CANDIDATES,
    RANK_INVARIANCE_DF,
    REAGG_MATERIALITY_DISCLOSURE_THRESHOLD,
    RHO_FROZEN_TOL,
    SECOND_TREE_EDGES,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
    VINE_BOUNDARY_RECOVERY_TOL,
    VINE_ROOT_DRIVER,
    VineDesignConfig,
    all_pre_registered_pairs,
    validate_vine_design_envelope,
    vine_copula_upgrade_use_restrictions,
    vine_pair_copula_pre_study,
)

FAST_N = 40_000


@pytest.fixture(scope="module")
def pre():
    return vine_pair_copula_pre_study(seed=42, n_scen=FAST_N)


class TestArchivedReferences:
    def test_residual_references_pinned(self):
        assert NESTED_PATHWISE_SCR_REFERENCE == pytest.approx(46_638.9)
        assert FROZEN_T_COMPONENT_SCR_REFERENCE == pytest.approx(39_975.654628199336)
        assert SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS == pytest.approx(6_114.9)
        assert GROUPED_T_COMPONENT_SCR_POINT == pytest.approx(35_604.39894619743)
        assert GROUPED_T_COMPONENT_SCR_BOOTSTRAP_MEAN == pytest.approx(35_372.49326229076)
        assert GROUPED_T_COPULA_FORM_RESIDUAL_ABS == pytest.approx(10_491.5)
        assert GROUPED_T_P90_CROSS_BLOCK_DILUTION < 0.0

    def test_rank_freeze_and_bootstrap_gates(self):
        assert RANK_INVARIANCE_DF == pytest.approx(2.9451)
        assert DF_REMATCH_TOL <= 1e-4
        assert RHO_FROZEN_TOL <= 1e-12
        assert VINE_BOUNDARY_RECOVERY_TOL <= 1e-9
        assert BOOTSTRAP_REPLICATES_GATE >= 200
        assert BOOTSTRAP_N_SIM_GATE >= 20_000
        assert BOOTSTRAP_SE_GATE <= 0.05
        assert REAGG_MATERIALITY_DISCLOSURE_THRESHOLD <= 0.01
        assert EXISTING_RISK_ID == "MR-016"
        assert NEXT_RISK_ID == "MR-017"


class TestConfigValidation:
    def test_validation(self):
        with pytest.raises(ValueError):
            VineDesignConfig(n_scen=100)
        with pytest.raises(ValueError):
            VineDesignConfig(rho=1.5)
        with pytest.raises(ValueError):
            VineDesignConfig(df_proxy=1.5)
        with pytest.raises(ValueError):
            VineDesignConfig(conditional_tail_strength=-0.1)
        with pytest.raises(ValueError):
            VineDesignConfig(confidence=1.0)
        with pytest.raises(ValueError):
            VineDesignConfig(tail_p=0.2)


class TestPreRegisteredEnvelope:
    def test_credit_root_structure_pinned(self):
        assert DRIVER_NAMES[VINE_ROOT_DRIVER] == "credit"
        assert MAX_VINE_TREES == 2
        assert len(PAIR_FAMILY_CANDIDATES) <= 4
        assert set(PAIR_FAMILY_CANDIDATES) == {
            "gaussian",
            "student_t",
            "survival_clayton",
            "survival_gumbel",
        }
        assert all(VINE_ROOT_DRIVER in edge for edge in FIRST_TREE_EDGES)
        assert all(edge[2] == VINE_ROOT_DRIVER for edge in SECOND_TREE_EDGES)

    def test_first_tree_spans_all_drivers(self):
        members = sorted({i for e in FIRST_TREE_EDGES for i in e})
        assert members == list(range(len(DRIVER_NAMES)))
        assert len(set(tuple(sorted(e)) for e in FIRST_TREE_EDGES)) == len(FIRST_TREE_EDGES)

    def test_envelope_checks(self):
        checks = validate_vine_design_envelope()
        assert checks["envelope_ok"] is True
        assert checks["candidate_count_ok"] is True
        assert checks["first_tree_spans_all_drivers"] is True
        assert checks["first_tree_is_credit_root_star"] is True
        assert checks["second_tree_uses_root_condition"] is True

    def test_pair_list_flattening(self):
        pairs = all_pre_registered_pairs()
        assert (2, 6) in pairs
        assert (5, 6) in pairs
        assert all(i < j for i, j in pairs)


class TestPreStudyMechanism:
    def test_boundary_recovery(self, pre):
        assert pre["boundary_recovery_max_abs"] <= VINE_BOUNDARY_RECOVERY_TOL
        assert pre["boundary_recovery_ok"] is True

    def test_conditional_targeting(self, pre):
        assert pre["target_upper_tail_lift"] > pre["holdout_upper_tail_lift"]
        assert pre["target_upper_tail_lift"] > 0.02
        assert pre["conditional_targeting_ok"] is True

    def test_mechanism_demonstrated(self, pre):
        assert pre["mechanism_demonstrated"] is True
        assert pre["search_envelope"]["envelope_ok"] is True

    def test_reproducible_digest(self):
        a = vine_pair_copula_pre_study(seed=42, n_scen=FAST_N)
        b = vine_pair_copula_pre_study(seed=42, n_scen=FAST_N)
        assert a["digest"] == b["digest"]

    def test_zero_strength_preserves_boundary(self):
        z = vine_pair_copula_pre_study(seed=7, n_scen=FAST_N, conditional_tail_strength=0.0)
        assert z["boundary_recovery_ok"] is True
        assert z["target_upper_tail_lift"] == pytest.approx(0.0, abs=0.02)


class TestUseRestrictions:
    def test_educational_restrictions(self):
        r = vine_copula_upgrade_use_restrictions()
        assert r["classification"] == "EDUCATIONAL"
        assert any("design note only" in s.lower() for s in r["restrictions"])
        assert any("frozen_t_boundary" in s for s in r["restrictions"])
        assert any("leakage" in s.lower() for s in r["restrictions"])


class TestDesignNoteBuilder:
    def test_build_note_pass(self):
        from scripts.build_phase29_task1_design_note import build_design_note

        note = build_design_note(fast=True)
        assert note["verdict"] == "PASS"
        assert note["classification"] == "EDUCATIONAL"
        assert "vine" in note["candidate_chosen"].lower()
        assert "MR-016" in note["problem"]
        assert note["pre_registered_structure"]["envelope_checks"]["envelope_ok"] is True
        assert any("Frozen boundary" in c for c in note["task2_acceptance_criteria"])
        assert any("HEADLINE" in c for c in note["task3_acceptance_criteria"])
        assert any("MR-016" in c for c in note["task4_acceptance_criteria"])
