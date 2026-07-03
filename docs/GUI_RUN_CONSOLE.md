# GUI Run Console (Owner-Directed Track, Roadmap §4.0)

**Document ID:** `GUI-RUN-CONSOLE`
**Created:** 2026-07-03 (GUI-1)
**Owner directive:** 2026-07-03 (KCW) — configure, trigger, and view calculation runs entirely in the GUI; no .py editing.
**Architecture (owner-selected):** local Python web server, stdlib only, `127.0.0.1` only.

## How to launch (no .py editing)

| OS | Action |
|---|---|
| Windows | double-click `launchers/Launch_Actuarial_GUI.bat` |
| macOS | double-click `launchers/Launch_Actuarial_GUI.command` |
| Linux | `launchers/launch_actuarial_gui.sh` |

Flow: input pages (run controls → model points → assumptions → ESG) → validation gate → **Run** → live progress → results at `/my-results`.

## GUI-1 (2026-07-03): asynchronous run execution

Before GUI-1, `POST /execute` ran the engine inside the HTTP request: the browser blocked for the whole run, a dropped connection lost the result, and there was no progress visibility. GUI-1 adds:

| Endpoint | Method | Purpose |
|---|---|---|
| `/execute-async` | POST | Submit a run (`{"smoke": bool}`); returns `job_id` immediately |
| `/jobs/<id>` | GET | Job status: `queued/running/succeeded/failed`, elapsed seconds, progress lines, full engine result on completion |
| `/jobs` | GET | Newest-first job summaries (seed for GUI-4 run history) |
| `/execute` | POST | Legacy synchronous run (kept for compatibility) |

Implementation: `par_model_v2/viewer/igui_job_manager.py` (`JobManager` — thread-safe, single-flight because the engine writes shared `run_output/` artifacts; injected runner keeps it unit-testable). Wiring: `scripts/run_gui.py` (`make_server` binds a per-server manager whose runner reuses the full gate-check → engine → user-results-refresh pipeline). The run page (`render_run_html`) now submits async and polls every 2 s; it remains fully self-contained (no external references).

Job records persist to `run_output/jobs/job_<id>.json` (git-ignored) so a server restart does not erase run history.

## Governance

- The validation gate is unchanged: a run is refused unless the gate is CLEARED; the reproducibility digest is carried into output provenance.
- The committed zero-install `ui_app.html` is never modified; user runs render in a separate user copy at `/my-results`.
- Governed headline figures are untouched by this track.
- Known pre-existing issue (NOT caused by GUI-1): the `ui_app.html` SHA-256 baseline family of tests (7 tests across task2/6/7 suites) fails on `main` pending the owner-gated Phase 38 re-baseline.


## GUI-2 (2026-07-03): sensitivities & stress console

`/stress` page + `par_model_v2/viewer/igui_stress.py`. Each stress deep-copies the gated inputs, applies ONE predefined change, **re-validates and re-gates** the stressed set (the Task-6 gate binds its digest to exact input bytes — it is refreshed, never bypassed), runs the same governed engine into an isolated `run_output/stress_<id>/` directory, and diffs the headline (nested/copula/var-covar SCR + per-driver standalone) against the base run.

| Endpoint | Method | Purpose |
|---|---|---|
| `/stress` | GET | Stress console page |
| `/stress-catalogue` | GET | Predefined stresses + per-input availability + base-run presence |
| `/run-stress` | POST | `{"stress_id", "smoke"}` → async job (same JobManager, `meta.kind="stress"`) |
| `/asset-stress` | GET | Deterministic Phase 9 asset-class stress suite (instant, display-only) |

Catalogue (all input-level, verifiably consumed by `run_model.py`): confidence 99.5→99.0/99.9, sum assured +20%, premium −20%, backing assets +50% (liquidity exposure), seed +1000 (Monte-Carlo sampling error), capital horizon 12→24m. Assumption blocks that do NOT flow into the capital path (lapse/mortality tables feed the liability stage) are deliberately excluded — a zero-delta toggle would mislead; they join with GUI-3+.

Verified live: base 76,988.8 → confidence-99.0 stress 66,297.6 (−13.9%), base artifacts and `/my-results` untouched.

## Roadmap

GUI-2 DONE(2026-07-03) → GUI-3 calibration runs → GUI-4 run history & compare (the `/jobs` registry is the seed).
