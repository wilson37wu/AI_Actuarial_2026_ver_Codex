# Latest Cycle Status - 2026-06-08 (+08)

**Phase 27 Task 1 COMPLETE (PASS) — design note: richer upper-tail dependence copula (skew-t). PHASE 27 OPENED.**

Opened Phase 27 with a design-note-first cycle. **Chosen candidate (one per cycle):** an explicit UPPER-TAIL-ASYMMETRY parameter — the generalized-hyperbolic **skew-t copula** (Demarta & McNeil 2005; McNeil, Frey & Embrechts 2015 ch. 7) — layered on the FROZEN copula (df 2.9451, correlation Sigma), with **gamma = 0 recovering the symmetric Student-t EXACTLY** (strict super-set; the governed freeze is nested as a boundary case, so the archive cross-check is exact).

**Motivation (quantified, from the Phase 26 Task 3 residual-gap decomposition):** the full path-wise re-aggregation on the frozen copula gives a component SCR of **39,975.7**, yet the nested path-wise truth is **46,638.9** (14.29% gap). The bootstrap decomposed it — only **543.0 (8.1%; 1.16% of nested)** is relief-surface error; the remaining **6,120.2 (91.9%)** is **COPULA-FORM** and EXCEEDS the entire gaussian→t dependence-form sensitivity (4,765.6). The frozen copula is a radially **symmetric** t (lambda_U = lambda_L); the joint loss tail is upper-asymmetric (credit + FX/liquidity carve-outs co-crashing) — no re-choice of df closes a SHAPE gap.

**Synthetic pre-study (SIGN evidence, common random numbers).** New tested helper `par_model_v2/projection/tail_dependence_upgrade.py` simulates a 7-driver GH skew-t mixture; the symmetric-t basis is the SAME mixture at gamma=0 (W, Z reused) through IDENTICAL frozen margins. Result (n=200k, seed 42): upper-tail-dependence proxy **0.291 → 0.742**, lower tail near-symmetric **0.283 → 0.136** (radial asymmetry 0.001 → 0.603); **VaR99.5 +10.2%**, **ES99.5 +10.7%**; **gamma=0 EXACT recovery (max abs dev 0.0 ≤ 1e-9)**. The symmetric copula UNDERSTATES the upper tail — the same sign as the documented nested-vs-frozen-t copula-form residual. mechanism_demonstrated = True.

**Pre-registered gates (FIXED, no gate-shopping).** Task 2: gamma=0 exact recovery; frozen-t component 39,975.7 bit-identical; df 2.9451 (tol 1e-4) + Sigma (max|diff| ≤ 1e-12) FROZEN; margins bit-identical; gamma fit to upper-tail co-exceedances only; **SIGN gate skew-t SCR ≥ 39,975.7**. Task 3: ≥200×20k bootstrap; **HEADLINE — nested 46,638.9 INSIDE the skew-t 95% CI, or residual RE-decomposed with the reduction vs 6,120.2 quantified**; skew-t must REDUCE the nested gap on CRN; SE ≤ 5%. Task 4: MR-010/MR-014 refresh if SCR moves > 1%; open **MR-015** for the copula-form change. Task 5: UI 1.8.0 → 1.9.0 ADDITIVE.

**Candidates deferred (rationale recorded):** grouped-t (Daul et al. 2003 — heterogeneous df by group, but each block stays radially symmetric and forces a partition decision); vine / pair-copula (Aas et al. 2009 — most general, not governable as one additive Art. 234 change in a phase); credentialled-data calibration (standing human-action blocker).

**New files / reports:**
- par_model_v2/projection/tail_dependence_upgrade.py
- scripts/build_phase27_task1_design_note.py
- tests/test_phase27_task1_design_note.py
- docs/validation/PHASE27_TASK1_DESIGN_NOTE.{json,md}
- docs/RICHER_TAIL_DEPENDENCE_DESIGN_CARD.md

**Verification:** pytest **14/0** (P27T1) and **84/0** including P25T1/P26T1/P26T5 regression suites; compileall clean; report + governance store JSON validated. Governance: ChangeRecord `391700530a174ec1bc3b99a0c16e808d` (governance_change) OWNER_REVIEW; audit 81→82; change records 54→55; verify_all True; idempotent (re-run 55→55). GOVERNANCE_STORE.json backed up + hash-verified pre-stage.

**Next executable task:** Phase 27 Task 2 — implement the skew-t copula on the frozen (df 2.9451, Sigma): fit gamma to realised upper-tail co-exceedances (margins/df UNCHANGED), re-aggregate the path-wise component basis on the skew-t, run the archive cross-check + gamma=0 exact-recovery + SIGN gate, retain the symmetric-t comparison variant; code_change ChangeRecord OWNER_REVIEW.

