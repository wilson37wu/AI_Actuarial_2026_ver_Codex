# G2++ Two-Factor Rate-Model Production Promotion

**Card ID:** `G2PP-PRODUCTION-PROMOTION`
**Roadmap item:** §4.1 #7 (MR-004)
**Status:** DONE — G2++ selectable in the governed ESG path; HW1F remains the default.
**Evidence:** `docs/validation/G2PP_PRODUCTION_PROMOTION.json` (schema `g2pp-production-promotion-1.0`, UNSIGNED)
**Builder:** `scripts/build_g2pp_promotion_evidence.py`
**Tests:** `tests/test_g2pp_promotion.py` (22, GREEN)

## Conclusion

The validated G2++ two-factor Gaussian short-rate process (Phase 20) is now a
**selectable production rate model** in `ScenarioSet.generate(...)`. Callers opt
in with `rate_model="g2pp"`; the one-factor Hull-White (HW1F) model stays the
default and is **byte-for-byte unchanged**. The promotion is a purely additive,
opt-in capability: no governed headline figure moves. Re-baselining the headline
onto G2++ is a separate, owner-gated decision.

## What changed (`par_model_v2/stochastic/esg_process.py`)

1. **Selector.** `ScenarioSet.generate(..., rate_model="hw1f", g2_params=None)`.
   `resolve_rate_model()` maps aliases (`g2pp`, `g2++`, `two-factor`, …) to a
   canonical key and raises on anything unknown (fail-loud — a config typo can
   never silently swap the rate model). `available_rate_models() == ("g2pp",
   "hw1f")`.
2. **G2++ path.** When `g2pp` is selected the generator builds
   `G2PlusRateProcess`, prices ZCBs with the G2++ affine formula, and emits two
   diagnostic factor columns `g2pp_x` / `g2pp_y` alongside the standard ESG
   columns. The equity/FX blocks are unchanged — they consume the simulated
   short-rate paths regardless of which rate model produced them.
3. **HW1F fallback identity.** The extra G2++ Brownian draw (factor *y*) is taken
   **only** in the `g2pp` branch and **after** the HW1F draws, so the HW1F RNG
   stream — and every governed HW1F headline — is untouched. Pinned digests guard
   this (Q `1aa0b3f4…`, P `bf7ede63…`).
4. **Snapshot.** A `g2_params` snapshot records `rate.g2pp.*` keys (not
   `rate.hw1f.*`) and points `model_equation_refs` at
   `G2PlusRateProcess._simulate_arrays`. The HW1F snapshot is unchanged.
5. **Curve-twist validator.** New `CurveTwistValidator` quantifies short-vs-long
   rate-change decorrelation and compares it to a one-factor benchmark.

## Evidence (educational proxy calibration; UNSIGNED)

| Dimension | Result |
|---|---|
| Selectability | `rate_model` selector + fail-loud resolver; `g2pp_x`/`g2pp_y` diagnostics |
| HW1F fallback | Default Q/P paths byte-identical to pinned digests (regression-locked) |
| Swaption fit | G2++ calibrated to the ATM proxy surface: RMSE **58.0 vol bps**, 24 quotes, G-SWPN gate **PASS** |
| Q-measure martingale | **PASS** — discounted-ZCB reconciliation, max rel. error 1Y 0.7% / 10Y 3.3% (tol 3.5%) |
| Curve twist | short↔10Y change corr **0.889 (G2++) vs 0.984 (HW1F)**, decorrelation gap **0.095**; factor corr −0.947 recovers the −0.95 calibrated ρ |

The one-factor HW1F set **fails** the curve-twist check by construction (a single
factor moves every tenor together — parallel shifts only). That contrast is the
evidence the two-factor promotion delivers: genuine, independent short/long
moves (twist and steepening).

## Scope and limitations

- **Opt-in only.** Governed TVOG / aggregation headlines run on HW1F and are
  unmoved. G2++ is available to callers and diagnostics.
- **UNSIGNED.** The swaption surface is the synthetic educational proxy
  (`g2pp_swaption.educational_proxy_vol_grid`), not a validated market surface;
  the prototype ZCB omits the second-order G2++ variance term, which is the
  source of the ~3.3% 10Y martingale residual (inside tolerance). Production use
  and any headline re-baseline require a validated market surface + independent
  review (IA TAS M §3.6).
- **Next.** Owner decision on whether/when to re-baseline the headline onto
  G2++, and (if pursued) swapping the prototype ZCB for the full-variance
  `EnhancedG2PlusRateProcess` analytic form in the production generate path.
