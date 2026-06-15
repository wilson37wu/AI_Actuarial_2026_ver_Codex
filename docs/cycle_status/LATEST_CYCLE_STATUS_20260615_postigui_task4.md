# Cycle Status - Post-Phase-IGUI Task 4 (MR-VR-1 variance-reduction implementation)

**Date:** 2026-06-15 (Claude Cowork 06:00/18:00 window; lock cycle 2026-06-15T12:08Z)
**Agent:** Claude (claude-opus-4-8), single in_progress task per AGENT_COORDINATION.md
**Verdict:** COMPLETE - PASS. Gates G1-G6 16/16; unit tests 11/11; full postigui regression green.

## What was done

Implemented candidate **MR-VR-1** (the single in_progress task, pre-registered by the
Task 3 design note): a DISCLOSED, efficiency-only inner-path variance-reduction study on
the TVOG estimator comparing crude i.i.d. Monte Carlo against antithetic pairing, common
random numbers (CRN) across the guarantee-on/off legs, and randomised-QMC (scrambled-Sobol)
inner sampling, on the same governed outer states.

New files:
- `par_model_v2/projection/variance_reduction_diagnostics.py` (implementation; numpy+stdlib only)
- `scripts/build_postigui_task4_variance_reduction.py` (report/governance builder)
- `tests/test_postigui_task4_variance_reduction.py` (11 tests, standalone harness)
- `docs/validation/POSTIGUI_TASK4_VARIANCE_REDUCTION.{json,md}`, `docs/POSTIGUI_TASK4_VARIANCE_REDUCTION_REPORT_CARD.md`

## Results (idempotent digest `cc0c2fea2bf9b86db75f6239a9ba6e3e0a1577a1e1290e24ce13732eb0c0f0d7`)

| Gate | Result |
|---|---|
| G1 Governed-headline invariance | Frozen-t 39,975.654628199336 BIT-IDENTICAL (dev 0); estimator additive/disclosed, not a swap |
| G2 Unbiasedness (>=200 reps) | antithetic/CRN/Sobol replicate means within 0.5% of crude (max ~0.01%) |
| G3 VR efficacy + CIs + ESS | Sobol-RQMC 2241x, CRN 18.9x, antithetic 1.88x (mean target), all with 95% bootstrap CIs + ESS + n* |
| G3 (tail) antithetic @99.5% | 1.31x (< 1.5x) -> DISCLOSED ineffective, echoing outer-basis precedents 0.72x-0.78x |
| G4 Slice-stable CRN reprod. | SeedSequence-spawn inner shocks; idempotent digest; n_inner/n_outer/seeds version-pinned |
| G5 Adoption materiality | indicated dSCR -0.0014% of headline -> immaterial; REPORTED, NOT applied (production estimator stays governed) |
| G6 Governance + UI discipline | ChangeRecord OWNER_REVIEW; 11 unit tests; ui_app.html byte-unchanged (no UI surface this cycle) |

Governance: ChangeRecord `f854f53132d0446a9178e4151e4a1b3a` governance_change OWNER_REVIEW;
change records 113 -> 114, audit 141 -> 142, integrity verify_all True. Re-run adds nothing.

Stop-rule: only the Monte-Carlo sampling scheme of an existing estimator changed; no copula
structure, no model parameter; MR-016/MR-017 untouched (Phase 30 compliant).

## Status / blockers / next

- **Status:** GREEN. MR-CAL-1 (Task 2) and MR-VR-1 (Task 4) both COMPLETE; the
  diagnostics/efficiency candidate pool under the stop-rule is now exhausted.
- **Blockers:** none for the model work. MR-LONGEV-1 (longevity 5th driver) is owner-gated
  (parameter-adding model-FORM change) and is NOT auto-run.
- **Coordination note (flagged for hardening):** `scripts/agent_lock.py` reported a false
  `ACQUIRED` when git `user.email`/`user.name` were unset in a fresh clone - the commit
  silently failed and the no-op push returned 0. This cycle set the identity and pushed the
  REAL lock (origin/main `fffac0b`). Recommend `_write_commit_push` fail loudly if the
  commit fails for any reason other than "nothing to commit".
- **Next (Task 5):** per the standing UI directive, build the ADDITIVE offline-UI efficiency
  panel for the VR study (model-output-only) as an additive contract bump; OR owner pivot to
  MR-LONGEV-1 / packaging A/B/C.
