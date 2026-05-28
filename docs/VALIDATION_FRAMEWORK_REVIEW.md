# Validation & Testing Framework Review
**Model:** PAR Fund Stochastic ALM & TVOG (Python)  
**Date:** 2026-05-18  
**Prepared by:** Claude Actuarial Agent (Automated Cycle 5)  
**Phase:** 1 — Model Review & Documentation  
**Task:** Review existing validation and testing framework  
**Version:** 1.0  

---

## Executive Summary

The model currently has two distinct testing layers: the **original GitHub repository test suite** (67 tests across 4 files, 88% pass rate with 8 known failures) and a **new monthly projection test suite** (62 tests, 100% pass rate) introduced in Cycle 3. Together these represent a good structural foundation for unit testing, but leave material gaps in integration coverage, stochastic validation, and model-level verification required by SOA ASOP 56 and IA TAS M.

**Overall validation readiness: 2 / 5 (Development-grade; not fit for production or regulatory use)**

The single highest-priority remediation is the distributed executor pickling fix (Phase 3), which unblocks scenario-level testing, convergence validation, and stress testing simultaneously.

---

## 1. Current Test Inventory

### 1.1 Original Repository Tests (GitHub — `par_model_v2/`)

From the Cycle 1 audit, the following test files exist in the repository:

| File | Tests | Passed | Failed | Coverage Domain |
|------|-------|--------|--------|-----------------|
| `test_dynamic_alm.py` | 11 | 10 | 1 | ALM rebalancing, buy/sell logic, transaction costs |
| `test_flexible_assumptions.py` | 21 | 21 | 0 | Assumption table lookup, hierarchical fallback, interpolation |
| `test_integration_e2e.py` | 28 | 24 | 4 | End-to-end scenario runs via distributed executor |
| `test_distributed_processing.py` | 7 | 4 | 3 | Multiprocessing batch runner, pickling, checkpoint/restart |
| **TOTAL** | **67** | **59** | **8** | |

**Pass rate: 88%** (59/67). Root causes of the 8 failures:

1. **ALM rebalancing (1 failure — `test_rebalancing_to_saa`):** The DynamicALMEngine does not issue buy orders when the initial portfolio is 100% cash and the SAA target requires allocating to bonds/equity. The rebalancing trigger only fires when holdings are above target (liquidation), not when they are below target (purchase). This is a logic bug, not a test bug.

