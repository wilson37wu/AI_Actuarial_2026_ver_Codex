# Sensitivity Analysis Report

**Report ID:** `598e35d0678d`  
**Generated:** 2026-05-23T02:19:56Z  
**Product:** PAR Endowment — 10y, SA=100,000, Age 35 M  
**Base TVOG:** 12,101.76  

---

## 1. Executive Summary

The largest TVOG sensitivity is to **r0 CBIRC cap 3%** (category: rate): delta TVOG = -7,608.48 (-62.9% of base).  

Key findings by category:

- **Rate**: max |delta| = 7,608.48; mean |Δ%| = 16.9%
- **Equity**: max |delta| = 0.00; mean |Δ%| = 0.0%
- **Liability**: max |delta| = 3,587.29; mean |Δ%| = 0.2%
- **Structure**: max |delta| = 55.41; mean |Δ%| = 0.3%

---

## 2. Shock Results

### 2.1. Interest-Rate Parameters (HW1F) — VR-SE01

| Shock | TVOG Base | TVOG Shocked | Δ TVOG | Δ% | Direction |
|-------|----------:|-------------:|-------:|---:|-----------|
| a +50% | 12,101.76 | 11,996.56 | -105.20 | -0.9% | DECREASE |
| a -50% | 12,101.76 | 12,156.37 | +54.61 | +0.5% | FLAT |
| sigma_r +50% | 12,101.76 | 11,854.44 | -247.32 | -2.0% | DECREASE |
| sigma_r -50% | 12,101.76 | 11,593.72 | -508.04 | -4.2% | DECREASE |
| r0 +25% | 12,101.76 | 8,232.88 | -3,868.88 | -32.0% | DECREASE |
| r0 CBIRC cap 3% | 12,101.76 | 4,493.28 | -7,608.48 | -62.9% | DECREASE |

### 2.2. Equity Parameters (GBM) — VR-SE02

| Shock | TVOG Base | TVOG Shocked | Δ TVOG | Δ% | Direction |
|-------|----------:|-------------:|-------:|---:|-----------|
| sigma_S +25% | 12,101.76 | 12,101.76 | +0.00 | +0.0% | FLAT |
| sigma_S -25% | 12,101.76 | 12,101.76 | +0.00 | +0.0% | FLAT |
| rho +0.15 | 12,101.76 | 12,101.76 | +0.00 | +0.0% | FLAT |
| rho -0.15 | 12,101.76 | 12,101.76 | +0.00 | +0.0% | FLAT |

### 2.3. Liability / Product Assumptions — VR-SE03

| Shock | TVOG Base | TVOG Shocked | Δ TVOG | Δ% | Direction |
|-------|----------:|-------------:|-------:|---:|-----------|
| lapse +25% | 12,101.76 | 12,101.76 | +0.00 | +0.0% | FLAT |
| lapse -25% | 12,101.76 | 12,101.76 | +0.00 | +0.0% | FLAT |
| qx +10% | 12,101.76 | 12,095.45 | -6.31 | -0.1% | FLAT |
| qx -10% | 12,101.76 | 12,108.07 | +6.31 | +0.1% | FLAT |
| det_rate +50bps | 12,101.76 | 15,513.61 | +3,411.85 | +28.2% | INCREASE |
| det_rate -50bps | 12,101.76 | 8,514.47 | -3,587.29 | -29.6% | DECREASE |

### 2.4. Model-Structure Shocks — VR-SE04

| Shock | TVOG Base | TVOG Shocked | Δ TVOG | Δ% | Direction |
|-------|----------:|-------------:|-------:|---:|-----------|
| n_scen 200 (stress) | 12,101.76 | 12,157.17 | +55.41 | +0.5% | FLAT |
| n_scen 1000 (convergence) | 12,101.76 | 12,115.77 | +14.01 | +0.1% | FLAT |

---

## 3. Tail Risk under Shocked Parameters

