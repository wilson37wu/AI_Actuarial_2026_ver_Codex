"""GD-3 - stepwise run-result decomposition set + GUI page (owner directive
2026-07-07: surface the calculation waterfall behind the run headline).

The engine is exercised against the COMMITTED governed Phase 22 Task 4
aggregation report (docs/validation) - the exact structural contract
scripts/run_model.py writes into run_output/ - so the reconciliation
identities are tested on a real artifact, not a toy."""

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_REPO, os.path.join(_REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from par_model_v2.projection.run_result_decomposition import (
    AGG_REPORT_NAME, CSV_NAMES, JSON_NAME, SCHEMA_VERSION, artifact_digest,
    build_run_decomposition, build_waterfall, decompose_report)
from par_model_v2.viewer.igui_decomposition import (
    DECOMP_GUI_SCHEMA_VERSION, DECOMP_SET_DIRNAME,
    build_decomposition_response, render_decomposition_html)

GOVERNED_REPORT = os.path.join(
    _REPO, "docs", "validation", "PHASE22_TASK4_AGGREGATION_REPORT.json")


def _fixture_dir():
    """tmp out_root carrying a copy of the governed report as the run
    artifact (never touches docs/validation or run_output)."""
    d = tempfile.mkdtemp(prefix="gd3_")
    shutil.copyfile(GOVERNED_REPORT, os.path.join(d, AGG_REPORT_NAME))
    return d


class TestEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(GOVERNED_REPORT, encoding="utf-8") as fh:
            cls.report = json.load(fh)
        cls.agg = cls.report["aggregation"]
        cls.res = decompose_report(cls.report)

    def test_schema_and_unsigned(self):
        self.assertEqual(self.res["schema"], SCHEMA_VERSION)
        self.assertIn("UNSIGNED", self.res["unsigned_note"])

    def test_waterfall_reconciles_bit_for_bit(self):
        steps = {s["id"]: s for s in self.res["waterfall"]}
        agg = self.agg
        self.assertEqual(steps["standalone_sum"]["value"],
                         agg["standalone_scr_sum"])
        self.assertEqual(steps["var_covar"]["cumulative"],
                         agg["var_covar_scr"])
        self.assertEqual(steps["copula"]["cumulative"], agg["copula_scr"])
        self.assertEqual(steps["nested"]["cumulative"], agg["nested_scr"])
        self.assertAlmostEqual(
            steps["diversification"]["value"],
            agg["var_covar_scr"] - agg["standalone_scr_sum"])
        self.assertAlmostEqual(
            steps["copula_uplift"]["value"],
            agg["copula_scr"] - agg["var_covar_scr"])
        self.assertAlmostEqual(
            steps["nested_residual"]["value"],
            agg["nested_scr"] - agg["copula_scr"])

    def test_waterfall_order_and_kinds(self):
        wf = self.res["waterfall"]
        drivers = self.agg["drivers"]
        self.assertEqual([s["id"] for s in wf[:len(drivers)]],
                         ["standalone_%s" % d for d in drivers])
        self.assertEqual([s["kind"] for s in wf[len(drivers):]],
                         ["subtotal", "delta", "subtotal", "delta",
                          "subtotal", "delta", "final"])
        # build steps accumulate to the standalone sum
        cum = 0.0
        for s in wf[:len(drivers)]:
            cum += s["value"]
            self.assertAlmostEqual(cum, s["cumulative"])

    def test_driver_shares_sum_to_100(self):
        rows = self.res["drivers"]
        self.assertEqual([r["driver"] for r in rows], self.agg["drivers"])
        self.assertAlmostEqual(
            sum(r["share_of_sum_pct"] for r in rows), 100.0, places=6)

    def test_copula_candidates_carry_selection(self):
        rows = self.res["copulas"]
        self.assertEqual(len(rows), len(
            self.agg["copula_report"]["copulas"]))
        selected = [r for r in rows if r["selected"]]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["name"], self.agg["copula_selected"])

    def test_convergence_and_bootstrap_carried(self):
        cv = self.res["convergence"]
        self.assertFalse(cv["skipped"])
        self.assertEqual(cv["n_sim_grid"],
                         self.agg["tail_diagnostics"]["n_sim_grid"])
        self.assertEqual(len(cv["var_path"]), len(cv["n_sim_grid"]))
        self.assertIsNotNone(self.res["bootstrap_ci"]["var_point"])

    def test_inconsistent_artifact_refused(self):
        bad = json.loads(json.dumps(self.report))
        bad["aggregation"]["standalone_scr"]["rate"] += 1000.0
        with self.assertRaises(ValueError):
            build_waterfall(bad["aggregation"])

    def test_non_report_refused(self):
        with self.assertRaises(ValueError):
            decompose_report({"not": "a report"})

    def test_artifact_name_in_lockstep_with_run_model(self):
        import run_model
        self.assertEqual(AGG_REPORT_NAME, run_model.AGG_REPORT_NAME)


