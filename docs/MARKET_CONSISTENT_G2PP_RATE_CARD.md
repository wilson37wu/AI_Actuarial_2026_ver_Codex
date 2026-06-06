# Market-Consistent G2++ Rate Driver Card

**Phase:** 20 - Market-Consistency and Multi-Factor Uplift

**Status:** Implementation staged; educational parameters pending swaption-surface calibration.

## Purpose

The enhanced G2++ module adds a two-factor Gaussian interest-rate driver with
exact OU factor simulation, analytic zero-coupon bond prices fitted to the
initial curve, analytic European options on zero-coupon bonds, and a G-RATE2
plausibility gate.

## What Changed

- `EnhancedG2PlusRateProcess` in `par_model_v2/stochastic/g2pp_rate.py`
- `zcb_price(x_t, y_t, t, T)` includes the G2++ affine convexity adjustment.
- `bond_option_price(T, S, K, call/put)` uses the closed-form Gaussian bond
  option formula and put-call parity.
- `evaluate_g_rate2_gate()` checks curve fit, option variance, parity, bounds,
  simulated factor correlation, and negative-rate support.

## Production Use Restriction

Do not use the Phase 20 Task 1 parameters for production pricing, capital, or
external disclosure. Phase 20 Task 2 must calibrate the G2++ parameters to an
observed swaption surface; Phase 20 Task 3 must add a martingale validation gate;
Phase 20 Task 4 must propagate the driver through the capital stack; independent
review remains required.
