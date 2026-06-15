"""Phase IGUI Task 4 - unittests for the assumptions input domain (owner-gated).

Covers: declarative spec integrity, default normalisation, range/choice/bool
coercion, the discount-curve normaliser, the loader-side validate_assumptions_dict
round-trip (incl. out-of-bounds / bad-choice / curve rejections), the
OWNER-GATING contract (governed-frozen echo is read-only; the server neutralises
any override; the loader rejects a direct override), the self-contained page,
ui_app.html byte-unchanged, and a localhost endpoint round-trip through run_gui.
Standard-library only; mirrors the Task-2 / Task-3 test style.
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

from par_model_v2.viewer import igui_assumptions as A  # noqa: E402
import load_user_inputs as L  # noqa: E402
import run_gui  # noqa: E402


class TestSpec(unittest.TestCase):
    def test_groups_cover_all_target_domains(self):
        groups = {f["group"] for f in A.ASSUMPTION_FIELDS}
        for g in ("Mortality", "Lapse & Surrender", "Expenses", "Premiums",
                  "Discount / Yield", "Bonus & Crediting", "Management Action",
                  "Reinsurance", "Risk"):
            self.assertIn(g, groups)

    def test_every_field_has_default_and_kind(self):
        for f in A.ASSUMPTION_FIELDS:
            self.assertIn("default", f)
            self.assertIn(f["kind"], ("float", "int", "choice", "bool", "text"))

    def test_governed_frozen_values(self):
        self.assertEqual(A.GOVERNED_FROZEN["copula_df_single_t"], 2.9451)
        self.assertEqual(A.GOVERNED_FROZEN["grouped_t_df_nonfin"], 37.866)
        self.assertEqual(A.GOVERNED_FROZEN["grouped_t_df_fin"], 8.506)

    def test_loader_frozen_lockstep(self):
        self.assertEqual(L.GOVERNED_FROZEN_ASSUMPTIONS, A.GOVERNED_FROZEN)

    def test_schema_version_lockstep(self):
        self.assertEqual(A.SCHEMA_VERSION, L.SCHEMA_VERSION)


class TestNormalize(unittest.TestCase):
    def test_defaults_normalise_clean(self):
        typed, errs = A.normalize_assumptions(A.default_assumptions())
        self.assertEqual(errs, [])
        self.assertIn("mortality", typed)
        self.assertEqual(typed["discount"]["mode"], "flat")

    def test_string_payload_coerced(self):
        raw = A.default_assumptions()
        raw["mortality"]["base_multiplier"] = "1.25"   # string as a form delivers
        raw["management_action"]["dynamic_rule_enabled"] = "false"
        typed, errs = A.normalize_assumptions(raw)
        self.assertEqual(errs, [])
        self.assertEqual(typed["mortality"]["base_multiplier"], 1.25)
        self.assertIs(typed["management_action"]["dynamic_rule_enabled"], False)

    def test_bad_number_reported(self):
        raw = A.default_assumptions()
        raw["mortality"]["base_multiplier"] = "abc"
        _, errs = A.normalize_assumptions(raw)
        self.assertTrue(any("base_multiplier" in e for e in errs))

    def test_bad_choice_reported(self):
        raw = A.default_assumptions()
        raw["reinsurance"]["type"] = "nope"
        _, errs = A.normalize_assumptions(raw)
        self.assertTrue(any("reinsurance.type" in e for e in errs))

    def test_curve_normaliser(self):
        out, errs = A._normalize_curve(A.DEFAULT_DISCOUNT_CURVE)
        self.assertEqual(errs, [])
        self.assertEqual(len(out), 5)
        _, e2 = A._normalize_curve([{"tenor": 0, "rate": 0.03}])
        self.assertTrue(e2)


class TestLoaderRoundTrip(unittest.TestCase):
    def _frag(self, mutate=None):
        a = json.loads(json.dumps(A.default_assumptions()))
        if mutate:
            mutate(a)
        typed, _ = A.normalize_assumptions(a)
        return A.assumptions_to_model_inputs(typed)

    def test_defaults_pass_loader(self):
        self.assertEqual(L.validate_assumptions_dict(self._frag()), [])

    def test_out_of_bounds_rejected(self):
        def m(a):
            a["risk"]["confidence"] = 1.5
        self.assertTrue(L.validate_assumptions_dict(self._frag(m)))

    def test_negative_expense_rejected(self):
        def m(a):
            a["expenses"]["per_policy"] = -1
        self.assertTrue(L.validate_assumptions_dict(self._frag(m)))

    def test_curve_mode_requires_curve(self):
        frag = self._frag()
        frag["assumptions"]["discount"]["mode"] = "curve"
        frag["assumptions"]["discount"]["curve"] = []
        self.assertTrue(L.validate_assumptions_dict(frag))

    def test_direct_frozen_override_rejected_by_loader(self):
        frag = self._frag()
        frag["assumptions"]["governed_frozen_readback"]["grouped_t_df_fin"] = 1.0
        errs = L.validate_assumptions_dict(frag)
        self.assertTrue(any("governed_frozen_readback" in e for e in errs))

    def test_unknown_frozen_key_rejected(self):
        frag = self._frag()
        frag["assumptions"]["governed_frozen_readback"]["sneaky"] = 1.0
        self.assertTrue(L.validate_assumptions_dict(frag))


class TestOwnerGating(unittest.TestCase):
    def test_to_model_inputs_always_attaches_governed_echo(self):
        # Even if a tampered echo arrives, the builder attaches the governed one.
        raw = A.default_assumptions()
        raw["governed_frozen_readback"] = {"copula_df_single_t": 9.999}
        typed, _ = A.normalize_assumptions(raw)
        frag = A.assumptions_to_model_inputs(typed)
        self.assertEqual(frag["assumptions"]["governed_frozen_readback"], A.GOVERNED_FROZEN)


class TestPage(unittest.TestCase):
    def test_self_contained_and_headline(self):
        page = A.render_assumptions_html()
        self.assertNotIn('src="http', page)
        self.assertNotIn('href="http', page)
        self.assertIn(A.GOVERNED_HEADLINE, page)
        self.assertIn("readonly", page)
        self.assertIn("copula_df_single_t", page)


class TestUiAppUnchanged(unittest.TestCase):
    def test_ui_app_byte_unchanged(self):
        with open(os.path.join(_REPO, "ui_app.html"), "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), A.UI_APP_SHA256)


class TestGate(unittest.TestCase):
    def test_gate_ok(self):
        g = A.validate_task4_gate(_REPO)
        self.assertTrue(g["ok"], [k for k, v in g["checks"].items() if not v])
        self.assertGreaterEqual(g["n_checks"], 25)


class TestEndpointRoundTrip(unittest.TestCase):
    def test_localhost_assumptions_round_trip(self):
        import tempfile
        tmp = os.path.join(tempfile.mkdtemp(prefix="igui_t4_"), "model_inputs.json")
        srv = run_gui.make_server(0, tmp)
        host, port = srv.server_address
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            base = "http://%s:%d" % (host, port)
            with urllib.request.urlopen(base + "/assumptions", timeout=5) as r:
                page = r.read().decode("utf-8")
                self.assertEqual(r.status, 200)
                self.assertIn("Assumptions", page)
            body = json.dumps({"assumptions": A.default_assumptions()}).encode("utf-8")
            req = urllib.request.Request(base + "/validate_assumptions", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                j = json.loads(r.read().decode("utf-8"))
                self.assertTrue(j["ok"])
                self.assertEqual(
                    j["model_inputs"]["assumptions"]["governed_frozen_readback"],
                    A.GOVERNED_FROZEN)
            req = urllib.request.Request(base + "/save_assumptions", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                j = json.loads(r.read().decode("utf-8"))
                self.assertTrue(j["ok"])
            with open(tmp, encoding="utf-8") as fh:
                self.assertIn("assumptions", json.load(fh))
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
