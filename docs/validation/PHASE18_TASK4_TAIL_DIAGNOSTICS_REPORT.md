# Phase 18 Task 4 — Four-Driver Tail-Convergence & Stability Diagnostics

**Drivers:** short_rate, equity_level, credit_spread, lapse_behaviour

**Verdict:** PASS - four-driver 99.5% capital metric converges, is bounded by a bootstrap CI, and benefits from variance reduction

Run `td4-tail-5cfa68cb` | 35.44 s | digest `f5748053fc8d`

## 1. Outer-count convergence (99.5% VaR / ES)

| N_outer | VaR | ES | ΔVaR (rel) |
|--------:|----:|---:|-----------:|
| 1,000 | 229,712.7 | 245,323.0 | — |
| 2,000 | 237,528.3 | 252,233.0 | 3.402% |
| 4,000 | 232,664.7 | 244,690.1 | 2.048% |
| 8,000 | 226,450.0 | 242,871.2 | 2.671% |
| 16,000 | 230,387.7 | 245,703.7 | 1.739% |

Converged: **True** (tol 2.00%); recommended N_outer ≥ **16,000**.

## 2. Bootstrap 95% CI (N_outer=8,000, B=1,200)

- VaR 231,150.3  CI [226,371.4, 239,438.1]  SE 3,095.0  (±2.83% of point)
- ES  249,352.5  CI [242,025.1, 255,749.5]  SE 3,501.9

## 3. Variance reduction (VaR estimator, 80 reps × N=4,096)

Copula correlation (realised 4x4 outer-state, rate/equity/credit/lapse): ((1.0, -0.115355, -0.194429, -0.029223), (-0.115355, 1.0, -0.292827, -0.020397), (-0.194429, -0.292827, 1.0, 0.031795), (-0.029223, -0.020397, 0.031795, 1.0))

| Scheme | VaR estimator SD | Variance-reduction ratio |
|--------|-----------------:|-------------------------:|
| Crude (pseudo-random) | 3,076.19 | 1.00× |
| Antithetic | 3,619.31 | 0.72× |
| Sobol QMC | 1,697.52 | 3.28× |

## Notes

- Four-driver (rate+equity+credit+lapse) extension of the Phase 17 Task 4 three-driver tail diagnostics; built on the Phase 18 Task 3 quadrivariate LSMC surface (no two-/three-driver diagnostics class modified).
- The fourth driver is the NON-FINANCIAL OU lapse-behaviour index; it is orthogonal to the financial drivers in the governed 4x4 ESG matrix but its realised liability impact still co-moves in the tail (anti-selection).
- Outer-count convergence and the bootstrap CI use the GOVERNED 4-factor correlated outer states (_outer_states_4d) with the once-fitted LSMC surface; they isolate outer Monte-Carlo (sampling) error, not proxy error.
- Proxy error is bounded separately by the Phase 18 Task 3 four-driver out-of-sample validation (OOS R^2=0.9638) report.
- The variance-reduction study uses a pilot-anchored Gaussian copula whose controlling correlation is the realised 4x4 outer-state correlation (rate/equity/credit/lapse) and whose margins are the empirical pilot margins, so crude / antithetic / Sobol target an identical distribution and the ratio is like-for-like.
- Antithetic uses negated normal quadruples; Sobol uses a scrambled base-2 sequence in 4 dimensions (n is a power of two for exact balance).
- Antithetic variates do not reduce the 99.5% VaR-estimator variance (ratio 0.72<1) - expected for an extreme quantile; QMC is the effective scheme here (ratio 3.28).
