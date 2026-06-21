# Phase IGUI - No-Prerequisite Packaging Options (Owner Decision Card)

**Doc id:** PHASE_IGUI_PACKAGING_OPTIONS_CARD
**Version:** 1.0.0
**Phase:** Phase IGUI - Actuarial Input & Run GUI (owner-directed 2026-06-14)
**Task:** Task 9 - phase summary + consolidated re-audit; scope a true no-prerequisite packaging path
**Classification:** educational / owner-decision options note
**Status:** OPEN - awaiting owner decision (nothing built; build tooling + outbound network are not available in the dev sandbox)
**No model parameter changes:** true · **Stop-rule honoured:** true · **MR-016/MR-017 not pre-empted:** true

---

## 1. Decision being asked of the owner

Task 8 delivered a **one-click launcher** (`scripts/launch_offline_gui.py` + OS double-click
wrappers). It removes all *GUI/runner* setup: a non-technical user double-clicks one file, the
input+run GUI opens on `127.0.0.1`, no `pip`, no `PYTHONPATH`, no environment activation.

**One prerequisite remains:** the `/execute` **compute** step spawns the model engine
(`scripts/run_model.py`), which imports **numpy / pandas / scipy**. If those are not present in
the Python that runs the launcher, the GUI loads and validates inputs fine, but pressing **Run**
fails. The launcher *discloses* this up front (`engine_status()` reports numpy/scipy presence) -
it never auto-installs.

This card scopes how to make the **compute** step also need **zero pre-install**, and asks the
owner to choose a path. The three options are mutually exclusive for a given release channel;
they can also coexist (e.g. ship the frozen binary for non-technical users, keep the source path
for actuaries).

---

## 2. Why this cannot simply be built in the current dev cycle

The standing environment constraints make an honest build impossible here, so this is a
**design/scoping note**, not an implementation:

- **No build toolchain:** PyInstaller / a C compiler / platform SDKs are not installed in the
  sandbox and `pip install` fails with **ENOSPC** (`/sessions` is 100% full).
- **No outbound network:** wheels cannot be downloaded to vendor them.
- **Frozen binaries are not cross-built:** a Windows `.exe`, a macOS app, and a Linux binary each
  must be built **on that OS** (ideally in CI runners). The sandbox is a single Linux host.

These are tooling/environment limits, not model limits. The recommendation below is structured so
the owner can green-light the work for a proper CI/release environment.

---

## 3. Option A - PyInstaller (or equivalent) frozen binary  *(recommended for non-technical users)*

Bundle the Python interpreter + numpy/pandas/scipy + the repo into a single self-contained
executable per OS. The user double-clicks `Launch_Actuarial_GUI` with **nothing** pre-installed -
not even Python.

**Mechanics**
- One-time spec: entry point = `scripts/launch_offline_gui.py`; `--add-data` the repo's data
  files (`production_run/`, the `model_inputs` template, the committed `ui_app.html`/`ui_data.json`,
  the `.claude-dev/GOVERNANCE_STORE.json` read-only echo) and the `par_model_v2` package.
- Build **per OS on that OS**, ideally in a CI matrix (GitHub Actions: `windows-latest`,
  `macos-latest`, `ubuntu-latest`). Each job runs PyInstaller and uploads the artifact.
- Ship as a versioned release asset. The binary still binds `127.0.0.1` only and makes no
  outbound call - the offline guarantee is unchanged.

**Pros**
- True zero-install for the end user, **including the compute step**. Best fit for the owner's
  "one button supplies inputs AND computes" goal.
- numpy/scipy versions are pinned into the binary -> reproducibility of the engine is frozen with
  the release (strengthens the governed-headline reproducibility story).
- No change to model code; the binary just wraps the existing launcher.

**Cons / risks**
- Large artifacts (~150-400 MB each because scipy/numpy ship BLAS). Per-OS builds.
- scipy/BLAS sometimes need PyInstaller hidden-imports / hooks; the first build must validate that
  `run_model.py` actually computes inside the frozen binary (a smoke run producing the headline
  39,975.654628199336).
- Code-signing/notarization needed to avoid OS "unidentified developer" blocks (Windows
  SmartScreen, macOS Gatekeeper). This is an org/signing-cert decision, not a code one.
