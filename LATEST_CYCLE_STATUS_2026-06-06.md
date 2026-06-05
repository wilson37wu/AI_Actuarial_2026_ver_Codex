# Automated Cycle Status - 2026-06-06 (READ FIRST)

## Headline
- Git is usable again: `git status` works, `HEAD` is `0a0228a86a6bc550fad2ec56e4a397bf58a3dce3`, and no `.git/*.lock` files are present.
- The residual combined GUI / governed Projection-mode reference bundle is verified and ready to commit from this shell.
- Phase 18 is now marked complete in `.claude-dev/MODEL_DEV_STATE.json`; Phase 19 Task 1 is active.

## Verified This Cycle
- `node scripts/combined_gui_self_test.cjs combined_model_app.html` -> `ok:true`.
  Projection mode rendered 4 SVG charts, governed model mode rendered 11 SVG charts, Results mode rendered 7 SVG charts, with 0 network calls and 0 JavaScript errors.
- `node scripts/offline_viewer_self_test.cjs model_result_viewer.html` -> `ok:true`.
  Original result viewer rendered 7 SVG charts/export controls, with 0 network calls and 0 JavaScript errors.
- `combined_app_data.json` contains schema `par-combined-app/v1`, Results data, Projection data, and a governed `projection.reference_run` with 240 monthly rows.
  Headline values: PV premiums 579,170.0432; net liability -41,078.9704; asset share at maturity 754,360.8055.
- `.claude-dev/MODEL_DEV_STATE.json` parses as valid JSON after the Phase 18 -> Phase 19 handoff update.

## Current Limits
- Python is not available in this Windows shell (`python`, `python3`, and `py` are absent), so `scripts/build_projection_reference.py` and pytest were not re-run here.
- Existing generated Python-derived artifacts are present and were verified structurally through the Node/JSON checks.
- Untracked write-probe junk remains and should not be committed: `_probe_write_2.tmp`, `_wtest_2`, `_wtest_2.tmp`, and `outputs/_writetest_combined.tmp`.

## Next Automated Cycle
1. If Python is available, run Phase 19 Task 1's Python/pytest health gate in batches.
2. Start Phase 19 Task 2 after the Python gate is green: re-apply the Phase 18 four-driver/copula viewer uplift on the healthy base.
3. Keep the combined GUI bundle committed as a separate verified UI/projection-reference milestone.
