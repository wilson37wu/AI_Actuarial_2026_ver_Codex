# Phase 34 Task 5 (gap H4) - Responsive / small-screen + high-contrast usability pass

**Date:** 2026-06-14T03:22:01Z  **Agent:** claude  **Verdict:** PASS  **Contract:** 1.18.0 (UNCHANGED)

## Scope
Closed gap H4 from the Phase 34 design note. PURE display/markup/behaviour layer:
no model figure is recomputed, `ui_data.json` is untouched, the embedded data
island in `ui_app.html` is **byte-identical** to the prior build (verified by
SHA-256: 1a9aad9b4c50d580...). Contract stays 1.18.0 (no key added or changed).

## What changed in ui_app.html (ADDITIVE only)
1. **Responsive pass** - a `@media (max-width:768px)` block: tighter `.wrap`/header
   padding, `.cards` reflow, and wide tables become independently horizontally
   scrollable (`table{display:block;overflow-x:auto;max-width:100%}`) so the page
   itself never overflows horizontally; `img,svg,canvas` capped at `max-width:100%`.
2. **Reduced motion** - a `@media (prefers-reduced-motion:reduce)` block neutralises
   animations/transitions/scroll-behaviour for users who request it.
3. **High-contrast theme** - a CSS-only `html.hc` variable override (pure black/white
   with `#fff` borders, yellow focus rings) plus a header toggle button.
4. **High-contrast toggle** - persisted via the **URL hash ONLY** (no localStorage /
   sessionStorage; file:// safe). The flag rides as a `&hc=1` suffix on the existing
   tab/section hash. `tabFromHash()` strips the `&...` flag before routing, and the
   three hash writers (G4 tab activation, H2 deep-link) preserve the flag, so a plain
   `#tab` or `#tab~section` hash keeps **exact** prior behaviour.

## Acceptance criteria (all met)
- No horizontal overflow at <=768px (tables scroll within their own container).
- High-contrast toggle is CSS-only, persists via URL hash only, no storage APIs.
- prefers-reduced-motion honoured.
- No regression in rendered figures - every pre-existing self-test check still passes.
- New self-test checks cover responsive media, table overflow-scroll, reduced-motion,
  the toggle (applies/removes class, writes/clears hash, aria-pressed), hash-restore,
  and the flag not breaking G4/H2 tab routing.
- Zero-install preserved: 0 external references across the 3 gated artifacts.

## Gate evidence
- `ui_app_self_test.cjs`: **ok:true, 340 checks, 0 network, 0 JS errors** (+13 H4 checks).
- 9/9 offline suites ok:true (0 network / 0 JS errors): ui_app, offline_viewer,
  combined_gui, userrun-fallback, distribution-fallback, integrity-fallback,
  search-deeplink, bundle-printall.
- External http(s) refs: ui_app.html 0 / model_result_viewer.html 0 / combined_model_app.html 0.
- Stop-rule (Phase 30) honoured; MR-016/MR-017 owner decision not pre-empted.
