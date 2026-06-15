"""Tests for Post-Phase-IGUI Task 1 - credentialled-data calibration design note."""

from __future__ import annotations

import json
import os

from par_model_v2.calibration.credentialled_residual_design import (
    CANDIDATE_ID,
    COPULA_FORM_RESIDUAL_LADDER,
    FROZEN_DRIVER_MARGINS,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    acceptance_gates,
    design_note,
    validate_design_note,
)
import scripts.build_postigui_task1_design_note as builder


def test_candidate_identity():
    assert CANDIDATE_ID == "MR-CAL-1"
    assert len(FROZEN_DRIVER_MARGINS) == 7


def test_frozen_references_bit_identical():
    assert FROZEN_T_COMPONENT_SCR_REFERENCE == 39_975.654628199336
    assert NESTED_PATHWISE_SCR_REFERENCE == 46_638.9
    assert set(COPULA_FORM_RESIDUAL_LADDER) == {"grouped_t", "frozen_t", "skew_t", "vine2"}
    assert COPULA_FORM_RESIDUAL_LADDER["vine2"] == 3_637.298487404965


def test_six_gates_fixed_ids():
    gates = acceptance_gates()
    assert [g["id"] for g in gates] == ["G1", "G2", "G3", "G4", "G5", "G6"]
    g1 = next(g for g in gates if g["id"] == "G1")
    assert "BIT-IDENTICAL" in g1["criterion"]


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
    assert gate["n_checks"] >= 13
    assert all(gate["checks"].values())


def test_sequencing_three_candidates():
    note = design_note()
    seq = note["candidate_sequencing"]
    assert seq["selected_now"] == "MR-CAL-1"
    assert seq["next_candidate"] == "MR-VR-1"
    assert seq["deferred_candidate"] == "MR-LONGEV-1"


def test_builder_writes_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(builder.__dict__.get("_REPO_ROOT", os.getcwd()))
    res = builder.main(use_governance=False)
    assert res["verdict"] == "PASS"
    assert res["gate_ok"] is True
    assert os.path.exists(builder.JSON_PATH)
    assert os.path.exists(builder.MD_PATH)
    assert os.path.exists(builder.CARD_PATH)
    with open(builder.JSON_PATH, encoding="utf-8") as fh:
        loaded = json.load(fh)
    assert loaded["candidate_id"] == "MR-CAL-1"
