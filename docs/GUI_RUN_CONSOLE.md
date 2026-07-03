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

## GUI-3 (2026-07-03): calibration console

`/calibration` page + `par_model_v2/viewer/igui_calibration.py`. Triggers the governed calibration pipelines against the roadmap-#1 live market-data pipeline and renders fit diagnostics in-page. **Every result is UNSIGNED by construction** (roadmap #2: parameters pend Model Owner approval; roadmap #1: no owner-approved live vendor source is configured — data resolves through the sealed snapshot/fixture tier). The banner and per-result flag are always shown.

| Endpoint | Method | Purpose |
|---|---|---|
| `/calibration` | GET | Calibration console page (market-data panel, run buttons, parameter card, UNSIGNED banner) |
| `/calibration-catalogue` | GET | The two pipelines + engine availability |
| `/market-data-status` | GET | CNY zero curve + CSI 300 via the governed pipeline: as-of, provenance tier, rows, SHA-256, lineage approver, UNSIGNED flag |
| `/run-calibration` | POST | `{"calibration_id"}` → async job (same JobManager, `meta.kind="calibration"`) |

Catalogue: `CAL_HW1F_SWAPTION` (Phase 13 — L-BFGS-B fit of (a, σ_r) per market; RMSE/SSE-proxy/max-error in bps, convergence, gates G-02/G-12) and `CAL_GBM_EQUITY` (Phase 14 — (σ_S, ERP, dividend yield, ρ) per market; observation counts, gate G-03). Diagnostics and the pipeline markdown report persist to an isolated `run_output/calibration_<id>/` directory.

Governance isolation: a GUI calibration run uses a **fresh in-memory GovernanceStore** — the repository `.claude-dev/GOVERNANCE_STORE.json` is never loaded, mutated, or persisted (regression-tested byte-for-byte). Production ESG parameters and governed headline figures are untouched; adopting calibrated parameters requires the owner's signed ChangeRecord outside this console.

## GUI-4 (2026-07-03): run history & compare

`/history` page + `par_model_v2/viewer/igui_run_history.py`. Every GUI-triggered run (model / stress / calibration) is registered from the GUI-1 persisted job records with the reproducibility tuple the roadmap names: run id, timestamps, **inputs digest** (Task-6 reproducibility digest), **seed** + run plan, and **headline outputs**.

| Endpoint | Method | Purpose |
|---|---|---|
| `/history` | GET | Run-history console (registry table, per-run detail, pick-two compare) |
| `/runs` | GET | The persisted run registry, newest first |
| `/runs/<id>` | GET | Open one past run (registry entry + full persisted record) |
| `/compare-runs?a=<id>&b=<id>` | GET | Side-by-side diff: metadata rows + headline deltas (B − A, GUI-2 delta shape) |

Durability: the shared `run_output/` artifacts are overwritten by later runs, so on first sight of a finished job the registry extracts the run plan (seed, scenario budget) from the run's aggregation report while it still exists and persists it back into the job record (additive `registry` block, atomic rewrite, re-parse guard). After that the entry no longer depends on the artifacts. The registry is read-only otherwise: it never deletes records, never touches the governance store, never changes a governed figure. Compare annotates honestly: smoke runs, kind mismatches, and identical-inputs-digest (sampling-only differences) are called out.

## GUI-5 (2026-07-03, owner request): one-click Save & RUN on the Run Controls page

The owner reported that the Run Controls page only wrote `model_inputs.json` — the Run button lived pages away. GUI-5 adds a green **Save & RUN model** button directly on `/` with two checkboxes: *fast smoke run* (default on) and *auto-fill missing sections with governed defaults* (default on).

`POST /save-run` orchestrates the existing governed steps server-side, bypassing nothing: (1) validate + save the posted run controls (same as `/save`); (2) auto-fill ONLY absent domains (model points + balance sheet / assumptions / ESG) through the same builders and validators the dedicated pages use; (3) re-run the Task-6 gate over the assembled file — a BLOCKED gate refuses the run and the page lists every blocking issue with links to the relevant input pages; (4) submit the run as a GUI-1 async job. The page polls `/jobs/<id>`, streams progress, and on success shows the headline with links to `/my-results` and `/history`. The engine re-verifies the gate before spawning, so `/save-run` cannot sidestep governance.

### GUI-5 hotfix (2026-07-03, same day)

Owner reported the button silently did nothing. Root cause: a collapsed backslash escape put RAW newlines inside JS string literals, so the page's whole inline script failed to parse and no click handler was ever attached — the page looked right but was inert. Fixed, and a permanent guard added: `tests/test_igui_page_scripts_syntax.py` runs `node --check` over every inline script of all nine GUI pages, so an unparseable page script can never ship again.

## CF-3 (2026-07-03, owner request): cash-flow projections page

`/cashflows` + `par_model_v2/viewer/igui_cashflows.py`. Renders the CF-track projection set (roadmap §4.0c) as inline-SVG charts (liability premium/expense/benefit/net by year; asset balances stacked by class) and tables (yearly 1–100 per class, or monthly drill-down into any chosen year), with the UNSIGNED banner, book-run-off marker and fund-shortfall callout. `GET /cashflow-data` computes from the SAVED `model_inputs.json`, caches by the CF inputs digest (no re-run while portfolio/balance sheet unchanged) and refreshes the six wide CSVs in `run_output/cashflow_set/`. Zero external references — charts are hand-drawn SVG, no CDN.

## Roadmap

**GUI track COMPLETE:** GUI-1 → GUI-4 all DONE(2026-07-03). The general backlog (roadmap §4.1) resumes next cycle.
