"""Phase 31 Task 3 - owner-facing summary tests."""

from __future__ import annotations

import copy
import json

import pytest

from par_model_v2.governance.owner_decision_package import (
    ESCALATION_OPTION_ID,
    NEUTRALITY_FORBIDDEN_PHRASES,
    OWNER_OPTION_IDS,
    PACK_DOC_ID,
    PACK_DOC_VERSION,
    REQUIRED_SUMMARY_SECTIONS,
    SUMMARY_DOC_ID,
    SUMMARY_DOC_VERSION,
    SUMMARY_MAX_WORDS,
    _summary_word_count,
    assemble_owner_pack,
    owner_summary,
    validate_owner_summary,
)


@pytest.fixture(scope="module")
def pack():
    return assemble_owner_pack()


@pytest.fixture(scope="module")
def summary():
    return owner_summary()


@pytest.fixture(scope="module")
def gate(summary):
    return validate_owner_summary(summary)


class TestGate:
    def test_gate_passes(self, gate):
        assert gate["ok"] is True

    def test_gate_has_25_checks(self, gate):
        assert gate["n_checks"] == 25

    def test_every_check_true(self, gate):
        assert all(gate["checks"].values()), [
            k for k, v in gate["checks"].items() if not v]


class TestIdentity:
    def test_summary_id_and_version(self, summary):
        md = summary["metadata"]
        assert md["summary_id"] == SUMMARY_DOC_ID
        assert md["summary_version"] == SUMMARY_DOC_VERSION

    def test_derived_from_the_assembled_pack(self, summary):
        assert summary["metadata"]["derived_from"] == {
            "pack_id": PACK_DOC_ID, "pack_version": PACK_DOC_VERSION}

    def test_educational_no_param_changes(self, summary):
        md = summary["metadata"]
        assert md["classification"] == "EDUCATIONAL"
        assert md["no_model_parameter_changes"] is True

    def test_all_required_sections_present(self, summary):
        for s in REQUIRED_SUMMARY_SECTIONS:
            assert s in summary


class TestFigureFidelity:
    def test_governed_headline_bit_for_bit(self, summary, pack):
        assert (summary["key_figures"]["governed_headline"]
                == pack["evidence_pack"]["governed_headline"]["value"])

    def test_vine_point_and_ci_bit_for_bit(self, summary, pack):
        v2 = pack["evidence_pack"]["disclosed_candidates"]["vine2"]
        assert summary["key_figures"]["disclosed_vine_point"] == v2["component_scr_point"]
        assert summary["key_figures"]["disclosed_vine_ci95"] == list(v2["bootstrap_ci95"])

    def test_nested_bit_for_bit(self, summary, pack):
        nr = pack["evidence_pack"]["nested_reference"]
        assert summary["key_figures"]["nested_reference"] == nr["value"]
        assert summary["key_figures"]["nested_inside_vine_ci95"] == nr["inside_vine2_ci95"]

    def test_residual_and_gap_bit_for_bit(self, summary, pack):
        gap = pack["evidence_pack"]["gap_decomposition"]
        assert summary["key_figures"]["copula_form_residual"] == gap["copula_form_part"]
        assert summary["key_figures"]["total_gap"] == gap["total_gap_point"]

    def test_decision_required_states_the_residual(self, summary, pack):
        gap = pack["evidence_pack"]["gap_decomposition"]
        assert f"{gap['copula_form_part']:,.1f}" in summary["decision_required"]

    def test_no_new_figures_vs_pack(self, summary, pack):
        """Every numeric leaf of key_figures must exist somewhere in the pack."""
        def leaves(node):
            if isinstance(node, dict):
                for v in node.values():
                    yield from leaves(v)
            elif isinstance(node, (list, tuple)):
                for v in node:
                    yield from leaves(v)
            elif isinstance(node, (int, float)) and not isinstance(node, bool):
                yield node
        pack_numbers = set(leaves(pack))
        for x in leaves(summary["key_figures"]):
            assert x in pack_numbers


