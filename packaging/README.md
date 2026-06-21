# Packaging - Option A frozen binary (no-prerequisite COMPUTE)

**Phase PKG Task 1** · status: **authoring only / decision-neutral** · owner A/B/C
choice is **not** pre-empted (see `docs/PHASE_IGUI_PACKAGING_OPTIONS_CARD.md`).

This directory holds the build *recipe* that turns the one-click offline launcher
(`scripts/launch_offline_gui.py`) into a single self-contained executable per OS.
A non-technical user double-clicks one file; **nothing** is pre-installed - not even
Python, numpy or scipy. This closes the last prerequisite the launcher discloses:
the `/execute` **compute** step (which imports numpy/pandas/scipy).

Adding these files changes no day-to-day behaviour: the CI workflow runs **only** on
manual dispatch or a `v*` tag, and nothing here touches the model, the governed
figures, or the committed zero-install RESULTS UI (`ui_app.html`).

## What's here

| File | Purpose |
|---|---|
| `actuarial_gui.spec` | PyInstaller spec: entry = the launcher; bundles numpy/pandas/scipy + `ui_app.html`, `ui_data.json`, `production_run/`, the governance echo and the pinned-stack file. |
| `release.workflow.yml` | CI matrix (ubuntu / windows / macos) **template** that installs the pinned engine + PyInstaller, runs the gate, builds, smoke-tests and uploads the binary; on a `v*` tag attaches binaries to a Release. Shipped here (not under `.github/`) because the automated dev token lacks GitHub `workflow` scope. **Install:** `mkdir -p .github/workflows && cp packaging/release.workflow.yml .github/workflows/release.yml` from a checkout whose token has `workflow` scope, then commit. |
| `../scripts/build_phase_pkg_task1_validate.py` | Stdlib-only structural gate (runs in the sandbox and as the CI pre-build step). |

## Build locally (any one OS)

```bash
python -m pip install pyinstaller==6.11.1 -r requirements-engine-lock.txt
pyinstaller --clean --noconfirm packaging/actuarial_gui.spec
# -> dist/Launch_Actuarial_GUI[.exe]
dist/Launch_Actuarial_GUI --self-test --no-browser   # prints JSON, exits 0
```

`--self-test` resolves the launch plan + engine status and starts no server -
the CI smoke step asserts `self_test_ok==true`, `host=="127.0.0.1"` and
`engine.engine_ready==true`.

## Build via CI

First install the workflow once: `mkdir -p .github/workflows && cp packaging/release.workflow.yml .github/workflows/release.yml` (needs a `workflow`-scope token), commit it. Then push a tag (`git tag v1.0.0 && git push origin v1.0.0`) **or** run the
`package-release` workflow from the Actions tab. Each OS job produces a binary
artifact; a tag build also publishes them as release assets.

## Offline & reproducibility guarantees (unchanged by freezing)

- The binary binds **`127.0.0.1` only** and makes **no outbound call** - identical
  to running from source.
- numpy 1.26.4 / pandas 2.2.3 / scipy 1.13.1 are **frozen into the artifact**
  (`requirements-engine-lock.txt`), so the governed headline SCR
  **39,975.654628199336** - a property of model + numerical stack - is reproducible
  per release.
- No model parameter is set; the binary only wraps the existing launcher.

## Known infra follow-ups (owner / signing-cert decisions, not code)

- **Code signing / notarization** (Windows SmartScreen, macOS Gatekeeper) needs an
  org signing certificate - left as `codesign_identity=None` in the spec.
- Unsigned one-file PyInstaller bundles can trip **antivirus false-positives**; UPX
  is disabled (`upx=False`) to reduce this. `onedir` is a fallback if a runner's
  scipy/BLAS hook needs it.
- Artifact size is ~150-400 MB/OS (scipy ships BLAS) - expected.

## Relationship to the other options

- **Option C (run from source)** stays fully supported and unchanged
  (`requirements-engine-lock.txt` + `docs/PHASE_IGUI_OFFLINE_INSTALL_APPENDIX.md`).
- **Option B (vendored wheels)** is neither added nor foreclosed; it can pin the
  exact same versions.
