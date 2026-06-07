# Phase 23 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** 2026-06-07T15:19:17.882446+00:00
**Verdict:** PASS - **PHASE 23 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.5.0, additive)

- **Tail-matched Student-t copula (Task 2):** df=2.9451 by pooled tail-dependence
  matching; t-SCR 46,756 vs nested 48,707 (rel err 4.0%) vs gaussian 14.9%
  and var-covar understatement 40.5% (MR-010).
- **Management Actions panel (Task 3):** dynamic reversionary-bonus cut
  (Solvency II Art. 23) - rule card (trigger 1.10 / floor 0.90 / PRE floor 60% /
  max relief 12%), 5/5 pre-registered gates, active share 44.2% (nested run),
  trigger sensitivity 1.05/1.10/1.15 all PASS, OOS R2 with actions 0.9983.
- **With-actions aggregation (Task 4):** nested SCR 48,707 -> 33,118
  (-32.0%); t-copula 46,756 -> 25,653; gaussian and var-covar with/without;
  per-driver standalone deltas; rank invariance (df unchanged at 2.9451);
  **saturation finding disclosed verbatim** - copula-on-standalone understates
  the nested with-actions benchmark; nested remains the capital reference.
- Headline verdicts extended with the three Phase 23 PASS verdicts;
  `viewer_data.json` rebuilt so governance reflects the live store.

## Verification

- `ui_data.json` contract checks: ALL PASS (25 checks).
- jsdom self-test: **ok:true**, 0 network calls / 0 JS errors over 69
  checks (13 new Phase 23 checks incl. panel cards, gate grid, with/without
  bars, trigger-sensitivity and standalone tables).

## Governance

- ChangeRecord `9df7b0fc63464614bc87b3c7b77cfff9` (OWNER_REVIEW); audit entries 65->65; change records 38->38;
  audit-chain integrity verify_all = True.
- Production sign-off remains withheld (educational classification): residual is
  credentialled-data calibration + independent APS X2 review - not a code gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6;
Solvency II Art. 23 / Art. 234.
