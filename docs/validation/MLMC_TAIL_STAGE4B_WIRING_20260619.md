# MLMC quantile/ES tail estimator — stage-4b wiring (W67)

_Generated 2026-06-19T00:18:25Z._

**Classification:** efficiency / estimator-only WIRING; ADDITIVE; OPT-IN; default OFF; no model-form change; no contract bump; no headline re-baseline; no owner sign-off consumed. Governed headline `39975.654628199336` and all governed artifacts byte-unchanged; contract `1.23.0`; default estimator stays `fixed`.

## Purpose

Stage 4b **wires** the W66 stage-4 tail tools (stratified outer sampling + ES bootstrap bias correction) into one mode-selectable entry point on the opt-in tail path, `tail_capital_diagnostics(variance_reduction=…, es_bias_correction=…)` — the tail analogue of the W60 stage-3 `engine_mean_liability_diagnostics` mean wiring. The **default is OFF and bit-identical** to the pre-W67 plain fixed-256 estimator.

## API

- Entry point: `par_model_v2.projection.mlmc_inner_estimator.tail_capital_diagnostics`
- Resolver: `par_model_v2.projection.mlmc_inner_estimator.resolve_tail_outer_sampler` — modes `['none', 'stratified', 'stratified_antithetic']`
- Default: `variance_reduction='none', es_bias_correction=False` (the governed-style fixed-256 estimator)

## Frozen-snapshot equivalence (gate G-W67a)

Config `{'mu_x': 0.02, 'sigma_x': 0.01, 'sigma_inner': 0.05, 'n_outer': 4000, 'n_inner': 256, 'seed': 20260619}` → frozen VaR `0.04820076634696653`, ES `0.051878781816970275`, SCR `0.027892778037151456`. The default `none` mode reproduces these **bit-for-bit** and equals a plain-outer `nested_single_level_tail` call bit-for-bit: **`True`**.

## Mode-selectable variance reduction (gate G-W67b, matched cost)

| Fn | matched-cost variance-reduction factor |
|---|---|
| VaR | 2.62× |
| ES | 2.86× |
| SCR | 2.46× |

- Stratified mode keeps the **same inner-path cost** as plain, so the factor is a matched-cost speedup. **G3 ≥2× on SCR: `True`**.

## Determinism + ES correction (gate G-W67c)

- Same seed → identical dict; ES correction deterministic and obeys the bootstrap identity `es_bc == 2·es_raw − boot_mean`; correction is additive (core VaR/ES/SCR unchanged): **`True`** (example es_bc `0.052048`, bias_hat `-1.689591e-04`).

## Verdict

**Overall: `PASS`.** G-W67a frozen-snapshot equivalence `True`; G-W67b mode-selectable VR `True`; G-W67c determinism/ES-identity `True`; G-W67d no-spillover `True`.

## Recommendation

MERGE-AS-OPT-IN WIRING: tail_capital_diagnostics exposes the W66 stratified outer sampler (and the optional ES bootstrap correction) as a selectable variance-reduction MODE on the opt-in tail path. The default 'none' mode is bit-identical to the pre-W67 plain fixed-256 estimator (frozen-snapshot equivalence), so the governed headline is untouched. Selecting 'stratified' delivers a matched-cost 2.46x SCR / 2.86x ES variance reduction at ZERO extra inner-path cost. Stage 5 (any tail-MLMC figure as the governed default) stays owner sign-off + a fresh frozen reference.
