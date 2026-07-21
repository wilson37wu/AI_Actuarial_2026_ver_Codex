# W196 — Cycle Status — 2026-07-21T09:08Z

**Agent:** Claude Cowork (`auto_actuarial_stochastic_model`)
**Lock cycle id:** `2026-07-21T09:08Z-d4ed`
**Type:** cadence root-cause diagnosis + verification battery + mount-sync
**Verdict:** ✅ FULL BATTERY GREEN — no model-FORM, contract, headline or banner change.

---

## Conclusion first

**The cadence bug is solved.** W194/W195 could only observe the symptom (runs firing ~1h
apart); this cycle read the scheduler configuration directly and found the cause:

> The task's cron expression is **`0 * * * *`** — *at minute 0 of every hour, every day*.
> It has **never** encoded the 12-hour cadence its own description claims.

The one-line fix is `0 6,18 * * *`. This is **owner infrastructure outside the repo**, so
per the skill's write-action rule it was **diagnosed and reported, not auto-applied**.
Nothing else changed: the model is healthy, byte-stable, and the mount is in sync.

## The cadence finding in full

Scheduler entry `auto_actuarial_stochastic_model`:

| Field | Value |
|---|---|
| `description` | "12h cadence: 02:00 & 14:00 HKT = 18:00 & 06:00 UTC, per AGENT_COORDINATION.md" |
| `cronExpression` | **`0 * * * *`** |
| `schedule` (rendered) | "At 6 minutes past the hour, **every hour, every day**" |
| `enabled` | `true` |
| `jitterSeconds` | 361 |
| `lastRunAt` | 2026-07-21T09:06:40Z |
| `nextRunAt` | **2026-07-21T10:06:01Z** (i.e. one hour later — will fire again) |

**Diagnosis.** The description and the cron disagree, and the cron wins. The intended
`0 6,18 * * *` (hour field `6,18`) was written as `0 * * * *` (hour field `*`), so the task
has been firing **24×/day instead of 2×/day** — a **12× over-run rate**. The `jitterSeconds:
361` explains the "6 minutes past the hour" rendering and the minute-level scatter across
W194 (07:14Z), W195 (08:08Z) and W196 (09:07Z).

**This also re-frames the "instability in both directions" recorded in W195.** There is only
*one* defect, not two:

- The **hourly duplicate firing** is the cron bug — permanent, systematic, still active.
- The **six-day outage** (2026-07-15..2026-07-20) is *not* a scheduler defect at all; an
  hourly cron cannot "drift" into a six-day silence. It is consistent with the host being
  off/asleep or the Cowork app not running. Different root cause, different owner fix.

W195 concluded the scheduler was "unstable in BOTH directions". With the config in hand the
correct reading is: **one config bug (hourly) plus one availability gap (host down).**

**Why this matters beyond tidiness.** Each spurious firing takes the push-based lock, runs a
full clean-room rebuild, and appends a cycle record. At 24×/day against a saturated backlog
that is ~22 wasted cycles/day, and it inflates `MODEL_DEV_LOG.md` (already 1.21 MB) and
`docs/cycle_status/` with near-duplicate records. The lock protocol has held throughout — no
corruption, no double-work, no Codex collision — but it is absorbing load it was never
designed to absorb.

## Coordination

- Preflight: **PROCEED**. `.agent_lock.json` free (`owner:null`, released by W195 at
  2026-07-21T08:14:39Z). No Codex lock or commits since W178.
- Lock acquired `2026-07-21T09:08:05Z`, TTL 120 min; released at end of cycle.
- All git in a throwaway clone (`/tmp/cc_20260721_090705`); the mounted `.git` untouched.

## Task selected

The single `in_progress` item in `.claude-dev/MODEL_DEV_STATE.json` remains **Phase 38
Task 3 — `ui_app.html` native-tab cutover**, which is **OWNER-GATED** (owner sha256
re-baseline across the gate scripts + a `ui_data` contract bump). Not executed.

The auto-admissible backlog remains saturated. Rather than re-run W195's no-op verification
pass unchanged — which the state file's own near-duplicate guard warns against — this cycle
paired the standard battery with the **one genuinely new, non-duplicate diagnostic available**:
reading the scheduler config that had been inferred-about but never inspected.

