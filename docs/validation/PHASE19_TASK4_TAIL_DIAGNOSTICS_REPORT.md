# Phase 19 Task 4 — Five-Driver Tail-Convergence & Stability Diagnostics

**Drivers:** short_rate, equity_level, credit_spread, lapse_behaviour, mortality_trend

**Verdict:** PASS - five-driver 99.5% capital metric converges, is bounded by a bootstrap CI, and benefits from variance reduction

Run `td5-tail-0ed04f5c` | 30.26 s | digest `760664b82614`

## 1. Outer-count convergence (99.5% VaR / ES)

| N_outer | VaR | ES | ΔVaR (rel) |
|--------:|----:|---:|-----------:|
| 1,000 | 228,660.8 | 245,247.7 | — |
| 2,000 | 240,837.4 | 253,983.1 | 5.325% |
| 4,000 | 232,319.2 | 244,700.2 | 3.537% |
| 8,000 | 228,278.0 | 243,000.9 | 1.739% |
| 16,000 | 230,879.3 | 246,336.8 | 1.140% |

Converged: **True** (tol 2.00%); recommended N_outer ≥ **8,000**.

## 2. Bootstrap 95% CI (N_outer=8,000, B=1,200)

- VaR 232,210.9  CI [227,582.4, 241,861.3]  SE 3,103.6  (±3.07% of point)
- ES  250,090.8  CI [242,967.2, 255,989.5]  SE 3,317.6

## 3. Variance reduction (VaR estimator, 60 reps × N=2,048)

Copula correlation (realised 5x5 outer-state, rate/equity/credit/lapse/mortality): ((1.0, -0.1282, -0.181526, -0.005828, 0.01229), (-0.1282, 1.0, -0.283194, 0.034799, 0.024897), (-0.181526, -0.283194, 1.0, -0.024988, -0.015417), (-0.005828, 0.034799, -0.024988, 1.0, -0.012093), (0.01229, 0.024897, -0.015417, -0.012093, 1.0))

| Scheme | VaR estimator SD | Variance-reduction ratio |
|--------|-----------------:|-------------------------:|
| Crude (pseudo-random) | 4,907.88 | 1.00× |
| Antithetic | 5,569.53 | 0.78× |
| Sobol QMC | 2,240.70 | 4.80× |

## Notes

- Five-driver (rate+equity+credit+lapse+mortality) extension of the Phase 18 Task 4 four-driver tail diagnostics; built on the Phase 19 Task 3 quintivariate LSMC surface (no two-/three-/four-driver diagnostics class modified).
- The fifth driver is the SECOND NON-FINANCIAL axis -- an OU mortality-trend index m(t) (Lee-Carter-style single systemic time index); it is orthogonal to the financial drivers AND to lapse in the governed 5x5 ESG matrix, but its realised liability impact still perturbs the tail through benefit timing on the sum-assured endowment.
- Outer-count convergence and the bootstrap CI use the GOVERNED 5-factor correlated outer states (_outer_states_5d) with the once-fitted LSMC surface; they isolate outer Monte-Carlo (sampling) error, not proxy error.
- Proxy error is bounded separately by the Phase 19 Task 3 five-driver out-of-sample validation (OOS R^2=0.9616) report.
- The variance-reduction study uses a pilot-anchored Gaussian copula whose controlling correlation is the realised 5x5 outer-state correlation (rate/equity/credit/lapse/mortality) and whose margins are the empirical pilot margins, so crude / antithetic / Sobol target an identical distribution and the ratio is like-for-like.
- Antithetic uses negated normal quintuples; Sobol uses a scrambled base-2 sequence in 5 dimensions (n is a power of two for exact balance).
- Antithetic variates do not reduce the 99.5% VaR-estimator variance (ratio 0.78<1) - expected for an extreme quantile; QMC is the effective scheme here (ratio 4.80).
