# Phase 26 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** 2026-06-08T07:27:56.682251+00:00
**Verdict:** PASS - **PHASE 26 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.8.0, additive)

A first-class **Full Re-Agg (P26)** panel:

- **Per-driver composition transform on the FROZEN copula (Task 2):**
  component-basis t SCR 39,976 vs re-anchored (LEVEL) 39,794 =
  **+0.46%**; relief on the cuttable component only with the per-scenario
  envelope clip; governed sigma 0.225 / alpha 0.7567 / benefit-share 0.8450
  UNCHANGED; copula FROZEN (df 2.9451, rho max|diff| 7.2e-16); 6/6 gates.
- **Frozen-copula margin bootstrap on the FULL component basis (Task 3):**
  t SCR mean 39,595, 95% CI [36,676, 42,943], SE **4.07%** of mean
  (<= 5%); the nested path-wise reference 46,639 sits **OUTSIDE the CI** ->
  the residual **14.29%** gap decomposes **91.9% COPULA-FORM** (the
  nested joint tail is heavier than the frozen t copula on standalone margins,
  exceeding the entire gaussian->t dependence-form sensitivity) and only
  **8.1% relief-surface** (bounded by the governed 1.16% OOS error).
- **Paired common-random-number delta matrix (Task 4):** composition
  correction (full - re-anchored, t) **+212 [46, 382]**,
  95% CI EXCLUDES zero (statistically significant) yet max |move| **0.55%**
  < 1% MR trigger -> MR-010/MR-014 numeric refresh **NOT required**, **MR-015
  stays free**; rank invariance re-verified (df/rho frozen); management-action
  relief dominates the capital picture.
- Headline verdicts extended with the three Phase 26 PASS verdicts; additive
  capital read-outs `t_copula_scr_pathwise_component` and
  `t_copula_scr_pathwise_component_bootstrap_mean`.

**Conclusion.** The full and re-anchored bases are economically
interchangeable on the frozen copula; the material gap to the nested truth is
a copula-FORM limitation, NOT a basis-choice effect. Nested with-actions
(path-wise) remains the capital reference.

## Verification

- `ui_data.json` contract checks: ALL PASS (42 substantive checks).
- jsdom self-test: **ok:true**, 0 network calls / 0 JS errors over
  118 checks (17 new Phase 26 checks incl. panel cards, basis matrix /
  paired-delta / gap-decomposition tables, gate grids, SCR bars).
- DISCLOSED forward-compat fix: the Phase 25 Task 5 exact-version test pin on
  "1.7.0" relaxed to a version floor >= (1,7,0) (additive bumps are the repo
  convention).

## Governance

- ChangeRecord `474879491df64f55a182be64b1f2cf2f` (OWNER_REVIEW); audit entries 81->81; change records
  54->54; audit-chain integrity verify_all = True.
- Production sign-off remains withheld (educational classification): residual
  is credentialled-data calibration + independent APS X2 review - not a code
  gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6;
Solvency II Art. 234; Efron & Tibshirani (1993) paired bootstrap.
