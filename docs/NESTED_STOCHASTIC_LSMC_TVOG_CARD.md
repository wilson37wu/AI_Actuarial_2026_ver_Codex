# Model Limitation Card — Nested-Stochastic / LSMC TVOG Capital Proxy

**Module:** `par_model_v2/projection/nested_stochastic_tvog.py`
**Phase:** 14 (Production Residual Closure and Model Sophistication) — Task 6
**Classification:** EDUCATIONAL ONLY — NOT a regulatory capital model
**Governance status:** ChangeRecord at OWNER_REVIEW; production sign-off withheld pending independent APS X2 review.

---

## 1. Purpose

Adds a capital-metric layer on top of the Phase 4 `TVOGEngine`. The time value of
the guarantee is re-valued at a future *capital horizon* `H` (default 12 months,
a 1-year-VaR / SCR-style horizon) and its distribution across real-world (outer)
scenarios is converted into VaR / Expected-Shortfall / SCR-proxy figures.

Two engines plus a diagnostic harness are provided:

| Engine | Method | Inner cost | Role |
|---|---|---|---|
| `NestedStochasticTVOGEngine` | Outer real-world scenarios x fresh inner Q nest per node | `N_outer x n_inner` | Brute-force ground truth |
| `LSMCProxyEngine` | Longstaff-Schwartz polynomial surface `L_hat(x)` fitted to noisy single-path samples | `N_fit` | Cheap production-style proxy |
| `NestedStochasticDiagnostics` | Convergence, reproducibility, proxy-vs-nested agreement | — | Validation evidence |

## 2. Capital-metric definition

Let `L(x)` be the conditional Q-measure value, **as of horizon H**, of the residual
guaranteed cashflows conditioned on the outer short rate `x = r_H`. For a guarantee
an *increase* in value is the insurer's loss, so capital is the upper tail of
`L = L(r_H)`:

```
VaR_alpha = quantile_alpha(L)
ES_alpha  = E[L | L >= VaR_alpha]
SCR_proxy = VaR_alpha(L) - E[L]
```

## 3. Validation evidence (seed=42, term=10y, issue age 40M, SA 100,000)

| Metric | Nested (ground truth) | LSMC proxy |
|---|---|---|
| Mean liability @ H | 84,267 | 84,438 |
| VaR 99.5% | 104,201 | 102,931 |
| ES 99.5% | 105,648 | 104,658 |
| SCR proxy | 19,934 | 18,493 |
| Inner valuations | 128,000 | 1,000 |

- **Proxy-vs-nested agreement** on the state grid: R^2 = **0.9932**, max abs relative error = **2.47%**.
- **SCR proxy gap** (LSMC vs nested): **7.2%**.
- **Cost reduction:** **128x** fewer inner valuations.
- **Inner Monte-Carlo convergence** (standard error of `L(x)` vs inner paths):

| n_inner | 64 | 256 | 1024 | 4096 |
|---|---|---|---|---|
| standard error | 1644.521 | 750.329 | 358.783 | 174.642 |

  SE decays monotonically and roughly as `1/sqrt(n_inner)` (ASOP 56 §3.5): **True**.
- **Reproducibility:** identical seed -> bit-identical conditional liabilities (SHA-256 match): **True**.

> Note: `LSMCProxyResult.fit_r2` (in-sample, ~0.36) is intentionally low — it is the
> R^2 of the regression against *noisy single-path* samples, most of whose variance is
> irreducible inner MC noise. The relevant accuracy metric is the proxy's agreement with
> the **high-accuracy nested conditional expectation** (R^2 = 0.9932 above).

## 4. Model-use restrictions

- **Single risk driver.** The capital tail is driven by the short rate at the horizon
  only. Equity, lapse, credit-spread and FX risks are NOT in the tail; this is a
  one-factor educational proxy.
- **Placeholder parameters.** HW1F parameters are placeholders
  (`HullWhiteParams.is_placeholder`); capital magnitudes are illustrative, not calibrated.
- **LSMC extrapolation.** The polynomial surface `L_hat(x)` is valid only across the
  fitted state range `[min(fit_states), max(fit_states)]`. Extrapolation beyond it is
  unsupported and may be unstable at high polynomial degree.
- **Convergence requirements.** Inner SE decays ~`1/sqrt(n_inner)`; a 99.5% capital
  figure requires `N_outer >= 2000` (ASOP 56 §3.5). Diagnostics must be run and reviewed
  before any figure is cited.
- **No management actions.** No dynamic management actions, bonus reactions or asset
  rebalancing are modelled in the inner valuation.
- **Not a regulatory SCR.** Independent APS X2 review pending; production sign-off
  withheld. Use only for education, methodology demonstration and testing.

## 5. Standards alignment

SOA ASOP 56 §3.1.3 (stochastic model documentation), §3.5 (scenario adequacy &
convergence); SOA ASOP 25 §3.3 (scenario generation); IA TAS M §3.2 (market-consistent
valuation), §3.6 (model validation, convergence, reproducibility); IFoA MCEV
Principles §7 (TVOG methodology); Longstaff & Schwartz (2001) for the LSMC regression.

## 6. Tests

`tests/test_phase14_nested_stochastic_tvog.py` — 23 tests, all PASS. Covers vectorised
-vs-loop numerical identity, capital-metric algebra, nested & LSMC engine runs,
unbiasedness vs nested, inner SE decay, proxy-vs-nested grid agreement, seed
reproducibility, model-use-restrictions disclosure, and input validation.
