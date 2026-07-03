# Cycle Status — 2026-07-03 — GUI-4 Run History & Compare

**Agent:** Claude Cowork (owner-triggered interactive cycle, same protocol as
scheduled task `actuarial-model-daily-improvement`)
**Item:** Roadmap §4.0 GUI-4 — Run history & compare (owner directive
2026-07-03; owner said "GUI 4 proceed")
**Outcome:** DONE — **GUI run-console track (GUI-1..GUI-4) COMPLETE**

## What landed

- `par_model_v2/viewer/igui_run_history.py` (new): persisted run registry
  built from the GUI-1 JobManager records (`run_output/jobs/job_<id>.json`)
  carrying the roadmap reproducibility tuple — run id, timestamps, Task-6
  inputs digest, seed + run plan, headline outputs (nested/copula/var-covar
  SCR + standalone drivers); `get_run` (open one past run);
  `compare_runs` (side-by-side metadata rows + headline deltas, B − A,
  GUI-2 delta shape, with smoke / kind-mismatch / identical-digest notes);
  self-contained `/history` console page (registry table, detail pane,
  pick-two compare).
- Durable enrichment: shared `run_output/` artifacts are overwritten by
  later runs, so the registry extracts the run plan (seed, scenario budget)
  from the aggregation report while it exists and persists it back into the
  job record (additive `registry` block, atomic rewrite, re-parse guard);
  regression-tested to survive artifact deletion.
- `scripts/run_gui.py`: routes `GET /history`, `GET /runs`,
  `GET /runs/<id>` (404 on unknown, path-traversal-safe),
  `GET /compare-runs?a=&b=` (422 without both ids).
- `par_model_v2/viewer/igui_run_execution.py`: run page links to the
  history console.
- `tests/test_gui4_run_history.py` (new, 14 tests): registry shape +
  newest-first ordering, reproducibility tuple, durable enrichment,
  corrupt-record tolerance, path-traversal refusal, compare deltas/notes,
  unknown-id handling, self-contained HTML, live server endpoint
  round-trips.
- `docs/GUI_RUN_CONSOLE.md` GUI-4 section; roadmap §4.0/§5 updated —
  §4.0 track marked COMPLETE, priority reverts to general backlog §4.1.

## Governance

- Registry is read-only over engine artifacts; only additive annotation of
  job records. Governance store untouched. No governed headline change;
  committed `ui_app.html` untouched; Phase 38 Task 3 stays owner-gated.
- Run registry entries preserve the UNSIGNED flag of calibration runs.

## Tests

GUI-4 suite 14/14 GREEN; full GUI track (GUI-1..GUI-4) 53 passed. Known
pre-existing `ui_app.html` sha-baseline failures on `main` (owner-gated
Phase 38 re-baseline) unchanged and unrelated.

## Next queued

General backlog §4.1 — highest-priority OPEN item is #2: execute HW1F
swaption calibration on a live/proxy quote set with parameter card
(UNSIGNED pending owner approval); the GUI-3 console is its display
surface.
