"""Tests for Phase 20 Task 3 -- market-consistency (martingale) gate G-MART.

Verifies each deflated-asset martingale identity under Q within a statistical
band, the exact HW1F simulator's distribution, the educational-Euler bias
diagnostic, the measure-specificity (P vs Q) diagnostic, and the gate verdict
logic.  Sample sizes are kept modest so the suite runs in well under 45 s.
"""

import math

import numpy as np
import pytest

from par_model_v2.stochastic.esg_process import (
    GBMParams,
    HullWhiteParams,
    HullWhiteRateProcess,
    Measure,
    RiskFreeCurve,
)
from par_model_v2.validation.phase20_market_consistency import (
    GMartGateReport,
    MartingaleCheck,
    _deflator,
    diagnostic_hw1f_euler_bias,
    evaluate_g_mart_gate,
    martingale_equity,
    martingale_equity_pmeasure,
    martingale_fx,
    martingale_g2pp,
    martingale_hw1f,
    simulate_hw1f_exact,
)

CURVE = RiskFreeCurve.flat(0.03, currency="CNY", market="CN")
SEED = 20260606


# --------------------------------------------------------------------------- #
# Deflator helper                                                             #
# --------------------------------------------------------------------------- #
def test_deflator_constant_rate_riemann_and_trapezoid():
    # flat 3% over 12 months -> D(1y) = exp(-0.03)
    grid = np.full((4, 13), 0.03)
    for method in ("riemann", "trapezoid"):
        d = _deflator(grid, method=method)
        assert d.shape == (4, 13)
        assert np.allclose(d[:, 0], 1.0)
        assert np.allclose(d[:, 12], math.exp(-0.03), atol=1e-12)


def test_deflator_rejects_unknown_method():
    with pytest.raises(ValueError):
        _deflator(np.zeros((2, 3)), method="simpson")


# --------------------------------------------------------------------------- #
# Exact HW1F simulator                                                        #
# --------------------------------------------------------------------------- #
def test_simulate_hw1f_exact_shape_and_initial():
    params = HullWhiteParams()
    grid = simulate_hw1f_exact(CURVE, params, 12, 2000, SEED)
    assert grid.shape == (2000, 13)
    # r(0) = alpha(0) = f(0,0) (x(0)=0) -> the curve forward, NOT params.initial_short_rate
    assert grid[0, 0] == pytest.approx(CURVE.instantaneous_forward(0.0), abs=1e-12)


def test_simulate_hw1f_exact_mean_matches_alpha():
    # E[r(t)] = alpha(t) = f(0,t) + sigma^2/(2 a^2)(1-e^{-a t})^2 since E[x]=0
    params = HullWhiteParams()
    a, sigma = params.mean_reversion_speed, params.short_rate_vol
    grid = simulate_hw1f_exact(CURVE, params, 12, 60000, SEED)
    t = 1.0
    alpha = CURVE.instantaneous_forward(t) + (sigma**2 / (2 * a**2)) * (1 - math.exp(-a * t)) ** 2
    assert np.mean(grid[:, 12]) == pytest.approx(alpha, abs=2e-4)


def test_simulate_hw1f_exact_reproducible():
    g1 = simulate_hw1f_exact(CURVE, HullWhiteParams(), 6, 500, SEED)
    g2 = simulate_hw1f_exact(CURVE, HullWhiteParams(), 6, 500, SEED)
    assert np.array_equal(g1, g2)


# --------------------------------------------------------------------------- #
# Per-driver martingale checks                                                #
# --------------------------------------------------------------------------- #
def test_hw1f_zcb_martingale_passes():
    checks, rate_grid, deflator = martingale_hw1f(CURVE, 12, (5.0, 10.0), 30000, SEED, 4.0)
    assert rate_grid.shape == (30000, 13)
    assert deflator.shape == (30000, 13)
    assert len(checks) == 2
    for c in checks:
        assert c.severity == "ERROR"
        assert c.passed, (c.check_id, c.n_std_errors)
        assert c.rel_error < 0.01


