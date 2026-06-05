"""
Tests for Phase 17 Task 3 — three-driver (rate + equity + credit-spread)
correlated risk aggregation
(``par_model_v2.projection.multi_driver_risk_aggregation`` three-driver API).

Sizes are kept modest so each pytest invocation stays inside the sandbox time
budget.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_capital_3d import (
    CreditExposureSpec,
    ThreeDriverCorrelation,
    _inner_pathwise_pvs_3d,
    _outer_states_3d,
)
from par_model_v2.projection.multi_driver_risk_aggregation import (
    ThreeDriverAggregationConfig,
    ThreeDriverStandaloneCapital,
    ThreeDriverCorrelatedAggregation,
    ThreeDriverRiskAggregationReport,
    ThreeDriverRiskAggregator,
    three_driver_risk_aggregation_use_restrictions,
    three_driver_risk_aggregation_use_restrictions_json,
)
from par_model_v2.stochastic.esg_process import GBMParams, HullWhiteParams, Measure
from par_model_v2.stochastic.credit_spread import CreditSpreadParams


@pytest.fixture(scope="module")
def product():
    return ParEndowmentProduct(
        term_years=10, issue_age=40, gender="M",
        sum_assured=100_000, annual_premium=6_000,
    )


@pytest.fixture(scope="module")
def aggregator(product):
    return ThreeDriverRiskAggregator(
        product,
        HullWhiteParams(),
        GBMParams(rate_equity_correlation=-0.15),
        CreditSpreadParams(),
        ThreeDriverCorrelation(),
        equity_guarantee=EquityGuaranteeSpec(guarantee_rate=1.0),
        credit_exposure=CreditExposureSpec(exposure_rate=1.0),
    )


@pytest.fixture(scope="module")
def small_cfg():
    return ThreeDriverAggregationConfig(
        n_outer=140, n_inner=64, seed=42,
        confidence_level=0.95, aggregation_gap_tolerance=0.50,
    )


@pytest.fixture(scope="module")
def report(aggregator, small_cfg):
    return aggregator.run(small_cfg)


def test_config_validation():
    with pytest.raises(ValueError):
        ThreeDriverAggregationConfig(n_outer=10)
    with pytest.raises(ValueError):
        ThreeDriverAggregationConfig(n_inner=4)
    with pytest.raises(ValueError):
        ThreeDriverAggregationConfig(confidence_level=1.2)
    with pytest.raises(ValueError):
        ThreeDriverAggregationConfig(aggregation_gap_tolerance=-0.1)


def test_config_serialises_measure():
    cfg = ThreeDriverAggregationConfig(outer_measure=Measure.P)
    assert cfg.to_dict()["outer_measure"] == "P"


def test_aggregator_runs(report):
    assert isinstance(report, ThreeDriverRiskAggregationReport)
    assert report.verdict.startswith(("PASS", "PARTIAL"))
    assert report.standalone.rate_capital.scr_proxy > 0
    assert report.standalone.equity_capital.scr_proxy > 0
    assert report.standalone.credit_capital.scr_proxy > 0
    assert report.aggregation.full_nested_capital.scr_proxy > 0
    assert report.aggregation.correlation_matrix_passed
    assert report.to_dict()["drivers"] == [
        "short_rate", "equity_guarantee", "credit_spread"
    ]


def test_varcovar_uses_governed_3x3_esg_matrix(report):
    scr = np.array(report.standalone.scr_vector, dtype=float)
    C = np.array(report.aggregation.esg_correlation_matrix, dtype=float)
    expected = np.sqrt(max(0.0, float(scr @ C @ scr)))
    assert report.aggregation.correlated_scr == pytest.approx(expected, rel=1e-9)
    # governed structure: unit diagonal, symmetric, negative off-diagonals
    assert C.shape == (3, 3)
    assert np.allclose(np.diag(C), 1.0)
    assert np.allclose(C, C.T)
    assert C[0, 1] == pytest.approx(-0.15)   # rate-equity
    assert C[0, 2] == pytest.approx(-0.20)   # rate-spread
    assert C[1, 2] == pytest.approx(-0.30)   # equity-spread


def test_crn_decomposition_is_exactly_additive(aggregator, small_cfg):
    """full_l == rate_l + equity_l + credit_l on shared inner paths (CRN)."""
    outer = _outer_states_3d(
        small_cfg.n_outer, small_cfg.capital_horizon_months, small_cfg.outer_measure,
        aggregator.hw_params, aggregator.gbm_params, aggregator.spread_params,
        aggregator.correlation, aggregator.initial_curve, small_cfg.seed,
    )
    rate_l, equity_l, credit_l = aggregator._component_liabilities(outer, small_cfg)
    # cross-check first node: an independent full valuation == sum of components
    rem = aggregator.product.term_months - small_cfg.capital_horizon_months
    child = np.random.SeedSequence(small_cfg.seed).spawn(len(outer))
    r, s, c = outer[0]
    inner_seed = int(child[0].generate_state(1)[0])
    full = _inner_pathwise_pvs_3d(
        float(r), float(s), float(c), small_cfg.n_inner, rem, aggregator.product,
        aggregator.hw_params, aggregator.gbm_params, aggregator.spread_params,
        aggregator.correlation, small_cfg.capital_horizon_months, inner_seed,
        aggregator.equity_guarantee, aggregator.credit_exposure, aggregator.annual_qx_fn,
    ).mean()
    recon = rate_l[0] + equity_l[0] + credit_l[0]
    assert recon == pytest.approx(full, rel=1e-9)


def test_diversification_evidence(report):
    standalone_sum = report.standalone.standalone_scr_sum
    a = report.aggregation
    assert a.correlated_scr <= standalone_sum + 1e-6
    assert a.full_nested_capital.scr_proxy <= standalone_sum + 1e-6
    assert a.diversification_benefit_formula >= 0
    assert a.diversification_benefit_nested >= 0


def test_mr010_understatement_positive(report):
    """Raw ESG-factor formula understates diversified nested capital."""
    a = report.aggregation
    # formula SCR < nested SCR  <=>  positive understatement fraction
    assert a.correlated_scr < a.full_nested_capital.scr_proxy
    assert a.esg_understatement_pct > 0.0
    assert a.formula_vs_nested_scr_gap < 0.0


def test_realised_loss_correlation_is_positive(report):
    """Components co-move positively in stress though factor corr is negative."""
    M = np.array(report.standalone.loss_correlation_matrix, dtype=float)
    assert M.shape == (3, 3)
    assert np.allclose(np.diag(M), 1.0)
    assert np.allclose(M, M.T)
    # off-diagonal realised loss correlations are positive (vs negative ESG)
    assert M[0, 1] > 0
    assert M[0, 2] > 0
    assert M[1, 2] > 0


def test_report_json_round_trip(report):
    parsed = json.loads(report.to_json())
    assert parsed["run_id"] == report.run_id
    assert parsed["aggregation"]["correlation_matrix_passed"] is True
    assert parsed["reproducibility_digest"] == report.reproducibility_digest
    assert len(parsed["aggregation"]["esg_correlation_matrix"]) == 3


def test_reproducible_digest(aggregator, small_cfg):
    a = aggregator.run(small_cfg)
    b = aggregator.run(small_cfg)
    assert a.reproducibility_digest == b.reproducibility_digest


def test_use_restrictions():
    restrictions = three_driver_risk_aggregation_use_restrictions()
    assert restrictions["module"].endswith("multi_driver_risk_aggregation.py")
    assert "EDUCATIONAL" in restrictions["classification"]
    assert restrictions["risk_drivers"] == ["short rate", "equity guarantee", "credit spread"]
    assert any("ASOP 56" in item for item in restrictions["standards"])
    parsed = json.loads(three_driver_risk_aggregation_use_restrictions_json())
    assert parsed["risk_drivers"] == ["short rate", "equity guarantee", "credit spread"]


def test_two_driver_api_unchanged():
    """Phase 15 two-driver aggregation symbols remain importable and intact."""
    from par_model_v2.projection.multi_driver_risk_aggregation import (
        MultiDriverRiskAggregator, RiskAggregationConfig,
        risk_aggregation_use_restrictions,
    )
    assert risk_aggregation_use_restrictions()["risk_drivers"] == [
        "short rate", "equity guarantee"
    ]
    assert RiskAggregationConfig().n_outer == 1000
    assert MultiDriverRiskAggregator is not None
