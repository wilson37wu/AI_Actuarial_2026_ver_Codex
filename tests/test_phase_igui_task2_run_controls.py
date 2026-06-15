"""Tests for Phase IGUI Task 2 - run controls + stdlib local runner.

Stdlib-only (unittest + urllib); does NOT import numpy/pandas/scipy or the
model orchestrator. Covers: run-controls normalisation, the loader round-trip
validator, the self-contained form, the localhost runner, and the Task-2 gate.
"""

import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from par_model_v2.viewer.igui_run_controls import (  # noqa: E402
    ALLOWED_SCALES,
    ALLOWED_THOUSANDS,
    GOVERNED_HEADLINE,
    RUN_CONTROL_FIELDS,
    SCHEMA_VERSION,
    UI_APP_SHA256,
    default_run_controls,
    normalize_run_controls,
    render_form_html,
    reproducibility_digest,
    run_controls_to_model_inputs,
    validate_task2_gate,
)
import load_user_inputs  # noqa: E402  (scripts/load_user_inputs.py)


class TestNormalise(unittest.TestCase):
    def test_defaults_normalise_clean(self):
        typed, errs = normalize_run_controls(default_run_controls())
        self.assertEqual(errs, [])
        self.assertIsInstance(typed["n_outer"], int)
        self.assertIsInstance(typed["seed"], int)
        self.assertEqual(typed["currency_code"], "HKD")

    def test_non_integer_rejected(self):
        bad = default_run_controls()
        bad["n_sim"] = "lots"
        _, errs = normalize_run_controls(bad)
        self.assertTrue(any("n_sim" in e for e in errs))

    def test_comma_grouped_integer_accepted(self):
        p = default_run_controls()
        p["n_sim"] = "200,000"
        typed, errs = normalize_run_controls(p)
        self.assertEqual(errs, [])
        self.assertEqual(typed["n_sim"], 200000)


class TestModelInputsFragment(unittest.TestCase):
    def setUp(self):
        self.typed, _ = normalize_run_controls(default_run_controls())
        self.mi = run_controls_to_model_inputs(
            self.typed, generated_at="1970-01-01T00:00:00+00:00")

    def test_schema_shape(self):
        self.assertEqual(self.mi["schema_version"], SCHEMA_VERSION)
        self.assertIn("currency", self.mi)
        self.assertIn("run_settings", self.mi)
        rs = self.mi["run_settings"]
        for k in ("n_outer", "n_inner", "n_sim", "bootstrap_replicates",
                  "horizon_months", "step_months", "seed", "output_label",
                  "reproducibility_digest"):
            self.assertIn(k, rs)
        self.assertEqual(self.mi["currency"]["valuation_date"], "2026-06-30")

    def test_digest_deterministic(self):
        d1 = reproducibility_digest(self.mi["currency"], self.mi["run_settings"])
        d2 = reproducibility_digest(self.mi["currency"], self.mi["run_settings"])
        self.assertEqual(d1, d2)
        self.assertTrue(d1.startswith("sha256:"))
        self.assertEqual(len(d1), 71)

    def test_digest_changes_with_seed(self):
        other = dict(self.typed, seed=43)
        mi2 = run_controls_to_model_inputs(other, generated_at="1970-01-01T00:00:00+00:00")
        self.assertNotEqual(
            self.mi["run_settings"]["reproducibility_digest"],
            mi2["run_settings"]["reproducibility_digest"])


