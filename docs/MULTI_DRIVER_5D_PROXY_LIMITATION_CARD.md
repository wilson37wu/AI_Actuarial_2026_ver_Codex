# Model-Limitation Card — Five-Driver Economic-Capital Proxy (Phase 19 Task 3)

**Module(s):** `par_model_v2/stochastic/mortality_trend.py`,
`par_model_v2/projection/multi_driver_capital_5d.py`,
`par_model_v2/projection/multi_driver_proxy_validation.py::FiveDriverProxyValidator`

**Classification:** EDUCATIONAL ONLY — NOT a regulatory capital model.

## Scope

A nested-stochastic / LSMC economic-capital proxy whose 99.5 % 1-year capital tail is driven
by **five** correlated drivers at the horizon: short rate `r_H`, equity level `S_H`, credit
spread `s_H`, the non-financial lapse-behaviour index `b_H`, and (new) the non-financial
**mortality-trend index** `m_H`. The mortality multiplier `G = exp(theta·m_H)` scales the
central mortality basis `q_x` of the guaranteed death / maturity benefits.

## What this closes

The documented Phase 18 four-driver limitation — "mortality-trend and FX risks are still NOT
in the tail" — is closed for the mortality-trend axis. The proxy now carries the IFoA
proxy-modelling working party's financial AND non-financial driver set bar FX / liquidity.

## Limitations & model-use restrictions

1. **Single systemic mortality factor.** One OU log-multiplier on `q_x`; no age / period /
   cohort (Lee-Carter / CBD) structure, no link to a longevity-hedge asset, no product /
   cohort segmentation.
2. **Small-driver caveat.** For a sum-assured endowment (death benefit = maturity benefit)
   the mortality driver acts mainly through benefit timing (discounting), so its marginal
   capital contribution is small and genuinely orthogonal — the LSMC surface assigns it a
   small coefficient and OOS R² stays dominated by rates/equity/credit/lapse. This is
   expected and honest, not a fit failure.
3. **Placeholder parameters.** `kappa_m / sigma_m` (and HW1F / GBM / CIR++ / OU-lapse) are
   illustrative, NOT calibrated to a mortality- or population-experience time series. Capital
   magnitudes are not calibrated.
4. **Surface validity region.** The quintivariate polynomial is valid only across the fitted
   5-D interquartile box; ≥3-way interactions are capped (default order 3); extrapolation is
   unsupported.
5. **Residual drivers.** FX and liquidity risks remain outside the proxy.
6. **No management actions.** No dynamic management actions, bonus reactions, asset
   rebalancing, or credit-asset trading in the inner valuation.
7. **Governance.** Independent APS X2 review pending; production sign-off withheld.

## Validation evidence

OOS proxy validation (disjoint-seed hold-out vs heavy nested truth): VERDICT PASS — selected
(deg 1, max_int 3, 6 terms), OOS R² 0.9616, VaR rel err 2.03 %, leakage-free, overfit gap
0.0031, textbook overfit signature (onset 21 terms). See
`docs/validation/PHASE19_TASK3_PROXY_VALIDATION_REPORT.{json,md}`.

**Standards:** SOA ASOP 7 §3.3; ASOP 25 §3.3; ASOP 56 §3.1.3/§3.4/§3.5; IA TAS M
§3.2/§3.5/§3.6; IFoA proxy-modelling WP; Lee & Carter (1992); Longstaff & Schwartz (2001).
