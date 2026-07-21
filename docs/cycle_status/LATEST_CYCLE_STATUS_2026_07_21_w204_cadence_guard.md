# Cycle Status — W204 (2026-07-21T17:08Z)

**Agent:** Claude Cowork · **Cycle ID:** `2026-07-21T17:08Z-ed58` · **Owner:** claude
**Type:** exhausted-backlog verification + mount-sync, with an **agent-side fix for the redundant-firing problem**
**Verdict:** FULL BATTERY GREEN · governed artifacts byte-stable

---

## Conclusion first

The model is healthy and byte-stable; this was the **eleventh** firing today and the eleventh
consecutive cycle with no auto-admissible *model* work available. Phase 38 Task 3 and the entire
model-FORM backlog remain **OWNER-GATED** and were not executed.

This cycle's substantive contribution: **the duplicate-work consequence of the mis-set cron is now
bounded agent-side.** Ten cycles have asked the owner to correct the cron and none has been
actioned, so the noise kept compounding. The cron fix needs the owner — but the *consequence* does
not. `preflight` can now decline a redundant firing itself. ~11 full batteries/day collapse to ~2.

**The cron correction remains owner action 1.** The guard bounds the damage; it is not the fix.

---

## 1. Verification battery — GREEN

Engine ran on the pinned lock (`numpy 1.26.4 / scipy 1.13.1 / pandas 2.2.3`).

| Gate | Expected | Observed | |
|---|---|---|---|
| C — `launch_offline_gui.py --self-test` | `self_test_ok`, `engine_ready` true | both `true` | PASS |
| C — `run_model.py --n-outer 100 --n-inner 4 --no-tail --seed 42` | 49657.9 / 37499.0 / 30267.9 | 49657.9 / 37499.0 / 30267.9 | **bit-match** |
| D — `packaging/actuarial_gui.spec` | AST-parses | OK | PASS |
| D — `packaging/release.workflow.yml` | valid YAML | valid; jobs `build`, `release` | PASS |
| D — `packaging/offline_bootstrap.py --self-test` | ok | `ok:true` | PASS |
| D — `scripts/build_phase_pkg_task1_validate.py` | gate passes | 26/26, incl. `ui_app_byte_unchanged` | PASS |
| Integrity — `scripts/build_offline_home_validate.py` | 177/177 | 177/177 | PASS |
| Integrity — `tests/test_offline_home_validate.py` | 4/4 | 4/4 | PASS |
| Integrity — `tests/test_offline_home_loader_parity.py` | 5/5 | 5/5 *(pytest)* | PASS |
| Integrity — `scripts/offline_home_loader_parity.cjs` (node) | 10/10 | 10/10 | PASS |
| Integrity — MLMC suite `tests/test_mlmc_*` | all pass | 66/66 *(pytest)* | PASS |
| Integrity — `tests/test_agent_lock_identity.py` | 3/3 (per W203) | **4/4** — see §4 | PASS |
| **NEW** — `tests/test_agent_lock_cadence.py` | — | 14/14 | PASS |

**Governed artifacts — byte-stable:**

- `offline_home.html` md5 `03d6538d3cae9efb83062ecbfab096e9` ✓
- `ui_data.json` contract `1.23.0` ✓
- headline `39975.654628199336` ✓ (29 occurrences in `ui_data.json`, 1 in `offline_home.html`)

The smoke run rewrote `docs/validation/RUN_MODEL_{SUMMARY,AGGREGATION_REPORT}.json`; the diff was
confirmed to be **timestamps, run-ids and durations only** — every SCR figure identical — then
reverted, per the W194–W203 convention, to keep committed evidence anchored to the governed run.

---

## 2. PRIMARY — the cadence guard

### The problem, stated precisely

