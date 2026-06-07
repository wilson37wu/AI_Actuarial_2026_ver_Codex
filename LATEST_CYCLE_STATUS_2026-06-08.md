# Latest Cycle Status - 2026-06-08 (+08) (cycle 24) - READ FIRST

**Phase 25 Task 3 COMPLETE (PASS 5/5 gates).
Next: Phase 25 Task 4 - tail diagnostics on the path-wise basis + MR-010/MR-014 refresh
(REQUIRED - trigger MET at Task 2: +14.17%); rank invariance df 2.9451 frozen.**

What this cycle did (matching path-wise proxy basis - truth and proxy now share an
IDENTICAL action basis, G1 convention):

- Health gate first: pytest batches green (386 tests); ui_app self-test ok:true; no foreign
  writes; governance store backed up (/var/tmp/p25t3_build/GOV_BACKUP_pre_p25t3.json) and
  re-verified unchanged before governance.
- NEW `par_model_v2/projection/pathwise_proxy_basis.py`: proxy relieved amount
  **relieved_hat = alpha * phi_sigma(CR_hat) * clip(B_hat, 0, L_hat)** - the governed relief
  curve smoothed over an effective lognormal dispersion of the path-wise CR (Gauss-Hermite
  21). TWO scalars (sigma 0.225, alpha 0.757) calibrated on the FIT sample ONLY
  (leakage-free); kappa reproduced from P24T3. Both candidates pre-registered in the design
  note were evaluated on FIT evidence; the zero-shock + level-factor candidate REJECTED
  (lambda 6.01, fit R^2 -15.2, state-dependent bias) and DISCLOSED; retained for the
  cadence sensitivity.
- Truth relieved amounts: FIT (2000 nodes @ 8 inner, 3 slices) and VAL (60 @ 384) are
  BIT-IDENTICAL re-runs of the archived Phase 22 Task 2 inner paths (exact equality of
  total/benefit/credit vs the archived P24T3 decomposition enforced at every slice);
  nested-eval truth = archived P25T2 stage (report digest re-verified).
- **RESULT (5/5 gates, unchanged Phase 22 gates): OOS R^2 with actions 0.9978 (>= 0.95);
  VaR99.5 rel err 0.40% (<= 10%); ES rel err 0.01%; SCR rel err 1.16% (proxy 46,095.8 vs
  nested 46,638.9). Truth nested with-actions SCR reproduces the archived P25T2 report
  exactly.** Annual-vs-monthly cadence sensitivity ratio 1.136 (deterministic basis).
- Deliverables: `docs/validation/PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.{json,md}` +
  `docs/PATHWISE_PROXY_BASIS_CARD.md` + staged
  `scripts/build_phase25_task3_pathwise_proxy_basis.py` (verify -> pwfit x3 -> pwval ->
  det x3 -> actions -> governance; idempotent re-run verified).
- Governance: ChangeRecord `fc9fc911fc51414abf0fc8e73cadc92c` (code_change) OWNER_REVIEW;
  audit 73->74; changes 46->47; verify_all True.
- Tests: 44 new PASS (`tests/test_phase25_task3_pathwise_proxy_basis.py`); regression
  **430 PASS / 0 FAIL**; compileall clean; ui self-test ok:true.

**Next executable action: Phase 25 Task 4** - joint-scenario tail diagnostics on the
path-wise with-actions basis (P24T4 pattern: saturation profile, delta matrix, var-covar
understatement refresh); **MR-010/MR-014 refresh REQUIRED** (trigger met +14.17% at Task 2);
rank invariance: df re-matched on WITHOUT-actions losses must remain 2.9451, copula
parameters FROZEN (Art. 234). Then Task 5 (UI 1.6.0 -> 1.7.0 ADDITIVE + PHASE 25 COMPLETE).

**Operating warnings (cycle 24):** ~44 s bash wall; PYTHONPATH=/var/tmp/pylibs:. ;
build long files OFF-MOUNT then cp + cmp; NEW: rewriting an EXISTING large file via the file
tool can leave the Linux mount view STALE (old byte length, new partial content) - caught by
py_compile; prefer bash-side heredoc writes for rewrites; back up the governance store before
any governance stage; re-check mtimes for parallel-run foreign writes before
governance/commit; next free risk ID MR-015. Stage data: /var/tmp/p25t3_stage,
/var/tmp/p25t2_stage, /var/tmp/p24t3_stage, /var/tmp/p23t3_stage, .phase22_task2_stage.

**Persisting blockers (human action):**
- Git ghost locks (`.git/index.lock`, `.git/HEAD.lock`, `.git/refs/heads/main.lock`) -
  commits land on `p22c9` via the alt-index workaround; push `p22c9:main` WORKS from the
  sandbox (push at the end of every cycle); locks only block fast-forwarding LOCAL main.
- Serialise/stagger the scheduled runs (collision demonstrated cycle 19).
- Production sign-off residual: credentialled calibration + independent APS X2 review.
- Disk /sessions ~89%.
