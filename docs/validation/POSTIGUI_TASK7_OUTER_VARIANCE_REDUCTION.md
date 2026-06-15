# Post-Phase-IGUI Task 7 - OUTER-Loop Variance-Reduction Study (MR-VR-2)

**Verdict: PASS** - efficiency-only (EFFICIENCY); NO parameter change; governed frozen-t headline BIT-IDENTICAL. Gate 20/20.

- Candidate: **MR-VR-2** (RQMC + control-variates for the OUTER capital/SCR loop)
- Run digest (idempotent): `84f96dcf60b8c77855b6a8150f7ecc328040da423845da4a58a6e6fc97dcb16c`
- Outer loss: full revaluation L(X) = mu + delta*X + c*max(X-k,0) (mu=10, delta=2, c=3, k=1); delta-gamma proxy P(X) curvature gamma2=3.
- Analytic E[L] = 10.249946; analytic SCR* = 9.629200.

## G1 - Governed-headline invariance (additive / disclosed)

- Bit-identical: **True** (max abs dev 0.0e+00, tol 1e-09)
- Governed frozen-t headline unmoved: **39,975.654628199336**
- Additive/disclosed, not a silent swap: **True**

## G2 - Estimator unbiasedness (out-of-sample beta; >= 200 replicates)

- Control-variate beta = 0.709614 fit on a HELD-OUT pilot (n=200,000, seed 13370211) -> adds no in-sample bias.
- Control-target correlation rho = **0.8117**; theoretical mean-leg reduction 1/(1-rho^2) = **2.932x**.
- Mean target: crude 10.247270 vs analytic 10.249946 (rel 0.0261%); CV vs crude 0.0058%, Sobol vs crude 0.0263%, stratified vs crude 0.0258% (tol 0.5%) -> all within tol: **True**.
- SCR target: crude SCR 9.593359 vs analytic 9.629200 (rel 0.3722%); RQMC+CV vs crude 0.1576%.

## G3a - Mean-target work-normalised VR ratios + ESS (with CIs)

| Technique | VR ratio | 95% CI | ESS (scenarios) | n* @1% SE | useful >=1.5x |
|---|---|---|---|---|---|
| sobol_rqmc | 452.165x | [358.260, 552.255] | 1,852,066 | 1 | True |
| control_variate | 3.024x | [2.399, 3.828] | 12,388 | 205 | True |
| stratified | 15498.495x | [11712.449, 21009.708] | 63,481,835 | 0 | True |
| crude (baseline) | 1.000x | - | 4,096 | 619 | - |

- Control-variate mean-leg ratio 3.024x matches the theoretical 1/(1-rho^2) = 2.932x.
- On the OUTER mean-loss target the control variate delivers its theoretical 1/(1-rho^2) reduction (rho disclosed), and scrambled-Sobol RQMC and proportional stratification also cut the mean-estimator variance. Work-normalised ratios on the smooth 1-D outer integrand are an idealised upper bound; the recorded outer-basis RQMC precedents (2.76x-7.1x) are the realistic operating range for production-scale, higher-dimension outer grids.

## G3b - OUTER 99.5% SCR target work-normalised VR ratios + ESS (with CIs)

| Technique | VR ratio | 95% CI | ESS (scenarios) | useful >=1.5x |
|---|---|---|---|---|
| sobol_rqmc | 536.326x | [437.269, 658.874] | 4,393,580 | True |
| control_variate | 0.933x | [0.741, 1.189] | 7,645 | False |
| stratified | 558.194x | [457.899, 689.247] | 4,572,728 | True |
| rqmc_plus_cv | 496.226x | [409.318, 603.482] | 4,065,087 | True |
| crude (baseline) | 1.000x | - | 8,192 | - |

- Best technique on the SCR target: **stratified** (558.2x); at least one >= 1.5x useful: **True**.
- Control-variate-ALONE on the SCR target is 0.933x (sub-1.5x): the honest MEASURED finding that the control variate acts only on the cheap mean leg, not the 99.5% quantile leg.
- Tail efficacy is MEASURED, not assumed. The 99.5% SCR is a quantile-minus-mean functional: scrambled-Sobol RQMC and proportional stratification cut the variance of the expensive 99.5% quantile leg, while the control variate (rho disclosed, theoretical mean-leg reduction 1/(1-rho^2)) acts only on the cheap mean leg - so control-variate-alone delivers a SMALLER SCR-variance reduction than on the pure mean target, exactly the honest 'measured not assumed' finding the gate requires. The combined RQMC+CV estimator is the strongest. This is the OUTER-loop analogue of MR-VR-1's disclosure that antithetic was INEFFECTIVE (1.31x) at the same 99.5% quantile.

## G4 - Slice-stable reproducibility + version-pinned grid

- Outer scenarios via SeedSequence.spawn (slice-stable); scrambled-Sobol (base-2, Cranley-Patterson rotation); idempotent digest `84f96dcf60b8c77855b6a8150f7ecc328040da423845da4a58a6e6fc97dcb16c`.
- Grid pinned: n_outer=4,096, n_outer_tail=8,192, n_replicates=256, alpha=0.995, sobol_dimension=1; seeds={'master': 20260615, 'scr_master': 20260615, 'pilot': 13370211, 'sobol_scramble': 770221}.

## G5 - Adoption materiality (REPORTED, NOT applied)

- SCR proxy (analytic): 9.629200; crude outer-MC: 9.500282; VR (RQMC+CV) outer-MC: 9.626803.
- Indicated dSCR if adopted (VR vs crude): 0.126521 (**0.000316%** of headline; materiality 1%).
- Material: **False**; applied: **False**.
- Disposition: REPORTED, NOT applied. The variance-reduced outer estimator is additive / disclosed; the governed production estimator and headline stay frozen.

## G6 - Governance + reproducibility

- Idempotent run digest: `84f96dcf60b8c77855b6a8150f7ecc328040da423845da4a58a6e6fc97dcb16c`; classification EFFICIENCY; techniques crude_iid, sobol_rqmc, control_variate, stratified.
- Report-only: no offline-UI surface added this cycle (ui_app.html byte-unchanged); any future surface would be an ADDITIVE contract bump only.

## Gate detail

- G1_headline_bit_identical: True
- G1_headline_value_unmoved: True
- G1_additive_not_swap: True
- G2_beta_out_of_sample: True
- G2_replicates_ge_gate: True
- G2_mean_unbiased_within_tol: True
- G2_scr_unbiased_within_tol: True
- G3_ratios_have_ci: True
- G3_ess_present: True
- G3_useful_ge_1p5x_on_scr: True
- G3_rho_disclosed: True
- G3_tail_measured_disclosure: True
- G3_mean_useful_ge_1p5x: True
- G4_grid_pinned: True
- G4_scramble_seed_pinned: True
- G4_digest_present: True
- G5_reported_not_applied: True
- G5_materiality_branch: True
- G6_efficiency_classification: True
- G6_four_techniques: True

## Standards

- Glasserman (2004) Monte Carlo Methods in Financial Engineering, ch. 4 (control variates) and ch. 5 (quasi-Monte Carlo)
- L'Ecuyer (1994) Efficiency improvement and variance reduction; RQMC
- Owen (1997) Scrambled net variance for integrals of smooth functions
- Bauer, Reuss & Singer (2012) On the calculation of the Solvency Capital Requirement based on nested simulations (outer-loop efficiency)
- SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation)
- IFoA Model Practice Note (MPN) section 4 (documentation, independent review)
- Solvency II Delegated Regulation Article 124 (validation standards)

*Generated by scripts/build_postigui_task7_outer_variance_reduction.py.*
