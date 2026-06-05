"""
Tests for the Phase 18 Task 3 FOUR-driver (rates + equity + credit-spread +
lapse-behaviour) nested / LSMC economic-capital proxy and its out-of-sample
proxy validation.

Modules under test:
  * par_model_v2.stochastic.lapse_behaviour  — OU behavioural (lapse-level) index
  * par_model_v2.projection.multi_driver_capital_4d — 4-driver nested / LSMC
  * par_model_v2.projection.multi_driver_proxy_validation::FourDriverProxyValidator

Coverage:
  * OU lapse-behaviour process: exact-discretisation moments, P=Q drift, M=exp(b)
  * quadrivariate total-degree polynomial basis: ordering, count, capped
    higher-order (>=3-way) interaction terms
  * LapseExposureSpec in-force factor: ~1 at the central point, monotone
    decreasing in the behavioural index and in the rate
  * FourDriverCorrelation: 4x4 matrix structure, lapse orthogonality default,
    Cholesky (incl. nearest-PD fallback)
  * four-driver inner valuation: shape, lapse sensitivity (low lapse -> higher
    liability), reproducibility
  * correlated outer states: shape + realised financial-block correlation signs
    + lapse near-orthogonality
  * FourDriverNestedEngine / FourDriverLSMCProxyEngine: capital ordering,
    fit/predict, input validation
  * FourDriverProxyValidator: disjoint-seed OOS validation runs, leakage-free,
    honest verdict string, reproducibility digest stability
  * governance: model-use restriction structure + JSON round-trip

Sizes are kept modest so each pytest invocation stays inside the sandbox time
budget.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.stochastic.esg_process import Measure, _antithetic_normals
from par_model_v2.stochastic.lapse_behaviour import (
    DEFAULT_LAPSE_KAPPA,
    DEFAULT_LAPSE_SIGMA,
    LapseBehaviourParams,
    LapseBehaviourProcess,
    default_lapse_behaviour,
)
from par_model_v2.projection.multi_driver_capital_4d import (
    DEFAULT_QUAD_LSMC_DEGREE,
    DEFAULT_MAX_INTERACTION_ORDER_4D,
    LapseExposureSpec,
    FourDriverCorrelation,
    FourDriverNestedEngine,
    FourDriverNestedResult,
    FourDriverLSMCProxyEngine,
    FourDriverLSMCResult,
    FourDriverDiagnostics,
    four_driver_use_restrictions,
    four_driver_use_restrictions_json,
    _inner_pathwise_pvs_4d,
    _outer_states_4d,
    _quad_poly_basis,
    _quad_poly_powers,
    _n_quad_basis_terms,
)
from par_model_v2.projection.multi_driver_proxy_validation import (
    DEFAULT_QUAD_BASIS_GRID,
    QuadProxyValidationConfig,
    QuadProxyValidationReport,
    FourDriverProxyValidator,
    quad_proxy_validation_use_restrictions,
    quad_proxy_validation_use_restrictions_json,
)


def _product():
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


# ---------------------------------------------------------------------------
# OU lapse-behaviour process
# ---------------------------------------------------------------------------

def test_lapse_params_validation():
    with pytest.raises(ValueError):
        LapseBehaviourParams(mean_reversion_speed=0.0)
    with pytest.raises(ValueError):
        LapseBehaviourParams(behaviour_vol=-0.1)
    p = LapseBehaviourParams()
    assert p.mean_reversion_speed == DEFAULT_LAPSE_KAPPA
    assert p.behaviour_vol == DEFAULT_LAPSE_SIGMA
    assert default_lapse_behaviour().initial_index == 0.0


def test_lapse_process_exact_moments():
    p = LapseBehaviourParams()
    proc = LapseBehaviourProcess(p)
    rng = np.random.default_rng(0)
    z = _antithetic_normals(rng, 20000, 12)
    paths = proc._simulate_array(20000, 12, Measure.P, z)
    assert paths.shape == (20000, 13)
    np.testing.assert_allclose(paths[:, 0], 0.0)
    bH = paths[:, 12]
    # antithetic mean ~ 0
    assert abs(float(bH.mean())) < 0.01
    # variance below the stationary bound and positive
    assert 0.0 < float(bH.std()) < p.stationary_std + 1e-6


def test_lapse_process_measure_invariance():
    """Behaviour is non-financial: P and Q paths are identical for the same shocks."""
    proc = LapseBehaviourProcess()
    rng = np.random.default_rng(1)
    z = _antithetic_normals(rng, 100, 12)
    pp = proc._simulate_array(100, 12, Measure.P, z)
    qp = proc._simulate_array(100, 12, Measure.Q, z)
    np.testing.assert_allclose(pp, qp)


def test_lapse_multiplier_lognormal():
    assert LapseBehaviourProcess.multiplier(0.0) == pytest.approx(1.0)
    assert float(LapseBehaviourProcess.multiplier(0.5)) > 1.0
    assert float(LapseBehaviourProcess.multiplier(-0.5)) < 1.0


# ---------------------------------------------------------------------------
# Quadrivariate basis
# ---------------------------------------------------------------------------

def test_quad_basis_count_and_constant_first():
    powers = _quad_poly_powers(1)
    # degree 1: constant + 4 linear = 5
    assert len(powers) == 5
    assert powers[0] == (0, 0, 0, 0)
    assert _n_quad_basis_terms(2) == 15


def test_quad_basis_caps_higher_order_interactions():
    # at degree 3 with max_interaction_order 3, only the four 3-way terms with
    # total order 3 are admitted; no 4-way term (needs total >= 4).
    powers = _quad_poly_powers(3, max_interaction_order=3)
    four_way = [p for p in powers if all(e >= 1 for e in p)]
    assert four_way == []  # 4-way needs total >= 4 > cap
    # lowering the cap removes 3-way terms entirely
    p_cap1 = _quad_poly_powers(3, max_interaction_order=1)
    three_way = [p for p in p_cap1 if sum(1 for e in p if e >= 1) >= 3]
    assert three_way == []
    assert _n_quad_basis_terms(3, 3) >= _n_quad_basis_terms(3, 2)


def test_quad_basis_design_matrix_shape_and_constant_column():
    X = np.random.default_rng(0).normal(size=(7, 4))
    D = _quad_poly_basis(X, 2)
    assert D.shape == (7, _n_quad_basis_terms(2))
    np.testing.assert_allclose(D[:, 0], 1.0)  # constant term
    with pytest.raises(ValueError):
        _quad_poly_basis(np.zeros((3, 3)), 2)  # wrong dimension


# ---------------------------------------------------------------------------
# LapseExposureSpec in-force factor
# ---------------------------------------------------------------------------

def test_inforce_factor_monotone_in_lapse_and_rate():
    le = LapseExposureSpec(credited_rate=0.025)
    H, T = 12, _product().term_months
    if_central = le.inforce_factor(0.025, 0.0, H, T)
    if_low = le.inforce_factor(0.025, -0.5, H, T)   # low lapse
    if_high = le.inforce_factor(0.025, 0.5, H, T)    # high lapse
    assert if_low > if_central > if_high            # decreasing in behaviour index
    if_high_rate = le.inforce_factor(0.06, 0.0, H, T)
    assert if_high_rate < if_central                 # higher rate -> more lapse
    # all in-force factors are positive and bounded
    for v in (if_central, if_low, if_high, if_high_rate):
        assert 0.0 < v < 3.0


def test_lapse_exposure_cap_validation():
    with pytest.raises(ValueError):
        LapseExposureSpec(lapse_cap=0.0)
    with pytest.raises(ValueError):
        LapseExposureSpec(lapse_cap=1.5)


# ---------------------------------------------------------------------------
# FourDriverCorrelation
# ---------------------------------------------------------------------------

def test_four_corr_matrix_structure_and_lapse_orthogonality():
    corr = FourDriverCorrelation()
    C = corr.matrix(gbm_rate_equity=-0.15)
    assert C.shape == (4, 4)
    np.testing.assert_allclose(np.diag(C), 1.0)
    np.testing.assert_allclose(C, C.T)
    # default lapse block is orthogonal to the financial drivers
    np.testing.assert_allclose(C[3, :3], 0.0)
    # financial 3x3 block carries the governed spread couplings (negative)
    assert C[0, 2] < 0 and C[1, 2] < 0


def test_four_corr_cholesky_reconstructs_matrix():
    corr = FourDriverCorrelation(lapse_rate=0.1, lapse_equity=-0.05, lapse_spread=0.2)
    L = corr.cholesky(-0.15)
    C = corr.matrix(-0.15)
    np.testing.assert_allclose(L @ L.T, C, atol=1e-8)


def test_four_corr_validation():
    with pytest.raises(ValueError):
        FourDriverCorrelation(lapse_rate=1.5)


# ---------------------------------------------------------------------------
# Four-driver inner valuation + outer states
# ---------------------------------------------------------------------------

def test_inner_pvs_shape_and_lapse_sensitivity():
    prod = _product()
    corr = FourDriverCorrelation()
    common = dict(
        n_inner=256, rem_months=prod.term_months - 12, product=prod,
        base_hw_params=None, gbm_params=None, spread_params=None,
        correlation=corr, h_month=12, seed=7,
        equity_guarantee=EquityGuaranteeSpec(), credit_exposure=None,
        lapse_exposure=LapseExposureSpec(),
    )
    # fill the None defaults via the engine's own defaults
    from par_model_v2.stochastic.esg_process import HullWhiteParams, GBMParams
    from par_model_v2.stochastic.credit_spread import CreditSpreadParams
    from par_model_v2.projection.multi_driver_capital_3d import CreditExposureSpec
    common.update(base_hw_params=HullWhiteParams(), gbm_params=GBMParams(),
                  spread_params=CreditSpreadParams(), credit_exposure=CreditExposureSpec())
    pv_low = _inner_pathwise_pvs_4d(0.025, 100.0, 0.015, -0.5, **common)
    pv_high = _inner_pathwise_pvs_4d(0.025, 100.0, 0.015, 0.5, **common)
    assert pv_low.shape == (256,)
    # low lapse retains more in-force benefits -> higher mean liability
    assert float(pv_low.mean()) > float(pv_high.mean())


def test_outer_states_shape_and_correlation_signs():
    prod = _product()
    from par_model_v2.stochastic.esg_process import HullWhiteParams, GBMParams
    from par_model_v2.stochastic.credit_spread import CreditSpreadParams
    X = _outer_states_4d(
        4000, 12, Measure.P, HullWhiteParams(), GBMParams(), CreditSpreadParams(),
        LapseBehaviourParams(), FourDriverCorrelation(), None, 42,
    )
    assert X.shape == (4000, 4)
    C = np.corrcoef(X.T)
    # governed financial couplings (rate-spread, equity-spread negative)
    assert C[0, 2] < 0.0 and C[1, 2] < 0.0
    # lapse driver ~ orthogonal to the financial drivers (default zero corr)
    assert abs(C[0, 3]) < 0.12 and abs(C[1, 3]) < 0.12 and abs(C[2, 3]) < 0.12


def test_inner_pvs_reproducible():
    prod = _product()
    from par_model_v2.stochastic.esg_process import HullWhiteParams, GBMParams
    from par_model_v2.stochastic.credit_spread import CreditSpreadParams
    from par_model_v2.projection.multi_driver_capital_3d import CreditExposureSpec
    kw = dict(
        n_inner=128, rem_months=prod.term_months - 12, product=prod,
        base_hw_params=HullWhiteParams(), gbm_params=GBMParams(),
        spread_params=CreditSpreadParams(), correlation=FourDriverCorrelation(),
        h_month=12, seed=99, equity_guarantee=EquityGuaranteeSpec(),
        credit_exposure=CreditExposureSpec(), lapse_exposure=LapseExposureSpec(),
    )
    a = _inner_pathwise_pvs_4d(0.02, 95.0, 0.02, 0.1, **kw)
    b = _inner_pathwise_pvs_4d(0.02, 95.0, 0.02, 0.1, **kw)
    np.testing.assert_allclose(a, b)


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------

def test_nested_engine_runs_and_orders_capital():
    eng = FourDriverNestedEngine(_product(), capital_horizon_months=12)
    res = eng.run(n_outer=200, n_inner=48, seed=42)
    assert isinstance(res, FourDriverNestedResult)
    cap = res.capital
    assert cap.es_liability >= cap.var_liability
    assert res.outer_states.shape == (200, 4)
    s = res.summary()
    assert s["drivers"] == ["short_rate", "equity_level", "credit_spread", "lapse_behaviour"]


def test_nested_engine_horizon_validation():
    with pytest.raises(ValueError):
        FourDriverNestedEngine(_product(), capital_horizon_months=0)
    with pytest.raises(ValueError):
        FourDriverNestedEngine(_product(), capital_horizon_months=12, confidence_level=1.2)


def test_lsmc_engine_fit_predict_and_degree_validation():
    eng = FourDriverLSMCProxyEngine(_product(), capital_horizon_months=12, degree=2)
    res = eng.fit_and_run(n_fit=300, n_outer_eval=1500, seed=42)
    assert isinstance(res, FourDriverLSMCResult)
    assert len(res.powers) == _n_quad_basis_terms(2)
    # predict on its own fit states returns finite values of the right length
    pred = res.predict(res.fit_states[:10])
    assert pred.shape == (10,) and np.all(np.isfinite(pred))
    with pytest.raises(ValueError):
        FourDriverLSMCProxyEngine(_product(), capital_horizon_months=12, degree=0)


def test_diagnostics_grid_agreement():
    eng = FourDriverLSMCProxyEngine(_product(), capital_horizon_months=12, degree=2)
    res = eng.fit_and_run(n_fit=300, n_outer_eval=1500, seed=42)
    diag = FourDriverDiagnostics(_product(), capital_horizon_months=12)
    agree = diag.proxy_vs_nested(res, grid_per_dim=2, n_inner=512, seed=11)
    assert agree.grid_states.shape == (16, 4)
    # the proxy explains the bulk of cross-grid variation
    assert agree.r2_vs_nested > 0.5
    d = FourDriverDiagnostics.reproducibility_digest(res.fitted_liabilities)
    assert isinstance(d, str) and len(d) == 64


# ---------------------------------------------------------------------------
# OOS proxy validator
# ---------------------------------------------------------------------------

def test_quad_config_validation():
    with pytest.raises(ValueError):
        QuadProxyValidationConfig(fit_seed=42, validation_seed=42)
    with pytest.raises(ValueError):
        QuadProxyValidationConfig(n_validation=4)
    cfg = QuadProxyValidationConfig()
    assert cfg.basis_grid == DEFAULT_QUAD_BASIS_GRID


def test_four_driver_validator_runs_leakage_free_and_verdicts():
    v = FourDriverProxyValidator(_product(), capital_horizon_months=12)
    cfg = QuadProxyValidationConfig(
        n_fit=240, n_validation=24, n_insample_heavy=20, n_inner_heavy=160,
        basis_grid=((1, 3), (2, 3), (3, 3)),
    )
    rep = v.validate(cfg, nested_n_outer=200, nested_n_inner=48)
    assert isinstance(rep, QuadProxyValidationReport)
    assert rep.leakage.leakage_free
    assert rep.leakage.n_exact_shared_states == 0
    assert rep.verdict.startswith("PASS") or rep.verdict.startswith("PARTIAL")
    # selected basis is one of the swept grid
    assert (rep.selected_degree, rep.selected_max_interaction_order) in cfg.basis_grid
    # report serialises and names all four drivers
    d = rep.to_dict()
    assert d["drivers"][-1] == "lapse_behaviour"
    json.loads(rep.to_json())


def test_four_driver_validator_reproducible_digest():
    cfg = QuadProxyValidationConfig(
        n_fit=200, n_validation=20, n_insample_heavy=16, n_inner_heavy=128,
        basis_grid=((1, 3), (2, 3)),
    )
    r1 = FourDriverProxyValidator(_product(), capital_horizon_months=12).validate(
        cfg, nested_n_outer=160, nested_n_inner=48)
    r2 = FourDriverProxyValidator(_product(), capital_horizon_months=12).validate(
        cfg, nested_n_outer=160, nested_n_inner=48)
    assert r1.reproducibility_digest == r2.reproducibility_digest


# ---------------------------------------------------------------------------
# Governance / model-use restrictions
# ---------------------------------------------------------------------------

def test_four_driver_use_restrictions_structure():
    r = four_driver_use_restrictions()
    assert "EDUCATIONAL" in r["classification"]
    assert "lapse" in r["risk_drivers"].lower()
    assert any("ASOP 7" in s for s in r["standards"])
    json.loads(four_driver_use_restrictions_json())


def test_quad_proxy_validation_use_restrictions_structure():
    r = quad_proxy_validation_use_restrictions()
    assert "four-driver" in r["classification"].lower()
    assert "lapse" in r["what_it_validates"].lower()
    json.loads(quad_proxy_validation_use_restrictions_json())
