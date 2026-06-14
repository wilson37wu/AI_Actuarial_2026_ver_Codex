# Consolidated Glossary & Methodology Explainer — Validation Report (Phase 36 Task 3, gap E2)

**Doc** `PHASE36_TASK3_E2_REPORT` v1.0.0 | Phase 36: Offline UI Accessibility Completion & Educational Reproducibility | classification educational | model parameter changes: **NONE** | contract **1.20.0 → 1.21.0 (ADDITIVE)** | result: **PASS**

## Summary

Closed gap **E2** of the Phase 36 design note. Promoted the sign-off-pack-scoped glossary (`owner_decision_p31.glossary`, 9 terms) to a **global, build-time-assembled** glossary / data dictionary covering every governed read-out across the 18 result tabs, surfaced as a new read-only **"Methodology & Glossary"** tab/panel. Display-only and additive: one new top-level key `explainer` is added; every pre-existing `ui_data` key renders bit-identically and the governed headline is unchanged.

## What changed

1. **`ui_data.json` — one new top-level key `explainer`** (additive contract bump 1.20.0 → 1.21.0). It holds 23 glossary terms (the 9 base terms carried **verbatim** plus 14 authored plain-language methodology terms), each with **definition + method/assumption basis + limitation provenance**; an **18-tab coverage map** (tab → primary read-out → terms); and verbatim-carried roots (`glossary`, `limitations`, `standard_references`, `figure_provenance`, `how_to_read`) copied bit-for-bit from `owner_decision_p31`.
2. **Verbatim carry-through.** The 9 base definitions and all limitation text are **copied programmatically** from the embedded payload at build time, so they are bit-for-bit; nothing is re-derived or re-labelled. A build-time self-assertion plus self-test checks confirm `explainer.limitations == owner_decision_p31.limitations`, `provenance.glossary_verbatim == owner_decision_p31.glossary`, and each base term's definition equals its source glossary entry.
3. **Display-only.** The panel contains **no model figure** (authored text is figure-scrubbed at build time; verbatim quotes of already-governed text are exempt) and recomputes nothing. The governed headline `39975.654628199336` and every pre-existing read-out render bit-identically.
4. **Integrity preserved.** The Phase 35 Task 3 (gap A2) per-section SHA-256 digests were recomputed with the **exact embedded JS** (new `explainer` section digested; root digest recomputed) so the in-browser verifier still agrees byte-for-byte. The H1 contract guard and the build pipeline were advanced additively to 1.21.0 (`explainer` appended to the required-keys list; key_count 23 → 24; pipeline layer chain base→1.19→1.20→**1.21**).
5. **New tab/panel.** `TABS` gains `["glossary","Methodology & Glossary"]`; a `#glossary` panel and `renderGlossary()` render the coverage table, the global term table, and the verbatim limitation/standard-reference roots read-only.

## Acceptance criteria (pre-registered in the Phase 36 design note) — all met

- every governed headline term and each tab's primary read-out has a glossary entry (definition + method basis + limitation provenance), assembled only at build time — **met** (23 terms; 18-tab coverage; governed-headline term present)
- limitation text carried bit-for-bit from `owner_decision_p31`; nothing re-derived or re-labelled — **met** (programmatic copy + verified)
- panel display-only; recomputes no model quantity (governed figures bit-identical) — **met**
- ADDITIVE-only contract change; every pre-existing key bit-identical — **met** (only `explainer` added; A2 digests recompute & verify)
- new self-test checks cover global-glossary presence, per-tab coverage, provenance carry-through; suite ok:true 0/0 — **met** (+15 checks)
- `ui_app_self_test.cjs` ok:true, 0 network, 0 JS errors; zero-install + `file://` safe — **met** (393 checks; 0 external refs)
- NO model parameter changes; stop-rule honoured; owner decision not pre-empted — **met**

## Evidence

| Self-test | ok | checks |
|---|---|---|
| ui_app_self_test | true | 393 (+15) |
| offline_viewer_self_test | true | 11 |
| combined_gui_self_test | true | 27 |
| ui_app_userrun_fallback_test | true | 9 |
| ui_app_distribution_fallback_test | true | 9 |
| ui_app_integrity_fallback_test | true | 10 |
| ui_app_search_deeplink_test | true | 18 |
| ui_app_bundle_printall_test | true | 21 |
| **total** | **8/8 ok** | **498** |

All suites: 0 network calls, 0 JS errors. Affected pytests updated and green: `test_phase34_task2_h1_contract_guard.py`, `test_phase35_task3_a2_digests.py`, `test_ui_contract_pipeline_reconcile.py` (21 passed). External references 0; `ui_app.html` 680,314 → 709,036 bytes; `ui_data.json` root digest `85a4f7c2…ac724`.

New self-test checks: `e2KeyPresent`, `e2TabPresent`, `e2PanelRenders`, `e2TabCoverageComplete`, `e2BaseDefinitionsVerbatim`, `e2BaseTermsAllCarried`, `e2LimitationsVerbatim`, `e2GlossaryProvenanceCarried`, `e2LimitationProvenancePerTerm`, `e2GovernedHeadlineTermPresent`, `e2DisplayOnly`, `e2ExplainerDigested`, `e2ContractIs121`, `e2HeadlineBitForBit`, `e2NoAuthoredFigures`.

## Governance

ChangeRecord `514e5c203ac24d2181dc7170452587ff` opened and left in **OWNER_REVIEW** (records 97 → 98, audit 125 → 126, risk register 17, audit integrity OK). PRESENTATION / ADDITIVE-DATA only — the MR-016/MR-017 dependence decision remains PENDING and entirely with the owner.
