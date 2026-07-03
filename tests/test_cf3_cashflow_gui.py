"""CF-3 tests: cash-flow projection GUI page + data endpoint
(owner request 2026-07-03)."""

import json
import os
import sys
import tempfile
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_REPO, os.path.join(_REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from par_model_v2.viewer import igui_cashflows as G


def _model_inputs():
    return {
        "portfolio": [
            {"product_type": "HKCD_PAR_2026", "issue_age": "45",
             "gender": "M", "term_years": "20", "sum_assured": "100000",
             "annual_premium": "5000", "policy_count": "1000",
             "vested_bonus": "0"},
            {"product_type": "HKRB_PAR_2026", "issue_age": "40",
             "gender": "F", "term_years": "20", "sum_assured": "250000",
             "annual_premium": "9000", "policy_count": "500",
             "vested_bonus": "1200"},
        ],
        "balance_sheet": {"assets": [
            {"asset_class": "Government bonds", "market_value": "120000000"},
            {"asset_class": "Equity", "market_value": "30000000"},
        ]},
    }


def _write_inputs(td, mi=None):
    path = os.path.join(td, "model_inputs.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(mi or _model_inputs(), fh)
    return path


class TestBuildResponse(unittest.TestCase):
    def test_full_payload_shape(self):
        with tempfile.TemporaryDirectory() as td:
            res = G.build_cashflow_response(_write_inputs(td),
                                            os.path.join(td, "out"))
            self.assertTrue(res["ok"], res)
            self.assertFalse(res["cached"])
            self.assertIn("UNSIGNED", res["unsigned_note"])
            self.assertEqual(res["horizon"], {"months": 1200, "years": 100})
            for key in ("liability_yearly", "asset_cf_yearly",
                        "asset_balance_yearly", "liability_monthly",
                        "asset_cf_monthly", "asset_balance_monthly"):
                t = res["tables"][key]
                self.assertIn("columns", t)
                self.assertIn("rows", t)
            self.assertEqual(len(res["tables"]["liability_yearly"]["rows"]), 100)
            self.assertEqual(len(res["tables"]["liability_monthly"]["rows"]), 1200)
            self.assertEqual(res["tables"]["liability_yearly"]["columns"][0],
                             "year")
            self.assertIn("HKCD_PAR_2026__cash_dividend",
                          res["tables"]["liability_yearly"]["columns"])
            # charts
            lc = res["charts"]["liability"]
            self.assertEqual(len(lc["years"]), 100)
            for k in ("premium", "expense", "benefits", "net"):
                self.assertEqual(len(lc[k]), 100)
            bc = res["charts"]["balances"]
            self.assertEqual(set(bc["classes"]),
                             {"Government bonds", "Equity"})
            for c in bc["classes"]:
                self.assertEqual(len(bc["series"][c]), 100)
            # CSV artifacts refreshed alongside
            self.assertTrue(os.path.exists(os.path.join(
                res["csv_dir"], "liability_cashflows_yearly.csv")))

    def test_digest_cache_hit_and_invalidation(self):
        with tempfile.TemporaryDirectory() as td:
            inputs = _write_inputs(td)
            out = os.path.join(td, "out")
            r1 = G.build_cashflow_response(inputs, out)
            self.assertFalse(r1["cached"])
            r2 = G.build_cashflow_response(inputs, out)
            self.assertTrue(r2["cached"])
            self.assertEqual(r1["inputs_digest"], r2["inputs_digest"])
            mi = _model_inputs()
            mi["portfolio"][0]["sum_assured"] = "150000"
            _write_inputs(td, mi)
            r3 = G.build_cashflow_response(inputs, out)
            self.assertFalse(r3["cached"])
            self.assertNotEqual(r3["inputs_digest"], r1["inputs_digest"])

    def test_missing_and_bad_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            res = G.build_cashflow_response(
                os.path.join(td, "nope.json"), td)
            self.assertFalse(res["ok"])
            mi = _model_inputs()
            mi["portfolio"] = []
            res = G.build_cashflow_response(_write_inputs(td, mi), td)
            self.assertFalse(res["ok"])
            self.assertIn("portfolio", res["errors"][0])
            mi = _model_inputs()
            mi["balance_sheet"] = {"assets": []}
            res = G.build_cashflow_response(_write_inputs(td, mi), td)
            self.assertFalse(res["ok"])


class TestRenderHtml(unittest.TestCase):
    def test_page_self_contained(self):
        page = G.render_cashflows_html()
        for needle in ("Cash-flow projections", "/cashflow-data",
                       "UNSIGNED", "chart-liab", "chart-bal",
                       "Monthly (drill into one year)"):
            self.assertIn(needle, page)
        self.assertNotIn("https://", page.replace(
            "http://www.w3.org/2000/svg", ""))
        self.assertNotIn("cdn", page.lower())


class TestServerEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        import run_gui
        cls._tmp = tempfile.mkdtemp(prefix="igui_cf3_")
        cls.inputs = os.path.join(cls._tmp, "model_inputs.json")
        with open(cls.inputs, "w", encoding="utf-8") as fh:
            json.dump(_model_inputs(), fh)
        cls.srv = run_gui.make_server(0, cls.inputs)
        cls.host, cls.port = cls.srv.server_address
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.th.start()
        cls.base = "http://%s:%d" % (cls.host, cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def _get(self, path):
        import urllib.error
        import urllib.request
        try:
            with urllib.request.urlopen(self.base + path, timeout=60) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_page_served(self):
        status, page = self._get("/cashflows")
        self.assertEqual(status, 200)
        self.assertIn("Cash-flow projections", page)

    def test_data_endpoint(self):
        status, body = self._get("/cashflow-data")
        self.assertEqual(status, 200, body[:300])
        j = json.loads(body)
        self.assertTrue(j["ok"])
        self.assertEqual(len(j["tables"]["asset_balance_yearly"]["rows"]), 100)


if __name__ == "__main__":
    unittest.main()
