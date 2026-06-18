# Cycle Status — W66 (claude, 2026-06-19, 18:00Z window; continues W65)

**Type:** Forward-research, **MLMC tail-estimator STAGE 4** — outer-loop variance reduction +
Expected-Shortfall bias correction. **Classification:** efficiency / estimator-only; **ADDITIVE**;
**OPT-IN**; no model-form change; no contract bump; no headline re-baseline; no owner sign-off consumed.

## Task
Execute the explicit W65 "Next" pointer (**W66 = MLMC stage 4**): resolve the stage-3 **CONDITIONAL**
verdict — the 99.5% quantile/ES tail functionals were unbiased but **high-variance** at feasible
budgets (ES single-run s.d. ≈10%), with a modest downward optimizer's-curse ES bias — using the two
design-note tools: (1) outer-loop **variance reduction** via stratified sampling of the Gaussian outer
driver, and (2) **ES bootstrap bias correction**.

## What shipped (all NEW/additive; zero governed artifacts touched)
- `par_model_v2/projection/mlmc_inner_estimator.py` (+~140 lines, additive): `_norm_ppf` (numpy-only
  Acklam inverse-normal CDF, |err|≈1e-9), `stratified_normal_outer_sampler` (equal-probability
  stratified Gaussian `OuterSampler`, drop-in, deterministic), `es_bias_corrected` (bootstrap
  bias-corrected ES, `ES_bc = 2·ES − E*[ES(L*)]`).
- `scripts/build_mlmc_tail_stage4_validation.py` → `docs/validation/MLMC_TAIL_STAGE4_VALIDATION_20260619.{md,json}`.
- `tests/test_mlmc_tail_stage4.py` — 10 seed-stable guards (ppf accuracy + scipy cross-check, sampler
  determinism/unbiasedness/symmetry, **variance reduction**, bootstrap identity + determinism, on-average
  bias lift, estimator composition).

## Result — VERDICT: PASS (resolves the W65 variance limitation for the fixed estimator)
- **Outer-loop variance reduction (matched cost, fixed-256, R=40, n_outer=2,500):**
  **VaR 2.19× / ES 4.04× / SCR 2.39×** replicate-variance reduction at **zero** extra inner-path cost
  (640,000 inner paths both arms) → **G3 ≥2× matched-cost speedup PASS** (SCR 2.39×). Stratification is
  free, so the variance factor *is* an effective-sample / RMSE speedup.
- **ES bias correction (plain outer, n_outer=400 where the O(1/n_outer) bias is material, R=80):**
  mean ES rel-bias **−2.16% → −0.24%** (~9× reduction) → **BC1 PASS**.
- **Important nuance (in the card):** stratification *already* removes the small-sample ES bias
  (stratified raw bias ≈+0.01%), so the bootstrap correction is the remedy for an **un-stratified**
  plain-MC pool and must **not** be stacked on stratification (stacking overcorrects).
- **MLMC telescoped tail (research note):** stratification helps less there and the MLMC **ES stays
  budget-sensitive** (can fall below VaR at small upper-level n_outer); the robust, recommended
  stage-4 opt-in is therefore **stratified outer (+ optional bootstrap ES correction) on the fixed-256
  governed-style estimator**, not the telescoped MLMC tail.
- **G4 identity/determinism PASS:** stratified `mlmc_nested_tail(L=0)` bit-for-bit == fixed; correction
  deterministic given a seed.

## Verification (green + byte-stable)
- `build_offline_home_validate` **177/177** ok:true; `offline_home_loader_parity` **10/10**;
  `tests/test_offline_home_validate` **4/4** (stdlib unittest); MLMC suite (inner+tail+stage3_wiring
  +tail_stage3+**tail_stage4**) **41 passed** (was 31; +10) in a throwaway venv (numpy 2.2.6 / scipy
  1.15.3 / pytest 9.1.0).
- `offline_home.html` md5 `03d6538d3cae9efb83062ecbfab096e9` (byte-identical W52–W66); governed
  artifacts (`ui_data.json` / `ui_app.html` / `combined_model_app.html` / `model_summary_card.html` /
  `model_result_viewer.html`) **byte-unchanged** (git status clean); headline **39975.654628199336**
  intact; contract **1.23.0**.

## Coordination
Git in a fresh `/tmp` ext4 clone of `origin/main` (mount `.git` untouched). `origin/main` was **ahead**
of the stale Downloads mount (mount last cycle = W59; origin = W65) → origin is the source of truth.
Lock acquired (`2026-06-18T23:10Z-a28b`) + released this cycle. NOTE: the Downloads mount is **not**
100% full this cycle (df shows ~317 G free) — the working-folder mirror was re-synced from origin.

## Next
**W67 (auto-admissible, recommended): stage-4b wiring** — expose the stratified outer sampler (and the
opt-in ES bootstrap correction) as a selectable **variance-reduction mode** on the opt-in tail path
(default OFF → governed headline byte-identical), gated by a frozen-snapshot equivalence check (mirrors
the W60 stage-3 wiring pattern). This is auto-runnable and does **not** re-baseline the headline.
**OR owner pivot** (the standing sole gate): **A** MR-LONGEV-1 [model-form, sign-off] / **B** LSMC
[sign-off] / **C** Phase IGUI [auto; owner's stated exclusive next major] / **D** Packaging [auto] /
**E** FREEZE. **Stage 5** (any tail-MLMC figure as the governed default) = owner sign-off + fresh frozen
reference only. No governed figure changes at any stage ≤ 4.
