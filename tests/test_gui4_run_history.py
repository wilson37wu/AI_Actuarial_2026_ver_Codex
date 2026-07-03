"""GUI-4 tests: run registry, durable enrichment, compare, endpoints
(Roadmap 4.0, owner directive 2026-07-03)."""

import json
import os
import sys
import tempfile
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_REPO, os.path.join(_REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from par_model_v2.viewer import igui_run_history as H


def _headline(nested=100.0):
    return {"nested_scr": nested, "copula_scr": nested * 0.9,
            "var_covar_scr": nested * 0.8,
            "standalone_scr": {"rate": 10.0, "equity": 20.0}}


def _job_record(job_id, *, kind="run", state="succeeded", seed=42,
                nested=100.0, digest="sha256:aa", report_path=None,
                smoke=True, registry=None):
    rec = {
        "job_id": job_id, "state": state, "smoke": smoke,
        "meta": {} if kind == "run" else {"kind": kind},
        "submitted_at": "2026-07-03T0{}:00:00+00:00".format(len(job_id) % 10),
        "started_at": None, "finished_at": "2026-07-03T09:00:00+00:00",
        "elapsed_seconds": 12.3,
        "progress": [], "error": None,
        "result": {"ok": state == "succeeded",
                   "reproducibility_digest": digest,
                   "headline": _headline(nested),
                   "out_dir": "/tmp/somewhere",
                   "report_path": report_path},
    }
    if registry is not None:
        rec["registry"] = registry
    return rec


def _write_job(jobs_dir, rec):
    path = os.path.join(jobs_dir, "job_{}.json".format(rec["job_id"]))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    return path


def _write_report(td, seed=42):
    path = os.path.join(td, "RUN_MODEL_AGGREGATION_REPORT.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"run_plan": {"seed": seed, "n_outer": 40, "n_inner": 200,
                                "n_sim": 2000, "horizon_months": 12,
                                "bootstrap_replicates": 500,
                                "output_label": "smoke_diagnostic"}}, fh)
    return path


class TestRegistry(unittest.TestCase):
    def test_empty_and_missing_dir(self):
        with tempfile.TemporaryDirectory() as td:
            reg = H.load_registry(os.path.join(td, "nope"))
        self.assertTrue(reg["ok"])
        self.assertEqual(reg["count"], 0)
        self.assertEqual(reg["runs"], [])

    def test_entries_newest_first_with_reproducibility_tuple(self):
        with tempfile.TemporaryDirectory() as td:
            rep = _write_report(td, seed=777)
            _write_job(td, _job_record("a1", nested=100.0, report_path=rep))
            _write_job(td, _job_record("b22", kind="stress", nested=120.0,
                                       digest="sha256:bb", report_path=rep))
            reg = H.load_registry(td)
            self.assertEqual(reg["count"], 2)
            by_id = {r["run_id"]: r for r in reg["runs"]}
            run = by_id["a1"]
            # the roadmap reproducibility tuple: id, timestamp, inputs hash,
            # seed, headline outputs
            self.assertEqual(run["reproducibility_digest"], "sha256:aa")
            self.assertEqual(run["seed"], 777)
            self.assertAlmostEqual(run["headline"]["nested_scr"], 100.0)
            self.assertTrue(run["submitted_at"])
            self.assertEqual(by_id["b22"]["kind"], "stress")

    def test_enrichment_is_persisted_and_survives_artifact_loss(self):
        with tempfile.TemporaryDirectory() as td:
            rep = _write_report(td, seed=555)
            path = _write_job(td, _job_record("c3", report_path=rep))
            reg1 = H.load_registry(td)
            self.assertEqual(reg1["runs"][0]["seed"], 555)
            # registry block was written back into the job record
            with open(path, encoding="utf-8") as fh:
                on_disk = json.load(fh)
            self.assertEqual(on_disk["registry"]["run_plan"]["seed"], 555)
            # simulate a later run overwriting the shared artifacts
            os.remove(rep)
            reg2 = H.load_registry(td)
            self.assertEqual(reg2["runs"][0]["seed"], 555)  # still known

    def test_corrupt_record_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as td:
            _write_job(td, _job_record("ok1"))
            with open(os.path.join(td, "job_bad.json"), "w") as fh:
                fh.write("{not json")
            reg = H.load_registry(td)
            self.assertEqual(reg["count"], 1)
            self.assertIn("job_bad.json", reg["skipped"])


class TestGetRun(unittest.TestCase):
    def test_open_and_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            _write_job(td, _job_record("z9"))
            got = H.get_run(td, "z9")
            self.assertTrue(got["ok"])
            self.assertEqual(got["entry"]["run_id"], "z9")
            self.assertEqual(got["record"]["job_id"], "z9")
            self.assertFalse(H.get_run(td, "missing")["ok"])

    def test_no_path_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            got = H.get_run(td, "../../etc/passwd")
            self.assertFalse(got["ok"])


