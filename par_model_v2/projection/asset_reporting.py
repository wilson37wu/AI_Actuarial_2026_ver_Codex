"""
Asset cashflow aggregation and market-value roll-forward reporting.

This Phase 9 module normalizes the fixed-income, private-asset, and derivative
examples into one monthly attribution view.  The output is intended for
educational ALM reporting and governance evidence, not production valuation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

import numpy as np
import pandas as pd

from par_model_v2.projection.derivatives import (
    BondForwardContract,
    DerivativeValuationResult,
    InterestRateSwapContract,
    default_phase9_derivative_examples,
    value_derivative_portfolio,
)
from par_model_v2.projection.fixed_income import (
    FixedIncomeInstrument,
    FixedIncomeProjectionResult,
    default_phase9_fixed_income_instruments,
    project_fixed_income_cashflows,
)
from par_model_v2.projection.private_assets import (
    PrivateAsset,
    PrivateAssetProjectionResult,
    default_phase9_private_assets,
    project_private_asset_cashflows,
)
from par_model_v2.stochastic import RiskFreeCurve


ROLLFORWARD_COLUMNS = [
    "month",
    "source_type",
    "instrument_id",
    "asset_class",
    "currency",
    "market_value_bom",
    "cash_income",
    "spread_income",
    "default_loss",
    "capital_call",
    "distribution",
    "principal_repayment",
    "derivative_cashflow",
    "market_value_change",
    "market_value_eom",
    "net_cashflow",
    "reported_market_value_eom",
]


@dataclass(frozen=True)
class AssetRollForwardReport:
    """Aggregated Phase 9 asset reporting output."""

    monthly_rollforward: pd.DataFrame
    by_class_attribution: pd.DataFrame
    source_summary: pd.DataFrame
    opening_market_value: float
    ending_market_value: float
    net_cashflow: float
    market_value_change: float
    governance_notes: List[str]


def aggregate_asset_rollforward(
    fixed_income: Optional[FixedIncomeProjectionResult] = None,
    private_assets: Optional[PrivateAssetProjectionResult] = None,
    derivatives: Optional[DerivativeValuationResult] = None,
    projection_months: Optional[int] = None,
) -> AssetRollForwardReport:
    """
    Combine asset-library projection outputs into a single monthly roll-forward.

    The attribution identity is:

    `EOM MV = BOM MV + capital calls - distributions - principal repayments
    - default losses + market value change`.

    Cash income and derivative cashflows are reported separately because they
    normally flow through income / hedge-settlement reporting rather than
    changing the holding market value directly.
    """
    projection_months = _infer_projection_months(
        projection_months,
        fixed_income,
        private_assets,
        derivatives,
    )
    if projection_months <= 0:
        raise ValueError("projection_months must be positive")

    frames: List[pd.DataFrame] = []
    if fixed_income is not None:
        frames.append(_normalize_fixed_income(fixed_income.cashflows))
    if private_assets is not None:
        frames.append(_normalize_private_assets(private_assets.cashflows))
    if derivatives is not None:
        frames.append(_normalize_derivatives(derivatives, projection_months))

    if frames:
        monthly = pd.concat(frames, ignore_index=True)
        monthly = monthly.reindex(columns=ROLLFORWARD_COLUMNS)
        monthly = monthly.sort_values(
            ["month", "source_type", "asset_class", "instrument_id"],
        ).reset_index(drop=True)
    else:
        monthly = pd.DataFrame(columns=ROLLFORWARD_COLUMNS)

    by_class = _class_attribution(monthly, projection_months)
    source_summary = _source_summary(monthly, projection_months)

    opening_mv = _month_sum(monthly, 1, "market_value_bom")
    ending_mv = _month_sum(monthly, projection_months, "market_value_eom")
    net_cashflow = float(monthly["net_cashflow"].sum()) if not monthly.empty else 0.0
    mv_change = float(monthly["market_value_change"].sum()) if not monthly.empty else 0.0

    return AssetRollForwardReport(
        monthly_rollforward=monthly,
        by_class_attribution=by_class,
        source_summary=source_summary,
        opening_market_value=opening_mv,
        ending_market_value=ending_mv,
        net_cashflow=net_cashflow,
        market_value_change=mv_change,
        governance_notes=[
            "SOA ASOP 7 / ASOP 56: income, principal, losses, capital activity, "
            "derivative settlements, and valuation movement are reported separately.",
            "IA TAS M: source_type and instrument_id preserve traceability from "
            "instrument projection outputs to class-level reporting.",
            "ERM limitation: deterministic educational roll-forward excludes "
            "stochastic default timing, liquidity haircuts, CVA, and production "
            "accounting classifications.",
        ],
    )


def project_phase9_asset_rollforward(
    projection_months: int,
    discount_rate_annual: float = 0.035,
    fixed_income_instruments: Optional[Iterable[FixedIncomeInstrument]] = None,
    private_asset_holdings: Optional[Iterable[PrivateAsset]] = None,
    swaps: Optional[Iterable[InterestRateSwapContract]] = None,
    bond_forwards: Optional[Iterable[BondForwardContract]] = None,
    discount_curve: Optional[RiskFreeCurve] = None,
) -> AssetRollForwardReport:
    """Build a complete starter Phase 9 asset roll-forward report."""
    if projection_months <= 0:
        raise ValueError("projection_months must be positive")

    if fixed_income_instruments is None:
        fixed_income_instruments = default_phase9_fixed_income_instruments()
    if private_asset_holdings is None:
        private_asset_holdings = default_phase9_private_assets()
    if swaps is None or bond_forwards is None:
        examples = default_phase9_derivative_examples()
        if swaps is None:
            swaps = examples["swaps"]
        if bond_forwards is None:
            bond_forwards = examples["bond_forwards"]
    if discount_curve is None:
        discount_curve = RiskFreeCurve.flat(
            discount_rate_annual,
            currency="HKD",
            market="HK",
            valuation_date="2026-06-02",
            curve_id="HKD-PHASE9-ROLLFORWARD-FLAT",
            source_id="phase9-asset-rollforward-placeholder",
        )

    fixed_income = project_fixed_income_cashflows(
        fixed_income_instruments,
        projection_months=projection_months,
        discount_rate_annual=discount_rate_annual,
    )
    private_assets = project_private_asset_cashflows(
        private_asset_holdings,
        projection_months=projection_months,
        discount_rate_annual=discount_rate_annual,
    )
    derivatives = value_derivative_portfolio(swaps, bond_forwards, discount_curve)

    return aggregate_asset_rollforward(
        fixed_income=fixed_income,
        private_assets=private_assets,
        derivatives=derivatives,
        projection_months=projection_months,
    )


def _infer_projection_months(
    projection_months: Optional[int],
    fixed_income: Optional[FixedIncomeProjectionResult],
    private_assets: Optional[PrivateAssetProjectionResult],
    derivatives: Optional[DerivativeValuationResult],
) -> int:
    if projection_months is not None:
        return int(projection_months)

    candidate_months: List[int] = []
    for result in (fixed_income, private_assets):
        if result is not None and not result.cashflows.empty:
            candidate_months.append(int(result.cashflows["month"].max()))
    if derivatives is not None and not derivatives.cashflow_schedule.empty:
        candidate_months.append(
            int(np.ceil(derivatives.cashflow_schedule["payment_time_years"].max() * 12.0))
        )
    return max(candidate_months) if candidate_months else 0


def _normalize_fixed_income(cashflows: pd.DataFrame) -> pd.DataFrame:
    if cashflows.empty:
        return pd.DataFrame(columns=ROLLFORWARD_COLUMNS)

    normalized = pd.DataFrame(
        {
            "month": cashflows["month"],
            "source_type": "FixedIncome",
            "instrument_id": cashflows["instrument_id"],
            "asset_class": cashflows["asset_class"],
            "currency": cashflows["currency"],
            "market_value_bom": cashflows["market_value_bom"],
            "cash_income": cashflows["coupon_income"],
            "spread_income": cashflows["spread_carry"],
            "default_loss": cashflows["default_loss"],
            "capital_call": 0.0,
            "distribution": 0.0,
            "principal_repayment": cashflows["principal_repayment"],
            "derivative_cashflow": 0.0,
            "market_value_change": (
                cashflows["market_value_eom"]
                - cashflows["market_value_bom"]
                + cashflows["default_loss"]
                + cashflows["principal_repayment"]
            ),
            "market_value_eom": cashflows["market_value_eom"],
            "net_cashflow": (
                cashflows["coupon_income"]
                + cashflows["spread_carry"]
                + cashflows["principal_repayment"]
                - cashflows["default_loss"]
            ),
            "reported_market_value_eom": cashflows["market_value_eom"],
        }
    )
    return normalized


def _normalize_private_assets(cashflows: pd.DataFrame) -> pd.DataFrame:
    if cashflows.empty:
        return pd.DataFrame(columns=ROLLFORWARD_COLUMNS)

    normalized = pd.DataFrame(
        {
            "month": cashflows["month"],
            "source_type": "PrivateAsset",
            "instrument_id": cashflows["asset_id"],
            "asset_class": cashflows["asset_class"],
            "currency": cashflows["currency"],
            "market_value_bom": cashflows["economic_nav_bom"],
            "cash_income": cashflows["cash_income"],
            "spread_income": cashflows["spread_income"],
            "default_loss": cashflows["default_loss"],
            "capital_call": cashflows["capital_call"],
            "distribution": cashflows["distribution"],
            "principal_repayment": cashflows["principal_repayment"],
            "derivative_cashflow": 0.0,
            "market_value_change": (
                cashflows["economic_nav_eom"]
                - cashflows["economic_nav_bom"]
                - cashflows["capital_call"]
                + cashflows["distribution"]
                + cashflows["principal_repayment"]
                + cashflows["default_loss"]
            ),
            "market_value_eom": cashflows["economic_nav_eom"],
            "net_cashflow": cashflows["net_cashflow"],
            "reported_market_value_eom": cashflows["reported_nav_eom"],
        }
    )
    return normalized


def _normalize_derivatives(
    derivatives: DerivativeValuationResult,
    projection_months: int,
) -> pd.DataFrame:
    rows: List[dict] = []
    valuations = derivatives.valuations
    if valuations.empty:
        return pd.DataFrame(columns=ROLLFORWARD_COLUMNS)

    schedule = derivatives.cashflow_schedule.copy()
    if schedule.empty:
        schedule = pd.DataFrame(columns=["instrument_id", "payment_time_years"])

    for _, valuation in valuations.iterrows():
        instrument_id = valuation["instrument_id"]
        derivative_type = valuation["derivative_type"]
        mv = float(valuation["market_value"])
        instrument_schedule = schedule[schedule.get("instrument_id") == instrument_id]

        cashflow_by_month = _derivative_cashflow_by_month(instrument_schedule)
        for month in range(1, projection_months + 1):
            derivative_cashflow = cashflow_by_month.get(month, 0.0)
            rows.append(
                {
                    "month": month,
                    "source_type": "Derivative",
                    "instrument_id": instrument_id,
                    "asset_class": f"Derivative:{derivative_type}",
                    "currency": valuation.get("currency", ""),
                    "market_value_bom": mv,
                    "cash_income": 0.0,
                    "spread_income": 0.0,
                    "default_loss": 0.0,
                    "capital_call": 0.0,
                    "distribution": 0.0,
                    "principal_repayment": 0.0,
                    "derivative_cashflow": derivative_cashflow,
                    "market_value_change": 0.0,
                    "market_value_eom": mv,
                    "net_cashflow": derivative_cashflow,
                    "reported_market_value_eom": mv,
                }
            )
    return pd.DataFrame(rows)


def _derivative_cashflow_by_month(schedule: pd.DataFrame) -> dict:
    if schedule.empty:
        return {}

    schedule = schedule.copy()
    schedule["month"] = np.ceil(schedule["payment_time_years"] * 12.0).astype(int)
    if "net_cashflow" in schedule.columns and "cashflow" in schedule.columns:
        cashflow = schedule["net_cashflow"].fillna(schedule["cashflow"]).fillna(0.0)
    elif "net_cashflow" in schedule.columns:
        cashflow = schedule["net_cashflow"].fillna(0.0)
    else:
        cashflow = schedule["cashflow"].fillna(0.0)
    schedule["derivative_cashflow"] = cashflow
    return schedule.groupby("month")["derivative_cashflow"].sum().to_dict()


def _class_attribution(monthly: pd.DataFrame, projection_months: int) -> pd.DataFrame:
    columns = [
        "asset_class",
        "source_type",
        "opening_market_value",
        "ending_market_value",
        "ending_reported_market_value",
        "cash_income",
        "spread_income",
        "default_loss",
        "capital_call",
        "distribution",
        "principal_repayment",
        "derivative_cashflow",
        "net_cashflow",
        "market_value_change",
    ]
    if monthly.empty:
        return pd.DataFrame(columns=columns)

    grouped = monthly.groupby(["asset_class", "source_type"], as_index=False).agg(
        cash_income=("cash_income", "sum"),
        spread_income=("spread_income", "sum"),
        default_loss=("default_loss", "sum"),
        capital_call=("capital_call", "sum"),
        distribution=("distribution", "sum"),
        principal_repayment=("principal_repayment", "sum"),
        derivative_cashflow=("derivative_cashflow", "sum"),
        net_cashflow=("net_cashflow", "sum"),
        market_value_change=("market_value_change", "sum"),
    )
    opening = (
        monthly[monthly["month"] == 1]
        .groupby(["asset_class", "source_type"], as_index=False)
        .agg(opening_market_value=("market_value_bom", "sum"))
    )
    ending = (
        monthly[monthly["month"] == projection_months]
        .groupby(["asset_class", "source_type"], as_index=False)
        .agg(
            ending_market_value=("market_value_eom", "sum"),
            ending_reported_market_value=("reported_market_value_eom", "sum"),
        )
    )
    return (
        grouped.merge(opening, on=["asset_class", "source_type"], how="left")
        .merge(ending, on=["asset_class", "source_type"], how="left")
        .reindex(columns=columns)
        .sort_values(["source_type", "asset_class"])
        .reset_index(drop=True)
    )


def _source_summary(monthly: pd.DataFrame, projection_months: int) -> pd.DataFrame:
    if monthly.empty:
        return pd.DataFrame(
            columns=[
                "source_type",
                "opening_market_value",
                "ending_market_value",
                "net_cashflow",
                "market_value_change",
            ]
        )

    summary = monthly.groupby("source_type", as_index=False).agg(
        net_cashflow=("net_cashflow", "sum"),
        market_value_change=("market_value_change", "sum"),
    )
    opening = (
        monthly[monthly["month"] == 1]
        .groupby("source_type", as_index=False)
        .agg(opening_market_value=("market_value_bom", "sum"))
    )
    ending = (
        monthly[monthly["month"] == projection_months]
        .groupby("source_type", as_index=False)
        .agg(ending_market_value=("market_value_eom", "sum"))
    )
    return (
        summary.merge(opening, on="source_type", how="left")
        .merge(ending, on="source_type", how="left")
        .sort_values("source_type")
        .reset_index(drop=True)
    )


def _month_sum(monthly: pd.DataFrame, month: int, column: str) -> float:
    if monthly.empty:
        return 0.0
    return float(monthly.loc[monthly["month"] == month, column].sum())


__all__ = [
    "AssetRollForwardReport",
    "aggregate_asset_rollforward",
    "project_phase9_asset_rollforward",
]
