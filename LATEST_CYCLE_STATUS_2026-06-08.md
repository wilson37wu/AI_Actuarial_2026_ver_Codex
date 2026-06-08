# Latest Cycle Status - 2026-06-08 (+08) (cycle 28) - READ FIRST

**Phase 26 Task 2 COMPLETE (PASS — per-driver composition transform on the FROZEN copula;
6/6 pre-registered gates; 17 new tests; governance verify_all True). Next: Phase 26 Task 3 —
frozen-copula margin bootstrap on the FULL re-aggregated (component) basis.**

What this cycle did:

- Health gate (targeted, DISCLOSED): cycle 27 closed green ~8h earlier; additive-only cycle.
  compileall clean; targeted suites 150 PASS / 0 FAIL pre-change; mtime check clean;
  governance store backed up + hash-verified (/var/tmp/p26t2_build/GOV_BACKUP_pre_p26t2.json).
- Archive cross-check FIRST (G1/G2): 12/12 PASS — P24T2 horizon + P25T4 LEVEL read-outs
  reproduced BIT-IDENTICALLY before any new computation; df re-matched 2.9451 (tol 1e-4);
  rho max|diff| 7.22e-16 (tol 1e-12) — copula FROZEN.
- NEW `par_model_v2/projection/pathwise_composition_transform.py`: per-scenario composition
  recovered from frozen margins; CUTTABLE sub-level (L_fit + rate/equity/lapse/mortality
  deviations) vs CARVE-OUT (credit/fx/liquidity); relief on the cuttable component only,
  B_comp = clip(beta_fit * V_cut, 0, V), per-scenario max_relief envelope clip; LEVEL
  variant retained on CRN. Governed sigma/alpha/beta_fit UNCHANGED (bit-equal P25T4).
- NEW `scripts/build_phase26_task2_composition_transform.py` (verify|reagg|report|governance)
  -> docs/validation/PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.{json,md} +
  docs/COMPOSITION_TRANSFORM_CARD.md. Verdict PASS. Idempotent.
- RESULTS: t(2.9451) SCR component 39,975.7 vs re-anchored 39,794.3 = +0.46% (SIGN gate
  PASS); gaussian 35,391.5 vs 35,210.1 (+0.52%); real-basis tail cuttable-share depression
  0.993 -> 0.974 (FAR smaller than synthetic 0.566 -> 0.470). Gap to nested 46,638.9:
  -14.68% -> -14.29% — composition closes only a small part; residual now expected to be
  relief-surface / copula-form error. DISCLOSED. MR 1% trigger NOT met (+0.46% < 1%).
- Governance: ChangeRecord `dcf5cc5132ad4cadb534ea47314d9684` (code_change) OWNER_REVIEW;
  audit 77->78; changes 50->51; verify_all True. Tests: 17 new PASS; P26 suites 30/0.

**Next executable action: Phase 26 Task 3 — frozen-copula margin bootstrap (>= 200 x 20k)
on the FULL re-aggregated (component) basis.** HEADLINE gate: nested 46,638.9 INSIDE the
95% CI, else residual gap MUST be decomposed (copula-form vs relief-surface) + disclosed —
given the +0.46% Task 2 move, decomposition is the LIKELY branch: plan the gap decomposition
explicitly (surface error via P25T3 OOS diagnostics vs copula-form via t-vs-gaussian /
margin-form deltas). SE <= 5%; seeds/config/digests recorded; idempotent;
methodology_change ChangeRecord OWNER_REVIEW. Stage to /var/tmp/p26t3_* in <44 s chunks
(200 replicates x 20k: chunk the replicate loop, persist partials, resume).

**Operating warnings (cycle 28):** ~44 s bash wall; MOUNT APPENDS UNRELIABLE — ALWAYS
build/append OFF-MOUNT (/var/tmp) then cp whole-file + cmp + grep-verify (worked cleanly
this cycle); PYTHONPATH=/var/tmp/pylibs:. ; NEVER rewrite an existing large mounted file via
the file tool; nohup does not survive between bash calls; back up + hash-verify the
governance store before any governance stage; re-check mtimes for parallel-run foreign
writes before governance/commit; next free risk ID MR-015. Stage data: /var/tmp/p26t2_stage
(verified_inputs.npz + reagg_result.json), /var/tmp/p26t2_build, /var/tmp/p26t1_build,
/var/tmp/p25t5_build, /var/tmp/p25t4_stage, /var/tmp/p25t3_stage, /var/tmp/p25t2_stage,
/var/tmp/p24t3_stage, /var/tmp/p23t2_stage (losses.npz), /var/tmp/p23t4_stage,
.phase22_task2_stage.

**Persisting blockers (human action):**
- Git ghost locks (`.git/index.lock`, `.git/HEAD.lock`, `.git/refs/heads/main.lock`) -
  commits land on `p22c9` via the alt-index workaround; push `p22c9:main` WORKS from the
  sandbox; locks only block fast-forwarding LOCAL main.
- Serialise/stagger the scheduled runs (Python-less Windows-shell runs waste cycles).
- Production sign-off residual: credentialled calibration + independent APS X2 review.
- Disk /sessions ~89%.
