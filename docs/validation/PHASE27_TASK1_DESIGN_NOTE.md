# Phase 27 Task 1 — Design Note: Richer Upper-Tail Dependence Copula

**Verdict: PASS** (design note + tested helper module + synthetic upper-tail-asymmetry pre-study). EDUCATIONAL ONLY.

## 0. Candidate selection (design-note-first discipline)

**Chosen:** richer upper-tail dependence - an explicit upper-tail-asymmetry parameter (GH skew-t copula) on the FROZEN (df 2.9451, Sigma); gamma = 0 recovers the symmetric t EXACTLY (strict super-set of the governed copula).

- Grouped-t copula: Daul et al. (2003): heterogeneous df by driver group is richer but each block remains radially SYMMETRIC (no upper-tail asymmetry, the demonstrated copula-form driver) and it forces a group-partition calibration decision up front. Deferred behind the single-parameter asymmetry upgrade.
- Vine / pair-copula: Aas et al. (2009): most general (d-1 trees of bivariate copulas) but the parameter surface cannot be governed as a single additive Art. 234 change in one phase. Deferred as the general fallback if the asymmetry parameter is insufficient.
- Credentialled-data calibration: BLOCKED on credentialled management-practice data (standing human-action blocker); not executable from the sandbox. Remains the production sign-off residual by design.

## 1. Problem

Phase 26 closed the BASIS question: the full path-wise copula re-aggregation (per-driver composition relief on the frozen copula) and the analytic re-anchoring are economically interchangeable (+0.46%), and the frozen-copula margin bootstrap is tight (SE 4.07%). Yet the component read-out 39,975.7 still sits 14.29% below the nested truth 46,638.9, and the bootstrap DECOMPOSED that residual: only 543.0 (8.1%; 1.16% of nested) is relief-surface error - the remaining 6,120.2 (91.9%) is COPULA-FORM and EXCEEDS the entire gaussian->t dependence-form sensitivity (4,765.6). The frozen copula is a Student-t: a SINGLE scalar df with a radially SYMMETRIC tail (lambda_U = lambda_L). The nested joint loss is upper-asymmetric - the simultaneous-large-loss corner (credit + FX/liquidity carve-outs co-crashing) is heavier than a symmetric t can represent at ANY df without distorting the body or the lower tail. No re-choice of df closes a SHAPE gap.

Archived Phase 26 Task 3 motivation figures (NOT consumed by gates): {"nested_scr": 46638.9, "frozen_t_component_scr": 39975.654628199336, "total_gap_rel_to_nested": 0.14286883635335879, "copula_form_residual_abs": 6120.196568775231, "copula_form_share_of_gap": 0.9185008546550519, "relief_surface_part_abs": 543.0488030254351, "dependence_form_sensitivity_t_minus_g": 4765.5546281993375}

## 2. Method — richer upper-tail dependence (skew-t copula; Tasks 2-3)

Phase 27 keeps the calibrated MARGINS and the governed rank dependence (df 2.9451, correlation Sigma) FROZEN and adds ONE new structural lever: an upper-tail-asymmetry parameter via the generalized-hyperbolic skew-t copula (Demarta & McNeil 2005; McNeil, Frey & Embrechts 2015 ch. 7), X = gamma*W + sqrt(W)*Z with W ~ InvGamma(df/2, df/2), Z ~ N(0, Sigma). The skewness vector gamma controls the radial asymmetry: gamma > 0 lifts the UPPER-tail dependence while leaving the lower tail near the symmetric level, and gamma = 0 reproduces the governed symmetric t EXACTLY (a strict super-set - the freeze is nested as a boundary case, so the archive cross-check is exact). Task 2 fits gamma to the realised upper-tail co-exceedances of the standalone capital-loss vectors (margins and df UNCHANGED), re-aggregates the path-wise component basis on the skew-t copula, and Task 3 bootstraps the skew-t SCR and re-decomposes the residual gap against the nested reference.

**Hypothesis:** The skew-t (gamma > 0) re-aggregated path-wise SCR is HIGHER than the frozen-t component read-out 39,975.7 (a heavier, asymmetric upper tail can only RAISE the joint 99.5% loss vs the symmetric freeze) and the gap to the nested reference 46,638.9 SHRINKS; the synthetic skew-t pre-study sign carries over.

## 3. Pre-study (synthetic upper-tail-asymmetry mechanism)

