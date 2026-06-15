# Phase PKG Task 1 - Option-A frozen-binary build infrastructure

**Status:** authoring only / decision-neutral · owner A/B/C choice **not** pre-empted
· no model/UI change · governance audit-chain preserved.

## Why now
After 4 consecutive owner-pivot-blocked windows, the standing pointer's documented
default is the auto-runnable packaging path. The Phase IGUI Task-9 phase summary
named the **no-prerequisite COMPUTE packaging decision (Option A/B/C)** as the only
residual, and the options card **recommends Option A** (PyInstaller frozen binary
via a CI release matrix). This task authors that recipe - it builds and publishes
nothing by itself.

## What changed
- `packaging/actuarial_gui.spec` - PyInstaller onefile spec wrapping
  `scripts/launch_offline_gui.py`; bundles the numpy/pandas/scipy engine plus the
  verbatim `ui_app.html`, `ui_data.json`, `production_run/`, the governance echo and
  the pinned-stack file. `console=True`, `upx=False` (AV-safety), signing left to
  the owner.
- `packaging/release.workflow.yml` (template; install to `.github/workflows/release.yml` with a `workflow`-scope token) - ubuntu/windows/macos matrix, **manual-dispatch
  or `v*`-tag only** (never a branch push), runs the gate, builds, smoke-tests the
  binary (`--self-test` asserting localhost-only + engine ready), uploads artifacts,
  and on a tag publishes a GitHub Release.
- `scripts/build_phase_pkg_task1_validate.py` + `tests/test_phase_pkg_task1_build_infra.py`
  - stdlib-only structural gate and its unittest wrapper.
- `packaging/README.md` - build/offline/reproducibility/follow-up docs.

## Invariants held
- No model parameter change; no UI contract change.
- `ui_app.html` byte-unchanged (sha256 `d82c65ec…`); governed headline
  **39,975.654628199336** still present in `ui_data.json`.
- Offline guarantee unchanged: the frozen binary binds `127.0.0.1` only, no
  outbound call. Engine pinned (numpy 1.26.4 / pandas 2.2.3 / scipy 1.13.1) so the
  governed headline is reproducible per release.
- Phase 30 stop-rule honoured; MR-016/MR-017 dependence decision untouched.

## Validation
`python scripts/build_phase_pkg_task1_validate.py` -> `ok:true` (25 checks).
`python -m unittest tests/test_phase_pkg_task1_build_infra.py` -> green.
Spec parses (`ast`); workflow parses (`yaml`) and is confirmed manual/tag-only.

## Residual (owner / infra, not code)
Code signing/notarization certificate; AV handling for unsigned onefile bundles;
`onedir` fallback if a runner needs it; publish-channel decision. The actual per-OS
build runs on CI (no build toolchain/network in the dev sandbox).
