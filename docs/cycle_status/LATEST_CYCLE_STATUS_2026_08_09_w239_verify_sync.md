# LATEST CYCLE STATUS — W239 — 2026-08-09T23:12Z

**Cycle:** W239 · **Owner:** claude (Cowork) · **Cycle-id:** `2026-08-09T23:09Z-de91`
**Type:** exhausted-backlog verification + mount-sync (SKILL-sanctioned branch) — **FULL BATTERY on a freshly-built pinned venv**
**Task pointer:** Phase 38 Task 3 (`ui_app.html` native-tab cutover) — **OWNER-GATED, not executed**

## Conclusion first
Model is unchanged and **byte-stable**; the working folder is synced to `origin/main`. This is the
**46th consecutive** cycle with **no auto-admissible model work** — Phase 38 Task 3 and the entire
model-FORM backlog remain owner-gated. The **FULL verification battery is GREEN** on a fresh pinned
engine venv (numpy 1.26.4 / scipy 1.13.1 / pandas 2.2.3). Environment is **healthy** (root FS **73%
used / 2.7 GB free**). **Genuinely-new this cycle:** the `/tmp` ghost-clone leak is **FLAT at 8** —
zero growth since W238 across ~10 hourly cron ticks (13:06Z–22:06Z), which **refines** W238's
"per-EXECUTING-firing" model: those nominal ticks did not actually boot an agent session, so the leak
tracks **app-active session boots**, not raw cron cadence.

## Verification battery — FULL, GREEN

| Gate | Result |
|---|---|
| C — offline GUI self-test | **`self_test_ok:true`, `engine_ready:true`** (`/tmp/venv_w239/bin/python`) |
| C — frozen smoke bit-match | **nested 49657.9 / gaussian 37499.0 / var-covar 30267.9** (`run_model` 100×4 no-tail seed 42) |
| D — spec AST parse | **OK** (`packaging/actuarial_gui.spec`) |
| D — release workflow YAML | **valid** (name / permissions / concurrency / jobs) |
| D — offline_bootstrap self-test | **ok** (exit 0, all `ok:true`) |
| D — build_phase_pkg_task1_validate | **ok=True** (26/26, incl. `ui_app_byte_unchanged`, `governed_headline_present`) |
| Integrity — build_offline_home_validate | **177/177** |
| Integrity — offline_home pytest | **4/4** |
| Integrity — loader parity (node v22.22.3) | **10/10** |
| Integrity — MLMC suite (`test_mlmc_*`) | **66/66** (1 skipped, 4246 deselected; 105.78s) |
| Agent-lock | preflight PROCEED `23:07Z` → acquire `23:09:30Z` cycle `de91` → release this cycle |

**Governed artifacts — byte-stable:** `offline_home.html` md5 `03d6538d3cae9efb83062ecbfab096e9`;
`ui_app.html` md5 `818249497e95ff25b8e4dda50d38502e`; `ui_data.json` contract `1.23.0`; headline SCR
`39975.654628199336`. Gate-C smoke rewrote `docs/validation/RUN_MODEL_{AGGREGATION_REPORT,SUMMARY}.json`
(run_timestamp / run_id / duration only — verdict PASS, reproducibility_digest `7c8a1a1b…`/`c9d24bc1…`
and SCR identical) and they were **reverted**.

## New this cycle — /tmp leak FLAT at 8 (refines W238)
`df /` free: **2.7 GB (73% used)** — healthy, unchanged from W238. Persistent `nobody`-owned clones
stayed at **8** (`cc_20260806_210742`, `…_220754`, `cc_20260807_020809`, `cc_20260808_100713`,
`…_110659`, `…_120712`, `cc_20260809_020726`, `…_030731`) — **no new clone** across the ten
`13:06Z…22:06Z` hourly cron ticks. W238's "per-EXECUTING-firing" rule predicted +1 clone per hourly
firing that boots a sandbox; observing **zero** additions implies those ticks **did not boot a Cowork
session** (the scheduler logs `lastRunAt` without necessarily starting an agent). Synthesis: the leak
grows per **app-active session boot** — which clusters into active windows (W238's +2 came from the
overnight 02–03Z window) — not per nominal cron tick. This leans back toward the W237 app-active-window
model and shows the leak is **bounded by real usage**, not by the mis-set hourly cron. This session's
own clone + `/tmp/venv_w239` self-clean at end-of-cycle (W203 own-session deletable).

## Cadence guard — ~11:1 suppression, holding
Between the W238 release (`2026-08-09T12:21:08Z`) and this firing (`23:06:32Z`, ~645 min later) the
hourly cron fired ~10 times (13:06Z…22:06Z); **all yielded** on the 600-min floor and only the 23:06Z
tick **proceeded** (~648 min after release, floor cleared). W204 guard collapsing ~11 hourly firings
to one working cycle, exactly as designed.

## Scheduler — cron STILL hourly (21st consecutive direct read)
```
cronExpression : 0 * * * *          <-- STILL hourly (scheduled-tasks API ground truth)
enabled        : true   jitterSeconds : 361
lastRunAt      : 2026-08-09T23:06:32.282Z   nextRunAt : 2026-08-10T00:06:01.000Z
```
`nextRunAt` +1 h is dispositive of an hourly cron. The task **description** already carries the
intended `0 2,14` (02:00/14:00 HKT = 06:00/18:00 UTC) — only the `cronExpression` is wrong. This
23:06Z firing precedes the **nominal Codex 00:00 slot** by ~51 min; Codex has **0 commits ever** and
the lock is released before 00:00, so no collision.

## Mount sync
All tracked files (excl. dynamic `.agent_lock.json`) synced clone→mount; governed set md5-match. The
mount `.git` stays stale by design under virtiofs.

## Owner actions (conclusion-first)
1. **Fix the cron** `0 * * * *` → `0 2,14 * * *` — 21st direct confirmation; one-field, reversible; durable fix for off-phase firing and the `/tmp` leak.
2. **Decide whether Codex runs at all** — 0 acquires / 0 commits ever.
3. **Rotate the GitHub PAT** embedded in the mount `origin` remote (W200, unrotated) — only open security item.
4. **Unblock or freeze the model frontier** — Phase 38 T3 / LSMC inner-loop proxy / MR-LONGEV-1 / MLMC stage-5 default / signed per-OS binaries; absent a decision, cycles stay verify+sync only.
