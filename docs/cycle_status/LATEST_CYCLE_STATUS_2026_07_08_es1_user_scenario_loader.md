# Cycle Status — 2026-07-08 — ES-1 user economic-scenario file validating loader

**Agent:** claude (scheduled `actuarial-model-daily-improvement`)
**Item:** ES-1 (owner-directed track 4.0f, directive 2026-07-08) — format spec + validating loader
**Result:** DONE — loader delivered; spec committed previous cycle (82033f4)

## What was built

- `par_model_v2/stochastic/user_scenarios.py` — validating loader for schema
  `esg-user-scenarios-1.0` (`docs/ECONOMIC_SCENARIO_FILE_FORMAT.md`):
  - `load_user_scenario_set(csv_path, manifest_path=None)` — FAIL-LOUD; enforces every
    spec §4 rule with the offending row/column reported:
    header exact (15 columns, fixed order); scenario contiguity `1..N`, years complete
    `1..100`, sorted, no duplicates (positional sequence check); strict finite numerics
    (blanks/NaN/inf rejected); plausibility bounds rates `[-0.05, 0.30]`,
    `EQ_RETURN [-0.99, 3.00]` (boundaries inclusive, regression-tested); manifest
    presence/JSON/schema-id/basis/rate+equity conventions/`n_scenarios ≥ 100`/
    `projection_years == 100`; `csv_sha256` byte-for-byte integrity gate.
  - Structured error surface: `UserScenarioValidationError.errors`
    (`where`/`row`/`column`/`message`, capped at 50 reported, exact total kept) and a
    non-raising `collect_validation_errors()` for the ES-2 GUI upload page.
  - `UserScenarioSet`: numpy rate cube `(N, 100, 12 tenors)` + equity matrix, manifest,
    file digest, UNSIGNED banner, and the spec §4.6 summary card — p5/p50/p95 of the 10Y
    rate and `EQ_RETURN` at projection years 1/10/50/100 (dict + text echo).
  - C-ROSS advisory WARNING attached when `n_scenarios < 2000` (spec §5 discipline).
- `tests/test_es1_user_scenarios.py` — 41 tests covering the happy path, every manifest
  convention violation, sha mismatch, all CSV structural/numeric/bounds failures with
  row+column assertions, error-cap accounting, and template↔loader lock-step.

## Verification

- 41/41 new tests GREEN.
- 244 GREEN total across ES-1 + ESG process/adapter + user-inputs + CF-1 +
  agent-lock-identity + GUI script-syntax suites. No regressions.

## Governance

- Purely additive. No governed headline figure (TVOG, aggregation) touched.
- User scenario files remain UNSIGNED scenario inputs; loader surfaces the banner and
  digest. Engine selection (`scenario_source`), measure guard and run-trail recording are
  ES-3; GUI upload is ES-2 (next queued items in track 4.0f).

## Next queued

- ES-2 GUI upload page (`/scenarios`): validate with row/col errors surfaced, percentile
  fan preview, persist with digest, gate integration.
