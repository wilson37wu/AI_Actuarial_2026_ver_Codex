# Implementation Plan — Generic Currency + User-Input Loader

**Status:** proposal for your review **before** any model-code change (per your instruction to deliver the manual + template first).
**Companions:** `production_run/MODEL_INPUTS_TEMPLATE.xlsx` (the input contract) and `production_run/USER_MANUAL_run_and_inputs.md`.
**Principle preserved:** no user-specific value is hardcoded; all calibrated/governed parameters keep their existing freeze + governance trail; every change is additive and backward-compatible (current synthetic values become defaults, so nothing breaks if the template is absent).

---

## 0. Current-state facts (measured, not assumed)

- `"CNY"` appears **215 times in code** (`par_model_v2/` + `scripts/`), **18 times in the GUI data** (`ui_data.json` / `ui_app.html`), and is the basis of **6 market-data fixture files**.
- Monetary outputs (SCR, asset MV) are currently shown as **bare numbers** — there is no currency label or symbol anywhere in the display layer.
- "CNY" in code is **two different things**: (a) a *reporting/provenance label*, and (b) a *market identity* tied to real fixture data (CNY government-bond yields, CSI 300 equity, CNY AA+ credit spreads, CNY swaption surface; FX/liquidity use HKD).
- User-specific financials are hardcoded in fixtures, e.g. `backing_asset_mv = 100,000`, `illiquid_share = 0.55`, `forced_sale_fraction = 0.40` (`par_model_v2/calibration/fixtures/hkd_liquidity_exposure_couplings_20260101.json`), and the synthetic 100k-policy book (`par_model_v2/projection/portfolio_generator.py`).

---

## 1. Workstream A — Generic, user-set currency (full re-currency)

Delivered in three layers of increasing depth. Layers A1–A2 are low-risk and self-contained; A3 is the deep "different market" change that needs **your data**.

### A1. Reporting/display currency (single source of truth)
**Goal:** one currency block drives every monetary label; "CNY" no longer hardcoded in the display.
**Changes:**
1. Add a `currency` object to the input contract and to `ui_data.json` `meta`:
   ```json
   "currency": {"code": "USD", "symbol": "$", "decimals": 0, "scale": "units", "thousands": "comma"}
   ```
2. In `scripts/build_ui_data.py`: read `currency` from `model_inputs.json` (fallback to a neutral default), write it to `meta`, and pass it into the embedded HTML.
3. In `ui_app.html` (generated): add one `fmtMoney(value)` helper that formats with the configured symbol/decimals/scale, and route every monetary render through it. Replace the lone `toLocaleString` call and bare-number money renders.
**Effort:** ~1 build script edit + the HTML template block. **Risk:** low (display only). **Test:** the existing `scripts/ui_app_self_test.cjs` (0 network / 0 JS errors) plus a new assertion that the chosen symbol renders and no literal "CNY" remains as a *display* label.

### A2. Calibration-market **label** genericization
**Goal:** nothing hardcodes the string "CNY" as a label; the market name is read from config and defaults to a neutral placeholder.
**Changes:**
1. Introduce a `market_profile` config (code + display label + fixture-prefix), e.g. `{"code": "LOCAL", "label": "Local market", "rates_fixture_prefix": "cny", ...}`. Default keeps the existing fixtures so current behaviour is unchanged.
2. Replace the literal defaults `s.get("market", "CNY")` and the `"CNY"`/`"HKD"` label strings in `par_model_v2/calibration/*` and the build scripts with reads from `market_profile`.
3. Reword provenance prose ("calibrated to CNY swaption data") to use the configured label ("calibrated to {label} swaption data").
**Effort:** moderate — touches ~215 references, but most are mechanical label substitutions concentrated in `calibration/` (market_data_source, calibration_framework, credit/equity/liquidity sources, g2pp_calibrator, phase13_backtest) and a handful of build scripts. **Risk:** low–moderate (no numeric change; pure relabel). **Test:** full pytest regression must stay green; a scan asserts no remaining hardcoded `"CNY"` *label literal* outside the fixture filenames.

### A3. Full re-currency — **different market data** (needs your input)
**Goal:** calibrate the drivers to a genuinely different market (e.g. USD/EUR), not just relabel.
**What this requires from you:** datasets matching the schema of the existing 6 fixtures, for the target market:
| Driver | Fixture to mirror | Data needed |
|---|---|---|
| Rates (HW1F/G2++) | `*_swaption_surface_*.json` | swaption normal-vol surface + a zero/discount curve |
| Rates backtest | `*_backtest_history_*.json` | ≥10y of 1Y government-bond yields |
| Equity (GBM) | `*_equity_history_*.json` | equity index history (returns + ERP) |
| Credit (CIR++) | `*_credit_spread_history_*.json` | AA+ (or chosen rating) OAS history |
| FX / liquidity | the HKD fixtures | FX spot history + liquidity-premium series |
**Changes:** drop the new fixtures in `par_model_v2/calibration/fixtures/` with the target-market prefix, point `market_profile.*_fixture_prefix` at them, then re-run the calibration cycle (each driver has a governed calibrator + gate). **Effort:** large, multi-cycle, and gated by data availability + an independent review. **Risk:** high (new calibration → new SCR) — this is a full model change with its own governance, not an input toggle.
**Recommendation:** ship A1 + A2 now (immediate value, low risk); schedule A3 as its own phase once you provide the target-market datasets.

