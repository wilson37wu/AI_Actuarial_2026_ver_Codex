# Cycle Status — 2026-07-09 — ES-3 user-scenario engine integration

**Item:** ES-3 (owner directive 2026-07-08, track 4.0f — User Economic-Scenario File).
**Status:** DONE — track 4.0f COMPLETE. **Owner:** claude (Cowork scheduled cycle).
**Governance:** purely additive; governed headline (TVOG / aggregation report) untouched.

## What shipped
Engine/run-layer integration of validated user economic-scenario files (ES-1 loader,
ES-2 GUI persist) into the governed run pipeline.

New `par_model_v2/stochastic/scenario_source.py` (numpy):
- Annual→monthly **piecewise-annual** interpolation (schema `es3-scenario-source-1.0`):
  each year-end spot-zero curve held across its 12 months; monthly short-rate proxy = the
  `3M` spot; monthly equity = geometric split `(1+annual)^(1/12)-1`, recompounding to the
  annual `EQ_RETURN` exactly (< 1e-9).
- `interpolate_monthly_paths()` → `short_rate` (S×M), `equity_return` (S×M), `rate_cube`
  (S×M×T), `year_index` (M); `monthly_mapping_summary()` → JSON-safe eyeball card.

New `par_model_v2/viewer/igui_scenario_source.py` (stdlib-only at import; numpy/loader/
engine lazy — GUI-layer contract, regression-tested):
- `read_scenario_source` (`model`|`user_file`, default `model`) + `read_run_intent`
  (`valuation`|`p_diagnostic`, default `valuation`), fail-loud on bad values.
- **Measure guard**: valuation→`risk_neutral`, p_diagnostic→`real_world`; a mismatch /
  missing / unknown-basis file is an **ERROR** carrying a structured
  `SCENARIO_MEASURE_DEVIATION` record (severity ERROR, required vs file basis, sha256,
  resolution). `evaluate_measure_guard` (non-raising) + `enforce_measure_guard` (raising).
- `build_scenario_source_provenance` (schema `es3-scenario-source-prov-1.0`) + digest-keyed
  `attach_scenario_source_for_run` (persist under `run_output/scenario_source_runs/<digest12>/`
  like CF-2/GD-4; persisted-CSV digest **re-verified** on attach → STALE on tamper/missing;
  cache reuse; never-raise).

`execute_run` wiring (`igui_run_execution.py`):
- Pre-run guard **refuses** a `user_file` run on mismatch (stage `scenario_measure_guard`,
  nothing spawned).
- Post-run best-effort attach + additive `scenario_source_provenance` stamp onto both
  RUN_MODEL artifacts **for a user-file run only** (a `model` run stays bit-identical).

`/save-scenarios` (`igui_scenarios.py`) now selects the saved file
(`scenario_source=user_file` + intent derived from the file basis) → end-to-end with zero
`.py` editing. ES-2's 19 tests still GREEN.

Spec `docs/ECONOMIC_SCENARIO_FILE_FORMAT.md` gains §7 (as-implemented engine consumption +
monthly rule); ES-3 roadmap row → DONE.

## Tests
- 29 new tests `tests/test_es3_scenario_source.py` (unittest) — GREEN.
- Regression GREEN on runnable numpy-only subset: ES-2 (19), CF-2 (16), GD-4 (15),
  GUI-1 (9), GUI-5 (8), page-scripts (2).
- 8 `test_phase_igui_task7_run_execution` failures (EndToEndSmoke + ui_app sha baseline)
  are PRE-EXISTING — identical on pristine main via stash A/B. Cause: scipy + pytest
  unavailable in this network-restricted sandbox; ui_app cutover is owner-gated.

## Boundary / next
- RE-BASELINING the governed headline (TVOG/aggregation) onto user scenarios moves a
  governed figure and remains the **owner-gated** follow-on — NOT part of ES-3.
- Track 4.0f COMPLETE → priority reverts to general backlog §4.1 (next OPEN: #3 CBIRC
  3.0% discount-cap remediation).
