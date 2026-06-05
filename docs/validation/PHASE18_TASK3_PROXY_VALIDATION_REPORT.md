# Phase 18 Task 3 — Four-Driver (rate+equity+credit+lapse) OOS Proxy Validation
**Verdict:** PASS — selected basis (deg 1, max_int 3) validated OOS (R^2=0.9638, VaR rel err=2.33%, leakage-free, overfit gap=0.0057)
**Run:** `fd-proxyval-5b3107a4`  ·  digest `12167cf6fd22`  ·  elapsed 19.9s

## What this validates
Out-of-sample skill of the Phase 18 Task 3 **quadrivariate** LSMC capital surface `L_hat(r,S,s,b)` — short rate, equity level, credit spread, and the **non-financial lapse-behaviour index** `b` — against high-accuracy nested ground truth on an independent disjoint-seed hold-out, with the basis `(degree, max_interaction_order)` selected by OOS error. The lapse driver is the **first non-financial** proxy driver, closing the documented lapse limitation of the Phase 17 three-driver proxy.

## Drivers
`short_rate, equity_level, credit_spread, lapse_behaviour`

## Configuration
- N_fit (single-inner) = 500; N_validation (heavy hold-out) = 60; n_inner_heavy = 384
- in-sample heavy subset = 40; fit_seed = 42; validation_seed = 20260605 (disjoint)
- basis grid = [[1, 3], [2, 3], [3, 2], [3, 3], [4, 3]]; selection metric = oos_rmse; confidence = 0.995; horizon = 12 months

## Selected basis & headline metrics
| metric | value |
|---|---|
| selected (degree, max_interaction_order) | (1, 3) |
| basis terms | 5 |
| OOS R² | 0.9638 |
| OOS RMSE | 6255.1 |
| OOS max abs rel error | 0.156 |
| in-sample (heavy) R² | 0.9694 |
| overfit gap (in−OOS) | 0.0057 |
| overfit onset (terms) | 15 |

## Capital comparison (proxy vs nested, 99.5%)
| metric | proxy | nested | rel error |
|---|---|---|---|
| VaR | 213322 | 218410 | 2.33% |
| ES  | 217060 | 226143 | 4.02% |
| SCR | 94237 | 100757 | 6.47% |
- nested benchmark: N_outer = 500, n_inner = 96

## Leakage diagnostics
- seeds disjoint: True; exact shared states: 0; min scaled pairwise distance: 0.1995; leakage-free: **True**

## Basis sweep (overfit signature)
| degree | max_int | terms | in-sample(heavy) R² | OOS R² | OOS RMSE | overfit gap |
|---|---|---|---|---|---|---|
| 1 | 3 | 5 | 0.9694 | 0.9638 | 6255.1 | 0.0057 |
| 2 | 3 | 15 | 0.9532 | 0.9075 | 9995.9 | 0.0457 |
| 3 | 2 | 31 | 0.9036 | 0.8721 | 11751.3 | 0.0315 |
| 3 | 3 | 35 | 0.8426 | 0.8775 | 11498.9 | -0.0349 |
| 4 | 3 | 57 | 0.7540 | 0.7155 | 17525.2 | 0.0384 |

The OOS R² **declines** as the basis grows (textbook overfit), so model selection picks the lean linear-in-standardised-driver basis. The lapse axis being non-financial / orthogonal means most of its effect is captured at low order.

## Standards
SOA ASOP 7 §3.3; SOA ASOP 56 §3.5; SOA ASOP 56 §3.1.3; SOA ASOP 25 §3.3; IA TAS M §3.6; IA TAS M §3.2; IFoA proxy-modelling working party; Longstaff & Schwartz (2001); Duffie & Singleton (1999); Cox-Ingersoll-Ross (1985)

## Model-use restrictions
EDUCATIONAL ONLY. Four risk drivers; mortality-trend and FX still NOT in the tail. Lapse is a single systemic OU behavioural index (no product/cohort structure); the behavioural `kappa_b`/`sigma_b` are illustrative placeholders, NOT fitted to a lapse-experience time series. The quadrivariate polynomial surface is valid only across the fitted 4-D interquartile state region; extrapolation is unsupported. Not a regulatory SCR. Independent APS X2 review pending; production sign-off withheld.
