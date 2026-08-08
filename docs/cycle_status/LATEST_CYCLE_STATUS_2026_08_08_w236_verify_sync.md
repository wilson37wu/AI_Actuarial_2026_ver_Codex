# Latest Cycle Status — W236 (2026-08-08T14:13Z)

**Cycle type:** exhausted-backlog verification + mount-sync (SKILL-sanctioned branch) — full battery on fresh pinned venv
**Owner/agent:** Claude Cowork · **cycle_id** `2026-08-08T14:08Z-58a2` · **lock** acquired 14:08:45Z, released end-of-cycle

## Conclusion
Model **unchanged and byte-stable**; working mount synced to `origin/main`. **43rd consecutive** cycle with no auto-admissible model work — Phase 38 Task 3 (`ui_app.html` native-tab cutover) and the whole model-FORM backlog stay owner-gated. Full verification battery re-ran **GREEN** on a freshly built pinned engine venv. Genuinely-new: the `/tmp` ghost-clone leak **resumed growing 3 → 6** (W235's "stable at 3" falsified), traced to cadence-**yielded** firings whose clones never reach the W203 self-cleanup.

## Verification battery — FULL, GREEN
- **Gate C** — `launch_offline_gui.py --self-test`: `self_test_ok:true`, `engine_ready:true`. `run_model.py --n-outer 100 --n-inner 4 --no-tail --seed 42` bit-matches the frozen reference **nested 49657.9 / gaussian 37499.0 / var-covar 30267.9**.
- **Gate D** — spec AST OK; `release.workflow.yml` valid (`name`/`permissions`/`concurrency`/`jobs`); `offline_bootstrap --self-test` ok (all `ok:true`); `build_phase_pkg_task1_validate` all checks `pass:true`.
- **Integrity** — `build_offline_home_validate` **177/177**; `test_offline_home_validate` **4/4**; `offline_home_loader_parity.cjs` (node v22.22.3) **10/10**; MLMC suite **66/66**.
- **Governed byte-stable** — `offline_home.html` md5 `03d6538d3cae9efb83062ecbfab096e9`; `ui_data.json` contract `1.23.0`; headline `39975.654628199336`; `ui_app.html` md5 `818249497e95ff25b8e4dda50d38502e`. Gate-C smoke rewrote `docs/validation/RUN_MODEL_{AGGREGATION_REPORT,SUMMARY}.json` (timestamp/duration only, verdict PASS) — **reverted**, not committed.

## Genuinely-new finding — /tmp leak resumed growth (3 → 6)
`/tmp` now holds **6** `nobody`-owned `cc_*` ghost clones: W235's three (`cc_20260806_210742`, `cc_20260806_220754`, `cc_20260807_020809`) **plus** `cc_20260808_100713`, `cc_20260808_110659`, `cc_20260808_120712` (10:07/11:07/12:07 Z). W235 called the leak "stable at 3"; that is now falsified. **Mechanism:** the clone is created (STEP 0.1) *before* the cadence preflight (STEP 0.3); a firing that YIELDS on cadence has already made its clone but takes the early-exit path (email + stop) which never reaches the W203 `rm -rf $CLONE` ("after push and after release"). So the cadence guard bounds email/brief noise but **cannot** bound `/tmp` clones. A `trap … EXIT` cleanup would fix the yield path (auto-admissible) but was **not** applied this cycle to preserve no-churn discipline and avoid touching `agent_lock.py` mid-owner-gate. Durable fix stays the cron correction.

## Environment
Root FS **72% / 2.7 GB free** — healthy (not yet a risk, but monotonic under an hourly cron). This session's own clone + `venv_eng` self-clean at end-of-cycle.

## Scheduler — 18th direct read
`cron 0 * * * *` (hourly) · `enabled=true` · `jitter=361s` · `lastRunAt 2026-08-08T14:06:10.071Z` · `nextRunAt 2026-08-08T15:06:01.000Z`. Task **description** now documents the intended `02:00 & 14:00 HKT = 18:00 & 06:00 UTC per AGENT_COORDINATION.md` — the correct intent is in the metadata; only the `cronExpression` is wrong. `nextRunAt 15:06:01Z` (one hour on) is dispositive that the cron is hourly, not `0 2,14`.

## Owner actions (conclusion-first)
1. **Fix cron `0 * * * *` → `0 2,14 * * *`** (02:00/14:00 HKT = 18:00/06:00 UTC) — 18th confirmation; single durable fix for the (now-growing) `/tmp` leak + off-phase firing. Reported, not applied (owner-scoped).
2. **Decide whether Codex runs at all** (0 acquires / 0 commits ever).
3. **Rotate the GitHub PAT** embedded in the mount `origin` remote (W200, unrotated).
4. **Unblock or freeze the model frontier** — Phase 38 T3 / LSMC inner-loop proxy / MR-LONGEV-1 / MLMC stage-5 default / signed per-OS binaries.

_No model-FORM / contract / headline / driver change; no TASK_PROMPT banner re-churn; no new graphic/brief; no scheduled-task mutation; no `agent_lock.py` change._
