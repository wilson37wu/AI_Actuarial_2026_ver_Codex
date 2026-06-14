# Offline UI Accessibility Completion & Educational Reproducibility — Design Note (Phase 36 Task 1)

**Doc** `PHASE36_TASK1_DESIGN_NOTE` v1.0.0 | Phase 36: Offline UI Accessibility Completion & Educational Reproducibility | classification educational | model parameter changes: NONE | gate: **PASS** (29 checks)

## Standing directive

The stochastic calculation chain is complete. The user interface uses **only** the model's output JSON to display results graphically and interactively, with **no pre-installation requirement** (single self-contained `file://`-openable HTML). Phases 32–35 delivered the zero-install consolidation (P32), interactive analytics & usability (P33), usability hardening (P34), and accessibility & evidence-integrity deepening (P35). This phase continues the standing directive with the next research-driven, **additive-only** offline-UI improvements.

## (a) Baseline audit (measured, frozen as cross-check targets)

- measured at 2026-06-14T14:10:00Z (Claude 18:00 UTC window; lock held, cycle 2026-06-14T14:07Z-2a94)
- `ui_app_self_test`: ok **True**, 368 checks, 0 network calls, 0 JS errors
- `offline_viewer_self_test`: ok **True**, 11 checks, 0 network calls, 0 JS errors
- `combined_gui_self_test`: ok **True**, 27 checks, 0 network calls, 0 JS errors
- `ui_app_userrun_fallback_test`: ok **True**, 9 checks, 0 network calls, 0 JS errors
- `ui_app_distribution_fallback_test`: ok **True**, 9 checks, 0 network calls, 0 JS errors
- `ui_app_integrity_fallback_test`: ok **True**, 10 checks, 0 network calls, 0 JS errors
- `ui_app_search_deeplink_test`: ok **True**, 18 checks, 0 network calls, 0 JS errors
- `ui_app_bundle_printall_test`: ok **True**, 21 checks, 0 network calls, 0 JS errors
- self-test checks total: **473**
- external references across HTML artifacts: **0** (single self-contained file)
- embedded `ui_data` contract: **1.20.0** (24 top-level keys, incl. `contract_manifest.section_digests` + `a11y_audit`)
- tabs (18): Overview, Inventory & Contract, Calibrations, Capital & Tail, Management Actions, Joint Actions (P24), Path-wise Actions (P25), Full Re-Agg (P26), Skew-t Tail (P27), Grouped-t Tail (P28), Vine Tail (P29), Stop-Rule (P30), SCR Comparator (P33), Distribution Explorer (P33), Owner Decision (P31), User Run (UIL), Governance, Integrity (H1)
- artifact: `ui_app.html` 678,921 bytes
- governance store: 96 ChangeRecords, 124 audit entries, 17 risk-register items
- governed headline (carried verbatim, never re-labelled): **39975.654628199336**

### Existing-feature audit (to avoid duplication — measured against `ui_app.html`)

- **Accessibility:** Phase 35 A1 delivered a *static* WCAG 2.1 AA pass — `:focus-visible` on every control, keyboard operability, and a build-time measured contrast-audit table in both themes. **Gap:** `aria-live` is present on **exactly one** surface (the integrity banner, `role="status" aria-live="polite"`). Dynamic state changes — tab activation, search-result counts, slider / percentile read-outs, integrity verify result — produce **no programmatic announcement**, so screen-reader users do not perceive them. The dynamic-content half of WCAG 2.1 AA (SC 4.1.3 Status Messages) is not yet covered.
- **Glossary / methodology:** a `glossary` object exists but is **scoped to the sign-off pack only** ("defines every technical term used [in the pack]"). There is no consolidated, cross-tab glossary / data-dictionary covering every governed read-out and its method/limitation provenance. ~36 inline "methodology" mentions exist but no single educational explainer surface.
- **Export:** per-section CSV exports exist (`inventory.csv`, `risk_register.csv`, `change_records.csv`, `deployment_gates.csv`, `owner_signoff_pack.csv`) plus a chart-PNG export, all via the existing `downloadText` / `downloadBlob` plumbing. **Gap:** there is no single **reproducibility evidence-pack** export that serialises the *exact embedded `ui_data` payload* + `contract_manifest` (incl. `section_digests` + `root_digest`) so a reviewer receives byte-identical, digest-verifiable evidence of what the UI displayed.

## (b) Gap list vs the directive (priority order, ONE gap per cycle)

### E1 (priority 1) — Live-region status announcements (WCAG 2.1 AA SC 4.1.3 completion)

Add a single visually-hidden polite live region (`aria-live="polite"`, `role="status"`, in the existing `sr-only` style) and route dynamic state changes through it: (i) tab activation announces the newly-active tab name, (ii) search announces the result count ("N results for …"), (iii) the Distribution Explorer / any slider announces its current percentile/value read-out (debounced), and (iv) the integrity verifier announces its verified/altered outcome. Announcements are **descriptive of existing on-screen state only** — no model figure is computed in the announcement path. Optionally record the wired surfaces as an additive `a11y_audit.live_regions` evidence list written at build time.

