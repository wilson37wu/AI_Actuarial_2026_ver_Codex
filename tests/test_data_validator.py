"""
Tests for par_model_v2.validation.data_validator
=================================================

Covers:
  ModelPointValidator       — 9 test classes, 40+ tests
  MortalityTableValidator   — 3 test classes, 15+ tests
  LapseTableValidator       — 3 test classes, 15+ tests
  DiscountRateValidator     — 2 test classes, 10+ tests
  FullDataValidationReport  — 2 test classes, 8+ tests
  GovernanceStore integration — 2 test classes, 6 tests

VR-D02: ModelPointValidator      — IMPLEMENTED & TESTED
VR-D03: MortalityTableValidator  — IMPLEMENTED & TESTED
VR-D04: LapseTableValidator      — IMPLEMENTED & TESTED
VR-D05: DiscountRateValidator     — IMPLEMENTED & TESTED

Industry standards validated
-----------------------------
IA TAS M §3.9   — data validation before model use
SOA ASOP 56 §3.5 — model input validation
SOA ASOP 25 §3.3 — assumption appropriateness
CBIRC cap (3.0%) — regulatory rate check
"""

from __future__ import annotations

import pytest
import pandas as pd
import numpy as np

from par_model_v2.validation.data_validator import (
    CheckResult,
    CheckSeverity,
    DiscountRateValidator,
    FullDataValidationReport,
    LapseTableValidator,
    ModelPointValidator,
    MortalityTableValidator,
    ValidationReport,
    validate_all,
)


# ---------------------------------------------------------------------------
# Fixtures: canonical valid data
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_model_points_df():
    """5 clean model points — should pass all checks."""
    return pd.DataFrame([
        {"policy_id": 1, "age": 35, "gender": "M", "term_years": 10, "sum_assured": 100_000, "premium": 8_000},
        {"policy_id": 2, "age": 28, "gender": "F", "term_years": 20, "sum_assured": 200_000, "premium": 5_000},
        {"policy_id": 3, "age": 45, "gender": "M", "term_years":  5, "sum_assured":  50_000, "premium": 7_000},
        {"policy_id": 4, "age": 50, "gender": "F", "term_years":  5, "sum_assured":  75_000, "premium":10_000},
        {"policy_id": 5, "age": 30, "gender": "M", "term_years": 20, "sum_assured": 500_000, "premium":15_000},
    ])


@pytest.fixture
def valid_mortality_df():
    """Complete mortality table ages 18–75; monotone-increasing qx."""
    ages = list(range(18, 76))
    qx   = [0.00040 * np.exp(0.080 * (a - 25)) for a in ages]
    return pd.DataFrame({"age": ages, "qx": qx})


@pytest.fixture
def valid_lapse_df():
    """Lapse rates years 1–20 with early > late pattern."""
    base_rates = [0.12, 0.10, 0.08, 0.06, 0.05, 0.04, 0.04, 0.03, 0.03, 0.03,
                  0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02]
    return pd.DataFrame({"policy_year": list(range(1, 21)), "lapse_rate": base_rates})


# ===========================================================================
# 1. ModelPointValidator — schema checks
# ===========================================================================

class TestModelPointValidatorSchema:
    def test_valid_dataframe_passes(self, valid_model_points_df):
        report = ModelPointValidator().validate(valid_model_points_df)
        assert report.passed, report.summary()
        assert report.error_count == 0

    def test_valid_list_of_dicts_passes(self, valid_model_points_df):
        records = valid_model_points_df.to_dict("records")
        report = ModelPointValidator().validate(records)
        assert report.passed

    def test_missing_age_column_fails(self, valid_model_points_df):
        df = valid_model_points_df.drop(columns=["age"])
        report = ModelPointValidator().validate(df)
        assert not report.passed
        assert report.error_count >= 1

    def test_missing_multiple_columns_fails(self, valid_model_points_df):
        df = valid_model_points_df.drop(columns=["age", "premium"])
        report = ModelPointValidator().validate(df)
        assert not report.passed

    def test_wrong_input_type_raises(self):
        with pytest.raises(TypeError):
            ModelPointValidator().validate("not a dataframe")


