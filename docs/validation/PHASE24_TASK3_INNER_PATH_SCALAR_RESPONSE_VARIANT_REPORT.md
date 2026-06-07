# Phase 24 Task 3 - Inner-Path Management-Action Dynamics Prototype

Run: 2026-06-07T18:22:44.838+00:00

## Verdict: PASS

The governed bonus-cut decision is applied to the projected cuttable bonus
cashflow PV, not only as an outer-node transform of the full liability.
Response factor: 85%; max cashflow relief at floor:
bonus_share 30% x (1-PRE 60%) x response 85% = 10.2%.

## Fixed Task 1 gates

* G1_inner_path_oos_r2_ge_0p95: PASS
* G2_inner_path_var_rel_error_le_0p10: PASS
* G3_inner_path_capital_le_without_actions: PASS
* G4_inner_path_monotone: PASS

## Capital impact (nested ground truth)

| basis | mean | VaR99.5 | ES | SCR |
| --- | --- | --- | --- | --- |
| without actions | 115994.1 | 171555.3 | 176570.2 | 55561.2 |
| outer-node Phase 23 basis | 111677.7 | 150968.6 | 155381.8 | 39290.9 |
| **inner-path cashflow basis** | **112325.2** | **154056.6** | **158560.1** | **41731.4** |

Outer-node vs inner-path delta: VaR 3088.0, SCR 2440.5;
positive means the cashflow basis gives less immediate relief than the
Phase 23 outer-node transform.

## Proxy OOS re-validation

* OOS R2: 0.9983
* Proxy VaR99.5: 153274.8 vs nested 154056.6; rel err 0.51%
* ES rel err 0.18%; SCR rel err 1.60%
* Active share 44.2%; floor share 8.0%

## Provenance

The same Phase 22 Task 2 staged primitives and selected seven-driver proxy
surface were cross-checked before use. Cross-checks: 6.

## Limitations

* Horizon-level prototype only; no monthly path-wise bonus declaration loop.
* Bonus cashflow response factor 0.85 is an educational placeholder for recognition lag / already-vested bonus inertia.
* This evidence draft is derived from archived Phase 23 Task 3 report values because Python/pytest is unavailable in the current Windows shell; rerun the Python staged builder in a Python-enabled environment for full array-level verification.
* Reference assets remain the fixed leakage-free Phase 23 proxy.

Digest `22aa9ee12d7562f9a40bb0a368a8731f779e817add529d11e00277ffb6349aec`.
