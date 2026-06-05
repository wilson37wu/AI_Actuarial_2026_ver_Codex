"""
Tests for the Phase 17 Task 2 out-of-sample TRIVARIATE proxy-model validation
(``par_model_v2.projection.multi_driver_proxy_validation.ThreeDriverProxyValidator``).

Coverage mirrors the Phase 15 (two-driver) proxy-validation tests, extended for
the third (credit-spread) driver and the (degree, max_interaction_order) basis
grid:

  * TriProxyValidationConfig validation (leakage seed guard, metric, basis grid,
    sizes)
  * _fit_tri_surface / _leakage_nd helpers (shared-data refit, perfect-fit R^2,
    3-D disjointness)
  * the core methodological claim: in-sample R^2 vs noisy single-path payoffs is
    LOW while in-sample R^2 vs heavy nested truth is HIGH (noisy fit_r2 is NOT a
    validation metric)
  * basis sweep: one row per (degree, max_int), OOS metrics finite, OOS R^2 high
  * model selection optimises the chosen OOS metric; selected_row consistency
  * overfit onset is consistent with the OOS RMSE profile (ordered by #terms)
  * capital comparison: proxy vs three-driver nested rel errors finite & bounded
  * leakage diagnostics: disjoint-seed hold-out is leakage-free, no shared states
  * reproducibility: identical config/seed -> identical digest
  * report to_dict / to_json round-trip
  * governance: trivariate use-restrictions structure + JSON round-trip

Sizes are kept small so each pytest invocation stays inside the sandbox time
budget; heavy targets use few inner paths.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_capital_3d import (
    CreditExposureSpec,
    ThreeDriverCorrelation,
)
from par_model_v2.projection.multi_driver_proxy_validation import (
    DEFAULT_TRI_BASIS_GRID,
    CapitalComparison,
    LeakageDiagnostics,
    ThreeDriverProxyValidator,
    TriBasisDiagnostics,
    TriProxyValidationConfig,
    TriProxyValidationReport,
    tri_proxy_validation_use_restrictions,
    tri_proxy_validation_use_restrictions_json,
    _fit_tri_surface,
    _leakage_nd,
    _r2,
)
from par_model_v2.stochastic.credit_spread import CreditSpreadParams
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
    return ThreeDriverProxyValidator(
        product, HullWhiteParams(), GBMParams(), CreditSpreadParams(),
        ThreeDriverCorrelation(),
        equity_guarantee=EquityGuaranteeSpec(guarantee_rate=1.0),
        credit_exposure=CreditExposureSpec(),
    )


@pytest.fixture(scope="module")
def small_cfg():
    return TriProxyValidationConfig(
        n_fit=400, n_validation=40, n_insample_heavy=20,
        n_inner_heavy=256, basis_grid=((1, 3), (2, 3), (3, 2), (3, 3)),
    )


@pytest.fixture(scope="module")
def report(validator, small_cfg):
    return validator.validate(small_cfg, nested_n_outer=300, nested_n_inner=48)


# --------------------------------------------------------------------------
# Config validation
# --------------------------------------------------------------------------

def test_default_basis_grid_constant():
    assert DEFAULT_TRI_BASIS_GRID == ((1, 3), (2, 3), (3, 2), (3, 3), (4, 3))


def test_config_rejects_equal_seeds():
    with pytest.raises(ValueError):
        TriProxyValidationConfig(fit_seed=5, validation_seed=5)


def test_config_rejects_bad_metric():
    with pytest.raises(ValueError):
        TriProxyValidationConfig(selection_metric="rmse")


def test_config_rejects_empty_grid():
    with pytest.raises(ValueError):
        TriProxyValidationConfig(basis_grid=())


def test_config_rejects_degree_below_one():
    with pytest.raises(ValueError):
        TriProxyValidationConfig(basis_grid=((0, 3),))


def test_config_rejects_negative_interaction_order():
    with pytest.raises(ValueError):
        TriProxyValidationConfig(basis_grid=((2, -1),))


def test_config_rejects_tiny_validation():
    with pytest.raises(ValueError):
        TriProxyValidationConfig(n_validation=4)


def test_config_to_dict_round_trip():
    cfg = TriProxyValidationConfig()
    d = cfg.to_dict()
    assert d["basis_grid"] == [list(p) for p in DEFAULT_TRI_BASIS_GRID]
    assert d["outer_measure"] == "P"
    assert json.loads(json.dumps(d))  # JSON serialisable


# --------------------------------------------------------------------------
# Low-level helpers
# --------------------------------------------------------------------------

def test_fit_tri_surface_perfect_linear():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 3))
    # exact linear target -> degree-1 surface must reproduce it (R^2 ~ 1)
    y = 3.0 + 2.0 * X[:, 0] - 1.5 * X[:, 1] + 0.7 * X[:, 2]
    surf = _fit_tri_surface(X, y, degree=1, max_interaction_order=3)
    assert surf.in_sample_r2_noisy > 0.999
    pred = surf.predict(X)
    assert _r2(y, pred) > 0.999


def test_leakage_nd_disjoint_seeds_clean(validator):
    fit_X = validator._states(120, 42)
    val_X = validator._states(40, 20260605)
    lk = _leakage_nd(fit_X, val_X, 42, 20260605)
    assert isinstance(lk, LeakageDiagnostics)
    assert lk.seeds_disjoint is True
    assert lk.n_exact_shared_states == 0
    assert lk.leakage_free is True
    assert lk.min_pairwise_distance > 0.0


def test_leakage_nd_same_seed_not_disjoint(validator):
    X = validator._states(50, 999)
    lk = _leakage_nd(X, X, 999, 999)
    assert lk.seeds_disjoint is False
    assert lk.leakage_free is False
    assert lk.n_exact_shared_states == len(X)


# --------------------------------------------------------------------------
# Methodological claim: noisy fit_r2 is NOT a validation metric
# --------------------------------------------------------------------------

def test_noisy_fit_r2_low_but_heavy_r2_high(report):
    # Every basis: the noisy single-path fit R^2 is far below the heavy
    # in-sample R^2 (the surface tracks the TRUE conditional expectation well
    # while single-path noise is irreducible).
    for row in report.basis_rows:
        assert row.in_sample_r2_noisy < 0.6
        assert row.in_sample_r2_heavy > row.in_sample_r2_noisy


# --------------------------------------------------------------------------
# Basis sweep / selection / overfit
# --------------------------------------------------------------------------

def test_one_row_per_basis(report, small_cfg):
    keys = {(r.degree, r.max_interaction_order) for r in report.basis_rows}
    assert keys == set(small_cfg.basis_grid)
    assert len(report.basis_rows) == len(small_cfg.basis_grid)


def test_oos_metrics_finite_and_high(report):
    for row in report.basis_rows:
        assert np.isfinite(row.oos_rmse) and row.oos_rmse > 0
        assert np.isfinite(row.oos_r2)
        assert np.isfinite(row.oos_mae)
        assert np.isfinite(row.oos_max_abs_rel_error)
    # the OOS-best row clears the educational gate
    best = max(report.basis_rows, key=lambda r: r.oos_r2)
    assert best.oos_r2 > 0.9


def test_selection_optimises_metric(validator, small_cfg):
    rep = validator.validate(small_cfg, nested_n_outer=300, nested_n_inner=48)
    sel = rep.selected_row()
    # default metric is oos_rmse -> selected basis must have the minimum
    assert sel.oos_rmse == min(r.oos_rmse for r in rep.basis_rows)
    assert (sel.degree, sel.max_interaction_order) == (
        rep.selected_degree, rep.selected_max_interaction_order
    )


def test_selection_by_oos_r2_metric(validator):
    cfg = TriProxyValidationConfig(
        n_fit=400, n_validation=40, n_insample_heavy=20, n_inner_heavy=256,
        basis_grid=((1, 3), (2, 3), (3, 3)), selection_metric="oos_r2",
    )
    rep = validator.validate(cfg, nested_n_outer=300, nested_n_inner=48)
    sel = rep.selected_row()
    assert sel.oos_r2 == max(r.oos_r2 for r in rep.basis_rows)


def test_overfit_onset_consistent_with_rmse_profile(report):
    onset = report.overfit_onset_terms
    if onset is not None:
        ordered = sorted(report.basis_rows, key=lambda r: r.n_basis_terms)
        idx = next(i for i, r in enumerate(ordered) if r.n_basis_terms == onset)
        assert idx >= 1
        assert ordered[idx].oos_rmse > ordered[idx - 1].oos_rmse * 1.001


def test_basis_rows_ordered_by_complexity(report):
    terms = [r.n_basis_terms for r in report.basis_rows]
    assert terms == sorted(terms)


# --------------------------------------------------------------------------
# Capital comparison & leakage in the full report
# --------------------------------------------------------------------------

def test_capital_comparison_bounded(report):
    cc = report.capital_comparison
    assert isinstance(cc, CapitalComparison)
    assert 0.0 <= cc.var_rel_error < 1.0
    assert 0.0 <= cc.es_rel_error < 1.0
    assert np.isfinite(cc.scr_rel_error)
    assert cc.proxy_capital.var_liability > 0
    assert cc.nested_capital.var_liability > 0


def test_report_leakage_free(report):
    assert report.leakage.leakage_free is True
    assert report.leakage.n_exact_shared_states == 0


def test_verdict_pass_or_partial(report):
    assert report.verdict.startswith("PASS") or report.verdict.startswith("PARTIAL")


# --------------------------------------------------------------------------
# Reproducibility & serialisation
# --------------------------------------------------------------------------

def test_reproducible_digest(validator, small_cfg):
    r1 = validator.validate(small_cfg, nested_n_outer=300, nested_n_inner=48)
    r2 = validator.validate(small_cfg, nested_n_outer=300, nested_n_inner=48)
    assert r1.reproducibility_digest == r2.reproducibility_digest


def test_report_to_dict_and_json(report):
    d = report.to_dict()
    assert d["drivers"] == ["short_rate", "equity_level", "credit_spread"]
    assert d["selected_degree"] == report.selected_degree
    assert d["selected_max_interaction_order"] == report.selected_max_interaction_order
    assert "selected_row" in d and "basis_rows" in d
    assert len(d["basis_rows"]) == len(report.basis_rows)
    parsed = json.loads(report.to_json())
    assert parsed["reproducibility_digest"] == report.reproducibility_digest


def test_tri_basis_diagnostics_to_dict():
    row = TriBasisDiagnostics(
        degree=2, max_interaction_order=3, n_basis_terms=10,
        in_sample_r2_noisy=0.2, in_sample_r2_heavy=0.95,
        oos_rmse=1234.5, oos_r2=0.96, oos_mae=900.0,
        oos_max_abs_rel_error=0.05, overfit_gap=-0.01,
    )
    d = row.to_dict()
    assert d["degree"] == 2 and d["max_interaction_order"] == 3
    assert d["n_basis_terms"] == 10


# --------------------------------------------------------------------------
# Governance / use-restrictions
# --------------------------------------------------------------------------

def test_use_restrictions_structure():
    r = tri_proxy_validation_use_restrictions()
    assert "EDUCATIONAL ONLY" in r["classification"]
    assert "TRIVARIATE" in r["what_it_validates"]
    assert "credit" in r["residual_risk"].lower()
    assert any("Duffie" in s for s in r["standards"])


def test_use_restrictions_json_round_trip():
    parsed = json.loads(tri_proxy_validation_use_restrictions_json())
    assert parsed["module"].endswith("ThreeDriverProxyValidator")
