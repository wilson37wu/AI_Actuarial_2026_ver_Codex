# Validation — Quantile/ES tail-functional MLMC, stage-2 prototype (W64)

**Window:** W64 (claude, 2026-06-19). **Classification:** efficiency / estimator-only —
**opt-in**, **no** model-form change, **no** contract bump, **no** headline re-baseline,
**no** owner sign-off consumed. Implements **stage 2** of
`docs/research/MLMC_QUANTILE_ESTIMATOR_DESIGN_NOTE_20260619.md`.
Machine-readable evidence: `docs/validation/MLMC_TAIL_STAGE2_PROTOTYPE_20260619.json`.

## What shipped
`par_model_v2/projection/mlmc_inner_estimator.py` gains a tail-functional estimator
alongside the existing mean estimator (the governed path keeps `inner_estimator="fixed"`):

- `ru_objective` / `ru_minimise_var_es` — the **Rockafellar-Uryasev** representation
  `ES_a = min_q[q + E[(L-q)_+]/(1-a)]`, `VaR_a = argmin_q`. The Lipschitz `(L-q)_+`
  integrand gives clean MLMC level-difference variance decay; the empirical minimiser is
  found exactly at an order-statistic breakpoint in `O(n log n)`.
- `smoothed_cdf_var` — a sigmoid-smoothed empirical-CDF inversion as an **independent VaR
  oracle** (`O(h)` smoothing bias → 0 as `h → 0`).
- `nested_single_level_tail` — the governed-style fixed-`n_inner` VaR/ES/SCR benchmark
  (mirrors `capital_metrics_from_liabilities`: upper-tail `np.quantile`, tail-mean ES,
  `SCR = VaR − E[L]`), reporting both empirical and RU figures.
- `mlmc_nested_tail` — telescopes the RU objective `Φ(q)=E_X[(L(X)−q)_+]` **and** the mean
  `E_X[L(X)]` over the geometric inner-path ladder `N_l = n0·M^l` with **antithetic**
  fine/coarse coupling; recovers `VaR = argmin J`, `ES = min J`, `SCR = VaR − E[L]`.
  `L=0` is the exact single-level reduction (delegates to the RU minimiser).

## Results (deterministic; analytic Normal nested testbed)
- **Telescoping identity (gate G4):** `mlmc_nested_tail(L=0)` is **bit-for-bit identical**
  to `nested_single_level_tail` on VaR, ES, SCR and mean (matched seed/params).
- **RU minimiser recovers VaR/ES:** vs the closed-form Normal truth at `N=256`,
  VaR rel-err **0.64%**, ES rel-err **0.77%**; the RU VaR matches the empirical
  `np.quantile` VaR to **4.7e-6** (absolute).
- **MLMC L>0 consistency:** ladder `[16,32,64,128]`, VaR rel-err **5.3%** / ES **5.1%** vs
  the fixed-`N=128` benchmark at modest samples, with the (linear) mean to **0.33%**;
  error shrinks with outer count (e.g. finest `n_outer` 1000→3000 ⇒ VaR rel-err 5.9%→2.8%,
  s.d. 1.8e-3→1.0e-3), confirming a consistent estimator.
- **Determinism:** identical results under a fixed seed (staged == monolithic).

## Tests
- `tests/test_mlmc_tail_estimator.py` — **10 passed, 1 scipy-skip**.
- Regression `tests/test_mlmc_inner_estimator.py` + `tests/test_mlmc_stage3_wiring.py` —
  **15 passed, 1 scipy-skip** (unchanged).

## Gates
- **G4 identity:** PASS (bit-for-bit). **G5 no-spillover:** PASS — `offline_home.html`
  md5 `03d6538d3cae9efb83062ecbfab096e9` unchanged; headline `39975.654628199336`;
  contract `1.23.0`; all governed artifacts byte-identical (git shows only the additive
  module change + the new test).
- **G0 bias / G1 equivalence / G2 tail accuracy** deferred to **stage 3** (validation card
  on the frozen governed snapshot); **G3 cost / variance-decay** deferred to **stage 4**.

## Next
- **W65 = stage 3:** G0/G1/G2 bias + equivalence + tail-accuracy validation of
  `mlmc_nested_tail` against the fixed-256 governed benchmark on the frozen snapshot
  (bootstrap-SE bias gate; produce a validation card). Auto-runnable.
- Then **stage 4** (cost/variance-decay, G3 ⇒ merge-as-opt-in vs shelve). **Stage 5**
  (make quantile-MLMC the governed default) remains **owner sign-off only**.
