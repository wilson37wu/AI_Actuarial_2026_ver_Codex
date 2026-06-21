# Cycle Status — 2026-06-16 (claude, 06:00 UTC window)

## Task (exactly one)
Re-baseline the **stale** Phase IGUI Task 10 offline-install gate UI sha → GREEN.
Auto-admissible, non-model-form maintenance (frontier remains OWNER PIVOT).

## What was wrong
`scripts/build_phase_igui_task10_offline_install.py` pinned
`UI_APP_BASELINE_SHA = 6dca35b3…d7e65` — the ui_app.html sha **as of Task 10**, i.e.
*before* the later authorized additive UI panels (Post-IGUI Task 5/8, MR-VR-1/VR-2;
contract → **1.23.0**) advanced the shipped UI to `d82c65ec…fee6`. The Task 10 gate
therefore reported `ui_app_byte_unchanged = False` and `test_gate_passes` /
`test_ui_app_byte_unchanged` were **silently RED on origin/main** — missed by recent
verification windows that did not execute this specific test file (limited test env).

`d82c65ec…` is the authoritative current artifact: it is what the file hashes to, what
the PKG Task1/2b gates and the governance store already record, and it passes every
offline self-test (contract 1.23.0, VR-2 panel, 0 network / 0 JS errors).

## Fix (2 edits, mirrors the 3rd-window stale-pin precedent)
1. `scripts/build_phase_igui_task10_offline_install.py`: `UI_APP_BASELINE_SHA`
   `6dca35b3…` → `d82c65ec…`.
2. `docs/PHASE_IGUI_OFFLINE_INSTALL_APPENDIX.md`: documented shipped-UI sha
   `6dca35b3…` → `d82c65ec…` (keeps `appendix_refs_committed_ui_sha` true **and** makes
   the appendix accurately state the UI users actually install).

`ui_app.html` was **NOT** modified (still `d82c65ec…`, byte-identical).

## Verification (executed fresh this sandbox: node 22 + jsdom, numpy 2.2.6, scipy absent)
- `test_phase_igui_task10_offline_install.py`: **16/16 PASS** (was 2 failed); gate
  `ok=True n_checks=16 failed=[]`.
- JS offline self-tests **ok:true**: ui_app, combined_gui, offline_viewer + 4 fallback
  suites (integrity / distribution / evidence-pack / userrun) — 0 network, 0 JS errors,
  0 external refs.
- Scipy-free sweep: `test_phase36_task5` 8/8, `test_offline_viewer` green,
  `test_phase_pkg_task2b` 7/7 (in isolation). The 2 task2b "failures" seen in a combined
  run are **cross-file test-pollution**, not regressions (pass alone).
- Governed headline **39,975.654628199336** untouched; live contract **1.23.0** unchanged;
  no model parameter / UI-contract change.

## Frontier — UNCHANGED: OWNER PIVOT
No auto-admissible model/UI/packaging work remains. Owner picks ONE:
(a) MR-LONGEV-1 longevity 5th driver [model-form, sign-off];
(b) LSMC SCR proxy [sign-off];
(c) Option-A publish — code-signing cert + channel [owner/infra];
(d) declare the auto-development frontier complete & **freeze**.
