"""Phase IGUI Task 6 - unittests for validation surfacing + governance gating.

Covers: the loader-side aggregate validator (per-domain present/ok/errors + overall
verdict, incl. missing-domain and invalid-field cases), the run-level reproducibility
digest (determinism, input sensitivity, timestamp invariance), the governance run-gate
record (CLEARED only when every domain is clean; BLOCKED surfaces blocking issues),
the self-contained gate page (no external refs; Run blocked by default), ui_app.html
byte-unchanged, loader/schema lock-step, and a localhost endpoint round-trip through
run_gui (GET /run-gate, POST /preflight, POST /run). Standard-library only; mirrors the
Task-5 test style.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import unittest
import urllib.request
import urllib.error

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from par_model_v2.viewer import igui_validation_gating as G  # noqa: E402
import load_user_inputs as L  # noqa: E402
import run_gui  # noqa: E402


def _clean():
    return G._clean_assembled_inputs()


class TestLockstep(unittest.TestCase):
    def test_schema_version_lockstep(self):
        self.assertEqual(G.SCHEMA_VERSION, L.SCHEMA_VERSION)

    def test_domains_order(self):
        self.assertEqual(G.DOMAINS, ("run_controls", "model_points", "assumptions", "esg"))
        self.assertEqual(L.GUI_INPUT_DOMAINS, G.DOMAINS)

    def test_frozen_structure_lockstep(self):
        self.assertEqual(G.FROZEN_COPULA_STRUCTURE, L.FROZEN_COPULA_STRUCTURE)


class TestAggregateValidator(unittest.TestCase):
    def test_clean_inputs_clear(self):
        v = L.validate_assembled_inputs(_clean())
        self.assertTrue(v["ok"], v)
        for d in G.DOMAINS:
            self.assertTrue(v["domains"][d]["present"])
            self.assertTrue(v["domains"][d]["ok"], (d, v["domains"][d]["errors"]))
        self.assertEqual(v["n_errors"], 0)

    def test_missing_domain_blocks(self):
        mi = json.loads(json.dumps(_clean()))
        mi.pop("esg")
        v = L.validate_assembled_inputs(mi)
        self.assertFalse(v["ok"])
        self.assertFalse(v["domains"]["esg"]["present"])
        self.assertFalse(v["domains"]["esg"]["ok"])
        self.assertGreaterEqual(len(v["domains"]["esg"]["errors"]), 1)
        # the other three remain clean
        for d in ("run_controls", "model_points", "assumptions"):
            self.assertTrue(v["domains"][d]["ok"])

    def test_invalid_field_surfaced(self):
        mi = json.loads(json.dumps(_clean()))
        mi["run_settings"]["n_outer"] = 0  # violates >= 1
        v = L.validate_assembled_inputs(mi)
        self.assertFalse(v["ok"])
        self.assertFalse(v["domains"]["run_controls"]["ok"])
        self.assertTrue(any("Outer scenarios" in e for e in v["domains"]["run_controls"]["errors"]))

    def test_non_dict_payload(self):
        v = L.validate_assembled_inputs(["not", "a", "dict"])
        self.assertFalse(v["ok"])

    def test_routes_through_real_loader(self):
        # the aggregate must equal the per-domain validators run directly
        mi = _clean()
        v = L.validate_assembled_inputs(mi)
        self.assertEqual(v["domains"]["run_controls"]["errors"],
                         L.validate_run_controls_dict(mi))
        self.assertEqual(v["domains"]["esg"]["errors"], L.validate_esg_dict(mi))


class TestDigest(unittest.TestCase):
    def test_shape(self):
        d = G.run_reproducibility_digest(_clean())
        self.assertTrue(d.startswith("sha256:"))
        self.assertEqual(len(d), 71)

    def test_deterministic(self):
        mi = _clean()
        self.assertEqual(G.run_reproducibility_digest(mi),
                         G.run_reproducibility_digest(json.loads(json.dumps(mi))))

    def test_sensitive_to_inputs(self):
        mi = _clean()
        moved = json.loads(json.dumps(mi))
        moved["run_settings"]["seed"] = int(moved["run_settings"]["seed"]) + 1
        self.assertNotEqual(G.run_reproducibility_digest(moved),
                            G.run_reproducibility_digest(mi))

    def test_ignores_timestamp_and_prior_gate(self):
        mi = _clean()
        base = G.run_reproducibility_digest(mi)
        noisy = json.loads(json.dumps(mi))
        noisy["generated_at"] = "2099-12-31T23:59:59+00:00"
        noisy["run_gate"] = {"decision": "CLEARED"}
        self.assertEqual(G.run_reproducibility_digest(noisy), base)


class TestRunGate(unittest.TestCase):
    def test_cleared(self):
        mi = _clean()
        v = L.validate_assembled_inputs(mi)
        gate = G.build_run_gate(mi, v, now="1970-01-01T00:00:00+00:00")
        self.assertEqual(gate["decision"], "CLEARED")
        self.assertTrue(gate["run_permitted"])
        self.assertEqual(gate["n_blocking_issues"], 0)
        self.assertEqual(gate["frozen_copula_structure"], G.FROZEN_COPULA_STRUCTURE)
        self.assertEqual(gate["governed_headline"], G.GOVERNED_HEADLINE)
        self.assertTrue(gate["reproducibility_digest"].startswith("sha256:"))
        self.assertEqual(gate["record_type"], "RUN_GATE")

    def test_blocked_lists_issues(self):
        mi = json.loads(json.dumps(_clean()))
        mi.pop("assumptions")
        v = L.validate_assembled_inputs(mi)
        gate = G.build_run_gate(mi, v)
        self.assertEqual(gate["decision"], "BLOCKED")
        self.assertFalse(gate["run_permitted"])
        self.assertGreaterEqual(gate["n_blocking_issues"], 1)
        self.assertTrue(any(b.startswith("[assumptions]") for b in gate["blocking_issues"]))

    def test_gate_does_not_mutate_inputs(self):
        mi = _clean()
        before = json.dumps(mi, sort_keys=True)
        G.build_run_gate(mi, L.validate_assembled_inputs(mi))
        self.assertEqual(json.dumps(mi, sort_keys=True), before)


class TestPage(unittest.TestCase):
    def test_self_contained(self):
        p = G.render_gate_html()
        self.assertNotIn("http://", p)
        self.assertNotIn("https://", p)
        self.assertNotIn("src=", p)

    def test_blocks_run_by_default(self):
        self.assertIn('id="btn-run" disabled', G.render_gate_html())

    def test_carries_headline_and_structure(self):
        p = G.render_gate_html()
        self.assertIn(G.GOVERNED_HEADLINE, p)
        self.assertIn(G.FROZEN_COPULA_STRUCTURE, p)


class TestUiAppUnchanged(unittest.TestCase):
    def test_byte_unchanged(self):
        path = os.path.join(_REPO, "ui_app.html")
        with open(path, "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), G.UI_APP_SHA256)


class TestGate(unittest.TestCase):
    def test_task6_gate_green(self):
        g = G.validate_task6_gate(_REPO)
        self.assertTrue(g["ok"], [k for k, v in g["checks"].items() if not v])


class TestLocalhostRoundTrip(unittest.TestCase):
    def test_preflight_and_run(self):
        import tempfile
        tmp = os.path.join(tempfile.mkdtemp(prefix="igui_t6_"), "model_inputs.json")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(_clean(), fh, indent=1)
        srv = run_gui.make_server(0, tmp)
        host, port = srv.server_address
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            base = "http://%s:%d" % (host, port)
            with urllib.request.urlopen(base + "/run-gate", timeout=5) as r:
                page = r.read().decode("utf-8")
                self.assertEqual(r.status, 200)
                self.assertIn("Run Gate", page)
            preq = urllib.request.Request(base + "/preflight", data=b"{}",
                                          headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(preq, timeout=5) as r:
                j = json.loads(r.read().decode("utf-8"))
                self.assertTrue(j["ok"])
            rreq = urllib.request.Request(base + "/run", data=b"{}",
                                          headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(rreq, timeout=5) as r:
                j = json.loads(r.read().decode("utf-8"))
                self.assertTrue(j["ok"])
                self.assertEqual(j["run_gate"]["decision"], "CLEARED")
            with open(tmp, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertIn("run_gate", saved)
            self.assertTrue(saved["run_gate"]["run_permitted"])
        finally:
            srv.shutdown()
            srv.server_close()

    def test_run_blocked_when_incomplete(self):
        import tempfile
        tmp = os.path.join(tempfile.mkdtemp(prefix="igui_t6b_"), "model_inputs.json")
        mi = json.loads(json.dumps(_clean()))
        mi.pop("esg")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(mi, fh, indent=1)
        srv = run_gui.make_server(0, tmp)
        host, port = srv.server_address
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            base = "http://%s:%d" % (host, port)
            rreq = urllib.request.Request(base + "/run", data=b"{}",
                                          headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(rreq, timeout=5) as r:
                    body = r.read().decode("utf-8")
                    code = r.status
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8")
                code = e.code
            j = json.loads(body)
            self.assertEqual(code, 422)
            self.assertFalse(j["ok"])
            self.assertEqual(j["run_gate"]["decision"], "BLOCKED")
            # nothing recorded into the file
            with open(tmp, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertNotIn("run_gate", saved)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
