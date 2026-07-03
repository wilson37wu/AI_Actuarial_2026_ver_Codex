"""GUI-2 tests: stress catalogue, apply/re-gate, deltas, endpoints (Roadmap 4.0)."""

import copy
import json
import os
import sys
import tempfile
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_REPO, os.path.join(_REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import load_user_inputs as lui
from par_model_v2.viewer import igui_stress as S
from par_model_v2.viewer.igui_run_execution import _clean_gated_inputs, verify_run_gate


def _base():
    if not hasattr(_base, "_cache"):
        _base._cache = _clean_gated_inputs()
    return copy.deepcopy(_base._cache)


class TestCatalogue(unittest.TestCase):
    def test_all_available_on_clean_inputs(self):
        cat = S.catalogue_for(_base())
        self.assertEqual(len(cat), len(S.STRESS_CATALOGUE))
        self.assertTrue(all(c["available"] for c in cat), cat)

    def test_availability_flags(self):
        mi = _base()
        mi["portfolio"] = []
        mi["balance_sheet"] = {}
        cat = {c["id"]: c for c in S.catalogue_for(mi)}
        self.assertFalse(cat["STRESS_SA_UP20"]["available"])
        self.assertFalse(cat["STRESS_EXPO_UP50"]["available"])
        self.assertTrue(cat["SENS_CONF_99"]["available"])
        cat_none = S.catalogue_for(None)
        self.assertTrue(all(not c["available"] for c in cat_none))


class TestApplyStress(unittest.TestCase):
    def test_every_stress_regates_cleanly(self):
        for item in S.STRESS_CATALOGUE:
            applied = S.apply_stress(_base(), item["id"], loader_module=lui)
            self.assertTrue(applied["ok"], (item["id"], applied.get("errors")))
            self.assertTrue(verify_run_gate(applied["stressed_inputs"])["ok"], item["id"])
            self.assertTrue(applied["changes"], item["id"])

    def test_base_inputs_not_mutated(self):
        mi = _base()
        snapshot = json.dumps(mi, sort_keys=True, default=str)
        S.apply_stress(mi, "STRESS_SA_UP20", loader_module=lui)
        self.assertEqual(json.dumps(mi, sort_keys=True, default=str), snapshot)

    def test_transforms_change_what_they_claim(self):
        a = S.apply_stress(_base(), "STRESS_SA_UP20", loader_module=lui)
        base_sa = _base()["portfolio"][0]["sum_assured"]
        self.assertAlmostEqual(
            a["stressed_inputs"]["portfolio"][0]["sum_assured"], base_sa * 1.2)
        a = S.apply_stress(_base(), "SENS_CONF_99", loader_module=lui)
        self.assertEqual(a["stressed_inputs"]["assumptions"]["confidence"], 0.99)
        a = S.apply_stress(_base(), "SENS_SEED_SHIFT", loader_module=lui)
        self.assertEqual(a["stressed_inputs"]["run_settings"]["seed"],
                         int(_base()["run_settings"]["seed"]) + 1000)

    def test_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            S.apply_stress(_base(), "NOPE", loader_module=lui)


class TestCompare(unittest.TestCase):
    def test_deltas(self):
        base = {"nested_scr": 100.0, "copula_scr": 90.0, "var_covar_scr": 80.0,
                "standalone_scr": {"rate": 10.0, "equity": 20.0}}
        stress = {"nested_scr": 120.0, "copula_scr": 81.0, "var_covar_scr": 80.0,
                  "standalone_scr": {"rate": 15.0, "equity": 20.0}}
        cmp_ = S.compare_headlines(base, stress)
        self.assertTrue(cmp_["ok"])
        rows = {r["metric"]: r for r in cmp_["rows"]}
        self.assertAlmostEqual(rows["nested_scr"]["delta"], 20.0)
        self.assertAlmostEqual(rows["nested_scr"]["delta_pct"], 20.0)
        self.assertAlmostEqual(rows["copula_scr"]["delta_pct"], -10.0)
        self.assertAlmostEqual(rows["standalone.rate"]["delta"], 5.0)

    def test_missing_side(self):
        self.assertFalse(S.compare_headlines(None, {"nested_scr": 1})["ok"])


class TestRunStressGateRefusal(unittest.TestCase):
    def test_missing_inputs_file(self):
        res = S.run_stress("/no/such/file.json", "SENS_CONF_99",
                           tempfile.mkdtemp(), smoke=True, repo_root=_REPO)
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "inputs_missing")


class TestAssetStressPanel(unittest.TestCase):
    def test_report_shape(self):
        rep = S.asset_stress_report()
        self.assertTrue(rep["ok"], rep)
        self.assertGreaterEqual(len(rep["scenarios"]), 3)
        for s in rep["scenarios"]:
            self.assertIn("total_impact", s)
            self.assertTrue(s["impacts_by_class"])
        json.dumps(rep)  # JSON-safe


class TestPages(unittest.TestCase):
    def test_stress_page_self_contained_and_wired(self):
        page = S.render_stress_html()
        for banned in ("http://", "https://", "src="):
            self.assertNotIn(banned, page)
        for needed in ("/run-stress", "/stress-catalogue", "/asset-stress", "/jobs/"):
            self.assertIn(needed, page)

    def test_run_page_links_stress_console(self):
        from par_model_v2.viewer.igui_run_execution import render_run_html
        self.assertIn('href="/stress"', render_run_html())


class TestHttpEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        import run_gui
        cls.tmp = tempfile.mkdtemp(prefix="gui2_http_")
        cls.inp = os.path.join(cls.tmp, "model_inputs.json")
        with open(cls.inp, "w", encoding="utf-8") as fh:
            json.dump(_base(), fh, indent=1)
        cls.srv = run_gui.make_server(0, cls.inp)
        host, port = cls.srv.server_address
        cls.base_url = "http://{}:{}".format(host, port)
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def _get(self, path):
        import urllib.request
        with urllib.request.urlopen(self.base_url + path, timeout=10) as r:
            return r.status, r.read().decode("utf-8")

    def test_stress_page_served(self):
        status, body = self._get("/stress")
        self.assertEqual(status, 200)
        self.assertIn("Stress &amp; sensitivities", body)

    def test_catalogue_endpoint(self):
        status, body = self._get("/stress-catalogue")
        self.assertEqual(status, 200)
        j = json.loads(body)
        self.assertTrue(j["ok"])
        self.assertEqual(len(j["catalogue"]), len(S.STRESS_CATALOGUE))

    def test_asset_stress_endpoint(self):
        status, body = self._get("/asset-stress")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

    def test_run_stress_requires_stress_id(self):
        import urllib.request, urllib.error
        req = urllib.request.Request(self.base_url + "/run-stress", data=b"{}",
                                     headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=10)
            self.fail("expected 422")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 422)
            self.assertIn("stress_id required", e.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
