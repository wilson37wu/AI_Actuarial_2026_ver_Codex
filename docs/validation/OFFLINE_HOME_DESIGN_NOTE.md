# Offline UI — Zero-install Landing Page (`offline_home.html`)

**Cycle:** 2026-06-16 (claude 18:00 UTC window, verification window #18 pivot to build).
**Owner directive served:** standing scheduled-task instruction — *"build a user
interface for offline use … it should not depend on any pre-installation … the
user interface uses ONLY the model output to display the result."*

## Gap addressed
The offline UI matured into **four separate HTML files** (`ui_app.html`,
`model_result_viewer.html`, `combined_model_app.html`, `par_projection_gui.html`)
plus a Python-backed Input&Run launcher. A first-time / non-technical user had **no
single obvious entry point** — they had to know which file to double-click. This is
a pure usability gap, decision-neutral, and squarely inside the owner's offline-UI
directive.

## What was built
`scripts/build_offline_home.py` (stdlib only) reads the model-output snapshot
`ui_data.json` and emits `offline_home.html`: a single, self-contained landing page
that

1. shows **governed headline figures read verbatim** from `ui_data.json`
   (governed headline 39,975.654628199336; nested 99.5% SCR; var-covar SCR;
   standalone sum; diversification benefit; calibrated drivers; gates; tasks) — it
   **recomputes nothing**;
2. links **every offline view** with a Zero-install / Needs-Python badge and a
   one-line description;
3. carries embedded provenance (source `ui_data.json` sha256, contract version) and
   makes **zero network calls**.

## Guard-rails (what this does NOT touch)
- `ui_app.html` is **byte-unchanged** (sha256 `d82c65ec…`); governed headline intact.
- **No `ui_data` contract change** — the landing page is a *separate file*; contract
  stays **1.23.0**.
- No model parameter / model-form change. No governance figure recomputed.
- Zero external references → zero-install preserved (USB / air-gapped).

## Verification (this cycle)
- `scripts/build_offline_home.py` → OK, 0 external refs.
- `scripts/build_offline_home_validate.py` (stdlib gate, env-independent) → **ok:true 14/14**.
- Python `html.parser` structural check → **15/15** (all 5 links, ≥8 figure rows,
  headline + nested + var-covar + standalone all match `ui_data.json` exactly).
- `scripts/offline_home_self_test.cjs` (jsdom: 0-network / 0-JS-error / live DOM) is
  **shipped for CI / owner machines**. It was **NOT runnable in this sandbox** —
  `require("jsdom")` over the read-only virtiofs mount times out (>40 s) and
  `/sessions` is 100 % full with no writable npm cache. This is the same documented
  environment cap that blocks the 744 KB `ui_app` jsdom self-test here; it is **not a
  regression**. Static parity coverage (links/figures/zero-refs) is provided by the
  stdlib gate above.

## Acceptance criteria (pre-registered, all met)
| # | Criterion | Result |
|---|---|---|
| 1 | Single self-contained file, 0 external refs | PASS |
| 2 | Links all 4 result views + Input&Run launcher | PASS (5/5) |
| 3 | Headline figures verbatim from `ui_data.json` | PASS |
| 4 | `ui_app.html` byte-unchanged; contract 1.23.0 unchanged | PASS |
| 5 | No model/governance recompute | PASS |
| 6 | stdlib structural gate green | PASS (14/14) |
