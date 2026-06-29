# LATEST CYCLE STATUS — Phase 38 Task 1 (claude, interactive) — 2026-06-29

**Type:** owner-directed interactive session. **Verdict:** PASS.
**Outcome:** asset/liability/net cash-flow + products surfaced to the offline UI as a new self-contained view.

## Owner ask
See asset & liability cash flows separately, add a net cash-flow projection, show tabs of products modelled & tested, and add these to the UI.

## Shipped (additive, display-only, no model-form change)
- `scripts/build_cashflow_products_view.py` — no-calculation bundler.
- `cashflow_products.html` — offline, 0 external refs. **Cash Flows** (Asset / Liability / Net) + **Products** tabs.
  - Net shows BOTH: underwriting (premium − expenses − benefits) and ALM (+ asset investment income), monthly + cumulative.
  - Liability shows guaranteed vs non-guaranteed benefit split.
  - Products: ParEndowment 5/10/20yr + HK reversionary-bonus + HK cash-dividend, mechanics + tested status + model-point schema.
- `index.html` — "Cash Flows & Products" entry card.

## Source & verification
- Source: `docs/validation/PROJECTION_REFERENCE_RUN.json` (governed 20yr PAR-endowment reference run, 240 months).
- node `--check` ✓ · HTML parse ✓ · DOM-shim render-smoke ✓ · data traceability ✓ (every value == source).
- Governed bytes unchanged: `ui_app.html` `d82c65ec…`, `offline_home.html` `03d6538d…`, `ui_data.json` `1.23.0`.

## Why companion page (not in-app tabs yet)
`build_ui_pipeline.py` does not reproduce the frozen `ui_app.html` sha (build timestamp), and the jsdom self-test is env-unrunnable here — so the in-app fold is **Phase 38 Task 3 (gated cutover)**.

## Next
- **Task 2 (auto-admissible):** 5yr & 10yr reference runs + product/term selector in `cashflow_products.html`.
- **Task 3 (gated):** fold Cash Flows + Products + Phase 37 Scenario Explorer into `ui_app.html` (jsdom env + sha re-baseline + contract bump).
Authoritative pointer = `.claude-dev/MODEL_DEV_STATE.json`.
