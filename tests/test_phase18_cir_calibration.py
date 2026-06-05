"""
Phase 18 Task 2 — CIR++ Credit-Spread Calibration tests.

Covers: deterministic synthesis, CIR OLS parameter recovery within documented
tolerances, plausibility-band gate, governance (APPROVED ChangeRecord +
PARAM_CHANGE audit + MR-012 MITIGATED), audit-digest integrity, and the
calibrated params round-tripping into a usable CreditSpreadProcess.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from par_model_v2.calibration.cir_calibrator import (
    CIRCalibrationInputs,
    CIRCalibrationResult,
    CIRCalibrator,
)
from par_model_v2.calibration.credit_market_data_source import (
    FileBasedCreditSpreadSource,
    build_credit_loader,
    check_credit_calibration,
    evaluate_credit_gate,
    synthesize_spread_history,
    KAPPA_MIN, KAPPA_MAX, LONG_RUN_MIN, LONG_RUN_MAX,
    SIGMA_MIN, SIGMA_MAX, LAMBDA_MIN, LAMBDA_MAX, MIN_OBS,
)
from par_model_v2.calibration.phase18_cir_calibration import (
    PLACEHOLDER_CIR,
    run_phase18_cir_calibration,
)
from par_model_v2.governance.audit_trail import (
    EntryType,
    GovernanceStore,
    MitigationStatus,
    SignOffStatus,
)
from par_model_v2.stochastic.credit_spread import CreditSpreadParams, CreditSpreadProcess
from par_model_v2.stochastic.esg_process import Measure


FIXTURE = "par_model_v2/calibration/fixtures/cny_credit_spread_history_20260101.json"

# Documented fixture targets.
TARGET_KAPPA = 0.60
TARGET_LONG_RUN = 0.012
TARGET_SIGMA = 0.040
TARGET_RN = 0.014


def _seed_store_with_mr012() -> GovernanceStore:
    """A minimal store carrying an IN_PROGRESS MR-012 entry for mitigation tests."""
    store = GovernanceStore()
    store.risk_register.add(
        risk_id="MR-012",
        title="Credit-spread driver educational",
        description="placeholder",
        category="model_error",
        likelihood=__import__("par_model_v2.governance.audit_trail", fromlist=["RiskRating"]).RiskRating.MEDIUM,
        impact=__import__("par_model_v2.governance.audit_trail", fromlist=["RiskRating"]).RiskRating.HIGH,
        owner="Model Owner",
        mitigation="classify educational",
        related_standard="IA TAS M §3.6",
        mitigation_status=MitigationStatus.IN_PROGRESS,
    )
    return store


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

def test_synthesis_deterministic_and_shaped():
    src = FileBasedCreditSpreadSource(FIXTURE)
    s1, d1 = synthesize_spread_history(src._data)
    s2, d2 = synthesize_spread_history(src._data)
    assert d1 == d2
    assert len(s1) >= 240
    pd.testing.assert_series_equal(s1, s2)  # deterministic given seed
    # All spreads strictly inside [floor, ceiling] and positive.
    assert (s1 > 0).all()
    assert (s1 < 0.20).all()


def test_synthesis_recovers_documented_mean():
    src = FileBasedCreditSpreadSource(FIXTURE)
    s, _ = synthesize_spread_history(src._data)
    # Long-run mean of the path should be near the documented target (within 25%).
    assert abs(float(s.mean()) - TARGET_LONG_RUN) / TARGET_LONG_RUN < 0.25


# ---------------------------------------------------------------------------
# Calibration recovery
# ---------------------------------------------------------------------------

def test_calibration_recovers_parameters_within_tolerance():
    loader = build_credit_loader("CNY")
    inputs, _ = loader.load()
    res = CIRCalibrator(inputs).calibrate()
    assert isinstance(res, CIRCalibrationResult)
    assert not res.is_placeholder
    # Long-run spread: sample-mean robust -> tight tolerance.
    assert abs(res.long_run_spread_p - TARGET_LONG_RUN) / TARGET_LONG_RUN < 0.25
    # Spread vol: residual-variance robust -> moderate tolerance.
    assert abs(res.spread_vol - TARGET_SIGMA) / TARGET_SIGMA < 0.40
    # Mean reversion: noisy slope -> factor-of-3 band, sign correct.
    assert TARGET_KAPPA / 3.0 <= res.mean_reversion_speed <= TARGET_KAPPA * 3.0
    # Lambda derived from the documented anchor, positive and bounded.
    assert 0.0 < res.market_price_of_credit_risk <= 2.0


def test_calibration_deterministic():
    loader = build_credit_loader("CNY")
    inputs, _ = loader.load()
    a = CIRCalibrator(inputs).calibrate()
    b = CIRCalibrator(inputs).calibrate()
    assert a.mean_reversion_speed == pytest.approx(b.mean_reversion_speed)
    assert a.long_run_spread_p == pytest.approx(b.long_run_spread_p)
    assert a.spread_vol == pytest.approx(b.spread_vol)
    assert a.market_price_of_credit_risk == pytest.approx(b.market_price_of_credit_risk)


def test_lambda_from_risk_neutral_anchor_relation():
    """lambda_s should satisfy s^Q_inf - s^P_inf = lambda * sigma^2 / kappa."""
    loader = build_credit_loader("CNY")
    inputs, _ = loader.load()
    res = CIRCalibrator(inputs).calibrate()
    implied_premium = res.market_price_of_credit_risk * res.spread_vol ** 2 / res.mean_reversion_speed
    actual_gap = TARGET_RN - res.long_run_spread_p
    # Either the relation holds, or lambda was clamped at the upper bound.
    if res.market_price_of_credit_risk < 2.0 - 1e-9:
        assert implied_premium == pytest.approx(actual_gap, abs=1e-4)


def test_no_anchor_falls_back_to_default_lambda():
    loader = build_credit_loader("CNY")
    inputs, _ = loader.load()
    inputs.risk_neutral_long_run_spread = None
    res = CIRCalibrator(inputs).calibrate()
    assert res.market_price_of_credit_risk == pytest.approx(PLACEHOLDER_CIR["market_price_of_credit_risk"])


def test_inputs_reject_bad_shift_and_negative_spreads():
    s = pd.Series([0.010, 0.011, 0.012], index=pd.date_range("2020-01-31", periods=3, freq="ME"))
    # shift above min spread -> invalid (x would be negative)
    with pytest.raises(ValueError):
        CIRCalibrationInputs(calibration_date=s.index[0].date(), spread_history=s, shift=0.011)
    neg = pd.Series([0.01, -0.001, 0.012], index=s.index)
    with pytest.raises(ValueError):
        CIRCalibrationInputs(calibration_date=s.index[0].date(), spread_history=neg, shift=0.001)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

def test_gate_passes_with_audit_and_in_bands():
    loader = build_credit_loader("CNY")
    inputs, _ = loader.load()
    res = CIRCalibrator(inputs).calibrate()
    chk = check_credit_calibration("CNY", len(inputs.spread_history), res, has_param_change_audit=True)
    assert chk.all_pass()
    assert evaluate_credit_gate(chk).status == "PASS"
    # Recovered values genuinely inside the published bands.
    assert KAPPA_MIN <= res.mean_reversion_speed <= KAPPA_MAX
    assert LONG_RUN_MIN <= res.long_run_spread_p <= LONG_RUN_MAX
    assert SIGMA_MIN <= res.spread_vol <= SIGMA_MAX
    assert LAMBDA_MIN <= res.market_price_of_credit_risk <= LAMBDA_MAX


def test_gate_fails_without_param_change_audit():
    loader = build_credit_loader("CNY")
    inputs, _ = loader.load()
    res = CIRCalibrator(inputs).calibrate()
    chk = check_credit_calibration("CNY", len(inputs.spread_history), res, has_param_change_audit=False)
    assert not chk.all_pass()
    assert evaluate_credit_gate(chk).status == "FAIL"


def test_loader_rejects_too_few_obs(tmp_path):
    import json
    src = FileBasedCreditSpreadSource(FIXTURE)
    data = dict(src._data)
    data["monthly_synthesis"] = dict(data["monthly_synthesis"], start_date="2025-06-30", end_date="2025-12-31")
    p = tmp_path / "tiny.json"
    p.write_text(json.dumps(data))
    from par_model_v2.calibration.credit_market_data_source import CreditSpreadDataLoader
    loader = CreditSpreadDataLoader(FileBasedCreditSpreadSource(p), min_obs=MIN_OBS)
    with pytest.raises(ValueError):
        loader.load()


# ---------------------------------------------------------------------------
# Calibrated params -> live process
# ---------------------------------------------------------------------------

def test_calibrated_params_drive_process():
    loader = build_credit_loader("CNY")
    inputs, _ = loader.load()
    params = CIRCalibrator(inputs).calibrate().to_params()
    assert isinstance(params, CreditSpreadParams)
    proc = CreditSpreadProcess(params)
    df = proc.simulate(n_scenarios=64, T_months=12, measure=Measure.P, seed=7)
    assert (df["credit_spread"] >= 0).all()
    assert df["measure"].iloc[0] == Measure.P.value
    # Q-measure spreads should on average exceed P (positive credit risk premium).
    p_mean = proc.simulate(64, 60, Measure.P, seed=11)["credit_spread"].mean()
    q_mean = proc.simulate(64, 60, Measure.Q, seed=11)["credit_spread"].mean()
    assert q_mean >= p_mean


# ---------------------------------------------------------------------------
# Governance pipeline
# ---------------------------------------------------------------------------

def test_pipeline_governance_and_mr012_mitigated():
    store = _seed_store_with_mr012()
    rep = run_phase18_cir_calibration(governance_store=store, persist_governance=False, write_report=False)
    assert rep.gate_gcr.status == "PASS"
    assert rep.change_record_status == SignOffStatus.APPROVED.value
    assert rep.mr012_status == MitigationStatus.MITIGATED.value
    # ChangeRecord present + APPROVED.
    cr = store.get_change_record(rep.change_record_id)
    assert cr.status == SignOffStatus.APPROVED
    assert cr.change_type == "assumption_change"
    # Exactly one PARAM_CHANGE entry for the credit params + audit integrity intact.
    pcs = [e for e in store.audit_trail.filter_by_type(EntryType.PARAM_CHANGE)
           if e.details.get("parameter_name") == "CIR_credit_spread_params[CNY]"]
    assert len(pcs) == 1
    assert pcs[0].details["old_value"] == PLACEHOLDER_CIR
    assert store.audit_trail.verify_all()
    # MR-012 in register is MITIGATED.
    assert store.risk_register.get("MR-012").mitigation_status == MitigationStatus.MITIGATED


def test_pipeline_report_roundtrips():
    store = _seed_store_with_mr012()
    rep = run_phase18_cir_calibration(governance_store=store, persist_governance=False, write_report=False)
    import json
    d = json.loads(rep.to_json())
    assert d["summary"]["market"] == "CNY"
    assert d["gate_gcr"]["gate_id"] == "G-CR"
    assert "PRODUCTION USE RESTRICTION" in rep.markdown
    assert "MR-012" in rep.markdown


def test_pipeline_without_mr012_entry_reports_not_found():
    store = GovernanceStore()  # no MR-012
    rep = run_phase18_cir_calibration(governance_store=store, persist_governance=False, write_report=False)
    assert rep.mr012_status == "NOT_FOUND"
    # Gate + ChangeRecord still succeed.
    assert rep.gate_gcr.status == "PASS"
    assert rep.change_record_status == SignOffStatus.APPROVED.value
