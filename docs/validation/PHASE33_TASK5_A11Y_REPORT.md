# Phase 33 Task 5 - Accessibility & Usability Pass (gap G4)
**Verdict: PASS** &middot; contract **1.17.0 (UNCHANGED, presentation-only; `ui_data.json` byte-identical to HEAD)** &middot; gap **G4** closed.
## What changed
- **Keyboard-operable tab strip**: Arrow/Home/End move the roving-`tabindex` focus; **Enter/Space activate** the focused tab. ARIA `tablist`/`tab`/`tabpanel` roles, `aria-controls` and a single `aria-selected` tab.
- **Tab selection survives reload** via the **URL hash only** (`history.replaceState` -> `location.hash`); **no localStorage/sessionStorage**, so it is `file://` safe.
- **Table captions**: every data table gets a visually-hidden `<caption>` (`.sr-only`) accessible name, re-applied after sub-view re-renders; `:focus-visible` outlines retained.

## Invariants (gated)
- Contract: **1.17.0** (unchanged); `ui_data.json` byte-identical to HEAD: **True**.
- Zero external references: **True**; single file **619,761** bytes; no web-storage APIs: **True**.

## Self-tests (jsdom, out-of-band)
| Suite | ok | checks | network | JS errors |
|---|---|---|---|---|
| ui_app | True | 297 | 0 | 0 |
| distribution_fallback | True | 9 | 0 | 0 |
| userrun_fallback | True | 9 | 0 | 0 |
| offline_viewer | True | 11 | 0 | 0 |
| combined_gui | True | 27 | 0 | 0 |

## Governance
- ChangeRecord `a147cb9df5f14af6ab01988d348dc997` status **OWNER_REVIEW** (OWNER_REVIEW).
- Audit-chain integrity: **True**.

## Next
- Task 6: phase summary + final consolidated re-audit (PHASE 33 COMPLETE).
