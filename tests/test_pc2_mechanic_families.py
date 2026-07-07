"""PC-2 (owner directive 2026-07-03, track 4.0d) - extended mechanic
families (whole-life par / term assurance / deferred annuity) +
per-product expense/decrement overrides.

Covers: family registry + catalogue validation, override validation and
resolve passthrough (absent = bit-identical legacy behaviour), the three
new CF projectors' mechanics, loader acceptance + routing into the run
engine's PAR/non-PAR split, and end-to-end CF-set builds from composed
inputs."""
import unittest

import numpy as np

import par_model_v2.projection.cashflow_projection_set as CF
import par_model_v2.projection.portfolio_construction as PC
from par_model_v2.projection.portfolio_generator import (
    PRODUCT_LINE_RB, USER_PRODUCT_LINE_MAP, split_model_points,
    portfolio_from_model_points)

NEW_FAMILIES = ("WL_PAR_2026", "TERM_2026", "ANNUITY_2026")


def _row(ptype, term=20, prem=5000.0, sa=100000.0, **kw):
    r = {"product_type": ptype, "issue_age": 40, "gender": "M",
         "term_years": term, "sum_assured": sa, "annual_premium": prem,
         "policy_count": 100, "vested_bonus": 0.0}
    r.update(kw)
    return r


def _bucket_totals(ptype, **kw):
    df = CF.project_liability_set([_row(ptype, **kw)])
    g = df[df["product_class"] == str(kw.get("product_id", ptype))]
    return {b: float(g[b].sum()) for b in CF.LIABILITY_BUCKETS}


class TestFamilyRegistry(unittest.TestCase):
    def test_new_families_registered_everywhere(self):
        for fam in NEW_FAMILIES:
            self.assertIn(fam, PC.PRODUCT_FAMILIES)
            self.assertIn(fam, CF._PRODUCT_PROJECTORS)
        from scripts.load_user_inputs import ALLOWED_PRODUCT_TYPES
        for fam in NEW_FAMILIES:
            self.assertIn(fam, ALLOWED_PRODUCT_TYPES)

    def test_annuity_bucket_added(self):
        self.assertIn("annuity_guaranteed", CF.LIABILITY_BUCKETS)

    def test_default_catalogue_offers_new_families(self):
        fams = {p["family"] for p in PC.default_product_catalogue()}
        for fam in NEW_FAMILIES:
            self.assertIn(fam, fams)
        self.assertEqual(
            PC.validate_product_catalogue(PC.default_product_catalogue()), [])


class TestCatalogueValidation(unittest.TestCase):
    def test_annuity_param_bounds(self):
        cat = [{"product_id": "A", "family": "ANNUITY_2026",
                "term_years_min": 15, "term_years_max": 40,
                "annuity_rate": 0.90}]
        errs = PC.validate_product_catalogue(cat)
        self.assertTrue(any("annuity_rate" in e for e in errs))

    def test_override_bounds_only_checked_when_present(self):
        base = {"product_id": "T", "family": "TERM_2026",
                "term_years_min": 5, "term_years_max": 30}
        self.assertEqual(PC.validate_product_catalogue([dict(base)]), [])
        bad = dict(base, mortality_multiplier=99.0)
        errs = PC.validate_product_catalogue([bad])
        self.assertTrue(any("mortality_multiplier" in e for e in errs))

    def test_composer_annuity_term_must_exceed_deferral(self):
        cat = [{"product_id": "A", "family": "ANNUITY_2026",
                "term_years_min": 5, "term_years_max": 40,
                "deferral_years": 10}]
        rows = [_row("ANNUITY_2026", term=8, product_id="A")]
        errs = PC.validate_composed_portfolio(rows, cat)
        self.assertTrue(any("exceed the deferral" in e for e in errs))

    def test_composer_no_vested_bonus_on_term_or_annuity(self):
        cat = [{"product_id": "T", "family": "TERM_2026",
                "term_years_min": 5, "term_years_max": 30}]
        rows = [_row("TERM_2026", term=10, product_id="T", vested_bonus=500)]
        errs = PC.validate_composed_portfolio(rows, cat)
        self.assertTrue(any("vested reversionary bonus" in e for e in errs))


