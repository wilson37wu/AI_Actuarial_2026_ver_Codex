# Lapse Behavioural-Index Calibration - Limitation Card

**Classification:** EDUCATIONAL ONLY - not a production persistency assumption.

## Scope

Phase 19 Task 5 calibrates the systemic lapse behavioural-index used by the
multi-driver economic-capital proxy.  The observed series is monthly
actual-to-expected lapse experience, transformed as `b_t = log(A/E_t)` and fitted
with the exact OU AR(1) transition:

`b_t = phi * b_{t-1} + theta_b * (1 - phi) + eps_t`

The calibration recovers `kappa_b`, `theta_b`, and `sigma_b`; the capital
projection starts from central `b(0)=0` so the tail reflects symmetric
behavioural uncertainty rather than a point-in-time experience deviation.

## Evidence

- G-LAPSE PASS on 240 monthly educational-proxy HK PAR A/E observations.
- `kappa_b=0.7854/yr`, half-life `0.88yr`.
- Long-run level `theta_b=-0.0360`, equivalent to A/E `0.965`.
- Behaviour volatility `sigma_b=0.1781`; stationary std `0.1421`.
- APPROVED assumption ChangeRecord and PARAM_CHANGE audit entry recorded in the
  GovernanceStore.

## Model-Use Restrictions

- The fixture is an educational proxy, not credentialled actual-vs-expected
  persistency experience.
- The estimator is a single-path OLS fit with no exposure weighting, standard
  errors, or product/cohort/duration segmentation.
- The behavioural index is one systemic lapse-level multiplier; it does not
  replace the separate dynamic lapse function that responds to interest-rate
  incentives.
- Production use requires a credentialled persistency study, exposure-weighted
  or maximum-likelihood estimation, assumption-owner approval, and independent
  APS X2 review.

## Standards

SOA ASOP 7 s3.3; SOA ASOP 25 s3.3; SOA ASOP 56 s3.4/s3.5; IA TAS M
s3.5/s3.6/s3.7.
