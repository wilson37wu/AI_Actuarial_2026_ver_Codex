# Phase 13 Task 4 — IA TAS M §3.6 Validation Report

**Model:** PAR Fund Stochastic ALM & TVOG (educational) — **Version:** v1.0.0-dev (post Phase 13 Task 3)
**Generated:** 2026-06-04T07:43:13.532434+00:00
**Evidence source:** embedded Phase 13 Task 4 snapshot (2026-06-04)

## G-06 Gate Verdict

**PASS** — 25/31 requirements PASS/WAIVED = 80.6% (threshold 80%); FAIL=0, PARTIAL=3, NOT_RUN=3.

| Outcome | Count |
|---|---|
| PASS | 25 |
| PARTIAL | 3 |
| NOT_RUN | 3 |
| FAIL | 0 |
| WAIVED | 0 |
| **Total** | **31** |

Overall report status: **PARTIAL** (PARTIAL expected while Tasks 5 & 6 are open).

## Per-Requirement Results

| Req | Category | Severity | Status | Evidence |
|---|---|---|---|---|
| VR-U01 | Unit | Critical | PASS | tests[ok] live[ok] |
| VR-U02 | Unit | Critical | PASS | tests[ok] live[ok] |
| VR-U03 | Unit | High | PASS | tests[ok] live[ok] |
| VR-U04 | Unit | High | PASS | tests[ok] live[ok] |
| VR-U05 | Unit | Medium | PASS | tests[ok] live[ok] |
| VR-U06 | Unit | High | PASS | tests[ok] live[ok] |
| VR-U07 | Unit | Medium | PASS | tests[ok] live[ok] |
| VR-I01 | Integration | Critical | PASS | tests[ok] live[ok] |
| VR-I02 | Integration | Critical | PASS | tests[ok] live[ok] |
| VR-I03 | Integration | Medium | PASS | tests[ok] live[ok] |
| VR-I04 | Integration | High | PASS | tests[ok] live[ok] |
| VR-S01 | Stochastic | Critical | PASS | tests[ok] live[ok] |
| VR-S02 | Stochastic | Critical | PASS | tests[ok] live[ok] |
| VR-S03 | Stochastic | High | PASS | tests[ok] live[ok] |
| VR-S04 | Stochastic | Critical | PASS | tests[ok] live[ok] |
| VR-S05 | Stochastic | High | PARTIAL | HW1F calibrated to a single live CNY/HKD swaption snapshot (Task 1); the rolling-window... |
| VR-SE01 | Sensitivity | High | PASS | tests[ok] live[ok] |
| VR-SE02 | Sensitivity | Critical | PASS | tests[ok] live[ok] |
| VR-SE03 | Sensitivity | High | PASS | tests[ok] live[ok] |
| VR-SE04 | Sensitivity | Medium | PASS | tests[ok] live[ok] |
| VR-B01 | Backtest | High | NOT_RUN | Asset-return backtest requires the live CNY 2015–2025 equity/bond series; wiring schedu... |
| VR-B02 | Backtest | Medium | NOT_RUN | Liability-cashflow backtest requires historical PAR-fund inforce experience data, which... |
| VR-B03 | Backtest | Medium | NOT_RUN | VaR/ES exception backtest requires >=250 days of historical P&L for the same calibrated... |
| VR-G01 | Governance | Critical | PASS | tests[ok] live[ok] |
| VR-G02 | Governance | High | PASS | tests[ok] live[ok] |
| VR-G03 | Governance | High | PARTIAL | APS X2 §3 requires sign-off by a reviewer independent of the model developer. The autom... |
| VR-G04 | Governance | Medium | PASS | tests[ok] live[ok] |
| VR-G05 | Governance | Critical | PARTIAL | Final production sign-off requires overall report PASS plus an independent validator; b... |
| VR-D01 | Data | High | PASS | tests[ok] live[ok] |
| VR-D02 | Data | High | PASS | tests[ok] live[ok] |
| VR-D03 | Data | Medium | PASS | tests[ok] live[ok] |

## Compliance by Layer

| Layer | PASS % |
|---|---|
| Unit | 100.0% |
| Integration | 100.0% |
| Stochastic | 80.0% |
| Sensitivity | 100.0% |
| Backtest | 0.0% |
| Governance | 60.0% |
| Data | 100.0% |

## Residual Requirements (mapped to remaining Phase 13 tasks)

- **VR-S05 [PARTIAL]** — HW1F calibrated to a single live CNY/HKD swaption snapshot (Task 1); the rolling-window coefficient-of-variation stability criterion requires a live multi-window CNY rate series, scheduled with the Task 5 live-data wiring.
- **VR-B01 [NOT_RUN]** — Asset-return backtest requires the live CNY 2015–2025 equity/bond series; wiring scheduled as Phase 13 Task 5 (G-09).
- **VR-B02 [NOT_RUN]** — Liability-cashflow backtest requires historical PAR-fund inforce experience data, which is not available in the educational dataset.
- **VR-B03 [NOT_RUN]** — VaR/ES exception backtest requires >=250 days of historical P&L for the same calibrated period; wired with the Task 5 live-data feed.
- **VR-G03 [PARTIAL]** — APS X2 §3 requires sign-off by a reviewer independent of the model developer. The automated SignOffWorkflow is operational but an independent human reviewer is pending (Phase 13 Task 6, G-08/G-10).
- **VR-G05 [PARTIAL]** — Final production sign-off requires overall report PASS plus an independent validator; blocked until the Layer-5 backtests (Task 5) and APS X2 review (Task 6) close. Educational use is permitted in the interim.

## Validation Finding (recorded)

`tests/test_guided_examples.py` errors (3 failed / 46 errors): the educational wrapper `par_model_v2/examples/guided_examples.py` has drifted from the current `RiskFreeCurve` / `FixedIncomeInstrument` / TVOG APIs. This wrapper backs no IA TAS M §3.6 requirement (the production reporting engine is tested separately and passes), so the G-06 score is unaffected. Proposed as model risk **MR-009** for change-controlled remediation in a later cycle.

## Governance

ChangeRecord `64e92edd61f94d8ea0c57fe77233b736` (change_type="governance_change") logged to the GovernanceStore, status **OWNER_REVIEW** (final APPROVED withheld pending independent APS X2 review — VR-G03 / Task 6).

---
*Educational model. A report whose overall status is not PASS must not be used for regulatory reporting, pricing, or external disclosure (IA TAS M §3.6).*