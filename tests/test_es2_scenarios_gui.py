"""ES-2 - user economic-scenario GUI upload page tests.

Covers: upload validation via the REAL ES-1 loader (row/column errors
surfaced structured), percentile fan-chart preview payload, digest-keyed
persistence + the ``user_scenarios`` block in model_inputs.json, run-gate
reset on save, /scenario-status digest re-verification (stale detection),
the preview cache, live HTTP round-trips over the run_gui server, and the
GUI-layer stdlib-only import contract.
"""
from __future__ import annotations

import csv as _csv
import io
import json
import os
import re
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

from par_model_v2.stochastic.user_scenarios import (
    EXPECTED_HEADER, MIN_SCENARIOS, PROJECTION_YEARS, SCHEMA_ID,
    TENOR_LABELS, compute_csv_sha256)
from par_model_v2.viewer.igui_scenarios import (
    PREVIEW_CACHE_NAME, SCN_GUI_SCHEMA_VERSION,
    build_scenario_save_response, build_scenario_status_response,
    build_scenario_validate_response, render_scenarios_html)

N_SCEN = MIN_SCENARIOS  # 100 x 100 = 10,000 rows - fast


def _rates_for(scen, year):
    base = 0.02 + 0.00005 * (scen % 7) + 0.00002 * (year % 11)
    return [round(base + 0.001 * i, 6) for i in range(len(TENOR_LABELS))]


def _eq_for(scen, year):
    return round(0.06 + 0.01 * ((scen + year) % 5) - 0.02 * (scen % 3), 6)


def _csv_text(n_scen=N_SCEN, mutate=None):
    rows = []
    for s in range(1, n_scen + 1):
        for y in range(1, PROJECTION_YEARS + 1):
            rows.append([s, y] + _rates_for(s, y) + [_eq_for(s, y)])
    if mutate is not None:
        mutate(rows)
    buf = io.StringIO()
    w = _csv.writer(buf, lineterminator="\n")
    w.writerow(EXPECTED_HEADER)
    w.writerows(rows)
    return buf.getvalue()


def _manifest_text(csv_text, n_scen=N_SCEN, override=None):
    with tempfile.NamedTemporaryFile("wb", suffix=".csv",
                                     delete=False) as fh:
        fh.write(csv_text.encode("utf-8"))
        tmp = fh.name
    try:
        sha = compute_csv_sha256(tmp)
    finally:
        os.unlink(tmp)
    manifest = {
        "schema": SCHEMA_ID,
        "n_scenarios": n_scen,
        "projection_years": PROJECTION_YEARS,
        "basis": "risk_neutral",
        "rate_convention": {"type": "zero_coupon_spot",
                            "compounding": "annual", "units": "decimal",
                            "day_count": "ACT/365F"},
        "equity_convention": {"type": "annual_total_return",
                              "units": "decimal"},
        "currency": "CNY",
        "source": "pytest synthetic ESG v1 (2026-07-08)",
        "created_utc": "2026-07-08T00:00:00Z",
        "csv_sha256": sha,
    }
    if override:
        manifest.update(override)
    return json.dumps(manifest)


def _valid_payload():
    c = _csv_text()
    return {"csv_text": c, "manifest_text": _manifest_text(c)}


# ------------------------------------------------------------- validation

class TestValidate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = build_scenario_validate_response(_valid_payload())

    def test_valid_pair_ok(self):
        self.assertTrue(self.res["ok"])
        self.assertEqual(self.res["stage"], "validated")
        self.assertEqual(self.res["schema"], SCN_GUI_SCHEMA_VERSION)
        self.assertEqual(self.res["n_scenarios"], N_SCEN)
        self.assertTrue(self.res["unsigned"])
        self.assertIn("UNSIGNED", self.res["unsigned_banner"])

    def test_fan_payload_shape(self):
        self.assertEqual(self.res["years"], list(range(1, 101)))
        fans = self.res["fans"]
        ids = {s["id"] for s in self.res["series"]}
        # 12 tenors + eq_return + cumulative index
        self.assertEqual(len(ids), len(TENOR_LABELS) + 2)
        for key in ids:
            self.assertIn(key, fans)
            for p in ("p5", "p25", "p50", "p75", "p95"):
                self.assertEqual(len(fans[key][p]), PROJECTION_YEARS)
        # percentile ordering holds everywhere on the 10Y fan
        f = fans["rate_10Y"]
        for i in range(PROJECTION_YEARS):
            self.assertLessEqual(f["p5"][i], f["p50"][i])
            self.assertLessEqual(f["p50"][i], f["p95"][i])

    def test_summary_card_and_cross_warning(self):
        card = self.res["summary_card"]
        self.assertEqual(card["n_scenarios"], N_SCEN)
        self.assertIn("1", card["by_projection_year"])
        self.assertIn("100", card["by_projection_year"])
        # 100 < 2000 -> C-ROSS advisory warning must surface on the page
        self.assertTrue(any("C-ROSS" in w for w in self.res["warnings"]))

    def test_missing_files_reported(self):
        res = build_scenario_validate_response({})
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "upload")
        msgs = " ".join(e["message"] for e in res["errors"])
        self.assertIn("CSV missing", msgs)
        self.assertIn("manifest missing", msgs)

    def test_row_column_surfaced_on_bad_cell(self):
        def mutate(rows):
            rows[204][10] = 0.95    # 10Y col, out of [-0.05, 0.30]
        c = _csv_text(mutate=mutate)
        res = build_scenario_validate_response(
            {"csv_text": c, "manifest_text": _manifest_text(c)})
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "validation")
        e = res["errors"][0]
        self.assertEqual(e["row"], 206)          # header + 1-based data row
        self.assertEqual(e["column"], "10Y")
        self.assertIn("plausibility", e["message"])
        self.assertEqual(res["n_errors"], 1)

    def test_manifest_digest_mismatch_reported(self):
        c = _csv_text()
        res = build_scenario_validate_response(
            {"csv_text": c,
             "manifest_text": _manifest_text(c, override={
                 "csv_sha256": "0" * 64})})
        self.assertFalse(res["ok"])
        self.assertTrue(any(e["column"] == "csv_sha256"
                            for e in res["errors"]))


