# SOA Stochastic Modeling Standards — Deviation Report
**Model:** PAR Fund Stochastic ALM & TVOG (Python)  
**Date:** 2026-05-18  
**Prepared by:** Claude Actuarial Agent (Automated Cycle 4)  
**Phase:** 1 — Model Review & Documentation  
**Task:** Identify deviations from SOA stochastic modeling standards  
**Version:** 1.0  

---

## Executive Summary

This report systematically identifies every deviation between the current PAR Fund model and the applicable SOA actuarial standards for stochastic modeling. The primary governing standards are **ASOP 56 (Modeling, 2020)**, **ASOP 25 (Credibility Procedures, 2013)**, and **ASOP 7 (Analysis of Life, Health, or P/C Insurer Cash Flows, 2011)**. Secondary references include VM-20/VM-21 stochastic reserve requirements and the SOA's *Practice Note on Stochastic Modeling*.

**Finding:** 24 deviations identified across 5 standards frameworks. 7 are classified as Critical (model cannot produce compliant output without remediation), 11 as High (material gap), and 6 as Medium (documentation/governance gap).

**Remediation roadmap:** Phases 2–4 address all Critical and High deviations. This report is the input to Phase 2 planning.

---

## Deviation Severity Scale

| Level | Definition |
|-------|------------|
| 🔴 Critical | Model output is non-compliant or non-producible without this fix |
| 🟠 High | Material gap relative to standard; raises model risk concerns |
| 🟡 Medium | Documentation or governance gap; model can run but is not auditable |

---

## 1. ASOP 56 — Modeling (2020)

ASOP 56 is the foundational SOA standard for all actuarial models. It governs model purpose, scope, documentation, testing, use, and governance.

---

### 1.1 Stochastic Process Documentation

**Requirement (ASOP 56 §3.1.3):** The actuary should document the model in sufficient detail that another actuary qualified in the same practice area could evaluate the appropriateness of the model. For stochastic models, this requires explicit documentation of the stochastic process assumed for each risk factor.

**Current state:** The model's ESG adapter (`ESGAdapter`) reads scenario paths from an external Moody's file. The stochastic process generating those paths (e.g., Hull-White 2-factor for rates, lognormal GBM for equity) is not documented anywhere in the codebase or supporting documentation. The Python code reads columns like `ESG.Economies.CNY.NominalZCBP(Rating, Tenor, 3)` but contains no description of the underlying process.

The new monthly projection engine (`monthly_projection.py`) uses a single deterministic `discount_rate_annual` parameter — no stochastic scenarios are consumed at all.

**Deviation:** 🔴 Critical  
**Gap:** Stochastic process type, parameterization, and calibration are entirely undocumented. A reviewing actuary cannot evaluate model appropriateness.  
**Remediation:** Phase 2 — implement and document a GBM-based internal ESG; document interest rate and equity process assumptions explicitly in code and in a dedicated `docs/ESG_PROCESS_DOCUMENTATION.md`.

---

### 1.2 Parameter Calibration Methodology

**Requirement (ASOP 56 §3.4):** The actuary should document how model parameters are selected and calibrated, including any calibration to historical data or market observables.

**Current state:** No calibration scripts, no parameter history, no calibration documentation. Key parameters are hardcoded:
- Discount rate: 3.5% (flat, no term structure)
- Investment returns by class: deterministic 4.5–6.0% per `investment_return.csv`
- Mortality: static table, basis undocumented
- Lapse: static table, basis undocumented
- Bonus rates: fixed schedule, no experience link

**Deviation:** 🔴 Critical  
**Gap:** No calibration methodology. Parameters appear to be illustrative rather than market-calibrated. The discount curve long-end rate (5.0% flat) is materially inconsistent with current CNY rates (~2.2–3.5%).  
**Remediation:** Phase 4 — implement calibration module; document parameter selection rationale; calibrate discount curve to CNY swap/bond market.

---

### 1.3 Scenario Count Adequacy & Convergence

**Requirement (ASOP 56 §3.5 / SOA Practice Note):** For stochastic models, the actuary should validate that the number of scenarios is sufficient for the intended use — typically via convergence testing (e.g., confirming that TVOG estimate stabilizes as scenario count increases from 100 → 500 → 1000).

