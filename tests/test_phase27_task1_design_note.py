"""Phase 27 Task 1 - design note + helper module tests (fast modes only)."""
from __future__ import annotations

import numpy as np
import pytest

from par_model_v2.projection.tail_dependence_upgrade import (
    BOOTSTRAP_N_SIM_GATE,
    BOOTSTRAP_REPLICATES_GATE,
    BOOTSTRAP_SE_GATE,
    COPULA_FORM_RESIDUAL_ABS,
    COPULA_FORM_SHARE_OF_GAP,
    DEPENDENCE_FORM_SENSITIVITY_T_MINUS_G,
    DF_REMATCH_TOL,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GAMMA_ZERO_RECOVERY_TOL,
    NESTED_PATHWISE_SCR_REFERENCE,
    NEW_RISK_ID,
    RANK_INVARIANCE_DF,
    REAGG_MATERIALITY_DISCLOSURE_THRESHOLD,
    RELIEF_SURFACE_PART_ABS,
    RHO_FROZEN_TOL,
    RICHER_COPULA_SIGN_GATE_REFERENCE,
    TOTAL_GAP_ABS,
    TOTAL_GAP_REL_TO_NESTED,
    SkewTConfig,
    skew_t_vs_symmetric_t_pre_study,
    tail_dependence_upgrade_use_restrictions,
)

FAST_N = 40_000


@pytest.fixture(scope="module")
def pre():
    return skew_t_vs_symmetric_t_pre_study(seed=42, n_scen=FAST_N)


class TestPreRegisteredConstants:
    def test_archived_references_pinned(self):
        # Archived Phase 26 figures (motivation; gates reference, not recompute)
        assert NESTED_PATHWISE_SCR_REFERENCE == pytest.approx(46_638.9)
        assert FROZEN_T_COMPONENT_SCR_REFERENCE == pytest.approx(39_975.654628, rel=1e-6)
        assert RICHER_COPULA_SIGN_GATE_REFERENCE == FROZEN_T_COMPONENT_SCR_REFERENCE
        # The quantified motivation: nested ABOVE the frozen-t component read-out
        assert NESTED_PATHWISE_SCR_REFERENCE > FROZEN_T_COMPONENT_SCR_REFERENCE

    def test_residual_decomposition_pinned(self):
        # The Phase 27 motivation: residual is COPULA-FORM dominated
        assert COPULA_FORM_SHARE_OF_GAP > 0.9
        assert COPULA_FORM_RESIDUAL_ABS > DEPENDENCE_FORM_SENSITIVITY_T_MINUS_G
        # copula-form + relief-surface ≈ total gap
        assert COPULA_FORM_RESIDUAL_ABS + RELIEF_SURFACE_PART_ABS == pytest.approx(
            TOTAL_GAP_ABS, rel=1e-6
        )
        assert TOTAL_GAP_REL_TO_NESTED == pytest.approx(0.142869, rel=1e-4)

    def test_rank_invariance_freeze(self):
        assert RANK_INVARIANCE_DF == pytest.approx(2.9451)
        assert DF_REMATCH_TOL <= 1e-4
        assert RHO_FROZEN_TOL <= 1e-12

    def test_disclosure_and_bootstrap_gates(self):
        assert 0.0 < REAGG_MATERIALITY_DISCLOSURE_THRESHOLD <= 0.01
        assert 0.0 < BOOTSTRAP_SE_GATE <= 0.05
        assert BOOTSTRAP_REPLICATES_GATE >= 200
        assert BOOTSTRAP_N_SIM_GATE >= 20_000
        assert GAMMA_ZERO_RECOVERY_TOL <= 1e-9
        assert NEW_RISK_ID == "MR-015"


class TestSkewTConfig:
    def test_validation(self):
        with pytest.raises(ValueError):
            SkewTConfig(n_scen=100)
        with pytest.raises(ValueError):
            SkewTConfig(rho=1.5)
        with pytest.raises(ValueError):
            SkewTConfig(df=1.5)
        with pytest.raises(ValueError):
            SkewTConfig(gamma=-0.1)
        with pytest.raises(ValueError):
            SkewTConfig(confidence=1.0)


class TestPreStudyMechanism:
    def test_sign_upper_tail_understatement(self, pre):
        # Symmetric copula UNDERSTATES the upper tail vs skew-t (positive sign)
        assert pre["var_understatement_rel_at_var995"] > 0.0
        assert pre["es_understatement_rel_at_es995"] > 0.0
        assert pre["understatement_sign_ok"] is True

    def test_radial_asymmetry(self, pre):
        td = pre["tail_dependence_proxy"]
        # skew-t lifts the UPPER tail; lower tail stays near-symmetric
        assert td["skew_t_upper"] > td["symmetric_t_upper"]
        assert td["skew_t_asymmetry"] > td["symmetric_t_asymmetry"]
        assert td["symmetric_t_asymmetry"] == pytest.approx(0.0, abs=0.05)
        assert pre["asymmetry_ok"] is True

    def test_ordering(self, pre):
        assert pre["var995"]["skew_t"] >= pre["var995"]["symmetric_t"]
        assert pre["es995"]["skew_t"] >= pre["es995"]["symmetric_t"]
        assert pre["ordering_ok"] is True

    def test_gamma_zero_exact_recovery(self, pre):
        # gamma = 0 reproduces the symmetric t EXACTLY (strict super-set)
        assert pre["gamma_zero_recovery_max_abs"] <= GAMMA_ZERO_RECOVERY_TOL
        assert pre["gamma_zero_recovery_ok"] is True

    def test_mechanism_demonstrated(self, pre):
        assert pre["mechanism_demonstrated"] is True

    def test_reproducible_digest(self):
        a = skew_t_vs_symmetric_t_pre_study(seed=42, n_scen=FAST_N)
        b = skew_t_vs_symmetric_t_pre_study(seed=42, n_scen=FAST_N)
        assert a["digest"] == b["digest"]

    def test_gamma_monotone_in_upper_tail(self):
        # Larger skewness -> heavier upper tail -> higher VaR99.5
        lo = skew_t_vs_symmetric_t_pre_study(seed=7, n_scen=FAST_N, gamma=0.4)
        hi = skew_t_vs_symmetric_t_pre_study(seed=7, n_scen=FAST_N, gamma=1.0)
        assert hi["var995"]["skew_t"] >= lo["var995"]["skew_t"]
        assert (
            hi["tail_dependence_proxy"]["skew_t_upper"]
            >= lo["tail_dependence_proxy"]["skew_t_upper"]
        )


class TestUseRestrictions:
    def test_educational(self):
        r = tail_dependence_upgrade_use_restrictions()
        assert r["classification"] == "EDUCATIONAL"
        assert any("design note only" in s.lower() for s in r["restrictions"])
        assert any("gamma = 0" in s.lower() or "nest" in s.lower() for s in r["restrictions"])


class TestDesignNoteBuilder:
    def test_build_note_pass(self):
        from scripts.build_phase27_task1_design_note import build_design_note

        note = build_design_note(fast=True)
        assert note["verdict"] == "PASS"
        assert note["classification"] == "EDUCATIONAL"
        assert "skew-t" in note["candidate_chosen"].lower()
        for key in (
            "task2_acceptance_criteria",
            "task3_acceptance_criteria",
            "task4_acceptance_criteria",
            "gap_analysis",
        ):
            assert note[key]
        # sign gate references the frozen-t component
        assert any(
            "sign gate" in c.lower() for c in note["task2_acceptance_criteria"]
        )
        # headline gate references the nested reference
        assert any(
            "headline" in c.lower() for c in note["task3_acceptance_criteria"]
        )