# ---------------------------------------------------------------- persist

class TestSaveAndStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="es2_")
        self.out_path = os.path.join(self.tmp, "model_inputs.json")
        self.store_root = os.path.join(self.tmp, "user_scenarios")

    def test_save_persists_block_and_resets_gate(self):
        # pre-seed a cleared gate: saving new scenario inputs must reset it
        with open(self.out_path, "w", encoding="utf-8") as fh:
            json.dump({"schema_version": "1.0.0",
                       "run_gate": {"decision": "CLEARED"}}, fh)
        res = build_scenario_save_response(
            _valid_payload(), self.out_path, self.store_root)
        self.assertTrue(res["ok"])
        self.assertEqual(res["stage"], "saved")
        self.assertTrue(res["gate_reset"])
        digest = res["csv_sha256"]
        store_dir = os.path.join(self.store_root, digest[:12])
        self.assertEqual(os.path.abspath(store_dir),
                         res["store_dir"])
        csv_path = os.path.join(store_dir, "economic_scenarios.csv")
        self.assertTrue(os.path.isfile(csv_path))
        self.assertTrue(os.path.isfile(
            os.path.join(store_dir, "economic_scenarios_manifest.json")))
        self.assertEqual(compute_csv_sha256(csv_path), digest)
        self.assertTrue(os.path.isfile(
            os.path.join(store_dir, PREVIEW_CACHE_NAME)))
        with open(self.out_path, encoding="utf-8") as fh:
            mi = json.load(fh)
        self.assertNotIn("run_gate", mi)           # gate RESET
        blk = mi["user_scenarios"]
        self.assertEqual(blk["schema"], SCHEMA_ID)
        self.assertEqual(blk["csv_sha256"], digest)
        self.assertEqual(blk["basis"], "risk_neutral")
        self.assertEqual(blk["n_scenarios"], N_SCEN)
        self.assertTrue(blk["unsigned"])
        self.assertEqual(blk["csv_path"], os.path.abspath(csv_path))

    def test_invalid_pair_never_persists(self):
        def mutate(rows):
            rows[0][14] = 99.0     # EQ_RETURN out of bounds
        c = _csv_text(mutate=mutate)
        res = build_scenario_save_response(
            {"csv_text": c, "manifest_text": _manifest_text(c)},
            self.out_path, self.store_root)
        self.assertFalse(res["ok"])
        self.assertFalse(os.path.exists(self.store_root))
        self.assertFalse(os.path.exists(self.out_path))

    def test_status_roundtrip_served_from_cache(self):
        build_scenario_save_response(
            _valid_payload(), self.out_path, self.store_root)
        st = build_scenario_status_response(self.out_path)
        self.assertTrue(st["ok"])
        self.assertTrue(st["present"])
        self.assertFalse(st["stale"])
        self.assertTrue(st["cached"])              # preview cache hit
        self.assertEqual(st["schema"], SCN_GUI_SCHEMA_VERSION)
        self.assertIn("rate_10Y", st["fans"])

    def test_status_rebuilds_preview_without_cache(self):
        res = build_scenario_save_response(
            _valid_payload(), self.out_path, self.store_root)
        os.unlink(os.path.join(self.store_root, res["csv_sha256"][:12],
                               PREVIEW_CACHE_NAME))
        st = build_scenario_status_response(self.out_path)
        self.assertTrue(st["ok"])
        self.assertFalse(st["cached"])
        self.assertIn("rate_10Y", st["fans"])

    def test_status_flags_tampered_file_stale(self):
        res = build_scenario_save_response(
            _valid_payload(), self.out_path, self.store_root)
        csv_path = os.path.join(self.store_root, res["csv_sha256"][:12],
                                "economic_scenarios.csv")
        with open(csv_path, "a", encoding="utf-8") as fh:
            fh.write("tampered\n")
        st = build_scenario_status_response(self.out_path)
        self.assertFalse(st["ok"])
        self.assertTrue(st["stale"])
        self.assertTrue(any("no longer matches" in e["message"]
                            for e in st["errors"]))

    def test_status_flags_missing_file_stale(self):
        res = build_scenario_save_response(
            _valid_payload(), self.out_path, self.store_root)
        os.unlink(os.path.join(self.store_root, res["csv_sha256"][:12],
                               "economic_scenarios.csv"))
        st = build_scenario_status_response(self.out_path)
        self.assertFalse(st["ok"])
        self.assertTrue(st["stale"])

    def test_status_no_set_yet(self):
        st = build_scenario_status_response(self.out_path)
        self.assertTrue(st["ok"])
        self.assertFalse(st["present"])

    def test_identical_upload_shares_one_store_copy(self):
        p = _valid_payload()
        r1 = build_scenario_save_response(p, self.out_path, self.store_root)
        r2 = build_scenario_save_response(p, self.out_path, self.store_root)
        self.assertEqual(r1["store_dir"], r2["store_dir"])
        self.assertEqual(len(os.listdir(self.store_root)), 1)


