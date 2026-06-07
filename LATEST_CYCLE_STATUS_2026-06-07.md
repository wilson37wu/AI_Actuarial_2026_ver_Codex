# Latest Cycle Status - 2026-06-07 (cycle 11)

**Phase 22 Task 5 COMPLETE (PASS) -> PHASE 22 COMPLETE (Tasks 1-5).
Next: Phase 23 Task 1 (research/design note: t-copula tail-dependence + management actions).**

What this cycle did:

- Offline-UI propagation: `scripts/build_ui_data.py` contract bumped additively 1.3.0 -> 1.4.0.
  UI now surfaces (a) Task 1 six-driver OOS REMEDIATED PASS (R2 0.9985) replacing the honest
  PARTIAL, (b) Task 2 seven-driver OOS PASS, (c) Task 3 G-LIQX calibrated exposure (22,000) +
  couplings as a first-class calibration panel (6/6 criteria, coupling bars vs 0.12 tolerance,
  is_placeholder=false), (d) Task 4 calibrated aggregation/tail read-outs (liquidity SCR 45.1,
  var-covar 28,991, copula 41,604, nested 48,707; MR-010 40.5% understatement) with the
  calibrated-vs-placeholder deltas embedded. Capital/tail loaders prefer the Phase 22 Task 4
  report with Phase 21 fallback.
- `viewer_data.json` rebuilt (governance = live store). Self-test extended with 4 Phase 22 checks:
  `node scripts/ui_app_self_test.cjs ui_app.html` -> **ok:true, 0 network / 0 JS errors (56 checks)**.
- New `scripts/build_phase22_task5_ui_propagation.py` (21 contract checks ALL PASS) + evidence
  report `docs/validation/PHASE22_TASK5_UI_PROPAGATION_REPORT.{json,md}`.
- Governance: ChangeRecord `880aeb5d621645c9adc8d2eb1f2ea88a` OWNER_REVIEW (code_change);
  audit 59->60; change records 32->33; verify_all True.
- Tests: 16 new PASS (`tests/test_phase22_task5_ui_propagation.py`); regression **187 PASS / 0 FAIL**.

**Next executable action: Phase 23 Task 1** - research/design note for the Tail-Dependence
Upgrade + Management Actions phase: (i) calibrated Student-t copula aggregation (df by
tail-dependence matching; addresses gaussian zero-tail-dependence residual behind MR-010);
(ii) management-action rule (dynamic reversionary-bonus cut under solvency stress) for the
nested ground truth + proxy with seven-driver OOS re-validation. State file updated
(`current_phase` = Phase 23). The offline UI continues to consume ONLY model output JSON.

**Operating warning:** Windows-side file-tool writes of long files truncate on sync to the Linux
mount. Write long repo files from bash and verify with ast.parse / json.loads / cmp.

**Persisting blockers (human action):**
- Git ghost locks (`.git/index.lock`, `.git/HEAD.lock`, `.git/refs/heads/main.lock`) - commits
  land on branch `p22c9` via the alt-index workaround; see GITHUB_PUSH_BLOCKER.md checklist.
- Local main ref stale behind ghost locks; remote main updated via `p22c9:main` pushes.
- Production sign-off residual: credentialled calibration + independent APS X2 review.

---

## Latest Cycle Status - 2026-06-07 (cycle 13 bookkeeping)

**Phase 23 Task 2 is COMPLETE based on existing evidence already present in the tree.**
Artifacts show the tail-matched Student-t copula aggregation ran at 2026-06-07T12:15:51Z:
`docs/validation/PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.json` verdict **PASS**,
df matched **2.9451**, t-copula SCR **46,756** vs nested **48,707** (4.0% rel error),
Gaussian baseline **41,472** (14.9% rel error), var-covar **28,991** (40.5% understatement).
MR-010 was refreshed, ChangeRecord `509699ae1f1d4adabe197bcf8419c92a` is OWNER_REVIEW,
and audit integrity is true.

This cycle did not rerun Python because this Windows shell has no `python`/`python3`/`py`, and
WSL is not installed. Work was limited to reconciling the already-generated Task 2 artifacts and
updating state/log bookkeeping. The active next task is **Phase 23 Task 3: management-action rule
(dynamic bonus participation cut under solvency stress) in nested ground truth + proxy; seven-driver
OOS re-validation**.

---

## Latest Cycle Status - 2026-06-07 (cycle 14)

**Phase 23 Task 3 COMPLETE (PASS, 5/5 fixed pre-registered gates).
Next: Phase 23 Task 4 (aggregation + tail diagnostics re-run WITH management actions).**

What this cycle did:

- NEW additive module `par_model_v2/projection/management_actions.py`: dynamic
  reversionary-bonus participation cut per Solvency II Art. 23 —
  `cut_factor = clip((CR - 0.90)/(1.10 - 0.90), 0, 1)`, CR = A_ref/L at the outer node,
  PRE floor 60%, max liability relief 12%, monotonicity GUARD at construction (rejects steep
  bands; the naive band-0.05 calibration is non-monotone and now unconstructible).
