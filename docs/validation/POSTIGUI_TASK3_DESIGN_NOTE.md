# Post-Phase-IGUI Task 3 - Design Note: Inner-Path Antithetic / CRN Variance Reduction for the TVOG Estimator

**Verdict: PASS** - pure governance (governance_change); NO parameter change; implementation DEFERRED. Classification: EFFICIENCY.

## 1. Candidate (pre-registered, exactly one)

- **MR-VR-1** - Inner-path antithetic / CRN variance reduction for the TVOG estimator
- Touches copula structure: **False** (Phase 30 stop-rule compliant)
- No model parameter change: **True**; implementation deferred: **True**
- Techniques under study: crude_iid, antithetic, crn, sobol_qmc

## 2. Context

MR-CAL-1 (credentialled-data calibration-residual diagnostics) COMPLETED at Post-Phase-IGUI Task 2: the margin-calibration residual is only 8.15% of the gap to nested, copula-FORM dominates at 91.85%, and the indicated dSCR (0.90%) was immaterial and not applied. With model FORM frozen under the Phase 30 binding stop-rule, the next worthwhile improvement is NUMERICAL, not structural: the inner-path / nested-stochastic TVOG estimator is the most compute-intensive part of the run, and its Monte Carlo variance directly sets how many inner paths are needed for a stable SCR. Antithetic pairing and common-random-numbers (CRN) across the guarantee-on / guarantee-off legs are the standard, bias-free variance-reduction levers. The recorded outer-basis precedents show Sobol-RQMC helps (2.8x-7.1x) while antithetic is expected-ineffective at the extreme 99.5% quantile (0.72x-0.78x) - so the study must MEASURE, not assume, the inner-path efficacy, with CIs.

Frozen cross-check references:

- Governed frozen-t component SCR: **39,975.654628**
- Nested path-wise reference: 46,638.9
- Variance-reduction ratio precedents (outer basis, work-normalised):

  - sobol_qmc_p16: 7.1x
  - sobol_qmc_p18: 2.76x
  - sobol_qmc_p19_4d: 3.28x
  - sobol_qmc_p21: 4.8x
  - antithetic_p19_4d: 0.72x
  - antithetic_p21: 0.78x

## 3. Scope deferred to next cycle (implementation)

- A DISCLOSED efficiency study on the inner-path TVOG estimator comparing crude i.i.d. MC against antithetic, CRN, and (optional) Sobol-RQMC inner sampling, all on the SAME governed outer states.
- Unbiasedness evidence: mean over >= 200 independent replicate seeds for each scheme agrees with crude within 0.5%, so no scheme shifts the estimate.
- Work-normalised variance-reduction ratios and effective-sample-size with >= 200-replicate CIs; the inner-path count n* needed for a target SE under each scheme.
- A DISCLOSED report + optional ADDITIVE offline-UI surface; the governed production estimator and headline SCR stay bit-identical (NOT an adoption).

## 4. Pre-registered acceptance gates (frozen now)

- **G1 Governed-headline invariance** - The governed frozen-t component SCR 39,975.654628199336 AND every governed capital output are recovered BIT-IDENTICAL (dev <= 1e-09) with the production estimator untouched. The variance-reduction estimator is ADDITIVE / DISCLOSED and never silently replaces the governed production estimator.
- **G2 Estimator unbiasedness** - Antithetic and CRN inner-path estimators are demonstrated UNBIASED for the TVOG / SCR target: the mean over >= 200 independent replicate seeds agrees with the crude estimator within 0.5% of the crude mean (no systematic shift introduced by the sampling-scheme transform).
- **G3 Variance-reduction efficacy with CIs** - Work-normalised variance-reduction ratios (crude vs antithetic vs CRN vs optional Sobol-RQMC) are reported with >= 200-replicate CIs and an effective-sample-size / efficiency read-out; >= 1.5x on at least one technique to be declared useful. Antithetic expected-INEFFECTIVE at the extreme 99.5% quantile is DISCLOSED, consistent with the recorded outer-basis precedents (0.72x-0.78x).
- **G4 Slice-stable CRN reproducibility** - Inner shocks drawn via slice-stable SeedSequence spawn (SeedSequence(seed).spawn(n)[i0:i1]) so staged builds are bit-reproducible; an idempotent run digest is emitted; all seeds and the n_inner / n_outer grid are documented and version-pinned.
- **G5 Adoption materiality - report not apply** - Any indicated change to the governed SCR from ADOPTING the variance-reduced estimator as production is REPORTED as an information item but NOT applied. If |indicated dSCR| > 1% of the governed headline, a new model-risk entry is OPENED rather than auto-switching the production estimator (which stays governed unless the owner adopts).
- **G6 Governance + offline-UI discipline** - Idempotent run digest; governance_change / methodology_change ChangeRecord left OWNER_REVIEW; unit tests added; if an offline-UI surface is added it is an ADDITIVE contract bump only, self-tests ok:true 0 network / 0 JS errors, 0 external refs, every pre-existing key bit-identical.

## 5. Candidate sequencing (pool of three)

- Completed prior: **MR-CAL-1** (credentialled-data calibration diagnostics, done at Task 2)
- Selected NOW: **MR-VR-1** (inner-path antithetic/CRN variance reduction for TVOG)
- Next candidate: **MR-LONGEV-1** (mortality-trend / longevity 5th driver - parameter-adding, owner sign-off)
- Rationale: (c) inner-path antithetic/CRN variance reduction is the recorded NEXT candidate after MR-CAL-1 completed; it is diagnostics/efficiency-only (cleanest stop-rule compliance, no parameter change, no copula structure). (a) longevity 5th-driver (MR-LONGEV-1) remains a parameter-adding model-FORM change deferred to a dedicated owner-sign-off cycle.

## 6. Stop-rule compliance

No copula structure and no model parameter touched; only the Monte Carlo sampling scheme of an existing estimator changes; MR-016/MR-017 untouched; governed headline frozen. Admissible under the Phase 30 binding stop-rule (bars new copula-structure candidates only).

## 7. Validation gate

- ok: **True** (16 checks)
- candidate_id: True
- no_param_change: True
- stop_rule_no_copula: True
- implementation_deferred: True
- change_type_governance: True
- four_vr_techniques: True
- crude_baseline_present: True
- headline_frozen: True
- nested_ref: True
- vr_precedents_present: True
- six_gates: True
- gate_ids: True
- g1_invariance: True
- g2_unbiasedness: True
- sequencing_present: True
- standards_cited: True

## 8. Standards

- Glasserman (2004) Monte Carlo Methods in Financial Engineering, ch. 4 (variance reduction: antithetics, common random numbers)
- L'Ecuyer (1994) Efficiency improvement and variance reduction; RQMC
- Boyle, Broadie & Glasserman (1997) Monte Carlo methods for security pricing
- SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation)
- IFoA Model Practice Note (MPN) section 4 (documentation, independent review)
- Solvency II Delegated Regulation Article 124 (validation standards)

*Generated by scripts/build_postigui_task3_design_note.py.*