# ------------------------------------------------------------ page + HTTP

class TestPageAndServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import run_gui
        cls.run_gui = run_gui
        cls.tmp = tempfile.mkdtemp(prefix="es2http_")
        cls.out_path = os.path.join(cls.tmp, "model_inputs.json")
        cls.srv = run_gui.make_server(0, cls.out_path)
        host, port = cls.srv.server_address
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = "http://%s:%d" % (host, port)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def _post(self, route, obj):
        body = json.dumps(obj).encode("utf-8")
        req = urllib.request.Request(
            self.base + route, data=body,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_page_served_with_nav_and_banner(self):
        with urllib.request.urlopen(self.base + "/scenarios",
                                    timeout=15) as r:
            html = r.read().decode("utf-8")
        self.assertEqual(r.status, 200)
        self.assertIn("User economic scenarios", html)
        self.assertIn("UNSIGNED", html)
        self.assertIn("esg-user-scenarios-1.0", html)
        self.assertEqual(html.count("<nav "), 1)
        self.assertIn('href="/scenarios"', html)

    def test_http_validate_save_status_roundtrip(self):
        code, res = self._post("/validate-scenarios", _valid_payload())
        self.assertEqual(code, 200)
        self.assertTrue(res["ok"])
        code, res = self._post("/save-scenarios", _valid_payload())
        self.assertEqual(code, 200)
        self.assertTrue(res["ok"])
        with urllib.request.urlopen(self.base + "/scenario-status",
                                    timeout=60) as r:
            st = json.loads(r.read().decode("utf-8"))
        self.assertTrue(st["ok"])
        self.assertTrue(st["present"])
        with open(self.out_path, encoding="utf-8") as fh:
            self.assertIn("user_scenarios", json.load(fh))

    def test_http_invalid_pair_is_422_with_row_col(self):
        def mutate(rows):
            rows[3][2] = "oops"    # 3M col non-numeric
        c = _csv_text(mutate=mutate)
        code, res = self._post(
            "/validate-scenarios",
            {"csv_text": c, "manifest_text": _manifest_text(c)})
        self.assertEqual(code, 422)
        self.assertFalse(res["ok"])
        e = res["errors"][0]
        self.assertEqual(e["row"], 5)
        self.assertEqual(e["column"], "3M")


# ------------------------------------------------------------- discipline

class TestImportDiscipline(unittest.TestCase):
    def test_gui_module_is_stdlib_only_at_import_time(self):
        """numpy / the ES-1 loader must only be imported lazily inside the
        builders (the GUI-layer stdlib-only contract)."""
        path = os.path.join(_REPO, "par_model_v2", "viewer",
                            "igui_scenarios.py")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        for mod in ("numpy", "pandas", "scipy"):
            self.assertIsNone(
                re.search(r"^(?:import|from)\s+%s\b" % mod, src,
                          re.MULTILINE),
                "%s imported at module level" % mod)
        self.assertIsNone(
            re.search(r"^(?:import|from)\s+par_model_v2\.stochastic", src,
                      re.MULTILINE),
            "ES-1 loader imported at module level")

    def test_render_html_self_contained(self):
        html = render_scenarios_html()
        # the SVG namespace URI is a namespace NAME, not a fetched resource
        stripped = html.replace("http://www.w3.org/2000/svg", "")
        self.assertNotIn("http://", stripped)
        self.assertNotIn("https://", stripped)
        self.assertNotIn("<link", html)
        self.assertNotIn("<script src", html)
        self.assertNotIn("<img", html)


if __name__ == "__main__":
    unittest.main()
