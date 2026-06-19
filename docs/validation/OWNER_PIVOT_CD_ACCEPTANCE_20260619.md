# Owner Pivot — Options C + D Selected & Accepted (2026-06-19)

**Owner decision (interactive, 2026-06-19):** "do C and D" — execute **C (Phase IGUI input+run GUI)** and **D (Packaging / build + CI)**. This **supersedes** the W68–W75 A/B/C/D/E owner-decision heartbeat gate. By selecting **C**, the owner **confirms acceptance of the relaxed zero-install constraint** for the input+run GUI (per the 2026-06-14 owner_direction); the committed zero-install **RESULTS** UI (`ui_app.html`) is unchanged.

## C — Phase IGUI: COMPLETE and end-to-end VERIFIED this session
Phase IGUI Tasks 1–10 + Post-IGUI Tasks 1–8 were built in prior cycles (input GUI, run controls, model points, assumptions, ESG, one-click offline launcher, offline-install appendix, pinned engine). This session verified the **live end-to-end run path** with the engine present (numpy 2.2.6 / scipy 1.15.3 / pandas 2.3.3):

- `scripts/launch_offline_gui.py --self-test --no-browser` → `self_test_ok: true`, `host: 127.0.0.1` (no wildcard / no outbound), `engine.engine_ready: true`. This is exactly the assertion the CI smoke step makes.
- `scripts/run_model.py` (the GUI `/execute` compute step), governed synthetic path, **fast smoke** config (`--n-outer 100 --n-inner 4 --no-tail`) ran the full governed pipeline (standalone → 7×7 var-covar → copula AIC selection → nested benchmark) and wrote the GUI-consumable `RUN_MODEL_AGGREGATION_REPORT.json` (aggregation shape `build_ui_data.py` parses) + `RUN_MODEL_SUMMARY.json`.
  - Smoke headline (NOT a governed figure — reduced sim budget): nested 49,657.9 · gaussian copula 37,499.0 · var-covar 30,267.9. The governed headline 39,975.65 is the 160×24 + tail configuration; the smoke run only proves the input→run→output path executes and is correctly shaped.

**Conclusion:** C is functionally complete and usable on any machine with Python 3.8+ and the pinned engine. No further in-sandbox build work is required for C.

## D — Packaging: AUTHORED + VERIFIED; final build is an owner/CI step by design
Phase PKG Task 1 (Option A frozen binary) + Task 2b (Option B offline wheelhouse) were authored in prior cycles. Verified this session:

- `packaging/actuarial_gui.spec` — PyInstaller spec compiles.
- `packaging/release.workflow.yml` — valid CI workflow (matrix `build` on ubuntu/windows/macos + `release` job; triggers `workflow_dispatch` and `push` tags `v*`).
- `packaging/offline_bootstrap.py --plan-only` — Option-B vendored-wheels plan resolves (stdlib).
- `scripts/build_phase_pkg_task1_validate.py` — structural gate **PASS** (incl. `ui_app_byte_unchanged`, `governed_headline_present`).

**Why the build itself is not produced here (honest constraints):**
1. **Per-OS binaries cannot be cross-built from this Linux sandbox** — a Windows `.exe` / macOS binary must be built on those OSes. That is precisely what the CI matrix is for.
2. **The CI workflow cannot be activated by the dev agent** — installing it to `.github/workflows/release.yml` requires a GitHub token with `workflow` scope, which the automated dev token lacks. This is why it ships as a template under `packaging/`.

### Remaining owner actions to ship installable binaries (one-time)
1. Install the workflow with a `workflow`-scope token:
   `mkdir -p .github/workflows && cp packaging/release.workflow.yml .github/workflows/release.yml` → commit.
2. Build per-OS binaries: push a tag (`git tag v1.0.0 && git push origin v1.0.0`) **or** run the `package-release` workflow from the Actions tab (`workflow_dispatch`).
   - **Or** build locally on any one OS: `python -m pip install pyinstaller==6.11.1 -r requirements-engine-lock.txt && pyinstaller --clean --noconfirm packaging/actuarial_gui.spec` → `dist/Launch_Actuarial_GUI[.exe]`.
3. (Option B alternative, no freezing) vendor wheels once: `python scripts/vendor_wheels.py` (the only networked step), then `python packaging/offline_bootstrap.py` on the air-gapped target.

> Note: `VERSION` still reads "Development complete — NOT cleared for production use." Tagging `v*` triggers a *release* publish; the dev agent did **not** create a release tag autonomously (that overstates production-readiness). The owner controls that gate.

## Net status
- **C:** COMPLETE + end-to-end verified.
- **D:** Build recipe COMPLETE + verified; producing installable binaries is the documented owner/CI step (workflow-scope install + tag/dispatch, or a one-line local build).
