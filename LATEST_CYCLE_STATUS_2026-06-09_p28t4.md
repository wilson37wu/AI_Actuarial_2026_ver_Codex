# Latest Cycle Status - 2026-06-09 (+08) - Phase 28 Task 4

**Phase 28 Task 4 COMPLETE (PASS, 6/6 gates). Grouped-t within/cross-block, upper/lower tail-dependence diagnostics + MR-010/MR-014 no-refresh decision + OPEN MR-016. Next: Phase 28 Task 5 (offline-UI propagation, contract 1.9.0 -> 1.10.0 ADDITIVE).**

Re-drew the FROZEN grouped-t copula (per-block df_NONFIN 37.866 / df_FIN 8.506 on the frozen Sigma) and the single-df t (homogeneous boundary, all df_g = the frozen 2.9451 with ONE shared mixing variate) on **COMMON random numbers** at the archived Phase 28 Task 3 per-replicate `cop_seed` values (**200 replicates x 20,000 sims**), and characterised the within-block (NON-FIN, FIN) and cross-block, upper and lower tail-dependence over the p-grid {0.80, 0.85, 0.90, 0.95}. NO new model parameter — a code-free diagnostics + governance task on the FROZEN copula.

**Result (p = 0.90, mean; 95% CI).** Grouped-t cross-block upper **0.1703 [0.1630, 0.1769]** vs single-df t cross-block upper **0.2573 [0.2446, 0.2687]** → **dilution −0.0871 [−0.0958, −0.0766]** (CI excludes 0; the grouped-t genuinely dilutes cross-block co-movement on CRN at every p — G2 PASS). Grouped within-FIN upper **0.1257** < single-df t within-FIN **0.1777** (df_FIN 8.5 > frozen 2.95 → lighter within-block tails). Within-block radial asymmetry (lambda_U − lambda_L) ≈ 0 with CI spanning 0 (0.00019 [−0.0120, 0.0127]) — finite-sample noise, as the t-copula is radially symmetric within a block; the **informative** asymmetry is HETEROGENEITY (within vs cross), the grouped-t lever. The independent per-block mixing — not only df_g > frozen — IS the dilution mechanism (homogeneous-boundary within-NON-FIN is bit-identical across legs because block 0 reuses the shared-mixing rng position; FIN and cross differ even at equal df).

**HEADLINE / cross-check (G1).** At p = 0.90 the recomputed grouped-t within-block (NON-FIN, FIN) upper, cross-block upper and heterogeneity_upper are **BIT-identical** (max abs dev **0.0**) to the cached P28T3 bootstrap records → faithful re-read, not a re-tune.

**MR-010/MR-014 refresh decision (G3): NO refresh.** The GOVERNED headline basis is the frozen single-df t (the maximal-cross-block-dependence, CONSERVATIVE boundary), recovered EXACTLY by the homogeneous boundary → governed move **0.0000%** (≤ 1% trigger). The grouped-t moves the disclosed component SCR DOWN (−10.93% point / −10.66% bootstrap mean) by DILUTING cross-block co-movement; that is non-conservative, so the grouped-t is **DISCLOSED, not adopted** into the headline. The disclosed move is documented, not actioned, and is now tracked by the NEW **MR-016**.

**MR-016 OPENED (G4).** Heterogeneous-tail / cross-block-dilution copula-FORM residual (model_error, MEDIUM x HIGH, OPEN; register 15 → 16). The copula-form residual to the nested truth WIDENS under the grouped-t (P28T3: 6,114.9 → 10,491.5); this is the SECOND negative super-set result after the Phase 27 skew-t (gamma_hat ~ 0) — a single copula on the standalone margins, asymmetric or block-heterogeneous, cannot close the UPWARD nested residual; it lives in nested inner-path joint dynamics. **Mitigation: vine / pair-copula (Aas et al. 2009), Phase 29.**

**Gates:** G1 archive cross-check bit-identical PASS; G2 grouped dilutes cross-block at every p PASS; G3 no MR refresh (governed move ≤ 1%) PASS; G4 MR-016 opened PASS; G5 digest idempotent (`e86057638b01`, re-run digest-identical) PASS; G6 governance OWNER_REVIEW + verify_all True PASS. **6/6.**

**Verification:** pytest P28T4 **11/0**; regression P28T1-T3 **35/0**, P27T1-T4 **48/0** (**94 passed, 0 failed**); compileall clean; report + governance JSON validated. Governance: ChangeRecord `0988ea9f865a49c3b938d22dc37af498` (governance_change) OWNER_REVIEW; audit 89 → 90; change records 61 → 62; risk register 15 → 16; verify_all True; idempotent (re-run added:false). GOV + STATE backed up + parse-verified pre (`/var/tmp/p28t4_stage/GOV_BACKUP_pre_p28t4.json`, `STATE_BACKUP_pre_p28t4.json`).

**New files / reports:**
- par_model_v2/projection/grouped_t_tail_diagnostics.py
- scripts/build_phase28_task4_tail_diagnostics.py
- tests/test_phase28_task4_tail_diagnostics.py
- docs/validation/PHASE28_TASK4_TAIL_DIAGNOSTICS_REPORT.{json,md}
- docs/GROUPED_T_TAIL_DIAGNOSTICS_CARD.md

**Next executable task: Phase 28 Task 5** — offline-UI propagation (data contract 1.9.0 → 1.10.0 ADDITIVE): grouped-t vs single-df t vs nested SCR, within/cross-block upper/lower tail-dependence grid + dilution, bootstrap CI, residual re-decomposition + widening, df_NONFIN/df_FIN, MR-016; UI consumes ONLY model-output JSON, zero-install. On Phase 28 completion → **Phase 29 vine / pair-copula (Aas et al. 2009)**.

**Standing blockers (human action):** git ghost locks (GITHUB_PUSH_BLOCKER.md) — sandbox commits/pushes blocked; this cycle's artefacts are on the mount but NOT pushed; production sign-off withheld pending credentialled data + independent APS X2 review (by design, educational). The fully-offline zero-install model-output-only interactive UI requirement remains SATISFIED. Sandbox note: scipy/numpy reused from `/var/tmp/pylibs` (PYTHONPATH); staged P28T2 (verified.npz, fit_result.json) and P28T3 (partial_*.json, cop_seeds) inputs survived on /var/tmp and were reused. Mount write-sync lag observed on one test file (authoritative file-tool view verified complete; tests validated 11/11 from a /var/tmp copy).

---
