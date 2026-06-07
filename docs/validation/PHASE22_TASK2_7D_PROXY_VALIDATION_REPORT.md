# Phase 22 Task 2 - Seven-Driver Proxy OOS Validation

Run: 2026-06-07T07:09:52.925817+00:00

## Verdict: PASS - seven-driver surface (analytic, deg 3, max_int 2, 46 terms) validated OOS (R2=0.9985, VaR/ES/SCR rel err 0.51%/0.18%/1.26%, liquidity offset exact, leakage-free)

Selected surface: **analytic**, degree 3, max interaction 2, 46 terms.
Liquidity enters as an analytic CIR-affine forced-sale haircut offset; FX enters
as the CIP-exact translation offset.

| fx_mode | (deg, max_int) | terms | OOS R2 | OOS RMSE | overfit gap |
| --- | --- | --- | --- | --- | --- |
| analytic | (1, 3) | 6 | 0.9863 | 2449.6 | 0.0053 |
| analytic | (2, 3) | 21 | 0.9984 | 835.2 | -0.0008 |
| analytic | (3, 2) | 46 | 0.9985 | 816.0 | -0.0008 |
| analytic | (3, 3) | 56 | 0.9984 | 842.1 | -0.0009 |
| analytic | (4, 3) | 91 | 0.9980 | 934.8 | -0.0014 |
| learned | (1, 3) | 7 | 0.9863 | 2445.7 | 0.0052 |
| learned | (2, 3) | 28 | 0.9982 | 884.5 | -0.0011 |
| learned | (3, 2) | 64 | 0.9981 | 923.2 | -0.0012 |
| learned | (3, 3) | 84 | 0.9977 | 1012.4 | -0.0009 |
| learned | (4, 3) | 135 | 0.9973 | 1084.2 | -0.0034 |

## Capital comparison

* Proxy VaR99.5: 170684.6 vs nested 171555.3 (rel err 0.51%)
* Proxy ES: 176250.8 vs nested 176570.2 (rel err 0.18%)
* SCR rel err: 1.26%
* Nested benchmark: n_outer=500, nested_n_inner=256

## Liquidity analytic feature

* Offset max abs error: 0.000e+00
* Baseline liquidity impact: 0.000e+00
* Exposure notional: 30000; tau=19.0 years; initial premium=0.6177%

## Leakage / reproducibility

* Leakage-free: True
* Reproducibility digest: `d383b9e106b0c9862b41ef6daeaf82a637950e5f8594e9ff59352285cdb24210`

## Governance

* ChangeRecord: 5d68c9b6a7694031b325bbb03dca630f (OWNER_REVIEW)
* MR-011: refreshed; MR-012: refreshed
* Audit integrity: True

## Notes

* Liquidity is an analytic CIR-affine offset, not a learned coefficient; the validation therefore tests the fitted stochastic-valuation surface plus the exact liquidity feature on the same disjoint hold-out.
* Proxy and nested capital are evaluated on the SAME eval outer states (seed 141), isolating surface error; nested benchmark uses 256 inner Q-paths per state.
