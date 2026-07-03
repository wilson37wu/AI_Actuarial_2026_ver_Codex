# Cycle Status — 2026-07-03 — GUI-5 Hotfix: Run-Button JS Syntax + Guard

**Agent:** Claude Cowork (owner-triggered interactive cycle)
**Item:** Owner report: "i click the run button but i cannot tell if
anything is running" — the GUI-5 Save & RUN button was inert.
**Outcome:** DONE (hotfix + permanent guard)

## Root cause

The GUI-5 patch wrote the page's new JS with single-backslash `\n` escapes;
the module's triple-quoted Python template turned them into REAL newlines
inside single-quoted JS string literals. The browser rejected the whole
inline script (SyntaxError), so no click handler was attached — the page
rendered correctly but every button wired by that script did nothing, with
no visible error. Unit tests passed because they checked substrings of the
HTML, not JS parseability.

## Fix + guard

- `par_model_v2/viewer/igui_run_controls.py`: 21 collapsed escapes doubled;
  served script now passes `node --check`.
- `tests/test_igui_page_scripts_syntax.py` (new): extracts every inline
  <script> from all nine GUI pages (run controls, model points,
  assumptions, ESG, run gate, run execution, stress, calibration, history)
  and runs `node --check` on each. A regex-based pure-Python fallback was
  evaluated and rejected (JS string grammar is not regex-checkable; a
  flaky guard is worse than none).

## Verification

- Served page script (over HTTP) passes `node --check`.
- Live e2e re-run: one click equivalent (`POST /save-run`, seed 45, smoke,
  autofill) → gate CLEARED → engine run succeeded → headline rendered
  (diagnostic smoke figure).
- Suites: gui5 8/8, page-scripts guard green, task2 run-controls 19 passed
  + the 2 pre-existing owner-gated sha-baseline failures (unchanged).

## Next queued

General backlog §4.1 #2 — HW1F calibration on live/proxy quote set.
