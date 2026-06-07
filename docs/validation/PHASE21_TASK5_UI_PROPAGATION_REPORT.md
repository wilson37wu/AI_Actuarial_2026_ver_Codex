# Phase 21 Task 5 — Offline-UI Propagation Report

**Generated (UTC):** 2026-06-07T04:14:41.753055+00:00
**Verdict:** PASS — **PHASE 21 COMPLETE (Tasks 1–5)**

## What the offline UI now surfaces (contract v1.3.0, additive)

- **G-FX gate** (6th driver): calibration-explorer panel with 6/6 criteria and
  MART-FX-CIP martingale evidence.
- **G-LIQ gate** (7th driver): calibration-explorer panel (kappa 0.9345/yr,
  long-run 63 bp, sigma 0.0213, lambda 2.0 CLAMPED — disclosed).
- **FX + liquidity standalone SCRs**: driver bars + KPI cards — FX 4,286,
  liquidity 63 (small-SCR finding note displayed).
- **Seven-driver aggregation**: standalone sum / var-covar 28,996 /
  gaussian copula 41,593 / nested 48,694; MR-010 understatement
  finding re-stated under seven drivers.
- **Seven-driver tail diagnostics**: copula-simulated convergence, simulated +
  honest small-sample nested bootstrap CIs, Sobol-RQMC variance reduction.
- Headline aggregation/tail verdicts refreshed from the stale five-driver
  baseline wording; the six-driver OOS **PARTIAL** verdict remains honestly listed.

## Verification

- `ui_data.json` contract checks: ALL PASS (19 checks).
- jsdom self-test: **ok:true**, 0 network calls / 0 JS errors over 52 checks.

## Governance

- ChangeRecord `45cacebd910b440891f28b48fd30fedd` (OWNER_REVIEW); audit entries 51->52; change records 27->28;
  audit-chain integrity verify_all = True.
- Production sign-off remains withheld (educational classification): residual is
  credentialled-data calibration + independent APS X2 review — not a code gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6.
