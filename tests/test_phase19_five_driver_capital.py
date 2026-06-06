"""
Tests for the Phase 19 Task 3 FIVE-driver (rates + equity + credit-spread +
lapse-behaviour + mortality-trend) nested / LSMC economic-capital proxy and its
out-of-sample proxy validation.

Modules under test:
  * par_model_v2.stochastic.mortality_trend       — OU mortality-trend index
  * par_model_v2.projection.multi_driver_capital_5d — 5-driver nested / LSMC
  * par_model_v2.projection.multi_driver_proxy_validation::FiveDriverProxyValidator

Coverage:
  * OU mortality-trend process: exact-discretisation moments, P=Q drift, G=exp(m)
  * quintivariate total-degree polynomial basis: ordering, count, capped
    higher-order (>=3-way) interaction terms
  * MortalityExposureSpec: multiplier ~1 at the central point; scaled q_x rises
    with the mortality-trend index; nested liability monotone in m
  * FiveDriverCorrelation: 5x5 matrix structure, mortality orthogonality default,
    Cholesky (incl. nearest-PD fallback)
  * five-driver inner valuation: shape, mortality sensitivity, reproducibility
  * correlated outer states: shape + mortality near-orthogonality
  * FiveDriverNestedEngine / FiveDriverLSMCProxyEngine: fit/predict, validation
  * FiveDriverProxyValidator: disjoint-seed OOS validation, leakage-free, honest
    verdict, reproducibility digest stability
  * governance: model-use restriction structure + JSON round-trip

Sizes are kept modest so each pytest invocation stays inside the sandbox budget.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import (
    ParEndowmentProduct,
    _base_annual_qx,
)
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.stochastic.esg_process import Measure, _antithetic_normals
from par_model_v2.stochastic.mortality_trend import (
    DEFAULT_MORTALITY_KAPPA,
    DEFAULT_MORTALITY_SIGMA,
    MortalityTrendParams,
    MortalityTrendProcess,
    default_mortality_trend,
)
from par_model_v2.projection.multi_driver_capital_5d import (
    DEFAULT_QUINT_LSMC_DEGREE,
    DEFAULT_MAX_INTERACTION_ORDER_5D,
    MortalityExposureSpec,
    FiveDriverCorrelation,
    FiveDriverNestedEngine,
    FiveDriverNestedResult,
    FiveDriverLSMCProxyEngine,
    FiveDriverLSMCResult,
    FiveDriverDiagnostics,
    five_driver_use_restrictions,
    five_driver_use_restrictions_json,
    _inner_pathwise_pvs_5d,
    _outer_states_5d,
    _quint_poly_basis,
    _quint_poly_powers,
    _n_quint_basis_terms,
)
from par_model_v2.projection.multi_driver_proxy_validation import (
    DEFAULT_QUINT_BASIS_GRID,
    QuintProxyValidationConfig,
    QuintProxyValidationReport,
    FiveDriverProxyValidator,
    quint_proxy_validation_use_restrictions,
    quint_proxy_validation_use_restrictions_json,
)


def _product():
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


# ---------------------------------------------------------------------------
# OU mortality-trend process
# ---------------------------------------------------------------------------

def test_mortality_params_validation():
    with pytest.raises(ValueError):
        MortalityTrendParams(mean_reversion_speed=0.0)
    with pytest.raises(ValueError):
        MortalityTrendParams(trend_vol=-0.1)
    p = MortalityTrendParams()
    assert p.mean_reversion_speed == DEFAULT_MORTALITY_KAPPA
    assert p.trend_vol == DEFAULT_MORTALITY_SIGMA
    assert default_mortality_trend().initial_index == 0.0


def test_mortality_stationary_std_and_to_dict():
    p = MortalityTrendParams(mean_reversion_speed=0.30, trend_vol=0.15)
    expected = 0.15 / np.sqrt(2.0 * 0.30)
    assert p.stationary_std == pytest.approx(expected, rel=1e-9)
    d = p.to_dict()
    assert d["mean_reversion_speed"] == 0.30
    assert "methodology" in d and "standard_references" in d


def test_mortality_process_shape_and_initial():
    proc = MortalityTrendProcess()
    rng = np.random.default_rng(1)
    shocks = rng.standard_normal((6, 24))
    paths = proc._simulate_array(6, 24, Measure.P, shocks)
    assert paths.shape == (6, 25)
    assert np.allclose(paths[:, 0], 0.0)


def test_mortality_process_p_equals_q():
    """Mortality trend is non-financial: identical dynamics under P and Q."""
    proc = MortalityTrendProcess()
    rng = np.random.default_rng(7)
    shocks = rng.standard_normal((50, 12))
    p_paths = proc._simulate_array(50, 12, Measure.P, shocks.copy())
    q_paths = proc._simulate_array(50, 12, Measure.Q, shocks.copy())
    assert np.allclose(p_paths, q_paths)


def test_mortality_process_stationary_moment():
    """Exact AR(1): long-horizon variance approaches sigma^2/(2 kappa)."""
    p = MortalityTrendParams(mean_reversion_speed=0.8, trend_vol=0.25)
    proc = MortalityTrendProcess(p)
    rng = np.random.default_rng(2024)
    n, T = 20000, 240
    shocks = rng.standard_normal((n, T))
    paths = proc._simulate_array(n, T, Measure.P, shocks)
    realized = paths[:, -1].std()
    assert realized == pytest.approx(p.stationary_std, rel=0.06)


def test_mortality_multiplier():
    proc = MortalityTrendProcess()
    assert float(proc.multiplier(0.0)) == pytest.approx(1.0)
    assert float(proc.multiplier(0.2)) == pytest.approx(np.exp(0.2))
    vec = proc.multiplier(np.array([-0.1, 0.0, 0.1]))
    assert vec.shape == (3,)
    assert vec[0] < vec[1] < vec[2]


# ---------------------------------------------------------------------------
# Quintivariate polynomial basis
# ---------------------------------------------------------------------------

def test_quint_poly_powers_count_and_cap():
    # degree 1: constant + 5 linear = 6 terms (independent of interaction cap)
    assert _n_quint_basis_terms(1, 3) == 6
    # capping higher-order (>=3-way) terms must not exceed the uncapped count
    capped = _n_quint_basis_terms(3, 2)
    uncapped = _n_quint_basis_terms(3, 99)
    assert capped < uncapped
    # every admitted >=3-way interaction respects the cap
    powers = _quint_poly_powers(3, 2)
    for tup in powers:
        nz = sum(1 for e in tup if e >= 1)
        if nz >= 3:
            assert sum(tup) <= 2


def test_quint_poly_basis_shape_and_constant():
    X = np.random.default_rng(0).standard_normal((7, 5))
    design = _quint_poly_basis(X, 2, 3)
    assert design.shape[0] == 7
    assert design.shape[1] == _n_quint_basis_terms(2, 3)
    # first column is the constant term
    assert np.allclose(design[:, 0], 1.0)


def test_quint_poly_basis_rejects_wrong_dim():
    with pytest.raises(ValueError):
        _quint_poly_basis(np.zeros((4, 4)), 2, 3)


# ---------------------------------------------------------------------------
# MortalityExposureSpec
# ---------------------------------------------------------------------------

def test_mortality_exposure_validation():
    with pytest.raises(ValueError):
        MortalityExposureSpec(trend_sensitivity=0.0)
    with pytest.raises(ValueError):
        MortalityExposureSpec(qx_cap=1.5)


def test_mortality_exposure_multiplier_and_scaled_qx():
    spec = MortalityExposureSpec()
    assert spec.multiplier(0.0) == pytest.approx(1.0)
    # scaled q_x at m=0 reproduces the base q_x
    fn0 = spec.scaled_qx_fn(0.0)
    assert fn0(50, "M") == pytest.approx(_base_annual_qx(50, "M"))
    # positive m raises q_x; negative lowers it; cap respected
    fn_hi = spec.scaled_qx_fn(0.3)
    fn_lo = spec.scaled_qx_fn(-0.3)
    assert fn_hi(50, "M") > _base_annual_qx(50, "M") > fn_lo(50, "M")
    assert fn_hi(50, "M") <= spec.qx_cap


# ---------------------------------------------------------------------------
# FiveDriverCorrelation
# ---------------------------------------------------------------------------

def test_five_driver_correlation_matrix_structure():
    corr = FiveDriverCorrelation()
    C = corr.matrix(gbm_rate_equity=-0.2)
    assert C.shape == (5, 5)
    assert np.allclose(C, C.T)
    assert np.allclose(np.diag(C), 1.0)
    # mortality orthogonal by default
    assert np.allclose(C[4, :4], 0.0)


def test_five_driver_correlation_cholesky_psd_fallback():
    # extreme couplings that may break naive PD -> nearest-PD fallback must work
    corr = FiveDriverCorrelation(
        mortality_rate=0.9, mortality_equity=-0.9,
        mortality_spread=0.9, mortality_lapse=-0.9,
    )
    L = corr.cholesky(gbm_rate_equity=-0.3)
    assert L.shape == (5, 5)
    assert np.all(np.isfinite(L))


def test_five_driver_correlation_rejects_bad_value():
    with pytest.raises(ValueError):
        FiveDriverCorrelation(mortality_rate=1.5)


# ---------------------------------------------------------------------------
# Five-driver inner valuation + outer states
# ---------------------------------------------------------------------------

def test_inner_pvs_5d_shape_and_reproducible():
    prod = _product()
    diag = FiveDriverDiagnostics(prod, capital_horizon_months=12)
    a = diag.nested_liability(0.025, 1.0, 0.011, 0.0, 0.0, n_inner=256, seed=5)
    b = diag.nested_liability(0.025, 1.0, 0.011, 0.0, 0.0, n_inner=256, seed=5)
    assert a == pytest.approx(b)  # same seed -> identical


def test_nested_liability_monotone_in_mortality():
    """Higher mortality-trend index -> higher guaranteed liability (timing)."""
    prod = _product()
    diag = FiveDriverDiagnostics(prod, capital_horizon_months=12)
    lo = diag.nested_liability(0.025, 1.0, 0.011, 0.0, -0.3, n_inner=2048, seed=7)
    mid = diag.nested_liability(0.025, 1.0, 0.011, 0.0, 0.0, n_inner=2048, seed=7)
    hi = diag.nested_liability(0.025, 1.0, 0.011, 0.0, 0.3, n_inner=2048, seed=7)
    assert lo < mid < hi


def test_outer_states_5d_shape_and_mortality_orthogonal():
    prod = _product()
    nest = FiveDriverNestedEngine(prod, capital_horizon_months=12)
    states = _outer_states_5d(
        400, 12, Measure.P, nest.hw_params, nest.gbm_params, nest.spread_params,
        nest.lapse_params, nest.mortality_params, nest.correlation, None, 42,
    )
    assert states.shape == (400, 5)
    # default mortality is orthogonal: realised corr with each financial col ~0
    m = states[:, 4]
    for j in range(4):
        c = np.corrcoef(states[:, j], m)[0, 1]
        assert abs(c) < 0.2


# ---------------------------------------------------------------------------
# Nested + LSMC engines
# ---------------------------------------------------------------------------

def test_five_driver_nested_engine_runs():
    prod = _product()
    nest = FiveDriverNestedEngine(prod, capital_horizon_months=12)
    res = nest.run(n_outer=120, n_inner=48, seed=42)
    assert isinstance(res, FiveDriverNestedResult)
    assert res.n_outer == 120
    assert res.capital.var_liability > 0.0
    assert res.capital.es_liability >= res.capital.var_liability
    assert "mortality_trend" in res.summary()["drivers"]


def test_five_driver_lsmc_fit_and_agreement():
    prod = _product()
    ls = FiveDriverLSMCProxyEngine(
        prod, capital_horizon_months=12, degree=1, max_interaction_order=3
    )
    lr = ls.fit_and_run(n_fit=400, n_outer_eval=2000, seed=42)
    assert isinstance(lr, FiveDriverLSMCResult)
    assert lr.centers.shape == (5,)
    assert len(lr.powers) == _n_quint_basis_terms(1, 3)
    diag = FiveDriverDiagnostics(prod, capital_horizon_months=12)
    agree = diag.proxy_vs_nested(lr, grid_per_dim=2, n_inner=512)
    assert agree.grid_states.shape == (32, 5)
    assert agree.r2_vs_nested > 0.9


def test_five_driver_lsmc_input_validation():
    prod = _product()
    with pytest.raises(ValueError):
        FiveDriverLSMCProxyEngine(prod, capital_horizon_months=12, degree=0)
    with pytest.raises(ValueError):
        FiveDriverNestedEngine(prod, capital_horizon_months=0)


# ---------------------------------------------------------------------------
# OOS proxy validator
# ---------------------------------------------------------------------------

def test_quint_config_validation():
    with pytest.raises(ValueError):
        QuintProxyValidationConfig(fit_seed=1, validation_seed=1)
    with pytest.raises(ValueError):
        QuintProxyValidationConfig(n_validation=2)
    cfg = QuintProxyValidationConfig()
    assert cfg.basis_grid == DEFAULT_QUINT_BASIS_GRID


def test_five_driver_proxy_validator_verdict_and_leakage():
    prod = _product()
    v = FiveDriverProxyValidator(prod, capital_horizon_months=12)
    cfg = QuintProxyValidationConfig(
        n_fit=300, n_validation=40, n_insample_heavy=30, n_inner_heavy=256,
        basis_grid=((1, 3), (2, 3), (3, 3)),
    )
    rep = v.validate(config=cfg, nested_n_outer=300, nested_n_inner=64)
    assert isinstance(rep, QuintProxyValidationReport)
    assert rep.leakage.leakage_free
    assert rep.verdict.startswith("PASS") or rep.verdict.startswith("PARTIAL")
    sr = rep.selected_row()
    assert sr.oos_r2 > 0.85
    # report round-trips through JSON
    d = json.loads(rep.to_json())
    assert d["drivers"][-1] == "mortality_trend"
    assert len(d["basis_rows"]) == 3


def test_five_driver_proxy_validator_digest_stable():
    prod = _product()
    v = FiveDriverProxyValidator(prod, capital_horizon_months=12)
    cfg = QuintProxyValidationConfig(
        n_fit=200, n_validation=30, n_insample_heavy=20, n_inner_heavy=192,
        basis_grid=((1, 3), (2, 3)),
    )
    r1 = v.validate(config=cfg, nested_n_outer=200, nested_n_inner=48)
    r2 = v.validate(config=cfg, nested_n_outer=200, nested_n_inner=48)
    assert r1.reproducibility_digest == r2.reproducibility_digest


# ---------------------------------------------------------------------------
# Governance / model-use restrictions
# ---------------------------------------------------------------------------

def test_five_driver_use_restrictions_structure():
    r = five_driver_use_restrictions()
    assert "EDUCATIONAL" in r["classification"]
    assert "mortality" in r["risk_drivers"].lower()
    json.loads(five_driver_use_restrictions_json())  # valid JSON


def test_quint_proxy_use_restrictions_structure():
    r = quint_proxy_validation_use_restrictions()
    assert "FiveDriverProxyValidator" in r["module"]
    json.loads(quint_proxy_validation_use_restrictions_json())  # valid JSON
