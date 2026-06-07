# Phase 24 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** 2026-06-07T20:20:00.477205+00:00
**Verdict:** PASS - **PHASE 24 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.6.0, additive)

A first-class **Joint Actions (P24)** panel:

- **Joint-scenario action-after-aggregation (Task 2):** the governed bonus-cut
  rule applied ONCE to the t(2.9451) joint liability - joint t-SCR 31,002 vs
  nested-with 33,118 (rel err 6.39% vs the 22.54% standalone-action
  baseline; **saturation gap closed**); the joint action only relieves; rank
  invariance re-gated; 4/4 pre-registered gates.
- **Inner-path action dynamics (Task 3):** bonus cut on INNER-PATH benefit
  cashflows (credit loss + analytic FX/liquidity offsets non-cuttable); OOS R2
  0.9984, VaR rel err 0.40%; **outer-node over-relief disclosed** - nested SCR
  39,290.9 -> 40,852.1 (+1,561, +4.0%); the inner-path basis is the more
  conservative, more faithful with-actions basis; 5/5 gates.
- **Joint-action tail diagnostics (Task 4):** the without -> with-standalone ->
  with-joint capital-delta matrix across all four benchmarks; the
  action-saturation profile (99.5% tail **100% saturated** - max relief
  everywhere capital is measured); the frozen-copula margin bootstrap (95% CI
  [26,471, 33,637] **containing the nested-with reference**; n_obs=160
  noise quantified); the MR-010 var-covar refresh (56.4% vs nested-with /
  53.5% vs t-joint); 3/3 gates.
- Headline verdicts extended with the three Phase 24 PASS verdicts; additive
  capital read-outs (`t_copula_scr_joint_action`,
  `nested_scr_with_inner_path`); `viewer_data.json` rebuilt so governance
  reflects the live store (43 change records pre-Task 5).

## Verification

- `ui_data.json` contract checks: ALL PASS (32 checks).
- jsdom self-test: **ok:true**, 0 network calls / 0 JS errors over 84
  checks (15 new Phase 24 checks incl. panel cards, delta-matrix /
  saturation-sweep / inner-path tables, gate grids, joint-vs-standalone bars).
- DISCLOSED forward-compat fix: two Phase 23 Task 5 test pins on contract
  "1.5.0" relaxed to a version floor (additive bumps are the repo convention).

## Governance

- ChangeRecord `a66844b709f848d78bdee7553e1e49db` (OWNER_REVIEW); audit entries 71->71; change records
  44->44; audit-chain integrity verify_all = True.
- Production sign-off remains withheld (educational classification): residual
  is credentialled-data calibration + independent APS X2 review - not a code
  gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6;
Solvency II Art. 23 / Art. 234.
