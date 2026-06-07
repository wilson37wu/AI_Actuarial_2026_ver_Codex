# Management-Action Rule Card (Phase 23 Task 3)

**Rule:** dynamic reversionary-bonus participation cut under solvency stress
(Solvency II Art. 23: objective, realistic, verifiable, monotone).

* cut_factor = clip((CR - 0.90) / (1.10 - 0.90), 0, 1) (retained-bonus factor)
* CR = A_ref / L_pre_action at the outer node; A_ref = 1.12 x fit-sample mean
* PRE floor: at least 60% of participating bonus always retained
* Max liability relief: 12.0%

**Verdict: PASS** - nested VaR99.5 reduced 20586.6 (12.00%),
SCR proxy reduced 16270.3; OOS R2 with actions 0.9983; VaR rel err 0.51%.

**Where it enters:** nested conditional liability (ground truth) AND the LSMC
proxy prediction as an analytic post-composition feature - no new learned
coefficients, no change to any governed upstream module.

**Use restrictions:** EDUCATIONAL_DEMONSTRATION_ONLY - parameters are
placeholders pending credentialled management-practice data + APS X2 review.

Evidence: docs/validation/PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.{json,md}
