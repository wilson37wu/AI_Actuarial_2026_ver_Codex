# Phase 23 Task 3 - Management-Action Rule (Dynamic Bonus Cut)

Run: 2026-06-07T13:17:47.606184+00:00

## Verdict: PASS

Rule: `cut_factor = clip((CR - 0.90) / (1.10 - 0.90), 0, 1)`;
retained bonus = pre_floor + (1 - pre_floor) * cut_factor; max liability
relief = bonus_share * (1 - pre_floor) = 12.0%.
CR = A_ref / L with A_ref = 1.12 x fit-sample mean liability
(115996.9) = 129916.5 (leakage-free).

## Gates (fixed pre-registered, Task 1 design note s5)

* G1_oos_r2_with_actions_ge_0p95: PASS
* G2_var_rel_error_with_actions_le_0p10: PASS
* G3_with_actions_capital_le_without: PASS
* G4_rule_monotone: PASS
* G5_no_action_above_trigger: PASS

## Capital impact (nested ground truth, n_outer=500, n_inner=256)

| metric | without actions | with actions | reduction |
| --- | --- | --- | --- |
| mean liability | 115994.1 | 111677.7 | 4316.3 |
| VaR 99.5 | 171555.3 | 150968.6 | 20586.6 |
| ES | 176570.2 | 155381.8 | 21188.4 |
| SCR proxy | 55561.2 | 39290.9 | 16270.3 |

Action active on 44.2% of nested outer states (at/below trigger);
8.0% at/below the floor (maximum cut).

## Proxy OOS re-validation (with actions)

* OOS R2: 0.9983 (without actions: 0.9985; gate >= 0.95)
* Proxy VaR99.5 (with actions): 150202.5 vs nested 150968.6 (rel err 0.51%; gate <= 10%)
* ES rel err: 0.18%; SCR rel err: 1.69%

## Trigger sensitivity (floor = trigger - 0.20)

| trigger | floor | active share | nested VaR with | VaR reduction | SCR reduction | OOS R2 | VaR rel err | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.05 | 0.85 | 35.4% | 150968.6 | 20586.6 | 17616.3 | 0.9985 | 0.51% | PASS |
| 1.10 | 0.90 | 44.2% | 150968.6 | 20586.6 | 16270.3 | 0.9983 | 0.51% | PASS |
| 1.15 | 0.95 | 56.0% | 150968.6 | 20586.6 | 14850.0 | 0.9979 | 0.51% | PASS |

## Provenance

All inner-path arrays reused bit-identically from .phase22_task2_stage (Phase 22 Task 2, seeds 42/20260607/7, nested 500x256); cross-checked against the archived report before use; the selected surface (analytic, deg 3, max_int 2) was refit deterministically from the same staged fit targets.

## Limitations

* Trigger/floor/bonus-share/PRE/reference-coverage are educational placeholders pending credentialled management-practice data and APS X2 review.
* The action is applied at the outer node as a transform of the conditional liability; a full inner-path bonus mechanism (per-path declared-bonus dynamics) is a documented future refinement.
* Coverage ratio uses a fixed reference-asset proxy, not a projected asset portfolio at the horizon.

## Reproducibility

* Digest: `07f8bbd52193a960b1c24310da22c26b301ecd1556f99d8647a1a1efbdc029c6`

*EDUCATIONAL MODEL - management-action parameters are placeholders;
production sign-off withheld pending credentialled data + APS X2 review.*
