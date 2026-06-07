"""Phase 23 Task 3 tests - management-action rule (dynamic bonus cut)."""

import numpy as np
import pytest

from par_model_v2.projection.management_actions import (
    OOS_R2_GATE,
    VAR_REL_ERROR_GATE,
    ManagementActionRule,
    management_action_use_restrictions,
    validate_with_actions,
)


@pytest.fixture()
def rule():
    return ManagementActionRule()


# ---------------------------------------------------------------- parameters
def test_default_rule_parameters(rule):
    d = rule.to_dict()
    assert d["cr_trigger"] == 1.10
    assert d["cr_floor"] == 0.90
    assert d["max_relief"] == pytest.approx(0.30 * 0.40)


def test_trigger_must_exceed_floor():
    with pytest.raises(ValueError):
        ManagementActionRule(cr_trigger=0.90, cr_floor=0.90)


def test_floor_must_be_positive():
    with pytest.raises(ValueError):
        ManagementActionRule(cr_floor=0.0, cr_trigger=1.0)


def test_bonus_share_range():
    with pytest.raises(ValueError):
        ManagementActionRule(bonus_share=1.0)
    with pytest.raises(ValueError):
        ManagementActionRule(bonus_share=-0.1)


def test_pre_floor_range():
    with pytest.raises(ValueError):
        ManagementActionRule(pre_floor=1.5)


def test_reference_coverage_positive():
    with pytest.raises(ValueError):
        ManagementActionRule(reference_coverage=0.0)


def test_monotonicity_guard_rejects_steep_band():
    # narrow band + deep cut -> non-monotone transform must be rejected
    with pytest.raises(ValueError, match="monotonicity guard"):
        ManagementActionRule(
            cr_trigger=1.03, cr_floor=0.98, bonus_share=0.30, pre_floor=0.50
        )


# ---------------------------------------------------------------- cut factor
def test_cut_factor_no_action_at_or_above_trigger(rule):
    cr = np.array([1.10, 1.2, 5.0])
    assert np.allclose(rule.cut_factor(cr), 1.0)
    assert np.allclose(rule.relief_fraction(cr), 0.0)


def test_cut_factor_max_cut_at_or_below_floor(rule):
    cr = np.array([0.90, 0.5, 0.01])
    assert np.allclose(rule.cut_factor(cr), 0.0)
    assert np.allclose(rule.relief_fraction(cr), rule.max_relief)


def test_cut_factor_linear_in_band(rule):
    assert rule.cut_factor(np.array([1.00]))[0] == pytest.approx(0.5)
    assert rule.cut_factor(np.array([1.05]))[0] == pytest.approx(0.75)


def test_cut_factor_monotone_in_cr(rule):
    cr = np.linspace(0.5, 1.5, 1001)
    cf = rule.cut_factor(cr)
    assert np.all(np.diff(cf) >= 0.0)


# ------------------------------------------------------------- coverage / A
def test_reference_assets_scaling(rule):
    assert rule.reference_assets(100.0) == pytest.approx(112.0)


def test_reference_assets_rejects_nonpositive(rule):
    with pytest.raises(ValueError):
        rule.reference_assets(0.0)


def test_coverage_ratio_basic(rule):
    cr = rule.coverage_ratio(np.array([112.0, 56.0]), 112.0)
    assert cr == pytest.approx([1.0, 2.0])


def test_coverage_ratio_rejects_nonpositive_liability(rule):
    with pytest.raises(ValueError):
        rule.coverage_ratio(np.array([-1.0]), 112.0)
    with pytest.raises(ValueError):
        rule.coverage_ratio(np.array([1.0]), 0.0)


# ------------------------------------------------------------------- apply
def test_apply_no_change_in_healthy_states(rule):
    a = rule.reference_assets(100.0)
    l = np.array([90.0, 100.0])  # CR = 1.244, 1.12 >= trigger
    out = rule.apply_to_liabilities(l, a)
    assert np.allclose(out, l)


def test_apply_reduces_liability_under_stress(rule):
    a = rule.reference_assets(100.0)
    l_stressed = np.array([130.0])  # CR = 0.862 < floor -> max relief
    out = rule.apply_to_liabilities(l_stressed, a)
    assert out[0] == pytest.approx(130.0 * (1.0 - rule.max_relief))
    assert out[0] < l_stressed[0]


def test_apply_never_increases_liability(rule):
    a = rule.reference_assets(100.0)
    l = np.linspace(60.0, 200.0, 2001)
    out = rule.apply_to_liabilities(l, a)
    assert np.all(out <= l + 1e-12)


def test_transform_monotone_on_wide_range(rule):
    a = rule.reference_assets(100.0)
    assert rule.is_monotone(a, 10.0, 1000.0)


def test_is_monotone_validates_range(rule):
    with pytest.raises(ValueError):
        rule.is_monotone(112.0, 100.0, 50.0)


