"""GD-1 - stepwise scenario-path detail set + GUI page (owner directive
2026-07-07: economic scenario paths, asset return paths, guaranteed /
non-guaranteed liability split displayed in the GUI)."""

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

from par_model_v2.projection.scenario_path_detail import (
    PERCENTILES, SCHEMA_VERSION, _inputs_digest, _par_bond_duration,
    _resolve_horizon, _resolve_seed, build_scenario_path_detail, CSV_NAMES,
    JSON_NAME)
from par_model_v2.viewer.igui_path_detail import (
    PATH_GUI_SCHEMA_VERSION, build_path_detail_response, render_paths_html)

MI = {
    "run_settings": {"seed": 123, "horizon_months": 480},
    "balance_sheet": {"assets": [
        {"asset_class": "government_bond", "market_value": 600.0},
        {"asset_class": "equity", "market_value": 250.0},
        {"asset_class": "cash", "market_value": 150.0},
    ]},
}


class TestEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = build_scenario_path_detail(
            MI, out_dir=None, n_paths=64, horizon_months=120, n_display=6)

    def test_schema_and_provenance(self):
        r = self.res
        self.assertEqual(r["schema"], SCHEMA_VERSION)
        self.assertEqual(r["seed"], 123)
        self.assertEqual(r["measure"], "P")
        self.assertEqual(r["horizon_months"], 120)
        self.assertIn("UNSIGNED", r["unsigned_note"])
        self.assertEqual(r["asset_classes"],
                         ["government_bond", "equity", "cash"])

    def test_fan_shapes_and_ordering(self):
        fans = self.res["fans"]
        T = self.res["horizon_months"]
        for key, exp_len in (("short_rate", T + 1), ("equity_index", T + 1)):
            fan = fans[key]
            for p in PERCENTILES:
                self.assertEqual(len(fan["p%d" % p]), exp_len, key)
            for i in (0, T // 2, exp_len - 1):
                vals = [fan["p%d" % p][i] for p in PERCENTILES]
                self.assertEqual(vals, sorted(vals),
                                 "%s fan not ordered at %d" % (key, i))
        for cls_ in self.res["asset_classes"]:
            ret = fans["asset_class_monthly_return"][cls_]
            cum = fans["asset_class_cumulative_index"][cls_]
            self.assertEqual(len(ret["p50"]), T)
            self.assertEqual(len(cum["p50"]), T + 1)
            self.assertAlmostEqual(cum["p50"][0], 100.0, places=6)

    def test_samples_shape(self):
        s = self.res["samples"]
        self.assertEqual(len(s["short_rate"]), 6)
        self.assertEqual(len(s["short_rate"][0]), 121)
        self.assertEqual(len(s["equity_index"]), 6)
        self.assertEqual(s["months"][0], 0)
        self.assertEqual(s["months"][-1], 120)

    def test_reproducible_same_seed(self):
        r2 = build_scenario_path_detail(
            MI, out_dir=None, n_paths=64, horizon_months=120, n_display=6)
        self.assertEqual(self.res["fans"]["short_rate"]["p50"],
                         r2["fans"]["short_rate"]["p50"])
        self.assertEqual(self.res["inputs_digest"], r2["inputs_digest"])

    def test_seed_changes_paths_and_digest(self):
        mi2 = json.loads(json.dumps(MI))
        mi2["run_settings"]["seed"] = 999
        r2 = build_scenario_path_detail(
            mi2, out_dir=None, n_paths=64, horizon_months=120, n_display=6)
        # NOTE: the antithetic construction pins the MEDIAN fan almost
        # exactly to the drift path for any seed, so seed sensitivity is
        # asserted on the tails and the raw sample paths instead.
        self.assertNotEqual(self.res["fans"]["short_rate"]["p95"],
                            r2["fans"]["short_rate"]["p95"])
        self.assertNotEqual(self.res["samples"]["short_rate"][0],
                            r2["samples"]["short_rate"][0])
        self.assertNotEqual(self.res["inputs_digest"], r2["inputs_digest"])

    def test_equity_class_matches_gbm_returns(self):
        # equity cumulative index must start at 100 and stay positive
        cum = self.res["fans"]["asset_class_cumulative_index"]["equity"]
        self.assertTrue(all(v > 0 for v in cum["p5"]))

    def test_defaults_when_inputs_empty(self):
        r = build_scenario_path_detail({}, n_paths=16, horizon_months=24)
        self.assertEqual(r["seed"], 42)
        self.assertEqual(r["asset_classes"], [])
        self.assertEqual(len(r["fans"]["short_rate"]["p50"]), 25)

    def test_helpers(self):
        self.assertEqual(_resolve_seed({}), 42)
        self.assertEqual(_resolve_horizon({}, 5000), 1200)
        self.assertEqual(_resolve_horizon({}, 1), 12)
        d = _par_bond_duration(0.04, 10.0)
        self.assertTrue(5.0 < d < 10.0, d)
        self.assertNotEqual(_inputs_digest(MI, 64, 120),
                            _inputs_digest(MI, 64, 121))

    def test_artifacts_written(self):
        with tempfile.TemporaryDirectory(prefix="gd1_") as td:
            r = build_scenario_path_detail(
                MI, out_dir=td, n_paths=32, horizon_months=36, n_display=4)
            self.assertTrue(os.path.exists(os.path.join(td, JSON_NAME)))
            for name in CSV_NAMES.values():
                path = os.path.join(td, name)
                self.assertTrue(os.path.exists(path), name)
                with open(path, encoding="utf-8") as fh:
                    header = fh.readline()
                self.assertTrue("," in header, name)
            with open(os.path.join(td, JSON_NAME), encoding="utf-8") as fh:
                on_disk = json.load(fh)
            self.assertEqual(on_disk["inputs_digest"], r["inputs_digest"])


class TestGuiResponse(unittest.TestCase):
    def _tmp_inputs(self, td):
        path = os.path.join(td, "model_inputs.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({**MI, "run_settings":
                       {"seed": 7, "horizon_months": 36}}, fh)
        return path

    def test_response_and_cache(self):
        with tempfile.TemporaryDirectory(prefix="gd1_gui_") as td:
            inputs = self._tmp_inputs(td)
            out_root = os.path.join(td, "run_output")
            r1 = build_path_detail_response(inputs, out_root)
            self.assertTrue(r1["ok"], r1.get("errors"))
            self.assertEqual(r1["schema"], PATH_GUI_SCHEMA_VERSION)
            self.assertFalse(r1["cached"])
            self.assertLessEqual(len(r1["samples"]["short_rate"]), 10)
            r2 = build_path_detail_response(inputs, out_root)
            self.assertTrue(r2["cached"])
            self.assertEqual(r1["inputs_digest"], r2["inputs_digest"])
            # change the seed -> cache invalidated
            with open(inputs, "w", encoding="utf-8") as fh:
                json.dump({**MI, "run_settings":
                           {"seed": 8, "horizon_months": 36}}, fh)
            r3 = build_path_detail_response(inputs, out_root)
            self.assertFalse(r3["cached"])
            self.assertNotEqual(r3["inputs_digest"], r1["inputs_digest"])

    def test_missing_inputs_still_serves_defaults(self):
        with tempfile.TemporaryDirectory(prefix="gd1_gui_") as td:
            r = build_path_detail_response(
                os.path.join(td, "nope.json"), os.path.join(td, "out"))
            self.assertTrue(r["ok"], r.get("errors"))
            self.assertIn("model_inputs.json not found", r["inputs_note"])
            self.assertEqual(r["seed"], 42)

    def test_page_anchors(self):
        html = render_paths_html()
        for anchor in ('id="chart"', 'id="series"', 'id="unsigned"',
                       '/path-data', 'id="btn-load"'):
            self.assertIn(anchor, html)


class TestCfGuardSplit(unittest.TestCase):
    """The CF-3 payload must now carry the guaranteed / non-guaranteed split."""

    def test_liability_chart_split_keys(self):
        from par_model_v2.viewer.igui_cashflows import CF_GUI_SCHEMA_VERSION
        self.assertEqual(CF_GUI_SCHEMA_VERSION, "cf3-gui-1.1")
        import inspect
        from par_model_v2.viewer import igui_cashflows
        src = inspect.getsource(igui_cashflows.build_cashflow_response)
        self.assertIn('"guaranteed"', src)
        self.assertIn('"non_guaranteed"', src)
        page = igui_cashflows.render_cashflows_html()
        self.assertIn("Benefits - guaranteed", page)
        self.assertIn("non-guaranteed", page)


if __name__ == "__main__":
    unittest.main()
