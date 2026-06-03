"""
Hong Kong participating product definitions for Phase 10.

This module defines the first Phase 10 liability product slices: Hong
Kong-style cash dividend and reversionary bonus participating endowments.  The
records are governed educational fixtures.  They define contract mechanics and
sample policy data; declaration rules and stochastic supportability are added
in later Phase 10 tasks.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from par_model_v2.projection.monthly_projection import (
    AssetPosition,
    ParEndowmentProduct,
    VALID_TERMS,
    run_full_projection,
)


_FIXTURE_PATH = Path(__file__).with_name("fixtures").joinpath(
    "hk_cash_dividend_policies.json"
)
_RB_FIXTURE_PATH = Path(__file__).with_name("fixtures").joinpath(
    "hk_reversionary_bonus_policies.json"
)
_POLICY_RECORDS = None
_RB_POLICY_RECORDS = None


def _require_text(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _require_finite(value: float, field_name: str) -> float:
    numeric = float(value)
    if not np.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    return numeric


def _require_probability(value: float, field_name: str) -> float:
    numeric = _require_finite(value, field_name)
    if numeric < 0.0 or numeric > 1.0:
        raise ValueError(f"{field_name} must be in [0, 1]")
    return numeric


@dataclass(frozen=True)
class HKDeclarationAssumption:
    """Governed declaration basis and sensitivity hook for HK PAR products.

    The mechanics classes define illustrated product rates.  This assumption
    record controls what is actually declared in a run and makes sensitivity
    shifts explicit for later supportability and TVOG consumers.
    """

    assumption_id: str = "PHASE10-HK-DECLARATION-BASE-2026"
    basis_name: str = "Educational board declaration basis"
    sensitivity_label: str = "BASE"
    cash_dividend_rate_multiplier: float = 1.0
    cash_dividend_rate_shift: float = 0.0
    reversionary_bonus_rate_multiplier: float = 1.0
    reversionary_bonus_rate_shift: float = 0.0
    terminal_bonus_pct_multiplier: float = 1.0
    terminal_bonus_pct_shift: float = 0.0
    min_declared_rate: float = 0.0
    max_declared_rate: float = 0.20
    min_terminal_bonus_pct: float = 0.0
    max_terminal_bonus_pct: float = 1.0
    source_id: str = "PHASE10-HK-DECLARATION-ASSUMPTION-EDU-2026"
    limitation_id: str = "LIM-P10-DECLARATION-PLACEHOLDER"
    notes: str = (
        "Educational declaration basis only; not a PRE policy, board minute, "
        "insurer filing, supportability result, or calibrated management action."
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "assumption_id", _require_text(self.assumption_id, "assumption_id"))
        object.__setattr__(self, "basis_name", _require_text(self.basis_name, "basis_name"))
        object.__setattr__(
            self,
            "sensitivity_label",
            _require_text(self.sensitivity_label, "sensitivity_label").upper(),
        )
        object.__setattr__(self, "source_id", _require_text(self.source_id, "source_id"))
        object.__setattr__(self, "limitation_id", _require_text(self.limitation_id, "limitation_id"))
        for field_name in (
            "cash_dividend_rate_multiplier",
            "reversionary_bonus_rate_multiplier",
            "terminal_bonus_pct_multiplier",
        ):
            value = _require_finite(getattr(self, field_name), field_name)
            if value < 0.0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, value)
        for field_name in (
            "cash_dividend_rate_shift",
            "reversionary_bonus_rate_shift",
            "terminal_bonus_pct_shift",
        ):
            object.__setattr__(self, field_name, _require_finite(getattr(self, field_name), field_name))
        rate_floor = _require_probability(self.min_declared_rate, "min_declared_rate")
        rate_cap = _require_probability(self.max_declared_rate, "max_declared_rate")
        terminal_floor = _require_probability(self.min_terminal_bonus_pct, "min_terminal_bonus_pct")
        terminal_cap = _require_probability(self.max_terminal_bonus_pct, "max_terminal_bonus_pct")
        if rate_cap < rate_floor:
            raise ValueError("max_declared_rate must be greater than or equal to min_declared_rate")
        if terminal_cap < terminal_floor:
            raise ValueError(
                "max_terminal_bonus_pct must be greater than or equal to min_terminal_bonus_pct"
            )
        object.__setattr__(self, "min_declared_rate", rate_floor)
        object.__setattr__(self, "max_declared_rate", rate_cap)
        object.__setattr__(self, "min_terminal_bonus_pct", terminal_floor)
        object.__setattr__(self, "max_terminal_bonus_pct", terminal_cap)

    def _bounded_rate(
        self,
        base_rate: float,
        multiplier: float,
        shift: float,
        floor: float,
        cap: float,
        field_name: str,
    ) -> float:
        base_rate = _require_probability(base_rate, field_name)
        declared_rate = base_rate * multiplier + shift
        return min(max(declared_rate, floor), cap)

    def declared_cash_dividend_rate(self, mechanics: HKCashDividendMechanics) -> float:
        """Return the run-level cash dividend declaration rate."""
        return self._bounded_rate(
            mechanics.annual_cash_dividend_rate,
            self.cash_dividend_rate_multiplier,
            self.cash_dividend_rate_shift,
            self.min_declared_rate,
            self.max_declared_rate,
            "annual_cash_dividend_rate",
        )

    def declared_reversionary_bonus_rate(self, mechanics: HKReversionaryBonusMechanics) -> float:
        """Return the run-level annual vested reversionary bonus rate."""
        return self._bounded_rate(
            mechanics.annual_reversionary_bonus_rate,
            self.reversionary_bonus_rate_multiplier,
            self.reversionary_bonus_rate_shift,
            self.min_declared_rate,
            self.max_declared_rate,
            "annual_reversionary_bonus_rate",
        )

    def declared_terminal_bonus_pct(self, mechanics: HKReversionaryBonusMechanics) -> float:
        """Return the run-level terminal bonus declaration percentage."""
        return self._bounded_rate(
            mechanics.terminal_bonus_pct,
            self.terminal_bonus_pct_multiplier,
            self.terminal_bonus_pct_shift,
            self.min_terminal_bonus_pct,
            self.max_terminal_bonus_pct,
            "terminal_bonus_pct",
        )

    def with_sensitivity(
        self,
        sensitivity_label: str,
        cash_dividend_rate_multiplier: Optional[float] = None,
        cash_dividend_rate_shift: Optional[float] = None,
        reversionary_bonus_rate_multiplier: Optional[float] = None,
        reversionary_bonus_rate_shift: Optional[float] = None,
        terminal_bonus_pct_multiplier: Optional[float] = None,
        terminal_bonus_pct_shift: Optional[float] = None,
    ) -> "HKDeclarationAssumption":
        """Return a copy with explicit sensitivity multipliers or shifts."""
        label = _require_text(sensitivity_label, "sensitivity_label").upper()
        updates = {
            "assumption_id": f"{self.assumption_id}-{label}",
            "sensitivity_label": label,
        }
        optional_updates = {
            "cash_dividend_rate_multiplier": cash_dividend_rate_multiplier,
            "cash_dividend_rate_shift": cash_dividend_rate_shift,
            "reversionary_bonus_rate_multiplier": reversionary_bonus_rate_multiplier,
            "reversionary_bonus_rate_shift": reversionary_bonus_rate_shift,
            "terminal_bonus_pct_multiplier": terminal_bonus_pct_multiplier,
            "terminal_bonus_pct_shift": terminal_bonus_pct_shift,
        }
        updates.update({key: value for key, value in optional_updates.items() if value is not None})
        return replace(self, **updates)

    def to_record(self) -> dict:
        record = asdict(self)
        record["is_placeholder"] = True
        return record


def default_hk_declaration_assumption() -> HKDeclarationAssumption:
    """Return the base Phase 10 declaration basis."""
    return HKDeclarationAssumption()


def hk_declaration_sensitivity(
    sensitivity_label: str,
    base: Optional[HKDeclarationAssumption] = None,
    cash_dividend_rate_multiplier: Optional[float] = None,
    cash_dividend_rate_shift: Optional[float] = None,
    reversionary_bonus_rate_multiplier: Optional[float] = None,
    reversionary_bonus_rate_shift: Optional[float] = None,
    terminal_bonus_pct_multiplier: Optional[float] = None,
    terminal_bonus_pct_shift: Optional[float] = None,
) -> HKDeclarationAssumption:
    """Build a named declaration sensitivity from the base assumption."""
    base = base or default_hk_declaration_assumption()
    return base.with_sensitivity(
        sensitivity_label=sensitivity_label,
        cash_dividend_rate_multiplier=cash_dividend_rate_multiplier,
        cash_dividend_rate_shift=cash_dividend_rate_shift,
        reversionary_bonus_rate_multiplier=reversionary_bonus_rate_multiplier,
        reversionary_bonus_rate_shift=reversionary_bonus_rate_shift,
        terminal_bonus_pct_multiplier=terminal_bonus_pct_multiplier,
        terminal_bonus_pct_shift=terminal_bonus_pct_shift,
    )


@dataclass(frozen=True)
class HKCashDividendMechanics:
    """Contract mechanics for an educational Hong Kong cash dividend product.

    Cash dividends are non-guaranteed annual cash payments.  They do not vest,
    do not increase the guaranteed death or maturity benefit, and are separated
    from the guaranteed projection fields for later TVOG and supportability
    reporting.
    """

    product_code: str
    product_name: str
    market: str = "HK"
    currency: str = "HKD"
    issue_age_min: int = 18
    issue_age_max: int = 65
    terms_years: Sequence[int] = VALID_TERMS
    min_sum_assured: float = 50_000.0
    max_sum_assured: float = 10_000_000.0
    premium_mode: str = "ANNUAL"
    dividend_option: str = "CASH"
    annual_cash_dividend_rate: float = 0.012
    guaranteed_maturity_multiple: float = 1.0
    death_benefit_multiple: float = 1.0
    surrender_value_pct: float = 0.90
    source_id: str = "PHASE10-HK-CASH-DIVIDEND-EDU-2026"
    limitation_id: str = "LIM-P10-CASH-DIVIDEND-PLACEHOLDER"
    notes: str = (
        "Educational Hong Kong participating cash dividend mechanics; "
        "not calibrated to insurer filing, PRE policy, or product brochure data."
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "product_code", _require_text(self.product_code, "product_code").upper())
        object.__setattr__(self, "product_name", _require_text(self.product_name, "product_name"))
        object.__setattr__(self, "market", _require_text(self.market, "market").upper())
        object.__setattr__(self, "currency", _require_text(self.currency, "currency").upper())
        object.__setattr__(self, "premium_mode", _require_text(self.premium_mode, "premium_mode").upper())
        object.__setattr__(self, "dividend_option", _require_text(self.dividend_option, "dividend_option").upper())
        object.__setattr__(self, "source_id", _require_text(self.source_id, "source_id"))
        object.__setattr__(self, "limitation_id", _require_text(self.limitation_id, "limitation_id"))
        terms = tuple(int(term) for term in self.terms_years)
        if not terms:
            raise ValueError("terms_years is required")
        unsupported = [term for term in terms if term not in VALID_TERMS]
        if unsupported:
            raise ValueError(
                "terms_years must use currently supported projection terms {}; got {}".format(
                    VALID_TERMS,
                    unsupported,
                )
            )
        if int(self.issue_age_min) < 0 or int(self.issue_age_max) < int(self.issue_age_min):
            raise ValueError("issue age range is invalid")
        min_sa = _require_finite(self.min_sum_assured, "min_sum_assured")
        max_sa = _require_finite(self.max_sum_assured, "max_sum_assured")
        if min_sa <= 0.0 or max_sa < min_sa:
            raise ValueError("sum assured range is invalid")
        object.__setattr__(self, "min_sum_assured", min_sa)
        object.__setattr__(self, "max_sum_assured", max_sa)
        object.__setattr__(
            self,
            "annual_cash_dividend_rate",
            _require_probability(self.annual_cash_dividend_rate, "annual_cash_dividend_rate"),
        )
        object.__setattr__(
            self,
            "guaranteed_maturity_multiple",
            _require_finite(self.guaranteed_maturity_multiple, "guaranteed_maturity_multiple"),
        )
        object.__setattr__(
            self,
            "death_benefit_multiple",
            _require_finite(self.death_benefit_multiple, "death_benefit_multiple"),
        )
        object.__setattr__(
            self,
            "surrender_value_pct",
            _require_probability(self.surrender_value_pct, "surrender_value_pct"),
        )
        object.__setattr__(self, "terms_years", terms)

    def annual_cash_dividend_amount(self, sum_assured: float) -> float:
        """Return the illustrated annual cash dividend for one in-force policy."""
        sum_assured = _require_finite(sum_assured, "sum_assured")
        if sum_assured < self.min_sum_assured or sum_assured > self.max_sum_assured:
            raise ValueError("sum_assured is outside product issue range")
        return sum_assured * self.annual_cash_dividend_rate

    def to_record(self) -> dict:
        record = asdict(self)
        record["terms_years"] = list(self.terms_years)
        record["is_placeholder"] = True
        return record


@dataclass(frozen=True)
class HKCashDividendPolicy:
    """Sample policy record for the Phase 10 cash dividend product."""

    policy_id: str
    product_code: str
    issue_age: int
    gender: str
    term_years: int
    sum_assured: float
    annual_premium: float
    policy_year: int
    inforce_count: float = 1.0
    premium_mode: str = "ANNUAL"
    dividend_option: str = "CASH"
    distribution_channel: str = "AGENCY"
    source_id: str = "PHASE10-HK-CASH-DIVIDEND-SAMPLE"

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _require_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "product_code", _require_text(self.product_code, "product_code").upper())
        object.__setattr__(self, "gender", _require_text(self.gender, "gender").upper())
        object.__setattr__(self, "premium_mode", _require_text(self.premium_mode, "premium_mode").upper())
        object.__setattr__(self, "dividend_option", _require_text(self.dividend_option, "dividend_option").upper())
        object.__setattr__(
            self,
            "distribution_channel",
            _require_text(self.distribution_channel, "distribution_channel").upper(),
        )
        object.__setattr__(self, "source_id", _require_text(self.source_id, "source_id"))
        if self.gender not in {"M", "F"}:
            raise ValueError("gender must be M or F")
        if int(self.term_years) not in VALID_TERMS:
            raise ValueError(f"term_years must be one of {VALID_TERMS}")
        if int(self.issue_age) < 0:
            raise ValueError("issue_age must be non-negative")
        if int(self.policy_year) < 1 or int(self.policy_year) > int(self.term_years):
            raise ValueError("policy_year must be in [1, term_years]")
        for field_name in ("sum_assured", "annual_premium", "inforce_count"):
            value = _require_finite(getattr(self, field_name), field_name)
            if value <= 0.0:
                raise ValueError(f"{field_name} must be positive")
            object.__setattr__(self, field_name, value)

    def validate_against(self, mechanics: HKCashDividendMechanics) -> None:
        if self.product_code != mechanics.product_code:
            raise ValueError("policy product_code does not match mechanics")
        if self.issue_age < mechanics.issue_age_min or self.issue_age > mechanics.issue_age_max:
            raise ValueError("issue_age is outside product issue range")
        if self.term_years not in mechanics.terms_years:
            raise ValueError("term_years is outside product term range")
        if self.sum_assured < mechanics.min_sum_assured or self.sum_assured > mechanics.max_sum_assured:
            raise ValueError("sum_assured is outside product issue range")
        if self.premium_mode != mechanics.premium_mode:
            raise ValueError("premium_mode does not match mechanics")
        if self.dividend_option != mechanics.dividend_option:
            raise ValueError("dividend_option does not match mechanics")

    def to_projection_product(
        self,
        mechanics: Optional[HKCashDividendMechanics] = None,
    ) -> ParEndowmentProduct:
        """
        Convert to the current deterministic projection contract.

        The existing engine can project the guaranteed endowment base.  Cash
        dividends remain a separate non-guaranteed schedule until Phase 10 adds
        declaration and supportability hooks.
        """
        mechanics = mechanics or default_hk_cash_dividend_mechanics()
        self.validate_against(mechanics)
        return ParEndowmentProduct(
            term_years=self.term_years,
            issue_age=self.issue_age,
            gender=self.gender,
            sum_assured=self.sum_assured * mechanics.guaranteed_maturity_multiple,
            annual_premium=self.annual_premium,
            rb_rate_annual=0.0,
            terminal_bonus_pct=0.0,
            surrender_value_pct=mechanics.surrender_value_pct,
            initial_rb_accum=0.0,
        )

    def to_record(self) -> dict:
        return asdict(self)


def default_hk_cash_dividend_mechanics() -> HKCashDividendMechanics:
    """Return the starter Phase 10 cash dividend product mechanics."""
    return HKCashDividendMechanics(
        product_code="HKCD_PAR_2026",
        product_name="HK Educational Cash Dividend Participating Endowment",
    )


def _load_policy_records() -> dict:
    global _POLICY_RECORDS
    if _POLICY_RECORDS is None:
        with _FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            raw_records = json.load(fixture_file)
        _POLICY_RECORDS = {
            _require_text(record["policy_id"], "policy_id"): record
            for record in raw_records["policies"]
        }
    return _POLICY_RECORDS


def available_hk_cash_dividend_policy_ids() -> tuple:
    """Return sample Phase 10 Hong Kong cash dividend policy IDs."""
    return tuple(sorted(_load_policy_records()))


def sample_hk_cash_dividend_policies(
    policy_ids: Optional[Iterable[str]] = None,
    mechanics: Optional[HKCashDividendMechanics] = None,
) -> List[HKCashDividendPolicy]:
    """Return governed sample policy records for the Phase 10 cash dividend product."""
    mechanics = mechanics or default_hk_cash_dividend_mechanics()
    records = _load_policy_records()
    selected_ids = list(policy_ids or available_hk_cash_dividend_policy_ids())
    policies: List[HKCashDividendPolicy] = []
    for policy_id in selected_ids:
        if policy_id not in records:
            raise KeyError(
                "no Phase 10 cash dividend policy fixture for {}; available policy IDs are {}".format(
                    policy_id,
                    ", ".join(available_hk_cash_dividend_policy_ids()),
                )
            )
        policy = HKCashDividendPolicy(**records[policy_id])
        policy.validate_against(mechanics)
        policies.append(policy)
    return policies


def sample_hk_cash_dividend_policy_table(
    policy_ids: Optional[Iterable[str]] = None,
    mechanics: Optional[HKCashDividendMechanics] = None,
    declaration_assumption: Optional[HKDeclarationAssumption] = None,
) -> pd.DataFrame:
    """Return the sample policy fixtures as a DataFrame with dividend fields."""
    mechanics = mechanics or default_hk_cash_dividend_mechanics()
    declaration_assumption = declaration_assumption or default_hk_declaration_assumption()
    declared_rate = declaration_assumption.declared_cash_dividend_rate(mechanics)
    rows = []
    for policy in sample_hk_cash_dividend_policies(policy_ids, mechanics):
        record = policy.to_record()
        record["market"] = mechanics.market
        record["currency"] = mechanics.currency
        record["annual_cash_dividend_rate"] = mechanics.annual_cash_dividend_rate
        record["declared_cash_dividend_rate"] = declared_rate
        record["illustrated_annual_cash_dividend"] = (
            policy.sum_assured * declared_rate * policy.inforce_count
        )
        record["declaration_assumption_id"] = declaration_assumption.assumption_id
        record["declaration_basis_name"] = declaration_assumption.basis_name
        record["sensitivity_label"] = declaration_assumption.sensitivity_label
        record["guarantee_status"] = "GUARANTEED_BASE_PLUS_NON_GUARANTEED_CASH_DIVIDEND"
        record["mechanics_source_id"] = mechanics.source_id
        record["declaration_source_id"] = declaration_assumption.source_id
        record["limitation_id"] = mechanics.limitation_id
        rows.append(record)
    return pd.DataFrame(rows)


def validate_hk_cash_dividend_policy_table(
    table: pd.DataFrame,
    mechanics: Optional[HKCashDividendMechanics] = None,
) -> bool:
    """Validate a policy table against the starter Phase 10 mechanics."""
    mechanics = mechanics or default_hk_cash_dividend_mechanics()
    required = {
        "policy_id",
        "product_code",
        "issue_age",
        "gender",
        "term_years",
        "sum_assured",
        "annual_premium",
        "policy_year",
    }
    missing = sorted(required.difference(table.columns))
    if missing:
        raise ValueError("policy table missing required columns: {}".format(", ".join(missing)))
    if table["policy_id"].duplicated().any():
        raise ValueError("policy_id values must be unique")
    policy_fields = sorted(
        required.union(
            {
                "inforce_count",
                "premium_mode",
                "dividend_option",
                "distribution_channel",
                "source_id",
            }.intersection(table.columns)
        )
    )
    for record in table[policy_fields].to_dict(orient="records"):
        policy = HKCashDividendPolicy(**record)
        policy.validate_against(mechanics)
    return True


def annual_cash_dividend_schedule(
    policy: HKCashDividendPolicy,
    mechanics: Optional[HKCashDividendMechanics] = None,
    declaration_assumption: Optional[HKDeclarationAssumption] = None,
) -> pd.DataFrame:
    """Return annual non-guaranteed cash dividend payment dates and amounts."""
    mechanics = mechanics or default_hk_cash_dividend_mechanics()
    declaration_assumption = declaration_assumption or default_hk_declaration_assumption()
    policy.validate_against(mechanics)
    declared_rate = declaration_assumption.declared_cash_dividend_rate(mechanics)
    annual_amount = policy.sum_assured * declared_rate * policy.inforce_count
    rows = []
    for policy_year in range(1, policy.term_years + 1):
        rows.append(
            {
                "policy_id": policy.policy_id,
                "product_code": policy.product_code,
                "policy_year": policy_year,
                "month": policy_year * 12,
                "declared_cash_dividend_rate": declared_rate,
                "cash_dividend": annual_amount,
                "guarantee_status": "NON_GUARANTEED",
                "dividend_option": mechanics.dividend_option,
                "declaration_assumption_id": declaration_assumption.assumption_id,
                "declaration_basis_name": declaration_assumption.basis_name,
                "sensitivity_label": declaration_assumption.sensitivity_label,
                "source_id": mechanics.source_id,
                "declaration_source_id": declaration_assumption.source_id,
                "limitation_id": mechanics.limitation_id,
            }
        )
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class HKAssetShareSupportReport:
    """Deterministic asset-share support evidence for a Phase 10 HK product."""

    product_variant: str
    policy_id: str
    support_basis_id: str
    declaration_assumption_id: str
    sensitivity_label: str
    support_tests: pd.DataFrame
    projection_summary: dict
    min_support_ratio: float
    min_support_margin: float
    limitation_id: str = "LIM-P10-ASSET-SHARE-SUPPORT-PLACEHOLDER"

    @property
    def final_support_margin(self) -> float:
        return float(self.support_tests["support_margin"].iloc[-1])

    @property
    def final_support_ratio(self) -> float:
        return float(self.support_tests["support_ratio"].iloc[-1])

    @property
    def is_supported(self) -> bool:
        passed = self.support_tests["support_status"] == "SUPPORTED"
        return bool(passed.all())

    def to_record(self) -> dict:
        return {
            "product_variant": self.product_variant,
            "policy_id": self.policy_id,
            "support_basis_id": self.support_basis_id,
            "declaration_assumption_id": self.declaration_assumption_id,
            "sensitivity_label": self.sensitivity_label,
            "final_support_margin": self.final_support_margin,
            "final_support_ratio": self.final_support_ratio,
            "is_supported": self.is_supported,
            "min_support_ratio": self.min_support_ratio,
            "min_support_margin": self.min_support_margin,
            "limitation_id": self.limitation_id,
        }


def default_hk_asset_share_fund_positions(scale: float = 0.01) -> List[AssetPosition]:
    """Return the starter deterministic ALM fund mix for Phase 10 support tests."""
    scale = _require_finite(scale, "scale")
    if scale <= 0.0:
        raise ValueError("scale must be positive")
    return [
        AssetPosition("Govt", 900_000.0 * scale, 880_000.0 * scale, 8.5, 0.032, 0.0, 8.5, ""),
        AssetPosition("Credit_A", 575_000.0 * scale, 570_000.0 * scale, 6.2, 0.038, 0.0, 6.2, "A"),
        AssetPosition("Equity", 700_000.0 * scale, 700_000.0 * scale, 0.0, 0.025, 0.06, 0.0, ""),
        AssetPosition("Cash", 125_000.0 * scale, 125_000.0 * scale, 0.0, 0.020, 0.0, 0.0, ""),
    ]


def _annual_asset_share_view(asset_share_projection: pd.DataFrame) -> pd.DataFrame:
    return asset_share_projection.loc[
        asset_share_projection["month"] % 12 == 0,
        [
            "policy_year",
            "month",
            "asset_share_eom",
            "investment_return",
            "policyholder_dist",
            "shareholder_dist",
        ],
    ].copy()


def _support_ratio(asset_share: pd.Series, obligation: pd.Series) -> pd.Series:
    return pd.Series(
        np.where(obligation > 0.0, asset_share / obligation, np.inf),
        index=asset_share.index,
    )


def _apply_support_status(
    table: pd.DataFrame,
    min_support_ratio: float,
    min_support_margin: float,
) -> pd.DataFrame:
    min_support_ratio = _require_finite(min_support_ratio, "min_support_ratio")
    min_support_margin = _require_finite(min_support_margin, "min_support_margin")
    table["support_margin"] = table["asset_share_eom"] - table["support_obligation"]
    table["support_ratio"] = _support_ratio(table["asset_share_eom"], table["support_obligation"])
    supported = (
        (table["support_margin"] >= min_support_margin)
        & (table["support_ratio"] >= min_support_ratio)
    )
    table["support_status"] = np.where(supported, "SUPPORTED", "NOT_SUPPORTED")
    return table


def hk_cash_dividend_asset_share_support_test(
    policy: HKCashDividendPolicy,
    mechanics: Optional[HKCashDividendMechanics] = None,
    declaration_assumption: Optional[HKDeclarationAssumption] = None,
    fund_positions: Optional[Sequence[AssetPosition]] = None,
    min_support_ratio: float = 1.0,
    min_support_margin: float = 0.0,
) -> HKAssetShareSupportReport:
    """Test deterministic asset-share support for declared cash dividends."""
    mechanics = mechanics or default_hk_cash_dividend_mechanics()
    declaration_assumption = declaration_assumption or default_hk_declaration_assumption()
    fund_positions = list(fund_positions or default_hk_asset_share_fund_positions())
    policy.validate_against(mechanics)

    projection = run_full_projection(policy.to_projection_product(mechanics), fund_positions)
    schedule = annual_cash_dividend_schedule(policy, mechanics, declaration_assumption)
    support_tests = schedule.merge(
        _annual_asset_share_view(projection.asset_share.projection),
        on=["policy_year", "month"],
        how="left",
    )
    support_tests["support_test_type"] = "CUMULATIVE_CASH_DIVIDEND"
    support_tests["support_obligation"] = support_tests["cash_dividend"].cumsum()
    support_tests = _apply_support_status(
        support_tests,
        min_support_ratio=min_support_ratio,
        min_support_margin=min_support_margin,
    )
    support_tests["product_variant"] = "CASH_DIVIDEND"
    support_tests["support_basis_id"] = "PHASE10-HK-ASSET-SHARE-SUPPORT-BASE-2026"

    return HKAssetShareSupportReport(
        product_variant="CASH_DIVIDEND",
        policy_id=policy.policy_id,
        support_basis_id="PHASE10-HK-ASSET-SHARE-SUPPORT-BASE-2026",
        declaration_assumption_id=declaration_assumption.assumption_id,
        sensitivity_label=declaration_assumption.sensitivity_label,
        support_tests=support_tests,
        projection_summary=projection.summary(),
        min_support_ratio=min_support_ratio,
        min_support_margin=min_support_margin,
    )


@dataclass(frozen=True)
class HKReversionaryBonusMechanics:
    """Contract mechanics for an educational Hong Kong reversionary bonus product.

    Reversionary bonuses are illustrated as annual declared additions to
    policyholder benefits.  Once declared, the vested bonus is reported in the
    guaranteed benefit split.  Terminal bonus remains non-guaranteed and payable
    only at maturity in the starter educational mechanics.
    """

    product_code: str
    product_name: str
    market: str = "HK"
    currency: str = "HKD"
    issue_age_min: int = 18
    issue_age_max: int = 65
    terms_years: Sequence[int] = VALID_TERMS
    min_sum_assured: float = 50_000.0
    max_sum_assured: float = 10_000_000.0
    premium_mode: str = "ANNUAL"
    bonus_option: str = "VESTED_REVERSIONARY"
    annual_reversionary_bonus_rate: float = 0.025
    terminal_bonus_pct: float = 0.35
    guaranteed_base_multiple: float = 1.0
    death_benefit_vested_bonus_multiple: float = 1.0
    maturity_vested_bonus_multiple: float = 1.0
    surrender_value_pct: float = 0.90
    source_id: str = "PHASE10-HK-RB-EDU-2026"
    limitation_id: str = "LIM-P10-RB-PLACEHOLDER"
    notes: str = (
        "Educational Hong Kong participating reversionary bonus mechanics; "
        "not calibrated to insurer PRE policy, board declaration, or filing data."
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "product_code", _require_text(self.product_code, "product_code").upper())
        object.__setattr__(self, "product_name", _require_text(self.product_name, "product_name"))
        object.__setattr__(self, "market", _require_text(self.market, "market").upper())
        object.__setattr__(self, "currency", _require_text(self.currency, "currency").upper())
        object.__setattr__(self, "premium_mode", _require_text(self.premium_mode, "premium_mode").upper())
        object.__setattr__(self, "bonus_option", _require_text(self.bonus_option, "bonus_option").upper())
        object.__setattr__(self, "source_id", _require_text(self.source_id, "source_id"))
        object.__setattr__(self, "limitation_id", _require_text(self.limitation_id, "limitation_id"))
        terms = tuple(int(term) for term in self.terms_years)
        if not terms:
            raise ValueError("terms_years is required")
        unsupported = [term for term in terms if term not in VALID_TERMS]
        if unsupported:
            raise ValueError(
                "terms_years must use currently supported projection terms {}; got {}".format(
                    VALID_TERMS,
                    unsupported,
                )
            )
        if int(self.issue_age_min) < 0 or int(self.issue_age_max) < int(self.issue_age_min):
            raise ValueError("issue age range is invalid")
        min_sa = _require_finite(self.min_sum_assured, "min_sum_assured")
        max_sa = _require_finite(self.max_sum_assured, "max_sum_assured")
        if min_sa <= 0.0 or max_sa < min_sa:
            raise ValueError("sum assured range is invalid")
        object.__setattr__(self, "min_sum_assured", min_sa)
        object.__setattr__(self, "max_sum_assured", max_sa)
        object.__setattr__(
            self,
            "annual_reversionary_bonus_rate",
            _require_probability(self.annual_reversionary_bonus_rate, "annual_reversionary_bonus_rate"),
        )
        object.__setattr__(
            self,
            "terminal_bonus_pct",
            _require_probability(self.terminal_bonus_pct, "terminal_bonus_pct"),
        )
        for field_name in (
            "guaranteed_base_multiple",
            "death_benefit_vested_bonus_multiple",
            "maturity_vested_bonus_multiple",
        ):
            value = _require_finite(getattr(self, field_name), field_name)
            if value < 0.0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, value)
        object.__setattr__(
            self,
            "surrender_value_pct",
            _require_probability(self.surrender_value_pct, "surrender_value_pct"),
        )
        object.__setattr__(self, "terms_years", terms)

    def annual_vested_bonus_addition(self, sum_assured: float) -> float:
        """Return the illustrated annual vested bonus addition."""
        sum_assured = _require_finite(sum_assured, "sum_assured")
        if sum_assured < self.min_sum_assured or sum_assured > self.max_sum_assured:
            raise ValueError("sum_assured is outside product issue range")
        return sum_assured * self.annual_reversionary_bonus_rate

    def to_record(self) -> dict:
        record = asdict(self)
        record["terms_years"] = list(self.terms_years)
        record["is_placeholder"] = True
        return record


@dataclass(frozen=True)
class HKReversionaryBonusPolicy:
    """Sample policy record for the Phase 10 reversionary bonus product."""

    policy_id: str
    product_code: str
    issue_age: int
    gender: str
    term_years: int
    sum_assured: float
    annual_premium: float
    policy_year: int
    initial_vested_bonus: float = 0.0
    inforce_count: float = 1.0
    premium_mode: str = "ANNUAL"
    bonus_option: str = "VESTED_REVERSIONARY"
    distribution_channel: str = "AGENCY"
    source_id: str = "PHASE10-HK-RB-SAMPLE"

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _require_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "product_code", _require_text(self.product_code, "product_code").upper())
        object.__setattr__(self, "gender", _require_text(self.gender, "gender").upper())
        object.__setattr__(self, "premium_mode", _require_text(self.premium_mode, "premium_mode").upper())
        object.__setattr__(self, "bonus_option", _require_text(self.bonus_option, "bonus_option").upper())
        object.__setattr__(
            self,
            "distribution_channel",
            _require_text(self.distribution_channel, "distribution_channel").upper(),
        )
        object.__setattr__(self, "source_id", _require_text(self.source_id, "source_id"))
        if self.gender not in {"M", "F"}:
            raise ValueError("gender must be M or F")
        if int(self.term_years) not in VALID_TERMS:
            raise ValueError(f"term_years must be one of {VALID_TERMS}")
        if int(self.issue_age) < 0:
            raise ValueError("issue_age must be non-negative")
        if int(self.policy_year) < 1 or int(self.policy_year) > int(self.term_years):
            raise ValueError("policy_year must be in [1, term_years]")
        for field_name in ("sum_assured", "annual_premium", "inforce_count"):
            value = _require_finite(getattr(self, field_name), field_name)
            if value <= 0.0:
                raise ValueError(f"{field_name} must be positive")
            object.__setattr__(self, field_name, value)
        initial_vested_bonus = _require_finite(self.initial_vested_bonus, "initial_vested_bonus")
        if initial_vested_bonus < 0.0:
            raise ValueError("initial_vested_bonus must be non-negative")
        object.__setattr__(self, "initial_vested_bonus", initial_vested_bonus)

    def validate_against(self, mechanics: HKReversionaryBonusMechanics) -> None:
        if self.product_code != mechanics.product_code:
            raise ValueError("policy product_code does not match mechanics")
        if self.issue_age < mechanics.issue_age_min or self.issue_age > mechanics.issue_age_max:
            raise ValueError("issue_age is outside product issue range")
        if self.term_years not in mechanics.terms_years:
            raise ValueError("term_years is outside product term range")
        if self.sum_assured < mechanics.min_sum_assured or self.sum_assured > mechanics.max_sum_assured:
            raise ValueError("sum_assured is outside product issue range")
        if self.premium_mode != mechanics.premium_mode:
            raise ValueError("premium_mode does not match mechanics")
        if self.bonus_option != mechanics.bonus_option:
            raise ValueError("bonus_option does not match mechanics")

    def to_projection_product(
        self,
        mechanics: Optional[HKReversionaryBonusMechanics] = None,
    ) -> ParEndowmentProduct:
        """
        Convert to the current deterministic projection contract.

        The current engine has RB and terminal-bonus fields but reports RB
        outgo as non-guaranteed.  Phase 10 guarantee-split schedules below keep
        the vested-bonus guarantee treatment explicit for downstream reporting.
        """
        mechanics = mechanics or default_hk_reversionary_bonus_mechanics()
        self.validate_against(mechanics)
        return ParEndowmentProduct(
            term_years=self.term_years,
            issue_age=self.issue_age,
            gender=self.gender,
            sum_assured=self.sum_assured * mechanics.guaranteed_base_multiple,
            annual_premium=self.annual_premium,
            rb_rate_annual=mechanics.annual_reversionary_bonus_rate,
            terminal_bonus_pct=mechanics.terminal_bonus_pct,
            surrender_value_pct=mechanics.surrender_value_pct,
            initial_rb_accum=self.initial_vested_bonus,
        )

    def to_record(self) -> dict:
        return asdict(self)


def default_hk_reversionary_bonus_mechanics() -> HKReversionaryBonusMechanics:
    """Return the starter Phase 10 reversionary bonus product mechanics."""
    return HKReversionaryBonusMechanics(
        product_code="HKRB_PAR_2026",
        product_name="HK Educational Reversionary Bonus Participating Endowment",
    )


def _load_rb_policy_records() -> dict:
    global _RB_POLICY_RECORDS
    if _RB_POLICY_RECORDS is None:
        with _RB_FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            raw_records = json.load(fixture_file)
        _RB_POLICY_RECORDS = {
            _require_text(record["policy_id"], "policy_id"): record
            for record in raw_records["policies"]
        }
    return _RB_POLICY_RECORDS


def available_hk_reversionary_bonus_policy_ids() -> tuple:
    """Return sample Phase 10 Hong Kong reversionary bonus policy IDs."""
    return tuple(sorted(_load_rb_policy_records()))


def sample_hk_reversionary_bonus_policies(
    policy_ids: Optional[Iterable[str]] = None,
    mechanics: Optional[HKReversionaryBonusMechanics] = None,
) -> List[HKReversionaryBonusPolicy]:
    """Return governed sample policy records for the Phase 10 reversionary bonus product."""
    mechanics = mechanics or default_hk_reversionary_bonus_mechanics()
    records = _load_rb_policy_records()
    selected_ids = list(policy_ids or available_hk_reversionary_bonus_policy_ids())
    policies: List[HKReversionaryBonusPolicy] = []
    for policy_id in selected_ids:
        if policy_id not in records:
            raise KeyError(
                "no Phase 10 reversionary bonus policy fixture for {}; available policy IDs are {}".format(
                    policy_id,
                    ", ".join(available_hk_reversionary_bonus_policy_ids()),
                )
            )
        policy = HKReversionaryBonusPolicy(**records[policy_id])
        policy.validate_against(mechanics)
        policies.append(policy)
    return policies


def annual_reversionary_bonus_schedule(
    policy: HKReversionaryBonusPolicy,
    mechanics: Optional[HKReversionaryBonusMechanics] = None,
    declaration_assumption: Optional[HKDeclarationAssumption] = None,
) -> pd.DataFrame:
    """Return annual vested-bonus additions and the guaranteed benefit split."""
    mechanics = mechanics or default_hk_reversionary_bonus_mechanics()
    declaration_assumption = declaration_assumption or default_hk_declaration_assumption()
    policy.validate_against(mechanics)
    declared_rate = declaration_assumption.declared_reversionary_bonus_rate(mechanics)
    declared_terminal_bonus_pct = declaration_assumption.declared_terminal_bonus_pct(mechanics)
    annual_addition = policy.sum_assured * declared_rate * policy.inforce_count
    base_guarantee = policy.sum_assured * mechanics.guaranteed_base_multiple * policy.inforce_count
    vested_balance = policy.initial_vested_bonus * policy.inforce_count
    rows = []
    for policy_year in range(1, policy.term_years + 1):
        vested_balance += annual_addition
        death_vested = vested_balance * mechanics.death_benefit_vested_bonus_multiple
        maturity_vested = vested_balance * mechanics.maturity_vested_bonus_multiple
        rows.append(
            {
                "policy_id": policy.policy_id,
                "product_code": policy.product_code,
                "policy_year": policy_year,
                "month": policy_year * 12,
                "annual_vested_bonus_addition": annual_addition,
                "vested_bonus_balance": vested_balance,
                "guaranteed_base_benefit": base_guarantee,
                "guaranteed_death_benefit": base_guarantee + death_vested,
                "guaranteed_maturity_benefit": base_guarantee + maturity_vested,
                "declared_reversionary_bonus_rate": declared_rate,
                "terminal_bonus_pct": declared_terminal_bonus_pct,
                "terminal_bonus_guarantee_status": "NON_GUARANTEED",
                "vested_bonus_guarantee_status": "GUARANTEED_AFTER_DECLARATION",
                "declaration_assumption_id": declaration_assumption.assumption_id,
                "declaration_basis_name": declaration_assumption.basis_name,
                "sensitivity_label": declaration_assumption.sensitivity_label,
                "source_id": mechanics.source_id,
                "declaration_source_id": declaration_assumption.source_id,
                "limitation_id": mechanics.limitation_id,
            }
        )
    return pd.DataFrame(rows)


def reversionary_bonus_guarantee_split(
    policy: HKReversionaryBonusPolicy,
    mechanics: Optional[HKReversionaryBonusMechanics] = None,
    declaration_assumption: Optional[HKDeclarationAssumption] = None,
) -> dict:
    """Return the maturity guarantee split for a sample reversionary bonus policy."""
    mechanics = mechanics or default_hk_reversionary_bonus_mechanics()
    declaration_assumption = declaration_assumption or default_hk_declaration_assumption()
    schedule = annual_reversionary_bonus_schedule(policy, mechanics, declaration_assumption)
    final_row = schedule.iloc[-1]
    base_guarantee = float(final_row["guaranteed_base_benefit"])
    vested_bonus = float(final_row["vested_bonus_balance"]) * mechanics.maturity_vested_bonus_multiple
    return {
        "policy_id": policy.policy_id,
        "product_code": policy.product_code,
        "guaranteed_base_benefit": base_guarantee,
        "vested_reversionary_bonus": vested_bonus,
        "total_guaranteed_maturity_benefit": base_guarantee + vested_bonus,
        "terminal_bonus_pct": declaration_assumption.declared_terminal_bonus_pct(mechanics),
        "terminal_bonus_guarantee_status": "NON_GUARANTEED",
        "declaration_assumption_id": declaration_assumption.assumption_id,
        "sensitivity_label": declaration_assumption.sensitivity_label,
        "source_id": mechanics.source_id,
        "declaration_source_id": declaration_assumption.source_id,
        "limitation_id": mechanics.limitation_id,
    }


def sample_hk_reversionary_bonus_policy_table(
    policy_ids: Optional[Iterable[str]] = None,
    mechanics: Optional[HKReversionaryBonusMechanics] = None,
    declaration_assumption: Optional[HKDeclarationAssumption] = None,
) -> pd.DataFrame:
    """Return sample reversionary bonus policy fixtures with guarantee-split fields."""
    mechanics = mechanics or default_hk_reversionary_bonus_mechanics()
    declaration_assumption = declaration_assumption or default_hk_declaration_assumption()
    declared_reversionary_bonus_rate = declaration_assumption.declared_reversionary_bonus_rate(mechanics)
    declared_terminal_bonus_pct = declaration_assumption.declared_terminal_bonus_pct(mechanics)
    rows = []
    for policy in sample_hk_reversionary_bonus_policies(policy_ids, mechanics):
        record = policy.to_record()
        split = reversionary_bonus_guarantee_split(policy, mechanics, declaration_assumption)
        record["market"] = mechanics.market
        record["currency"] = mechanics.currency
        record["annual_reversionary_bonus_rate"] = mechanics.annual_reversionary_bonus_rate
        record["declared_reversionary_bonus_rate"] = declared_reversionary_bonus_rate
        record["terminal_bonus_pct"] = declared_terminal_bonus_pct
        record["projected_vested_reversionary_bonus"] = split["vested_reversionary_bonus"]
        record["total_guaranteed_maturity_benefit"] = split["total_guaranteed_maturity_benefit"]
        record["declaration_assumption_id"] = declaration_assumption.assumption_id
        record["declaration_basis_name"] = declaration_assumption.basis_name
        record["sensitivity_label"] = declaration_assumption.sensitivity_label
        record["guarantee_status"] = "BASE_PLUS_VESTED_RB_GUARANTEED_TERMINAL_BONUS_NON_GUARANTEED"
        record["mechanics_source_id"] = mechanics.source_id
        record["declaration_source_id"] = declaration_assumption.source_id
        record["limitation_id"] = mechanics.limitation_id
        rows.append(record)
    return pd.DataFrame(rows)


def validate_hk_reversionary_bonus_policy_table(
    table: pd.DataFrame,
    mechanics: Optional[HKReversionaryBonusMechanics] = None,
) -> bool:
    """Validate a policy table against the starter Phase 10 reversionary bonus mechanics."""
    mechanics = mechanics or default_hk_reversionary_bonus_mechanics()
    required = {
        "policy_id",
        "product_code",
        "issue_age",
        "gender",
        "term_years",
        "sum_assured",
        "annual_premium",
        "policy_year",
    }
    missing = sorted(required.difference(table.columns))
    if missing:
        raise ValueError("policy table missing required columns: {}".format(", ".join(missing)))
    if table["policy_id"].duplicated().any():
        raise ValueError("policy_id values must be unique")
    policy_fields = sorted(
        required.union(
            {
                "initial_vested_bonus",
                "inforce_count",
                "premium_mode",
                "bonus_option",
                "distribution_channel",
                "source_id",
            }.intersection(table.columns)
        )
    )
    for record in table[policy_fields].to_dict(orient="records"):
        policy = HKReversionaryBonusPolicy(**record)
        policy.validate_against(mechanics)
    return True


def hk_reversionary_bonus_asset_share_support_test(
    policy: HKReversionaryBonusPolicy,
    mechanics: Optional[HKReversionaryBonusMechanics] = None,
    declaration_assumption: Optional[HKDeclarationAssumption] = None,
    fund_positions: Optional[Sequence[AssetPosition]] = None,
    min_support_ratio: float = 1.0,
    min_support_margin: float = 0.0,
) -> HKAssetShareSupportReport:
    """Test deterministic asset-share support for vested and terminal bonuses."""
    mechanics = mechanics or default_hk_reversionary_bonus_mechanics()
    declaration_assumption = declaration_assumption or default_hk_declaration_assumption()
    fund_positions = list(fund_positions or default_hk_asset_share_fund_positions())
    policy.validate_against(mechanics)

    projection_product = replace(
        policy.to_projection_product(mechanics),
        rb_rate_annual=declaration_assumption.declared_reversionary_bonus_rate(mechanics),
        terminal_bonus_pct=declaration_assumption.declared_terminal_bonus_pct(mechanics),
    )
    projection = run_full_projection(projection_product, fund_positions)
    schedule = annual_reversionary_bonus_schedule(policy, mechanics, declaration_assumption)
    support_tests = schedule.merge(
        _annual_asset_share_view(projection.asset_share.projection),
        on=["policy_year", "month"],
        how="left",
    )
    final_month = policy.term_years * 12
    support_tests["support_test_type"] = "VESTED_RB_PLUS_MATURITY_TERMINAL_BONUS"
    support_tests["terminal_bonus_support_target"] = np.where(
        support_tests["month"] == final_month,
        support_tests["asset_share_eom"] * support_tests["terminal_bonus_pct"],
        0.0,
    )
    support_tests["support_obligation"] = (
        support_tests["vested_bonus_balance"]
        + support_tests["terminal_bonus_support_target"]
    )
    support_tests = _apply_support_status(
        support_tests,
        min_support_ratio=min_support_ratio,
        min_support_margin=min_support_margin,
    )
    support_tests["product_variant"] = "REVERSIONARY_BONUS"
    support_tests["support_basis_id"] = "PHASE10-HK-ASSET-SHARE-SUPPORT-BASE-2026"

    return HKAssetShareSupportReport(
        product_variant="REVERSIONARY_BONUS",
        policy_id=policy.policy_id,
        support_basis_id="PHASE10-HK-ASSET-SHARE-SUPPORT-BASE-2026",
        declaration_assumption_id=declaration_assumption.assumption_id,
        sensitivity_label=declaration_assumption.sensitivity_label,
        support_tests=support_tests,
        projection_summary=projection.summary(),
        min_support_ratio=min_support_ratio,
        min_support_margin=min_support_margin,
    )


@dataclass(frozen=True)
class HKLiabilityReportingPack:
    """Portfolio-level liability reporting views for Phase 10 HK PAR products."""

    reserve_view: pd.DataFrame
    tvog_view: pd.DataFrame
    bonus_supportability_view: pd.DataFrame
    management_summary: pd.DataFrame
    support_reports: List[HKAssetShareSupportReport]
    reporting_basis_id: str
    declaration_assumption_id: str
    sensitivity_label: str
    limitation_id: str = "LIM-P10-LIABILITY-REPORTING-PLACEHOLDER"
    governance_notes: List[str] = field(
        default_factory=lambda: [
            "SOA ASOP 56: reserve, option-value, and supportability rows retain policy, product, declaration, and source lineage.",
            "IA TAS M: management summaries are reproducible from policy-level views and do not replace actuarial sign-off.",
            "ERM limitation: TVOG rows require supplied Q-measure stochastic results; deterministic reserve views are educational only.",
        ]
    )

    def to_record(self) -> dict:
        return {
            "reporting_basis_id": self.reporting_basis_id,
            "declaration_assumption_id": self.declaration_assumption_id,
            "sensitivity_label": self.sensitivity_label,
            "policy_count": int(len(self.reserve_view)),
            "product_variants": sorted(self.reserve_view["product_variant"].unique().tolist()),
            "total_deterministic_reserve": float(
                self.reserve_view["deterministic_reserve"].sum()
            ),
            "supported_policy_count": int(
                (self.bonus_supportability_view["is_supported"] == True).sum()
            ),
            "tvog_reported_count": int(
                (self.tvog_view["tvog_status"] == "SUPPLIED_Q_MEASURE_TVOG").sum()
            ),
            "limitation_id": self.limitation_id,
            "governance_notes": list(self.governance_notes),
        }


def hk_liability_reserve_view(
    support_reports: Sequence[HKAssetShareSupportReport],
) -> pd.DataFrame:
    """Return policy-level deterministic reserve reporting rows."""
    rows = []
    for report in support_reports:
        summary = report.projection_summary
        first_row = report.support_tests.iloc[0]
        rows.append(
            {
                "policy_id": report.policy_id,
                "product_variant": report.product_variant,
                "product_code": first_row["product_code"],
                "currency": "HKD",
                "term_years": int(summary["term_years"]),
                "sum_assured": float(summary["sum_assured"]),
                "annual_premium": float(summary["annual_premium"]),
                "pv_premiums": float(summary["pv_premiums"]),
                "pv_guaranteed_benefits": float(summary["pv_guaranteed_benefits"]),
                "pv_non_guaranteed_benefits": float(
                    summary["pv_non_guaranteed_benefits"]
                ),
                "pv_expenses": float(summary["pv_expenses"]),
                "deterministic_reserve": float(summary["pv_net_liability"]),
                "asset_share_at_maturity": float(summary["asset_share_at_maturity"]),
                "declaration_assumption_id": report.declaration_assumption_id,
                "sensitivity_label": report.sensitivity_label,
                "support_basis_id": report.support_basis_id,
                "reserve_basis": "DETERMINISTIC_EDUCATIONAL_PROJECTION",
                "limitation_id": report.limitation_id,
            }
        )
    return pd.DataFrame(rows)


def _tvog_attr(result, field_name: str, default=np.nan):
    if result is None:
        return default
    if isinstance(result, dict):
        return result.get(field_name, default)
    return getattr(result, field_name, default)


def _is_finite_number(value) -> bool:
    try:
        return bool(np.isfinite(value))
    except (TypeError, ValueError):
        return False


def hk_liability_tvog_view(
    support_reports: Sequence[HKAssetShareSupportReport],
    tvog_results: Optional[dict] = None,
) -> pd.DataFrame:
    """Return policy-level TVOG reporting rows, using supplied Q-measure results."""
    tvog_results = tvog_results or {}
    rows = []
    for report in support_reports:
        summary = report.projection_summary
        result = tvog_results.get(report.policy_id)
        tvog_amount = _tvog_attr(result, "tvog")
        status = (
            "SUPPLIED_Q_MEASURE_TVOG"
            if _is_finite_number(tvog_amount)
            else "NOT_RUN_Q_MEASURE_REQUIRED"
        )
        rows.append(
            {
                "policy_id": report.policy_id,
                "product_variant": report.product_variant,
                "product_code": report.support_tests["product_code"].iloc[0],
                "currency": "HKD",
                "deterministic_guaranteed_pv": float(summary["pv_guaranteed_benefits"]),
                "q_measure_stochastic_guaranteed_pv": _tvog_attr(
                    result,
                    "pv_guaranteed_stochastic_mean",
                ),
                "tvog_amount": tvog_amount,
                "pv_p5": _tvog_attr(result, "pv_p5"),
                "pv_p95": _tvog_attr(result, "pv_p95"),
                "n_scenarios": _tvog_attr(result, "n_scenarios"),
                "tvog_run_id": _tvog_attr(result, "run_id", ""),
                "tvog_status": status,
                "measure_requirement": "Q",
                "declaration_assumption_id": report.declaration_assumption_id,
                "sensitivity_label": report.sensitivity_label,
                "limitation_id": "LIM-P10-TVOG-Q-MEASURE-REQUIRED",
            }
        )
    return pd.DataFrame(rows)


def hk_bonus_supportability_view(
    support_reports: Sequence[HKAssetShareSupportReport],
) -> pd.DataFrame:
    """Return final-period bonus supportability rows from support reports."""
    rows = []
    for report in support_reports:
        final_row = report.support_tests.iloc[-1]
        rows.append(
            {
                "policy_id": report.policy_id,
                "product_variant": report.product_variant,
                "product_code": final_row["product_code"],
                "support_basis_id": report.support_basis_id,
                "support_test_type": final_row["support_test_type"],
                "final_asset_share": float(final_row["asset_share_eom"]),
                "final_support_obligation": float(final_row["support_obligation"]),
                "final_support_margin": report.final_support_margin,
                "final_support_ratio": report.final_support_ratio,
                "support_status": final_row["support_status"],
                "is_supported": report.is_supported,
                "min_support_ratio": report.min_support_ratio,
                "min_support_margin": report.min_support_margin,
                "declaration_assumption_id": report.declaration_assumption_id,
                "sensitivity_label": report.sensitivity_label,
                "limitation_id": report.limitation_id,
            }
        )
    return pd.DataFrame(rows)


def hk_liability_management_summary(
    reserve_view: pd.DataFrame,
    tvog_view: pd.DataFrame,
    bonus_supportability_view: pd.DataFrame,
) -> pd.DataFrame:
    """Return product-variant management summary rows."""
    rows = []
    for product_variant, reserve_group in reserve_view.groupby("product_variant", sort=True):
        tvog_group = tvog_view[tvog_view["product_variant"] == product_variant]
        support_group = bonus_supportability_view[
            bonus_supportability_view["product_variant"] == product_variant
        ]
        supported_count = int((support_group["is_supported"] == True).sum())
        missing_tvog_count = int(
            (tvog_group["tvog_status"] != "SUPPLIED_Q_MEASURE_TVOG").sum()
        )
        not_supported_count = int(len(support_group) - supported_count)
        rows.append(
            {
                "product_variant": product_variant,
                "policy_count": int(len(reserve_group)),
                "total_sum_assured": float(reserve_group["sum_assured"].sum()),
                "total_annual_premium": float(reserve_group["annual_premium"].sum()),
                "total_deterministic_reserve": float(
                    reserve_group["deterministic_reserve"].sum()
                ),
                "total_pv_guaranteed_benefits": float(
                    reserve_group["pv_guaranteed_benefits"].sum()
                ),
                "total_reported_tvog": float(
                    tvog_group.loc[
                        tvog_group["tvog_status"] == "SUPPLIED_Q_MEASURE_TVOG",
                        "tvog_amount",
                    ].sum()
                ),
                "q_measure_tvog_missing_count": missing_tvog_count,
                "supported_policy_count": supported_count,
                "not_supported_policy_count": not_supported_count,
                "minimum_support_margin": float(support_group["final_support_margin"].min()),
                "minimum_support_ratio": float(support_group["final_support_ratio"].min()),
                "management_status": (
                    "REVIEW_REQUIRED"
                    if missing_tvog_count > 0 or not_supported_count > 0
                    else "READY_FOR_MANAGEMENT_REVIEW"
                ),
            }
        )
    return pd.DataFrame(rows)


def build_hk_liability_reporting_pack(
    cash_dividend_policies: Optional[Iterable[HKCashDividendPolicy]] = None,
    reversionary_bonus_policies: Optional[Iterable[HKReversionaryBonusPolicy]] = None,
    cash_dividend_mechanics: Optional[HKCashDividendMechanics] = None,
    reversionary_bonus_mechanics: Optional[HKReversionaryBonusMechanics] = None,
    declaration_assumption: Optional[HKDeclarationAssumption] = None,
    fund_positions: Optional[Sequence[AssetPosition]] = None,
    tvog_results: Optional[dict] = None,
    min_support_ratio: float = 1.0,
    min_support_margin: float = 0.0,
) -> HKLiabilityReportingPack:
    """Build the starter Phase 10 HK liability reporting pack."""
    cash_dividend_mechanics = cash_dividend_mechanics or default_hk_cash_dividend_mechanics()
    reversionary_bonus_mechanics = (
        reversionary_bonus_mechanics or default_hk_reversionary_bonus_mechanics()
    )
    declaration_assumption = declaration_assumption or default_hk_declaration_assumption()
    fund_positions = list(fund_positions or default_hk_asset_share_fund_positions())
    cash_dividend_policies = list(
        cash_dividend_policies
        if cash_dividend_policies is not None
        else sample_hk_cash_dividend_policies(mechanics=cash_dividend_mechanics)
    )
    reversionary_bonus_policies = list(
        reversionary_bonus_policies
        if reversionary_bonus_policies is not None
        else sample_hk_reversionary_bonus_policies(mechanics=reversionary_bonus_mechanics)
    )

    support_reports: List[HKAssetShareSupportReport] = []
    for policy in cash_dividend_policies:
        support_reports.append(
            hk_cash_dividend_asset_share_support_test(
                policy,
                mechanics=cash_dividend_mechanics,
                declaration_assumption=declaration_assumption,
                fund_positions=fund_positions,
                min_support_ratio=min_support_ratio,
                min_support_margin=min_support_margin,
            )
        )
    for policy in reversionary_bonus_policies:
        support_reports.append(
            hk_reversionary_bonus_asset_share_support_test(
                policy,
                mechanics=reversionary_bonus_mechanics,
                declaration_assumption=declaration_assumption,
                fund_positions=fund_positions,
                min_support_ratio=min_support_ratio,
                min_support_margin=min_support_margin,
            )
        )

    reserve_view = hk_liability_reserve_view(support_reports)
    tvog_view = hk_liability_tvog_view(support_reports, tvog_results=tvog_results)
    supportability_view = hk_bonus_supportability_view(support_reports)
    management_summary = hk_liability_management_summary(
        reserve_view,
        tvog_view,
        supportability_view,
    )
    return HKLiabilityReportingPack(
        reserve_view=reserve_view,
        tvog_view=tvog_view,
        bonus_supportability_view=supportability_view,
        management_summary=management_summary,
        support_reports=support_reports,
        reporting_basis_id="PHASE10-HK-LIABILITY-REPORTING-BASE-2026",
        declaration_assumption_id=declaration_assumption.assumption_id,
        sensitivity_label=declaration_assumption.sensitivity_label,
    )
