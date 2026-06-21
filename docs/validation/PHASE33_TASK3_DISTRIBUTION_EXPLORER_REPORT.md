# Phase 33 Task 3 - Embedded-Distribution Drill-Down (Gap G2)

**Generated (UTC):** 2026-06-12T20:24:32.478626+00:00
**Verdict:** PASS - gap G2 closed (contract 1.16.0 -> 1.17.0, ADDITIVE)

## What the offline UI now surfaces

A **Distribution Explorer (P33)** tab over PRECOMPUTED grids embedded at
build time by `scripts/build_ui_data.py` from the archived Phase 16
loss-distribution model output (`docs/validation/PHASE16_LOSS_DISTRIBUTION.json`, sha256 `863fd04d40b4...`):

- **Empirical CDF grid** - 41 exact grid points at the archived
  histogram bin edges (0.0 -> 1.0, monotone), hover full-precision
  readouts, grid-point slider, tail zoom (F >= 0.90); the connecting curve
  is labelled *display interpolation*.
- **Quantile grid** - 13 fixed probabilities (0.5% ... 99.5%), inverse
  histogram CDF computed at build time (linear within a bin, labelled at
  histogram resolution). Build-time p50 107,121.2 vs archived p50
  107,159.3 (within one bin width 2,470.7).
- **Archived sections carried bit-for-bit** - 8 percentiles, 5-level
  confidence sweep, 40-bin histogram, headline VaR/ES/SCR
  (148,903.3 / 155,728.1 / 41,039.8).
- **Per-seed CDF overlays** - 4 archived seeds.
- **Provenance panel** - source path, sha256, generation timestamp,
  reproducibility digest, computation method.

## Pre-registered acceptance criteria (design note, gap G2)

- grids computed ONLY at build time, provenance stamped: **PASS**
- embedded grid values reproducible from the archived artefacts: **PASS**
  (independent recomputation here reproduces every value EXACTLY)
- graceful neutral fallback for older payloads: **PASS** (dedicated jsdom
  fallback test - neutral message, no leaked figures, other tabs render,
  0 network / 0 JS errors)
- new self-test checks (grid presence, readout values, fallback): **PASS**
  (18 added; suite 266 checks ok:true, 0 network / 0 JS errors)
- ADDITIVE-only contract change: **PASS** (1.16.0 -> 1.17.0; pre-existing
  inventory entries bit-identical; governance limited to the existing
  P32T4 store-sync sweep refresh; meta.generated_utc is the build stamp)
- zero-install preserved: **PASS** (0 external references, single file)
- NO model parameter changes: **PASS** (display layer recomputes nothing
  beyond labelled display interpolation)
- offline viewer + combined GUI + user-run fallback self-tests: **PASS**

## Verification

- UI contract/grid checks: ALL PASS (24 substantive checks).
- jsdom self-tests: ui_app ok:true (266 checks, 0 network / 0 JS
  errors); distribution fallback ok:true; offline viewer ok:true;
  combined GUI ok:true; user-run fallback ok:true.

## Governance

- ChangeRecord `b01e374511f7480fa3a24f5d239f2d17` (OWNER_REVIEW); audit entries 114->115; change records
  86->87; audit-chain integrity verify_all = True.
- The MR-016/MR-017 dependence decision remains PENDING with the model
  owner; nothing on this tab recomputes or re-labels governed figures.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6; IFoA MPN s4.
