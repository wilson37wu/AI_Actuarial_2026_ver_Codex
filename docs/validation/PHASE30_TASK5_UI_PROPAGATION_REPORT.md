# Phase 30 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** 2026-06-11T09:18:08.118053+00:00
**Verdict:** PASS - **PHASE 30 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.13.0, additive)

A first-class **Stop-Rule (P30)** panel:

- **Roadmap decision (Task 1):** option A (tree-3 vine deepening) selected
  design-note-first; the binding stop-rule (option D) pre-registered; the
  Phase 31 owner decision package (option C) committed regardless of
  outcome; option B (nested-aware calibration) reserved as an
  owner-approved escalation.
- **Tree-3 candidate on the FROZEN P29 2-tree fit (Task 2):** DUAL boundary
  recovery bit-identical FIRST (frozen-t **39,976** AND 2-tree vine
  **42,459**, dev 0.0). Data-support DISCLOSURE: all four pre-registered
  joint-conditional third-tree pairs are **zero-strength** (n_fit
  {3,3,3,1} of 112 fit rows), so the candidate component SCR
  **42,459** is **BIT-IDENTICAL** to the 2-tree vine.
- **Margin bootstrap (Task 3):** tree-3 SCR mean **41,752**, 95% CI
  **[38,594, 44,556]**, SE **3.81%** (<= 5%); nested 46,639
  remains **OUTSIDE the CI**; per-replicate tree-3 minus 2-tree vine
  EXACTLY ZERO in all 200 replicates; copula-form residual **3,637**
  UNCHANGED vs the 2-tree vine.
- **Binding stop-rule + MR decision (Task 4):** pair-level tail grid (6
  first-tree + 5 second-tree + 4 third-tree + 3 holdout pairs, 4 p-levels,
  95% CIs); overfit gate PASS (holdout/fit ratio **0.049** = P29
  reference); **STOP-RULE APPLIED** - MR-016 and MR-017 **KEEP OPEN**,
  **dependence-FORM escalation under MR-016 ENDS**, **Phase 31 = owner
  decision package**; governed headline recovered bit-identically (move
  **0.0000%** -> MR-010/MR-014 no refresh).
- Additive capital read-outs `tree3_vine_scr_component_point` and
  `tree3_vine_scr_component_bootstrap_mean`.

**Conclusion.** Phase 30 closes the dependence-FORM escalation arc that ran
P27 (skew-t) -> P28 (grouped-t) -> P29 (2-tree vine) -> P30 (tree-3): the
vine narrowed the copula-form residual by 65% but the data cannot support
deeper conditional structure (zero-strength tree 3), and the nested truth
stays outside the sampling band. Per the pre-registered stop-rule, no
further copula-structure candidates may be opened without owner sign-off;
the decision moves to the owner (adopt the disclosed read-out vs accept the
residual vs fund option B).

## Verification

- `ui_data.json` contract checks: ALL PASS (48 substantive checks).
- jsdom self-test: **ok:true**, 0 network calls / 0 JS errors over
  172 checks (18 new Phase 30 checks incl. panel cards, third-tree edge
  table, pair-level tail table (18 rows = 6+5+4+3), residual table, gate
  grids, SCR + lift bar charts, stop-rule text assertions).

## Governance

- ChangeRecord `3ea0836fc67f405dbef26e5f954e680d` (OWNER_REVIEW); audit entries 103->104; change records
  75->76; audit-chain integrity verify_all = True.
- Production sign-off remains withheld (educational classification).

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6; Solvency II
Art. 234; Aas et al. (2009); IFoA MPN s4.
