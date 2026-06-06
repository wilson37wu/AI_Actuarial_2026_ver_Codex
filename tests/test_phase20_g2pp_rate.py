"""
Phase 20 Task 1 tests: enhanced G2++ rates driver and G-RATE2 gate.
"""

from datetime import date

import pytest

from par_model_v2.stochastic import (
    EnhancedG2PlusRateProcess,
    G2PlusParams,
    Measure,
    RiskFreeCurve,
    evaluate_g_rate2_gate,
)


def _curve():
    return RiskFreeCurve(
        tenors_years=(0.0, 1.0, 2.0, 5.0, 10.0, 30.0),
        zero_rates=(0.018, 0.019, 0.020, 0.023, 0.026, 0.028),
        currency="CNY",
        market="CN",
        valuation_date=date(2026, 6, 6),
        curve_id="CNY-G2PP-TEST-20260606",
        source_id="EDU-G2PP-TEST",
    )


def _params():
    return G2PlusParams(
        mean_reversion_x=0.12,
        mean_reversion_y=0.45,
        vol_x=0.010,
        vol_y=0.007,
        factor_correlation=-0.65,
        short_rate_floor=None,
        short_rate_ceiling=None,
    )


def test_analytic_zcb_fits_initial_curve_at_time_zero():
    curve = _curve()
    process = EnhancedG2PlusRateProcess(_params(), curve)

    for tenor in (0.25, 1.0, 2.5, 7.0, 20.0):
        assert process.zcb_price(0.0, 0.0, 0.0, tenor) == pytest.approx(
            curve.discount_factor(tenor),
            abs=1e-14,
        )


def test_zcb_price_responds_to_factor_states_and_maturity_identity():
    process = EnhancedG2PlusRateProcess(_params(), _curve())

    base = process.zcb_price(0.0, 0.0, 1.0, 10.0)
    higher_rate_state = process.zcb_price(0.01, 0.004, 1.0, 10.0)

    assert process.zcb_price(0.03, -0.02, 5.0, 5.0) == pytest.approx(1.0)
    assert higher_rate_state < base


def test_bond_option_formula_obeys_put_call_parity_and_bounds():
    curve = _curve()
    process = EnhancedG2PlusRateProcess(_params(), curve)
    expiry = 5.0
    maturity = 10.0
    strike = 0.82

    call = process.bond_option_price(expiry, maturity, strike, "call")
    put = process.bond_option_price(expiry, maturity, strike, "put")
    parity = curve.discount_factor(maturity) - strike * curve.discount_factor(expiry)

    assert process.bond_option_variance(expiry, maturity) > 0.0
    assert call - put == pytest.approx(parity, abs=1e-12)
    assert 0.0 <= call <= curve.discount_factor(maturity)
    assert put >= 0.0


def test_simulator_returns_exact_ou_factor_diagnostics():
    process = EnhancedG2PlusRateProcess(_params(), _curve())

    df = process.simulate(2500, 12, Measure.Q, seed=20260606, cap_zcb_at_par=False)

    assert set(["g2pp_x", "g2pp_y", "zcb_1y", "zcb_10y", "rate_model"]).issubset(df.columns)
    assert df["measure"].unique().tolist() == ["Q"]
    assert df["rate_model"].unique().tolist() == ["G2++"]
    assert len(df) == 2500 * 13
    terminal = df[df["month"] == 12]
    assert terminal["g2pp_x"].std() > terminal["g2pp_y"].std()


def test_simulator_rejects_invalid_measure_and_dimensions():
    process = EnhancedG2PlusRateProcess(_params(), _curve())

    with pytest.raises(ValueError, match="measure"):
        process.simulate(10, 12, "bad")
    with pytest.raises(ValueError, match="n_scenarios"):
        process.simulate(0, 12, Measure.Q)
    with pytest.raises(ValueError, match="t_months"):
        process.simulate(1, -1, Measure.Q)


def test_negative_rate_curve_preserves_uncapped_discount_factors_above_par():
    curve = RiskFreeCurve.flat(-0.006, currency="JPY", market="JP", valuation_date=date(2026, 6, 6))
    process = EnhancedG2PlusRateProcess(_params(), curve)

    df = process.simulate(20, 6, Measure.Q, seed=7, cap_zcb_at_par=False)

    assert process.zcb_price(0.0, 0.0, 0.0, 1.0) > 1.0
    assert df.loc[df["month"] == 0, "zcb_1y"].iloc[0] > 1.0


def test_g_rate2_gate_passes_all_plausibility_checks():
    report = evaluate_g_rate2_gate(EnhancedG2PlusRateProcess(_params(), _curve()))

    assert report.gate_id == "G-RATE2"
    assert report.status == "PASS"
    assert report.passed is True
    assert len(report.checks) == 6
    assert all(check.passed for check in report.checks)
    assert report.diagnostics.curve_fit_max_abs_error <= 1e-12
    assert report.diagnostics.put_call_parity_error <= 1e-10
    assert report.diagnostics.negative_rate_discount_factor > 1.0
