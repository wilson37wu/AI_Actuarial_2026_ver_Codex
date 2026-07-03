"""GUI-5 tests: one-click Save & RUN from the Run Controls page
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

import run_gui
from par_model_v2.viewer.igui_run_controls import (
    default_run_controls, render_form_html)


class _FakeJobManager:
    """Captures submissions without spawning the engine."""

    def __init__(self, accept=True):
        self.accept = accept
        self.submissions = []

    def submit(self, smoke=True, runner=None, meta=None):
        self.submissions.append({"smoke": smoke, "meta": meta})
        if not self.accept:
            return {"ok": False, "error": "busy", "active_job_id": "other"}
        return {"ok": True, "job_id": "fake-job-1", "state": "queued"}


def _tmp_inputs():
    return os.path.join(tempfile.mkdtemp(prefix="igui5_"),
                        "model_inputs.json")


class TestSaveRunOrchestration(unittest.TestCase):
    def test_autofill_clears_gate_and_submits(self):
        out = _tmp_inputs()
        jm = _FakeJobManager()
        res = run_gui.build_save_run_response(
            default_run_controls(), out, jm)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["stage"], "run_submitted")
        self.assertEqual(res["job_id"], "fake-job-1")
        # all three missing domains were filled with governed defaults
        self.assertEqual(set(res["autofilled"]),
                         {"model_points+balance_sheet", "assumptions", "esg"})
        self.assertEqual(res["gate"]["decision"], "CLEARED")
        self.assertTrue(str(res["gate"]["reproducibility_digest"]
                            ).startswith("sha256:"))
        # the assembled file carries every domain + the written gate
        with open(out, encoding="utf-8") as fh:
            mi = json.load(fh)
        for key in ("run_settings", "portfolio", "balance_sheet",
                    "assumptions", "esg", "run_gate"):
            self.assertIn(key, mi)
        self.assertTrue(mi["run_gate"]["run_permitted"])
        # exactly one submission, smoke default True
        self.assertEqual(len(jm.submissions), 1)
        self.assertTrue(jm.submissions[0]["smoke"])

    def test_no_autofill_blocks_with_actionable_issues(self):
        out = _tmp_inputs()
        jm = _FakeJobManager()
        payload = dict(default_run_controls())
        payload["autofill"] = False
        res = run_gui.build_save_run_response(payload, out, jm)
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "run_gate_blocked")
        self.assertTrue(res["blocking_issues"])
        self.assertEqual(res["autofilled"], [])
        self.assertEqual(jm.submissions, [])  # nothing spawned
        # run controls were still saved (partial progress is kept)
        with open(out, encoding="utf-8") as fh:
            mi = json.load(fh)
        self.assertIn("run_settings", mi)
        self.assertNotIn("run_gate", mi)  # blocked gate never written

    def test_invalid_controls_fail_before_anything_else(self):
        out = _tmp_inputs()
        jm = _FakeJobManager()
        payload = dict(default_run_controls())
        payload["seed"] = "not-a-number"
        res = run_gui.build_save_run_response(payload, out, jm)
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "save_failed")
        self.assertEqual(jm.submissions, [])
        self.assertFalse(os.path.exists(out))  # invalid inputs never written

    def test_busy_job_manager_reported(self):
        out = _tmp_inputs()
        jm = _FakeJobManager(accept=False)
        res = run_gui.build_save_run_response(
            default_run_controls(), out, jm)
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "job_refused")
        self.assertEqual(res["active_job_id"], "other")

    def test_no_job_manager_reported(self):
        out = _tmp_inputs()
        res = run_gui.build_save_run_response(
            default_run_controls(), out, None)
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "no_job_manager")

    def test_seed_flows_into_gated_inputs(self):
        out = _tmp_inputs()
        payload = dict(default_run_controls())
        payload["seed"] = 46  # the owner's screenshot value
        res = run_gui.build_save_run_response(payload, out, _FakeJobManager())
        self.assertTrue(res["ok"], res)
        with open(out, encoding="utf-8") as fh:
            mi = json.load(fh)
        self.assertEqual(int(mi["run_settings"]["seed"]), 46)


class TestPageWiring(unittest.TestCase):
    def test_run_button_and_flow_present(self):
        page = render_form_html()
        for needle in ("btn-run", "Save &amp; RUN model", "/save-run",
                       "run-smoke", "run-autofill", "/jobs/",
                       "/my-results", "RUN GATE BLOCKED"):
            self.assertIn(needle, page)
        # page stays self-contained (no external references)
        self.assertNotIn("https://", page)
        # governed headline still carried bit-for-bit
        self.assertIn("39,975.654628199336", page)


class TestServerEndpoint(unittest.TestCase):
    def test_post_save_run_roundtrip_blocked_and_cleared(self):
        import threading
        import urllib.error
        import urllib.request
        out = _tmp_inputs()
        srv = run_gui.make_server(0, out)
        # swap in a capture-only manager: no engine spawn in unit tests
        jm = _FakeJobManager()
        srv.RequestHandlerClass.job_manager = jm
        host, port = srv.server_address
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            base = "http://%s:%d" % (host, port)

            def post(body):
                req = urllib.request.Request(
                    base + "/save-run",
                    data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=30) as r:
                        return r.status, json.loads(r.read().decode("utf-8"))
                except urllib.error.HTTPError as exc:
                    return exc.code, json.loads(exc.read().decode("utf-8"))

            body = dict(default_run_controls())
            body["autofill"] = False
            status, j = post(body)
            self.assertEqual(status, 422)
            self.assertEqual(j["stage"], "run_gate_blocked")

            body = dict(default_run_controls())
            body["autofill"] = True
            body["smoke"] = True
            status, j = post(body)
            self.assertEqual(status, 200, j)
            self.assertEqual(j["stage"], "run_submitted")
            self.assertEqual(j["job_id"], "fake-job-1")
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
