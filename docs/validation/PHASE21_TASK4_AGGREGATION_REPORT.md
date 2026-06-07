# Phase 21 Task 4 — Seven-Driver Tail-Dependent Aggregation + Tail Diagnostics

**Run:** 2026-06-07T02:21:44.766723+00:00
**Verdict:** PASS
**ChangeRecord:** `d57a31a5ebf94173bf5c55c5b9669ead` (OWNER_REVIEW)
**MR-010:** MITIGATED | **MR-012:** MITIGATED

## Standalone SCRs (99.5%, 1y)

| Driver | SCR |
|---|---|
| rate | 14486.3 |
| equity | 15931.6 |
| credit | 4713.9 |
| lapse | 22538.9 |
| mortality | 387.2 |
| fx | 4286.4 |
| liquidity | 63.3 |
| **Sum** | **62407.6** |

## Reconciliation

| Measure | SCR | vs nested |
|---|---|---|
| Var-covar (7x7 ESG) | 28996.2 | +40.5% understatement |
| Copula (gaussian) | 41592.6 | 14.6% rel err |
| Nested benchmark | 48694.0 | — |

Interaction residual (CRN sum vs nested): -16.6%.

## Tail diagnostics

* Copula-simulated VaR convergence over n_sim grid [10000, 25000, 50000, 100000, 200000]: last successive
  delta 0.07% (tol 1%) → **CONVERGED**.
* Simulated bootstrap 95% CI: VaR [158409, 158956] (SE 139,
  rel-halfwidth 0.2%); ES [162716, 163390].
* Nested small-sample bootstrap (n_outer=160): VaR [155625, 165796]
  (rel-halfwidth 3.1%) — wide by construction, disclosed.
* Variance reduction: scrambled-Sobol RQMC vs crude MC ratio **3.6x**
  (n=4096, 15 replications).

## Liquidity driver (7th)

Calibrated CIR++ (Task 3 G-LIQ): kappa=0.9345/yr, long-run 63bp,
sigma=0.0213, lambda_l=2.00. Exposure notional 30000
(educational placeholder). Inner conditioning is ANALYTIC and
CIR-affine-exact; liquidity standalone SCR 63.3 — small under the
calibrated mean reversion (documented finding, not a wiring defect).

## Notes

* SEVENTH DRIVER = CIR++ liquidity/funding-spread premium with the Phase 21 Task 3 G-LIQ-calibrated parameters (kappa=0.9345/yr, long-run 63bp, sigma=0.0213, lambda_l=2.00); the EXPOSURE notional (30000) and 7x7 liquidity couplings are educational placeholders.
* Inner Q-nest liquidity conditioning is ANALYTIC and CIR-AFFINE-EXACT: haircut(l_H) = 1 - exp(-phi tau) A(tau) exp(-B(tau) x_H) under the Q-re-anchored long-run level; liability impact is baseline-centred, liq_l = notional (haircut(l_H) - haircut(l_0)).
* First six drivers and the five-driver CRN component liabilities are reproduced bit-for-bit from the Phase 21 Task 1 six-driver engine (liquidity shock drawn last; regression-tested).
* Var-covar (7x7 ESG) understates nested by 40.5%; copula (gaussian) reconciles within 14.6% (MR-010 refresh under seven drivers).
* Liquidity standalone SCR 63.3 is SMALL relative to rate 14486.3 / equity 15931.6: the calibrated mean reversion (half-life 0.74y) pulls the premium back over the 19y workout horizon, so 1-in-200 one-year liquidity translation risk on a hold-to-maturity book is modest — an honest, documented finding, not a wiring defect (the haircut mapping is verified affine-exact).
* MR-012 driver-omission residual is CLOSED at the aggregation level: all seven documented drivers (rate, equity, credit, lapse, mortality, fx, liquidity) now enter the correlated capital aggregation.

## Use restrictions

EDUCATIONAL ONLY — see report JSON `use_restrictions`.

*Standards: SOA ASOP 56 section 3.1.3/3.4/3.5; SOA ASOP 25 section 3.3; IA TAS M section 3.2/3.5/3.6; Solvency II Delegated Regulation Article 234 (aggregation); EIOPA volatility-adjustment methodology (illiquidity premium); Duffie-Singleton 1999; Brigo-Mercurio 2006; L'Ecuyer 2018 (RQMC)*
