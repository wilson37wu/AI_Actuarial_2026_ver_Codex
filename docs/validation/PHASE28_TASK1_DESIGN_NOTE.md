# Phase 28 Task 1 — Design Note: Grouped-t / Heterogeneous Tail-Dependence Copula

**Verdict: PASS** (design note + tested helper module + synthetic heterogeneous-tail-dependence pre-study). EDUCATIONAL ONLY.

## 0. Candidate selection (design-note-first discipline)

**Chosen:** grouped-t copula (Daul et al. 2003) - per-block degrees of freedom (heterogeneous tail dependence across driver blocks) on the FROZEN correlation Sigma; the homogeneous boundary (all df_g = 2.9451, single shared mixing variate) recovers the governed single-df t EXACTLY (strict super-set; nested freeze).

- Vine / pair-copula: Aas et al. (2009): most general (d-1 trees of bivariate copulas) but the parameter surface cannot be governed as a single additive Art. 234 change in one phase. Retained as the general fallback if a block-homogeneous grouped-t still cannot represent the nested inner-path joint dynamics.
- Heavier single pooled df: A uniform tail-heaviness move (lower the single df / re-anchor): does NOT add the ACROSS-driver tail-dependence heterogeneity the residual points to - a single df already failed at Phase 26/27 and forces lambda equal on every pair. Rejected.
- Credentialled-data calibration: BLOCKED on credentialled management-practice data (standing human-action blocker); not executable from the sandbox. Remains the production sign-off residual by design.

## 1. Problem

Phase 27 closed the upper-tail-ASYMMETRY question NEGATIVELY: fitting the skew-t skewness scalar gamma leakage-free to the realised standalone upper-tail co-exceedances pinned it at gamma_hat ~ 6.2e-05 (the realised margins show no radial asymmetry), so the copula-FORM residual fell only 6,120.2 -> 6,114.9 (0.09%) and was RE-CONFIRMED as NOT a standalone-driver asymmetry effect (MR-015 OPEN). The frozen copula is a SINGLE-df Student-t: it imposes ONE tail-dependence level on EVERY pair (lambda_ij = lambda for all i,j at the common df). The nested joint loss is HETEROGENEOUS: the financial / carve-out block (credit loss + FX/liquidity offsets) co-crashes far harder WITHIN the block than it co-moves with the non-financial block. A single pooled df cannot represent within-block >> cross-block tail dependence - no re-choice of one df closes a heterogeneity gap.

Archived Phase 27 motivation figures (NOT consumed by gates): {"nested_scr": 46638.9, "frozen_t_component_scr": 39975.654628199336, "total_gap_rel_to_nested": 0.14286883635335879, "skewt_gamma_hat": 6.24229466599955e-05, "skewt_reconfirmed_copula_form_residual_abs": 6114.9, "copula_form_share_of_gap": 0.9185008546550519, "dependence_form_sensitivity_t_minus_g": 4765.5546281993375}

## 2. Method — grouped-t / heterogeneous tail dependence (Tasks 2-3)

Phase 28 keeps the calibrated MARGINS and the governed correlation Sigma FROZEN and adds ONE structured lever: per-block degrees of freedom via the grouped t-copula (Daul et al. 2003). Partition the d drivers into m blocks; each block g carries its own radial mixing variate W_g ~ InvGamma(df_g/2, df_g/2) on the SAME Gaussian draw Z ~ N(0, Sigma): X_k = sqrt(W_g(k)) * Z_k for driver k in block g. Within a block the pair tail dependence is the t-tail of df_g (shared mixing -> strong co-crash); across blocks the mixing is independent -> weaker cross-block tail dependence. The homogeneous boundary (all df_g = 2.9451 with a SINGLE shared mixing variate) reproduces the governed single-df t EXACTLY (a strict super-set; the freeze is the m=1 / fully-pooled boundary, so the archive cross-check is exact). Task 2 fits the per-block df_g to the realised within-block vs cross-block co-exceedances of the standalone capital-loss vectors (margins and Sigma UNCHANGED) on the PRE-REGISTERED partition, re-aggregates the path-wise component basis on the grouped-t, and Task 3 bootstraps the grouped-t SCR and re-decomposes the residual gap against the nested reference.

