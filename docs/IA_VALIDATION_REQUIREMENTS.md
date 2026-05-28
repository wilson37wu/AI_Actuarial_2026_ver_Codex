# IA TAS M §3.6 Validation Requirements
## PAR Fund Stochastic ALM & TVOG Model

**Document Type:** Model Validation Requirements Specification  
**Prepared by:** Claude Actuarial Agent (Automated Cycle 13)  
**Date:** 2026-05-18  
**Phase:** 2 — Industry Standards Alignment (Final Phase 2 Task)  
**Task:** Update model validation requirements per IA standards  
**Version:** 1.0  
**Status:** APPROVED — supersedes VALIDATION_FRAMEWORK_REVIEW.md validation scope section

---

## 1. Purpose and Scope

This document specifies the complete set of validation requirements for the PAR Fund Stochastic ALM & TVOG model, structured per the Institute and Faculty of Actuaries (IFoA) Technical Actuarial Standard for Models (TAS M), §3.6 (Testing and Validation).

It replaces the informal gap analysis in `docs/VALIDATION_FRAMEWORK_REVIEW.md` with a formal, machine-readable requirements registry implemented in `par_model_v2/validation/ia_validation.py`. Each requirement is:

- Uniquely identified (VR-\<layer\>\<number\>)
- Mapped to a specific TAS M / ASOP section
- Rated by severity (Critical / High / Medium / Low)
- Given concrete, measurable acceptance criteria
- Assigned to a development phase for execution

**This document governs what "validation complete" means for each phase of model development.** No model output should be used for regulatory reporting, pricing, or external disclosure until all CRITICAL requirements are in PASS or WAIVED status.

---

## 2. Governing Standards

| Standard | Applicability |
|----------|---------------|
| **TAS M 3.6** | Primary standard: scope, proportionality, and depth of validation |
| **TAS M 3.6.2** | Unit testing of individual model components |
| **TAS M 3.6.3** | Integration testing of the assembled model |
| **TAS M 3.6.4** | Stochastic scenario adequacy and convergence evidence |
| **TAS M 3.6.5** | Independent validation requirement for material components |
| **TAS M 3.8** | Sensitivity analysis as part of validation |
| **TAS M 3.9** | Data quality and data governance |
| **APS X2** | Peer review requirements (IA guidance) |
| **ASOP 56 §3.5** | Model testing: unit, integration, and scenario tests (SOA) |
| **ASOP 7 §3.5** | Scenario selection and adequacy documentation (SOA) |
| **ASOP 25 §3.6** | Assumption appropriateness validation (SOA) |
| **IFoA Modelling Practice Note §4** | Model risk register governance |

**Proportionality note (TAS M 3.6.1):** Validation depth must be proportionate to model materiality. This model is used for TVOG computation informing pricing and reserving decisions for a PAR life insurance fund — it is classified as **high materiality**. Full validation per all layers below is required before production use.

---

## 3. Validation Layers

Validation is organised into seven layers, executed in dependency order:

| Layer | Category | Description | Primary Phase |
|-------|----------|-------------|---------------|
| 1 | **Unit** | Individual function / class correctness | Phase 2–3 |
| 2 | **Integration** | Cross-module data flows and consistency | Phase 3 |
| 3 | **Stochastic** | ESG convergence, martingale test, fan charts | Phase 4 |
| 4 | **Sensitivity** | Parameter shocks and monotonicity analysis | Phase 4 |
| 5 | **Backtest** | Out-of-sample historical comparison | Phase 4 |
| 6 | **Governance** | Audit trail, change control, peer review | Phase 3–5 |
| 7 | **Data** | Input data schema, ranges, completeness | Phase 3 |

Layers 3–5 are blocked by: (1) distributed executor pickling bug (Phase 3 fix), and (2) ESG `simulate()` implementation (Phase 3).

---

## 4. Severity Framework

