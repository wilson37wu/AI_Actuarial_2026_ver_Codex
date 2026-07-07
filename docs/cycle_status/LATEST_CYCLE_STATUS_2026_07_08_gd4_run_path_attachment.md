# Cycle Status — 2026-07-08 — GD-4: scenario-path detail bound to executed runs

**Agent:** claude (scheduled task `actuarial-model-daily-improvement`)
**Item:** roadmap §4.0e GD-4 (owner directive 2026-07-07) — highest-priority OPEN item; completes track 4.0e
**Lock:** acquired/released per `AGENT_COORDINATION.md` (cycle 2026-07-07T16:07Z-4ab4)

## What was built

Before this cycle the `/paths` page always simulated from the CURRENT saved
`model_inputs.json`, so after any input change the paths shown no longer
matched past executed runs. GD-4 binds the GD-1 scenario-path set to each
executed run:

- `par_model_v2/viewer/igui_path_detail.py`
  - `attach_path_detail_for_run(inputs_path, out_root)` — builds the GD-1 set
    into `run_output/path_detail_runs/<digest12>/path_detail/` (JSON + 6 CSVs
    + page cache), keyed by the GD-1 inputs digest: identical-input runs share
    one persisted copy (digest-cache hit), and later runs never overwrite an
    earlier run's set (unlike the shared `run_output` engine artifacts).
    Never raises — a path-detail hiccup cannot fail the governed run.
  - `load_run_path_detail(jobs_dir, run_id)` — serves the persisted payload
    for a past run with run provenance stamped on it (schema + digest guards,
    path-traversal-safe run_id handling). The current inputs file is NOT read.
  - `/paths` page: `?run=<id>` query binding + run-provenance banner
    (`run-note`); unchanged behaviour with no query param.
- `par_model_v2/viewer/igui_run_execution.py` — `execute_run` step (6): after
  artifact stamping, best-effort attach; the attachment block rides the run
  result, so the GUI-1 `JobManager` persists it on the job record.
- `par_model_v2/viewer/igui_run_history.py` — registry entries surface
  `path_detail` (available / digest / dir); history table gains a per-run
  **Paths** button (`/paths?run=<id>`); `compare_runs` notes whether the two
  runs carry the SAME / DIFFERING / missing persisted path sets.
- `scripts/run_gui.py` — `/path-data?run=<id>` routes to the persisted
  per-run loader; plain `/path-data` unchanged (current-inputs behaviour).

Diagnostic overlay only — governed headline figures untouched; parameters
remain UNSIGNED (banner carried through from the GD-1 payload).

## Tests

- NEW `tests/test_gd4_run_path_attachment.py` — 15 tests: digest-keyed
  persistence + cache reuse + no-overwrite across seeds; never-raise on
  corrupt inputs; persisted-set loader provenance/schema/digest/traversal
  guards; pre-GD-4 runs report "no persisted set"; registry + compare
  surfacing; execute_run wiring contract; page plumbing; LIVE HTTP
  round-trip (`make_server` → `/path-data?run=` 200 + unknown run 422).
- GREEN: 154 across GD-1..4, GUI-1..5, CF-1/CF-3, PC-1, nav,
  script-syntax (node) and agent-lock suites.
- 8 pre-existing failures in `test_phase_igui_task7_run_execution.py`
  (ui_app sha-baseline / live-run gate, owner-gated Phase 38 lineage)
  verified UNCHANGED on clean main via stash A/B.
- Limitation this cycle: a full `run_model.py` live smoke could not be
  executed in the sandbox (scipy wheel download stalled); the GD-4 GUI
  surface was e2e-verified over live HTTP instead, and the attach engine
  runs the real GD-1 simulation (numpy/pandas) in the new tests.

## Next queued item

Roadmap §4.0c CF-2 (run integration of the cash-flow projection set — same
attachment pattern, now with a GD-4 precedent) or §4.1 #2 HW1F swaption
calibration execution.
