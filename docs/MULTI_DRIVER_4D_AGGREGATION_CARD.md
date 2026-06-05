# Four-Driver Tail-Dependent Risk Aggregation - Limitation Card

**Classification:** EDUCATIONAL ONLY - placeholder parameters; not a regulatory capital model.

## Scope

Phase 18 Task 4 adds `par_model_v2/projection/multi_driver_capital_4d_aggregation.py` (four-driver standalone decomposition + 4x4 var-covar + copula-on-realised-losses aggregation, benchmarked to genuine four-driver nested capital) and `FourDriverTailDiagnostics` (outer-count convergence, bootstrap CI/SE, and crude/antithetic/Sobol variance reduction) for the four-driver economic-capital proxy (rate + equity-guarantee + credit-spread + lapse-behaviour).

## Why (MR-010, four-driver)

Adding the non-financial lapse driver WIDENS the ESG-factor var-covar understatement to 47.4% of the diversified nested capital, because the realised capital-loss vectors all co-move positively in the tail (anti-selection) while several ESG factor off-diagonals are negative or zero. The AIC-selected copula on the realised losses reconciles to four-driver nested capital within 9.4%, **mitigating MR-010** for four drivers.

## Four-driver finding (multiplicative lapse coupling)

The lapse driver scales the policyholder benefit MULTIPLICATIVELY through the in-force factor IF(r,b), so the CRN additive decomposition leaves a -11.1%-of-nested interaction residual and the genuine nested capital is **super-additive** vs the CRN-additive standalone sum. 'Nested <= standalone sum' is therefore NOT a valid invariant for four drivers; the residual is reported, not removed.

## Limitations / model-use restrictions

- Lapse behaviour is a single systemic OU index with placeholder parameters and no product / cohort structure.
- Mortality-trend, FX, liquidity and management-action drivers remain outside the four-driver aggregation.
- Copulas are fitted to a finite outer-state sample; tail-dependence estimates are sampling-noisy and marginals do not extrapolate.
- The variance-reduction study runs on a smooth pilot-anchored Gaussian-copula surrogate of the horizon-state distribution.
- Credentialled calibration data and independent APS X2 review are required before any production use.

## Standards

SOA ASOP 56 §3.5, SOA ASOP 56 §3.1.3, SOA ASOP 25 §3.3, SOA ASOP 7 §3.3, IA TAS M §3.2, IA TAS M §3.6, Solvency II Delegated Reg. Art. 234, IFoA Life Aggregation & Simulation working party, L'Ecuyer (2018) RQMC.
