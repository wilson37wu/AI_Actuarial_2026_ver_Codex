"""Phase 24 Task 1 tests: joint-action aggregation module + design-note contract."""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

from par_model_v2.projection.joint_action_aggregation import (
    INNER_PATH_OOS_R2_GATE,
    INNER_PATH_VAR_REL_ERROR_GATE,
    JOINT_REL_ERROR_GATE,
    STANDALONE_ACTION_REL_ERROR_BASELINE,
    JointActionAggregator,
    JointActionConfig,
    joint_action_use_restrictions,
    simulate_gaussian_copula_uniforms,
    synthetic_saturation_pre_study,
)
from par_model_v2.projection.management_actions import ManagementActionRule

NOTE_JSON = os.path.join("docs", "validation", "PHASE24_TASK1_DESIGN_NOTE.json")
NOTE_MD = os.path.join("docs", "validation", "PHASE24_TASK1_DESIGN_NOTE.md")

RULE = ManagementActionRule()
R2 = np.array([[1.0, 0.5], [0.5, 1.0]])


def _toy_aggregator(n: int = 400, seed: int = 7) -> JointActionAggregator:
    rng = np.random.default_rng(seed)
    losses = {
        "a": 50_000.0 + 8_000.0 * rng.standard_normal(n),
        "b": 50_000.0 + 6_000.0 * rng.standard_normal(n),
    }
    return JointActionAggregator(losses, R2, RULE, l_fit=100_000.0)


# ---------------------------------------------------------------- config
def test_config_rejects_small_n_sim():
    with pytest.raises(ValueError):
        JointActionConfig(n_sim=10)


def test_config_rejects_nonpositive_df():
    with pytest.raises(ValueError):
        JointActionConfig(df=0.0)


def test_config_rejects_bad_confidence():
    with pytest.raises(ValueError):
        JointActionConfig(confidence=1.5)


def test_config_to_dict_labels_copula():
    assert JointActionConfig().to_dict()["copula"] == "gaussian"
    assert JointActionConfig(df=2.9451).to_dict()["copula"].startswith("t(")


# ---------------------------------------------------------------- gates
def test_pre_registered_gates_fixed_values():
    assert JOINT_REL_ERROR_GATE == 0.10
    assert STANDALONE_ACTION_REL_ERROR_BASELINE == 0.225
    assert INNER_PATH_OOS_R2_GATE == 0.95
    assert INNER_PATH_VAR_REL_ERROR_GATE == 0.10


# ---------------------------------------------------------------- copula sims
def test_gaussian_uniforms_shape_range_reproducible():
    u1 = simulate_gaussian_copula_uniforms(np.random.default_rng(1), 500, R2)
    u2 = simulate_gaussian_copula_uniforms(np.random.default_rng(1), 500, R2)
    assert u1.shape == (500, 2)
    assert np.all((u1 > 0) & (u1 < 1))
    assert np.array_equal(u1, u2)


# ---------------------------------------------------------------- aggregator
def test_aggregator_rejects_empty_losses():
    with pytest.raises(ValueError):
        JointActionAggregator({}, R2, RULE, l_fit=1.0)


def test_aggregator_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        JointActionAggregator(
            {"a": np.ones(5), "b": np.ones(6)}, R2, RULE, l_fit=1.0
        )


def test_aggregator_rejects_bad_correlation_shape():
    with pytest.raises(ValueError):
        JointActionAggregator(
            {"a": np.ones(5), "b": np.ones(5)}, np.eye(3), RULE, l_fit=1.0
        )


def test_aggregator_rejects_nonpositive_l_fit():
    with pytest.raises(ValueError):
        JointActionAggregator(
            {"a": np.ones(5), "b": np.ones(5)}, R2, RULE, l_fit=0.0
        )


def test_joint_levels_anchored_at_l_fit():
    agg = _toy_aggregator()
    u = simulate_gaussian_copula_uniforms(np.random.default_rng(3), 50_000, R2)
    v = agg.joint_levels(u)
    # anchored: mean of joint level close to l_fit (empirical-margin noise only)
    assert abs(float(np.mean(v)) - 100_000.0) < 1_500.0


def test_joint_levels_rejects_bad_shape():
    agg = _toy_aggregator()
    with pytest.raises(ValueError):
        agg.joint_levels(np.zeros((10, 3)))


