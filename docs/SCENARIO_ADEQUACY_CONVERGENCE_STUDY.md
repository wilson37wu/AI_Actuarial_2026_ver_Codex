# Scenario-Adequacy Convergence Study

**Schema:** `scenario-adequacy-convergence-1.0`  
**Roadmap item:** s4.1 #5 (C-ROSS gap #6)  
**Generated:** 2026-07-09T12:40:20.262146+00:00  
**Inputs digest:** `9e4a2a4cc63ec999...`  
**Error model:** empirical_antithetic (8 replication(s) per count)  
**Deterministic discount base:** 3.000% (CBIRC 3.0% cap)  
**Seed policy:** base 42, stride 10000  

> Purely-additive diagnostic on the governed `TVOGEngine`. No governed headline figure is changed. **UNSIGNED**.

## Convergence report (TVOG with 95% CI bands)

| N | TVOG | iid SE | effective SE | 95% CI half-width | rel. CI | 95% CI band | runtime (s) | >= floor | <= tol |
|---:|---:|---:|---:|---:|---:|:--|---:|:--:|:--:|
| 500 | 8,514.5 | 571.9 | 47.6 | 93.3 | 1.10% | [8,421, 8,608] | 8.26 | . | Y |
| 1,000 | 8,528.5 | 405.0 | 42.9 | 84.1 | 0.99% | [8,444, 8,613] | 16.58 | . | Y |
| 2,000 | 8,489.6 | 280.8 | 27.7 | 54.3 | 0.64% | [8,435, 8,544] | 32.87 | Y | Y |
| 5,000 | 8,461.1 | 174.1 | 17.3 | 34.0 | 0.40% | [8,427, 8,495] | 82.41 | Y | Y |

## Convergence diagnostics

- Reference TVOG = 8,461.1 at N = 5,000; effective SE = 17.3 (SE(N) = 1,225.7 / sqrt(N)).
- Realised antithetic variance-reduction factor (iid SE / empirical SE): **10.0x**.
- Monte-Carlo error scaling exponent (fit of log SE vs log N): **-0.460** vs theoretical -0.500.
- N 500 -> 1,000: CI half-width ratio observed 0.901 vs theoretical 0.707 (sqrt law); |dTVOG| 14.0 within combined CI.
- N 1,000 -> 2,000: CI half-width ratio observed 0.645 vs theoretical 0.707 (sqrt law); |dTVOG| 38.9 within combined CI.
- N 2,000 -> 5,000: CI half-width ratio observed 0.626 vs theoretical 0.632 (sqrt law); |dTVOG| 28.5 within combined CI.

## Runtime benchmark

- Total wall-clock: **140.13 s** across 4 scenario counts x 8 replications.

## Recommendation memo

- **Recommended production scenario count: 2,000.**
- Binding constraint: **CBIRC C-ROSS floor** (effective precision needs ~202; regulatory floor is 2,000).
- Target precision (95% CI half-width <= 2.0% of |TVOG|) is **MET** at the 2,000-scenario floor (predicted 0.63% on the empirical_antithetic error model).
- CBIRC C-ROSS >= 2,000 floor is **satisfied** by the recommendation.
- Realised variance reduction from the governed antithetic sampler: **10.0x** in standard-error terms; ignoring it (naive iid) would over-provision to ~20,341 scenarios.
- Observed Monte-Carlo error scaling exponent -0.460 vs theoretical -0.500 (confirms 1/sqrt(N) convergence).
- Point estimate is **stable from N = 500** (each rung lands inside the previous rung's 95% CI).

_Diagnostic only; UNSIGNED. Governed portfolio TVOG headline untouched - re-baselining onto any revised scenario count remains owner-gated._
