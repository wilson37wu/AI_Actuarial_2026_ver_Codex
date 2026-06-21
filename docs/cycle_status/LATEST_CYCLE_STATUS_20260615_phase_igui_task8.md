# Cycle status - Phase IGUI Task 8 (one-click offline packaging + own-run results refresh)

**Date:** 2026-06-15 (Claude Cowork 06:00 UTC window)
**Task:** Phase IGUI Task 8 - one-click offline packaging + own-run results refresh
**Status:** COMPLETE

## What landed
- **One-click offline launcher** `scripts/launch_offline_gui.py` (standard-library only) +
  OS double-click wrappers in `launchers/` (`Launch_Actuarial_GUI.bat` Windows /
  `Launch_Actuarial_GUI.command` macOS / `launch_actuarial_gui.sh` Linux / `README.md`):
  - puts the repo on `sys.path` so **no install / pip / PYTHONPATH setup** is needed;
  - picks a free `127.0.0.1` port (falls back if the default is busy), starts the existing
    stdlib runner `scripts/run_gui.py` bound to localhost only, opens the browser;
  - **discloses** whether the out-of-process numpy/scipy engine is importable (the GUI +
    offline RESULTS UI are pure stdlib; only the `/execute` compute child needs the engine)
    - it never installs anything, it reports;
  - `build_launch_plan` / `engine_status` are unit-testable; `--self-test` resolves the plan
    WITHOUT binding a server.
- **Own-run results refresh** `par_model_v2/viewer/igui_results_refresh.py` (stdlib only,
  DISPLAY LAYER): `refresh_user_results` drives `scripts/build_ui_data` with its run-evidence
  sources temporarily repointed at the user's `run_output/` and its outputs repointed at a
  USER directory, producing `user_results/ui_app_user.html` + `ui_data_user.json` that carry
  the user's OWN run **VERBATIM** via the existing `user_run` contract - then RESTORES every
  `build_ui_data` constant in a `finally`. The committed zero-install `ui_app.html` /
  `ui_data.json` are **never written** and are asserted byte-for-byte unchanged (sha256
  before/after); a committed-template mutation is a HARD failure. `validate_task8_gate`
  (13 checks) covers it.
- **Runner wiring** `scripts/run_gui.py`: on a SUCCESSFUL `/execute` run the runner
  best-effort refreshes the USER copy (a refresh hiccup NEVER fails the run) and exposes it
  at GET `/my-results` (+ `/my-results.json`), with a self-contained placeholder until a run
  exists.

## Verification
- 8 new unittests green (`tests/test_phase_igui_task8_results_refresh.py`): verbatim-headline
  USER copy; self-contained/offline USER html; graceful no-run fallback; committed-template
  byte-unchanged invariant; the 13-check Task-8 gate; launcher plan / engine-status /
  self-test-starts-no-server.
- `validate_task8_gate` ok: **13/13**.
- `scripts/run_gui.py --self-test` green, incl. the new `/my-results` routes.
- Committed `ui_app.html` **byte-unchanged** (sha256 `6dca35b3...`); `ui_data.json` unchanged.
- 0 new third-party runtime deps in the GUI/runner/refresh layer; 0 outbound network calls;
  0 external refs in the USER html.
- Governance: ChangeRecord `099ff0cb` OWNER_REVIEW (records 107->108, audit 135->136,
  integrity OK). Contract 1.21.0 unchanged; headline SCR 39,975.654628199336 carried verbatim.

## Environment note (not a regression)
- `scipy` is absent in this dev sandbox (`/sessions` 100% full; `pip` install ENOSPC, the
  standing human ask). The Task-7 suite's LIVE model-spawn tests therefore cannot execute
  here (`ModuleNotFoundError: scipy`); they are unrelated to this cycle - Task 8 is
  display-layer only and fully green. The pytest-based legacy suites likewise cannot be
  collected without `pytest` installed.

## Constraints honoured
- NO model parameter change; Phase 30 stop-rule (frozen copula structure echoed read-only);
  MR-016/MR-017 owner decision not pre-empted; one task this cycle; agent lock held;
  fresh-clone git per AGENT_COORDINATION.md.

## Next
- Task 9: Phase IGUI phase summary + consolidated re-audit; research/scope a true
  no-prerequisite packaging path (PyInstaller frozen binary OR vendored numpy/scipy wheels)
  so the COMPUTE step needs no pre-install either - present as an owner-decision options note
  (build tooling/network not available in this dev cycle).
