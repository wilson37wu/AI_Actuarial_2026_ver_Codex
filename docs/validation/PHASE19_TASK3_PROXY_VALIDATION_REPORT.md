# Phase 19 Task 3 — Five-Driver Out-of-Sample Proxy-Validation Report

**Driver added:** mortality-trend (5th capital driver; 2nd non-financial) — closes the
documented Phase 18 four-driver limitation ("mortality-trend and FX risks are still NOT in
the tail").

**State vector:** `x = (r_H, S_H, s_H, b_H, m_H)` — short rate, equity level, credit spread,
lapse-behaviour index, **mortality-trend index**, at the 1-year capital horizon.

## Method

- **New driver** `par_model_v2/stochastic/mortality_trend.py` — mean-reverting OU
  mortality-trend index `m(t)` (exact AR(1) discretisation; non-financial ⇒ P = Q drift),
  horizon mortality multiplier `G = exp(m)` (lognormal; a single-systemic-factor analogue of
  the Lee-Carter time index). Defaults `kappa_m = 0.30/yr`, `sigma_m = 0.15` ⇒ stationary
  std ≈ 0.194.
- **Five-driver liability** `par_model_v2/projection/multi_driver_capital_5d.py` — the
  mortality multiplier `G(m_H)` scales the central annual `q_x` of the guaranteed death /
  maturity benefits (`MortalityExposureSpec`, default `theta = 1`). For a sum-assured
  endowment (death benefit = maturity benefit) the driver acts mainly through benefit
  **timing**, so it is a genuinely orthogonal SMALL driver. The 4×4 (rate/equity/credit/
  lapse) block is inherited; mortality is orthogonal by default in the governed 5×5 ESG
  correlation (configurable). Nested ground truth + quintivariate capped-interaction LSMC
  surface + diagnostics mirror the four-driver API.
- **OOS validation** `FiveDriverProxyValidator` — fit on `N_fit` single-inner-path states
  (seed 42), validate on an INDEPENDENT disjoint-seed hold-out (seed 20260606) against HEAVY
  nested truth (`n_inner_heavy` Q-paths/state); basis selection over a
  `(degree, max_interaction_order)` grid by OOS RMSE/R²; leakage + overfit diagnostics +
  honest verdict.

## Evidence (seed 42; n_fit=500 / n_val=60 / n_inner_heavy=384; nested 500×96)

**VERDICT: PASS** — selected basis (degree 1, max_interaction_order 3, 6 terms),
OOS R² = **0.9616**, VaR rel err **2.03 %** (ES 3.18 %, SCR 5.81 %) vs heavy nested truth,
leakage-free (0 shared states), overfit gap **0.0031**. Textbook overfit signature
(OOS R² 0.962 → 0.851 → 0.651 → 0.340 as the basis grows 6 → 21 → 56 → 91 terms; onset
21 terms). Reproducibility digest `f8a97423b85b`.

| basis (deg, max_int) | terms | OOS R² |
|----------------------|-------|--------|
| (1, 3)               | 6     | 0.962  |
| (2, 3)               | 21    | 0.851  |
| (3, 3)               | 56    | 0.651  |
| (4, 3)               | 91    | 0.340  |

Five-driver nested VaR99.5 ≈ 231,310 (cf. four-driver ≈ 230,388) — the mortality-trend
driver adds a small, monotone increment consistent with a benefit-timing effect on a
sum-assured endowment. The mortality multiplier is verified monotone: nested `L` at
`m = -0.3 / 0 / +0.3` = 138,515 / 138,762 / 139,091.

## Production-use restriction

EDUCATIONAL ONLY. Placeholder HW1F / GBM / CIR++ / OU-lapse / OU-mortality parameters; the
mortality-trend index is a single systemic level factor with no age / period / cohort
structure and no longevity-hedge asset. FX and liquidity risks remain outside the proxy.
Independent APS X2 review pending; production sign-off withheld.

**Standards:** SOA ASOP 7 §3.3; ASOP 25 §3.3; ASOP 56 §3.1.3/§3.5; IA TAS M §3.2/§3.6;
IFoA proxy-modelling working party; Lee & Carter (1992); Longstaff & Schwartz (2001);
Duffie & Singleton (1999); Cox-Ingersoll-Ross (1985).
