"""Phase 23 Task 4 tests -- aggregation + tail read-outs WITH management actions.

Contract / evidence tests (fast; no nested projection): the heavy realisation
ran in scripts/build_phase23_task4_aggregation_with_actions.py with archived
evidence in docs/validation/PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.governance.audit_trail import GovernanceStore, MitigationStatus
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/validation/PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.json"
T2_REPORT = ROOT / "docs/validation/PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.json"
T3_REPORT = ROOT / "docs/validation/PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.json"
MD = ROOT / "docs/validation/PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.md"
CARD = ROOT / "docs/WITH_ACTIONS_AGGREGATION_CARD.md"
GOV = ROOT / ".claude-dev/GOVERNANCE_STORE.json"

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
CHANGE_TITLE = (
    "Phase 23 Task 4 - seven-driver aggregation + tail read-outs re-run "
    "WITH management actions"
)


@pytest.fixture(scope="module")
def rep():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def t2():
    return json.loads(T2_REPORT.read_text(encoding="utf-8"))["aggregation"]


@pytest.fixture(scope="module")
def store():
    return GovernanceStore.from_json(GOV.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- evidence
class TestEvidenceContract:
    def test_report_exists_and_pass(self, rep):
        assert rep["verdict"] == "PASS"

    def test_all_pre_registered_gates_pass(self, rep):
        assert set(rep["gates"]) == {
            "G1_t_copula_with_actions_gate", "G2_nested_with_le_without",
            "G3_all_standalone_with_le_without", "G4_df_rank_invariance"}
        assert all(rep["gates"].values())

    def test_markdown_and_card_exist(self):
        assert "PASS" in MD.read_text(encoding="utf-8")
        assert "RANK-INVARIANT" in CARD.read_text(encoding="utf-8")

    def test_rule_matches_task3(self, rep):
        t3 = json.loads(T3_REPORT.read_text(encoding="utf-8"))["result"]
        assert rep["rule"] == t3["rule"]
        assert rep["reference_assets"] == pytest.approx(
            t3["reference_assets"], abs=1e-9)
        assert rep["fit_mean_liability"] == pytest.approx(
            t3["fit_mean_liability"], abs=1e-9)

    def test_crosschecks_recorded(self, rep):
        assert rep["crosscheck_count"] == 13

    def test_config_matches_task2(self, rep, t2):
        c = rep["aggregation_with_actions"]["config"]
        assert c["seed"] == t2["config"]["seed"] == 20260607
        assert c["n_sim"] == t2["config"]["n_sim"] == 200_000
        assert list(c["thresholds"]) == list(t2["config"]["thresholds"])

    def test_use_restrictions_educational(self, rep):
        assert rep["use_restrictions"]["classification"] == (
            "EDUCATIONAL_DEMONSTRATION_ONLY")


# ----------------------------------------------------------- capital logic
class TestCapitalReadouts:
    def test_nested_with_le_without(self, rep):
        d, wo = rep["aggregation_with_actions"], rep["without_actions_baseline"]
        assert d["nested_scr"] <= wo["nested_scr"]

    def test_every_standalone_with_le_without(self, rep):
        w = np.array(rep["standalone_scr_with_actions"])
        wo = np.array(rep["without_actions_baseline"]["standalone_scr"])
        assert w.shape == wo.shape == (7,)
        assert np.all(w <= wo + 1e-9)

    def test_var_covar_and_copulas_reduced(self, rep):
        d, wo = rep["aggregation_with_actions"], rep["without_actions_baseline"]
        for k in ("var_covar_scr", "gaussian_scr", "t_matched_scr"):
            assert d[k] < wo[k]

    def test_deltas_consistent(self, rep):
        d, wo = rep["aggregation_with_actions"], rep["without_actions_baseline"]
        for k in ("nested_scr", "var_covar_scr", "gaussian_scr", "t_matched_scr"):
            assert rep["deltas"][k] == pytest.approx(d[k] - wo[k], abs=1e-6)
            assert rep["deltas"][k] < 0.0

    def test_small_drivers_unchanged_by_construction(self, rep):
        # anchored at CR = 1.12 > trigger 1.10: action never fires standalone
        idx = {k: i for i, k in enumerate(DRIVERS)}
        w = rep["standalone_scr_with_actions"]
        wo = rep["without_actions_baseline"]["standalone_scr"]
        for k in ("mortality", "liquidity"):
            assert w[idx[k]] == pytest.approx(wo[idx[k]], abs=1e-6)

    def test_active_share_in_unit_interval(self, rep):
        assert 0.0 < rep["floor_share_full"] < rep["active_share_full"] < 1.0

    def test_t_copula_gate_arms(self, rep):
        d = rep["aggregation_with_actions"]
        assert (d["t_matched_rel_error_vs_nested"]
                <= d["gaussian_rel_error_vs_nested"]
                or d["t_matched_rel_error_vs_nested"] <= 0.25)


# ----------------------------------------------------------- rank invariance
class TestRankInvariance:
    def test_df_matched_identical_to_task2(self, rep, t2):
        assert rep["aggregation_with_actions"]["df_matched"] == pytest.approx(
            t2["df_matched"], abs=1e-9)

    def test_monotone_transform_preserves_ranks_synthetic(self):
        rule = ManagementActionRule()
        rng = np.random.default_rng(7)
        base = 115_996.867
        v = base + rng.normal(0.0, 20_000.0, size=400)
        v = np.clip(v, 1_000.0, None)
        w = rule.apply_to_liabilities(v, rule.reference_assets(base))
        assert np.array_equal(np.argsort(v, kind="stable"),
                              np.argsort(w, kind="stable"))

    def test_rule_monotone_on_realised_range(self, rep):
        rule = ManagementActionRule()
        a_ref = rule.reference_assets(rep["fit_mean_liability"])
        assert rule.is_monotone(a_ref, 50_000.0, 200_000.0)

    def test_scr_translation_invariance_of_anchor(self):
        rng = np.random.default_rng(11)
        x = rng.normal(0.0, 5_000.0, size=256)
        a = capital_metrics_from_liabilities(x, 0.995, 12).scr_proxy
        b = capital_metrics_from_liabilities(x + 115_996.867, 0.995, 12).scr_proxy
        assert a == pytest.approx(b, abs=1e-6)

    def test_relief_bounded_by_max_relief(self):
        rule = ManagementActionRule()
        cr = np.linspace(0.2, 2.0, 1001)
        rf = rule.relief_fraction(cr)
        assert np.all(rf >= -1e-12) and np.all(rf <= rule.max_relief + 1e-12)


# ----------------------------------------------------------------- governance
class TestGovernance:
    def test_change_record_owner_review(self, rep, store):
        rec = next(r for r in store.change_records if r.title == CHANGE_TITLE)
        assert rec.record_id == rep["change_record_id"]
        status = rec.status.value if hasattr(rec.status, "value") else str(rec.status)
        assert "OWNER_REVIEW" in status.upper()
        assert rec.change_type == "methodology_change"

    def test_mr010_mr014_refreshed_and_mitigated(self, rep, store):
        assert rep["mr010_refreshed"] and rep["mr014_refreshed"]
        for rid, frag in (("MR-010", "Task 4 refresh"), ("MR-014", "Task 4")):
            risk = store.risk_register.get(rid)
            assert risk.mitigation_status == MitigationStatus.MITIGATED
            assert frag in (risk.notes or "")

    def test_audit_chain_integrity(self, rep, store):
        assert rep["audit_integrity_ok"] is True
        assert store.audit_trail.verify_all() is True

    def test_audit_entry_for_run(self, rep, store):
        run_id = rep["aggregation_with_actions"]["run_id"]
        assert any(run_id in json.dumps(e.to_dict(), default=str)
                   for e in store.audit_trail.entries)


# ------------------------------------------------------------------ fail path
class TestFailPath:
    def test_gate_fails_on_bad_verdict(self):
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location(
            "b_p23t4", ROOT / "scripts/build_phase23_task4_aggregation_with_actions.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        z = {"nested_scr": np.array([100.0])}
        w = {"nested_scr_with": np.array([150.0]),  # WORSE than without
             "standalone_scr_with": np.array([1.0]),
             "standalone_scr_without": np.array([2.0])}
        d_bad = {"verdict": "FAIL", "df_matched": 99.0}
        g = mod._gates(d_bad, z, w)
        assert not g["G1_t_copula_with_actions_gate"]
        assert not g["G2_nested_with_le_without"]
        assert not g["G4_df_rank_invariance"]

    def test_monotonicity_guard_still_rejects_steep_band(self):
        with pytest.raises(ValueError):
            ManagementActionRule(cr_trigger=1.10, cr_floor=1.05)
