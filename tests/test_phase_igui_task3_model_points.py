"""Tests for Phase IGUI Task 3 - model points + in-force ingest.

Stdlib-only (unittest + urllib); does NOT import numpy/pandas/scipy or the
model orchestrator. Covers: model-point normalisation + row editing, the
balance-sheet reconciliation, the disclosed book-scaling preview, the in-force
CSV/JSON ingest, the loader round-trip validator (incl. rejection cases), the
self-contained page, the localhost runner's new endpoints, and the Task-3 gate.
"""

import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from par_model_v2.viewer.igui_model_points import (  # noqa: E402
    ALLOWED_GENDERS,
    ALLOWED_PRODUCT_TYPES,
    GOVERNED_HEADLINE,
    MODEL_POINT_FIELDS,
    SCHEMA_VERSION,
    UI_APP_SHA256,
    book_scaling_disclosure,
    default_balance_sheet,
    default_model_points,
    ingest_inforce,
    normalize_balance_sheet,
    normalize_model_points,
    portfolio_to_model_inputs,
    reconcile_balance_sheet,
    render_model_points_html,
    validate_task3_gate,
)
import load_user_inputs  # noqa: E402  (scripts/load_user_inputs.py)


class TestNormaliseRows(unittest.TestCase):
    def test_defaults_normalise_clean(self):
        rows, errs = normalize_model_points(default_model_points())
        self.assertEqual(errs, [])
        self.assertEqual(len(rows), 3)
        self.assertIsInstance(rows[0]["issue_age"], int)
        self.assertIsInstance(rows[0]["sum_assured"], float)

    def test_blank_scaffold_row_skipped(self):
        rows = default_model_points() + [{f["id"]: "" for f in MODEL_POINT_FIELDS}]
        typed, errs = normalize_model_points(rows)
        self.assertEqual(errs, [])
        self.assertEqual(len(typed), 3)  # the empty row is dropped

    def test_non_numeric_reported_with_row_and_field(self):
        rows = default_model_points()
        rows[1]["sum_assured"] = "lots"
        _, errs = normalize_model_points(rows)
        self.assertTrue(any("row 2" in e and "sum_assured" in e for e in errs))

    def test_comma_grouped_numbers_accepted(self):
        rows = default_model_points()
        rows[0]["sum_assured"] = "100,000"
        rows[0]["policy_count"] = "1,000"
        typed, errs = normalize_model_points(rows)
        self.assertEqual(errs, [])
        self.assertEqual(typed[0]["sum_assured"], 100000.0)
        self.assertEqual(typed[0]["policy_count"], 1000)

    def test_add_and_delete_semantics(self):
        # "edit" = mutate a row dict; "add"/"delete" = list ops the GUI performs
        rows = default_model_points()
        rows.append({"product_type": "HKCD_PAR_2026", "issue_age": "30",
                     "gender": "F", "term_years": "10", "sum_assured": "50000",
                     "annual_premium": "2000", "policy_count": "10",
                     "vested_bonus": "0"})
        typed, errs = normalize_model_points(rows)
        self.assertEqual(errs, [])
        self.assertEqual(len(typed), 4)
        del rows[0]
        typed2, _ = normalize_model_points(rows)
        self.assertEqual(len(typed2), 3)


class TestBalanceSheetReconcile(unittest.TestCase):
    def test_defaults_reconcile(self):
        bs, errs = normalize_balance_sheet(default_balance_sheet())
        self.assertEqual(errs, [])
        rec = reconcile_balance_sheet(bs)
        self.assertEqual(rec["sum_of_asset_rows"], 200000000.0)
        self.assertTrue(rec["reconciles"])
        self.assertAlmostEqual(rec["illiquid_share"], 20000000.0 / 200000000.0)

    def test_mismatch_detected(self):
        d = default_balance_sheet()
        d["stated_total_backing_asset_mv"] = "199000000"
        bs, _ = normalize_balance_sheet(d)
        rec = reconcile_balance_sheet(bs)
        self.assertFalse(rec["reconciles"])
        self.assertEqual(rec["difference"], -1000000.0)

    def test_illiquid_flags_parsed(self):
        bs, errs = normalize_balance_sheet(default_balance_sheet())
        self.assertEqual(errs, [])
        self.assertTrue(any(a["illiquid"] for a in bs["assets"]))
        self.assertTrue(any(not a["illiquid"] for a in bs["assets"]))


