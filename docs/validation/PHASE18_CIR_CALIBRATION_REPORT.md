# Phase 18 Task 2 — CIR++ Credit-Spread Calibration Report (MR-012)
## CNY AA+ Corporate OAS — Educational-Proxy Credit-Market Data

**Run:** 2026-06-05 09:16:33 UTC
**Gate:** G-CR ✅ **PASS**
**ChangeRecord:** `14fce4d6b97a4f54889a07ac2b6fc043` — **APPROVED** (assumption_change; MR-012)
**Risk MR-012:** **MITIGATED**

> **PRODUCTION USE RESTRICTION.** Calibration uses an educational-proxy fixture, a
> single-path CIR OLS estimator, and an automation-driven three-stage sign-off. Replace
> with credentialled live extracts (ChinaBond / Wind / Markit), use a full
> maximum-likelihood / Kalman estimator with standard errors, and obtain a genuine
> Assumption Owner + independent APS X2 review before production pricing or capital use.

## 1. Summary

The CIR++ credit-spread placeholders (kappa=0.30, long_run=0.015, sigma=0.05, lambda=0.10)
were replaced with values calibrated from 240 months of educational-proxy CNY AA+ corporate
OAS history. The mean-reversion speed and long-run spread come from the homoscedastic CIR
OLS transition regression, the spread vol from its residual variance, and the market price of
credit risk from a documented risk-neutral long-run anchor. This is the third economic risk
driver in the nested/LSMC capital proxy (rate + equity + credit), so the calibration feeds the
three-driver 99.5% VaR/ES and the credit standalone capital.

## 2. Calibration Results (CNY)

| Parameter | Value |
|-----------|-------|
| Calibration date | 2026-01-01 |
| Monthly observations | 240 |
| Mean-reversion speed `kappa` | 0.5028 /yr |
| P-measure long-run spread `s_inf^P` | 0.0111 (111 bp) |
| Spread vol `sigma_s` | 0.0371 |
| Market price of credit risk `lambda_s` | 1.0575 |
| CIR++ shift `phi` | 0.0030 (30 bp) |
| Initial spread `s(0)` | 0.0109 (109 bp) |
| Risk-neutral long-run anchor `s_inf^Q` | 0.0140 |
| Feller condition `2 kappa b / sigma^2` | holds |
| CIR-regression fit R² (diagnostic) | 0.0245 |
| Parameter status | ✅ calibrated |

**G-CR criteria**

| Criterion | Pass |
|-----------|------|
| c1_min_obs | ✅ |
| c2_kappa_in_band | ✅ |
| c3_long_run_in_band | ✅ |
| c4_sigma_in_band | ✅ |
| c5_lambda_in_band | ✅ |
| c6_not_placeholder_with_audit | ✅ |

> The CIR-regression R² is intentionally low: on a near-equilibrium monthly path the
> increment ``dx`` is dominated by diffusion noise, so a low R² is expected and is NOT a
> validation metric. The recovered long-run level (sample-mean robust) and spread vol
> (residual-variance robust) are the credible estimates; ``kappa`` is the noisier slope.

**Data Lineage**

| Field | Value |
|-------|-------|
| Lineage ID | `LINCR_CNY_20260101` |
| Source type | educational_historical_proxy |
| Fixture version | 1.0.0 |
| Approved by | ModelGovernance_Phase18 |
| SHA-256 | `f63fe078eaa80dda76c1691e465834e5...` |

## 3. Calibration Gate Status

| Gate | Status | Evidence |
|------|--------|----------|
| G-CR | ✅ PASS | CNY: n=240, kappa=0.5028, long_run=0.0111 (111bp), sigma=0.0371, lambda=1.0575 |

## 4. Governance

ChangeRecord `14fce4d6b97a4f54889a07ac2b6fc043` (assumption_change) logged to the GovernanceStore and driven
DRAFT → PEER_REVIEW → OWNER_REVIEW → **APPROVED**, with one PARAM_CHANGE audit entry
(1 total). Risk-register entry **MR-012** moved to **MITIGATED**. This operationally
demonstrates the IA TAS M §3.5/§3.7 change-control workflow on the credit-spread assumption set.

**Standards addressed:** SOA ASOP 56 §3.4 (calibration documentation); SOA ASOP 25 §3.3
(credibility / historical estimation); IA TAS M §3.5/§3.6/§3.7; IFoA APS X2 §4.2.

## 5. Limitations and Next Steps

1. **Educational-proxy data.** The fixture approximates published ChinaBond/Wind AA+ OAS
   levels via a deterministic seeded CIR synthesis; it is reproducible but is not a
   credentialled vendor feed.
2. **Single-path OLS.** ``kappa`` from a single 20-year monthly path has wide sampling
   error; a production estimator should use maximum likelihood / Kalman filtering with
   standard errors and a multi-name / rating-segmented panel.
3. **Risk premium from a single anchor.** ``lambda_s`` is backed out from one documented
   risk-neutral long-run spread; a production calibration should use a term structure of
   CDS / bond-implied spreads.
4. **Residual MR-012.** Calibrating the credit driver moves MR-012 to MITIGATED but does
   not close it: the trivariate proxy still omits material drivers (lapse, mortality/longevity,
   FX, liquidity) and awaits an independent APS X2 review. Phase 18 Task 3 adds the
   dynamic-lapse driver.
