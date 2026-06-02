"""Tests for Phase 9 interest rate swap and bond forward examples."""

from __future__ import annotations

import pytest

from par_model_v2.projection import (
    BondForwardContract,
    InterestRateSwapContract,
    default_phase9_derivative_examples,
    value_bond_forward,
    value_derivative_portfolio,
    value_interest_rate_swap,
)
from par_model_v2.stochastic import RiskFreeCurve


def _curve(rate: float = 0.03) -> RiskFreeCurve:
    return RiskFreeCurve.flat(
        rate,
        currency="HKD",
        market="HK",
        valuation_date="2026-06-02",
        curve_id="HKD-FLAT-TEST",
        source_id="SRC-HKD-FLAT-TEST",
    )


def _swap(**kwargs) -> InterestRateSwapContract:
    defaults = dict(
        swap_id="IRS_TEST",
        notional=1_000_000.0,
        fixed_rate=0.030,
        maturity_years=5.0,
        pay_fixed=True,
        payment_frequency_per_year=2,
        currency="HKD",
    )
    defaults.update(kwargs)
    return InterestRateSwapContract(**defaults)


def _forward(**kwargs) -> BondForwardContract:
    defaults = dict(
        forward_id="BOND_FWD_TEST",
        notional=500_000.0,
        spot_dirty_price=98.0,
        contract_forward_price=98.75,
        bond_coupon_rate=0.030,
        bond_maturity_years=8.0,
        forward_maturity_years=1.0,
        long_forward=True,
        coupon_frequency_per_year=2,
        currency="HKD",
    )
    defaults.update(kwargs)
    return BondForwardContract(**defaults)


class TestInterestRateSwapValuation:
    def test_par_swap_has_near_zero_value(self) -> None:
        curve = _curve(0.03)
        par_rate = value_interest_rate_swap(_swap(fixed_rate=0.0), curve)["fair_fixed_rate"]

        valuation = value_interest_rate_swap(_swap(fixed_rate=par_rate), curve)

        assert valuation["valuation_measure"] == "Q"
        assert valuation["discount_curve_id"] == "HKD-FLAT-TEST"
        assert valuation["fixed_leg_pv"] == pytest.approx(valuation["floating_leg_pv"])
        assert valuation["market_value"] == pytest.approx(0.0, abs=1e-8)
        assert valuation["collateral_basis"]
        assert valuation["limitation_id"]

    def test_pay_fixed_swap_loses_value_when_fixed_rate_exceeds_par(self) -> None:
        curve = _curve(0.03)
        par_rate = value_interest_rate_swap(_swap(fixed_rate=0.0), curve)["fair_fixed_rate"]

        valuation = value_interest_rate_swap(_swap(fixed_rate=par_rate + 0.01), curve)

        assert valuation["market_value"] < 0.0

    def test_receive_fixed_direction_reverses_value(self) -> None:
        curve = _curve(0.03)
        pay_fixed = value_interest_rate_swap(_swap(fixed_rate=0.04, pay_fixed=True), curve)
        receive_fixed = value_interest_rate_swap(_swap(fixed_rate=0.04, pay_fixed=False), curve)

        assert receive_fixed["market_value"] == pytest.approx(-pay_fixed["market_value"])

    def test_invalid_swap_inputs_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="notional"):
            _swap(notional=0.0)
        with pytest.raises(ValueError, match="maturity_years"):
            _swap(start_years=5.0, maturity_years=5.0)


class TestBondForwardValuation:
    def test_bond_forward_fair_price_has_zero_value(self) -> None:
        curve = _curve(0.03)
        fair_price = value_bond_forward(_forward(contract_forward_price=0.0), curve)[
            "fair_forward_price"
        ]

        valuation = value_bond_forward(_forward(contract_forward_price=fair_price), curve)

        assert valuation["valuation_measure"] == "Q"
        assert valuation["discount_curve_source_id"] == "SRC-HKD-FLAT-TEST"
        assert valuation["market_value"] == pytest.approx(0.0, abs=1e-8)
        assert valuation["pv_coupons_before_delivery_per_100"] > 0.0
        assert valuation["settlement_basis"]
        assert valuation["limitation_id"]

    def test_long_forward_gains_when_contract_price_is_below_fair(self) -> None:
        curve = _curve(0.03)
        fair_price = value_bond_forward(_forward(contract_forward_price=0.0), curve)[
            "fair_forward_price"
        ]

        valuation = value_bond_forward(_forward(contract_forward_price=fair_price - 1.0), curve)

        assert valuation["market_value"] > 0.0

    def test_short_forward_reverses_value(self) -> None:
        curve = _curve(0.03)
        long_forward = value_bond_forward(_forward(contract_forward_price=97.0), curve)
        short_forward = value_bond_forward(
            _forward(contract_forward_price=97.0, long_forward=False),
            curve,
        )

        assert short_forward["market_value"] == pytest.approx(-long_forward["market_value"])

    def test_invalid_bond_forward_inputs_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="spot_dirty_price"):
            _forward(spot_dirty_price=0.0)
        with pytest.raises(ValueError, match="bond_maturity_years"):
            _forward(bond_maturity_years=1.0, forward_maturity_years=1.0)


class TestDerivativePortfolioFixtures:
    def test_default_examples_include_swap_and_bond_forward(self) -> None:
        examples = default_phase9_derivative_examples()
        result = value_derivative_portfolio(
            examples["swaps"],
            examples["bond_forwards"],
            _curve(0.032),
        )

        assert set(result.valuations["derivative_type"]) == {
            "InterestRateSwap",
            "BondForward",
        }
        assert result.total_market_value == pytest.approx(result.valuations["market_value"].sum())
        assert len(result.cashflow_schedule) > len(result.valuations)
