# Phase 23 Task 2 -- Tail-Matched Student-t Copula Aggregation

**Verdict: PASS** (gate: PASS if t(df_matched) SCR rel err <= gaussian baseline rel err OR <= 25%; lambda_U + threshold sensitivity + capped-share disclosed)

EDUCATIONAL ONLY. Drivers: rate, equity, credit, lapse, mortality, fx, liquidity (n_obs=160).

## Benchmarks (99.5% 1y SCR)

| Aggregation | SCR | rel err vs nested |
|---|---|---|
| Nested ground truth | 48707.4 | -- |
| Var-covar (ESG factor) | 28990.9 | 40.5% (MR-010) |
| Gaussian copula (AIC incumbent, same-seed rerun) | 41472.4 | 14.9% |
| Gaussian copula (archived Phase 22 Task 4) | 41604.3 | 14.6% |
| **t(df=2.95) tail-matched** | **46756.0** | **4.0%** |

## Tail-dependence matching (>=3 thresholds; pooled MEDIAN df)

| q | E[tail obs] | pooled df | capped share | mean lambda_U | max lambda_U |
|---|---|---|---|---|---|
| 0.80 | 32 | 1.80 | 0% | 0.246 | 0.719 |
| 0.85 | 24 | 2.95 | 0% | 0.192 | 0.708 |
| 0.90 | 16 | 3.63 | 14% | 0.152 | 0.688 |

Matched df = **2.95** (median across thresholds; capped-pair share 5%).

## Disclosures

- df matched by tail-dependence inversion (Demarta-McNeil 2005), NOT by AIC/MLE on the body: pooled MEDIAN pairwise df, median across 3 thresholds.
- Pooled common-df t-copula is exchangeable in df across pairs -- a disclosed simplification (per-pair dfs are reported).
- Capped-pair share 5% (pairs whose inversion hit a df search bound; disclosed, not hidden).
- Gaussian baseline simulated with the same empirical marginals and seed family for an apples-to-apples SCR comparison.

Digest `42d37077c4c9fdae`; run `tcopula-tailmatch-7a27ad23`; config seed 20260607, n_sim 200000.

Standards: SOA ASOP 56 s3.5; SOA ASOP 25 s3.3; IA TAS M s3.6; Solvency II Delegated Reg. Art. 234; IFoA Life Aggregation & Simulation WP; Demarta-McNeil 2005 (t-copula tail dependence).
