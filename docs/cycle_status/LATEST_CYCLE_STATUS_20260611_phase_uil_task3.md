# Cycle status — 2026-06-11 06:00 UTC window (Claude) — Phase UIL Task 3 (B3)

**Task:** `scripts/run_model.py` run orchestrator — single user-facing entry point.
**Verdict:** COMPLETE. ChangeRecord `92142116880240d2828d9eaac365f696` (code_change, OWNER_REVIEW); audit 100→101, changes 72→73, verify_all True.

## What landed
- **`scripts/run_model.py` (new):** `--inputs model_inputs.json` threads validated user inputs through the unchanged governed Phase 22 Task 4 seven-driver engine: standalone losses → 7×7 var-covar → copula aggregation (AIC on realised losses) → nested benchmark → bootstrap SCR CIs → tail diagnostics. Honours Run Settings `n_sim` / `seed` / `bootstrap_replicates` / `horizon_months` / `output_label` (+ optional `n_outer`/`n_inner` keys) and Assumptions `confidence`; CLI flags override; per-field provenance recorded in the output.
- **Representative product:** no inputs → governed synthetic 45/M/100,000/5,000/20y (parameter-identity vs the archived P22T4 config asserted in tests); user portfolio → inforce-weighted mean of PAR rows, term snapped to supported terms (5/10/20y, disclosed), book totals + linear scale factor reported as a DISCLOSED approximation, GMMB rows split out and disclosed.
- **Liquidity exposure:** user balance sheet via the B2 `resolve_exposure_spec` overlay (`illiquid MV × forced-sale fraction`), else archived G-LIQX calibration; fail-loud on placeholders. Frozen seven-driver correlation never user-settable.
- **Outputs:** `docs/validation/RUN_MODEL_AGGREGATION_REPORT.json` — same structural `aggregation` contract as the PHASE22_TASK4 snapshot `build_ui_data.py` already parses — plus `RUN_MODEL_SUMMARY.json`; re-parse-guarded; governed evidence files never overwritten.
- **Wire-through:** `production_run/run_production_model.py` gains a `capital` stage; under `--stage all` it runs automatically when a `model_inputs.json` exists (skip + pointer message otherwise; explicit `--stage capital` runs the governed-default profile; no seed pass-through so the template seed wins). Verified end-to-end: template → `load_user_inputs.py` → `PAR_MODEL_INPUTS` → `run_model.py` → evidence + `capital_result.json`.
- **Worked example (committed evidence):** template demo book (3 model points, 2,500 policies, USD), n_sim 20,000, seed 20260608, label `WorkedExample_TemplateDemoBook`, reduced nested profile `--n-outer 100 --n-inner 4` (sandbox wall-clock limit; disclosed in `run_plan.provenance`). Headline: nested SCR 71,112.1; gaussian-copula SCR 49,825.9; var-covar 37,625.9; verdict REVIEW (expected at reduced profile — var-covar understatement is the known finding). Deterministic re-run reproduced bit-identical headline figures.
- **Manual:** `production_run/USER_MANUAL_run_and_inputs.md` §4 Step 3 marked LIVE (usage, input semantics, disclosed-approximation notes, wrapper invocation).

## Tests
- 23 new `tests/test_run_model.py` (plan resolution + provenance, parameter-identity gates vs archived P22T4 config/exposure, weighted-mean representative product + term snap + GMMB split, GUI structural contract, fail-loud paths, wiring). All green.
- Regression: UIL-area 86 PASS; phase22/phase30/vine/user-inputs selection 189 PASS; governance/audit selection 205 PASS; `compileall` clean.
- **Disclosed fix (pre-existing red, not from this task):** two P24T3 MR-014 note-pin tests failed on origin/main because the Phase 25 Task 4 path-wise refresh superseded the Phase 24 note (`update_mitigation` replaces notes). Fixed forward-compatibly per the repo's latest-refresh-supersedes convention (same class as the cycle-20 fix); supersession chain must still trace to Phase 24.

## Environment notes (for the next agent)
- Remote `origin/main` was AHEAD of the Cowork mount at cycle start (Task 2 had been pushed 05:22 UTC); all work was done in a fresh full clone and the mount was synced after push.
- This sandbox now kills background processes at tool-call boundaries (~45 s budget per call). Long monolithic runs must be staged or profile-reduced; the orchestrator honours `n_outer`/`n_inner` in `run_settings` for exactly this reason. `/var/tmp/pylibs` (scipy/openpyxl/pytest) was rebuilt this cycle.

## Next
- **In progress →** Phase UIL Task 4 (B4+A1): `build_ui_data.py` stamps currency + output_label into meta (and can surface the RUN_MODEL_* snapshot), `ui_app.html` money formatting via `fmtMoney`, production_run README + manual end-to-end, ADDITIVE GUI contract bump.
- Then resume Phase 30 Task 4 (tree-3 tail diagnostics + binding stop-rule / MR-016/MR-017 decision).
