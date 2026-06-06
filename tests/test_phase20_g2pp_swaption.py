"""
Phase 20 Task 2 tests: G2++ European swaption pricing, calibration, G-SWPN gate.

Fast tests exercise the analytic pricer (parity, monotonicity, Black benchmark,
curve identity).  One module-scoped fixture runs the full calibration/gate once
(deterministic) and a small Monte-Carlo cross-check validates the pricer.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from par_model_v2.stochastic.esg_process import G2PlusParams, Measure
from par_model_v2.stochastic.g2pp_rate import EnhancedG2PlusRateProcess
from par_model_v2.stochastic.g2pp_swaption import (
    black_implied_vol,
    black_swaption_price,
    calibrate_g2pp_to_swaptions,
    educational_proxy_curve,
    educational_proxy_vol_grid,
    evaluate_g_swpn_gate,
    g2pp_swaption_price,
    par_swap_rate,
    swap_schedule,
)


def _process(rho: float = -0.7) -> EnhancedG2PlusRateProcess:
    curve = educational_proxy_curve()
    params = G2PlusParams(
        mean_reversion_x=0.08,
        mean_reversion_y=0.60,
        vol_x=0.009,
        vol_y=0.005,
        factor_correlation=rho,
        short_rate_floor=None,
        short_rate_ceiling=None,
    )
    return EnhancedG2PlusRateProcess(params, curve)


# --------------------------------------------------------------------------- #
# Schedule / Black helpers
# --------------------------------------------------------------------------- #


def test_swap_schedule_semiannual():
    times, accruals = swap_schedule(5.0, 10.0, 2)
    assert len(times) == 20
    assert times[0] == pytest.approx(5.5)
    assert times[-1] == pytest.approx(15.0)
    assert all(a == pytest.approx(0.5) for a in accruals)


def test_black_implied_vol_roundtrip():
    curve = educational_proxy_curve()
    times, accruals = swap_schedule(5.0, 10.0, 2)
    fwd, annuity = par_swap_rate(curve, 5.0, times, accruals)
    price = black_swaption_price(annuity, fwd, fwd, 0.22, 5.0, "payer")
    vol = black_implied_vol(price, annuity, fwd, fwd, 5.0, "payer")
    assert vol == pytest.approx(0.22, abs=1e-4)


def test_black_atm_payer_equals_receiver():
    times, accruals = swap_schedule(3.0, 5.0, 2)
    fwd, annuity = par_swap_rate(educational_proxy_curve(), 3.0, times, accruals)
    payer = black_swaption_price(annuity, fwd, fwd, 0.2, 3.0, "payer")
    receiver = black_swaption_price(annuity, fwd, fwd, 0.2, 3.0, "receiver")
    assert payer == pytest.approx(receiver, rel=1e-12)


# --------------------------------------------------------------------------- #
# G2++ analytic swaption pricer
# --------------------------------------------------------------------------- #


def test_g2pp_atm_parity():
    proc = _process()
    times, accruals = swap_schedule(5.0, 10.0, 2)
    fwd, _ = par_swap_rate(proc.initial_curve, 5.0, times, accruals)
    payer = g2pp_swaption_price(proc, 5.0, times, accruals, fwd, "payer")
    receiver = g2pp_swaption_price(proc, 5.0, times, accruals, fwd, "receiver")
    assert payer == pytest.approx(receiver, abs=1e-10)
    assert payer > 0.0


def test_g2pp_offatm_swap_parity():
    proc = _process()
    times, accruals = swap_schedule(5.0, 10.0, 2)
    fwd, annuity = par_swap_rate(proc.initial_curve, 5.0, times, accruals)
    strike = fwd + 0.005
    payer = g2pp_swaption_price(proc, 5.0, times, accruals, strike, "payer")
    receiver = g2pp_swaption_price(proc, 5.0, times, accruals, strike, "receiver")
    # payer - receiver == annuity * (forward - strike)
    assert (payer - receiver) == pytest.approx(annuity * (fwd - strike), abs=1e-9)


def test_g2pp_price_monotonic_in_vol():
    times, accruals = swap_schedule(5.0, 10.0, 2)
    low = _process()  # vol_x 0.009
    high = EnhancedG2PlusRateProcess(
        G2PlusParams(
            mean_reversion_x=0.08, mean_reversion_y=0.60, vol_x=0.014, vol_y=0.008,
            factor_correlation=-0.7, short_rate_floor=None, short_rate_ceiling=None,
        ),
        low.initial_curve,
    )
    fwd, _ = par_swap_rate(low.initial_curve, 5.0, times, accruals)
    p_low = g2pp_swaption_price(low, 5.0, times, accruals, fwd, "payer")
    p_high = g2pp_swaption_price(high, 5.0, times, accruals, fwd, "payer")
    assert p_high > p_low


def test_g2pp_implied_vol_plausible():
    proc = _process()
    times, accruals = swap_schedule(3.0, 5.0, 2)
    fwd, annuity = par_swap_rate(proc.initial_curve, 3.0, times, accruals)
    price = g2pp_swaption_price(proc, 3.0, times, accruals, fwd, "payer")
    vol = black_implied_vol(price, annuity, fwd, fwd, 3.0, "payer")
    assert 0.02 < vol < 1.0


def test_g2pp_matches_monte_carlo():
    proc = _process()
    T, tenor = 3.0, 5.0
    times, accruals = swap_schedule(T, tenor, 2)
    fwd, _ = par_swap_rate(proc.initial_curve, T, times, accruals)
    analytic = g2pp_swaption_price(proc, T, times, accruals, fwd, "payer")

    months = int(round(T * 12))
    dt = 1.0 / 12.0
    arr = proc.simulate_arrays(120000, months, Measure.Q, seed=2024)
    r = arr["r_short"]
    disc = np.exp(-np.trapezoid(r, dx=dt, axis=1))
    xT, yT = arr["x"][:, -1], arr["y"][:, -1]
    cf = [fwd * accruals[i] for i in range(len(times))]
    cf[-1] += 1.0
    bond = np.zeros_like(xT)
    for ci, ti in zip(cf, times):
        bx = proc.factor_loading(proc.params.mean_reversion_x, T, ti)
        by = proc.factor_loading(proc.params.mean_reversion_y, T, ti)
        ratio = proc.initial_curve.discount_factor(ti) / proc.initial_curve.discount_factor(T)
        conv = proc._convexity_adjustment(T, ti)
        bond += ci * ratio * np.exp(-bx * xT - by * yT + conv)
    payoff = disc * np.maximum(1.0 - bond, 0.0)
    mc = float(np.mean(payoff))
    se = float(np.std(payoff) / math.sqrt(len(payoff)))
    assert abs(analytic - mc) < 4.0 * se


# --------------------------------------------------------------------------- #
# Proxy surface, calibration, and the G-SWPN gate (run once)
# --------------------------------------------------------------------------- #


def test_proxy_grid_shape_and_disclaimer():
    grid = educational_proxy_vol_grid()
    assert grid["source"] == "EDUCATIONAL_PROXY"
    assert "do not use in production" in grid["disclaimer"].lower()
    assert len(grid["quotes"]) == 24
    assert all(0.05 < q["black_vol"] < 0.50 for q in grid["quotes"])


@pytest.fixture(scope="module")
def gate_report():
    return evaluate_g_swpn_gate()


def test_gate_passes(gate_report):
    assert gate_report.status == "PASS"
    assert gate_report.passed
    assert all(c.passed for c in gate_report.checks)


def test_gate_has_seven_checks(gate_report):
    ids = [c.check_id for c in gate_report.checks]
    assert ids == [
        "G-SWPN-01", "G-SWPN-02", "G-SWPN-03", "G-SWPN-04",
        "G-SWPN-05", "G-SWPN-06", "G-SWPN-07",
    ]


def test_calibrated_params_valid(gate_report):
    p = gate_report.calibration.params
    assert p.mean_reversion_x > 0.0
    assert p.mean_reversion_y > p.mean_reversion_x
    assert p.vol_x > 0.0 and p.vol_y > 0.0
    assert -1.0 < p.factor_correlation < 1.0


def test_calibration_fit_quality(gate_report):
    cal = gate_report.calibration
    assert cal.n_quotes == 24
    assert cal.rmse_vol_bps <= 75.0
    assert cal.converged


def test_gate_to_dict_serialises(gate_report):
    import json

    payload = gate_report.to_dict()
    assert payload["gate_id"] == "G-SWPN"
    assert "EDUCATIONAL" in payload["use_restriction"]
    json.dumps(payload)  # must be JSON-serialisable