def test_run_reproducible_same_seed():
    agg = _toy_aggregator()
    cfg = JointActionConfig(n_sim=5_000, seed=11, df=3.0)
    r1, r2 = agg.run(cfg), agg.run(cfg)
    assert r1.digest == r2.digest
    assert r1.var_joint_with == r2.var_joint_with


def test_run_action_reduces_tail_and_shares_valid():
    agg = _toy_aggregator()
    res = agg.run(JointActionConfig(n_sim=20_000, seed=5, df=2.9451))
    assert res.var_joint_with <= res.var_joint_without + 1e-9
    assert 0.0 <= res.floor_share <= res.active_share <= 1.0
    assert res.a_ref == RULE.reference_assets(res.l_fit)


def test_run_matches_manual_rule_application():
    agg = _toy_aggregator()
    cfg = JointActionConfig(n_sim=4_000, seed=23)  # gaussian
    res = agg.run(cfg)
    u = simulate_gaussian_copula_uniforms(np.random.default_rng(23), 4_000, agg.correlation)
    v = agg.joint_levels(u)
    w = RULE.apply_to_liabilities(v, agg.a_ref)
    assert np.isclose(res.var_joint_with, float(np.quantile(w, 0.995)))


def test_result_to_dict_roundtrip():
    res = _toy_aggregator().run(JointActionConfig(n_sim=2_000, seed=2))
    d = res.to_dict()
    assert json.loads(json.dumps(d))["digest"] == res.digest


# ---------------------------------------------------------------- pre-study
@pytest.fixture(scope="module")
def pre_study():
    return synthetic_saturation_pre_study(
        seed=42, n_truth=20_000, n_outer=1_000, n_sim=20_000
    )


def test_pre_study_standalone_basis_understates_truth(pre_study):
    assert pre_study["understatement_sign_ok"] is True
    assert pre_study["standalone_action_var995"] < pre_study["truth_var995_with"]


def test_pre_study_joint_basis_recovers_truth(pre_study):
    assert pre_study["joint_recovers_truth"] is True
    assert pre_study["joint_action_rel_err"] < pre_study["standalone_action_rel_err"]
    assert pre_study["joint_action_rel_err"] < 0.05


def test_pre_study_active_share_consistent(pre_study):
    assert abs(pre_study["joint_action_active_share"] - pre_study["truth_active_share"]) < 0.05


# ---------------------------------------------------------------- use restrictions
def test_use_restrictions_educational():
    ur = joint_action_use_restrictions()
    assert ur["classification"] == "EDUCATIONAL"
    assert any("NOT for production" in r for r in ur["restrictions"])


# ---------------------------------------------------------------- design note
@pytest.fixture(scope="module")
def note():
    assert os.path.exists(NOTE_JSON), "run scripts/build_phase24_task1_design_note.py first"
    with open(NOTE_JSON, encoding="utf-8") as fh:
        return json.load(fh)


def test_note_verdict_pass(note):
    assert note["verdict"] == "PASS"
    assert note["classification"] == "EDUCATIONAL"


def test_note_gates_match_module_constants(note):
    crit = " ".join(note["task2_acceptance_criteria"])
    assert f"{JOINT_REL_ERROR_GATE:.0%}" in crit
    assert f"{STANDALONE_ACTION_REL_ERROR_BASELINE:.1%}" in crit
    assert "2.9451" in crit
    crit3 = " ".join(note["task3_acceptance_criteria"])
    assert str(INNER_PATH_OOS_R2_GATE) in crit3


def test_note_gap_analysis_four_rows_with_keys(note):
    rows = note["gap_analysis"]
    assert len(rows) == 4
    for g in rows:
        for k in ("standard", "requirement", "current_state", "gap", "phase24_design"):
            assert g[k]


def test_note_pre_study_mechanism_recorded(note):
    pre = note["pre_study_synthetic_saturation"]
    assert pre["understatement_sign_ok"] is True
    assert pre["joint_recovers_truth"] is True


def test_note_markdown_rendered():
    assert os.path.exists(NOTE_MD)
    md = open(NOTE_MD, encoding="utf-8").read()
    assert "Verdict: PASS" in md
    assert "action-after-aggregation" in md.lower()
    assert "no gate-shopping" in md.lower()