class TestArtifacts(unittest.TestCase):
    def test_json_and_csvs_written_and_digest_stable(self):
        root = _fixture_dir()
        try:
            out = os.path.join(root, "decomp")
            res = build_run_decomposition(
                os.path.join(root, AGG_REPORT_NAME), out_dir=out)
            self.assertTrue(os.path.exists(res["json_path"]))
            self.assertEqual(os.path.basename(res["json_path"]), JSON_NAME)
            for name in CSV_NAMES:
                path = res["csv_paths"][name]
                self.assertTrue(os.path.exists(path), name)
                with open(path, encoding="utf-8") as fh:
                    self.assertGreater(len(fh.readlines()), 1, name)
            with open(res["json_path"], encoding="utf-8") as fh:
                again = json.load(fh)
            self.assertEqual(again["source_digest"], res["source_digest"])
            self.assertEqual(
                res["source_digest"],
                artifact_digest(os.path.join(root, AGG_REPORT_NAME)))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_missing_artifact_raises(self):
        with self.assertRaises(FileNotFoundError):
            build_run_decomposition("/nonexistent/report.json")


class TestGuiResponse(unittest.TestCase):
    def test_no_run_artifact_is_a_clean_error(self):
        root = tempfile.mkdtemp(prefix="gd3_empty_")
        try:
            res = build_decomposition_response(root)
            self.assertFalse(res["ok"])
            self.assertIn(AGG_REPORT_NAME, res["errors"][0])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_fresh_then_cached_then_invalidated(self):
        root = _fixture_dir()
        try:
            first = build_decomposition_response(root)
            self.assertTrue(first["ok"])
            self.assertFalse(first["cached"])
            self.assertEqual(first["gui_schema"], DECOMP_GUI_SCHEMA_VERSION)
            second = build_decomposition_response(root)
            self.assertTrue(second["cached"])
            self.assertEqual(second["source_digest"],
                             first["source_digest"])
            # touching the artifact invalidates the cache
            path = os.path.join(root, AGG_REPORT_NAME)
            with open(path, encoding="utf-8") as fh:
                rep = json.load(fh)
            rep["run_timestamp"] = "2026-07-07T00:00:00+00:00"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(rep, fh)
            third = build_decomposition_response(root)
            self.assertTrue(third["ok"])
            self.assertFalse(third["cached"])
            self.assertNotEqual(third["source_digest"],
                                first["source_digest"])
            set_dir = os.path.join(root, DECOMP_SET_DIRNAME)
            self.assertTrue(os.path.exists(
                os.path.join(set_dir, JSON_NAME)))
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestPageAndRoutes(unittest.TestCase):
    def test_page_is_self_contained(self):
        html = render_decomposition_html()
        self.assertIn("SCR build-up waterfall", html)
        self.assertIn("/decomposition-data", html)
        # (the SVG namespace URI "http://www.w3.org/2000/svg" is inline
        # metadata, not an external reference - same guard as GD-1/GD-2)
        for banned in ("<script src", "<link", "cdn.", "https://"):
            self.assertNotIn(banned, html, banned)

    def test_routes_wired(self):
        import run_gui
        srv = run_gui.make_server(
            0, os.path.join(tempfile.mkdtemp(prefix="gd3_srv_"), "mi.json"))
        host, port = srv.server_address
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = "http://%s:%d" % (host, port)
        try:
            with urllib.request.urlopen(base + "/decomposition",
                                        timeout=15) as r:
                page = r.read().decode("utf-8")
            self.assertIn("Stepwise run-result decomposition", page)
            self.assertIn("<nav ", page)
            try:
                with urllib.request.urlopen(base + "/decomposition-data",
                                            timeout=30) as r:
                    body = json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:  # 422 = no run yet: fine
                self.assertEqual(exc.code, 422)
                body = json.loads(exc.read().decode("utf-8"))
            self.assertIn("ok", body)
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
