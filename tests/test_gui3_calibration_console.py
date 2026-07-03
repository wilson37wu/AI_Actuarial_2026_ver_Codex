"""GUI-3 tests: calibration catalogue, market-data status, runs, endpoints
(Roadmap 4.0, owner directive 2026-07-03)."""

import json
import os
import sys
import tempfile
import time
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_REPO, os.path.join(_REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from par_model_v2.viewer import igui_calibration as C

_STORE_PATH = os.path.join(_REPO, ".claude-dev", "GOVERNANCE_STORE.json")


def _store_bytes():
    if not os.path.exists(_STORE_PATH):
        return None
    with open(_STORE_PATH, "rb") as fh:
        return fh.read()


class TestCatalogue(unittest.TestCase):
    def test_shape_and_ids(self):
        cat = C.calibration_catalogue()
        self.assertEqual(len(cat), len(C.CALIBRATION_CATALOGUE))
        ids = {c["id"] for c in cat}
        self.assertEqual(ids, {"CAL_HW1F_SWAPTION", "CAL_GBM_EQUITY"})
        for c in cat:
            for key in ("id", "label", "model", "description", "available",
                        "unsigned"):
                self.assertIn(key, c)
            self.assertTrue(c["unsigned"])  # always UNSIGNED by construction

    def test_availability_matches_engine_probe(self):
        ok, _ = C._engine_available()
        self.assertTrue(all(c["available"] == ok
                            for c in C.calibration_catalogue()))

    def test_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            C._find("NOPE")


@unittest.skipUnless(C._engine_available()[0], "engine deps missing")
class TestMarketDataStatus(unittest.TestCase):
    def test_both_datasets_resolve_with_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            st = C.market_data_status(cache_dir=td)
        self.assertTrue(st["ok"], st)
        self.assertFalse(st["live_source_configured"])
        by_name = {d["dataset"]: d for d in st["datasets"]}
        self.assertEqual(set(by_name), {"cny_yield_curve", "csi300_index"})
        for d in by_name.values():
            self.assertTrue(d["ok"], d)
            self.assertIn(d["provenance"], ("file_fixture", "cached_snapshot",
                                            "live_fetch"))
            self.assertEqual(len(d["sha256"]), 64)
            self.assertGreater(d["rows"], 0)
            # no owner-approved live source -> never presented as signed
            self.assertTrue(d["unsigned"], d)

    def test_engine_unavailable_degrades(self):
        orig = C._engine_available
        C._engine_available = lambda: (False, "forced-off")
        try:
            st = C.market_data_status()
            self.assertFalse(st["ok"])
            self.assertIn("forced-off", st["error"])
        finally:
            C._engine_available = orig


@unittest.skipUnless(C._engine_available()[0], "engine deps missing")
class TestRunCalibration(unittest.TestCase):
    def test_hw1f_end_to_end_unsigned_isolated(self):
        before = _store_bytes()
        with tempfile.TemporaryDirectory() as td:
            res = C.run_calibration("CAL_HW1F_SWAPTION", td,
                                    cache_dir=os.path.join(td, "cache"))
            self.assertTrue(res["ok"], res)
            self.assertTrue(res["unsigned"])
            self.assertEqual(res["unsigned_reason"], C.UNSIGNED_REASON)
            self.assertFalse(res["governance"]["repo_store_touched"])
            # per-market parameter card + fit diagnostics
            markets = {m["market"]: m for m in res["markets"]}
            self.assertEqual(set(markets), {"CNY", "HKD"})
            for m in markets.values():
                for pkey in ("a", "sigma_r", "r0"):
                    self.assertIn(pkey, m["parameters"])
                diag = m["diagnostics"]
                for dkey in ("rmse_bps", "sse_proxy_bps2",
                             "max_abs_error_bps", "converged", "lineage"):
                    self.assertIn(dkey, diag)
                if diag["rmse_bps"] is not None:
                    self.assertAlmostEqual(diag["sse_proxy_bps2"],
                                           float(diag["rmse_bps"]) ** 2)
            self.assertIn("G-02", res["gates"])
            self.assertIn("G-12", res["gates"])
            # isolated artifacts persisted + re-parseable
            self.assertTrue(res["diagnostics_path"].startswith(
                os.path.join(td, "calibration_CAL_HW1F_SWAPTION")))
            with open(res["diagnostics_path"], encoding="utf-8") as fh:
                on_disk = json.load(fh)
            self.assertEqual(on_disk["calibration_id"], "CAL_HW1F_SWAPTION")
            self.assertTrue(on_disk["unsigned"])
            self.assertTrue(os.path.exists(os.path.join(
                td, "calibration_CAL_HW1F_SWAPTION", "CALIBRATION_REPORT.md")))
        # the repository governance store is byte-identical after the run
        self.assertEqual(before, _store_bytes())

    def test_gbm_end_to_end_unsigned(self):
        before = _store_bytes()
        with tempfile.TemporaryDirectory() as td:
            res = C.run_calibration("CAL_GBM_EQUITY", td,
                                    cache_dir=os.path.join(td, "cache"))
            self.assertTrue(res["ok"], res)
            self.assertTrue(res["unsigned"])
            markets = {m["market"]: m for m in res["markets"]}
            self.assertEqual(set(markets), {"CNY", "HK"})  # phase14 MARKETS
            for m in markets.values():
                for pkey in ("sigma_S", "erp", "dividend_yield", "rho"):
                    self.assertIn(pkey, m["parameters"])
                self.assertGreater(m["diagnostics"]["n_daily_obs"], 0)
            self.assertIn("G-03", res["gates"])
        self.assertEqual(before, _store_bytes())

    def test_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            C.run_calibration("NOPE", tempfile.gettempdir())

    def test_engine_unavailable_refuses(self):
        orig = C._engine_available
        C._engine_available = lambda: (False, "forced-off")
        try:
            with tempfile.TemporaryDirectory() as td:
                res = C.run_calibration("CAL_HW1F_SWAPTION", td)
            self.assertFalse(res["ok"])
            self.assertIn("forced-off", res["errors"][0])
        finally:
            C._engine_available = orig


class TestRenderHtml(unittest.TestCase):
    def test_page_self_contained_and_unsigned(self):
        page = C.render_calibration_html()
        for needle in ("Calibration console", "UNSIGNED",
                       "/calibration-catalogue", "/market-data-status",
                       "/run-calibration", "/jobs/"):
            self.assertIn(needle, page)
        self.assertNotIn("http://", page.replace("http://127.0.0.1", ""))
        self.assertNotIn("https://", page)  # zero external references


@unittest.skipUnless(C._engine_available()[0], "engine deps missing")
class TestServerEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        import run_gui
        cls._tmp = tempfile.mkdtemp(prefix="igui3_")
        cls.srv = run_gui.make_server(
            0, os.path.join(cls._tmp, "model_inputs.json"))
        cls.host, cls.port = cls.srv.server_address
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.th.start()
        cls.base = "http://%s:%d" % (cls.host, cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def _get(self, path):
        import urllib.request
        with urllib.request.urlopen(self.base + path, timeout=30) as r:
            return r.status, r.read().decode("utf-8")

    def _post(self, path, body):
        import urllib.error
        import urllib.request
        req = urllib.request.Request(
            self.base + path, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_console_page_served(self):
        status, page = self._get("/calibration")
        self.assertEqual(status, 200)
        self.assertIn("Calibration console", page)
        self.assertIn("UNSIGNED", page)

    def test_catalogue_and_market_data_endpoints(self):
        status, body = self._get("/calibration-catalogue")
        self.assertEqual(status, 200)
        j = json.loads(body)
        self.assertTrue(j["ok"])
        self.assertEqual({c["id"] for c in j["catalogue"]},
                         {"CAL_HW1F_SWAPTION", "CAL_GBM_EQUITY"})
        status, body = self._get("/market-data-status")
        self.assertEqual(status, 200)
        j = json.loads(body)
        self.assertIn("datasets", j)

    def test_run_calibration_requires_id(self):
        status, j = self._post("/run-calibration", {})
        self.assertEqual(status, 422)
        self.assertFalse(j["ok"])

    def test_run_calibration_job_roundtrip(self):
        status, j = self._post("/run-calibration",
                               {"calibration_id": "CAL_GBM_EQUITY"})
        self.assertEqual(status, 200)
        self.assertTrue(j["ok"], j)
        job_id = j["job_id"]
        deadline = time.time() + 300
        state = None
        while time.time() < deadline:
            _, body = self._get("/jobs/" + job_id)
            snap = json.loads(body)
            state = snap.get("state")
            if state in ("succeeded", "failed"):
                break
            time.sleep(1.0)
        self.assertEqual(state, "succeeded", snap)
        self.assertEqual(snap["meta"]["kind"], "calibration")
        result = snap["result"]
        self.assertTrue(result["unsigned"])
        self.assertEqual(result["calibration_id"], "CAL_GBM_EQUITY")
        self.assertTrue(result["markets"])


if __name__ == "__main__":
    unittest.main()