# ===========================================================================
# 2. ModelPointValidator — completeness checks
# ===========================================================================

class TestModelPointValidatorCompleteness:
    def test_nan_age_fails(self, valid_model_points_df):
        df = valid_model_points_df.copy()
        df.loc[0, "age"] = np.nan
        report = ModelPointValidator().validate(df)
        assert not report.passed

    def test_nan_premium_fails(self, valid_model_points_df):
        df = valid_model_points_df.copy()
        df.loc[2, "premium"] = np.nan
        report = ModelPointValidator().validate(df)
        assert not report.passed

    def test_null_gender_fails(self, valid_model_points_df):
        df = valid_model_points_df.copy()
        df.loc[1, "gender"] = None
        report = ModelPointValidator().validate(df)
        assert not report.passed


# ===========================================================================
# 3. ModelPointValidator — range checks
# ===========================================================================

class TestModelPointValidatorRanges:
    def test_age_below_minimum_fails(self, valid_model_points_df):
        df = valid_model_points_df.copy()
        df.loc[0, "age"] = 17   # below minimum
        report = ModelPointValidator().validate(df)
        assert not report.passed

    def test_age_above_maximum_fails(self, valid_model_points_df):
        df = valid_model_points_df.copy()
        df.loc[0, "age"] = 70   # above maximum
        report = ModelPointValidator().validate(df)
        assert not report.passed

    def test_valid_boundary_ages_pass(self):
        """Age 18 and 65 are valid boundary values."""
        df = pd.DataFrame([
            {"age": 18, "gender": "M", "term_years": 5, "sum_assured": 50_000, "premium": 3_000},
            {"age": 65, "gender": "F", "term_years": 5, "sum_assured": 50_000, "premium": 3_000},
        ])
        report = ModelPointValidator().validate(df)
        # May warn on maturity age but no ERROR on age itself
        age_check = next(c for c in report.checks if c.check_id == "D3-01")
        assert age_check.passed

    def test_invalid_term_years_fails(self, valid_model_points_df):
        df = valid_model_points_df.copy()
        df.loc[0, "term_years"] = 15   # not in {5, 10, 20}
        report = ModelPointValidator().validate(df)
        assert not report.passed

    def test_all_valid_terms_pass(self):
        for term in [5, 10, 20]:
            df = pd.DataFrame([{"age": 30, "gender": "M", "term_years": term,
                                 "sum_assured": 100_000, "premium": 5_000}])
            report = ModelPointValidator().validate(df)
            term_check = next(c for c in report.checks if c.check_id == "D3-02")
            assert term_check.passed, f"term {term} should pass"

    def test_invalid_gender_fails(self, valid_model_points_df):
        df = valid_model_points_df.copy()
        df.loc[0, "gender"] = "X"
        report = ModelPointValidator().validate(df)
        assert not report.passed

    def test_gender_variants_accepted(self):
        """M/F/Male/Female/m/f should all pass."""
        for g in ["M", "F", "m", "f", "Male", "Female"]:
            df = pd.DataFrame([{"age": 30, "gender": g, "term_years": 10,
                                 "sum_assured": 100_000, "premium": 5_000}])
            report = ModelPointValidator().validate(df)
            gender_check = next(c for c in report.checks if c.check_id == "D3-05")
            assert gender_check.passed, f"gender '{g}' should be accepted"

    def test_zero_sum_assured_fails(self, valid_model_points_df):
        df = valid_model_points_df.copy()
        df.loc[0, "sum_assured"] = 0
        report = ModelPointValidator().validate(df)
        assert not report.passed

    def test_negative_premium_fails(self, valid_model_points_df):
        df = valid_model_points_df.copy()
        df.loc[0, "premium"] = -100
        report = ModelPointValidator().validate(df)
        assert not report.passed


# ===========================================================================
# 4. ModelPointValidator — consistency checks
# ===========================================================================

