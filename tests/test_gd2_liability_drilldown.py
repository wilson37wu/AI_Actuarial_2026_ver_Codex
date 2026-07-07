"""GD-2 - stepwise liability drill-down set + GUI page (owner directive
2026-07-07: per-model-point / per-product-class bucket-level cash-flow
inspector with guaranteed / non-guaranteed split)."""

import json
import os
import sys
import tempfile
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_REPO, os.path.join(_REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np

from par_model_v2.projection.cashflow_projection_set import (
    HORIZON_MONTHS, LIABILITY_BUCKETS, project_liability_set)
from par_model_v2.projection.liability_drilldown import (
    CSV_NAMES, JSON_NAME, SCHEMA_VERSION, STEP_COLUMNS, _coerce_portfolio,
    _inputs_digest, build_liability_drilldown, yearly_stepwise)
from par_model_v2.viewer.igui_drilldown import (
    DD_GUI_SCHEMA_VERSION, build_drilldown_response, render_drilldown_html)

MI = {
    "portfolio": [
        {"product_type": "HKCD_PAR_2026", "issue_age": "45", "gender": "M",
         "term_years": "20", "sum_assured": "100000",
         "annual_premium": "5000", "policy_count": "1000",
         "vested_bonus": "0"},
        {"product_type": "HKRB_PAR_2026", "issue_age": "40", "gender": "F",
         "term_years": "20", "sum_assured": "250000",
         "annual_premium": "9000", "policy_count": "500",
         "vested_bonus": "1200"},
        {"product_type": "HKRB_PAR_2026", "issue_age": "55", "gender": "M",
         "term_years": "10", "sum_assured": "80000",
         "annual_premium": "4000", "policy_count": "250",
         "vested_bonus": "0"},
    ],
}


class TestEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = build_liability_drilldown(MI, out_dir=None)

    def test_schema_and_selections(self):
        r = self.res
        self.assertEqual(r["schema"], SCHEMA_VERSION)
        self.assertIn("UNSIGNED", r["unsigned_note"])
        kinds = [s["kind"] for s in r["selections"]]
        self.assertEqual(kinds.count("model_point"), 3)
        # two distinct classes -> two class selections
        self.assertEqual(kinds.count("product_class"), 2)
        ids = [s["id"] for s in r["selections"]]
        self.assertIn("mp-1", ids)
        self.assertIn("class-HKRB_PAR_2026", ids)

    def test_stepwise_frame_shape(self):
        for s in self.res["selections"]:
            f = self.res["frames"][s["id"]]
            self.assertEqual(list(f.columns), STEP_COLUMNS)
            self.assertEqual(len(f), HORIZON_MONTHS)

    def test_decrement_counts_consistent(self):
        # in-force starts at the policy count and never increases
        f = self.res["frames"]["mp-1"]
        self.assertAlmostEqual(f["in_force_bom"].iloc[0], 1000.0)
        self.assertTrue((np.diff(f["in_force_bom"][:240]) <= 1e-9).all())
        # decrements only occur while in force (term 20y = 240m)
        self.assertAlmostEqual(f["death_count"][240:].sum(), 0.0)
        self.assertAlmostEqual(f["surrender_count"][240:].sum(), 0.0)
        self.assertGreater(f["death_count"][:240].sum(), 0.0)

    def test_guaranteed_split_adds_up(self):
        for s in self.res["selections"]:
            f = self.res["frames"][s["id"]]
            np.testing.assert_allclose(
                f["benefit_guaranteed"] + f["benefit_non_guaranteed"],
                f["total_benefit"], rtol=1e-12, atol=1e-9)
            np.testing.assert_allclose(
                f["premium"] - f["expense"] - f["total_benefit"],
                f["net_cashflow"], rtol=1e-12, atol=1e-9)

    def test_reconciles_exactly_with_cf1_class_totals(self):
        """THE consistency guarantee: class drill-down == CF-1 engine."""
        cf1 = project_liability_set(_coerce_portfolio(MI))
        for cls in ("HKCD_PAR_2026", "HKRB_PAR_2026"):
            ours = self.res["frames"]["class-" + cls]
            ref = (cf1[cf1["product_class"] == cls]
                   .sort_values("month").reset_index(drop=True))
            for b in LIABILITY_BUCKETS:
                np.testing.assert_allclose(
                    ours[b].to_numpy(), ref[b].to_numpy(),
                    rtol=1e-12, atol=1e-9,
                    err_msg="bucket %s diverges for %s" % (b, cls))

    def test_model_points_sum_to_class(self):
        mp2 = self.res["frames"]["mp-2"]
        mp3 = self.res["frames"]["mp-3"]
        cls = self.res["frames"]["class-HKRB_PAR_2026"]
        np.testing.assert_allclose(
            (mp2["premium"] + mp3["premium"]).to_numpy(),
            cls["premium"].to_numpy(), rtol=1e-12, atol=1e-9)

    def test_yearly_rollup(self):
        f = self.res["frames"]["mp-1"]
        y = yearly_stepwise(f)
        self.assertEqual(len(y), 100)
        self.assertAlmostEqual(y["premium"].sum(), f["premium"].sum(),
                               places=6)
        # year-1 in-force = BOM month 1; cumulative_net = month-12 value
        self.assertAlmostEqual(y["in_force_bom"].iloc[0],
                               f["in_force_bom"].iloc[0])
        self.assertAlmostEqual(y["cumulative_net"].iloc[0],
                               f["cumulative_net"].iloc[11])

    def test_digest_sensitivity(self):
        d1 = _inputs_digest(MI)
        mi2 = json.loads(json.dumps(MI))
        mi2["portfolio"][0]["sum_assured"] = "999999"
        self.assertNotEqual(d1, _inputs_digest(mi2))
        # balance sheet does NOT enter the liability drill-down digest
        mi3 = json.loads(json.dumps(MI))
        mi3["balance_sheet"] = {"assets": [{"asset_class": "cash",
                                            "market_value": "1"}]}
        self.assertEqual(d1, _inputs_digest(mi3))

    def test_empty_portfolio_raises(self):
        with self.assertRaises(ValueError):
            build_liability_drilldown({"portfolio": []})


class TestArtifacts(unittest.TestCase):
    def test_json_and_csvs_written(self):
        with tempfile.TemporaryDirectory() as td:
            res = build_liability_drilldown(MI, out_dir=td)
            self.assertTrue(os.path.exists(os.path.join(td, JSON_NAME)))
            for name in CSV_NAMES:
                self.assertTrue(os.path.exists(os.path.join(td, name)), name)
            with open(os.path.join(td, JSON_NAME), encoding="utf-8") as fh:
                j = json.load(fh)
            self.assertEqual(j["schema"], SCHEMA_VERSION)
            self.assertEqual(j["inputs_digest"], res["inputs_digest"])
            self.assertIn("yearly_preview", j)
            self.assertNotIn("frames", j)  # frames never serialised
            with open(os.path.join(td, CSV_NAMES[0]), encoding="utf-8") as fh:
                header = fh.readline().strip().split(",")
            self.assertEqual(header, ["selection"] + STEP_COLUMNS)


class TestGuiResponse(unittest.TestCase):
    def _write_inputs(self, td, mi=None):
        path = os.path.join(td, "model_inputs.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(mi or MI, fh)
        return path

    def test_full_payload_and_cache(self):
        with tempfile.TemporaryDirectory() as td:
            inputs = self._write_inputs(td)
            out = os.path.join(td, "out")
            res = build_drilldown_response(inputs, out)
            self.assertTrue(res["ok"], res)
            self.assertEqual(res["schema"], DD_GUI_SCHEMA_VERSION)
            self.assertFalse(res["cached"])
            self.assertIn("UNSIGNED", res["unsigned_note"])
            self.assertEqual(len(res["selections"]), 5)
            for s in res["selections"]:
                t = res["tables"][s["id"]]
                self.assertEqual(len(t["yearly"]["rows"]), 100)
                self.assertEqual(len(t["monthly"]["rows"]), HORIZON_MONTHS)
                c = res["charts"][s["id"]]
                self.assertEqual(len(c["guaranteed"]), 100)
                self.assertEqual(len(c["non_guaranteed"]), 100)
            # second call: served from digest cache
            res2 = build_drilldown_response(inputs, out)
            self.assertTrue(res2["cached"])
            self.assertEqual(res2["inputs_digest"], res["inputs_digest"])

    def test_cache_invalidated_on_input_change(self):
        with tempfile.TemporaryDirectory() as td:
            inputs = self._write_inputs(td)
            out = os.path.join(td, "out")
            r1 = build_drilldown_response(inputs, out)
            mi2 = json.loads(json.dumps(MI))
            mi2["portfolio"][0]["annual_premium"] = "6000"
            self._write_inputs(td, mi2)
            r2 = build_drilldown_response(inputs, out)
            self.assertFalse(r2["cached"])
            self.assertNotEqual(r1["inputs_digest"], r2["inputs_digest"])

    def test_missing_inputs_file(self):
        with tempfile.TemporaryDirectory() as td:
            res = build_drilldown_response(
                os.path.join(td, "nope.json"), os.path.join(td, "out"))
            self.assertFalse(res["ok"])
            self.assertTrue(any("not found" in e for e in res["errors"]))

    def test_no_portfolio(self):
        with tempfile.TemporaryDirectory() as td:
            res = build_drilldown_response(
                self._write_inputs(td, {"portfolio": []}),
                os.path.join(td, "out"))
            self.assertFalse(res["ok"])


class TestPage(unittest.TestCase):
    def test_page_self_contained(self):
        html = render_drilldown_html()
        for needle in ("Stepwise liability drill-down", "sel-pick",
                       "chart-dd", "drilldown-data", "UNSIGNED"):
            self.assertIn(needle, html)
        low = html.lower()
        # zero external references (the SVG namespace constant is local)
        for banned in ("<script src", "<link", "cdn.", "https://"):
            self.assertNotIn(banned, low)


if __name__ == "__main__":
    unittest.main()
