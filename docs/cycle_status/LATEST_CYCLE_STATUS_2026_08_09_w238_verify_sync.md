# LATEST CYCLE STATUS — W238 — 2026-08-09T12:20Z

**Cycle:** W238 · **Owner:** claude (Cowork) · **Cycle-id:** `2026-08-09T12:09Z-a974`
**Type:** exhausted-backlog verification + mount-sync (SKILL-sanctioned branch) — **FULL BATTERY on a freshly-built pinned venv**
**Task pointer:** Phase 38 Task 3 (`ui_app.html` native-tab cutover) — **OWNER-GATED, not executed**

## Conclusion first
Model is unchanged and **byte-stable**; the working folder is synced to `origin/main`. This is the
**45th consecutive** cycle with **no auto-admissible model work** — Phase 38 Task 3 and the entire
model-FORM backlog remain owner-gated. The **FULL verification battery is GREEN** on a fresh pinned
engine venv. Environment is **healthy** (root FS **73% used / 2.7 GB free**). **Genuinely-new this
cycle:** the `/tmp` ghost-clone leak grew **6 → 8**, and the two new clones (both cadence-yield
firings in the 02–03Z window that each still left a clone, while the 04–11Z firings left none)
**reconcile** the competing W236 ("per-firing") and W237 ("app-active") models into a single
**"per-EXECUTING-firing"** rule: one clone leaks per firing that actually spins up a sandbox session,
whether or not it then yields on cadence.

## Verification battery — FULL, GREEN

| Gate | Result |
|---|---|
| C — offline GUI self-test | **`self_test_ok:true`, `engine_ready:true`** (`/tmp/venv_engine_w238/bin/python`) |
| C — frozen smoke bit-match | **nested 49657.9 / gaussian 37499.0 / var-covar 30267.9** (`run_model` 100×4 no-tail seed 42) |
| D — spec AST parse | **OK** |
| D — release workflow YAML | **valid** (jobs `build`, `release`) |
| D — offline_bootstrap self-test | **ok** (exit 0, all `ok:true`) |
| D — build_phase_pkg_task1_validate | **ok=True** (26/26, incl. `ui_app_byte_unchanged`, `governed_headline_present`) |
| Integrity — build_offline_home_validate | **177/177** |
| Integrity — offline_home pytest | **4/4** |
| Integrity — loader parity (node v22.22.3) | **10/10** |
| Integrity — MLMC suite (`test_mlmc_*`) | **66/66** (1 skipped) |
| Agent-lock | preflight PROCEED `12:08Z` → acquire `12:09:21Z` cycle `a974` → release this cycle |

**Governed artifacts — byte-stable:** `offline_home.html` md5 `03d6538d3cae9efb83062ecbfab096e9`;
`ui_app.html` md5 `818249497e95ff25b8e4dda50d38502e`; `ui_data.json` contract `1.23.0`; headline SCR
`39975.654628199336`. Gate-C smoke rewrote `docs/validation/RUN_MODEL_{AGGREGATION_REPORT,SUMMARY}.json`
(timestamp/id/duration only — verdict PASS, digest & SCR identical) and they were **reverted**.

## New this cycle — /tmp leak 6 → 8 reconciles W236 and W237
`df /` free: **2.7 GB (73% used)** — healthy. Persistent `nobody`-owned clones went **6 → 8**
(+`cc_20260809_020726`, +`cc_20260809_030731`). Both additions sit in the overnight **02–03Z**
window and both **post-date the 01:18Z W237 release by <600 min**, so both were **cadence-YIELD**
firings — yet each still left a clone (STEP 0.1 clones before STEP 0.3 yields). The 04:06Z–11:06Z
firings left **nothing**. Synthesis — **"per-EXECUTING-firing"**: a clone leaks once per firing that
actually spins up a sandbox session (regardless of the later cadence yield); firings that never
start a session leak nothing. This subsumes W236 (per-firing) and W237 (app-active-window). The
W229 "time-critical <1 day" disk state was retired by the reboot/purge observed at W232 and has not
recurred. This session's own clone + venv self-clean at end-of-cycle (W203).

## Cadence guard — ~11:1 suppression, holding
Between the W237 release (`2026-08-09T01:18:23Z`) and this firing (`12:06:28Z`, ~648 min later) the
hourly cron fired ~10 times (02:06Z…11:06Z); **all yielded** on the 600-min floor and only 12:06Z
**proceeded**. W204 guard collapsing ~11 hourly firings to one working cycle, as designed.

## Scheduler — cron STILL hourly (20th consecutive direct read)
```
cronExpression : 0 * * * *          <-- STILL hourly (scheduled-tasks API ground truth)
enabled        : true   jitterSeconds : 361
lastRunAt      : 2026-08-09T12:06:28.437Z   nextRunAt : 2026-08-09T13:06:01.000Z
```
`nextRunAt` +1 h is dispositive of an hourly cron. The task **description** already carries the
intended `0 2,14` (02:00/14:00 HKT = 06:00/18:00 UTC) — only the `cronExpression` is wrong. This
12:06Z firing landed in the **nominal Codex 12:00 slot**; Codex has **0 commits ever**, so no collision.

## Mount sync
All tracked files (excl. dynamic `.agent_lock.json`) synced clone→mount; governed set md5-match. The
mount `.git` stays stale by design.

## Owner actions (conclusion-first)
1. **Fix the cron** `0 * * * *` → `0 2,14 * * *` — 20th direct confirmation; one-field, reversible; durable fix for off-phase firing and the `/tmp` leak.
2. **Decide whether Codex runs at all** — 0 acquires / 0 commits ever across 1229 commits.
3. **Rotate the GitHub PAT** embedded in the mount `origin` remote (W200, unrotated) — only open security item.
4. **Unblock or freeze the model frontier** — Phase 38 T3 / LSMC inner-loop proxy / MR-LONGEV-1 / MLMC stage-5 default / signed per-OS binaries; absent a decision, cycles stay verify+sync only.
