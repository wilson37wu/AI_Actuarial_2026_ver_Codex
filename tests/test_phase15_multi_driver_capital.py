"""
Tests for the Phase 15 Task 1 two-driver (rates + equity) nested / LSMC
economic-capital proxy (``par_model_v2.projection.multi_driver_capital``).

Coverage:
  * bivariate total-degree polynomial basis (ordering, count, values)
  * EquityGuaranteeSpec validation, units/floor
  * two-driver inner valuation: shape, equity & rate sensitivity, the
    guarantee-off reduction (equity component drops out -> independent of S)
  * measure handling (outer P, inner Q)
  * reproducibility (seed-determinism digest)
  * MultiDriverNestedEngine: capital-metric ordering, input validation
  * MultiDriverLSMCProxyEngine: fit/predict, degree validation, proxy-vs-nested
  * MultiDriverDiagnostics: 2-D grid agreement R^2, reproducibility
  * governance: model-use restrictions structure + JSON round-trip

Sizes are kept modest so each pytest invocation stays inside the sandbox time
budget; the heavier proxy-vs-nested check uses fewer inner paths.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import (
    DEFAULT_MULTI_LSMC_DEGREE,
    EquityGuaranteeSpec,
    MultiDriverNestedEngine,
    MultiDriverNestedResult,
    MultiDriverLSMCProxyEngine,
    MultiDriverLSMCResult,
    MultiDriverDiagnostics,
    MultiDriverProxyAgreement,
    multi_driver_use_restrictions,
    multi_driver_use_restrictions_json,
    _inner_pathwise_pvs_2d,
    _outer_states_2d,
    _multi_poly_basis,
    _multi_poly_powers,
    _n_basis_terms,
)
from par_model_v2.stochastic.esg_process import HullWhiteParams, GBMParams, Measure


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
def eg():
    return EquityGuaranteeSpec(guarantee_rate=1.0)


# ---------------------------------------------------------------------------
# Bivariate polynomial basis
# ---------------------------------------------------------------------------

def test_poly_powers_count_and_total_degree():
    for deg in range(1, 6):
        powers = _multi_poly_powers(deg)
        assert len(powers) == _n_basis_terms(deg) == (deg + 1) * (deg + 2) // 2
        assert all(a + b <= deg for (a, b) in powers)
        # constant term present exactly once
        assert powers.count((0, 0)) == 1


def test_poly_powers_ordering_degree2():
    assert _multi_poly_powers(2) == [(0, 0), (0, 1), (1, 0), (0, 2), (1, 1), (2, 0)]


def test_poly_basis_values_degree1():
    X = np.array([[2.0, 3.0], [0.5, -1.0]])
    B = _multi_poly_basis(X, 1)
    # degree-1 powers: (0,0),(0,1),(1,0) -> [1, x1, x0]
    assert B.shape == (2, 3)
    np.testing.assert_allclose(B[:, 0], [1.0, 1.0])
    np.testing.assert_allclose(B[:, 1], X[:, 1])
    np.testing.assert_allclose(B[:, 2], X[:, 0])


def test_poly_basis_values_degree2():
    X = np.array([[2.0, 3.0]])
    B = _multi_poly_basis(X, 2)
    # (0,0),(0,1),(1,0),(0,2),(1,1),(2,0)
    np.testing.assert_allclose(B[0], [1.0, 3.0, 2.0, 9.0, 6.0, 4.0])


def test_poly_basis_rejects_wrong_shape():
    with pytest.raises(ValueError):
        _multi_poly_basis(np.array([1.0, 2.0, 3.0]), 2)


# ---------------------------------------------------------------------------
# EquityGuaranteeSpec
# ---------------------------------------------------------------------------

def test_equity_guarantee_units_floor():
    spec = EquityGuaranteeSpec(guarantee_rate=0.8, initial_index_level=100.0)
    assert spec.units(100_000) == pytest.approx(1000.0)
    assert spec.floor(100_000) == pytest.approx(80_000.0)


@pytest.mark.parametrize("bad", [-0.1, 5.5])
def test_equity_guarantee_rate_validation(bad):
    with pytest.raises(ValueError):
        EquityGuaranteeSpec(guarantee_rate=bad)


def test_equity_guarantee_index_level_validation():
    with pytest.raises(ValueError):
        EquityGuaranteeSpec(initial_index_level=0.0)


# ---------------------------------------------------------------------------
# Two-driver inner valuation
# ---------------------------------------------------------------------------

def test_inner_pvs_shape(product, hw, gbm, eg):
    rem = product.term_months - 12
    pvs = _inner_pathwise_pvs_2d(0.03, 100.0, 256, rem, product, hw, gbm, 12, 7, eg)
    assert pvs.shape == (256,)
    assert np.all(pvs > 0)


def test_inner_pvs_equity_sensitivity(product, hw, gbm, eg):
    """Put-style guarantee value decreases as the equity level rises."""
    rem = product.term_months - 12
    n = 8192
    low_s = _inner_pathwise_pvs_2d(0.03, 70.0, n, rem, product, hw, gbm, 12, 7, eg).mean()
    high_s = _inner_pathwise_pvs_2d(0.03, 140.0, n, rem, product, hw, gbm, 12, 7, eg).mean()
    assert low_s > high_s


def test_inner_pvs_rate_sensitivity(product, hw, gbm, eg):
    """Lower rates -> higher discounted guarantee value."""
    rem = product.term_months - 12
    n = 8192
    low_r = _inner_pathwise_pvs_2d(0.01, 100.0, n, rem, product, hw, gbm, 12, 7, eg).mean()
    high_r = _inner_pathwise_pvs_2d(0.06, 100.0, n, rem, product, hw, gbm, 12, 7, eg).mean()
    assert low_r > high_r


def test_inner_pvs_guarantee_off_drops_equity(product, hw, gbm):
    """With guarantee_rate=0 the equity put is zero, so L is independent of S."""
    off = EquityGuaranteeSpec(guarantee_rate=0.0)
    rem = product.term_months - 12
    n = 4096
    a = _inner_pathwise_pvs_2d(0.03, 60.0, n, rem, product, hw, gbm, 12, 7, off)
    b = _inner_pathwise_pvs_2d(0.03, 160.0, n, rem, product, hw, gbm, 12, 7, off)
    # same rate seed/state -> identical rate paths -> identical guaranteed PV
    np.testing.assert_allclose(a, b, rtol=0, atol=1e-9)


def test_inner_pvs_reproducible(product, hw, gbm, eg):
    rem = product.term_months - 12
    a = _inner_pathwise_pvs_2d(0.03, 100.0, 512, rem, product, hw, gbm, 12, 123, eg)
    b = _inner_pathwise_pvs_2d(0.03, 100.0, 512, rem, product, hw, gbm, 12, 123, eg)
    np.testing.assert_array_equal(a, b)


# ---------------------------------------------------------------------------
# Outer state sampling (correlated rate + equity)
# ---------------------------------------------------------------------------

def test_outer_states_2d_shape_and_measure(product, hw, gbm):
    outer = _outer_states_2d(300, 12, Measure.P, hw, gbm, None, 42)
    assert outer.shape == (300, 2)
    assert np.all(outer[:, 0] > -0.1) and np.all(outer[:, 0] < 0.5)   # plausible rates
    assert np.all(outer[:, 1] > 0)                                    # positive index


def test_outer_states_2d_reproducible(product, hw, gbm):
    a = _outer_states_2d(200, 12, Measure.P, hw, gbm, None, 42)
    b = _outer_states_2d(200, 12, Measure.P, hw, gbm, None, 42)
    np.testing.assert_array_equal(a, b)


# ---------------------------------------------------------------------------
# Nested engine
# ---------------------------------------------------------------------------

def test_nested_engine_runs(product, hw, gbm, eg):
    res = MultiDriverNestedEngine(
        product, hw, gbm, equity_guarantee=eg, confidence_level=0.95,
    ).run(n_outer=150, n_inner=80, seed=42)
    assert isinstance(res, MultiDriverNestedResult)
    cap = res.capital
    # ES >= VaR >= mean for an upper-tail loss metric
    assert cap.es_liability >= cap.var_liability >= cap.mean_liability
    assert cap.scr_proxy == pytest.approx(cap.var_liability - cap.mean_liability, rel=1e-9)
    assert res.outer_states.shape == (150, 2)
    assert res.total_inner_valuations == 150 * 80


def test_nested_engine_reproducible(product, hw, gbm, eg):
    kw = dict(n_outer=120, n_inner=64, seed=99)
    a = MultiDriverNestedEngine(product, hw, gbm, equity_guarantee=eg).run(**kw)
    b = MultiDriverNestedEngine(product, hw, gbm, equity_guarantee=eg).run(**kw)
    d = MultiDriverDiagnostics.reproducibility_digest
    assert d(a.conditional_liabilities) == d(b.conditional_liabilities)


def test_nested_engine_horizon_validation(product, hw, gbm):
    with pytest.raises(ValueError):
        MultiDriverNestedEngine(product, hw, gbm, capital_horizon_months=product.term_months)
    with pytest.raises(ValueError):
        MultiDriverNestedEngine(product, hw, gbm, capital_horizon_months=0)


def test_nested_engine_confidence_validation(product, hw, gbm):
    with pytest.raises(ValueError):
        MultiDriverNestedEngine(product, hw, gbm, confidence_level=1.5)


# ---------------------------------------------------------------------------
# LSMC proxy engine
# ---------------------------------------------------------------------------

def test_lsmc_engine_runs(product, hw, gbm, eg):
    res = MultiDriverLSMCProxyEngine(
        product, hw, gbm, equity_guarantee=eg, confidence_level=0.95, degree=2,
    ).fit_and_run(n_fit=600, n_outer_eval=2000, seed=42)
    assert isinstance(res, MultiDriverLSMCResult)
    assert res.beta.shape == (_n_basis_terms(2),)
    assert res.fit_states.shape == (600, 2)
    assert res.capital.es_liability >= res.capital.var_liability
    assert len(res.powers) == _n_basis_terms(2)


def test_lsmc_predict_matches_manual_beta(product, hw, gbm, eg):
    res = MultiDriverLSMCProxyEngine(
        product, hw, gbm, equity_guarantee=eg, degree=2,
    ).fit_and_run(n_fit=400, n_outer_eval=800, seed=7)
    X = np.array([[0.025, 105.0], [0.045, 95.0]])
    Xs = (X - res.centers) / res.scales
    manual = _multi_poly_basis(Xs, res.degree) @ res.beta
    np.testing.assert_allclose(res.predict(X), manual, rtol=1e-9)


def test_lsmc_predict_single_state(product, hw, gbm, eg):
    res = MultiDriverLSMCProxyEngine(
        product, hw, gbm, equity_guarantee=eg, degree=2,
    ).fit_and_run(n_fit=400, n_outer_eval=800, seed=7)
    out = res.predict(np.array([0.03, 100.0]))
    assert out.shape == (1,)


def test_lsmc_degree_validation(product, hw, gbm):
    with pytest.raises(ValueError):
        MultiDriverLSMCProxyEngine(product, hw, gbm, degree=0)


def test_default_degree_constant():
    assert DEFAULT_MULTI_LSMC_DEGREE == 2


# ---------------------------------------------------------------------------
# Proxy-vs-nested agreement (the headline validation metric)
# ---------------------------------------------------------------------------

def test_proxy_vs_nested_agreement(product, hw, gbm, eg):
    proxy = MultiDriverLSMCProxyEngine(
        product, hw, gbm, equity_guarantee=eg, degree=2,
    ).fit_and_run(n_fit=1200, n_outer_eval=3000, seed=42)
    diag = MultiDriverDiagnostics(product, hw, gbm, equity_guarantee=eg)
    agree = diag.proxy_vs_nested(proxy, grid_per_dim=4, n_inner=2048, seed=11)
    assert isinstance(agree, MultiDriverProxyAgreement)
    assert agree.grid_states.shape == (16, 2)
    # bivariate quadratic surface should track the nested truth closely
    assert agree.r2_vs_nested > 0.95
    assert agree.max_abs_rel_error < 0.08


def test_diagnostics_reproducibility_digest():
    arr = np.array([1.0, 2.0, 3.0])
    d = MultiDriverDiagnostics.reproducibility_digest
    assert d(arr) == d(arr.copy())
    assert d(arr) != d(arr + 1e-3)


# ---------------------------------------------------------------------------
# Governance disclosure
# ---------------------------------------------------------------------------

def test_use_restrictions_structure():
    r = multi_driver_use_restrictions()
    assert "EDUCATIONAL" in r["classification"]
    assert "short rate" in r["risk_drivers"] and "equity" in r["risk_drivers"]
    assert "single-risk-driver" in r["improvement_over_task6"]
    assert any("ASOP 56" in s for s in r["standards"])


def test_use_restrictions_json_round_trip():
    parsed = json.loads(multi_driver_use_restrictions_json())
    assert parsed["module"].endswith("multi_driver_capital.py")
    assert isinstance(parsed["standards"], list)
