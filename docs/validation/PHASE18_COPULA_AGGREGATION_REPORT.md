# Phase 18 Task 1 — Copula-Based Tail-Dependent Risk Aggregation

**Classification:** EDUCATIONAL ONLY — placeholder parameters; not a regulatory capital model.

**Verdict:** PASS - copula aggregation (selected: gaussian) reconciles to nested capital within 1.4% (best 1.4%) vs var-covar 34.5%; MR-010 mitigated

Drivers: short_rate, equity_guarantee, credit_spread.  Run `copula-agg-afefd696`; reproducibility digest `270cc6426dfa5f9b`.

## Benchmarks

- Three-driver **nested** SCR (diversified ground truth): **39774.6**
- Legacy **var-covar** SCR (governed ESG *factor* correlation): **26061.7** — understates nested by **34.5%** (MR-010)
- Standalone SCR sum (comonotonic bound): 46209.4

Realised capital-loss correlation (rate, equity, credit): [[1.0, 0.503, 0.783], [0.503, 1.0, 0.571], [0.783, 0.571, 1.0]].

## Copula aggregation results (99.5%)

| Copula | SCR | rel. err vs nested | upper-tail dep. λU | AIC | params |
|---|--:|--:|--:|--:|---|
| gaussian ⟵ selected | 40342.0 | 1.43% | 0.000 | -680.7 | corr |
| student_t | 40388.6 | 1.54% | 0.008 | -675.7 | df=50 |
| survival_clayton | 45771.8 | 15.08% | 0.644 | -303.7 | θ=1.58 |

**Selected copula (min AIC):** `gaussian`.

## MR-010 finding (empirical justification — Solvency II Art. 234)

The var-covar formula understates diversified nested capital by ~34% for two compounding reasons: (1) it aggregates with the governed ESG *factor* correlation (negative off-diagonals) while the realised capital-*loss* vectors co-move strongly *positively* in the tail; and (2) an elliptical formula has zero asymptotic tail dependence.  Re-fitting the dependence with a copula on the **realised loss vectors** removes (1) entirely: the AIC-selected copula reconciles to the nested benchmark within 1.4–15.1%.  The Student-t fit collapses toward Gaussian (high df), and survival-Clayton (genuine upper-tail dependence) bounds the estimate conservatively from above — i.e. at this sample the residual *tail* dependence beyond the (correctly-signed) linear loss correlation is modest.  This **MITIGATES MR-010**: the copula engine, fitted to realised losses, is the recommended aggregation; the var-covar formula is retained for reference only.

## Standards

SOA ASOP 56 §3.5, SOA ASOP 25 §3.3, IA TAS M §3.6, Solvency II Delegated Reg. Art. 234, IFoA Life Aggregation & Simulation WP, Demarta-McNeil 2005 (t-copula).
