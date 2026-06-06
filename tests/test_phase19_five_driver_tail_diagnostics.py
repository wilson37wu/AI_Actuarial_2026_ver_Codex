"""
Tests for the Phase 19 Task 4 (remaining) FIVE-driver tail-convergence and
stability diagnostics:
      - FiveDriverTailDiagnostics (outer-count convergence, bootstrap CI/SE,
        crude/antithetic/Sobol variance reduction) on the Phase 19 Task 3
        quintivariate (rate+equity+credit+lapse+mortality) LSMC surface.

Sizes are kept modest so each pytest invocation stays inside the sandbox budget.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_tail_diagnostics import (
    FiveDriverTailConfig,
    FiveDriverTailDiagnostics,
    FiveDriverTailReport,
    VarianceReduction5D,
    five_driver_tail_use_restrictions,
    five_driver_tail_use_restrictions_json,
)


def _product():
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


_LIGHT_KW = dict(
    n_fit=250, capital_horizon_months=12,
    outer_grid=(500, 1000, 2000), n_bootstrap=400, bootstrap_n_outer=2000,
    vr_replications=30, vr_n_outer=1024, vr_pilot_n=2000,
)


@pytest.fixture(scope="module")
def tail_report():
    return FiveDriverTailDiagnostics(_product()).run(config=FiveDriverTailConfig(**_LIGHT_KW))


def test_tail_config_validation():
    with pytest.raises(ValueError):
        FiveDriverTailConfig(vr_n_outer=1000)         # not a power of two
    with pytest.raises(ValueError):
        FiveDriverTailConfig(outer_grid=(2000, 1000))  # not ascending
    with pytest.raises(ValueError):
        FiveDriverTailConfig(n_fit=10)
    cfg = FiveDriverTailConfig()
    assert cfg.lsmc_degree >= 1
    assert cfg.to_dict()["max_interaction_order"] == cfg.max_interaction_order
    assert cfg.to_dict()["outer_grid"] == list(cfg.outer_grid)


def test_tail_report_structure(tail_report):
    assert isinstance(tail_report, FiveDriverTailReport)
    assert len(tail_report.drivers) == 5
    assert tail_report.drivers[3] == "lapse_behaviour"
    assert tail_report.drivers[4] == "mortality_trend"
    c = tail_report.convergence
    assert len(c.var_path) == 3
    assert len(c.var_successive_rel_change) == 2
    b = tail_report.bootstrap
    assert b.var_ci_low <= b.var_point <= b.var_ci_high
    assert b.var_standard_error > 0
    assert tail_report.verdict.startswith(("PASS", "PARTIAL"))


def test_tail_variance_reduction_5d(tail_report):
    v = tail_report.variance_reduction
    assert isinstance(v, VarianceReduction5D)
    corr = np.array(v.copula_corr)
    assert corr.shape == (5, 5)
    assert np.allclose(np.diag(corr), 1.0, atol=1e-6)
    assert np.allclose(corr, corr.T, atol=1e-6)
    # Sobol QMC reduces the VaR-estimator variance (ratio > 1) on the smooth
    # surrogate; this is the headline efficiency result.
    assert v.sobol_var_ratio > 1.0


def test_tail_var_in_bootstrap_ci(tail_report):
    c = tail_report.convergence
    b = tail_report.bootstrap
    # The convergence VaR (independent outer sample) sits inside the bootstrap
    # CI of the bootstrap outer sample, give or take Monte-Carlo noise at small N.
    assert b.var_ci_low * 0.9 <= c.final_var <= b.var_ci_high * 1.1


def test_tail_mortality_is_second_nonfinancial_axis(tail_report):
    # mortality-trend outer state is near-orthogonal to the financial drivers
    # (rate, equity, credit) AND to lapse in the realised outer-state corr.
    corr = np.array(tail_report.variance_reduction.copula_corr)
    mort_offdiag = np.abs(corr[4, :4])
    assert float(mort_offdiag.max()) < 0.25


def test_tail_reproducibility():
    rep1 = FiveDriverTailDiagnostics(_product()).run(config=FiveDriverTailConfig(**_LIGHT_KW))
    rep2 = FiveDriverTailDiagnostics(_product()).run(config=FiveDriverTailConfig(**_LIGHT_KW))
    assert rep1.reproducibility_digest == rep2.reproducibility_digest


def test_tail_json_markdown_and_restrictions(tail_report):
    blob = json.loads(tail_report.to_json())
    assert blob["drivers"][4] == "mortality_trend"
    assert "variance_reduction" in blob
    assert "convergence" in blob and "bootstrap" in blob
    md = tail_report.to_markdown()
    assert "Five-Driver Tail-Convergence" in md
    r = five_driver_tail_use_restrictions()
    assert len(r["risk_drivers"]) == 5
    assert json.loads(five_driver_tail_use_restrictions_json())["component"] == "FiveDriverTailDiagnostics"
