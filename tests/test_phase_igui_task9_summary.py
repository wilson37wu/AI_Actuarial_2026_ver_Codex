"""Phase IGUI Task 9 - tests for the phase summary + consolidated re-audit builder.

These tests are stdlib-only (no model engine / scipy needed). They validate the
deterministic, offline consolidated gate and the documentation invariants:
committed RESULTS-UI byte-identity, governance integrity preserved, the seven-link
input->results chain, and the packaging owner-decision note presence.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build_phase_igui_task9_summary.py"
GOV = REPO / ".claude-dev" / "GOVERNANCE_STORE.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_phase_igui_task9_summary", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTask9Summary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()
        from par_model_v2.governance.audit_trail import GovernanceStore
        cls.store = GovernanceStore.from_json(GOV.read_text(encoding="utf-8"))
        cls.summary = cls.mod.build_summary(cls.store)
        cls.gate = cls.mod.validate_task9_gate(cls.store, cls.summary)

    def test_gate_green(self):
        self.assertTrue(self.gate["ok"], [k for k, v in self.gate["checks"].items() if not v])

    def test_gate_has_thirteen_checks(self):
        self.assertEqual(self.gate["n_checks"], 13)

    def test_ui_app_byte_unchanged(self):
        ra = self.summary["consolidated_reaudit"]
        self.assertTrue(ra["ui_app_byte_unchanged"])
        self.assertEqual(ra["ui_app_sha256"], self.mod.UI_APP_BASELINE_SHA)

    def test_chain_has_seven_links(self):
        self.assertEqual(len(self.summary["chain_inputs_to_results"]), 7)
        tasks = [c["task"] for c in self.summary["chain_inputs_to_results"]]
        self.assertEqual(tasks, ["Task 2", "Task 3", "Task 4", "Task 5",
                                 "Task 6", "Task 7", "Task 8"])

    def test_audit_chain_integrity_preserved(self):
        self.assertTrue(self.store.audit_trail.verify_all())

    def test_python_gates_core_green(self):
        for k in ["task1_design_note", "task2_run_controls", "task3_model_points",
                  "task4_assumptions", "task5_esg", "task6_validation_gating",
                  "task8_results_refresh"]:
            self.assertEqual(self.mod.PY_GATES[k]["result"], "OK")

    def test_task7_block_cause_documented(self):
        self.assertIn("scipy", self.mod.PY_GATES["task7_run_execution"]["blocked_cause"])

    def test_headline_carried(self):
        self.assertEqual(self.summary["consolidated_reaudit"]["headline_scr_carried"],
                         self.mod.HEADLINE)

    def test_offline_battery_offline(self):
        b = self.summary["offline_results_ui_battery"]
        self.assertEqual(b["network_calls"], 0)
        self.assertEqual(b["external_refs"], 0)

    def test_packaging_note_present(self):
        self.assertTrue((REPO / "docs" / "PHASE_IGUI_PACKAGING_OPTIONS_CARD.md").exists())

    def test_no_model_parameter_changes_flag(self):
        self.assertTrue(self.summary["no_model_parameter_changes"])
        self.assertTrue(self.summary["stop_rule_honoured"])

    def test_summary_json_serialisable(self):
        json.dumps(self.summary)


if __name__ == "__main__":
    unittest.main()
