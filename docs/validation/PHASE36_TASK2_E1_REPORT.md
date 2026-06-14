# Live-Region Status Announcements — Validation Report (Phase 36 Task 2, gap E1)

**Doc** `PHASE36_TASK2_E1_REPORT` v1.0.0 | Phase 36: Offline UI Accessibility Completion & Educational Reproducibility | classification educational | model parameter changes: **NONE** | contract **1.20.0 (unchanged)** | result: **PASS**

## Summary

Closed gap **E1** of the Phase 36 design note: completed the *dynamic* half of WCAG 2.1 AA (SC 4.1.3 Status Messages) on the zero-install offline UI. Previously `aria-live` was present only on the visible contract-mismatch banner, so dynamic state changes produced no programmatic announcement for screen-reader users. This task adds **one** visually-hidden polite live region and routes four dynamic surfaces through it. Pure ARIA/JS/presentation — **no contract change**, payload byte-identical, every governed figure bit-for-bit.

## What changed (`ui_app.html`, ARIA/JS only)

1. **One dedicated live region** — `<div id="srlive" class="sr-only" role="status" aria-live="polite" aria-atomic="true">`, inserted after the (separate, visible) contract-mismatch banner. It is `sr-only` and never visible.
2. **`announce(msg)` helper** — writes a concise text update to `#srlive` (guarded, never throws). Polite, never `assertive` (no interruption); focus is never stolen.
3. **Four wired surfaces** (each describes *already-on-screen* state; nothing is recomputed):
   - **Tab activation** → "Showing tab: \<name\>". On the **Integrity** tab it also appends the verify outcome ("… Content integrity verified" / "… check: content altered"), because that panel renders once and its status is the meaningful message.
   - **Global search** → "N result(s) for \<query\>".
   - **Distribution Explorer slider** → "Distribution read-out: \<percentile / F(loss) read-out\>".
   - **Content-integrity verifier** → "Content integrity verified" / "check: content altered".
4. **Single announcer** — the inline distribution read-out (`#dx-readout`) loses its own `aria-live` so `#srlive` is the one dedicated announcer for the slider (no double-speak). The visible contract-mismatch banner is unchanged.

## Acceptance criteria (pre-registered in the Phase 36 design note) — all met

- exactly one polite live region, wired to tab activation, search-result count, slider read-out, and integrity verify result — **met**
- announcements describe on-screen state only; announce path computes no model figure (governed **39975.654628199336** bit-for-bit) — **met**
- focus not stolen; no `aria-live="assertive"`; region `sr-only` and never visible — **met**
- ADDITIVE-only; embedded payload byte-identical (Phase 35 A2 per-section SHA-256 digests still verify in-browser by construction) — **met**
- new self-test checks cover region presence + the four wiring points — **met** (+10 checks)
- `ui_app_self_test.cjs` ok:true, 0 network, 0 JS errors — **met** (378 checks)
- zero-install preserved: 0 external references, single self-contained `file://` HTML, no storage API — **met**
- NO model parameter changes; Phase 30 stop-rule honoured; MR-016/MR-017 not pre-empted — **met**
- all eight offline self-tests remain ok:true — **met** (483 total checks)

## Evidence

| Self-test | ok | checks |
|---|---|---|
| ui_app_self_test | true | 378 (+10) |
| offline_viewer_self_test | true | 11 |
| combined_gui_self_test | true | 27 |
| ui_app_userrun_fallback_test | true | 9 |
| ui_app_distribution_fallback_test | true | 9 |
| ui_app_integrity_fallback_test | true | 10 |
| ui_app_search_deeplink_test | true | 18 |
| ui_app_bundle_printall_test | true | 21 |
| **total** | **8/8 ok** | **483** |

All suites: 0 network calls, 0 JS errors. Embedded payload byte-identical (SHA-256 match); contract 1.20.0; external references 0; `ui_app.html` 678,921 → 680,314 bytes.

New self-test checks: `e1LiveRegionPresent`, `e1ExactlyOneLiveRegion`, `e1NoAssertiveAnywhere`, `e1AnnounceFnPresent`, `e1TabAnnounces`, `e1SearchAnnounces`, `e1SliderAnnounces`, `e1IntegrityAnnounces`, `e1HeadlineBitForBit`, `e1DxReadoutNotLive`.

## Governance

ChangeRecord `b274a0e0c43d4cd5affd5affbce45ec9` (code_change) opened **OWNER_REVIEW**; change records 96 → 97; audit entries 124 → 125; risk register 17; audit integrity True. Presentation/ARIA only — the MR-016/MR-017 dependence decision remains entirely with the owner.

## Standards

WCAG 2.1 AA SC 4.1.3 (Status Messages); WAI-ARIA 1.2 (`role=status` / `aria-live=polite` / `aria-atomic`); SOA ASOP 41 (accessible actuarial communications).

## Reproduce

```
python3 scripts/build_phase36_task2_e1_live_regions.py      # idempotent ARIA/JS patch
PYTHONPATH=. python3 scripts/build_phase36_task2_e1_governance.py
node scripts/ui_app_self_test.cjs ui_app.html               # ok:true, 378 checks, 0/0
```

## Next

Phase 36 **Task 3 (gap E2)** — consolidated glossary & methodology explainer surface (ADDITIVE contract bump 1.20.0 → next minor; `explainer` key only).
