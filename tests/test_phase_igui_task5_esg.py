"""Phase IGUI Task 5 - unittests for the ESG input domain (stop-rule-bounded, owner-gated).

Covers: settable-provenance spec integrity, default normalisation, range/date/text
coercion, the loader-side validate_esg_dict round-trip (incl. out-of-bounds / bad-date
rejections), the OWNER-GATING contract (governed-frozen ESG echo is read-only; the
server neutralises any override; the loader rejects a direct override), the STOP-RULE
guard (no new copula-structure candidate, in the echo or smuggled as a top-level key),
the self-contained page, ui_app.html byte-unchanged, and a localhost endpoint round-trip
through run_gui. Standard-library only; mirrors the Task-4 test style.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import unittest
import urllib.request

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from par_model_v2.viewer import igui_esg as E  # noqa: E402
import load_user_inputs as L  # noqa: E402
import run_gui  # noqa: E402


class TestSpec(unittest.TestCase):
    def test_groups_cover_all_target_domains(self):
        groups = {f["group"] for f in E.ESG_FIELDS}
        for g in ("Market Data", "Scenario Set", "Calibration Targets"):
            self.assertIn(g, groups)

    def test_every_field_has_default_and_kind(self):
        for f in E.ESG_FIELDS:
            self.assertIn("default", f)
            self.assertIn(f["kind"], ("float", "int", "choice", "bool", "text", "date"))

    def test_governed_frozen_values(self):
        self.assertEqual(E.GOVERNED_ESG_FROZEN["equity.equity_vol"], 0.22)
        self.assertEqual(E.GOVERNED_ESG_FROZEN["dependence.copula_df_single_t"], 2.9451)
        self.assertEqual(E.GOVERNED_ESG_FROZEN["dependence.grouped_t_df_nonfin"], 37.866)
        self.assertEqual(E.GOVERNED_ESG_FROZEN["dependence.grouped_t_df_fin"], 8.506)
        self.assertEqual(E.GOVERNED_ESG_FROZEN["dependence.copula_structure"],
                         "single_t_grouped_FROZEN")

    def test_loader_frozen_lockstep(self):
        self.assertEqual(L.GOVERNED_ESG_FROZEN, E.GOVERNED_ESG_FROZEN)
        self.assertEqual(L.FROZEN_COPULA_STRUCTURE, E.FROZEN_COPULA_STRUCTURE)

    def test_schema_version_lockstep(self):
        self.assertEqual(E.SCHEMA_VERSION, L.SCHEMA_VERSION)


class TestNormalize(unittest.TestCase):
    def test_defaults_normalise_clean(self):
        typed, errs = E.normalize_esg(E.default_esg())
        self.assertEqual(errs, [])
        self.assertIn("market_data", typed)
        self.assertIn("calibration", typed)

    def test_string_payload_coerces(self):
        # a realistic form delivers every field as a string; normalize coerces them
        raw = {f["id"]: str(f["default"]) for f in E.ESG_FIELDS}
        raw["calibration.target_10y_rate"] = "0.034"
        raw["scenario.documented_paths"] = "5000"
        typed, errs = E.normalize_esg(raw)
        self.assertEqual(errs, [])
        self.assertEqual(typed["calibration"]["target_10y_rate"], 0.034)
        self.assertEqual(typed["scenario"]["documented_paths"], 5000)

    def test_bad_number_reported(self):
        bad = json.loads(json.dumps(E.default_esg()))
        bad["calibration"]["target_10y_rate"] = "abc"
        _, errs = E.normalize_esg(bad)
        self.assertTrue(any("target_10y_rate" in e for e in errs))

    def test_bad_date_reported(self):
        bad = json.loads(json.dumps(E.default_esg()))
        bad["market_data"]["valuation_date"] = "31-05-2026"
        _, errs = E.normalize_esg(bad)
        self.assertTrue(any("valuation_date" in e for e in errs))


class TestLoaderRoundTrip(unittest.TestCase):
    def _frag(self, mutate=None):
        d = json.loads(json.dumps(E.default_esg()))
        if mutate:
            mutate(d)
        typed, errs = E.normalize_esg(d)
        self.assertEqual(errs, [], errs)
        return E.esg_to_model_inputs(typed)

    def test_defaults_pass_loader(self):
        self.assertEqual(L.validate_esg_dict(self._frag()), [])

    def test_out_of_bounds_caught(self):
        frag = self._frag(lambda d: d["calibration"].__setitem__("target_equity_vol", 9.0))
        self.assertTrue(len(L.validate_esg_dict(frag)) > 0)

    def test_documented_paths_lower_bound(self):
        frag = self._frag(lambda d: d["scenario"].__setitem__("documented_paths", 0))
        self.assertTrue(len(L.validate_esg_dict(frag)) > 0)

    def test_empty_text_caught(self):
        frag = self._frag(lambda d: d["market_data"].__setitem__("curve_source", ""))
        self.assertTrue(len(L.validate_esg_dict(frag)) > 0)

    def test_frozen_echo_is_governed(self):
        frag = self._frag()
        self.assertEqual(frag["esg"]["governed_esg_readback"], E.GOVERNED_ESG_FROZEN)

    def test_direct_frozen_override_rejected(self):
        frag = self._frag()
        frag["esg"]["governed_esg_readback"]["equity.equity_vol"] = 9.999
        errs = L.validate_esg_dict(frag)
        self.assertTrue(any("equity.equity_vol" in e for e in errs))

    def test_unknown_frozen_key_rejected(self):
        frag = self._frag()
        frag["esg"]["governed_esg_readback"]["dependence.new_param"] = 1.0
        errs = L.validate_esg_dict(frag)
        self.assertTrue(any("new_param" in e for e in errs))

    def test_stop_rule_new_structure_in_echo_rejected(self):
        frag = self._frag()
        frag["esg"]["governed_esg_readback"]["dependence.copula_structure"] = "vine_tree3"
        errs = L.validate_esg_dict(frag)
        self.assertTrue(any("stop-rule" in e.lower() for e in errs))

    def test_stop_rule_smuggled_top_level_structure_rejected(self):
        frag = self._frag()
        frag["esg"]["copula_structure"] = "skew_t_candidate"
        errs = L.validate_esg_dict(frag)
        self.assertTrue(any("stop-rule" in e.lower() for e in errs))

    def test_smuggled_frozen_structure_value_ok(self):
        frag = self._frag()
        frag["esg"]["copula_structure"] = "single_t_grouped_FROZEN"
        self.assertEqual(L.validate_esg_dict(frag), [])


class TestPage(unittest.TestCase):
    def test_self_contained_and_headline(self):
        page = E.render_esg_html()
        self.assertNotIn('src="http', page)
        self.assertNotIn('href="http', page)
        self.assertIn("39,975.654628199336", page)

    def test_shows_frozen_and_stop_rule(self):
        page = E.render_esg_html()
        self.assertIn("readonly", page)
        self.assertIn("copula_df_single_t", page)
        self.assertIn("single_t_grouped_FROZEN", page)
        self.assertIn("stop-rule", page)


class TestGate(unittest.TestCase):
    def test_task5_gate_ok(self):
        res = E.validate_task5_gate(_REPO)
        self.assertTrue(res["ok"], json.dumps(res["checks"], indent=1))

    def test_ui_app_byte_unchanged(self):
        with open(os.path.join(_REPO, "ui_app.html"), "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), E.UI_APP_SHA256)


class TestEndpoint(unittest.TestCase):
    def test_localhost_round_trip(self):
        import tempfile
        tmp = os.path.join(tempfile.mkdtemp(prefix="igui_t5_"), "model_inputs.json")
        srv = run_gui.make_server(0, tmp)
        host, port = srv.server_address
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            base = "http://%s:%d" % (host, port)
            with urllib.request.urlopen(base + "/esg", timeout=5) as r:
                page = r.read().decode("utf-8")
                self.assertEqual(r.status, 200)
                self.assertIn("single_t_grouped_FROZEN", page)
            body = json.dumps({"esg": E.default_esg()}).encode("utf-8")
            req = urllib.request.Request(base + "/validate_esg", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                j = json.loads(r.read().decode("utf-8"))
                self.assertTrue(j["ok"])
            # override neutralised by the server
            tampered = {"esg": E.default_esg()}
            tampered["esg"]["governed_esg_readback"] = {"equity.equity_vol": 9.9}
            treq = urllib.request.Request(base + "/validate_esg",
                                          data=json.dumps(tampered).encode("utf-8"),
                                          headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(treq, timeout=5) as r:
                j = json.loads(r.read().decode("utf-8"))
                self.assertTrue(j["ok"])
                self.assertEqual(
                    j["model_inputs"]["esg"]["governed_esg_readback"]["equity.equity_vol"], 0.22)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
