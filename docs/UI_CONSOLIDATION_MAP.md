# UI Consolidation Map — Phase 37 Task 1 (2026-06-29)

**Goal:** end the "which file do I open?" confusion across six overlapping offline
HTML surfaces by declaring ONE canonical app and a single entry point, and recording
the disposition of every file. Display-only / zero-install throughout.

## Decision
- **Single entry point: `index.html`** (new) — the front door; links to the canonical
  app and the visual dashboard, and lists the archived views.
- **Canonical application: `ui_app.html`** — the full interactive report (5 core tabs
  + P24–P28 tail-dependence deep-dives; chart/CSV/PDF export; ARIA a11y; jsdom-verified
  0-network). All future UI features (Phase 37 Tasks 2–5) land here.
- **Visual dashboard: `offline_home.html`** — kept as the at-a-glance inline-SVG
  dashboard / card chooser (governed; md5 `03d6538d…`, 177-check validator).

## Disposition table
| File | Size | Role | Disposition | Notes |
|---|---|---|---|---|
| `index.html` | ~6 KB | Entry point | **NEW — keep** | Zero-JS, 0 external refs. Open this first. |
| `ui_app.html` | 744 KB | Interactive report | **KEEP — canonical** | Byte-pinned (sha256 `d82c65ec…`) by PKG/IGUI gates. Untouched this task. |
| `offline_home.html` | 91 KB | Visual dashboard / chooser | **KEEP — dashboard** | Byte-pinned (md5 `03d6538d…`); its validator requires the four files below to exist + resolve. Untouched this task. |
| `combined_model_app.html` | 456 KB | Older combined model+GUI app | **Archive → ui_app.html** | Has a frozen `combined_gui_self_test` (jsdom) suite. In-page banner deferred (see below). |
| `model_result_viewer.html` | 142 KB | Standalone result viewer | **Archive → ui_app.html** | Has a frozen `offline_viewer_self_test` (jsdom) suite. In-page banner deferred. |
| `par_projection_gui.html` | 86 KB | PAR projection GUI prototype | **Archive → ui_app.html** | No test/hash pin. Linked by `offline_home.html`. |
| `model_summary_card.html` | 8.5 KB | One-card headline summary | **Archive → ui_app.html** | No test/hash pin; recommended by the `offline_home` chooser. |

## Why in-page deprecation banners are DEFERRED (not applied this task)
The design note's Task 1 calls for an in-page "superseded" banner on each archived
view. They are **deferred to a governed cutover sub-step** because:
1. `combined_model_app.html` and `model_result_viewer.html` carry **jsdom self-test
   suites** (`combined_gui_self_test`, `offline_viewer_self_test`) that are
   **env-unrunnable in this sandbox** (`node_modules/jsdom` is gitignored/absent), so
   a content change there cannot be re-verified now.
2. `offline_home.html` (byte-frozen) **links to** these files; its validator asserts
   those hrefs resolve. Editing the targets is fine, but the banner wording should be
   introduced together with the `offline_home` cutover so the chooser and the banners
   stay consistent.
This matches the Phase 37 principle: **re-baseline governed artifacts deliberately,
in a gate-equipped step — never as a side effect.** The single entry point
(`index.html`) already routes users to the canonical app, so the consolidation goal
is met now; the banners are polish for the cutover.

## Acceptance (this task)
- `index.html` created: zero `<script>`, **0 external refs** (no `http(s)://`,
  `<script src>`, `<link>`, `@import`) → fully offline.
- Governed artifacts **byte-unchanged**: `ui_app.html` sha256 `d82c65ec…`,
  `offline_home.html` md5 `03d6538d…`, `ui_data.json` contract `1.23.0`.
- No existing HTML modified; no file deleted/renamed (offline_home links still resolve).
- `UI_README.md` names `index.html` as the entry and `ui_app.html` as canonical.

## Follow-ups
- **Task 1b (governed cutover):** add in-page "superseded → ui_app.html" banners to the
  four archived views; re-run/re-baseline their self-test suites in a jsdom-equipped env.
- **Tasks 2–5:** Scenario Explorer → Executive one-screen → tour/glossary/provenance →
  responsive/theme + contract cutover — all in `ui_app.html`.