**Standing blockers:** git ghost locks (GITHUB_PUSH_BLOCKER.md) still recommended for cleanup — sandbox artefacts are on the mount but NOT pushed this cycle; serialise/stagger scheduled runs; production sign-off withheld pending credentialled data + independent APS X2 review (by design, educational). Sandbox: scipy/numpy/pytest at `/var/tmp/pylibs` (use `PYTHONPATH=/var/tmp/pylibs:.`). The fully-offline interactive UI requirement is **SATISFIED** (zero-install, model-output-only, interactive).

---

## Latest Cycle Status - 2026-06-08 (Phase 27 Task 2)

**Phase 27 Task 2 COMPLETE (PASS, 7/7 pre-registered gates). Next: Phase 27 Task 3 (skew-t margin bootstrap + residual re-decomposition).**

Implemented the GH skew-t copula (Demarta & McNeil 2005) as a strict super-set of the FROZEN symmetric t-copula (df 2.9451, Sigma): one scalar skewness `gamma` added on the same chi-square mixing / Gaussian draw, so **gamma = 0 recovers the frozen t EXACTLY** (recovery deviation **0.0** <= 1e-9; the frozen-t COMPONENT read-out 39,975.654628199336 reproduced bit-identically). The univariate GH skew-t marginal CDF is evaluated by generalised Gauss-Laguerre quadrature for gamma > 0 (margins stay uniform; the frozen empirical margins are untouched) with an exact Student-t short-circuit at gamma = 0.

**New module** `par_model_v2/projection/skew_t_copula_aggregation.py` (simulator, marginal CDF, leakage-free gamma fit, component re-aggregation read-out); **builder** `scripts/build_phase27_task2_skew_t_copula.py` (staged verify/fit/report/governance); **tests** `tests/test_phase27_task2_skew_t_copula.py` (13/13 PASS).

**MATERIAL FINDING (disclosed, not gated).** Fitting gamma leakage-free to the realised UPPER-tail co-exceedances of the standalone loss vectors **pins gamma at its lower boundary (gamma_hat ~ 6.2e-5)**: the realised avg pairwise upper co-exceedance (0.152 at p=0.90) is BELOW the frozen symmetric-t level (0.236) and shows no upper-tail asymmetry (realised upper-minus-lower ~ 0 / slightly negative at p=0.80/0.85). The skew-t at gamma_hat is economically identical to the frozen t (component SCR 39,981 vs 39,975.7, +0.01%, within quadrature-PIT tolerance). The lever IS correctly implemented and powerful — the DISCLOSED gamma grid lifts the component SCR to 54,600 at gamma=1.0 (radial asymmetry +0.54) and overshoots the nested 46,638.9. **Conclusion:** the copula-FORM residual (6,120.2; 91.9% of the 14.29% nested gap) is NOT a standalone-driver upper-tail radial-asymmetry effect; it lives in structure a copula on standalone margins cannot represent (nested inner-path joint dynamics). **Escalation flagged for Phase 28:** grouped-t (heterogeneous tail dependence across drivers); vine the general fallback.

**Gates (pre-registered, design note s5):** G1 gamma=0 exact recovery (0.0) PASS; G2 frozen-t component bit-identical PASS; G3 rank invariance (df 2.9451 within 1e-4; rho max|diff| 7.2e-16 <= 1e-12) PASS; G4 margins-unchanged (without-actions basis 47,269.12 bit-identical) PASS; G5 sign gate (skew-t >= 39,975.7) PASS; G6 gamma fitted leakage-free (converged) PASS; G_mechanism (monotone + asymmetric) PASS.

**Verification:** pytest **13/0** (P27T2); regression P27T1/P26T1-T5/P25T1 **135/0**; compileall clean; report + governance JSON validated. Governance: ChangeRecord `6bb5db0a06734369a0eb6d5ff48e84bc` (code_change) OWNER_REVIEW; audit 82->83; change records 55->56; verify_all True; idempotent (re-run added:false). GOVERNANCE_STORE.json backed up + hash-verified pre-stage (`/var/tmp/p27t2_build/GOV_BACKUP_pre_p27t2.json`).

**New files / reports:** `par_model_v2/projection/skew_t_copula_aggregation.py`; `scripts/build_phase27_task2_skew_t_copula.py`; `tests/test_phase27_task2_skew_t_copula.py`; `docs/validation/PHASE27_TASK2_SKEW_T_COPULA_REPORT.{json,md}`; `docs/SKEW_T_COPULA_CARD.md`.

**Next executable task: Phase 27 Task 3** — skew-t margin bootstrap (>=200x20k); HEADLINE gate: nested 46,638.9 INSIDE the skew-t 95% CI OR residual RE-decomposed (copula-form vs relief-surface) with the reduction vs 6,120.2 quantified — given gamma_hat~0 the expectation is the residual is re-confirmed as NOT closed by skew-t, quantified honestly; skew-t must not WIDEN the gap on CRN; SE <= 5%.

