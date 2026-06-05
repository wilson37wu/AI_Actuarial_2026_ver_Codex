# Phase 17 Task 4 — Three-Driver Tail-Convergence & Stability Diagnostics

**Drivers:** short_rate, equity_level, credit_spread

**Verdict:** PASS - three-driver 99.5% capital metric converges, is bounded by a bootstrap CI, and benefits from variance reduction

Run `td3-tail-01b2bb43` | 12.45 s | digest `aca7800a921a`

## 1. Outer-count convergence (99.5% VaR / ES)

| N_outer | VaR | ES | ΔVaR (rel) |
|--------:|----:|---:|-----------:|
| 500 | 149,782.5 | 150,253.5 | — |
| 1,000 | 150,265.3 | 156,377.9 | 0.322% |
| 2,000 | 149,885.4 | 152,954.5 | 0.253% |
| 3,000 | 152,296.8 | 155,757.2 | 1.609% |

Converged: **True** (tol 2.00%); recommended N_outer ≥ **1,000**.

## 2. Bootstrap 95% CI (N_outer=3,000, B=1,200)

- VaR 150,859.1  CI [149,634.1, 152,369.3]  SE 692.4  (±0.91% of point)
- ES  154,241.5  CI [152,023.0, 156,636.7]  SE 1,163.7

## 3. Variance reduction (VaR estimator, 80 reps × N=2,048)

Copula correlation (realised 3x3 outer-state, rate/equity/credit): ((1.0, -0.085935, -0.219415), (-0.085935, 1.0, -0.278116), (-0.219415, -0.278116, 1.0))

| Scheme | VaR estimator SD | Variance-reduction ratio |
|--------|-----------------:|-------------------------:|
| Crude (pseudo-random) | 1,231.40 | 1.00× |
| Antithetic | 1,307.44 | 0.89× |
| Sobol QMC | 741.34 | 2.76× |

## Notes

- Three-driver (rate+equity+credit) extension of the Phase 15 Task 4 two-driver tail diagnostics; built on the Phase 17 Task 1 trivariate LSMC surface (no Task 1/2/3 module modified).
- Outer-count convergence and the bootstrap CI use the GOVERNED 3-factor correlated outer states (_outer_states_3d) with the once-fitted LSMC surface; they isolate outer Monte-Carlo (sampling) error, not proxy error.
- Proxy error is bounded separately by the Phase 17 Task 1 proxy-vs-nested (R^2=0.964) and Task 2 out-of-sample (OOS R^2=0.9751) reports.
- The variance-reduction study uses a pilot-anchored Gaussian copula whose controlling correlation is the realised 3x3 outer-state correlation (rate/equity/credit) and whose margins are the empirical pilot margins, so crude / antithetic / Sobol target an identical distribution and the ratio is like-for-like.
- Antithetic uses negated normal triples; Sobol uses a scrambled base-2 sequence in 3 dimensions (n is a power of two for exact balance).
- Antithetic variates do not reduce the 99.5% VaR-estimator variance (ratio 0.89<1) - expected for an extreme quantile; QMC is the effective scheme here (ratio 2.76).
