# Phase 25 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** 2026-06-08T01:58:56.564479+00:00
**Verdict:** PASS - **PHASE 25 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.7.0, additive)

A first-class **Path-wise Actions (P25)** panel:

- **Path-wise bonus declaration in the nested truth (Task 2):** per-time-step
  retained-bonus factor on the path-wise coverage proxy (carve-outs
  preserved; without-actions bit-identical) - with-actions SCR 46,639
  (path-wise) vs 40,852 (horizon basis) = **+14.17%**; the path-wise
  basis relieves LESS (recognition-lag effect, two-sided) and is the more
  conservative, more faithful read-out; action share 41.4%, cut-then-restore
  share 29.4%; 6/6 pre-registered gates.
- **Matching path-wise proxy basis (Task 3):** smoothed-relief response
  surface (sigma 0.225, alpha 0.7567; FIT-only, leakage-free): OOS R2
  0.9978, VaR rel err 0.40%, SCR rel err 1.16% on the IDENTICAL path-wise
  action basis; annual/monthly declaration-cadence sensitivity 1.136
  disclosed; 5/5 gates.
- **Path-wise tail diagnostics (Task 4):** the without -> with-horizon ->
  with-path-wise capital-delta matrix across all four benchmarks (var-covar:
  no path-wise analogue, DISCLOSED); the raw cut saturates 100% of the 99.5%
  tail but the mean smoothed relief fraction is 0.0811 < 0.12 (restoration
  caps realised relief); the frozen-copula margin bootstrap (95% CI
  [35,793, 42,496]) with the nested path-wise reference **OUTSIDE the
  CI** - the analytic re-anchoring understates nested by 14.7% beyond
  noise, the quantified motivation for the next-phase full path-wise copula
  re-aggregation; MR-010/MR-014 refreshed (var-covar understatement
  69.1%); rank invariance re-gated (df 2.9451, copula FROZEN); 4/4
  gates.
- Headline verdicts extended with the three Phase 25 PASS verdicts; additive
  capital read-outs (`nested_scr_with_pathwise`,
  `t_copula_scr_pathwise_readout`); `viewer_data.json` rebuilt so governance
  reflects the live store (48 change records pre-Task 5).

## Verification

- `ui_data.json` contract checks: ALL PASS (43 checks).
- jsdom self-test: **ok:true**, 0 network calls / 0 JS errors over
  101 checks (17 new Phase 25 checks incl. panel cards, delta-matrix /
  tail-profile / proxy-basis tables, gate grids, pathwise-vs-horizon bars).
- DISCLOSED forward-compat fix: two Phase 24 Task 5 test pins on contract
  "1.6.0" relaxed to a version floor (additive bumps are the repo
  convention).

## Governance

- ChangeRecord `3fa4394e568b48fc9ee06dd8a64dd44b` (OWNER_REVIEW); audit entries 76->76; change records
  49->49; audit-chain integrity verify_all = True.
- Production sign-off remains withheld (educational classification): residual
  is credentialled-data calibration + independent APS X2 review - not a code
  gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6;
Solvency II Art. 23 / Art. 234.
