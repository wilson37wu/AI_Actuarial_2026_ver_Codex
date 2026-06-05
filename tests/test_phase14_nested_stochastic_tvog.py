"""Phase 14 Task 6 — Nested-stochastic / LSMC TVOG capital-proxy tests.

Covers the capital-metric layer added on top of the Phase 4 TVOGEngine:

  * Vectorised residual valuation is numerically identical to the per-month loop
  * CapitalMetrics VaR/ES/SCR-proxy algebra and tail ordering
  * NestedStochasticTVOGEngine — ground-truth run, sane capital, audit hook
  * LSMCProxyEngine — fit/predict, surface evaluation, unbiasedness vs nested
  * Convergence diagnostics — inner standard error decays ~1/sqrt(n_inner)
  * Reproducibility — identical seed => identical SHA-256; different seed differs
  * Proxy-vs-nested agreement — high R^2 against high-accuracy nested L(x)
  * Model-use restrictions disclosure (governance)
  * Input validation guards

SOA ASOP 56 §3.1.3/§3.5; SOA ASOP 25 §3.3; IA TAS M §3.2/§3.6.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.tvog import _scenario_discount_factors
from par_model_v2.stochastic.esg_process import HullWhiteParams, Measure
from par_model_v2.projection.nested_stochastic_tvog import (
    CAPITAL_OUTER_MINIMUM,
    DEFAULT_CONFIDENCE_LEVEL,
    CapitalMetrics,
    LSMCProxyEngine,
    NestedStochasticDiagnostics,
    NestedStochasticTVOGEngine,
    capital_metrics_from_liabilities,
    model_use_restrictions,
    model_use_restrictions_json,
    _inner_pathwise_pvs,
    _residual_cashflow_vector,
    _residual_guaranteed_pv,
    _vectorised_discount_factors,
)


@pytest.fixture(scope="module")
def product():
    return ParEndowmentProduct(
        term_years=10, issue_age=40, gender="M",
        sum_assured=100_000, annual_premium=6_000,
    )


@pytest.fixture(scope="module")
def hw():
    return HullWhiteParams()


# ---------------------------------------------------------------------------
# Vectorised valuation == per-month loop
# ---------------------------------------------------------------------------

def test_vectorised_pv_matches_loop(product):
    rng = np.random.default_rng(0)
    rate_paths = 0.02 + 0.005 * rng.standard_normal((8, 109))  # rem = 108
    cf = _residual_cashflow_vector(product, 12)
    disc = _vectorised_discount_factors(rate_paths)
    vec = disc @ cf
    loop = np.array([
        _residual_guaranteed_pv(product, 12, _scenario_discount_factors(rate_paths[i], 108))
        for i in range(rate_paths.shape[0])
    ])
    assert np.max(np.abs(vec - loop)) < 1e-6


def test_discount_factor_starts_at_one(product):
    rate_paths = np.full((3, 25), 0.03)
    disc = _vectorised_discount_factors(rate_paths)
    assert np.allclose(disc[:, 0], 1.0)
    # monotone non-increasing under positive rates
    assert np.all(np.diff(disc, axis=1) <= 1e-12)


def test_residual_cashflow_vector_zero_when_no_horizon_left(product):
    cf = _residual_cashflow_vector(product, product.term_months)
    assert cf.shape == (1,)
    assert cf.sum() == 0.0


def test_residual_cashflow_maturity_dominates(product):
    cf = _residual_cashflow_vector(product, 12)
    # maturity benefit at the final residual month is the largest single flow
    assert cf[-1] == pytest.approx(cf.max())
    assert cf[-1] > 0.9 * product.sum_assured  # survival-weighted maturity


# ---------------------------------------------------------------------------
# CapitalMetrics algebra
# ---------------------------------------------------------------------------

def test_capital_metrics_tail_ordering():
    rng = np.random.default_rng(1)
    liab = 100.0 + 10.0 * rng.standard_normal(20_000)
    cm = capital_metrics_from_liabilities(liab, 0.995, 12)
    assert cm.var_liability >= cm.mean_liability
    assert cm.es_liability >= cm.var_liability
    assert cm.scr_proxy == pytest.approx(cm.var_liability - cm.mean_liability)
    assert cm.n_outer == 20_000


def test_capital_metrics_summary_roundtrip():
    cm = CapitalMetrics(0.995, 100.0, 130.0, 140.0, 30.0, 1000, 12)
    s = cm.summary()
    assert s["confidence_level"] == 0.995
    assert s["scr_proxy"] == 30.0
    assert json.dumps(s)  # serialisable


# ---------------------------------------------------------------------------
# Nested-stochastic engine
# ---------------------------------------------------------------------------

def test_nested_engine_runs_and_is_sane(product, hw):
    eng = NestedStochasticTVOGEngine(product, hw, outer_measure="P")
    res = eng.run(n_outer=200, n_inner=128, seed=42)
    assert res.n_outer == 200
    assert res.total_inner_valuations == 200 * 128
    c = res.capital
    assert c.var_liability >= c.mean_liability
    assert c.es_liability >= c.var_liability
    assert c.scr_proxy > 0.0
    assert res.conditional_liabilities.shape == (200,)
    assert np.all(res.inner_standard_errors >= 0.0)


def test_nested_engine_q_outer_measure_supported(product, hw):
    eng = NestedStochasticTVOGEngine(product, hw, outer_measure=Measure.Q)
    res = eng.run(n_outer=120, n_inner=64, seed=3)
    assert res.capital.mean_liability > 0.0


def test_nested_engine_records_audit_entry(product, hw):
    from par_model_v2.governance.audit_trail import GovernanceStore

    store = GovernanceStore()
    before = len(store.audit_trail.entries)
    eng = NestedStochasticTVOGEngine(product, hw, outer_measure="P")
    res = eng.run(n_outer=80, n_inner=64, seed=9, governance_store=store)
    assert res.audit_entry_id is not None
    assert len(store.audit_trail.entries) == before + 1


# ---------------------------------------------------------------------------
# LSMC proxy engine
# ---------------------------------------------------------------------------

def test_lsmc_engine_runs(product, hw):
    eng = LSMCProxyEngine(product, hw, outer_measure="P", degree=3)
    res = eng.fit_and_run(n_fit=400, n_outer_eval=800, seed=42)
    assert res.n_fit == 400
    assert res.n_outer_eval == 800
    assert res.beta.shape == (4,)
    assert res.capital.var_liability >= res.capital.mean_liability
    # predict returns an array of the right shape
    pred = res.predict(res.fit_states[:10])
    assert pred.shape == (10,)


def test_lsmc_unbiased_mean_vs_nested(product, hw):
    """LSMC mean liability should track the nested ground-truth mean."""
    nested = NestedStochasticTVOGEngine(product, hw, outer_measure="P").run(
        n_outer=400, n_inner=256, seed=42)
    lsmc = LSMCProxyEngine(product, hw, outer_measure="P", degree=3).fit_and_run(
        n_fit=600, n_outer_eval=2000, seed=42)
    rel = abs(lsmc.capital.mean_liability - nested.capital.mean_liability) / nested.capital.mean_liability
    assert rel < 0.02


def test_lsmc_degree_validation(product, hw):
    with pytest.raises(ValueError):
        LSMCProxyEngine(product, hw, degree=0)


# ---------------------------------------------------------------------------
# Convergence diagnostics (ASOP 56 §3.5)
# ---------------------------------------------------------------------------

def test_inner_standard_error_decays(product, hw):
    diag = NestedStochasticDiagnostics(product, hw)
    pts = diag.inner_convergence(inner_counts=(64, 256, 1_024, 4_096))
    assert diag.standard_error_decays(pts)
    # SE should roughly halve when n_inner quadruples (1/sqrt(n))
    ratio = pts[0].standard_error / pts[2].standard_error
    assert 2.5 < ratio < 6.0


def test_inner_means_stabilise(product, hw):
    diag = NestedStochasticDiagnostics(product, hw)
    pts = diag.inner_convergence(inner_counts=(256, 4_096))
    coarse, fine = pts[0].mean_liability, pts[1].mean_liability
    assert abs(coarse - fine) < 3.0 * pts[0].standard_error + 1.0


# ---------------------------------------------------------------------------
# Proxy-vs-nested agreement
# ---------------------------------------------------------------------------

def test_proxy_matches_nested_on_grid(product, hw):
    lsmc = LSMCProxyEngine(product, hw, outer_measure="P", degree=3).fit_and_run(
        n_fit=600, n_outer_eval=600, seed=42)
    diag = NestedStochasticDiagnostics(product, hw)
    agr = diag.proxy_vs_nested(lsmc, grid=np.linspace(0.005, 0.04, 7), n_inner=2_048)
    assert agr.r2_vs_nested > 0.95
    assert agr.max_abs_rel_error < 0.10


# ---------------------------------------------------------------------------
# Reproducibility (IA TAS M §3.6)
# ---------------------------------------------------------------------------

def test_same_seed_is_bit_identical(product, hw):
    eng = NestedStochasticTVOGEngine(product, hw, outer_measure="P")
    a = eng.run(n_outer=150, n_inner=128, seed=42)
    b = eng.run(n_outer=150, n_inner=128, seed=42)
    digest = NestedStochasticDiagnostics.reproducibility_digest
    assert digest(a.conditional_liabilities) == digest(b.conditional_liabilities)
    assert a.capital.var_liability == pytest.approx(b.capital.var_liability)


def test_different_seed_differs(product, hw):
    eng = NestedStochasticTVOGEngine(product, hw, outer_measure="P")
    a = eng.run(n_outer=150, n_inner=128, seed=42)
    b = eng.run(n_outer=150, n_inner=128, seed=99)
    digest = NestedStochasticDiagnostics.reproducibility_digest
    assert digest(a.conditional_liabilities) != digest(b.conditional_liabilities)


# ---------------------------------------------------------------------------
# Model-use restrictions disclosure
# ---------------------------------------------------------------------------

def test_model_use_restrictions_keys():
    r = model_use_restrictions()
    for key in (
        "classification", "single_risk_driver", "placeholder_parameters",
        "lsmc_extrapolation", "convergence_requirements", "governance", "standards",
    ):
        assert key in r
    assert "EDUCATIONAL" in r["classification"]
    assert str(CAPITAL_OUTER_MINIMUM) in r["convergence_requirements"]


def test_model_use_restrictions_json_serialisable():
    parsed = json.loads(model_use_restrictions_json())
    assert isinstance(parsed["standards"], list)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_horizon_must_be_within_term(product, hw):
    with pytest.raises(ValueError):
        NestedStochasticTVOGEngine(product, hw, capital_horizon_months=0)
    with pytest.raises(ValueError):
        NestedStochasticTVOGEngine(product, hw, capital_horizon_months=product.term_months)


def test_confidence_level_range(product, hw):
    with pytest.raises(ValueError):
        NestedStochasticTVOGEngine(product, hw, confidence_level=0.4)
    with pytest.raises(ValueError):
        NestedStochasticTVOGEngine(product, hw, confidence_level=1.0)


def test_default_confidence_is_995():
    assert DEFAULT_CONFIDENCE_LEVEL == 0.995


def test_inner_pathwise_pvs_shape(product, hw):
    pvs = _inner_pathwise_pvs(0.02, 32, 108, product, hw, 12, seed=5)
    assert pvs.shape == (32,)
    assert np