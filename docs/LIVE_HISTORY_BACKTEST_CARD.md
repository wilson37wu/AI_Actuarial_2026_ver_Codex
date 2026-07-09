# Live-History Backtest Bridge — Roadmap Item #6

**Document ID:** `LIVE-HISTORY-BACKTEST-CARD`
**Created:** 2026-07-09 (Claude Cowork continuous-improvement cycle)
**Roadmap:** `docs/CONTINUOUS_IMPROVEMENT_ROADMAP.md` §4.1 item #6 (maps to Limitation #5; depends on item #1)
**Module:** `par_model_v2/calibration/live_history_backtest.py`
**Evidence artifact:** `docs/validation/LIVE_HISTORY_BACKTEST.json` (schema `live-history-backtest-1.0`, **UNSIGNED**)
**Status:** DONE — purely additive diagnostic; **no governed headline (TVOG, aggregation) re-baselined**.

---

## 1. What this delivers

Item #6 asks to *"populate `BacktestEngine` with live CNY curve / CSI 300 series
(item 1 dependency); Kupiec POF + coverage tests on ≥10y history; recalibration
triggers evaluated."* This bridge does exactly that by connecting roadmap item
#1's **live market-data pipeline** (`live_market_data_pipeline.py`) to the
governed Phase-4 / Phase-13 backtest stack, and adds an explicit, structured
**recalibration-trigger** evaluation.

It is the item-#6 delta over Phase 13 Task 5 (Gate G-09), which already ran
Kupiec + coverage on a ≥10y annual fixture but (a) read that fixture through its
own `FileBasedBacktestHistorySource` rather than the item-#1 pipeline, and (b)
reported only a single `requires_recalibration` boolean.

## 2. How the item-#1 pipeline is used (the "item 1 dependency")

`CNYBacktestHistoryLoader` subclasses item #1's `_BaseMarketDataLoader`, so the
annual **CNY 1Y short-rate** and **CSI 300 total-return** series flow through
the same governed machinery item #1 shipped:

- **Three provenance tiers** resolved in order — `live_fetch` → `cached_snapshot`
  → `file_fixture`. No credentialled feed ships, so the offline default resolves
  the `file_fixture` tier and the lineage is flagged **UNSIGNED pending Model
  Owner source approval** (never self-approved). A second load promotes to the
  `cached_snapshot` tier (regression-tested).
- **`SnapshotCache` SHA-256 sealing** — every resolved series is snapshot-sealed;
  the payload SHA-256 is re-verified on read (tamper → `SnapshotIntegrityError`).
- **`DataLineageRecord`** (IA TAS M §3.6) carried end-to-end into the report.

The realised **series** (rate + equity) are sealed through the pipeline; the
**loss basis** and the in/out-of-sample **window** are model conventions read
from the same fixture (they are not market observations).

## 3. Kupiec POF + coverage on ≥10y

The sealed series feed the **unchanged** governed path — `LiveBacktestDataLoader`
→ `calibrate_from_history` (in-sample window only, genuine out-of-sample
holdout) → `BacktestEngine`. The engine computes rate/equity band coverage,
empirical VaR/ES exceptions, the **Kupiec proportion-of-failures** p-values, and
the Q-measure martingale check. Gate **G-09** is evaluated on the full ≥10-year
series (12 annual observations, 2014–2025: 7-year in-sample / 5-year OOS).

**Scipy-free Kupiec.** `backtesting._kupiec_pof_pvalue` previously imported
`scipy.stats.chi2.sf`. It now calls `_chi2_sf_df1`, which uses scipy when present
and otherwise the **exact** closed form for one degree of freedom,
`chi2.sf(x, 1) = erfc(sqrt(x/2))` (a χ²₁ variate is Z²). This is numerically
identical and keeps the Kupiec test runnable in the offline sandbox / minimal CI.

## 4. Recalibration triggers evaluated

`evaluate_recalibration_triggers(full_result, oos_result)` maps the backtest
outcome onto a governed, per-signal trigger set — each with a severity and a
specific recommended action:

| Trigger | Threshold | Severity |
|---|---|---|
| `rate_band_coverage` | ≥ 70% | CRITICAL |
| `equity_band_coverage` | ≥ 70% | CRITICAL |
| `kupiec_var95_pof` | p > 0.05 | HIGH |
| `kupiec_var99_pof` | p > 0.05 | HIGH |
| `var99_breach_rate` | ≤ 5% | CRITICAL |
| `var95_breach_rate` | ≤ 10% | MEDIUM |
| `martingale_q_measure` | all pass | CRITICAL |
| `oos_coverage_drift` | ≤ 0.20 | HIGH |

The overall recommendation is the worst breached severity: CRITICAL →
`RECALIBRATION_REQUIRED`, HIGH → `SCHEDULE_RECALIBRATION`, MEDIUM →
`ENHANCED_MONITORING`, else `NO_ACTION_MONITOR`.

## 5. Current result (educational-proxy fixture, 2,000 scenarios, seed 20260709)

- Provenance `file_fixture`; 12 annual observations; G-09 gate **PASS**
  (rate coverage 75%, equity coverage 100%, Kupiec VaR95 p=0.267, VaR99 breach 0%).
- Recalibration recommendation **`SCHEDULE_RECALIBRATION`** — one HIGH trigger
  (`oos_coverage_drift`) from the small 5-year out-of-sample window; all VaR/
  coverage/martingale triggers clear. This is a stability signal, not a headline
  change.
- `inputs_digest` is a stable SHA-256 over the sealed series + basis + run
  knobs (timestamps excluded), so re-runs are reproducible.

## 6. Reproduce

```
PYTHONPATH=. python3 scripts/build_live_history_backtest.py --scenarios 2000 --seed 20260709
```

Writes `docs/validation/LIVE_HISTORY_BACKTEST.json`. Tests:
`python3 -m unittest tests.test_live_history_backtest` (19 tests).

## 7. Production restriction

The bundled history is an **educational proxy** of published ChinaBond / CSI /
Wind levels, not a credentialled vendor feed. Replace with a licensed extract
and complete the Model-Owner sign-off before any regulatory or capital-adequacy
use. Re-baselining any governed headline onto a refreshed live calibration
remains **owner-gated**.

**Standards:** SOA ASOP 56 §3.5 (backtesting), ASOP 23 (data quality),
IA TAS M §3.6 (traceability / independent review); CBIRC C-ROSS scenario/tail bar.
