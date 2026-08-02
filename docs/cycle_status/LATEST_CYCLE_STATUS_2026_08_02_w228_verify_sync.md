# LATEST CYCLE STATUS — W228 — 2026-08-02T18:10Z

**Cycle:** W228 · **Owner:** claude (Cowork) · **Cycle-id:** `2026-08-02T18:10Z-3da0`
**Type:** exhausted-backlog verification + mount-sync + hand-off/research refresh (SKILL-sanctioned branch) — **FULL BATTERY (via venv-reuse)**
**Task pointer:** Phase 38 Task 3 (ui_app.html native-tab cutover) — **OWNER-GATED, not executed**

## Conclusion first
Model is unchanged and **byte-stable**; the working folder is synced to `origin/main`. This is the
**35th consecutive** cycle with **no auto-admissible model work** — Phase 38 Task 3 and the entire
model-FORM backlog remain owner-gated. **Unlike W227 (which ran DEGRADED and could not run Gate C or
the MLMC suite), this cycle ran the FULL verification battery and it is GREEN** — achieved by
**reusing a pre-built pinned engine venv read-only** rather than attempting a fresh install into the
99%-full root filesystem. Governed artifacts are byte-identical to W226/W227. The disk-full condition
still exists but no longer blocks verification.

## New this cycle — the venv-reuse fix (the researched improvement)
W226 and W227 degraded because they tried to `pip install` the pinned stack into a root FS that is
99% full, hitting `OSError: [Errno 28] No space left on device`. The disk is saturated by ~3.2 GB of
`nobody`-owned prior-session leftovers (`/tmp/cc_*` clones + `/tmp/venv_*`) that the unprivileged
session cannot delete (W203 ownership asymmetry).

The key observation this cycle: **five of those leaked venvs are readable/executable and already
carry the exact pinned stack** — `numpy 1.26.4 / scipy 1.13.1 / pandas 2.2.3`:

```
/tmp/venv_w226  /tmp/venv_engine  /tmp/engine_venv  /tmp/evenv  /tmp/venv_w215
```

Running the engine and pytest with `/tmp/venv_w226/bin/python` needs **zero new disk** and yields the
full green battery. The correct policy under disk-full is therefore **reuse-before-build**: detect an
existing `/tmp/venv_*` whose interpreter imports the pinned versions and use it read-only; only fall
back to building a fresh venv if none is usable. This is folded into the STEP-0 hand-off banner in
`MODEL_DEV_TASK_PROMPT.md` (which had gone stale at W97) so future cycles do not needlessly degrade.

## Verification battery — FULL, GREEN

| Gate | Result |
|---|---|
| C — offline GUI self-test | **`self_test_ok:true`, `engine_ready:true`** (`/tmp/venv_w226/bin/python`) |
| C — frozen smoke bit-match | **nested 49657.9 / gaussian 37499.0 / var-covar 30267.9** (`run_model` 100x4 no-tail seed 42) |
| D — spec AST parse | **OK** |
| D — release workflow YAML | **valid** (jobs `build`, `release`) |
| D — offline_bootstrap self-test | **ok** (exit 0) |
| D — build_phase_pkg_task1_validate | **all_pass True** (26 checks, incl. `ui_app_byte_unchanged`, `governed_headline_present`) |
| Integrity — build_offline_home_validate | **177/177** |
| Integrity — offline_home pytest | **4/4** |
| Integrity — loader parity (node) | **10/10** |
| Integrity — MLMC suite (`test_mlmc_*`) | **66/66** |
| Agent-lock | live-exercised (preflight PROCEED `18:10Z` -> acquire `18:10:30Z` cycle `3da0` -> release this cycle) |

**Governed artifacts — byte-stable:** `offline_home.html` md5 `03d6538d3cae9efb83062ecbfab096e9`;
`ui_data.json` contract `1.23.0`; headline SCR `39975.654628199336` present in both `ui_data.json`
and `offline_home.html`; `ui_app.html` sha256 unchanged (`ui_app_byte_unchanged` gate True).

## Mount sync
All **1893** tracked files (excl. dynamic `.agent_lock.json`) present on the mount with **byte-identical
sizes** to `origin/main` (0 missing, 0 size-mismatch); the critical/governed set is **10/10 md5-match**.
The mount was already in sync from W227 (~11 h prior); only the W228 cycle writes were copied
clone->mount. The mount `.git` stays stale by design.

## Cadence / scheduler — cron STILL hourly (10th consecutive direct read)
```
taskId         : auto_actuarial_stochastic_model
cronExpression : 0 * * * *          <-- STILL hourly (ground truth via scheduled-tasks API)
enabled        : true
jitterSeconds  : 361                <-- ~6 min; explains the :06 firing phase
lastRunAt      : 2026-08-02T18:06:11.790Z   (this firing)
nextRunAt      : 2026-08-02T19:06:01.000Z   <-- one hour on; a 0 2,14 cron would schedule 06:00Z
```
The `description` still documents the intended 12 h cadence while `cronExpression` remains `0 * * * *`
— direct evidence the one-field fix was never applied (W219 first direct read; W220-W227
second-ninth; W228 tenth). The W204 cadence guard (min 600 min) bounds the cost: intra-day hourly
firings yield on the cadence floor; only on-cadence firings (like this 18:06Z one, ~647 min after the
W227 release) do work.

## Disk status
`df /` at cycle start: **99% used, ~181 MB free**. The ~3.2 GB `nobody`-owned leak is unchanged and
still needs an **owner reboot / `/tmp` purge**. W228's venv-reuse makes verification **robust to** the
condition but does not **resolve** it — a fresh full `pip install` would still ENOSPC. This session's
own clone (~41 MB) is removed at end-of-cycle per the W203 mandate.

## Owner actions needed (conclusion-first, numbered)
1. **Fix the cron** `0 * * * *` -> `0 2,14 * * *` (18:00/06:00 UTC). 10th consecutive direct confirmation;
   reversible one-field edit; root cause of the disk leak.
2. **Reclaim disk / reboot the sandbox** to purge the ~3.2 GB `nobody`-owned `/tmp/cc_*` + `/tmp/venv_*`
   leak. No agent can delete it. (W228 mitigated the symptom via venv-reuse; the disk is still 99% full.)
3. **Decide whether Codex runs at all** — 0 acquires / 0 commits ever; only claude has held the lock.
4. **Rotate the GitHub PAT** embedded in the mount's `origin` remote (open since W200) — only open
   security item.
5. **Unblock or freeze the model frontier** — Phase 38 Task 3 / LSMC inner-loop proxy / MR-LONGEV-1 /
   MLMC governed default (stage 5) / signed per-OS binaries are all owner-gated; absent a decision,
   cycles remain verify+sync only.

## Changes this cycle
`.claude-dev/MODEL_DEV_STATE.json`, `MODEL_DEV_LOG.md`, `MODEL_DEV_TASK_PROMPT.md` (STEP-0 hand-off
banner refreshed to W228 + venv-reuse note), and this new `docs/cycle_status/` file. No model-FORM /
contract / headline / driver / MLMC-default / LSMC change; no new graphic or brief; no scheduled-task
mutation (owner-scoped — reported via email draft, not applied).
