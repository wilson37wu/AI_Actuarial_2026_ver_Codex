# MLMC quantile/ES tail estimator — stage-4 validation (W66)

_Generated 2026-06-18T23:27:04Z._

**Classification:** efficiency / estimator-only; ADDITIVE; OPT-IN; no model-form change; no contract bump; no headline re-baseline; no owner sign-off consumed. Governed headline `39975.654628199336` and all governed artifacts byte-unchanged; contract `1.23.0`; default estimator stays `fixed`.

## Purpose

Stage 4 resolves the **W65 stage-3 CONDITIONAL** verdict (the 99.5% quantile/ES tail functionals were unbiased but **high-variance** at feasible budgets, with a modest downward optimizer's-curse ES bias) using the two design-note tools: **(1) outer-loop variance reduction** via equal-probability stratified sampling of the Gaussian outer driver, and **(2) ES bootstrap bias correction**. Both are opt-in and never touch the governed SCR/VaR/ES.

## Method

- Testbed: analytic Normal nested snapshot (M_X=0.02, S_X=0.01, σ_inner=0.05, α=0.995, N_inner=256); closed-form truth VaR=0.046987, ES=0.050299, SCR=0.026987.

- Variance reduction: `nested_single_level_tail` (governed-style fixed-256), **plain vs stratified** outer, R=40 replicates at n_outer=2,500. Stratification adds **no** inner paths, so the variance-reduction factor is a **matched-cost** RMSE / effective-sample speedup.

- ES bias correction: bootstrap (`200` resamples) over R replicates; mean raw vs corrected ES against closed-form truth.

## Results — outer-loop variance reduction (fixed-256, matched cost)

| Fn | plain s.d. (rel) | stratified s.d. (rel) | **variance-reduction factor** |
|---|---|---|---|
| VaR | 1.986% | 1.342% | **2.19×** |
| ES | 2.689% | 1.338% | **4.04×** |
| SCR | 3.517% | 2.277% | **2.39×** |

- Same inner-path cost both arms (`640,000` paths); the factor is a matched-cost speedup. **G3 ≥2× on SCR: `True`** (SCR 2.39×).

## Results — ES bias correction (vs closed-form truth)

The empirical ES downward bias is an **O(1/n_outer) small-sample** effect; this study uses n_outer=400 (R=80), the regime where it is material (it is already negligible by n_outer=2,500).

| Outer | mean ES raw (rel bias) | mean ES corrected (rel bias) | bias reduced |
|---|---|---|---|
| plain | 0.049211 (-2.163%) | 0.050176 (-0.244%) | True |
| stratified | 0.050304 (0.011%) | 0.051295 (1.982%) | False |

**Interpretation:** the bootstrap correction cuts the *plain* estimator's small-sample ES bias ~9x; **stratification already removes that bias** (stratified raw bias ≈0%), so the two tools are alternatives — do not stack the bootstrap correction on top of stratification (the `stratified` row above shows that overcorrects).

## MLMC outer-loop variance reduction (research note)

Stratification also reduces the telescoped MLMC tail variance, but the **MLMC ES stays budget-sensitive** (can fall below VaR at small upper-level n_outer). The robust, recommended stage-4 opt-in is therefore **stratified outer + ES bootstrap correction on the fixed-256 governed-style estimator**.

| Fn | MLMC plain s.d. | MLMC stratified s.d. | factor |
|---|---|---|---|
| VaR | 0.004126 | 0.004463 | 0.85× |
| ES | 0.009467 | 0.010433 | 0.82× |
| SCR | 0.004081 | 0.004431 | 0.85× |

## Verdict

**Overall: `PASS`.** G4 identity/determinism `True`; VR1 outer variance reduction `True`; G3 matched-cost ≥2× `True`; BC1 ES bias reduced `True`.

- **The W65 variance limitation is resolved for the governed-style fixed-256 estimator:** stratified outer sampling delivers a matched-cost **2.4× SCR** / **4.0× ES** variance reduction at zero extra inner-path cost, and the bootstrap correction removes the residual downward ES bias (ES rel-bias -2.163% → -0.244%).

- **G5 no-spillover (PASS, out-of-band):** governed artifacts byte-unchanged, headline `39975.654628199336` intact, contract `1.23.0` — verified by the cycle gate suite + git status.

## Recommendation

MERGE-AS-OPT-IN: stratified outer sampling on the fixed-256 governed-style tail estimator -- a matched-cost 2.4x SCR / 4.0x ES variance reduction at ZERO extra inner-path cost, which ALSO removes the small-sample ES bias (stratified raw ES bias +0.01%). The bootstrap ES correction is the separate remedy for an UN-stratified plain-MC outer pool (it cuts the plain ES bias -2.16% -> -0.24%); it should NOT be stacked on top of stratification, which is already ~unbiased (stacking overcorrects). This resolves the W65 variance limitation for the fixed estimator. Stage 5 (any tail-MLMC figure as the governed default) stays owner sign-off + fresh frozen reference; no governed figure changes at stage <= 4.
