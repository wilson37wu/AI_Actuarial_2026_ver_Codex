# MLMC inner-estimator — stage-2 prototype validation (W58)

_Generated 2026-06-18T15:17:50Z._

**Classification:** estimator-only; ADDITIVE; opt-in; no model-form change; no contract bump; governed headline unchanged. Not wired into the governed run; governed headline `39,975.654628199336` and all governed artifacts unchanged.

## Analytic nested testbed (closed-form estimand)

- Inner-path ladder: `[8, 16, 32, 64, 128]` (finest N_L = 128).
- Closed-form estimand at N_L: `0.00051953`.
- Single-level estimate: `0.00051851` (SE 6.05e-06, cost 768,000).
- MLMC estimate: `0.00052070` (SE 1.05e-05, cost 248,192).
- Equivalence rel-err (MLMC vs single-level): `0.422%`.
- Matched-RMSE speedup: `1.03x`.
- Reproducible (same seed -> identical): `True`.

## Governed inner sampler (real model machinery)

- Conditional-mean equivalence at 4 short-rate states, finest N_L = 256.
- Max rel-err (MLMC vs fixed-256 conditional mean): `0.115%`.

## Pre-registered gates

| Gate | Stage | Status |
|---|---|---|
| G1_same_headline_equivalence_frozen_snapshot | 3 | DEFERRED |
| G2_le_1pct_relerr_vs_fixed256 | 2 | PASS |
| G3_ge_2x_net_cost_cut | 2 | MEASURED |
| G4_staged_eq_monolithic_reproducibility | 2 | PASS |
| G5_governed_artifact_no_spillover | 2 | PASS |

**Stage-3 (owner-confirmable):** wire the opt-in estimator into the governed nested run behind `inner_estimator='mlmc'`, then run G1 (frozen-snapshot headline equivalence) and confirm G3 >=2x at N_L=256. Making MLMC the default for any governed figure is stage 5 and requires owner sign-off.