class TestLoaderRoundTrip(unittest.TestCase):
    """The GUI payload must round-trip through the REAL loader validator."""

    def setUp(self):
        typed, _ = normalize_run_controls(default_run_controls())
        self.mi = run_controls_to_model_inputs(typed)

    def test_loader_validator_exists(self):
        self.assertTrue(hasattr(load_user_inputs, "validate_run_controls_dict"))

    def test_clean_fragment_passes_loader(self):
        self.assertEqual(load_user_inputs.validate_run_controls_dict(self.mi), [])

    def test_loader_enums_lockstep_with_core(self):
        self.assertEqual(ALLOWED_SCALES, load_user_inputs.ALLOWED_SCALES)
        self.assertEqual(ALLOWED_THOUSANDS, load_user_inputs.ALLOWED_THOUSANDS)
        self.assertEqual(SCHEMA_VERSION, load_user_inputs.SCHEMA_VERSION)

    def test_bad_currency_code_rejected(self):
        bad = json.loads(json.dumps(self.mi))
        bad["currency"]["code"] = "DOLLAR"
        errs = load_user_inputs.validate_run_controls_dict(bad)
        self.assertTrue(any("currency code" in e for e in errs))

    def test_zero_n_sim_rejected(self):
        bad = json.loads(json.dumps(self.mi))
        bad["run_settings"]["n_sim"] = 0
        self.assertTrue(load_user_inputs.validate_run_controls_dict(bad))

    def test_step_not_dividing_horizon_rejected(self):
        bad = json.loads(json.dumps(self.mi))
        bad["run_settings"]["horizon_months"] = 12
        bad["run_settings"]["step_months"] = 5
        errs = load_user_inputs.validate_run_controls_dict(bad)
        self.assertTrue(any("step" in e.lower() for e in errs))

    def test_bad_date_rejected(self):
        bad = json.loads(json.dumps(self.mi))
        bad["currency"]["valuation_date"] = "2026-13-40"
        self.assertTrue(load_user_inputs.validate_run_controls_dict(bad))


class TestForm(unittest.TestCase):
    def setUp(self):
        self.html = render_form_html()

    def test_has_every_field(self):
        for f in RUN_CONTROL_FIELDS:
            self.assertIn('name="%s"' % f["id"], self.html, f["id"])

    def test_zero_external_refs(self):
        import re
        self.assertEqual(re.findall(r'(?:src|href)="(?:https?:)?//', self.html), [])

    def test_carries_governed_headline(self):
        self.assertIn(GOVERNED_HEADLINE, self.html)


class TestLocalRunner(unittest.TestCase):
    def test_localhost_round_trip(self):
        import tempfile
        import threading
        import urllib.request
        import run_gui
        out = os.path.join(tempfile.mkdtemp(prefix="igui_t2_"), "model_inputs.json")
        srv = run_gui.make_server(0, out)
        host, port = srv.server_address
        self.assertEqual(host, "127.0.0.1")  # localhost only
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            base = "http://%s:%d" % (host, port)
            with urllib.request.urlopen(base + "/", timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertIn("Run Controls", r.read().decode("utf-8"))
            body = json.dumps(default_run_controls()).encode("utf-8")
            req = urllib.request.Request(
                base + "/save", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                j = json.loads(r.read().decode("utf-8"))
            self.assertTrue(j["ok"])
            self.assertTrue(os.path.exists(out))
            with open(out, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(
                load_user_inputs.validate_run_controls_dict(saved), [])
        finally:
            srv.shutdown()
            srv.server_close()

    def test_self_test_entrypoint(self):
        import run_gui
        self.assertEqual(run_gui.self_test(), 0)


class TestGate(unittest.TestCase):
    def test_gate_passes_against_repo(self):
        gate = validate_task2_gate(repo_root=REPO)
        self.assertTrue(gate["ok"], gate["checks"])
        self.assertGreaterEqual(gate["n_checks"], 20)

    def test_gate_ui_app_byte_unchanged(self):
        gate = validate_task2_gate(repo_root=REPO)
        self.assertTrue(gate["checks"]["ui_app_byte_unchanged"])
        # the frozen hash is the audited Phase-36 ui_app.html
        self.assertEqual(len(UI_APP_SHA256), 64)

    def test_gate_fails_on_missing_repo(self):
        self.assertFalse(validate_task2_gate(repo_root="/nonexistent")["ok"])


if __name__ == "__main__":
    unittest.main()
