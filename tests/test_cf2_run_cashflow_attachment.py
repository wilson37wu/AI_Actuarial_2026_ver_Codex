"""CF-2 - cash-flow projection set bound to EXECUTED runs (roadmap 4.0c,
owner directive 2026-07-03).

Covers: the per-run attachment builder (digest-keyed persistence + cache
reuse, never-raise contract, stale-set guard by digest keying), the
persisted-set loader for past runs (provenance stamping, schema/digest
guards, traversal safety), the run registry / compare surfacing, the
execute_run hook, and the /cashflows & /history page plumbing
(query-param fetch, CFs button) incl. the run_gui /cashflow-data?run=
route.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from par_model_v2.viewer.igui_cashflows import (  # noqa: E402
    CF_GUI_SCHEMA_VERSION,
    CF_RUN_SCHEMA_VERSION,
    RUN_CF_SET_DIRNAME,
    attach_cashflow_set_for_run,
    load_run_cashflow_set,
    render_cashflows_html,
)
from par_model_v2.viewer.igui_run_history import (  # noqa: E402
    _entry_from_record,
    compare_runs,
    render_history_html,
)


def _model_inputs(count="1000"):
    return {
        "portfolio": [
            {"product_type": "HKCD_PAR_2026", "issue_age": "45",
             "gender": "M", "term_years": "20", "sum_assured": "100000",
             "annual_premium": "5000", "policy_count": count,
             "vested_bonus": "0"},
        ],
        "balance_sheet": {"assets": [
            {"asset_class": "Government bonds", "market_value": "120000000"},
            {"asset_class": "Equity", "market_value": "30000000"},
        ]},
    }


def _write_inputs(root, mi=None):
    path = os.path.join(root, "model_inputs.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_model_inputs() if mi is None else mi, fh)
    return path


def _job_record(job_id, cf_att=None, headline=None):
    rec = {"job_id": job_id, "state": "succeeded", "smoke": True,
           "meta": {"kind": "run"}, "submitted_at": "2026-07-08T06:00:00Z",
           "finished_at": "2026-07-08T06:05:00Z", "elapsed_seconds": 300.0,
           "progress": [], "error": None,
           "result": {"ok": True, "reproducibility_digest": "sha256:aa",
                      "headline": headline or {"nested_scr": 100.0}},
           "registry": {"schema": "gui4-history-1.0",
                        "run_plan": {"seed": 77}}}
    if cf_att is not None:
        rec["result"]["cashflow_set"] = cf_att
    return rec


def _persist(jobs_dir, rec):
    os.makedirs(jobs_dir, exist_ok=True)
    with open(os.path.join(jobs_dir, "job_%s.json" % rec["job_id"]),
              "w", encoding="utf-8") as fh:
        json.dump(rec, fh)


class TestAttachForRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cf2_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.inputs = _write_inputs(self.tmp)
        self.out = os.path.join(self.tmp, "run_output")

    def test_attach_builds_digest_keyed_set(self):
        att = attach_cashflow_set_for_run(self.inputs, self.out)
        self.assertTrue(att["ok"], att)
        self.assertEqual(att["schema"], CF_RUN_SCHEMA_VERSION)
        self.assertFalse(att["cached"])
        self.assertEqual(att["horizon"], {"months": 1200, "years": 100})
        self.assertIn(RUN_CF_SET_DIRNAME, att["dir"])
        self.assertIn(att["inputs_digest"][:12], att["dir"])
        self.assertTrue(os.path.exists(
            os.path.join(att["dir"], "CF_GUI_CACHE.json")))
        # engine CSV artifacts live beside the cache
        csvs = [n for n in os.listdir(att["dir"]) if n.endswith(".csv")]
        self.assertGreaterEqual(len(csvs), 6)

    def test_second_attach_is_digest_cache_hit(self):
        first = attach_cashflow_set_for_run(self.inputs, self.out)
        again = attach_cashflow_set_for_run(self.inputs, self.out)
        self.assertTrue(again["ok"])
        self.assertTrue(again["cached"])
        self.assertEqual(first["inputs_digest"], again["inputs_digest"])
        self.assertEqual(first["dir"], again["dir"])

    def test_different_inputs_get_their_own_directory(self):
        a = attach_cashflow_set_for_run(self.inputs, self.out)
        other = _write_inputs(self.tmp, _model_inputs(count="500"))
        b = attach_cashflow_set_for_run(other, self.out)
        self.assertTrue(a["ok"] and b["ok"])
        self.assertNotEqual(a["inputs_digest"], b["inputs_digest"])
        self.assertNotEqual(a["dir"], b["dir"])
        # the earlier run's set is NOT overwritten (stale-set guard)
        self.assertTrue(os.path.exists(
            os.path.join(a["dir"], "CF_GUI_CACHE.json")))

    def test_empty_inputs_report_not_raise(self):
        empty = _write_inputs(self.tmp, {})
        att = attach_cashflow_set_for_run(empty, self.out)
        self.assertFalse(att["ok"])
        self.assertTrue(att["errors"])

    def test_corrupt_inputs_never_raise(self):
        bad = os.path.join(self.tmp, "model_inputs.json")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        att = attach_cashflow_set_for_run(bad, self.out)
        self.assertFalse(att["ok"])
        self.assertTrue(att["errors"])


class TestLoadRunCashflowSet(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cf2_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.out = os.path.join(self.tmp, "run_output")
        self.jobs = os.path.join(self.out, "jobs")
        self.att = attach_cashflow_set_for_run(
            _write_inputs(self.tmp), self.out)
        self.assertTrue(self.att["ok"])

    def test_load_persisted_set_with_run_provenance(self):
        _persist(self.jobs, _job_record("r1", self.att))
        got = load_run_cashflow_set(self.jobs, "r1")
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["schema"], CF_GUI_SCHEMA_VERSION)
        self.assertEqual(got["run_id"], "r1")
        self.assertTrue(got["cached"])
        self.assertIn("r1", got["run_note"])
        self.assertEqual(got["inputs_digest"], self.att["inputs_digest"])
        self.assertIn("tables", got)
        self.assertIn("charts", got)

    def test_unknown_run_and_traversal_safe(self):
        self.assertFalse(load_run_cashflow_set(self.jobs, "nope")["ok"])
        self.assertFalse(load_run_cashflow_set(
            self.jobs, "../../etc/passwd")["ok"])

    def test_pre_cf2_run_reports_no_set(self):
        _persist(self.jobs, _job_record("old", None))
        got = load_run_cashflow_set(self.jobs, "old")
        self.assertFalse(got["ok"])
        self.assertIn("no persisted cash-flow set", got["errors"][0])

    def test_digest_mismatch_refused(self):
        att = dict(self.att)
        att["inputs_digest"] = "0" * 64
        _persist(self.jobs, _job_record("bad", att))
        got = load_run_cashflow_set(self.jobs, "bad")
        self.assertFalse(got["ok"])
        self.assertIn("digest", got["errors"][0])

    def test_missing_cache_file_refused(self):
        att = dict(self.att)
        att["dir"] = os.path.join(self.tmp, "gone")
        _persist(self.jobs, _job_record("lost", att))
        self.assertFalse(load_run_cashflow_set(self.jobs, "lost")["ok"])


class TestRegistryAndCompareSurfacing(unittest.TestCase):
    def _entries(self, att_a, att_b):
        return (_entry_from_record(_job_record("a", att_a)),
                _entry_from_record(_job_record("b", att_b)))

    def test_entry_surfaces_attachment(self):
        att = {"ok": True, "schema": CF_RUN_SCHEMA_VERSION,
               "inputs_digest": "d" * 64, "dir": "/x/cashflow_set"}
        ea, eb = self._entries(att, None)
        self.assertTrue(ea["cashflow_set"]["available"])
        self.assertEqual(ea["cashflow_set"]["inputs_digest"], "d" * 64)
        self.assertFalse(eb["cashflow_set"]["available"])

    def test_compare_notes_same_and_differing_sets(self):
        tmp = tempfile.mkdtemp(prefix="cf2_")
        self.addCleanup(shutil.rmtree, tmp, True)
        jobs = os.path.join(tmp, "jobs")
        att1 = {"ok": True, "inputs_digest": "d" * 64, "dir": "/x"}
        att2 = {"ok": True, "inputs_digest": "e" * 64, "dir": "/y"}
        for jid, att in (("a", att1), ("b", att1), ("c", att2), ("d", None)):
            _persist(jobs, _job_record(jid, att))
        same = compare_runs(jobs, "a", "b")
        self.assertTrue(any("SAME persisted cash-flow" in n
                            for n in same["notes"]))
        diff = compare_runs(jobs, "a", "c")
        self.assertTrue(any("cash-flow sets DIFFER" in n
                            for n in diff["notes"]))
        one = compare_runs(jobs, "a", "d")
        self.assertTrue(any("only one side carries a persisted cash-flow" in n
                            for n in one["notes"]))


class TestExecuteRunHook(unittest.TestCase):
    def test_execute_run_source_wires_attachment(self):
        # the hook itself is exercised in the live e2e; here we lock the
        # contract: execute_run carries a cashflow_set block and the
        # attachment call sits AFTER the artifacts are stamped
        import inspect
        from par_model_v2.viewer import igui_run_execution as mod
        src = inspect.getsource(mod.execute_run)
        self.assertIn("attach_cashflow_set_for_run", src)
        self.assertIn('"cashflow_set": cf_att', src)
        self.assertLess(src.index("stamped run-gate provenance"),
                        src.index("attach_cashflow_set_for_run"))


class TestPagePlumbing(unittest.TestCase):
    def test_cashflows_page_supports_run_param(self):
        html = render_cashflows_html()
        self.assertIn("RUN_ID", html)
        self.assertIn("/cashflow-data?run=", html)
        self.assertIn('id="run-note"', html)
        # stays self-contained: zero external references
        self.assertNotIn("https://", html)
        self.assertEqual(html.count("http://"),
                         html.count("http://www.w3.org/2000/svg"))

    def test_history_page_has_cfs_button(self):
        html = render_history_html()
        self.assertIn("data-cfs", html)
        self.assertIn("/cashflows?run=", html)

    def test_run_gui_route_serves_per_run_data(self):
        import importlib
        import threading
        import urllib.error
        import urllib.request
        sys.path.insert(0, os.path.join(REPO, "scripts"))
        try:
            run_gui = importlib.import_module("run_gui")
        finally:
            sys.path.pop(0)
        tmp = tempfile.mkdtemp(prefix="cf2_")
        self.addCleanup(shutil.rmtree, tmp, True)
        srv = run_gui.make_server(port=0, out_path=_write_inputs(tmp))
        # bind the jobs dir to a temp registry carrying one CF-2 run
        out = os.path.join(tmp, "run_output")
        jobs = os.path.join(out, "jobs")
        att = attach_cashflow_set_for_run(_write_inputs(tmp), out)
        _persist(jobs, _job_record("r9", att))
        srv.RequestHandlerClass._jobs_dir = lambda self: jobs
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        self.addCleanup(srv.shutdown)
        base = "http://127.0.0.1:%d" % srv.server_address[1]
        with urllib.request.urlopen(base + "/cashflow-data?run=r9") as r:
            got = json.loads(r.read().decode("utf-8"))
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["run_id"], "r9")
        self.assertIn("run_note", got)
        try:
            urllib.request.urlopen(base + "/cashflow-data?run=missing")
            self.fail("expected HTTP 422 for unknown run")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 422)
            body = json.loads(exc.read().decode("utf-8"))
            self.assertFalse(body["ok"])


if __name__ == "__main__":
    unittest.main()