- Antivirus false-positives on unsigned one-file PyInstaller bundles are common.

**Effort:** medium. ~1 cycle to author + validate the spec on Linux; per-OS CI + signing is an
infra/owner task.

---

## 4. Option B - Vendored wheels + bootstrap into a local venv

Ship the platform wheels for numpy/pandas/scipy in a `vendor/` directory; the launcher, on first
run, creates a local `.venv` and `pip install --no-index --find-links vendor/` (offline, from the
bundled wheels only), then runs from it.

**Pros**
- Smaller than a frozen binary if the user already has a matching Python; transparent (real files,
  not an opaque binary); easy to audit which wheel versions are used.
- Still fully offline (`--no-index`); no network at run time.

**Cons / risks**
- **Wheel-matching is brittle:** wheels are specific to OS x CPU arch x Python minor version
  (`cp311` vs `cp312`, `manylinux` vs `macosx_arm64` vs `win_amd64`). To cover common users you
  must vendor a **matrix** of wheels -> large repo footprint and a maintenance burden.
- Requires a Python interpreter to already exist on the machine (so not *truly* zero-prereq).
- First-run venv creation is slower and can fail on locked-down corporate machines.
- Vendoring large binary wheels in git bloats the repo (LFS or a release asset is better).

**Effort:** medium-low to prototype the bootstrap; high ongoing maintenance for the wheel matrix.

---

## 5. Option C - Status quo (disclosed prerequisite) + optional offline installer doc

Keep Task 8 as-is: one-click GUI; the compute step requires a Python with numpy/pandas/scipy,
which the launcher **discloses**. Provide a short offline-install appendix (a pinned
`requirements.txt` + an instruction to `pip install` once, or point at a standard scientific
Python distribution).

**Pros**
- Zero new work, zero new artifacts to maintain, zero signing/AV concerns.
- Actuaries/analysts (the realistic operators of a valuation model) almost always already have a
  scientific Python stack.

**Cons**
- Not "one button computes" for a truly bare machine - the owner's stated end-state is only
  partially met for non-technical users.

**Effort:** ~0 (already shipped; only a doc appendix).

---

## 6. Comparison

| Dimension | A. Frozen binary | B. Vendored wheels | C. Status quo |
|---|---|---|---|
| End-user pre-install for COMPUTE | **none** | Python only | Python + sci stack |
| Offline at run time | yes | yes | yes |
| Per-OS build needed | yes (CI matrix) | wheel matrix | no |
| Artifact size | large (150-400 MB) | medium-large | none |
| Signing / AV exposure | high (needs signing) | low | none |
| Engine-version reproducibility | **frozen in binary** | pinned wheels | user's env |
| Maintenance burden | per-release CI build | wheel matrix upkeep | none |
| Meets "one button computes" | **fully** | mostly | partially |
| Buildable in this sandbox | no (no tooling/net) | no (no net) | already done |

---

## 7. Recommendation

**Primary: Option A (frozen binary) via a CI release matrix, for the non-technical-user channel** -
it is the only option that fully delivers the owner's "press one button to supply inputs AND
compute" end-state and additionally **freezes the numpy/scipy engine version into the release**,
which strengthens reproducibility of the governed headline.

**Keep Option C as the developer/actuary channel** (run from source) so day-to-day model
development is unaffected.

**De-prioritise Option B** unless a frozen binary is rejected for size/signing reasons; its
wheel-matrix maintenance cost is the worst of the three.

**Prerequisite for any build:** a CI/release environment with build tooling, per-OS runners, a
code-signing certificate, and outbound network - none of which exist in the autonomous dev
sandbox. This card requests the owner authorise that environment (or accept Option C as the
shipped end-state).

---

## 8. Guardrails that hold under every option

- Offline/localhost-only (`127.0.0.1`, no outbound network) is preserved.
- The committed zero-install **RESULTS** UI (`ui_app.html`, sha256
  `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65`) stays byte-unchanged; the
  user's own run is rendered into a separate `user_results/` copy (Task 8).
- The compute step still runs **only behind the Task-6 validation/gating** via the Task-7 driver.
- No model parameter change; Phase 30 stop-rule honoured; MR-016/MR-017 owner decision not
  pre-empted.

*Owner action: select A, B, C, or A+C; and, if A or B, authorise a build/release environment.*
