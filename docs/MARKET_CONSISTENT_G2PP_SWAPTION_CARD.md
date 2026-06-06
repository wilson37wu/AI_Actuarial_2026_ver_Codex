# Market-Consistent G2++ Swaption Calibration Card

**Phase:** 20 - Market-Consistency and Multi-Factor Uplift (Task 2)

**Status:** Calibrated to an EDUCATIONAL PROXY swaption surface; pending martingale
validation (Task 3), capital propagation (Task 4), and independent review.

## Purpose

Task 2 makes the enhanced G2++ rate driver calibratable. It adds an analytic
European swaption pricer (Brigo-Mercurio one-dimensional Gaussian-quadrature
decomposition into an option on the fixed-leg coupon bond), Black (lognormal)
ATM pricing/implied-vol inversion for the targets, a derivative-free Nelder-Mead
calibration of (a, b, sigma, eta, rho), and the G-SWPN calibration-quality gate.

## Calibrated Parameters (educational proxy surface)

| Parameter | Symbol | Value |
| --- | --- | ---: |
| Mean reversion (factor 1) | a | 0.03454 |
| Mean reversion (factor 2) | b | 0.95828 |
| Volatility (factor 1) | sigma | 0.00637 |
| Volatility (factor 2) | eta | 0.00240 |
| Factor correlation | rho | -0.9082 |

Fit: implied-vol RMSE 54.7 bps, worst-point 173.0 bps, relative-price
RMSE 0.0270 across 24 ATM quotes. Gate **PASS**.

## Validation

- Analytic pricer cross-checked against Monte Carlo (within 4 standard errors).
- ATM payer/receiver swaption put-call (swap) parity holds to ~1e-16.
- Calibrated engine still reprices the input curve exactly (affine ZCB identity).

## Production Use Restriction

The swaption surface is a SYNTHETIC educational placeholder, not market data. Do
not use the calibrated parameters for production pricing, capital, or external
disclosure. Phase 20 Task 3 must add a market-consistency martingale validation
gate; Task 4 must propagate the driver through the capital stack; recalibration to
a validated market surface and independent reviewer sign-off remain required.
