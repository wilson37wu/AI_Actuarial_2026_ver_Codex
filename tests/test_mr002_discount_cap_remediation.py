"""MR-002 / roadmap §4.1 #3 — CBIRC 3.0% discount-cap remediation.

Contract under test
-------------------
A liability-reserving discount rate ABOVE the CBIRC 3.0% valuation cap must be a
HARD validation ERROR (fails the report) UNLESS an APPROVED deviation
ChangeRecord authorises that specific override, in which case it is downgraded to
a governed WARNING (report passes with caution).

Standards: CBIRC C-ROSS reserve valuation (2023); SOA ASOP 56 §3.5;
IA TAS M §3.5 (material-assumption sign-off).

Written in unittest style so it runs under ``python -m unittest`` in the
network-restricted sandbox where pytest is unavailable (it also collects cleanly
under pytest).
"""

import unittest

import pandas as pd

from par_model_v2.validation.data_validator import (
    DiscountRateValidator,
    CheckSeverity,
    discount_rate_deviation_approved,
    validate_all,
)
from par_model_v2.governance.audit_trail import (
    ChangeRecord,
    GovernanceStore,
    SignOffStatus,
)

CAP = 0.030
ABOVE = 0.035          # legacy non-compliant rate
WELL_ABOVE = 0.040


def _d3r01(report):
    return next(c for c in report.checks if c.check_id == "D3-R01")


def _d3r03(report):
    return next(c for c in report.checks if c.check_id == "D3-R03")


def _approved_deviation_record(rate=ABOVE):
    """Build a fully-APPROVED assumption ChangeRecord authorising ``rate``."""
    cr = ChangeRecord.create(
        title=f"MR-002 deviation: reserving discount rate {rate:.3%} (owner-approved)",
        description="Owner-approved deviation above the CBIRC 3.0% valuation cap.",
        change_type="assumption_change",
        affected_components=["monthly_projection.discount_rate_annual"],
        standard_references=["CBIRC C-ROSS 2023", "IA TAS M §3.5"],
        before_snapshot={"discount_rate_annual": CAP},
        after_snapshot={"discount_rate_annual": rate},
        impact_assessment="Reserve impact quantified; owner sign-off obtained.",
        author="tester",
        phase="test",
    )
    cr.submit_for_peer_review("peer")
    cr.submit_to_owner("peer")
    cr.approve("owner")
    return cr


class TestScalarCapSeverity(unittest.TestCase):
    def setUp(self):
        self.v = DiscountRateValidator()

    def test_at_cap_passes(self):
        r = self.v.validate(CAP)
        self.assertTrue(r.passed)
        self.assertTrue(_d3r01(r).passed)

    def test_below_cap_passes(self):
        r = self.v.validate(0.025)
        self.assertTrue(_d3r01(r).passed)

    def test_above_cap_no_approval_is_error(self):
        r = self.v.validate(ABOVE)
        c = _d3r01(r)
        self.assertFalse(c.passed)
        self.assertEqual(c.severity, CheckSeverity.ERROR)
        self.assertFalse(r.passed)
        self.assertGreaterEqual(r.error_count, 1)

    def test_above_cap_with_approval_flag_is_warning(self):
        r = self.v.validate(ABOVE, approved_deviation=True)
        c = _d3r01(r)
        self.assertFalse(c.passed)
        self.assertEqual(c.severity, CheckSeverity.WARNING)
        self.assertTrue(r.passed)

    def test_error_details_mention_no_approved_deviation(self):
        c = _d3r01(self.v.validate(ABOVE))
        self.assertIn("no", c.details.lower())
        self.assertIn("cbirc", c.details.lower())