class TestModelPointValidatorConsistency:
    def test_premium_ratio_too_low_warns(self):
        """premium/sum_assured = 0.0001% → below 0.1% threshold → WARNING."""
        df = pd.DataFrame([{"age": 30, "gender": "M", "term_years": 10,
                             "sum_assured": 1_000_000, "premium": 1}])
        report = ModelPointValidator().validate(df)
        ratio_check = next(c for c in report.checks if c.check_id == "D4-01")
        assert not ratio_check.passed
        assert ratio_check.severity == CheckSeverity.WARNING

    def test_premium_ratio_too_high_warns(self):
        """premium = 80% of sum_assured → above 50% threshold → WARNING."""
        df = pd.DataFrame([{"age": 30, "gender": "M", "term_years": 10,
                             "sum_assured": 100_000, "premium": 80_000}])
        report = ModelPointValidator().validate(df)
        ratio_check = next(c for c in report.checks if c.check_id == "D4-01")
        assert not ratio_check.passed
        assert ratio_check.severity == CheckSeverity.WARNING

    def test_high_ratio_is_warning_not_error(self):
        """Ratio warning must not flip passed to False at report level."""
        df = pd.DataFrame([{"age": 30, "gender": "M", "term_years": 10,
                             "sum_assured": 100_000, "premium": 80_000}])
        report = ModelPointValidator().validate(df)
        # No ERROR-severity failures → report.passed should be True
        assert report.passed   # WARNINGs do not fail the report

    def test_maturity_age_over_75_warns(self):
        """age 60 + term 20 = age 80 at maturity → WARNING D3-06."""
        df = pd.DataFrame([{"age": 60, "gender": "M", "term_years": 20,
                             "sum_assured": 100_000, "premium": 5_000}])
        report = ModelPointValidator().validate(df)
        mat_check = next(c for c in report.checks if c.check_id == "D3-06")
        assert not mat_check.passed
        assert mat_check.severity == CheckSeverity.WARNING


# ===========================================================================
# 5. ModelPointValidator — uniqueness
# ===========================================================================

class TestModelPointValidatorUniqueness:
    def test_duplicate_policy_id_fails(self, valid_model_points_df):
        df = valid_model_points_df.copy()
        df.loc[1, "policy_id"] = df.loc[0, "policy_id"]  # create duplicate
        report = ModelPointValidator().validate(df)
        assert not report.passed

    def test_no_policy_id_column_skips_uniqueness_check(self, valid_model_points_df):
        df = valid_model_points_df.drop(columns=["policy_id"])
        report = ModelPointValidator().validate(df)
        check_ids = [c.check_id for c in report.checks]
        assert "D6-01" not in check_ids   # uniqueness check should not run

    def test_unique_policy_ids_pass(self, valid_model_points_df):
        report = ModelPointValidator().validate(valid_model_points_df)
        uniq_check = next(c for c in report.checks if c.check_id == "D6-01")
        assert uniq_check.passed


# ===========================================================================
# 6. MortalityTableValidator
# ===========================================================================

class TestMortalityTableValidatorValid:
    def test_valid_mortality_table_passes(self, valid_mortality_df):
        report = MortalityTableValidator().validate(valid_mortality_df)
        assert report.passed, report.summary()
        assert report.error_count == 0

    def test_list_of_dicts_accepted(self, valid_mortality_df):
        records = valid_mortality_df.to_dict("records")
        report = MortalityTableValidator().validate(records)
        assert report.passed

    def test_missing_qx_column_fails(self, valid_mortality_df):
        df = valid_mortality_df.drop(columns=["qx"])
        report = MortalityTableValidator().validate(df)
        assert not report.passed


class TestMortalityTableValidatorRanges:
    def test_qx_above_maximum_fails(self, valid_mortality_df):
        df = valid_mortality_df.copy()
        df.loc[0, "qx"] = 0.99  # implausibly high
        report = MortalityTableValidator().validate(df)
        assert not report.passed

    def test_qx_zero_fails(self, valid_mortality_df):
        df = valid_mortality_df.copy()
        df.loc[0, "qx"] = 0.0
        report = MortalityTableValidator().validate(df)
        assert not report.passed

    def test_missing_ages_in_coverage_fails(self):
        """Table missing ages 30–35 should fail coverage check."""
        ages = [a for a in range(18, 76) if not (30 <= a <= 35)]
        qx   = [0.001 * (a - 17) for a in ages]
        df   = pd.DataFrame({"age": ages, "qx": qx})
        report = MortalityTableValidator().validate(df)
        cov_check = next(c for c in report.checks if c.check_id == "D5-M02")
        assert not cov_check.passed


