# Post-Phase-IGUI Task 4 - Inner-Path Variance-Reduction Study (MR-VR-1)

**Verdict: PASS** - efficiency-only (EFFICIENCY); NO parameter change; governed frozen-t headline BIT-IDENTICAL. Gate 16/16.

- Candidate: **MR-VR-1**
- Run digest (idempotent): `cc0c2fea2bf9b86db75f6239a9ba6e3e0a1577a1e1290e24ce13732eb0c0f0d7`
- Inner integrand: Black-Scholes guarantee put (S0=100, G=105, sigma=0.18, T=10, r=0.025); analytic L = 12.470979

## G1 - Governed-headline invariance (additive / disclosed)

- Bit-identical: **True** (max abs dev 0.0e+00, tol 1e-09)
- Governed frozen-t headline unmoved: **39,975.654628199336**
- Additive/disclosed, not a silent swap: **True**

## G2 - Estimator unbiasedness (>= 200 replicates, within 0.5% of crude)

- Replicates: 256; inner paths/estimate: 4,096
- Crude mean 12.491352 vs analytic 12.470979 (rel 0.1634%)
- Antithetic vs crude: **0.3259%**; CRN vs crude: **0.1897%**; Sobol vs crude: **0.1646%** (tol 0.5%) -> all within tol: **True**

## G3 - Work-normalised variance-reduction ratios + ESS (with CIs)

| Technique | VR ratio | 95% CI | ESS (paths) | n* @1% SE | useful >=1.5x |
|---|---|---|---|---|---|
| antithetic | 1.882x | [1.456, 2.403] | 7,709 | 10,129 | True |
| crn | 18.929x | [14.671, 24.304] | 77,533 | 1,007 | True |
| sobol_qmc | 2241.111x | [1841.071, 2729.705] | 9,179,590 | 9 | True |
| crude (baseline) | 1.000x | - | 4,096 | 19,064 | - |

- At least one technique >= 1.5x useful: **True**.
- Work-normalised variance-reduction ratios are an UPPER bound idealisation: the inner integrand here is the smooth 1-D Black-Scholes put, where Sobol-RQMC's O(N^-1) convergence yields a very large ratio at N_inner. Real nested valuations with payoff kinks and higher inner dimension will see SMALLER (but still material) RQMC gains - the recorded outer-basis precedents (Sobol 2.8x-7.1x) are the realistic operating range. CRN across the guarantee-on/off legs is dimension-robust; antithetic helps the smooth mean but not the extreme quantile (see tail_study).

## G3 (tail) - Antithetic at the extreme 99.5% quantile (DISCLOSED ineffective)

- Antithetic work-normalised ratio on the 99.5% inner-loss quantile: **1.314x** [1.037, 1.692] -> ineffective (< 1.5x): **True**
- Outer-basis precedents: antithetic_p19_4d 0.72x, antithetic_p21 0.78x.
- Antithetic pairing is expected-INEFFECTIVE for the extreme 99.5% capital quantile: the symmetric +Z/-Z transform reduces the variance of smooth means but not of an extreme order statistic. The measured work-normalised ratio is reported with a CI and sits BELOW the 1.5x 'useful' bar - the same qualitative finding as the recorded outer-basis antithetic precedents (0.72x-0.78x, also sub-useful): antithetic is NOT the lever for the extreme quantile. Sobol-RQMC and CRN are the useful levers for the inner estimator.

## G4 - Slice-stable reproducibility + version-pinned grid

- Inner shocks via SeedSequence.spawn (slice-stable); idempotent digest `cc0c2fea2bf9b86db75f6239a9ba6e3e0a1577a1e1290e24ce13732eb0c0f0d7`.
- Grid pinned: n_inner=4,096, n_inner_tail=8,192, n_replicates=256, n_outer=2,000, alpha=0.995; seeds={'master': 20260615, 'outer': 770115, 'scr_inner': 330921, 'cp_shift': 90210}.

## G5 - Adoption materiality (REPORTED, NOT applied)

- SCR proxy (analytic outer): 12.4081; crude inner-MC: 12.9787; Sobol inner-MC: 12.4267.
- Indicated dSCR if adopted (Sobol vs crude): -0.5520 (**-0.0014%** of headline; materiality 1%).
- Material: **False**; applied: **False**.
- Disposition: REPORTED, NOT applied. The variance-reduced estimator is additive / disclosed; the governed production estimator and headline stay frozen.

## G6 - Governance + reproducibility

- Idempotent run digest: `cc0c2fea2bf9b86db75f6239a9ba6e3e0a1577a1e1290e24ce13732eb0c0f0d7`; classification EFFICIENCY; techniques crude_iid, antithetic, crn, sobol_qmc.
- Report-only: no offline-UI surface added this cycle (ui_app.html byte-unchanged); any future surface would be an ADDITIVE contract bump only.

## Gate detail

- G1_headline_bit_identical: True
- G1_headline_value_unmoved: True
- G1_additive_not_swap: True
- G2_replicates_ge_gate: True
- G2_unbiased_within_tol: True
- G3_ratios_have_ci: True
- G3_ess_present: True
- G3_nstar_present: True
- G3_useful_ge_1p5x: True
- G3_antithetic_tail_disclosed: True
- G4_grid_pinned: True
- G4_digest_present: True
- G5_reported_not_applied: True
- G5_materiality_branch: True
- G6_efficiency_classification: True
- G6_four_techniques: True

## Standards

- Glasserman (2004) Monte Carlo Methods in Financial Engineering, ch. 4 (variance reduction: antithetics, common random numbers)
- L'Ecuyer (1994) Efficiency improvement and variance reduction; RQMC
- Boyle, Broadie & Glasserman (1997) Monte Carlo methods for security pricing
- SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation)
- IFoA Model Practice Note (MPN) section 4 (documentation, independent review)
- Solvency II Delegated Regulation Article 124 (validation standards)

*Generated by scripts/build_postigui_task4_variance_reduction.py.*
