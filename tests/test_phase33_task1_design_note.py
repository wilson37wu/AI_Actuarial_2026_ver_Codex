"""Tests for Phase 33 Task 1 - interactive analytics design note + gate."""

import copy
import json
import os
import unittest

from par_model_v2.viewer.ui_interactive_analytics import (
    BASELINE,
    DOC_ID,
    DOC_VERSION,
    HTML_ARTIFACTS,
    design_note,
    validate_design_note,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestDesignNoteStructure(unittest.TestCase):
    def setUp(self):
        self.note = design_note()

    def test_identity(self):
        self.assertEqual(self.note["metadata"]["doc_id"], DOC_ID)
        self.assertEqual(self.note["metadata"]["doc_version"], DOC_VERSION)

    def test_no_model_parameter_changes_and_stop_rule(self):
        self.assertTrue(self.note["metadata"]["no_model_parameter_changes"])
        self.assertTrue(self.note["metadata"]["stop_rule_honoured"])
        self.assertTrue(self.note["metadata"]["owner_decision_pending"])

    def test_four_gaps_in_priority_order(self):
        gaps = self.note["gaps"]
        self.assertEqual([g["gap_id"] for g in gaps], ["G1", "G2", "G3", "G4"])
        self.assertEqual([g["priority"] for g in gaps], [1, 2, 3, 4])

    def test_every_gap_is_additive_with_criteria(self):
        for g in self.note["gaps"]:
            self.assertIn("ADDITIVE", g["contract_change"])
            self.assertGreaterEqual(len(g["acceptance_criteria"]), 8)

    def test_g1_pins_headline_and_no_new_data(self):
        crits = " | ".join(self.note["gaps"][0]["acceptance_criteria"])
        self.assertIn("39,975.654628199336", crits)
        self.assertIn("no new build-time data", crits)
        self.assertIn("registry order", crits)

    def test_g2_pins_precomputed_grids_and_fallback(self):
        crits = " | ".join(self.note["gaps"][1]["acceptance_criteria"])
        self.assertIn("build time", crits)
        self.assertIn("fallback", crits)

    def test_g3_pins_blank_decision_and_csv_fidelity(self):
        crits = " | ".join(self.note["gaps"][2]["acceptance_criteria"])
        self.assertIn("BLANK", crits)
        self.assertIn("bit-for-bit", crits)

    def test_g4_pins_keyboard_aria_and_no_storage(self):
        crits = " | ".join(self.note["gaps"][3]["acceptance_criteria"])
        self.assertIn("keyboard", crits)
        self.assertIn("ARIA", crits)
        self.assertIn("localStorage", crits)

    def test_baseline_self_tests_green(self):
        for k in ("ui_app_self_test", "offline_viewer_self_test",
                  "combined_gui_self_test", "ui_app_userrun_fallback_test"):
            st = self.note["baseline_audit"][k]
            self.assertTrue(st["ok"])
            self.assertEqual(st["js_errors"], 0)
            self.assertEqual(st["network_calls"], 0)

    def test_baseline_tab_inventory_consistent(self):
        base = self.note["baseline_audit"]
        self.assertEqual(len(base["tabs"]), base["tab_count"])
        self.assertEqual(len(set(base["tabs"])), base["tab_count"])
        self.assertEqual(base["tab_count"], 15)

    def test_baseline_contract_is_phase32_final(self):
        self.assertEqual(self.note["baseline_audit"]["contract_version"], "1.16.0")

    def test_note_is_json_serialisable(self):
        json.dumps(self.note)


class TestGate(unittest.TestCase):
    def setUp(self):
        self.note = design_note()

    def test_gate_passes_against_repo(self):
        gate = validate_design_note(self.note, repo_root=REPO)
        self.assertTrue(gate["ok"], gate["checks"])
        self.assertGreaterEqual(gate["n_checks"], 23)

    def test_gate_fails_on_wrong_doc_id(self):
        bad = copy.deepcopy(self.note)
        bad["metadata"]["doc_id"] = "TAMPERED"
        gate = validate_design_note(bad, repo_root=REPO)
        self.assertFalse(gate["ok"])
        self.assertFalse(gate["checks"]["doc_identity"])

    def test_gate_fails_on_parameter_change_claim(self):
        bad = copy.deepcopy(self.note)
        bad["metadata"]["no_model_parameter_changes"] = False
        self.assertFalse(validate_design_note(bad, repo_root=REPO)["ok"])

    def test_gate_fails_on_dropped_gap(self):
        bad = copy.deepcopy(self.note)
        bad["gaps"] = bad["gaps"][:3]
        gate = validate_design_note(bad, repo_root=REPO)
        self.assertFalse(gate["checks"]["four_gaps"])

    def test_gate_fails_on_non_additive_gap(self):
        bad = copy.deepcopy(self.note)
        bad["gaps"][1]["contract_change"] = "BREAKING 2.0.0"
        gate = validate_design_note(bad, repo_root=REPO)
        self.assertFalse(gate["checks"]["each_gap_additive_only"])

    def test_gate_fails_on_red_baseline(self):
        bad = copy.deepcopy(self.note)
        bad["baseline_audit"]["ui_app_self_test"]["js_errors"] = 3
        gate = validate_design_note(bad, repo_root=REPO)
        self.assertFalse(gate["checks"]["baseline_ui_app_self_test_green"])

    def test_gate_fails_on_contract_version_drift(self):
        bad = copy.deepcopy(self.note)
        bad["baseline_audit"]["contract_version"] = "9.9.9"
        gate = validate_design_note(bad, repo_root=REPO)
        self.assertFalse(gate["checks"]["live_contract_version_match"])

    def test_gate_fails_on_unfrozen_headline(self):
        bad = copy.deepcopy(self.note)
        bad["gaps"][0]["acceptance_criteria"] = [
            c for c in bad["gaps"][0]["acceptance_criteria"]
            if "39,975" not in c]
        gate = validate_design_note(bad, repo_root=REPO)
        self.assertFalse(gate["checks"]["g1_headline_frozen"])

    def test_gate_fails_on_missing_repo(self):
        gate = validate_design_note(self.note, repo_root="/nonexistent")
        self.assertFalse(gate["ok"])

    def test_live_artifacts_exist_and_have_no_external_refs(self):
        for name in HTML_ARTIFACTS:
            self.assertTrue(os.path.exists(os.path.join(REPO, name)), name)
        gate = validate_design_note(self.note, repo_root=REPO)
        self.assertTrue(gate["checks"]["live_zero_external_refs"])

    def test_governance_counts_floor(self):
        gate = validate_design_note(self.note, repo_root=REPO)
        self.assertTrue(gate["checks"]["live_governance_counts_match"])
        self.assertEqual(BASELINE["governance_store"]["risk_register"], 17)


if __name__ == "__main__":
    unittest.main()
