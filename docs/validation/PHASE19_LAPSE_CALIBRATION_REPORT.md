# Phase 19 Task 5 — Lapse Behavioural-Index Calibration Report (MR-003 / MR-011)
## HK PAR Actual/Expected Lapse Experience — Educational-Proxy Data

**Run:** 2026-06-06 00:17:39 UTC
**Gate:** G-LAPSE ✅ **PASS**
**ChangeRecord:** `9dbd97f031f7412f941ca07793e2d3be` — **APPROVED** (assumption_change; MR-003 / MR-011)
**Risk MR-003:** **MITIGATED**  **Risk MR-011:** **MITIGATED**

> **PRODUCTION USE RESTRICTION.** Calibration uses an educational-proxy A/E fixture, a
> single-path OU AR(1) OLS estimator, and an automation-driven three-stage sign-off. Replace
> with a credentialled actual-vs-expected persistency study (cohort/duration-segmented,
> exposure-weighted, with standard errors), use an exposure-weighted / maximum-likelihood
> estimator, and obtain a genuine Assumption Owner + independent APS X2 review before
> production pricing or capital use.

## 1. Summary

The OU lapse behavioural-index placeholders (kappa_b=0.40, sigma_b=0.30) were replaced with
values calibrated from 240 months of educational-proxy HK PAR actual-to-expected (A/E) lapse
experience. The mean-reversion speed and long-run level come from the OU AR(1) transition
regression on log(A/E), and the behaviour vol from its residual variance via the OU stationary
relation. The behavioural index is the *level* uncertainty of policyholder behaviour — the
fourth (first non-financial) driver in the nested/LSMC capital proxy — so the calibration feeds
the five-driver 99.5% VaR/ES and the lapse standalone capital.

## 2. Calibration Results (HK_PAR)

| Parameter | Value |
|-----------|-------|
| Calibration date | 2026-01-01 |
| Monthly observations | 240 |
| Mean-reversion speed `kappa_b` | 0.7854 /yr |
| Half-life `ln2/kappa_b` | 0.88 yr |
| P-measure long-run level `theta_b` | -0.0360 (A/E 0.965) |
| Behaviour vol `sigma_b` | 0.1781 |
| Stationary std `sigma_b/sqrt(2 kappa_b)` | 0.1421 |
| 1-sd A/E multiplier `exp(±stat.std)` | [0.868, 1.153] |
| Capital `b(0)` | 0.0000 |
| AR(1) regression fit R² (diagnostic) | 0.8783 |
| Parameter status | ✅ calibrated |

**G-LAPSE criteria**

| Criterion | Pass |
|-----------|------|
| c1_min_obs | ✅ |
| c2_kappa_in_band | ✅ |
| c3_long_run_in_band | ✅ |
| c4_sigma_in_band | ✅ |
| c5_stationary_std_in_band | ✅ |
| c6_not_placeholder_with_audit | ✅ |

> The AR(1) regression R² reflects the persistence of the monthly A/E series; the recovered
> long-run level (sample-mean robust) and behaviour vol (residual-variance robust) are the
> credible estimates, while ``kappa_b`` is the noisier slope on a single path. A low or
> moderate R² is expected and is NOT a validation metric.

**Data Lineage**

| Field | Value |
|-------|-------|
| Lineage ID | `LINLAPSE_HK_PAR_20260101` |
| Source type | educational_historical_proxy |
| Fixture version | 1.0.0 |
| Approved by | ModelGovernance_Phase19 |
| SHA-256 | `55ba9cdad9acddf59827fff8777bc2df...` |

## 3. Calibration Gate Status

| Gate | Status | Evidence |
|------|--------|----------|
| G-LAPSE | ✅ PASS | HK_PAR: n=240, kappa=0.7854 (half-life 0.9yr), long_run_level=-0.0360 (A/E 0.965), sigma=0.1781, stationary_std=0.1421 |

## 4. Governance

ChangeRecord `9dbd97f031f7412f941ca07793e2d3be` (assumption_change) logged to the GovernanceStore and driven
DRAFT → PEER_REVIEW → OWNER_REVIEW → **APPROVED**, with one PARAM_CHANGE audit entry
(1 total). Risk-register entries **MR-003** moved to **MITIGATED** and **MR-011** moved to
**MITIGATED**. This operationally demonstrates the IA TAS M §3.5/§3.7 change-control workflow on
the lapse-behaviour assumption set.

**Standards addressed:** SOA ASOP 7 §3.3 (policyholder behaviour); SOA ASOP 56 §3.4
(calibration documentation); SOA ASOP 25 §3.3 (credibility / historical estimation);
IA TAS M §3.5/§3.6/§3.7; IFoA APS X2 §4.2.

## 5. Limitations and Next Steps

1. **Educational-proxy data.** The fixture approximates published HK PAR persistency-study A/E
   dispersion via a deterministic seeded OU synthesis; it is reproducible but is not a
   credentialled experience-study extract.
2. **Single-path OLS, no exposure weighting.** ``kappa_b`` from a single 20-year monthly path
   has wide sampling error; a production estimator should use an exposure-weighted /
   maximum-likelihood estimator with standard errors and a cohort/duration-segmented panel.
3. **Single systemic level factor.** The behavioural index is one systemic lapse-level factor
   with no product / cohort structure and no dependence on the rate-driven dynamic-lapse
   function (kept deliberately orthogonal).
4. **Residual MR-003 / MR-011.** Calibrating the lapse driver moves MR-003 and MR-011 to
   MITIGATED but does not close them: the five-driver proxy still omits material drivers
   (FX, liquidity) and awaits an independent APS X2 review. **This completes Phase 19.**
