# CIR++ Credit-Spread Calibration Card (Phase 18 Task 2)

**Status:** EDUCATIONAL — calibrated to an educational-proxy fixture; production
sign-off withheld. **Risk:** MR-012 → **MITIGATED** (not closed).
**Gate:** G-CR **PASS**. **ChangeRecord:** assumption_change, **APPROVED**
(automation-driven three-stage sign-off).

## What this calibration does

Replaces the CIR++ credit-spread placeholders in `CreditSpreadParams`
(`par_model_v2/stochastic/credit_spread.py`) with values estimated from a
documented CNY AA+ corporate OAS history. The credit spread is the **third**
economic risk driver in the nested / LSMC economic-capital proxy
(rate + equity + credit), so these parameters feed the three-driver 99.5%
VaR / ES, the SCR-proxy, and the reduced-form hazard×LGD credit-loss component
on spread-sensitive backing assets.

| Parameter | Placeholder | Calibrated | Source |
|-----------|-------------|------------|--------|
| `mean_reversion_speed` (kappa) | 0.30 | ~0.50 /yr | CIR OLS transition-regression slope |
| `long_run_spread_p` (s∞ᴾ) | 0.015 | ~0.011 (111 bp) | CIR OLS intercept/slope (≈ sample mean) |
| `spread_vol` (sigma) | 0.05 | ~0.037 | residual variance / dt |
| `market_price_of_credit_risk` (lambda) | 0.10 | ~1.06 | documented risk-neutral anchor, CIR risk-premium relation |

## Methodology (SOA ASOP 56 §3.4)

The square-root factor `x = s − phi` follows `dx = kappa(b − x)dt + sigma√x dW`.
Calibration uses the textbook homoscedastic CIR OLS regression (Kladivko 2007;
Brigo–Mercurio 2006): normalising the Euler increment by `√x_{t−1}` gives a
two-regressor linear model whose coefficients recover `kappa = −beta2` and
`b = beta1/kappa`; `sigma² = Var(residuals)/dt`. The market price of credit
risk is backed out of a documented risk-neutral long-run anchor `s∞^Q` via
`s∞^Q − s∞ᴾ = lambda · sigma²/kappa`, clamped to `[0, risk_premium_upper]`.

## Components

- `par_model_v2/calibration/cir_calibrator.py` — `CIRCalibrator`, inputs/result.
- `par_model_v2/calibration/credit_market_data_source.py` — fixture source,
  loader, deterministic CIR synthesis, plausibility-band gate (G-CR).
- `par_model_v2/calibration/phase18_cir_calibration.py` — pipeline + governance.
- `par_model_v2/calibration/fixtures/cny_credit_spread_history_20260101.json` —
  documented-target educational-proxy fixture.
- `scripts/build_phase18_task2_calibration.py` — idempotent governance/report build.
- `tests/test_phase18_cir_calibration.py` — 14 tests.
- `docs/validation/PHASE18_CIR_CALIBRATION_REPORT.{md,json}` — run evidence.

## Limitations / model-use restrictions

1. **Educational-proxy data.** Deterministic seeded CIR synthesis approximating
   ChinaBond / Wind AA+ OAS levels; not a credentialled vendor feed.
2. **Single-path OLS.** `kappa` from one 20-year monthly path has wide sampling
   error (the CIR-regression R² is low by construction — `dx` is diffusion-
   dominated near equilibrium; this is **not** a validation metric). A production
   estimator needs maximum likelihood / Kalman filtering with standard errors and
   a rating-segmented panel.
3. **Single risk-premium anchor.** `lambda` is derived from one risk-neutral
   long-run spread; production work needs a CDS / bond-implied term structure.
4. **Residual MR-012.** The trivariate proxy still omits material drivers
   (lapse, mortality / longevity trend, FX, liquidity) and awaits an independent
   APS X2 review. Calibrating credit **mitigates** but does **not** close MR-012.

**Standards:** SOA ASOP 56 §3.4; SOA ASOP 25 §3.3; IA TAS M §3.5/§3.6/§3.7;
IFoA APS X2 §4.2. **Refs:** Cox–Ingersoll–Ross (1985); Brigo–Mercurio (2006);
Kladivko (2007); Duffie–Singleton (1999).