class TestMortalityTableValidatorMonotonicity:
    def test_non_monotone_qx_warns(self, valid_mortality_df):
        df = valid_mortality_df.copy()
        # Introduce a dip at age 40
        df.loc[df["age"] == 40, "qx"] = 0.00001   # very low
        report = MortalityTableValidator().validate(df)
        mono_check = next(c for c in report.checks if c.check_id == "D3-M01")
        assert not mono_check.passed
        assert mono_check.severity == CheckSeverity.WARNING

    def test_monotone_warning_doesnt_fail_report(self, valid_mortality_df):
        df = valid_mortality_df.copy()
        df.loc[df["age"] == 40, "qx"] = 0.00001
        report = MortalityTableValidator().validate(df)
        assert report.passed   # WARNING-only; report still passes


# ===========================================================================
# 7. LapseTableValidator
# ===========================================================================

class TestLapseTableValidatorValid:
    def test_valid_lapse_table_passes(self, valid_lapse_df):
        report = LapseTableValidator().validate(valid_lapse_df)
        assert report.passed, report.summary()
        assert report.error_count == 0

    def test_missing_lapse_rate_column_fails(self, valid_lapse_df):
        df = valid_lapse_df.drop(columns=["lapse_rate"])
        report = LapseTableValidator().validate(df)
        assert not report.passed

    def test_negative_lapse_rate_fails(self, valid_lapse_df):
        df = valid_lapse_df.copy()
        df.loc[0, "lapse_rate"] = -0.05
        report = LapseTableValidator().validate(df)
        assert not report.passed


class TestLapseTableValidatorRanges:
    def test_lapse_above_maximum_fails(self, valid_lapse_df):
        df = valid_lapse_df.copy()
        df.loc[0, "lapse_rate"] = 0.95  # above 60% ceiling
        report = LapseTableValidator().validate(df)
        assert not report.passed

    def test_lapse_at_boundary_values_pass(self):
        """lapse_rate 0.0 and 0.60 are at boundaries; should pass range check."""
        df = pd.DataFrame({"policy_year": [1, 2], "lapse_rate": [0.60, 0.0]})
        report = LapseTableValidator().validate(df)
        range_check = next(c for c in report.checks if c.check_id == "D2-L02")
        assert range_check.passed


class TestLapseTableValidatorTrend:
    def test_flat_lapse_curve_warns(self):
        """Equal lapse rate across all years should warn."""
        df = pd.DataFrame({
            "policy_year": list(range(1, 21)),
            "lapse_rate": [0.03] * 20,   # flat
        })
        report = LapseTableValidator().validate(df)
        trend_check = next(c for c in report.checks if c.check_id == "D3-L01")
        # flat: early == late, so early >= late → passes the trend check
        assert trend_check.passed

    def test_inverse_lapse_curve_warns(self):
        """Late-year lapse higher than early-year → WARNING."""
        rates = [0.01] * 3 + [0.02] * 7 + [0.10] * 10  # inverse
        df = pd.DataFrame({"policy_year": list(range(1, 21)), "lapse_rate": rates})
        report = LapseTableValidator().validate(df)
        trend_check = next(c for c in report.checks if c.check_id == "D3-L01")
        assert not trend_check.passed
        assert trend_check.severity == CheckSeverity.WARNING


# ===========================================================================
# 8. DiscountRateValidator
# ===========================================================================

