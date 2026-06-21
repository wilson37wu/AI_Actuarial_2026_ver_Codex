# Option B - Fully-offline vendored-wheels install (no-network COMPUTE engine)

This is **Option B** of `docs/PHASE_IGUI_PACKAGING_OPTIONS_CARD.md`: give a user the
numpy/pandas/scipy **COMPUTE engine** with **zero network access** and **no global
install**, by vendoring the exact pinned wheels into a local `wheelhouse/` and
installing them into a throw-away virtual environment with `pip --no-index`.

It sits beside the other two packaging paths and **forecloses neither**:

| Option | What it removes | Build step | Owner inputs |
|---|---|---|---|
| A - frozen binary (`packaging/actuarial_gui.spec`) | Python prerequisite entirely | CI/PyInstaller (per-OS) | code-signing cert, publish channel |
| **B - vendored wheels (this)** | network + global install | one `pip download` harvest | none |
| C - run from source (`requirements-engine-lock.txt`) | nothing (documents the prereq) | none | none |

The input GUI, validation/gating chain and the offline **RESULTS UI stay pure stdlib**
and need none of this; Option B only provisions the second layer - the `/execute`
COMPUTE step (`scripts/run_model.py`).

## Two steps, one of them networked

**Step 1 (networked, run ONCE by an owner/CI on a networked machine):** harvest the
pinned wheels into `wheelhouse/`.

```
python3 scripts/vendor_wheels.py
# cross-platform (one wheelhouse per target), e.g. a CI matrix:
python3 scripts/vendor_wheels.py --platform manylinux2014_x86_64 --python-version 312
python3 scripts/vendor_wheels.py --platform win_amd64          --python-version 312
python3 scripts/vendor_wheels.py --platform macosx_11_0_arm64  --python-version 312
```

This is the **only** step that touches the internet. It is a thin, auditable wrapper
over `pip download --only-binary :all: -r requirements-engine-lock.txt`. Ship the
populated `wheelhouse/` next to the repo (USB stick, internal share, release asset).

**Step 2 (fully offline, run by the user, no network):** create the venv and install
from the local wheelhouse only.

```
python3 packaging/offline_bootstrap.py            # creates .venv_engine, installs offline
python3 packaging/offline_bootstrap.py --status   # is the wheelhouse usable?
python3 packaging/offline_bootstrap.py --plan-only # show the exact pip argv, do nothing
```

The planned install is always `pip install --no-index --no-build-isolation
--find-links wheelhouse -r requirements-engine-lock.txt` - `--no-index` is the
offline guarantee (pip is never allowed to consult PyPI or any remote index).

Then activate the venv and start the one-click launcher:

```
. .venv_engine/bin/activate      # Windows: .venv_engine\Scripts\activate
python3 scripts/launch_offline_gui.py
```

## Offline guarantee (verified by the gate)

`python3 packaging/offline_bootstrap.py --self-test` proves, by introspection and
without creating a venv, that the planned install forces `--no-index`, resolves only
from a local `--find-links` directory, targets the pinned requirements, and contains
no `http(s)://` or `--index-url` token. `scripts/build_phase_pkg_task2b_validate.py`
wraps that plus the structural checks and re-asserts the governed RESULTS UI
(`ui_app.html`) is byte-unchanged and the governed headline is intact.

## Reproducibility

The wheels are the *exact* pins in `requirements-engine-lock.txt`
(numpy==1.26.4 / pandas==2.2.3 / scipy==1.13.1), so the governed headline SCR
**39,975.654628199336** is reproduced bit-for-bit by a from-wheelhouse install on a
matching interpreter. For hash-pinned integrity, regenerate the lock with
`pip-compile --generate-hashes` in a networked CI environment (no network in the
autonomous dev sandbox to harvest hashes).

## What this task did NOT do

No wheels are vendored in-repo (they are large, platform-specific binaries; the
harvest is the owner/CI step above). No model parameter changed; no UI contract
changed; `ui_app.html` is byte-identical to the certified baseline. Decision-neutral:
Options A and C remain fully available.
