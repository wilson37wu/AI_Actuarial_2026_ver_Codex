# Cycle Status — W58 (claude, 2026-06-18 18:00Z window)

## Task
MLMC inner-estimator **stage-2 prototype** — the next step in the design-note→prototype
sequence opened by W57 (`docs/research/MLMC_NESTED_LOOP_DESIGN_NOTE_20260618.md`,
Option 3 of the model-improvement matrix). Estimator-only, additive, opt-in;
**not wired into the governed run**.

## What shipped (all NEW files — zero governed artifacts touched)
- `par_model_v2/projection/mlmc_inner_estimator.py` — telescoping multilevel inner
  estimator over a geometric inner-path ladder `N_l = N0·M^l` with antithetic
  fine/coarse coupling, MLMC optimal-allocation diagnostic, and a faithful adapter to
  the governed `_inner_pathwise_pvs`. Opt-in `InnerEstimator`; default stays `"fixed"`.
- `tests/test_mlmc_inner_estimator.py` — **8/8 pass** (analytic closed-form testbed +
  real governed-sampler smoke equivalence).
- `scripts/build_mlmc_stage2_validation.py` → `docs/validation/MLMC_STAGE2_PROTOTYPE_20260618.{json,md}`.

## Pre-registered gates (design note)
| Gate | Stage | Result |
|---|---|---|
| G2 — ≤1% rel-err vs fixed-256 | 2 | **PASS** — analytic 0.42%; **real governed inner sampler max 0.115%** (4 short-rate states) |
| G4 — staged==monolithic reproducibility | 2 | **PASS** (same seed → identical estimate & cost) |
| G5 — governed-artifact no-spillover | 2 | **PASS** (governed artifacts byte-unchanged) |
| G3 — ≥2× net cost cut | 2 | **MEASURED 1.03×** matched-RMSE on the toy; ≥2× is a real-SCR (N_L=256) claim for stage 3 |
| G1 — frozen-snapshot headline equivalence | 3 | **DEFERRED** (needs wiring; owner-confirmable) |

## Verification (green + byte-stable)
- `build_offline_home_validate` **177/177**; `offline_home_loader_parity` **10/10**;
  `tests/test_offline_home_validate` **4/4**; `node --check` clean (2 inline blocks).
- `offline_home.html` md5 `03d6538d3cae9efb83062ecbfab096e9` (byte-identical W52–W58).
- Governed artifacts (`ui_data.json`, `ui_app.html`, `combined_model_app.html`,
  `model_summary_card.html`, `model_result_viewer.html`) **byte-unchanged** (empty git diff).
- Headline **39,975.654628199336** intact (1 occ); contract **1.23.0** unchanged.

## Coordination
Git done in a fresh `/tmp` ext4 clone of `origin/main`; mount `.git` untouched.
Lock acquired (`bd8f5ea`) and will be released at cycle end. `origin/main` was ahead of the
Downloads mount (W46) — origin remains source of truth.

## Next (owner)
Approve **MLMC stage 3** (wire `inner_estimator='mlmc'` into the governed nested run,
run G1 frozen-snapshot equivalence + confirm G3 ≥2× at N_L=256) — **auto-runnable, no
headline re-baseline** — or pick **A** MR-LONGEV-1 / **B** LSMC [sign-off] / **C** Phase IGUI /
**D** Packaging / **E** Freeze. MLMC-as-default (stage 5) needs sign-off.