**Current state:** No scenario count is defined. No convergence testing exists. The distributed executor was designed for batch scenario runs but the pickling bug prevents it from operating. No convergence validation script exists.

**Deviation:** 🔴 Critical  
**Gap:** Scenario adequacy is undemonstrated. TVOG output (when implemented) would have unknown standard error.  
**Remediation:** Phase 3 — add `scripts/scenario_convergence_test.py`; produce convergence chart for TVOG as function of N (50, 100, 250, 500, 1000 scenarios).

---

### 1.4 Real-World vs. Risk-Neutral Scenario Distinction

**Requirement (ASOP 56 §3.3 / ASOP 7 §3.8):** The model must clearly distinguish between real-world (P-measure) scenarios used for cash flow projections and risk-neutral (Q-measure) scenarios used for option pricing. For TVOG, the choice of measure is material and must be disclosed.

**Current state:** No documentation exists anywhere in the codebase distinguishing P-measure from Q-measure scenarios. The Moody's ESG provides one set of scenarios; whether these are calibrated for real-world or risk-neutral use is not specified.

**Deviation:** 🔴 Critical (for TVOG use)  
**Gap:** TVOG computed under P-measure scenarios would be incorrect for market-consistent valuation (e.g., IFRS 17 CSM calculations). This distinction is unresolved.  
**Remediation:** Phase 2 — document intended measure for each model use case; when implementing TVOG, specify and justify the scenario calibration basis.

---

### 1.5 TVOG Computation Module

**Requirement (ASOP 56 §3.1):** The model must be fit for purpose. The stated purpose of this model is "Stochastic ALM & TVOG." TVOG (Time Value of Options and Guarantees) is the present value, under stochastic scenarios, of the embedded options and guarantees in the policyholder contract net of their value in the best estimate scenario.

**Current state:** No TVOG module exists. The monthly projection engine computes a single deterministic path. The distributed executor (intended for multi-scenario runs) is non-functional due to the pickling bug. No scenario aggregation, no option payoff extraction, no TVOG output.

**Deviation:** 🔴 Critical  
**Gap:** The model's stated primary output is entirely absent.  
**Remediation:** Phase 4 — implement `par_model_v2/valuation/tvog.py`; requires a working ESG (or internal GBM generator), fixed distributed executor, and stochastic liability projection.

---

### 1.6 Sensitivity Analysis Framework

**Requirement (ASOP 56 §3.5.2):** The actuary should test the sensitivity of model output to changes in key assumptions, particularly those to which the model is highly sensitive.

**Current state:** No sensitivity runner exists. No parameter shock infrastructure. The assumption provider supports table-driven parameters but there is no mechanism to apply a +/-X% shock to an assumption and re-run the model. No sensitivity report exists.

**Deviation:** 🟠 High  
**Gap:** Unknown model sensitivity to discount rate, lapse, and mortality assumptions — all of which are flagged as potentially miscalibrated.  
**Remediation:** Phase 3 — implement `scripts/sensitivity_runner.py`; produce tornado charts for +/-10% shocks on top 5 assumptions; key sensitivities: discount rate (DV01), lapse rate, mortality, bonus rate, expense inflation.

---

### 1.7 Model Governance & Change Control

**Requirement (ASOP 56 §3.7):** The actuary should consider appropriate governance and controls for the model, including version control, model change documentation, and review and approval processes.

**Current state:**
- Version inconsistency: `__version__.py = 0.1.0` vs `__init__.py = 2.0.0`
- No model change log within the code (only `MODEL_DEV_LOG.md` added this session)
- No approval workflow, no review records
- No model governance policy document

**Deviation:** 🟡 Medium  
**Gap:** Unresolved version inconsistency creates confusion about what "version" has been tested or reviewed. No formal governance process.  
**Remediation:** Phase 2 — reconcile version to `0.2.0` (pre-production); create `docs/MODEL_GOVERNANCE_POLICY.md`; version tags in git from this point forward.

---

### 1.8 Model Limitations Disclosure

**Requirement (ASOP 56 §3.1.4):** The actuary should identify and disclose material limitations of the model in actuarial communications relying on it.

