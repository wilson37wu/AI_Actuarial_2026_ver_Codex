"""Phase 22 Task 3 — liquidity exposure-notional + coupling calibration tests."""

import json
from pathlib import Path

import numpy as np
import pytest

import par_model_v2.projection.multi_driver_capital_7d_aggregation as agg7
from par_model_v2.calibration.phase22_liquidity_exposure_calibration import (
    COUPLING_KEYS,
    PLACEHOLDER_COUPLINGS,
    PLACEHOLDER_EXPOSURE_NOTIONAL,
    build_calibrated_correlation,
    check_exposure_calibration,
    derive_exposure_notional,
    estimate_couplings,
    evaluate_gliqx_gate,
    liquidity_exposure_use_restrictions,
    load_exposure_fixture,
    run_phase22_liquidity_exposure_calibration,
    synthesize_joint_panel,
    var_covar_sensitivity,
)
from par_model_v2.governance.audit_trail import GovernanceStore


@pytest.fixture(scope="module")
def spec_lineage():
    return load_exposure_fixture()


@pytest.fixture(scope="module")
def panel(spec_lineage):
    return synthesize_joint_panel(spec_lineage[0])


def test_exposure_notional_reproducible(spec_lineage):
    spec, _ = spec_lineage
    exp = derive_exposure_notional(spec)
    e = spec["exposure_inputs"]
    assert exp["exposure_notional"] == pytest.approx(
        e["backing_asset_mv"] * e["illiquid_share"] * e["forced_sale_fraction"])
    lo, hi = e["notional_band"]
    assert lo <= exp["exposure_notional"] <= hi
    assert exp["exposure_notional"] != PLACEHOLDER_EXPOSURE_NOTIONAL


def test_exposure_inputs_validated(spec_lineage):
    spec, _ = spec_lineage
    bad = json.loads(json.dumps(spec))
    bad["exposure_inputs"]["illiquid_share"] = 1.5
    with pytest.raises(ValueError):
        derive_exposure_notional(bad)


def test_synthesis_deterministic(spec_lineage, panel):
    spec, _ = spec_lineage
    p2 = synthesize_joint_panel(spec)
    assert np.array_equal(panel["innovations"], p2["innovations"])
    assert np.array_equal(panel["liquidity_core_path"], p2["liquidity_core_path"])


def test_couplings_recovered_within_tolerance(spec_lineage, panel):
    spec, _ = spec_lineage
    est = estimate_couplings(panel)
    tol = float(spec["coupling_tolerance"])
    for k in COUPLING_KEYS:
        assert abs(est[k] - float(spec["target_couplings"][k])) <= tol, k


def test_calibrated_matrix_psd_and_shape(spec_lineage, panel):
    spec, _ = spec_lineage
    est = estimate_couplings(panel)
    corr, report = build_calibrated_correlation(spec, est)
    C = corr.matrix(float(spec["gbm_rate_equity_corr"]))
    assert C.shape == (7, 7)
    assert np.allclose(C, C.T)
    assert np.allclose(np.diag(C), 1.0)
    assert bool(report.passed)
    assert np.linalg.eigvalsh(C).min() > 0.0


def test_sensitivity_bounded_and_linear_scaling(spec_lineage, panel):
    spec, _ = spec_lineage
    est = estimate_couplings(panel)
    corr, _ = build_calibrated_correlation(spec, est)
    exp = derive_exposure_notional(spec)
    s = var_covar_sensitivity(spec, corr, exp["exposure_notional"])
    assert s["calibrated_vs_placeholder_rel_change"] <= s["max_allowed_rel_change"]
    assert s["grid_spread_rel"] <= s["max_allowed_rel_change"]
    assert s["max_perturbation_rel_change"] <= s["max_allowed_rel_change"]
    assert len(s["var_covar_scr_grid"]) == len(s["notional_multipliers"])
    # liquidity is currently net-diversifying at this scale (documented finding)
    assert s["liquidity_net_diversifying"] == (s["net_liquidity_cross_term"] < 0.0)


def test_full_pipeline_gate_pass_in_memory():
    report = run_phase22_liquidity_exposure_calibration(
        governance_store=GovernanceStore(), write_report=False,
        persist_governance=False)
    assert report["gate_gliqx"]["status"] == "PASS"
    assert all(report["criteria"].values()), report["criteria"]
    assert report["change_record_status"] == "OWNER_REVIEW"
    assert report["audit_integrity_ok"] is True
    assert report["is_placeholder"] is False
    assert report["exposure"]["exposure_notional"] == pytest.approx(22000.0)


def test_gate_fails_on_bad_recovery(spec_lineage, panel):
    spec, lineage = spec_lineage
    est = estimate_couplings(panel)
    corr, corr_report = build_calibrated_correlation(spec, est)
    exp = derive_exposure_notional(spec)
    sens = var_covar_sensitivity(spec, corr, exp["exposure_notional"])
    bad = dict(est)
    bad["liq_spread"] = est["liq_spread"] + 1.0  # way outside tolerance
    check = check_exposure_calibration(spec, lineage, exp, bad, corr_report,
                                       sens, has_param_change_audit=True)
    gate = evaluate_gliqx_gate(check)
    assert gate.status == "FAIL"
    assert not check.criteria["c3_couplings_recovered_within_tol"]


def test_loader_fallback_and_calibrated(tmp_path, monkeypatch):
    # fallback branch
    monkeypatch.setattr(agg7, "_TASK22_3_REPORT", tmp_path / "missing.json")
    notional, ph = agg7.calibrated_liquidity_exposure_notional()
    assert ph is True and notional == PLACEHOLDER_EXPOSURE_NOTIONAL
    corr, ph2 = agg7.calibrated_seven_driver_correlation()
    assert ph2 is True
    assert corr.liq_spread == PLACEHOLDER_COUPLINGS["liq_spread"]
    # calibrated branch (minimal injected report)
    rp = tmp_path / "report.json"
    rp.write_text(json.dumps({
        "gate_gliqx": {"status": "PASS"},
        "exposure": {"exposure_notional": 22000.0},
        "estimated_couplings": {"liq_rate": -0.08, "liq_equity": -0.29,
                                "liq_spread": 0.46, "liq_lapse": 0.11,
                                "liq_mortality": 0.02, "liq_fx": 0.11},
    }), encoding="utf-8")
    monkeypatch.setattr(agg7, "_TASK22_3_REPORT", rp)
    notional, ph = agg7.calibrated_liquidity_exposure_notional()
    assert ph is False and notional == pytest.approx(22000.0)
    corr, ph2 = agg7.calibrated_seven_driver_correlation()
    assert ph2 is False and corr.liq_spread == pytest.approx(0.46)


def test_use_restrictions_educational():
    r = liquidity_exposure_use_restrictions()
    assert r["status"] == "EDUCATIONAL"
    assert any("APS X2" in x for x in r["restrictions"])
