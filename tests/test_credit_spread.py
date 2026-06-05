"""
Tests for the Phase 17 Task 1 CIR++ stochastic credit-spread driver
(``par_model_v2.stochastic.credit_spread``).

Coverage:
  * parameter validation (kappa/sigma>0, initial>=shift, floor<ceiling)
  * non-negativity / clamp of simulated spreads (full-truncation Euler)
  * mean reversion toward the long-run level
  * P vs Q distinctness (positive credit risk premium => Q spreads exceed P)
  * antithetic-normal shock-shape enforcement
  * simulate() DataFrame schema + measure enforcement
  * inner-Q conditioning starts at the conditioning spread state
  * reduced-form expected-credit-loss fraction in [0, 1) and monotone in spread
  * reproducibility (seed determinism)
"""

import numpy as np
import pytest

from par_model_v2.stochastic.credit_spread import (
    CreditSpreadParams,
    CreditSpreadProcess,
    _inner_q_spread_process,
    expected_credit_loss_fraction,
)
from par_model_v2.stochastic.esg_process import Measure, MeasureEnforcementError


def _shocks(n, k, seed=0):
    return np.random.default_rng(seed).standard_normal((n, k))


# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------

def test_params_defaults_placeholder():
    p = CreditSpreadParams()
    assert p.is_placeholder is True
    assert p.initial_x == pytest.approx(p.initial_spread - p.shift)
    assert p.long_run_x_p == pytest.approx(p.long_run_spread_p - p.shift)


@pytest.mark.parametrize("kw", [
    {"mean_reversion_speed": 0.0},
    {"mean_reversion_speed": -0.1},
    {"spread_vol": 0.0},
    {"initial_spread": 0.001, "shift": 0.002},   # initial < shift
    {"spread_floor": 0.2, "spread_ceiling": 0.1},
])
def test_params_validation_rejects_bad(kw):
    with pytest.raises(ValueError):
        CreditSpreadParams(**kw)


# --------------------------------------------------------------------------
# Simulation
# --------------------------------------------------------------------------

def test_simulate_array_shape_and_nonnegative():
    proc = CreditSpreadProcess()
    arr = proc._simulate_array(500, 24, Measure.P, _shocks(500, 24, 1))
    assert arr.shape == (500, 25)
    assert (arr >= proc.params.spread_floor).all()
    assert (arr <= proc.params.spread_ceiling).all()


def test_simulate_array_rejects_bad_shock_shape():
    proc = CreditSpreadProcess()
    with pytest.raises(ValueError):
        proc._simulate_array(10, 12, Measure.P, _shocks(10, 6))


def test_mean_reverts_toward_long_run():
    # Start well below the long-run level; the mean should drift upward.
    p = CreditSpreadParams(initial_spread=0.004, long_run_spread_p=0.020,
                           shift=0.002, mean_reversion_speed=0.8)
    proc = CreditSpreadProcess(p)
    arr = proc._simulate_array(4000, 120, Measure.P, _shocks(4000, 120, 3))
    assert arr[:, -1].mean() > arr[:, 0].mean()
    # ... and converge close to the (higher) long-run target after a long horizon
    assert abs(arr[:, -1].mean() - p.long_run_spread_p) < 0.002
    assert abs(arr[:, -1].mean() - p.long_run_spread_p) < abs(arr[:, 0].mean() - p.long_run_spread_p)


def test_q_has_positive_credit_risk_premium():
    proc = CreditSpreadProcess(CreditSpreadParams(market_price_of_credit_risk=0.3))
    z = _shocks(5000, 36, 9)
    pmean = proc._simulate_array(5000, 36, Measure.P, z)[:, -1].mean()
    qmean = proc._simulate_array(5000, 36, Measure.Q, z)[:, -1].mean()
    assert qmean > pmean


def test_simulate_dataframe_schema_and_measure():
    proc = CreditSpreadProcess()
    df = proc.simulate(40, 12, Measure.P, seed=5)
    assert list(df.columns) == ["scenario_id", "month", "credit_spread", "measure"]
    assert len(df) == 40 * 13
    assert (df["measure"] == "P").all()
    assert (df["credit_spread"] >= 0).all()


# --------------------------------------------------------------------------
# Inner-Q conditioning
# --------------------------------------------------------------------------

def test_inner_q_process_starts_at_conditioning_state():
    proc = _inner_q_spread_process(0.035, CreditSpreadParams())
    arr = proc._simulate_array(50, 6, Measure.Q, _shocks(50, 6, 2))
    assert arr[:, 0] == pytest.approx(0.035)


def test_inner_q_process_handles_deep_tail_below_shift():
    # conditioning spread below the default shift must not raise
    proc = _inner_q_spread_process(0.001, CreditSpreadParams(shift=0.002))
    arr = proc._simulate_array(20, 4, Measure.Q, _shocks(20, 4, 4))
    assert (arr >= 0).all()


# --------------------------------------------------------------------------
# Expected credit loss
# --------------------------------------------------------------------------

def test_expected_credit_loss_fraction_in_unit_interval():
    proc = CreditSpreadProcess()
    arr = proc._simulate_array(1000, 60, Measure.P, _shocks(1000, 60, 6))
    loss = expected_credit_loss_fraction(arr)
    assert loss.shape == (1000,)
    assert ((loss >= 0.0) & (loss < 1.0)).all()


def test_expected_credit_loss_monotone_in_spread_level():
    lo = np.full((100, 13), 0.005)
    hi = np.full((100, 13), 0.05)
    assert expected_credit_loss_fraction(hi).mean() > expected_credit_loss_fraction(lo).mean()


def test_expected_credit_loss_requires_2d():
    with pytest.raises(ValueError):
        expected_credit_loss_fraction(np.zeros(5))


# --------------------------------------------------------------------------
# Reproducibility
# --------------------------------------------------------------------------

def test_reproducible_same_seed():
    proc = CreditSpreadProcess()
    a = proc.simulate(30, 12, Measure.Q, seed=123)["credit_spread"].to_numpy()
    b = proc.simulate(30, 12, Measure.Q, seed=123)["credit_spread"].to_numpy()
    assert np.array_equal(a, b)
