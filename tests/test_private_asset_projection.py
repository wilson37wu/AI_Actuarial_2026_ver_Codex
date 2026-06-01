"""Tests for Phase 9 private credit, private equity, and infrastructure models."""

from __future__ import annotations

import pytest

from par_model_v2.projection import (
    InfrastructureAsset,
    PrivateCreditAsset,
    PrivateEquityAsset,
    default_phase9_private_assets,
    project_private_asset_cashflows,
)


def _private_credit(**kwargs) -> PrivateCreditAsset:
    defaults = dict(
        asset_id="PC_TEST",
        strategy="Senior secured lending",
        market_value=100_000.0,
        book_value=99_000.0,
        cash_yield=0.075,
        spread_bps=400.0,
        annual_default_probability=0.018,
        recovery_rate=0.50,
        liquidity_lag_months=2,
        valuation_smoothing_months=4,
        maturity_years=1.0,
        currency="HKD",
    )
    defaults.update(kwargs)
    return PrivateCreditAsset(**defaults)


def _private_equity(**kwargs) -> PrivateEquityAsset:
    defaults = dict(
        asset_id="PE_TEST",
        strategy="Buyout fund",
        funded_nav=80_000.0,
        unfunded_commitment=40_000.0,
        book_value=78_000.0,
        annual_call_rate=0.30,
        annual_distribution_rate=0.06,
        annual_nav_growth_rate=0.10,
        j_curve_months=12,
        j_curve_drag_annual=0.04,
        valuation_lag_months=3,
        valuation_smoothing_months=4,
        currency="HKD",
    )
    defaults.update(kwargs)
    return PrivateEquityAsset(**defaults)


def _infrastructure(**kwargs) -> InfrastructureAsset:
    defaults = dict(
        asset_id="INFRA_TEST",
        project_type="Availability-based transport",
        market_value=120_000.0,
        book_value=118_000.0,
        cash_yield=0.055,
        inflation_linkage=0.70,
        inflation_assumption=0.025,
        availability_factor=0.98,
        revenue_shock=-0.10,
        duration_years=12.0,
        concession_years=25.0,
        valuation_smoothing_months=6,
        currency="HKD",
    )
    defaults.update(kwargs)
    return InfrastructureAsset(**defaults)


class TestPrivateAssetRecords:
    def test_private_credit_record_exposes_loss_liquidity_and_governance(self) -> None:
        record = _private_credit().to_record()

        assert record["asset_class"] == "PrivateCredit"
        assert record["cash_yield"] == pytest.approx(0.075)
        assert record["spread_bps"] == pytest.approx(400.0)
        assert record["expected_default_loss_rate"] == pytest.approx(0.009)
        assert record["liquidity_lag_months"] == 2
        assert record["source_id"]
        assert record["limitation_id"]

    def test_private_equity_converts_to_legacy_equity_position(self) -> None:
        pos = _private_equity().to_asset_position()

        assert pos.asset_class == "Equity"
        assert pos.market_value == pytest.approx(80_000.0)
        assert pos.annual_yield == pytest.approx(0.06)
        assert pos.annual_capital_growth == pytest.approx(0.10)

    def test_infrastructure_record_exposes_inflation_and_revenue_stress(self) -> None:
        record = _infrastructure().to_record()

        assert record["asset_class"] == "Infrastructure"
        assert record["inflation_linkage"] == pytest.approx(0.70)
        assert record["availability_factor"] == pytest.approx(0.98)
        assert record["revenue_shock"] == pytest.approx(-0.10)
        assert record["valuation_smoothing_months"] == 6

    def test_invalid_ranges_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="annual_default_probability"):
            _private_credit(annual_default_probability=1.20)
        with pytest.raises(ValueError, match="valuation_smoothing_months"):
            _private_equity(valuation_smoothing_months=0)
        with pytest.raises(ValueError, match="availability_factor"):
            _infrastructure(availability_factor=1.20)


class TestPrivateAssetCashflows:
    def test_private_credit_projects_yield_spread_default_and_lagged_principal(self) -> None:
        result = project_private_asset_cashflows([_private_credit()], projection_months=14)
        first = result.cashflows.iloc[0]

        assert first["cash_income"] == pytest.approx(100_000.0 * 0.075 / 12.0)
        assert first["spread_income"] == pytest.approx(100_000.0 * 0.040 / 12.0)
        assert first["default_loss"] == pytest.approx(100_000.0 * 0.009 / 12.0)
        assert result.cashflows["principal_repayment"].iloc[:13].sum() == pytest.approx(0.0)
        assert result.cashflows["principal_repayment"].iloc[13] > 0.0
        assert result.total_default_loss > 0.0
        assert result.pv_net_cashflow > 0.0

    def test_private_equity_projects_capital_calls_distributions_and_j_curve(self) -> None:
        result = project_private_asset_cashflows([_private_equity()], projection_months=2)
        first = result.cashflows.iloc[0]

        assert first["capital_call"] == pytest.approx(40_000.0 * 0.30 / 12.0)
        assert first["distribution"] == pytest.approx(80_000.0 * 0.06 / 12.0)
        assert first["nav_growth"] == pytest.approx(80_000.0 * (0.10 - 0.04) / 12.0)
        assert first["net_cashflow"] == pytest.approx(first["distribution"] - first["capital_call"])
        assert result.total_capital_calls > result.total_distributions

    def test_infrastructure_projects_cash_yield_and_inflation_uplift(self) -> None:
        result = project_private_asset_cashflows([_infrastructure()], projection_months=1)
        first = result.cashflows.iloc[0]

        expected_cash = 120_000.0 * 0.055 * 0.98 * 0.90 / 12.0
        expected_inflation = 120_000.0 * 0.70 * 0.025 / 12.0

        assert first["cash_income"] == pytest.approx(expected_cash)
        assert first["inflation_uplift"] == pytest.approx(expected_inflation)
        assert first["revenue_shock_loss"] == pytest.approx(120_000.0 * 0.10 * 0.055 / 12.0)
        assert first["economic_nav_eom"] > first["economic_nav_bom"]

    def test_default_phase9_fixture_covers_all_private_asset_classes(self) -> None:
        result = project_private_asset_cashflows(
            default_phase9_private_assets(),
            projection_months=6,
        )

        assert set(result.by_asset["asset_class"]) == {
            "PrivateCredit",
            "PrivateEquity",
            "Infrastructure",
        }
        assert set(result.by_class_summary["asset_class"]) == {
            "Infrastructure",
            "PrivateCredit",
            "PrivateEquity",
        }
        assert len(result.cashflows) == 18
