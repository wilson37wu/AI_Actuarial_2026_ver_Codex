# Phase PKG Task 2 (Option B) — Offline vendored-wheels venv bootstrap

**Doc id:** PHASE_PKG_TASK2B_OFFLINE_WHEELHOUSE · **Version:** 1.0.0 · **Date:** 2026-06-16
**Phase:** Phase PKG — No-prerequisite packaging (owner-decision card, Option B)
**Agent:** ClaudeCowork_AutoDev · **Classification:** build-infrastructure / authoring-only / decision-neutral
**No model parameter change:** true · **UI contract change:** false · **Stop-rule honoured:** true · **MR-016/MR-017 pre-empted:** false

## What landed
Option B of `docs/PHASE_IGUI_PACKAGING_OPTIONS_CARD.md`: a **fully-offline** install of the
numpy/pandas/scipy COMPUTE engine via vendored wheels — no network, no global install.

- `packaging/offline_bootstrap.py` (stdlib): creates a venv and installs the pinned engine with
  `pip install --no-index --no-build-isolation --find-links wheelhouse -r requirements-engine-lock.txt`.
  `--no-index` is the offline guarantee. Modes: default bootstrap, `--status`, `--plan-only`, `--self-test`.
- `scripts/vendor_wheels.py` (stdlib): the **single networked** harvest step — a thin `pip download
  --only-binary :all: -r requirements-engine-lock.txt -d wheelhouse` wrapper with `--platform` /
  `--python-version` passthrough for a cross-OS CI matrix; `--print-argv` for the no-network gate.
- `scripts/build_phase_pkg_task2b_validate.py` (stdlib): structural gate (loads the bootstrap module,
  asserts the planned argv forces `--no-index`/`--find-links`/pinned-reqs and carries no remote URL,
  runs its `--self-test`, checks the vendor wrapper + docs, and re-asserts `ui_app.html` byte-unchanged
  and the governed headline present).
- `tests/test_phase_pkg_task2b_offline_wheelhouse.py`: 7 stdlib unittests.
- `packaging/OPTION_B_README.md`: two-step walkthrough (networked harvest → offline install).

## Verification (run this cycle)
- **offline_bootstrap `--self-test`: ok:true** — planned install forces `--no-index`, local
  `--find-links` only, pinned requirements, **no `http(s)://` / `--index-url`** in the plan.
- **Structural gate: ok:true, 20/20.**
- **Unittest: 7/7 OK.**
- **Governed RESULTS UI `ui_app.html` byte-unchanged** (sha256 `d82c65ec…`); governed headline
  **39,975.654628199336** present; contract **1.23.0** unchanged.

## Discipline / scope
Authoring-only: **no wheels vendored in-repo** (platform-specific binaries; the harvest is the
owner/CI step) and **nothing built or installed in the dev sandbox** (no outbound network), mirroring
how Option A's binary is built in CI rather than in-cycle. **Decision-neutral:** Options A (frozen
binary) and C (run from source) remain fully available; this only completes the A/B/C menu so the
owner can adopt any one. No model/UI/contract change; Phase 30 stop-rule honoured; MR-016/MR-017 not
pre-empted.
