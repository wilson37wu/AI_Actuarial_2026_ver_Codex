"""Phase 22 Task 2 tests - seven-driver proxy OOS validation."""

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_7d import (
    SeptProxyValidationConfig,
    SevenDriverLiquidityProxyValidator,
    seven_driver_proxy_config,
    seven_driver_proxy_use_restrictions,
)
from par_model_v2.projection.multi_driver_proxy_validation_6d_remediation import (
    REMEDIATED_FIT_N_INNER,
    REMEDIATED_N_FIT,
    REMEDIATED_NESTED_N_INNER,
)
from par_model_v2.projection.multi_driver_capital_6d_fx import (
    SixDriverFXRiskAggregator,
)
from par_model_v2.projection.multi_driver_capital_7d_aggregation import (
    SevenDriverLiquidityRiskAggregator,
)
from par_model_v2.stochastic.esg_process import Measure


REPORT = Path("docs/validation/PHASE22_TASK2_7D_PROXY_VALIDATION_REPORT.json")


@pytest.fixture(scope="module")
def product():
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


@pytest.fixture(scope="module")
def validator(product):
    return SevenDriverLiquidityProxyValidator(product)


def _smooth_l5(states7):
    x = np.asarray(states7, dtype=float)
    return (
        100000.0
        + 850000.0 * x[:, 0]
        + 0.35 * x[:, 1]
        + 120000.0 * x[:, 2]
        + 20000.0 * x[:, 3]
        + 10000.0 * x[:, 4]
        + 2.0e7 * x[:, 0] ** 2
    )


def test_config_defaults_inherit_phase22_remediation_sizing():
    cfg = seven_driver_proxy_config()
    assert cfg.n_fit == REMEDIATED_N_FIT
    assert cfg.fit_n_inner == REMEDIATED_FIT_N_INNER
    assert cfg.nested_n_inner == REMEDIATED_NESTED_N_INNER
    assert cfg.validation_seed != cfg.fit_seed


def test_states_7d_preserve_first_six_driver_crn(product):
    a7 = SevenDriverLiquidityRiskAggregator(product)
    a6 = SixDriverFXRiskAggregator(product)
    s7 = a7._outer_states_7d(32, 12, Measure.P, 42)
    s6 = a6._outer_states_6d(32, 12, Measure.P, 42)
    assert s7.shape == (32, 7)
    np.testing.assert_array_equal(s7[:, :6], s6)


def test_liquidity_term_is_exact_and_baseline_centred(validator):
    states = validator.states(20, 123)
    tau = validator.agg._liquidity_tau_years(12)
    direct = validator.agg.liquidity_exposure.liability_impact(
        states[:, 6], validator.agg.liquidity_params, tau
    )
    np.testing.assert_allclose(validator.liquidity_term(states), direct)
    base = np.array([states[0].copy()])
    base[0, 6] = validator.agg.liquidity_params.initial_premium
    assert float(validator.liquidity_term(base)[0]) == pytest.approx(0.0, abs=1e-10)


def test_validate_with_precomputed_smooth_targets_passes(validator):
    cfg = SeptProxyValidationConfig(
        n_fit=120,
        n_validation=24,
        n_insample_heavy=24,
        n_eval=120,
        n_inner_heavy=2,
        nested_n_inner=2,
        fit_n_inner=1,
        basis_grid=((1, 3), (2, 3)),
        fx_modes=("analytic",),
    )
    fit_X = validator.states(cfg.n_fit, cfg.fit_seed)
    val_X = validator.states(cfg.n_validation, cfg.validation_seed)
    in_X = fit_X[: cfg.n_insample_heavy]
    eval_X = validator.states(cfg.n_eval, cfg.eval_seed)
    rep = validator.validate(
        cfg,
        precomputed={
            "fit_y5": _smooth_l5(fit_X),
            "val_truth5": _smooth_l5(val_X),
            "insample_truth5": _smooth_l5(in_X),
            "nested_l5": _smooth_l5(eval_X),
        },
    )
    d = rep.to_dict()
    assert d["verdict"].startswith("PASS")
    assert d["drivers"][-1] == "liquidity_premium"
    assert d["selected_row"]["oos_r2"] > 0.99
    assert d["capital_comparison"]["var_rel_error"] < 1e-8
    assert d["liquidity_axis_evidence"]["max_abs_offset_error"] == pytest.approx(0.0)
    assert d["leakage"]["leakage_free"] is True


def test_validate_rejects_wrong_precomputed_length(validator):
    cfg = SeptProxyValidationConfig(
        n_fit=20,
        n_validation=8,
        n_insample_heavy=8,
        n_eval=20,
        n_inner_heavy=1,
        nested_n_inner=1,
        fit_n_inner=1,
        basis_grid=((1, 3),),
    )
    with pytest.raises(ValueError, match="fit_y5"):
        validator.validate(cfg, precomputed={"fit_y5": np.zeros(3)})


@pytest.mark.skipif(not REPORT.exists(), reason="evidence report not built")
def test_saved_phase22_task2_report_gate():
    rep = json.loads(REPORT.read_text())["validation"]
    assert rep["verdict"].startswith("PASS")
    assert rep["selected_row"]["oos_r2"] >= 0.95
    assert rep["capital_comparison"]["var_rel_error"] <= 0.10
    assert rep["capital_comparison"]["es_rel_error"] <= 0.10
    assert rep["capital_comparison"]["scr_rel_error"] <= 0.10
    assert rep["liquidity_axis_evidence"]["max_abs_offset_error"] <= 1e-9


def test_use_restrictions_disclose_liquidity_placeholder():
    r = seven_driver_proxy_use_restrictions()
    assert r["model"] == "SevenDriverLiquidityProxyValidator"
    assert "EDUCATIONAL" in r["status"]
    assert "liquidity" in r["residual_risk"].lower()
