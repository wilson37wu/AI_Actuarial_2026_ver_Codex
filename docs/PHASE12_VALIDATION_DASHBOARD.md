# PAR Actuarial Model v2 — Validation Dashboard

**Report ID:** `6b4cdafb-b83d-4185-ae51-f30a5c3c9a00`  
**Generated:** 2026-06-04T02:16:31Z  
**Model version:** 2.0.0  
**Report version:** 1.0.0  

---

> ⚠️ **EDUCATIONAL MODEL** — Not cleared for production, regulatory reporting,
> pricing decisions, or external disclosure.  See Section 3 and Section 7.

---

## Section 1 — Model Health Checks

**Overall:** ✅ PASS  | Pass rate: **100.0%** (10/10)

| Check ID | Name | Status |
|----------|------|--------|
| VR-H01 | Module imports | ✅ PASS |
| VR-H02 | HybridGrid smoke test | ✅ PASS |
| VR-H03 | DynamicALMEngine smoke test | ✅ PASS |
| VR-H04 | DistributedExecutor sequential | ✅ PASS |
| VR-H05 | DataValidator pipeline | ✅ PASS |
| VR-H06 | VaR/ES computation | ✅ PASS |
| VR-H07 | GovernanceStore round-trip | ✅ PASS |
| VR-H08 | IA validation registry | ✅ PASS |
| VR-H09 | Monthly projection wiring | ✅ PASS |
| VR-H10 | ESGAdapter schema validation | ✅ PASS |


---

## Section 2 — IA TAS M Validation Requirements

**Overall:** ⚠️ PARTIAL  | Compliance: **0.0%** (0/31 PASS)

| Layer | PASS | FAIL | PARTIAL | NOT RUN |
|-------|------|------|---------|----------|
| Layer 1 — Unit | 0 | 0 | 0 | 7 |
| Layer 2 — Integration | 0 | 0 | 0 | 4 |
| Layer 3 — Stochastic | 0 | 0 | 0 | 5 |
| Layer 4 — Sensitivity | 0 | 0 | 0 | 4 |
| Layer 5 — Backtest | 0 | 0 | 0 | 3 |
| Layer 6 — Governance | 0 | 0 | 0 | 5 |
| Layer 7 — Data | 0 | 0 | 0 | 3 |

**Critical failures / open items:**

- VR-U01 [NOT_RUN] — Monthly Projection Unit Tests — 100% Pass
- VR-U02 [NOT_RUN] — ALM Engine Unit Tests — Rebalancing Bug Fixed
- VR-I01 [NOT_RUN] — End-to-End Projection Integration Test
- VR-I02 [NOT_RUN] — Distributed Executor Integration Test
- VR-S01 [NOT_RUN] — Scenario Convergence Test — TVOG Stability
- VR-S02 [NOT_RUN] — Martingale Test — Risk-Neutral Scenario Adequacy
- VR-S04 [NOT_RUN] — P / Q Measure Segregation Test
- VR-SE02 [NOT_RUN] — Lapse Rate Sensitivity — Dynamic Lapse Impact
- VR-G01 [NOT_RUN] — AuditTrail — All Production Runs Logged
- VR-G05 [NOT_RUN] — Validation Report — Final Sign-Off Before Production Use

> _Note: 31 requirements are defined; automated check callables are stubs_
> _returning NOT\_RUN until the requirements are formally validated against_
> _calibrated data in a production environment.  This is expected for an_
> _educational model — see Limitation Cards (Section 3)._


---

## Section 3 — Model Limitation Cards

**Status:** ❌ OPEN CRITICAL  | 11 cards total (2 CRITICAL, 8 HIGH, 1 MEDIUM, 0 LOW)

| Module Area | Open Cards |
|-------------|------------|
| ESG | 6 |
| Liability | 5 |

**Open CRITICAL limitations (block production use):**

- ESG-LC-001
- HK-LC-003


---

## Section 4 — Calibration Summary

**All modules converged:** ✅ Yes

| Module | Markets | Method | Status |
|--------|---------|--------|--------|
| Interest Rate Curves (HW1F) | USD, EUR, HKD, CNY, JPY | L-BFGS-B minimisation of ATM swaption normal-vol errors | ✅ CONVERGED |
| Equity (GBM) | US, EU, HK/CN, JP, Asia ex-JP | 60/40 implied-vol / historical-vol credibility blend | ✅ CONVERGED |
| Credit Spreads (Nelson-Siegel) | IG (AAA–BBB), HY (BB–CCC) | scipy least_squares, TRF method on OAS grids | ✅ CONVERGED |
| Liabilities — Mortality & Lapse | HK (HKML 2016) | HKML 2016 improvement + 60/40 credibility; exponential  | ✅ CONVERGED |

