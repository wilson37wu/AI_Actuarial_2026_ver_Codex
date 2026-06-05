"""
Tests for Phase 15 Task 3 correlated risk aggregation.
"""

import json

import numpy as np
import pytest

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_risk_aggregation import (
    MultiDriverRiskAggregator,
    RiskAggregationConfig,
    RiskAggregationReport,
    risk_aggregation_use_restrictions,
    risk_aggregation_use_restrictions_json,
)
from par_model_v2.stochastic.esg_process import GBMParams, HullWhiteParams, Measure


@pytest.fixture(scope="module")
def product():
    return ParEndowmentProduct(
        term_years=10,
        issue_age=40,
        gender="M",
        sum_assured=100_000,
        annual_premium=6_000,
    )


@pytest.fixture(scope="module")
def aggregator(product):
    return MultiDriverRiskAggregator(
        product,
        HullWhiteParams(),
        GBMParams(rate_equity_correlation=-0.15),
        equity_guarantee=EquityGuaranteeSpec(guarantee_rate=1.0),
    )


@pytest.fixture(scope="module")
def small_cfg():
    return RiskAggregationConfig(
        n_outer=220,
        n_inner=96,
        seed=42,
        confidence_level=0.95,
        aggregation_gap_tolerance=0.50,
    )


@pytest.fixture(scope="module")
def report(aggregator, small_cfg):
    return aggregator.run(small_cfg)


def test_config_validation():
    with pytest.raises(ValueError):
        RiskAggregationConfig(n_outer=10)
    with pytest.raises(ValueError):
        RiskAggregationConfig(n_inner=4)
    with pytest.raises(ValueError):
        RiskAggregationConfig(confidence_level=1.2)
    with pytest.raises(ValueError):
        RiskAggregationConfig(aggregation_gap_tolerance=-0.1)


def test_config_serialises_measure():
    cfg = RiskAggregationConfig(outer_measure=Measure.P)
    assert cfg.to_dict()["outer_measure"] == "P"


def test_aggregator_runs(report):
    assert isinstance(report, RiskAggregationReport)
    assert report.verdict.startswith(("PASS", "PARTIAL"))
    assert report.standalone.rate_capital.scr_proxy > 0
    assert report.standalone.equity_capital.scr_proxy > 0
    assert report.aggregation.full_nested_capital.scr_proxy > 0
    assert report.aggregation.correlation_matrix_passed


def test_correlated_formula_uses_esg_correlation(report):
    r = report.standalone.rate_capital.scr_proxy
    e = report.standalone.equity_capital.scr_proxy
    rho = report.aggregation.esg_rate_equity_correlation
    expected = np.sqrt(max(0.0, r * r + e * e + 2.0 * rho * r * e))
    assert report.aggregation.correlated_scr == pytest.approx(expected)
    assert report.aggregation.esg_correlation_matrix == ((1.0, rho), (rho, 1.0))


def test_diversification_evidence(report):
    standalone_sum = report.standalone.standalone_scr_sum
    assert report.aggregation.correlated_scr <= standalone_sum
    assert report.aggregation.full_nested_capital.scr_proxy <= standalone_sum
    assert report.aggregation.diversification_benefit_formula >= 0
    assert report.aggregation.diversification_benefit_nested >= 0


def test_component_correlation_is_finite(report):
    assert np.isfinite(report.standalone.component_loss_correlation)
    assert -1.0 <= report.standalone.component_loss_correlation <= 1.0


def test_report_json_round_trip(report):
    parsed = json.loads(report.to_json())
    assert parsed["run_id"] == report.run_id
    assert parsed["aggregation"]["correlation_matrix_passed"] is True
    assert parsed["reproducibility_digest"] == report.reproducibility_digest


def test_reproducible_digest(aggregator, small_cfg):
    a = aggregator.run(small_cfg)
    b = aggregator.run(small_cfg)
    assert a.reproducibility_digest == b.reproducibility_digest


def test_use_restrictions():
    restrictions = risk_aggregation_use_restrictions()
    assert restrictions["module"].endswith("multi_driver_risk_aggregation.py")
    assert "EDUCATIONAL" in restrictions["classification"]
    assert any("ASOP 56" in item for item in restrictions["standards"])
    parsed = json.loads(risk_aggregation_use_restrictions_json())
    assert parsed["risk_drivers"] == ["short rate", "equity guarantee"]
