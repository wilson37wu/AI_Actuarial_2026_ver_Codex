"""Tests for Phase 9 asset cashflow aggregation and roll-forward reporting."""

from __future__ import annotations

import pytest

from par_model_v2.projection import (
    aggregate_asset_rollforward,
    default_phase9_derivative_examples,
    default_phase9_fixed_income_instruments,
    default_phase9_private_assets,
    project_fixed_income_cashflows,
    project_phase9_asset_rollforward,
    project_private_asset_cashflows,
    value_derivative_portfolio,
)
from par_model_v2.stochastic import RiskFreeCurve


def _curve(rate: float = 0.032) -> RiskFreeCurve:
    return RiskFreeCurve.flat(
        rate,
        currency="HKD",
        market="HK",
        valuation_date="2026-06-02",
        curve_id="HKD-ROLLFORWARD-TEST",
        source_id="SRC-HKD-ROLLFORWARD-TEST",
    )


class TestAssetRollForwardAggregation:
    def test_combines_fixed_private_and_derivative_rows(self) -> None:
        fixed = project_fixed_income_cashflows(
            default_phase9_fixed_income_instruments(),
            projection_months=12,
        )
        private = project_private_asset_cashflows(
            default_phase9_private_assets(),
            projection_months=12,
        )
        examples = default_phase9_derivative_examples()
        derivatives = value_derivative_portfolio(
            examples["swaps"],
            examples["bond_forwards"],
            _curve(),
        )

        report = aggregate_asset_rollforward(fixed, private, derivatives, 12)

        assert set(report.monthly_rollforward["source_type"]) == {
            "FixedIncome",
            "PrivateAsset",
            "Derivative",
        }
        assert set(report.by_class_attribution["source_type"]) == {
            "FixedIncome",
            "PrivateAsset",
            "Derivative",
        }
        assert report.opening_market_value == pytest.approx(
            report.monthly_rollforward.query("month == 1")["market_value_bom"].sum()
        )
        assert report.ending_market_value == pytest.approx(
            report.monthly_rollforward.query("month == 12")["market_value_eom"].sum()
        )
        assert report.net_cashflow == pytest.approx(
            report.monthly_rollforward["net_cashflow"].sum()
        )
        assert report.governance_notes

    def test_rollforward_identity_holds_by_class(self) -> None:
        report = project_phase9_asset_rollforward(
            projection_months=6,
            discount_curve=_curve(),
        )

        for _, row in report.by_class_attribution.iterrows():
            expected_ending = (
                row["opening_market_value"]
                + row["capital_call"]
                - row["distribution"]
                - row["principal_repayment"]
                - row["default_loss"]
                + row["market_value_change"]
            )
            assert row["ending_market_value"] == pytest.approx(expected_ending)

    def test_derivative_schedule_cashflows_map_to_payment_months(self) -> None:
        examples = default_phase9_derivative_examples()
        derivatives = value_derivative_portfolio(
            examples["swaps"],
            examples["bond_forwards"],
            _curve(),
        )
        report = aggregate_asset_rollforward(
            derivatives=derivatives,
            projection_months=12,
        )

        derivative_rows = report.monthly_rollforward[
            report.monthly_rollforward["source_type"] == "Derivative"
        ]
        scheduled_months = set(
            derivative_rows.loc[derivative_rows["derivative_cashflow"] != 0.0, "month"]
        )

        assert 6 in scheduled_months
        assert 12 in scheduled_months
        assert report.source_summary.loc[
            report.source_summary["source_type"] == "Derivative",
            "net_cashflow",
        ].iloc[0] == pytest.approx(derivative_rows["derivative_cashflow"].sum())

    def test_default_phase9_report_covers_expected_classes(self) -> None:
        report = project_phase9_asset_rollforward(projection_months=3)

        classes = set(report.by_class_attribution["asset_class"])
        assert {"Government", "Corporate", "PrivateCredit"} <= classes
        assert "Derivative:InterestRateSwap" in classes
        assert "Derivative:BondForward" in classes
        assert len(report.source_summary) == 3
