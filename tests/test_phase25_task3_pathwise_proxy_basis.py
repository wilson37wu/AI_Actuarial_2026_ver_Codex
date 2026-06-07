"""Phase 25 Task 3 tests - matching path-wise proxy basis + OOS re-validation.

Fast unit tests only (no heavy nested re-runs): surface maths, calibration
guards, leakage-freedom, monotonicity, validation gate semantics and failure
paths, deterministic-basis contract, build-report contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_7d import (
    SevenDriverLiquidityProxyValidator,
    seven_driver_proxy_config,
)
from par_model_v2.projection.pathwise_proxy_basis import (
    PATHWISE_OOS_R2_GATE,
    PATHWISE_VAR_REL_ERROR_GATE,
    calibrate_pathwise_level_factor,
    calibrate_pathwise_response_surface,
    deterministic_pathwise_relieved,
    pathwise_declaration_fit_sliced,
    pathwise_proxy_basis_use_restrictions,
    pathwise_surface_monotonicity_check,
    smoothed_relief_response,
    validate_pathwise_proxy_basis,
)

REPORT = Path("docs/validation/PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.json")
CARD = Path("docs/PATHWISE_PROXY_BASIS_CARD.md")


@pytest.fixture(scope="module")
def rule() -> ManagementActionRule:
    return ManagementActionRule()


@pytest.fixture(scope="module")
def validator() -> SevenDriverLiquidityProxyValidator:
    return SevenDriverLiquidityProxyValidator(ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20))


# ---------------------------------------------------------------------------
# gates pinned (no gate-shopping)
# ---------------------------------------------------------------------------

class TestGatesPinned:
    def test_oos_r2_gate_unchanged_phase22(self):
        assert PATHWISE_OOS_R2_GATE == 0.95

    def test_var_rel_error_gate_unchanged_phase22(self):
        assert PATHWISE_VAR_REL_ERROR_GATE == 0.10


# ---------------------------------------------------------------------------
# smoothed relief response surface
# ---------------------------------------------------------------------------

class TestSmoothedReliefResponse:
    def test_sigma_zero_recovers_relief_fraction(self, rule):
        cr = np.array([0.5, 0.9, 1.0, 1.1, 1.5])
        np.testing.assert_allclose(
            smoothed_relief_response(rule, cr, 0.0),
            rule.relief_fraction(cr))

    def test_non_increasing_in_cr(self, rule):
        cr = np.linspace(0.3, 3.0, 500)
        phi = smoothed_relief_response(rule, cr, 0.25)
        assert np.all(np.diff(phi) <= 1e-12)

    def test_bounded_by_max_relief(self, rule):
        cr = np.linspace(0.05, 5.0, 200)
        for s in (0.05, 0.25, 0.6):
            phi = smoothed_relief_response(rule, cr, s)
            assert np.all(phi >= -1e-15)
            assert np.all(phi <= rule.max_relief + 1e-12)

    def test_scalar_input_returns_float(self, rule):
        out = smoothed_relief_response(rule, np.float64(1.0), 0.2)
        assert isinstance(out, float)

    def test_smoothing_spreads_the_trigger(self, rule):
        # just above the trigger the raw relief is 0 but the smoothed
        # response is positive (diffusion-driven cuts from healthy nodes)
        cr = rule.cr_trigger + 0.05
        assert rule.relief_fraction(np.array([cr]))[0] == 0.0
        assert smoothed_relief_response(rule, np.array([cr]), 0.25)[0] > 0.0

    def test_negative_sigma_raises(self, rule):
        with pytest.raises(ValueError):
            smoothed_relief_response(rule, np.array([1.0]), -0.1)

    def test_nan_sigma_raises(self, rule):
        with pytest.raises(ValueError):
            smoothed_relief_response(rule, np.array([1.0]), float("nan"))


# ---------------------------------------------------------------------------
# candidate (a) level factor
# ---------------------------------------------------------------------------

class TestLevelFactor:
    def test_exact_recovery(self):
        d = np.array([1.0, 2.0, 3.0])
        assert calibrate_pathwise_level_factor(2.5 * d, d) == pytest.approx(2.5)

    def test_zero_signal_raises(self):
        with pytest.raises(ValueError, match="no signal"):
            calibrate_pathwise_level_factor(
                np.array([10.0, 20.0]), np.array([0.0, 0.0]))

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            calibrate_pathwise_level_factor(
                np.array([1.0, 2.0]), np.array([1.0]))

    def test_negative_relieved_raises(self):
        with pytest.raises(ValueError):
            calibrate_pathwise_level_factor(
                np.array([-1.0, 2.0]), np.array([1.0, 1.0]))


# ---------------------------------------------------------------------------
# candidate (b) response-surface calibration
# ---------------------------------------------------------------------------

class TestSurfaceCalibration:
    def test_recovers_known_surface(self, rule):
        rng = np.random.default_rng(7)
        cr = rng.uniform(0.7, 1.8, 400)
        ben = rng.uniform(50.0, 150.0, 400)
        truth = 0.8 * smoothed_relief_response(rule, cr, 0.3) * ben
        rec = calibrate_pathwise_response_surface(rule, cr, ben, truth)
        assert rec["sigma"] == pytest.approx(0.3, abs=0.026)
        assert rec["alpha"] == pytest.approx(0.8, rel=0.05)
        assert rec["fit_r2_relieved"] > 0.999
        assert rec["sigma_interior"]

    def test_two_scalars_only_contract(self, rule):
        rng = np.random.default_rng(8)
        cr = rng.uniform(0.7, 1.8, 100)
        ben = rng.uniform(50.0, 150.0, 100)
        truth = 0.5 * smoothed_relief_response(rule, cr, 0.2) * ben
        rec = calibrate_pathwise_response_surface(rule, cr, ben, truth)
        for k in ("sigma", "alpha", "fit_r2_relieved", "fit_truth_mean",
                  "fit_pred_mean", "sigma_grid_lo", "sigma_grid_hi",
                  "sigma_interior", "gh_order"):
            assert k in rec

    def test_misaligned_raises(self, rule):
        with pytest.raises(ValueError):
            calibrate_pathwise_response_surface(
                rule, np.array([1.0, 1.1]), np.array([1.0]),
                np.array([1.0, 2.0]))

    def test_negative_truth_raises(self, rule):
        with pytest.raises(ValueError):
            calibrate_pathwise_response_surface(
                rule, np.array([1.0, 1.1]), np.array([1.0, 1.0]),
                np.array([-1.0, 1.0]))

    def test_zero_truth_raises(self, rule):
        # alpha <= 0 on every sigma -> no positive-signal fit
        with pytest.raises(ValueError, match="calibration failed"):
            calibrate_pathwise_response_surface(
                rule, np.array([2.5, 2.6, 2.7]), np.array([1.0, 1.0, 1.0]),
                np.array([0.0, 0.0, 0.0]))

    def test_leakage_freedom_lambda_independent_of_oos(self, rule):
        # calibration consumes ONLY the fit arrays: same fit inputs ->
        # identical record regardless of any other data in scope
        rng = np.random.default_rng(9)
        cr = rng.uniform(0.7, 1.8, 200)
        ben = rng.uniform(50.0, 150.0, 200)
        truth = 0.6 * smoothed_relief_response(rule, cr, 0.25) * ben
        rec1 = calibrate_pathwise_response_surface(rule, cr, ben, truth)
        rec2 = calibrate_pathwise_response_surface(
            rule, cr.copy(), ben.copy(), truth.copy())
        assert rec1 == rec2


# ---------------------------------------------------------------------------
# monotonicity
# ---------------------------------------------------------------------------

class TestSurfaceMonotonicity:
    def test_default_rule_monotone(self, rule):
        assert pathwise_surface_monotonicity_check(
            rule, 100.0, 0.25, 0.76, 10.0, 1000.0)

    def test_bad_range_raises(self, rule):
        with pytest.raises(ValueError):
            pathwise_surface_monotonicity_check(
                rule, 100.0, 0.25, 0.76, 100.0, 10.0)

    def test_bad_beta_raises(self, rule):
        with pytest.raises(ValueError):
            pathwise_surface_monotonicity_check(
                rule, 100.0, 0.25, 0.76, 10.0, 1000.0, betas=(1.5,))


# ---------------------------------------------------------------------------
# validation gate semantics (synthetic, fast)
# ---------------------------------------------------------------------------

def _synthetic(rule, n_val=200, n_nested=400, seed=11):
    rng = np.random.default_rng(seed)
    a_ref = rule.reference_assets(100.0)
    val_l = rng.lognormal(np.log(100.0), 0.25, n_val)
    nested_l = rng.lognormal(np.log(100.0), 0.25, n_nested)
    ben_val = 0.8 * val_l
    ben_nested = 0.8 * nested_l
    sigma, alpha = 0.25, 0.75
    surface = {"sigma": sigma, "alpha": alpha, "fit_r2_relieved": 0.99,
               "sigma_interior": True}

    def reld(l, b):
        cr = rule.coverage_ratio(l, a_ref)
        return alpha * smoothed_relief_response(rule, cr, sigma) * b

    return dict(
        rule=rule, fit_mean_liability=100.0, surface=surface,
        kappa_credit=1.1,
        val_truth=val_l, val_pred=val_l.copy(),
        nested_l=nested_l, proxy_l=nested_l.copy(),
        benefit_val=ben_val, benefit_nested=ben_nested,
        benefit_proxy_val=ben_val.copy(),
        benefit_proxy_nested=ben_nested.copy(),
        relieved_truth_val=reld(val_l, ben_val),
        relieved_truth_nested=reld(nested_l, ben_nested),
        confidence_level=0.995, capital_horizon_months=12,
        calibration_leakage_free=True,
    )


class TestValidateGates:
    def test_perfect_proxy_passes_all_gates(self, rule):
        res = validate_pathwise_proxy_basis(**_synthetic(rule))
        assert res["verdict"] == "PASS"
        assert all(res["gates"].values())
        assert res["oos_r2_with_actions_pathwise"] == pytest.approx(1.0)
        assert res["var_rel_error_with_actions"] == pytest.approx(0.0)

    def test_gate_keys_pinned(self, rule):
        res = validate_pathwise_proxy_basis(**_synthetic(rule))
        assert sorted(res["gates"]) == [
            "G1_identical_pathwise_action_basis_truth_and_proxy",
            "G2_oos_r2_with_actions_ge_0p95",
            "G3_var_rel_error_with_actions_le_0p10",
            "G4_monotone_on_pathwise_basis",
            "G5_leakage_free_calibration_and_no_action_above_trigger",
        ]

    def test_noisy_prediction_fails_r2_gate(self, rule):
        kw = _synthetic(rule)
        rng = np.random.default_rng(12)
        kw["val_pred"] = kw["val_truth"] * rng.uniform(0.3, 1.7, len(
            kw["val_truth"]))
        res = validate_pathwise_proxy_basis(**kw)
        assert not res["gates"]["G2_oos_r2_with_actions_ge_0p95"]
        assert res["verdict"] == "FAIL"

    def test_biased_proxy_fails_var_gate(self, rule):
        kw = _synthetic(rule)
        kw["proxy_l"] = kw["nested_l"] * 1.5
        kw["benefit_proxy_nested"] = kw["benefit_nested"] * 1.5
        res = validate_pathwise_proxy_basis(**kw)
        assert not res["gates"]["G3_var_rel_error_with_actions_le_0p10"]
        assert res["verdict"] == "FAIL"

    def test_leakage_flag_fails_g5(self, rule):
        kw = _synthetic(rule)
        kw["calibration_leakage_free"] = False
        res = validate_pathwise_proxy_basis(**kw)
        assert not res["gates"][
            "G5_leakage_free_calibration_and_no_action_above_trigger"]
        assert res["verdict"] == "FAIL"

    def test_negative_alpha_fails_g1(self, rule):
        kw = _synthetic(rule)
        kw["surface"] = dict(kw["surface"], alpha=-0.5)
        res = validate_pathwise_proxy_basis(**kw)
        assert not res["gates"][
            "G1_identical_pathwise_action_basis_truth_and_proxy"]

    def test_with_actions_capital_le_without(self, rule):
        res = validate_pathwise_proxy_basis(**_synthetic(rule))
        assert (res["nested_capital_with_pathwise"]["scr_proxy"]
                <= res["nested_capital_without"]["scr_proxy"] + 1e-9)
        assert (res["proxy_capital_with_pathwise"]["var_liability"]
                <= res["proxy_capital_without"]["var_liability"] + 1e-9)

    def test_optional_sections_passthrough(self, rule):
        kw = _synthetic(rule)
        kw["candidate_comparison"] = {"selected": "b"}
        kw["cadence_sensitivity"] = {"annual_over_monthly_mean_ratio": 1.1}
        res = validate_pathwise_proxy_basis(**kw)
        assert res["candidate_comparison"]["selected"] == "b"
        assert "declaration_cadence_sensitivity" in res

    def test_diagnostics_contract(self, rule):
        res = validate_pathwise_proxy_basis(**_synthetic(rule))
        for sample in ("val_nodes", "nested_nodes"):
            diag = res["relieved_approximation_diagnostics"][sample]
            for k in ("mean_abs_error", "mean_abs_rel_error_active",
                      "active_share_truth", "active_share_estimate", "corr"):
                assert k in diag


# ---------------------------------------------------------------------------
# deterministic expected-path basis (candidate (a) / cadence sensitivity)
# ---------------------------------------------------------------------------

class TestDeterministicBasis:
    def test_non_negative_and_cadence(self, rule, validator):
        cfg = seven_driver_proxy_config()
        X = validator.states(3, cfg.eval_seed)
        offs = validator.fx_term(X) + validator.liquidity_term(X)
        a_ref = rule.reference_assets(120000.0)
        m1 = deterministic_pathwise_relieved(validator, X, rule, a_ref, offs)
        m12 = deterministic_pathwise_relieved(
            validator, X, rule, a_ref, offs, cadence_months=12)
        assert np.all(m1 >= 0.0) and np.all(m12 >= 0.0)

    def test_deterministic_reproducible(self, rule, validator):
        cfg = seven_driver_proxy_config()
        X = validator.states(2, cfg.eval_seed)
        offs = validator.fx_term(X) + validator.liquidity_term(X)
        a_ref = rule.reference_assets(120000.0)
        a = deterministic_pathwise_relieved(validator, X, rule, a_ref, offs)
        b = deterministic_pathwise_relieved(validator, X, rule, a_ref, offs)
        np.testing.assert_array_equal(a, b)

    def test_bad_cadence_raises(self, rule, validator):
        with pytest.raises(ValueError):
            deterministic_pathwise_relieved(
                validator, np.zeros((1, 7)), rule, 1.0, np.zeros(1),
                cadence_months=0)

    def test_misaligned_offsets_raise(self, rule, validator):
        with pytest.raises(ValueError):
            deterministic_pathwise_relieved(
                validator, np.zeros((2, 7)), rule, 1.0, np.zeros(1))


class TestFitSliced:
    def test_bad_n_inner_raises(self, rule, validator):
        with pytest.raises(ValueError):
            pathwise_declaration_fit_sliced(
                validator, np.zeros((1, 7)), 0, 1, 42, 0, rule, 1.0,
                np.zeros(1), np.zeros(1))

    def test_contract_and_consistency(self, rule, validator):
        cfg = seven_driver_proxy_config()
        X = validator.states(2, cfg.fit_seed)
        offs = validator.fx_term(X) + validator.liquidity_term(X)
        a_ref = rule.reference_assets(120000.0)
        out = pathwise_declaration_fit_sliced(
            validator, X, 0, 2, cfg.fit_seed, 2, rule, a_ref, offs,
            np.zeros(2))
        for k in ("total", "benefit", "credit", "relieved_pathwise",
                  "relieved_horizon", "action_share", "restoration_share",
                  "cr_path0_mean"):
            assert k in out and out[k].shape == (2,)
        np.testing.assert_allclose(
            out["total"], out["benefit"] + out["credit"], rtol=1e-12)
        assert np.all(out["relieved_pathwise"] >= 0.0)


# ---------------------------------------------------------------------------
# build-report contract + use restrictions
# ---------------------------------------------------------------------------

class TestReportContract:
    def test_report_exists_and_passes(self):
        rep = json.loads(REPORT.read_text(encoding="utf-8"))
        assert rep["verdict"] == "PASS"
        assert all(rep["result"]["gates"].values())
        assert len(rep["result"]["gates"]) == 5

    def test_report_gates_definition_pre_registered(self):
        rep = json.loads(REPORT.read_text(encoding="utf-8"))
        gd = rep["gates_definition"]
        assert gd["oos_r2_gate"] == 0.95
        assert gd["var_rel_error_gate"] == 0.10
        assert "pre-registered" in gd["source"]

    def test_report_fit_only_calibration_disclosed(self):
        rep = json.loads(REPORT.read_text(encoding="utf-8"))
        sur = rep["result"]["surface_calibration_fit_only"]
        assert sur["sigma_interior"]
        assert sur["alpha"] > 0.0
        assert "candidate_comparison" in rep["result"]
        assert rep["result"]["candidate_comparison"]["selected"] == (
            "b_smoothed_relief_response_surface")

    def test_report_truth_consistency_with_p25t2(self):
        rep = json.loads(REPORT.read_text(encoding="utf-8"))
        assert rep["p25t2_truth_consistency"]["match"]

    def test_report_digest_present(self):
        rep = json.loads(REPORT.read_text(encoding="utf-8"))
        assert len(rep["reproducibility_digest"]) == 64

    def test_card_exists_educational(self):
        text = CARD.read_text(encoding="utf-8")
        assert "EDUCATIONAL" in text

    def test_use_restrictions(self):
        ur = pathwise_proxy_basis_use_restrictions()
        assert ur["classification"] == "EDUCATIONAL_DEMONSTRATION_ONLY"
        assert any("Production" in p for p in ur["prohibited_uses"])
