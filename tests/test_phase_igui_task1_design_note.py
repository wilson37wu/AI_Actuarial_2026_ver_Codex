"""Tests for Phase IGUI Task 1 - Actuarial Input & Run GUI design note + gate."""

import copy
import json
import os
import unittest

from par_model_v2.viewer.igui_input_run_gui import (
    BASELINE,
    CHOSEN_ARCHITECTURE,
    DOC_ID,
    DOC_VERSION,
    GOVERNED_HEADLINE,
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

    def test_discipline_flags(self):
        md = self.note["metadata"]
        self.assertTrue(md["no_model_parameter_changes"])
        self.assertTrue(md["stop_rule_honoured"])
        self.assertTrue(md["owner_decision_pending"])
        self.assertTrue(md["zero_install_results_ui_preserved"])

    def test_architecture_chosen_is_stdlib_local_runner(self):
        arch = self.note["architecture_decision"]
        self.assertEqual(arch["chosen"], CHOSEN_ARCHITECTURE)
        self.assertEqual(CHOSEN_ARCHITECTURE, "L2_stdlib_local_runner")
        ids = [o["id"] for o in arch["options"]]
        self.assertEqual(len(ids), 3)
        self.assertIn(CHOSEN_ARCHITECTURE, ids)
        self.assertTrue(arch["results_ui_untouched"])
        self.assertEqual(arch["new_third_party_runtime_deps"], 0)
        self.assertEqual(arch["network_calls"], 0)

    def test_every_architecture_option_has_pros_cons_verdict(self):
        for o in self.note["architecture_decision"]["options"]:
            self.assertTrue(o["pros"])
            self.assertTrue(o["cons"])
            self.assertTrue(o["verdict"])

    def test_coverage_map_six_domains_ordered(self):
        ids = [d["id"] for d in self.note["input_schema_coverage_map"]["domains"]]
        self.assertEqual(ids, [
            "D1_run_controls", "D2_policy_model_points", "D3_assumptions",
            "D4_esg_economic", "D5_validation_gating", "D6_integration"])

    def test_each_domain_has_current_target_gap_task(self):
        for d in self.note["input_schema_coverage_map"]["domains"]:
            self.assertTrue(d["current_coverage"])
            self.assertTrue(d["target"])
            self.assertTrue(d["gap"])
            self.assertTrue(d["task"])

    def test_integration_chain_names_real_plumbing(self):
        chain = self.note["input_schema_coverage_map"]["integration_chain"]
        self.assertIn("model_inputs.json", chain)
        self.assertIn("run_model.py", chain)
        self.assertIn("ui_app.html", chain)

    def test_staged_tasks_one_per_domain(self):
        staged = self.note["staged_tasks"]
        self.assertEqual(len(staged), 6)
        self.assertEqual([t["domain_id"] for t in staged], [
            "D1_run_controls", "D2_policy_model_points", "D3_assumptions",
            "D4_esg_economic", "D5_validation_gating", "D6_integration"])
        for t in staged:
            self.assertGreaterEqual(len(t["acceptance_criteria"]), 7)

    def test_headline_carried_bit_for_bit(self):
        crits = " | ".join(self.note["acceptance_criteria_common"])
        self.assertIn(GOVERNED_HEADLINE, crits)

    def test_baseline_nine_suites_green(self):
        for k in ("ui_app_self_test", "ui_app_evidence_pack_fallback_test",
                  "ui_app_integrity_fallback_test", "ui_app_distribution_fallback_test",
                  "ui_app_userrun_fallback_test", "ui_app_search_deeplink_test",
                  "ui_app_bundle_printall_test", "offline_viewer_self_test",
                  "combined_gui_self_test"):
            st = self.note["baseline_audit"][k]
            self.assertTrue(st["ok"])
            self.assertEqual(st["js_errors"], 0)
            self.assertEqual(st["network_calls"], 0)

    def test_baseline_check_total_consistent(self):
        base = self.note["baseline_audit"]
        total = sum(base[k]["n_checks"] for k in (
            "ui_app_self_test", "ui_app_evidence_pack_fallback_test",
            "ui_app_integrity_fallback_test", "ui_app_distribution_fallback_test",
            "ui_app_userrun_fallback_test", "ui_app_search_deeplink_test",
            "ui_app_bundle_printall_test", "offline_viewer_self_test",
            "combined_gui_self_test"))
        self.assertEqual(total, base["self_test_checks_total"])
        self.assertEqual(total, 522)

    def test_note_is_json_serialisable(self):
        json.dumps(self.note)


class TestGate(unittest.TestCase):
    def setUp(self):
        self.note = design_note()

    def test_gate_passes_against_repo(self):
        gate = validate_design_note(self.note, repo_root=REPO)
        self.assertTrue(gate["ok"], gate["checks"])
        self.assertGreaterEqual(gate["n_checks"], 33)

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

    def test_gate_fails_on_wrong_architecture(self):
        bad = copy.deepcopy(self.note)
        bad["architecture_decision"]["chosen"] = "L3_frozen_binary_bundle"
        # chosen must equal the pre-registered CHOSEN_ARCHITECTURE
        self.assertFalse(
            validate_design_note(bad, repo_root=REPO)["checks"]["architecture_chosen_valid"])

    def test_gate_fails_on_dropped_domain(self):
        bad = copy.deepcopy(self.note)
        bad["input_schema_coverage_map"]["domains"] = \
            bad["input_schema_coverage_map"]["domains"][:5]
        gate = validate_design_note(bad, repo_root=REPO)
        self.assertFalse(gate["checks"]["coverage_six_domains_ordered"])

    def test_gate_fails_on_new_dep_claim(self):
        bad = copy.deepcopy(self.note)
        bad["architecture_decision"]["new_third_party_runtime_deps"] = 3
        self.assertFalse(
            validate_design_note(bad, repo_root=REPO)["checks"]["architecture_no_new_deps"])

    def test_gate_fails_on_red_baseline(self):
        bad = copy.deepcopy(self.note)
        bad["baseline_audit"]["ui_app_self_test"]["js_errors"] = 2
        gate = validate_design_note(bad, repo_root=REPO)
        self.assertFalse(gate["checks"]["baseline_ui_app_self_test_green"])

    def test_gate_fails_on_dropped_headline(self):
        bad = copy.deepcopy(self.note)
        bad["acceptance_criteria_common"] = [
            c for c in bad["acceptance_criteria_common"] if "39,975" not in c]
        gate = validate_design_note(bad, repo_root=REPO)
        self.assertFalse(gate["checks"]["headline_carried_bit_for_bit"])

    def test_gate_fails_on_missing_repo(self):
        gate = validate_design_note(self.note, repo_root="/nonexistent")
        self.assertFalse(gate["ok"])

    def test_live_artifacts_exist_and_zero_external_refs(self):
        for name in HTML_ARTIFACTS:
            self.assertTrue(os.path.exists(os.path.join(REPO, name)), name)
        gate = validate_design_note(self.note, repo_root=REPO)
        self.assertTrue(gate["checks"]["live_zero_external_refs"])

    def test_live_plumbing_present(self):
        gate = validate_design_note(self.note, repo_root=REPO)
        self.assertTrue(gate["checks"]["live_loader_present"])
        self.assertTrue(gate["checks"]["live_orchestrator_present"])

    def test_live_governance_counts_floor(self):
        gate = validate_design_note(self.note, repo_root=REPO)
        self.assertTrue(gate["checks"]["live_governance_counts_floor"])
        self.assertEqual(BASELINE["governance_store"]["risk_register"], 17)


if __name__ == "__main__":
    unittest.main()