**Hypothesis:** The grouped-t produces WITHIN-block >> CROSS-block upper-tail dependence that a single pooled df cannot (heterogeneity the residual points to). Its effect on AGGREGATE SCR is TWO-SIDED and resolved empirically: because the single-df t shares ONE mixing variate it is the MAXIMAL-cross-block-dependence boundary, so the grouped-t's independent per-block mixing can RAISE the within-carve-out corner while DILUTING cross-block co-movement. Whether the net closes the upward nested residual 46,638.9 depends on whether the nested structure is within-block-concentrated; a WIDENING is itself informative (escalate to the vine).

## 3. Pre-study (synthetic heterogeneous-tail-dependence mechanism)

- Synthetic portfolio: 7 drivers, 2 blocks (FIN/carve-out [0, 4, 6] weight 0.44; NON-FIN [1, 2, 3, 5]); grouped-t df_fin=2.5, df_nonfin=15.0; single-df t basis shares ONE mixing variate (df_pooled=4.0) on common random numbers; identical frozen margins; n_scen=200,000, seed=42
- Upper-tail dependence (p=0.99): grouped within-FIN 0.352 vs cross-block 0.054 (heterogeneity +0.298); single-df t within-FIN 0.291 vs cross 0.293 (heterogeneity -0.002, near-uniform)
- Cross-block dilution: grouped cross-block tail dependence is -81.4% of the single-t cross level — the single-df t is the MAXIMAL-cross-block boundary
- VaR99.5: single-t 179.68; grouped-t 170.05 → aggregate moves -5.4% (DOWN) — DISCLOSED two-sided, the grouped-t is a heterogeneity lever not a tail-heaviness lever
- ES99.5 move: -7.1%
- Homogeneous-boundary EXACT recovery: max abs deviation 0.0e+00 (≤ 1e-09)
- heterogeneity_ok=True; homogeneous_recovery_ok=True; (diagnostics) sign_ok=False, ordering_ok=False; mechanism_demonstrated=True; digest=e7eb461bc3904e6e65c0583bb75bd18222eaba7b180c84267fdc1b87cc2021fb

The pre-study uses a SYNTHETIC seven-driver, two-block portfolio on common random numbers; the single-df t basis shares ONE mixing variate across all drivers (same Z, same base Gamma draw), through IDENTICAL frozen margins - so the ONLY difference is the per-block tail-dependence heterogeneity. The grouped-t lifts within-carve-out upper-tail dependence to 0.352 (vs cross-block 0.054; heterogeneity +0.298) while the single-df t stays near-uniform across blocks (heterogeneity -0.002). The homogeneous boundary recovery is EXACT (max abs deviation 0.0e+00). DISCLOSED two-sided sign: on this portfolio the cross-block dilution (-81.4% vs the single-t cross level) dominates, so aggregate VaR99.5 moves -5.4% (DOWN) - the grouped-t is a tail-dependence HETEROGENEITY lever, not a uniform tail-heaviness lever, and its aggregate effect is NOT sign-pinned (unlike the skew-t). It demonstrates the MECHANISM, not the magnitude or the sign of the real-data effect; both are quantified only at Tasks 2-3.

## 4. Gap analysis (standards vs current model)

### Solvency II Del. Reg. Art. 234; IFoA Aggregation WP (dependence on the basis used, incl. tail behaviour)

- **Requirement:** Diversification/dependence empirically justified ON THE BASIS ACTUALLY USED for capital, INCLUDING heterogeneous tail co-movement across risk types; the copula form must be adequate, not only its parameters.
- **Current state:** Copula frozen as a SINGLE-df Student-t (df 2.9451): lambda_ij identical for EVERY pair. The carve-out block co-crashes harder within-block than across blocks - a heterogeneity the single df cannot represent.
- **Gap:** After the skew-t reconfirmation (gamma_hat ~ 0) ~91.8% of the 14.29% nested gap (6,114.9) remains copula-FORM; a single df forces uniform pairwise tail dependence and cannot separate within- from cross-block.
- **Phase 28 design:** Task 2: add per-block df_g (grouped-t) on the frozen Sigma; the homogeneous boundary recovers the freeze exactly; fit df_g to realised within/cross-block co-exceedances on the pre-registered partition.

