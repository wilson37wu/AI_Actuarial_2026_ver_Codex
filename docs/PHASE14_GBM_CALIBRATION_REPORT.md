# Phase 14 Task 2 — GBM Equity Calibration Report (G-03)
## CSI 300 (CNY) and Hang Seng (HK/China) — Educational-Proxy Market Data

**Run:** 2026-06-04 11:24:19 UTC
**Gate:** G-03 ✅ **PASS**
**ChangeRecord:** `25719549943a4ae2a04c1ddc36a156c9` — **APPROVED** (assumption_change; MR-002)
**Risk MR-002:** **MITIGATED**

> **PRODUCTION USE RESTRICTION.** Calibration uses educational-proxy fixtures and an
> automation-driven three-stage sign-off. Replace with credentialled live extracts
> (CSI / ChinaBond / Wind / HKMA / Bloomberg) and obtain a genuine Assumption Owner +
> independent APS X2 review before production pricing or capital use.

## 1. Summary

The GBM equity placeholders (sigma_S=0.22, ERP=0.045, dividend=0.025, rho=-0.15) were
replaced with values calibrated from ~10 years of daily CSI 300 (CNY) and Hang Seng
(HK/China) educational-proxy history. The calibrated ERP sits below the 4.5%
placeholder, removing the systematic investment-return overstatement flagged in
**MR-002**, and the rate-equity correlation is now a data-based negative figure.

## 2. Calibration Results

### CNY Results

| Parameter | Value |
|-----------|-------|
| Calibration date | 2026-01-01 |
| Daily observations | 2,609 |
| Equity vol `sigma_S` (blended) | 0.2158 (21.6% p.a.) |
| — historical vol | 0.2245 |
| — ATM implied vol | 0.2100 |
| Equity risk premium `ERP` | 0.0327 (3.27% p.a.) |
| Dividend yield `delta` (EWMA) | 0.0229 (2.29% p.a.) |
| Rate-equity correlation `rho` | -0.1965 |
| Parameter status | ✅ calibrated |

**G-03 criteria (CNY)**

| Criterion | Pass |
|-----------|------|
| c1_min_daily_obs | ✅ |
| c2_sigma_in_band | ✅ |
| c3_erp_documented | ✅ |
| c4_rho_in_band | ✅ |
| c5_not_placeholder | ✅ |
| c6_param_change_audit | ✅ |

**Data Lineage**

| Field | Value |
|-------|-------|
| Lineage ID | `LINEQ_CNY_20260101` |
| Source type | educational_historical_proxy |
| Fixture version | 1.0.0 |
| Approved by | ModelGovernance_Phase14 |
| SHA-256 | `32a11c268fbefa2e234d2002a06c1c50...` |


### HK Results

| Parameter | Value |
|-----------|-------|
| Calibration date | 2026-01-01 |
| Daily observations | 2,609 |
| Equity vol `sigma_S` (blended) | 0.2524 (25.2% p.a.) |
| — historical vol | 0.2709 |
| — ATM implied vol | 0.2400 |
| Equity risk premium `ERP` | 0.0171 (1.71% p.a.) |
| Dividend yield `delta` (EWMA) | 0.0326 (3.26% p.a.) |
| Rate-equity correlation `rho` | -0.1493 |
| Parameter status | ✅ calibrated |

**G-03 criteria (HK)**

| Criterion | Pass |
|-----------|------|
| c1_min_daily_obs | ✅ |
| c2_sigma_in_band | ✅ |
| c3_erp_documented | ✅ |
| c4_rho_in_band | ✅ |
| c5_not_placeholder | ✅ |
| c6_param_change_audit | ✅ |

**Data Lineage**

| Field | Value |
|-------|-------|
| Lineage ID | `LINEQ_HK_CN_20260101` |
| Source type | educational_historical_proxy |
| Fixture version | 1.0.0 |
| Approved by | ModelGovernance_Phase14 |
| SHA-256 | `aa9b23ef23b9c0265ab3f06a983cb3ca...` |


## 3. Production Gate Status

| Gate | Status | Evidence |
|------|--------|----------|
| G-03 | ✅ PASS | CNY: n=2609, sigma_S=0.2158, ERP=0.0327, div=0.0229, rho=-0.1965; HK: n=2609, sigma_S=0.2524, ERP=0.0171, div=0.0326, rho=-0.1493 |

## 4. Governance

ChangeRecord `25719549943a4ae2a04c1ddc36a156c9` (assumption_change) logged to the GovernanceStore and driven
DRAFT → PEER_REVIEW → OWNER_REVIEW → **APPROVED**, with one PARAM_CHANGE audit entry
per market (2 total). Risk-register entry **MR-002** moved to **MITIGATED**. This
operationally demonstrates the IA TAS M §3.5/§3.7 change-control workflow on the equity
assumption set.

**Standards addressed:** SOA ASOP 56 §3.4 (calibration documentation); SOA ASOP 25 §3.3
(credibility / historical estimation); IA TAS M §3.5/§3.6/§3.7; IFoA APS X2 §4.2.

## 5. Limitations and Next Steps

1. **Educational-proxy data.** Fixtures approximate published CSI/HSI/ChinaBond/HKMA
   levels; they are deterministic and reproducible (seeded synthesis) but are not a
   credentialled vendor feed.
2. **Implied vol is a single ATM point.** A full vol surface (smile/term structure) is
   out of scope; the blended sigma_S uses a 60/40 implied/historical weighting per
   methodology §6.2.
3. **ERP is single-market historical.** Cross-validation against survey ERP and a
   regime-aware estimator is a production residual.
4. **Next Phase 14 task:** Remediate MR-009 — migrate `examples/guided_examples.py` to
   the current RiskFreeCurve/FixedIncomeInstrument/TVOG APIs and bring
   `tests/test_guided_examples.py` green.