**Current state:** No model risk card, no limitations document. Known material limitations not formally disclosed:
1. Requires external Moody's ESG file (model non-runnable E2E without it)
2. Distributed executor pickling bug (no multi-scenario runs)
3. ALM rebalancing does not work from 100% cash
4. Discount curve rate overstated vs. market
5. Dynamic lapse absent
6. TVOG not implemented

**Deviation:** 🟡 Medium  
**Gap:** Anyone using the model has no formal reference for its known limitations.  
**Remediation:** Phase 5 — produce `docs/MODEL_RISK_CARD.md`; include limitations, known issues, intended uses, and out-of-scope uses.

---

### 1.9 Model Testing & Validation

**Requirement (ASOP 56 §3.6):** The actuary should test the model to confirm it is performing as intended, including unit testing, integration testing, and if applicable, independent validation.

**Current state:**
- Monthly projection tests: 62/62 passing (100%) — good for the new module
- Legacy tests (from audit): 59/67 passing (88%) — 8 failures in distributed executor and ALM rebalancing
- No independent validation
- No backtest framework
- No benchmark comparison

**Deviation:** 🟠 High  
**Gap:** Known test failures in production components are unresolved. 88% pass rate is below the 100% required for compliant production use. No backtesting against historical data.  
**Remediation:** Phase 3 — fix all 8 known test failures (pickling bug, ALM rebalancing); add integration tests for monthly projection; Phase 4 — backtesting framework.

---

## 2. ASOP 25 — Credibility Procedures (2013)

ASOP 25 governs how actuaries use credibility theory when setting assumptions based on experience data.

---

### 2.1 Assumption Basis Documentation

**Requirement (ASOP 25 §3.5):** The actuary should disclose the source of data used in the credibility procedure, including any relevant characteristics of the data and any adjustments made.

**Current state:** All 12 assumption tables have undocumented bases:
- Mortality: No reference to China Life Experience Study (CLES) or China Life Tables (CLT 2010–2013)
- Lapse: No reference to industry experience or company data; basis unknown
- Expenses: No inflation basis documented (CPI, HICP, or company-specific)
- Bonus rates: Labeled "discretionary" but no historical or governance basis stated

**Deviation:** 🟠 High  
**Gap:** A reviewing actuary cannot verify that assumptions are appropriate for the product and market. Regulatory submissions using these assumptions would require supplementary documentation.  
**Remediation:** Phase 2 — augment `docs/ASSUMPTIONS_REGISTER.md` Section 3 with explicit basis reference for each assumption; add `data_source` field to `metadata.json`.

---

### 2.2 Credibility Weighting Methodology

**Requirement (ASOP 25 §3.3):** Where company experience is blended with industry experience, the actuary should document the credibility weighting approach (limited fluctuation, Bühlmann, etc.).

**Current state:** No credibility weighting exists. Assumptions appear to be industry tables adopted wholesale. The enhanced tables (e.g., `mortality_qx_enhanced.csv`) may represent company experience overlays but there is no documentation of blending methodology.

**Deviation:** 🟡 Medium  
**Gap:** Unknown whether assumptions reflect company-specific risk profile or are fully industry-based.  
**Remediation:** Phase 2 — document in assumptions register whether assumptions are: (a) industry table, (b) company experience only, or (c) credibility-weighted blend with stated weights.

---

### 2.3 Mortality Improvement Factors

**Requirement (ASOP 25 / ASOP 56 §3.4):** Long-duration liability models must consider prospective mortality improvements. Static tables are generally not appropriate for products with 20+ year projection horizons without explicit justification.

**Current state:** All mortality tables are static (no improvement factors). The 20-year PAR endowment projects to policyholder age 55+, a period of material mortality improvement in China (~1.5–2.0% per annum per CLES studies).

**Deviation:** 🟠 High  
**Gap:** Mortality reserves and asset shares for long-duration products are likely overstated (if higher qx → higher death benefit outgo). Effect could be +/- 5–15% on PV net liability depending on term.  
**Remediation:** Phase 2 — add annual improvement factor column (`impr_pct`) to `mortality_qx.csv`; apply in monthly_projection.py; default to 1.5% p.a. based on CLES trend.

---

