# Phase IGUI - Offline-Install Appendix (Option C, decision-neutral)

**Doc id:** PHASE_IGUI_OFFLINE_INSTALL_APPENDIX
**Version:** 1.0.0
**Phase:** Phase IGUI - Actuarial Input & Run GUI (owner-directed 2026-06-14)
**Task:** Task 10 - Option-C offline-install appendix + pinned engine requirements
**Classification:** educational / install documentation
**Status:** decision-neutral. Supports the owner's **Option C** (run from source, see
`docs/PHASE_IGUI_PACKAGING_OPTIONS_CARD.md`) and **pre-empts nothing** - Option A (frozen
binary) and Option B (vendored wheels) remain fully open and can reuse the same pins.
**No model parameter changes:** true - **Stop-rule honoured:** true - **MR-016/MR-017 not pre-empted:** true

---

## 1. What needs installing, and what does not

The application has two clearly separated layers:

| Layer | What it does | Dependencies |
|---|---|---|
| Input GUI + validation/gating + offline RESULTS UI | Enter every valuation input on `127.0.0.1`, clear the gate, browse results | **Python standard library only** - nothing to install beyond Python 3.8+ |
| COMPUTE engine (`/execute` -> `scripts/run_model.py`) | Runs the stochastic model end-to-end and produces YOUR run | **numpy, pandas, scipy** |

So a bare-Python machine can already supply inputs and browse the committed results. The **only**
thing the install below adds is the ability to press **Run** and compute your own numbers.

The one-click launcher (`scripts/launch_offline_gui.py`) detects and **discloses** the engine
state up front via `engine_status()`; it never auto-installs. This appendix is the manual,
fully-offline path to satisfy that one prerequisite when you choose Option C.

---

## 2. The pinned engine (reproducibility anchor)

`requirements-engine-lock.txt` pins the engine to exact versions:

```
numpy==1.26.4
pandas==2.2.3
scipy==1.13.1
```

The governed headline SCR **39,975.654628199336** is a property of the model **and** the
numerical stack underneath it. Pinning the stack is what makes a run-from-source COMPUTE step
**reproducible** rather than merely "works on my machine". `requirements.txt` deliberately keeps
compatible *ranges* (`numpy>=1.26,<3.0`, `pandas>=2.2,<3.0`, `scipy>=1.13,<2.0`) for day-to-day
development; this lock file is the frozen anchor for a valuation run.

**Supported interpreters:** CPython **3.9 - 3.12** (the scipy 1.13.x wheel coverage). Python 3.8
runs the GUI but is below scipy 1.13's floor; use 3.9+ for the compute step.

---

## 3. Install once (then fully offline)

You need outbound network access **once**, only to fetch the three wheels. After that every run
is offline (`127.0.0.1`, no outbound calls).

### 3a. Recommended - isolated virtual environment (does not touch system Python)

```bash
# from the repository root
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-engine-lock.txt
```

### 3b. Or install into the Python you already launch with

```bash
python -m pip install -r requirements-engine-lock.txt
```

### 3c. Air-gapped machine (no network at all)

On a networked machine of the **same OS / CPU arch / Python minor version**, download the wheels:

```bash
python -m pip download -r requirements-engine-lock.txt -d wheelhouse/
```

Copy `wheelhouse/` to the air-gapped machine, then install with no index:

```bash
python -m pip install --no-index --find-links wheelhouse/ -r requirements-engine-lock.txt
```

(3c is essentially a manual, user-driven flavour of packaging Option B; it is offered here only
as a convenience for locked-down sites and does not change the owner's A/B/C decision.)

---

## 4. Verify the engine is ready

```bash
python -c "import numpy,pandas,scipy;print(numpy.__version__,pandas.__version__,scipy.__version__)"
# expect: 1.26.4 2.2.3 1.13.1
```

Or let the launcher tell you (it prints the engine line on start):

```bash
python scripts/launch_offline_gui.py --self-test
# JSON includes: "engine": {"engine_ready": true, "modules": {"numpy": true, "scipy": true}, ...}
```

When `engine_ready` is `true`, the **Run the model end-to-end** button computes your own results;
they appear at `/my-results` in the same offline UI. The committed zero-install `ui_app.html`
(sha256 `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65`) is never modified - your
run is rendered into a separate `user_results/` copy.

---

## 5. Troubleshooting

- **`No module named scipy` when you press Run** - the launcher is using a Python without the
  engine. Activate the venv from section 3a (or install into the launching Python) and restart the
  launcher. The GUI and input entry work regardless; only COMPUTE needs the engine.
- **`pip` fails with no network** - use the air-gapped path (section 3c) from a same-platform machine.
- **A different scipy/numpy is already installed** - the model still runs within the
  `requirements.txt` ranges, but the headline may differ in the last digits; use the pinned lock
  for bit-for-bit reproducibility.
- **Python 3.8** - upgrade to 3.9+ for the compute step (scipy 1.13 floor); 3.8 is fine for the
  GUI/browse layers.

---

## 6. Guardrails (unchanged under this appendix)

- Localhost-only (`127.0.0.1`), no outbound network at run time.
- The committed zero-install **RESULTS** UI stays byte-unchanged; your run lands in `user_results/`.
- COMPUTE runs only behind the Task-6 validation/gating via the Task-7 driver.
- **No model parameter change**; Phase 30 stop-rule honoured; MR-016/MR-017 owner decision not
  pre-empted. This appendix documents an install path only.

---

*This appendix realises the "optional offline installer doc" named under Option C section 5 of
`docs/PHASE_IGUI_PACKAGING_OPTIONS_CARD.md`. Choosing Option A or B later does not invalidate it -
those options can pin the identical versions.*
