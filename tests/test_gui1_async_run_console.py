"""GUI-1 tests: async job manager + /execute-async + /jobs endpoints (Roadmap 4.0)."""

import json
import os
import sys
import threading
import time
import unittest
import urllib.request

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_REPO, os.path.join(_REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from par_model_v2.viewer.igui_job_manager import JobManager


def _wait_until(pred, timeout=10.0, step=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(step)
    return False


class TestJobManagerLifecycle(unittest.TestCase):
    def test_success_path(self):
        release = threading.Event()

        def runner(smoke):
            release.wait(5)
            return {"ok": True, "stage": "done", "smoke": smoke,
                    "progress": ["engine line 1", "engine line 2"],
                    "headline": {"nested_scr": 1.0}}

        jm = JobManager(runner)
        sub = jm.submit(smoke=True)
        self.assertTrue(sub["ok"])
        jid = sub["job_id"]
        self.assertTrue(_wait_until(lambda: jm.status(jid)["state"] == "running"))
        st = jm.status(jid)
        self.assertTrue(any("elapsed" in line for line in st["progress"]))
        release.set()
        self.assertTrue(_wait_until(lambda: jm.status(jid)["state"] == "succeeded"))
        st = jm.status(jid)
        self.assertEqual(st["result"]["headline"]["nested_scr"], 1.0)
        self.assertIn("engine line 1", st["progress"])
        self.assertIsNotNone(st["finished_at"])

    def test_failure_and_exception_paths(self):
        jm = JobManager(lambda smoke: {"ok": False, "stage": "run_gate_blocked"})
        jid = jm.submit()["job_id"]
        self.assertTrue(_wait_until(lambda: jm.status(jid)["state"] == "failed"))
        self.assertEqual(jm.status(jid)["error"], "run_gate_blocked")

        def boom(smoke):
            raise RuntimeError("engine exploded")

        jm2 = JobManager(boom)
        jid2 = jm2.submit()["job_id"]
        self.assertTrue(_wait_until(lambda: jm2.status(jid2)["state"] == "failed"))
        self.assertIn("engine exploded", jm2.status(jid2)["error"])

    def test_single_flight(self):
        release = threading.Event()

        def runner(smoke):
            release.wait(5)
            return {"ok": True}

        jm = JobManager(runner)
        first = jm.submit()
        self.assertTrue(_wait_until(lambda: jm.status(first["job_id"])["state"] == "running"))
        second = jm.submit()
        self.assertFalse(second["ok"])
        self.assertEqual(second["active_job_id"], first["job_id"])
        release.set()
        self.assertTrue(_wait_until(lambda: jm.status(first["job_id"])["state"] == "succeeded"))
        third = jm.submit()          # allowed again after terminal state
        self.assertTrue(third["ok"])

    def test_unknown_job(self):
        jm = JobManager(lambda smoke: {"ok": True})
        self.assertFalse(jm.status("nope")["ok"])

    def test_persistence(self):
        import tempfile
        d = tempfile.mkdtemp(prefix="gui1_jobs_")
        jm = JobManager(lambda smoke: {"ok": True, "progress": ["p1"]}, persist_dir=d)
        jid = jm.submit()["job_id"]
        self.assertTrue(_wait_until(lambda: jm.status(jid)["state"] == "succeeded"))
        path = os.path.join(d, "job_{}.json".format(jid))
        self.assertTrue(_wait_until(lambda: os.path.exists(path)))
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
        self.assertEqual(rec["job_id"], jid)
        self.assertEqual(rec["state"], "succeeded")

    def test_list_jobs_newest_first(self):
        jm = JobManager(lambda smoke: {"ok": True})
        a = jm.submit()["job_id"]
        self.assertTrue(_wait_until(lambda: jm.status(a)["state"] == "succeeded"))
        b = jm.submit()["job_id"]
        self.assertTrue(_wait_until(lambda: jm.status(b)["state"] == "succeeded"))
        jobs = jm.list_jobs()["jobs"]
        self.assertEqual([j["job_id"] for j in jobs[:2]], [b, a])


class TestHttpEndpoints(unittest.TestCase):
    """Round-trip /execute-async + /jobs through the real localhost server,
    with the engine runner stubbed on the bound JobManager (no model spawn)."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        import run_gui  # scripts/run_gui.py

        cls.tmp = tempfile.mkdtemp(prefix="gui1_http_")
        out_path = os.path.join(cls.tmp, "model_inputs.json")
        cls.srv = run_gui.make_server(0, out_path)
        # stub the engine: fast fake run
        cls.release = threading.Event()

        def fake_runner(smoke):
            cls.release.wait(5)
            return {"ok": True, "stage": "done", "progress": ["fake engine ran"],
                    "headline": {"nested_scr": 42.0},
                    "reproducibility_digest": "sha256:stub"}

        cls.srv.RequestHandlerClass.job_manager = JobManager(
            fake_runner, persist_dir=os.path.join(cls.tmp, "jobs"))
        host, port = cls.srv.server_address
        cls.base = "http://{}:{}".format(host, port)
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def _post(self, path, body):
        req = urllib.request.Request(self.base + path,
                                     data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    def _get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    def test_async_round_trip(self):
        sub = self._post("/execute-async", {"smoke": True})
        self.assertTrue(sub["ok"], sub)
        jid = sub["job_id"]
        st = self._get("/jobs/{}".format(jid))
        self.assertIn(st["state"], ("queued", "running"))
        self.release.set()
        self.assertTrue(_wait_until(
            lambda: self._get("/jobs/{}".format(jid))["state"] == "succeeded"))
        st = self._get("/jobs/{}".format(jid))
        self.assertEqual(st["result"]["headline"]["nested_scr"], 42.0)
        listing = self._get("/jobs")
        self.assertTrue(listing["ok"])
        self.assertEqual(listing["jobs"][0]["job_id"], jid)

    def test_unknown_job_404(self):
        import urllib.error
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/jobs/does-not-exist")
        self.assertEqual(ctx.exception.code, 404)


class TestRunPageAsyncWiring(unittest.TestCase):
    def test_page_uses_async_endpoints_and_stays_self_contained(self):
        from par_model_v2.viewer.igui_run_execution import render_run_html
        page = render_run_html()
        self.assertIn("/execute-async", page)
        self.assertIn("/jobs/", page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        self.assertNotIn("src=", page)
        self.assertIn('id="btn-run" type="button" disabled', page)


if __name__ == "__main__":
    unittest.main()