2. **Distributed executor pickling (7 failures):** Python's `multiprocessing` module cannot serialize locally-scoped functions. All distributed tests pass locally-defined lambdas or closures as `process_func`, which raises `AttributeError: Can't pickle local object`. This affects all multi-scenario batch runs.

### 1.2 New Monthly Projection Tests (Local — `tests/`)

Introduced in Cycle 3 (`tests/test_monthly_projection.py`). Confirmed results from this cycle's live test run:

| Class | Tests | Passed | Failed | Coverage |
|-------|-------|--------|--------|----------|
| `TestHelpers` | 3 | 3 | 0 | `monthly_discount_factor`, `monthly_mortality_qx` (UDD) |
| `TestProduct` | 3 | 3 | 0 | `ParEndowmentProduct` validation and properties |
| `TestLiability` | 14 | 14 | 0 | `project_liability_cashflows` — 5/10/20Y parametrized |
| `TestAssets` | 7 | 7 | 0 | `project_asset_cashflows` — income, MV, PV |
| `TestAssetShare` | 6 | 6 | 0 | `run_full_projection` — 70/30 split, surplus distribution |
| `TestEndToEnd` | 9 | 9 | 0 | All 3 terms × 3 properties, maturity NG monotonicity |
| **TOTAL** | **62** | **62** | **0** | |

**Pass rate: 100%** (62/62). Test runtime: 2.08 seconds.

---

## 2. Test Quality Assessment

### 2.1 Strengths

**Monthly projection tests (strong):**
- Parametrized across all valid terms (5, 10, 20Y) — no gaps from term-specific bugs
- Mathematical identities verified at source (UDD formula, monthly compounding, PV recomputation)
- Sign constraints enforced (non-negative in-force, non-negative asset share EOM)
- Structural invariants checked (acquisition expense month-1-only, maturity benefit last-month-only)
- No null values asserted across all output DataFrames
- 70/30 profit-sharing ratio verified numerically

**Assumption tests (strong):**
- 21 tests covering hierarchical lookup, multi-dimensional interpolation, and fallback logic
- This is the most complete test coverage in the original repository

### 2.2 Weaknesses

**Monthly projection tests (gaps):**
- No boundary/edge case tests: zero sum assured, zero premium, maximum issue age
- No error-path tests: invalid inputs beyond `term_years` (e.g., negative premium, future entry age > term age)
- No property-based tests (e.g., monotonicity of asset share vs. investment return)
- Asset cashflow tests use a single fixed fixture — no parametrization across asset mix scenarios
- No test for surrender benefit values at each month of surrender
- No cross-module consistency check: PV(asset income) vs. PV(liability cashflows) balance

**Integration gaps (critical for model validity):**
- No end-to-end test from assumption tables → liability CFs → asset CFs → asset share → TVOG
- No test that runs monthly projection under multiple discount rate scenarios and checks monotonicity
- No test verifying asset-liability matching at the fund level

**Stochastic validation (entirely absent):**
- No scenario convergence test (TVOG stability as N → ∞)
- No martingale test for risk-neutral ESG scenarios
- No scenario fan chart validation (percentile reasonableness)
- No calibration stability test (parameter estimate variance across calibration windows)

---

## 3. Coverage Gap Analysis by Module

| Module | Unit Test Coverage | Integration Coverage | Stochastic Coverage | Priority |
|--------|-------------------|---------------------|---------------------|----------|
| `monthly_projection.py` | ✅ 62 tests, 100% pass | ❌ None | ❌ None | Phase 3 |
| `assumptions/` (original) | ✅ 21 tests, 100% pass | ❌ None | ❌ None | Phase 3 |
| `assets/` dynamic ALM | ⚠️ 10/11 pass, 1 ALM bug | ❌ None | ❌ None | Phase 3 |
| `valuation/` asset share engine | ⚠️ Partial (in integration tests) | ❌ 4 failures | ❌ None | Phase 3 |
| `valuation/` distributed executor | ❌ 4/7 pass, pickling bug | ❌ Blocked | ❌ Blocked | **Phase 3, Task 1** |
| `esg/` adapter | ❌ No tests (ESG file missing) | ❌ Blocked | ❌ Blocked | Phase 4 |
| `liabilities/` deterministic | ❌ No standalone tests | ❌ None | ❌ None | Phase 3 |
| `model_points/` | ❌ No tests | ❌ None | ❌ None | Phase 3 |
| `grid/` hybrid time grid | ❌ No tests | ❌ None | ❌ None | Phase 3 |
| TVOG computation | ❌ Module does not exist | ❌ | ❌ | Phase 4 |

---

## 4. Validation Framework vs. SOA/IA Requirements

### 4.1 ASOP 56 §3.5 — Model Testing

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| Unit testing of model components | ⚠️ Partial — 2 modules well tested, 7 untested | Expand to all modules |
| Sensitivity testing | ❌ Not implemented | No parameter shock runner |
| Convergence validation (stochastic) | ❌ Not implemented | No scenario-count stability test |
| Comparison to alternative model / benchmark | ❌ Not implemented | No benchmark liability values |
| Back-testing | ❌ Not implemented | No historical data; Phase 4 |

### 4.2 IA TAS M — Model Validation

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| Independent validation | ❌ Not implemented | All tests written by model developer |
| Documentation of validation methodology | ❌ Not implemented | This document is the start |
| Validation of assumptions vs. experience | ❌ Not implemented | No experience data in repository |
| Disclosure of validation limitations | ❌ Not implemented | Phase 5 |

### 4.3 ERM — Tail Risk Validation

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| VaR at 99.5% confidence | ❌ Not implemented | No stochastic run possible (executor broken) |
| Expected Shortfall | ❌ Not implemented | Same blocker |
| Stress scenario output | ❌ Not implemented | No stress runner |
| Convergence of tail metrics | ❌ Not implemented | Requires stochastic capability first |

---

## 5. Recommended Validation Framework (Target State)

The following four-layer framework is recommended to bring the model to production-grade validation by end of Phase 3/4:

### Layer 1 — Unit Tests (Expand by Phase 3)

Priority additions to existing test suite:

1. `test_dynamic_alm.py` — Fix `test_rebalancing_to_saa` (ALM bug fix first); add tests for all-bond, all-equity, and mixed starting portfolios
2. `test_deterministic_liability.py` (new) — Unit tests for original `DeterministicLiability` module
3. `test_assumption_provider.py` (expand) — Shock/stress tests via assumption override API
4. `test_model_points.py` (new) — Synthetic MP generation, grouping, aggregation
5. `test_grid.py` (new) — Hybrid monthly/annual grid boundary conditions
6. Add edge cases to `test_monthly_projection.py` — zero premium, surrender at each month, rate sensitivity

### Layer 2 — Integration Tests (Phase 3)

1. End-to-end deterministic run: assumptions → model points → liabilities → assets → asset share → output report
2. Asset-liability cashflow balance check at fund level
3. Multi-policy portfolio aggregation validation
4. ESG → monthly projection → TVOG pipeline (once ESG generator exists)

### Layer 3 — Stochastic Validation (Phase 4)

1. **Scenario convergence test:** Run TVOG for N = 50, 100, 250, 500, 1000; confirm |TVOG(N) − TVOG(N/2)| / TVOG(N) < 1% at N = 1000
2. **Martingale test:** Under risk-neutral scenarios, E[discount_factor × ZCB_price(T)] = 1; verify across all simulated paths
3. **Fan chart reasonableness:** Plot 5th/50th/95th percentile of key outputs; confirm economically sensible range
4. **Tail metric stability:** VaR(99.5%) and ES(99%) stable to ±5% from N = 500 to N = 1000

### Layer 4 — Backtesting & Benchmarking (Phase 4)

1. **Benchmark liability values:** Compare deterministic projection outputs to closed-form endowment reserves (Fackler accumulation) — should match within 0.1%
2. **Assumption experience analysis:** When inforce data available, A/E ratios for mortality and lapse
3. **Discount curve backtest:** Validate projected rates vs. realised CNY rates over rolling 1Y windows

---

## 6. Immediate Remediation Priorities

Ranked by leverage (unblocking other work):

| # | Action | Unblocks | Phase |
|---|--------|---------|-------|
| 1 | Fix distributed executor pickling bug | All stochastic testing, TVOG, VaR/ES | Phase 3 |
| 2 | Fix ALM rebalancing (100%-cash starting position) | Integration tests, ALM validation | Phase 3 |
| 3 | Implement internal GBM ESG generator | ESG module tests, convergence test, TVOG | Phase 4 |
| 4 | Add deterministic liability unit tests | Integration test, benchmark comparison | Phase 3 |
| 5 | Implement sensitivity runner (`+/-10% shocks`) | ASOP 56 §3.5.2 compliance | Phase 3 |
| 6 | Reconcile version (0.1.0 vs 2.0.0) | Clean release tagging | Phase 2 |

---

## 7. Conclusions

The model's testing foundation is uneven: the new monthly projection module is well-tested and production-quality; the original stochastic ALM modules have significant gaps, two critical bugs, and no stochastic validation at all. The validation framework does not currently meet SOA ASOP 56, IA TAS M, or ERM requirements for production actuarial use.

**Phase 3 (Validation & Testing) must begin by fixing the distributed executor pickling bug.** This single fix unblocks scenario-level testing and is the critical path to all downstream stochastic validation. Once that is resolved, the validation framework described in Section 5 can be built systematically over two or three cycles.

---

*This document forms part of the Phase 1 deliverables. It feeds directly into Phase 3 test planning and Phase 2 standards alignment work.*
