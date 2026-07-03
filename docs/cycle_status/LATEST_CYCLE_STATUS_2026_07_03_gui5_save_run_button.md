# Cycle Status — 2026-07-03 — GUI-5 Save & RUN Button (Owner Request)

**Agent:** Claude Cowork (owner-triggered interactive cycle)
**Item:** GUI-5 — owner request 2026-07-03: "I need a run button to kick off
the calculation process in this screen [Run Controls]; now it only gives an
updated json file but the model does not seem to run."
**Outcome:** DONE

## What landed

- `par_model_v2/viewer/igui_run_controls.py`: green **Save & RUN model**
  button on the Run Controls page + smoke / auto-fill checkboxes; in-page
  progress streaming (polls the GUI-1 `/jobs/<id>` endpoint), headline
  readout on success with links to `/my-results` and `/history`; on a
  blocked gate, every blocking issue is listed with links to the Model
  Points / Assumptions / ESG / Run Gate pages. Page stays fully
  self-contained; governed headline still carried bit-for-bit.
- `scripts/run_gui.py`: `POST /save-run` = `build_save_run_response()`:
  save controls (same validator as `/save`) → optional governed-default
  auto-fill of ABSENT domains only (same builders/validators as the
  dedicated pages) → Task-6 run gate (digest bound to final bytes; blocked
  gate written NEVER, run refused) → GUI-1 async job submission. The engine
  re-verifies the gate before spawning — no governance bypass.
- `tests/test_gui5_save_run.py` (8 tests): autofill-clears-gate-and-submits,
  no-autofill blocks with actionable issues (nothing spawned, blocked gate
  not written), invalid controls fail before any write, busy/missing job
  manager reporting, owner's seed 46 flows into gated inputs, page wiring,
  HTTP round-trip (422 blocked / 200 submitted).

## Live end-to-end verification (real engine)

One click with defaults + auto-fill + smoke: gate CLEARED
(digest sha256:07f5…804b00), job succeeded in ~20 s, headline rendered
(nested_scr 61,344.29 smoke-diagnostic), `/my-results` refreshed.
Diagnostic smoke figures — not governed capital results.

## Tests

GUI-5 8/8 GREEN; GUI-1..4 suites + task2 run-controls suite: 72 passed,
2 pre-existing failures (`ui_app.html` sha-baseline family, owner-gated
Phase 38) confirmed identical on unmodified main.

## Next queued

General backlog §4.1 #2 — HW1F calibration on live/proxy quote set
(UNSIGNED pending owner approval).
