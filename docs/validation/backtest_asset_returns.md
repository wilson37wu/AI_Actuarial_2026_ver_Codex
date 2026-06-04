# VR-B01 — Asset Return Backtest (5Y Rolling / Out-of-Sample)

**Standard:** SOA ASOP 56 §3.5; IA TAS M §3.6.4 — **Market:** CNY (educational proxy)
**Generated:** 2026-06-04T13:27:04.939843+00:00

## Result: PASS

| Criterion | Target | Observed | Verdict |
|---|---|---|---|
| Observed equity return in [5th, 95th] pctile band | >= 80% of obs | 100% (OOS) | PASS |
| Observed bond yield in [5th, 95th] pctile band | >= 80% of windows | 100% (OOS) / 75% (full) | PASS |
| Backtest period | 2015–2025 (>= 10y) | 2014-2025 (12 obs) | PASS |
| Backtest report produced | docs/validation/backtest_asset_returns.md | this file | PASS |

## Corroborating diagnostics

- Out-of-sample holdout: 5 obs; in-sample calibration -> genuine holdout test.
- Kupiec POF p-values (OOS): 95% = 0.474, 99% = 0.751 (both > 0.05).
- Q-measure discount-factor martingale diagnostics: all pass.
- Recalibration trigger: none.

---
*Educational model. CNY series is a documented educational proxy; a credentialled vendor feed is a tracked production residual.*