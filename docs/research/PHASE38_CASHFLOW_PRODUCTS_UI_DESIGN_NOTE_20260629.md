# Phase 38 — Asset / Liability / Net Cash-Flow & Products in the UI (design note)

**Owner-directed (2026-06-29, interactive):** "I also want to see cash-flow projection from
asset and liability separately, add a net cash-flow projection, and show tabs with the products
being modelled and tested — add these to the UI." Display-only, zero-install (owner's standing rule).

## Finding — most of this already exists in the engine
`par_model_v2/projection/monthly_projection.py` already computes, monthly:
- **Liability cash flows** — premium, expenses (acq/renewal), death (guar `dG` + non-guar `dN`),
  maturity (`mG`/`mN`), surrender (`sv`), and a **liability-side net** `ncf = premium − expenses − benefits`.
- **Asset cash flows** — by class: Govt (`gC`+`gM`), Credit (`cC`+`cM`), Equity (`eD`+`eG`), Cash (`ci`),
  total income `ti`, fund market value `fmv`.
- **Asset share** roll-forward (70/30 profit share).
The governed reference run is persisted at `docs/validation/PROJECTION_REFERENCE_RUN.json` (20yr PAR
endowment, age 40 M, SA 1,000,000, prem 60,000). **Products:** ParEndowment (5/10/20yr) + HK participating
(reversionary-bonus, cash-dividend). **Gap:** none of it reached the UI (`ui_data.json` was SCR/capital/tail only).

## What "net cash flow" means here (owner: BOTH views)
- **Underwriting net** = premium − expenses − benefits (the engine `ncf`).
- **ALM net** = underwriting net + asset investment income (`ti`) — the asset-vs-liability liquidity view.

## Task 1 (DONE this session) — Cash Flows & Products offline view
`scripts/build_cashflow_products_view.py` (a **no-calculation bundler**, same philosophy as `build_ui_data.py`)
reads `PROJECTION_REFERENCE_RUN.json` + the product catalogue and emits **`cashflow_products.html`**:
self-contained, **0 external refs**, fully offline. Tabs:
- **Cash Flows** → **Asset** (income by class + FMV), **Liability** (premium/benefits/expenses + net, plus a
  guaranteed-vs-non-guaranteed split), **Net** (underwriting + ALM, monthly and cumulative), each with inline-SVG
  charts and a PV-summary KPI strip.
- **Products** — ParEndowment 20yr (reference, charted), 5/10yr variants, HK reversionary-bonus, HK cash-dividend:
  mechanics, key parameters, tested status, and the model-point schema.
Linked from `index.html`. **Verification:** node `--check` clean; HTML stdlib-parsed; **DOM-shim render smoke PASS**
(all 4 panels populate, charts emit SVG); **data traceability PASS** (every series/PV equals the source JSON);
governed artifacts byte-unchanged (`ui_app` sha256 `d82c65ec…`, `offline_home` md5 `03d6538d…`).

## Why a companion page, not tabs inside ui_app.html (this session)
A rebuild of the byte-pinned canonical `ui_app.html` could not be **verified** here: (1) `build_ui_pipeline.py`
does NOT reproduce the governed file byte-for-byte (it embeds a fresh build timestamp → sha `82940e58…` ≠
governed `d82c65ec…`), so any rebuild forces a sha re-baseline across ~10 governance/gate scripts; and (2) the
authoritative offline self-test `scripts/ui_app_self_test.cjs` needs **jsdom**, which is absent in this sandbox.
Shipping an unverifiable rebuild of the governed app would violate its own gate. The companion page delivers the
feature now, fully verified, and is reachable from the single entry point.

## Roadmap
- **Task 2 (next, auto-admissible):** generate 5yr & 10yr PAR-endowment reference runs via
  `run_full_projection` (persist as governed CF JSON) and add a product/term selector to `cashflow_products.html`
  so the user can switch the charted product. Stays display-only + traceable.
- **Task 3 (gated cutover, jsdom-equipped env):** fold Cash Flows + Products (and the Phase 37 Scenario Explorer)
  into `ui_app.html` as native tabs via a new `build_ui_pipeline.py` layer; re-baseline the pinned sha256 + bump
  the contract; run the jsdom self-test (0-network/0-error) before publishing.

## Acceptance (this task) — all met
0 external refs · node-check + render-smoke + traceability PASS · governed bytes unchanged · linked from `index.html`.
