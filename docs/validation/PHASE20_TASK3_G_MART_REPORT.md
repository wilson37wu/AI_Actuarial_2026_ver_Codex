# Phase 20 Task 3 -- Market-Consistency (Martingale) Gate G-MART

**Run:** 2026-06-06T09:25:49.350310+00:00

**Gate G-MART:** PASS (8/6 ERROR checks pass; 8 checks incl. diagnostics)

## Numeraire and method

Money-market account B(t) = exp(int_0^t r ds). Each deflated-asset martingale identity is
tested by Monte-Carlo against its analytic target within a 4-standard-error band
(n = 40000 paths; horizon t = 1.00y).

## Checks

| Check | Severity | Result | MC estimate | Target | Rel err | n-sigma |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| MART-HW1F-ZCB-5Y | ERROR | PASS | 0.835065 | 0.835270 | 2.45e-04 | 0.97 |
| MART-HW1F-ZCB-10Y | ERROR | PASS | 0.718643 | 0.718924 | 3.90e-04 | 1.00 |
| MART-HW1F-EULER-BIAS | INFO | PASS | 0.768840 | 0.718924 | 6.94e-02 | 58.91 |
| MART-G2PP-ZCB-5Y | ERROR | PASS | 0.835442 | 0.835270 | 2.06e-04 | 1.22 |
| MART-G2PP-ZCB-10Y | ERROR | PASS | 0.719163 | 0.718924 | 3.32e-04 | 1.22 |
| MART-EQ-FWD | ERROR | PASS | 99.984283 | 100.000000 | 1.57e-04 | 0.14 |
| MART-PQ-MEASURE | INFO | PASS | 104.646180 | 104.602786 | 4.15e-04 | 0.37 |
| MART-FX-CIP | ERROR | PASS | 7.799514 | 7.800000 | 6.23e-05 | 0.13 |

## Summary

- Worst ERROR-check deviation: 1.22 sigma (band 4 sigma).
- Max ERROR relative error: 3.90e-04.
- Drivers covered: HW1F rates, G2++ rates, GBM equity, FX (CIP).

## Diagnostics (non-gating)

- The educational monthly-Euler HW1F simulator shows a documented ~7% martingale bias vs the
  exact dynamics (MART-HW1F-EULER-BIAS) -- exact simulation is used for the gate.
- Under P the discounted equity drifts up by exp(ERP*t) (MART-PQ-MEASURE), confirming the
  martingale property is Q-specific.

## Governance

- ChangeRecord: 955fe35ce8034a9cb98904a7b6d79c62 (OWNER_REVIEW).
- MR-013: IN_PROGRESS (refreshed).
- Audit integrity: True.

## Production restriction

EDUCATIONAL market-consistency evidence. The martingale gate confirms the simulators are arbitrage-free under Q at the tested horizon and Monte-Carlo accuracy; it is NOT a production sign-off. Calibration to a validated market surface and independent (APS X2) review remain pending.
