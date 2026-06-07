# Phase 22 Task 1 — Six-Driver OOS Proxy-Validation Remediation

Run: 2026-06-07T05:16:56.420481+00:00

## Verdict: PASS — remediated six-driver surface (analytic, 46 terms) validated OOS (R^2=0.9985, VaR/ES/SCR rel err 0.50%/0.19%/1.25%, leakage-free, overfit gap=-0.0008, FX axis within 0.00%)

Remediation applied vs the Phase 21 Task 2 PARTIAL (OOS R² 0.949837):
fit targets de-noised 1 → 8 inner Q-paths/state; training states
500 → 2000; eval nested benchmark 96 → 256 inner; targeted
rate/equity-curvature candidate (deg-1 all drivers + {r^2, S^2, r*S} (9 terms, analytic FX offset)).

Final selected surface: **analytic** (46 terms) — targeted_wins=False;
selection by OOS RMSE across the FULL governed sweep + the targeted candidate.

| fx_mode | (deg, max_int) | terms | OOS R^2 | OOS RMSE | overfit gap |
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
| analytic_targeted | (2, 2) | 9 | 0.9930 | 1745.7 | 0.0020 |

## Capital comparison (final surface vs de-noised nested benchmark, same eval states)

* Proxy VaR99.5: 170711.8 vs nested 171573.6 (rel err 0.50%)
* Proxy ES: 176260.6 vs nested 176593.0 (rel err 0.19%)
* SCR rel err: 1.25% (n_eval=500, nested_n_inner=256)
* Phase 22 gate: OOS R² ≥ 0.95 AND VaR, ES AND SCR rel err ≤ 10% (stricter than Phase 21).

## FX-axis recovery

* Theoretical CIP-exact slope: -3846.15; recovered: -3846.15 (rel err 0.00%)

## Leakage / reproducibility

* Hold-out leakage-free: True (disjoint seeds; same protocol as Phase 21 Task 2)
* Reproducibility digest: `e2495368569cd388883cb76a8f9d5c13138259ed52f92d744de9a14679932262`

## Governance

* ChangeRecord: 6f88fd2a1fa449908a7cd8236ea30d33 (OWNER_REVIEW)
* MR-011: refreshed; MR-012: refreshed
* Audit integrity: True

## Notes

* FX-mode head-to-head (best OOS RMSE): analytic offset 816.02 vs learned hexavariate 884.55 — the control-variate design dominates the fully-learned FX axis at this educational scale.
* Proxy and nested capital are evaluated on the SAME eval outer states (seed 141), so the comparison isolates pure surface error; the nested benchmark uses 256 heavy inner Q-paths per state.
* FX-axis recovery: surface partial-FX slope -3846.15 vs CIP-exact theoretical -3846.15 (rel err 0.00%).
