"""Tests for Phase 10 Hong Kong participating product definitions."""

from __future__ import annotations

import pytest

from par_model_v2.projection import (
    HKCashDividendMechanics,
    HKCashDividendPolicy,
    HKDeclarationAssumption,
    HKReversionaryBonusMechanics,
    HKReversionaryBonusPolicy,
    ParEndowmentProduct,
    annual_cash_dividend_schedule,
    annual_reversionary_bonus_schedule,
    available_hk_cash_dividend_policy_ids,
    available_hk_reversionary_bonus_policy_ids,
    default_hk_cash_dividend_mechanics,
    default_hk_declaration_assumption,
    default_hk_reversionary_bonus_mechanics,
    hk_declaration_sensitivity,
    reversionary_bonus_guarantee_split,
    sample_hk_cash_dividend_policies,
    sample_hk_cash_dividend_policy_table,
    sample_hk_reversionary_bonus_policies,
    sample_hk_reversionary_bonus_policy_table,
    validate_hk_cash_dividend_policy_table,
    validate_hk_reversionary_bonus_policy_table,
)


class TestHKCashDividendMechanics:
    def test_default_mechanics_identifies_cash_dividend_terms(self) -> None:
        mechanics = default_hk_cash_dividend_mechanics()

        assert mechanics.market == "HK"
        assert mechanics.currency == "HKD"
        assert mechanics.dividend_option == "CASH"
        assert mechanics.annual_cash_dividend_rate == pytest.approx(0.012)
        assert mechanics.to_record()["is_placeholder"] is True

    def test_invalid_term_is_rejected_until_projection_support_exists(self) -> None:
        with pytest.raises(ValueError, match="terms_years"):
            HKCashDividendMechanics(
                product_code="BAD",
                product_name="unsupported term",
                terms_years=(15,),
            )

    def test_cash_dividend_amount_uses_sum_assured_rate(self) -> None:
        mechanics = default_hk_cash_dividend_mechanics()

        assert mechanics.annual_cash_dividend_amount(500_000.0) == pytest.approx(6_000.0)


class TestHKCashDividendPolicies:
    def test_fixture_policy_ids_are_stable(self) -> None:
        assert available_hk_cash_dividend_policy_ids() == (
            "HKCD000001",
            "HKCD000002",
            "HKCD000003",
        )

    def test_sample_policies_validate_against_mechanics(self) -> None:
        policies = sample_hk_cash_dividend_policies()
        mechanics = default_hk_cash_dividend_mechanics()

        assert len(policies) == 3
        for policy in policies:
            policy.validate_against(mechanics)
            assert policy.product_code == mechanics.product_code

    def test_unknown_policy_fixture_is_rejected(self) -> None:
        with pytest.raises(KeyError, match="available policy IDs"):
            sample_hk_cash_dividend_policies(["UNKNOWN"])

    def test_policy_converts_to_current_projection_contract(self) -> None:
        policy = sample_hk_cash_dividend_policies(["HKCD000001"])[0]
        projection_product = policy.to_projection_product()

        assert isinstance(projection_product, ParEndowmentProduct)
        assert projection_product.rb_rate_annual == pytest.approx(0.0)
        assert projection_product.terminal_bonus_pct == pytest.approx(0.0)
        assert projection_product.surrender_value_pct == pytest.approx(0.90)

    def test_invalid_policy_age_is_rejected_by_mechanics(self) -> None:
        policy = HKCashDividendPolicy(
            policy_id="BADAGE",
            product_code="HKCD_PAR_2026",
            issue_age=70,
            gender="F",
            term_years=10,
            sum_assured=500_000.0,
            annual_premium=40_000.0,
            policy_year=1,
        )

        with pytest.raises(ValueError, match="issue_age"):
            policy.validate_against(default_hk_cash_dividend_mechanics())


class TestHKCashDividendTablesAndSchedules:
    def test_sample_policy_table_contains_governance_and_dividend_fields(self) -> None:
        table = sample_hk_cash_dividend_policy_table()

        assert validate_hk_cash_dividend_policy_table(table)
        assert set(table["currency"]) == {"HKD"}
        assert table["illustrated_annual_cash_dividend"].sum() == pytest.approx(
            (500_000.0 + 800_000.0 + 300_000.0) * 0.012
        )
        assert table["mechanics_source_id"].str.len().min() > 0
        assert table["limitation_id"].str.len().min() > 0

    def test_policy_table_rejects_duplicate_policy_id(self) -> None:
        table = sample_hk_cash_dividend_policy_table()
        table.loc[1, "policy_id"] = table.loc[0, "policy_id"]

        with pytest.raises(ValueError, match="unique"):
            validate_hk_cash_dividend_policy_table(table)

    def test_annual_cash_dividend_schedule_is_non_guaranteed_cash(self) -> None:
        policy = sample_hk_cash_dividend_policies(["HKCD000001"])[0]
        schedule = annual_cash_dividend_schedule(policy)

        assert len(schedule) == policy.term_years
        assert list(schedule["month"]) == [12, 24, 36, 48, 60, 72, 84, 96, 108, 120]
        assert set(schedule["guarantee_status"]) == {"NON_GUARANTEED"}
        assert schedule["cash_dividend"].sum() == pytest.approx(6_000.0 * policy.term_years)


