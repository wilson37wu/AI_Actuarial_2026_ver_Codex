"""Phase 25 Task 1 tests: path-wise bonus dynamics module + design-note contract."""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.pathwise_bonus_dynamics import (
    BASES,
    PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD,
    PATHWISE_OOS_R2_GATE,
    PATHWISE_VAR_REL_ERROR_GATE,
    PathwiseBonusConfig,
    pathwise_bonus_use_restrictions,
    retained_bonus_rate,
    simulate_bases,
    synthetic_recognition_lag_pre_study,
)

NOTE_JSON = os.path.join("docs", "validation", "PHASE25_TASK1_DESIGN_NOTE.json")
NOTE_MD = os.path.join("docs", "validation", "PHASE25_TASK1_DESIGN_NOTE.md")
CARD_MD = os.path.join("docs", "PATHWISE_BONUS_DECLARATION_DESIGN_CARD.md")

RULE = ManagementActionRule()
FAST = dict(n_outer=600, n_inner=30, n_steps=8)


@pytest.fixture(scope="module")
def pre():
    return synthetic_recognition_lag_pre_study(seed=42, **FAST)


# ---------------------------------------------------------------- config
def test_config_rejects_small_n_outer():
    with pytest.raises(ValueError):
        PathwiseBonusConfig(n_outer=10)


def test_config_rejects_small_n_inner():
    with pytest.raises(ValueError):
        PathwiseBonusConfig(n_inner=2)


def test_config_rejects_single_step():
    with pytest.raises(ValueError):
        PathwiseBonusConfig(n_steps=1)


def test_config_rejects_bad_confidence():
    with pytest.raises(ValueError):
        PathwiseBonusConfig(confidence=1.2)


def test_config_rejects_nonpositive_sigma():
    with pytest.raises(ValueError):
        PathwiseBonusConfig(sigma=0.0)


def test_config_to_dict_round_trip_keys():
    d = PathwiseBonusConfig().to_dict()
    assert {"n_outer", "n_inner", "n_steps", "seed", "confidence"} <= set(d)


# ---------------------------------------------------------------- retained rate
def test_retained_rate_bounds():
    cr = np.linspace(0.5, 1.5, 101)
    r = retained_bonus_rate(RULE, cr)
    assert np.all(r >= RULE.pre_floor - 1e-12) and np.all(r <= 1.0 + 1e-12)


def test_retained_rate_full_above_trigger_floor_below_floor():
    assert retained_bonus_rate(RULE, np.array([RULE.cr_trigger + 0.01])) == pytest.approx(1.0)
    assert retained_bonus_rate(RULE, np.array([RULE.cr_floor - 0.01])) == pytest.approx(RULE.pre_floor)


def test_retained_rate_monotone_in_cr():
    cr = np.linspace(0.6, 1.4, 201)
    assert np.all(np.diff(retained_bonus_rate(RULE, cr)) >= -1e-12)


# ---------------------------------------------------------------- simulation
def test_simulate_bases_returns_all_bases():
    sim = simulate_bases(PathwiseBonusConfig(**FAST), RULE)
    for b in BASES:
        assert np.asarray(sim[b]).shape == (FAST["n_outer"],)


def test_elementwise_bounds_without_dominates_max_cut():
    sim = simulate_bases(PathwiseBonusConfig(**FAST), RULE)
    wo, mc = np.asarray(sim["without"]), np.asarray(sim["max_cut"])
    for b in ("horizon", "pathwise"):
        x = np.asarray(sim[b])
        assert np.all(x <= wo + 1e-7) and np.all(x >= mc - 1e-7)


def test_common_random_numbers_without_basis_is_deterministic_in_seed():
    a = simulate_bases(PathwiseBonusConfig(**FAST, seed=7), RULE)["without"]
    b = simulate_bases(PathwiseBonusConfig(**FAST, seed=7), RULE)["without"]
    assert np.array_equal(np.asarray(a), np.asarray(b))


