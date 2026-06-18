# MLMC inner-estimator — stage-3 wiring validation (W60)

_Generated 2026-06-18T17:15:39Z._

**Classification:** estimator-only; ADDITIVE; opt-in; wired behind inner_estimator='mlmc' (default 'fixed'); no model-form change; no contract bump; governed headline unchanged. Governed headline `39,975.654628199336` and all governed artifacts unchanged; contract unchanged.

## What changed this stage

The opt-in MLMC inner estimator (W58 stage-2 prototype) is now **wired into the governed engine** behind `NestedStochasticTVOGEngine.run(inner_estimator='mlmc')`. The default stays `'fixed'`, so every governed run is byte-identical to before. Selecting `'mlmc'` additionally attaches mean-liability efficiency diagnostics — it never alters the governed SCR/VaR/ES, which is a *quantile* of the L(X) distribution and stays fixed single-level.

## Governed-config run (n_outer=256, n_inner=256, seed=42)

- Fixed governed SCR_proxy: `20319.3258`.
- Governed capital bit-identical fixed-vs-mlmc: `True`.
- Fixed-run `.summary()` unchanged (no MLMC keys): `True`.
- Inner-path ladder: `[16, 32, 64, 128, 256]` (finest N_L = 256).
- Fixed-256 mean liability: `84262.832850`.
- MLMC mean liability: `84256.831725` (SE 5.03e+02, inner cost 20,480).
- G1 mean-liability rel-err: `0.0071%`.
- G3 matched-RMSE speedup at N_L=256 (real sampler): `3.444x`.

## Pre-registered gates

| Gate | Stage | Status |
|---|---|---|
| G1_frozen_snapshot_equivalence | 3 | PASS |
| G3_ge_2x_net_cost_cut_at_NL256 | 3 | PASS |
| G4_staged_eq_monolithic_reproducibility | 3 | PASS |
| G5_governed_artifact_no_spillover | 3 | PASS |

**Remaining owner gate (stage 5):** stage 5: making MLMC the default for a governed quantile figure (SCR/VaR/ES) needs owner sign-off + a fresh frozen reference; the quantile functional is non-linear so a quantile-MLMC estimator is required first.
