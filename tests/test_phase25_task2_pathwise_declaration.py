"""Phase 25 Task 2 tests - path-wise bonus declaration in the nested truth.

Covers the per-time-step declaration mechanics (bit-identical without-actions
basis, envelope guard, degenerate-rule equivalences), the node-level guard,
the fixed pre-registered gates, the evidence report, and governance.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from par_model_v2.governance.audit_trail import GovernanceStore
from par_model_v2.projection.inner_path_action_dynamics import (
    PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD,
    apply_inner_path_action,
    apply_pathwise_declaration_node,
    inner_pathwise_pv_components_5d,
    pathwise_declaration_components_5d,
    pathwise_declaration_use_restrictions,
    validate_pathwise_declaration,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_7d import (
    SevenDriverLiquidityProxyValidator,
    seven_driver_proxy_config,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / (
    "docs/validation/PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.json")
MD = ROOT / "docs/validation/PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.md"
CARD = ROOT / "docs/PATHWISE_DECLARATION_CARD.md"
GOV = ROOT / ".claude-dev/GOVERNANCE_STORE.json"

CHANGE_TITLE = (
    "Phase 25 Task 2 - path-wise bonus declaration in the nested truth "
    "(per-time-step retained-bonus factor on a path-wise coverage proxy)")


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


@pytest.fixture(scope="module")
def small_run(validator, rule):
    """One outer state, 16 inner paths - shared across mechanics tests."""
    cfg = seven_driver_proxy_config()
    v = validator
    X = v.states(cfg.n_eval, cfg.eval_seed)
    row = X[0]
    r, s, c, b, m = (float(x) for x in row[:5])
    args = (r, s, c, b, m, 16, v._rem, v.product, v.agg.hw_params,
            v.agg.gbm_params, v.agg.spread_params, v.agg.correlation,
            v.capital_horizon_months, 20260608,
            v.agg.equity_guarantee, v.agg.credit_exposure,
            v.agg.lapse_exposure, v.agg.mortality_exposure)
    return args


# ------------------------------------------------------------ mechanics ----

def test_without_actions_basis_bit_identical(small_run, rule):
    args = small_run
    ben0, cre0 = inner_pathwise_pv_components_5d(*args)
    res = pathwise_declaration_components_5d(
        *args, rule, 130000.0, node_offset=500.0, horizon_relief=0.05)
    assert np.array_equal(ben0, res["benefit"])
    assert np.array_equal(cre0, res["credit"])


def test_horizon_relief_is_exact_scalar_response(small_run, rule):
    args = small_run
    res = pathwise_declaration_components_5d(
        *args, rule, 130000.0, node_offset=500.0, horizon_relief=0.05)
    assert np.allclose(res["relieved_horizon"], 0.05 * res["benefit"],
                       rtol=1e-12, atol=0.0)


def test_pathwise_relief_within_carveout_envelope(small_run, rule):
    args = small_run
    res = pathwise_declaration_components_5d(
        *args, rule, 130000.0, node_offset=500.0, horizon_relief=0.05)
    env = rule.max_relief * res["benefit"]
    assert np.all(res["relieved_pathwise"] >= -1e-12)
    assert np.all(res["relieved_pathwise"] <= env + 1e-9)


def test_no_action_when_coverage_always_above_trigger(small_run, rule):
    args = small_run
    res = pathwise_declaration_components_5d(
        *args, rule, 1e12, node_offset=500.0, horizon_relief=0.0)
    assert float(np.abs(res["relieved_pathwise"]).max()) == 0.0
    assert res["action_share"] == 0.0
    assert res["restoration_share"] == 0.0


def test_max_cut_when_coverage_always_below_floor(small_run, rule):
    args = small_run
    res = pathwise_declaration_components_5d(
        *args, rule, 1e-3, node_offset=500.0,
        horizon_relief=rule.max_relief)
    assert np.allclose(res["relieved_pathwise"],
                       rule.max_relief * res["benefit"], rtol=1e-10)
    # constant maximum cut == horizon basis at maximum relief
    assert np.allclose(res["relieved_pathwise"], res["relieved_horizon"],
                       rtol=1e-10)


def test_diagnostics_reported(small_run, rule):
    args = small_run
    res = pathwise_declaration_components_5d(
        *args, rule, 130000.0, node_offset=500.0, horizon_relief=0.05)
    assert 0.0 <= res["action_share"] <= 1.0
    assert 0.0 <= res["restoration_share"] <= res["action_share"] + 1e-12
    assert res["cr_path0_min"] > 0.0
    assert res["cr_path0_mean"] >= res["cr_path0_min"]


# ------------------------------------------------------ node-level guard ----

def test_node_guard_clips_to_envelope(rule):
    l = np.array([100e3, 120e3, 150e3])
    b = np.array([60e3, 70e3, 90e3])
    relieved = np.array([1e9, 0.0, 5e3])  # first absurdly large
    out, clip_share = apply_pathwise_declaration_node(rule, l, b, relieved)
    cap = rule.max_relief * b
    assert np.allclose(out[0], l[0] - cap[0])
    assert np.allclose(out[1], l[1])
    assert np.allclose(out[2], l[2] - 5e3)
    assert clip_share == pytest.approx(1.0 / 3.0)


def test_node_guard_negative_relieved_is_identity(rule):
    l = np.array([100e3])
    out, _ = apply_pathwise_declaration_node(
        rule, l, np.array([50e3]), np.array([-1.0]))
    assert np.allclose(out, l)


# ----------------------------------------------------------------- gates ----

def _synthetic_inputs(rule, sign_ok=True):
    rng = np.random.default_rng(7)
    n = 400
    l = 100e3 + 20e3 * rng.standard_normal(n) ** 2
    b = 0.7 * l
    a_ref = rule.reference_assets(float(l.mean()))
    relief_node = rule.relief_fraction(rule.coverage_ratio(l, a_ref))
    env = rule.max_relief * np.clip(b, 0.0, l)
    relieved_hz = relief_node * np.clip(b, 0.0, l)
    if sign_ok:
        # path-wise relieves LESS in the tail (restoration dynamic)
        relieved_pw = 0.6 * relieved_hz
    else:
        # force MORE tail relief than the horizon basis (sign violation):
        # halve the horizon relief and put the path-wise at the envelope
        relieved_hz = 0.5 * relieved_hz
        relieved_pw = env
    return float(l.mean()), l, b, relieved_pw, relieved_hz


def test_validate_pathwise_declaration_pass(rule):
    fit_mean, l, b, pw, hz = _synthetic_inputs(rule, sign_ok=True)
    res = validate_pathwise_declaration(
        rule, fit_mean, l, b, pw, hz, True, 0.995, 12, 0.4, 0.3)
    assert res["verdict"] == "PASS"
    assert all(res["gates"].values())


def test_validate_pathwise_declaration_sign_gate_fails(rule):
    fit_mean, l, b, pw, hz = _synthetic_inputs(rule, sign_ok=False)
    res = validate_pathwise_declaration(
        rule, fit_mean, l, b, pw, hz, True, 0.995, 12, 0.4, 0.3)
    assert not res["gates"]["G2_sign_gate_pathwise_scr_ge_horizon_scr"]
    assert res["verdict"] == "FAIL"  # G5 also fails by construction


def test_validate_bit_identical_flag_is_gated(rule):
    fit_mean, l, b, pw, hz = _synthetic_inputs(rule, sign_ok=True)
    res = validate_pathwise_declaration(
        rule, fit_mean, l, b, pw, hz, False, 0.995, 12, 0.4, 0.3)
    assert not res["gates"]["G4_without_actions_bit_identical"]
    assert res["verdict"] == "FAIL"


def test_gate_keys_fixed_pre_registered(rule):
    fit_mean, l, b, pw, hz = _synthetic_inputs(rule, sign_ok=True)
    res = validate_pathwise_declaration(
        rule, fit_mean, l, b, pw, hz, True, 0.995, 12, 0.4, 0.3)
    assert sorted(res["gates"]) == [
        "G1_carveouts_preserved_relieved_within_envelope",
        "G2_sign_gate_pathwise_scr_ge_horizon_scr",
        "G3_monotonicity_guard_pathwise_basis",
        "G4_without_actions_bit_identical",
        "G5_horizon_basis_reproduced",
        "G6_no_action_above_trigger",
    ]


def test_horizon_basis_reproduction_gate_matches_p24t3_transform(rule):
    fit_mean, l, b, pw, hz = _synthetic_inputs(rule, sign_ok=True)
    a_ref = rule.reference_assets(fit_mean)
    res = validate_pathwise_declaration(
        rule, fit_mean, l, b, pw, hz, True, 0.995, 12, 0.4, 0.3)
    direct = apply_inner_path_action(rule, a_ref, l, b)
    hz_cap = res["nested_capital_with_horizon"]
    assert hz_cap["var_liability"] == pytest.approx(
        float(np.quantile(direct, 0.995)), rel=1e-9)


def test_materiality_threshold_reexported():
    assert PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD == pytest.approx(0.01)


def test_use_restrictions_disclose_residuals():
    u = pathwise_declaration_use_restrictions()
    assert u["classification"] == "EDUCATIONAL_DEMONSTRATION_ONLY"
    text = json.dumps(u)
    assert "foresight" in text
    assert "annual" in text
    assert "Production capital or solvency decisions" in str(
        u["prohibited_uses"])


# ---------------------------------------------------------------- report ----

class TestReport:
    def test_report_exists_and_passes(self, rep):
        assert rep["verdict"] == "PASS"
        assert all(rep["result"]["gates"].values())

    def test_sign_gate_pathwise_ge_horizon(self, rep):
        r = rep["result"]
        assert (r["nested_capital_with_pathwise"]["scr_proxy"]
                >= r["nested_capital_with_horizon"]["scr_proxy"] - 1e-9)
        assert (r["nested_capital_with_pathwise"]["var_liability"]
                >= r["nested_capital_with_horizon"]["var_liability"] - 1e-9)

    def test_with_actions_le_without(self, rep):
        r = rep["result"]
        assert (r["nested_capital_with_pathwise"]["scr_proxy"]
                <= r["nested_capital_without"]["scr_proxy"] + 1e-9)
        assert (r["nested_capital_with_horizon"]["scr_proxy"]
                <= r["nested_capital_without"]["scr_proxy"] + 1e-9)

    def test_without_actions_reference_unchanged(self, rep):
        wo = rep["result"]["nested_capital_without"]
        assert wo["scr_proxy"] == pytest.approx(55561.1889, abs=1e-3)
        assert wo["var_liability"] == pytest.approx(171555.268, abs=1e-2)

    def test_horizon_basis_consistent_with_p24t3(self, rep):
        c = rep["p24t3_horizon_basis_consistency"]
        assert c["match"]
        assert c["scr_p24t3_archived"] == pytest.approx(
            40852.05410858347, abs=1e-6)

    def test_materiality_disclosure_flagged(self, rep):
        d = rep["result"]["pathwise_vs_horizon_delta"]
        assert d["materiality_disclosure_threshold"] == pytest.approx(0.01)
        # the realised delta exceeds 1% -> Task 4 MUST refresh MR-010/MR-014
        assert d["mr010_mr014_refresh_required_task4"] == (
            abs(d["scr_delta_rel_to_horizon"]) > 0.01)

    def test_restoration_is_a_real_dynamic(self, rep):
        r = rep["result"]
        assert r["pathwise_restoration_share"] > 0.0
        assert r["pathwise_action_share"] >= r["pathwise_restoration_share"]

    def test_residuals_documented(self, rep):
        text = json.dumps(rep["residuals_documented"])
        assert "annual" in text.lower()
        assert "foresight" in text.lower()

    def test_verify_stage_crosschecks_all_pass(self, rep):
        assert all(rep["verify_stage"]["checks"].values())

    def test_markdown_and_card_written(self, rep):
        md = MD.read_text(encoding="utf-8")
        assert rep["verdict"] in md
        assert "path-wise" in md.lower()
        card = CARD.read_text(encoding="utf-8")
        assert "EDUCATIONAL" in card

    def test_digest_present(self, rep):
        assert len(rep["reproducibility_digest"]) == 64


# ------------------------------------------------------------ governance ----

class TestGovernance:
    def test_change_record_owner_review(self, rep, store):
        rec = next(
            x for x in store.change_records if x.title == CHANGE_TITLE)
        assert rec.record_id == rep["change_record_id"]
        status = (rec.status.value if hasattr(rec.status, "value")
                  else str(rec.status))
        assert "OWNER_REVIEW" in status.upper().replace(" ", "_")
        assert rec.change_type == "assumption_change"

    def test_audit_integrity(self, rep, store):
        assert rep["audit_integrity_ok"]
        assert store.audit_trail.verify_all()