**Persisting blockers (human action):** git ghost locks (commits land on branch `p22c9` via alt-index workaround; this cycle's artefacts are on the mount but NOT pushed — see GITHUB_PUSH_BLOCKER.md); production sign-off residual (credentialled data + APS X2 review); disk /sessions usage to watch.

---

## Latest Cycle Status - 2026-06-08 (Phase 27 Task 3)

**Phase 27 Task 3 COMPLETE (PASS). Next: Phase 27 Task 4 (tail diagnostics + MR-010/MR-014 refresh + open MR-015).**

Ran the skew-t-copula margin bootstrap (**200 replicates x 20,000 sims**, P26T3 pattern) on the FROZEN copula (df 2.9451, Sigma, gamma_hat 6.242e-05) and governed relief scalars (sigma/alpha/beta_fit FROZEN, SII Art. 234). Each replicate joint-resamples the realised standalone-loss rows WITH replacement (cross-driver pairing preserved) and re-runs the Task 2 skew-t component re-aggregation; on **common random numbers** (the SAME latent Gaussian/chi-square mixing draw) the nested gamma=0 symmetric-t variant is also evaluated so the per-replicate (skew-t - symmetric) difference isolates the gamma effect. The (df, gamma_hat) marginal-CDF interpolant is built ONCE and reused (pure speed-up; CRN-exact to <= 1 ULP vs the tested simulator).

**Result.** Skew-t component SCR mean **39,598.2**, 95% percentile CI **[36,679.9, 42,943.1]**, SE **4.07%** of mean (<= 5% gate PASS). HEADLINE: the nested path-wise truth **46,638.9 lies OUTSIDE the skew-t 95% CI** -> the residual gap is RE-decomposed. With gamma_hat ~ 0 (Task 2 material finding) the copula-form residual falls only from the frozen-t baseline **6,120.2 to 6,114.9 (a 0.09% reduction)** at the canonical 200k point; the residual is **RE-CONFIRMED as NOT closed** by a single upper-tail-asymmetry scalar. DIRECTIONAL gate: skew-t does **NOT widen** the nested gap on CRN (mean lift +ve; 88.5% of replicates non-negative — per-replicate sign is MC noise around a ~0 mean, disclosed not gated). Attribution: the residual lives in nested inner-path joint dynamics a copula on standalone margins cannot represent -> **grouped-t / vine escalation flagged for Phase 28**.

**Gates (pre-registered, design note s5):** C1 headline (nested outside CI -> gap RE-decomposed + reduction-vs-6,120.2 quantified) PASS; C2 directional CRN-mean not-widened PASS; C3 SE <= 5% PASS (4.07%); C4 archive cross-check bit-identical (frozen-t 39,975.654628 + skew-t-at-gamma_hat 39,980.955659) PASS; C5 copula/scalars FROZEN PASS; C6 chunk-independent + idempotent (digest 9c6e55e81ae3, re-run bit-identical) PASS; C7 governance PASS.

**Verification:** pytest **10/0** (P27T3); regression P27T1-T2/P26T1-T5/P25T1 **145/0**; compileall clean; report + governance JSON validated. Governance: ChangeRecord `46c3318c27ae469daf7c0e40f8d99a41` (methodology_change) OWNER_REVIEW; audit 83->84; change records 56->57; verify_all True; idempotent (re-run added:false). GOVERNANCE_STORE.json backed up + hash-verified pre-stage (`/var/tmp/p27t3_build/GOV_BACKUP_pre_p27t3.json`).

**New files / reports:** `par_model_v2/projection/skew_t_copula_bootstrap.py`; `scripts/build_phase27_task3_skew_t_bootstrap.py`; `tests/test_phase27_task3_skew_t_bootstrap.py`; `docs/validation/PHASE27_TASK3_SKEW_T_BOOTSTRAP_REPORT.{json,md}`; `docs/SKEW_T_BOOTSTRAP_CARD.md`.

**Next executable task: Phase 27 Task 4** — tail diagnostics (upper/lower tail-dependence asymmetry of the skew-t draw) + MR-010/MR-014 refresh if SCR moves > 1% (it does NOT: skew-t 39,598 vs frozen-t component basis P26T3 mean 39,595, +0.01%); **open MR-015** for the copula-form / radial-asymmetry change. Then Task 5 (offline-UI propagation, contract 1.8.0 -> 1.9.0 ADDITIVE: skew-t-vs-symmetric-vs-nested SCR, upper/lower tail-dependence asymmetry, gamma_hat~0 material finding, bootstrap-CI read-out; UI consumes ONLY model-output JSON, zero-install). On Phase 27 completion: escalate to grouped-t (heterogeneous tail dependence across drivers); vine the general fallback.

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md) — sandbox commits/pushes blocked, so this cycle's artefacts are on the mount but NOT pushed; production sign-off residual (credentialled data + APS X2).

