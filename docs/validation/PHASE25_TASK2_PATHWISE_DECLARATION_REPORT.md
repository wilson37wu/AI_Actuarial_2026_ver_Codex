# Phase 25 Task 2 - Path-Wise Bonus Declaration in the Nested Truth

Run: 2026-06-07T22:22:26.222567+00:00

## Verdict: PASS

The governed bonus-cut decision is re-evaluated at EVERY inner month on a
path-wise coverage proxy (CR_t = rolled-forward reference assets / remaining
pre-action path liability); the Phase 24 Task 3 horizon-level basis is
retained as the sensitivity variant and the without-actions basis is
unchanged bit-identically (slice-enforced archive cross-check).

## Gates (fixed pre-registered, Phase 25 Task 1 design note s5)

* G1_carveouts_preserved_relieved_within_envelope: PASS
* G2_sign_gate_pathwise_scr_ge_horizon_scr: PASS
* G3_monotonicity_guard_pathwise_basis: PASS
* G4_without_actions_bit_identical: PASS
* G5_horizon_basis_reproduced: PASS
* G6_no_action_above_trigger: PASS

## Capital: horizon-level vs path-wise declaration basis (nested truth, n=500)

| metric | without actions | with (horizon, P24T3) | with (path-wise, this task) | pathwise - horizon |
| --- | --- | --- | --- | --- |
| mean liability | 115994.1 | 112273.5 | 112305.2 | 31.7 |
| VaR 99.5 | 171555.3 | 153125.5 | 158944.1 | 5818.5 |
| ES | 176570.2 | 157827.8 | 163343.6 | 5515.8 |
| SCR proxy | 55561.2 | 40852.1 | 46638.9 | 5786.8 |

SCR delta relative to the horizon basis: 14.17% (MR-010/MR-014 Task 4
refresh trigger at 1%: REQUIRED).

The horizon-level basis freezes the maximum cut at stressed outer nodes for the whole projection while the path-wise basis RESTORES the bonus on recovering inner paths (and cuts on deteriorating paths from healthy nodes), so the path-wise basis relieves LESS in the tail and its with-actions SCR is the more conservative read-out (recognition-lag effect, two-sided).

## Path-wise declaration diagnostics

* Inner paths with at least one cut: 41.4% (mean across nodes)
* Cut-then-restored inner paths: 29.4% (restoration is a real dynamic)
* Nodes with any inner-path action: 100.0%; with any restoration: 100.0%
* Mean initial path-wise coverage ratio: 1.344
* Relieved-amount envelope clip binding on 0.0% of nodes (path-wise)

## Horizon-basis consistency (sensitivity variant retained)

Horizon-basis SCR reproduced vs the archived P24T3 report: |diff| =
8.58e-06 (match).

## Residuals documented (Task 3 items)

* Declaration frequency: monthly inner-step declarations; an annual declaration cadence (with board-discretion smoothing) is the Task 3 documentation item.
* Adaptedness: the coverage proxy discounts remaining cashflows with the realised inner path (perfect-foresight proxy); an adapted valuation would require nested-nested simulation.
* The node-level analytic FX/liquidity offset enters the path-wise proxy undecayed.

## Limitations

* Management-action parameters are educational placeholders pending credentialled data + APS X2 review.
* The proxy (LSMC) side still uses the horizon-level basis; the matching path-wise proxy basis feature is Task 3.
* Coverage ratio uses a fixed reference-asset proxy rolled forward at the inner short rate.

Reproducibility digest: `9f8f9b33c998bb04920cd116824d48d97f225552eb49ed19ed574e85dd896450`
