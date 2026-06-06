# Market-Consistency (Martingale) Gate Card -- G-MART

**Phase:** 20 - Market-Consistency and Multi-Factor Uplift (Task 3)

**Status:** Martingale evidence at EDUCATIONAL calibration; gate PASS. Production
sign-off withheld pending capital re-aggregation (Task 4), UI surfacing (Task 5),
recalibration to a validated market surface, and independent (APS X2) review.

## Purpose

G-MART is an output-only, additive validation gate that verifies the economic-scenario
generators are arbitrage-free under the risk-neutral measure Q. With the money-market
account B(t) = exp(int_0^t r ds) as numeraire, every traded asset deflated by B(t) must
be a Q-martingale. The gate tests these identities by Monte-Carlo within a k-standard-error
band, so each PASS is a statistical hypothesis test, not an arbitrary point comparison.

## Identities tested

| Driver | Identity |
| --- | --- |
| HW1F rates (exact) | E^Q[ D(t) P_HW(t,T) ] = P(0,T) |
| G2++ / 2F rates | E^Q[ D(t) P_G2(t,T) ] = P(0,T) |
| GBM equity | E^Q[ D(t) S(t) exp(q_S t) ] = S(0) |
| FX (covered interest parity) | E^Q_d[ D_d(t) X(t) exp(r_f t) ] = X(0) |

The deflator for the analytic-bond checks uses the trapezoidal integral of the simulated
short rate (O(dt^2)); the equity/FX checks use the left-point integral that matches the
GBM/FX Euler drift exactly, so the discrete discounted-asset identity is exact there.

## Result (educational proxy; seed 20260606)

- Gate **PASS**: worst error 1.22 sigma, max relative error 3.90e-04 over 40000 paths,
  horizon t = 1.00y.
- Drivers covered: HW1F rates, G2++ rates, GBM equity, FX (CIP).

## Honest diagnostics (informational, non-gating)

- **MART-HW1F-EULER-BIAS:** the EDUCATIONAL monthly-Euler `HullWhiteRateProcess.simulate`
  (mean-reversion-to-forward, no convexity term, r0 = params.initial_short_rate) carries a
  ~7% martingale bias vs the exact dynamics. Use the exact HW1F simulation for any
  market-consistent valuation; the educational Euler path generator is for illustration only.
- **MART-PQ-MEASURE:** under the real-world measure P the discounted equity is NOT a
  martingale -- it drifts up by exp(ERP*t). This confirms the martingale property is
  genuinely Q-specific (P/Q separation, G-05 / MR-004).

## Model-use restriction

EDUCATIONAL market-consistency evidence. The martingale gate confirms the simulators are arbitrage-free under Q at the tested horizon and Monte-Carlo accuracy; it is NOT a production sign-off. Calibration to a validated market surface and independent (APS X2) review remain pending.
