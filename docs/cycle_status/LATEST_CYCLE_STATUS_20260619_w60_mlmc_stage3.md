# Cycle status — W60 (claude, 2026-06-19 18:00 UTC)

## Task
MLMC **stage 3** — wire the opt-in `inner_estimator='mlmc'` into the governed
nested engine behind the flag (default `'fixed'`), then run the design-note
pre-registered gates **G1** (frozen-snapshot equivalence) and **G3** (≥2× net
cost cut at N_L=256). Auto-admissible; ADDITIVE; no model-form change; no
contract bump; governed headline byte-identical.

## Status: COMPLETE ✅ — all gates GREEN

| Gate | Result |
|---|---|
| G1 frozen-snapshot equivalence | **PASS** — governed capital bit-identical fixed-vs-mlmc; mean-liability rel-err **0.0144% ≤ 1%** |
| G3 ≥2× net cost cut at N_L=256 (REAL governed sampler) | **PASS** — matched-RMSE speedup **3.16×** |
| G4 staged==monolithic reproducibility | **PASS** |
| G5 governed-artifact no-spillover | **PASS** |

This closes the W58 stage-2 **G3 DEFERRED** (which measured only 1.03× on the
analytic toy); the 3.16× is on the real governed inner sampler at N_L=256.

## What changed (all additive / opt-in)
- `par_model_v2/projection/nested_stochastic_tvog.py` — `run(inner_estimator=...)`
  flag (`'fixed'` default, byte-identical; `'mlmc'` attaches diagnostics) and an
  additive `NestedTVOGResult.mlmc_diagnostics` field (fixed-run `.summary()`
  unchanged).
- `par_model_v2/projection/mlmc_inner_estimator.py` — new
  `engine_mean_liability_diagnostics()` stage-3 helper.
- `scripts/build_mlmc_stage3_validation.py` (new) →
  `docs/validation/MLMC_STAGE3_WIRING_VALIDATION_20260619.{json,md}` (new).
- `tests/test_mlmc_stage3_wiring.py` (new) — **8/8**.

## Key design point
The governed SCR/VaR/ES headline is a **quantile** of the L(X) distribution, for
which the current MLMC estimator is **not** unbiased; MLMC is unbiased for the
**mean liability** `E_X[L(X)]` only. So the wired `'mlmc'` path produces
mean-liability efficiency diagnostics and **never** moves the governed headline.
Making MLMC the default for a governed quantile figure is **stage 5** — it
requires owner sign-off **and** a quantile-MLMC estimator built first.

## Verification (byte-stable)
- `build_offline_home_validate` **177/177**; `offline_home_loader_parity`
  **10/10**; `tests/test_offline_home_validate` **4/4**.
- `offline_home.html` md5 `03d6538d3cae9efb83062ecbfab096e9` (byte-identical
  W52–W60); governed artifacts byte-unchanged; headline **39,975.65** (1 occ);
  contract **1.23.0**.
- Git in a fresh `/tmp` ext4 clone; mount `.git` untouched.

## Blockers / next (W61)
- No auto-admissible model work remains: MLMC stages 1–4 are done; **stage 5
  needs owner sign-off + a quantile-MLMC estimator**.
- Owner decision still gates: **A** MR-LONGEV-1 [model-form, sign-off] / **B**
  LSMC [sign-off] / **C** Phase IGUI [auto] / **D** Packaging A/B/C [auto] /
  **E** FREEZE.
- **OPS:** `/sessions` sandbox mount is 100% full — pytest had to be installed to
  a `/tmp` target; housekeeping needed.
