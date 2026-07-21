# W195 — Cycle Status — 2026-07-21T08:08Z

**Agent:** Claude Cowork (`auto_actuarial_stochastic_model`)
**Lock cycle id:** `2026-07-21T08:08Z-40d9`
**Type:** exhausted-backlog verification + mount-sync (record-only)
**Verdict:** ✅ FULL BATTERY GREEN — no model-FORM, contract, headline, banner or new-doc change.

---

## Conclusion first

The model is healthy and byte-stable; the mount is in sync; nothing changed but the record. The material new finding is about the **scheduler, not the model**: W195 fired **54 minutes after W194** on the same morning. The hourly-duplicate failure mode has **returned within 24 hours of the six-day outage** — so the scheduler is not drifting in one direction, it is **unstable in both**. That escalates the cadence fix from housekeeping to the top owner action.

## Coordination

- Preflight: **PROCEED**. `.agent_lock.json` free (`owner:null`, released by W194 at 2026-07-21T07:26:45Z). No Codex lock or commits since W178.
- Lock acquired `2026-07-21T08:08:06Z`, TTL 120 min, released at end of cycle.
- All git in a throwaway clone (`/tmp/cc_20260721_080707`); the mounted `.git` was never touched.

## Task selected

The single `in_progress` item in `.claude-dev/MODEL_DEV_STATE.json` remains **Phase 38 Task 3 — `ui_app.html` native-tab cutover**, which is **OWNER-GATED** (owner sha256 re-baseline across the gate scripts + a `ui_data` contract bump). Not executed. Per the skill's exhausted-backlog branch and the near-duplicate guard, this cycle ran one verification + full mount-sync pass and added no new graphics, briefs or banner re-churn.

## Engine environment — second independent clean-room rebuild

Fresh sandbox, no reusable engine libs. Rebuilt from `requirements-engine-lock.txt`:

| Package | Pinned | Resolved |
|---|---|---|
| numpy | 1.26.4 | 1.26.4 ✅ |
| pandas | 2.2.3 | 2.2.3 ✅ |
| scipy | 1.13.1 | 1.13.1 ✅ |

**Operational note (supersedes the W194 workaround).** W194 used `pip --target`, which let a transitive resolver drag `numpy 2.2.6` metadata into the target and required a `--no-deps` install plus manual `dist-info` removal. This cycle used a plain **`python -m venv` + `pip install -r`**, which resolved all three pins correctly **with no shadowing and no manual cleanup**. Recommended install path for anyone reproducing the lock: use a venv, not `pip --target`.

Because this is a second from-zero rebuild in a *different* sandbox 54 minutes after W194's, the bit-match below is now reproduced across **two independent clean-room environments**.

## Verification gates

### Gate C — offline GUI
- `scripts/launch_offline_gui.py --self-test` → `self_test_ok: true`, `engine_ready: true` (numpy ✅ scipy ✅)
- `scripts/run_model.py --n-outer 100 --n-inner 4 --no-tail --seed 42` → **exact bit-match**:

| Aggregation | Frozen reference | This run |
|---|---|---|
| nested | 49657.9 | **49657.9** ✅ |
| gaussian copula | 37499.0 | **37499.0** ✅ |
| var-covar | 30267.9 | **30267.9** ✅ |

### Gate D — packaging recipe
- `packaging/actuarial_gui.spec` AST-parses ✅
- `packaging/release.workflow.yml` YAML-parses ✅
- `packaging/offline_bootstrap.py --self-test` → `self_test_ok: true` ✅
- `scripts/build_phase_pkg_task1_validate.py` → `ok: true`, **26/26 checks pass** ✅ (incl. `ui_app_byte_unchanged`, `governed_headline_present`)

Per-OS binary BUILD remains owner/CI-gated (no `.github/workflows`, no `v*` tags in-sandbox) — correct, not a failure.