| Severity | Definition | Consequence of Failure |
|----------|------------|------------------------|
| **Critical** | Fundamental model correctness or regulatory compliance | Blocks all production use and regulatory filing |
| **High** | Material model quality gap | Requires documented exception + senior sign-off |
| **Medium** | Model quality gap; non-blocking | Requires remediation plan within next phase |
| **Low** | Informational | Addressed at next convenient opportunity |

---

## 5. Requirement Registry

The full machine-readable registry is in `par_model_v2/validation/ia_validation.py` as `IA_VALIDATION_REQUIREMENTS` (a `List[ValidationRequirement]`). The table below provides a human-readable summary.

### 5.1 Layer 1 — Unit Testing

| Req ID | Name | Severity | Reference | Phase |
|--------|------|----------|-----------|-------|
| VR-U01 | Monthly Projection Unit Tests — 100% Pass | Critical | TAS M 3.6.2 | 2 |
| VR-U02 | ALM Engine Unit Tests — Rebalancing Bug Fixed | Critical | TAS M 3.6.2 | 3 |
| VR-U03 | Risk Metrics Unit Tests — VaR/ES Correctness | High | TAS M 3.6.2; ASOP 56 §3.5 | 2 |
| VR-U04 | Stress Testing Unit Tests — CBIRC Scenario Coverage | High | TAS M 3.6.2; ASOP 7 §3.5 | 2 |
| VR-U05 | Governance/Audit Trail Unit Tests | Medium | TAS M 3.6.2; TAS M 3.3; 3.7 | 2 |
| VR-U06 | ESGAdapter Unit Tests — Data Loading and Validation | High | TAS M 3.6.2; TAS M 3.9 | 3 |
| VR-U07 | HybridGrid Unit Tests — Boundary Conditions | Medium | TAS M 3.6.2 | 3 |

**Current status (Phase 2 completion):**
- VR-U01: ✅ PASS — 62/62 monthly projection tests passing
- VR-U02: 🔴 NOT RUN — ALM rebalancing bug not yet fixed (Phase 3)
- VR-U03: ✅ PASS — All risk metrics tests passing
- VR-U04: ✅ PASS — All stress testing tests passing
- VR-U05: ✅ PASS — All governance tests passing
- VR-U06: 🔴 NOT RUN — No ESGAdapter tests exist yet (Phase 3)
- VR-U07: 🔴 NOT RUN — No HybridGrid tests exist yet (Phase 3)

### 5.2 Layer 2 — Integration Testing

| Req ID | Name | Severity | Reference | Phase |
|--------|------|----------|-----------|-------|
| VR-I01 | End-to-End Projection Integration Test | Critical | TAS M 3.6.3 | 3 |
| VR-I02 | Distributed Executor Integration Test | Critical | TAS M 3.6.3; ASOP 56 §3.5 | 3 |
| VR-I03 | Governance Integration — Audit Events on Model Run | Medium | TAS M 3.6.3; TAS M 3.3 | 3 |
| VR-I04 | Risk Metrics Integration — VaR/ES on Live Scenario Output | High | TAS M 3.6.3; ASOP 7 §3.3 | 3 |

**Current status:** All 🔴 NOT RUN — blocked by pickling bug (VR-I02 is the critical unblock).

### 5.3 Layer 3 — Stochastic Validation

| Req ID | Name | Severity | Reference | Phase |
|--------|------|----------|-----------|-------|
| VR-S01 | Scenario Convergence Test — TVOG Stability | Critical | TAS M 3.6.4; ASOP 56 §3.5 | 4 |
| VR-S02 | Martingale Test — Risk-Neutral Scenario Adequacy | Critical | TAS M 3.6.4; ASOP 56 §3.1.3 | 4 |
| VR-S03 | Scenario Fan Chart — Percentile Reasonableness | High | TAS M 3.6.4; TAS M 3.8 | 4 |
| VR-S04 | P / Q Measure Segregation Test | Critical | ASOP 56 §3.1.3 | 3 |
| VR-S05 | Hull-White Calibration Stability Test | High | ASOP 56 §3.1.3 | 4 |

