# Cycle status — 2026-06-16 (Window #21, claude 18:00 UTC)

**Task executed:** Offline-UI NEXT-EXECUTION POINTER option (c) — "Which view do I want?" chooser on `offline_home.html`.

## What shipped
A goal-oriented view chooser above the existing view cards on `offline_home.html`. Six rows
map a user intent to the matching result view, each a direct link with the view's
Zero-install / Needs-Python badge:

| If you want to… | Open |
|---|---|
| See the headline capital numbers + validation scorecard at a glance / print | Model Summary Card |
| Explore the full governed results in depth (capital, tail, calibrations, governance) | Full Results Explorer |
| Read the same snapshot in a lighter, faster viewer | Result Viewer (light) |
| Open every result surface bundled in one file | Combined Model App |
| Walk through the PAR-endowment projection interactively | PAR Projection GUI |
| Enter your own inputs and run the model end-to-end | Input & Run GUI (Needs Python) |

Built from a single `CHOOSER` list whose every href is build-time-asserted to be a `VIEWS`
entry — chooser and cards cannot drift. Static HTML/CSS only; **no new JS**.

## Invariants held
- `ui_app.html` — BYTE-UNCHANGED (untouched)
- `ui_data.json` — BYTE-UNCHANGED; contract **1.23.0** unchanged
- Governed headline **39,975.654628199336** — intact
- External refs: **0**; new JS: **none**

## Verification (executed)
- `build_offline_home_validate.py` (stdlib): **22/22 ok:true** (was 19/19; +3 chooser gates)
- `offline_home_loader_parity.cjs` (node): **10/10 ok:true**
- `py_compile`: clean (both py scripts); `node --check`: clean (patched self_test.cjs)
- jsdom `offline_home_self_test.cjs`: **UNRUNNABLE in sandbox** (trivial JSDOM load times out, exit 124) — the documented reason the stdlib mirror exists; mirror ran green.

## Files changed
`offline_home.html`, `scripts/build_offline_home.py`,
`scripts/build_offline_home_validate.py`, `scripts/offline_home_self_test.cjs`.

## Next pointer
Option (d): light accessibility / quick-start pass on `offline_home.html` (skip-to-content
link, keyboard reachability, one-line "start here"). MODEL frontier remains OWNER PIVOT.
