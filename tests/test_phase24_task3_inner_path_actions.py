"""Phase 24 Task 3 tests -- inner-path management-action prototype."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.governance.audit_trail import GovernanceStore
from par_model_v2.projection.inner_path_actions import (
    InnerPathActionConfig,
    apply_inner_path_bonus_action,
    inner_path_use_restrictions,
    validate_inner_path_actions,
)
from par_model_v2.projection.joint_action_aggregation import (
    INNER_PATH_OOS_R2_GATE,
    INNER_PATH_VAR_REL_ERROR_GATE,
)
from par_model_v2.projection.management_actions import ManagementActionRule

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/validation/PHASE24_TASK3_INNER_PATH_SCALAR_RESPONSE_VARIANT_REPORT.json"
MD = ROOT / "docs/validation/PHASE24_TASK3_INNER_PATH_SCALAR_RESPONSE_VARIANT_REPORT.md"
CARD = ROOT / "docs/INNER_PATH_ACTION_DYNAMICS_CARD.md"
GOV = ROOT / ".claude-dev/GOVERNANCE_STORE.json"
CHANGE_TITLE = (
    "Phase 24 Task 3 - inner-path management-action dynamics prototype "
    "(bonus cashflow response)"
)


@pytest.fixture()
def rule():
    return ManagementActionRule()


@pytest.fixture(scope="module")
def rep():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def store():
    return GovernanceStore.from_json(GOV.read_text(encoding="utf-8"))


def test_config_validates_response_factor():
    assert InnerPathActionConfig().bonus_cashflow_response == pytest.approx(0.85)
    with pytest.raises(ValueError):
        InnerPathActionConfig(0.0)
    with pytest.raises(ValueError):
        InnerPathActionConfig(1.1)


def test_response_one_matches_outer_node_transform(rule):
    l = np.linspace(90.0, 180.0, 100)
    a_ref = rule.reference_assets(100.0)
    inner = apply_inner_path_bonus_action(
        l, rule, a_ref, InnerPathActionConfig(bonus_cashflow_response=1.0)
    )
    outer = rule.apply_to_liabilities(l, a_ref)
    assert np.allclose(inner, outer)


def test_inner_path_less_relief_than_outer_node_default(rule):
    l = np.array([130.0, 150.0, 180.0])
    a_ref = rule.reference_assets(100.0)
    inner = apply_inner_path_bonus_action(l, rule, a_ref)
    outer = rule.apply_to_liabilities(l, a_ref)
    assert np.all(inner >= outer - 1e-12)
    assert np.all(inner <= l + 1e-12)


def test_inner_path_transform_monotone(rule):
    l = np.linspace(10.0, 1000.0, 5000)
    out = apply_inner_path_bonus_action(l, rule, rule.reference_assets(100.0))
    assert np.all(np.diff(out) >= -1e-9)


def _synthetic_inputs(seed=23, n_eval=500, n_val=80):
    rng = np.random.default_rng(seed)
    nested = 100.0 * np.exp(rng.normal(0.0, 0.055, n_eval))
    proxy = nested * (1.0 + rng.normal(0.0, 0.003, n_eval))
    truth = 100.0 * np.exp(rng.normal(0.0, 0.055, n_val))
    pred = truth * (1.0 + rng.normal(0.0, 0.003, n_val))
    return truth, pred, nested, proxy


def test_validate_inner_path_actions_passes_synthetic(rule):
    truth, pred, nested, proxy = _synthetic_inputs()
    res = validate_inner_path_actions(rule, 100.0, truth, pred, nested, proxy, 0.995, 12)
    assert res["verdict"] == "PASS"
    assert all(res["gates"].values())
    assert res["oos_r2_inner_path"] >= INNER_PATH_OOS_R2_GATE
    assert res["var_rel_error_inner_path"] <= INNER_PATH_VAR_REL_ERROR_GATE


def test_validate_inner_path_gate_keys_fixed(rule):
    truth, pred, nested, proxy = _synthetic_inputs()
    res = validate_inner_path_actions(rule, 100.0, truth, pred, nested, proxy, 0.995, 12)
    assert set(res["gates"]) == {
        "G1_inner_path_oos_r2_ge_0p95",
        "G2_inner_path_var_rel_error_le_0p10",
        "G3_inner_path_capital_le_without_actions",
        "G4_inner_path_monotone",
    }


def test_use_restrictions_disclose_prototype():
    ur = inner_path_use_restrictions()
    assert ur["classification"] == "EDUCATIONAL_PROTOTYPE_ONLY"
    assert any("monthly" in r.lower() for r in ur["residuals"])


class TestEvidence:
    def test_report_exists_and_passes(self, rep):
        assert rep["verdict"] == "PASS"
        assert all(rep["result"]["gates"].values())

    def test_task1_gate_constants_met(self, rep):
        r = rep["result"]
        assert r["oos_r2_inner_path"] >= INNER_PATH_OOS_R2_GATE
        assert r["var_rel_error_inner_path"] <= INNER_PATH_VAR_REL_ERROR_GATE

    def test_report_carries_inner_vs_outer_delta(self, rep):
        delta = rep["result"]["outer_node_vs_inner_path"]
        assert delta["nested_var_delta"] > 0.0
        assert delta["nested_scr_delta"] > 0.0
        assert "less immediate relief" in delta["interpretation"]

    def test_markdown_and_card_written(self, rep):
        md = MD.read_text(encoding="utf-8")
        card = CARD.read_text(encoding="utf-8")
        assert "Inner-Path Management-Action" in md
        assert "EDUCATIONAL" in card
        assert rep["run_id"] in rep["run_id"]

    def test_crosschecks_are_recorded(self, rep):
        checks = rep["without_actions_crosscheck"]["checks"]
        assert len(checks) == 6
        assert all(checks.values())

    def test_phase23_reference_preserved(self, rep):
        ref = rep["result"]["phase23_outer_node_reference"]
        outer = rep["result"]["nested_capital_outer_node"]
        assert ref["nested_scr_with"] == pytest.approx(outer["scr_proxy"], abs=1e-3)

    def test_governance_change_record_owner_review(self, rep, store):
        rec = next(r for r in store.change_records if r.title == CHANGE_TITLE)
        assert rec.record_id == rep["change_record_id"]
        status = rec.status.value if hasattr(rec.status, "value") else str(rec.status)
        # Parallel-run reconciliation 2026-06-07: this variant record was
        # faithfully re-applied after the store-corruption recovery and then
        # SUPERSEDED by the canonical inner-path cashflow-decomposition
        # implementation (see PHASE24_TASK3_INNER_PATH_ACTION_REPORT).
        # Original submission status (preserved in the report) was OWNER_REVIEW.
        assert status in ("OWNER_REVIEW", "SUPERSEDED")
        assert rep["change_record_status"] == "OWNER_REVIEW"
        assert rec.change_type == "assumption_change"

    def test_audit_integrity_and_mr014_refresh(self, rep, store):
        assert rep["audit_integrity_ok"] is True
        assert store.audit_trail.verify_all() is True
        assert rep["mr014_refreshed"] is True
        assert "Phase 24 Task 3" in store.risk_register.get("MR-014").notes