class TestCompare(unittest.TestCase):
    def test_side_by_side_deltas_and_meta(self):
        with tempfile.TemporaryDirectory() as td:
            _write_job(td, _job_record("a1", nested=100.0, digest="sha256:aa"))
            _write_job(td, _job_record("b2", nested=120.0, digest="sha256:bb"))
            cmp_ = H.compare_runs(td, "a1", "b2")
            self.assertTrue(cmp_["ok"])
            rows = {r["metric"]: r for r in cmp_["comparison"]["rows"]}
            self.assertAlmostEqual(rows["nested_scr"]["delta"], 20.0)
            self.assertAlmostEqual(rows["nested_scr"]["delta_pct"], 20.0)
            meta = {m["field"]: m for m in cmp_["meta_rows"]}
            self.assertFalse(meta["reproducibility_digest"]["same"])
            self.assertTrue(meta["state"]["same"])
            # smoke note is surfaced
            self.assertTrue(any("SMOKE" in n for n in cmp_["notes"]))

    def test_same_digest_note(self):
        with tempfile.TemporaryDirectory() as td:
            _write_job(td, _job_record("a1", nested=100.0, digest="sha256:same"))
            _write_job(td, _job_record("b2", nested=101.0, digest="sha256:same"))
            cmp_ = H.compare_runs(td, "a1", "b2")
            self.assertTrue(any("identical inputs digest" in n
                                for n in cmp_["notes"]))

    def test_unknown_side_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            _write_job(td, _job_record("a1"))
            self.assertFalse(H.compare_runs(td, "a1", "nope")["ok"])
            self.assertFalse(H.compare_runs(td, "nope", "a1")["ok"])

    def test_kind_mismatch_note(self):
        with tempfile.TemporaryDirectory() as td:
            _write_job(td, _job_record("a1"))
            _write_job(td, _job_record("b2", kind="calibration"))
            cmp_ = H.compare_runs(td, "a1", "b2")
            self.assertTrue(any("different run kinds" in n
                                for n in cmp_["notes"]))


class TestRenderHtml(unittest.TestCase):
    def test_page_self_contained(self):
        page = H.render_history_html()
        for needle in ("Run history", "/runs", "/compare-runs",
                       "Compare A vs B"):
            self.assertIn(needle, page)
        self.assertNotIn("https://", page)  # zero external references


class TestServerEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        import run_gui
        cls._tmp = tempfile.mkdtemp(prefix="igui4_")
        cls.srv = run_gui.make_server(
            0, os.path.join(cls._tmp, "model_inputs.json"))
        cls.host, cls.port = cls.srv.server_address
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.th.start()
        cls.base = "http://%s:%d" % (cls.host, cls.port)
        # seed the server's REAL jobs dir with two synthetic records
        import run_gui as rg
        cls.jobs_dir = os.path.join(rg._REPO, rg.RUN_OUTPUT_DIR, "jobs")
        os.makedirs(cls.jobs_dir, exist_ok=True)
        cls._created = []
        for rec in (_job_record("guitest_a", nested=100.0),
                    _job_record("guitest_b", nested=110.0)):
            cls._created.append(_write_job(cls.jobs_dir, rec))

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        for p in cls._created:
            try:
                os.remove(p)
            except OSError:
                pass

    def _get(self, path):
        import urllib.request
        with urllib.request.urlopen(self.base + path, timeout=30) as r:
            return r.status, r.read().decode("utf-8")

    def test_history_page_served(self):
        status, page = self._get("/history")
        self.assertEqual(status, 200)
        self.assertIn("Run history", page)

    def test_runs_and_detail_and_compare(self):
        status, body = self._get("/runs")
        self.assertEqual(status, 200)
        j = json.loads(body)
        self.assertTrue(j["ok"])
        ids = {r["run_id"] for r in j["runs"]}
        self.assertLessEqual({"guitest_a", "guitest_b"}, ids)

        status, body = self._get("/runs/guitest_a")
        self.assertEqual(status, 200)
        j = json.loads(body)
        self.assertTrue(j["ok"])
        self.assertEqual(j["entry"]["run_id"], "guitest_a")

        status, body = self._get("/compare-runs?a=guitest_a&b=guitest_b")
        self.assertEqual(status, 200)
        j = json.loads(body)
        self.assertTrue(j["ok"], j)
        rows = {r["metric"]: r for r in j["comparison"]["rows"]}
        self.assertAlmostEqual(rows["nested_scr"]["delta"], 10.0)

    def test_unknown_run_404(self):
        import urllib.error
        try:
            self._get("/runs/definitely_missing")
            status = 200
        except urllib.error.HTTPError as exc:
            status = exc.code
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
