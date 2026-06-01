"""
Private asset educational models for Phase 9 ALM asset expansion.

The models are intentionally transparent and deterministic.  They expose the
cashflow and valuation drivers that are usually hidden inside private asset
return assumptions: credit loss, capital calls, distributions, valuation lags,
inflation linkage, availability, and revenue shocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Union

import numpy as np
import pandas as pd

from par_model_v2.projection.monthly_projection import AssetPosition, monthly_discount_factor


def _require_finite(name: str, value: float) -> None:
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _require_probability(name: str, value: float) -> None:
    _require_finite(name, value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")


def _smoothing_weight(months: int) -> float:
    if months <= 0:
        raise ValueError("valuation_smoothing_months must be positive")
    return min(1.0, 1.0 / float(months))


@dataclass(frozen=True)
class PrivateCreditAsset:
    """Private credit holding with explicit spread, loss, and liquidity fields."""

    asset_id: str
    strategy: str
    market_value: float
    book_value: float
    cash_yield: float
    spread_bps: float
    annual_default_probability: float
    recovery_rate: float = 0.40
    liquidity_lag_months: int = 3
    valuation_smoothing_months: int = 3
    maturity_years: float = 5.0
    currency: str = "HKD"
    source_id: str = "phase9-private-credit-placeholder"
    limitation_id: str = "PHASE9-PRIVATE-CREDIT-PLACEHOLDER"

    def __post_init__(self) -> None:
        if not self.asset_id:
            raise ValueError("asset_id is required")
        if not self.strategy:
            raise ValueError("strategy is required")
        if self.liquidity_lag_months < 0:
            raise ValueError("liquidity_lag_months must be non-negative")
        _validate_non_negative_fields(
            self,
            ("market_value", "book_value", "cash_yield", "spread_bps", "maturity_years"),
        )
        _require_probability("annual_default_probability", self.annual_default_probability)
        _require_probability("recovery_rate", self.recovery_rate)
        _smoothing_weight(self.valuation_smoothing_months)

    @property
    def expected_default_loss_rate(self) -> float:
        return self.annual_default_probability * (1.0 - self.recovery_rate)

    def to_record(self) -> Dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "asset_class": "PrivateCredit",
            "strategy": self.strategy,
            "market_value": self.market_value,
            "book_value": self.book_value,
            "cash_yield": self.cash_yield,
            "spread_bps": self.spread_bps,
            "annual_default_probability": self.annual_default_probability,
            "recovery_rate": self.recovery_rate,
            "expected_default_loss_rate": self.expected_default_loss_rate,
            "liquidity_lag_months": self.liquidity_lag_months,
            "valuation_smoothing_months": self.valuation_smoothing_months,
            "maturity_years": self.maturity_years,
            "currency": self.currency,
            "source_id": self.source_id,
            "limitation_id": self.limitation_id,
        }

    def to_asset_position(self) -> AssetPosition:
        return AssetPosition(
            asset_class="Credit_Private",
            market_value=self.market_value,
            book_value=self.book_value,
            annual_yield=self.cash_yield,
            annual_capital_growth=0.0,
            average_maturity_years=self.maturity_years,
            credit_rating="Private",
        )


@dataclass(frozen=True)
class PrivateEquityAsset:
    """Private equity commitment with capital calls, J-curve, and distributions."""

    asset_id: str
    strategy: str
    funded_nav: float
    unfunded_commitment: float
    book_value: float
    annual_call_rate: float
    annual_distribution_rate: float
    annual_nav_growth_rate: float
    j_curve_months: int = 24
    j_curve_drag_annual: float = 0.04
    valuation_lag_months: int = 3
    valuation_smoothing_months: int = 4
    currency: str = "HKD"
    source_id: str = "phase9-private-equity-placeholder"
    limitation_id: str = "PHASE9-PRIVATE-EQUITY-PLACEHOLDER"

    def __post_init__(self) -> None:
        if not self.asset_id:
            raise ValueError("asset_id is required")
        if not self.strategy:
            raise ValueError("strategy is required")
        if self.j_curve_months < 0:
            raise ValueError("j_curve_months must be non-negative")
        if self.valuation_lag_months < 0:
            raise ValueError("valuation_lag_months must be non-negative")
        _validate_non_negative_fields(
            self,
            (
                "funded_nav",
                "unfunded_commitment",
                "book_value",
                "annual_call_rate",
                "annual_distribution_rate",
                "j_curve_drag_annual",
            ),
        )
        _require_finite("annual_nav_growth_rate", self.annual_nav_growth_rate)
        _smoothing_weight(self.valuation_smoothing_months)

    def to_record(self) -> Dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "asset_class": "PrivateEquity",
            "strategy": self.strategy,
            "market_value": self.funded_nav,
            "book_value": self.book_value,
            "funded_nav": self.funded_nav,
            "unfunded_commitment": self.unfunded_commitment,
            "annual_call_rate": self.annual_call_rate,
            "annual_distribution_rate": self.annual_distribution_rate,
            "annual_nav_growth_rate": self.annual_nav_growth_rate,
            "j_curve_months": self.j_curve_months,
            "j_curve_drag_annual": self.j_curve_drag_annual,
            "valuation_lag_months": self.valuation_lag_months,
            "valuation_smoothing_months": self.valuation_smoothing_months,
            "currency": self.currency,
            "source_id": self.source_id,
            "limitation_id": self.limitation_id,
        }

    def to_asset_position(self) -> AssetPosition:
        return AssetPosition(
            asset_class="Equity",
            market_value=self.funded_nav,
            book_value=self.book_value,
            annual_yield=self.annual_distribution_rate,
            annual_capital_growth=self.annual_nav_growth_rate,
        )


@dataclass(frozen=True)
class InfrastructureAsset:
    """Infrastructure holding with inflation linkage and revenue stress fields."""

    asset_id: str
    project_type: str
    market_value: float
    book_value: float
    cash_yield: float
    inflation_linkage: float
    inflation_assumption: float
    availability_factor: float = 1.0
    revenue_shock: float = 0.0
    duration_years: float = 12.0
    concession_years: float = 25.0
    valuation_smoothing_months: int = 6
    currency: str = "HKD"
    source_id: str = "phase9-infrastructure-placeholder"
    limitation_id: str = "PHASE9-INFRASTRUCTURE-PLACEHOLDER"

    def __post_init__(self) -> None:
        if not self.asset_id:
            raise ValueError("asset_id is required")
        if not self.project_type:
            raise ValueError("project_type is required")
        _validate_non_negative_fields(
            self,
            (
                "market_value",
                "book_value",
                "cash_yield",
                "inflation_linkage",
                "duration_years",
                "concession_years",
            ),
        )
        _require_finite("inflation_assumption", self.inflation_assumption)
        _require_finite("revenue_shock", self.revenue_shock)
        _require_probability("availability_factor", self.availability_factor)
        if self.revenue_shock < -1.0:
            raise ValueError("revenue_shock must be greater than or equal to -1")
        _smoothing_weight(self.valuation_smoothing_months)

    def to_record(self) -> Dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "asset_class": "Infrastructure",
            "project_type": self.project_type,
            "market_value": self.market_value,
            "book_value": self.book_value,
            "cash_yield": self.cash_yield,
            "inflation_linkage": self.inflation_linkage,
            "inflation_assumption": self.inflation_assumption,
            "availability_factor": self.availability_factor,
            "revenue_shock": self.revenue_shock,
            "duration_years": self.duration_years,
            "concession_years": self.concession_years,
            "valuation_smoothing_months": self.valuation_smoothing_months,
            "currency": self.currency,
            "source_id": self.source_id,
            "limitation_id": self.limitation_id,
        }

    def to_asset_position(self) -> AssetPosition:
        return AssetPosition(
            asset_class="Infrastructure",
            market_value=self.market_value,
            book_value=self.book_value,
            duration_years=self.duration_years,
            annual_yield=self.cash_yield,
            annual_capital_growth=self.inflation_linkage * self.inflation_assumption,
            average_maturity_years=self.concession_years,
        )


PrivateAsset = Union[PrivateCreditAsset, PrivateEquityAsset, InfrastructureAsset]


@dataclass(frozen=True)
class PrivateAssetProjectionResult:
    """Monthly private asset projection output."""

    cashflows: pd.DataFrame
    by_asset: pd.DataFrame
    by_class_summary: pd.DataFrame
    pv_net_cashflow: float
    total_default_loss: float
    total_capital_calls: float
    total_distributions: float


def _validate_non_negative_fields(obj: object, fields: Iterable[str]) -> None:
    for name in fields:
        value = float(getattr(obj, name))
        _require_finite(name, value)
        if value < 0.0:
            raise ValueError(f"{name} must be non-negative")


def project_private_asset_cashflows(
    assets: Iterable[PrivateAsset],
    projection_months: int,
    discount_rate_annual: float = 0.035,
) -> PrivateAssetProjectionResult:
    """
    Project monthly private asset cashflows and smoothed reporting NAV.

    The projection is deterministic and educational.  It should be used for
    governance, reporting-schema, and stress-test examples only until calibrated
    private asset assumptions are approved by the model owner.
    """
    assets = list(assets)
    if projection_months <= 0:
        raise ValueError("projection_months must be positive")
    _require_finite("discount_rate_annual", discount_rate_annual)

    v_m = monthly_discount_factor(discount_rate_annual)
    rows: List[Dict[str, object]] = []
    state = _initial_private_asset_state(assets)

    for month in range(1, projection_months + 1):
        discount_factor = v_m ** month
        for asset in assets:
            if isinstance(asset, PrivateCreditAsset):
                row = _project_private_credit_month(asset, state[asset.asset_id], month)
            elif isinstance(asset, PrivateEquityAsset):
                row = _project_private_equity_month(asset, state[asset.asset_id], month)
            elif isinstance(asset, InfrastructureAsset):
                row = _project_infrastructure_month(asset, state[asset.asset_id], month)
            else:
                raise TypeError(f"Unsupported private asset type: {type(asset)!r}")

            row["discount_factor"] = discount_factor
            row["pv_net_cashflow"] = row["net_cashflow"] * discount_factor
            rows.append(row)

    cashflows = pd.DataFrame(rows)
    by_asset = pd.DataFrame([asset.to_record() for asset in assets])
    by_class_summary = _private_asset_summary(cashflows, projection_months)

    return PrivateAssetProjectionResult(
        cashflows=cashflows,
        by_asset=by_asset,
        by_class_summary=by_class_summary,
        pv_net_cashflow=float(cashflows["pv_net_cashflow"].sum()) if not cashflows.empty else 0.0,
        total_default_loss=float(cashflows["default_loss"].sum()) if not cashflows.empty else 0.0,
        total_capital_calls=float(cashflows["capital_call"].sum()) if not cashflows.empty else 0.0,
        total_distributions=float(cashflows["distribution"].sum()) if not cashflows.empty else 0.0,
    )


def _initial_private_asset_state(assets: Iterable[PrivateAsset]) -> Dict[str, Dict[str, float]]:
    state: Dict[str, Dict[str, float]] = {}
    for asset in assets:
        if isinstance(asset, PrivateCreditAsset):
            state[asset.asset_id] = {
                "economic_nav": asset.market_value,
                "reported_nav": asset.market_value,
            }
        elif isinstance(asset, PrivateEquityAsset):
            state[asset.asset_id] = {
                "economic_nav": asset.funded_nav,
                "reported_nav": asset.funded_nav,
                "unfunded_commitment": asset.unfunded_commitment,
            }
        elif isinstance(asset, InfrastructureAsset):
            state[asset.asset_id] = {
                "economic_nav": asset.market_value,
                "reported_nav": asset.market_value,
            }
        else:
            raise TypeError(f"Unsupported private asset type: {type(asset)!r}")
    return state


def _base_row(
    month: int,
    asset_id: str,
    asset_class: str,
    currency: str,
    economic_nav_bom: float,
    reported_nav_bom: float,
) -> Dict[str, object]:
    return {
        "month": month,
        "asset_id": asset_id,
        "asset_class": asset_class,
        "currency": currency,
        "economic_nav_bom": economic_nav_bom,
        "reported_nav_bom": reported_nav_bom,
        "cash_income": 0.0,
        "spread_income": 0.0,
        "default_loss": 0.0,
        "capital_call": 0.0,
        "distribution": 0.0,
        "nav_growth": 0.0,
        "inflation_uplift": 0.0,
        "revenue_shock_loss": 0.0,
        "principal_repayment": 0.0,
        "net_cashflow": 0.0,
        "economic_nav_eom": 0.0,
        "reported_nav_eom": 0.0,
        "liquidity_lag_months": 0,
        "valuation_lag_months": 0,
        "valuation_smoothing_months": 0,
    }


def _project_private_credit_month(
    asset: PrivateCreditAsset,
    state: Dict[str, float],
    month: int,
) -> Dict[str, object]:
    econ_bom = state["economic_nav"]
    reported_bom = state["reported_nav"]
    cash_income = econ_bom * asset.cash_yield / 12.0
    spread_income = econ_bom * asset.spread_bps / 10_000.0 / 12.0
    default_loss = econ_bom * asset.expected_default_loss_rate / 12.0
    maturity_month = max(1, int(round(asset.maturity_years * 12.0)))
    principal = econ_bom if month == maturity_month + asset.liquidity_lag_months else 0.0
    econ_eom = max(0.0, econ_bom - default_loss - principal)
    reported_eom = reported_bom + _smoothing_weight(asset.valuation_smoothing_months) * (
        econ_eom - reported_bom
    )

    state["economic_nav"] = econ_eom
    state["reported_nav"] = reported_eom

    row = _base_row(month, asset.asset_id, "PrivateCredit", asset.currency, econ_bom, reported_bom)
    row.update(
        {
            "cash_income": cash_income,
            "spread_income": spread_income,
            "default_loss": default_loss,
            "principal_repayment": principal,
            "net_cashflow": cash_income + spread_income + principal - default_loss,
            "economic_nav_eom": econ_eom,
            "reported_nav_eom": reported_eom,
            "liquidity_lag_months": asset.liquidity_lag_months,
            "valuation_smoothing_months": asset.valuation_smoothing_months,
        }
    )
    return row


def _project_private_equity_month(
    asset: PrivateEquityAsset,
    state: Dict[str, float],
    month: int,
) -> Dict[str, object]:
    econ_bom = state["economic_nav"]
    reported_bom = state["reported_nav"]
    unfunded_bom = state["unfunded_commitment"]
    capital_call = min(unfunded_bom, unfunded_bom * asset.annual_call_rate / 12.0)
    distribution = econ_bom * asset.annual_distribution_rate / 12.0
    j_curve_drag = asset.j_curve_drag_annual if month <= asset.j_curve_months else 0.0
    nav_growth = econ_bom * (asset.annual_nav_growth_rate - j_curve_drag) / 12.0
    econ_eom = max(0.0, econ_bom + capital_call + nav_growth - distribution)
    reported_eom = reported_bom + _smoothing_weight(asset.valuation_smoothing_months) * (
        econ_eom - reported_bom
    )

    state["economic_nav"] = econ_eom
    state["reported_nav"] = reported_eom
    state["unfunded_commitment"] = max(0.0, unfunded_bom - capital_call)

    row = _base_row(month, asset.asset_id, "PrivateEquity", asset.currency, econ_bom, reported_bom)
    row.update(
        {
            "capital_call": capital_call,
            "distribution": distribution,
            "nav_growth": nav_growth,
            "net_cashflow": distribution - capital_call,
            "economic_nav_eom": econ_eom,
            "reported_nav_eom": reported_eom,
            "valuation_lag_months": asset.valuation_lag_months,
            "valuation_smoothing_months": asset.valuation_smoothing_months,
        }
    )
    return row


def _project_infrastructure_month(
    asset: InfrastructureAsset,
    state: Dict[str, float],
    month: int,
) -> Dict[str, object]:
    econ_bom = state["economic_nav"]
    reported_bom = state["reported_nav"]
    inflation_uplift = econ_bom * asset.inflation_linkage * asset.inflation_assumption / 12.0
    revenue_shock_loss = max(0.0, -asset.revenue_shock) * econ_bom * asset.cash_yield / 12.0
    cash_income = (
        econ_bom
        * asset.cash_yield
        * asset.availability_factor
        * max(0.0, 1.0 + asset.revenue_shock)
        / 12.0
    )
    econ_eom = max(0.0, econ_bom + inflation_uplift)
    reported_eom = reported_bom + _smoothing_weight(asset.valuation_smoothing_months) * (
        econ_eom - reported_bom
    )

    state["economic_nav"] = econ_eom
    state["reported_nav"] = reported_eom

    row = _base_row(month, asset.asset_id, "Infrastructure", asset.currency, econ_bom, reported_bom)
    row.update(
        {
            "cash_income": cash_income,
            "inflation_uplift": inflation_uplift,
            "revenue_shock_loss": revenue_shock_loss,
            "net_cashflow": cash_income,
            "economic_nav_eom": econ_eom,
            "reported_nav_eom": reported_eom,
            "valuation_smoothing_months": asset.valuation_smoothing_months,
        }
    )
    return row


def _private_asset_summary(cashflows: pd.DataFrame, projection_months: int) -> pd.DataFrame:
    columns = [
        "asset_class",
        "cash_income",
        "spread_income",
        "default_loss",
        "capital_call",
        "distribution",
        "nav_growth",
        "inflation_uplift",
        "net_cashflow",
        "pv_net_cashflow",
        "ending_reported_nav",
    ]
    if cashflows.empty:
        return pd.DataFrame(columns=columns)

    summary = (
        cashflows.groupby("asset_class", as_index=False)
        .agg(
            cash_income=("cash_income", "sum"),
            spread_income=("spread_income", "sum"),
            default_loss=("default_loss", "sum"),
            capital_call=("capital_call", "sum"),
            distribution=("distribution", "sum"),
            nav_growth=("nav_growth", "sum"),
            inflation_uplift=("inflation_uplift", "sum"),
            net_cashflow=("net_cashflow", "sum"),
            pv_net_cashflow=("pv_net_cashflow", "sum"),
        )
        .sort_values("asset_class")
        .reset_index(drop=True)
    )
    ending_nav = (
        cashflows[cashflows["month"] == projection_months]
        .groupby("asset_class", as_index=False)
        .agg(ending_reported_nav=("reported_nav_eom", "sum"))
    )
    return summary.merge(ending_nav, on="asset_class", how="left")


def default_phase9_private_assets() -> List[PrivateAsset]:
    """Starter educational private asset holdings for Phase 9."""
    return [
        PrivateCreditAsset(
            asset_id="HK_PC_DIRECT_LENDING_EDU",
            strategy="Senior secured direct lending",
            market_value=180_000.0,
            book_value=178_000.0,
            cash_yield=0.075,
            spread_bps=420.0,
            annual_default_probability=0.018,
            recovery_rate=0.50,
            liquidity_lag_months=3,
            valuation_smoothing_months=3,
            maturity_years=4.0,
        ),
        PrivateEquityAsset(
            asset_id="HK_PE_BUYOUT_EDU",
            strategy="Diversified buyout fund",
            funded_nav=125_000.0,
            unfunded_commitment=75_000.0,
            book_value=120_000.0,
            annual_call_rate=0.30,
            annual_distribution_rate=0.08,
            annual_nav_growth_rate=0.11,
            j_curve_months=24,
            j_curve_drag_annual=0.04,
            valuation_lag_months=3,
            valuation_smoothing_months=4,
        ),
        InfrastructureAsset(
            asset_id="HK_INFRA_AVAILABILITY_EDU",
            project_type="Availability-based infrastructure",
            market_value=210_000.0,
            book_value=205_000.0,
            cash_yield=0.055,
            inflation_linkage=0.70,
            inflation_assumption=0.025,
            availability_factor=0.98,
            revenue_shock=-0.05,
            duration_years=13.0,
            concession_years=25.0,
            valuation_smoothing_months=6,
        ),
    ]


__all__ = [
    "InfrastructureAsset",
    "PrivateAsset",
    "PrivateAssetProjectionResult",
    "PrivateCreditAsset",
    "PrivateEquityAsset",
    "default_phase9_private_assets",
    "project_private_asset_cashflows",
]
