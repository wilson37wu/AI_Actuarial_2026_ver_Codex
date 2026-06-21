# Post-Phase-IGUI Task 6 - Design Note: RQMC + Control-Variates Variance Reduction for the OUTER Capital (SCR) Loop

**Verdict: PASS** - pure governance (governance_change); NO parameter change; implementation DEFERRED. Classification: EFFICIENCY.

## 1. Candidate (pre-registered, exactly one)

- **MR-VR-2** - RQMC + control-variates variance reduction for the OUTER capital (SCR) loop
- Touches copula structure: **False** (Phase 30 stop-rule compliant)
- No model parameter change: **True**; implementation deferred: **True**
- Techniques under study: crude_iid, sobol_rqmc, control_variate, stratified

## 2. Context

Both prior diagnostics/efficiency candidates are COMPLETE: MR-CAL-1 (credentialled-data calibration residuals, Task 2) and MR-VR-1 (inner-path antithetic/CRN/RQMC variance reduction for the TVOG estimator, Task 4, surfaced offline at Task 5). MR-VR-1 delivered large gains on the MEAN-TVOG target (Sobol-RQMC 2241x, CRN 18.9x, antithetic 1.88x) but explicitly left the OUTER capital loop untouched, and recorded that antithetic is INEFFECTIVE (1.31x) precisely at the 99.5% quantile - which is the OUTER loop's target. The remaining admissible numerical gain is therefore on the OUTER SCR estimator: the 99.5% tail over the governed outer scenario set. Two levers suit a tail target without introducing bias: scrambled-Sobol randomised-QMC over the outer scenario grid (precedented at 2.76x-7.1x on the outer aggregation basis), and a CONTROL VARIATE formed from the cheap closed-form / proxy SCR already computed alongside the nested estimate (variance falls by 1/(1-rho^2) for control-target correlation rho, with NO bias once beta is fit out-of-sample). With model FORM frozen under the Phase 30 binding stop-rule, this is a NUMERICAL improvement only: the study must MEASURE - with CIs - whether RQMC and the control variate actually cut outer-loop variance at the 99.5% quantile, and the governed production estimator and headline SCR stay BIT-IDENTICAL.

Frozen cross-check references:

- Governed frozen-t component SCR: **39,975.654628**
- Nested path-wise reference: 46,638.9
- MR-VR-1 inner-loop variance-reduction results (work-normalised, crude=1.0):

  - sobol_rqmc_mean_tvog: 2241x
  - crn_mean_tvog: 18.9x
  - antithetic_mean_tvog: 1.88x
  - antithetic_q995: 1.31x

- Outer-basis scrambled-Sobol RQMC precedents (work-normalised, crude=1.0):

  - sobol_qmc_p16: 7.1x
  - sobol_qmc_p18: 2.76x
  - sobol_qmc_p19_4d: 3.28x
  - sobol_qmc_p21: 4.8x

## 3. Scope deferred to next cycle (implementation)

- A DISCLOSED efficiency study on the OUTER capital / SCR loop comparing crude i.i.d. MC against scrambled-Sobol RQMC, a closed-form/proxy control variate, and (optional) proportional tail stratification - all targeting the governed 99.5% SCR over the SAME governed model.
- Unbiasedness evidence: control-variate beta fit on a held-out pilot so it adds no bias, and the RQMC mean over >= 200 independent scramble seeds agrees with crude within 0.5%.
- Work-normalised variance-reduction ratios and effective-sample-size with >= 200-replicate CIs at the 99.5% target; the outer scenario count n* needed for a target SCR standard error under each scheme; the disclosed control-target correlation rho and realised reduction 1/(1-rho^2).
- A DISCLOSED report + optional ADDITIVE offline-UI surface; the governed production estimator and headline SCR stay bit-identical (NOT an adoption).

## 4. Pre-registered acceptance gates (frozen now)

