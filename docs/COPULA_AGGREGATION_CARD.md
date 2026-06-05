# Copula-Based Tail-Dependent Risk Aggregation — Limitation Card

**Classification:** EDUCATIONAL ONLY — placeholder parameters; not a regulatory capital model.

## Scope

Phase 18 Task 1 adds `par_model_v2/projection/multi_driver_copula_aggregation.py`, a copula-based aggregation engine for the three-driver (rate + equity + credit-spread) economic-capital proxy. It fits Gaussian, Student-t and survival-Clayton copulas to the realised standalone capital-loss vectors, rebuilds the joint loss from empirical marginals plus each copula, and reads the 99.5% aggregate SCR off the simulated joint loss, benchmarking to the three-driver nested ground truth.

## Why (MR-010)

The legacy variance-covariance formula understates diversified nested capital by 34.5% because it aggregates on the governed ESG *factor* correlation (negative off-diagonals) while the realised capital-*loss* vectors co-move strongly *positively* in the tail, and because an elliptical formula has zero tail dependence. The AIC-selected copula reconciles to nested within 1.4%, **mitigating MR-010**.

## Limitations / model-use restrictions

- Copulas are fitted to a finite outer-state sample; tail-dependence estimates are sampling-noisy.
- Marginals are empirical, so the aggregate cannot extrapolate beyond each component's simulated loss range.
- Student-t and survival-Clayton impose a single exchangeable / elliptical tail-dependence structure across all driver pairs.
- Credit is a single systemic CIR++ spread proxy; lapse, mortality trend, FX, liquidity and management action remain outside the aggregation.
- Credentialled calibration data and independent APS X2 review are required before any production use.

## Standards

SOA ASOP 56 §3.5, SOA ASOP 25 §3.3, IA TAS M §3.6, Solvency II Delegated Reg. Art. 234, IFoA Life Aggregation & Simulation working party, Demarta-McNeil 2005 (t-copula).
