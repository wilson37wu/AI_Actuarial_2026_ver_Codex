"""Tests for Post-Phase-IGUI Task 6 - outer-loop variance-reduction design note (MR-VR-2)."""

from __future__ import annotations

import json
import os

from par_model_v2.projection.outer_loop_efficiency_design import (
    CANDIDATE_ID,
    COMPLETED_PRIOR_CANDIDATE_ID,
    COMPLETED_POOL,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    INNER_LOOP_VR_RESULTS,
    MIN_VARIANCE_REDUCTION_RATIO,
    NESTED_PATHWISE_SCR_REFERENCE,
    NEXT_CANDIDATE_ID,
    OUTER_RQMC_PRECEDENTS,
    VR_TECHNIQUES,
    acceptance_gates,
    design_note,
    validate_design_note,
)
import scripts.build_postigui_task6_design_note as builder


def test_candidate_identity():
    assert CANDIDATE_ID == "MR-VR-2"
    assert len(VR_TECHNIQUES) == 4
    assert "crude_iid" in VR_TECHNIQUES
    assert "sobol_rqmc" in VR_TECHNIQUES
    assert "control_variate" in VR_TECHNIQUES


def test_frozen_references_bit_identical():
    assert FROZEN_T_COMPONENT_SCR_REFERENCE == 39_975.654628199336
    assert NESTED_PATHWISE_SCR_REFERENCE == 46_638.9
    # the outer target IS the 99.5% quantile, where antithetic was measured INEFFECTIVE
    assert INNER_LOOP_VR_RESULTS["antithetic_q995"] < MIN_VARIANCE_REDUCTION_RATIO
    assert INNER_LOOP_VR_RESULTS["sobol_rqmc_mean_tvog"] > 1.0
    assert len(OUTER_RQMC_PRECEDENTS) >= 4


def test_six_gates_fixed_ids():
    gates = acceptance_gates()
    assert [g["id"] for g in gates] == ["G1", "G2", "G3", "G4", "G5", "G6"]
    g1 = next(g for g in gates if g["id"] == "G1")
    assert "BIT-IDENTICAL" in g1["criterion"]
    g2 = next(g for g in gates if g["id"] == "G2")
    assert "UNBIASED" in g2["criterion"]


def test_stop_rule_and_no_param_change():
    note = design_note()
    assert note["no_model_parameter_changes"] is True
    assert note["touches_copula_structure"] is False
    assert note["implementation_deferred"] is True
    assert note["change_type"] == "governance_change"


def test_validation_gate_ok():
    note = design_note()
    gate = validate_design_note(note)
    assert gate["ok"] is True
    assert gate["n_checks"] >= 18
    assert all(gate["checks"].values())


def test_sequencing_three_candidates():
    note = design_note()
    seq = note["candidate_sequencing"]
    assert seq["selected_now"] == "MR-VR-2"
    assert seq["completed_prior"] == "MR-VR-1"
    assert seq["next_candidate"] == "MR-LONGEV-1"
    assert COMPLETED_PRIOR_CANDIDATE_ID == "MR-VR-1"
    assert NEXT_CANDIDATE_ID == "MR-LONGEV-1"
    assert set(COMPLETED_POOL) == {"MR-CAL-1", "MR-VR-1"}


def test_owner_decision_note_present():
    note = design_note()
    assert "MR-LONGEV-1" in note["owner_decision_note"]
    assert "packaging" in note["owner_decision_note"].lower()


def test_builder_writes_artifacts():
    res = builder.main(use_governance=False)
    assert res["verdict"] == "PASS"
    assert res["gate_ok"] is True
    assert os.path.exists(builder.JSON_PATH)
    assert os.path.exists(builder.MD_PATH)
    assert os.path.exists(builder.CARD_PATH)
    with open(builder.JSON_PATH, encoding="utf-8") as fh:
        loaded = json.load(fh)
    assert loaded["candidate_id"] == "MR-VR-2"