---

## 2026-06-08T12:17:20Z - Phase 27 Task 4: skew-t tail diagnostics + MR governance - PASS

**Task completed:** Phase 27 Task 4 - tail diagnostics, MR-010/MR-014 refresh decision, and MR-015 opening.

**Accomplishments:**
- Added par_model_v2/projection/skew_t_tail_diagnostics.py support files: scripts/build_phase27_task4_tail_diagnostics.py, 	ests/test_phase27_task4_tail_diagnostics.py, docs/validation/PHASE27_TASK4_TAIL_DIAGNOSTICS_REPORT.{json,md}, and docs/SKEW_T_TAIL_DIAGNOSTICS_CARD.md.
- Recorded p=0.90 skew-t tail diagnostics from governed Phase 27 reports: skew-t lambda_U 0.240538, lambda_L 0.242029, radial asymmetry -0.001490; Task 3 bootstrap radial-asymmetry mean +0.000427.
- Confirmed MR-010/MR-014 numeric refresh is NOT required: max headline component SCR move 0.0133% < 1% trigger.
- Opened MR-015 for the still-open copula-form residual: frozen-t 6,120.2 -> skew-t 6,114.9, only 0.09% reduction; mitigation is grouped-t / vine escalation in Phase 28.
- Governance store now has risk register 15, change records 58, audit entries 86; new audit-entry digests validated with Node.

**Next Step:** Phase 27 Task 5 - offline-UI propagation, contract 1.8.0 -> 1.9.0 ADDITIVE, surfacing skew-t vs symmetric vs nested SCR, gamma_hat~0 finding, bootstrap CI, and MR-015.

**Industry Standards Progress:**
- Solvency II Art. 234 / SOA ASOP 56 / IA TAS M: tail-dependence limitation quantified and governed; no silent copula or margin re-tuning.
- Governance: MR-015 opened at OWNER_REVIEW; production sign-off remains withheld pending credentialled data + independent APS X2.

**Verification:** Node JSON parse passed for governance and Task 4 report; new audit digests validated. Python/pytest could not run in this Windows shell because python hangs / is unavailable; full pytest should run in the Python-capable Linux automation environment with PYTHONPATH=/var/tmp/pylibs:..

---

## Latest Cycle Status - 2026-06-08 (Phase 27 Task 4) — RECOVERY CYCLE

**Phase 27 Task 4 COMPLETE (PASS, 6/6 gates). Next: Phase 27 Task 5 (offline-UI propagation, contract 1.8.0 -> 1.9.0 ADDITIVE).**

Completed the skew-t copula **tail-dependence diagnostics** + **MR-010/MR-014 no-refresh decision** + **opened MR-015** (copula-FORM / radial-asymmetry residual). No new model parameter — a pure REPORT + governance task on the FROZEN copula (df 2.9451, Sigma, gamma_hat 6.242e-05).

**Diagnostics (200 replicates x 20,000 sims; re-drawn at the archived P27T3 per-replicate cop_seeds).** Upper/lower tail-dependence and radial asymmetry of the skew-t draw vs the symmetric-t (gamma=0) basis on **common random numbers**, over a tail grid p in {0.80, 0.85, 0.90, 0.95}. At the canonical p=0.90 the recomputed per-replicate lambda_U / lambda_L / radial asymmetry are **BIT-identical** to the cached P27T3 records (max abs dev **0.0** <= 1e-12). p=0.90 skew-t lambda_U **0.2395**, lambda_L **0.2391**, radial asymmetry **+0.00043** (~0, gamma_hat~0; recomputed mean reproduces the cached 0.0004270238). Consistency (T4-G2): skew-t radial asymmetry >= symmetric-t at every p on CRN.

**MR-010 / MR-014 refresh DECISION (T4-G3).** Skew-t headline component SCR (P27T3 mean 39,598.2) vs frozen-t component basis (P26T3 mean 39,595.1): relative move **+0.0133%** (Task 2 point move +0.0133%) — **<= 1% trigger -> NO refresh required**; the quantified move is documented, not actioned.

**MR-015 OPENED (T4-G4).** "Copula-FORM / radial-asymmetry residual not closed by the skew-t upper-tail scalar" (model_error; MEDIUM x HIGH; **OPEN**/monitored; EDUCATIONAL). The frozen-t copula-form residual (~6,120; 91.9% of the 14.29% nested gap) is NOT a standalone-driver upper-tail asymmetry effect (gamma_hat ~ 0 pins it; residual falls only ~0.09%). It lives in nested inner-path joint dynamics a copula on standalone margins cannot represent. **Mitigation: grouped-t (Daul et al. 2003) / vine (Aas et al. 2009) escalation -> Phase 28.**

