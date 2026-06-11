# Cycle Status — 2026-06-11 — Phase UIL Task 2 (B2): de-hardcoded fixtures

**Agent:** Claude Cowork · **Lock:** acquired 05:10Z (cycle_id 2026-06-11T05:10Z-d23d), released end of cycle · **Result: COMPLETE**

## Coordination note
This cycle started while the previous Claude cycle (B1, acquired 04:09Z) was finishing its push; preflight at 05:10Z correctly saw the lock released and the B1 work already on origin/main, so this cycle moved straight to the state pointer's next task (B2). No clobbering; no force-push.

## What shipped
- **`par_model_v2/user_inputs.py` (new, LIVE):** single access point for `model_inputs.json`. Resolution: explicit path → `PAR_MODEL_INPUTS` env var → `production_run/model_inputs.json` → repo root. **Absent file → `None` / governed defaults (bit-identical); present-but-broken file → `UserInputsError` (never silent fallback).** Schema major pinned to 1. Accessors: `exposure_overrides`, `capital_params` (governed defaults 0.995 / 0.225 / 0.7567 / 0.8450 + `source` provenance), `user_model_points`, `run_settings`.
- **phase22 (`resolve_exposure_spec`, additive):** overlays user `backing_asset_mv` / `illiquid_share` / `forced_sale_fraction` on the fixture spec with an `exposure_source` provenance flag; `derive_exposure_notional` and the G-LIQX gate are untouched; fixture spec never mutated.
- **portfolio generator (additive):** `split_model_points` (PAR vs GMMB rows — GMMB routed by B3 orchestrator), `portfolio_from_model_points` (one record per model point, `inforce_count = policy_count`, fail-loud row-level validation against Phase 10 mechanics ranges incl. cash-line vested-bonus rejection, ids UCD/URB, `source_id USER_INPUTS`), `build_portfolio` dispatcher (user book if supplied, else `generate_hk_par_portfolio` — same digest).
- **Frozen params:** copula df / grouped-t dfs remain governed read-only; NOT reachable from user inputs.
- **Tests: 19 passed** (`tests/test_user_inputs_integration.py`) — resolution/fail-loud cases, exact-equality governed-default gates, fixture-path exposure identity (100,000/0.55/0.40 → 22,000), user overlay (250,000×0.40×0.35 = 35,000), user-book build + stable digest, multi-row fail-loud aggregation, **bit-identical `build_portfolio` regression digest**. Existing `test_portfolio_generator.py` + `test_phase22_task3_liquidity_exposure.py`: **35 passed unchanged**; UIL T1 suite 19/19.
- **Governance:** ChangeRecord `0dbc8cd110044a8186fe0f0bd8a50df3` (code_change, **OWNER_REVIEW**) via `scripts/build_phase_uil_task2_governance.py` (idempotent); audit 99→100, change records 71→72, `verify_all` True.

## Capital impact
None with no inputs file — enforced by exact-equality regression tests. The B3 orchestrator is the first end-to-end consumer.

## Next (state pointer set)
**Phase UIL Task 3 (B3):** `scripts/run_model.py` orchestrator — single entry point `--inputs model_inputs.json`; threads inputs through P22T4 aggregator → standalone losses → copula aggregation → bootstrap → tail diagnostics; writes the same `docs/validation/*.json` shape the GUI consumes; honours n_sim / seed / replicates / horizon / output_label. Then B4+A1 GUI currency wiring → resume Phase 30 Task 4.

## Notes for the other agent (Codex)
- `par_model_v2/user_inputs.py` is THE access point for user inputs — do not read `model_inputs.json` directly elsewhere.
- The bit-identical no-inputs gate is a hard contract: any consumer change must keep `tests/test_user_inputs_integration.py` exact-equality tests green.
