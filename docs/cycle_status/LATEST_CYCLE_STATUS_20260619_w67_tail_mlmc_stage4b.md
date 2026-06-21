# Latest cycle status — W67 (claude) — MLMC tail-estimator STAGE 4B WIRING

**UTC:** 2026-06-19 ~00:20Z window · **Agent:** claude · **Verdict:** PASS (4/4 gates) · **Type:** efficiency/estimator-only, ADDITIVE, OPT-IN, default OFF

## What shipped
Wired the W66 stage-4 tail variance-reduction tools into one mode-selectable entry point on the opt-in tail path:
`par_model_v2/projection/mlmc_inner_estimator.tail_capital_diagnostics(variance_reduction in {none, stratified, stratified_antithetic}, es_bias_correction=...)`,
with `resolve_tail_outer_sampler(mode, mu, sigma)` and `TAIL_VR_MODES`. Tail analogue of the W60 stage-3 `engine_mean_liability_diagnostics` mean wiring.

## Gates (build_mlmc_tail_stage4b_wiring.py → PASS)
- **G-W67a frozen-snapshot equivalence:** default mode == plain fixed-256 `nested_single_level_tail` and == frozen reference, bit-for-bit (VaR 0.04820076634696653 / ES 0.051878781816970275 / SCR 0.027892778037151456).
- **G-W67b mode-selectable VR (matched cost):** stratified VaR 2.62× / ES 2.86× / SCR 2.46× at zero extra inner-path cost (G3 ≥ 2× PASS).
- **G-W67c determinism + ES identity:** deterministic; `es_bc == 2·es_raw − boot_mean`; ES correction additive (core figures unchanged).
- **G-W67d no-spillover:** governed headline `39975.654628199336`, contract `1.23.0`, offline_home.html md5 `03d6538d3cae9efb83062ecbfab096e9` — all byte-unchanged.

## Tests
MLMC tail suites **38 passed / 0 failed** (new `test_mlmc_tail_stage4b.py` 12/12; stage4 9; tail_estimator 10; inner 7). 3 scipy-oracle checks skipped (scipy absent in sandbox — env limit, not a regression).

## Files
- Modified: `par_model_v2/projection/mlmc_inner_estimator.py` (+123, additive symbols only)
- New: `scripts/build_mlmc_tail_stage4b_wiring.py`, `docs/validation/MLMC_TAIL_STAGE4B_WIRING_20260619.{json,md}`, `tests/test_mlmc_tail_stage4b.py`
- State/docs: `.claude-dev/MODEL_DEV_STATE.json`, `MODEL_DEV_TASK_PROMPT.md` (W68 pointer), `MODEL_DEV_LOG.md`

## Reconciliation
Structured `in_progress` "Post-Phase-IGUI Task 8" was STALE (offline-UI MR-VR-2 panel already shipped on origin as `postigui_vr2` / contract 1.23.0) → moved to `completed`.

## Next (W68)
Auto: a single verification / consumer-doc pass (no new graphic, no model-FORM change). OR owner pivot — (A) MR-LONGEV-1 longevity 5th driver [model-form, sign-off]; (B) LSMC SCR proxy [sign-off]; (C) Phase IGUI extensions [auto]; (D) packaging A/B/C build/CI [auto]; (E) declare frontier COMPLETE & FREEZE. Stage 5 (tail-MLMC as governed default) needs owner sign-off + a fresh frozen reference.
