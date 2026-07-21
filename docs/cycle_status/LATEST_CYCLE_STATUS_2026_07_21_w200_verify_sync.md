# W200 — Exhausted-backlog verification + mount-sync (record-only)

- **Cycle:** W200 · lock `2026-07-21T13:09Z-49b6` · owner `claude`
- **Preflight:** PROCEED (owner `null`; released by claude 12:21:35Z)
- **Task executed:** W200 exhausted-backlog verification + mount-sync. Phase 38 Task 3 remains **OWNER-GATED** and was not executed.
- **Verdict:** FULL BATTERY GREEN · governed artifacts byte-stable · **record-only**

## Why this document is deliberately short

W199 already root-caused the two live findings (CODEX-HAS-NEVER-RUN; the hourly-cron
cost case). The skill forbids near-duplicate briefs when the auto backlog is exhausted.
This cycle therefore adds **no new analysis** — it is the verification record only, plus
two facts that are new *as observations* and are carried to the owner email.

## Verification battery

| Gate | Check | Result |
|---|---|---|
| C | `launch_offline_gui.py --self-test` | `self_test_ok:true`, `engine_ready:true` |
| C | `run_model.py --n-outer 100 --n-inner 4 --no-tail --seed 42` | nested **49657.9** / gaussian **37499.0** / var-covar **30267.9** — exact match to frozen reference |
| D | `packaging/actuarial_gui.spec` | AST parses |
| D | `packaging/release.workflow.yml` | structurally valid (122 lines, `jobs:` present; pyyaml absent in sandbox → structural fallback) |
| D | `packaging/offline_bootstrap.py --self-test` | `ok:true` |
| D | `scripts/build_phase_pkg_task1_validate.py` | `ok:true` (incl. `governed_headline_present`) |
| D | per-OS binary build | owner/CI-gated by design — **not** a failure |
| I | `scripts/build_offline_home_validate.py` | **177/177** |
| I | `tests/test_offline_home_validate.py` | **4/4** |
| I | `scripts/offline_home_loader_parity.cjs` (node) | **10/10** |
| I | MLMC suite `tests/test_mlmc_*` | **66 passed** |
| I | `offline_home.html` md5 | `03d6538d3cae9efb83062ecbfab096e9` — **unchanged** |
| I | `ui_data.json` contract | `1.23.0` — **unchanged**; headline `39975.654628199336` present |

Environment: reused pinned venv (`numpy 1.26.4 / scipy 1.13.1 / pandas 2.2.3`).

**Byte-stability note.** The only working-tree diff after the smoke run was
non-deterministic run metadata in `docs/validation/RUN_MODEL_{AGGREGATION_REPORT,SUMMARY}.json`
— `run_id`, `duration_seconds`, `wall_clock_seconds`. **Zero numeric model results changed.**
Reverted before commit.

## Observation 1 — cron defect re-confirmed from the scheduler API itself

Read directly off the scheduler this cycle (not inferred from clone timestamps):

```
taskId:         auto_actuarial_stochastic_model
cronExpression: "0 * * * *"          <- hourly
description:    "...12h cadence: 02:00 & 14:00 HKT = 18:00 & 06:00 UTC..."   <- already correct
lastRunAt:      2026-07-21T13:06:42Z
nextRunAt:      2026-07-21T14:06:01Z
enabled:        true    jitterSeconds: 361
```

The fix remains **HALF-APPLIED**: the description was corrected, the cron was not.
Required value: **`0 6,18 * * *`**. This is the 7th firing today (W194 07:14Z, W195 08:08Z,
W196 09:07Z, W197 10:08Z, W198 11:06Z, W199 12:08Z, W200 13:09Z) and the 8th fires at 14:06Z.

**Not auto-applied.** The scheduler is owner infrastructure outside the repo, and the skill's
write-action rule limits this agent to reporting. Same call as W196–W199.

## Observation 2 — NEW: credential exposure in the mount's git remote

The mounted working folder's `origin` URL embeds a **GitHub personal access token**
(`https://wilson37wu:ghp_***@github.com/...`). Consequently `git remote get-url origin` —
which STEP 0 of this very skill instructs every cycle to run — prints a **live credential in
plaintext** into the agent transcript, and into any log or tool-output capture of it.

This has been true for every cycle to date, so the token should be treated as
already-disclosed. Recommended: rotate the PAT, then switch the remote to SSH or a git
credential helper so the secret never appears in a command's output.

**Reported, not remediated** — rotating an owner credential is outside auto-admissible scope.

## Standing position

The auto-admissible backlog has been exhausted for **7 consecutive cycles**. Every remaining
item is owner-gated (model-form change, contract bump, headline re-baseline, MR-LONGEV-1,
MLMC stage 5, LSMC proxy, signed binaries). Until the owner either unblocks one of those or
corrects the cron, each firing can only reproduce this same green record.
