# Latest Cycle Status - 2026-06-08 (+08) (cycle 25) - READ FIRST

**Phase 25 Task 4 COMPLETE (PASS 4/4 gates + governance verify_all True).
Next: Phase 25 Task 5 - UI contract 1.6.0 -> 1.7.0 ADDITIVE (path-wise declaration +
delta-matrix + tail-diagnostics panels consume ONLY model-output JSON) + PHASE 25 COMPLETE
documentation.**

What this cycle did (path-wise tail diagnostics + capital-delta matrix + REQUIRED
MR-010/MR-014 refresh; trigger was MET at Task 2 with +14.17%):

- Health gate first: full regression green - **2,684 tests PASS / 0 FAIL across all 94 files**
  (file/class/node-chunked under the 44 s wall; this is the TRUE pytest total - prior cycles'
  "386/430" tallied only a subset); ui_app self-test ok:true; governance store backed up +
  hash-verified before governance.
- REPAIRED `.claude-dev/MODEL_DEV_STATE.json` - corrupted by the cycle-24 mount-staleness
  rewrite (unterminated string + duplicated tail); truncated at last clean line, P25T2 entry
  closed, P25T3 entry reconstructed from the archived report; json-valid again.
- NEW `par_model_v2/projection/pathwise_tail_diagnostics.py`: t/gaussian path-wise read-outs
  via ANALYTIC RE-ANCHORING - governed P25T3 surface (sigma 0.225, alpha 0.7567) + FIT benefit
  share (beta_fit 0.8450, leakage-free) applied ONCE to the anchored joint level through the
  IDENTICAL envelope transform as truth/proxy; CRN vs horizon basis; NOT a full path-wise
  copula re-aggregation (documented next-phase candidate).
- **RESULT: 99.5% SCR (without -> horizon -> path-wise): nested 55,561.2 -> 40,852.1 ->
  46,638.9 (+14.17%); t(2.9451) 46,756.0 -> 31,001.8 -> 39,794.3 (+28.4%); gaussian 41,472.4
  -> 26,267.1 -> 35,210.1 (+34.0%); var-covar with: no path-wise analogue (DISCLOSED).
  Path-wise relieves LESS everywhere - horizon basis understates with-actions SCR across the
  matrix. Var-covar understatement refreshed: 69.1% vs nested path-wise (was 56.4%).
  Rank invariance: df re-matched 2.9451 (|diff| 7.0e-6), rho 7.2e-16 - copula FROZEN.**
- Tail: raw cut saturates 100% of the 99.5% tail but mean smoothed relief fraction 0.0838 <
  max_relief 0.12 (restoration caps realised relief). Bootstrap SCR SE 4.1%; **nested
  path-wise reference OUTSIDE the 95% CI [35,793, 42,496] - the re-anchoring understates
  nested by 14.7% beyond margin noise: quantified motivation for the next-phase full
  path-wise copula re-aggregation.**
- Deliverables: `docs/validation/PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.{json,md}` +
  `docs/PATHWISE_TAIL_DIAGNOSTICS_CARD.md` + staged
  `scripts/build_phase25_task4_pathwise_tail_diagnostics.py` (verify -> diag -> boot ->
  governance; idempotent re-run digest-identical; 36 archive cross-checks; P24T2 horizon
  read-outs reproduced bit-identically).
- Governance: ChangeRecord `a68dd3b9df114d07bfa4103d0ac1be2b` (methodology_change)
  OWNER_REVIEW; MR-010 + MR-014 refreshed (pins -> "Phase 25 Task 4"); audit 74->75; changes
  47->48; verify_all True.
- Tests: 39 new PASS (`tests/test_phase25_task4_pathwise_tail_diagnostics.py`); compileall
  clean; ui self-test ok:true.

**Next executable action: Phase 25 Task 5** - ui_data.json contract 1.6.0 -> 1.7.0 ADDITIVE:
path-wise declaration panel (pathwise-vs-horizon delta matrix, restoration-share diagnostics
41.4%/29.4%, smoothed-relief-fraction profile, gates + bootstrap disclosure), then PHASE 25
COMPLETE documentation. After that: design-note-first candidate selection for the next phase -
full path-wise copula re-aggregation (quantified motivation: 14.7% beyond-noise understatement)
vs credentialled-data calibration (human-blocked).

**Operating warnings (cycle 25):** ~44 s bash wall; PYTHONPATH=/var/tmp/pylibs:. ; build long
files OFF-MOUNT then cp + cmp; NEVER rewrite an existing large mounted file via the file tool
(cycle-24 staleness corrupted MODEL_DEV_STATE.json - repaired this cycle; use bash heredoc +
cp + cmp); back up + hash-verify the governance store before any governance stage; re-check
mtimes for parallel-run foreign writes before governance/commit; nohup background jobs do NOT
survive between bash calls (each call is a fresh process namespace) - chunk instead; next free
risk ID MR-015. Stage data: /var/tmp/p25t4_stage (rho, df re-match, beta_fit, scalars),
/var/tmp/p25t3_stage, /var/tmp/p25t2_stage, /var/tmp/p24t3_stage, /var/tmp/p23t2_stage
(losses.npz - copula primitives), /var/tmp/p23t4_stage, .phase22_task2_stage.

**Persisting blockers (human action):**
- Git ghost locks (`.git/index.lock`, `.git/HEAD.lock`, `.git/refs/heads/main.lock`) -
  commits land on `p22c9` via the alt-index workaround; push `p22c9:main` WORKS from the
  sandbox (push at the end of every cycle); locks only block fast-forwarding LOCAL main.
- Serialise/stagger the scheduled runs (collision demonstrated cycle 19).
- Production sign-off residual: credentialled calibration + independent APS X2 review.
- Disk /sessions ~89%.
