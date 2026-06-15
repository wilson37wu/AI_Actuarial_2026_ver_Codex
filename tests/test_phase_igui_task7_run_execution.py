"""Phase IGUI Task 7 - unittests for end-to-end run + results handoff.

Covers: gate verification (a missing / blocked / tampered gate is refused; a
CLEARED gate on the exact gated inputs is accepted); the run_model.py command
builder (smoke overlay vs base); a real end-to-end SMOKE run (gate -> run ->
capture -> digest-carried-into-provenance -> user_run handoff); the refusal path
spawns nothing; the offline RESULTS UI (ui_app.html) stays byte-unchanged; the
self-contained run page (no external refs, Run blocked by default); and the
pre-registered Task-7 gate. Standard-library only; mirrors the Task-6 test style.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from par_model_v2.viewer import igui_run_execution as X  # noqa: E402
from par_model_v2.viewer import igui_validation_gating as G  # noqa: E402


def _gated():
    return X._clean_gated_inputs()


class TestGateVerification(unittest.TestCase):
    def test_missing_gate_refused(self):
        v = X.verify_run_gate({"schema_version": X.SCHEMA_VERSION})
        self.assertFalse(v["ok"])
        self.assertTrue(any("no run_gate" in r for r in v["reasons"]))

    def test_non_dict_refused(self):
        self.assertFalse(X.verify_run_gate(None)["ok"])
        self.assertFalse(X.verify_run_gate([1, 2])["ok"])

    def test_cleared_gate_accepted(self):
        v = X.verify_run_gate(_gated())
        self.assertTrue(v["ok"], v["reasons"])
        self.assertEqual(v["decision"], "CLEARED")
        self.assertTrue(v["reproducibility_digest"].startswith("sha256:"))

    def test_tampered_inputs_refused(self):
        mi = _gated()
        mi["run_settings"]["seed"] = int(mi["run_settings"].get("seed", 0)) + 1
        v = X.verify_run_gate(mi)
        self.assertFalse(v["ok"])
        self.assertTrue(any("digest" in r for r in v["reasons"]))

    def test_blocked_decision_refused(self):
        mi = _gated()
        mi["run_gate"]["decision"] = "BLOCKED"
        mi["run_gate"]["run_permitted"] = False
        self.assertFalse(X.verify_run_gate(mi)["ok"])


class TestCommandBuilder(unittest.TestCase):
    def test_base_command(self):
        cmd = X.build_run_command("mi.json", "out", smoke=False)
        self.assertIn("--inputs", cmd)
        self.assertIn("--out", cmd)
        self.assertTrue(any(c.endswith("run_model.py") for c in cmd))
        self.assertNotIn("--no-tail", cmd)

    def test_smoke_overlay(self):
        cmd = X.build_run_command("mi.json", "out", smoke=True)
        self.assertIn("--no-tail", cmd)
        self.assertIn("--n-outer", cmd)
        self.assertIn(str(X.SMOKE_OVERRIDES["n_outer"]), cmd)


class TestStdlibOnly(unittest.TestCase):
    def test_no_forbidden_runtime_import(self):
        mod = os.path.join(_REPO, "par_model_v2", "viewer", "igui_run_execution.py")
        self.assertFalse(X._source_has_forbidden_import(mod))


class TestRunPage(unittest.TestCase):
    def test_self_contained(self):
        page = X.render_run_html()
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        self.assertNotIn("src=", page)

    def test_blocks_run_by_default(self):
        self.assertIn('id="btn-run" type="button" disabled', X.render_run_html())

    def test_carries_headline_and_structure(self):
        page = X.render_run_html()
        self.assertIn(G.GOVERNED_HEADLINE, page)
        self.assertIn(G.FROZEN_COPULA_STRUCTURE, page)


class TestUiAppUnchanged(unittest.TestCase):
    def test_byte_unchanged(self):
        with open(os.path.join(_REPO, "ui_app.html"), "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), X.UI_APP_SHA256)


class TestRefusalSpawnsNothing(unittest.TestCase):
    def test_blocked_gate_writes_no_artifact(self):
        tmp = tempfile.mkdtemp(prefix="igui7t_")
        inp = os.path.join(tmp, "model_inputs.json")
        with open(inp, "w", encoding="utf-8") as fh:
            json.dump({"schema_version": X.SCHEMA_VERSION}, fh)
        out = os.path.join(tmp, "out")
        res = X.execute_run(inp, out, smoke=True, repo_root=_REPO)
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "run_gate_not_cleared")
        self.assertFalse(os.path.exists(os.path.join(out, X.SUMMARY_NAME)))

    def test_missing_inputs(self):
        res = X.execute_run("/no/such/model_inputs.json", "/tmp/x_out",
                            smoke=True, repo_root=_REPO)
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "inputs_missing")


class TestEndToEndSmoke(unittest.TestCase):
    """A real gate -> run -> capture -> handoff smoke run (slower; ~10s)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="igui7e2e_")
        cls.inp = os.path.join(cls.tmp, "model_inputs.json")
        with open(cls.inp, "w", encoding="utf-8") as fh:
            json.dump(_gated(), fh, indent=1)
        cls.out = os.path.join(cls.tmp, "out")
        cls.res = X.execute_run(cls.inp, cls.out, smoke=True, repo_root=_REPO)

    def test_run_completed(self):
        self.assertTrue(self.res["ok"], self.res.get("errors"))
        self.assertEqual(self.res["stage"], "run_complete")

    def test_headline_present(self):
        self.assertTrue(self.res["headline"]["nested_scr"])

    def test_artifacts_written(self):
        self.assertTrue(os.path.exists(os.path.join(self.out, X.SUMMARY_NAME)))
        self.assertTrue(os.path.exists(os.path.join(self.out, X.AGG_REPORT_NAME)))

    def test_digest_carried_into_provenance(self):
        with open(os.path.join(self.out, X.SUMMARY_NAME), encoding="utf-8") as fh:
            summ = json.load(fh)
        prov = summ.get("run_gate_provenance") or {}
        self.assertEqual(prov.get("reproducibility_digest"),
                         self.res["reproducibility_digest"])
        self.assertTrue(prov["reproducibility_digest"].startswith("sha256:"))
        self.assertTrue(prov.get("smoke_run"))

    def test_handoff_user_run_contract(self):
        ur = self.res["handoff"]["user_run"]
        # the SAME keys build_ui_data._build_user_run carries verbatim
        for key in ("headline", "run_plan", "inputs_provenance"):
            self.assertIn(key, ur)
        self.assertEqual(ur["reproducibility_digest"],
                         self.res["reproducibility_digest"])

    def test_ui_app_still_unchanged_after_run(self):
        with open(os.path.join(_REPO, "ui_app.html"), "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), X.UI_APP_SHA256)


class TestTask7Gate(unittest.TestCase):
    def test_gate_green(self):
        g = X.validate_task7_gate(_REPO, run_live=True)
        self.assertTrue(g["ok"], [k for k, v in g["checks"].items() if not v])
        self.assertGreaterEqual(g["n_checks"], 19)


if __name__ == "__main__":
    unittest.main()
