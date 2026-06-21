"""Phase 31 Task 1 - owner decision package pre-registration tests."""

from __future__ import annotations

import pytest

from par_model_v2.governance.owner_decision_package import (
    ESCALATION_HISTORY,
    ESCALATION_OPTION_ID,
    NO_MODEL_PARAMETER_CHANGES,
    OWNER_OPTION_IDS,
    STOP_RULE_RECORD,
    evidence_pack_registry,
    owner_options,
    signoff_workflow,
    validate_owner_package,
)
from par_model_v2.projection.dependence_roadmap import (
    VINE2_BOOTSTRAP_CI95,
    VINE2_COMPONENT_SCR_BOOTSTRAP_MEAN,
    VINE2_COMPONENT_SCR_POINT,
    VINE2_COPULA_FORM_RESIDUAL_POINT,
)
from par_model_v2.projection.grouped_t_upgrade import (
    COPULA_FORM_RESIDUAL_ABS as FROZEN_T_COPULA_FORM_RESIDUAL_ABS,
)
from par_model_v2.projection.vine_copula_upgrade import (
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    NESTED_PATHWISE_SCR_REFERENCE,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
)
from par_model_v2.projection.vine_tree3_tail_diagnostics import (
    P30T3_TREE3_CI_HI,
    P30T3_TREE3_CI_LO,
    P30T3_TREE3_COMPONENT_MEAN,
)


@pytest.fixture(scope="module")
def pack():
    return evidence_pack_registry()


@pytest.fixture(scope="module")
def options():
    return owner_options()


@pytest.fixture(scope="module")
def workflow():
    return signoff_workflow()


@pytest.fixture(scope="module")
def gate(pack, options, workflow):
    return validate_owner_package(pack, options, workflow)


class TestRegisteredFigures:
    def test_governed_headline_bit_for_bit(self, pack):
        assert pack["governed_headline"]["value"] == FROZEN_T_COMPONENT_SCR_REFERENCE
        assert pack["governed_headline"]["value"] == pytest.approx(39_975.654628199336)

    def test_headline_never_moved(self, pack):
        assert pack["governed_headline"]["move_pct_through_p27_p30"] == 0.0

    def test_vine2_readout(self, pack):
        v2 = pack["disclosed_candidates"]["vine2"]
        assert v2["component_scr_point"] == VINE2_COMPONENT_SCR_POINT
        assert v2["bootstrap_mean"] == VINE2_COMPONENT_SCR_BOOTSTRAP_MEAN
        assert v2["bootstrap_ci95"] == list(VINE2_BOOTSTRAP_CI95)
        assert v2["adopted"] is False

    def test_tree3_bit_identical_zero_strength(self, pack):
        t3 = pack["disclosed_candidates"]["tree3"]
        assert t3["component_scr_point"] == VINE2_COMPONENT_SCR_POINT
        assert t3["bit_identical_to_vine2"] is True
        assert t3["bootstrap_mean"] == P30T3_TREE3_COMPONENT_MEAN
        assert t3["bootstrap_ci95"] == [P30T3_TREE3_CI_LO, P30T3_TREE3_CI_HI]
        assert t3["adopted"] is False

    def test_nested_reference_outside_both_cis(self, pack):
        nr = pack["nested_reference"]
        assert nr["value"] == NESTED_PATHWISE_SCR_REFERENCE
        assert nr["inside_vine2_ci95"] is False
        assert nr["inside_tree3_ci95"] is False

    def test_residual_ladder_values_and_order(self, pack):
        ladder = pack["residual_ladder"]
        vals = [r["copula_form_residual_abs"] for r in ladder]
        assert vals == [
            GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
            FROZEN_T_COPULA_FORM_RESIDUAL_ABS,
            SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
            VINE2_COPULA_FORM_RESIDUAL_POINT,
        ]
        assert all(a > b for a, b in zip(vals, vals[1:]))

    def test_display_roundings_match_task_prompt(self, pack):
        # The design-note display figures pinned in MODEL_DEV_TASK_PROMPT.md.
        assert round(FROZEN_T_COMPONENT_SCR_REFERENCE, 1) == 39_975.7
        assert round(VINE2_COMPONENT_SCR_POINT, 1) == 42_458.6
        assert round(VINE2_COPULA_FORM_RESIDUAL_POINT, 1) == 3_637.3
        assert round(FROZEN_T_COPULA_FORM_RESIDUAL_ABS, 1) == 6_120.2
        assert SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS == 6_114.9
        assert GROUPED_T_COPULA_FORM_RESIDUAL_ABS == 10_491.5
        assert NESTED_PATHWISE_SCR_REFERENCE == 46_638.9

    def test_escalation_history_p26_to_p30(self, pack):
        phases = [e["phase"] for e in pack["escalation_history"]]
        assert phases == ["Phase 26", "Phase 27", "Phase 28", "Phase 29", "Phase 30"]
        assert len(ESCALATION_HISTORY) == 5

    def test_stop_rule_record(self, pack):
        sr = pack["risk_register_status"]["stop_rule_record"]
        assert sr["applied"] is True
        assert sr["trigger_met"] is True
        assert sr["governed_headline_move_pct"] == 0.0
        assert sr["tree3_zero_strength"] is True
        assert STOP_RULE_RECORD["effect"].endswith("ENDS")

    def test_mr_registers_open(self, pack):
        rr = pack["risk_register_status"]
        assert rr["MR-016"].startswith("OPEN")
        assert rr["MR-017"].startswith("OPEN")


