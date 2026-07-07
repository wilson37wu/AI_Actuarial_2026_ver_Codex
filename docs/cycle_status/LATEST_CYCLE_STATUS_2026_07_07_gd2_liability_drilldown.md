# Cycle Status — 2026-07-07 — GD-2 Stepwise Liability Drill-Down

**Agent:** Claude Cowork (scheduled `actuarial-model-daily-improvement`)
**Item:** GD-2 (roadmap §4.0e, owner directive 2026-07-07 — GUI stepwise-detail track)
**Outcome:** DONE — pushed to `main`, lock released.

## What was built

Per-model-point / per-product-class bucket-level cash-flow inspector:

- `par_model_v2/projection/liability_drilldown.py` — GD-2 engine.
  Selections = every portfolio row (model point) + every product class.
  Stepwise monthly columns (1..1200): BOM in-force policy count, expected
  death / surrender counts, premium, expense, all 9 CF-1 liability buckets,
  guaranteed / non-guaranteed benefit subtotals, net and cumulative net
  cash flow. Yearly rollup 1..100 (flows sum; in-force = year-start;
  cumulative = year-end). Artifacts: `LIABILITY_DRILLDOWN_SET.json` +
  `liability_drilldown_monthly.csv` + `liability_drilldown_yearly.csv`,
  stamped with a digest over portfolio + product catalogue. UNSIGNED
  declaration-scale note carried on every payload.
- **Consistency guarantee:** the engine calls the SAME `_PRODUCT_PROJECTORS`
  on the SAME `resolve_portfolio` output as the CF-1 set, so the class-level
  drill-down reconciles bucket-by-bucket, month-by-month with
  `project_liability_set` to 1e-9 (regression test), and model points sum
  to their class.
- `par_model_v2/viewer/igui_drilldown.py` — `/drilldown` GUI page
  (CF-3 interaction pattern): selection picker, lifetime KPI strip, yearly
  SVG build-up chart (premium / expense / gtd vs non-gtd benefits / net),
  stepwise table with yearly + per-year monthly granularity, UNSIGNED
  banner, zero external references. `/drilldown-data` endpoint is
  digest-cached (`DD_GUI_CACHE.json`) — unchanged inputs never re-run the
  engine.
- Wiring: `scripts/run_gui.py` routes; nav link on all console pages;
  page registered in the node `--check` script-syntax guard and the
  PC-1c nav regression test.

## Verification

- 15 new tests in `tests/test_gd2_liability_drilldown.py` — engine schema,
  stepwise shapes, decrement-count consistency, gtd+non-gtd == total,
  **exact CF-1 reconciliation**, MP-sum-to-class, yearly rollup semantics,
  digest sensitivity (balance sheet excluded), artifacts, GUI payload +
  cache hit/invalidation, error paths, page self-containment.
- 60 GREEN across GD-2 + GD-1 + CF-1 + CF-3 + nav + script-syntax suites.
- Broader GUI suites: 92 passed, 12 failed — the 12 are IDENTICAL on clean
  `main` with this change stashed (pre-existing sha-baseline/env failures,
  Phase 38 Task 3 owner-gated); no new regressions.
- Live e2e: server booted, `/drilldown` renders with nav, `/drilldown-data`
  fresh compute then cache hit verified; KPIs plausible (20y CD block:
  premium 61.4M, gtd benefits 63.2M, non-gtd 13.8M).

## Governance

Diagnostic overlay only — governed headline figures (TVOG, aggregation
reports) untouched. Declaration scales remain UNSIGNED pending Model Owner
approval. No governance store changes.

## Next queued

GD-3 (stepwise run-result decomposition / waterfall) — next OPEN item in
the owner-directed 4.0e track; then GD-4 (bind path detail to executed
runs), CF-2, PC-2.
