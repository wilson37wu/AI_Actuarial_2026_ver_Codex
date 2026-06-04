# Model Limitation Card — Two-Driver (Rates + Equity) Nested / LSMC Capital Proxy

**Module:** `par_model_v2/projection/multi_driver_capital.py`
**Phase:** 15 — Multi-Risk Economic Capital and Proxy-Model Validation (Task 1)
**Classification:** EDUCATIONAL ONLY — NOT a regulatory capital model
**Status:** OWNER_REVIEW — independent APS X2 review pending; production sign-off withheld
**Standards:** SOA ASOP 56 §3.1.3/§3.5; SOA ASOP 25 §3.3; IA TAS M §3.2/§3.6; IFoA MCEV Principles §7; Longstaff & Schwartz (2001)

## What this adds

Generalises the Phase 14 Task 6 single-factor (short-rate-only) nested / LSMC capital proxy to **two correlated risk drivers** — the short rate `r_H` and the equity level `S_H` at the capital horizon `H`. This directly closes the documented single-risk-driver limitation of Task 6 ("Equity, lapse, credit-spread, and FX risks are NOT in the tail").

The conditional, horizon-H Q-value of the residual guarantee now has two components valued on the **same** correlated inner (rate, equity) paths:

1. **Guaranteed benefits** (rate-driven) — residual death + maturity guaranteed cashflows discounted along the inner short-rate path. Recovers the Task 6 liability exactly when the equity guarantee is switched off.
2. **Equity-linked maturity guarantee** (rates + equity) — a GMMB / put-style guarantee `max(G − units·S_T, 0)` on the policyholder fund, discounted from `T` to `H`. Depends on both `r_H` (discounting + risk-neutral drift `μ^Q = r − q`) and `S_H` (moneyness).

The ESG `rate_equity_correlation` ρ is carried through **both** the outer projection and the inner Q nest via the same Cholesky construction used by `ScenarioSet.generate` (`z_S = ρ·z_r + √(1−ρ²)·z_indep`).

The Longstaff-Schwartz surface is now a **bivariate total-degree polynomial** `L̂(r, S) = Σ_{a+b≤degree} β_{a,b}·r_c^a·S_c^b` (per-dimension centred/scaled), with `(degree+1)(degree+2)/2` terms (6 at the default degree 2).

## Validation evidence (seed = 42, 10y / age 40M / SA 100k)

| Metric | Value |
|---|---|
| Proxy-vs-nested R² (5×5 state grid) | **0.9936** |
| Proxy-vs-nested max abs rel error | **2.67%** |
| Inner SE decay (64→256→1024→4096) | 3842 → 1698 → 843 → 426 (~1/√n) |
| Same-seed reproducibility | bit-identical (SHA-256 match) |
| Cost reduction (nested inner / LSMC inner) | 64× fewer inner valuations |
| 99.5% SCR-proxy, equity guarantee ON | 42,886 |
| 99.5% SCR-proxy, rate-only (guarantee OFF) | 21,242 |
| Equity-guarantee capital add-on (SCR-proxy) | **21,644** |

The non-zero equity-guarantee SCR add-on confirms the equity driver now contributes to the capital tail.

**Note on in-sample `fit_r2` (~0.20):** this is expected Longstaff-Schwartz behaviour. The regression targets are *single-inner-path* payoffs with large pathwise variance, so the in-sample R² against those noisy targets is low by construction. The meaningful validation metric is the proxy-vs-**nested** R² (0.9936), which confirms the fitted surface recovers the true conditional expectation.

## Limitations / model-use restrictions

- **Two risk drivers only.** Lapse, credit-spread, mortality-trend, and FX risks are still NOT in the tail.
- **Placeholder parameters.** HW1F and GBM parameters are illustrative; capital magnitudes are NOT calibrated.
- **No extrapolation.** The bivariate polynomial surface is valid only across the fitted 2-D state region (10–90 percentile box); extrapolation is unsupported and may be unstable at high degree.
- **Convergence required.** Inner SE decays ~1/√(n_inner); a 99.5% metric requires N_outer ≥ 2,000 (ASOP 56 §3.5). Proxy-vs-nested agreement must be reviewed before any figure is cited.
- **No management actions.** No dynamic management actions, bonus reactions, or asset rebalancing in the inner valuation.
- **Governance.** Independent APS X2 review pending; production sign-off withheld. Use only for education, methodology demonstration, and testing.

## Tests

`tests/test_phase15_multi_driver_capital.py` — 29 tests PASS (basis, guarantee spec, two-driver inner sensitivity, guarantee-off reduction, measure handling, reproducibility, nested engine, LSMC engine, proxy-vs-nested agreement, governance disclosure).
