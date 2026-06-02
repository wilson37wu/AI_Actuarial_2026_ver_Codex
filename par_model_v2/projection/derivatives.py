"""
Educational derivative valuation examples for Phase 9 asset expansion.

The examples are deterministic and curve-based.  They expose the valuation
measure, discounting basis, collateral assumption, settlement timing, and
limitations needed for governed actuarial reporting examples.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

from par_model_v2.stochastic import RiskFreeCurve


def _require_finite(name: str, value: float) -> None:
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _require_text(value: str, name: str) -> str:
    if not str(value).strip():
        raise ValueError(f"{name} is required")
    return str(value)


def _payment_times(start_years: float, maturity_years: float, frequency_per_year: int) -> List[float]:
    if frequency_per_year <= 0:
        raise ValueError("payment_frequency_per_year must be positive")
    if maturity_years <= start_years:
        raise ValueError("maturity_years must exceed start_years")
    step = 1.0 / float(frequency_per_year)
    n_payments = int(np.ceil((maturity_years - start_years) * frequency_per_year - 1e-12))
    times = [start_years + step * (i + 1) for i in range(n_payments)]
    times[-1] = maturity_years
    return times


@dataclass(frozen=True)
class InterestRateSwapContract:
    """Plain-vanilla fixed-vs-floating interest rate swap contract."""

    swap_id: str
    notional: float
    fixed_rate: float
    maturity_years: float
    pay_fixed: bool = True
    start_years: float = 0.0
    payment_frequency_per_year: int = 2
    currency: str = "HKD"
    collateral_basis: str = "OIS discounting placeholder"
    source_id: str = "phase9-irs-placeholder"
    limitation_id: str = "PHASE9-IRS-PLACEHOLDER"

    def __post_init__(self) -> None:
        _require_text(self.swap_id, "swap_id")
        _require_text(self.currency, "currency")
        _require_text(self.collateral_basis, "collateral_basis")
        _require_text(self.source_id, "source_id")
        _require_text(self.limitation_id, "limitation_id")
        for name in ("notional", "fixed_rate", "start_years", "maturity_years"):
            _require_finite(name, float(getattr(self, name)))
        if self.notional <= 0.0:
            raise ValueError("notional must be positive")
        if self.start_years < 0.0:
            raise ValueError("start_years must be non-negative")
        _payment_times(self.start_years, self.maturity_years, self.payment_frequency_per_year)

    def payment_times(self) -> List[float]:
        return _payment_times(
            self.start_years,
            self.maturity_years,
            self.payment_frequency_per_year,
        )

    def to_record(self) -> Dict[str, object]:
        return {
            "instrument_id": self.swap_id,
            "derivative_type": "InterestRateSwap",
            "notional": self.notional,
            "fixed_rate": self.fixed_rate,
            "start_years": self.start_years,
            "maturity_years": self.maturity_years,
            "pay_fixed": self.pay_fixed,
            "payment_frequency_per_year": self.payment_frequency_per_year,
            "currency": self.currency,
            "collateral_basis": self.collateral_basis,
            "source_id": self.source_id,
            "limitation_id": self.limitation_id,
        }


@dataclass(frozen=True)
class BondForwardContract:
    """Forward purchase or sale of a coupon bond using price-per-100 notation."""

    forward_id: str
    notional: float
    spot_dirty_price: float
    contract_forward_price: float
    bond_coupon_rate: float
    bond_maturity_years: float
    forward_maturity_years: float
    long_forward: bool = True
    coupon_frequency_per_year: int = 2
    currency: str = "HKD"
    settlement_basis: str = "cash-settled educational placeholder"
    source_id: str = "phase9-bond-forward-placeholder"
    limitation_id: str = "PHASE9-BOND-FORWARD-PLACEHOLDER"

    def __post_init__(self) -> None:
        _require_text(self.forward_id, "forward_id")
        _require_text(self.currency, "currency")
        _require_text(self.settlement_basis, "settlement_basis")
        _require_text(self.source_id, "source_id")
        _require_text(self.limitation_id, "limitation_id")
        for name in (
            "notional",
            "spot_dirty_price",
            "contract_forward_price",
            "bond_coupon_rate",
            "bond_maturity_years",
            "forward_maturity_years",
        ):
            _require_finite(name, float(getattr(self, name)))
        if self.notional <= 0.0:
            raise ValueError("notional must be positive")
        if self.spot_dirty_price <= 0.0:
            raise ValueError("spot_dirty_price must be positive")
        if self.contract_forward_price < 0.0:
            raise ValueError("contract_forward_price must be non-negative")
        if self.bond_coupon_rate < 0.0:
            raise ValueError("bond_coupon_rate must be non-negative")
        if self.forward_maturity_years <= 0.0:
            raise ValueError("forward_maturity_years must be positive")
        if self.bond_maturity_years <= self.forward_maturity_years:
            raise ValueError("bond_maturity_years must exceed forward_maturity_years")
        if self.coupon_frequency_per_year <= 0:
            raise ValueError("coupon_frequency_per_year must be positive")

    def coupon_times_before_delivery(self) -> List[float]:
        step = 1.0 / float(self.coupon_frequency_per_year)
        times: List[float] = []
        t = step
        while t <= self.forward_maturity_years + 1e-12:
            times.append(min(t, self.forward_maturity_years))
            t += step
        return times

    def to_record(self) -> Dict[str, object]:
        return {
            "instrument_id": self.forward_id,
            "derivative_type": "BondForward",
            "notional": self.notional,
            "spot_dirty_price": self.spot_dirty_price,
            "contract_forward_price": self.contract_forward_price,
            "bond_coupon_rate": self.bond_coupon_rate,
            "bond_maturity_years": self.bond_maturity_years,
            "forward_maturity_years": self.forward_maturity_years,
            "long_forward": self.long_forward,
            "coupon_frequency_per_year": self.coupon_frequency_per_year,
            "currency": self.currency,
            "settlement_basis": self.settlement_basis,
            "source_id": self.source_id,
            "limitation_id": self.limitation_id,
        }


@dataclass(frozen=True)
class DerivativeValuationResult:
    """Valuation output for educational derivative examples."""

    valuations: pd.DataFrame
    cashflow_schedule: pd.DataFrame
    total_market_value: float


def value_interest_rate_swap(
    swap: InterestRateSwapContract,
    discount_curve: RiskFreeCurve,
) -> Dict[str, object]:
    """
    Value a plain-vanilla swap from the discount curve.

    Floating-leg PV uses the standard single-curve par approximation
    `N * (P(0,start) - P(0,maturity))`.  This is intentionally a teaching
    example and not a production multi-curve collateral valuation.
    """
    payment_times = swap.payment_times()
    accrual = 1.0 / float(swap.payment_frequency_per_year)
    annuity = sum(accrual * discount_curve.discount_factor(t) for t in payment_times)
    fixed_leg_pv = swap.notional * swap.fixed_rate * annuity
    floating_leg_pv = swap.notional * (
        discount_curve.discount_factor(swap.start_years)
        - discount_curve.discount_factor(swap.maturity_years)
    )
    fair_fixed_rate = floating_leg_pv / (swap.notional * annuity)
    receive_float_pay_fixed = floating_leg_pv - fixed_leg_pv
    market_value = receive_float_pay_fixed if swap.pay_fixed else -receive_float_pay_fixed

    return {
        **swap.to_record(),
        "valuation_measure": "Q",
        "discount_curve_id": discount_curve.curve_id,
        "discount_curve_source_id": discount_curve.source_id,
        "annuity": annuity,
        "fixed_leg_pv": fixed_leg_pv,
        "floating_leg_pv": floating_leg_pv,
        "fair_fixed_rate": fair_fixed_rate,
        "market_value": market_value,
    }


def interest_rate_swap_cashflow_schedule(
    swap: InterestRateSwapContract,
    discount_curve: RiskFreeCurve,
) -> pd.DataFrame:
    """Return fixed and forward-floating educational cashflow rows."""
    rows: List[Dict[str, object]] = []
    previous_time = swap.start_years
    direction = -1.0 if swap.pay_fixed else 1.0
    for payment_time in swap.payment_times():
        accrual = payment_time - previous_time
        forward_rate = discount_curve.forward_rate(previous_time, payment_time)
        fixed_coupon = swap.notional * swap.fixed_rate * accrual
        floating_coupon = swap.notional * forward_rate * accrual
        net_cashflow = direction * fixed_coupon - direction * floating_coupon
        discount_factor = discount_curve.discount_factor(payment_time)
        rows.append(
            {
                "instrument_id": swap.swap_id,
                "derivative_type": "InterestRateSwap",
                "payment_time_years": payment_time,
                "accrual_years": accrual,
                "fixed_coupon": fixed_coupon,
                "forward_rate": forward_rate,
                "floating_coupon": floating_coupon,
                "net_cashflow": net_cashflow,
                "discount_factor": discount_factor,
                "pv_net_cashflow": net_cashflow * discount_factor,
                "currency": swap.currency,
            }
        )
        previous_time = payment_time
    return pd.DataFrame(rows)


def value_bond_forward(
    forward: BondForwardContract,
    discount_curve: RiskFreeCurve,
) -> Dict[str, object]:
    """Value a bond forward using cost-of-carry price-per-100 mechanics."""
    coupon_amount = 100.0 * forward.bond_coupon_rate / float(forward.coupon_frequency_per_year)
    pv_coupons = sum(
        coupon_amount * discount_curve.discount_factor(t)
        for t in forward.coupon_times_before_delivery()
        if t < forward.forward_maturity_years + 1e-12
    )
    delivery_df = discount_curve.discount_factor(forward.forward_maturity_years)
    fair_forward_price = (forward.spot_dirty_price - pv_coupons) / delivery_df
    unit_count = forward.notional / 100.0
    long_value = unit_count * (fair_forward_price - forward.contract_forward_price) * delivery_df
    market_value = long_value if forward.long_forward else -long_value

    return {
        **forward.to_record(),
        "valuation_measure": "Q",
        "discount_curve_id": discount_curve.curve_id,
        "discount_curve_source_id": discount_curve.source_id,
        "pv_coupons_before_delivery_per_100": pv_coupons,
        "delivery_discount_factor": delivery_df,
        "fair_forward_price": fair_forward_price,
        "market_value": market_value,
    }


def bond_forward_cashflow_schedule(
    forward: BondForwardContract,
    discount_curve: RiskFreeCurve,
) -> pd.DataFrame:
    """Return coupon carry and settlement rows for the bond forward example."""
    rows: List[Dict[str, object]] = []
    unit_count = forward.notional / 100.0
    coupon_amount = 100.0 * forward.bond_coupon_rate / float(forward.coupon_frequency_per_year)
    for coupon_time in forward.coupon_times_before_delivery():
        if coupon_time <= forward.forward_maturity_years + 1e-12:
            discount_factor = discount_curve.discount_factor(coupon_time)
            cashflow = coupon_amount * unit_count
            rows.append(
                {
                    "instrument_id": forward.forward_id,
                    "derivative_type": "BondForward",
                    "payment_time_years": coupon_time,
                    "cashflow_type": "coupon_before_delivery",
                    "cashflow": cashflow,
                    "discount_factor": discount_factor,
                    "pv_cashflow": cashflow * discount_factor,
                    "currency": forward.currency,
                }
            )

    valuation = value_bond_forward(forward, discount_curve)
    settlement_df = discount_curve.discount_factor(forward.forward_maturity_years)
    settlement_cashflow = (
        (valuation["fair_forward_price"] - forward.contract_forward_price)
        * unit_count
        * (1.0 if forward.long_forward else -1.0)
    )
    rows.append(
        {
            "instrument_id": forward.forward_id,
            "derivative_type": "BondForward",
            "payment_time_years": forward.forward_maturity_years,
            "cashflow_type": "forward_settlement",
            "cashflow": settlement_cashflow,
            "discount_factor": settlement_df,
            "pv_cashflow": settlement_cashflow * settlement_df,
            "currency": forward.currency,
        }
    )
    return pd.DataFrame(rows)


def value_derivative_portfolio(
    swaps: Iterable[InterestRateSwapContract],
    bond_forwards: Iterable[BondForwardContract],
    discount_curve: RiskFreeCurve,
) -> DerivativeValuationResult:
    """Value the starter derivative portfolio and return records plus schedules."""
    valuation_rows: List[Dict[str, object]] = []
    schedules: List[pd.DataFrame] = []

    for swap in swaps:
        valuation_rows.append(value_interest_rate_swap(swap, discount_curve))
        schedules.append(interest_rate_swap_cashflow_schedule(swap, discount_curve))
    for forward in bond_forwards:
        valuation_rows.append(value_bond_forward(forward, discount_curve))
        schedules.append(bond_forward_cashflow_schedule(forward, discount_curve))

    valuations = pd.DataFrame(valuation_rows)
    cashflow_schedule = pd.concat(schedules, ignore_index=True) if schedules else pd.DataFrame()
    total_market_value = (
        float(valuations["market_value"].sum()) if not valuations.empty else 0.0
    )
    return DerivativeValuationResult(
        valuations=valuations,
        cashflow_schedule=cashflow_schedule,
        total_market_value=total_market_value,
    )


def default_phase9_derivative_examples() -> Dict[str, List[object]]:
    """Starter educational swap and bond-forward examples for Phase 9."""
    return {
        "swaps": [
            InterestRateSwapContract(
                swap_id="HKD_PAY_FIXED_5Y_EDU",
                notional=500_000.0,
                fixed_rate=0.032,
                maturity_years=5.0,
                pay_fixed=True,
                payment_frequency_per_year=2,
                currency="HKD",
            )
        ],
        "bond_forwards": [
            BondForwardContract(
                forward_id="HK_GOVT_10Y_FORWARD_1Y_EDU",
                notional=300_000.0,
                spot_dirty_price=98.50,
                contract_forward_price=99.25,
                bond_coupon_rate=0.030,
                bond_maturity_years=10.0,
                forward_maturity_years=1.0,
                long_forward=True,
                coupon_frequency_per_year=2,
                currency="HKD",
            )
        ],
    }


__all__ = [
    "BondForwardContract",
    "DerivativeValuationResult",
    "InterestRateSwapContract",
    "bond_forward_cashflow_schedule",
    "default_phase9_derivative_examples",
    "interest_rate_swap_cashflow_schedule",
    "value_bond_forward",
    "value_derivative_portfolio",
    "value_interest_rate_swap",
]
