"""Phase 15 Task 4 — tail-convergence & stability diagnostics tests."""

from __future__ import annotations

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_tail_diagnostics import (
    BootstrapInterval,
    MultiDriverTailDiagnostics,
    OuterConvergence,
    SchemeVariance,
    TailDiagnosticsConfig,
    TailDiagnosticsReport,
    VarianceReduction,
    _correlate,
    _draw_normals,
    _states_from_normals,
    _var_es,
    tail_diagnostics_use_restrictions,
    tail_diagnostics_use_restrictions_json,
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
    return TailDiagnosticsConfig(
        n_fit=300, outer_grid=(400, 800, 1_600),
        n_bootstrap=200, bootstrap_n_outer=1_500,
        vr_replications=30, vr_n_outer=512, vr_pilot_n=1_500, seed=42,
    )


@pytest.fixture(scope="module")
def report(product, fast_cfg):
    eng = MultiDriverTailDiagnostics(product, equity_guarantee=EquityGuaranteeSpec(1.0))
    return eng.run(fast_cfg)


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

def test_config_defaults_valid():
    cfg = TailDiagnosticsConfig()
    assert cfg.vr_n_outer & (cfg.vr_n_outer - 1) == 0     # power of two
    assert list(cfg.outer_grid) == sorted(cfg.outer_grid)


@pytest.mark.parametrize("kwargs", [
    {"n_fit": 10},
    {"lsmc_degree": 0},
    {"confidence_level": 1.0},
    {"outer_grid": (1_000,)},
    {"outer_grid": (2_000, 1_000)},
    {"outer_grid": (0, 100)},
    {"convergence_tol": 0.0},
    {"n_bootstrap": 10},
    {"vr_replications": 1},
    {"vr_n_outer": 1_000},        # not a power of two
    {"vr_n_outer": 32},           # too small
    {"vr_pilot_n": 10},
])
def test_config_rejects_bad_inputs(kwargs):
    with pytest.raises(ValueError):
        TailDiagnosticsConfig(**kwargs)


def test_config_round_trip(fast_cfg):
    d = fast_cfg.to_dict()
    assert d["vr_n_outer"] == 512
    assert d["outer_measure"] == "P"


# ---------------------------------------------------------------------------
# _var_es helper
# ---------------------------------------------------------------------------

def test_var_es_upper_tail():
    x = np.arange(0.0, 1_000.0)
    var, es = _var_es(x, 0.995)
    assert var == pytest.approx(np.quantile(x, 0.995))
    assert es >= var            # ES is the mean beyond VaR on the upper tail


def test_var_es_constant_sample():
    x = np.full(500, 42.0)
    var, es = _var_es(x, 0.995)
    assert var == pytest.approx(42.0)
    assert es == pytest.approx(42.0)


# ---------------------------------------------------------------------------
# Sampling-scheme drivers
# ---------------------------------------------------------------------------

def test_crude_normals_shape_and_seed():
    a = _draw_normals("crude", 256, seed=1)
    b = _draw_normals("crude", 256, seed=1)
    c = _draw_normals("crude", 256, seed=2)
    assert a.shape == (256, 2)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_antithetic_is_balanced():
    z = _draw_normals("antithetic", 256, seed=3)
    assert z.shape == (256, 2)
    # exact antithetic pairing -> column sums cancel to ~0
    assert np.allclose(z.sum(axis=0), 0.0, atol=1e-9)


def test_sobol_uniform_coverage():
    z = _draw_normals("sobol", 1_024, seed=4)
    assert z.shape == (1_024, 2)
    # mapped back to uniforms, a scrambled Sobol net is near-uniform on [0,1]^2
    from scipy import stats
    u = stats.norm.cdf(z)
    assert abs(u.mean() - 0.5) < 0.02


def test_unknown_scheme_raises():
    with pytest.raises(ValueError):
        _draw_normals("halton", 128, seed=0)


# ---------------------------------------------------------------------------
# Copula surrogate primitives
# ---------------------------------------------------------------------------

def test_correlate_induces_target_correlation():
    rng = np.random.default_rng(0)
    z = rng.standard_normal((200_000, 2))
    w = _correlate(z, -0.3)
    rho = np.corrcoef(w[:, 0], w[:, 1])[0, 1]
    assert rho == pytest.approx(-0.3, abs=0.01)
    # marginals stay standard normal
    assert w[:, 1].std() == pytest.approx(1.0, abs=0.01)


def test_states_from_normals_reproduce_pilot_margins():
    rng = np.random.default_rng(1)
    r_pilot = np.sort(rng.normal(0.03, 0.01, 5_000))
    s_pilot = np.sort(rng.lognormal(4.6, 0.2, 5_000))
    z = rng.standard_normal((20_000, 2))
    states = _states_from_normals(z, r_pilot, s_pilot)
    # surrogate margin medians match the pilot medians (empirical inverse CDF)
    assert np.median(states[:, 0]) == pytest.approx(np.median(r_pilot), abs=5e-4)
    assert np.median(states[:, 1]) == pytest.approx(np.median(s_pilot), rel=0.05)


# ---------------------------------------------------------------------------
# End-to-end report structure
# ---------------------------------------------------------------------------

def test_report_types(report):
    assert isinstance(report, TailDiagnosticsReport)
    assert isinstance(report.convergence, OuterConvergence)
    assert isinstance(report.bootstrap, BootstrapInterval)
    assert isinstance(report.variance_reduction, VarianceReduction)
    assert report.verdict.startswith(("PASS", "PARTIAL"))


def test_convergence_paths_aligned(report, fast_cfg):
    c = report.convergence
    assert c.n_outer_grid == fast_cfg.outer_grid
    assert len(c.var_path) == len(fast_cfg.outer_grid)
    assert len(c.var_successive_rel_change) == len(fast_cfg.outer_grid) - 1
    assert c.recommended_n_outer in fast_cfg.outer_grid
    assert c.final_var == report.convergence.var_path[-1]


def test_convergence_recommended_is_first_below_tol(report, fast_cfg):
    c = report.convergence
    if c.converged:
        # the recommended N is the grid point at which change first dips below tol
        for i, ch in enumerate(c.var_successive_rel_change):
            if ch <= fast_cfg.convergence_tol:
                assert c.recommended_n_outer == fast_cfg.outer_grid[i + 1]
                break


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
# Variance reduction
# ---------------------------------------------------------------------------

def test_variance_reduction_schemes_present(report, fast_cfg):
    vr = report.variance_reduction
    assert {vr.crude.scheme, vr.antithetic.scheme, vr.sobol.scheme} == {
        "crude", "antithetic", "sobol"}
    for s in (vr.crude, vr.antithetic, vr.sobol):
        assert isinstance(s, SchemeVariance)
        assert s.n_replications == fast_cfg.vr_replications
        assert s.var_std > 0


def test_schemes_estimate_same_var_mean(report):
    # all three schemes are unbiased for the same VaR -> means agree closely
    vr = report.variance_reduction
    means = [vr.crude.var_mean, vr.antithetic.var_mean, vr.sobol.var_mean]
    assert max(means) - min(means) < 0.02 * abs(vr.crude.var_mean)


def test_sobol_reduces_variance(report):
    # QMC on a smooth 2-D integrand should beat crude MC
    assert report.variance_reduction.sobol_var_ratio > 1.0


def test_variance_ratios_finite_positive(report):
    vr = report.variance_reduction
    for r in (vr.antithetic_var_ratio, vr.sobol_var_ratio,
              vr.antithetic_es_ratio, vr.sobol_es_ratio):
        assert np.isfinite(r) and r > 0


# ---------------------------------------------------------------------------
# Reproducibility & serialization
# ---------------------------------------------------------------------------

def test_reproducible_digest(product, fast_cfg):
    eng = MultiDriverTailDiagnostics(product, equity_guarantee=EquityGuaranteeSpec(1.0))
    a = eng.run(fast_cfg)
    b = eng.run(fast_cfg)
    assert a.reproducibility_digest == b.reproducibility_digest
    assert a.convergence.var_path == b.convergence.var_path
    assert a.variance_reduction.sobol.var_std == b.variance_reduction.sobol.var_std


def test_report_json_round_trip(report):
    d = json.loads(report.to_json())
    assert d["verdict"] == report.verdict
    assert d["convergence"]["recommended_n_outer"] == report.convergence.recommended_n_outer
    assert "variance_reduction" in d
    assert d["bootstrap"]["var_point"] == round(report.bootstrap.var_point, 4)


def test_report_markdown_contains_sections(report):
    md = report.to_markdown()
    assert "Outer-count convergence" in md
    assert "Bootstrap" in md
    assert "Variance reduction" in md
    assert "Sobol" in md


# ---------------------------------------------------------------------------
# Governance disclosure
# ---------------------------------------------------------------------------

def test_use_restrictions_structure():
    r = tail_diagnostics_use_restrictions()
    assert "EDUCATIONAL ONLY" in r["classification"]
    assert "SOA ASOP 56 §3.5" in r["standards"]
    assert "variance_reduction_surrogate" in r
    assert json.loads(tail_diagnostics_use_restrictions_json())["module"].endswith(
        "multi_driver_tail_diagnostics.py")


def test_horizon_must_be_inside_term(product):
    eng = MultiDriverTailDiagnostics(product, equity_guarantee=EquityGuaranteeSpec(1.0))
    bad = TailDiagnosticsConfig(capital_horizon_months=10_000, n_fit=60,
                                outer_grid=(200, 400), n_bootstrap=100,
                                bootstrap_n_outer=200, vr_replications=10,
                                vr_n_outer=64, vr_pilot_n=200)
    with pytest.raises(ValueError):
        eng.run(bad)