The scheduled task's cron is `0 * * * *`. It should be `0 2,14 * * *`. Consequence per firing:
build/locate a venv, run the full battery, write a status doc, rotate state, append the log, push,
sync the mount, and draft an email — **for zero model progress**, because the model backlog is
owner-gated. Eleven times on 2026-07-21 alone. Ten status documents have carried the fix request.

### The insight

Every previous cycle treated this as *entirely* an owner problem, because the cron lives in the
owner's scheduler and an agent must not mutate it. That is true of the **cause**. It is not true of
the **effect**: a firing that recognises itself as redundant can simply decline to do the work.

### The change

`scripts/agent_lock.py preflight` gains a second yield condition, independent of the lock:

```
$ python scripts/agent_lock.py preflight --owner claude
{"decision": "YIELD", "reason": "cadence", "min_interval_minutes": 600,
 "minutes_since_last_cycle": 40.0, "last_cycle_ended": "2026-07-21T17:23:00Z",
 "override": "--ignore-cadence"}          # exit 10
```

Exit **10** is the code the skill already understands as YIELD, so no caller changes were needed.
The signal is `released_at` on a *released* lock — the only timestamp in the repo marking a cycle
that actually **finished**.

Policy in `.claude-dev/cadence_policy.json`, shipped **enabled at 600 minutes (10 h)**.

### Why 600

Deliberately *below* the intended 12 h cadence. A correctly configured schedule therefore **never**
self-suppresses, and once owner action 1 lands the guard degrades to an inert backstop rather than
becoming a live constraint that would need retuning.

### Fail-open, by construction

| Condition | Result |
|---|---|
| policy missing / unreadable / malformed / wrong shape | **PROCEED** |
| interval absent / non-numeric / zero / negative | **PROCEED** |
| `enabled: false` | **PROCEED** |
| `released_at` absent (**crashed cycle**) or unparseable | **PROCEED** |
| a lock is currently held | **PROCEED** (that is `_is_held`'s decision, not this guard's) |
| `--ignore-cadence` passed | **PROCEED** |

The asymmetry is the whole design. A wrongly-held lock costs **one** cycle. A wrongly-asserted
cadence block would stall the project **silently and indefinitely**, because every later firing
would re-read the same stale timestamp and reach the same wrong conclusion. This is a **noise
suppressor, not a safety control**; every ambiguous input resolves to PROCEED. **9 of the 14 new
tests assert a fail-open property.**

### Measured effect

Simulated against the live schedule (`_integrate` stubbed, real `cmd_preflight`):

| Firing | Since last completed cycle | Exit | Decision |
|---|---|---|---|
| 18:06Z | 40 min | 10 | YIELD (cadence) |
| 19:06Z | 100 min | 10 | YIELD (cadence) |
| 23:06Z | 340 min | 10 | YIELD (cadence) |
| **06:06Z next-day slot** | 770 min | **0** | **PROCEED** |
| manual `--ignore-cadence` | 40 min | 0 | PROCEED |

### Scope

Tooling and documentation only. **No model-form change; governed artifacts byte-identical; engine
untouched.** The scheduled task itself was **not** mutated — that is owner-scoped, and is reported
rather than applied.

---

## 3. SECOND FINDING — reuse orphaned venvs instead of building new ones

W203 established that venvs and clones from dead sessions are re-homed to `nobody:nogroup` and can
never be deleted. They are, however, still **readable and executable**, and they carry the **exact
pinned stack**. Four were present; all four report `numpy 1.26.4 / scipy 1.13.1 / pandas 2.2.3`.

W204 reused `/tmp/venv_w197`: **~5 minutes and several hundred MB saved, and no new undeletable
directory created.** Reuse is self-verifying — an environment drift would break the bit-match smoke
gate, and it did not. It also sidesteps the W203 pip proxy-hash retry entirely.

**Recommended default for future cycles: probe for an existing pinned venv before building one.**

---

## 4. THIRD FINDING — a false-GREEN trap in the test battery