## 3. ASOP 7 — Analysis of Life, Health, or P/C Insurer Cash Flows (2011)

ASOP 7 governs cash flow analysis including ALM, scenario testing, and liability projection.

---

### 3.1 Dynamic Policyholder Behavior (Dynamic Lapse)

**Requirement (ASOP 7 §3.5):** Cash flow analysis for products with embedded options (e.g., surrender rights on participating products) should consider dynamic policyholder behavior — lapse rates that respond to interest rate or competitive market conditions.

**Current state:** Static lapse tables only. For a PAR endowment, the surrender value is guaranteed at 90% of asset share, creating a material interest-rate-sensitive option for policyholders. Dynamic lapse is the primary driver of TVOG on this product type.

**Deviation:** 🔴 Critical (for TVOG)  
**Gap:** Without dynamic lapse, the TVOG cannot be correctly computed. The model systematically understates policyholder option value in rising rate environments.  
**Remediation:** Phase 2 — implement dynamic lapse function: `lapse_rate(t) = base_lapse(t) * f(i(t) - credited_rate(t))` where `f` is a sensitivity function (e.g., logistic with calibrated slope); document in assumptions register.

---

### 3.2 Interest Rate Sensitivity Analysis (DV01 / Duration)

**Requirement (ASOP 7 §3.7):** Cash flow analysis should quantify the sensitivity of asset and liability values to interest rate changes, including dollar duration (DV01) and convexity.

**Current state:** No duration or DV01 metrics. The asset cashflow engine computes market values by asset class but provides no duration or interest rate sensitivity output. The liability projection is deterministic with no rate-shocked variants.

**Deviation:** 🟠 High  
**Gap:** ALM mismatch cannot be quantified. Interest rate risk exposure is unknown.  
**Remediation:** Phase 3 — add `compute_dv01()` function to asset cashflow module; add parallel liability projection at discount_rate ±1bp and ±100bp; produce duration gap report.

---

### 3.3 Asset-Liability Duration Matching

**Requirement (ASOP 7 §3.6):** The analysis should describe the degree of asset-liability matching and assess risks from mismatch.

**Current state:** The SAA defines target allocations (e.g., 60% Govt, 20% Credit, 10% Equity, 10% Cash) but no duration matching analysis exists. Government bond maturities and liability durations are not compared.

**Deviation:** 🟠 High  
**Gap:** Potential duration gap creates unquantified interest rate risk. China CNY government bonds at SAA weights may not match the duration of 5/10/20-year PAR liabilities.  
**Remediation:** Phase 3 — compute modified duration of liability stream; compute portfolio duration from asset cashflows; report duration gap; flag if gap exceeds ±2 years as action trigger.

---

### 3.4 ALM Rebalancing Logic — 100% Cash Bug

**Requirement (ASOP 7 §3.6):** ALM models must correctly implement the stated investment strategy. A rebalancing engine that does not rebalance under certain starting conditions is a model error.

**Current state:** Known bug: when portfolio starts at 100% cash and SAA target is ~10% cash, the rebalancing engine fails to purchase assets — cash weight remains at 1.0 after rebalancing. Test `test_rebalancing_to_saa` confirms this failure.

**Deviation:** 🔴 Critical  
**Gap:** Initial fund asset allocation cannot be established correctly. The model cannot be initialized from a newly-launched fund (cash-only starting position), which is the most common deployment scenario.  
**Remediation:** Phase 3 — fix `DynamicALMEngine` to trigger buy transactions when cash is above SAA target; add test for both rebalancing directions (cash→SAA and SAA→cash).

---

## 4. ERM / Risk Framework Deviations

These deviations relate to enterprise risk management standards and tail risk quantification, which are required for internal model approval under Solvency II-equivalent frameworks and PRC C-ROSS II.

---

### 4.1 Value at Risk (VaR) Computation

**Requirement (C-ROSS II, IAIS ICP 16, ERM best practice):** Stochastic models must produce tail risk metrics at specified confidence levels (e.g., VaR 99.5% for Solvency Capital Requirement).

**Current state:** No VaR computation. No scenario aggregation to produce distribution of outcomes.

