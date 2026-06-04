# Phase 14 Task 4 — IA TAS M §3.6 Re-validation Report

**Model:** PAR Fund Stochastic ALM & TVOG (educational) — **Version:** v1.0.0-dev (post Phase 14 Task 3)
**Generated:** 2026-06-04T13:27:04.938507+00:00
**Evidence source:** embedded Phase 13 Task 4 snapshot (2026-06-04) + Phase 13 Task 5 OOS backtest (in-process re-run) + rolling HW1F calibration

## G-06 Gate Verdict

**PASS** — 26/31 requirements PASS/WAIVED = 83.9% (threshold 80%); FAIL=0, PARTIAL=5, NOT_RUN=0.

## Phase 14 Stretch Target (>= 90% PASS)

**NOT MET** — actual 83.9%.

Stretch target of >= 90% PASS. Residual requirements require credentialled data feeds (sub-annual CNY rates for VR-S05; daily P&L for VR-B03; historical PAR inforce experience for VR-B02) and an independent human APS X2 reviewer (VR-G03/G05) — the documented production-residual class, not a code gap.

| Outcome | Count |
|---|---|
| PASS | 26 |
| PARTIAL | 5 |
| NOT_RUN | 0 |
| FAIL | 0 |
| WAIVED | 0 |
| **Total** | **31** |

## Re-scored Requirements (Phase 14 Task 4)

| Req | Prior | Now | Evidence |
|---|---|---|---|
| VR-S05 | PARTIAL | PARTIAL | Rolling 5y windows (n=8): sigma_r stable & in [0.001,0.020]; mean-reversion alpha mean=0.692, CV=54% -> out... |
| VR-B01 | NOT_RUN | PASS | OOS coverage equity=100%/rate=100% (>=80%); n_obs=12 (2014-2025); Kupiec95=0.474; martingale_pass=True; rec... |
| VR-B02 | NOT_RUN | PARTIAL | Lapse A/E=100.1% vs calibrated dynamic-lapse (R^2=0.9999) on SYNTHETIC HK PAR experience; historical inforc... |
| VR-B03 | NOT_RUN | PARTIAL | Kupiec POF p95=0.474/p99=0.751 (>0.05 -> exception frequency binomially consistent with confidence level); ... |

## All Requirements

| Req | Category | Severity | Status |
|---|---|---|---|
| VR-U01 | Unit | Critical | PASS |
| VR-U02 | Unit | Critical | PASS |
| VR-U03 | Unit | High | PASS |
| VR-U04 | Unit | High | PASS |
| VR-U05 | Unit | Medium | PASS |
| VR-U06 | Unit | High | PASS |
| VR-U07 | Unit | Medium | PASS |
| VR-I01 | Integration | Critical | PASS |
| VR-I02 | Integration | Critical | PASS |
| VR-I03 | Integration | Medium | PASS |
| VR-I04 | Integration | High | PASS |
| VR-S01 | Stochastic | Critical | PASS |
| VR-S02 | Stochastic | Critical | PASS |
| VR-S03 | Stochastic | High | PASS |
| VR-S04 | Stochastic | Critical | PASS |
| VR-S05 | Stochastic | High | PARTIAL |
| VR-SE01 | Sensitivity | High | PASS |
| VR-SE02 | Sensitivity | Critical | PASS |
| VR-SE03 | Sensitivity | High | PASS |
| VR-SE04 | Sensitivity | Medium | PASS |
| VR-B01 | Backtest | High | PASS |
| VR-B02 | Backtest | Medium | PARTIAL |
| VR-B03 | Backtest | Medium | PARTIAL |
| VR-G01 | Governance | Critical | PASS |
| VR-G02 | Governance | High | PASS |
| VR-G03 | Governance | High | PARTIAL |
| VR-G04 | Governance | Medium | PASS |
| VR-G05 | Governance | Critical | PARTIAL |
| VR-D01 | Data | High | PASS |
| VR-D02 | Data | High | PASS |
| VR-D03 | Data | Medium | PASS |

## Residual Requirements & Closure Path

- **VR-S05 [PARTIAL]** — Rolling 5y windows (n=8): sigma_r stable & in [0.001,0.020]; mean-reversion alpha mean=0.692, CV=54% -> outside [0.02,0.30] and CV>20%: poorly identified from annual data (documented limitation; needs sub-annual credentialled rates).
- **VR-B02 [PARTIAL]** — Lapse A/E=100.1% vs calibrated dynamic-lapse (R^2=0.9999) on SYNTHETIC HK PAR experience; historical inforce data and mortality A/E unavailable in the educational dataset -> PARTIAL.
- **VR-B03 [PARTIAL]** — Kupiec POF p95=0.474/p99=0.751 (>0.05 -> exception frequency binomially consistent with confidence level); literal daily bands (4-6% / 0.5-1.5%) and >=250-day window not satisfiable with 12 annual educational-proxy obs.
- **VR-G03 [PARTIAL]** — APS X2 §3 requires sign-off by a reviewer independent of the model developer. The automated SignOffWorkflow is operational but an independent human reviewer is pending (Phase 13 Task 6, G-08/G-10).
- **VR-G05 [PARTIAL]** — Final production sign-off requires overall report PASS plus an independent validator; blocked until the Layer-5 backtests (Task 5) and APS X2 review (Task 6) close. Educational use is permitted in the interim.

## Governance

ChangeRecord `05f624242d144ba6bd06f5e4f3484777` (governance_change) logged, status **OWNER_REVIEW** (final APPROVED withheld pending independent APS X2 review — VR-G03).

---
*Educational model. A report whose overall status is not PASS must not be used for regulatory reporting, pricing, or external disclosure (IA TAS M §3.6).*