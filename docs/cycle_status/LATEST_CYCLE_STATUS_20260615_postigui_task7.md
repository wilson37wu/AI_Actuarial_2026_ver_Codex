# Latest Cycle Status - Post-Phase-IGUI Task 7 (MR-VR-2 OUTER-loop variance reduction)

**Owner agent:** Claude Cowork (06:00/18:00 UTC window)
**Cycle:** 2026-06-15 (~15:08-15:30 UTC) | **Lock cycle_id:** 2026-06-15T15:08Z-d884
**Status: COMPLETE - PASS.** Exactly one task done (the single in_progress item).

## What was done
Implemented candidate **MR-VR-2**: scrambled-Sobol randomised-QMC + control-variate
variance reduction for the **OUTER capital / 99.5% SCR estimator**, against the six
pre-registered gates G1-G6 frozen in the Task 6 design note. Efficiency-only,
additive/disclosed; **no model parameter change, no copula structure** (Phase 30
stop-rule honoured).

New files:
- `par_model_v2/projection/outer_loop_variance_reduction.py` (implementation)
- `scripts/build_postigui_task7_outer_variance_reduction.py` (builder + governance)
- `tests/test_postigui_task7_outer_variance_reduction.py` (12 unit tests)
- `docs/validation/POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION.{json,md}`
- `docs/POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION_REPORT_CARD.md`

## Headline results
- Validation gates **20/20**; unit tests **12/12**; idempotent digest `84f96dcf...`.
- Work-normalised OUTER 99.5% SCR variance-reduction ratios (>=200-replicate bootstrap CIs):
  **Sobol-RQMC 536x / stratified 558x / RQMC+CV 496x**. Best technique: stratified.
- Control-target correlation **rho = 0.812**, theoretical mean-leg reduction
  **1/(1-rho^2) = 2.93x** (measured mean-leg CV ratio 3.02x - agrees).
- **Measured-not-assumed tail finding (DISCLOSED):** control-variate-ALONE = **0.93x**
  on the 99.5% SCR target (sub-1.5x) - it acts only on the cheap mean leg, not the
  quantile leg. This is the OUTER-loop analogue of MR-VR-1's antithetic-ineffective-
  at-99.5% disclosure. RQMC / stratification are the levers for the quantile leg.
- Estimators **UNBIASED**: control-variate beta fit out-of-sample on a 200k held-out
  pilot; replicate means within 0.5% of crude/analytic.
- Governed frozen-t headline 39,975.654628199336 **BIT-IDENTICAL** (dev 0).
- Indicated adoption dSCR **+0.000316%** of headline (immaterial), **REPORTED-NOT-applied**.

## Governance
ChangeRecord `3ebea247...` opened **OWNER_REVIEW** (governance_change). Store now
**117 change records / 145 audit entries**, audit integrity OK. Governance re-run is
idempotent (adds nothing).

## Regression
Sibling VR/design tests green: Task 4 11/11, Task 5 14/14, Task 6 design-note import-clean.
`ui_app.html` untouched (report-only cycle).

## State / next
- Efficiency/diagnostic pool **MR-CAL-1 + MR-VR-1 + MR-VR-2 now EXHAUSTED** under the
  Phase 30 stop-rule (copula-structure candidates barred).
- **Next (Task 8):** ADDITIVE, model-output-only offline-UI efficiency panel for the
  MR-VR-2 outer-loop study (contract bump only), OR owner pivot.
- **Owner decisions pending (NOT auto-run):** MR-LONGEV-1 longevity 5th-driver
  (parameter-adding model-FORM change, needs sign-off); packaging A/B/C; or declare the
  auto-development frontier complete and freeze. MR-016/MR-017 owner-pending.
