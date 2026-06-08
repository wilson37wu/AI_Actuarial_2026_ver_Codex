"""Phase 26 Task 1 - design note + helper module tests (fast modes only)."""
from __future__ import annotations

import numpy as np
import pytest

from par_model_v2.projection.pathwise_copula_reaggregation import (
    BOOTSTRAP_SE_GATE,
    DF_REMATCH_TOL,
    FULL_REAGG_SIGN_GATE_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
    REAGG_MATERIALITY_DISCLOSURE_THRESHOLD,
    REANCHORING_BOOTSTRAP_CI95,
    REANCHORING_UNDERSTATEMENT_REL,
    RHO_FROZEN_TOL,
    T_COPULA_REANCHORED_READOUT,
    SyntheticReaggConfig,
    pathwise_reaggregation_use_restrictions,
    synthetic_level_vs_component_pre_study,
)

FAST_N = 40_000


@pytest.fixture(scope="module")
def pre():
    return synthetic_level_vs_component_pre_study(seed=42, n_scen=FAST_N)


class TestPreRegisteredConstants:
    def test_archived_references_pinned(self):
        # Archived Phase 25 figures (motivation; gates reference, not recompute)
        assert NESTED_PATHWISE_SCR_REFERENCE == pytest.approx(46_638.9)
        assert T_COPULA_REANCHORED_READOUT == pytest.approx(39_794.3)
        assert FULL_REAGG_SIGN_GATE_REFERENCE == T_COPULA_REANCHORED_READOUT
        lo, hi = REANCHORING_BOOTSTRAP_CI95
        assert lo < hi
        # The quantified motivation: nested sits ABOVE the CI
        assert NESTED_PATHWISE_SCR_REFERENCE > hi
        assert REANCHORING_UNDERSTATEMENT_REL == pytest.approx(0.147)

    def test_rank_invariance_freeze(self):
        assert RANK_INVARIANCE_DF == pytest.approx(2.9451)
        assert DF_REMATCH_TOL <= 1e-4
        assert RHO_FROZEN_TOL <= 1e-12

    def test_disclosure_and_bootstrap_gates(self):
        assert 0.0 < REAGG_MATERIALITY_DISCLOSURE_THRESHOLD <= 0.01
        assert 0.0 < BOOTSTRAP_SE_GATE <= 0.05


class TestSyntheticConfig:
    def test_validation(self):
        with pytest.raises(ValueError):
            SyntheticReaggConfig(n_scen=100)
        with pytest.raises(ValueError):
            SyntheticReaggConfig(rho=1.5)
        with pytest.raises(ValueError):
            SyntheticReaggConfig(df=1.5)
        with pytest.raises(ValueError):
            SyntheticReaggConfig(confidence=0.3)


class TestPreStudy:
    def test_mechanism_demonstrated(self, pre):
        assert pre["mechanism_demonstrated"] is True
        assert pre["understatement_sign_ok"] is True
        assert pre["ordering_ok"] is True
        assert pre["bounds_ok"] is True

    def test_sign_and_ordering(self, pre):
        v = pre["var995"]
        # level basis understates the component basis; both relieve vs without
        assert v["without"] >= v["component"] >= v["level"]
        assert pre["level_understatement_rel_at_var995"] >= 0.0

    def test_tail_cuttable_share_depressed(self, pre):
        # The mechanism: the tail is carve-out-driven
        assert pre["beta_tail_mean"] < pre["beta_mean"]
        assert pre["tail_cuttable_share_depression"] > 0.0

    def test_rerank_not_mean_shift(self, pre):
        # Mean relief nearly unchanged between bases (within 10%)
        a, b = pre["mean_relief_level"], pre["mean_relief_component"]
        assert abs(a - b) / a < 0.10

    def test_reproducible_digest(self, pre):
        again = synthetic_level_vs_component_pre_study(seed=42, n_scen=FAST_N)
        assert again["digest"] == pre["digest"]
        assert again["var995"]["component"] == pytest.approx(
            pre["var995"]["component"]
        )

    def test_seed_sensitivity_sign_stable(self):
        for seed in (7, 2026):
            p = synthetic_level_vs_component_pre_study(seed=seed, n_scen=FAST_N)
            assert p["understatement_sign_ok"] is True

    def test_config_recorded(self, pre):
        cfg = pre["config"]
        assert cfg["n_scen"] == FAST_N
        assert cfg["seed"] == 42
        assert len(cfg["cuttable_mask"]) == 7
        # Carve-out drivers present and not all drivers cuttable
        assert 0.0 < float(np.sum(cfg["cuttable_mask"])) < 7.0


class TestUseRestrictions:
    def test_classification_and_content(self):
        r = pathwise_reaggregation_use_restrictions()
        assert r["classification"] == "EDUCATIONAL"
        text = " ".join(r["restrictions"])
        assert "SIGN" in text
        assert "FROZEN" in text or "frozen" in text
        assert "APS X2" in text


class TestDesignNoteBuilder:
    def test_note_builds_fast_and_passes(self):
        import sys
        sys.path.insert(0, "scripts")
        try:
            from build_phase26_task1_design_note import _card, _md, build_design_note
        finally:
            sys.path.pop(0)
        note = build_design_note(fast=True)
        assert note["verdict"] == "PASS"
        assert note["classification"] == "EDUCATIONAL"
        assert "full path-wise copula re-aggregation" in note["candidate_chosen"]
        assert set(note["candidates_not_chosen"]) == {
            "credentialled_data_calibration", "declaration_cadence_refinement",
        }
        # Pre-registered gates present for tasks 2-4 + task 5 plan
        assert len(note["task2_acceptance_criteria"]) >= 5
        assert len(note["task3_acceptance_criteria"]) >= 4
        assert len(note["task4_acceptance_criteria"]) >= 3
        assert "1.7.0 -> 1.8.0" in note["task5_plan"]
        md = _md(note)
        for section in ("## 0. Candidate selection", "## 1. Problem", "## 2. Method",
                        "## 3. Pre-study", "## 4. Gap analysis",
                        "## 5. Acceptance criteria", "## 6. Limitations",
                        "## 7. Standards"):
            assert section in md
        assert "no gate-shopping" in md
        card = _card(note)
        assert "Design Card (Phase 26)" in card
        assert "46,638.9" in card