# ---------------------------------------------------------------- pre-study
def test_pre_study_mechanism_demonstrated(pre):
    assert pre["mechanism_demonstrated"] is True


def test_pre_study_understatement_sign(pre):
    assert pre["var995"]["pathwise"] > pre["var995"]["horizon"]


def test_pre_study_relief_ordering_at_var(pre):
    v = pre["var995"]
    assert v["without"] >= v["pathwise"] > v["horizon"] >= v["max_cut"]


def test_pre_study_restoration_is_real_dynamic(pre):
    assert 0.0 < pre["pathwise_restoration_share"] <= pre["pathwise_action_share"] <= 1.0


def test_pre_study_bounds_ok(pre):
    assert pre["bounds_ok"] is True


def test_pre_study_two_sided_lag_median_negative(pre):
    # healthy nodes: path-wise cuts MORE than the (no-action) horizon basis
    assert pre["median_diff_pathwise_minus_horizon"] < 0.0


def test_pre_study_digest_reproducible():
    a = synthetic_recognition_lag_pre_study(seed=11, **FAST)
    b = synthetic_recognition_lag_pre_study(seed=11, **FAST)
    assert a["digest"] == b["digest"]


def test_pre_study_digest_seed_sensitive(pre):
    other = synthetic_recognition_lag_pre_study(seed=43, **FAST)
    assert other["digest"] != pre["digest"]


# ---------------------------------------------------------------- gates pinned
def test_gates_pinned_unchanged_phase22_values():
    assert PATHWISE_OOS_R2_GATE == 0.95
    assert PATHWISE_VAR_REL_ERROR_GATE == 0.10


def test_materiality_disclosure_threshold_pinned():
    assert PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD == 0.01


def test_use_restrictions_contract():
    u = pathwise_bonus_use_restrictions()
    assert u["classification"] == "EDUCATIONAL" and u["production_use"] is False
    assert u["gates"]["pathwise_oos_r2_gate"] == PATHWISE_OOS_R2_GATE


# ---------------------------------------------------------------- note contract
def test_note_json_exists_and_passes():
    with open(NOTE_JSON) as fh:
        note = json.load(fh)
    assert note["verdict"] == "PASS"
    assert note["classification"] == "EDUCATIONAL"


def test_note_json_contract_keys():
    with open(NOTE_JSON) as fh:
        note = json.load(fh)
    for k in ("candidate_chosen", "candidates_not_chosen", "motivation_from_phase24_task3",
              "problem", "method_design", "pre_study_recognition_lag", "gap_analysis",
              "task2_acceptance_criteria", "task3_acceptance_criteria",
              "task4_acceptance_criteria", "task5_plan", "limitations", "use_restrictions"):
        assert k in note, k


def test_note_json_pre_study_checks_true():
    with open(NOTE_JSON) as fh:
        pre_ = json.load(fh)["pre_study_recognition_lag"]
    assert pre_["understatement_sign_ok"] and pre_["bounds_ok"] and pre_["relief_ordering_ok"]


def test_note_json_gap_analysis_covers_standards():
    with open(NOTE_JSON) as fh:
        gaps = json.load(fh)["gap_analysis"]
    text = " ".join(g["standard"] for g in gaps)
    for s in ("Art. 23", "ASOP 56", "TAS M", "Art. 234"):
        assert s in text, s


def test_note_md_headers_present():
    with open(NOTE_MD) as fh:
        md = fh.read()
    for h in ("## 0. Candidate selection", "## 1. Problem", "## 2. Method",
              "## 3. Pre-study", "## 4. Gap analysis", "## 5. Acceptance criteria",
              "## 6. Limitations", "## 7. Standards"):
        assert h in md, h


def test_card_exists_with_gates():
    with open(CARD_MD) as fh:
        card = fh.read()
    assert "Path-Wise Bonus Declaration" in card and "Pre-registered gates" in card
