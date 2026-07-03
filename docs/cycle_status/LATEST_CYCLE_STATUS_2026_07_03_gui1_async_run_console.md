# Cycle Status — 2026-07-03 — GUI-1: Async Run Console

**Agent:** claude (owner-initiated cycle, interactive session)
**Protocol:** AGENT_COORDINATION.md (lock acquired/released; throwaway clone; one task)
**Item:** Roadmap §4.0 GUI-1 (owner directive 2026-07-03)

## Delivered
- `par_model_v2/viewer/igui_job_manager.py` — thread-safe single-flight JobManager (queued/running/succeeded/failed, elapsed, progress, persisted job records, injected runner).
- `scripts/run_gui.py` — `/execute-async` (POST), `/jobs/<id>` + `/jobs` (GET); per-server manager bound in `make_server`, runner reuses gate-check → engine → user-results-refresh pipeline; legacy `/execute` kept.
- `par_model_v2/viewer/igui_run_execution.py` — run page now submits async and polls every 2 s; still fully self-contained (no http/https/src=), run button still gate-disabled by default.
- `.gitignore` — run_output/, user_results/.
- `docs/GUI_RUN_CONSOLE.md` (new track card).

## Verification
- 9 new tests GREEN (`tests/test_gui1_async_run_console.py`): lifecycle, failure/exception, single-flight, persistence, newest-first listing, HTTP round-trip with stubbed engine, 404, page wiring/self-containment.
- Live end-to-end through the real engine (smoke config): submit → running (non-blocking confirmed) → succeeded 5.4 s → real headline + /my-results refresh OK.
- `run_gui.py --self-test` GREEN. IGUI regression suites: 65 passed; 7 failures are PRE-EXISTING on clean main (ui_app.html SHA-256 baseline family, owner-gated Phase 38 re-baseline) — verified identical before/after via git stash.

## Governance
- No governed headline figure changed. ui_app.html untouched. Validation gate semantics unchanged.

## Blockers / owner attention
- Pre-existing: 7 ui_app sha-baseline test failures on main await the owner-gated Phase 38 sha256 re-baseline (not addressed here; out of scope).

## Next queued
- GUI-2: sensitivities & stress in GUI with base-vs-stress deltas.