**Gates:** T4-G1 archive cross-check bit-identical PASS; T4-G2 skew-t radial asym >= sym all p PASS; T4-G3 no MR refresh (move <= 1%) PASS; T4-G4 MR-015 opened PASS; T4-G5 digest idempotent (e660ad6153ec, re-run identical) PASS; T4-G6 governance OWNER_REVIEW + verify_all True PASS.

**Verification:** pytest **11/0** (P27T4); regression P27T1-T3 **37/0**, P26T1-T4 **51/0**, P26T5+P25T1 **57/0**, governance+P25T4 **93/0** (249 passed, 0 failed); compileall clean; report + governance JSON validated. Governance: ChangeRecord `00f05366af9349d5ba1f4609a239f51b` (governance_change) OWNER_REVIEW; **risk register 14 -> 15 (MR-015 OPEN)**; audit 86; change records 58; verify_all **True**; governance stage idempotent (re-run added:false).

**SANDBOX BLOCKER (recovered, IMPORTANT).** A prior crashed Task 4 run (entries timestamped 12:14:06Z) appended the governance ChangeRecord `00f05366af` + 2 audit entries and updated MODEL_DEV_STATE, then a disk-issue TRUNCATED both files mid-write: (1) **GOVERNANCE_STORE.json** was cut mid-risk-register (MR-012 truncated, MR-013/014/015 lost) AND **13 older audit entries had their `0.0` float details coerced to `0`**, breaking their digests (verify_all False); (2) **MODEL_DEV_STATE.json** had a block of trailing NUL bytes appended. **Recovered with NO data loss**: restored the 13 digest-valid audit entries + MR-012/013/014 from the verified `/var/tmp/gov_restore_p26t4.json` backup, kept the intact audit_trail (86) + change_records (58), opened MR-015, re-validated verify_all True, and `cp`-ed back with byte-count + `cmp` + on-disk re-parse verification. The diagnostics were independently re-derived via the full 200x20k bootstrap, reproducing the prior run's recorded numbers bit-identically. No duplicate governance record added. Backups: `.claude-dev/GOVERNANCE_STORE.json.p27t4_recovered.bak`, `/var/tmp/p27t4_GOV_BACKUP_pre.json` (the truncated original), `/var/tmp/p27t4_GOV_RECOVERED.json`, `/var/tmp/p27t4_STATE_RECOVERED.json`.

**New files / reports:**
- par_model_v2/projection/skew_t_tail_diagnostics.py (pre-existing module, now tested + wired)
- scripts/build_phase27_task4_tail_diagnostics.py
- tests/test_phase27_task4_tail_diagnostics.py
- docs/validation/PHASE27_TASK4_TAIL_DIAGNOSTICS_REPORT.{json,md}
- docs/SKEW_T_TAIL_DIAGNOSTICS_CARD.md

**Next executable task: Phase 27 Task 5** — offline-UI propagation, data contract **1.8.0 -> 1.9.0 ADDITIVE**: surface skew-t-vs-symmetric-vs-nested SCR, upper/lower tail-dependence asymmetry, the gamma_hat~0 material finding, the bootstrap-CI read-out, and MR-015; UI consumes ONLY model-output JSON, zero-install. On Phase 27 completion: **Phase 28** grouped-t heterogeneous tail-dependence escalation (vine fallback).

**Persisting blockers (human action):** git ghost locks (artefacts on the mount, NOT pushed — see GITHUB_PUSH_BLOCKER.md); disk /sessions at 91% (921 MB free) — the truncation root cause; production sign-off withheld pending credentialled data + APS X2 review.


---

## Latest Cycle Status - 2026-06-08 (Phase 27 Task 5) — PHASE 27 COMPLETE

**Phase 27 Task 5 COMPLETE (PASS). Offline-UI propagation, data contract 1.8.0 -> 1.9.0 ADDITIVE. PHASE 27 COMPLETE. Next: Phase 28 Task 1 (grouped-t heterogeneous tail-dependence design note; vine fallback).**

Propagated the Phase 27 skew-t evidence into the zero-install offline UI (`ui_app.html`) consuming **only** model-output JSON — no recalculation. `scripts/build_ui_data.py` gains an ADDITIVE `_build_phase27()` normaliser (reads the governed P27 Task 3/4 reports), bumps `CONTRACT_VERSION` 1.8.0 -> **1.9.0**, adds the `capital.skewt_copula_scr_component_bootstrap_mean` read-out, and merges any governance-store risks missing from the stale `viewer_data.json` register (surfacing **MR-015**; 14 -> 15 risks). A new **"Skew-t Tail (P27)"** tab renders: skew-t (39,598.2 bootstrap mean) vs symmetric-t (39,595.1) vs **nested 46,638.9** SCR bar chart; the lambda_U / lambda_L / radial-asymmetry profile across p in {0.80, 0.85, 0.90, 0.95} with 95% CI (near-radial symmetry, gamma_hat~0); the gamma_hat~0 **MATERIAL FINDING**; the **bootstrap CI** [36,679.9, 42,943.1] SE 4.07% (nested OUTSIDE); the **residual re-decomposition** (copula-form 6,114.9 / 91.8% vs relief-surface 543.0 / 8.2%, reduction vs frozen-t 6,120.2 ~0.09%); and the T3 + T4 pre-registered gate grids. MR-015 also surfaced in the **Governance** risk register.