class TestBookScaling(unittest.TestCase):
    def test_par_only_gmmb_disclosed(self):
        rows, _ = normalize_model_points(default_model_points())
        bk = book_scaling_disclosure(rows)
        self.assertEqual(bk["par_rows"], 2)
        self.assertEqual(bk["gmmb_rows_disclosed"], 1)

    def test_weighted_representative_and_scale_factor(self):
        rows, _ = normalize_model_points(default_model_points())
        bk = book_scaling_disclosure(rows)["book_scaling"]
        # PAR rows: (100000 x1000) + (250000 x500) = 225,000,000 ; counts 1500
        self.assertEqual(bk["policy_count_total"], 1500.0)
        self.assertEqual(bk["sum_assured_total"], 225000000.0)
        self.assertAlmostEqual(bk["representative_sum_assured"], 225000000.0 / 1500.0)
        self.assertAlmostEqual(bk["linear_scale_factor"], 1500.0)


class TestIngest(unittest.TestCase):
    def test_csv_alias_mapping(self):
        text = ("Product,Age,Sex,Term,FaceValue,Premium,Count,Bonus\n"
                "HKCD_PAR_2026,45,M,20,100000,5000,1000,0\n"
                "HKRB_PAR_2026,40,F,25,250000,9000,500,1200\n")
        rows, errs = ingest_inforce(text, "auto")
        self.assertEqual(errs, [])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["product_type"], "HKCD_PAR_2026")
        self.assertEqual(rows[1]["sum_assured"], "250000")
        # round-trips through normalise + loader
        typed, nerr = normalize_model_points(rows)
        self.assertEqual(nerr, [])
        bs, _ = normalize_balance_sheet(default_balance_sheet())
        frag = portfolio_to_model_inputs(typed, bs)
        self.assertEqual(load_user_inputs.validate_portfolio_dict(frag), [])

    def test_json_list_and_gender_normalised(self):
        text = json.dumps([{"product_type": "gmmb", "age": 50, "sex": "female",
                            "term": 15, "sa": 300000, "premium": 12000,
                            "count": 250, "bonus": 0}])
        rows, errs = ingest_inforce(text, "auto")
        self.assertEqual(errs, [])
        self.assertEqual(rows[0]["product_type"], "GMMB_EQ_2026")
        self.assertEqual(rows[0]["gender"], "F")

    def test_json_portfolio_wrapper(self):
        text = json.dumps({"portfolio": [{"product_type": "HKCD_PAR_2026",
                                          "issue_age": 45, "gender": "M",
                                          "term_years": 20, "sum_assured": 100000,
                                          "annual_premium": 5000,
                                          "policy_count": 1000,
                                          "vested_bonus": 0}]})
        rows, errs = ingest_inforce(text, "auto")
        self.assertEqual(errs, [])
        self.assertEqual(len(rows), 1)

    def test_empty_and_unmappable_fail_loud(self):
        self.assertNotEqual(ingest_inforce("", "auto")[1], [])
        rows, errs = ingest_inforce("foo,bar\n1,2\n", "auto")
        self.assertNotEqual(errs, [])


