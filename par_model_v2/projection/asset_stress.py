"""
Asset class stress testing for the Phase 9 educational asset library.

The module provides deterministic stress attribution for fixed income, private
assets, and derivative examples.  It is intended for governance evidence and
ALM teaching packs, not production market-risk capital.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

import numpy as np
import pandas as pd

from par_model_v2.projection.derivatives import (
    BondForwardContract,
    InterestRateSwapContract,
    default_phase9_derivative_examples,
    value_derivative_portfolio,
)
from par_model_v2.projection.fixed_income import (
    FixedIncomeInstrument,
    default_phase9_fixed_income_instruments,
    fixed_income_market_value_after_shock,
)
from par_model_v2.projection.private_assets import (
    InfrastructureAsset,
    PrivateAsset,
    PrivateCreditAsset,
    PrivateEquityAsset,
    default_phase9_private_assets,
)
from par_model_v2.stochastic import RiskFreeCurve


STRESS_RESULT_COLUMNS = [
    "scenario_id",
    "scenario_description",
    "source_type",
    "instrument_id",
    "asset_class",
    "currency",
    "base_market_value",
    "stressed_market_value",
    "market_value_impact",
    "impact_pct",
    "stress_driver",
    "governance_note",
]


@dataclass(frozen=True)
class AssetStressScenario:
    """Deterministic asset stress definition for Phase 9 reporting."""

    scenario_id: str
    description: str
    rate_shift_bps: float = 0.0
    spread_shift_bps: float = 0.0
    downgrade_spread_bps_per_notch: float = 0.0
    private_credit_default_multiplier: float = 1.0
    private_credit_recovery_shift: float = 0.0
    private_equity_nav_shock: float = 0.0
    infrastructure_inflation_shift: float = 0.0
    infrastructure_revenue_shock: float = 0.0
    derivative_curve_shift_bps: float = 0.0
    governance_note: str = "Educational deterministic stress; not calibrated market-risk capital."

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("scenario_id is required")
        if not self.description:
            raise ValueError("description is required")
        for name in (
            "rate_shift_bps",
            "spread_shift_bps",
            "downgrade_spread_bps_per_notch",
            "private_credit_default_multiplier",
            "private_credit_recovery_shift",
            "private_equity_nav_shock",
            "infrastructure_inflation_shift",
            "infrastructure_revenue_shock",
            "derivative_curve_shift_bps",
        ):
            value = float(getattr(self, name))
            if not np.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.private_credit_default_multiplier < 0.0:
            raise ValueError("private_credit_default_multiplier must be non-negative")
        if self.private_equity_nav_shock < -1.0:
            raise ValueError("private_equity_nav_shock must be greater than or equal to -1")
        if self.infrastructure_revenue_shock < -1.0:
            raise ValueError("infrastructure_revenue_shock must be greater than or equal to -1")


@dataclass(frozen=True)
class AssetStressReport:
    """Phase 9 asset stress result with instrument and class attribution."""

    stress_results: pd.DataFrame
    scenario_summary: pd.DataFrame
    governance_notes: List[str]


def default_phase9_asset_stress_scenarios() -> List[AssetStressScenario]:
    """Starter governed stress scenarios for the Phase 9 asset examples."""
    return [
        AssetStressScenario(
            scenario_id="HKD_RATE_UP_150BP",
            description="HKD rates increase by 150 bps with matching derivative curve shock.",
            rate_shift_bps=150.0,
            derivative_curve_shift_bps=150.0,
            governance_note=(
                "ERM rate-risk stress: duration and curve-valuation impacts only; "
                "convexity, optionality, and liquidity are not calibrated."
            ),
        ),
        AssetStressScenario(
            scenario_id="CREDIT_SPREAD_DEFAULT_STRESS",
            description="Credit spreads widen, downgrade spread allowance applies, and private credit losses increase.",
            spread_shift_bps=125.0,
            downgrade_spread_bps_per_notch=75.0,
            private_credit_default_multiplier=2.0,
            private_credit_recovery_shift=-0.15,
            governance_note=(
                "ERM credit-risk stress: spread and expected-loss effects are explicit; "
                "transition matrices and stochastic default timing are outside scope."
            ),
        ),
        AssetStressScenario(
            scenario_id="PRIVATE_MARKET_LIQUIDITY_STRESS",
            description="Private equity NAV markdown, private credit loss pressure, and infrastructure revenue stress.",
            private_credit_default_multiplier=1.5,
            private_credit_recovery_shift=-0.10,
            private_equity_nav_shock=-0.20,
            infrastructure_revenue_shock=-0.20,
            governance_note=(
                "Private-asset stress: NAV markdowns and cash-yield pressure are deterministic "
                "proxies until calibrated liquidity and appraisal data are available."
            ),
        ),
        AssetStressScenario(
            scenario_id="INFLATION_DOWNSIDE_STRESS",
            description="Inflation-linked infrastructure uplift declines and availability revenue weakens.",
            infrastructure_inflation_shift=-0.015,
            infrastructure_revenue_shock=-0.10,
            governance_note=(
                "Infrastructure stress: inflation and revenue sensitivities are first-order "
                "educational approximations, not project-finance valuation models."
            ),
        ),
    ]


def run_asset_class_stress_tests(
    scenarios: Optional[Iterable[AssetStressScenario]] = None,
    fixed_income_instruments: Optional[Iterable[FixedIncomeInstrument]] = None,
    private_asset_holdings: Optional[Iterable[PrivateAsset]] = None,
    swaps: Optional[Iterable[InterestRateSwapContract]] = None,
    bond_forwards: Optional[Iterable[BondForwardContract]] = None,
    discount_curve: Optional[RiskFreeCurve] = None,
) -> AssetStressReport:
    """
    Run deterministic stress attribution across Phase 9 asset classes.

    Results are reported by scenario, source type, asset class, and instrument.
    Positive `market_value_impact` means the stressed market value is higher
    than the base market value; negative values are losses.
    """
    scenarios = list(scenarios or default_phase9_asset_stress_scenarios())
    fixed_income_instruments = list(
        fixed_income_instruments or default_phase9_fixed_income_instruments()
    )
    private_asset_holdings = list(private_asset_holdings or default_phase9_private_assets())
    if swaps is None or bond_forwards is None:
        examples = default_phase9_derivative_examples()
        if swaps is None:
            swaps = examples["swaps"]
        if bond_forwards is None:
            bond_forwards = examples["bond_forwards"]
    swaps = list(swaps)
    bond_forwards = list(bond_forwards)
    if discount_curve is None:
        discount_curve = RiskFreeCurve.flat(
            0.035,
            currency="HKD",
            market="HK",
            valuation_date="2026-06-02",
            curve_id="HKD-PHASE9-STRESS-FLAT",
            source_id="phase9-asset-stress-placeholder",
        )

    rows: List[dict] = []
    for scenario in scenarios:
        rows.extend(_fixed_income_stress_rows(scenario, fixed_income_instruments))
        rows.extend(_private_asset_stress_rows(scenario, private_asset_holdings))
        rows.extend(_derivative_stress_rows(scenario, swaps, bond_forwards, discount_curve))

    results = pd.DataFrame(rows)
    if results.empty:
        results = pd.DataFrame(columns=STRESS_RESULT_COLUMNS)
    else:
        results = (
            results.reindex(columns=STRESS_RESULT_COLUMNS)
            .sort_values(["scenario_id", "source_type", "asset_class", "instrument_id"])
            .reset_index(drop=True)
        )

    summary = _scenario_summary(results)
    return AssetStressReport(
        stress_results=results,
        scenario_summary=summary,
        governance_notes=[
            "SOA ASOP 56: stress definitions disclose rate, spread, default, private-asset, "
            "infrastructure, and derivative valuation drivers separately.",
            "IA TAS M: each stress row preserves scenario_id, source_type, asset_class, "
            "instrument_id, and governance_note for audit traceability.",
            "ERM limitation: stresses are deterministic educational shocks and are not "
            "calibrated VaR/ES, liquidity-haircut, CVA, or statutory-capital models.",
        ],
    )


def _fixed_income_stress_rows(
    scenario: AssetStressScenario,
    instruments: Iterable[FixedIncomeInstrument],
) -> List[dict]:
    rows: List[dict] = []
    for instrument in instruments:
        stressed = fixed_income_market_value_after_shock(
            instrument,
            rate_shift_bps=scenario.rate_shift_bps,
            spread_shift_bps=scenario.spread_shift_bps,
            downgrade_spread_bps_per_notch=scenario.downgrade_spread_bps_per_notch,
        )
        rows.append(
            _stress_row(
                scenario=scenario,
                source_type="FixedIncome",
                instrument_id=instrument.instrument_id,
                asset_class=instrument.asset_class,
                currency=instrument.currency,
                base_market_value=instrument.market_value,
                stressed_market_value=stressed,
                stress_driver=(
                    "duration_repricing:"
                    f"rate={scenario.rate_shift_bps:.0f}bp,"
                    f"spread={scenario.spread_shift_bps:.0f}bp"
                ),
            )
        )
    return rows


def _private_asset_stress_rows(
    scenario: AssetStressScenario,
    assets: Iterable[PrivateAsset],
) -> List[dict]:
    rows: List[dict] = []
    for asset in assets:
        if isinstance(asset, PrivateCreditAsset):
            base = asset.market_value
            base_loss = base * asset.expected_default_loss_rate
            stressed_pd = min(1.0, asset.annual_default_probability * scenario.private_credit_default_multiplier)
            stressed_recovery = min(1.0, max(0.0, asset.recovery_rate + scenario.private_credit_recovery_shift))
            stressed_loss = base * stressed_pd * (1.0 - stressed_recovery)
            stressed = max(0.0, base - max(0.0, stressed_loss - base_loss))
            rows.append(
                _stress_row(
                    scenario,
                    "PrivateAsset",
                    asset.asset_id,
                    "PrivateCredit",
                    asset.currency,
                    base,
                    stressed,
                    (
                        "expected_loss:"
                        f"pd_multiplier={scenario.private_credit_default_multiplier:.2f},"
                        f"recovery_shift={scenario.private_credit_recovery_shift:.2%}"
                    ),
                )
            )
        elif isinstance(asset, PrivateEquityAsset):
            base = asset.funded_nav
            stressed = max(0.0, base * (1.0 + scenario.private_equity_nav_shock))
            rows.append(
                _stress_row(
                    scenario,
                    "PrivateAsset",
                    asset.asset_id,
                    "PrivateEquity",
                    asset.currency,
                    base,
                    stressed,
                    f"nav_markdown={scenario.private_equity_nav_shock:.2%}",
                )
            )
        elif isinstance(asset, InfrastructureAsset):
            base = asset.market_value
            inflation_effect = base * asset.inflation_linkage * scenario.infrastructure_inflation_shift
            revenue_effect = -base * asset.cash_yield * max(0.0, -scenario.infrastructure_revenue_shock)
            stressed = max(0.0, base + inflation_effect + revenue_effect)
            rows.append(
                _stress_row(
                    scenario,
                    "PrivateAsset",
                    asset.asset_id,
                    "Infrastructure",
                    asset.currency,
                    base,
                    stressed,
                    (
                        "infrastructure:"
                        f"inflation_shift={scenario.infrastructure_inflation_shift:.2%},"
                        f"revenue_shock={scenario.infrastructure_revenue_shock:.2%}"
                    ),
                )
            )
        else:
            raise TypeError(f"Unsupported private asset type: {type(asset)!r}")
    return rows


def _derivative_stress_rows(
    scenario: AssetStressScenario,
    swaps: Iterable[InterestRateSwapContract],
    bond_forwards: Iterable[BondForwardContract],
    discount_curve: RiskFreeCurve,
) -> List[dict]:
    base = value_derivative_portfolio(swaps, bond_forwards, discount_curve).valuations
    stressed_curve = discount_curve.parallel_shift(scenario.derivative_curve_shift_bps / 10_000.0)
    stressed = value_derivative_portfolio(swaps, bond_forwards, stressed_curve).valuations
    if base.empty:
        return []

    stressed_by_id = stressed.set_index("instrument_id")
    rows: List[dict] = []
    for _, base_row in base.iterrows():
        instrument_id = base_row["instrument_id"]
        stressed_row = stressed_by_id.loc[instrument_id]
        rows.append(
            _stress_row(
                scenario=scenario,
                source_type="Derivative",
                instrument_id=instrument_id,
                asset_class=f"Derivative:{base_row['derivative_type']}",
                currency=base_row.get("currency", ""),
                base_market_value=float(base_row["market_value"]),
                stressed_market_value=float(stressed_row["market_value"]),
                stress_driver=f"curve_revaluation={scenario.derivative_curve_shift_bps:.0f}bp",
            )
        )
    return rows


def _stress_row(
    scenario: AssetStressScenario,
    source_type: str,
    instrument_id: str,
    asset_class: str,
    currency: str,
    base_market_value: float,
    stressed_market_value: float,
    stress_driver: str,
) -> dict:
    impact = float(stressed_market_value) - float(base_market_value)
    impact_pct = impact / float(base_market_value) if float(base_market_value) else 0.0
    return {
        "scenario_id": scenario.scenario_id,
        "scenario_description": scenario.description,
        "source_type": source_type,
        "instrument_id": instrument_id,
        "asset_class": asset_class,
        "currency": currency,
        "base_market_value": float(base_market_value),
        "stressed_market_value": float(stressed_market_value),
        "market_value_impact": impact,
        "impact_pct": impact_pct,
        "stress_driver": stress_driver,
        "governance_note": scenario.governance_note,
    }


def _scenario_summary(results: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "scenario_id",
        "base_market_value",
        "stressed_market_value",
        "market_value_impact",
        "impact_pct",
        "largest_loss_asset_class",
        "largest_loss_source_type",
    ]
    if results.empty:
        return pd.DataFrame(columns=columns)

    summary = results.groupby("scenario_id", as_index=False).agg(
        base_market_value=("base_market_value", "sum"),
        stressed_market_value=("stressed_market_value", "sum"),
        market_value_impact=("market_value_impact", "sum"),
    )
    summary["impact_pct"] = np.where(
        summary["base_market_value"] != 0.0,
        summary["market_value_impact"] / summary["base_market_value"],
        0.0,
    )

    losses = (
        results.groupby(["scenario_id", "asset_class", "source_type"], as_index=False)
        .agg(class_market_value_impact=("market_value_impact", "sum"))
        .sort_values(["scenario_id", "class_market_value_impact"])
        .drop_duplicates("scenario_id", keep="first")
        .rename(
            columns={
                "asset_class": "largest_loss_asset_class",
                "source_type": "largest_loss_source_type",
            }
        )
    )
    return (
        summary.merge(
            losses[["scenario_id", "largest_loss_asset_class", "largest_loss_source_type"]],
            on="scenario_id",
            how="left",
        )
        .reindex(columns=columns)
        .sort_values("scenario_id")
        .reset_index(drop=True)
    )


__all__ = [
    "AssetStressReport",
    "AssetStressScenario",
    "default_phase9_asset_stress_scenarios",
    "run_asset_class_stress_tests",
]
