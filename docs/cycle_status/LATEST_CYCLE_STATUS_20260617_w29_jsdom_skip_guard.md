# Cycle Status — 2026-06-17 (Window #29, claude)

## Task (one, decision-neutral, auto-admissible — surfaced by verification)
Make the offline-viewer **node/jsdom self-test skip gracefully** when the optional
`jsdom` module is unavailable (fresh clone / clean CI without the gitignored
`node_modules`), instead of hard-failing — bringing the lone offending test in line with
the established pattern already used in `tests/test_phase36_task4_e3_evidence_pack.py`.

## Why
Verification this cycle ran the standing gates + an expanded regression subset
(measure-enforcement, governance, offline_home validate, offline_viewer, agent_lock).
Everything was green **except** one test that hard-failed in the fresh `/tmp` clone:
`tests/test_offline_viewer.py::test_offline_self_test_script_runs_on_rendered_html`.
Root cause: the test invokes a node self-test (`scripts/offline_viewer_self_test.cjs`)
that `require('jsdom')`. `jsdom` lives in `node_modules/`, which is **gitignored** — so it
is present on dev hosts and the mount but ABSENT in any fresh clone / clean CI checkout.
The test already skipped when `node` was missing, but NOT when `jsdom` was missing, so it
produced a **false red** in every clean environment. The repo's other jsdom-backed tests
already skip in this situation (canonical pattern at `test_phase36_task4` ~line 125); this
test was the inconsistent outlier.

## Change (single file: `tests/test_offline_viewer.py`)
1. Set `NODE_PATH` to the repo-root `node_modules` (when present) so jsdom resolves on
   dev hosts / the mount — mirrors `test_phase36_task4`.
2. After the subprocess run, if it failed with `Cannot find module 'jsdom'` /
   `MODULE_NOT_FOUND`, `pytest.skip("jsdom unavailable: …")` instead of asserting.
3. The success path (jsdom present → returncode 0 → the original network/JS-error/export
   assertions) is **logically unchanged**.

No model-form change. No governed-artifact change. No contract change.

## Verification (executed)
- `python -m py_compile tests/test_offline_viewer.py` — clean.
- Fresh clone (no jsdom): `pytest tests/test_offline_viewer.py` → **20 passed, 1 skipped**
  (was: 20 passed, **1 failed**). Skip reason recorded: "jsdom unavailable: …".
- Mount (jsdom present): `node scripts/offline_viewer_self_test.cjs model_result_viewer.html`
  → exit 0 (confirmed this session) — the success path still exercises the real jsdom
  assertions; the slow-host render variance is why the test budgets 90s.
- Standing gates still green: `build_offline_home_validate.py` **28/28** ok:true;
  `test_offline_home_validate` + `test_agent_lock_identity` + `test_measure_enforcement`
  + `test_governance` all pass.
- Governed artifacts BYTE-UNCHANGED: offline_home.html `9bf29b8a8b8faab0ea1c61e539036a37`,
  ui_app.html `818249497e95ff25b8e4dda50d38502e`, ui_data.json
  `70b747a05c00d29bd6e286a7ee4cf42c`; headline 39,975.654628199336; contract 1.23.0.
- Git in a fresh `/tmp` clone per AGENT_COORDINATION.md §5; mount `.git` untouched;
  clone↔mount md5-identical for the patched test (`556b77c6…`).

## Status
Repo green. Auto-admissible offline-UI pool (a–g) + efficiency/diagnostic pool
(MR-CAL-1/VR-1/VR-2) remain EXHAUSTED. Model frontier STILL at **OWNER PIVOT** — no
auto-admissible model/UI/efficiency item open.

## NEXT-EXECUTION POINTER — OWNER PIVOT (unchanged; needs owner decision)
Pick ONE (none auto-starts a model-form change):
1. **MR-LONGEV-1** longevity 5th driver [model-form change, sign-off].
2. **LSMC** proxy [sign-off].
3. **MLMC** nested-loop efficiency [no re-baseline, equivalence-gated — closest to
   auto-admissible of the efficiency options].
4. Resume **Phase IGUI** [non-model; confirm scope].
5. **Packaging A/B/C** / declare frontier complete & **freeze**.
Ranked rationale + decision matrix: `docs/research/MODEL_IMPROVEMENT_RESEARCH_20260617.md`.
Authoritative in_progress pointer = `.claude-dev/MODEL_DEV_STATE.json`.
