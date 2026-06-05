"""
Tests for the Phase 17 Task 1 three-driver (rates + equity + credit-spread)
nested / LSMC economic-capital proxy
(``par_model_v2.projection.multi_driver_capital_3d``).

Coverage:
  * trivariate total-degree polynomial basis: ordering, count, capped 3-way
    interaction terms (cap bites at degree >= 4)
  * CreditExposureSpec / ThreeDriverCorrelation validation + Cholesky (incl.
    nearest-PD fallback)
  * three-driver inner valuation: shape, spread sensitivity, the
    credit-exposure-off reduction (credit component drops out)
  * correlated outer states: shape + realised (r,s)/(S,s) correlation signs
  * measure handling (outer P, inner Q)
  * reproducibility (seed-determinism digest)
  * ThreeDriverNestedEngine: capital-metric ordering, input validation
  * ThreeDriverLSMCProxyEngine: fit/predict, degree validation, proxy-vs-nested
  * ThreeDriverDiagnostics: 3-D grid agreement R^2
  * governance: model-use restrictions structure + JSON round-trip

Sizes are kept modest so each pytest invocation stays inside the sandbox time
budget.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_capital_3d import (
    DEFAULT_TRI_LSMC_DEGREE,
    DEFAULT_MAX_INTERACTION_ORDER,
    CreditExposureSpec,
    ThreeDriverCorrelation,
    ThreeDriverNestedEngine,
    ThreeDriverNestedResult,
    ThreeDriverLSMCProxyEngine,
    ThreeDriverLSMCResult,
    ThreeDriverDiagnostics,
    ThreeDriverProxyAgreement,
    three_driver_use_restrictions,
    three_driver_use_restrictions_json,
    _inner_pathwise_pvs_3d,
    _outer_states_3d,
    _correlated_shocks_3,
    _tri_poly_basis,
    _tri_poly_powers,
    _n_tri_basis_terms,
)
from par_model_v2.stochastic.esg_process import HullWhiteParams, GBMParams, Measure
from par_model_v2.stochastic.credit_spread import CreditSpreadParams


@pytest.fixture(scope="module")
def product():
    return ParEndowmentProduct(
        term_years=10, issue_age=40, gender="M",
        sum_assured=100_000, annual_premium=6_000,
    )


@pytest.fixture(scope="module")
def hw():
    return HullWhiteParams()


@pytest.fixture(scope="module")
def gbm():
    return GBMParams()


@pytest.fixture(scope="module")
def sp():
    return CreditSpreadParams()


@pytest.fixture(scope="module")
def corr():
    return ThreeDriverCorrelation()


@pytest.fixture(scope="module")
def eg():
    return EquityGuaranteeSpec(guarantee_rate=1.0)


@pytest.fixture(scope="module")
def ce():
    return CreditExposureSpec(exposure_rate=1.0)


# ---------------------------------------------------------------------------
# Trivariate polynomial basis
# ---------------------------------------------------------------------------

def test_poly_powers_total_degree_bound():
    for deg in range(1, 5):
        powers = _tri_poly_powers(deg, max_interaction_order=99)
        assert all(a + b + c <= deg for (a, b, c) in powers)
        assert powers.count((0, 0, 0)) == 1
        # full total-degree count C(deg+3, 3)
        from math import comb
        assert len(powers) == comb(deg + 3, 3)


def test_interaction_cap_removes_high_order_three_way():
    # At degree 4 the genuine 3-way terms with total order 4 are (2,1,1) perms.
    full = _tri_poly_powers(4, max_interaction_order=99)
    capped = _tri_poly_powers(4, max_interaction_order=3)
    removed = set(full) - set(capped)
    assert removed == {(2, 1, 1), (1, 2, 1), (1, 1, 2)}
    # degree<=3 unaffected by the default cap (only (1,1,1) is 3-way at deg3)
    assert _tri_poly_powers(3, 3) == _tri_poly_powers(3, 99)


def test_basis_matrix_values_and_shape():
    X = np.array([[2.0, 3.0, 5.0]])
    powers = _tri_poly_powers(2)
    B = _tri_poly_basis(X, 2)
    assert B.shape == (1, len(powers))
    for j, (a, b, c) in enumerate(powers):
        assert B[0, j] == pytest.approx(2.0 ** a * 3.0 ** b * 5.0 ** c)


def test_basis_rejects_wrong_width():
    with pytest.raises(ValueError):
        _tri_poly_basis(np.zeros((3, 2)), 2)


def test_n_basis_terms_matches_powers():
    for deg in range(0, 5):
        assert _n_tri_basis_terms(deg) == len(_tri_poly_powers(deg))


# ---------------------------------------------------------------------------
# Spec / correlation validation
# ---------------------------------------------------------------------------

def test_credit_exposure_validation_and_notional():
    assert CreditExposureSpec(2.0).notional(100_000) == pytest.approx(200_000)
    with pytest.raises(ValueError):
        CreditExposureSpec(-1.0)


def test_correlation_matrix_symmetry_and_diagonal(gbm):
    c = ThreeDriverCorrelation(rate_spread=-0.2, equity_spread=-0.3)
    M = c.matrix(gbm.rate_equity_correlation)
    assert np.allclose(M, M.T)
    assert np.allclose(np.diag(M), 1.0)


def test_correlation_cholesky_reconstructs(gbm):
    c = ThreeDriverCorrelation(rate_spread=-0.2, equity_spread=-0.3)
    L = c.cholesky(gbm.rate_equity_correlation)
    assert np.allclose(L @ L.T, c.matrix(gbm.rate_equity_correlation), atol=1e-8)
    assert np.allclose(np.triu(L, 1), 0.0)   # lower triangular


def test_correlation_nearest_pd_fallback(gbm):
    # An impossible correlation set (forces non-PD) must still yield a factor.
    c = ThreeDriverCorrelation(rate_equity=0.95, rate_spread=-0.95, equity_spread=0.95)
    L = c.cholesky(gbm.rate_equity_correlation)
    recon = L @ L.T
    assert np.all(np.linalg.eigvalsh(recon) > -1e-10)
    assert np.allclose(np.diag(recon), 1.0, atol=1e-6)


def test_correlated_shocks_match_target_correlation(gbm):
    c = ThreeDriverCorrelation(rate_spread=-0.25, equity_spread=-0.35)
    L = c.cholesky(gbm.rate_equity_correlation)
    rng = np.random.default_rng(0)
    zr, zs, zc = _correlated_shocks_3(rng, 20000, 4, L)
    flat = np.column_stack([zr.ravel(), zs.ravel(), zc.ravel()])
    emp = np.corrcoef(flat.T)
    assert emp[0, 2] == pytest.approx(-0.25, abs=0.05)
    assert emp[1, 2] == pytest.approx(-0.35, abs=0.05)


# ---------------------------------------------------------------------------
# Inner valuation
# ---------------------------------------------------------------------------

def test_inner_pvs_shape(product, hw, gbm, sp, corr, eg, ce):
    pvs = _inner_pathwise_pvs_3d(
        0.02, 100.0, 0.012, 128, 108, product, hw, gbm, sp, corr, 12, 1, eg, ce
    )
    assert pvs.shape == (128,)
    assert np.all(pvs > 0)


def test_inner_pvs_increases_with_spread(product, hw, gbm, sp, corr, eg, ce):
    lo = _inner_pathwise_pvs_3d(0.02, 100.0, 0.004, 1500, 108, product, hw, gbm, sp, corr, 12, 7, eg, ce).mean()
    hi = _inner_pathwise_pvs_3d(0.02, 100.0, 0.05, 1500, 108, product, hw, gbm, sp, corr, 12, 7, eg, ce).mean()
    assert hi > lo


def test_credit_exposure_off_removes_spread_sensitivity(product, hw, gbm, sp, corr, eg):
    ce0 = CreditExposureSpec(exposure_rate=0.0)
    lo = _inner_pathwise_pvs_3d(0.02, 100.0, 0.004, 1500, 108, product, hw, gbm, sp, corr, 12, 7, eg, ce0).mean()
    hi = _inner_pathwise_pvs_3d(0.02, 100.0, 0.05, 1500, 108, product, hw, gbm, sp, corr, 12, 7, eg, ce0).mean()
    # credit component gone -> spread level should not move the liability
    assert lo == pytest.approx(hi, rel=1e-9)


def test_inner_reproducible_same_seed(product, hw, gbm, sp, corr, eg, ce):
    a = _inner_pathwise_pvs_3d(0.02, 100.0, 0.012, 200, 108, product, hw, gbm, sp, corr, 12, 5, eg, ce)
    b = _inner_pathwise_pvs_3d(0.02, 100.0, 0.012, 200, 108, product, hw, gbm, sp, corr, 12, 5, eg, ce)
    assert np.array_equal(a, b)


# ---------------------------------------------------------------------------
# Outer states
# ---------------------------------------------------------------------------

def test_outer_states_shape_and_correlation_signs(hw, gbm, sp):
    c = ThreeDriverCorrelation(rate_spread=-0.2, equity_spread=-0.3)
    X = _outer_states_3d(4000, 12, Measure.P, hw, gbm, sp, c, None, 42)
    assert X.shape == (4000, 3)
    assert np.corrcoef(X[:, 0], X[:, 2])[0, 1] < 0      # rate-spread negative
    assert np.corrcoef(X[:, 1], X[:, 2])[0, 1] < 0      # equity-spread negative
    assert (X[:, 2] >= 0).all()                          # spreads non-negative


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------

def test_nested_engine_capital_ordering(product, hw, gbm, sp, corr):
    eng = ThreeDriverNestedEngine(product, hw, gbm, sp, corr)
    res = eng.run(n_outer=400, n_inner=64, seed=42)
    assert isinstance(res, ThreeDriverNestedResult)
    cap = res.capital
    assert cap.es_liability >= cap.var_liability >= cap.mean_liability
    assert cap.scr_proxy == pytest.approx(cap.var_liability - cap.mean_liability)
    assert res.outer_states.shape == (400, 3)
    assert res.summary()["drivers"] == ["short_rate", "equity_level", "credit_spread"]


def test_nested_engine_rejects_bad_horizon(product, hw, gbm, sp, corr):
    with pytest.raises(ValueError):
        ThreeDriverNestedEngine(product, hw, gbm, sp, corr, capital_horizon_months=0)
    with pytest.raises(ValueError):
        ThreeDriverNestedEngine(product, hw, gbm, sp, corr, confidence_level=1.5)


def test_lsmc_engine_fit_and_predict(product, hw, gbm, sp, corr):
    eng = ThreeDriverLSMCProxyEngine(product, hw, gbm, sp, corr, degree=2)
    res = eng.fit_and_run(n_fit=500, n_outer_eval=3000, seed=42)
    assert isinstance(res, ThreeDriverLSMCResult)
    assert res.beta.shape[0] == len(res.powers)
    assert res.capital.es_liability >= res.capital.var_liability
    # predict broadcasts over a (m,3) state batch
    pred = res.predict(res.fit_states[:10])
    assert pred.shape == (10,)
    assert res.summary()["max_interaction_order"] == DEFAULT_MAX_INTERACTION_ORDER


def test_lsmc_engine_rejects_bad_degree(product, hw, gbm, sp, corr):
    with pytest.raises(ValueError):
        ThreeDriverLSMCProxyEngine(product, hw, gbm, sp, corr, degree=0)


def test_proxy_vs_nested_grid_agreement(product, hw, gbm, sp, corr):
    proxy = ThreeDriverLSMCProxyEngine(product, hw, gbm, sp, corr, degree=2).fit_and_run(
        n_fit=600, n_outer_eval=3000, seed=42
    )
    diag = ThreeDriverDiagnostics(product, hw, gbm, sp, corr)
    ag = diag.proxy_vs_nested(proxy, grid_per_dim=3, n_inner=1500, seed=11)
    assert isinstance(ag, ThreeDriverProxyAgreement)
    assert ag.grid_states.shape == (27, 3)
    assert ag.r2_vs_nested > 0.80          # strong surface agreement in-region


def test_diagnostics_reproducibility_digest_stable():
    arr = np.array([1.0, 2.0, 3.0])
    d1 = ThreeDriverDiagnostics.reproducibility_digest(arr)
    d2 = ThreeDriverDiagnostics.reproducibility_digest(arr.copy())
    assert d1 == d2 and len(d1) == 64


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

def test_use_restrictions_structure_and_json():
    r = three_driver_use_restrictions()
    assert "EDUCATIONAL" in r["classification"]
    assert "credit spread" in r["risk_drivers"]
    assert any("3.5" in s for s in r["standards"])
    parsed = json.loads(three_driver_use_restrictions_json())
    assert parsed["module"].endswith("multi_driver_capital_3d.py")
