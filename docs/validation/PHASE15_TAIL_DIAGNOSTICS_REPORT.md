# Phase 15 Task 4 — Tail-Convergence & Stability Diagnostics

**Verdict:** PASS - 99.5% capital metric converges, is bounded by a bootstrap CI, and benefits from variance reduction

Run `md-tail-7a52688d` | 25.3 s | digest `03398506b8c6`

## 1. Outer-count convergence (99.5% VaR / ES)

| N_outer | VaR | ES | ΔVaR (rel) |
|--------:|----:|---:|-----------:|
| 1,000 | 149,974.4 | 153,476.4 | — |
| 2,000 | 149,101.0 | 155,621.3 | 0.582% |
| 4,000 | 149,615.9 | 155,356.5 | 0.345% |

Converged: **True** (tol 2.00%); recommended N_outer ≥ **2,000**.

## 2. Bootstrap 95% CI (N_outer=2,500, B=1,500)

- VaR 150,632.2  CI [149,402.1, 154,390.5]  SE 1,486.3  (±1.66% of point)
- ES  155,454.7  CI [152,499.9, 157,861.4]  SE 1,382.4

## 3. Variance reduction (VaR estimator, 60 reps × N=4,096, copula ρ=-0.100)

| Scheme | VaR estimator SD | Variance-reduction ratio |
|--------|-----------------:|-------------------------:|
| Crude (pseudo-random) | 1,096.08 | 1.00× |
| Antithetic | 1,216.31 | 0.81× |
| Sobol QMC | 411.26 | 7.10× |

## Notes

- Outer-count convergence and the bootstrap CI use the GOVERNED outer states (ScenarioSet.generate) with the once-fitted LSMC surface; they isolate outer Monte-Carlo (sampling) error, not proxy error.
- Proxy error is bounded separately by the Task 1 proxy-vs-nested (R^2=0.9936) and Task 2 out-of-sample reports.
- The variance-reduction study uses a pilot-anchored Gaussian copula (governed ESG rho; empirical pilot margins) so crude / antithetic / Sobol target an identical distribution and the ratio is like-for-like.
- Antithetic uses negated normal pairs; Sobol uses a scrambled base-2 sequence (n is a power of two for exact balance).
- Antithetic variates do not reduce the 99.5% VaR-estimator variance (ratio 0.81<1) — expected for an extreme quantile; QMC is the effective scheme here (ratio 7.10).
