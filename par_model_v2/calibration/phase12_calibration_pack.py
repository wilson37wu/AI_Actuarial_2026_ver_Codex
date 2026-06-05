"""
Phase 12 calibration assumption pack for governed educational examples.

The pack builder turns existing starter fixtures and assumption objects into a
single audit-ready artefact for curves, regional equity, credit, and Hong Kong
participating liability declarations.  It does not claim market calibration:
every row is labelled as educational until approved market data and owner
sign-off are supplied.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from par_model_v2.projection.fixed_income import default_phase9_fixed_income_instruments
from par_model_v2.projection.hk_participating import (
    default_hk_cash_dividend_mechanics,
    default_hk_declaration_assumption,
    default_hk_reversionary_bonus_mechanics,
)
from par_model_v2.projection.private_assets import PrivateCreditAsset, default_phase9_private_assets
from par_model_v2.stochastic import (
    default_phase7_starter_curves,
    default_phase8_equity_factors,
)


SOURCE_ID = "PHASE12-T1-CALIBRATION-PACK"
LIMITATION_ID = "PHASE12-T1-CALIBRATION-PACK-LIMIT"
PACK_VERSION = "1.0.0"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _coerce_date(value: Optional[str | date]) -> date:
    if value is None:
        return date.today()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _finite(value: float, name: str) -> float:
    numeric = float(value)
    if not np.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


@dataclass(frozen=True)
class CalibrationAssumptionCard:
    """One assumption row in the Phase 12 calibration pack."""

    category: str
    assumption_id: str
    assumption_name: str
    basis: str
    value: float
    unit: str
    source_id: str
    limitation_id: str
    validation_status: str
    owner_role: str
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_placeholder: bool = True

    def __post_init__(self) -> None:
        if not self.category:
            raise ValueError("category is required")
        if not self.assumption_id:
            raise ValueError("assumption_id is required")
        if not self.assumption_name:
            raise ValueError("assumption_name is required")
        _finite(self.value, "value")
        if self.validation_status not in {"PASS", "WARN", "FAIL", "PENDING_SIGNOFF"}:
            raise ValueError("validation_status must be PASS, WARN, FAIL, or PENDING_SIGNOFF")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationInputCheck:
    """Validation check over the generated calibration assumption pack."""

    check_id: str
    check_name: str
    status: str
    message: str
    observed: Optional[float] = None
    threshold: Optional[float] = None

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Phase12CalibrationPack:
    """Governed collection of starter calibration assumption cards."""

    pack_id: str
    generated_at: str
    calibration_date: date
    version: str
    assumption_cards: List[CalibrationAssumptionCard]
    input_checks: List[CalibrationInputCheck]
    source_id: str = SOURCE_ID
    limitation_id: str = LIMITATION_ID

    @property
    def completeness_status(self) -> str:
        has_fail = any(check.status == "FAIL" for check in self.input_checks)
        if has_fail:
            return "BLOCKED"
        if any(card.is_placeholder for card in self.assumption_cards):
            return "EDUCATIONAL_PLACEHOLDER"
        return "READY_FOR_SIGNOFF"

    def category_summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for card in self.assumption_cards:
            summary[card.category] = summary.get(card.category, 0) + 1
        return summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "generated_at": self.generated_at,
            "calibration_date": self.calibration_date.isoformat(),
            "version": self.version,
            "source_id": self.source_id,
            "limitation_id": self.limitation_id,
            "completeness_status": self.completeness_status,
            "category_summary": self.category_summary(),
            "assumption_cards": [card.to_dict() for card in self.assumption_cards],
            "input_checks": [check.to_dict() for check in self.input_checks],
        }

    def write_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path

    def write_markdown(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")
        return path

    def to_markdown(self) -> str:
        lines = [
            "# Phase 12 Calibration Assumption Pack",
            "",
            f"**Pack ID:** `{self.pack_id}`  ",
            f"**Generated:** {self.generated_at}  ",
            f"**Calibration date:** {self.calibration_date.isoformat()}  ",
            f"**Completeness status:** {self.completeness_status}  ",
            f"**Source ID:** {self.source_id}  ",
            f"**Limitation ID:** {self.limitation_id}",
            "",
            "## Category Summary",
            "",
            "| Category | Cards |",
            "|----------|------:|",
        ]
        for category, count in sorted(self.category_summary().items()):
            lines.append(f"| {category} | {count} |")

        lines += [
            "",
            "## Assumption Cards",
            "",
            "| Category | Assumption | Value | Unit | Status | Owner |",
            "|----------|------------|------:|------|--------|-------|",
        ]
        for card in self.assumption_cards:
            lines.append(
                f"| {card.category} | {card.assumption_name} | {card.value:.6g} | "
                f"{card.unit} | {card.validation_status} | {card.owner_role} |"
            )

        lines += [
            "",
            "## Input Checks",
            "",
            "| Check | Status | Message |",
            "|-------|--------|---------|",
        ]
        for check in self.input_checks:
            lines.append(f"| {check.check_id} | {check.status} | {check.message} |")

        lines += [
            "",
            "## Use Restriction",
            "",
            "This pack packages starter assumptions for education and workflow testing only. "
            "Do not use it for pricing, capital, external reporting, or assumption sign-off "
            "until each card is replaced by approved market or experience data.",
            "",
            f"*Source ID: {self.source_id} | Limitation ID: {self.limitation_id}*",
        ]
        return "\n".join(lines) + "\n"


def build_curve_calibration_cards(calibration_date: Optional[str | date] = None) -> List[CalibrationAssumptionCard]:
    """Build cards for starter risk-free curve nodes and derived diagnostics."""
    valuation_date = _coerce_date(calibration_date)
    cards: List[CalibrationAssumptionCard] = []
    for currency, curve in sorted(default_phase7_starter_curves(valuation_date).items()):
        zero_1y = curve.zero_rate(1.0)
        zero_10y = curve.zero_rate(10.0)
        cards.append(
            CalibrationAssumptionCard(
                category="curve",
                assumption_id=f"CURVE-{currency}-{valuation_date:%Y%m%d}",
                assumption_name=f"{currency} 10Y risk-free zero rate",
                basis="Phase 7 starter continuously compounded curve fixture",
                value=zero_10y,
                unit="decimal_rate",
                source_id=curve.source_id,
                limitation_id=LIMITATION_ID,
                validation_status="PENDING_SIGNOFF",
                owner_role="Market Assumption Owner",
                notes="Starter curve, not calibrated to live market data in this pack.",
                metadata={
                    "currency": currency,
                    "curve_id": curve.curve_id,
                    "zero_1y": zero_1y,
                    "zero_10y": zero_10y,
                    "discount_factor_10y": curve.discount_factor(10.0),
                    "n_tenor_points": len(curve.tenors_years),
                    "compounding": curve.compounding,
                },
            )
        )
    return cards


def build_equity_calibration_cards(calibration_date: Optional[str | date] = None) -> List[CalibrationAssumptionCard]:
    """Build cards for starter regional equity volatility assumptions."""
    valuation_date = _coerce_date(calibration_date)
    cards: List[CalibrationAssumptionCard] = []
    for market, factor in sorted(default_phase8_equity_factors(valuation_date).items()):
        params = factor.params
        cards.append(
            CalibrationAssumptionCard(
                category="equity",
                assumption_id=f"EQUITY-{market}-{valuation_date:%Y%m%d}",
                assumption_name=f"{factor.index_name} equity volatility",
                basis="Phase 8 starter regional equity factor fixture",
                value=params.equity_vol,
                unit="annualized_volatility",
                source_id=factor.source_id,
                limitation_id=LIMITATION_ID,
                validation_status="PENDING_SIGNOFF",
                owner_role="Market Assumption Owner",
                notes="Starter GBM volatility; replace with implied or historical calibration.",
                metadata={
                    "market": market,
                    "region": factor.region,
                    "currency": factor.currency,
                    "factor_id": factor.factor_id,
                    "dividend_yield": params.dividend_yield,
                    "equity_risk_premium": params.equity_risk_premium,
                    "rate_equity_correlation": params.rate_equity_correlation,
                    "initial_index_level": params.initial_index_level,
                },
            )
        )
    return cards


def build_credit_calibration_cards() -> List[CalibrationAssumptionCard]:
    """Build cards for public and private credit spread/loss assumptions."""
    cards: List[CalibrationAssumptionCard] = []
    for instrument in default_phase9_fixed_income_instruments():
        if instrument.spread_bps <= 0 and instrument.annual_default_probability <= 0:
            continue
        cards.append(
            CalibrationAssumptionCard(
                category="credit",
                assumption_id=f"CREDIT-{instrument.instrument_id}",
                assumption_name=f"{instrument.credit_rating} {instrument.asset_class} spread",
                basis="Phase 9 fixed-income educational instrument fixture",
                value=instrument.spread_bps,
                unit="basis_points",
                source_id=instrument.source_id,
                limitation_id=instrument.limitation_id,
                validation_status="PENDING_SIGNOFF",
                owner_role="Credit Assumption Owner",
                notes="Credit spread and default assumptions are illustrative.",
                metadata={
                    "instrument_id": instrument.instrument_id,
                    "currency": instrument.currency,
                    "duration_years": instrument.duration_years,
                    "annual_default_probability": instrument.annual_default_probability,
                    "recovery_rate": instrument.recovery_rate,
                },
            )
        )

    for asset in default_phase9_private_assets():
        if isinstance(asset, PrivateCreditAsset):
            cards.append(
                CalibrationAssumptionCard(
                    category="credit",
                    assumption_id=f"PRIVATE-CREDIT-{asset.asset_id}",
                    assumption_name=f"{asset.strategy} expected default loss",
                    basis="Phase 9 private-credit educational asset fixture",
                    value=asset.expected_default_loss_rate,
                    unit="annual_loss_rate",
                    source_id=asset.source_id,
                    limitation_id=asset.limitation_id,
                    validation_status="PENDING_SIGNOFF",
                    owner_role="Credit Assumption Owner",
                    notes="Expected loss equals PD times LGD; not fitted to portfolio experience.",
                    metadata={
                        "asset_id": asset.asset_id,
                        "currency": asset.currency,
                        "spread_bps": asset.spread_bps,
                        "annual_default_probability": asset.annual_default_probability,
                        "recovery_rate": asset.recovery_rate,
                    },
                )
            )
    return cards


def build_liability_calibration_cards() -> List[CalibrationAssumptionCard]:
    """Build cards for HK PAR declaration assumptions and product mechanics."""
    declaration = default_hk_declaration_assumption()
    cash_mech = default_hk_cash_dividend_mechanics()
    rb_mech = default_hk_reversionary_bonus_mechanics()
    return [
        CalibrationAssumptionCard(
            category="liability",
            assumption_id=declaration.assumption_id + "-CASH",
            assumption_name="HK cash dividend declared rate",
            basis=declaration.basis_name,
            value=declaration.declared_cash_dividend_rate(cash_mech),
            unit="decimal_rate",
            source_id=declaration.source_id,
            limitation_id=declaration.limitation_id,
            validation_status="PENDING_SIGNOFF",
            owner_role="Liability Assumption Owner",
            notes=declaration.notes,
            metadata={"product_code": cash_mech.product_code, "sensitivity_label": declaration.sensitivity_label},
        ),
        CalibrationAssumptionCard(
            category="liability",
            assumption_id=declaration.assumption_id + "-RB",
            assumption_name="HK reversionary bonus declared rate",
            basis=declaration.basis_name,
            value=declaration.declared_reversionary_bonus_rate(rb_mech),
            unit="decimal_rate",
            source_id=declaration.source_id,
            limitation_id=declaration.limitation_id,
            validation_status="PENDING_SIGNOFF",
            owner_role="Liability Assumption Owner",
            notes=declaration.notes,
            metadata={"product_code": rb_mech.product_code, "sensitivity_label": declaration.sensitivity_label},
        ),
        CalibrationAssumptionCard(
            category="liability",
            assumption_id=declaration.assumption_id + "-TB",
            assumption_name="HK terminal bonus declared percentage",
            basis=declaration.basis_name,
            value=declaration.declared_terminal_bonus_pct(rb_mech),
            unit="decimal_percentage_of_asset_share",
            source_id=declaration.source_id,
            limitation_id=declaration.limitation_id,
            validation_status="PENDING_SIGNOFF",
            owner_role="Liability Assumption Owner",
            notes=declaration.notes,
            metadata={"product_code": rb_mech.product_code, "sensitivity_label": declaration.sensitivity_label},
        ),
    ]


def validate_calibration_cards(cards: Sequence[CalibrationAssumptionCard]) -> List[CalibrationInputCheck]:
    """Run structural validation over calibration cards."""
    categories = {card.category for card in cards}
    required_categories = {"curve", "equity", "credit", "liability"}
    checks = [
        CalibrationInputCheck(
            check_id="P12-CAL-01",
            check_name="required category coverage",
            status="PASS" if required_categories.issubset(categories) else "FAIL",
            message=f"covered categories: {', '.join(sorted(categories))}",
            observed=float(len(categories)),
            threshold=float(len(required_categories)),
        ),
        CalibrationInputCheck(
            check_id="P12-CAL-02",
            check_name="unique assumption ids",
            status="PASS" if len({card.assumption_id for card in cards}) == len(cards) else "FAIL",
            message=f"{len(cards)} cards checked for duplicate assumption IDs.",
            observed=float(len({card.assumption_id for card in cards})),
            threshold=float(len(cards)),
        ),
        CalibrationInputCheck(
            check_id="P12-CAL-03",
            check_name="finite values",
            status="PASS" if all(np.isfinite(card.value) for card in cards) else "FAIL",
            message="all card values must be finite.",
        ),
        CalibrationInputCheck(
            check_id="P12-CAL-04",
            check_name="placeholder disclosure",
            status="PASS" if all(card.is_placeholder for card in cards) else "WARN",
            message="educational starter pack is fully placeholder-disclosed.",
        ),
    ]
    return checks


def build_phase12_calibration_pack(
    calibration_date: Optional[str | date] = None,
    categories: Optional[Iterable[str]] = None,
) -> Phase12CalibrationPack:
    """Build the full Phase 12 calibration pack.

    Parameters
    ----------
    calibration_date:
        As-of date for fixture valuation and pack metadata.
    categories:
        Optional subset of ``curve``, ``equity``, ``credit``, ``liability``.
    """
    cal_date = _coerce_date(calibration_date)
    selected = {category.lower() for category in categories} if categories else {
        "curve", "equity", "credit", "liability"
    }
    invalid = selected.difference({"curve", "equity", "credit", "liability"})
    if invalid:
        raise ValueError(f"unknown calibration categories: {', '.join(sorted(invalid))}")

    cards: List[CalibrationAssumptionCard] = []
    if "curve" in selected:
        cards.extend(build_curve_calibration_cards(cal_date))
    if "equity" in selected:
        cards.extend(build_equity_calibration_cards(cal_date))
    if "credit" in selected:
        cards.extend(build_credit_calibration_cards())
    if "liability" in selected:
        cards.extend(build_liability_calibration_cards())

    checks = validate_calibration_cards(cards)
    return Phase12CalibrationPack(
        pack_id="P12-CAL-" + str(uuid.uuid4())[:8].upper(),
        generated_at=_now_utc(),
        calibration_date=cal_date,
        version=PACK_VERSION,
        assumption_cards=cards,
        input_checks=checks,
    )


__all__ = [
    "CalibrationAssumptionCard",
    "CalibrationInputCheck",
    "Phase12CalibrationPack",
    "build_credit_calibration_cards",
    "build_curve_calibration_cards",
    "build_equity_calibration_cards",
    "build_liability_calibration_cards",
    "build_phase12_calibration_pack",
    "validate_calibration_cards",
]
