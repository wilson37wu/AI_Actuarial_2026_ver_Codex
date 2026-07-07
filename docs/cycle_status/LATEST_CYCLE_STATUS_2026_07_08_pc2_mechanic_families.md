# Cycle Status — 2026-07-08 — PC-2 extended mechanic families (COMPLETES track 4.0d)

**Agent:** Claude Cowork (scheduled `actuarial-model-daily-improvement`)
**Item:** PC-2 — extend mechanic families (whole-life par, term assurance, annuity) + per-product expense/decrement overrides (owner directive 2026-07-03, roadmap §4.0d)
**Outcome:** DONE — track 4.0d COMPLETE; priority reverts to the general backlog (§4.1, next: #2 HW1F swaption calibration execution)

## What shipped

- **Three new mechanic families** in `portfolio_construction.PRODUCT_FAMILIES`, the CF projection engine and the governed loader enum:
  - `WL_PAR_2026` — whole-life participating; RB mechanics under a documented endowment-at-limit convention; mapped to the PAR RB line (`USER_PRODUCT_LINE_MAP`) so composed WL books run END-TO-END through the stochastic engine's representative-product path.
  - `TERM_2026` — level term assurance; guaranteed SA on death only, NO maturity benefit; optional surrender (`surrender_value_pct` default 0.0).
  - `ANNUITY_2026` — deferred life annuity (`sum_assured` = notional): deferral-phase premiums accumulate the asset-share proxy; from vesting a GUARANTEED monthly annuity (`annuity_rate` x notional / 12) posts to the NEW `annuity_guaranteed` bucket; death-in-deferral returns the asset share; deferral-only surrender; post-vesting lapse lock-in (`lapse_stop_month`); composer enforces term > deferral.
- **Non-par scope note:** `TERM_2026`/`ANNUITY_2026` carry no participation/financial-option guarantee in this model form; `split_model_points` routes them (with GMMB) OUT of the stochastic PAR book; their cash flows are covered by the deterministic CF set + /cashflows + /drilldown.
- **Per-product overrides** (`OVERRIDE_PARAMS`, any family, bounds-validated, applied ONLY when explicitly set): `acq_expense_pct`, `renewal_expense_pct`, `renewal_expense_fixed_monthly`, `mortality_multiplier`, `lapse_multiplier` — threaded consistently through `_decrements` / `_premium_expense` / `_asset_share_proxy` for all six projectors; absent keys regression-tested BIT-IDENTICAL to legacy.
- **Tenth liability bucket** `annuity_guaranteed` — suffix-classified guaranteed everywhere (CF-3 chart split, GD-2 drilldown, rollups); CSV/JSON additive.
- Loader (`ALLOWED_PRODUCT_TYPES`, vested-bonus rules, `n_par` incl. WL), `igui_model_points` (enum, lockstep literal, aliases wl/term/annuity, help), default catalogue (+`WL_PAR_STD`/`TERM_STD`/`ANNUITY_DEF`; /portfolio page renders families dynamically).

## Tests

- 23 new tests in `tests/test_pc2_mechanic_families.py` (registry, catalogue/composer validation, override passthrough + bit-identity, all three projector mechanics, loader acceptance/rejection, PAR/non-PAR routing, WL-on-RB-line build, end-to-end CF set from composed inputs).
- 194 GREEN across `test_pc2_* / test_pc1_* / test_cf1-3_* / test_gd1-4_* / test_user_inputs / test_portfolio_generator / test_phase_igui_task3 (22) / test_pc1c_nav / test_igui_page_scripts_syntax / test_agent_lock_identity` incl. live HTTP roundtrips.
- 2 pre-existing owner-gated `ui_app.html` sha-baseline failures unchanged — verified pre-existing on clean main via stash A/B.

## Governance

Governed headline figures untouched (no default-input change; new families are additive input capability). Catalogue rates/parameters remain UNSIGNED scenario inputs pending Model Owner approval. Phase 38 Task 3 stays owner-gated.

## Operational note

First attempt this cycle was interrupted by a sandbox VM restart after tests had passed but before docs/commit; the same fresh claude lock (18:07Z acquire, TTL 120) was reused and the work re-applied from scratch in a new clone. Two consecutive lock-acquire commits on main (a810d11, 63dc38e) stem from the network flap during the first acquire — both claude/PC-2, harmless.

**Next queued item:** §4.1 #2 — execute HW1F swaption calibration on live/proxy quote set (parameter card + fit diagnostics, UNSIGNED).