def test_bonus_cut_nondecreasing_as_coverage_falls(rule):
    # design-note acceptance: cut non-decreasing as CR falls
    cr = np.linspace(1.5, 0.5, 501)
    cut_applied = 1.0 - rule.cut_factor(cr)
    assert np.all(np.diff(cut_applied) >= 0.0)


# ------------------------------------------------- validate_with_actions
def _synthetic_inputs(seed=7, n_eval=500, n_val=60):
    rng = np.random.default_rng(seed)
    nested = 100.0 * np.exp(rng.normal(0.0, 0.05, n_eval))
    proxy = nested * (1.0 + rng.normal(0.0, 0.004, n_eval))
    truth = 100.0 * np.exp(rng.normal(0.0, 0.05, n_val))
    pred = truth * (1.0 + rng.normal(0.0, 0.004, n_val))
    return truth, pred, nested, proxy


def test_validate_with_actions_passes_gates(rule):
    truth, pred, nested, proxy = _synthetic_inputs()
    res = validate_with_actions(
        rule, 100.0, truth, pred, nested, proxy, 0.995, 12
    )
    assert res["verdict"] == "PASS"
    assert all(res["gates"].values())
    assert res["oos_r2_with_actions"] >= OOS_R2_GATE
    assert res["var_rel_error_with_actions"] <= VAR_REL_ERROR_GATE


def test_validate_with_actions_capital_not_increased(rule):
    truth, pred, nested, proxy = _synthetic_inputs()
    res = validate_with_actions(
        rule, 100.0, truth, pred, nested, proxy, 0.995, 12
    )
    w = res["nested_capital_with"]
    wo = res["nested_capital_without"]
    assert w["var_liability"] <= wo["var_liability"] + 1e-9
    assert w["scr_proxy"] <= wo["scr_proxy"] + 1e-9
    assert res["nested_var_reduction"] >= 0.0
    assert res["nested_scr_reduction"] >= 0.0


def test_validate_with_actions_tail_relief_strictly_positive(rule):
    truth, pred, nested, proxy = _synthetic_inputs()
    res = validate_with_actions(
        rule, 100.0, truth, pred, nested, proxy, 0.995, 12
    )
    # the rule must actually bite in the tail for this calibration
    assert res["nested_var_reduction"] > 0.0
    assert 0.0 < res["active_share_nested"] < 1.0


def test_validate_with_actions_reference_assets_from_fit_mean_only(rule):
    truth, pred, nested, proxy = _synthetic_inputs()
    res = validate_with_actions(
        rule, 100.0, truth, pred, nested, proxy, 0.995, 12
    )
    assert res["reference_assets"] == pytest.approx(
        rule.reference_assets(100.0)
    )
    res2 = validate_with_actions(
        rule, 90.0, truth, pred, nested, proxy, 0.995, 12
    )
    assert res2["reference_assets"] == pytest.approx(
        rule.reference_assets(90.0)
    )


def test_validate_with_actions_gate_keys_fixed(rule):
    truth, pred, nested, proxy = _synthetic_inputs()
    res = validate_with_actions(
        rule, 100.0, truth, pred, nested, proxy, 0.995, 12
    )
    assert set(res["gates"]) == {
        "G1_oos_r2_with_actions_ge_0p95",
        "G2_var_rel_error_with_actions_le_0p10",
        "G3_with_actions_capital_le_without",
        "G4_rule_monotone",
        "G5_no_action_above_trigger",
    }


def test_validate_with_actions_fails_on_bad_proxy(rule):
    truth, pred, nested, proxy = _synthetic_inputs()
    rng = np.random.default_rng(123)
    bad_pred = truth.mean() + rng.normal(0.0, 30.0, truth.size)
    res = validate_with_actions(
        rule, 100.0, truth, bad_pred, nested, proxy, 0.995, 12
    )
    assert not res["gates"]["G1_oos_r2_with_actions_ge_0p95"]
    assert res["verdict"] == "FAIL"


def test_validate_with_actions_deterministic(rule):
    truth, pred, nested, proxy = _synthetic_inputs()
    r1 = validate_with_actions(
        rule, 100.0, truth, pred, nested, proxy, 0.995, 12
    )
    r2 = validate_with_actions(
        rule, 100.0, truth, pred, nested, proxy, 0.995, 12
    )
    assert r1["oos_r2_with_actions"] == r2["oos_r2_with_actions"]
    assert r1["nested_capital_with"] == r2["nested_capital_with"]


# ------------------------------------------------------------- governance
def test_use_restrictions_block():
    ur = management_action_use_restrictions()
    assert ur["classification"] == "EDUCATIONAL_DEMONSTRATION_ONLY"
    assert any("Production" in p for p in ur["prohibited_uses"])
    assert "APS X2" in ur["rationale"]
