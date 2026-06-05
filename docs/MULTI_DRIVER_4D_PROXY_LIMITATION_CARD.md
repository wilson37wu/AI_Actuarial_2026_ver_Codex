# Model Limitation Card — Four-Driver (rate + equity + credit + lapse) Economic-Capital Proxy

**Status:** EDUCATIONAL ONLY — not a regulatory capital model. Production sign-off withheld; independent APS X2 review pending.
**Phase / cycle:** Phase 18 Task 3 (2026-06-05).
**Modules:** `par_model_v2/stochastic/lapse_behaviour.py`, `par_model_v2/projection/multi_driver_capital_4d.py`, `par_model_v2/projection/multi_driver_proxy_validation.py::FourDriverProxyValidator`.

## Scope
Generalises the Phase 17 three-driver (rate + equity + credit-spread) nested / LSMC capital proxy to a **fourth, non-financial driver** — a stochastic policyholder-behaviour (lapse-level) index `b`. The horizon lapse multiplier `M = exp(b)` scales the calibrated dynamic-lapse basis through an **in-force factor** on the policyholder-benefit components. The state is `x = (r_H, S_H, s_H, b_H)`.

This closes the documented LAPSE limitation of the Phase 17 proxy and is the recommended next step of the IFoA proxy-modelling working party (financial AND non-financial drivers).

## What was demonstrated this cycle
- A non-financial OU behavioural driver with exact-discretisation moments, `P = Q` drift (no traded hedge), and a lognormal multiplier `M = exp(b)`.
- A four-driver nested ground truth and a **quadrivariate** capped-interaction LSMC surface; the lapse driver is genuinely orthogonal to the financial drivers in the governed 4×4 ESG correlation (realised outer `corr(·, b) ≈ 0`).
- Disjoint-seed **out-of-sample** four-driver proxy validation: **VERDICT PASS** — selected lean basis (degree 1, max_int 3, 5 terms), OOS R² 0.9638, VaR rel err 2.33%, leakage-free (0 shared states), overfit gap 0.0057, textbook overfit signature (OOS R² 0.964 → 0.716 as the basis grows 5 → 57 terms; onset at 15 terms). Digest `12167cf6fd22`.

## Limitations (model-use restrictions)
1. **Residual drivers.** Mortality-trend, FX, and liquidity risks are still NOT in the tail. The proxy now spans rate + equity + credit + lapse only.
2. **Lapse model.** Single systemic OU behavioural index — no product / cohort structure, no mortality-trend interaction, no surrender-value path dependency. The in-force factor scales only the guaranteed + equity-guarantee benefit components; credit loss (asset side) is not in-force scaled.
3. **Placeholder calibration.** HW1F / GBM / CIR++ / OU-behaviour parameters are illustrative. The behavioural `kappa_b` / `sigma_b` are NOT fitted to a lapse-experience time series. The dynamic-lapse coupling uses a deliberately milder parameterisation than the pricing assumption (the capital driver applies the horizon short rate as a sustained market rate over the whole remaining term). Capital magnitudes are NOT calibrated.
4. **LSMC extrapolation.** The quadrivariate polynomial surface is valid only across the fitted 4-D interquartile state region. Higher-order (≥3-way) interaction terms are capped (default order 3). Extrapolation is unsupported.
5. **No management actions.** No dynamic management actions, bonus reactions, asset rebalancing, or credit-asset trading in the inner valuation.

## Residual / open items
| Item | Status | Owner action |
|---|---|---|
| MR-010 (factor vs realised loss-correlation understatement) | refresh for 4 drivers in Phase 18 Task 4 | risk |
| MR-012 (credit / multi-driver proxy is educational) | refresh for 4 drivers in Phase 18 Task 5 governance | governance |
| Behavioural-index calibration to lapse experience | pending credentialled data | calibration |
| Independent APS X2 review | pending | governance |
| Mortality-trend / FX / liquidity drivers | not yet in the proxy | model dev |

## Standards
SOA ASOP 7 §3.3 (behaviour basis); ASOP 56 §3.1.3/§3.4/§3.5; ASOP 25 §3.3; IA TAS M §3.2/§3.5/§3.6; IFoA proxy-modelling working party; Longstaff & Schwartz (2001); Duffie-Singleton (1999); CIR (1985).
