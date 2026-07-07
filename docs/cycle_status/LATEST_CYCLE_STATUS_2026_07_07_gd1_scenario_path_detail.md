# Cycle Status - 2026-07-07 - GD-1 Scenario-Path Detail (owner directive)

**Agent:** Claude Cowork · **Lock:** acquired/released this cycle
**Item:** GD-1 (new owner-directed track §4.0e, registered this cycle)

## Owner directive (2026-07-07, interactive)
"Focus on enriching GUI and allow for more detailed stepwise calculation to be
output and displayed in general, like economic scenario paths, asset returns
path, asset cash flow by asset class, liability cash flow by guarantee and
non-guarantee etc."

Registered as roadmap track **4.0e** (GD-1..GD-4); GD-1 implemented this cycle.
Asset CF by class and liability CF by gtd/non-gtd buckets were already served
by the CF-1/CF-3 set; the missing pieces were the STOCHASTIC PATH layer and a
front-and-centre gtd/non-gtd split - both delivered here.

## Delivered
1. **`par_model_v2/projection/scenario_path_detail.py`** (engine)
   - Real-world (Measure.P) HW1F short-rate paths + rho-correlated GBM
     equity paths (governed educational parameters), seeded from the SAVED
     `run_settings.seed`; horizon from `run_settings.horizon_months`
     (bounded 12..1200, default 480).
   - Per-asset-class monthly-return paths using the SAME class mechanics as
     the CF-1 set: bond = carry + par-duration mark-to-market proxy,
     equity = GBM total return, cash = short-rate carry; cumulative
     total-return indices (base 100).
   - Percentile fans p5/p25/p50/p75/p95 per month for every series + raw
     sample paths; artifacts `path_detail.json` + 6 CSVs with sha-256 inputs
     digest; UNSIGNED note on everything (display-only overlay).
2. **`par_model_v2/viewer/igui_path_detail.py`** + wiring in
   `scripts/run_gui.py`: new **/paths** console page (nav-linked) with
   inline-SVG fan charts, sample-path overlays, series picker (rate, equity,
   per-class return / cumulative), provenance card; `GET /path-data`
   digest-cached endpoint; graceful governed-default view when no inputs
   are saved yet.
3. **CF-3 enrichment:** liability chart payload + page now carry
   **guaranteed vs non-guaranteed** benefit series (cash dividend counted
   non-guaranteed); schema bumped to `cf3-gui-1.1` (cache-safe).

## Tests
- 13 new tests (`tests/test_gd1_scenario_path_detail.py`): fan ordering &
  shapes, seed reproducibility + sensitivity (tails/samples - antithetic
  median is drift-pinned by construction), horizon bounds, artifact
  round-trip, GUI cache hit/invalidate, page anchors, CF split guard.
- Regression: nav-on-every-page (now incl. /paths), node `--check` inline
  script syntax guard (now incl. /paths), CF-1/CF-3/PC-1, GUI-2/3/4/5.
- **114 GREEN** across the affected suites; live e2e: /paths page served
  with single nav, /path-data fresh then cached, seed/horizon/classes bound
  to saved inputs.

## Governance
- No governed headline figure touched; overlay is UNSIGNED and display-only.
- Pre-existing owner-gated Phase 38 Task 3 (ui_app sha re-baseline) remains
  gated and untouched.

## Next queued
- GD-4 (bind path set to executed runs) or CF-2 (attach CF set to run
  registry) - natural pair; then GD-2 policy-level stepwise drill-down.
