# Cycle status - Phase IGUI Task 7 (end-to-end run + results handoff)

**Date:** 2026-06-15 (Claude Cowork 06:00 UTC window)
**Task:** Phase IGUI Task 7 - end-to-end run + results handoff (Phase IGUI MVP)
**Status:** COMPLETE - Phase IGUI MVP done

## What landed
- **Gate-guarded end-to-end driver** `par_model_v2/viewer/igui_run_execution.py` (standard-library only):
  - `verify_run_gate` refuses to spawn the model unless `model_inputs.json` carries a Task-6 `run_gate`
    with `decision==CLEARED` / `run_permitted==True`, matching schema version, every domain present+clean,
    AND a reproducibility digest that re-verifies against the live inputs (a gate lifted off an
    altered/different input set is rejected).
  - `execute_run` drives `scripts/run_model.py` **as a child process** (so the GUI/runner layer keeps
    zero third-party runtime deps while the numpy/scipy engine runs out of process), captures
    stdout/stderr as progress, reads back the two RUN_MODEL artifacts, **stamps a `run_gate_provenance`
    block** (the Task-6 reproducibility digest + decision + governed headline + read-only frozen copula
    structure) onto each, and shapes the offline RESULTS-UI handoff.
  - `build_results_handoff` produces the SAME `user_run` contract the offline UI already consumes
    (`scripts/build_ui_data._build_user_run`).
  - Self-contained run page (`render_run_html`, GET `/run-execution`): Run button disabled until the
    gate clears; live progress/errors; post-run headline read-outs; governed headline + frozen structure
    echoed read-only.
- **Runner** `scripts/run_gui.py`: GET `/run-execution` + POST `/execute` (writes `RUN_MODEL_*.json`
  into `run_output/`, never clobbering governed `docs/validation` evidence). Rebased off `origin/main`
  after finding a truncated mount copy.

## Verification
- 21 new unittests green (`tests/test_phase_igui_task7_run_execution.py`), incl. **2 real end-to-end
  smoke runs** (gate -> run -> capture -> digest-in-provenance -> handoff) and the refusal path.
- Task-7 acceptance gate `validate_task7_gate` ok: **19/19** (incl. a live smoke run).
- Full Phase IGUI suite green: **157** tests.
- `ui_app.html` **byte-unchanged** (sha256 `6dca35b3...`), re-asserted AFTER a live run.
- 0 new third-party runtime deps in the GUI/runner layer; 0 outbound network calls.
- Governance: ChangeRecord `fe3f09c8` OWNER_REVIEW (records 106->107, audit 134->135, integrity OK).
- Contract 1.21.0 unchanged; headline SCR 39,975.654628199336 carried bit-for-bit.

## Constraints honoured
- NO model parameter change; Phase 30 stop-rule (frozen copula structure echoed read-only);
  MR-016/MR-017 owner decision not pre-empted; one task this cycle; agent lock held.

## Next
- Task 8: one-click offline packaging (no pre-install launcher) + wire `run_output/` -> the offline
  RESULTS UI so a user sees THEIR OWN run (leaving the committed `ui_app.html` template byte-unchanged).