> _Calibration uses synthetic / placeholder data._
> _Scripts: `scripts/calibration/run_all_calibrations.py`._
> _Guide: `docs/CALIBRATION_SCRIPTS_GUIDE.md`._


---

## Section 5 — Test Suite Summary

**Total collected:** 1,079 tests (excluding heavy Monte Carlo suites)

| Module Area | Tests |
|-------------|-------|
| HK Participating Products (Phase 10) | 164 |
| Data Validator / Governance / Model Health / IA Validation / Audi | 256 |
| Hybrid Grid / Fixed Income / Derivative / Private Asset / ALM / R | 204 |
| ESG Adapter / Asset Stress / Stress Testing / Calibration | 198 |
| Portfolio Generator (Phase 11 Task 1) | 25 |
| Chunked Processor (Phase 11 Task 2) | 46 |
| Educational Reporting Pack (Phase 11 Task 5) | 50 |
| Guided Examples (Phase 12 Task 3) | 45 |
| Other (Phase 1–9 suites) | 91 |

**Heavy suites excluded from automated regression sweep**  
_(Each exceeds sandbox 45-second per-command limit; unaffected by Phase 12 changes.)_

- test_tvog.py — Monte Carlo TVOG (>500 scenarios)
- test_esg_process.py — Full stochastic ESG convergence suite
- test_sensitivity.py — 18-shock sensitivity grid
- test_backtesting.py (heavy) — Full out-of-sample backtest
- test_distributed_executor.py (multiprocessing) — Parallel chunk execution


---

## Section 6 — Phase Completion Tracker

**Overall:** [███████████████████░] **98.5%**  (67/68 tasks, 11/12 phases complete)

| # | Phase | Status | Tasks |
|---|-------|--------|-------|
|  1 | Model Review & Documentation | ✅ completed | 6/6 |
|  2 | Industry Standards Alignment | ✅ completed | 6/6 |
|  3 | Model Validation & Testing | ✅ completed | 8/8 |
|  4 | Calibration & Backtesting | ✅ completed | 7/7 |
|  5 | Documentation & Delivery | ✅ completed | 6/6 |
|  6 | ESG Scope and Architecture | ✅ completed | 5/5 |
|  7 | Interest Rate and Yield Curve ESG | ✅ completed | 5/5 |
|  8 | Equity, FX, and Correlation ESG | ✅ completed | 5/5 |
|  9 | Asset Class and Derivative Library | ✅ completed | 5/5 |
| 10 | Hong Kong Participating Liability Products | ✅ completed | 5/5 |
| 11 | 100,000-Policy Processing and Reporting | ✅ completed | 5/5 |
| 12 | Governance, Calibration, Educational Pack | 🔄 in_progress | 4/5 |


---

## Section 7 — Overall Readiness Verdict

### ✅ READY_FOR_EDUCATIONAL_USE

The model meets all automated quality gates for educational publication. IA TAS M validation requirements remain as stubs (NOT_RUN) by design — they require calibrated production data and independent review before a production validation sign-off can be issued.

**Gates met:**

- ✅ All 10 health checks PASS (VR-H01..VR-H10)
- ✅ All calibration modules converged (curves, equity, credit, liabilities)
- ✅ 11 limitation cards documented (2 CRITICAL — disclosed, expected for educational model)
- ✅ Phase completion at 98.5% (67/68 tasks)
- ✅ Test suite: 1,079 tests collected (heavy Monte Carlo suites excluded)

**Gates not met / open items:**

- ⚠️ IA TAS M validation requirements: 31/31 NOT_RUN (automated stubs — manual validation required for production)

> ⚠️ **Production cleared: No**  
> This model is NOT cleared for regulatory reporting, pricing decisions,
> or external disclosure.  See limitation cards and validation requirements.


---

_Generated by `par_model_v2.validation.validation_dashboard` (PHASE12-T4-VALIDATION-DASHBOARD). Standards: SOA ASOP 56, IA TAS M §3.6, ERM, IFoA MPN §4._