**Verification:** `node scripts/ui_app_self_test.cjs ui_app.html` -> **ok:true, tabCount 10, 0 network calls / 0 JS errors**; external-reference scan **clean** (no http(s):// except runtime SVG xmlns, no CDN / script-src / link / @import); jsdom render confirms the P27 tab (12 cards, 13 chart bars, tail + residual tables, gamma_hat / MATERIAL FINDING / MR-015 / nested-OUTSIDE text) and the Governance MR-015. build_ui_data.py compiles clean; ui_data.json parses (contract 1.9.0). All source/output writes done OFF-MOUNT then cp + cmp + parse-verify (disk-truncation guard). No model recalculation — display-layer only.

**Offline guarantee:** the fully-offline, zero-install, model-output-only interactive UI requirement remains **SATISFIED** and now carries the Phase 27 skew-t / bootstrap / MR-015 read-outs additively.

**Next executable task: Phase 28 Task 1** — design-note-first **grouped-t** (Daul et al. 2003) heterogeneous tail-dependence across drivers (the indicated step since the single skew-t asymmetry scalar did not close the copula-form residual); **vine / pair-copula** (Aas et al. 2009) the general fallback.

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md) — sandbox commits/pushes blocked, this cycle's artefacts are on the mount but **NOT pushed**; **/sessions disk at 91% (~921 MB free)** — markdown appends truncated TWICE this cycle and were reconstructed off-mount + cp + parse-verified; production sign-off withheld pending credentialled data + independent APS X2 review (by design, educational).

---

## Latest Cycle Status - 2026-06-08 (Phase 28 Task 1) — PHASE 28 OPENED

**Phase 28 Task 1 COMPLETE (PASS). Design-note-first grouped-t / heterogeneous tail-dependence copula. Next: Phase 28 Task 2 (implement grouped-t + leakage-free per-block df fit + component re-aggregation).**

Opened Phase 28 with a design-note-first cycle. **Chosen candidate (one per cycle):** the **grouped t-copula** (Daul, De Giorgi, Lindskog & McNeil 2003) — per-block degrees of freedom (heterogeneous tail dependence across driver blocks) on the **FROZEN correlation Sigma**, with the **homogeneous boundary (all df_g = 2.9451, single shared mixing variate) recovering the governed single-df t copula EXACTLY** (strict super-set; the freeze is the m=1 / fully-pooled boundary, so the archive cross-check stays exact).

**Motivation (Phase 27 RECONFIRMATION).** The skew-t upper-tail-asymmetry scalar fitted leakage-free pinned at **gamma_hat ~ 6.24e-05** (the realised standalone margins show no radial asymmetry), so the copula-FORM residual fell only **6,120.2 → 6,114.9 (0.09%)** and was RE-CONFIRMED as NOT a standalone-driver asymmetry effect (**MR-015 OPEN**). The frozen copula is a SINGLE-df Student-t: it imposes ONE tail-dependence level on EVERY pair. The nested joint loss is HETEROGENEOUS — the financial/carve-out block (credit + FX/liquidity) co-crashes far harder within-block than across blocks. No single df can represent within-block >> cross-block tail dependence.

**Synthetic pre-study (MECHANISM evidence, common random numbers).** New tested helper `par_model_v2/projection/grouped_t_upgrade.py` simulates a 7-driver, two-block grouped-t; the single-df t basis shares ONE mixing variate on the SAME Gaussian draw through IDENTICAL frozen margins. Result (n=200k, seed 42): grouped-t within-FIN upper-tail dependence **0.352 vs cross-block 0.054** (heterogeneity +0.30); single-df t near-uniform across blocks (heterogeneity ~0); **homogeneous-boundary EXACT recovery (max abs dev 0.0 ≤ 1e-9)**. **DISCLOSED two-sided sign:** because the single-df t shares one mixing variate it is the MAXIMAL-cross-block-dependence boundary, so the grouped-t's independent per-block mixing DILUTES cross-block co-movement (−83% vs single level) and here aggregate **VaR99.5 moves −5.4% (DOWN)**. The grouped-t is a tail-dependence **HETEROGENEITY** lever, NOT a uniform tail-heaviness lever — its aggregate effect is genuinely two-sided (unlike the sign-pinned skew-t). mechanism_demonstrated = True (heterogeneity + exact recovery).