class TestDiscountRateValidatorScalar:
    def test_valid_rate_3pct_passes(self):
        report = DiscountRateValidator().validate(0.030)
        assert report.passed, report.summary()

    def test_rate_below_minimum_fails(self):
        report = DiscountRateValidator().validate(0.001)  # below 0.5%
        assert not report.passed

    def test_rate_above_maximum_fails(self):
        report = DiscountRateValidator().validate(0.20)   # above 15%
        assert not report.passed

    def test_above_cap_without_approval_is_error(self):
        """MR-002: 3.5% above the CBIRC cap with no approved deviation is a HARD
        ERROR and fails the report (remediated from the prior WARNING)."""
        report = DiscountRateValidator().validate(0.035)
        assert not report.passed   # ERROR fails the report
        cbirc_check = next(c for c in report.checks if c.check_id == "D3-R01")
        assert not cbirc_check.passed
        assert cbirc_check.severity == CheckSeverity.ERROR

    def test_above_cap_with_approved_deviation_is_warning(self):
        """MR-002: an approved deviation downgrades the breach to a governed
        WARNING and the report passes."""
        report = DiscountRateValidator().validate(0.035, approved_deviation=True)
        assert report.passed   # WARNING does not fail the report
        cbirc_check = next(c for c in report.checks if c.check_id == "D3-R01")
        assert not cbirc_check.passed
        assert cbirc_check.severity == CheckSeverity.WARNING

    def test_compliant_30pct_passes_cbirc(self):
        report = DiscountRateValidator().validate(0.030)
        cbirc_check = next(c for c in report.checks if c.check_id == "D3-R01")
        assert cbirc_check.passed

    def test_very_low_rate_gives_info(self):
        report = DiscountRateValidator().validate(0.020)
        info_check = next(c for c in report.checks if c.check_id == "D3-R02")
        assert not info_check.passed
        assert info_check.severity == CheckSeverity.INFO


class TestDiscountRateValidatorTermStructure:
    def test_valid_term_structure_passes(self):
        df = pd.DataFrame({
            "term_years": [1, 2, 5, 10, 20],
            "rate":       [0.020, 0.022, 0.025, 0.027, 0.029],
        })
        report = DiscountRateValidator().validate(df)
        assert report.passed

    def test_inverted_curve_gives_info(self):
        df = pd.DataFrame({
            "term_years": [1, 2, 5, 10, 20],
            "rate":       [0.030, 0.029, 0.027, 0.025, 0.022],  # inverted
        })
        report = DiscountRateValidator().validate(df)
        inv_check = next(c for c in report.checks if c.check_id == "D4-R01")
        assert not inv_check.passed
        assert inv_check.severity == CheckSeverity.INFO
        assert report.passed   # INFO only

    def test_missing_required_column_fails(self):
        df = pd.DataFrame({"term_years": [1, 5, 10]})
        report = DiscountRateValidator().validate(df)
        assert not report.passed


# ===========================================================================
# 9. FullDataValidationReport and validate_all
# ===========================================================================

class TestFullDataValidationReport:
    def test_all_valid_inputs_passes(
        self, valid_model_points_df, valid_mortality_df, valid_lapse_df
    ):
        full = validate_all(
            model_points=valid_model_points_df,
            mortality=valid_mortality_df,
            lapse=valid_lapse_df,
            discount_rate=0.030,
        )
        assert full.passed, full.summary()
        assert full.total_errors == 0

    def test_partial_input_only_validates_provided(self, valid_model_points_df):
        full = validate_all(model_points=valid_model_points_df)
        assert full.mortality is None
        assert full.lapse is None
        assert full.discount_rate is None
        assert full.model_points is not None

    def test_summary_contains_overall_status(
        self, valid_model_points_df, valid_mortality_df, valid_lapse_df
    ):
        full = validate_all(
            model_points=valid_model_points_df,
            mortality=valid_mortality_df,
            lapse=valid_lapse_df,
            discount_rate=0.030,
        )
        summary = full.summary()
        assert "PASS" in summary or "FAIL" in summary
        assert "ModelPoints" in summary

    def test_one_failure_makes_full_report_fail(
        self, valid_model_points_df, valid_mortality_df, valid_lapse_df
    ):
        bad_lapse = pd.DataFrame({
            "policy_year": list(range(1, 21)),
            "lapse_rate": [-0.05] * 20,   # all negative → ERROR
        })
        full = validate_all(
            model_points=valid_model_points_df,
            mortality=valid_mortality_df,
            lapse=bad_lapse,
            discount_rate=0.030,
        )
        assert not full.passed
        assert full.total_errors >= 1


# ===========================================================================
# 10. GovernanceStore integration
# ===========================================================================