def test_g2pp_zcb_martingale_passes():
    checks = martingale_g2pp(CURVE, 12, (5.0, 10.0), 30000, SEED, 4.0)
    assert len(checks) == 2
    for c in checks:
        assert c.passed, (c.check_id, c.n_std_errors)
        assert c.rel_error < 0.01


def test_equity_forward_martingale_passes():
    _, rate_grid, deflator = martingale_hw1f(CURVE, 12, (5.0,), 20000, SEED, 4.0)
    checks = martingale_equity(rate_grid, deflator, 12, GBMParams(), 20000, SEED + 2, 4.0)
    assert len(checks) == 1
    c = checks[0]
    assert c.check_id == "MART-EQ-FWD"
    assert c.passed, c.n_std_errors
    assert c.target == pytest.approx(GBMParams().initial_index_level)


def test_fx_cip_martingale_passes():
    checks = martingale_fx(0.03, 0.01, 12, 0.10, 7.8, 20000, SEED, 4.0)
    assert len(checks) == 1
    c = checks[0]
    assert c.check_id == "MART-FX-CIP"
    assert c.passed, c.n_std_errors
    assert c.target == pytest.approx(7.8)


# --------------------------------------------------------------------------- #
# Diagnostics (informational, non-gating)                                     #
# --------------------------------------------------------------------------- #
def test_euler_bias_diagnostic_detects_bias():
    c = diagnostic_hw1f_euler_bias(CURVE, 12, 10.0, 4000, SEED)
    assert c.severity == "INFO"
    assert c.passed  # estimate finite -> reported
    # the educational Euler scheme is materially biased (several %), unlike the exact one
    assert c.rel_error > 0.01
    assert c.n_std_errors > 10.0


def test_pmeasure_breaks_martingale_under_P():
    _, rate_grid, deflator = martingale_hw1f(CURVE, 12, (5.0,), 20000, SEED, 4.0)
    c = martingale_equity_pmeasure(rate_grid, deflator, 12, GBMParams(), 20000, SEED + 3)
    assert c.severity == "INFO"
    assert c.passed  # upward drift present under P
    # the deflated asset drifts above S(0) under P
    assert c.estimate > GBMParams().initial_index_level


# --------------------------------------------------------------------------- #
# Gate orchestration                                                          #
# --------------------------------------------------------------------------- #
def test_g_mart_gate_passes_and_structure():
    report = evaluate_g_mart_gate(n_scenarios=20000, seed=SEED)
    assert isinstance(report, GMartGateReport)
    assert report.gate_id == "G-MART"
    assert report.status == "PASS"
    assert report.passed
    d = report.to_dict()
    ids = {c["check_id"] for c in d["checks"]}
    assert {"MART-HW1F-ZCB-5Y", "MART-HW1F-ZCB-10Y", "MART-G2PP-ZCB-5Y",
            "MART-G2PP-ZCB-10Y", "MART-EQ-FWD", "MART-FX-CIP"} <= ids
    # all ERROR checks pass; gate passed iff every ERROR check passes
    assert all(c["passed"] for c in d["checks"] if c["severity"] == "ERROR")
    assert d["diagnostics"]["worst_n_std_errors"] <= 4.0
    assert "use_restriction" in d


def test_g_mart_gate_json_roundtrip():
    report = evaluate_g_mart_gate(n_scenarios=8000, seed=SEED)
    import json
    parsed = json.loads(report.to_json())
    assert parsed["gate_id"] == "G-MART"
    assert parsed["n_checks"] == len(parsed["checks"])


def test_gate_fails_if_error_check_fails():
    # a synthetic report with one failing ERROR check must not pass
    good = MartingaleCheck("X", True, "ERROR", "", 1.0, 1.0, 0.01, 0.0, 0.0, 4.0)
    bad = MartingaleCheck("Y", False, "ERROR", "", 1.0, 2.0, 0.01, 50.0, 1.0, 4.0)
    info = MartingaleCheck("Z", False, "INFO", "", 1.0, 1.0, 0.01, 0.0, 0.0, 4.0)
    assert GMartGateReport("G-MART", "FAIL", [good, info]).passed  # INFO ignored
    assert not GMartGateReport("G-MART", "FAIL", [good, bad]).passed