class TestResolveOverrides(unittest.TestCase):
    def test_overrides_passed_only_when_present(self):
        cat = [{"product_id": "T", "family": "TERM_2026",
                "term_years_min": 5, "term_years_max": 30,
                "acq_expense_pct": 0.02}]
        rows = PC.resolve_portfolio([_row("TERM_2026", term=10,
                                          product_id="T")], cat)
        mech = rows[0]["mechanics"]
        self.assertEqual(mech["acq_expense_pct"], 0.02)
        self.assertNotIn("renewal_expense_pct", mech)
        self.assertNotIn("mortality_multiplier", mech)


class TestTermProjector(unittest.TestCase):
    def test_death_only_no_maturity_no_surrender_by_default(self):
        tot = _bucket_totals("TERM_2026", term=10)
        self.assertGreater(tot["death_guaranteed"], 0.0)
        self.assertGreater(tot["premium"], 0.0)
        for b in ("maturity_guaranteed", "maturity_non_guaranteed",
                  "surrender_guaranteed", "surrender_non_guaranteed",
                  "cash_dividend", "annuity_guaranteed",
                  "death_non_guaranteed"):
            self.assertEqual(tot[b], 0.0, b)

    def test_surrender_value_pct_enables_surrender_cf(self):
        tot = _bucket_totals("TERM_2026", term=10,
                             mechanics={"surrender_value_pct": 0.5})
        self.assertGreater(tot["surrender_guaranteed"], 0.0)


class TestAnnuityProjector(unittest.TestCase):
    def test_payout_after_deferral_only(self):
        row = _row("ANNUITY_2026", term=30,
                   mechanics={"deferral_years": 10, "annuity_rate": 0.05})
        df = CF.project_liability_set([row])
        g = df[df["product_class"] == "ANNUITY_2026"].set_index("month")
        ann = g["annuity_guaranteed"]
        self.assertEqual(float(ann.loc[1:120].sum()), 0.0)
        self.assertGreater(float(ann.loc[121:360].sum()), 0.0)
        # premiums stop at vesting; no annuity CF beyond term
        self.assertEqual(float(g["premium"].loc[121:].sum()), 0.0)
        self.assertEqual(float(ann.loc[361:].sum()), 0.0)
        # locked in after vesting: no surrender CF in payout phase
        self.assertEqual(float(g["surrender_guaranteed"].loc[121:].sum()), 0.0)

    def test_no_death_benefit_after_vesting(self):
        row = _row("ANNUITY_2026", term=30,
                   mechanics={"deferral_years": 5})
        df = CF.project_liability_set([row])
        g = df[df["product_class"] == "ANNUITY_2026"].set_index("month")
        self.assertGreater(float(g["death_guaranteed"].loc[1:60].sum()), 0.0)
        self.assertEqual(float(g["death_guaranteed"].loc[61:].sum()), 0.0)


class TestWholeLifeProjector(unittest.TestCase):
    def test_wl_matches_rb_mechanics_same_inputs(self):
        rb = _bucket_totals("HKRB_PAR_2026", term=40)
        wl = _bucket_totals("WL_PAR_2026", term=40)
        for b in CF.LIABILITY_BUCKETS:
            self.assertAlmostEqual(rb[b], wl[b], places=6, msg=b)


class TestDecrementExpenseOverrides(unittest.TestCase):
    def test_mortality_multiplier_raises_death_cf(self):
        base = _bucket_totals("TERM_2026", term=10)
        up = _bucket_totals("TERM_2026", term=10,
                            mechanics={"mortality_multiplier": 2.0})
        self.assertGreater(up["death_guaranteed"], base["death_guaranteed"])

    def test_lapse_multiplier_zero_kills_surrender_cf(self):
        base = _bucket_totals("HKRB_PAR_2026", term=20)
        nolapse = _bucket_totals("HKRB_PAR_2026", term=20,
                                 mechanics={"lapse_multiplier": 0.0})
        self.assertGreater(base["surrender_guaranteed"], 0.0)
        self.assertEqual(nolapse["surrender_guaranteed"], 0.0)
        self.assertGreater(nolapse["maturity_guaranteed"],
                           base["maturity_guaranteed"])

    def test_expense_overrides_change_expense_only_when_present(self):
        base = _bucket_totals("HKCD_PAR_2026", term=15)
        cheap = _bucket_totals("HKCD_PAR_2026", term=15,
                               mechanics={"acq_expense_pct": 0.0,
                                          "renewal_expense_pct": 0.0,
                                          "renewal_expense_fixed_monthly": 0.0})
        self.assertLess(cheap["expense"], base["expense"])
        self.assertAlmostEqual(cheap["premium"], base["premium"], places=6)

    def test_absent_overrides_bit_identical_to_legacy(self):
        # empty mechanics dict must reproduce the no-mechanics projection
        a = _bucket_totals("HKRB_PAR_2026", term=20)
        b = _bucket_totals("HKRB_PAR_2026", term=20, mechanics={})
        for k in CF.LIABILITY_BUCKETS:
            self.assertEqual(a[k], b[k], k)