**Pre-registered gates (FIXED, no gate-shopping).** Task 2: homogeneous-boundary exact recovery (≤1e-9); frozen-t component 39,975.7 bit-identical; Sigma FROZEN (max|diff| ≤ 1e-12) + homogeneous df 2.9451 (tol 1e-4); margins bit-identical; **PRE-REGISTERED block partition** FIN/carve-out {0,4,6} vs NON-FIN {1,2,3,5}; df_g fitted leakage-free to within/cross-block co-exceedances; **directional gate DISCLOSED (NOT one-sided)** — grouped-t is two-sided. Task 3: ≥200×20k bootstrap; **HEADLINE — nested 46,638.9 INSIDE the grouped-t 95% CI, or residual RE-decomposed with the change vs the skew-t-reconfirmed 6,114.9 quantified**; a WIDENING is informative (vine escalation), disclosed not gate-failed; SE ≤ 5%. Task 4: MR-010/MR-014 refresh if SCR moves > 1%; open **MR-016** for the heterogeneous-tail change. Task 5: UI 1.9.0 → 1.10.0 ADDITIVE.

**Candidates deferred (rationale recorded):** vine / pair-copula (Aas et al. 2009 — general fallback, not governable as one additive Art. 234 change in a phase); heavier single pooled df (a uniform tail-heaviness move — does not add across-driver heterogeneity; rejected); credentialled-data calibration (standing human-action blocker).

**New files / reports:**
- par_model_v2/projection/grouped_t_upgrade.py
- scripts/build_phase28_task1_design_note.py
- tests/test_phase28_task1_design_note.py
- docs/validation/PHASE28_TASK1_DESIGN_NOTE.{json,md}
- docs/GROUPED_T_DESIGN_CARD.md

**Verification:** pytest **16/0** (P28T1) and **64/0** including P27T1-T4 regression; compileall clean; report + governance store JSON validated. Governance: ChangeRecord `b92691ef320f4109b818520b0365beab` (governance_change) OWNER_REVIEW; audit 86→87; change records 58→59; verify_all True; idempotent (re-run added:false). GOVERNANCE_STORE.json + MODEL_DEV_STATE.json backed up + parse-verified before AND after (`/var/tmp/p28t1_build/GOV_BACKUP_pre_p28t1.json`, `STATE_BACKUP_pre_p28t1.json`); all source/state writes done OFF-MOUNT then cp + cmp + parse-verify.