### Integrity / governance
- `scripts/build_offline_home_validate.py` → **177/177** ✅
- `tests/test_offline_home_validate.py` → **4/4** ✅
- `scripts/offline_home_loader_parity.cjs` (node v22.22.3) → **10/10** ✅
- MLMC suite (`tests/test_mlmc_*.py`) → **66/66** ✅ (single 29s run)

### Governed artifacts — byte-stable
| Artifact | Expected | Observed |
|---|---|---|
| `offline_home.html` md5 | `03d6538d…` | `03d6538d3cae9efb83062ecbfab096e9` ✅ |
| `ui_data.json` contract | 1.23.0 | **1.23.0** ✅ |
| governed headline | 39975.654628199336 | **39975.654628199336** ✅ |

### Reproducibility
The smoke run regenerated `docs/validation/RUN_MODEL_AGGREGATION_REPORT.json` and `RUN_MODEL_SUMMARY.json`. The diff was **exclusively** non-deterministic run metadata — `run_timestamp`, `duration_seconds`, `wall_clock_seconds`, random `run_id` labels. Every substantive figure was bit-identical, and **both `reproducibility_digest` values were unchanged** (`7c8a1a1bd8c10a05…`, `c9d24bc1199175f7…`), confirming W194's finding from a second environment. Both files were reverted so the commit footprint stays record-only.

## Mount sync

**Effective NO-OP.** Full `git ls-files` md5 diff, clone vs mount:

```
tracked = 1858 | identical = 1856 | stale = 2 | missing = 0
```

The 2 stale entries were the two `docs/validation/RUN_MODEL_*.json` files this cycle's own smoke run had just rewritten; after reverting them the mount is **1858/1858 identical**. (`.agent_lock.json` excluded as dynamic.) The mount `.git` ref stays stale by design — virtiofs forbids deletes, so all git runs in the throwaway clone.

## Change footprint

- `.claude-dev/MODEL_DEV_STATE.json` — W195 cycle entry, `last_run`, `overall_status`
- `MODEL_DEV_LOG.md` — W195 entry appended
- `docs/cycle_status/LATEST_CYCLE_STATUS_2026_07_21_w195_verify_sync.md` — this file
- `.agent_lock.json` — acquire + release

No source, model, contract, governed-artifact, banner or `MODEL_DEV_TASK_PROMPT.md` change.

## Owner actions required

1. **Fix the scheduler cadence — now the top item, both failure modes confirmed inside 24h.** 2026-07-14: fifteen firings at roughly hourly intervals. 2026-07-15 → 07-20: no runs at all (six-day outage). 2026-07-21: W194 at 07:14Z, then W195 at 08:08Z — **54 minutes later**, hourly duplication again. The scheduler is unstable in both directions, so neither "it drifts late" nor "it stalls" describes it. Target: 12h cadence at **06:00 / 18:00 UTC**, preserving the 6h offset from Codex (00:00 / 12:00 UTC). Until fixed, duplicate cycles burn compute to re-verify an unchanged repo — W195 produced zero substantive delta over W194.
2. **Phase 38 Task 3 — decide or defer.** The `ui_app.html` native-tab cutover needs an owner sha256 re-baseline across the gate scripts plus a `ui_data` contract bump. It has been the `in_progress` pointer since Phase 38 opened; every auto cycle since must skip it.
3. **Unblock the model-FORM backlog (or confirm the hold).** LSMC proxy for the inner risk-neutral valuation, MLMC as the governed stage-5 default, the MR-LONGEV-1 longevity driver, and signed per-OS binaries are all owner-gated. Until one is released, auto cycles can only re-verify — W195 is the ~96th consecutive record-only cycle.

## Forward pointer (unchanged)

The highest-leverage genuinely-new direction remains an **LSMC (least-squares Monte Carlo) regression proxy** of the inner risk-neutral valuation, replacing the brute-force nested inner loop for SCR — the canonical next model-FORM step beyond the exhausted MLMC variance-reduction track. Model-FORM change, stays **owner-gated**. No banner re-churn this cycle (near-duplicate per W97–W194).
