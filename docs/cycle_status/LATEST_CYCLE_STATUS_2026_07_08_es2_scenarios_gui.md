# Cycle Status — 2026-07-08 — ES-2 GUI scenario-file upload

**Agent:** Claude Cowork (scheduled `actuarial-model-daily-improvement`)
**Item:** ES-2 — GUI upload page for user economic scenario files (owner-directed track 4.0f, directive 2026-07-08, KCW)
**Outcome:** DONE — track 4.0f now ES-1 DONE / ES-2 DONE / ES-3 OPEN (next queued)

## What shipped

- **`par_model_v2/viewer/igui_scenarios.py`** (new): the ES-2 layer.
  - Stdlib-only at import time (GUI-layer contract); the ES-1 loader and
    numpy are imported lazily inside the builders — regression-tested.
  - `build_scenario_validate_response`: posted CSV + manifest texts are
    written byte-exact (binary) to a temp pair and routed through the REAL
    ES-1 loader (`load_user_scenario_set`); every §4 violation is returned
    as a structured row/column error (capped at 50, exact total preserved).
  - Preview payload on a clean pair: spec §4.6 summary card + percentile
    fans (p5/p25/p50/p75/p95 by projection year) for all 12 rate tenors,
    EQ_RETURN and the cumulative equity index; C-ROSS <2,000 advisory
    warning carried through; UNSIGNED banner everywhere.
  - `build_scenario_save_response`: persists the pair byte-exact under
    `run_output/user_scenarios/<digest12>/` (digest-keyed store like
    CF-2/GD-4 — identical uploads share one copy, a different set never
    overwrites an earlier one; the persisted CSV is re-hashed and must
    reproduce the validated digest, fail-loud) + a preview cache; merges a
    `user_scenarios` provenance block into `model_inputs.json` and POPS any
    recorded `run_gate` — **gate integration**: inputs changed, the Task-6
    gate must re-clear, which binds the block into the run-gate
    reproducibility digest.
  - `build_scenario_status_response`: re-hashes the stored CSV on EVERY
    read; tampered / missing files are reported STALE, never silently
    served.
  - `render_scenarios_html`: self-contained `/scenarios` page (inline SVG
    fan preview with series picker, error table, saved-set card, zero
    external references).
- **`scripts/run_gui.py`**: GET `/scenarios`, GET `/scenario-status`,
  POST `/validate-scenarios`, POST `/save-scenarios`; nav link added
  (`igui_portfolio_builder.NAV_LINKS`).
- **Guards extended:** `/scenarios` added to the nav-on-every-page test and
  the node `--check` inline-script syntax guard.

## Tests

- 19 new tests in `tests/test_es2_scenarios_gui.py` (validation incl.
  row/column surfacing + digest mismatch, persistence + gate reset +
  digest-keyed store dedup, status stale detection for tampered and missing
  files, preview-cache hit/rebuild, live HTTP round-trips over
  `run_gui.make_server`, stdlib-import discipline, self-contained page).
- 292 GREEN this cycle across ES-1/ES-2, GUI-1..5, CF, GD, PC-1/PC-2,
  IGUI task 2/3/5/6 and agent-lock suites.
- 8 pre-existing owner-gated `ui_app.html` sha-baseline failures unchanged
  (verified via stash A/B on clean HEAD) — Phase 38 Task 3 gate, untouched.

## Governance

- Purely additive; no governed headline figure touched (TVOG headline,
  aggregation reports byte-identical — no engine path modified).
- User scenario files remain UNSIGNED scenario inputs; the digest is
  recorded in `model_inputs.json` and enters the run-gate reproducibility
  digest when the gate re-clears.
- Engine consumption (`scenario_source: model|user_file`, risk-neutral /
  real-world measure guard, run governance trail, monthly interpolation
  mapping) is **ES-3** — the next queued item.

## Blockers

None.
