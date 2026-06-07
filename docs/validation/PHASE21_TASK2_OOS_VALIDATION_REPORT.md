# Phase 21 Task 2 -- Six-Driver Out-of-Sample Proxy Validation (FX included)

Run: 2026-06-06T23:26:24.401105+00:00

## Verdict: PARTIAL — OOS R^2 0.9498 < 0.95

Selected surface: **fx_mode=analytic, degree=1, max_interaction_order=3** (6 terms),
chosen by oos_rmse across BOTH fx modes and the full basis grid.

| fx_mode | (deg, max_int) | terms | OOS R^2 | OOS RMSE | overfit gap |
| --- | --- | --- | --- | --- | --- |
| analytic | (1, 3) | 6 | 0.9498 | 4686.0 | -0.0018 |
| analytic | (2, 3) | 21 | 0.7938 | 9500.9 | -0.0009 |
| analytic | (3, 2) | 46 | 0.5830 | 13511.0 | -0.0358 |
| analytic | (3, 3) | 56 | 0.3737 | 16557.3 | 0.0231 |
| analytic | (4, 3) | 91 | 0.0629 | 20254.0 | -0.2669 |
| learned | (1, 3) | 7 | 0.9483 | 4757.1 | -0.0016 |
| learned | (2, 3) | 28 | 0.6741 | 11944.6 | 0.0446 |
| learned | (3, 2) | 64 | 0.0844 | 20020.1 | 0.2567 |
| learned | (3, 3) | 84 | -0.2636 | 23518.8 | 0.4500 |
| learned | (4, 3) | 135 | -0.9402 | 29143.4 | -0.0294 |

## Capital comparison (selected surface vs nested benchmark, same eval states)

* Proxy VaR99.5: 182596.7 vs nested 172285.2 (rel err 5.99%)
* Proxy ES: 184421.7 vs nested 176257.3 (rel err 4.63%)
* SCR rel err: 15.97% (n_eval=500, nested_n_inner=96)

## FX-axis recovery

* Theoretical CIP-exact slope: -3846.15; recovered: -3846.15 (rel err 0.00%)

## Leakage / reproducibility

* Hold-out leakage-free: True (0 shared states; seeds 42 vs 20260607)
* Reproducibility digest: `fcf295bd845c3d3c644f394e2a8bcba9549c6355ed10b4219e7896ec1c1657d7`

## Governance

* ChangeRecord: c2f29042b5f44dd7b3670d7de87e09a2 (OWNER_REVIEW)
* MR-011: refreshed; MR-012: refreshed
* Audit integrity: True

## Notes

* FX-mode head-to-head (best OOS RMSE): analytic offset 4686.04 vs learned hexavariate 4757.11 — the control-variate design dominates the fully-learned FX axis at this educational scale.
* Proxy and nested capital are evaluated on the SAME eval outer states (seed 141), so the comparison isolates pure surface error; the nested benchmark uses 96 heavy inner Q-paths per state.
* FX-axis recovery: surface partial-FX slope -3846.15 vs CIP-exact theoretical -3846.15 (rel err 0.00%).
* verdict drivers: OOS R^2 0.9498 < 0.95