class TestHKDeclarationAssumptions:
    def test_default_declaration_basis_preserves_mechanics_rates(self) -> None:
        assumption = default_hk_declaration_assumption()

        assert assumption.declared_cash_dividend_rate(default_hk_cash_dividend_mechanics()) == pytest.approx(0.012)
        assert assumption.declared_reversionary_bonus_rate(
            default_hk_reversionary_bonus_mechanics()
        ) == pytest.approx(0.025)
        assert assumption.declared_terminal_bonus_pct(
            default_hk_reversionary_bonus_mechanics()
        ) == pytest.approx(0.35)
        assert assumption.to_record()["is_placeholder"] is True

    def test_negative_sensitivity_multiplier_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            HKDeclarationAssumption(cash_dividend_rate_multiplier=-0.1)

    def test_cash_dividend_sensitivity_flows_to_schedule_and_table(self) -> None:
        assumption = hk_declaration_sensitivity(
            "DIV_DOWN_50",
            cash_dividend_rate_multiplier=0.50,
        )
        policy = sample_hk_cash_dividend_policies(["HKCD000001"])[0]
        schedule = annual_cash_dividend_schedule(
            policy,
            declaration_assumption=assumption,
        )
        table = sample_hk_cash_dividend_policy_table(
            ["HKCD000001"],
            declaration_assumption=assumption,
        )

        assert set(schedule["sensitivity_label"]) == {"DIV_DOWN_50"}
        assert schedule["declared_cash_dividend_rate"].iloc[0] == pytest.approx(0.006)
        assert schedule["cash_dividend"].sum() == pytest.approx(3_000.0 * policy.term_years)
        assert table["illustrated_annual_cash_dividend"].iloc[0] == pytest.approx(3_000.0)

    def test_reversionary_bonus_sensitivity_flows_to_schedule_and_split(self) -> None:
        assumption = hk_declaration_sensitivity(
            "BONUS_DOWN",
            reversionary_bonus_rate_multiplier=0.80,
            terminal_bonus_pct_multiplier=0.50,
        )
        policy = sample_hk_reversionary_bonus_policies(["HKRB000001"])[0]
        schedule = annual_reversionary_bonus_schedule(
            policy,
            declaration_assumption=assumption,
        )
        split = reversionary_bonus_guarantee_split(
            policy,
            declaration_assumption=assumption,
        )

        assert schedule["declared_reversionary_bonus_rate"].iloc[0] == pytest.approx(0.020)
        assert schedule["terminal_bonus_pct"].iloc[-1] == pytest.approx(0.175)
        assert schedule["vested_bonus_balance"].iloc[-1] == pytest.approx(120_000.0)
        assert split["total_guaranteed_maturity_benefit"] == pytest.approx(720_000.0)
        assert split["terminal_bonus_pct"] == pytest.approx(0.175)


class TestHKReversionaryBonusMechanics:
    def test_default_mechanics_identifies_vested_bonus_terms(self) -> None:
        mechanics = default_hk_reversionary_bonus_mechanics()

        assert mechanics.market == "HK"
        assert mechanics.currency == "HKD"
        assert mechanics.bonus_option == "VESTED_REVERSIONARY"
        assert mechanics.annual_reversionary_bonus_rate == pytest.approx(0.025)
        assert mechanics.terminal_bonus_pct == pytest.approx(0.35)
        assert mechanics.to_record()["is_placeholder"] is True

    def test_invalid_terminal_bonus_pct_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="terminal_bonus_pct"):
            HKReversionaryBonusMechanics(
                product_code="BAD",
                product_name="bad terminal bonus",
                terminal_bonus_pct=1.5,
            )

    def test_annual_vested_bonus_addition_uses_sum_assured_rate(self) -> None:
        mechanics = default_hk_reversionary_bonus_mechanics()

        assert mechanics.annual_vested_bonus_addition(600_000.0) == pytest.approx(15_000.0)