**Deviation:** 🟠 High  
**Gap:** The model cannot support regulatory capital calculations or internal risk reporting.  
**Remediation:** Phase 2 — add `compute_var(scenarios, confidence=0.995)` to valuation module; depends on operational ESG and TVOG implementation.

---

### 4.2 Expected Shortfall (CVaR)

**Requirement:** Same as VaR above. ES/CVaR provides a more coherent tail risk measure and is preferred under IFRS 17 and C-ROSS II.

**Current state:** Absent.

**Deviation:** 🟠 High  
**Gap:** As above.  
**Remediation:** Phase 2 — co-implement with VaR: `compute_cvar(scenarios, confidence=0.995)`.

---

### 4.3 Stress Testing Framework

**Requirement (ASOP 56 §3.5.3):** Stress tests should include prescribed regulatory stresses and company-defined adverse scenarios.

**Current state:** No stress scenarios defined. No stressed assumption tables.

**Deviation:** 🟡 Medium  
**Gap:** Cannot demonstrate resilience to adverse conditions.  
**Remediation:** Phase 3 — define 5 standard stress scenarios: (1) +200bp rate shock, (2) -100bp rate shock, (3) +20% lapse shock, (4) +15% mortality shock, (5) -30% equity crash. Produce stressed TVOG and asset share results for each.

---

## 5. Distributed Executor — Pickling Bug

This is documented separately as it is a pre-requisite for all stochastic output.

### 5.1 Distributed Executor Pickling Failure

**Requirement:** The multi-scenario model architecture depends on `DistributedExecutor` to parallelize scenario runs. This is a required infrastructure component for any stochastic output.

**Current state:** `DistributedExecutor` cannot serialize locally-defined functions due to Python `multiprocessing` pickling constraints. 7 tests fail directly from this cause (4 in `test_integration_e2e.py`, 3 in `test_distributed_processing.py`).

**Deviation:** 🔴 Critical  
**Root cause:** The `process_func` argument passed to the executor is a closure or lambda defined in test scope. Python's `pickle` cannot serialize these. Functions must be defined at module top-level or use `cloudpickle`/`dill` instead of the default pickler.  
**Remediation:** Phase 3, Option A — Move all `process_func` definitions to module top-level. Option B — Replace `multiprocessing.Pool` with `concurrent.futures.ProcessPoolExecutor` using `cloudpickle` as serializer.

---

## 6. Summary: Deviation Register

| # | Standard | Deviation | Severity | Phase |
|---|----------|-----------|----------|-------|
| 1 | ASOP 56 §3.1.3 | Stochastic process not documented | 🔴 Critical | 2 |
| 2 | ASOP 56 §3.4 | Parameter calibration methodology absent | 🔴 Critical | 4 |
| 3 | ASOP 56 §3.5 | Scenario count adequacy unvalidated | 🔴 Critical | 3 |
| 4 | ASOP 56 §3.3 | P-measure vs Q-measure not distinguished | 🔴 Critical | 2 |
| 5 | ASOP 56 §3.1 | TVOG module absent (stated primary output) | 🔴 Critical | 4 |
| 6 | ASOP 7 §3.5 | Dynamic lapse absent | 🔴 Critical | 2 |
| 7 | ASOP 7 §3.6 | ALM rebalancing bug (100% cash) | 🔴 Critical | 3 |
| 8 | Infra | Distributed executor pickling failure | 🔴 Critical | 3 |
| 9 | ASOP 56 §3.5.2 | No sensitivity analysis framework | 🟠 High | 3 |
| 10 | ASOP 56 §3.6 | Known test failures unresolved (88% pass) | 🟠 High | 3 |
| 11 | ASOP 25 §3.5 | Assumption basis undocumented | 🟠 High | 2 |
| 12 | ASOP 25 | No mortality improvement factors | 🟠 High | 2 |
| 13 | ASOP 7 §3.7 | No DV01 / interest rate sensitivity | 🟠 High | 3 |
| 14 | ASOP 7 §3.6 | No asset-liability duration analysis | 🟠 High | 3 |
| 15 | ERM | No VaR computation | 🟠 High | 2 |
| 16 | ERM | No Expected Shortfall computation | 🟠 High | 2 |
| 17 | ASOP 56 §3.7 | Version inconsistency (0.1.0 vs 2.0.0) | 🟡 Medium | 2 |
| 18 | ASOP 56 §3.7 | No model governance policy | 🟡 Medium | 2 |
| 19 | ASOP 56 §3.1.4 | No model limitations disclosure | 🟡 Medium | 5 |
| 20 | ASOP 25 §3.3 | No credibility weighting documented | 🟡 Medium | 2 |
| 21 | ERM | No stress testing framework | 🟡 Medium | 3 |
| 22 | ASOP 7 | Discount curve rate inconsistent with market | 🟠 High | 4 |
| 23 | ASOP 56 | No independent model validation | 🟠 High | 5 |
| 24 | ASOP 56 | No model user documentation / guide | 🟡 Medium | 5 |