## Engine environment — third independent clean-room rebuild

Fresh sandbox, no reusable engine libs. Rebuilt from `requirements-engine-lock.txt` using
`python -m venv` + `pip install -r`, **W195's recommended path**:

| Package | Pinned | Resolved |
|---|---|---|
| numpy | 1.26.4 | 1.26.4 ✅ |
| pandas | 2.2.3 | 2.2.3 ✅ |
| scipy | 1.13.1 | 1.13.1 ✅ |

Clean resolution, no numpy shadowing, no manual `dist-info` cleanup. **W195's venv-over-
`pip --target` recommendation is now confirmed on a second independent trial**, and the
governed bit-match is reproduced across **three** clean-room environments.

## Verification gates

### Gate C — offline GUI
- `scripts/launch_offline_gui.py --self-test` → `self_test_ok: true`, `engine_ready: true`
  (numpy ✅ scipy ✅)
- `scripts/run_model.py --n-outer 100 --n-inner 4 --no-tail --seed 42` → **exact bit-match**:

| Aggregation | Frozen reference | This run |
|---|---|---|
| nested | 49657.9 | **49657.9** ✅ |
| gaussian copula | 37499.0 | **37499.0** ✅ |
| var-covar | 30267.9 | **30267.9** ✅ |

### Gate D — packaging recipe
- `packaging/actuarial_gui.spec` AST-parses ✅
- `packaging/release.workflow.yml` YAML-parses ✅
- `packaging/offline_bootstrap.py --self-test` → `ok: true` ✅
- `scripts/build_phase_pkg_task1_validate.py` → `ok: true`, **26/26 checks** ✅

Per-OS binary BUILD remains owner/CI-gated (no `.github/workflows`, no `v*` tags
in-sandbox) — correct, not a failure.

### Integrity / governance
- `scripts/build_offline_home_validate.py` → **177/177** ✅ (`failed: []`)
- `tests/test_offline_home_validate.py` → **4/4** ✅
- `scripts/offline_home_loader_parity.cjs` (node) → **10/10** ✅ (`failed: []`)
- MLMC suite → **66/66** ✅ (inner 8, stage3_wiring 8, tail_estimator 11, tail_stage3 4,
  tail_stage4 10, tail_stage4b 12, tail_stage5 13)

### Governed artifacts — byte-stable
| Artifact | Expected | Observed |
|---|---|---|
| `offline_home.html` md5 | `03d6538d…` | **`03d6538d3cae9efb83062ecbfab096e9`** ✅ |
| `ui_data.json` contract | 1.23.0 | **1.23.0** ✅ |
| headline SCR | 39975.654628199336 | **39975.654628199336** ✅ |

The smoke run rewrote only `run_timestamp` / `duration_seconds` in the two
`docs/validation/RUN_MODEL_*.json` evidence files — all computed figures bit-identical.
Reverted per W195 precedent, so this cycle is record-only.

## Owner actions

1. **Fix the cron: `0 * * * *` → `0 6,18 * * *`.** Single-field change; restores the
   documented 06:00/18:00 UTC cadence and the ≥6h stagger from Codex. **Top priority** —
   it is still firing hourly (next: 10:06Z).
2. **Separately, investigate the 2026-07-15..20 availability gap.** Not the same defect;
   an hourly cron cannot produce a six-day silence. Likely host off / app not running.
3. **Decide Phase 38 Task 3** — the `ui_app.html` native-tab cutover needs an owner sha256
   re-baseline plus a `ui_data` contract bump. It is the only thing standing between the
   auto-agent and a non-saturated backlog.
4. **Consider rotating `MODEL_DEV_LOG.md`** (1.21 MB). Once (1) lands the growth rate drops
   12×, but the existing bulk stays.

## Not done (owner-gated, unchanged)

Model-FORM changes, contract bumps, headline re-baseline, MR-LONGEV-1 longevity driver,
MLMC-as-governed-default (stage 5), LSMC proxy, signed per-OS binaries. The researched
forward pointer is unchanged: **LSMC regression proxy** of the inner risk-neutral valuation
remains the highest-leverage genuinely-new direction beyond the exhausted MLMC track.