class TestOptions:
    def test_registry_order(self, summary):
        assert tuple(o["option_id"] for o in summary["options_at_a_glance"]) \
            == OWNER_OPTION_IDS

    def test_option_attributes_from_pack(self, summary, pack):
        for o in summary["options_at_a_glance"]:
            src = pack["owner_options"][o["option_id"]]
            assert o["summary"] == src["what"]
            assert o["capital_effect_abs"] == src["capital_effect_abs"]
            assert o["governance_risk"] == src["governance_risk"]
            assert o["escalation_path_open"] == src["escalation_path_open"]

    def test_only_o3_escalation_open(self, summary):
        for o in summary["options_at_a_glance"]:
            assert o["escalation_path_open"] == (
                o["option_id"] == ESCALATION_OPTION_ID)


class TestNeutrality:
    def test_no_steering_language(self, summary):
        text = json.dumps(summary, default=float).lower()
        for phrase in NEUTRALITY_FORBIDDEN_PHRASES:
            assert phrase not in text

    def test_no_recommendation_keys(self, summary):
        for k in summary.keys():
            assert "recommend" not in k.lower()
            assert "preferred" not in k.lower()

    def test_no_decision_prefilled(self, summary):
        assert "decision_option_id" not in json.dumps(summary, default=float)


class TestWorkflowAndLocation:
    def test_workflow_steps_match_pack(self, summary, pack):
        assert [(w["step"], w["actor"]) for w in summary["what_happens_next"]] \
            == [(s["step"], s["actor"]) for s in pack["signoff_workflow"]]

    def test_points_to_full_pack_and_design_note(self, summary):
        loc = summary["where_to_find_detail"]
        assert loc["full_pack_id"] == PACK_DOC_ID
        assert "PHASE31_TASK2_OWNER_DECISION_PACK" in loc["full_pack_files"]
        assert "PHASE31_TASK1_DESIGN_NOTE" in loc["design_note_files"]

    def test_caveats_cover_single_run_stop_rule_risks(self, summary):
        caveats = " ".join(summary["caveats"]).lower()
        assert "one nested run" in caveats
        assert "stop-rule" in caveats
        assert "mr-016" in caveats and "mr-017" in caveats


class TestOnePage:
    def test_word_cap(self, summary):
        assert _summary_word_count(summary) <= SUMMARY_MAX_WORDS

    def test_word_count_positive(self, summary):
        assert _summary_word_count(summary) > 100


class TestGateRejectsTampering:
    def test_tampered_headline_fails(self, summary):
        bad = copy.deepcopy(summary)
        bad["key_figures"]["governed_headline"] += 1.0
        g = validate_owner_summary(bad)
        assert g["ok"] is False
        assert g["checks"]["governed_headline_bit_for_bit"] is False

    def test_steering_language_fails(self, summary):
        bad = copy.deepcopy(summary)
        bad["caveats"] = list(bad["caveats"]) + ["we recommend option O1"]
        g = validate_owner_summary(bad)
        assert g["ok"] is False
        assert g["checks"]["no_steering_language"] is False

    def test_reordered_options_fail(self, summary):
        bad = copy.deepcopy(summary)
        bad["options_at_a_glance"] = bad["options_at_a_glance"][::-1]
        g = validate_owner_summary(bad)
        assert g["ok"] is False
        assert g["checks"]["options_in_registry_order"] is False

    def test_missing_section_fails(self, summary):
        bad = copy.deepcopy(summary)
        del bad["caveats"]
        g = validate_owner_summary(bad)
        assert g["ok"] is False
        assert g["checks"]["all_required_sections"] is False

    def test_bloated_summary_fails(self, summary):
        bad = copy.deepcopy(summary)
        bad["where_to_find_detail"] = dict(bad["where_to_find_detail"])
        bad["where_to_find_detail"]["padding"] = "lorem " * (SUMMARY_MAX_WORDS + 1)
        g = validate_owner_summary(bad)
        assert g["ok"] is False
        assert g["checks"]["one_page_word_cap"] is False

    def test_prefilled_decision_fails(self, summary):
        bad = copy.deepcopy(summary)
        bad["caveats"] = list(bad["caveats"]) + ['decision_option_id: "O1"']
        g = validate_owner_summary(bad)
        assert g["ok"] is False
        assert g["checks"]["no_decision_prefilled"] is False
