# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec - Phase PKG Task 1 (Option A, owner-decision card recommended).

Freezes the *one-click offline launcher* (``scripts/launch_offline_gui.py``)
plus the numpy/pandas/scipy compute engine into a single self-contained
executable, so a non-technical user can run the Actuarial Input & Run GUI -
INPUTS, validation/gating AND the end-to-end COMPUTE step - with NOTHING
pre-installed (not even Python).

This spec is AUTHORING ONLY. It builds nothing in the dev sandbox (no build
toolchain / no network there); it is validated structurally by
``scripts/build_phase_pkg_task1_validate.py`` and exercised by the CI release
matrix (``.github/workflows/release.yml``) on windows/macos/ubuntu runners.

Invariants this spec preserves (see PHASE_IGUI_PACKAGING_OPTIONS_CARD.md):
  * The frozen app binds ``127.0.0.1`` ONLY and makes no outbound call - the
    offline guarantee is identical to running from source.
  * No model parameter is changed; the binary just wraps the existing launcher.
  * Pinning numpy/pandas/scipy into the artifact FREEZES the numerical stack
    with the release, strengthening the governed-headline reproducibility story
    (governed SCR 39975.654628199336 is a property of model + stack).
  * The committed zero-install RESULTS UI (``ui_app.html``) is bundled VERBATIM.

Build locally (any single OS):
    python -m pip install pyinstaller==6.11.1 -r requirements-engine-lock.txt
    pyinstaller packaging/actuarial_gui.spec
Result: dist/Launch_Actuarial_GUI[.exe]  (onefile)
Smoke:  dist/Launch_Actuarial_GUI --self-test --no-browser   # prints JSON, exit 0
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ``SPECPATH`` is injected by PyInstaller; repo root is its parent.
REPO = os.path.abspath(os.path.join(SPECPATH, os.pardir))

ENTRY = os.path.join(REPO, "scripts", "launch_offline_gui.py")

# --- runtime data the GUI / runner reads (repo-relative -> bundled root) -------
# Only files that exist are bundled; each tuple is (src_abs, dest_dir_in_bundle).
_DATA_CANDIDATES = [
    ("ui_app.html", "."),                       # zero-install RESULTS UI (verbatim)
    ("ui_data.json", "."),                       # governed UI payload
    ("production_run", "production_run"),         # input template + user manual
    (os.path.join(".claude-dev", "GOVERNANCE_STORE.json"), ".claude-dev"),
    ("requirements-engine-lock.txt", "."),       # pinned-stack provenance echo
]
datas = []
for rel, dest in _DATA_CANDIDATES:
    src = os.path.join(REPO, rel)
    if os.path.exists(src):
        datas.append((src, dest))

# --- engine + dynamically-imported runner modules -----------------------------
# launch_offline_gui.py does ``import run_gui`` after putting scripts/ on sys.path,
# so PyInstaller's static analysis cannot see it: pull the runner + loader and the
# numpy/pandas/scipy stack in explicitly.
binaries = []
hiddenimports = [
    "run_gui",
    "load_user_inputs",
    "run_model",
]
for pkg in ("numpy", "pandas", "scipy"):
    p_datas, p_binaries, p_hidden = collect_all(pkg)
    datas += p_datas
    binaries += p_binaries
    hiddenimports += p_hidden
# par_model_v2 is importable as a package; collect its submodules too.
hiddenimports += collect_submodules("par_model_v2")

block_cipher = None

a = Analysis(
    [ENTRY],
    pathex=[REPO, os.path.join(REPO, "scripts")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest", "IPython", "notebook"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Launch_Actuarial_GUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX off: avoids AV false positives on scipy/BLAS
    runtime_tmpdir=None,
    console=True,              # console so engine/offline status is visible
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,    # signing/notarization = owner/infra decision
    entitlements_file=None,
)
