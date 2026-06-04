"""
Tests for the Phase 15 Task 2 out-of-sample proxy-model validation
(``par_model_v2.projection.multi_driver_proxy_validation``).

Coverage:
  * ProxyValidationConfig validation (leakage seed guard, metric, degrees, sizes)
  * _fit_surface / _r2 helpers (shared-data refit, perfect-fit R^2)
  * leakage diagnostics: disjoint-seed hold-out is leakage-free
  * the core methodological claim: in-sample R^2 vs noisy single-path payoffs is
    LOW while in-sample R^2 vs heavy nested truth is HIGH (so noisy fit_r2 is not
    a validation metric)
  * degree sweep: one row per degree, OOS metrics finite, OOS R^2 high
  * model selection: selected degree optimises the chosen OOS metric
  * overfit onset detection is consistent with the OOS RMSE profile
  * capital comparison: proxy vs nested rel errors finite and bounded
  * reproducibility: identical config/seed -> identical digest
  * report to_dict / to_json round-trip; selected_row consistency
  * governance: use-restrictions structure + JSON round-trip

Sizes are kept small so each pytest invocation stays inside the sandbox time
budget; heavy targets use few inner paths.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_proxy_validation import (
    DEFAULT_DEGREE_GRID,
    CapitalComparison,
    DegreeDiagnostics,
    LeakageDiagnostics,
    MultiDriverProxyValidator,
    ProxyValidationConfig,
    ProxyValidationReport,
    proxy_validation_use_restrictions,
    proxy_validation_use_restrictions_json,
    _fit_surface,
    _r2,
)
from par_model_v2.stochastic.esg_process import GBMParams, HullWhiteParams, Measure


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def product():
    return ParEndowmentProduct(
        term_years=10, issue_age=40, gender="M",
        sum_assured=100_000, annual_premium=6_000,
    )


@pytest.fixture(scope="module")
def validator(product):
    return MultiDriverProxyValidator(
        product, HullWhiteParams(), GBMParams(),
        equity_guarantee=EquityGuaranteeSpec(guarantee_rate=1.0),
    )


@pytest.fixture(scope="module")
def small_cfg():
    return ProxyValidationConfig(
        n_fit=400, n_validation=40, n_insample_heavy=20,
        n_inner_heavy=256, degrees=(1, 2, 3),
    )


@pytest.fixture(scope="module")
def report(validator, small_cfg):
    return validator.validate(small_cfg, nested_n_outer=300, nested_n_inner=48)


# --------------------------------------------------------------------------
# Config validation
# --------------------------------------------------------------------------

def test_config_rejects_equal_fit_and_validation_seed():
    with pytest.raises(ValueError):
        ProxyValidationConfig(fit_seed=5, validation_seed=5)


def test_config_rejects_bad_metric():
    with pytest.raises(ValueError):
        ProxyValidationConfig(selection_metric="r_squared")


def test_config_rejects_empty_or_low_degree():
    with pytest.raises(ValueError):
        ProxyValidationConfig(degrees=())
    with pytest.raises(ValueError):
        ProxyValidationConfig(degrees=(0, 1))


def test_config_rejects_tiny_validation_set():
    with pytest.raises(ValueError):
        ProxyValidationConfig(n_validation=4)


def test_config_to_dict_round_trips_measure():
    cfg = ProxyValidationConfig(outer_measure=Measure.P)
    d = cfg.to_dict()
    assert d["outer_measure"] == Measure.P.value
    assert d["degrees"] == list(cfg.degrees)


# --------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------

def test_fit_surface_recovers_linear_function_exactly():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 2))
    # exact affine target -> degree-1 surface should fit ~perfectly
    y = 3.0 + 2.0 * X[:, 0] - 1.5 * X[:, 1]
    surf = _fit_surface(X, y, degree=1)
    pred = surf.predict(X)
    assert surf.in_sample_r2_noisy > 0.999
    assert np.allclose(pred, y, atol=1e-6)


def test_r2_perfect_and_mean_baseline():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert _r2(y, y) == pytest.approx(1.0)
    # predicting the mean -> R^2 == 0
    assert _r2(y, np.full_like(y, y.mean())) == pytest.approx(0.0)


# --------------------------------------------------------------------------
# Leakage diagnostics
# --------------------------------------------------------------------------

def test_holdout_is_leakage_free(report):
    lk = report.leakage
    assert isinstance(lk, LeakageDiagnostics)
    assert lk.seeds_disjoint is True
    assert lk.n_exact_shared_states == 0
    assert lk.min_pairwise_distance > 0.0
    assert lk.leakage_free is True


# --------------------------------------------------------------------------
# Core methodological claim
# --------------------------------------------------------------------------

def test_noisy_fit_r2_is_low_but_heavy_r2_is_high(report):
    """The single-path fit_r2 is NOT a validation metric: it is far below the
    heavy in-sample R^2 at every degree, motivating the OOS validation."""
    for row in report.degree_rows:
        assert row.in_sample_r2_noisy < 0.6
        assert row.in_sample_r2_heavy > row.in_sample_r2_noisy
    # the proxy actually reproduces truth well on the hold-out
    assert max(r.oos_r2 for r in report.degree_rows) > 0.9


# --------------------------------------------------------------------------
# Degree sweep + selection
# --------------------------------------------------------------------------

def test_degree_sweep_has_one_row_per_degree(report, small_cfg):
    degs = sorted(r.degree for r in report.degree_rows)
    assert degs == sorted(small_cfg.degrees)
    for row in report.degree_rows:
        assert isinstance(row, DegreeDiagnostics)
        assert np.isfinite(row.oos_rmse) and row.oos_rmse >= 0.0
        assert np.isfinite(row.oos_r2)
        assert np.isfinite(row.oos_max_abs_rel_error)
        assert row.n_basis_terms == (row.degree + 1) * (row.degree + 2) // 2


def test_selection_optimises_oos_rmse(report):
    best = min(report.degree_rows, key=lambda r: r.oos_rmse)
    assert report.selected_degree == best.degree
    assert report.selection_metric == "oos_rmse"


def test_selection_by_oos_r2(validator, small_cfg):
    cfg = ProxyValidationConfig(
        n_fit=small_cfg.n_fit, n_validation=small_cfg.n_validation,
        n_insample_heavy=small_cfg.n_insample_heavy,
        n_inner_heavy=small_cfg.n_inner_heavy, degrees=small_cfg.degrees,
        selection_metric="oos_r2",
    )
    rep = validator.validate(cfg, nested_n_outer=300, nested_n_inner=48)
    best = max(rep.degree_rows, key=lambda r: r.oos_r2)
    assert rep.selected_degree == best.degree


def test_overfit_onset_consistent_with_rmse_profile(report):
    onset = report.overfit_onset_degree
    if onset is not None:
        ordered = sorted(report.degree_rows, key=lambda r: r.degree)
        idx = [r.degree for r in ordered].index(onset)
        assert idx >= 1
        assert ordered[idx].oos_rmse > ordered[idx - 1].oos_rmse


# --------------------------------------------------------------------------
# Capital comparison
# --------------------------------------------------------------------------

def test_capital_comparison_rel_errors_finite(report):
    cc = report.capital_comparison
    assert isinstance(cc, CapitalComparison)
    for e in (cc.var_rel_error, cc.es_rel_error, cc.scr_rel_error):
        assert np.isfinite(e) and e >= 0.0
    # proxy VaR should be in the right ballpark of nested VaR (educational tol)
    assert cc.var_rel_error < 0.25
    assert cc.proxy_capital.es_liability >= cc.proxy_capital.var_liability


# --------------------------------------------------------------------------
# Reproducibility
# --------------------------------------------------------------------------

def test_reproducible_digest(validator, small_cfg):
    r1 = validator.validate(small_cfg, nested_n_outer=300, nested_n_inner=48)
    r2 = validator.validate(small_cfg, nested_n_outer=300, nested_n_inner=48)
    assert r1.reproducibility_digest == r2.reproducibility_digest
    assert r1.selected_degree == r2.selected_degree


# --------------------------------------------------------------------------
# Report serialisation
# --------------------------------------------------------------------------

def test_report_to_dict_and_json(report):
    assert isinstance(report, ProxyValidationReport)
    d = report.to_dict()
    assert d["selected_degree"] == report.selected_degree
    assert d["selected_row"]["degree"] == report.selected_degree
    assert len(d["degree_rows"]) == len(report.degree_rows)
    assert "leakage" in d and "capital_comparison" in d
    assert d["verdict"].startswith(("PASS", "PARTIAL"))
    # JSON round-trip
    parsed = json.loads(report.to_json())
    assert parsed["run_id"] == report.run_id
    assert parsed["reproducibility_digest"] == report.reproducibility_digest


def test_selected_row_matches_selected_degree(report):
    assert report.selected_row().degree == report.selected_degree


def test_verdict_is_honest(report):
    sel = report.selected_row()
    if report.verdict.startswith("PASS"):
        assert sel.oos_r2 >= 0.95
        assert report.capital_comparison.var_rel_error <= 0.10
        assert report.leakage.leakage_free


# --------------------------------------------------------------------------
# Governance
# --------------------------------------------------------------------------

def test_use_restrictions_structure_and_json():
    r = proxy_validation_use_restrictions()
    for key in ("module", "classification", "what_it_validates",
                "heavy_target_caveat", "residual_risk", "governance", "standards"):
        assert key in r
    assert "EDUCATIONAL" in r["classification"]
    assert isinstance(r["standards"], list) and r["standards"]
    parsed = json.loads(proxy_validation_use_restrictions_json())
    assert parsed["module"].endswith("multi_driver_proxy_validation.py")


def test_default_degree_grid_constant():
    assert DEFAULT_DEGREE_GRID == (1, 2, 3, 4)
