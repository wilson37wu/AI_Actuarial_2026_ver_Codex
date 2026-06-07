# Model Card -- Tail-Matched t-Copula Aggregation (Phase 23 Task 2)

**Classification: EDUCATIONAL.** Replaces AIC-only copula selection with a
Student-t copula whose df (2.95) is calibrated by matching the
empirical pairwise upper-tail dependence of the REALISED seven-driver
standalone capital losses (Demarta-McNeil closed-form inversion; pooled
MEDIAN pairwise df; median across thresholds [0.8, 0.85, 0.9]).

| Metric | Value |
|---|---|
| Nested SCR (truth) | 48707.4 |
| Var-covar SCR | 28990.9 (40.5% under; MR-010) |
| Gaussian copula SCR (same-seed) | 41472.4 (14.9%) |
| t(df-matched) SCR | 46756.0 (4.0%) |
| Verdict | PASS |

**Fixed gate (recorded Phase 23 Task 1, before benchmark errors were seen):**
PASS if t(df_matched) SCR rel err <= gaussian baseline rel err OR <= 25%; lambda_U + threshold sensitivity + capped-share disclosed.

**Limitations:** finite-threshold lambda_U estimator is noisy at n=160
(thresholds 0.80/0.85/0.90, not the large-n 0.97+ of the design pre-study);
single pooled df (exchangeable); empirical marginals bounded by realised
support; educational-proxy data; APS X2 independent review pending.

**Use restrictions:** see `t_copula_aggregation_use_restrictions()`.
Evidence: `docs/validation/PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.json`.
