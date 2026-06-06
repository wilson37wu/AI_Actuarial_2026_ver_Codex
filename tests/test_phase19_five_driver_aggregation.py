"""
Tests for the Phase 19 Task 4 FIVE-driver tail-dependent risk aggregation
(rates + equity + credit-spread + lapse-behaviour + mortality-trend).

Module under test:
  * par_model_v2.projection.multi_driver_capital_5d_aggregation

Coverage:
  * config defaults + validation guards
  * _NoLapseExposure / _NoMortalityExposure switch their drivers OFF
  * report shape: five standalone SCRs, 5x5 loss-correlation, drivers tuple
  * standalone SCR sum == sum of component SCRs
  * mortality is a SMALL, orthogonal driver (smallest standalone SCR; near-zero
    ESG off-diagonals)
  * var-covar understatement (MR-010) is reported and the copula reconciles to
    nested better than the var-covar formula (verdict PASS)
  * CRN multiplicative interaction residual reported (lapse x mortality on the
    guaranteed leg)
  * reproducibility: identical config -> identical digest
  * JSON / Markdown round-trip + governance use-restrictions structure
  * horizon validation guard

Sizes are kept modest so each pytest invocation stays inside the sandbox budget.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital_5d_aggregation import (
    DEFAULT_FIVED_AGG_GAP_TOLERANCE,
    FiveDriverAggregationConfig,
    FiveDriverRiskAggregator,
    FiveDriverStandaloneCapital,
    FiveDriverVarCovarAggregation,
    FiveDriverAggregationReport,
    _NoLapseExposure,
    _NoMortalityExposure,
    five_driver_aggregation_use_restrictions,
    five_driver_aggregation_use_restrictions_json,
)


def _product():
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


@pytest.fixture(scope="module")
def agg_report():
    cfg = FiveDriverAggregationConfig(
        n_outer=120, n_inner=24, seed=42, n_sim_copula=20_000,
    )
    return FiveDriverRiskAggregator(_product()).run(config=cfg)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_agg_config_defaults_and_validation():
    cfg = FiveDriverAggregationConfig()
    assert cfg.n_outer >= 100
    assert cfg.aggregation_gap_tolerance == DEFAULT_FIVED_AGG_GAP_TOLERANCE
    assert 0.5 < cfg.confidence_level < 1.0
    with pytest.raises(ValueError):
        FiveDriverAggregationConfig(n_outer=10)
    with pytest.raises(ValueError):
        FiveDriverAggregationConfig(confidence_level=1.5)
    with pytest.raises(ValueError):
        FiveDriverAggregationConfig(n_sim_copula=10)
    with pytest.raises(ValueError):
        FiveDriverAggregationConfig(capital_horizon_months=0)
    d = cfg.to_dict()
    assert d["n_outer"] == cfg.n_outer and "outer_measure" in d


# ---------------------------------------------------------------------------
# Driver-OFF switches
# ---------------------------------------------------------------------------

def test_no_lapse_exposure_inforce_is_unity():
    off = _NoLapseExposure()
    assert off.inforce_factor(0.03, 0.5, 12, 240) == 1.0
    assert off.inforce_factor(-0.01, -0.4, 60, 240) == 1.0


def test_no_mortality_exposure_multiplier_is_unity():
    off = _NoMortalityExposure()
    # Mortality OFF => multiplier is identically 1.0 for any trend state.
    assert off.multiplier(0.0) == 1.0
    assert off.multiplier(0.5) == 1.0
    assert off.multiplier(-0.5) == 1.0


# ---------------------------------------------------------------------------
# Report structure
# ---------------------------------------------------------------------------

def test_agg_report_shapes_and_drivers(agg_report):
    rep = agg_report
    assert isinstance(rep, FiveDriverAggregationReport)
    assert rep.drivers == (
        "short_rate", "equity_guarantee", "credit_spread",
        "lapse_behaviour", "mortality_trend",
    )
    sa = rep.standalone
    assert isinstance(sa, FiveDriverStandaloneCapital)
    # five standalone capitals present
    for cap in (sa.rate_capital, sa.equity_capital, sa.credit_capital,
                sa.lapse_capital, sa.mortality_capital):
        assert cap.scr_proxy >= 0.0
    # 5x5 realised-loss correlation
    lc = np.array(sa.loss_correlation_matrix)
    assert lc.shape == (5, 5)
    assert np.allclose(np.diag(lc), 1.0, atol=1e-6)
    # 5x5 ESG correlation
    esg = np.array(rep.var_covar.esg_correlation_matrix)
    assert esg.shape == (5, 5)


def test_standalone_scr_sum_matches_components(agg_report):
    sa = agg_report.standalone
    expected = (
        sa.rate_capital.scr_proxy + sa.equity_capital.scr_proxy
        + sa.credit_capital.scr_proxy + sa.lapse_capital.scr_proxy
        + sa.mortality_capital.scr_proxy
    )
    assert sa.standalone_scr_sum == pytest.approx(expected, rel=1e-9)
    assert np.allclose(
        sa.scr_vector(),
        [sa.rate_capital.scr_proxy, sa.equity_capital.scr_proxy,
         sa.credit_capital.scr_proxy, sa.lapse_capital.scr_proxy,
         sa.mortality_capital.scr_proxy],
    )


def test_mortality_is_small_orthogonal_driver(agg_report):
    """Mortality trend is non-financial and orthogonal: smallest standalone SCR
    and (near-)zero ESG off-diagonals in its row/column."""
    sa = agg_report.standalone
    scrs = {
        "rate": sa.rate_capital.scr_proxy,
        "equity": sa.equity_capital.scr_proxy,
        "credit": sa.credit_capital.scr_proxy,
        "lapse": sa.lapse_capital.scr_proxy,
        "mortality": sa.mortality_capital.scr_proxy,
    }
    assert scrs["mortality"] == min(scrs.values())
    esg = np.array(agg_report.var_covar.esg_correlation_matrix)
    # mortality is index 4; default 5x5 has zero couplings to financial drivers
    assert np.allclose(esg[4, :4], 0.0, atol=1e-9)
    assert np.allclose(esg[:4, 4], 0.0, atol=1e-9)
    assert esg[4, 4] == pytest.approx(1.0)


def test_diversification_and_understatement(agg_report):
    vc = agg_report.var_covar
    # var-covar SCR cannot exceed the undiversified standalone sum
    assert vc.correlated_scr <= agg_report.standalone.standalone_scr_sum + 1e-6
    assert vc.correlation_matrix_passed
    # MR-010: ESG-factor var-covar understates the diversified nested capital
    assert vc.esg_understatement_pct > 0.0
    assert vc.correlated_scr < agg_report.nested_scr
    assert vc.diversification_benefit_formula >= 0.0


def test_copula_beats_var_covar_and_verdict(agg_report):
    rep = agg_report
    sel = rep.copula.selected
    assert sel.scr_rel_error_vs_nested < rep.var_covar.formula_vs_nested_scr_rel_error
    assert rep.verdict.startswith("PASS")
    assert "five-driver" in rep.verdict


def test_interaction_residual_reported(agg_report):
    vc = agg_report.var_covar
    # The CRN additive split leaves a non-trivial multiplicative interaction
    # residual (lapse x equity and lapse x mortality on the guaranteed leg).
    assert vc.crn_additive_capital.scr_proxy > 0.0
    assert abs(vc.interaction_residual_rel) > 1e-4
    expected = vc.crn_additive_capital.scr_proxy - agg_report.nested_scr
    assert vc.interaction_residual_scr == pytest.approx(expected, rel=1e-6)


def test_agg_reproducibility():
    cfg = FiveDriverAggregationConfig(
        n_outer=110, n_inner=16, seed=7, n_sim_copula=15_000,
    )
    rep1 = FiveDriverRiskAggregator(_product()).run(config=cfg)
    rep2 = FiveDriverRiskAggregator(_product()).run(config=cfg)
    assert rep1.reproducibility_digest == rep2.reproducibility_digest
    assert rep1.nested_scr == pytest.approx(rep2.nested_scr, rel=1e-12)


def test_agg_json_and_markdown_roundtrip(agg_report):
    rep = agg_report
    obj = json.loads(rep.to_json())
    assert obj["verdict"] == rep.verdict
    assert len(obj["drivers"]) == 5
    assert "mortality_capital" in obj["standalone"]
    md = rep.to_markdown()
    assert "# Phase 19 Task 4" in md
    assert "Mortality trend" in md


def test_agg_use_restrictions():
    r = five_driver_aggregation_use_restrictions()
    assert r["classification"].startswith("EDUCATIONAL")
    assert "mortality trend" in r["risk_drivers"]
    assert len(r["risk_drivers"]) == 5
    parsed = json.loads(five_driver_aggregation_use_restrictions_json())
    assert parsed["module"].endswith("multi_driver_capital_5d_aggregation.py")


def test_agg_horizon_validation():
    cfg = FiveDriverAggregationConfig(
        n_outer=100, n_inner=8, capital_horizon_months=10_000,
    )
    with pytest.raises(ValueError):
        FiveDriverRiskAggregator(_product()).run(config=cfg)
