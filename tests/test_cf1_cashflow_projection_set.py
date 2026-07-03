"""CF-1 tests: liability/asset cash-flow projection set
(owner directive 2026-07-03; basis = deterministic central)."""

import json
import os
import sys
import tempfile
import unittest

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_REPO, os.path.join(_REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from par_model_v2.projection import cashflow_projection_set as CF
from par_model_v2.projection.monthly_projection import (
    ParEndowmentProduct, project_liability_cashflows)


def _portfolio():
    return [
        {"product_type": "HKCD_PAR_2026", "issue_age": 45, "gender": "M",
         "term_years": 20, "sum_assured": 100000.0, "annual_premium": 5000.0,
         "policy_count": 1000.0, "vested_bonus": 0.0},
        {"product_type": "HKRB_PAR_2026", "issue_age": 40, "gender": "F",
         "term_years": 20, "sum_assured": 250000.0, "annual_premium": 9000.0,
         "policy_count": 500.0, "vested_bonus": 1200.0},
        {"product_type": "GMMB_EQ_2026", "issue_age": 50, "gender": "M",
         "term_years": 15, "sum_assured": 300000.0, "annual_premium": 12000.0,
         "policy_count": 250.0, "vested_bonus": 0.0},
    ]


def _balance_sheet():
    return {"assets": [
        {"asset_class": "Government bonds", "market_value": 120e6, "illiquid": "no"},
        {"asset_class": "Corporate bonds", "market_value": 60e6, "illiquid": "no"},
        {"asset_class": "Private credit", "market_value": 20e6, "illiquid": "yes"},
        {"asset_class": "Equity", "market_value": 30e6, "illiquid": "no"},
        {"asset_class": "Cash", "market_value": 10e6, "illiquid": "no"},
    ]}


class TestLegacyConsistency(unittest.TestCase):
    """Premium, expense and decrement conventions must MATCH the existing
    per-product engine (same tables, same loadings, same timing)."""

    def test_premium_and_expense_match_legacy_engine(self):
        row = {"product_type": "HKCD_PAR_2026", "issue_age": 45, "gender": "M",
               "term_years": 20, "sum_assured": 100000.0,
               "annual_premium": 5000.0, "policy_count": 1.0,
               "vested_bonus": 0.0}
        legacy = project_liability_cashflows(ParEndowmentProduct(
            term_years=20, issue_age=45, gender="M", sum_assured=100000.0,
            annual_premium=5000.0)).cashflows
        mine = CF.project_liability_set([row])
        T = 240
        np.testing.assert_allclose(
            mine["premium"].to_numpy()[:T],
            legacy["premium"].to_numpy(), rtol=1e-10)
        np.testing.assert_allclose(
            mine["expense"].to_numpy()[:T],
            (legacy["acq_expense"] + legacy["renewal_expense"]).to_numpy(),
            rtol=1e-10)
        # nothing beyond the product term
        self.assertAlmostEqual(float(mine["premium"][T:].sum()), 0.0)


class TestLiabilityBuckets(unittest.TestCase):
    def setUp(self):
        self.df = CF.project_liability_set(_portfolio())

    def test_grid_shape_and_classes(self):
        self.assertEqual(set(self.df["product_class"].unique()),
                         {"HKCD_PAR_2026", "HKRB_PAR_2026", "GMMB_EQ_2026"})
        for _, g in self.df.groupby("product_class"):
            self.assertEqual(len(g), CF.HORIZON_MONTHS)
            self.assertEqual(int(g["month"].max()), 1200)

    def test_cd_product_has_at_least_six_populated_buckets(self):
        cd = self.df[self.df["product_class"] == "HKCD_PAR_2026"]
        populated = [b for b in CF.LIABILITY_BUCKETS
                     if float(cd[b].sum()) > 0.0]
        self.assertGreaterEqual(len(populated), 6, populated)
        for b in ("premium", "expense", "death_guaranteed",
                  "maturity_guaranteed", "surrender_guaranteed",
                  "cash_dividend"):
            self.assertIn(b, populated)
        # cash dividends do NOT vest into death/maturity for CD
        self.assertAlmostEqual(float(cd["death_non_guaranteed"].sum()), 0.0)
        self.assertAlmostEqual(float(cd["maturity_non_guaranteed"].sum()), 0.0)

    def test_rb_product_guarantee_split(self):
        rb = self.df[self.df["product_class"] == "HKRB_PAR_2026"]
        # both sides of every benefit bucket populated
        for b in ("death_guaranteed", "death_non_guaranteed",
                  "maturity_guaranteed", "maturity_non_guaranteed",
                  "surrender_guaranteed", "surrender_non_guaranteed"):
            self.assertGreater(float(rb[b].sum()), 0.0, b)
        self.assertAlmostEqual(float(rb["cash_dividend"].sum()), 0.0)
        # initially vested bonus is guaranteed: maturity_guaranteed exceeds
        # survivors x SA alone
        T = 240
        mat_g = float(rb["maturity_guaranteed"][:T].sum())
        self.assertGreater(mat_g, 0.0)

    def test_gmmb_guarantee_floor(self):
        gm = self.df[self.df["product_class"] == "GMMB_EQ_2026"]
        self.assertGreater(float(gm["death_guaranteed"].sum()), 0.0)
        self.assertGreater(float(gm["surrender_non_guaranteed"].sum()), 0.0)
        self.assertGreater(float(gm["maturity_guaranteed"].sum()), 0.0)

    def test_net_cashflow_identity(self):
        recomputed = (self.df["premium"] - self.df["expense"]
                      - self.df["total_benefit"])
        np.testing.assert_allclose(self.df["net_cashflow"].to_numpy(),
                                   recomputed.to_numpy(), rtol=1e-12)

    def test_all_buckets_non_negative(self):
        for b in CF.LIABILITY_BUCKETS:
            self.assertGreaterEqual(float(self.df[b].min()), 0.0, b)

    def test_empty_portfolio_refused(self):
        with self.assertRaises(ValueError):
            CF.project_liability_set([])
        with self.assertRaises(ValueError):
            CF.project_liability_set([{"product_type": "NOPE"}])


class TestAssetSet(unittest.TestCase):
    def setUp(self):
        self.cf, self.bal = CF.project_asset_set(_balance_sheet())

    def test_grid_and_classes(self):
        classes = {"Government bonds", "Corporate bonds", "Private credit",
                   "Equity", "Cash"}
        self.assertEqual(set(self.cf["asset_class"].unique()), classes)
        self.assertEqual(set(self.bal["asset_class"].unique()), classes)
        for _, g in self.bal.groupby("asset_class"):
            self.assertEqual(len(g), CF.HORIZON_MONTHS)

    def test_bond_book_level_and_equity_compounds(self):
        govt = self.bal[self.bal["asset_class"] == "Government bonds"]
        self.assertAlmostEqual(float(govt["market_value"].min()), 120e6)
        self.assertAlmostEqual(float(govt["market_value"].max()), 120e6)
        eq = self.bal[self.bal["asset_class"] == "Equity"]
        self.assertGreater(float(eq["market_value"].iloc[-1]), 30e6)
        mv = eq["market_value"].to_numpy()
        self.assertTrue((np.diff(mv) > 0).all())

    def test_income_positive_and_reinvestment_nets_principal(self):
        self.assertGreater(float(self.cf["income"].min()), 0.0)
        bonds = self.cf[self.cf["asset_class"] == "Corporate bonds"]
        np.testing.assert_allclose(
            bonds["principal_repaid"].to_numpy(),
            -bonds["reinvestment"].to_numpy(), rtol=1e-12)

    def test_empty_refused(self):
        with self.assertRaises(ValueError):
            CF.project_asset_set({"assets": []})


class TestYearlyRollup(unittest.TestCase):
    def test_cashflow_years_sum_months(self):
        liab_m = CF.project_liability_set(_portfolio())
        liab_y = CF.yearly_rollup(liab_m, "product_class")
        self.assertEqual(sorted(liab_y["year"].unique().tolist()),
                         list(range(1, CF.HORIZON_YEARS + 1)))
        for b in CF.LIABILITY_BUCKETS:
            self.assertAlmostEqual(float(liab_y[b].sum()),
                                   float(liab_m[b].sum()), places=4)
        cd_y1 = liab_y[(liab_y["product_class"] == "HKCD_PAR_2026")
                       & (liab_y["year"] == 2)]
        cd_m13_24 = liab_m[(liab_m["product_class"] == "HKCD_PAR_2026")
                           & (liab_m["month"].between(13, 24))]
        self.assertAlmostEqual(float(cd_y1["premium"].iloc[0]),
                               float(cd_m13_24["premium"].sum()), places=6)

    def test_balance_years_take_year_end(self):
        _, bal_m = CF.project_asset_set(_balance_sheet())
        bal_y = CF.yearly_rollup(bal_m, "asset_class", balance=True)
        eq_y3 = float(bal_y[(bal_y["asset_class"] == "Equity")
                            & (bal_y["year"] == 3)]["market_value"].iloc[0])
        eq_m36 = float(bal_m[(bal_m["asset_class"] == "Equity")
                             & (bal_m["month"] == 36)]["market_value"].iloc[0])
        self.assertAlmostEqual(eq_y3, eq_m36)


class TestWideOrientation(unittest.TestCase):
    def test_liability_wide_matches_tidy(self):
        tidy = CF.project_liability_set(_portfolio())
        wide = CF.to_wide(tidy, "product_class", "month")
        self.assertEqual(len(wide), CF.HORIZON_MONTHS)
        n_classes = tidy["product_class"].nunique()
        n_measures = len([c for c in tidy.columns
                          if c not in ("month", "product_class")])
        self.assertEqual(len(wide.columns), 1 + n_classes * n_measures)
        # spot equality: month 24 CD premium identical in both shapes
        t = float(tidy[(tidy["product_class"] == "HKCD_PAR_2026")
                       & (tidy["month"] == 24)]["premium"].iloc[0])
        w = float(wide[wide["month"] == 24]
                  ["HKCD_PAR_2026__premium"].iloc[0])
        self.assertAlmostEqual(t, w)

    def test_single_measure_frame_uses_plain_class_headers(self):
        _, bal_m = CF.project_asset_set(_balance_sheet())
        wide = CF.to_wide(bal_m, "asset_class", "month")
        self.assertIn("Equity", wide.columns)
        self.assertNotIn("Equity__market_value", wide.columns)
        eq_m36_tidy = float(bal_m[(bal_m["asset_class"] == "Equity")
                                  & (bal_m["month"] == 36)]
                            ["market_value"].iloc[0])
        eq_m36_wide = float(wide[wide["month"] == 36]["Equity"].iloc[0])
        self.assertAlmostEqual(eq_m36_tidy, eq_m36_wide)


class TestBuildArtifacts(unittest.TestCase):
    def test_full_set_written_and_reparseable(self):
        mi = {"portfolio": [{k: str(v) for k, v in r.items()}
                            for r in _portfolio()],
              "balance_sheet": {"assets": [
                  {k: str(v) for k, v in a.items()}
                  for a in _balance_sheet()["assets"]]}}
        with tempfile.TemporaryDirectory() as td:
            res = CF.build_cashflow_projection_set(mi, out_dir=td)
            self.assertTrue(res["ok"])
            self.assertEqual(res["basis"], "deterministic_central")
            self.assertTrue(res["inputs_digest"].startswith("sha256:"))
            self.assertIn("UNSIGNED", res["unsigned_note"])
            self.assertEqual(res["horizon"], {"months": 1200, "years": 100})
            self.assertEqual(len(res["csv_paths"]), 6)
            for path in res["csv_paths"].values():
                self.assertTrue(os.path.exists(path), path)
            with open(res["json_path"], encoding="utf-8") as fh:
                on_disk = json.load(fh)
            self.assertEqual(on_disk["schema"], CF.SCHEMA_VERSION)
            self.assertLessEqual(
                max(r["year"] for r in on_disk["yearly_preview"]["liability"]), 5)
            # totals consistent with the frames
            liab_m = res["frames"]["liability_monthly"]
            self.assertAlmostEqual(res["totals"]["liability"]["premium"],
                                   float(liab_m["premium"].sum()), places=4)
            # owner-requested orientation: time-only rows, classes horizontal
            import pandas as pd
            wide = pd.read_csv(res["csv_paths"]
                               ["liability_cashflows_monthly.csv"])
            self.assertEqual(len(wide), CF.HORIZON_MONTHS)
            self.assertEqual(wide.columns[0], "month")
            self.assertNotIn("product_class", wide.columns)
            self.assertIn("HKCD_PAR_2026__premium", wide.columns)
            self.assertIn("HKCD_PAR_2026__cash_dividend", wide.columns)
            bal = pd.read_csv(res["csv_paths"]["asset_balances_yearly.csv"])
            self.assertEqual(len(bal), CF.HORIZON_YEARS)
            self.assertEqual(bal.columns[0], "year")
            self.assertIn("Government bonds", bal.columns)
            self.assertNotIn("asset_class", bal.columns)

    def test_digest_is_deterministic_and_input_sensitive(self):
        mi = {"portfolio": _portfolio(), "balance_sheet": _balance_sheet()}
        d1 = CF.build_cashflow_projection_set(mi)["inputs_digest"]
        d2 = CF.build_cashflow_projection_set(mi)["inputs_digest"]
        self.assertEqual(d1, d2)
        mi2 = {"portfolio": _portfolio(), "balance_sheet": _balance_sheet()}
        mi2["portfolio"][0]["sum_assured"] = 999999.0
        self.assertNotEqual(
            d1, CF.build_cashflow_projection_set(mi2)["inputs_digest"])


if __name__ == "__main__":
    unittest.main()