class TestLoaderRoundTrip(unittest.TestCase):
    def test_defaults_pass_loader(self):
        rows, _ = normalize_model_points(default_model_points())
        bs, _ = normalize_balance_sheet(default_balance_sheet())
        frag = portfolio_to_model_inputs(rows, bs)
        self.assertEqual(load_user_inputs.validate_portfolio_dict(frag), [])
        self.assertEqual(frag["schema_version"], SCHEMA_VERSION)

    def test_bad_product_rejected(self):
        rows, _ = normalize_model_points(default_model_points())
        bs, _ = normalize_balance_sheet(default_balance_sheet())
        frag = portfolio_to_model_inputs(rows, bs)
        frag["portfolio"][0]["product_type"] = "NOT_A_PRODUCT"
        errs = load_user_inputs.validate_portfolio_dict(frag)
        self.assertTrue(any("Product type" in e for e in errs))

    def test_cash_dividend_with_bonus_rejected(self):
        rows, _ = normalize_model_points(default_model_points())
        bs, _ = normalize_balance_sheet(default_balance_sheet())
        frag = portfolio_to_model_inputs(rows, bs)
        frag["portfolio"][0]["vested_bonus"] = 999.0  # cash-dividend row
        errs = load_user_inputs.validate_portfolio_dict(frag)
        self.assertTrue(any("vested reversionary bonus" in e for e in errs))

    def test_only_gmmb_rejected(self):
        rows, _ = normalize_model_points([default_model_points()[2]])  # GMMB only
        bs, _ = normalize_balance_sheet(default_balance_sheet())
        frag = portfolio_to_model_inputs(rows, bs)
        errs = load_user_inputs.validate_portfolio_dict(frag)
        self.assertTrue(any("at least one PAR" in e for e in errs))

    def test_balance_sheet_mismatch_rejected(self):
        rows, _ = normalize_model_points(default_model_points())
        d = default_balance_sheet()
        d["stated_total_backing_asset_mv"] = "123456789"
        bs, _ = normalize_balance_sheet(d)
        frag = portfolio_to_model_inputs(rows, bs)
        errs = load_user_inputs.validate_portfolio_dict(frag)
        self.assertTrue(any("does not match the sum of asset rows" in e for e in errs))

    def test_enums_lockstep_with_loader(self):
        self.assertEqual(ALLOWED_PRODUCT_TYPES, load_user_inputs.ALLOWED_PRODUCT_TYPES)
        self.assertEqual(ALLOWED_GENDERS, load_user_inputs.ALLOWED_GENDERS)
        self.assertEqual(SCHEMA_VERSION, load_user_inputs.SCHEMA_VERSION)


class TestPageAndGate(unittest.TestCase):
    def test_self_contained_page(self):
        page = render_model_points_html()
        self.assertIn(GOVERNED_HEADLINE, page)
        self.assertEqual(len(__import__("re").findall(r'(?:src|href)="(?:https?:)?//', page)), 0)
        for ep in ("/validate_portfolio", "/save_portfolio", "/ingest", "/reconcile"):
            self.assertIn(ep, page)

    def test_ui_app_byte_unchanged(self):
        import hashlib
        with open(os.path.join(REPO, "ui_app.html"), "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), UI_APP_SHA256)

    def test_gate_green(self):
        r = validate_task3_gate(REPO)
        self.assertTrue(r["ok"], [k for k, v in r["checks"].items() if not v])
        self.assertGreaterEqual(r["n_checks"], 28)


class TestLocalhostRunner(unittest.TestCase):
    def test_endpoints_round_trip(self):
        import threading
        import urllib.request
        import tempfile
        import run_gui
        tmp = os.path.join(tempfile.mkdtemp(prefix="igui3_"), "model_inputs.json")
        srv = run_gui.make_server(0, tmp)
        host, port = srv.server_address
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            base = "http://%s:%d" % (host, port)
            with urllib.request.urlopen(base + "/model-points", timeout=5) as r:
                self.assertEqual(r.status, 200)
            body = json.dumps({"portfolio": default_model_points(),
                               "balance_sheet": default_balance_sheet()}).encode()
            req = urllib.request.Request(base + "/save_portfolio", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                j = json.loads(r.read().decode())
            self.assertTrue(j["ok"])
            with open(tmp) as fh:
                saved = json.load(fh)
            self.assertIn("portfolio", saved)
            self.assertIn("balance_sheet", saved)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