class TestHKReversionaryBonusPolicies:
    def test_fixture_policy_ids_are_stable(self) -> None:
        assert available_hk_reversionary_bonus_policy_ids() == (
            "HKRB000001",
            "HKRB000002",
            "HKRB000003",
        )

    def test_sample_policies_validate_against_mechanics(self) -> None:
        policies = sample_hk_reversionary_bonus_policies()
        mechanics = default_hk_reversionary_bonus_mechanics()

        assert len(policies) == 3
        for policy in policies:
            policy.validate_against(mechanics)
            assert policy.product_code == mechanics.product_code

    def test_unknown_policy_fixture_is_rejected(self) -> None:
        with pytest.raises(KeyError, match="available policy IDs"):
            sample_hk_reversionary_bonus_policies(["UNKNOWN"])

    def test_policy_converts_to_current_projection_contract(self) -> None:
        policy = sample_hk_reversionary_bonus_policies(["HKRB000002"])[0]
        projection_product = policy.to_projection_product()

        assert isinstance(projection_product, ParEndowmentProduct)
        assert projection_product.rb_rate_annual == pytest.approx(0.025)
        assert projection_product.terminal_bonus_pct == pytest.approx(0.35)
        assert projection_product.initial_rb_accum == pytest.approx(112_500.0)

    def test_invalid_policy_bonus_option_is_rejected_by_mechanics(self) -> None:
        policy = HKReversionaryBonusPolicy(
            policy_id="BADBONUS",
            product_code="HKRB_PAR_2026",
            issue_age=40,
            gender="M",
            term_years=10,
            sum_assured=500_000.0,
            annual_premium=40_000.0,
            policy_year=1,
            bonus_option="CASH",
        )

        with pytest.raises(ValueError, match="bonus_option"):
            policy.validate_against(default_hk_reversionary_bonus_mechanics())


class TestHKReversionaryBonusTablesAndSchedules:
    def test_sample_policy_table_contains_governance_and_guarantee_split_fields(self) -> None:
        table = sample_hk_reversionary_bonus_policy_table()

        assert validate_hk_reversionary_bonus_policy_table(table)
        assert set(table["currency"]) == {"HKD"}
        assert table["projected_vested_reversionary_bonus"].sum() == pytest.approx(
            (600_000.0 * 0.025 * 10)
            + (112_500.0 + 900_000.0 * 0.025 * 20)
            + (35_000.0 + 350_000.0 * 0.025 * 5)
        )
        assert table["total_guaranteed_maturity_benefit"].min() > table["sum_assured"].min()
        assert table["mechanics_source_id"].str.len().min() > 0
        assert table["limitation_id"].str.len().min() > 0

    def test_policy_table_rejects_duplicate_policy_id(self) -> None:
        table = sample_hk_reversionary_bonus_policy_table()
        table.loc[1, "policy_id"] = table.loc[0, "policy_id"]

        with pytest.raises(ValueError, match="unique"):
            validate_hk_reversionary_bonus_policy_table(table)

    def test_annual_bonus_schedule_vests_into_guaranteed_split(self) -> None:
        policy = sample_hk_reversionary_bonus_policies(["HKRB000001"])[0]
        schedule = annual_reversionary_bonus_schedule(policy)

        assert len(schedule) == policy.term_years
        assert list(schedule["month"]) == [12, 24, 36, 48, 60, 72, 84, 96, 108, 120]
        assert set(schedule["vested_bonus_guarantee_status"]) == {"GUARANTEED_AFTER_DECLARATION"}
        assert set(schedule["terminal_bonus_guarantee_status"]) == {"NON_GUARANTEED"}
        assert schedule["vested_bonus_balance"].iloc[-1] == pytest.approx(150_000.0)
        assert schedule["guaranteed_maturity_benefit"].iloc[-1] == pytest.approx(750_000.0)

    def test_guarantee_split_separates_base_vested_and_terminal_bonus(self) -> None:
        policy = sample_hk_reversionary_bonus_policies(["HKRB000003"])[0]
        split = reversionary_bonus_guarantee_split(policy)

        assert split["guaranteed_base_benefit"] == pytest.approx(350_000.0)
        assert split["vested_reversionary_bonus"] == pytest.approx(78_750.0)
        assert split["total_guaranteed_maturity_benefit"] == pytest.approx(428_750.0)
        assert split["terminal_bonus_pct"] == pytest.approx(0.35)
        assert split["terminal_bonus_guarantee_status"] == "NON_GUARANTEED"
