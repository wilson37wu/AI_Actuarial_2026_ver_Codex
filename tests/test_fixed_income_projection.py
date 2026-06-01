"""Tests for Phase 9 fixed-income instrument library."""

from __future__ import annotations

import pytest

from par_model_v2.projection import (
    FixedIncomeInstrument,
    default_phase9_fixed_income_instruments,
    fixed_income_market_value_after_shock,
    project_fixed_income_cashflows,
)


def _corp_bond(**kwargs) -> FixedIncomeInstrument:
    defaults = dict(
        instrument_id="CORP_A_TEST",
        asset_class="Corporate",
        market_value=100_000.0,
        book_value=98_000.0,
        coupon_rate=0.048,
        duration_years=5.0,
        spread_bps=160.0,
        downgrade_notches=1,
        annual_default_probability=0.012,
        recovery_rate=0.40,
        maturity_years=5.0,
        credit_rating="A",
        currency="HKD",
    )
    defaults.update(kwargs)
    return FixedIncomeInstrument(**defaults)


class TestFixedIncomeInstrument:
    def test_record_exposes_governance_and_credit_fields(self) -> None:
        bond = _corp_bond()
        record = bond.to_record()

        assert record["coupon_rate"] == pytest.approx(0.048)
        assert record["duration_years"] == pytest.approx(5.0)
        assert record["spread_bps"] == pytest.approx(160.0)
        assert record["downgrade_notches"] == 1
        assert record["annual_default_probability"] == pytest.approx(0.012)
        assert record["recovery_rate"] == pytest.approx(0.40)
        assert record["expected_default_loss_rate"] == pytest.approx(0.0072)
        assert record["source_id"]
        assert record["limitation_id"]

    def test_invalid_default_probability_rejected(self) -> None:
        with pytest.raises(ValueError, match="annual_default_probability"):
            _corp_bond(annual_default_probability=1.5)

    def test_converts_to_legacy_asset_position(self) -> None:
        pos = _corp_bond().to_asset_position()
        assert pos.asset_class == "Credit_A"
        assert pos.annual_yield == pytest.approx(0.048)
        assert pos.duration_years == pytest.approx(5.0)
        assert pos.average_maturity_years == pytest.approx(5.0)
        assert pos.credit_rating == "A"


class TestFixedIncomeCashflows:
    def test_monthly_coupon_spread_and_default_loss_are_explicit(self) -> None:
        result = project_fixed_income_cashflows([_corp_bond()], projection_months=12)
        first = result.cashflows.iloc[0]

        assert first["coupon_income"] == pytest.approx(100_000.0 * 0.048 / 12.0)
        assert first["spread_carry"] == pytest.approx(100_000.0 * 0.016 / 12.0)
        assert first["default_loss"] == pytest.approx(100_000.0 * 0.012 * 0.60 / 12.0)
        assert first["net_income"] == pytest.approx(
            first["coupon_income"] - first["default_loss"]
        )
        assert result.total_default_loss > 0.0
        assert result.pv_net_income > 0.0

    def test_bullet_principal_repaid_at_maturity_month(self) -> None:
        result = project_fixed_income_cashflows(
            [_corp_bond(maturity_years=1.0, annual_default_probability=0.0)],
            projection_months=12,
        )
        principal = result.cashflows["principal_repayment"]

        assert principal.iloc[:11].sum() == pytest.approx(0.0)
        assert principal.iloc[11] == pytest.approx(100_000.0)
        assert result.total_principal_repayment == pytest.approx(100_000.0)
        assert result.cashflows["market_value_eom"].iloc[-1] == pytest.approx(0.0)

    def test_summary_rolls_up_by_asset_class(self) -> None:
        bonds = [
            _corp_bond(instrument_id="CORP_A_1"),
            _corp_bond(instrument_id="CORP_BBB_1", credit_rating="BBB", spread_bps=240.0),
        ]
        result = project_fixed_income_cashflows(bonds, projection_months=3)
        summary = result.by_class_summary.iloc[0]

        assert list(result.by_class_summary["asset_class"]) == ["Corporate"]
        assert summary["coupon_income"] == pytest.approx(result.cashflows["coupon_income"].sum())
        assert summary["default_loss"] == pytest.approx(result.cashflows["default_loss"].sum())
        assert summary["pv_net_income"] == pytest.approx(result.cashflows["pv_net_income"].sum())

    def test_default_phase9_fixture_has_government_and_corporate_bonds(self) -> None:
        instruments = default_phase9_fixed_income_instruments()
        classes = {inst.asset_class for inst in instruments}
        result = project_fixed_income_cashflows(instruments, projection_months=6)

        assert {"Government", "Corporate"} <= classes
        assert len(result.by_instrument) == len(instruments)
        assert set(result.by_instrument["instrument_id"]) == {
            inst.instrument_id for inst in instruments
        }


class TestFixedIncomeDurationRepricing:
    def test_rate_spread_and_downgrade_shocks_reduce_market_value(self) -> None:
        bond = _corp_bond()
        no_shock = fixed_income_market_value_after_shock(bond)
        stressed = fixed_income_market_value_after_shock(
            bond,
            rate_shift_bps=100.0,
            spread_shift_bps=50.0,
            downgrade_spread_bps_per_notch=75.0,
        )

        expected_shift = (100.0 + 50.0 + 75.0) / 10_000.0
        expected = 100_000.0 * (1.0 - 5.0 * expected_shift)

        assert no_shock == pytest.approx(100_000.0 * (1.0 - 5.0 * 0.0075))
        assert stressed == pytest.approx(expected)
        assert stressed < no_shock

    def test_extreme_shock_floors_market_value_at_zero(self) -> None:
        assert fixed_income_market_value_after_shock(
            _corp_bond(duration_years=30.0),
            rate_shift_bps=1_000.0,
            spread_shift_bps=1_000.0,
        ) == pytest.approx(0.0)