- contract change: **none required** (pure HTML/ARIA/JS). If evidence is recorded: ADDITIVE bump (1.20.0 → 1.21.0) adding `a11y_audit.live_regions` ONLY; every pre-existing key renders bit-identically.

**(c) Pre-registered acceptance criteria:**

- exactly one polite live region exists; tab activation, search-result count, slider/percentile read-out, and integrity verify result each push a concise text update to it
- announcements describe existing on-screen state only; the announcement path computes no model figure (the governed headline 39975.654628199336 and all governed read-outs render bit-identically)
- focus is **not** stolen and no `aria-live="assertive"` is used (no interruption); the region is `sr-only` and never visible
- if `a11y_audit.live_regions` is added it is written ONLY at build time and is display-read-only; ADDITIVE-only — every pre-existing `ui_data` key renders bit-identically
- new self-test checks cover the live-region presence and the four wiring points; suite stays ok:true 0/0
- `ui_app_self_test.cjs` ok:true with 0 network calls and 0 JS errors after the change
- zero-install preserved: 0 external references, single self-contained HTML; `file://` safe (no network, no storage API)
- NO model parameter changes; Phase 30 stop-rule honoured; MR-016/MR-017 owner decision not pre-empted
- all eight offline self-tests remain ok:true

### E2 (priority 2) — Consolidated glossary & methodology explainer surface

Promote the sign-off-pack-scoped `glossary` to a **global, build-time-assembled** glossary / data-dictionary covering every governed read-out across the 18 tabs: each entry carries term, plain-language definition, the method/assumption basis, and the limitation provenance (carried verbatim from `owner_decision_p31.limitations` and the archived design notes — nothing re-derived). Surface it as a read-only "Methodology & Glossary" panel and link key figures to their entry. Display-only; no recompute.

- contract change: ADDITIVE bump (→ next minor) adding an `explainer` (or `glossary_global`) key ONLY; every pre-existing key renders bit-identically.

**(c) Pre-registered acceptance criteria:**

- every governed headline term and each tab's primary read-out has a glossary entry with definition + method basis + limitation provenance, assembled ONLY at build time
- limitation text is carried bit-for-bit from `owner_decision_p31` / archived design notes; nothing is re-derived or re-labelled
- the panel is display-only; it recomputes no model quantity (governed figures render bit-identically)
- ADDITIVE-only contract change; every pre-existing `ui_data` key renders bit-identically
- new self-test checks cover the global glossary presence, per-tab coverage, and provenance carry-through; suite stays ok:true 0/0
- `ui_app_self_test.cjs` ok:true, 0 network, 0 JS errors; zero-install + `file://` safe preserved
- NO model parameter changes; stop-rule honoured; owner decision not pre-empted

### E3 (priority 3) — Single reproducibility evidence-pack export

Add one in-browser action ("Export evidence pack") that serialises the **exact embedded `ui_data` payload** together with `contract_manifest` (including `section_digests` + `root_digest`) and the build/provenance stamp to a downloaded file via the existing `downloadText`/`downloadBlob` plumbing (Blob / data-URI — no network, no storage API, `file://` safe), so a reviewer receives byte-identical, independently digest-verifiable evidence of exactly what the UI displayed.

- contract change: **none** (export reuses the embedded payload and the existing manifest; no new `ui_data` key).

**(c) Pre-registered acceptance criteria:**

- the exported payload bytes equal the embedded `ui_data` bytes; the exported `section_digests`/`root_digest` recompute and match (verified by the existing in-browser verifier and by a dedicated fallback test)
- the export path performs NO network call and uses NO storage API; works under `file://`
- a hash is not a model figure: the governed headline and all governed read-outs render bit-identically; the export recomputes no model quantity
- new self-test checks cover the export control presence and byte/digest equality via a jsdom fallback test; suite stays ok:true 0/0
- `ui_app_self_test.cjs` ok:true, 0 network, 0 JS errors; zero-install preserved
- NO model parameter changes; stop-rule honoured; owner decision not pre-empted

## (d) Execution plan (design-note-first; ONE gap per cycle)

1. **Phase 36 Task 1 (THIS cycle):** research + this design note (baseline frozen, three gaps pre-registered with acceptance criteria, gate PASS). No code/data change.
2. **Phase 36 Task 2:** implement **E1** (live-region announcements), add self-test checks, re-audit.
3. **Phase 36 Task 3:** implement **E2** (consolidated glossary/explainer), additive contract bump, add self-test checks.
4. **Phase 36 Task 4:** implement **E3** (reproducibility evidence-pack export) + fallback test.
5. **Phase 36 Task 5:** phase summary + consolidated baseline re-audit (self-test counts, external-ref scan, contract inventory) → PHASE 36 COMPLETE.

## Invariants honoured

NO model parameter changes · Phase 30 binding stop-rule honoured (dependence-FORM escalation ended; MR-016/MR-017 KEEP_OPEN) · MR-016/MR-017 owner decision not pre-empted · zero-install / single self-contained `file://`-safe HTML preserved · ADDITIVE-only contract changes · every gap surfaces figures bit-for-bit from the embedded payload.
