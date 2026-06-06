# FX / Currency Sixth-Driver Card -- G-FX

**Phase:** 21 - FX + Liquidity Drivers and Six/Seven-Driver Economic Capital (Task 1)

**Status:** EDUCATIONAL placeholder parameters; gate PASS. Production sign-off
withheld pending six-driver LSMC OOS validation (Task 2), liquidity driver (Task 3),
re-aggregation + tail diagnostics (Task 4), UI propagation (Task 5), credentialled
calibration, and independent (APS X2) review.

## Driver

Lognormal FX spot X(t) (base per foreign unit; educational HKD-per-USD book, X0 = 7.8).
Outer real-world paths use the P-measure drift; the Q measure uses the covered-interest-
parity drift (r_d - r_f). The sixth governed shock is Cholesky-correlated to the five
existing drivers through a 6x6 ESG matrix that embeds the governed 5x5 block unchanged.

## CIP-exact inner conditioning

The educational FX exposure is a foreign-currency asset leg. Under Q the deflated
translated foreign money-market account is a martingale (Phase 20 MART-FX-CIP):
E^Q[D_d(H+s) X(H+s) exp(r_f (H+s)) | X_H] = D_d(H) X_H exp(r_f H), so the inner
conditional PV given X_H is analytic and exact: fx_l = notional * (1 - X_H / X0)
(a translation loss when the foreign currency depreciates).

## G-FX gate (6/6 criteria)

| Criterion | Result | Evidence (truncated) |
| --- | --- | --- |
| FX-01-positive-spots | PASS | min_spot=6.172983 |
| FX-02-lognormal-moments | PASS | log_mean_emp=-0.0018; log_mean_theory=-0.0018; z_mean=0.0 |
| FX-03-pq-measure-separation | PASS | terminal_mean_P=8.19895; terminal_mean_Q=7.956634; ratio=1.030455 |
| FX-04-q-cip-martingale | PASS | check_id=MART-FX-CIP; estimate=7.800573; target=7.8 |
| FX-05-correlation-wiring | PASS | realised_rate_fx_corr=-0.15129; target=-0.15; tolerance=0.02 |
| FX-06-exposure-mapping | PASS | impact_at_initial_spot=0.0; monotone_decreasing_in_spot=True; loss_at_20pct_depreciation=6000.0 |

## Six-driver aggregation evidence (n_outer=160, n_inner=24, seed=42, 99.5% / 12m)

| Driver | Standalone SCR |
| --- | --- |
| rate | 14486.3 |
| equity | 15931.6 |
| credit | 4713.9 |
| lapse | 22538.9 |
| mortality | 387.2 |
| fx | 4286.4 |

* Var-covar (6x6 ESG): 28992.0 (understates nested by 40.5% -- MR-010 pattern)
* Copula (gaussian): 41232.0 (within 15.4% of nested -- MR-010/MR-012 mitigation)
* Nested benchmark: 48737.5
* Verdict: **PASS**

## Limitations / use restrictions

* FX parameters are educational placeholders (fx_vol, drift, couplings); NOT calibrated to credentialled market data.
* The FX exposure is a single translated foreign asset leg with an analytic CIP-exact conditional valuation; real books carry term-structured, optioned and partially hedged FX exposures.
* The lognormal FX process has no jumps, stochastic volatility or peg/de-peg regime dynamics; a pegged currency (e.g. HKD) is materially regime-driven, so the tail is stylised, not historical.
* The first five drivers' inner Q nest remains the governed HW1F nest conditioned at the realised G2++ r_H (Phase 20 residual).
* Six-driver LSMC proxy-surface validation is Phase 21 Task 2; until it reports, the nested benchmark is the only validated 6D ground truth.
* Not for production capital, pricing, or regulatory reporting.

## Standards

* SOA ASOP 56 section 3.1.3
* SOA ASOP 56 section 3.4/3.5
* IA TAS M section 3.5/3.6
* Solvency II Delegated Regulation Article 188 (currency risk)
* Solvency II Delegated Regulation Article 234
* Brigo-Mercurio 2006