class TestLoaderAndRunRouting(unittest.TestCase):
    def test_loader_accepts_new_families_with_par_anchor(self):
        from scripts.load_user_inputs import validate_portfolio_dict
        payload = {"portfolio": [
            _row("HKRB_PAR_2026"), _row("WL_PAR_2026", term=50),
            _row("TERM_2026", term=10), _row("ANNUITY_2026", term=30)]}
        self.assertEqual([e for e in validate_portfolio_dict(payload)
                          if "[Portfolio]" in e or "Portfolio" in e], [])

    def test_loader_rejects_vested_bonus_on_new_nonpar(self):
        from scripts.load_user_inputs import validate_portfolio_dict
        payload = {"portfolio": [_row("HKRB_PAR_2026"),
                                 _row("ANNUITY_2026", term=30,
                                      vested_bonus=100.0)]}
        errs = validate_portfolio_dict(payload)
        self.assertTrue(any("vested reversionary bonus" in e for e in errs))

    def test_wl_only_portfolio_counts_as_par(self):
        from scripts.load_user_inputs import validate_portfolio_dict
        errs = validate_portfolio_dict(
            {"portfolio": [_row("WL_PAR_2026", term=50)]})
        self.assertFalse(any("at least one PAR" in e for e in errs))

    def test_split_routes_wl_par_and_nonpar(self):
        pts = [_row("HKCD_PAR_2026"), _row("WL_PAR_2026", term=50),
               _row("TERM_2026", term=10), _row("ANNUITY_2026", term=30),
               _row("GMMB_EQ_2026", term=15)]
        par, nonpar = split_model_points(pts)
        self.assertEqual([p["product_type"] for p in par],
                         ["HKCD_PAR_2026", "WL_PAR_2026"])
        self.assertEqual([p["product_type"] for p in nonpar],
                         ["TERM_2026", "ANNUITY_2026", "GMMB_EQ_2026"])

    def test_wl_builds_on_rb_line(self):
        self.assertEqual(USER_PRODUCT_LINE_MAP["WL_PAR_2026"],
                         PRODUCT_LINE_RB)
        res = portfolio_from_model_points([_row("WL_PAR_2026", term=50)])
        self.assertEqual(list(res.policies["product_line"].unique()),
                         [PRODUCT_LINE_RB])


class TestEndToEndCFSet(unittest.TestCase):
    def test_composed_set_builds_with_new_families(self):
        cat = PC.default_product_catalogue()
        rows = [
            dict(_row("x"), product_id="PAR_CD_SHORT", term_years=8),
            dict(_row("x"), product_id="WL_PAR_STD", term_years=50),
            dict(_row("x"), product_id="TERM_STD", term_years=15),
            dict(_row("x"), product_id="ANNUITY_DEF", term_years=30),
        ]
        for r in rows:
            r.pop("product_type")
        self.assertEqual(PC.validate_composed_portfolio(rows, cat), [])
        strategy = PC.default_asset_strategy()
        model_inputs = {
            "portfolio": rows,
            "product_catalogue": cat,
            "asset_strategy": strategy,
            "balance_sheet": PC.derive_balance_sheet(strategy),
        }
        result = CF.build_cashflow_projection_set(model_inputs)
        self.assertTrue(result["ok"])
        self.assertEqual(sorted(result["product_classes"]),
                         ["ANNUITY_DEF", "PAR_CD_SHORT", "TERM_STD",
                          "WL_PAR_STD"])
        self.assertGreater(
            result["totals"]["liability"]["annuity_guaranteed"], 0.0)
        liab = result["frames"]["liability_monthly"]
        ann = liab[liab["product_class"] == "ANNUITY_DEF"]
        self.assertEqual(
            float(ann[ann["month"] <= 120]["annuity_guaranteed"].sum()), 0.0)


if __name__ == "__main__":
    unittest.main()
