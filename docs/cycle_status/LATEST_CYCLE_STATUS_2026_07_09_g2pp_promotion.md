# Cycle Status — 2026-07-09 — §4.1 #7 G2++ Two-Factor Rate-Model Promotion

**Agent:** Claude Cowork (`actuarial-model-daily-improvement`)
**Item:** Roadmap §4.1 #7 (MR-004) — G2++ two-factor rate model promotion
**Outcome:** DONE — tests GREEN, evidence UNSIGNED, governed headline untouched
**Lock:** `2026-07-09T14:07Z-bc9c` (claude), acquired clean (preflight PROCEED)

## Conclusion

G2++ is a selectable production rate model in `ScenarioSet.generate(rate_model=
"g2pp")`; HW1F remains the default and is byte-for-byte unchanged. Opt-in only —
no governed headline moves. Highest-priority OPEN general-backlog item cleared;
§4.1 #1–#7 now DONE.

## Delivered

- **Code** (`par_model_v2/stochastic/esg_process.py`): `rate_model` selector +
  `g2_params` on `generate()`; `resolve_rate_model` / `available_rate_models` /
  `RATE_MODEL_REGISTRY` (fail-loud); `g2_params` support in
  `ParameterSnapshot.from_process_params`; new `CurveTwistValidator`
  (+ `CurveTwistEvidenceReport` / `CurveTwistCheck`).
- **Evidence**: `scripts/build_g2pp_promotion_evidence.py` →
  `docs/validation/G2PP_PRODUCTION_PROMOTION.json`
  (`g2pp-production-promotion-1.0`, inputs_digest `3f527cca…`, UNSIGNED).
- **Docs**: `docs/G2PP_PRODUCTION_PROMOTION_CARD.md`;
  `docs/ESG_G2PP_RATE_PROCESS_DESIGN.md` §Production Promotion; roadmap §4 #7 →
  DONE + §5 cycle-log row.
- **Tests**: `tests/test_g2pp_promotion.py` (22, GREEN).

## Evidence summary (educational proxy; UNSIGNED)

| Check | Result |
|---|---|
| HW1F fallback byte-identity (Q/P) | PASS (pinned digests) |
| Swaption fit (proxy ATM surface) | RMSE 58.0 vol bps; G-SWPN gate PASS |
| Q-measure martingale (promoted set) | PASS (max rel err 1Y 0.7% / 10Y 3.3%, tol 3.5%) |
| Curve twist (short↔10Y change corr) | 0.889 G2++ vs 0.984 HW1F; gap 0.095; factor corr −0.947 |

## Verification

- New suite: 22/22 GREEN.
- Regression via minimal pytest shim (scipy/pytest unavailable in the
  network-restricted sandbox): test_esg_process 79, test_phase20_g2pp_rate 7,
  test_phase20_market_consistency 14, test_phase20_g2pp_swaption 14,
  test_scenario_adequacy 24, test_sensitivity 45, test_esg_adapter 77 → 282
  passed.
- The 2 `test_phase20_task4_g2pp_aggregation` failures are pre-existing
  scipy-absence, A/B-confirmed identical on pristine main (not this change).

## Governance

Purely additive, opt-in diagnostic. Governed TVOG/aggregation headline
untouched. Re-baselining the headline onto G2++, and replacing the prototype
ZCB with the full-variance `EnhancedG2PlusRateProcess` analytic form in the
production generate path, remain owner-gated.

## Next queued

§4.1 #8 — Stochastic bonus declaration (pathwise TVOG).
