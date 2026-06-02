"""Tests for Phase 9 asset class stress reporting."""

from __future__ import annotations

import pytest

from par_model_v2.projection import (
    AssetStressScenario,
    default_phase9_asset_stress_scenarios,
    run_asset_class_stress_tests,
)
from par_model_v2.stochastic import RiskFreeCurve


def _curve(rate: float = 0.032) -> RiskFreeCurve:
    return RiskFreeCurve.flat(
        rate,
        currency="HKD",
        market="HK",
        valuation_date="2026-06-02",
        curve_id="HKD-STRESS-TEST",
        source_id="SRC-HKD-STRESS-TEST",
    )


class TestAssetStressScenarios:
    def test_default_stress_pack_covers_core_phase9_risks(self) -> None:
        scenarios = default_phase9_asset_stress_scenarios()

        assert {scenario.scenario_id for scenario in scenarios} == {
            "HKD_RATE_UP_150BP",
            "CREDIT_SPREAD_DEFAULT_STRESS",
            "PRIVATE_MARKET_LIQUIDITY_STRESS",
            "INFLATION_DOWNSIDE_STRESS",
        }
        assert all(scenario.governance_note for scenario in scenarios)

    def test_invalid_stress_inputs_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="private_credit_default_multiplier"):
            AssetStressScenario(
                scenario_id="BAD",
                description="bad multiplier",
                private_credit_default_multiplier=-1.0,
            )
        with pytest.raises(ValueError, match="private_equity_nav_shock"):
            AssetStressScenario(
                scenario_id="BAD",
                description="bad nav shock",
                private_equity_nav_shock=-1.5,
            )


class TestAssetStressReporting:
    def test_stress_report_has_instrument_and_scenario_attribution(self) -> None:
        report = run_asset_class_stress_tests(discount_curve=_curve())

        assert set(report.stress_results["source_type"]) == {
            "FixedIncome",
            "PrivateAsset",
            "Derivative",
        }
        assert set(report.scenario_summary["scenario_id"]) == {
            scenario.scenario_id for scenario in default_phase9_asset_stress_scenarios()
        }
        assert report.governance_notes
        assert report.stress_results["instrument_id"].notna().all()
        assert report.stress_results["governance_note"].str.len().min() > 0

    def test_rate_stress_reduces_fixed_income_market_value(self) -> None:
        scenario = AssetStressScenario(
            scenario_id="RATE_TEST",
            description="rate up",
            rate_shift_bps=100.0,
            derivative_curve_shift_bps=100.0,
        )
        report = run_asset_class_stress_tests([scenario], discount_curve=_curve())
        fixed_income = report.stress_results[
            report.stress_results["source_type"] == "FixedIncome"
        ]

        assert fixed_income["market_value_impact"].sum() < 0.0
        assert report.scenario_summary.iloc[0]["base_market_value"] == pytest.approx(
            report.stress_results["base_market_value"].sum()
        )
        assert report.scenario_summary.iloc[0]["market_value_impact"] == pytest.approx(
            report.stress_results["market_value_impact"].sum()
        )

    def test_private_market_stress_marks_down_private_assets(self) -> None:
        scenario = AssetStressScenario(
            scenario_id="PRIVATE_TEST",
            description="private stress",
            private_credit_default_multiplier=2.0,
            private_credit_recovery_shift=-0.10,
            private_equity_nav_shock=-0.25,
            infrastructure_revenue_shock=-0.20,
        )
        report = run_asset_class_stress_tests([scenario], discount_curve=_curve())
        private_assets = report.stress_results[
            report.stress_results["source_type"] == "PrivateAsset"
        ]

        assert private_assets["market_value_impact"].sum() < 0.0
        assert set(private_assets["asset_class"]) == {
            "Infrastructure",
            "PrivateCredit",
            "PrivateEquity",
        }

    def test_derivative_curve_stress_revalues_derivatives(self) -> None:
        scenario = AssetStressScenario(
            scenario_id="DERIVATIVE_TEST",
            description="curve shock",
            derivative_curve_shift_bps=200.0,
        )
        report = run_asset_class_stress_tests([scenario], discount_curve=_curve())
        derivatives = report.stress_results[
            report.stress_results["source_type"] == "Derivative"
        ]

        assert not derivatives.empty
        assert derivatives["market_value_impact"].abs().sum() > 0.0
