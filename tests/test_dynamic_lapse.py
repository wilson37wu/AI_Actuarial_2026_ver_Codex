"""
Tests — Phase 13 Task 2: Dynamic Lapse Model, Calibration, and Gates (G-04, G-11)
=================================================================================
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from par_model_v2.projection.dynamic_lapse import (
    DynamicLapseAssumption,
    LapseCalibrationDiagnostics,
    LapseExperiencePoint,
    base_annual_lapse,
    build_hk_par_experience_study,
    calibrate_dynamic_lapse,
    default_hk_par_dynamic_lapse,
)
from par_model_v2.projection.monthly_projection import (
    ParEndowmentProduct,
    dynamic_annual_lapse,
    project_liability_cashflows,
)
from par_model_v2.calibration.phase13_dynamic_lapse import (
    evaluate_g04_gate,
    evaluate_g11_gate,
    run_lapse_scenario_grid,
    run_phase13_dynamic_lapse,
)
from par_model_v2.governance.audit_trail import GovernanceStore, SignOffStatus


# ---------------------------------------------------------------------------
# Functional form
# ---------------------------------------------------------------------------

def test_base_schedule_matches_legacy():
    assert base_annual_lapse(1) == 0.12
    assert base_annual_lapse(2) == 0.09
    assert base_annual_lapse(3) == 0.07
    assert base_annual_lapse(5) == 0.05
    assert base_annual_lapse(10) == 0.03
    assert base_annual_lapse(20) == 0.015


def test_efficiency_multiplier_bounds():
    a = DynamicLapseAssumption(beta=0.55, kappa=0.02)
    # bounded in (1 - beta, 1 + beta)
    assert a.efficiency_multiplier(-1e9) > 1.0 - a.beta - 1e-9
    assert a.efficiency_multiplier(+1e9) < 1.0 + a.beta + 1e-9
    assert a.efficiency_multiplier(0.0) == pytest.approx(1.0)


def test_efficiency_monotone_in_spread():
    a = default_hk_par_dynamic_lapse()
    spreads = np.linspace(-0.05, 0.05, 25)
    mults = [a.efficiency_multiplier(s) for s in spreads]
    assert all(b >= x - 1e-12 for x, b in zip(mults, mults[1:]))


def test_mass_lapse_monotone_and_bounded():
    a = DynamicLapseAssumption(shock_max=0.18, tau=0.03, width=0.01)
    assert a.mass_lapse(-0.10) == pytest.approx(0.0, abs=1e-6)
    assert a.mass_lapse(+0.20) == pytest.approx(0.18, abs=1e-6)
    # half-max at the threshold tau
    assert a.mass_lapse(0.03) == pytest.approx(0.09, abs=1e-6)
    seq = [a.mass_lapse(s) for s in np.linspace(-0.05, 0.10, 30)]
    assert all(b >= x - 1e-12 for x, b in zip(seq, seq[1:]))


def test_mass_lapse_no_overflow_extremes():
    a = default_hk_par_dynamic_lapse()
    assert a.mass_lapse(-1e6) == 0.0
    assert a.mass_lapse(1e6) == pytest.approx(a.shock_max)


def test_annual_rate_directionality():
    a = default_hk_par_dynamic_lapse(credited_rate=0.025)
    itm = a.annual_rate(1, market_rate=0.005)   # guarantee in the money
    base = a.annual_rate(1, market_rate=0.025)  # market == credited
    otm = a.annual_rate(1, market_rate=0.055)   # out of the money
    assert itm < base < otm


def test_annual_rate_is_clamped():
    a = DynamicLapseAssumption(beta=0.9, kappa=0.001, shock_max=0.5, tau=0.0,
                               width=0.001, lapse_cap=0.95)
    assert 0.0 <= a.annual_rate(1, 0.50) <= 0.95


def test_annual_rate_accepts_economic_inputs_signature():
    # G-04 criterion 1: function accepts at least rate and policy_year.
    a = default_hk_par_dynamic_lapse()
    val = a.annual_rate(policy_year=4, market_rate=0.04)
    assert isinstance(val, float) and val > 0.0


# ---------------------------------------------------------------------------
# Validation guards
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    {"beta": 1.0}, {"beta": -0.1}, {"kappa": 0.0}, {"width": 0.0},
    {"shock_max": -0.1}, {"lapse_floor": 0.5, "lapse_cap": 0.4},
])
def test_invalid_params_raise(kwargs):
    with pytest.raises(ValueError):
        DynamicLapseAssumption(**kwargs)


# ---------------------------------------------------------------------------
# Experience study + calibration (G-11)
# ---------------------------------------------------------------------------

def test_experience_study_shape_and_determinism():
    e1 = build_hk_par_experience_study()
    e2 = build_hk_par_experience_study()
    assert len(e1) == 48
    assert all(isinstance(p, LapseExperiencePoint) for p in e1)
    assert [p.observed_annual_lapse for p in e1] == [p.observed_annual_lapse for p in e2]


def test_experience_study_lapse_rises_with_spread():
    e = build_hk_par_experience_study()
    year1 = sorted((p for p in e if p.policy_year == 1), key=lambda p: p.spread)
    obs = [p.observed_annual_lapse for p in year1]
    assert obs[0] < obs[-1]  # OTM lapses exceed ITM lapses


def test_calibration_recovers_generating_params():
    a, diag = calibrate_dynamic_lapse()
    assert diag.converged
    assert diag.r_squared > 0.99
    assert diag.rmse < 0.005
    # generating params were beta=0.55, kappa=0.02, shock=0.18, tau=0.03
    assert a.beta == pytest.approx(0.55, abs=0.15)
    assert a.kappa == pytest.approx(0.02, abs=0.01)
    assert a.shock_max == pytest.approx(0.18, abs=0.05)


def test_calibration_diagnostics_serialisable():
    _, diag = calibrate_dynamic_lapse()
    d = diag.to_dict()
    assert set(["rmse", "r_squared", "fitted_params", "optimizer"]).issubset(d)
    assert isinstance(d["standard_references"], list)


# ---------------------------------------------------------------------------
# Projection integration
# ---------------------------------------------------------------------------

def _product():
    return ParEndowmentProduct(
        term_years=20, issue_age=40, gender="M",
        sum_assured=1_000_000.0, annual_premium=60_000.0,
    )


def test_static_path_unchanged_when_no_dynamic_lapse():
    p = _product()
    r1 = project_liability_cashflows(p)
    r2 = project_liability_cashflows(p, dynamic_lapse=None)
    assert r1.pv_net_liability == r2.pv_net_liability
    assert r1.pv_surrender_benefits == r2.pv_surrender_benefits


def test_dynamic_lapse_changes_surrender_pv():
    p = _product()
    a = default_hk_par_dynamic_lapse(credited_rate=0.025)
    static = project_liability_cashflows(p)
    dyn_otm = project_liability_cashflows(p, dynamic_lapse=a, market_rate=0.065)
    # out-of-the-money: dynamic surrenders exceed static
    assert dyn_otm.pv_surrender_benefits > static.pv_surrender_benefits


def test_dynamic_lapse_market_rate_callable():
    p = _product()
    a = default_hk_par_dynamic_lapse()
    res = project_liability_cashflows(
        p, dynamic_lapse=a, market_rate=lambda yr: 0.025 + 0.001 * yr
    )
    assert math.isfinite(res.pv_net_liability)


def test_monthly_projection_dynamic_annual_lapse_helper():
    # helper lives in monthly_projection.py (G-04 criterion 1 location)
    low = dynamic_annual_lapse(1, market_rate=0.005, credited_rate=0.025)
    high = dynamic_annual_lapse(1, market_rate=0.055, credited_rate=0.025)
    assert low < high


# ---------------------------------------------------------------------------
# Non-FLAT sensitivity (G-04 criterion 2)
# ---------------------------------------------------------------------------

def test_lapse_response_is_non_flat():
    a = default_hk_par_dynamic_lapse()
    impacts = run_lapse_scenario_grid(a)
    # static baseline is invariant to market rate
    statics = {round(i.pv_net_liability_static, 2) for i in impacts}
    assert len(statics) == 1
    # dynamic response varies materially across scenarios
    dyn_vals = [i.pv_net_liability_dynamic for i in impacts]
    assert max(dyn_vals) - min(dyn_vals) > 0.0
    assert max(abs(i.net_liability_delta_pct) for i in impacts) > 0.5


# ---------------------------------------------------------------------------
# Gates + governance
# ---------------------------------------------------------------------------

def test_g04_and_g11_pass():
    a, diag = calibrate_dynamic_lapse()
    impacts = run_lapse_scenario_grid(a)
    assert evaluate_g04_gate(diag, impacts).status == "PASS"
    assert evaluate_g11_gate(diag).status == "PASS"


def test_g04_fails_on_flat_response():
    a, diag = calibrate_dynamic_lapse()
    # craft a degenerate "flat" impact set
    class _Flat:
        net_liability_delta_pct = 0.0
    assert evaluate_g04_gate(diag, [_Flat(), _Flat()]).status == "FAIL"


def test_pipeline_change_record_approved():
    store = GovernanceStore()
    rep = run_phase13_dynamic_lapse(governance_store=store)
    assert rep.change_record_status == SignOffStatus.APPROVED.value
    assert rep.gate_g04.status == "PASS"
    assert rep.gate_g11.status == "PASS"
    cr = store.get_change_record(rep.change_record_id)
    assert cr.status == SignOffStatus.APPROVED
    assert "dynamic_lapse" in cr.description
    # full sign-off workflow recorded
    assert len(cr.sign_off_history) == 3


def test_pipeline_report_serialisable_and_complete():
    rep = run_phase13_dynamic_lapse()
    d = rep.to_dict()
    assert set(["assumption", "diagnostics", "impacts", "gate_g04",
                "gate_g11", "change_record_status"]).issubset(d)
    assert len(d["impacts"]) == 5
    assert "Dynamic Lapse Calibration Report" in rep.markdown
