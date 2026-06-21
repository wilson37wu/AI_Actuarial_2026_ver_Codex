# Consumer Note — Selecting the Tail Variance-Reduction Mode (MLMC stage-4b)

**Window:** W68 (claude, 2026-06-19) · **Type:** consumer-doc / verification pass
**Classification:** documentation + verification only — **no model-form change, no contract bump, no headline re-baseline, no owner sign-off consumed.**

---

## TL;DR

The W67 stage-4b wiring exposes the W66 tail variance-reduction tools as **one
mode-selectable entry point** on the **opt-in** nested-tail path:
`par_model_v2.projection.mlmc_inner_estimator.tail_capital_diagnostics(...)`.

- **Default is OFF** (`variance_reduction="none"`, `es_bias_correction=False`) and is
  **bit-identical** to a plain fixed-256 `nested_single_level_tail` call and to the
  frozen W67 reference snapshot. The governed SCR/VaR/ES headline
  **39975.654628199336** is untouched.
- Selecting **`"stratified"`** (or `"stratified_antithetic"`) cuts the Monte-Carlo
  **replicate variance** of the 99.5% tail VaR / ES / SCR at the **same inner-path
  cost** (stratification is free) — measured this cycle at **VaR 2.62× / ES 2.86× /
  SCR 2.46×**.
- This is an **efficiency/estimator** affordance for *callers who opt in* (e.g. tail
  sensitivity studies, replicate-stability work). It does **not** change any governed
  figure. Making any tail-MLMC figure the governed default is **stage 5** and requires
  **owner sign-off + a fresh frozen reference**.

---

## The opt-in API

```python
from par_model_v2.projection.mlmc_inner_estimator import (
    tail_capital_diagnostics, resolve_tail_outer_sampler, TAIL_VR_MODES,
)

TAIL_VR_MODES  # ('none', 'stratified', 'stratified_antithetic')

tail_capital_diagnostics(
    *,
    mu_x, sigma_x, sigma_inner,        # governed-style 1-D Gaussian tail testbed
    alpha=0.995,                       # tail confidence (governed = 99.5%)
    n_outer, n_inner=256, seed=20260619,
    variance_reduction="none",         # one of TAIL_VR_MODES
    es_bias_correction=False,          # attach W66 bootstrap-corrected ES
    es_bias_n_boot=200, es_bias_method="ru",
) -> dict
```

The estimand is the **governed-style analytic nested tail estimator** — a 1-D Gaussian
outer driver `X ~ N(mu_x, sigma_x)` with inner liability draws `N(X, sigma_inner)` —
the exact testbed the W66 stage-4 study validated. `variance_reduction` selects the
**outer-sampling mode** via `resolve_tail_outer_sampler`; unknown modes raise
`ValueError`.

## Copy-paste example

```python
# (1) Governed-identical baseline — bit-for-bit the frozen W67 snapshot.
base = tail_capital_diagnostics(
    mu_x=0.02, sigma_x=0.01, sigma_inner=0.05,
    n_outer=4000, n_inner=256, seed=20260619,
    variance_reduction="none")
# base["var"] == 0.04820076634696653
# base["es"]  == 0.051878781816970275
# base["scr"] == 0.027892778037151456

# (2) Same cost, lower replicate variance — opt in to stratified outer sampling.
strat = tail_capital_diagnostics(
    mu_x=0.02, sigma_x=0.01, sigma_inner=0.05,
    n_outer=4000, n_inner=256, seed=20260619,
    variance_reduction="stratified")
# strat["inner_path_cost"] == base["inner_path_cost"]   # cost is unchanged
# point estimates differ slightly; their REPLICATE variance is ~2.5-2.9x smaller
```

## Which mode to pick

| Goal | Mode | Notes |
|---|---|---|
| Reproduce/justify the governed headline | `none` | Bit-identical to plain fixed-256; this is the only mode that is part of the governed contract. |
| Tighter tail VaR/ES/SCR at fixed budget | `stratified` | Free variance reduction (no extra inner paths). Recommended opt-in for tail studies. |
| Maximum outer-variance reduction | `stratified_antithetic` | Adds antithetic pairing on top of stratification. Use when the outer driver dominates replicate noise. |

**ES bias correction.** `es_bias_correction=True` attaches the W66 bootstrap-corrected
ES (`es_bias_corrected`, `es_bias_hat`, ...) — useful at **small `n_outer`** on the
**plain (`none`)** pool, where the optimizer's-curse ES bias is largest.
**Do NOT stack it on a stratified pool:** stratification already removes the
small-sample ES bias, so stacking over-corrects. Rule of thumb: `none` + bias
correction for small-sample ES; `stratified` *without* bias correction for variance.

## Return-dict keys

`estimand, variance_reduction, es_bias_correction, alpha, n_outer, n_inner,
inner_path_cost, var, es, scr, mean_liability, var_empirical, es_empirical,
governed_default, note` — plus, when `es_bias_correction=True`:
`es_bias_corrected, es_bias_hat, es_bias_boot_mean, es_bias_n_boot`.
The dict is JSON-serialisable.

---

## W68 verification evidence (this cycle)

Re-ran in a throwaway venv (numpy 2.2.6 / scipy 1.15.3 / pandas / pytest 9.1.0):

- **Offline-UI byte-stability:** `build_offline_home_validate` **177/177**;
  `offline_home_loader_parity.cjs` **10/10**; `tests/test_offline_home_validate` **4/4**;
  `offline_home.html` md5 **03d6538d3cae9efb83062ecbfab096e9** (byte-identical W52–W68).
- **MLMC suite:** **53 passed / 0 failed** (inner-estimator, stage-3 wiring, tail
  estimator, tail stage-3/4/4b — the 3 scipy-oracle tests that env-skipped at W67 now
  execute and pass).
- **Stage-4b re-validation (deterministic):** `g_w67a` frozen-snapshot equivalence,
  `g_w67b` mode-selectable VR, `g_w67c` determinism + ES bootstrap identity, `g_w67d`
  no-spillover — **all PASS**; matched-cost factors **VaR 2.620× / ES 2.858× / SCR
  2.456×** (G3 ≥2× PASS). `git status` clean after re-running the builder ⇒ outputs
  reproduce byte-for-byte.
- **Governed anchors intact:** headline **39975.654628199336** present (32 occ. in
  `GOVERNANCE_STORE.json`); `ui_data.json` contract **1.23.0**; no governed artifact
  modified (only this new note + state/log/cycle-status added).

## Boundaries

- Everything above is **opt-in** and changes **no governed figure**. The governed
  SCR/VaR/ES remains the **fixed single-level** estimate.
- **Stage 5** — promoting any tail-MLMC / variance-reduced figure to the governed
  default — is **owner-gated**: it requires explicit owner sign-off and a fresh frozen
  reference snapshot, and would carry a contract bump.

## References

- Stage-4b wiring evidence: `docs/validation/MLMC_TAIL_STAGE4B_WIRING_20260619.md`
- Stage-4 study: `docs/validation/MLMC_TAIL_STAGE4_VALIDATION_20260619.md`
- Quantile/ES design note: `docs/research/MLMC_QUANTILE_ESTIMATOR_DESIGN_NOTE_20260619.md`
- Owner decision matrix: `docs/research/MODEL_IMPROVEMENT_RESEARCH_20260617.md`
- Source: `par_model_v2/projection/mlmc_inner_estimator.py`
  (`tail_capital_diagnostics`, `resolve_tail_outer_sampler`, `TAIL_VR_MODES`)
