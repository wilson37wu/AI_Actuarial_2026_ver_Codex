# Cycle Status — 2026-06-11 — Phase UIL Task 1 (B1): user-input loader

**Agent:** Claude Cowork · **Lock:** acquired 04:09Z, released end of cycle · **Result: COMPLETE**

## What shipped
- **`scripts/load_user_inputs.py` (new, LIVE):** reads `production_run/MODEL_INPUTS_TEMPLATE.xlsx` by tab name + header (openpyxl); validates every user field (currency block incl. ISO code + valuation date; asset MVs >= 0 with positive total and derived illiquid share; forced-sale fraction in (0,1]; positive BEL/guarantee index; portfolio rows complete with product types in {HKCD_PAR_2026, HKRB_PAR_2026, GMMB_EQ_2026}; confidence in (0,1); relief sigma > 0; alpha/benefit share in (0,1]; positive integer run settings); writes schema-versioned **`model_inputs.json` (1.0.0)** and re-parses it before exit; echoes currency, total asset MV, total sum assured, policy count.
- **Fail-loud contract:** every issue reported as `Tab 'X', row N, field 'Y': message`; all issues listed together; CLI exit 1; no JSON written on failure. Stale derived totals (e.g. edited rows without recalculation) are caught against the recomputed sum.
- **Frozen params:** copula df / grouped-t dfs are read back for provenance echo only — **never user-settable**.
- **`tests/test_user_inputs.py` (new): 19 passed** — shipped-template happy path (totals 100,000 MV / 290,000,000 SA / 2,500 policies) + 15 fail-loud cases (missing tab, bad product, incomplete row, range violations, bad date/code, stale total, multi-error aggregation, CLI exit codes).
- **Manual:** `production_run/USER_MANUAL_run_and_inputs.md` §4 marked the loader **LIVE** (orchestrator B3 / GUI wire-through B4 still target workflow).
- **Governance:** ChangeRecord `dcbc94cdcc474cb9951d762bfeb358b2` (code_change, **OWNER_REVIEW**) via `scripts/build_phase_uil_task1_governance.py` (idempotent); audit 98→99, change records 70→71, `verify_all` True.

## Capital impact
None. Pure I/O + validation; no model code path consumes `model_inputs.json` yet. Governed frozen-t headline untouched.

## Next (state pointer set)
**Phase UIL Task 2 (B2):** de-hardcode fixtures additively — `phase22_liquidity_exposure_calibration.py` (balance-sheet inputs w/ fixture fallback 100,000 / 0.55 / 0.40), `portfolio_generator.py` (user model points w/ synthetic fallback), capital-path confidence/sigma/alpha/benefit_share from inputs (governed defaults 0.995 / 0.225 / 0.7567 / 0.8450). Regression gate: governed read-outs bit-identical with no inputs present. Then B3 orchestrator → B4+A1 GUI → resume Phase 30 Task 4.

## Notes for the other agent (Codex)
- New convention reminder: cycle status files live in `docs/cycle_status/`.
- `model_inputs.json` is gitignored output; the schema contract is in the loader docstring + tests.