**Current status:** VR-S04 🟠 PARTIAL (VaR/ES UserWarning implemented; TVOG consumer check deferred). All others 🔴 NOT RUN.

### 5.4 Layer 4 — Sensitivity Analysis

| Req ID | Name | Severity | Reference | Phase |
|--------|------|----------|-----------|-------|
| VR-SE01 | Discount Rate Sensitivity — TVOG Impact | High | TAS M 3.8; ASOP 7 §3.5 | 4 |
| VR-SE02 | Lapse Rate Sensitivity — Dynamic Lapse Impact | Critical | TAS M 3.8; ASOP 7 §3.5 | 4 |
| VR-SE03 | Investment Return Sensitivity — Bond / Equity Shock | High | TAS M 3.8; CBIRC C-ROSS | 4 |
| VR-SE04 | Mortality Sensitivity — Longevity Shock | Medium | TAS M 3.8; ASOP 25 §3.6 | 4 |

**Current status:** All 🔴 NOT RUN — Phase 4 targets.

### 5.5 Layer 5 — Backtesting

| Req ID | Name | Severity | Reference | Phase |
|--------|------|----------|-----------|-------|
| VR-B01 | Asset Return Backtest — 5Y Rolling Window | High | ASOP 56 §3.5 | 4 |
| VR-B02 | Liability Cashflow Backtest — Monthly Projection | Medium | ASOP 25 §3.6 | 4 |
| VR-B03 | VaR/ES Backtest — Exception Frequency | Medium | ERM Framework | 4 |

**Current status:** All 🔴 NOT RUN — Phase 4 targets.

### 5.6 Layer 6 — Governance

| Req ID | Name | Severity | Reference | Phase |
|--------|------|----------|-----------|-------|
| VR-G01 | AuditTrail — All Production Runs Logged | Critical | TAS M 3.3; 3.7 | 3 |
| VR-G02 | Model Change Control — ChangeRecord for All Breaking Changes | High | TAS M 3.7 | 3 |
| VR-G03 | Peer Review — APS X2 Sign-Off on Material Work Products | High | APS X2; TAS M 3.6.5 | 5 |
| VR-G04 | Model Risk Register — All Risks Rated and Mitigated | Medium | IFoA Practice Note §4 | 3 |
| VR-G05 | Validation Report — Final Sign-Off Before Production Use | Critical | TAS M 3.6; APS X2 | 5 |

**Current status:** VR-G01/G02/G04 🔴 NOT RUN (framework built, wiring deferred). VR-G03/G05 🔴 NOT RUN (Phase 5).

### 5.7 Layer 7 — Data Validation

| Req ID | Name | Severity | Reference | Phase |
|--------|------|----------|-----------|-------|
| VR-D01 | ESG Input Data — Schema and Range Validation on Load | High | TAS M 3.9 | 3 |
| VR-D02 | Inforce Data — Model Point Validation | High | TAS M 3.9 | 3 |
| VR-D03 | Assumption Tables — Range and Completeness Validation | Medium | TAS M 3.9; ASOP 25 §3.4 | 3 |

**Current status:** All 🔴 NOT RUN — Phase 3 targets.

---

## 6. Phase-by-Phase Validation Roadmap

### Phase 2 (Current — Completing)

**Requirements targeted this phase:**

| Req ID | Target Status | Achieved |
|--------|---------------|---------|
| VR-U01 | PASS | ✅ |
| VR-U03 | PASS | ✅ |
| VR-U04 | PASS | ✅ |
| VR-U05 | PASS | ✅ |
| VR-S04 | PARTIAL | 🟠 |

**Validation framework itself:** `par_model_v2/validation/ia_validation.py` delivered this cycle — 31 requirements defined, 64 unit tests passing (288 total across all test files).

### Phase 3 — Model Validation & Testing

**Priority order:**

