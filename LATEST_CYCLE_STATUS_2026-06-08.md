# Latest Cycle Status - 2026-06-08 (+08) (cycle 29) - READ FIRST

**Phase 26 Task 3 COMPLETE (PASS — frozen-copula margin bootstrap 200×20k on the FULL
re-aggregated component basis; SE gate PASS; HEADLINE decomposition branch executed +
disclosed; 10 new tests; governance verify_all True). Next: Phase 26 Task 4 —
full-vs-reanchored delta matrix + MR-010/MR-014 1% refresh re-check + rank invariance
re-verify (next free risk ID MR-015).**

What this cycle did:

- Health gate (targeted, DISCLOSED): governance store backed up + hash-verified
  (/var/tmp/p26t3_build_gov_backup.json, sha256 c0ce4600…); mtime foreign-write check clean
  (only the new module newer than cycle 28); compileall clean; P26T2 suite 17/17 PASS.
- Archive cross-check FIRST (B3/B4): Task 2 t-component read-out reproduced BIT-IDENTICALLY
  (39975.6546, digest c97714b0a831) and all six Task 2 gates PASS BEFORE any bootstrap;
  copula FROZEN (df re-matched 2.9451 tol 1e-4; rho max|diff| 7.2e-16 tol 1e-12); governed
  sigma 0.225 / alpha 0.7567 / beta_fit 0.8450 UNCHANGED.
- NEW `par_model_v2/projection/pathwise_composition_bootstrap.py`: non-parametric bootstrap
  over the realised standalone-loss rows (joint resample WITH replacement → cross-driver
  pairing preserved); copula df/rho + relief scalars FROZEN inside every replicate
  (SII Art. 234); t- and gaussian-copula component read-outs on common random numbers;
  per-replicate `SeedSequence(master).spawn()` → chunk-independent, resume-safe, idempotent.
  Helpers: `summarise_ci`, `decompose_residual_gap`, `bootstrap_digest`, use-restrictions.
- NEW `scripts/build_phase26_task3_margin_bootstrap.py` (verify | chunk --start/--stop |
  aggregate | report | governance). Staged in five 40-replicate chunks (~9 s each, <44 s wall;
  one chunk re-run after a 45 s loop timeout — resume worked cleanly from partials) →
  docs/validation/PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.{json,md} +
  docs/COMPOSITION_BOOTSTRAP_CARD.md. Verdict PASS. Idempotent (digest 97aa928bcbf7;
  first-5-replicate re-run bit-identical).
- RESULTS: component t SCR mean **39,595.1**, 95% CI **[36,676.2, 42,943.1]**, SE 1,610.0
  (**4.07%** of mean → SE gate ≤5% PASS). HEADLINE: nested **46,638.9 OUTSIDE** the 95% CI
  (above the upper bound) → DECOMPOSITION branch (pre-registered, expected given the +0.46%
  Task 2 move). Residual gap nested − component = 6,663.2 (**+14.29%** of nested) decomposed:
  relief-surface part **543.0 (8.1%)** — bounded independently by the governed P25T3 OOS SCR
  rel err 1.16%; copula-form residual **6,120.2 (91.9%)**. Copula-form DOMINANT; the residual
  EXCEEDS the entire gaussian→t dependence-form sensitivity (4,765.6) → the genuine nested
  joint tail is heavier than the frozen t(2.9451) copula on standalone margins. DISCLOSED.
- Governance: ChangeRecord `9049003b55d742f1812d5b083e3cd518` (methodology_change) OWNER_REVIEW;
  audit 78→79; changes 51→52; verify_all True. Tests: 10 new PASS; P26+governance+copula
  regression 136/0.

**Next executable action: Phase 26 Task 4 — full-vs-reanchored delta matrix** (component-vs-
level-vs-without across t/gaussian, with the bootstrap CIs attached); re-check the MR-010/
MR-014 1% disclosure trigger after Tasks 2–3 (Task 2 was +0.46% < 1%; confirm the combined
move stays sub-1% or refresh the MR notes); re-verify rank invariance (df/rho frozen); open
the next free risk ID **MR-015** if a new disclosure is needed; methodology_change ChangeRecord
OWNER_REVIEW; idempotent; stage to /var/tmp/p26t4_* in <44 s chunks. Then Task 5 (UI contract
1.7.0 → 1.8.0 ADDITIVE: surface the component-basis bootstrap CI + gap decomposition in the
offline UI; PHASE 26 COMPLETE docs).

**Operating warnings (cycle 29):** ~44 s bash wall (a 4-chunk loop timed out at 45 s — chunk
the bootstrap in ≤40-replicate / ≤~10 s stages, partials persist so resume is free);
MOUNT APPENDS UNRELIABLE — build/append OFF-MOUNT (/var/tmp) then cp whole-file + cmp +
grep-verify (clean this cycle for the module/script/tests); PYTHONPATH=/var/tmp/pylibs:. ;
NEVER rewrite an existing large mounted f