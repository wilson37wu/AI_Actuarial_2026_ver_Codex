# Phase 25 Task 3 - Matching Path-Wise Proxy Basis + Seven-Driver OOS Re-Validation

Run: 2026-06-07T23:28:50.191644+00:00

## Verdict: PASS

The LSMC proxy gains the matching analytic path-wise action basis
(relieved_hat = alpha * phi_sigma(CR_hat) * clip(B_hat, 0, L_hat); sigma,
alpha and kappa calibrated on the FIT sample only), so truth and proxy share
an IDENTICAL action basis (G1 convention) and the seven-driver OOS
re-validation runs at the unchanged Phase 22 gates.

## Gates (fixed pre-registered, Phase 25 Task 1 design note s5)

* G1_identical_pathwise_action_basis_truth_and_proxy: PASS
* G2_oos_r2_with_actions_ge_0p95: PASS
* G3_var_rel_error_with_actions_le_0p10: PASS
* G4_monotone_on_pathwise_basis: PASS
* G5_leakage_free_calibration_and_no_action_above_trigger: PASS

## OOS re-validation (with actions, path-wise basis)

* OOS R^2: **0.9978** (gate >= 0.95); without actions 0.9985
* Proxy VaR99.5 158306.1 vs nested 158944.1; rel err **0.40%** (gate <= 10%)
* ES rel err 0.01%; SCR rel err 1.16%
* Nested SCR with-actions (path-wise) 46638.9; without 55561.2

## Surface calibration (FIT sample only, leakage-free)

* sigma = 0.225 (effective path-wise CR dispersion; grid interior: True)
* alpha = 0.757; fit R^2 on per-node relieved amounts = 0.8006
* kappa (credit carve-out, P24T3 reproduced) = 1.0368

## Candidate comparison (selection on FIT evidence only)

Selected: **b_smoothed_relief_response_surface**. Candidate (a) zero-shock + level factor lambda =
6.01 achieves fit R^2 -15.152 (active on 38% of fit nodes vs
truth 95%): The zero-shock path misses diffusion-driven cuts at mid-coverage nodes (state-dependent bias: exact in the saturated deep tail, near-zero signal at mid coverage), so one level factor cannot match the per-node relieved amounts; disclosed and retained for the cadence sensitivity.

## Relieved-amount approximation (disclosed)

| sample | corr | mean abs err | active truth | active proxy |
| --- | --- | --- | --- | --- |
| validation (60) | 0.992 | 334.2 | 100% | 100% |
| nested eval (500) | 0.984 | 414.0 | 100% | 100% |

Envelope clip binding: truth 0.0% / proxy 0.0% of nested nodes.

## Declaration-cadence sensitivity (residual read-out)

Annual vs monthly declaration on the deterministic basis: mean relieved
ratio 1.136 (monthly 609.7 -> annual 692.5); max node delta 1292.4.

## Truth consistency

Nested with-actions (path-wise) SCR reproduces the archived P25T2 report:
|diff| = 0.00e+00 (match).

## Residuals documented

* Declaration cadence: the truth declares monthly; the annual-cadence sensitivity is quantified on the deterministic expected-path basis (see declaration_cadence_sensitivity).
* Adaptedness: the truth coverage proxy discounts remaining cashflows with the realised inner path (perfect-foresight proxy); an adapted valuation would require nested-nested simulation.
* The node-level analytic FX/liquidity offset enters the coverage proxy undecayed.
* The effective dispersion sigma is constant across nodes; a (CR, vol)-state-dependent sigma is the documented refinement.

## Limitations

* Management-action parameters are educational placeholders pending credentialled data + APS X2 review.
* The proxy relieved amount is an analytic approximation of the per-node inner-path mean; per-node error disclosed in relieved_approximation_diagnostics.
* Tail diagnostics + MR-010/MR-014 refresh on the path-wise basis are Task 4 (refresh trigger MET at Task 2: +14.17%).

Reproducibility digest: `2960b95ea36ffabeadc18c96cb1420e4c43a40a5380c47bd0d0f0499a9970675`
