# Phase 21 Task 3 — Liquidity-Premium Driver Calibration (G-LIQ)

**Run:** 2026-06-07 01:18:49 UTC
**Market:** HKD (educational-proxy liquidity premium / funding spread)
**Gate G-LIQ:** PASS ✅

## What this is

The CIR++ liquidity-premium / funding-spread driver is the **seventh** —
and the **last documented-but-omitted** — risk driver of the multi-driver
economic-capital proxy (rate, equity, credit spread, dynamic lapse, mortality
trend, FX, liquidity). This task calibrates it to educational-proxy HKD
history, mirroring the GBM/HW1F/CIR/OU-lapse calibrators.

## Calibrated parameters

| Parameter | Value |
|---|---|
| Mean reversion kappa_l | 0.9345 /yr (half-life 0.7 yr) |
| Long-run premium (P) | 0.0063 (63 bp) |
| Premium vol sigma_l | 0.0213 |
| Market price of liquidity risk lambda_l | 2.0000 |
| CIR++ shift | 0.0010 |
| Initial premium l(0) | 0.0062 |
| Feller ratio (2 kappa b / sigma^2) | 21.71 (holds) |
| Observations | 240 monthly |
| Fit R^2 (homoscedastic CIR regression) | 0.0426 |

## G-LIQ criteria

| Criterion | Outcome |
|---|---|
| c1_min_obs | PASS |
| c2_kappa_in_band | PASS |
| c3_long_run_in_band | PASS |
| c4_sigma_in_band | PASS |
| c5_lambda_in_band | PASS |
| c6_not_placeholder_with_audit | PASS |

**Evidence:** HKD: n=240, kappa=0.9345, long_run=0.0063 (63bp), sigma=0.0213, lambda=2.0000

## Governance

- ChangeRecord `07880f42a2b84174a54b6261c0fd7131` — status **APPROVED** (assumption_change)
- PARAM_CHANGE audit entries: cb76cf75759a41e59eec55511057907c
- MR-011 (multi-driver proxy educational): **MITIGATED**
- MR-012 (driver omissions / educational calibration): **MITIGATED**

## Methodology

Delegated homoscedastic CIR OLS transition regression (one tested estimator
for both CIR++ drivers — credit and liquidity): kappa_l and the P long-run
premium from the regression, sigma_l from the residual variance, lambda_l from
the documented risk-neutral long-run anchor via b^Q - b^P = lambda_l sigma_l^2 / kappa_l.

## Model-use restrictions

EDUCATIONAL ONLY. Single systemic liquidity factor; educational-proxy fixture;
single-path OLS; automation-driven sign-off. Production use requires a
credentialled liquidity-premium series, an ML/Kalman estimator with standard
errors, and an independent APS X2 review. Seven-driver capital aggregation is
Phase 21 Task 4 — capital evidence remains six-driver until then.

*Standards: SOA ASOP 56 3.1.3/3.4; SOA ASOP 25 3.3; IA TAS M 3.4/3.5/3.6;
EIOPA VA illiquidity-premium methodology; CIR (1985); Brigo-Mercurio (2006).*