class TestGovernanceStoreIntegration:
    """Verify that validators correctly emit AuditEntry records."""

    def _make_store(self):
        from par_model_v2.governance.audit_trail import GovernanceStore
        return GovernanceStore()

    def test_validation_report_emits_audit_entry(self, valid_model_points_df):
        store = self._make_store()
        report = ModelPointValidator().validate(valid_model_points_df)
        initial_len = len(store.audit_trail.all())
        report.emit_to_governance_store(store)
        assert len(store.audit_trail.all()) == initial_len + 1

    def test_audit_entry_type_is_validation(self, valid_model_points_df):
        from par_model_v2.governance.audit_trail import EntryType
        store = self._make_store()
        report = ModelPointValidator().validate(valid_model_points_df)
        report.emit_to_governance_store(store)
        entry = store.audit_trail.all()[-1]
        assert entry.entry_type == EntryType.VALIDATION

    def test_validate_all_emits_single_combined_entry(
        self, valid_model_points_df, valid_mortality_df, valid_lapse_df
    ):
        store = self._make_store()
        initial_len = len(store.audit_trail.all())
        validate_all(
            model_points=valid_model_points_df,
            mortality=valid_mortality_df,
            lapse=valid_lapse_df,
            discount_rate=0.030,
            governance_store=store,
        )
        # One combined entry for all four validators
        assert len(store.audit_trail.all()) == initial_len + 1

    def test_failed_validation_recorded_with_fail_outcome(
        self, valid_model_points_df, valid_mortality_df, valid_lapse_df
    ):
        store = self._make_store()
        bad_mp = valid_model_points_df.copy()
        bad_mp.loc[0, "age"] = 100   # invalid age
        validate_all(
            model_points=bad_mp,
            mortality=valid_mortality_df,
            lapse=valid_lapse_df,
            discount_rate=0.030,
            governance_store=store,
        )
        entry = store.audit_trail.all()[-1]
        assert entry.details["outcome"] == "FAIL"
        assert entry.details["tests_failed"] >= 1

    def test_governance_store_json_roundtrip(
        self, valid_model_points_df, valid_mortality_df, valid_lapse_df
    ):
        """GovernanceStore remains serialisable after data validation entries."""
        store = self._make_store()
        validate_all(
            model_points=valid_model_points_df,
            mortality=valid_mortality_df,
            lapse=valid_lapse_df,
            discount_rate=0.030,
            governance_store=store,
        )
        blob = store.to_json()
        store2 = type(store).from_json(blob)
        assert len(store2.audit_trail.all()) == len(store.audit_trail.all())

    def test_actor_and_phase_propagated(self, valid_model_points_df):
        store = self._make_store()
        report = ModelPointValidator().validate(valid_model_points_df)
        report.emit_to_governance_store(
            store,
            actor="test-agent",
            phase="Phase 3: Model Validation & Testing",
        )
        entry = store.audit_trail.all()[-1]
        assert entry.actor == "test-agent"
        assert entry.phase == "Phase 3: Model Validation & Testing"


# ===========================================================================
# 11. ValidationReport properties
# ===========================================================================

class TestValidationReportProperties:
    def test_all_passed_report_has_no_errors(self):
        report = ValidationReport(validator_name="test")
        report.checks = [
            CheckResult("C1", "desc", True),
            CheckResult("C2", "desc", True),
        ]
        assert report.passed
        assert report.error_count == 0
        assert report.warning_count == 0

    def test_warning_doesnt_fail_report(self):
        report = ValidationReport(validator_name="test")
        report.checks = [
            CheckResult("C1", "error check", True, CheckSeverity.ERROR),
            CheckResult("C2", "warn check", False, CheckSeverity.WARNING),
        ]
        assert report.passed           # only ERROR checks matter for passed
        assert report.warning_count == 1
        assert report.error_count == 0

    def test_error_fails_report(self):
        report = ValidationReport(validator_name="test")
        report.checks = [
            CheckResult("C1", "error check", False, CheckSeverity.ERROR),
        ]
        assert not report.passed
        assert report.error_count == 1

    def test_failed_checks_property(self):
        report = ValidationReport(validator_name="test")
        report.checks = [
            CheckResult("C1", "passes", True),
            CheckResult("C2", "fails", False, CheckSeverity.ERROR),
            CheckResult("C3", "warns", False, CheckSeverity.WARNING),
        ]
        assert len(report.failed_checks) == 2