- Rule enters the NESTED conditional liability AND identically the LSMC proxy prediction as an
  analytic post-composition basis feature; A_ref leakage-free from the fit-sample mean
  (115,997 x 1.12). Phase 22 Task 2 staged primitives reused bit-identically (6/6
  archived-report cross-checks before any action work).
- **Results (nested 500x256):** VaR99.5 171,555 -> 150,969 (-12.0%); ES 176,570 -> 155,382;
  SCR proxy 55,561 -> 39,291 (-29.3%); action active on 44.2% of outer states. OOS R2 with
  actions 0.9983 (gate >=0.95); proxy-vs-nested VaR rel err 0.51% (gate <=10%); trigger
  sensitivity 1.05/1.10/1.15 all PASS.
- Governance: MR-014 opened + MITIGATED. **Disclosure:** the design note planned "MR-013" but
  that ID was already the G2++ market-consistency risk; the first governance run overwrote it,
  was caught the same cycle, and the original MR-013 was RESTORED from the pre-stage backup.
  ChangeRecord `cf22c050bca44a84a843fb262a2efb84` (assumption_change) OWNER_REVIEW;
  audit 62->63; changes 34->35; verify_all True.
- Tests: 29 new PASS (`tests/test_phase23_task3_management_actions.py`); regression
  **271 PASS / 0 FAIL**; `node scripts/ui_app_self_test.cjs ui_app.html` ok:true (no UI change
  this cycle — propagation is Task 5).
- Evidence: `docs/validation/PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.{json,md}`;
  `docs/MANAGEMENT_ACTION_RULE_CARD.md`.

**Next executable action: Phase 23 Task 4** — aggregation + tail-diagnostics re-run WITH
management actions: realise with-actions standalone capital losses, re-run the tail-matched
t(2.95) copula vs gaussian vs var-covar vs nested-with-actions, quantify with-vs-without
capital deltas, refresh MR-010/MR-014 (methodology_change ChangeRecord). Then Task 5:
offline-UI propagation (management-action panel; UI consumes ONLY model output JSON) +
PHASE 23 COMPLETE documentation.

**Persisting blockers (human action):** git ghost locks (commit via alt-index workaround on
branch `p22c9`); production sign-off residual (credentialled data + APS X2 review); disk ~90%.

---

## Latest Cycle Status - 2026-06-07 (cycle 15)

**Phase 23 Task 4 COMPLETE (PASS, 4/4 fixed pre-registered gates + governance).
Next: Phase 23 Task 5 (offline-UI propagation + PHASE 23 COMPLETE documentation).**

What this cycle did:

- NEW staged build `scripts/build_phase23_task4_aggregation_with_actions.py`: seven-driver
  aggregation + tail read-outs re-run WITH the governed Task 3 management-action rule.
  Without-actions losses reused bit-identically from the Task 2 stage after **13/13 archive
  cross-checks**; disclosed anchoring convention V_k = L_fit + (vec_k - mean_k); nested
  benchmark = rule applied to the full conditional liability; A_ref identical to Task 3.
- **Results (99.5% 1y SCR):** nested 48,707.4 -> **33,117.8** (-32.0%); tail-matched
  t(2.9451) 46,756.0 -> 25,652.9; gaussian 41,472.4 -> 23,921.8; var-covar 28,990.9 ->
  14,428.7 (56.4% understatement vs nested-with; MR-010 refreshed). Action active on 46.9%
  of outer nodes. RANK INVARIANCE gated: df re-matched at exactly 2.9451.
- **MATERIAL FINDING (disclosed):** copula-on-standalone-losses understates the nested
  with-actions benchmark (t rel err 4.0% -> 22.5%) because the action saturates (max relief
  12%) in the joint tail; gate PASS on the fixed <=25% arm; nested remains the reference.
- Governance: ChangeRecord `912ef3f92e714188baec4377ab59474d` (methodology_change)
  OWNER_REVIEW; MR-010 + MR-014 refreshed; audit 63->64; changes 35->36; verify_all True.
- Tests: 25 new PASS (`tests/test_phase23_task4_aggregation_with_actions.py`); regression
  **307 PASS / 0 FAIL** (incl. full p21 suite; heavy test run solo). UI self-test ok:true.
- Evidence: `docs/validation/PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.{json,md}`;
  `docs/WITH_ACTIONS_AGGREGATION_CARD.md`.

**Next executable action: Phase 23 Task 5** - offline-UI propagation: management-action
panel (rule card, active/floor shares, trigger sensitivity from Task 3) + with-actions
capital read-outs and the Task 4 saturation finding; contract bump 1.4.0 -> 1.5.0
(additive); UI keeps consuming ONLY model output JSON. Then PHASE 23 COMPLETE docs.

**Persisting blockers (human action):** git ghost locks (commit via alt-index workaround on
branch `p22c9`); production sign-off residual (credentialled data + APS X2 review); disk
/sessions ~90%; sandbox kills background shells between tool calls (run long tests solo).