| Shock | P5 PV Guar | P95 PV Guar | P5–P95 Range |
|-------|----------:|------------:|-------------:|
| a +50% | 64,907.91 | 102,958.33 | 38,050.42 |
| a -50% | 60,170.79 | 108,170.86 | 48,000.06 |
| sigma_r +50% | 54,950.31 | 111,776.98 | 56,826.67 |
| sigma_r -50% | 71,723.75 | 93,743.97 | 22,020.21 |
| r0 +25% | 59,743.07 | 100,976.50 | 41,233.43 |
| r0 CBIRC cap 3% | 56,865.56 | 96,836.68 | 39,971.13 |
| sigma_S +25% | 62,768.28 | 104,931.80 | 42,163.52 |
| sigma_S -25% | 62,768.28 | 104,931.80 | 42,163.52 |
| rho +0.15 | 62,768.28 | 104,931.80 | 42,163.52 |
| rho -0.15 | 62,768.28 | 104,931.80 | 42,163.52 |
| lapse +25% | 62,768.28 | 104,931.80 | 42,163.52 |
| lapse -25% | 62,768.28 | 104,931.80 | 42,163.52 |
| qx +10% | 62,791.43 | 104,924.53 | 42,133.10 |
| qx -10% | 62,745.12 | 104,939.08 | 42,193.96 |
| det_rate +50bps | 62,768.28 | 104,931.80 | 42,163.52 |
| det_rate -50bps | 62,768.28 | 104,931.80 | 42,163.52 |
| n_scen 200 (stress) | 60,290.69 | 108,090.38 | 47,799.69 |
| n_scen 1000 (convergence) | 62,792.92 | 104,930.92 | 42,138.00 |

---

## 4. Key Risk Drivers

Parameters are ranked by |Δ TVOG| from largest to smallest:

| Rank | Parameter | |Δ TVOG| | Δ% |
|------|-----------|--------:|---:|
| 1 | r0 CBIRC cap 3% | 7,608.48 | -62.9% |
| 2 | r0 +25% | 3,868.88 | -32.0% |
| 3 | det_rate -50bps | 3,587.29 | -29.6% |
| 4 | det_rate +50bps | 3,411.85 | +28.2% |
| 5 | sigma_r -50% | 508.04 | -4.2% |
| 6 | sigma_r +50% | 247.32 | -2.0% |
| 7 | a +50% | 105.20 | -0.9% |
| 8 | n_scen 200 (stress) | 55.41 | +0.5% |
| 9 | a -50% | 54.61 | +0.5% |
| 10 | n_scen 1000 (convergence) | 14.01 | +0.1% |
| 11 | qx -10% | 6.31 | +0.1% |
| 12 | qx +10% | 6.31 | -0.1% |
| 13 | sigma_S +25% | 0.00 | +0.0% |
| 14 | sigma_S -25% | 0.00 | +0.0% |
| 15 | rho +0.15 | 0.00 | +0.0% |
| 16 | rho -0.15 | 0.00 | +0.0% |
| 17 | lapse +25% | 0.00 | +0.0% |
| 18 | lapse -25% | 0.00 | +0.0% |

---

## 5. Industry Standards Alignment

| Requirement | Reference | Status |
|-------------|-----------|--------|
| Rate parameter sensitivity (mean-reversion, vol, r0) | SOA ASOP 56 §3.5; IA VR-SE01 | IMPLEMENTED |
| Equity parameter sensitivity (sigma_S, correlation) | SOA ASOP 56 §3.5; IA VR-SE02 | IMPLEMENTED |
| Lapse and mortality assumption shocks | SOA ASOP 56 §3.6; IA VR-SE03 | IMPLEMENTED |
| Model structure sensitivity (scenario count) | SOA ASOP 56 §3.5; IA VR-SE04 | IMPLEMENTED |
| Tail risk under shocks (P5/P95) | ERM | IMPLEMENTED |
| Governance audit entries | IA TAS M §3.3 | IMPLEMENTED |

---

## 6. Limitations

- All runs use placeholder ESG parameters (not yet market-calibrated). Sensitivity magnitudes will change after Phase 4 calibration is finalised.
- Lapse and mortality shocks apply uniform multipliers across all policy years and ages. Dynamic / scenario-dependent assumption shocks are deferred to Phase 5.
- Scenario count shocks (VR-SE04) test numerical stability only; the 200-scenario run is below the ASOP 56 §3.5 minimum and must not be used for production reporting.

---

*Automated report generated by `SensitivityEngine`. Report ID: 598e35d0678d.*
