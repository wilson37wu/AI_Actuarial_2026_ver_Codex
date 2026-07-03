# Cycle Status — 2026-07-03 — GUI-3 Calibration Console

**Agent:** Claude Cowork (scheduled task `actuarial-model-daily-improvement`)
**Item:** Roadmap §4.0 GUI-3 — Calibration runs in GUI (owner-directed track, directive 2026-07-03)
**Outcome:** DONE

## What landed

- `par_model_v2/viewer/igui_calibration.py` (new): calibration catalogue
  (`CAL_HW1F_SWAPTION` Phase 13, `CAL_GBM_EQUITY` Phase 14),
  `market_data_status()` over the roadmap-#1 governed pipeline (CNY zero
  curve + CSI 300: as-of, provenance tier, rows, SHA-256, lineage approver,
  UNSIGNED flag), `run_calibration()` into isolated
  `run_output/calibration_<id>/` (diagnostics JSON + pipeline markdown
  report, re-parse guard), and the self-contained `/calibration` console
  page with a permanent UNSIGNED banner.
- `scripts/run_gui.py`: routes `GET /calibration`, `GET
  /calibration-catalogue`, `GET /market-data-status`, `POST
  /run-calibration` (async via the GUI-1 JobManager,
  `meta.kind="calibration"`).
- `par_model_v2/viewer/igui_run_execution.py`: run page links to the
  calibration console.
- `tests/test_gui3_calibration_console.py` (new): catalogue shape,
  market-data provenance, HW1F + GBM end-to-end (parameter card, fit
  diagnostics incl. SSE-proxy = RMSE², gates G-02/G-12/G-03), UNSIGNED
  invariants, **repo governance store byte-identical after runs**,
  engine-unavailable degradation, unknown-id refusal, live server endpoint
  round-trip incl. async job completion.
- `docs/GUI_RUN_CONSOLE.md`: GUI-3 section; roadmap §4.0/§5 updated.

## Fit diagnostics surfaced

HW1F: a, sigma_r, r0 per market; RMSE (bps), SSE-proxy (RMSE², bps²), max
abs error (bps), L-BFGS-B convergence, placeholder flag, data lineage,
gates G-02/G-12. GBM: sigma_S, ERP, dividend yield, rho; historical vs
implied vol, daily observation count, per-market calibration check, gate
G-03.

## Governance

- Every GUI calibration result carries `unsigned: true` + reason (roadmap
  #2 owner sign-off pending; roadmap #1 fixture/cache data tier — no
  owner-approved live vendor source).
- Fresh in-memory GovernanceStore per run; `.claude-dev/GOVERNANCE_STORE.json`
  never read/written (regression-tested).
- No governed headline figure changed; committed `ui_app.html` untouched;
  Phase 38 Task 3 remains owner-gated (this cycle is NOT sign-off for it).

## Tests

New GUI-3 suite GREEN; GUI-1/GUI-2 suites re-run GREEN (see cycle log for
counts). Known pre-existing `ui_app.html` sha-baseline failures on `main`
(owner-gated Phase 38 re-baseline) are unchanged and not caused by this
cycle.

## Next queued

GUI-4 — run history & compare (persisted run registry, side-by-side diff);
the GUI-1 `/jobs` registry and persisted `job_<id>.json` records are the
seed.
