# Latest Cycle Status - 2026-06-08 (+08) (cycle 22) - READ FIRST

**Phase 25 Task 1 COMPLETE (design note, PASS).
Next: Phase 25 Task 2 - path-wise declaration in the nested truth.**

What this cycle did (design note + additive helper module - no numeric output path changed):

- Health gate first: pytest batches green (339 tests); ui_app self-test ok:true; no foreign
  writes; governance store backed up (/var/tmp/p25t1_build/GOV_BACKUP_pre_p25t1.json).
- **Candidate chosen (design-note-first):** full path-wise bonus declaration dynamics - the
  governed bonus-cut decision re-evaluated at EVERY inner time step on a path-wise coverage
  proxy, vs the P24T3 horizon-level convention (decision frozen at the outer node; relief
  constant across inner paths - the documented residual). NOT chosen: t-copula on the
  inner-path basis (deferred - Task 2 changes that basis; avoids superseded evidence);
  credentialled calibration (blocked on data - standing human-action blocker).
- NEW tested helper module `par_model_v2/projection/pathwise_bonus_dynamics.py`: four
  declaration bases (without / horizon / pathwise / max_cut bound) on common random numbers;
  retained-bonus-rate mapping (PRE floor + cuttable share, unchanged governed rule shape);
  synthetic recognition-lag pre-study.
- **Pre-study (synthetic fund, seed 42, 4000x100x10):** horizon-level basis UNDERSTATES the
  path-wise with-actions tail loss by **12.2% at VaR99.5**; cut-then-RESTORED share 69.8%
  (restoration is a real dynamic); median path-wise minus horizon diff NEGATIVE on healthy
  nodes (two-sided lag); understatement_sign_ok / relief_ordering_ok / bounds_ok all True.
  Mechanism, not magnitude (disclosed).
- **Pre-registered gates (Tasks 2-4, no gate-shopping):** OOS R^2 >= 0.95; VaR rel err <= 10%
  (unchanged Phase 22 gates); SIGN gate pathwise SCR >= horizon SCR at 99.5% (magnitude
  disclosed, not gated); MR-010/MR-014 disclosure trigger at 1% SCR delta; rank invariance
  df unchanged 2.9451 on without-actions losses (copula frozen). P24T3 carve-outs preserved.
- Deliverables: `docs/validation/PHASE25_TASK1_DESIGN_NOTE.{json,md}` +
  `docs/PATHWISE_BONUS_DECLARATION_DESIGN_CARD.md` + `scripts/build_phase25_task1_design_note.py`
  (idempotent re-run verified).
- Governance: ChangeRecord `fe5846be67a945a28fd60208f6b87972` (governance_change) OWNER_REVIEW;
  audit 71->72; changes 44->45; verify_all True.
- Tests: 29 new PASS (`tests/test_phase25_task1_design_note.py`); regression **368 PASS /
  0 FAIL** (339 prior batches + 29 new); compileall clean; ui self-test ok:true.

**Next executable action: Phase 25 Task 2** - path-wise declaration in the nested truth:
extend `inner_path_action_dynamics.py` with the per-time-step retained-bonus factor on a
path-wise coverage proxy (carve-outs preserved; horizon-level basis retained as sensitivity);
archive cross-check the without-actions basis bit-identically BEFORE any new computation;
gates per design-note s5; assumption_change ChangeRecord OWNER_REVIEW.

**Operating warnings (unchanged):** ~44 s bash wall; PYTHONPATH=/var/tmp/pylibs:. ;
long-file writes truncate on the mount (build OFF-MOUNT then cp + cmp - zero incidents this
cycle); back up the governance store before any governance stage; re-check mtimes for
parallel-run foreign writes before governance/commit; next free risk ID MR-015.

**Persisting blockers (human action):**
- Git ghost locks (`.git/index.lock`, `.git/HEAD.lock`, `.git/refs/heads/main.lock`) -
  commits land on `p22c9` via the alt-index workaround; push `p22c9:main` WORKS from the
  sandbox (push at the end of every cycle); locks only block fast-forwarding LOCAL main.
- Serialise/stagger the scheduled runs (collision demonstrated cycle 19).
- Production sign-off residual: credentialled calibration + independent APS X2 review.
- Disk /sessions ~89%.