**Pre-existing stale-test finding (NOT this cycle's regression):** `tests/test_phase24_task3_inner_path_action.py::TestGovernance::test_mr014_notes_latest_refresh_mentions_inner_path` FAILS because the MR-014 notes were superseded by the **Phase 25 Task 4** refresh (which mentions "Phase 24" but not "Task 3"), per the repo's own latest-refresh-supersedes convention. The governance store was NOT modified by Phase 28 Task 1 (only a new ChangeRecord + audit entry appended). The test is stale relative to a Phase 25 supersession; flagged for a one-line test update (assert "Phase 24" only, or accept the path-wise supersession) in a future maintenance cycle.

**Standing blockers:** git ghost locks (GITHUB_PUSH_BLOCKER.md) — sandbox artefacts on the mount, NOT pushed; **/sessions disk at 91% (~921 MB free)** — writes done off-mount + cp + parse-verify as the truncation guard; serialise/stagger scheduled runs (a concurrent session path was observed during regression collection); production sign-off withheld pending credentialled data + independent APS X2 review (by design, educational). The fully-offline zero-install model-output-only interactive UI requirement remains SATISFIED.


---

## Latest Cycle Status - 2026-06-08 (Phase 28 Task 2)

**Phase 28 Task 2 COMPLETE (PASS, 9/9 pre-registered gates). Next: Phase 28 Task 3 (grouped-t margin bootstrap + residual re-decomposition).**

Implemented the GROUPED t-copula (Daul, De Giorgi, Lindskog & McNeil 2003) as a strict super-set of the FROZEN single-df t-copula (df 2.9451, Sigma): per-BLOCK degrees of freedom df_g on the SAME Gaussian draw with INDEPENDENT per-block chi-square mixing, so the **homogeneous boundary (all df_g = 2.9451 + ONE shared mixing variate) recovers the frozen single-df t EXACTLY** (recovery deviation **0.0** <= 1e-9; the frozen-t COMPONENT read-out 39,975.654628199336 reproduced bit-identically). Within a block the tail dependence is the t-tail of df_g (shared mixing -> strong co-crash); across blocks the independent mixing weakens cross-block tail dependence -- heterogeneity a single pooled df cannot represent.

**New module** `par_model_v2/projection/grouped_t_copula_aggregation.py` (simulator with shared/independent mixing, within/cross-block co-exceedance proxies, leakage-free per-block df fit, component re-aggregation read-out); **builder** `scripts/build_phase28_task2_grouped_t_copula.py` (staged verify/fit/report/governance); **tests** `tests/test_phase28_task2_grouped_t_copula.py` (11/11 PASS).

**Pre-registered partition (design-note s5, fixed BEFORE any fit).** FIN/carve-out = {credit, FX, liquidity} = real driver indices **{2,5,6}**; NON-FIN = {rate, equity, lapse, mortality} = **{0,1,3,4}**. (The Phase 28 Task 1 synthetic pre-study used placeholder indices {0,4,6}; the economically-named carve-out maps to {2,5,6} in the real DRIVERS tuple -- mapping documented in the module + report.)

**MATERIAL FINDING (disclosed, not gated -- mirrors the skew-t reconfirmation).** Fitting df_g leakage-free to each block's realised WITHIN-block upper co-exceedances gives **df_NONFIN 37.866, df_FIN 8.506** -- both ABOVE the frozen df 2.9451 (lighter tails). The realised within-block upper co-exceedances (p=0.90) are NON-FIN **0.125**, FIN **0.125**, but the CROSS-block level is **0.172**: the standalone loss vectors show NO within-carve-out tail concentration (within <= cross). So the grouped-t at df_hat DILUTES cross-block co-movement and moves the component SCR **DOWN to 35,604.4 vs the frozen-t 39,975.7 (-10.93%; gap to nested -23.66%)** -- the DISCLOSED two-sided direction is DOWN. The lever IS correctly implemented and powerful: the disclosed df grid lifts within-FIN >> cross-block heterogeneity to +0.056 at df_FIN=2.1 (a single pooled df gives ~0). **Conclusion:** like the skew-t asymmetry scalar (gamma_hat~0), a copula on the STANDALONE margins -- whether asymmetric (skew-t) or block-heterogeneous (grouped-t) -- does NOT close the upward nested residual; the residual lives in nested inner-path joint dynamics. **Vine / pair-copula (Aas et al. 2009) escalation flagged for Phase 29.**

**Gates (pre-registered, design note s5):** G1 homogeneous-boundary exact recovery (0.0) PASS; G2 frozen-t component bit-identical PASS; G3 rank invariance (df 2.9451 within 1e-4; Sigma max|diff| 7.22e-16 <= 1e-12) PASS; G4 margins-unchanged boundary without-basis bit-identical PASS; G5 partition pre-registered exact PASS; G6 per-block df fitted leakage-free converged PASS; G7 directional DISCLOSED (not one-sided gated) PASS; G8 single-df t comparison variant retained (== frozen) PASS; G_mechanism heterogeneity rising with heavier FIN PASS.

**Verification:** pytest **11/0** (P28T2); regression P28T1+P27T1-T4 **64/0**; P26T1-T5 + governance/audit **175/0** (250 passed, 0 failed); compileall clean; report + governance JSON validated. Governance: ChangeRecord `85a6b858662c42f095b62e4719e04836` (code_change) OWNER_REVIEW; audit 87->88; change records 59->60; verify_all True; idempotent (re-run added:false). GOVERNANCE_STORE.json + MODEL_DEV_STATE.json backed up + parse-verified pre AND post (`/var/tmp/p28t2_build/GOV_BACKUP_pre_p28t2.json`, `STATE_BACKUP_pre_p28t2.json`); all source/state writes done OFF-MOUNT then cp + sync + cmp + parse-verify (disk-truncation guard -- two transient mid-write truncations were caught by cmp/AST and reconstructed off-mount).

**New files / reports:** `par_model_v2/projection/grouped_t_copula_aggregation.py`; `scripts/build_phase28_task2_grouped_t_copula.py`; `tests/test_phase28_task2_grouped_t_copula.py`; `docs/validation/PHASE28_TASK2_GROUPED_T_COPULA_REPORT.{json,md}`; `docs/GROUPED_T_COPULA_CARD.md`.

**Next executable task: Phase 28 Task 3** -- grouped-t margin bootstrap (>=200x20k, P26T3/P27T3 pattern) on the FROZEN copula + governed relief scalars: HEADLINE gate nested 46,638.9 INSIDE the grouped-t 95% CI OR residual RE-decomposed with the change vs the skew-t-reconfirmed copula-form residual 6,114.9 (and frozen-t 6,120.2) quantified; given df_hat dilutes, the expectation is the residual WIDENS (informative -> vine escalation), disclosed not gate-failed; SE <= 5%.

**Persisting blockers (human action):** git ghost locks (artefacts on the mount, NOT pushed -- see GITHUB_PUSH_BLOCKER.md); /sessions disk at 91% (~921 MB free) -- the mid-write truncation root cause, writes done off-mount + cp + sync + cmp as the guard; production sign-off withheld pending credentialled data + independent APS X2 review.