1. **Fix ALM rebalancing bug** → unblocks VR-U02
2. **Fix distributed executor pickling** → unblocks VR-I01, VR-I02, VR-I04
3. **Implement ESGAdapter unit tests** → addresses VR-U06, VR-D01
4. **Wire AuditTrail into run loop** → addresses VR-G01, VR-G02
5. **Add HybridGrid unit tests** → addresses VR-U07
6. **Add model point and assumption data validation** → addresses VR-D02, VR-D03

**Exit criterion for Phase 3:** All VR-U\*, VR-I\*, and VR-D\* requirements in PASS or PARTIAL status. VR-S04 in PASS.

### Phase 4 — Calibration & Backtesting

1. Implement ESG `simulate()` → unblocks VR-S01 through VR-S05
2. Calibrate HW1F and GBM to historical CNY data → enables VR-B01
3. Generate TVOG under calibrated scenarios → enables VR-SE01, VR-SE02, VR-SE03, VR-SE04
4. Collect historical experience data → enables VR-B02, VR-B03

**Exit criterion for Phase 4:** All VR-S\*, VR-SE\*, VR-B\* requirements in PASS or PARTIAL. Sensitivity tables signed off.

### Phase 5 — Documentation & Delivery

1. Peer review (APS X2) of TVOG estimate, calibration report → VR-G03
2. Generate final ValidationReport with ValidationRunner
3. Sign-off by model developer + independent validator → VR-G05
4. Archive report and model version

**Exit criterion for Phase 5 (Production Readiness):**
- `ValidationReport.overall_status == ValidationStatus.PASS`
- Zero CRITICAL requirements in FAIL or NOT_RUN state
- All PARTIAL requirements have documented waivers

---

## 7. Compliance Tracking — Current Snapshot (Phase 2 End)

| Category | Total Reqs | PASS | PARTIAL | NOT RUN | Compliance % |
|----------|-----------|------|---------|---------|-------------|
| Unit | 7 | 4 | 0 | 3 | 57% |
| Integration | 4 | 0 | 0 | 4 | 0% |
| Stochastic | 5 | 0 | 1 | 4 | 0% |
| Sensitivity | 4 | 0 | 0 | 4 | 0% |
| Backtest | 3 | 0 | 0 | 3 | 0% |
| Governance | 5 | 0 | 0 | 5 | 0% |
| Data | 3 | 0 | 0 | 3 | 0% |
| **TOTAL** | **31** | **4** | **1** | **26** | **13%** |

**Overall status: PARTIAL — not fit for production use.**

The 13% compliance figure at Phase 2 end reflects that most automated checks are blocked by dependencies (pickling bug, ESG simulation) rather than incomplete design. The framework, documentation, and code are fully specified — execution follows in Phases 3–4.

---

## 8. Using the Validation Framework

```python
from par_model_v2.validation import ValidationRunner, ValidationCategory

# Run all requirements
runner = ValidationRunner(model_version="2.0.0-phase2")
report = runner.run()

# Print markdown summary
print(report.to_markdown())

# Check if model is production-ready
if report.overall_status.value != "PASS":
    print(f"Not production-ready: {report.failed} failures, {report.not_run} not run")

# Save JSON report for governance archive
with open(".claude-dev/validation_report_phase2.json", "w") as f:
    f.write(report.to_json())

# Run only unit tests (skip stochastic layer if ESG not ready)
runner_units = ValidationRunner(
    skip_categories=[
        ValidationCategory.STOCHASTIC,
        ValidationCategory.BACKTEST,
        ValidationCategory.INTEGRATION,
    ]
)
report_units = runner_units.run()
```

---

## 9. Document Change History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-18 | Claude Actuarial Agent (Cycle 13) | Initial release — Phase 2 final task |

**Supersedes:** The validation scope section of `docs/VALIDATION_FRAMEWORK_REVIEW.md` (Phase 1, Cycle 5). That document remains the source for the qualitative gap analysis and test inventory; this document governs formal requirements and acceptance criteria.

---

*Prepared per IA TAS M §3.6 validation requirements. Next review: Phase 3 completion.*
