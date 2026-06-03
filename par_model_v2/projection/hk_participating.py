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
) -> pd.DataFrame:
    """Return annual vested-bonus additions and the guaranteed benefit split."""
    mechanics = mechanics or default_hk_reversionary_bonus_mechanics()
    policy.validate_against(mechanics)
    annual_addition = mechanics.annual_vested_bonus_addition(policy.sum_assured) * policy.inforce_count
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
                "terminal_bonus_pct": mechanics.terminal_bonus_pct,
                "terminal_bonus_guarantee_status": "NON_GUARANTEED",
                "vested_bonus_guarantee_status": "GUARANTEED_AFTER_DECLARATION",
                "source_id": mechanics.source_id,
                "limitation_id": mechanics.limitation_id,
            }
        )
    return pd.DataFrame(rows)


def reversionary_bonus_guarantee_split(
    policy: HKReversionaryBonusPolicy,
    mechanics: Optional[HKReversionaryBonusMechanics] = None,
) -> dict:
    """Return the maturity guarantee split for a sample reversionary bonus policy."""
    mechanics = mechanics or default_hk_reversionary_bonus_mechanics()
    schedule = annual_reversionary_bonus_schedule(policy, mechanics)
    final_row = schedule.iloc[-1]
    base_guarantee = float(final_row["guaranteed_base_benefit"])
    vested_bonus = float(final_row["vested_bonus_balance"]) * mechanics.maturity_vested_bonus_multiple
    return {
        "policy_id": policy.policy_id,
        "product_code": policy.product_code,
        "guaranteed_base_benefit": base_guarantee,
        "vested_reversionary_bonus": vested_bonus,
        "total_guaranteed_maturity_benefit": base_guarantee + vested_bonus,
        "terminal_bonus_pct": mechanics.terminal_bonus_pct,
        "terminal_bonus_guarantee_status": "NON_GUARANTEED",
        "source_id": mechanics.source_id,
        "limitation_id": mechanics.limitation_id,
    }


def sample_hk_reversionary_bonus_policy_table(
    policy_ids: Optional[Iterable[str]] = None,
    mechanics: Optional[HKReversionaryBonusMechanics] = None,
) -> pd.DataFrame:
    """Return sample reversionary bonus policy fixtures with guarantee-split fields."""
    mechanics = mechanics or default_hk_reversionary_bonus_mechanics()
    rows = []
    for policy in sample_hk_reversionary_bonus_policies(policy_ids, mechanics):
        record = policy.to_record()
        split = reversionary_bonus_guarantee_split(policy, mechanics)
        record["market"] = mechanics.market
        record["currency"] = mechanics.currency
        record["annual_reversionary_bonus_rate"] = mechanics.annual_reversionary_bonus_rate
        record["terminal_bonus_pct"] = mechanics.terminal_bonus_pct
        record["projected_vested_reversionary_bonus"] = split["vested_reversionary_bonus"]
        record["total_guaranteed_maturity_benefit"] = split["total_guaranteed_maturity_benefit"]
        record["guarantee_status"] = "BASE_PLUS_VESTED_RB_GUARANTEED_TERMINAL_BONUS_NON_GUARANTEED"
        record["mechanics_source_id"] = mechanics.source_id
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
