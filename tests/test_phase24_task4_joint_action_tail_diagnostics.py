"""Tests for Phase 24 Task 4 -- joint-action tail diagnostics + delta matrix."""
import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.governance.audit_trail import GovernanceStore, MitigationStatus
from par_model_v2.projection.joint_action_aggregation import (
    JointActionAggregator,
    JointActionConfig,
)
from par_model_v2.projection.joint_action_tail_diagnostics import (
    BOOTSTRAP_N_SIM,
    BOOTSTRAP_REPLICATES,
    CONFIDENCE_SWEEP,
    CONVERGENCE_PREFIXES,
    SEED_STABILITY_SEEDS,
    bootstrap_margin_ci,
    build_delta_matrix,
    confidence_sweep_with_saturation,
    prefix_convergence,
    seed_stability,
)
from par_model_v2.projection.management_actions import ManagementActionRule

REPORT = Path("docs/validation/PHASE24_TASK4_JOINT_ACTION_TAIL_DIAGNOSTICS_REPORT.json")
P24T2_REPORT = Path("docs/validation/PHASE24_TASK2_JOINT_ACTION_REAGGREGATION_REPORT.json")
P23T4_REPORT = Path("docs/validation/PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.json")
GOV = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = (
    "Phase 24 Task 4 - joint-action tail diagnostics + with-vs-without / "
    "joint-vs-standalone capital-delta matrix"
)


