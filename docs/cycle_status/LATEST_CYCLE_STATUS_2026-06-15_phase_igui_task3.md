# Latest cycle status - 2026-06-15 (Phase IGUI Task 3)

**Agent:** Claude Cowork (`auto_actuarial_stochastic_model`), 06:00/18:00 UTC window.
**Cycle:** Phase IGUI Task 3 - model points + in-force ingest (`D2_policy_model_points`).
**Lock:** acquired `claude` (cycle 2026-06-15T01:09Z); released at end.

## What landed

- **`par_model_v2/viewer/igui_model_points.py`** (stdlib only) - editable PAR + GMMB
  model-point rows (the eight canonical Portfolio columns) with fail-loud per-row/field
  normalisation; balance-sheet asset rows + stated-total reconciliation (same tolerance
  the Excel parser uses); a **disclosed, non-governed** book-scaling preview computed
  exactly as `scripts/run_model.resolve_product` reports it (inforce-weighted
  representative PAR point + linear scale factor; GMMB rows disclosed by count); a
  CSV/JSON in-force ingest mapping flexible column/key names onto the Portfolio schema;
  a builder to the `model_inputs.json {portfolio, balance_sheet, totals}` sub-schema; a
  self-contained interactive page; and `validate_task3_gate` (30 checks).
- **`scripts/run_gui.py`** - serves `GET /model-points` (add/edit/delete rows, file
  upload, live reconcile + book-scaling panel; zero external refs) and `POST
  /validate_portfolio /save_portfolio /reconcile /ingest`. Run-controls routes
  unchanged; the `model_inputs.json` merge preserves the Task-2 `{currency,
  run_settings}`. Also repaired a latent truncation: `main()`'s final `return 0` had
  been corrupted to a bare name `retur` by an earlier in-place write.
- **`scripts/load_user_inputs.py`** - additive `validate_portfolio_dict` (no openpyxl),
  same rules as `parse_portfolio` / `parse_balance_sheet`. Excel path unchanged.
- Evidence: `docs/validation/PHASE_IGUI_TASK3_MODEL_POINTS.{json,md}`;
  `scripts/build_phase_igui_task3_model_points.py`; 24 new unittests in
  `tests/test_phase_igui_task3_model_points.py`.

## Gates / tests

- Task-3 gate: **ok, 30 checks**. Localhost self-test: **ok**.
- New unittests: **24** green. IGUI Task-1 (**24**) + Task-2 (**21**) still green.
- 0 new third-party runtime deps; 0 outbound network calls; 0 external refs.
- `ui_app.html` byte-unchanged (sha256 `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65`).
- Contract **1.21.0** unchanged. Governed headline SCR **39,975.654628199336** carried bit-for-bit.

## Governance

- ChangeRecord `9a86cb63` opened, status **OWNER_REVIEW**. Store: change_records 102 -> 103,
  audit 130 -> 131, **risk register frozen at 17**. Audit integrity verified.

## State

- Phase IGUI Task 3 -> **completed**. Next `in_progress` = **Task 4 (assumptions, owner-gated)**.

## Blockers / owner actions

1. **MR-016 / MR-017 dependence decision remains PENDING with the owner** (not pre-empted).
2. **Task 4 (assumptions) is owner-gated**: it must surface assumption inputs + a loader-side
   validator WITHOUT changing any governed/frozen parameter (copula df, grouped-t dfs, Sigma
   stay read-only echo). Confirm scope before the next cycle if any assumption should be writable.
