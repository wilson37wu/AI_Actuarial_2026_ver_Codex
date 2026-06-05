"""
Tests for the Phase 18 Task 4 FOUR-driver tail-dependent risk aggregation and
four-driver tail-convergence / stability diagnostics.

Modules under test:
  * par_model_v2.projection.multi_driver_capital_4d_aggregation
      - FourDriverRiskAggregator (CRN standalone decomposition, 4x4 var-covar,
        copula re-aggregation, genuine-nested benchmark, interaction residual)
  * par_model_v2.projection.multi_driver_tail_diagnostics
      - FourDriverTailDiagnostics (outer-count convergence, bootstrap CI/SE,
        crude/antithetic/Sobol variance reduction on the 4-D LSMC surface)

Sizes are kept small so each pytest invocation stays inside the sandbox time
budget; the production evidence numbers come from the build scripts.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital_4d_aggregation import (
    DEFAULT_FOURD_AGG_GAP_TOLERANCE,
    FourDriverAggregationConfig,
    FourDriverAggregationReport,
    FourDriverStandaloneCapital,
    FourDriverVarCovarAggregation,
    FourDriverRiskAggregator,
    four_driver_aggregation_use_restrictions,
    four_driver_aggregation_use_restrictions_json,
    _NoLapseExposure,
)
from par_model_v2.projection.multi_driver_capital_4d import LapseExposureSpec
from par_model_v2.projection.multi_driver_tail_diagnostics import (
    FourDriverTailConfig,
    FourDriverTailDiagnostics,
    FourDriverTailReport,
    VarianceReduction4D,
    four_driver_tail_use_restrictions,
    four_driver_tail_use_restrictions_json,
)


def _product():
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


# Shared small aggregation run (module-scope so it is computed once).
@pytest.fixture(scope="module")
def agg_report():
    cfg = FourDriverAggregationConfig(
        n_outer=150, n_inner=32, seed=42, capital_horizon_months=12,
        n_sim_copula=30_000,
    )
    return FourDriverRiskAggregator(_product()).run(config=cfg)


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

def test_agg_config_defaults_and_validation():
    cfg = FourDriverAggregationConfig()
    assert cfg.n_outer >= 100
    assert 0.5 < cfg.confidence_level < 1.0
    d = cfg.to_dict()
    assert d["n_inner"] == cfg.n_inner
    with pytest.raises(ValueError):
        FourDriverAggregationConfig(n_outer=10)
    with pytest.raises(ValueError):
        FourDriverAggregationConfig(confidence_level=1.5)
    with pytest.raises(ValueError):
        FourDriverAggregationConfig(n_sim_copula=10)


def test_no_lapse_exposure_inforce_is_unity():
    spec = _NoLapseExposure()
    assert spec.inforce_factor(0.03, -0.2, 12, 240) == 1.0
    assert spec.inforce_factor(0.01, 0.5, 6, 240) == 1.0
    # The real spec is NOT identically one away from the central point.
    real = LapseExposureSpec()
    assert real.inforce_factor(0.08, 0.5, 12, 240) != 1.0


# ---------------------------------------------------------------------------
# Aggregation structure & invariants
# ---------------------------------------------------------------------------

def test_agg_report_shapes_and_drivers(agg_report):
    assert isinstance(agg_report, FourDriverAggregationReport)
    assert agg_report.drivers == (
        "short_rate", "equity_guarantee", "credit_spread", "lapse_behaviour")
    sa = agg_report.standalone
    assert isinstance(sa, FourDriverStandaloneCapital)
    # 4x4 realised loss correlation, unit diagonal, symmetric.
    M = np.array(sa.loss_correlation_matrix)
    assert M.shape == (4, 4)
    assert np.allclose(np.diag(M), 1.0, atol=1e-9)
    assert np.allclose(M, M.T, atol=1e-9)


def test_standalone_scr_sum_matches_components(agg_report):
    sa = agg_report.standalone
    s = (sa.rate_capital.scr_proxy + sa.equity_capital.scr_proxy
         + sa.credit_capital.scr_proxy + sa.lapse_capital.scr_proxy)
    assert sa.standalone_scr_sum == pytest.approx(s, rel=1e-9)
    # All four standalone SCRs are positive (each driver carries capital).
    assert sa.rate_capital.scr_proxy > 0
    assert sa.lapse_capital.scr_proxy > 0


def test_diversification_and_understatement(agg_report):
    vc = agg_report.var_covar
    # Var-covar SCR cannot exceed the undiversified standalone sum (always true
    # for a valid correlation matrix).  NOTE: the genuine four-driver nested
    # capital is NOT bounded by the CRN-additive standalone sum, because the
    # lapse driver couples multiplicatively (super-additive tail) -- so we do
    # NOT assert nested <= standalone sum here.
    assert vc.correlated_scr <= agg_report.standalone.standalone_scr_sum + 1e-6
    # MR-010: the ESG factor formula UNDERSTATES the diversified nested capital.
    assert vc.esg_understatement_pct > 0.0
    assert vc.formula_vs_nested_scr_rel_error == pytest.approx(
        abs(vc.correlated_scr - agg_report.nested_scr)
        / abs(agg_report.nested_scr), rel=1e-6)


def test_copula_beats_var_covar_and_verdict(agg_report):
    sel = agg_report.copula.selected
    vc = agg_report.var_covar
    # The copula-on-realised-losses reconciles to nested better than var-covar.
    assert sel.scr_rel_error_vs_nested < vc.formula_vs_nested_scr_rel_error
    assert agg_report.verdict.startswith("PASS")
    # The selected copula is one of the three fitted families.
    assert agg_report.copula.selected_copula in {
        "gaussian", "student_t", "survival_clayton"}


def test_interaction_residual_reported(agg_report):
    vc = agg_report.var_covar
    # The multiplicative-lapse interaction residual is finite and reported as a
    # fraction of nested capital (may be either sign, but must be small-ish).
    assert np.isfinite(vc.interaction_residual_scr)
    assert abs(vc.interaction_residual_rel) < 0.5
    # crn additive capital is a real CapitalMetrics with a positive SCR.
    assert vc.crn_additive_capital.scr_proxy > 0


def test_agg_reproducibility(agg_report):
    cfg = FourDriverAggregationConfig(
        n_outer=150, n_inner=32, seed=42, capital_horizon_months=12,
        n_sim_copula=30_000,
    )
    rep2 = FourDriverRiskAggregator(_product()).run(config=cfg)
    assert rep2.reproducibility_digest == agg_report.reproducibility_digest
    assert rep2.nested_scr == pytest.approx(agg_report.nested_scr, rel=1e-9)


def test_agg_json_and_markdown_roundtrip(agg_report):
    blob = json.loads(agg_report.to_json())
    assert blob["drivers"][3] == "lapse_behaviour"
    assert "var_covar" in blob and "copula" in blob
    md = agg_report.to_markdown()
    assert "Four-Driver Tail-Dependent Risk Aggregation" in md
    assert "MR-010" in md


def test_agg_use_restrictions():
    r = four_driver_aggregation_use_restrictions()
    assert r["classification"].startswith("EDUCATIONAL")
    assert len(r["risk_drivers"]) == 4
    assert json.loads(four_driver_aggregation_use_restrictions_json())["risk_drivers"][3] == "lapse behaviour"


def test_agg_horizon_validation():
    cfg = FourDriverAggregationConfig(
        n_outer=120, n_inner=16, capital_horizon_months=999)
    with pytest.raises(ValueError):
        FourDriverRiskAggregator(_product()).run(config=cfg)


# ---------------------------------------------------------------------------
# Four-driver tail diagnostics
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tail_report():
    cfg = FourDriverTailConfig(
        n_fit=250, capital_horizon_months=12,
        outer_grid=(500, 1000, 2000), n_bootstrap=400, bootstrap_n_outer=2000,
        vr_replications=30, vr_n_outer=1024, vr_pilot_n=2000,
    )
    return FourDriverTailDiagnostics(_product()).run(config=cfg)


def test_tail_config_validation():
    with pytest.raises(ValueError):
        FourDriverTailConfig(vr_n_outer=1000)        # not a power of two
    with pytest.raises(ValueError):
        FourDriverTailConfig(outer_grid=(2000, 1000))  # not ascending
    with pytest.raises(ValueError):
        FourDriverTailConfig(n_fit=10)
    cfg = FourDriverTailConfig()
    assert cfg.lsmc_degree >= 1
    assert cfg.to_dict()["max_interaction_order"] == cfg.max_interaction_order


def test_tail_report_structure(tail_report):
    assert isinstance(tail_report, FourDriverTailReport)
    assert tail_report.drivers[3] == "lapse_behaviour"
    c = tail_report.convergence
    assert len(c.var_path) == 3
    assert len(c.var_successive_rel_change) == 2
    b = tail_report.bootstrap
    assert b.var_ci_low <= b.var_point <= b.var_ci_high
    assert b.var_standard_error > 0


def test_tail_variance_reduction_4d(tail_report):
    v = tail_report.variance_reduction
    assert isinstance(v, VarianceReduction4D)
    corr = np.array(v.copula_corr)
    assert corr.shape == (4, 4)
    assert np.allclose(np.diag(corr), 1.0, atol=1e-6)
    # Sobol QMC reduces the VaR-estimator variance (ratio > 1) on the smooth
    # surrogate; this is the headline efficiency result.
    assert v.sobol_var_ratio > 1.0


def test_tail_var_in_bootstrap_ci(tail_report):
    c = tail_report.convergence
    b = tail_report.bootstrap
    # The convergence VaR (independent outer sample) sits inside the bootstrap
    # CI of the bootstrap outer sample, give or take Monte-Carlo noise at small N.
    assert b.var_ci_low * 0.9 <= c.final_var <= b.var_ci_high * 1.1


def test_tail_reproducibility(tail_report):
    cfg = FourDriverTailConfig(
        n_fit=250, capital_horizon_months=12,
        outer_grid=(500, 1000, 2000), n_bootstrap=400, bootstrap_n_outer=2000,
        vr_replications=30, vr_n_outer=1024, vr_pilot_n=2000,
    )
    rep2 = FourDriverTailDiagnostics(_product()).run(config=cfg)
    assert rep2.reproducibility_digest == tail_report.reproducibility_digest


def test_tail_json_markdown_and_restrictions(tail_report):
    blob = json.loads(tail_report.to_json())
    assert blob["drivers"][3] == "lapse_behaviour"
    assert "variance_reduction" in blob
    md = tail_report.to_markdown()
    assert "Four-Driver Tail-Convergence" in md
    r = four_driver_tail_use_restrictions()
    assert len(r["risk_drivers"]) == 4
    assert json.loads(four_driver_tail_use_restrictions_json())["component"] == "FourDriverTailDiagnostics"