class TestDeviationHelper(unittest.TestCase):
    def test_approved_exact_rate_true(self):
        recs = [_approved_deviation_record(ABOVE)]
        self.assertTrue(discount_rate_deviation_approved(recs, ABOVE))

    def test_approved_but_rate_mismatch_false(self):
        recs = [_approved_deviation_record(ABOVE)]
        self.assertFalse(discount_rate_deviation_approved(recs, WELL_ABOVE))

    def test_draft_record_false(self):
        cr = ChangeRecord.create(
            title="draft", description="", change_type="assumption_change",
            affected_components=[], standard_references=[],
            before_snapshot={"discount_rate_annual": CAP},
            after_snapshot={"discount_rate_annual": ABOVE},
            impact_assessment="x", author="a", phase="p",
        )  # stays DRAFT
        self.assertFalse(discount_rate_deviation_approved([cr], ABOVE))

    def test_at_cap_record_does_not_authorise(self):
        # A record whose after-snapshot equals the cap (e.g. MR-001) never
        # authorises operating ABOVE the cap.
        cr = _approved_deviation_record(CAP)
        self.assertFalse(discount_rate_deviation_approved([cr], CAP))

    def test_wrong_change_type_false(self):
        cr = _approved_deviation_record(ABOVE)
        cr.change_type = "code_change"
        self.assertFalse(discount_rate_deviation_approved([cr], ABOVE))

    def test_none_and_empty_false(self):
        self.assertFalse(discount_rate_deviation_approved(None, ABOVE))
        self.assertFalse(discount_rate_deviation_approved([], ABOVE))

    def test_accepts_governance_store(self):
        store = GovernanceStore()
        store.add_change_record(_approved_deviation_record(ABOVE))
        self.assertTrue(discount_rate_deviation_approved(store, ABOVE))


class TestTermStructureCapSeverity(unittest.TestCase):
    def setUp(self):
        self.v = DiscountRateValidator()
        self.df = pd.DataFrame(
            {"term_years": [1, 5, 10], "rate": [0.028, 0.032, 0.035]}
        )

    def test_above_cap_no_approval_is_error(self):
        r = self.v.validate(self.df)
        c = _d3r03(r)
        self.assertFalse(c.passed)
        self.assertEqual(c.severity, CheckSeverity.ERROR)
        self.assertFalse(r.passed)

    def test_above_cap_with_flag_is_warning(self):
        r = self.v.validate(self.df, approved_deviation=True)
        c = _d3r03(r)
        self.assertEqual(c.severity, CheckSeverity.WARNING)
        self.assertTrue(r.passed)

    def test_all_within_cap_passes(self):
        df = pd.DataFrame({"term_years": [1, 5, 10], "rate": [0.020, 0.025, 0.030]})
        r = self.v.validate(df)
        self.assertTrue(_d3r03(r).passed)
        self.assertTrue(r.passed)

    def test_governance_authorises_every_above_cap_rate(self):
        store = GovernanceStore()
        store.add_change_record(_approved_deviation_record(0.032))
        store.add_change_record(_approved_deviation_record(0.035))
        r = self.v.validate(self.df, governance=store)
        self.assertEqual(_d3r03(r).severity, CheckSeverity.WARNING)
        self.assertTrue(r.passed)

    def test_governance_partial_authorisation_still_error(self):
        store = GovernanceStore()
        store.add_change_record(_approved_deviation_record(0.032))  # 0.035 unsigned
        r = self.v.validate(self.df, governance=store)
        self.assertEqual(_d3r03(r).severity, CheckSeverity.ERROR)
        self.assertFalse(r.passed)


class TestValidateAllThreads(unittest.TestCase):
    def test_above_cap_no_approval_fails(self):
        fr = validate_all(discount_rate=ABOVE)
        self.assertFalse(fr.discount_rate.passed)

    def test_above_cap_flag_passes(self):
        fr = validate_all(discount_rate=ABOVE, discount_rate_approved_deviation=True)
        self.assertTrue(fr.discount_rate.passed)

    def test_compliant_rate_passes(self):
        fr = validate_all(discount_rate=CAP)
        self.assertTrue(fr.discount_rate.passed)


class TestEndToEndGovernance(unittest.TestCase):
    def test_validate_uses_store_to_downgrade(self):
        store = GovernanceStore()
        store.add_change_record(_approved_deviation_record(ABOVE))
        r = DiscountRateValidator().validate(ABOVE, governance=store)
        self.assertEqual(_d3r01(r).severity, CheckSeverity.WARNING)
        self.assertTrue(r.passed)

    def test_empty_store_leaves_error(self):
        store = GovernanceStore()
        r = DiscountRateValidator().validate(ABOVE, governance=store)
        self.assertEqual(_d3r01(r).severity, CheckSeverity.ERROR)
        self.assertFalse(r.passed)


if __name__ == "__main__":
    unittest.main()