- **G1 - Governed-headline invariance.** The governed frozen-t component SCR 39,975.654628199336 AND every governed capital output are recovered BIT-IDENTICAL (dev <= 1e-09) with the production estimator untouched. The outer-loop RQMC / control-variate estimator is ADDITIVE / DISCLOSED and never silently replaces the governed production estimator.
- **G2 - Estimator unbiasedness (control variate + RQMC).** The control-variate estimator is demonstrated UNBIASED for the SCR / 99.5% tail target - the control coefficient beta is estimated on a held-out pilot so the variate adds NO bias - and the scrambled-Sobol RQMC mean over >= 200 independent scramble seeds agrees with the crude estimator within 0.5% of the crude mean (no systematic shift introduced by the sampling-scheme transform).
- **G3 - Variance-reduction efficacy with CIs (tail target).** Work-normalised variance-reduction ratios (crude vs scrambled-Sobol RQMC vs control-variate vs optional stratified) for the OUTER 99.5% SCR target are reported with >= 200-replicate CIs and an effective-sample-size / efficiency read-out; >= 1.5x on at least one technique to be declared useful. Because the OUTER target IS the 99.5% quantile - where MR-VR-1 recorded antithetic as INEFFECTIVE (1.31x) - the study MEASURES, never assumes, tail efficacy; the control-variate correlation rho and realised reduction 1/(1-rho^2) are disclosed.
- **G4 - Slice-stable RQMC reproducibility.** Scrambled-Sobol outer point sets drawn via slice-stable SeedSequence spawn (SeedSequence(seed).spawn(n)[i0:i1]) so staged builds are bit-reproducible; the scramble seed, Sobol dimension, and outer/inner grid are documented and version-pinned; an idempotent run digest is emitted.
- **G5 - Adoption materiality - report not apply.** Any indicated change to the governed SCR from ADOPTING the variance-reduced outer estimator as production is REPORTED as an information item but NOT applied. If |indicated dSCR| > 1% of the governed headline, a new model-risk entry is OPENED rather than auto-switching the production estimator (which stays governed unless the owner adopts).
- **G6 - Governance + offline-UI discipline.** Idempotent run digest; governance_change / methodology_change ChangeRecord left OWNER_REVIEW; unit tests added; if an offline-UI surface is added it is an ADDITIVE contract bump only, self-tests ok:true 0 network / 0 JS errors, 0 external refs, every pre-existing key bit-identical.

## 5. Candidate sequencing

- Completed pool (efficiency/diagnostics): MR-CAL-1, MR-VR-1
- Selected now: **MR-VR-2**
- Next candidate: **MR-LONGEV-1** (deferred, owner sign-off)

(c) OUTER-loop RQMC + control-variates is the recorded NEXT efficiency candidate after MR-VR-1 completed the INNER path; it is diagnostics/efficiency-only (cleanest stop-rule compliance, no parameter change, no copula structure) and it directly attacks the 99.5% tail target that the inner-path antithetic lever could not. (a) longevity 5th-driver (MR-LONGEV-1) remains a parameter-adding model-FORM change deferred to a dedicated owner-sign-off cycle; (b) a packaging A/B/C pivot remains available to the owner but is not a model-improvement candidate.

## 6. Owner-decision note

The diagnostics/efficiency pool is NOT yet exhausted: MR-VR-2 (this candidate) is a clean, admissible numerical-efficiency improvement on the outer loop. After MR-VR-2, the pool of stop-rule-admissible efficiency/diagnostic work narrows materially, and the next substantive model improvement (MR-LONGEV-1 longevity 5th driver) is a parameter-adding model-FORM change requiring explicit owner sign-off - it is NOT auto-run. Owner options recorded for the cycle after MR-VR-2: (1) sign off MR-LONGEV-1; (2) pivot to packaging A/B/C build-spec / CI release-matrix; (3) declare the auto-development frontier complete and freeze.

## 7. Stop-rule compliance

No copula structure and no model parameter touched; only the Monte Carlo sampling scheme (RQMC point set) of an existing estimator changes and an unbiased control variate is added; MR-016/MR-017 untouched; governed headline frozen. Admissible under the Phase 30 binding stop-rule (which bars new copula-structure candidates only).

## 8. Standard references

- Glasserman (2004) Monte Carlo Methods in Financial Engineering, ch. 4 (control variates) and ch. 5 (quasi-Monte Carlo)
- L'Ecuyer (1994) Efficiency improvement and variance reduction; RQMC
- Owen (1997) Scrambled net variance for integrals of smooth functions
- Bauer, Reuss & Singer (2012) On the calculation of the Solvency Capital Requirement based on nested simulations (outer-loop efficiency)
- SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation)
- IFoA Model Practice Note (MPN) section 4 (documentation, independent review)
- Solvency II Delegated Regulation Article 124 (validation standards)

## 9. Self-consistency gate: PASS (22/22 checks)

*Generated by scripts/build_postigui_task6_design_note.py.*
