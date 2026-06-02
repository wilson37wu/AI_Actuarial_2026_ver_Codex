"""
Hong Kong participating product definitions for Phase 10.

This module defines the first Phase 10 liability product slice: a Hong
Kong-style cash dividend participating endowment.  The records are governed
educational fixtures.  They define contract mechanics and sample policy data;
declaration rules and stochastic supportability are added in later Phase 10
tasks.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from par_model_v2.projection.monthly_projection import (
    ParEndowmentProduct,
    VALID_TERMS,
)


_FIXTURE_PATH = Path(__file__).with_name("fixtures").joinpath(
    "hk_cash_dividend_policies.json"
)
_POLICY_RECORDS = None


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
) -> pd.DataFrame:
    """Return the sample policy fixtures as a DataFrame with dividend fields."""
    mechanics = mechanics or default_hk_cash_dividend_mechanics()
    rows = []
    for policy in sample_hk_cash_dividend_policies(policy_ids, mechanics):
        record = policy.to_record()
        record["market"] = mechanics.market
        record["currency"] = mechanics.currency
        record["annual_cash_dividend_rate"] = mechanics.annual_cash_dividend_rate
        record["illustrated_annual_cash_dividend"] = (
            mechanics.annual_cash_dividend_amount(policy.sum_assured) * policy.inforce_count
        )
        record["guarantee_status"] = "GUARANTEED_BASE_PLUS_NON_GUARANTEED_CASH_DIVIDEND"
        record["mechanics_source_id"] = mechanics.source_id
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
) -> pd.DataFrame:
    """Return annual non-guaranteed cash dividend payment dates and amounts."""
    mechanics = mechanics or default_hk_cash_dividend_mechanics()
    policy.validate_against(mechanics)
    annual_amount = mechanics.annual_cash_dividend_amount(policy.sum_assured) * policy.inforce_count
    rows = []
    for policy_year in range(1, policy.term_years + 1):
        rows.append(
            {
                "policy_id": policy.policy_id,
                "product_code": policy.product_code,
                "policy_year": policy_year,
                "month": policy_year * 12,
                "cash_dividend": annual_amount,
                "guarantee_status": "NON_GUARANTEED",
                "dividend_option": mechanics.dividend_option,
                "source_id": mechanics.source_id,
                "limitation_id": mechanics.limitation_id,
            }
        )
    return pd.DataFrame(rows)
