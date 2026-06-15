"""Phase IGUI Task 8 - own-run results refresh + one-click launcher tests.

Covers:
  * the USER-results refresh builds a USER copy from synthetic run_output and
    carries the run headline VERBATIM into ``user_run``;
  * the committed zero-install ``ui_app.html`` / ``ui_data.json`` stay
    BYTE-for-byte unchanged across the refresh;
  * graceful fallback when there is no user run;
  * the Task-8 acceptance gate (``validate_task8_gate``);
  * the one-click launcher resolves a localhost launch plan + engine status and
    never starts a server in --self-test.

All stdlib; no model spawn (display layer only); no network.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
SCRIPTS = os.path.join(REPO, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from par_model_v2.viewer import igui_results_refresh as RR  # noqa: E402


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _seed_run_output(dst):
    """Copy the governed sample RUN_MODEL evidence into a fake run_output dir."""
    os.makedirs(dst, exist_ok=True)
    val = os.path.join(REPO, "docs", "validation")
    src_s = os.path.join(val, RR.SUMMARY_NAME)
    src_a = os.path.join(val, RR.AGG_REPORT_NAME)
    shutil.copy2(src_s, os.path.join(dst, RR.SUMMARY_NAME))
    shutil.copy2(src_a, os.path.join(dst, RR.AGG_REPORT_NAME))
    return src_s


class TestResultsRefresh(unittest.TestCase):
    def setUp(self):
        self.committed_html = os.path.join(REPO, "ui_app.html")
        self.committed_json = os.path.join(REPO, "ui_data.json")
        self.html0 = _sha(self.committed_html)
        self.json0 = _sha(self.committed_json)
        self.work = tempfile.mkdtemp(prefix="t8_")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)
        # The committed template files MUST be byte-unchanged after every test.
        self.assertEqual(_sha(self.committed_html), self.html0)
        self.assertEqual(_sha(self.committed_json), self.json0)

    def test_refresh_builds_user_copy_with_verbatim_headline(self):
        run_out = os.path.join(self.work, "run_output")
        src_s = _seed_run_output(run_out)
        user_dir = os.path.join(self.work, "user_results")
        res = RR.refresh_user_results(run_out, user_dir, repo_root=REPO)
        self.assertTrue(res["ok"], res)
        self.assertTrue(os.path.isfile(res["user_html"]))
        self.assertTrue(os.path.isfile(res["user_json"]))
        # USER copy must be a SEPARATE file from the committed template.
        self.assertNotEqual(os.path.abspath(res["user_html"]),
                            os.path.abspath(self.committed_html))
        # Headline carried VERBATIM from the run summary.
        with open(src_s, encoding="utf-8") as fh:
            want = (json.load(fh).get("headline") or {})
        with open(res["user_json"], encoding="utf-8") as fh:
            got = (json.load(fh).get("user_run") or {}).get("headline") or {}
        self.assertTrue(got)
        self.assertEqual(got, want)
        self.assertTrue(res["committed_ui_app_unchanged"])
        self.assertTrue(res["committed_ui_data_unchanged"])

    def test_user_html_is_self_contained_offline(self):
        run_out = os.path.join(self.work, "run_output")
        _seed_run_output(run_out)
        user_dir = os.path.join(self.work, "user_results")
        res = RR.refresh_user_results(run_out, user_dir, repo_root=REPO)
        with open(res["user_html"], encoding="utf-8") as fh:
            html = fh.read()
        # Zero-install discipline: no external network references.
        for bad in ("http://", "https://", "src=\"//", "cdn."):
            self.assertNotIn(bad, html.replace("http://127.0.0.1", "LOCAL"))

    def test_graceful_fallback_no_run(self):
        empty = os.path.join(self.work, "empty")
        os.makedirs(empty, exist_ok=True)
        res = RR.refresh_user_results(empty, os.path.join(self.work, "u"),
                                      repo_root=REPO)
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "no_user_run")
        self.assertTrue(res["committed_ui_app_unchanged"])

    def test_committed_template_unchanged_invariant(self):
        run_out = os.path.join(self.work, "run_output")
        _seed_run_output(run_out)
        RR.refresh_user_results(run_out, os.path.join(self.work, "u"),
                                repo_root=REPO)
        self.assertEqual(_sha(self.committed_html), self.html0)
        self.assertEqual(_sha(self.committed_json), self.json0)

    def test_task8_gate_all_green(self):
        gate = RR.validate_task8_gate(REPO, run_live=True)
        self.assertTrue(gate["ok"], gate)
        self.assertEqual(gate["n_pass"], gate["n_checks"])
        self.assertGreaterEqual(gate["n_checks"], 13)


class TestLauncher(unittest.TestCase):
    def test_build_launch_plan_localhost(self):
        import launch_offline_gui as L
        plan = L.build_launch_plan(0, "model_inputs.json")
        self.assertEqual(plan["host"], "127.0.0.1")
        self.assertTrue(plan["url"].startswith("http://127.0.0.1:"))
        self.assertIn("engine", plan)
        self.assertIn("numpy", plan["engine"]["modules"])

    def test_engine_status_shape(self):
        import launch_offline_gui as L
        st = L.engine_status()
        self.assertIn("engine_ready", st)
        self.assertEqual(set(st["modules"]), {"numpy", "scipy"})

    def test_self_test_starts_no_server(self):
        # --self-test must resolve a plan and exit 0 WITHOUT binding a server.
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "launch_offline_gui.py"),
             "--self-test", "--port", "0"],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertTrue(out["self_test_ok"])
        self.assertEqual(out["host"], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