**Totals: 8 Critical | 10 High | 6 Medium | 24 Total**

---

## 7. Remediation Priority and Phase Mapping

### Phase 2 (Next): Industry Standards Alignment
Priority deviations to address:
- #1 — Document stochastic process (implement GBM-based internal ESG)
- #4 — Distinguish P-measure vs Q-measure; document intended use
- #6 — Implement dynamic lapse function
- #11 — Document assumption bases in register and metadata
- #12 — Add mortality improvement factors (1.5% p.a. default, CLES basis)
- #15, #16 — Scaffold VaR and ES functions (requires ESG and TVOG first)
- #17, #18 — Fix version inconsistency; create governance policy

### Phase 3: Model Validation & Testing
Priority deviations to address:
- #7 — Fix ALM rebalancing 100%-cash bug
- #8 — Fix distributed executor pickling failure
- #3 — Implement scenario convergence testing
- #9 — Implement sensitivity analysis runner
- #10 — Fix all test failures; achieve 100% pass rate
- #13, #14 — Add DV01 and duration analysis
- #21 — Define and implement stress scenarios

### Phase 4: Calibration & Backtesting
Priority deviations to address:
- #2 — Implement and document parameter calibration methodology
- #5 — Implement TVOG module (after ESG, dynamic lapse, distributed executor are fixed)
- #22 — Recalibrate discount curve to CNY market data

### Phase 5: Documentation & Delivery
Priority deviations to address:
- #19 — Model limitations disclosure (model risk card)
- #23 — Independent model validation
- #24 — End-user documentation and model usage guide

---

## 8. Compliance Status After This Report

| Framework | Pre-Phase 1 | After Phase 1 | Target (Post Phase 5) |
|-----------|-------------|---------------|----------------------|
| ASOP 56 Modeling | ❌ 0/8 items | ⚠️ 2/8 (audit trail, test suite) | ✅ 8/8 |
| ASOP 25 Credibility | ❌ 0/3 items | ⚠️ 1/3 (register structure) | ✅ 3/3 |
| ASOP 7 Cash Flows | ❌ 0/4 items | ⚠️ 1/4 (cashflow audit trail) | ✅ 4/4 |
| ERM Framework | ❌ 0/3 items | ❌ 0/3 | ✅ 3/3 |
| Infrastructure | ❌ 0/2 items | ⚠️ 1/2 (monthly projection working) | ✅ 2/2 |

---

## 9. Key Recommendations

**Immediate action (before next scheduled run can proceed to Phase 2):**

1. **Fix the distributed executor pickling bug.** This is the single highest-leverage fix: once resolved, multi-scenario runs become possible, which unblocks TVOG, VaR, ES, scenario convergence testing, and stress testing simultaneously.

2. **Implement GBM-based internal ESG.** Removing the Moody's file dependency makes the model self-contained and allows all stochastic testing to proceed without external data. A simple 2-factor Hull-White for rates + GBM for equity is sufficient for development purposes; the adapter architecture already supports swapping ESG sources.

3. **Implement dynamic lapse.** This is the primary driver of TVOG for a PAR endowment with surrender guarantees. Without it, TVOG cannot be validly estimated.

---

*This document is produced autonomously as part of the 12-hour model development cycle. It represents the output of Phase 1, Task 3. The next cycle will begin Phase 1, Task 4: "Review existing validation and testing framework."*

*All deviations identified here are input to the Phase 2 work plan.*

---

**End of Report**
