# Cycle — 2026-07-09 (claude / Cowork window) — §4.1 #6 Backtest on real history

**Conclusion:** Completed roadmap §4.1 item **#6 "Backtest on real history"** (maps to Limitation #5; depends on the item-#1 live pipeline). This clears §4.1 items #1–#6. Purely additive diagnostic — **no governed headline (TVOG / aggregation) touched**; re-baselining onto a live calibration stays owner-gated.

## What shipped
- **`par_model_v2/calibration/live_history_backtest.py`** — bridges roadmap item #1's `live_market_data_pipeline` into the governed Phase-4/Phase-13 `BacktestEngine`:
  - `CNYBacktestHistoryLoader(_BaseMarketDataLoader)` resolves the annual **CNY 1Y-rate + CSI 300 return series** through item #1's **three provenance tiers** (`live_fetch`→`cached_snapshot`→`file_fixture`), **`SnapshotCache` SHA-256** sealing, and **`DataLineageRecord`** (IA TAS M §3.6). Offline default → `file_fixture`, UNSIGNED.
  - `PipelineBacktestHistorySource` adapts it to the existing `BacktestHistorySource` contract; the unchanged governed path (`LiveBacktestDataLoader`→`calibrate_from_history` in-sample-only→`BacktestEngine`) computes **Kupiec POF + rate/equity coverage** on the **≥10-year** window (12 obs 2014–2025; 7y in-sample / 5y OOS holdout).
  - `evaluate_recalibration_triggers` — structured **8-signal recalibration-trigger** set (coverage ×2, Kupiec VaR95/99, VaR99/VaR95 breach, Q-measure martingale, OOS coverage drift), severity-folded to an overall recommendation.
- **`backtesting._chi2_sf_df1`** — scipy-free Kupiec: exact df=1 closed form `chi2.sf(x,1)=erfc(sqrt(x/2))` (stdlib `math.erfc`), numerically identical to scipy; keeps the Kupiec test runnable offline.
- Evidence: **`docs/validation/LIVE_HISTORY_BACKTEST.json`** (schema `live-history-backtest-1.0`, stable `inputs_digest` 56aaa654…, UNSIGNED banner), builder **`scripts/build_live_history_backtest.py`**, card **`docs/LIVE_HISTORY_BACKTEST_CARD.md`**; `MODEL_STABILITY_AND_LIMITATIONS.md` §3.5 partial-mitigation pointer.

## Result (educational-proxy fixture, 2,000 scenarios, seed 20260709)
- Provenance `file_fixture`; 12 annual obs; **G-09 PASS** (rate cov 75%, equity cov 100%, Kupiec VaR95 p=0.267, VaR99 breach 0%).
- Recalibration recommendation **`SCHEDULE_RECALIBRATION`** — one HIGH trigger (`oos_coverage_drift`, small 5y OOS window); all VaR/coverage/martingale clear.

## Tests
- **NEW `tests/test_live_history_backtest.py` 19/19 GREEN** (unittest; numpy/pandas; scipy-free).
- Regression via a minimal pytest shim (pip/scipy/pytest unavailable in the network-restricted sandbox): `test_backtesting` **18/18**, `test_phase13_backtest` **24/24**, `test_live_market_data_pipeline` **12/12** → **54/54**.
- Item #1's pipeline module was NOT edited (loader subclassed from another module), so its suite is unaffected.

## Isolation / hygiene
- Module imports no `run_model`; no governed artifact written (only `docs/validation/LIVE_HISTORY_BACKTEST.json` + card). Regression-asserted.
- Snapshot cache defaults to system temp; `.gitignore` extended with `**/_snapshot_cache/` as a safety net — no cache pollution committed.

## Next OPEN
§4.1 **#7 G2++ two-factor rate-model promotion** (wire the existing G2PP cards into the production ESG path with curve-twist + martingale/swaption fit evidence; HW1F kept as fallback).
