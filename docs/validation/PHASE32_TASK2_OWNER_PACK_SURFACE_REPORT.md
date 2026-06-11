# Phase 32 Task 2 - Owner-Decision-Pack Surface (Gap G1)

**Generated (UTC):** 2026-06-11T14:22:09.288508+00:00
**Verdict:** PASS - gap G1 closed (contract v1.14.0, additive)

## What the offline UI now surfaces

A first-class **Owner Decision (P31)** tab carrying the Phase 31 owner
decision pack VERBATIM (bit-for-bit; nothing recomputed):

- **Evidence pack:** governed headline **39,975.7** (unchanged through
  P27-P30); disclosed candidates (2-tree vine point **42,458.6**, tree-3
  bootstrap mean **41,751.9**, with 95% CIs); nested single-run reference
  **46,638.9** outside both CIs; copula-form residual ladder; gap
  decomposition; MR-016 / MR-017 status; binding stop-rule record.
- **Owner options:** the three options in **registry order** (O1_adopt_disclosed_vine_readout -> O2_accept_residual_with_monitoring -> O3_fund_second_independent_nested_run), NO
  default, no steering language; per-option capital effect, pre-registered
  acceptance criteria, escalation-path flag and governance risk.
- **Sign-off workflow:** all 6 steps; the decision sits at step 4 (model
  owner).
- **Decision record:** rendered **BLANK** until the owner decides.
- **Figure provenance, limitations, standards** carried verbatim.

## Pre-registered acceptance criteria (design note, gap G1)

- every displayed figure bit-for-bit from the pack: **PASS** (deep equality
  on all 13 carried keys)
- neutrality preserved (registry order / NO default / decision BLANK):
  **PASS**
- new self-test checks cover the surface: **PASS** (25 added; suite
  196 checks ok:true)
- ui_app self-test 0 network / 0 JS errors: **PASS** (0/0)
- ADDITIVE-only contract change (1.13.0 -> 1.14.0): **PASS** (every
  pre-existing ui_data key bit-identical; sha256-stable inventory)
- zero-install preserved: **PASS** (0 external references, single
  self-contained HTML)
- NO model parameter changes: **PASS** (display layer only)
- offline viewer + combined GUI self-tests: **PASS** (ok:true both)

## Verification

- `ui_data.json` contract checks: ALL PASS (14 substantive checks).
- jsdom self-tests: ui_app ok:true (196 checks, 0 network / 0 JS
  errors); offline viewer ok:true; combined GUI ok:true.

## Governance

- ChangeRecord `63b701f440eb4cfb9c83f7c34ce9f009` (OWNER_REVIEW); audit entries 108->109; change records
  80->81; audit-chain integrity verify_all = True.
- The Phase 31 owner decision itself remains PENDING with the model owner.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6; IFoA MPN s4;
Solvency II Art. 234.
