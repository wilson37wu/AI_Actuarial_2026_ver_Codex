# Cycle status — 2026-06-15 — Phase IGUI Task 2

**Owner:** claude (Cowork auto-dev, 06:00 UTC window)
**Task:** Phase IGUI Task 2 — run controls + stdlib local-runner scaffolding (`D1_run_controls`)
**Status:** COMPLETE
**Lock:** acquired (`2026-06-15T00:08Z-3ebc`), released at end of cycle.

## What landed

A standard-library-only local runner for the owner-directed input+run GUI, plus the run-controls layer it serves and the loader-side validation it round-trips through.

- `scripts/run_gui.py` — stdlib `http.server` (`ThreadingHTTPServer`) bound to `127.0.0.1`; serves a self-contained run-controls page (zero external references) and exposes `GET /`, `GET /healthz`, `POST /validate`, `POST /save`. No third-party runtime dependency; no outbound network call. `--self-test` does an in-process localhost GET/POST round-trip.
- `par_model_v2/viewer/igui_run_controls.py` — declarative run-control field spec, payload normalisation, a builder to the `model_inputs.json` `{currency, run_settings}` sub-schema, a deterministic per-run `sha256` reproducibility digest, the self-contained form renderer, and `validate_task2_gate` (21 checks).
- `scripts/load_user_inputs.py` — **additive** `validate_run_controls_dict()`: validates the `{currency, run_settings}` fragment with the SAME rules as the Excel template parsers (no `openpyxl` needed). The Excel path is unchanged.

This closes the Task-1 `D1_run_controls` gaps: explicit valuation date, explicit projection **step**, explicit **outer/inner** scenario split, and a surfaced **per-run reproducibility digest**.

## Verification

- 21 new unittests green (`tests/test_phase_igui_task2_run_controls.py`) — normalisation, loader round-trip incl. rejection cases, self-contained form, a real localhost GET/POST round-trip, and the Task-2 gate.
- Task-2 gate `ok:true` / 21 checks (stdlib-only imports, localhost bind, loader-validator presence + enum/schema lock-step, digest determinism, form headline + zero external refs, `ui_app.html` byte-unchanged via frozen sha256, governance floors).
- Task-1 suite still green (24).
- `ui_app.html` byte-unchanged: sha256 `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65`. The nine offline self-tests are unaffected (RESULTS UI not touched).

## Discipline

0 new third-party runtime deps · localhost-only / offline · NO contract change (1.21.0) · NO model parameter change · Phase 30 stop-rule honoured · MR-016/MR-017 owner decision not pre-empted · governed headline `39,975.654628199336` carried bit-for-bit.

## Governance

ChangeRecord `0c8ab61a1001440cac5f6657942f8616` (OWNER_REVIEW). Store: change_records 101→102, audit 129→130, risk register 17 (frozen). Audit integrity verified.

## Next

Phase IGUI Task 3 — model points + in-force ingest (`D2_policy_model_points`): interactive add/edit/delete of PAR + GMMB rows and a CSV/JSON in-force upload path mapping to the Portfolio schema; balance-sheet reconciliation surfaced; RESULTS UI stays byte-unchanged.
