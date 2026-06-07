"""Phase 24 Task 3 tests - inner-path action dynamics (canonical basis).

Covers the cashflow-decomposition module, the matching analytic proxy base,
the fixed pre-registered gates, the evidence report, governance, and the
parallel-run reconciliation (scalar-response variant superseded).
"""

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.governance.audit_trail import GovernanceStore
from par_model_v2.projection.inner_path_action_dynamics import (
    INNER_PATH_OOS_R2_GATE,
    INNER_PATH_VAR_REL_ERROR_GATE,
    apply_inner_path_action,
    deterministic_credit_pv,
    inner_path_monotonicity_check,
    inner_path_use_restrictions,
    inner_pathwise_pv_components_5d,
    validate_inner_path_actions,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_7d import (
    SevenDriverLiquidityProxyValidator,
    seven_driver_proxy_config,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/validation/PHASE24_TASK3_INNER_PATH_ACTION_REPORT.json"
MD = ROOT / "docs/validation/PHASE24_TASK3_INNER_PATH_ACTION_REPORT.md"
CARD = ROOT / "docs/INNER_PATH_ACTION_CARD.md"
VARIANT = ROOT / (
    "docs/validation/"
    "PHASE24_TASK3_INNER_PATH_SCALAR_RESPONSE_VARIANT_REPORT.json")
GOV = ROOT / ".claude-dev/GOVERNANCE_STORE.json"

CANONICAL_TITLE = (
    "Phase 24 Task 3 - inner-path management-action dynamics prototype "
    "(bonus cut on inner-path benefit cashflows)")
VARIANT_TITLE = (
    "Phase 24 Task 3 - inner-path management-action dynamics prototype "
    "(bonus cashflow response)")


@pytest.fixture(scope="module")
def rule():
    return ManagementActionRule()


@pytest.fixture(scope="module")
def rep():
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def store():
    return GovernanceStore.from_json(GOV.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator():
    prod = ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20)
    return SevenDriverLiquidityProxyValidator(prod)


# ---------------------------------------------------------------- unit ----

def test_gate_constants_reexported():
    assert INNER_PATH_OOS_R2_GATE == pytest.approx(0.95)
    assert INNER_PATH_VAR_REL_ERROR_GATE == pytest.approx(0.10)


def test_zero_benefit_base_is_identity(rule):
    l = np.array([80e3, 110e3, 150e3])
    out = apply_inner_path_action(rule, 130e3, l, np.zeros(3))
    assert np.allclose(out, l)


def test_full_liability_base_recovers_outer_node_transform(rule):
    l = np.linspace(60e3, 220e3, 41)
    a_ref = 130e3
    inner = apply_inner_path_action(rule, a_ref, l, l)
    outer = rule.apply_to_liabilities(l, a_ref)
    assert np.allclose(inner, outer)


def test_benefit_base_clipped_to_liability_envelope(rule):
    l = np.array([100e3, 100e3])
    over = apply_inner_path_action(rule, 90e3, l, np.array([5e5, -5e5]))
    same = apply_inner_path_action(rule, 90e3, l, np.array([100e3, 0.0]))
    assert np.allclose(over, same)


def test_no_action_at_or_above_trigger(rule):
    a_ref = 130e3
    l = np.array([a_ref / rule.cr_trigger, a_ref / (rule.cr_trigger + 0.5)])
    out = apply_inner_path_action(rule, a_ref, l, l * 0.8)
    assert np.allclose(out, l)


def test_inner_path_relieves_less_than_outer_node(rule):
    l = np.linspace(125e3, 220e3, 50)  # stressed: CR below trigger
    a_ref = 130e3
    inner = apply_inner_path_action(rule, a_ref, l, 0.8 * l)
    outer = rule.apply_to_liabilities(l, a_ref)
    assert np.all(inner >= outer - 1e-9)
    assert np.any(inner > outer + 1.0)


def test_monotonicity_check_passes_default_rule(rule):
    assert inner_path_monotonicity_check(rule, 130e3, 5e4, 4e5)


def test_monotonicity_check_validates_inputs(rule):
    with pytest.raises(ValueError):
        inner_path_monotonicity_check(rule, 130e3, -1.0, 4e5)
    with pytest.raises(ValueError):
        inner_path_monotonicity_check(rule, 130e3, 5e4, 4e5, betas=(1.5,))


def test_per_path_application_equals_node_level_formula(rule):
    rng = np.random.default_rng(7)
    pv = rng.lognormal(np.log(110e3), 0.25, 500)
    ben = 0.85 * pv
    l_node = float(pv.mean())
    a_ref = 130e3
    cr = rule.coverage_ratio(np.array([l_node]), a_ref)
    relief = float(rule.relief_fraction(cr)[0])
    per_path = float(np.mean(pv - relief * ben))
    node_level = float(apply_inner_path_action(
        rule, a_ref, np.array([l_node]), np.array([float(ben.mean())]))[0])
    assert per_path == pytest.approx(node_level, rel=1e-12)


def test_components_bit_identical_to_archived_pipeline(validator):
    cfg = seven_driver_proxy_config()
    X = validator.states(2, cfg.validation_seed)
    for j in range(2):
        ben, cre = inner_pathwise_pv_components_5d(
            *[float(v) for v in X[j][:5]], 16, validator._rem,
            validator.product, validator.agg.hw_params,
            validator.agg.gbm_params, validator.agg.spread_params,
            validator.agg.correlation, validator.capital_horizon_months,
            1234 + j, validator.agg.equity_guarantee,
            validator.agg.credit_exposure, validator.agg.lapse_exposure,
            validator.agg.mortality_exposure, None)
        orig = validator._pvs_5d(X[j], 16, 1234 + j)
        assert np.array_equal(ben + cre, orig)
        assert np.all(cre >= 0.0)


def test_deterministic_credit_pv_properties(validator):
    cfg = seven_driver_proxy_config()
    X = validator.states(3, cfg.validation_seed)
    a = deterministic_credit_pv(validator, X)
    b = deterministic_credit_pv(validator, X)
    assert np.array_equal(a, b)
    assert np.all(a > 0.0)
    X_hi = X.copy()
    X_hi[:, 2] = X_hi[:, 2] + 0.02  # higher spread -> higher credit loss
    assert np.all(deterministic_credit_pv(validator, X_hi) > a)


def test_validate_inner_path_actions_synthetic(rule):
    rng = np.random.default_rng(11)
    nested = rng.lognormal(np.log(115e3), 0.18, 400)
    proxy = nested * (1.0 + rng.normal(0.0, 0.01, 400))
    val_t = rng.lognormal(np.log(115e3), 0.18, 60)
    val_p = val_t * (1.0 + rng.normal(0.0, 0.01, 60))
    res = validate_inner_path_actions(
        rule, float(nested.mean()), val_t, val_p, nested, proxy,
        0.84 * val_t, 0.84 * nested, 0.84 * val_p, 0.84 * proxy,
        0.995, 12)
    assert res["verdict"] == "PASS"
    assert res["outer_vs_inner_path_delta"]["nested_scr_delta"] >= 0.0


def test_gate_keys_fixed_pre_registered(rule):
    rng = np.random.default_rng(3)
    l = rng.lognormal(np.log(115e3), 0.15, 200)
    res = validate_inner_path_actions(
        rule, float(l.mean()), l[:50], l[:50], l, l,
        0.8 * l[:50], 0.8 * l, 0.8 * l[:50], 0.8 * l, 0.995, 12)
    assert sorted(res["gates"]) == [
        "G1_identical_action_basis_truth_and_proxy",
        "G2_oos_r2_with_actions_ge_0p95",
        "G3_var_rel_error_with_actions_le_0p10",
        "G4_monotone_on_inner_path_basis",
        "G5_with_le_without_and_no_action_above_trigger",
    ]


def test_use_restrictions_disclose_prototype():
    u = inner_path_use_restrictions()
    assert u["classification"] == "EDUCATIONAL_DEMONSTRATION_ONLY"
    assert any("path-wise" in x for x in [u["rationale"]])
    assert "Production capital or solvency decisions" in u["prohibited_uses"]


# -------------------------------------------------------------- report ----

class TestReport:
    def test_report_exists_and_passes(self, rep):
        assert rep["verdict"] == "PASS"
        assert all(rep["result"]["gates"].values())

    def test_phase22_gates_met(self, rep):
        r = rep["result"]
        assert r["oos_r2_with_actions_inner_path"] >= INNER_PATH_OOS_R2_GATE
        assert (r["var_rel_error_with_actions"]
                <= INNER_PATH_VAR_REL_ERROR_GATE)

    def test_outer_vs_inner_delta_disclosed_and_conservative(self, rep):
        d = rep["result"]["outer_vs_inner_path_delta"]
        assert d["nested_var_99_5_delta"] > 0.0
        assert d["nested_scr_delta"] > 0.0
        assert "conservative" in d["interpretation"]

    def test_without_actions_reference_preserved(self, rep):
        nwo = rep["result"]["nested_capital_without"]
        assert nwo["var_liability"] == pytest.approx(171555.268, abs=0.01)
        assert nwo["scr_proxy"] == pytest.approx(55561.1889, abs=0.01)

    def test_carveout_diagnostics_disclosed(self, rep):
        cd = rep["credit_carveout_diagnostics"]
        assert 0.8 < cd["kappa_fit_calibrated"] < 1.2
        assert cd["val_nodes"]["corr"] > 0.95
        assert cd["nested_nodes"]["corr"] > 0.95
        assert (cd["credit_share_of_liability_nested"]
                + cd["benefit_share_of_liability_nested"]
                == pytest.approx(1.0, abs=1e-9))

    def test_verify_stage_crosschecks_all_pass(self, rep):
        assert all(rep["verify_stage"]["checks"].values())

    def test_markdown_and_card_written(self, rep):
        md = MD.read_text(encoding="utf-8")
        card = CARD.read_text(encoding="utf-8")
        assert "Inner-Path Management-Action" in md
        assert "EDUCATIONAL" in card
        assert rep["reproducibility_digest"][:8] in rep["run_id"]

    def test_residual_documented(self, rep):
        assert "path-wise" in rep["residual_documented"]


# ------------------------------------------- parallel-run reconciliation ----

class TestParallelRunReconciliation:
    def test_reconciliation_disclosed(self, rep):
        pr = rep["parallel_run_reconciliation"]
        assert "scalar" in pr["event"]
        assert any("SUPERSEDED" in x for x in pr["remediation"])

    def test_variant_report_retained(self):
        v = json.loads(VARIANT.read_text(encoding="utf-8"))
        assert v["verdict"] == "PASS"
        assert (v["result"]["config"]["bonus_cashflow_response"]
                == pytest.approx(0.85))

    def test_variant_change_record_superseded(self, store):
        rec = next(
            r for r in store.change_records if r.title == VARIANT_TITLE)
        status = (rec.status.value if hasattr(rec.status, "value")
                  else str(rec.status))
        assert status == "SUPERSEDED"


# ---------------------------------------------------------- governance ----

class TestGovernance:
    def test_canonical_change_record_owner_review(self, rep, store):
        rec = next(
            r for r in store.change_records if r.title == CANONICAL_TITLE)
        assert rec.record_id == rep["change_record_id"]
        status = (rec.status.value if hasattr(rec.status, "value")
                  else str(rec.status))
        assert status == "OWNER_REVIEW" == rep["change_record_status"]
        assert rec.change_type == "assumption_change"

    def test_audit_integrity(self, rep, store):
        assert rep["audit_integrity_ok"] is True
        assert store.audit_trail.verify_all() is True

    def test_mr014_notes_latest_refresh_mentions_inner_path(self, store):
        notes = store.risk_register.get("MR-014").notes
        assert "Phase 24 Task 3" in notes
