# Cycle Status — 2026-07-08 — CF-2 run integration (cash-flow set bound to executed runs)

**Agent:** Claude Cowork (scheduled task `actuarial-model-daily-improvement`)
**Item:** CF-2 — roadmap §4.0c (owner directive 2026-07-03) — **COMPLETES track 4.0c**
**Status:** DONE — tests green, no governed headline change

## What was delivered

Every successful GUI/engine run now carries its own persisted cash-flow
projection set, mirroring the GD-4 pattern for scenario paths:

- `par_model_v2/viewer/igui_cashflows.py`:
  - `attach_cashflow_set_for_run(inputs_path, out_root)` — writes the CF-1
    set to `run_output/cashflow_set_runs/<digest12>/cashflow_set/`, keyed by
    the CF-1 inputs digest. Identical-input runs share one copy
    (digest-cache hit); later runs never overwrite an earlier run's set.
    The digest key IS the stale-set guard. Never raises.
  - `load_run_cashflow_set(jobs_dir, run_id)` — serves the set persisted
    with a past run (schema + digest re-verified against the attachment,
    traversal-safe, run-provenance note stamped).
  - `/cashflows` page: `?run=<id>` binding + run-provenance banner.
- `par_model_v2/viewer/igui_run_execution.py`: `execute_run` step 6b calls
  the attach best-effort AFTER artifact stamping — a cash-flow hiccup can
  never fail the governed run; result carries a `cashflow_set` block that
  the GUI-1 JobManager persists on the job record. `/save-run` flows
  through the same path (it dispatches execute_run), so the DoD "CF set
  produced with every GUI run" holds for both entry points.
- `scripts/run_gui.py`: `/cashflow-data?run=<id>` route.
- `par_model_v2/viewer/igui_run_history.py`: registry entries surface
  `cashflow_set` availability + digest; history table gains a per-run
  `CFs` button; compare notes same/differing/missing CF sets.

## Tests

- NEW `tests/test_cf2_run_cashflow_attachment.py` — 16 tests: digest-keyed
  persistence, cache reuse, no-overwrite isolation, never-raise contract,
  loader guards (unknown run, traversal, pre-CF-2 run, digest mismatch,
  missing cache), registry/compare surfacing, execute_run source contract,
  page plumbing, live HTTP round-trip (fresh + unknown-run 422).
- 112 GREEN across CF1-3 / GD1-4 / GUI4-5 / nav / PC-1 / agent-lock /
  script-syntax suites.
- Live e2e: real smoke `execute_run` attached the set fresh (6 CSVs), then
  digest-cache hit on identical re-run; GD-4 path attachment unaffected.
- task7 suite: scipy installed successfully this cycle (stalled last
  cycle), so the live-run tests PASS; the 3 remaining failures are the
  owner-gated Phase 38 ui_app sha-baseline set, pre-existing on main
  (verified via stash A/B).

## Governance

Diagnostic overlay only — governed headline figures untouched (TVOG,
aggregation reports byte-identical); declaration scales remain UNSIGNED;
artifacts carry the CF-1 inputs SHA-256 digest for reproducibility.

## Next queued item

Track 4.0c is COMPLETE (CF-1/2/3 DONE). Highest-priority OPEN items:
PC-2 (extend mechanic families, §4.0d) and general backlog #2 (HW1F
swaption calibration execution, MR-001/MR-008).
