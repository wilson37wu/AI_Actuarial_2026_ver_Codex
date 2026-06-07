"""Phase 24 Task 2 tests -- joint-scenario (action-after-aggregation) re-aggregation.

Contract / evidence tests (fast; no projection): the staged build ran in
scripts/build_phase24_task2_joint_action_reaggregation.py with archived
evidence in docs/validation/PHASE24_TASK2_JOINT_ACTION_REAGGREGATION_REPORT.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.governance.audit_trail import GovernanceStore
from par_model_v2.projection.joint_action_aggregation import (
    JOINT_REL_ERROR_GATE,
    STANDALONE_ACTION_REL_ERROR_BASELINE,
    JointActionAggregator,
    JointActionConfig,
)
from par_model_v2.projection.management_actions import ManagementActionRule

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/validation/PHASE24_TASK2_JOINT_ACTION_REAGGREGATION_REPORT.json"
MD = ROOT / "docs/validation/PHASE24_TASK2_JOINT_ACTION_REAGGREGATION_REPORT.md"
CARD = ROOT / "docs/JOINT_ACTION_AGGREGATION_CARD.md"
T2_REPORT = ROOT / "docs/validation/PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.json"
T4_REPORT = ROOT / "docs/validation/PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.json"
GOV = ROOT / ".claude-dev/GOVERNANCE_STORE.json"

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
CHANGE_TITLE = (
    "Phase 24 Task 2 - joint-scenario (action-after-aggregation) "
    "t-copula re-aggregation vs nested-with-actions"
)


@pytest.fixture(scope="module")
def rep():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def t2():
    return json.loads(T2_REPORT.read_text(encoding="utf-8"))["aggregation"]


@pytest.fixture(scope="module")
def t4():
    return json.loads(T4_REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def store():
    return GovernanceStore.from_json(GOV.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- evidence
class TestEvidenceContract:
    def test_report_exists_and_pass(self, rep):
        assert rep["verdict"] == "PASS"

    def test_all_pre_registered_gates_pass(self, rep):
        assert set(rep["gates"]) == {
            "G1_joint_t_rel_error_le_10pct",
            "G2_joint_t_strictly_below_standalone_baseline",
            "G3_df_rank_invariance",
            "G4_archive_crosschecks_pass"}
        assert all(rep["gates"].values())

    def test_gate_constants_match_module(self, rep):
        c = rep["pre_registered_gate_constants"]
        assert c["JOINT_REL_ERROR_GATE"] == JOINT_REL_ERROR_GATE
        assert (c["STANDALONE_ACTION_REL_ERROR_BASELINE"]
                == STANDALONE_ACTION_REL_ERROR_BASELINE)

    def test_markdown_and_card_exist(self, rep):
        md = MD.read_text(encoding="utf-8")
        card = CARD.read_text(encoding="utf-8")
        assert rep["verdict"] in md and "action-after-aggregation" in md.lower()
        assert "EDUCATIONAL_DEMONSTRATION_ONLY" in card

    def test_drivers_and_n_obs(self, rep):
        assert tuple(rep["drivers"]) == DRIVERS
        assert rep["n_obs"] == 160

    def test_crosschecks_recorded(self, rep):
        assert rep["crosscheck_count"] == 25

    def test_use_restrictions_present(self, rep):
        ur = rep["use_restrictions"]
        assert ur["classification"] == "EDUCATIONAL"
        assert any("NOT for production" in r for r in ur["restrictions"])


# ------------------------------------------------------------ gate numerics
class TestGateNumerics:
    def test_t_rel_error_within_pre_registered_gates(self, rep):
        t_rel = rep["joint_action"]["t_rel"]
        assert t_rel <= JOINT_REL_ERROR_GATE
        assert t_rel < STANDALONE_ACTION_REL_ERROR_BASELINE

    def test_rel_error_consistent_with_scrs(self, rep):
        d = rep["joint_action"]
        expect = abs(d["t_scr"] - rep["nested_scr_with"]) / rep["nested_scr_with"]
        assert d["t_rel"] == pytest.approx(expect, rel=1e-9)

    def test_saturation_gap_closed_vs_p23t4_baseline(self, rep, t4):
        base = t4["aggregation_with_actions"]["t_matched_rel_error_vs_nested"]
        assert rep["standalone_action_baseline_p23t4"][
            "t_matched_rel_error_vs_nested"] == pytest.approx(base)
        assert rep["joint_action"]["t_rel"] < base

    def test_gaussian_joint_improves_on_gaussian_standalone(self, rep, t4):
        assert (rep["joint_action"]["g_rel"]
                < t4["aggregation_with_actions"]["gaussian_rel_error_vs_nested"])

    def test_nested_with_matches_p23t4_reference(self, rep, t4):
        assert rep["nested_scr_with"] == pytest.approx(
            t4["aggregation_with_actions"]["nested_scr"], abs=1e-3)

    def test_df_rank_invariance_vs_p23t2(self, rep, t2):
        assert rep["df_matched"] == pytest.approx(t2["df_matched"], abs=1e-9)
        assert round(rep["df_rematched"], 4) == pytest.approx(rep["df_matched"])

    def test_joint_action_only_relieves(self, rep):
        d = rep["joint_action"]
        assert d["joint_action_only_relieves"] is True
        assert d["t_scr"] <= d["t_scr_without"] + 1e-9

    def test_joint_without_close_to_archived_t_without(self, rep, t2):
        # Monte-Carlo seed-path difference only: same dependence basis.
        assert abs(rep["joint_action"]["t_without_diff_pct"]) < 0.05
        assert rep["archived_t_without"] == pytest.approx(t2["t_matched_scr"])

    def test_active_share_in_unit_interval_and_plausible(self, rep):
        d = rep["joint_action"]
        assert 0.0 < d["floor_share"] <= d["active_share"] < 1.0

    def test_rule_matches_governed_defaults(self, rep):
        assert rep["rule"] == ManagementActionRule().to_dict()

    def test_seed_and_nsim_match_archived_convention(self, rep):
        assert rep["joint_action"]["t_config"]["n_sim"] == 200_000
        assert rep["joint_action"]["t_config"]["seed"] == 20260607
        assert rep["joint_action"]["g_config"]["copula"] == "gaussian"

    def test_reproducibility_digests_present(self, rep):
        assert len(rep["reproducibility_digest"]) == 64
        assert len(rep["joint_action"]["t_digest"]) == 12
        assert rep["joint_action"]["t_digest"] != rep["joint_action"]["g_digest"]


# ------------------------------------------------------------- governance
class TestGovernance:
    def test_change_record_owner_review(self, rep, store):
        rec = next(r for r in store.change_records if r.title == CHANGE_TITLE)
        assert rec.record_id == rep["change_record_id"]
        status = rec.status.value if hasattr(rec.status, "value") else str(rec.status)
        assert status == "OWNER_REVIEW" == rep["change_record_status"]
        assert rec.change_type == "methodology_change"

    def test_audit_chain_intact(self, rep, store):
        assert rep["audit_integrity_ok"] is True
        assert store.audit_trail.verify_all() is True

    def test_mr_refresh_flags_and_notes(self, rep, store):
        assert rep["mr010_refreshed"] and rep["mr014_refreshed"]
        assert "Phase 24 Task 2" in store.risk_register.get("MR-010").notes
        assert "Phase 24 Task 2" in store.risk_register.get("MR-014").notes

    def test_change_snapshots_quantified(self, store):
        rec = next(r for r in store.change_records if r.title == CHANGE_TITLE)
        assert rec.before_snapshot["t_matched_rel_error_vs_nested"] > \
            rec.after_snapshot["t_joint_rel_error_vs_nested"]


# ---------------------------------------------------- behaviour (synthetic)
class TestSyntheticBehaviour:
    def test_joint_action_reduces_tail_on_synthetic_losses(self):
        rng = np.random.default_rng(7)
        losses = {"a": rng.lognormal(9.0, 0.5, 300), "b": rng.lognormal(8.8, 0.6, 300)}
        agg = JointActionAggregator(
            standalone_losses=losses,
            correlation=np.array([[1.0, 0.5], [0.5, 1.0]]),
            rule=ManagementActionRule(),
            l_fit=100_000.0,
        )
        res = agg.run(JointActionConfig(n_sim=20_000, seed=3, df=3.0))
        assert res.scr_joint_with <= res.scr_joint_without + 1e-9
        assert 0.0 <= res.floor_share <= res.active_share <= 1.0

    def test_synthetic_run_reproducible(self):
        rng = np.random.default_rng(11)
        losses = {"a": rng.lognormal(9.0, 0.4, 200), "b": rng.lognormal(8.9, 0.5, 200)}
        agg = JointActionAggregator(
            standalone_losses=losses,
            correlation=np.array([[1.0, 0.4], [0.4, 1.0]]),
            rule=ManagementActionRule(),
            l_fit=90_000.0,
        )
        r1 = agg.run(JointActionConfig(n_sim=10_000, seed=5, df=4.0))
        r2 = agg.run(JointActionConfig(n_sim=10_000, seed=5, df=4.0))
        assert r1.digest == r2.digest
        assert r1.var_joint_with == r2.var_joint_with