---

## 2. Workstream B — User-input loader + orchestrator (kill the hardcodes)

### B1. `scripts/load_user_inputs.py` (new)
- Reads `production_run/MODEL_INPUTS_TEMPLATE.xlsx` (openpyxl) by **tab name + header**, validates ranges (shares ∈ (0,1], positive MV, confidence ∈ (0,1), product types in the allowed set, portfolio rows complete), and writes a normalised, schema-versioned **`model_inputs.json`**.
- Fails loudly with a precise message (tab, row, field) on any bad/missing cell; echoes currency, total asset MV, total sum assured, and policy count for a sanity check.
- Pure I/O + validation — no model math, so it is fast and easy to unit-test.

### B2. De-hardcode the fixtures (additive, backward-compatible)
- `par_model_v2/calibration/phase22_liquidity_exposure_calibration.py`: read `backing_asset_mv`, `illiquid_share` (or derive from the asset table), `forced_sale_fraction` from `model_inputs.json` if present; **else** fall back to the current fixture (100,000 / 0.55 / 0.40). The exposure-notional derivation and its gate stay identical.
- `par_model_v2/projection/portfolio_generator.py`: accept a user model-point table from `model_inputs.json` (product, age, gender, term, SA, premium, count, vested bonus); else generate the synthetic book as today.
- `par_model_v2/projection/*` capital path + `JointActionAggregator` driver: take `confidence`, `sigma`, `alpha`, `benefit_share` from the inputs (defaulting to the governed values 0.995 / 0.225 / 0.7567 / 0.8450).
- **No frozen copula/df values become user inputs** — they remain governed and read-only (the template shows them grey).

### B3. `scripts/run_model.py` (new orchestrator)
- Single entry point: `python3 scripts/run_model.py --inputs model_inputs.json`.
- Threads `model_inputs.json` through the existing, already-tested primitives (the Phase 22 Task 4 aggregator → standalone losses → copula aggregation → bootstrap → tail diagnostics) and writes the same `docs/validation/*.json` shape the GUI already consumes — so **`build_ui_data.py` needs no structural change** beyond the currency meta (A1).
- Honours `n_sim`, `seed`, `bootstrap_replicates`, `horizon`, and `output_label` from Run Settings.

### B4. Wire-through to the GUI
- `build_ui_data.py` already bundles `docs/validation/*.json`; after A1 it also stamps the `currency` + `output_label` into `meta`, and the GUI formats accordingly. No new GUI tab required.

---

## 3. File-by-file change summary

| File | Change | Workstream | Risk |
|---|---|---|---|
| `scripts/load_user_inputs.py` | **new** — xlsx → `model_inputs.json` + validation | B1 | low |
| `scripts/run_model.py` | **new** — orchestrator producing result JSONs | B3 | medium |
| `par_model_v2/config/market_profile.py` | **new** — currency + market-label config | A1/A2 | low |
| `scripts/build_ui_data.py` | read currency, stamp `meta`, pass to HTML | A1 | low |
| `ui_app.html` (generated) | add `fmtMoney`, route money renders, drop label "CNY" | A1 | low |
| `par_model_v2/calibration/*` (≈8 files) | market label from config; reword provenance | A2 | low–med |
| `par_model_v2/calibration/phase22_liquidity_exposure_calibration.py` | balance-sheet inputs from config w/ fallback | B2 | medium |
| `par_model_v2/projection/portfolio_generator.py` | user model points w/ fallback | B2 | medium |
| `par_model_v2/calibration/fixtures/<market>_*.json` | **new** target-market data (you provide) | A3 | high |
| `tests/test_user_inputs.py`, `tests/test_currency_format.py` | **new** | A/B | low |

---

## 4. Governance, testing, rollout

- **Backward compatibility:** every change is additive — absent a template, the model runs exactly as today (synthetic defaults). This keeps the full regression suite green and the audit chain intact.
- **Governance:** A2 (relabel) and B (input plumbing) are `code_change` records at OWNER_REVIEW. A3 (re-calibration) is a `methodology_change` per driver with its existing gates — full sign-off needs credentialled data + independent APS X2 review.
- **Tests:** new unit tests for the loader (range/format validation) and the currency formatter; existing pytest regression + the `ui_app_self_test.cjs` offline guarantee (0 network / 0 JS errors) must stay green; an external-ref scan confirms no CDN/script leaks.
- **Suggested rollout (one task per cycle, matching the project's discipline):**
  1. A1 — display currency end-to-end (template field already present).
  2. B1 — input loader + `model_inputs.json` schema + tests.
  3. B2 — de-hardcode balance-sheet + portfolio (with fallbacks).
  4. B3 — `run_model.py` orchestrator + a worked example run.
  5. A2 — market-label genericization + provenance rewording.
  6. A3 — (only after you supply target-market datasets) re-currency calibration phase.

---

## 5. What I need from you to proceed

1. **Approve** A1 + A2 + B (low/medium-risk, no new data needed) to start next cycle.
2. For **A3 (full re-currency)**: confirm the **target market** (e.g. USD, EUR) and whether you can supply the five datasets in §1.A3; otherwise A3 stays parked and the model keeps its current calibration while displaying your chosen reporting currency.
3. Confirm the **template field set** in `production_run/MODEL_INPUTS_TEMPLATE.xlsx` matches how you think about your inputs — add/remove asset classes, product types, or assumption fields as needed and I will align the loader schema.
