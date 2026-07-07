# Cycle Status — 2026-07-07 — GD-3 Stepwise run-result decomposition

**Agent:** Claude Cowork (scheduled task `actuarial-model-daily-improvement`)
**Item:** Roadmap §4.0e GD-3 (owner directive 2026-07-07, KCW): surface the
per-driver standalone SCR build-up from the run artifacts as a calculation
waterfall view in the GUI.
**Status:** DONE

## What was built

- `par_model_v2/projection/run_result_decomposition.py` — stdlib-only,
  READ-ONLY engine over the executed run's
  `run_output/RUN_MODEL_AGGREGATION_REPORT.json` (the evidence file
  `scripts/run_model.py` writes; artifact-name kept in lock-step,
  regression-tested). Produces:
  - a 14-step waterfall: 7 standalone driver SCRs (build) → standalone sum
    (subtotal) → var-covar diversification credit (delta) → var-covar SCR →
    copula tail-dependence adjustment (delta) → copula SCR → nested
    interaction residual (delta) → headline nested SCR (final), each step
    carrying the running cumulative;
  - reconciliation identities asserted fail-loud (inconsistent artifacts
    are refused, never silently rendered);
  - per-driver standalone SCR share table, copula AIC-candidate evidence
    (selected flag), tail-convergence path + bootstrap CI carry-through;
  - artifacts `RUN_DECOMPOSITION_SET.json` + 4 tidy CSVs (waterfall,
    drivers, copulas, convergence), stamped with the sha256 of the source
    artifact bytes; UNSIGNED diagnostic note.
- `par_model_v2/viewer/igui_decomposition.py` — `/decomposition` page
  (floating-bar waterfall SVG with step connectors + tooltips, provenance
  card, KPI strip, waterfall/driver/copula tables, VaR-ES convergence
  chart, UNSIGNED banner; inline JS/SVG only, zero external refs) and
  `build_decomposition_response` (digest-cached in
  `run_output/decomposition_set/`; unchanged artifact never re-derives).
- `scripts/run_gui.py` — `/decomposition` + `/decomposition-data` routes;
  nav link "Waterfall" (`igui_portfolio_builder.NAV_LINKS`).
- Guards extended: nav-on-every-page test and node `--check` inline-script
  syntax test now cover the new page.

## Scope note

The executed-run artifact set carries the SCR aggregation evidence only.
The governed TVOG headline is produced by a separate, owner-gated pipeline
and is NOT decomposed here — governed headline figures untouched (standing
constraint honoured; the roadmap item's TVOG wording is satisfiable only
once TVOG build-up artifacts are attached to executed runs, which would be
new scope, e.g. alongside GD-4 run-registry attachments).

## Tests

- 15 new tests in `tests/test_gd3_run_decomposition.py` (identities
  bit-for-bit vs the committed governed Phase 22 Task 4 report, order/kind
  contract, share sum = 100 %, copula selection carry, convergence and
  bootstrap carry, inconsistent/non-report refusal, artifact writing +
  digest stability, GUI cache fresh→cached→invalidated, clean no-run
  error, page self-containment, live route wiring incl. nav).
- 47 GREEN across GD-1/GD-2/GD-3 + nav + script-syntax suites; 108 passed
  on the wider GUI/CF subset.
- 10 pre-existing failures on main (ui_app sha-baseline family + task7
  e2e) confirmed UNCHANGED via stash A/B on the same subset.
- Live e2e: server started, `/decomposition` renders with nav,
  `/decomposition-data` fresh compute then cached hit verified, JSON + 4
  CSVs on disk.

## Blockers

None. Next queued items: GD-4 (bind GD-1 path set to executed runs), CF-2
(attach CF set to run registry), backlog #2 (HW1F swaption calibration).