- Synthetic portfolio: 7 drivers, GH skew-t mixture (df=4.0, rho=0.5, gamma=0.7); symmetric-t basis is the SAME mixture at gamma=0 on common random numbers; identical frozen margins; n_scen=200,000, seed=42
- VaR99.5: symmetric-t 179.68; skew-t 197.95 → symmetric basis UNDERSTATES by 10.2%
- ES99.5 understatement: 10.7%
- Upper-tail-dependence proxy (p=0.99): skew-t 0.742 vs symmetric-t 0.291; lower tail skew-t 0.136 vs symmetric-t 0.283
- Radial asymmetry (upper−lower): skew-t 0.605 vs symmetric-t 0.008 (~0)
- gamma=0 EXACT recovery: max abs deviation 0.0e+00 (≤ 1e-09)
- understatement_sign_ok=True; asymmetry_ok=True; ordering_ok=True; gamma_zero_recovery_ok=True; digest=0ed75b742babce6b8e34b02e82d3d5e4305b66214ae44acc2af2e922b904c4f3

The pre-study uses a SYNTHETIC seven-driver portfolio on common random numbers; the symmetric-t basis is the SAME GH mixture with gamma = 0 (mixing variate W and Gaussian Z reused), through IDENTICAL frozen margins - so the ONLY difference is upper-tail asymmetry. Positive skewness lifts the upper-tail-dependence proxy to 0.742 (vs 0.291 symmetric) while the lower tail stays near-symmetric (0.136), and raises VaR99.5 by 10.2% and ES99.5 by 10.7%: the symmetric copula UNDERSTATES upper-tail capital, the SAME sign as the documented nested-vs-frozen-t copula-form residual. The gamma = 0 recovery is EXACT (max abs deviation 0.0e+00). It demonstrates the MECHANISM and its SIGN, not the magnitude of the real-data effect (synthetic margins; single skewness scalar; no per-node clip binding); the real magnitude is quantified only at Tasks 2-3.

## 4. Gap analysis (standards vs current model)

### Solvency II Del. Reg. Art. 234; IFoA Aggregation WP (dependence on the basis used, incl. tail behaviour)

- **Requirement:** Diversification/dependence empirically justified ON THE BASIS ACTUALLY USED for capital, INCLUDING tail behaviour and tail asymmetry; the copula form must be adequate, not only its parameters.
- **Current state:** Copula frozen as a radially-SYMMETRIC Student-t (df 2.9451, tail-matched on average pairwise upper-tail dependence, Phase 23 Task 2). lambda_U = lambda_L by construction; the joint loss tail is upper-asymmetric.
- **Gap:** 91.9% of the 14.29% nested gap (6,120.2) is copula-FORM and exceeds the whole gaussian->t dependence-form sensitivity (4,765.6) - a SHAPE gap no df re-choice can close.
- **Phase 27 design:** Task 2: add an upper-tail-asymmetry parameter (skew-t) on the frozen (df, Sigma); gamma = 0 recovers the freeze exactly; fit gamma to realised upper-tail co-exceedances (margins/df unchanged).

### SOA ASOP 56 §3.5 (dependency structure appropriate to purpose)

- **Requirement:** The dependency structure - including tail co-movement and its asymmetry - appropriate to the intended purpose; material structural limitations identified and addressed where practicable.
- **Current state:** The symmetric-t structural limitation is DISCLOSED (P26T3 decomposition) and registered, but not yet remediated.
- **Gap:** A disclosed structural limitation that dominates the residual should be attacked with a richer structure, not left as standing disclosure.
- **Phase 27 design:** Skew-t is the cheapest super-set: one extra parameter, exact nesting of the freeze, governed as a single additive copula change.

### IA TAS M §3.2/§3.6 (limitations disclosed; evidence reproducible)

- **Requirement:** Material limitations disclosed with quantification; remediation evidence reproducible with recorded config and pre-registered gates.
- **Current state:** P26T3/T5 disclose the copula-form residual verbatim in the report, risk register and offline UI with the bootstrap CI.
- **Gap:** Disclosure exists; the REMEDIATION (a richer copula form) is the open item.
- **Phase 27 design:** Task 3 headline gate: skew-t 95% bootstrap CI tested against nested 46,638.9 (closure or residual re-decomposed); seeds/config/digests recorded; Task 4 refreshes MR-010/MR-014 and opens MR-015 for the copula-form change.

### Solvency II Del. Reg. Art. 23 (management actions consistent with practice)

- **Requirement:** Allowance for management actions consistent with how they would be exercised - including which losses are relievable in a JOINT tail event.
- **Current state:** The carve-out (non-cuttable) drivers - credit loss, FX/liquidity offsets - dominate the joint tail (P24T3/P26T2); a symmetric copula under-weights their simultaneous-crash corner.
- **Gap:** Under-stating the joint upper tail under-states the un-relievable carve-out losses, i.e. understates required capital.
- **Phase 27 design:** The skew-t lifts the upper-tail corner where the carve-outs co-move; relief still applies only to the cuttable component per scenario (P26T2 convention unchanged).

## 5. Acceptance criteria (FIXED, pre-registered — no gate-shopping)

**Task 2:**

