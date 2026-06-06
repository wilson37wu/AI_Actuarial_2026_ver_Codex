# Multi-Driver 5D Capital -- Two-Factor G2++ Rate Driver Card

**Phase:** 20 - Market-Consistency and Multi-Factor Uplift (Task 4)

**Status:** Capital re-aggregation evidence at EDUCATIONAL calibration; verdict PASS - five-driver copula aggregation (selected: gaussian) reconciles to nested capital within 12.4% vs var-covar 39.7%; MR-010 five-driver mitigation confirmed.
Production sign-off withheld pending UI surfacing (Task 5), a fully G2++-consistent inner
nest, a larger outer sample, and independent (APS X2) review.

## Purpose

Re-aggregates the five-driver economic-capital proxy with the swaption-calibrated
two-factor G2++ rate driver replacing the single-factor Hull-White driver in the
outer real-world state, isolating the capital impact of the second (slope/curvature)
factor and the calibrated factor volatilities/correlation.

## Method

- OUTER rate state r_H = phi(t) + x(t) + y(t) (exact-OU factors), anchored to the same
  initial curve as HW1F; dominant factor x carries the governed 5x5 ESG cross-correlation,
  second factor y is correlated to x by the calibrated rho and otherwise orthogonal.
- INNER conditional valuation reuses the governed HW1F Q nest at r_H (real-world-outer /
  risk-neutral-inner; ASOP 56 section 3.5).
- Aggregation: 5x5 ESG var-covar (MR-010) and copula-on-realised-losses (MR-012),
  benchmarked to genuine five-driver nested capital.

## Headline result (educational proxy)

- Horizon short-rate dispersion falls from ~114 bps (HW1F placeholder) to ~49 bps
  (calibrated G2++): rate-risk and nested capital fall materially.
- Nested SCR: 104,132 (HW1F) -> 55,116 (G2++).
- G2++ var-covar understates nested by 39.7% (MR-010); G2++ copula (gaussian) reconciles
  within 12.4% (MR-012) -- the tail-dependent mitigation re-confirmed under the 2F driver.

## Model-use restriction

Educational only. The G2++ rate driver is calibrated to an educational-proxy swaption
surface; the inner nest remains HW1F. Not for production capital, pricing, or disclosure.
