"""Phase 17 Task 4 — three-driver (rate+equity+credit) tail-diagnostics tests.

Additive companion to ``tests/test_phase15_tail_diagnostics.py`` for the
two-driver suite.  Exercises the credit-augmented trivariate LSMC surface
tail diagnostics: outer-count convergence, bootstrap CI, variance reduction,
the 3x3 copula-correlation surrogate, reproducibility, and serialization.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_capital_3d import (
    CreditExposureSpec,
    ThreeDriverCorrelation,
)
from par_model_v2.stochastic.credit_spread import CreditSpreadParams
from par_model_v2.stochastic.esg_process import GBMParams, HullWhiteParams
from par_model_v2.projection.multi_driver_tail_diagnostics import (
    BootstrapInterval,
    OuterConvergence,
    SchemeVariance,
    ThreeDriverTailConfig,
    ThreeDriverTailDiagnostics,
    ThreeDriverTailReport,
    VarianceReduction3D,
    _correlate_nd,
    _draw_normals_nd,
    _nearest_correlation_matrix,
    _states_from_normals_nd,
    _var_es,
    three_driver_tail_use_restrictions,
    three_driver_tail_use_restrictions_json,
)


# ---------------------------------------------------------------------------
# Fixtures — one report shared across the suite (the run is the expensive part)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def product():
    return ParEndowmentProduct(
        term_years=10, issue_age=40, gender="M",
        sum_assured=100_000, annual_premium=6_000,
    )


@pytest.fixture(scope="module")
def fast_cfg():
    return ThreeDriverTailConfig(
        n_fit=300, outer_grid=(400, 800, 1_600),
        n_bootstrap=200, bootstrap_n_outer=1_500,
        vr_replications=30, vr_n_outer=512, vr_pilot_n=1_500, seed=42,
    )


@pytest.fixture(scope="module")
def engine(product):
    return ThreeDriverTailDiagnostics(
        product, HullWhiteParams(), GBMParams(rate_equity_correlation=-0.15),
        CreditSpreadParams(), ThreeDriverCorrelation(),
        equity_guarantee=EquityGuaranteeSpec(guarantee_rate=1.0),
        credit_exposure=CreditExposureSpec(exposure_rate=1.0),
    )


@pytest.fixture(scope="module")
def report(engine, fast_cfg):
    return engine.run(fast_cfg)


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

def test_config_defaults_valid():
    cfg = ThreeDriverTailConfig()
    assert cfg.vr_n_outer & (cfg.vr_n_outer - 1) == 0
    assert list(cfg.outer_grid) == sorted(cfg.outer_grid)
    assert cfg.max_interaction_order >= 0


@pytest.mark.parametrize("kwargs", [
    {"n_fit": 10},
    {"lsmc_degree": 0},
    {"max_interaction_order": -1},
    {"confidence_level": 1.0},
    {"outer_grid": (1_000,)},
    {"outer_grid": (2_000, 1_000)},
    {"convergence_tol": 0.0},
    {"n_bootstrap": 10},
    {"vr_replications": 1},
    {"vr_n_outer": 1_000},
    {"vr_n_outer": 32},
    {"vr_pilot_n": 10},
])
def test_config_rejects_bad_inputs(kwargs):
    with pytest.raises(ValueError):
        ThreeDriverTailConfig(**kwargs)


def test_config_round_trip(fast_cfg):
    d = fast_cfg.to_dict()
    assert d["vr_n_outer"] == 512
    assert d["outer_measure"] == "P"
    assert "max_interaction_order" in d


# ---------------------------------------------------------------------------
# N-dimensional sampling-scheme + copula primitives
# ---------------------------------------------------------------------------

def test_crude_normals_nd_shape_and_seed():
    a = _draw_normals_nd("crude", 256, 3, seed=1)
    b = _draw_normals_nd("crude", 256, 3, seed=1)
    c = _draw_normals_nd("crude", 256, 3, seed=2)
    assert a.shape == (256, 3)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_antithetic_nd_is_balanced():
    z = _draw_normals_nd("antithetic", 256, 3, seed=3)
    assert z.shape == (256, 3)
    assert np.allclose(z.sum(axis=0), 0.0, atol=1e-9)


def test_sobol_nd_uniform_coverage():
    z = _draw_normals_nd("sobol", 1_024, 3, seed=4)
    assert z.shape == (1_024, 3)
    from scipy import stats
    u = stats.norm.cdf(z)
    assert abs(u.mean() - 0.5) < 0.02


def test_draw_normals_nd_unknown_scheme_raises():
    with pytest.raises(ValueError):
        _draw_normals_nd("halton", 128, 3, seed=0)


def test_draw_normals_nd_bad_dim_raises():
    with pytest.raises(ValueError):
        _draw_normals_nd("crude", 128, 0, seed=0)


def test_nearest_correlation_matrix_repairs_non_pd():
    bad = np.array([[1.0, 0.95, -0.95],
                    [0.95, 1.0, 0.95],
                    [-0.95, 0.95, 1.0]])
    C = _nearest_correlation_matrix(bad)
    w = np.linalg.eigvalsh(C)
    assert np.all(w > -1e-10)                    # positive semidefinite
    assert np.allclose(np.diag(C), 1.0)


def test_correlate_nd_induces_target_correlation():
    rng = np.random.default_rng(0)
    z = rng.standard_normal((200_000, 3))
    target = np.array([[1.0, -0.3, -0.2],
                       [-0.3, 1.0, -0.25],
                       [-0.2, -0.25, 1.0]])
    w = _correlate_nd(z, target)
    emp = np.corrcoef(w, rowvar=False)
    assert emp[0, 1] == pytest.approx(-0.3, abs=0.01)
    assert emp[0, 2] == pytest.approx(-0.2, abs=0.01)
    assert emp[1, 2] == pytest.approx(-0.25, abs=0.01)


def test_states_from_normals_nd_reproduces_pilot_margins():
    rng = np.random.default_rng(1)
    m0 = np.sort(rng.normal(0.03, 0.01, 5_000))
    m1 = np.sort(rng.lognormal(4.6, 0.2, 5_000))
    m2 = np.sort(rng.gamma(2.0, 0.01, 5_000))
    z = rng.standard_normal((20_000, 3))
    states = _states_from_normals_nd(z, (m0, m1, m2))
    assert states.shape == (20_000, 3)
    assert np.median(states[:, 0]) == pytest.approx(np.median(m0), abs=5e-4)
    assert np.median(states[:, 1]) == pytest.approx(np.median(m1), rel=0.05)
    assert np.median(states[:, 2]) == pytest.approx(np.median(m2), rel=0.05)


def test_states_from_normals_nd_dim_mismatch_raises():
    z = np.zeros((10, 2))
    with pytest.raises(ValueError):
        _states_from_normals_nd(z, (np.arange(5.0), np.arange(5.0), np.arange(5.0)))


# ---------------------------------------------------------------------------
# End-to-end report structure
# ---------------------------------------------------------------------------

def test_report_types(report):
    assert isinstance(report, ThreeDriverTailReport)
    assert isinstance(report.convergence, OuterConvergence)
    assert isinstance(report.bootstrap, BootstrapInterval)
    assert isinstance(report.variance_reduction, VarianceReduction3D)
    assert report.verdict.startswith(("PASS", "PARTIAL"))


def test_report_drivers_are_three(report):
    assert report.drivers == ("short_rate", "equity_level", "credit_spread")
    assert report.lsmc_summary["drivers"] == ["short_rate", "equity_level", "credit_spread"]


def test_convergence_paths_aligned(report, fast_cfg):
    c = report.convergence
    assert c.n_outer_grid == fast_cfg.outer_grid
    assert len(c.var_path) == len(fast_cfg.outer_grid)
    assert len(c.var_successive_rel_change) == len(fast_cfg.outer_grid) - 1
    assert c.recommended_n_outer in fast_cfg.outer_grid
    assert c.final_var == report.convergence.var_path[-1]


def test_bootstrap_ci_orders_and_brackets_point(report):
    b = report.bootstrap
    assert b.var_ci_low <= b.var_point <= b.var_ci_high
    assert b.es_ci_low <= b.es_point <= b.es_ci_high
    assert b.var_standard_error > 0
    assert b.var_ci_rel_halfwidth >= 0


def test_es_at_least_var(report):
    assert report.bootstrap.es_point >= report.bootstrap.var_point
    assert report.convergence.final_es >= report.convergence.final_var


# ---------------------------------------------------------------------------
# Variance reduction (three-driver copula)
# ---------------------------------------------------------------------------

def test_variance_reduction_schemes_present(report, fast_cfg):
    vr = report.variance_reduction
    assert {vr.crude.scheme, vr.antithetic.scheme, vr.sobol.scheme} == {
        "crude", "antithetic", "sobol"}
    for s in (vr.crude, vr.antithetic, vr.sobol):
        assert isinstance(s, SchemeVariance)
        assert s.n_replications == fast_cfg.vr_replications
        assert s.var_std > 0


def test_copula_corr_is_3x3_symmetric_unit_diagonal(report):
    C = np.asarray(report.variance_reduction.copula_corr, dtype=float)
    assert C.shape == (3, 3)
    assert np.allclose(np.diag(C), 1.0)
    assert np.allclose(C, C.T)
    # governed defaults: all three off-diagonals are negative
    assert C[0, 1] < 0 and C[0, 2] < 0 and C[1, 2] < 0


def test_schemes_estimate_same_var_mean(report):
    vr = report.variance_reduction
    means = [vr.crude.var_mean, vr.antithetic.var_mean, vr.sobol.var_mean]
    assert max(means) - min(means) < 0.03 * abs(vr.crude.var_mean)


def test_sobol_reduces_variance(report):
    # QMC on a smooth low-dimensional integrand should beat crude MC
    assert report.variance_reduction.sobol_var_ratio > 1.0


def test_variance_ratios_finite_positive(report):
    vr = report.variance_reduction
    for r in (vr.antithetic_var_ratio, vr.sobol_var_ratio,
              vr.antithetic_es_ratio, vr.sobol_es_ratio):
        assert np.isfinite(r) and r > 0


# ---------------------------------------------------------------------------
# Reproducibility & serialization
# ---------------------------------------------------------------------------

def test_reproducible_digest(engine, fast_cfg):
    a = engine.run(fast_cfg)
    b = engine.run(fast_cfg)
    assert a.reproducibility_digest == b.reproducibility_digest
    assert a.convergence.var_path == b.convergence.var_path
    assert a.variance_reduction.sobol.var_std == b.variance_reduction.sobol.var_std
    assert a.variance_reduction.copula_corr == b.variance_reduction.copula_corr


def test_report_json_round_trip(report):
    d = json.loads(report.to_json())
    assert d["verdict"] == report.verdict
    assert d["drivers"] == list(report.drivers)
    assert d["convergence"]["recommended_n_outer"] == report.convergence.recommended_n_outer
    assert "variance_reduction" in d
    assert len(d["variance_reduction"]["copula_corr"]) == 3
    assert d["bootstrap"]["var_point"] == round(report.bootstrap.var_point, 4)


def test_report_markdown_contains_sections(report):
    md = report.to_markdown()
    assert "Three-Driver" in md
    assert "Outer-count convergence" in md
    assert "Bootstrap" in md
    assert "Variance reduction" in md
    assert "Sobol" in md
    assert "credit_spread" in md


# ---------------------------------------------------------------------------
# Governance disclosure
# ---------------------------------------------------------------------------

def test_use_restrictions_structure():
    r = three_driver_tail_use_restrictions()
    assert "EDUCATIONAL ONLY" in r["classification"]
    assert "SOA ASOP 56 §3.5" in r["standards"]
    assert "variance_reduction_surrogate" in r
    assert "credit" in r["scope"].lower()
    assert json.loads(three_driver_tail_use_restrictions_json())["module"].startswith(
        "par_model_v2/projection/multi_driver_tail_diagnostics.py")


def test_horizon_must_be_inside_term(product):
    eng = ThreeDriverTailDiagnostics(
        product, equity_guarantee=EquityGuaranteeSpec(1.0),
        credit_exposure=CreditExposureSpec(1.0),
    )
    bad = ThreeDriverTailConfig(capital_horizon_months=10_000, n_fit=60,
                                outer_grid=(200, 400), n_bootstrap=100,
                                bootstrap_n_outer=200, vr_replications=10,
                                vr_n_outer=64, vr_pilot_n=200)
    with pytest.raises(ValueError):
        eng.run(bad)