class TestOwnerOptions:
    def test_exactly_three_pre_registered(self, options):
        assert tuple(options.keys()) == OWNER_OPTION_IDS
        assert len(OWNER_OPTION_IDS) == 3

    def test_each_option_has_at_least_three_criteria(self, options):
        for o in options.values():
            assert len(o["acceptance_criteria"]) >= 3

    def test_o1_capital_effect_is_adoption_delta(self, options):
        o1 = options["O1_adopt_disclosed_vine_readout"]
        assert o1["capital_effect_abs"] == pytest.approx(
            VINE2_COMPONENT_SCR_POINT - FROZEN_T_COMPONENT_SCR_REFERENCE)
        assert o1["escalation_path_open"] is False

    def test_o1_requires_signoff_and_mr017_plan(self, options):
        crits = " ".join(options["O1_adopt_disclosed_vine_readout"]["acceptance_criteria"])
        assert "owner sign-off" in crits
        assert "MR-017 mitigation plan" in crits

    def test_o2_zero_capital_tolerance_and_trigger(self, options):
        o2 = options["O2_accept_residual_with_monitoring"]
        assert o2["capital_effect_abs"] == 0.0
        crits = " ".join(o2["acceptance_criteria"])
        assert "TOLERANCE" in crits and "MONITORING TRIGGER" in crits

    def test_o3_is_the_only_open_escalation_path(self, options):
        open_paths = [k for k, o in options.items() if o["escalation_path_open"]]
        assert open_paths == [ESCALATION_OPTION_ID]
        crits = " ".join(options[ESCALATION_OPTION_ID]["acceptance_criteria"])
        assert "pre-registered design note BEFORE the run" in crits
        assert "INDEPENDENT" in crits

    def test_no_option_changes_parameters_this_phase(self):
        assert NO_MODEL_PARAMETER_CHANGES is True


class TestSignoffWorkflow:
    def test_ordered_steps(self, workflow):
        assert [s["step"] for s in workflow] == list(range(1, len(workflow) + 1))
        assert len(workflow) == 6

    def test_owner_makes_the_decision(self, workflow):
        owner_steps = [s for s in workflow if s["actor"] == "model owner"]
        assert len(owner_steps) == 2
        assert any("record the decision" in s["action"] for s in owner_steps)

    def test_independent_review_present(self, workflow):
        assert any("independent" in s["actor"] for s in workflow)

    def test_every_step_cites_standards(self, workflow):
        for s in workflow:
            assert len(s["standards"]) >= 1
        joined = " ".join(st for s in workflow for st in s["standards"])
        assert "IFoA MPN" in joined and "ASOP 56" in joined


class TestValidationGate:
    def test_gate_ok(self, gate):
        assert gate["ok"] is True
        assert gate["n_checks"] >= 18
        assert all(gate["checks"].values())

    def test_gate_catches_headline_tamper(self, options, workflow):
        bad = evidence_pack_registry()
        bad["governed_headline"]["value"] = 40_000.0
        g = validate_owner_package(bad, options, workflow)
        assert g["ok"] is False
        assert g["checks"]["headline_matches_frozen_t"] is False

    def test_gate_catches_adoption_tamper(self, options, workflow):
        bad = evidence_pack_registry()
        bad["disclosed_candidates"]["vine2"]["adopted"] = True
        g = validate_owner_package(bad, options, workflow)
        assert g["checks"]["no_candidate_adopted"] is False

    def test_gate_catches_missing_option(self, pack, workflow):
        bad = owner_options()
        bad.pop(ESCALATION_OPTION_ID)
        g = validate_owner_package(pack, bad, workflow)
        assert g["checks"]["exactly_three_options"] is False

    def test_gate_catches_workflow_disorder(self, pack, options):
        bad = signoff_workflow()
        bad[0]["step"] = 99
        g = validate_owner_package(pack, options, bad)
        assert g["checks"]["workflow_ordered"] is False


class TestBuilder:
    def test_build_design_note_pass(self):
        from scripts.build_phase31_task1_owner_decision_design_note import (
            build_design_note,
        )
        note = build_design_note()
        assert note["verdict"] == "PASS"
        assert note["change_type"] == "governance_change"
        assert note["no_model_parameter_changes"] is True
        assert note["validation_gate"]["ok"] is True
        assert tuple(note["owner_options"].keys()) == OWNER_OPTION_IDS

    def test_markdown_render_contains_key_figures(self):
        from scripts.build_phase31_task1_owner_decision_design_note import (
            _card,
            _md,
            build_design_note,
        )
        note = build_design_note()
        md = _md(note)
        for token in ("39,975.654628", "42,458.5527", "46,638.9", "3,637.3",
                      "O3_fund_second_independent_nested_run", "IFoA MPN"):
            assert token in md
        card = _card(note)
        assert "Three pre-registered options" in card

    def test_json_serialisable(self):
        import json as _json

        from scripts.build_phase31_task1_owner_decision_design_note import (
            build_design_note,
        )
        _json.dumps(build_design_note(), default=float)
