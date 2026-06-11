# Phase 29 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** 2026-06-11T00:25:26.809696+00:00
**Verdict:** PASS - **PHASE 29 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.11.0, additive)

A first-class **Vine Tail (P29)** panel:

- **Truncated credit-root C-vine prototype on FROZEN margins (Task 2):**
  vine candidate component SCR **42,459** (+6.21% vs frozen-t 39,976,
  +19.25% vs grouped-t 35,604); gap to the nested path-wise reference
  46,639 narrowed to **-8.96%** - the FIRST dependence candidate to move
  TOWARD the nested read-out (disclosed, not gated); EXACT frozen-t boundary
  recovery (dev 0.0); leakage-free family selection surfaced; copula and
  margins FROZEN (df 2.9451, rho max|diff| < 1e-12).
- **Vine margin bootstrap on the frozen fit (Task 3):** vine SCR mean
  **41,918**, 95% CI **[38,655, 45,284]**, SE **4.04%** of mean
  (<= 5%); nested 46,639 remains **OUTSIDE the CI**; the copula-form
  residual NARROWS to **3,637** (-65.33% vs grouped-t, -40.52% vs
  skew-t) - the first candidate to NARROW below BOTH baselines.
- **Pair-level tail diagnostics + overfit check + MR decision (Task 4):**
  candidate-vs-frozen upper/lower tail-dependence grid over p in
  {0.80, 0.85, 0.90, 0.95} for all 11 fitted links (first/second tree)
  PLUS 3 never-fitted holdout pairs with 95% CIs; largest lift
  rate-liquidity|credit **+0.8514** at p=0.90; fit-vs-holdout overfit gate
  PASS (max holdout lift 0.0414 vs max fitted lift 0.8514, ratio
  **0.049**); **MR-016 KEEP OPEN** (nested outside CI - close criteria
  not met; narrowing DISCLOSED) and **MR-017 OPENED** (residual vine-FORM
  limitations); governed headline recovered bit-identically (move
  **0.0000%** -> MR-010/MR-014 no refresh).
- Additive capital read-outs `vine_copula_scr_component_point` and
  `vine_copula_scr_component_bootstrap_mean`.

**Conclusion.** The vine is the most informative dependence candidate to
date: it tilts the upper tail in the right direction on every fitted link
and materially narrows the copula-form residual, but the nested truth stays
outside its sampling band, so it remains a DISCLOSED alternative read-out -
NOT adopted into the governed headline without owner sign-off. The residual
lives in nested inner-path joint dynamics tracked by MR-017.

## Verification

- `ui_data.json` contract checks: ALL PASS (44 substantive checks).
- jsdom self-test: **ok:true**, 0 network calls / 0 JS errors over
  150 checks (16 new Phase 29 checks incl. panel cards, pair-level tail
  table (14 rows = 6 first-tree + 5 second-tree + 3 holdout), gap
  re-decomposition table, gate grids, SCR + lift bar charts).

## Governance

- ChangeRecord `242342e615a146c1a1fdedc6381a9fc9` (OWNER_REVIEW); audit entries 95->95; change records
  67->67; audit-chain integrity verify_all = True.
- Production sign-off remains withheld (educational classification):
  residual is credentialled-data calibration + independent APS X2 review -
  not a code gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6; Solvency II
Art. 234; Aas et al. (2009); Efron & Tibshirani (1993).
