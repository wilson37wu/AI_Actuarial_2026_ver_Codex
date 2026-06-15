# PHASE_IGUI_TASK3_MODEL_POINTS (v1.0.0)

**Task:** Phase IGUI Task 3 - model points + in-force ingest  
**Domain:** D2_policy_model_points  
**Generated:** 2026-06-15T01:25:32.112906+00:00

## Acceptance gate

- gate ok: **True** (30 checks)
- new third-party runtime deps: **0**
- outbound network calls: **0**
- localhost self-test ok: **True**
- RESULTS UI (ui_app.html) byte-unchanged: **True** (sha256 `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65`)
- governed headline carried bit-for-bit: **39,975.654628199336**

## Capabilities this cycle

- interactive add/edit/delete of PAR + GMMB model-point rows
- CSV/JSON in-force upload mapped to the Portfolio schema (flexible headers)
- balance-sheet asset rows + stated-total reconciliation (parser tolerance)
- DISCLOSED non-governed book-scaling preview (echoes run_model.resolve_product)

## New localhost runner routes

- `GET /model-points`
- `POST /validate_portfolio`
- `POST /save_portfolio`
- `POST /reconcile`
- `POST /ingest`

## Reconciliation (defaults)

- sum of asset rows: 200000000.0
- stated total: 200000000.0
- reconciles: **True**
- illiquid share: 0.1

## Disclosed book-scaling preview (defaults, NON-GOVERNED)

- PAR rows: 2 ; GMMB rows disclosed: 1
- policy count total: 1500.0
- representative sum assured: 150000.0
- linear scale factor: 1500.0

## Gate checks

- PASS model_points_module_present
- PASS run_gui_present
- PASS loader_present
- PASS model_points_module_stdlib_only
- PASS run_gui_serves_model_points
- PASS run_gui_has_portfolio_endpoints
- PASS run_gui_still_localhost
- PASS loader_has_portfolio_validator
- PASS schema_version_lockstep
- PASS loader_product_enum_lockstep
- PASS loader_gender_enum_lockstep
- PASS pg_product_line_map_present
- PASS defaults_normalise_clean
- PASS defaults_three_rows
- PASS fragment_has_portfolio_and_bs
- PASS fragment_passes_loader_validator
- PASS defaults_reconcile
- PASS mismatch_detected
- PASS book_scaling_par_only
- PASS book_scaling_has_factor
- PASS csv_ingest_two_rows
- PASS json_ingest_one_row
- PASS empty_ingest_fails_loud
- PASS page_carries_headline
- PASS page_has_endpoints
- PASS page_zero_external_refs
- PASS ui_app_byte_unchanged
- PASS live_zero_external_refs
- PASS governance_risk_register_frozen
- PASS governance_change_records_floor
