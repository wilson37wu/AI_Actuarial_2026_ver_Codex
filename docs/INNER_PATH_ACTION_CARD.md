# Inner-Path Action Dynamics Card (Phase 24 Task 3)

**What changed:** the governed reversionary-bonus cut now acts on the
INNER-PATH policyholder-benefit cashflows (guaranteed + equity-guarantee
PVs, in-force scaled) instead of uniformly rescaling the whole outer-node
conditional liability. Credit-loss (asset-side) and analytic FX/liquidity
offsets are no longer relieved.

* Decision unchanged: pre-action outer-node coverage ratio CR = A_ref / L.
* Per inner path i: PV_with_i = PV_i - relief(CR) * B_i.
* Proxy gains the matching analytic base B_hat = clip(poly5 - kappa*C_det, 0, L_hat);
  kappa fit-calibrated (leakage-free).

**Verdict: PASS** - OOS R2 0.9984 (gate >= 0.95); VaR rel err
0.40% (gate <= 10%); nested SCR with actions: outer-node basis
39290.9 -> inner-path basis 40852.1 (delta +1561.2;
the outer-node transform over-relieved non-cuttable components).

**Residual:** full path-wise dynamic declaration (per-time-step action)
remains out of scope - documented for a future phase.

**Use restrictions:** EDUCATIONAL_DEMONSTRATION_ONLY.

Evidence: docs/validation/PHASE24_TASK3_INNER_PATH_ACTION_REPORT.{json,md}
