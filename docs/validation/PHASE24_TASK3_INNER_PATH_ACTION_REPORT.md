# Phase 24 Task 3 - Inner-Path Management-Action Dynamics Prototype

Run: 2026-06-07T18:33:42.725563+00:00

## Verdict: PASS

The governed bonus-cut rule moves from the outer-node liability transform
into the inner-path benefit cashflows: only in-force policyholder benefits
(guaranteed + equity-guarantee PVs) are cuttable; the asset-side credit
loss and the analytic FX/liquidity offsets are carved out. The action
decision remains the pre-action outer-node coverage ratio (horizon-level
declared-rate response).

## Gates (fixed pre-registered, Phase 24 Task 1 design note s5)

* G1_identical_action_basis_truth_and_proxy: PASS
* G2_oos_r2_with_actions_ge_0p95: PASS
* G3_var_rel_error_with_actions_le_0p10: PASS
* G4_monotone_on_inner_path_basis: PASS
* G5_with_le_without_and_no_action_above_trigger: PASS

## Capital: outer-node vs inner-path with-actions basis (nested truth, n=500)

| metric | without actions | with (outer-node, Phase 23) | with (inner-path, this task) | inner - outer |
| --- | --- | --- | --- | --- |
| mean liability | 115994.1 | 111677.7 | 112273.5 | 595.7 |
| VaR 99.5 | 171555.3 | 150968.6 | 153125.5 | 2156.9 |
| ES | 176570.2 | 155381.8 | 157827.8 | 2446.0 |
| SCR proxy | 55561.2 | 39290.9 | 40852.1 | 1561.2 |

The outer-node transform relieves the asset-side credit-loss component and the analytic FX/liquidity offsets as if they were cuttable bonus; the inner-path basis restricts the cut to policyholder-benefit cashflows, so it relieves LESS and is the more conservative (and more faithful) with-actions basis.

## Proxy OOS re-validation (inner-path with-actions basis)

* OOS R2: 0.9984 (without actions: 0.9985; gate >= 0.95)
* Proxy-vs-nested VaR99.5 rel err: 0.40% (gate <= 10%)
* ES rel err: 0.13%; SCR rel err: 1.22%
* Action active on 44.2% of nested outer states; 8.0% at the floor.

## Proxy credit carve-out (matching analytic post-composition base)

* kappa (fit-calibrated, leakage-free): 1.0368
* val nodes: mean abs rel err 0.82%, corr 0.9983
* nested nodes: mean abs rel err 0.89%, corr 0.9963
* credit share of 5d liability (nested mean): 15.87%

## Residual (documented)

Full path-wise dynamic declaration (action re-evaluated at every inner time step on a path-wise solvency position) remains OUT of scope (Phase 24 Task 1 design note, Method B scope note); the relief factor is constant across the inner paths of one outer node. A per-time-step declared-rate mechanism is the documented future refinement.

## Provenance

All inner-path component decompositions are BIT-IDENTICAL re-runs of the archived Phase 22 Task 2 stage (.phase22_task2_stage; seeds 42/20260607/142; exact equality of the per-node total enforced at every slice); the L7 arrays and fit-mean are the archived Phase 23 Task 3 stage (/var/tmp/p23t3_stage), digest-matched to the archived report.

## Limitations

* Management-action parameters are educational placeholders pending credentialled data + APS X2 review.
* Declared-rate response is horizon-level (outer-node decision); full path-wise declaration is a documented residual.
* The proxy credit carve-out is an expected-path approximation with a single fit-calibrated level factor; per-node approximation error is disclosed in credit_carveout_diagnostics.
* Coverage ratio uses a fixed reference-asset proxy.

## Reproducibility

* Digest: `46b51c6ba1db103572e132293e82bf0e1b07eb84cd85832f6007e41aae2b4b85`

*EDUCATIONAL MODEL - management-action parameters are placeholders;
production sign-off withheld pending credentialled data + APS X2 review.*