- Add an upper-tail-asymmetry parameter (GH skew-t copula) on the FROZEN (df 2.9451, Sigma); the symmetric t is recovered EXACTLY at gamma = 0 (strict super-set; nested freeze)
- gamma = 0 EXACT-recovery check: skew-t aggregate reproduces the symmetric-t aggregate to within 1e-09 on common random numbers (archive cross-check is then exact)
- Frozen-t COMPONENT read-out 39,975.7 reproduced bit-identically BEFORE any skew-t computation (archive cross-check)
- Rank invariance: df re-matched on the WITHOUT-actions staged losses within 0.0001 of 2.9451; correlation matrix max|diff| <= 1e-12 (df + Sigma FROZEN; only gamma added; Art. 234)
- Margins UNCHANGED: standalone marginal capital bit-identical (the upgrade changes the COPULA only)
- gamma fitted to realised upper-tail co-exceedances of the standalone loss vectors (no re-tuning of df/Sigma/margins; leakage-free)
- Sign gate (pre-registered): skew-t re-aggregated path-wise SCR >= frozen-t component 39,975.7; magnitude DISCLOSED, not gated
- Symmetric-t component basis RETAINED and reported alongside as the comparison variant
- No gate-shopping: these gates fixed in this Task 1 note before any real-data skew-t fit
- code_change ChangeRecord OWNER_REVIEW

**Task 3:**

- Skew-t margin bootstrap: >= 200 replicates x 20,000 sims (P26T3 pattern)
- HEADLINE gate: nested path-wise reference 46,638.9 INSIDE the skew-t 95% bootstrap CI (closure of the copula-form residual) - if still outside, the residual gap MUST be RE-decomposed (residual copula-form vs relief-surface) and the REDUCTION vs the frozen-t copula-form residual 6,120.2 quantified - no silent acceptance
- Directional gate: skew-t REDUCES the nested gap on common random numbers vs the symmetric-t basis (no widening)
- Bootstrap SE <= 5% of the mean SCR
- Idempotent re-run digest-identical; seeds/config recorded
- methodology_change ChangeRecord OWNER_REVIEW

**Task 4:**

- Tail diagnostics on the skew-t basis: skew-vs-symmetric and skew-vs-nested deltas at VaR/ES/SCR; upper- vs lower-tail dependence reported (the asymmetry is the headline)
- MR-010 / MR-014 refreshed if the skew-t SCR moves more than 1% from the frozen-t component read-out (disclosure trigger, not pass/fail); open MR-015 for the copula-form (radial-asymmetry) change
- Rank invariance re-verified: df 2.9451 on without-actions losses; correlation frozen; only gamma added (no silent re-tuning)
- Reproducibility: seeds, config, digests recorded; assumption_change/governance ChangeRecord OWNER_REVIEW

**Task 5 plan:** Offline-UI propagation (ui_data.json contract 1.8.0 -> 1.9.0 ADDITIVE; richer-tail panel: skew-t-vs-symmetric-t-vs-nested SCR comparison, upper/lower tail-dependence asymmetry, bootstrap CI closure read-out, gates) + PHASE 27 COMPLETE documentation; UI consumes ONLY model-output JSON, zero-install.

## 6. Limitations

- The synthetic pre-study proves the upper-tail-asymmetry mechanism and its SIGN, not the magnitude (synthetic margins; single skewness scalar; rank-PIT copula isolation; no per-node clip binding).
- The skew-t adds ONE asymmetry parameter; if the real residual needs heterogeneous tail dependence ACROSS drivers, grouped-t (deferred) is the next escalation; vine is the general fallback.
- gamma is fitted to upper-tail co-exceedances - a finite-sample estimate; its sampling error is propagated through the Task 3 bootstrap.
- Margins and df remain the calibrated frozen values; the upgrade does not revisit the marginal calibration (out of scope this phase).
- Action parameters remain educational placeholders pending credentialled practice data + independent APS X2 review.

## 7. Standards

- Solvency II Delegated Reg. Art. 234 (empirically justified diversification incl. tail behaviour; dependence justified on the basis actually used for capital)
- Solvency II Delegated Reg. Art. 23 (future management actions: objective, realistic, verifiable)
- SOA ASOP 56 §3.1.3/§3.4/§3.5
- SOA ASOP 25 §3.3
- IA TAS M §3.2/§3.6
- IFoA Life Aggregation & Simulation working party
- Demarta & McNeil (2005), The t copula and related copulas (skew-t copula)
- McNeil, Frey & Embrechts (2015), Quantitative Risk Management ch. 7 (GH skew-t; tail dependence)
- Daul, De Giorgi, Lindskog & McNeil (2003), The grouped t-copula
- Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence (vines)

*Generated by scripts/build_phase27_task1_design_note.py — educational model; production sign-off withheld.*