@pytest.fixture(scope="module")
def rep():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p24t2():
    return json.loads(P24T2_REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def store():
    return GovernanceStore.from_json(GOV.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def toy_agg():
    rng = np.random.default_rng(7)
    losses = {
        "a": 100_000.0 + 8_000.0 * rng.standard_normal(160),
        "b": 100_000.0 + 6_000.0 * rng.standard_normal(160),
    }
    R = np.array([[1.0, 0.4], [0.4, 1.0]])
    return JointActionAggregator(
        standalone_losses=losses, correlation=R,
        rule=ManagementActionRule(), l_fit=100_000.0,
    )


class TestEvidenceContract:
    def test_verdict_pass(self, rep):
        assert rep["verdict"] == "PASS"

    def test_all_gates_pass(self, rep):
        assert all(rep["gates"].values())
        assert set(rep["gates"]) == {
            "G1_delta_matrix_complete_and_crosschecked",
            "G2_var_covar_understatement_refreshed",
            "G3_reproducibility_recorded",
        }

    def test_crosschecks_before_compute(self, rep):
        assert rep["crosscheck_count"] >= 25

    def test_delta_matrix_levels(self, rep):
        assert set(rep["delta_matrix"]) == {
            "nested", "t_copula", "gaussian", "var_covar"}

    def test_reproduction_bit_identical(self, rep):
        r = rep["reproduction_of_p24t2"]
        assert r["t_scr_abs_diff"] < 1e-9
        assert r["g_scr_abs_diff"] < 1e-9
        assert r["t_digest_match"] and r["g_digest_match"]

    def test_reproducibility_fields(self, rep):
        assert rep["seed"] == 20260607
        assert rep["n_sim"] == 200_000
        assert len(rep["reproducibility_digest"]) == 64
        assert rep["tail_diagnostics"]["bootstrap"]["seed"] == 20260608

    def test_diagnostics_are_disclosed_not_gated(self, rep):
        # no post-hoc numeric acceptance thresholds on the diagnostics
        assert "no gate-shopping" in rep["gate_note"]
        for k in rep["gates"]:
            assert "saturation" not in k and "bootstrap" not in k


class TestDeltaMatrixNumbers:
    def test_joint_scr_matches_p24t2(self, rep, p24t2):
        ja = rep["delta_matrix"]["t_copula"]["joint_action"]["scr"]
        assert abs(ja - p24t2["joint_action"]["t_scr"]) < 1e-9

    def test_standalone_scr_matches_p23t4(self, rep):
        t4 = json.loads(P23T4_REPORT.read_text(encoding="utf-8"))
        sa = rep["delta_matrix"]["t_copula"]["standalone_action"]["scr"]
        assert abs(
            sa - t4["aggregation_with_actions"]["t_matched_scr"]) < 1e-9

    def test_joint_vs_standalone_positive_for_t(self, rep):
        # joint-action basis removes the saturation double-count -> higher SCR
        assert rep["delta_matrix"]["t_copula"][
            "joint_minus_standalone_scr"] > 0

    def test_with_actions_below_without_everywhere(self, rep):
        for lv in ("nested", "t_copula", "gaussian"):
            row = rep["delta_matrix"][lv]
            assert row["joint_action"]["scr"] < row["without"]["scr"]

    def test_nested_reference_consistent(self, rep):
        row = rep["delta_matrix"]["nested"]
        assert row["standalone_action"]["scr"] == row["joint_action"]["scr"]

    def test_var_covar_understatement_refreshed(self, rep):
        vc = rep["var_covar_refresh"]
        assert 0.50 < vc["understatement_vs_nested_with"] < 0.60
        assert 0.45 < vc["understatement_vs_t_joint"] < 0.60
        assert vc["understatement_vs_nested_with"] > \
            vc["understatement_vs_nested_without_basis_p22t4"]


class TestTailDiagnostics:
    def test_sweep_monotone(self, rep):
        s = rep["tail_diagnostics"]["confidence_sweep"]
        v = [r["var_with"] for r in s]
        assert v == sorted(v)
        assert [r["confidence"] for r in s] == list(CONFIDENCE_SWEEP)

    def test_saturation_increases_with_confidence(self, rep):
        s = rep["tail_diagnostics"]["confidence_sweep"]
        sat = [r["tail_saturation_share"] for r in s]
        assert sat[-1] >= sat[0]
        assert rep["diagnostic_findings"]["tail_saturation_share_at_995"] > 0.9

    def test_prefix_convergence_final_zero(self, rep):
        c = rep["tail_diagnostics"]["prefix_convergence"]
        assert [r["n_sim"] for r in c] == sorted(list(CONVERGENCE_PREFIXES))
        assert c[-1]["scr_rel_delta_vs_full"] == 0.0
        assert c[-2]["scr_rel_delta_vs_full"] < 0.05

    def test_seed_stability_small(self, rep):
        ss = rep["tail_diagnostics"]["seed_stability"]
        assert len(ss["rows"]) == len(SEED_STABILITY_SEEDS)
        assert ss["scr_max_rel_spread"] < 0.10

    def test_bootstrap_contract(self, rep):
        b = rep["tail_diagnostics"]["bootstrap"]
        assert b["n_replicates"] == BOOTSTRAP_REPLICATES
        assert b["n_sim_per_replicate"] == BOOTSTRAP_N_SIM
        assert b["n_obs"] == 160
        for k in ("var_with", "es_with", "scr_with"):
            ci = b[k]
            assert ci["ci_lo_95"] < ci["mean"] < ci["ci_hi_95"]
            assert ci["se"] > 0

    def test_nested_inside_bootstrap_ci(self, rep):
        b = rep["tail_diagnostics"]["bootstrap"]["scr_with"]
        nw = rep["delta_matrix"]["nested"]["joint_action"]["scr"]
        assert b["ci_lo_95"] <= nw <= b["ci_hi_95"]
        assert rep["diagnostic_findings"]["nested_with_inside_bootstrap_ci"]


class TestModuleBehaviour:
    def test_sweep_function_runs(self, toy_agg):
        s = confidence_sweep_with_saturation(
            toy_agg, 20_000, 42, 4.0, confidences=(0.95, 0.995))
        assert len(s) == 2
        assert s[0]["var_with"] <= s[1]["var_with"] + 1e-9
        for r in s:
            assert r["var_with"] <= r["var_without"] + 1e-9
            assert 0.0 <= r["tail_saturation_share"] <= 1.0

    def test_prefix_convergence_crn(self, toy_agg):
        c = prefix_convergence(toy_agg, 42, 4.0, prefixes=(5_000, 20_000))
        assert c[-1]["var_rel_delta_vs_full"] == 0.0

    def test_seed_stability_function(self, toy_agg):
        ss = seed_stability(toy_agg, 4.0, 20_000, seeds=(1, 2, 3))
        assert len(ss["rows"]) == 3
        assert ss["scr_max_rel_spread"] >= 0.0

    def test_bootstrap_function_deterministic(self, toy_agg):
        kw = dict(
            losses_without=toy_agg.losses, correlation=toy_agg.correlation,
            rule=toy_agg.rule, l_fit=toy_agg.l_fit,
            anchor_means=toy_agg.anchor_means, df=4.0,
            n_replicates=10, n_sim=5_000, seed=99,
        )
        b1 = bootstrap_margin_ci(**kw)
        b2 = bootstrap_margin_ci(**kw)
        assert b1["scr_with"] == b2["scr_with"]

    def test_build_delta_matrix_handles_none(self):
        w = {"nested": {"var": 1.0, "es": 2.0, "scr": 3.0},
             "t_copula": {"var": 1.0, "es": 2.0, "scr": 3.0},
             "gaussian": {"var": 1.0, "es": 2.0, "scr": 3.0},
             "var_covar": {"var": None, "es": None, "scr": 2.0}}
        sa = {"var_covar": {"var": None, "es": None, "scr": 1.0},
              "nested": {"var": 1.0, "es": 2.0, "scr": 2.5},
              "t_copula": {"var": None, "es": None, "scr": 2.0},
              "gaussian": {"var": None, "es": None, "scr": 2.0}}
        ja = {"nested": {"var": 1.0, "es": 2.0, "scr": 2.5},
              "t_copula": {"var": 0.9, "es": 1.9, "scr": 2.4},
              "gaussian": {"var": 0.9, "es": 1.9, "scr": 2.2},
              "var_covar": {"var": None, "es": None, "scr": None}}
        m = build_delta_matrix(w, sa, ja)
        assert m["var_covar"]["joint_action"]["scr"] is None
        assert "joint_minus_standalone_scr" not in m["var_covar"]
        d = m["t_copula"]["joint_action_minus_without"]
        assert abs(d["scr_delta"] - (-0.6)) < 1e-12


class TestGovernance:
    def test_change_record_owner_review(self, store):
        rec = next(r for r in store.change_records if r.title == CHANGE_TITLE)
        status = rec.status.value if hasattr(rec.status, "value") else str(rec.status)
        assert "owner" in status.lower() or "OWNER" in status

    def test_mr_notes_refreshed(self, store):
        for rid in ("MR-010", "MR-014"):
            risk = store.risk_register.get(rid)
            assert risk.mitigation_status == MitigationStatus.MITIGATED
            assert "Phase 24" in (risk.notes or "")
        assert "Task 4" in (store.risk_register.get("MR-010").notes or "")

    def test_audit_integrity(self, rep, store):
        assert rep["audit_integrity_ok"] is True
        assert store.audit_trail.verify_all()

    def test_report_governance_fields(self, rep):
        assert rep["mr010_refreshed"] and rep["mr014_refreshed"]
        assert rep["change_record_id"]
