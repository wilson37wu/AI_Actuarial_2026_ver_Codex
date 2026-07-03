# Cycle Status — 2026-07-03 — CF-3 Cash-Flow GUI Page (Owner Request)

**Item:** Owner request: display the cash-flow projections in the GUI as
table and chart.
**Outcome:** DONE — CF track (CF-1/1b/1c/3) complete except CF-2 run
integration.

- `par_model_v2/viewer/igui_cashflows.py` (new): `/cashflows` page —
  liability CF components line chart + stacked asset-balance bars (inline
  SVG, zero external refs), three tables (liability / asset CF / balances)
  in yearly or per-year monthly granularity, UNSIGNED banner,
  book_runoff_month + shortfall callouts; `build_cashflow_response` =
  digest-cached data builder that also refreshes the six wide CSVs.
- `scripts/run_gui.py`: GET /cashflows, GET /cashflow-data.
- Run page links to the new console; page registered in the node JS-syntax
  guard (GUI-5 lesson applied).
- Tests: 6 new (payload shape incl. 100/1200-row tables + chart series,
  digest cache hit/invalidation, missing/bad inputs, self-contained page,
  live endpoint round-trip); 85 GREEN across CF + GUI suites.

Next queued: CF-2 (attach CF set to every GUI run), then general backlog
#2 (HW1F live/proxy calibration).
