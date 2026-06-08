# Latest Cycle Status - 2026-06-08 (+08) (cycle 27) - READ FIRST

**Phase 26 Task 1 COMPLETE (PASS — design note, pre-registered gates, 13 new tests,
governance verify_all True). Next: Phase 26 Task 2 — per-driver composition transform
on the frozen copula.**

What this cycle did (design-note-first candidate selection + design note):

- Health gate (targeted, DISCLOSED): cycle 26 closed green 8-10h earlier; this cycle adds
  ONLY new additive files. compileall clean; P24T1/P25T1/P25T3/P25T4 + new P26T1 suites
  163 PASS / 0 FAIL; foreign-write mtime check clean; governance store backed up +
  hash-verified (/var/tmp/p26t1_build/GOV_BACKUP_pre_p26t1.json).
- CHOSEN candidate (a): full path-wise copula re-aggregation — quantified motivation:
  the P25T4 analytic re-anchoring (constant-share LEVEL transform) understates the nested
  path-wise reference 46,638.9 by 14.7% BEYOND bootstrap noise (outside 95% CI
  [35,793, 42,496]). NOT chosen: (b) credentialled calibration (human-blocked);
  (c) declaration-cadence refinement (DEFERRED — would be superseded by this phase's basis
  change; sensitivity 1.136 archived).
- NEW `par_model_v2/projection/pathwise_copula_reaggregation.py`: synthetic 7-driver
  t-copula level-vs-component pre-study — carve-out (non-cuttable) drivers dominate the
  tail, so the LEVEL transform understates the COMPONENT-basis VaR99.5 (~1.0% on CRN; sign
  stable seeds 42/7/2026; tail cuttable share 0.566 -> 0.470; re-ranking not mean shift).
  Sign evidence only; magnitude at Tasks 2-3.
- `scripts/build_phase26_task1_design_note.py` -> docs/validation/PHASE26_TASK1_DESIGN_NOTE.{json,md}
  + docs/PATHWISE_COPULA_REAGGREGATION_DESIGN_CARD.md. Verdict PASS. Idempotent verified.
- Pre-registered gates (s5, no gate-shopping): T2 copula FROZEN (df 2.9451 tol 1e-4; rho
  <= 1e-12), archive cross-check bit-identical first, sign gate full t SCR >= 39,794.3,
  sigma/alpha unchanged; T3 bootstrap >= 200x20k, HEADLINE nested 46,638.9 INSIDE 95% CI
  else decomposed + disclosed, SE <= 5%; T4 delta matrix + MR-010/MR-014 1% trigger + rank
  invariance; T5 UI 1.7.0 -> 1.8.0 ADDITIVE + PHASE 26 COMPLETE.
- Governance: ChangeRecord `40fb20ee3b9a41a7a2b6a47a587ada91` (governance_change)
  OWNER_REVIEW; audit 76->77; changes 49->50; verify_all True.
- Tests: 13 new PASS (tests/test_phase26_task1_design_note.py).
- REPAIRED (DISCLOSED): MODEL_DEV_LOG.md tail (cycle-26 truncation; a direct mount append
  VANISHED silently this cycle) — rebuilt OFF-MOUNT, whole-file cp + cmp verified.

**Next executable action: Phase 26 Task 2 — per-driver composition transform on the
frozen copula** (recover per-driver loss composition from the frozen margins per joint
scenario; relief on the CUTTABLE component only with per-scenario max_relief envelope clip;
governed sigma 0.225 / alpha 0.757 UNCHANGED; gates above; code_change ChangeRecord).

**Operating warnings (cycle 27):** ~44 s bash wall; MOUNT APPENDS UNRELIABLE — this cycle a
direct >>-append to MODEL_DEV_LOG.md vanished while the byte count grew; ALWAYS build/append
OFF-MOUNT (/var/tmp) then cp whole-file + cmp + grep-verify; PYTHONPATH=/var/tmp/pylibs:. ;
NEVER rewrite an existing large mounted file via the file tool; nohup does not survive
between bash calls; back up + hash-verify the governance store before any governance stage;
re-check mtimes for parallel-run foreign writes before governance/commit; next free risk ID
MR-015. Stage data: /var/tmp/p26t1_build, /var/tmp/p25t5_build, /var/tmp/p25t4_stage,
/var/tmp/p25t3_stage, /var/tmp/p25t2_stage, /var/tmp/p24t3_stage, /var/tmp/p23t2_stage
(losses.npz), /var/tmp/p23t4_stage, .phase22_task2_stage.

**Persisting blockers (human action):**
- Git ghost locks (`.git/index.lock`, `.git/HEAD.lock`, `.git/refs/heads/main.lock`) -
  commits land on `p22c9` via the alt-index workaround; push `p22c9:main` WORKS from the
  sandbox; locks only block fast-forwarding LOCAL main.
- Serialise/stagger the scheduled runs (Python-less Windows-shell runs waste cycles).
- Production sign-off residual: credentialled calibration + independent APS X2 review.
- Disk /sessions ~89%.