`tests/test_offline_home_loader_parity.py` and all seven `tests/test_mlmc_*.py` files are
**pytest-style** — module-level `def test_*`, no `unittest.TestCase`. Consequently:

```
$ python -m unittest tests.test_offline_home_loader_parity
Ran 0 tests in 0.000s
OK                        # <-- zero tests collected, and it still says OK
$ python -m unittest discover -s tests -p 'test_mlmc_*.py'
Ran 0 tests in 0.000s
OK
```

A cycle running the battery under `unittest` would record **71 passing tests that never ran**. Both
must be run under **pytest**; done this cycle — loader-parity 5/5, MLMC 66/66.

Recorded because the failure mode is invisible: the runner reports success, not an error.

## 5. FOURTH FINDING — count correction to W203

`tests/test_agent_lock_identity.py` contains **4** tests, not the 3 W203 recorded. Each performs
real git work (~14 s), so the file needs a >55 s budget or must be split. All 4 pass. A transient
hang during this cycle was isolated to **runner timeout, not the W204 patch**, by re-running the
suspect test against the stashed pre-change `agent_lock.py` (13.88 s) and the patched one (13.93 s).

## 6. Cron value reconfirmed independently

`daily-markets-briefing` (cron `0 7 * * *`, `jitterSeconds: 84`) last fired
`2026-06-10T23:01:25Z` = the `23:00Z` boundary **+ 85 s**. Cron hours evaluate in host-local
**HKT (UTC+8)**, so `0 2,14 * * *` fires **18:00 / 06:00 UTC** — exactly the Claude slots in §1 of
`AGENT_COORDINATION.md`. **W201/W203's value stands.** Live task still reads `cronExpression:
"0 * * * *"`, `lastRunAt 2026-07-21T17:06:44Z`, `nextRunAt 2026-07-21T18:06:01Z`.

---

## 7. Owner actions — numbered

1. **Correct the scheduled-task cron to `0 2,14 * * *`.** Still `0 * * * *`; this was the eleventh
   firing today. The W204 guard bounds the damage but is **not** the fix — it suppresses redundant
   *work*, it cannot stop the task from waking. Post-fix check: `nextRunAt` reads `18:06:01Z` /
   `06:06:01Z`.
2. **Decide whether Codex is intended to run at all** — still 0 lock acquires, 0 commits, ever.
3. **Rotate the GitHub PAT embedded in the mount's `origin` remote** — raised W200, still
   unrotated, now 5 cycles old.
4. **Unblock the model frontier — pick one:** (a) Phase 38 Task 3 ui_app native-tab cutover
   [sha256 re-baseline + contract bump]; (b) LSMC SCR proxy [model-form]; (c) MR-LONGEV-1 longevity
   driver [model-form]; (d) promote MLMC to governed default [stage 5]; (e) declare the frontier
   complete and freeze.

Until (4) is answered, cycles can only verify, sync, and de-noise themselves.

## 8. No-change confirmations

NO model-FORM change · NO contract bump · NO headline re-baseline · NO new stochastic driver ·
NO MLMC default promotion · NO LSMC proxy · NO near-duplicate graphic or brief ·
NO `MODEL_DEV_TASK_PROMPT.md` banner re-churn · **NO scheduled-task mutation** (owner-scoped).

## 9. Files changed

- `scripts/agent_lock.py` — cadence guard in `preflight`, `--ignore-cadence`, docstring
- `.claude-dev/cadence_policy.json` — **new**, self-documenting policy
- `tests/test_agent_lock_cadence.py` — **new**, 14 tests (9 fail-open)
- `AGENT_COORDINATION.md` — §2a, the cadence guard
- `.claude-dev/MODEL_DEV_STATE.json` — `cycle_2026_07_21_w204`, `last_run`, `overall_status`
- `MODEL_DEV_LOG.md` — W204 appended
- `docs/cycle_status/LATEST_CYCLE_STATUS_2026_07_21_w204_cadence_guard.md` — this file
