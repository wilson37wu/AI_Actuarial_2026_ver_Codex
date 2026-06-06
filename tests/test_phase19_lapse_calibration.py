"""
Tests for the Phase 19 Task 5 OU lapse behavioural-index calibration.

Modules under test:
  * par_model_v2.calibration.lapse_calibrator
      - LapseBehaviourCalibrator (OU AR(1) transition regression: kappa_b +
        long-run level, residual variance -> sigma_b via the stationary relation)
  * par_model_v2.calibration.lapse_experience_data_source
      - FileBasedLapseExperienceSource / LapseExperienceDataLoader (deterministic
        OU A/E synthesis + lineage), G-LAPSE plausibility gate
  * par_model_v2.calibration.phase19_lapse_calibration
      - run_phase19_lapse_calibration (ChangeRecord + PARAM_CHANGE audit +
        MR-003/MR-011 MITIGATED + report)

Sizes are kept small so each pytest invocation stays inside the sandbox time
budget; the production evidence numbers come from the build script.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from par_model_v2.calibration.lapse_calibrator import (
    LapseBehaviourCalibrator,
    LapseCalibrationInputs,
    LapseCalibrationResult,
)
from par_model_v2.calibration.lapse_experience_data_source import (
    KAPPA_MAX,
    KAPPA_MIN,
    SIGMA_MAX,
    SIGMA_MIN,
    THETA_MAX,
    THETA_MIN,
    FileBasedLapseExperienceSource,
    LapseExperienceDataLoader,
    build_lapse_loader,
    check_lapse_calibration,
    evaluate_lapse_gate,
    synthesize_ae_history,
)
from par_model_v2.stochastic.lapse_behaviour import LapseBehaviourParams


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _synth_ou_ae(kappa, theta, sigma, n=360, dt=1.0 / 12.0, seed=11, b0=0.0):
    """Exact OU AR(1) A/E series for recovery tests."""
    rng = np.random.default_rng(seed)
    phi = np.exp(-kappa * dt)
    cstd = np.sqrt(sigma * sigma * (1.0 - phi * phi) / (2.0 * kappa))
    b = np.empty(n)
    b[0] = b0
    for t in range(1, n):
        b[t] = phi * b[t - 1] + theta * (1.0 - phi) + cstd * rng.standard_normal()
    idx = pd.date_range("2000-01-31", periods=n, freq="ME")
    return pd.Series(np.exp(b), index=idx, name="ae")


# ---------------------------------------------------------------------------
# Calibrator
# ---------------------------------------------------------------------------

def test_calibrator_recovers_known_ou_parameters():
    ae = _synth_ou_ae(kappa=0.5, theta=0.0, sigma=0.18, n=600, seed=3)
    res = LapseBehaviourCalibrator(LapseCalibrationInputs(date(2026, 1, 1), ae)).calibrate()
    # Long-run level and vol are the robust estimates; allow generous bands for the
    # single-path OLS intercept (theta = c/(1-phi) amplifies sampling error as phi->1).
    assert abs(res.long_run_level) < 0.12
    assert 0.13 < res.behaviour_vol < 0.24
    assert 0.2 < res.mean_reversion_speed < 1.2
    assert res.is_placeholder is False
    assert res.n_obs == 600


def test_calibrator_stationary_std_and_half_life_consistent():
    ae = _synth_ou_ae(kappa=0.5, theta=0.0, sigma=0.18, n=400, seed=5)
    res = LapseBehaviourCalibrator(LapseCalibrationInputs(date(2026, 1, 1), ae)).calibrate()
    expect_sd = res.behaviour_vol / np.sqrt(2.0 * res.mean_reversion_speed)
    assert res.stationary_std == pytest.approx(expect_sd, rel=1e-9)
    assert res.half_life_years == pytest.approx(np.log(2.0) / res.mean_reversion_speed, rel=1e-9)
    assert res.long_run_ae == pytest.approx(np.exp(res.long_run_level), rel=1e-9)


def test_calibrator_to_params_roundtrips_into_process_params():
    ae = _synth_ou_ae(kappa=0.6, theta=0.02, sigma=0.2, n=300, seed=7)
    res = LapseBehaviourCalibrator(LapseCalibrationInputs(date(2026, 1, 1), ae)).calibrate()
    params = res.to_params()
    assert isinstance(params, LapseBehaviourParams)
    assert params.mean_reversion_speed == pytest.approx(res.mean_reversion_speed)
    assert params.behaviour_vol == pytest.approx(res.behaviour_vol)
    assert params.initial_index == pytest.approx(res.initial_index)


def test_calibrator_rejects_bad_inputs():
    with pytest.raises(TypeError):
        LapseCalibrationInputs(date(2026, 1, 1), [1.0, 1.1, 0.9])  # not a Series
    with pytest.raises(ValueError):
        LapseCalibrationInputs(date(2026, 1, 1), pd.Series([1.0, 1.1]))  # too few
    with pytest.raises(ValueError):
        LapseCalibrationInputs(date(2026, 1, 1), pd.Series([1.0, -0.1, 0.9]))  # non-positive A/E


def test_calibrator_handles_non_mean_reverting_sample():
    # A near-random-walk (very low kappa) must not crash and must stay finite/positive.
    ae = _synth_ou_ae(kappa=0.02, theta=0.0, sigma=0.1, n=200, seed=9)
    res = LapseBehaviourCalibrator(LapseCalibrationInputs(date(2026, 1, 1), ae)).calibrate()
    assert res.mean_reversion_speed > 0
    assert np.isfinite(res.behaviour_vol) and res.behaviour_vol > 0
    assert np.isfinite(res.stationary_std)


# ---------------------------------------------------------------------------
# Data source / synthesis / loader
# ---------------------------------------------------------------------------

def test_synthesis_is_deterministic_and_positive():
    spec = {
        "market": "HK_PAR",
        "as_of_date": "2026-01-01",
        "target_mean_reversion": 0.5,
        "target_long_run_level": 0.0,
        "target_behaviour_vol": 0.18,
        "ae_floor": 0.3,
        "ae_ceiling": 3.0,
        "monthly_synthesis": {
            "seed": 20260106,
            "steps_per_year": 12,
            "start_date": "2006-01-31",
            "end_date": "2025-12-31",
            "initial_index": 0.05,
        },
    }
    s1, d1 = synthesize_ae_history(spec)
    s2, d2 = synthesize_ae_history(spec)
    assert d1 == d2 == date(2026, 1, 1)
    assert (s1.to_numpy() == s2.to_numpy()).all()
    assert (s1.to_numpy() > 0).all()
    assert len(s1) >= 240


def test_loader_reads_bundled_fixture_and_calibrates_in_band():
    loader = build_lapse_loader()
    inputs, lineage = loader.load()
    assert len(inputs.ae_history) >= 60
    assert lineage.lineage_id.startswith("LINLAPSE_")
    res = LapseBehaviourCalibrator(inputs).calibrate()
    assert KAPPA_MIN <= res.mean_reversion_speed <= KAPPA_MAX
    assert THETA_MIN <= res.long_run_level <= THETA_MAX
    assert SIGMA_MIN <= res.behaviour_vol <= SIGMA_MAX


def test_loader_rejects_too_few_observations(tmp_path):
    import json

    fixture = {
        "fixture_id": "TINY",
        "market": "HK_PAR",
        "as_of_date": "2026-01-01",
        "target_mean_reversion": 0.5,
        "target_long_run_level": 0.0,
        "target_behaviour_vol": 0.18,
        "monthly_synthesis": {
            "seed": 1,
            "steps_per_year": 12,
            "start_date": "2025-01-31",
            "end_date": "2025-06-30",  # < 60 obs
            "initial_index": 0.0,
        },
    }
    p = tmp_path / "tiny.json"
    p.write_text(json.dumps(fixture), encoding="utf-8")
    loader = LapseExperienceDataLoader(FileBasedLapseExperienceSource(p))
    with pytest.raises(ValueError):
        loader.load()


# ---------------------------------------------------------------------------
# G-LAPSE gate
# ---------------------------------------------------------------------------

def test_glapse_gate_passes_on_calibrated_fixture():
    loader = build_lapse_loader()
    inputs, _ = loader.load()
    res = LapseBehaviourCalibrator(inputs).calibrate()
    check = check_lapse_calibration("HK_PAR", res.n_obs, res, has_param_change_audit=True)
    gate = evaluate_lapse_gate(check)
    assert gate.gate_id == "G-LAPSE"
    assert gate.status == "PASS"
    assert all(check.criteria.values())


def test_glapse_gate_fails_without_audit():
    loader = build_lapse_loader()
    inputs, _ = loader.load()
    res = LapseBehaviourCalibrator(inputs).calibrate()
    check = check_lapse_calibration("HK_PAR", res.n_obs, res, has_param_change_audit=False)
    gate = evaluate_lapse_gate(check)
    assert gate.status == "FAIL"
    assert check.criteria["c6_not_placeholder_with_audit"] is False


# ---------------------------------------------------------------------------
# Full pipeline + governance
# ---------------------------------------------------------------------------

def test_pipeline_runs_and_mitigates_risks():
    from par_model_v2.governance.audit_trail import GovernanceStore
    from par_model_v2.calibration.phase19_lapse_calibration import (
        run_phase19_lapse_calibration,
    )

    store = GovernanceStore()
    report = run_phase19_lapse_calibration(
        governance_store=store, write_report=False, persist_governance=False
    )
    assert report.gate_glapse.status == "PASS"
    assert report.change_record_status == "APPROVED"
    # Risks absent from a fresh store report NOT_FOUND but the run must not crash.
    assert report.mr003_status in {"MITIGATED", "NOT_FOUND"}
    assert report.mr011_status in {"MITIGATED", "NOT_FOUND"}
    assert store.audit_trail.verify_all() is True
    assert len(report.audit_entry_ids) == 1
    assert "PRODUCTION USE RESTRICTION" in report.markdown


def test_pipeline_against_canonical_store_mitigates_both_risks():
    import os

    from par_model_v2.governance.audit_trail import GovernanceStore
    from par_model_v2.calibration.phase19_lapse_calibration import (
        run_phase19_lapse_calibration,
    )

    store_path = ".claude-dev/GOVERNANCE_STORE.json"
    if not os.path.exists(store_path):
        pytest.skip("canonical governance store not present")
    store = GovernanceStore.from_json(open(store_path, encoding="utf-8").read())
    report = run_phase19_lapse_calibration(
        governance_store=store, write_report=False, persist_governance=False
    )
    assert report.mr003_status == "MITIGATED"
    assert report.mr011_status == "MITIGATED"
    assert store.audit_trail.verify_all() is True
