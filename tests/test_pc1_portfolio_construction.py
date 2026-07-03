"""PC-1 tests: flexible portfolio construction - asset SAA, product
catalogue, composer, engine integration, GUI endpoints
(owner directive 2026-07-03)."""

import json
import os
import sys
import tempfile
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_REPO, os.path.join(_REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from par_model_v2.projection import portfolio_construction as PC


class TestAssetStrategyValidation(unittest.TestCase):
    def test_default_is_valid(self):
        self.assertEqual(PC.validate_asset_strategy(
            PC.default_asset_strategy()), [])

    def test_weights_must_sum_to_one(self):
        st = PC.default_asset_strategy()
        st["saa"][0]["weight"] = 0.99
        errs = PC.validate_asset_strategy(st)
        self.assertTrue(any("sum to 1.0" in e for e in errs))

    def test_kind_params_and_bounds(self):
        st = PC.default_asset_strategy()
        st["saa"][0]["kind"] = "spaceship"
        errs = PC.validate_asset_strategy(st)
        self.assertTrue(any("kind" in e for e in errs))
        st = PC.default_asset_strategy()
        st["saa"][0]["annual_yield"] = 0.9  # > 50% bound
        errs = PC.validate_asset_strategy(st)
        self.assertTrue(any("annual_yield" in e for e in errs))

    def test_duplicate_class_and_bad_total(self):
        st = PC.default_asset_strategy()
        st["saa"][1]["asset_class"] = st["saa"][0]["asset_class"]
        self.assertTrue(any("duplicate" in e for e in
                            PC.validate_asset_strategy(st)))
        st = PC.default_asset_strategy()
        st["total_market_value"] = -5
        self.assertTrue(any("total market value" in e for e in
                            PC.validate_asset_strategy(st)))


class TestCatalogueValidation(unittest.TestCase):
    def test_default_is_valid(self):
        self.assertEqual(PC.validate_product_catalogue(
            PC.default_product_catalogue()), [])

    def test_duplicate_id_family_and_ranges(self):
        cat = PC.default_product_catalogue()
        cat[1]["product_id"] = cat[0]["product_id"]
        self.assertTrue(any("duplicate" in e for e in
                            PC.validate_product_catalogue(cat)))
        cat = PC.default_product_catalogue()
        cat[0]["family"] = "NOPE"
        self.assertTrue(any("family" in e for e in
                            PC.validate_product_catalogue(cat)))
        cat = PC.default_product_catalogue()
        cat[0]["term_years_max"] = 1  # < min
        self.assertTrue(any("term range" in e for e in
                            PC.validate_product_catalogue(cat)))
        cat = PC.default_product_catalogue()
        cat[0]["cash_dividend_rate"] = 0.5  # > 20% bound
        self.assertTrue(any("cash_dividend_rate" in e for e in
                            PC.validate_product_catalogue(cat)))


class TestComposerValidation(unittest.TestCase):
    def _rows(self):
        return [{"product_id": "PAR_CD_SHORT", "issue_age": 40,
                 "gender": "M", "term_years": 10, "sum_assured": 80000,
                 "annual_premium": 6000, "policy_count": 800,
                 "vested_bonus": 0}]

    def test_ok_and_term_range_enforced(self):
        cat = PC.default_product_catalogue()
        self.assertEqual(PC.validate_composed_portfolio(self._rows(), cat), [])
        rows = self._rows()
        rows[0]["term_years"] = 30  # PAR_CD_SHORT allows 5..10
        errs = PC.validate_composed_portfolio(rows, cat)
        self.assertTrue(any("outside the product's range" in e for e in errs))

    def test_unknown_product_and_cd_vested_bonus(self):
        cat = PC.default_product_catalogue()
        rows = self._rows()
        rows[0]["product_id"] = "GHOST"
        self.assertTrue(any("unknown product_id" in e for e in
                            PC.validate_composed_portfolio(rows, cat)))
        rows = self._rows()
        rows[0]["vested_bonus"] = 500
        self.assertTrue(any("vested reversionary bonus" in e for e in
                            PC.validate_composed_portfolio(rows, cat)))


class TestDerivations(unittest.TestCase):
    def test_balance_sheet_from_saa(self):
        bs = PC.derive_balance_sheet(PC.default_asset_strategy())
        total = sum(a["market_value"] for a in bs["assets"])
        self.assertAlmostEqual(total, 200_000_000.0, places=2)
        self.assertAlmostEqual(bs["stated_total_backing_asset_mv"], total)
        by = {a["asset_class"]: a for a in bs["assets"]}
        self.assertAlmostEqual(by["Government bonds"]["market_value"], 80e6)
        self.assertTrue(by["Private credit"]["illiquid"])
        # loader scalar fields present
        for k in ("forced_sale_fraction", "best_estimate_liability",
                  "equity_guarantee_initial_index"):
            self.assertIn(k, bs)

    def test_existing_scalars_preserved(self):
        bs0 = {"forced_sale_fraction": 0.35,
               "best_estimate_liability": 123.0,
               "equity_guarantee_initial_index": 99.0}
        bs = PC.derive_balance_sheet(PC.default_asset_strategy(), bs0)
        self.assertEqual(bs["forced_sale_fraction"], 0.35)
        self.assertEqual(bs["best_estimate_liability"], 123.0)

    def test_mechanics_from_strategy(self):
        mechs = PC.asset_mechanics_from_strategy(PC.default_asset_strategy())
        self.assertEqual(mechs["Equity"]["kind"], "equity")
        self.assertAlmostEqual(mechs["Government bonds"]["annual_yield"], 0.032)

    def test_resolve_portfolio(self):
        cat = PC.default_product_catalogue()
        rows = [{"product_id": "PAR_RB_LONG", "term_years": 25},
                {"product_type": "HKCD_PAR_2026", "term_years": 20}]  # legacy
        out = PC.resolve_portfolio(rows, cat)
        self.assertEqual(out[0]["product_type"], "HKRB_PAR_2026")
        self.assertAlmostEqual(out[0]["mechanics"]["rb_rate"], 0.025)
        self.assertNotIn("mechanics", out[1])  # legacy passthrough


class TestEngineIntegration(unittest.TestCase):
    def _mi(self):
        return {
            "asset_strategy": PC.default_asset_strategy(),
            "product_catalogue": PC.default_product_catalogue(),
            "portfolio": [
                {"product_id": "PAR_CD_SHORT",
                 "product_type": "HKCD_PAR_2026", "issue_age": 40,
                 "gender": "M", "term_years": 10, "sum_assured": 80000,
                 "annual_premium": 6000, "policy_count": 800,
                 "vested_bonus": 0},
                {"product_id": "PAR_CD_LONG",
                 "product_type": "HKCD_PAR_2026", "issue_age": 45,
                 "gender": "M", "term_years": 20, "sum_assured": 100000,
                 "annual_premium": 5000, "policy_count": 1000,
                 "vested_bonus": 0},
            ],
            "balance_sheet": PC.derive_balance_sheet(
                PC.default_asset_strategy()),
        }

    def test_products_report_separately_with_their_own_rates(self):
        from par_model_v2.projection.cashflow_projection_set import (
            build_cashflow_projection_set)
        res = build_cashflow_projection_set(self._mi())
        # short and long CD products are distinct output classes
        self.assertEqual(set(res["product_classes"]),
                         {"PAR_CD_SHORT", "PAR_CD_LONG"})
        liab = res["frames"]["liability_monthly"]
        short = liab[liab["product_class"] == "PAR_CD_SHORT"]
        # short product ends at 120 months
        self.assertAlmostEqual(float(short["premium"][120:].sum()), 0.0)
        # catalogue rate flows through: anniversary dividends land at
        # months 13, 25, ... (dividend rate x SA x count x in-force)
        m13 = float(short[short["month"] == 13]["cash_dividend"].iloc[0])
        self.assertGreater(m13, 0.0)
        long_ = liab[liab["product_class"] == "PAR_CD_LONG"]
        m13_long = float(long_[long_["month"] == 13]["cash_dividend"].iloc[0])
        # 1.5% (short) vs 1.2% (long) per-policy dividend rates show through
        # after scaling out SA x count (in-force decay is second-order here)
        self.assertGreater(m13 / (80000 * 800), m13_long / (100000 * 1000))

    def test_saa_mechanics_drive_asset_classes(self):
        from par_model_v2.projection.cashflow_projection_set import (
            build_cashflow_projection_set)
        mi = self._mi()
        mi["asset_strategy"]["saa"][0]["annual_yield"] = 0.10  # govt 10%
        res = build_cashflow_projection_set(mi)
        acf = res["frames"]["asset_cf_monthly"]
        g1 = float(acf[(acf["asset_class"] == "Government bonds")
                       & (acf["month"] == 1)]["investment_income"].iloc[0])
        self.assertAlmostEqual(g1, 80e6 * 0.10 / 12.0, delta=1.0)
        self.assertEqual(set(res["asset_classes"]),
                         {"Government bonds", "Corporate bonds",
                          "Private credit", "Equity", "Cash"})


class TestGuiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        import run_gui
        cls._tmp = tempfile.mkdtemp(prefix="igui_pc1_")
        cls.inputs = os.path.join(cls._tmp, "model_inputs.json")
        cls.srv = run_gui.make_server(0, cls.inputs)
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
            return r.status, json.loads(r.read().decode("utf-8"))

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

    def test_page_and_defaults(self):
        import urllib.request
        with urllib.request.urlopen(self.base + "/portfolio", timeout=30) as r:
            page = r.read().decode("utf-8")
        self.assertIn("Portfolio construction", page)
        status, j = self._get("/portfolio-defaults")
        self.assertEqual(status, 200)
        self.assertTrue(j["ok"])
        self.assertEqual(len(j["asset_strategy"]["saa"]), 5)
        self.assertEqual(len(j["product_catalogue"]), 4)
        self.assertIn("HKCD_PAR_2026", j["families"])

    def test_validate_save_roundtrip_and_gate_reset(self):
        from par_model_v2.viewer.igui_portfolio_builder import (
            default_composed_portfolio)
        body = {"asset_strategy": PC.default_asset_strategy(),
                "product_catalogue": PC.default_product_catalogue(),
                "portfolio": default_composed_portfolio()}
        status, j = self._post("/validate_construction", body)
        self.assertEqual(status, 200, j)
        self.assertTrue(j["ok"], j)
        self.assertNotIn("written", j)
        # seed a stale gate to prove save clears it
        with open(self.inputs, "w", encoding="utf-8") as fh:
            json.dump({"run_gate": {"decision": "CLEARED"}}, fh)
        status, j = self._post("/save_construction", body)
        self.assertEqual(status, 200, j)
        self.assertTrue(j["ok"], j)
        with open(self.inputs, encoding="utf-8") as fh:
            mi = json.load(fh)
        for key in ("asset_strategy", "product_catalogue", "portfolio",
                    "balance_sheet"):
            self.assertIn(key, mi)
        self.assertNotIn("run_gate", mi)  # inputs changed -> gate reset
        # every saved row is loader-valid (governed contract)
        import load_user_inputs as loader
        self.assertEqual(loader.validate_portfolio_dict(
            {"portfolio": mi["portfolio"],
             "balance_sheet": mi["balance_sheet"]}), [])
        self.assertTrue(all(r.get("product_id") for r in mi["portfolio"]))

    def test_invalid_construction_422(self):
        st = PC.default_asset_strategy()
        st["saa"][0]["weight"] = 0.7  # breaks the sum
        status, j = self._post("/validate_construction", {
            "asset_strategy": st,
            "product_catalogue": PC.default_product_catalogue(),
            "portfolio": []})
        self.assertEqual(status, 422)
        self.assertFalse(j["ok"])


if __name__ == "__main__":
    unittest.main()