### SOA ASOP 56 3.5 (dependency structure appropriate to purpose)

- **Requirement:** The dependency structure - including the heterogeneity of tail co-movement across risk types - appropriate to the intended purpose; material structural limitations addressed where practicable.
- **Current state:** The single-df homogeneity limitation is DISCLOSED (P27 reconfirmation, MR-015) but not remediated; the skew-t scalar did not close it.
- **Gap:** A disclosed structural limitation that dominates the residual should be attacked with the structurally indicated richer form (heterogeneous tail dependence), not a uniform parameter re-choice.
- **Phase 28 design:** Grouped-t is the cheapest structured super-set: m per-block df parameters, exact nesting of the freeze, governed as a single additive copula change on a pre-registered partition.

### IA TAS M 3.2/3.6 (limitations disclosed; evidence reproducible)

- **Requirement:** Material limitations disclosed with quantification; remediation evidence reproducible with recorded config and pre-registered gates.
- **Current state:** P27 discloses the copula-form residual and MR-015 verbatim in the report, risk register and offline UI with the bootstrap CI.
- **Gap:** Disclosure exists; the REMEDIATION (heterogeneous tail dependence) is the open item.
- **Phase 28 design:** Task 3 headline gate: grouped-t 95% bootstrap CI tested against nested 46,638.9 (closure or residual RE-decomposed with the reduction vs the skew-t-reconfirmed 6,114.9 quantified); seeds/config/digests recorded; Task 4 refreshes MR-010/MR-014 and opens MR-016 for the heterogeneous-tail change.

### Solvency II Del. Reg. Art. 23 (management actions consistent with practice)

- **Requirement:** Allowance for management actions consistent with how they would be exercised - including which losses are relievable in a JOINT tail event.
- **Current state:** The carve-out (non-cuttable) drivers - credit loss, FX/liquidity offsets - dominate the joint tail (P24T3/P26T2); a single df treats their internal co-crash the same as their co-movement with cuttable drivers.
- **Gap:** Mis-stating the WITHIN-carve-out joint tail mis-states the un-relievable carve-out losses, i.e. mis-states required capital; the direction is empirical.
- **Phase 28 design:** The grouped-t lets the carve-out block carry its own (heavier) tail while relief still applies only to the cuttable component per scenario (P26T2 convention unchanged).

## 5. Acceptance criteria (FIXED, pre-registered — no gate-shopping)

**Task 2:**

- Implement the grouped-t copula (per-block df_g) on the FROZEN correlation Sigma; the single-df t is recovered EXACTLY at the homogeneous boundary (all df_g = 2.9451, single shared mixing variate; strict super-set; nested freeze)
- Homogeneous-boundary EXACT-recovery check: grouped-t aggregate reproduces the single-df t aggregate to within 1e-09 on common random numbers (archive cross-check is then exact)
- Frozen-t COMPONENT read-out 39,975.7 reproduced bit-identically BEFORE any grouped-t computation (archive cross-check)
- Rank invariance: correlation matrix max|diff| <= 1e-12 (Sigma FROZEN); the homogeneous df stays at 2.9451 within 0.0001; only per-block df_g added (Art. 234; no silent re-tuning of Sigma)
- Margins UNCHANGED: standalone marginal capital bit-identical (the upgrade changes the COPULA only)
- Block partition PRE-REGISTERED in this note: FIN/carve-out = drivers [0, 4, 6] (credit, FX, liquidity), NON-FIN = drivers [1, 2, 3, 5]; df_g fitted to realised within/cross-block co-exceedances (no re-tuning of Sigma/margins; leakage-free)
- Directional gate (DISCLOSED, NOT one-sided): grouped-t re-aggregated path-wise SCR reported vs the frozen-t component 39,975.7; the grouped-t is two-sided (within-block concentration vs cross-block dilution), so the sign is resolved empirically and disclosed, not pre-gated upward
- Single-df t component basis RETAINED and reported alongside as the comparison variant
- No gate-shopping: these gates fixed in this Task 1 note before any real-data grouped-t fit
- code_change ChangeRecord OWNER_REVIEW

