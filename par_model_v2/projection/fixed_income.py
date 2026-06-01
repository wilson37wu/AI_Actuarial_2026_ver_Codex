"""
Fixed-income instrument library for educational ALM asset modelling.

The module keeps instrument-level credit attributes separate from the legacy
AssetPosition aggregate cashflow model.  It is intentionally transparent:
coupon income, spread carry, downgrade repricing, and expected default losses
are exposed as auditable columns rather than hidden in a single return rate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from par_model_v2.projection.monthly_projection import AssetPosition, monthly_discount_factor


def _require_finite(name: str, value: float) -> None:
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True)
class FixedIncomeInstrument:
    """Governed fixed-income holding with explicit credit-risk fields."""

    instrument_id: str
    asset_class: str
    market_value: float
    book_value: float
    coupon_rate: float
    duration_years: float
    spread_bps: float = 0.0
    downgrade_notches: int = 0
    annual_default_probability: float = 0.0
    recovery_rate: float = 0.40
    maturity_years: float = 0.0
    credit_rating: str = ""
    currency: str = "HKD"
    source_id: str = "phase9-fixed-income-placeholder"
    limitation_id: str = "PHASE9-FI-PLACEHOLDER"

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("instrument_id is required")
        if not self.asset_class:
            raise ValueError("asset_class is required")
        if self.downgrade_notches < 0:
            raise ValueError("downgrade_notches must be non-negative")

        for name in (
            "market_value",
            "book_value",
            "coupon_rate",
            "duration_years",
            "spread_bps",
            "annual_default_probability",
            "recovery_rate",
            "maturity_years",
        ):
            _require_finite(name, float(getattr(self, name)))

        if self.market_value < 0.0:
            raise ValueError("market_value must be non-negative")
        if self.book_value < 0.0:
            raise ValueError("book_value must be non-negative")
        if self.coupon_rate < 0.0:
            raise ValueError("coupon_rate must be non-negative")
        if self.duration_years < 0.0:
            raise ValueError("duration_years must be non-negative")
        if not 0.0 <= self.annual_default_probability <= 1.0:
            raise ValueError("annual_default_probability must be between 0 and 1")
        if not 0.0 <= self.recovery_rate <= 1.0:
            raise ValueError("recovery_rate must be between 0 and 1")
        if self.maturity_years < 0.0:
            raise ValueError("maturity_years must be non-negative")

    @property
    def expected_default_loss_rate(self) -> float:
        """Annual expected loss rate from probability of default and recovery."""
        return self.annual_default_probability * (1.0 - self.recovery_rate)

    def to_record(self) -> Dict[str, object]:
        return {
            "instrument_id": self.instrument_id,
            "asset_class": self.asset_class,
            "market_value": self.market_value,
            "book_value": self.book_value,
            "coupon_rate": self.coupon_rate,
            "duration_years": self.duration_years,
            "spread_bps": self.spread_bps,
            "downgrade_notches": self.downgrade_notches,
            "annual_default_probability": self.annual_default_probability,
            "recovery_rate": self.recovery_rate,
            "expected_default_loss_rate": self.expected_default_loss_rate,
            "maturity_years": self.maturity_years,
            "credit_rating": self.credit_rating,
            "currency": self.currency,
            "source_id": self.source_id,
            "limitation_id": self.limitation_id,
        }

    def to_asset_position(self) -> AssetPosition:
        """Convert to the legacy aggregate asset cashflow input."""
        asset_class = "Govt" if self.asset_class.lower().startswith("gov") else self.asset_class
        if asset_class not in {"Govt", "Equity", "Cash"}:
            asset_class = f"Credit_{self.credit_rating}" if self.credit_rating else "Credit"
        return AssetPosition(
            asset_class=asset_class,
            market_value=self.market_value,
            book_value=self.book_value,
            duration_years=self.duration_years,
            annual_yield=self.coupon_rate,
            annual_capital_growth=0.0,
            average_maturity_years=self.maturity_years,
            credit_rating=self.credit_rating,
        )


@dataclass(frozen=True)
class FixedIncomeProjectionResult:
    """Monthly projection output for fixed-income instruments."""

    cashflows: pd.DataFrame
    by_instrument: pd.DataFrame
    by_class_summary: pd.DataFrame
    pv_net_income: float
    total_default_loss: float
    total_principal_repayment: float


def fixed_income_market_value_after_shock(
    instrument: FixedIncomeInstrument,
    rate_shift_bps: float = 0.0,
    spread_shift_bps: float = 0.0,
    downgrade_spread_bps_per_notch: float = 75.0,
) -> float:
    """
    Duration-based market-value approximation after rate, spread, and downgrade shocks.

    The approximation is first order and intended for educational stress testing.
    Convexity, optionality, liquidity haircuts, and stochastic transition matrices
    are deliberately outside this first Phase 9 slice.
    """
    for name, value in {
        "rate_shift_bps": rate_shift_bps,
        "spread_shift_bps": spread_shift_bps,
        "downgrade_spread_bps_per_notch": downgrade_spread_bps_per_notch,
    }.items():
        _require_finite(name, float(value))

    total_shift = (
        rate_shift_bps
        + spread_shift_bps
        + instrument.downgrade_notches * downgrade_spread_bps_per_notch
    ) / 10_000.0
    shocked = instrument.market_value * (1.0 - instrument.duration_years * total_shift)
    return max(0.0, shocked)


def project_fixed_income_cashflows(
    instruments: Iterable[FixedIncomeInstrument],
    projection_months: int,
    discount_rate_annual: float = 0.035,
    rate_shift_bps: float = 0.0,
    spread_shift_bps: float = 0.0,
    downgrade_spread_bps_per_notch: float = 75.0,
) -> FixedIncomeProjectionResult:
    """Project monthly coupon income, spread carry, maturities, and default losses."""
    instruments = list(instruments)
    if projection_months <= 0:
        raise ValueError("projection_months must be positive")
    _require_finite("discount_rate_annual", float(discount_rate_annual))

    v_m = monthly_discount_factor(discount_rate_annual)
    remaining_mv = {inst.instrument_id: inst.market_value for inst in instruments}
    rows: List[Dict[str, object]] = []

    for month in range(1, projection_months + 1):
        discount_factor = v_m ** month
        for inst in instruments:
            mv_bom = remaining_mv[inst.instrument_id]
            coupon_income = mv_bom * inst.coupon_rate / 12.0
            spread_carry = mv_bom * inst.spread_bps / 10_000.0 / 12.0
            default_loss = mv_bom * inst.expected_default_loss_rate / 12.0

            maturity_month: Optional[int] = None
            if inst.maturity_years > 0.0:
                maturity_month = max(1, int(round(inst.maturity_years * 12.0)))
            principal_repayment = mv_bom if maturity_month == month else 0.0
            mv_eom = max(0.0, mv_bom - default_loss - principal_repayment)
            remaining_mv[inst.instrument_id] = mv_eom

            net_income = coupon_income - default_loss
            rows.append(
                {
                    "month": month,
                    "instrument_id": inst.instrument_id,
                    "asset_class": inst.asset_class,
                    "currency": inst.currency,
                    "credit_rating": inst.credit_rating,
                    "market_value_bom": mv_bom,
                    "coupon_income": coupon_income,
                    "spread_carry": spread_carry,
                    "default_loss": default_loss,
                    "principal_repayment": principal_repayment,
                    "net_income": net_income,
                    "market_value_eom": mv_eom,
                    "discount_factor": discount_factor,
                    "pv_net_income": net_income * discount_factor,
                }
            )

    cashflows = pd.DataFrame(rows)
    if cashflows.empty:
        cashflows = pd.DataFrame(
            columns=[
                "month",
                "instrument_id",
                "asset_class",
                "currency",
                "credit_rating",
                "market_value_bom",
                "coupon_income",
                "spread_carry",
                "default_loss",
                "principal_repayment",
                "net_income",
                "market_value_eom",
                "discount_factor",
                "pv_net_income",
            ]
        )

    by_instrument = pd.DataFrame(
        [
            {
                **inst.to_record(),
                "shocked_market_value": fixed_income_market_value_after_shock(
                    inst,
                    rate_shift_bps=rate_shift_bps,
                    spread_shift_bps=spread_shift_bps,
                    downgrade_spread_bps_per_notch=downgrade_spread_bps_per_notch,
                ),
            }
            for inst in instruments
        ]
    )

    if cashflows.empty:
        by_class_summary = pd.DataFrame(
            columns=[
                "asset_class",
                "coupon_income",
                "spread_carry",
                "default_loss",
                "principal_repayment",
                "net_income",
                "pv_net_income",
                "ending_market_value",
            ]
        )
    else:
        by_class_summary = (
            cashflows.groupby("asset_class", as_index=False)
            .agg(
                coupon_income=("coupon_income", "sum"),
                spread_carry=("spread_carry", "sum"),
                default_loss=("default_loss", "sum"),
                principal_repayment=("principal_repayment", "sum"),
                net_income=("net_income", "sum"),
                pv_net_income=("pv_net_income", "sum"),
            )
            .sort_values("asset_class")
            .reset_index(drop=True)
        )
        ending_mv = (
            cashflows[cashflows["month"] == projection_months]
            .groupby("asset_class", as_index=False)
            .agg(ending_market_value=("market_value_eom", "sum"))
        )
        by_class_summary = by_class_summary.merge(ending_mv, on="asset_class", how="left")

    return FixedIncomeProjectionResult(
        cashflows=cashflows,
        by_instrument=by_instrument,
        by_class_summary=by_class_summary,
        pv_net_income=float(cashflows["pv_net_income"].sum()) if not cashflows.empty else 0.0,
        total_default_loss=float(cashflows["default_loss"].sum()) if not cashflows.empty else 0.0,
        total_principal_repayment=float(cashflows["principal_repayment"].sum())
        if not cashflows.empty
        else 0.0,
    )


def default_phase9_fixed_income_instruments() -> List[FixedIncomeInstrument]:
    """Starter educational government and corporate bond holdings for Phase 9."""
    return [
        FixedIncomeInstrument(
            instrument_id="HK_GOVT_10Y_EDU",
            asset_class="Government",
            market_value=600_000.0,
            book_value=590_000.0,
            coupon_rate=0.030,
            duration_years=8.0,
            spread_bps=0.0,
            maturity_years=10.0,
            credit_rating="AA+",
            currency="HKD",
        ),
        FixedIncomeInstrument(
            instrument_id="HK_CORP_A_7Y_EDU",
            asset_class="Corporate",
            market_value=250_000.0,
            book_value=248_000.0,
            coupon_rate=0.045,
            duration_years=5.6,
            spread_bps=150.0,
            downgrade_notches=1,
            annual_default_probability=0.006,
            recovery_rate=0.40,
            maturity_years=7.0,
            credit_rating="A",
            currency="HKD",
        ),
    ]


__all__ = [
    "FixedIncomeInstrument",
    "FixedIncomeProjectionResult",
    "default_phase9_fixed_income_instruments",
    "fixed_income_market_value_after_shock",
    "project_fixed_income_cashflows",
]
