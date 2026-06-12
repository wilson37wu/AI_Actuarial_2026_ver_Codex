# Phase 33 Task 2 - Interactive Cross-Phase SCR Comparator (Gap G1)

**Generated (UTC):** 2026-06-12T11:03:34.336376+00:00
**Verdict:** PASS - gap G1 closed (contract v1.16.0 UNCHANGED; display layer only)

## What the offline UI now surfaces

A first-class **SCR Comparator (P33)** tab - an interactive, neutral
comparison of every dependence-structure component-SCR estimate already
embedded in the snapshot (registry order):

| Structure | Point (embedded) |
|---|---|
| Frozen single-df t (GOVERNED HEADLINE, default baseline) | 39,975.7 |
| Grouped-t (P28) | 35,604.4 |
| Skew-t (P27) | 39,981.0 |
| Vine 2-tree (P29) | 42,458.6 |
| Vine 3-tree (P30) | 42,458.6 |
| Nested path-wise reference (P24; point only) | 46,638.9 |

- **User-selectable baseline** (default = governed frozen-t; the governed
  label never moves with the selection).
- **Signed delta table** vs the selected baseline, explicitly labelled
  *display arithmetic - NOT new model output*.
- **95% bootstrap CI overlay chart** (whiskers = embedded CIs; the nested
  reference is point-only, disclosed as such).
- **Figure provenance**: the exact embedded ui_data key for every figure.

## Pre-registered acceptance criteria (design note, gap G1)

- every comparator figure traces bit-for-bit to an already-embedded
  ui_data 1.16.0 key (no new build-time data): **PASS** (ui_data.json and
  the embedded snapshot are byte-identical to the previous commit)
- governed frozen-t headline 39,975.654628199336 stays the default
  baseline and is never re-labelled: **PASS** (exact-precision check +
  re-label checks under non-default baselines)
- comparator neutral - registry order, no adoption/steering language:
  **PASS**
- new self-test checks cover baseline switching, delta signs and CI
  overlay rendering: **PASS** (16 added; suite 248 checks ok:true)
- ui_app self-test 0 network / 0 JS errors: **PASS** (0/0)
- ADDITIVE-only contract change (if any): **PASS** (NO change at all -
  contract stays 1.16.0)
- zero-install preserved: **PASS** (0 external references, single
  self-contained HTML)
- NO model parameter changes: **PASS** (display layer only; the only
  arithmetic is the labelled display subtraction)
- offline viewer + combined GUI + user-run fallback self-tests: **PASS**

## Verification

- UI contract checks: ALL PASS (14 substantive checks).
- jsdom self-tests: ui_app ok:true (248 checks, 0 network / 0 JS
  errors); offline viewer ok:true; combined GUI ok:true; user-run
  fallback ok:true.

## Governance

- ChangeRecord `a87fd9f8aaaa47b1bd9b57f82c5f380b` (OWNER_REVIEW); audit entries 113->114; change records
  85->86; audit-chain integrity verify_all = True.
- The MR-016/MR-017 dependence decision remains PENDING with the model
  owner; the comparator recommends nothing.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6; IFoA MPN s4;
Solvency II Art. 234.
