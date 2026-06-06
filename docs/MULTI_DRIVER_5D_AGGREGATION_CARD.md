# Five-Driver Tail-Dependent Risk Aggregation - Limitation Card

**Classification:** EDUCATIONAL ONLY - placeholder parameters; not a regulatory capital model.

## Scope

Phase 19 Task 4 adds `par_model_v2/projection/multi_driver_capital_5d_aggregation.py` (five-driver standalone decomposition + 5x5 var-covar + copula-on-realised-losses aggregation, benchmarked to genuine five-driver nested capital) for the five-driver economic-capital proxy (rate + equity-guarantee + credit-spread + lapse-behaviour + **mortality-trend**). It generalises the Phase 18 Task 4 four-driver aggregation; the five-driver nested primitives (Phase 19 Task 3) and the Phase 18 Task 1 copula aggregator are imported, never modified.

## Why (MR-010, five-driver)

Adding the second non-financial driver (mortality trend) keeps the ESG-factor var-covar understatement wide at ~48.8% of the diversified nested capital: the realised capital-loss vectors all co-move positively in the tail (anti-selection) while several ESG factor off-diagonals are negative or zero and mortality's row is orthogonal (zeros). The AIC-selected copula on the realised losses reconciles to five-driver nested capital within ~6.5%, **mitigating MR-010** for five drivers.

## Mortality-trend driver (5th, second non-financial, orthogonal)

Mortality trend enters via the multiplier `G(m_H) = exp(theta * m_H)` scaling the central annual `q_x`. It is **non-financial** (P = Q, no risk premium) and **orthogonal** to every financial driver in the default 5x5 matrix, so its standalone SCR is the **smallest** of the five drivers and the five-driver nested SCR is a small monotone increment over the four-driver figure (benefit-timing on a sum-assured endowment). The copula must not over-state this second orthogonal tail axis - the MR-012 tail-aggregation governance check.

## Five-driver finding (multiplicative lapse x mortality coupling)

BOTH the lapse driver (in-force factor `IF(r,b)`) and the mortality driver (`G(m_H)` on `q_x`) scale the guaranteed leg MULTIPLICATIVELY, so the CRN additive decomposition leaves a non-trivial interaction residual (the `IF x equity-guarantee` and `IF x mortality-G` cross-terms). 'Nested <= standalone sum' is therefore NOT a valid invariant for five drivers; the residual is measured and disclosed, not removed.

## Limitations / model-use restrictions

- Mortality trend is a single systemic Lee-Carter-style OU level index with placeholder parameters and no age / cohort / basis-risk structure.
- Lapse behaviour is a single systemic OU index with placeholder parameters and no product / cohort structure.
- FX, liquidity and management-action drivers remain outside the five-driver aggregation.
- Copulas are fitted to a finite outer-state sample; tail-dependence estimates are sampling-noisy and marginals do not extrapolate.
- A dedicated five-driver tail-convergence / variance-reduction diagnostics module and offline-viewer five-driver uplift are the remaining Phase 19 Task 4 sub-items (next cycle), mirroring the Phase 18 Task 3 -> Task 4 split.
- Credentialled calibration data and independent APS X2 review are required before any production use.

## Standards

SOA ASOP 56 §3.5, SOA ASOP 56 §3.1, SOA ASOP 25 §3.3, SOA ASOP 7 §3.3, IA TAS M §3.2, IA TAS M §3.5, IA TAS M §3.6, Solvency II Delegated Reg. Art. 234, IFoA Life Aggregation & Simulation working party, Lee & Carter (1992).