**Task 3:**

- Grouped-t margin bootstrap: >= 200 replicates x 20,000 sims (P26T3/P27T3 pattern)
- HEADLINE gate: nested path-wise reference 46,638.9 INSIDE the grouped-t 95% bootstrap CI (closure of the copula-form residual) - if still outside, the residual gap MUST be RE-decomposed (residual copula-form vs relief-surface) and the CHANGE vs the skew-t-reconfirmed copula-form residual 6,114.9 (and the frozen-t 6,120.2) quantified - no silent acceptance
- Directional diagnostic (DISCLOSED, NOT a hard gate): the grouped-t-vs-single-t nested-gap change on common random numbers is reported with its sign; a WIDENING is informative (the residual is not within-block-concentrated -> vine escalation) and is documented, not gate-failed
- Bootstrap SE <= 5% of the mean SCR
- Idempotent re-run digest-identical; seeds/config recorded
- methodology_change ChangeRecord OWNER_REVIEW

**Task 4:**

- Tail diagnostics on the grouped-t basis: within-block vs cross-block upper/lower tail dependence (the heterogeneity is the headline); grouped-vs-single and grouped-vs-nested deltas at VaR/ES/SCR
- MR-010 / MR-014 refreshed if the grouped-t SCR moves more than 1% from the frozen-t component read-out (disclosure trigger, not pass/fail); open MR-016 for the heterogeneous-tail-dependence change
- Rank invariance re-verified: Sigma frozen; homogeneous df 2.9451; only per-block df_g added (no silent re-tuning)
- Reproducibility: seeds, config, digests recorded; assumption_change/governance ChangeRecord OWNER_REVIEW

**Task 5 plan:** Offline-UI propagation (ui_data.json contract 1.9.0 -> 1.10.0 ADDITIVE; grouped-t panel: grouped-t-vs-single-t-vs-nested SCR comparison, within-block vs cross-block tail-dependence heterogeneity, bootstrap CI closure/re-decomposition read-out, MR-016, gates) + PHASE 28 documentation; UI consumes ONLY model-output JSON, zero-install.

## 6. Limitations

- The synthetic pre-study proves the heterogeneous-tail-dependence mechanism and the EXACT homogeneous-boundary nesting, not the magnitude or the SIGN of the real-data aggregate effect (synthetic margins; two-block partition; rank-PIT copula isolation; no per-node clip binding).
- The grouped-t is a HETEROGENEITY lever, not a tail-heaviness lever: because the single-df t is the maximal-cross-block-dependence boundary, the grouped-t can DILUTE cross-block co-movement and LOWER aggregate SCR - on the synthetic it does. Whether it closes the upward nested residual is an open empirical question for Tasks 2-3.
- If a block-homogeneous grouped-t still cannot represent the nested inner-path joint dynamics, the vine / pair-copula (Aas et al. 2009) is the general fallback (Phase 29).
- The block partition is a NEW modelling decision; it is pre-registered here (financial/carve-out vs non-financial) but a different partition would require its own governed note.
- Margins and Sigma remain the calibrated frozen values; the upgrade does not revisit the marginal calibration or the correlation (out of scope this phase).
- Action parameters remain educational placeholders pending credentialled practice data + independent APS X2 review.

## 7. Standards

- Solvency II Delegated Reg. Art. 234 (empirically justified diversification incl. tail behaviour; dependence justified on the basis actually used for capital)
- Solvency II Delegated Reg. Art. 23 (future management actions: objective, realistic, verifiable)
- SOA ASOP 56 3.1.3/3.4/3.5
- SOA ASOP 25 3.3
- IA TAS M 3.2/3.6
- IFoA Life Aggregation & Simulation working party
- Daul, De Giorgi, Lindskog & McNeil (2003), The grouped t-copula
- Demarta & McNeil (2005), The t copula and related copulas
- McNeil, Frey & Embrechts (2015), Quantitative Risk Management ch. 7 (grouped t; tail dependence)
- Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence (vines)

*Generated by scripts/build_phase28_task1_design_note.py — educational model; production sign-off withheld.*
