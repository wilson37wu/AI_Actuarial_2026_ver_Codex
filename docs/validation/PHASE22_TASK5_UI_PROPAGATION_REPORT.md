# Phase 22 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** 2026-06-07T10:18:59.596798+00:00
**Verdict:** PASS - **PHASE 22 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.4.0, additive)

- **Six-driver OOS remediation (Task 1):** the displayed honest PARTIAL verdict is
  replaced by the REMEDIATED PASS (OOS R2=0.9985, max |rel err| 2.02%).
- **Seven-driver OOS validation (Task 2):** new PASS verdict (R2=0.9985,
  VaR/ES/SCR rel err 0.51%/0.18%/1.26%, liquidity offset exact, leakage-free).
- **G-LIQX calibration panel (Task 3):** exposure notional 22,000
  (placeholder 30,000 retired), six estimated couplings with recovery-tolerance
  bars, 6/6 criteria, lineage-checksummed fixture, is_placeholder=false.
- **Calibrated aggregation (Task 4):** liquidity SCR 45.1 (was 63.5);
  var-covar 28,991 vs nested 48,707 (MR-010 understatement re-confirmed);
  gaussian copula 41,604; calibrated-vs-placeholder deltas embedded;
  tail diagnostics re-run CONVERGED.
- Headline aggregation/tail verdicts now carry the G-LIQX-CALIBRATED wording;
  `viewer_data.json` rebuilt so governance reflects the live store.

## Verification

- `ui_data.json` contract checks: ALL PASS (21 checks).
- jsdom self-test: **ok:true**, 0 network calls / 0 JS errors over 56 checks.

## Governance

- ChangeRecord `880aeb5d621645c9adc8d2eb1f2ea88a` (OWNER_REVIEW); audit entries 59->60; change records 32->33;
  audit-chain integrity verify_all = True.
- Production sign-off remains withheld (educational classification): residual is
  credentialled-data calibration + independent APS X2 review - not a code gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6.
