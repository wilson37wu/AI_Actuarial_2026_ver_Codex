# Phase 37 — Offline UI: from viewer to interactive decision tool (design note)

**Owner-directed (2026-06-29, interactive):** "devise next phase for enhancement
focusing on user interface." This note is the executable spec. Methodology =
design-note-first (repo convention). One task per auto-cycle.

## Why this phase
- The stochastic **model is complete and frozen** (5-driver G2++, nested 99.5% SCR
  headline 39,975.65; MLMC efficiency frontier complete thru stage 4). The only
  remaining model work — stage-5 default, MR-LONGEV-1 longevity, LSMC — is
  **owner-sign-off-gated**, so the auto-cycle has been idling on maintenance
  heartbeats (W70–W81). Phase 37 gives it real, auto-admissible UI work.
- The offline UI (`ui_app.html`) is a **mature viewer but not a decision tool**:
  zero-install, fully offline, data embedded inline; 5 core tabs (Overview,
  Inventory & Contract, Calibrations, Capital & Tail, Governance) + phase deep-dives
  (P24–P28); PNG/CSV/PDF export; ARIA/keyboard a11y; jsdom-verified 0-network. It
  **displays** pre-computed output but does not let users **explore** it.
- There are **six overlapping HTML surfaces** — `ui_app.html` (744 KB, the rich
  viewer), `offline_home.html` (91 KB, governed 11-graphic home, md5 03d6538d),
  `combined_model_app.html` (456 KB), `model_result_viewer.html` (142 KB),
  `par_projection_gui.html` (86 KB), `model_summary_card.html` (8.5 KB) — with no
  single declared entry point. A user does not know which file to open.

## Hard constraints (every task)
1. **Zero pre-install, fully offline.** No server, no network, no CDN, no build step
   for the end user. Data snapshot embedded inline.
2. **Display-only — consumes ONLY model-output JSON.** The UI must NOT run or
   re-run the stochastic model. Interactive controls do **lookup / slice / scale**
   over the embedded `ui_data.json` snapshot; they never compute a new SCR. Any
   number shown must trace to a value already in the snapshot.
3. **Gated like the rest of the repo.** Each task must keep the jsdom offline
   self-test green (`scripts/ui_app_self_test.cjs` → 0 network calls / 0 JS errors)
   and pass the external-reference scan (no `http(s)://`, `<script src>`, `<link>`,
   `@import`). Bump the `ui_data.json` contract version per task; governed artifacts
   stay byte-stable until an explicit, gate-updated cutover.
4. **Additive + reversible.** Prefer adding a tab/control over rewriting; keep each
   cycle's diff reviewable.

## Task breakdown (one per cycle; Task 1 leads, owner-selected)

### Task 1 (LEAD) — Consolidate to one canonical app + declare the entry point
**Goal:** end the "which file do I open?" confusion before adding features.
- **Canonical = `ui_app.html`** (richest, already gated, already the README's
  subject). Confirm via an inventory of all six HTML surfaces.
- Author `docs/UI_CONSOLIDATION_MAP.md`: for each of the six files, record
  purpose, overlap, and disposition — **keep** (`ui_app.html`), **fold/cross-link**
  (`offline_home.html`'s 11 inline-SVG graphics → surfaced from `ui_app.html`), or
  **deprecate** (`combined_model_app.html`, `model_result_viewer.html`,
  `par_projection_gui.html`, `model_summary_card.html`).
- Add a small, offline, zero-JS **deprecation banner** to each deprecated file:
  "Superseded — open `ui_app.html` for the full interactive report." (Static HTML,
  no redirect script, no network.)
- Add a top-level **entry pointer**: a minimal `index.html` (or update `UI_README`)
  that names `ui_app.html` as THE app and links the rest as archived.
- **Defer** the deeper fold of `offline_home`'s graphics into `ui_app` to a Task 1b
  sub-step so the governed `offline_home.html` md5/177-check gate is only
  re-baselined deliberately (not as a side effect).
- **Acceptance:** `ui_app.html` jsdom self-test stays 0-network/0-error; each
  deprecated file still opens and shows the banner with 0 network; `UI_README.md`
  names the canonical app; `UI_CONSOLIDATION_MAP.md` present; governed artifacts
  byte-unchanged (no `offline_home.html`/`ui_data.json` diff this task), OR, if the
  entry pointer touches a governed file, its validator baseline is updated in the
  same commit and re-passes.

### Task 2 — Interactive Scenario Explorer (lookup, no re-calc)
Controls for the pre-computed option set — {aggregation method, copula family,
management-action set, confidence level, outer-count n} — that instantly display
the matching SCR / VaR / ES / diversification benefit by **looking up** the
embedded grid; A/B side-by-side compare. Pre-req: `build_ui_data.py` emits the
option→result grid into `ui_data.json` (no calculation; it bundles values the model
already produced). Gate: every shown value asserted present in the snapshot.

### Task 3 — Executive one-screen view
Board-ready: headline SCR + units; interactive standalone→var-covar→copula→nested
**waterfall** (diversification benefit + tail uplift on hover); top-5 risks from the
register; a **technical / plain-language toggle** (captions templated from JSON, not
generated). Gate: jsdom + caption-traceability.

### Task 4 — Guided tour + glossary + provenance
Dismissible first-open walkthrough; inline term tooltips (SCR, VaR, ES, TVOG,
copula, diversification); a **provenance badge** (run timestamp, git SHA, contract
version, n_outer×n_inner config) so the snapshot is trustable. Pure presentation.

### Task 5 — Responsive + theme + governance cutover
Tablet/phone responsive layout; light/dark toggle; full a11y + offline-gate re-run;
**`ui_data.json` contract bump**; governed re-baseline (offline_home md5 + 177-check
validator updated in-commit); `UI_README` refresh; ship.

## Out of scope (owner-gated; NOT part of Phase 37)
Any model re-run, model-FORM change, new stochastic driver, copula/aggregation
change, or headline re-baseline. Phase 37 is presentation-only over frozen output.

## Acceptance gates (summary)
`scripts/ui_app_self_test.cjs` 0-network/0-error · external-ref scan clean · per-task
`ui_data.json` contract bump · governed artifacts byte-stable until deliberate,
gate-updated cutover · design-note-first · one task per cycle.
