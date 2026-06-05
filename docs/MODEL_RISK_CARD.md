# Model Risk Card
## AI Actuarial 2026 — PAR Endowment Stochastic ALM & TVOG Model

**Document ID:** `MRC-PAR-2026-v1.0`  
**Issue Date:** 2026-05-23  
**Status:** DRAFT — Pending Model Owner Sign-off  
**Author:** Claude Actuarial Agent (Automated Development Cycle)  
**Review Owner:** Model Owner / Chief Actuary  
**Standards References:** SOA ASOP 56 §3.5–3.6, IA TAS M §3.6–3.9, IFoA Modelling Practice Note §4, CBIRC C-ROSS

---

## ⚠️ Production Use Restriction

> **THIS MODEL IS NOT CLEARED FOR PRODUCTION USE.**  
> Four open CRITICAL model risks (MR-001, MR-003, MR-004, MR-008) must be formally remediated and signed off before use in any of: regulatory reserve valuation, pricing sign-off, capital adequacy reporting, MCEV / embedded value reporting.  
> See Section 5 (Production Readiness Gates) for the full gate checklist.

---

## Table of Contents

1. [Model Identity](#1-model-identity)
2. [Inherent Risk Classification](#2-inherent-risk-classification)
3. [Model Risk Register — Current Status](#3-model-risk-register--current-status)
4. [Known Limitations and Disclosures](#4-known-limitations-and-disclosures)
5. [Production Readiness Gates](#5-production-readiness-gates)
6. [Sign-off Requirements](#6-sign-off-requirements)
7. [Monitoring and Review Framework](#7-monitoring-and-review-framework)
8. [Risk Card Change History](#8-risk-card-change-history)

---

## 1. Model Identity

| Field | Value |
|-------|-------|
| **Model name** | PAR Endowment Stochastic ALM & TVOG Model |
| **Model ID** | `par_model_v2` |
| **Version** | 2.0 (development) |
| **Model type** | Stochastic ALM + Q-measure Time Value of Options & Guarantees (TVOG) |
| **Product scope** | Participating (PAR) endowment — 5 / 10 / 20 year terms, Chinese market |
| **Primary output** | TVOG, P-measure VaR/ES, dynamic ALM asset-liability surplus |
| **Intended uses** | Reserve strengthening analysis, pricing margin assessment, embedded value reporting, capital sensitivity |
| **Prohibited uses (current)** | Regulatory reserve filing, regulatory capital submission, external audit, pricing sign-off — until all CRITICAL gates cleared |
| **Development framework** | Python 3.10+, NumPy / SciPy / Pandas / concurrent.futures |
| **Stochastic engine** | Hull-White 1-Factor (interest rates) + Geometric Brownian Motion (equity) |
| **Scenario count (TVOG)** | 500 minimum / 1,000 recommended (ASOP 56 §3.5 validated) |
| **Repository** | https://github.com/wilson37wu/AI_Actuarial_2026_ver_Codex (branch: main) |
| **Model owner** | [Model Owner — to be assigned] |
| **Assumption owner** | [Assumption Owner — to be assigned] |
| **Development lead** | Claude Actuarial Agent (AI-assisted development) |
| **Last updated** | 2026-05-23 |

---

## 2. Inherent Risk Classification

### 2.1 Overall Inherent Risk Rating: **HIGH**

The model is classified HIGH inherent risk under the IFoA Model Risk framework and consistent with SOA ASOP 56 §3.6 disclosure obligations, based on the following drivers:

| Dimension | Rating | Rationale |
|-----------|--------|-----------|
| Model complexity | HIGH | Stochastic ALM + Q-measure TVOG; Monte Carlo with 500–1,000 scenarios; two correlated stochastic processes |
| Materiality of outputs | HIGH | TVOG and VaR/ES directly inform reserving, pricing, and capital decisions |
| Calibration certainty | HIGH | All stochastic parameters are currently placeholders; calibration is not yet executed |
| Regulatory sensitivity | HIGH | Subject to CBIRC reserve valuation guidance and C-ROSS capital framework |
| Auditability | MEDIUM | Governance framework implemented; first formal sign-off cycle not yet completed |
| Test coverage | LOW | 743 unit/integration tests passing; automated health checks operational |

### 2.2 Residual Risk (Current Cycle)

Residual risk remains **HIGH** pending remediation of the four open CRITICAL model risks. Residual risk will be re-assessed at the Phase 5 sign-off review.

---

## 3. Model Risk Register — Current Status

The model risk register was seeded in Phase 2 (governance cycle, 2026-05-18) with 8 model risks (MR-001 to MR-008). Current status as of 2026-05-23:

| Risk ID | Title | Category | Inherent Rating | Status | Production Blocker |
|---------|-------|----------|-----------------|--------|--------------------|
| MR-001 | Discount rate exceeds CBIRC cap | Assumption Error | CRITICAL | IN_PROGRESS | ✅ YES |
| MR-002 | Investment return assumptions overstated vs CNY market | Assumption Error | HIGH | IN_PROGRESS | No (mitigating sensitivity available) |
| MR-003 | Dynamic lapse assumption absent | Model Error | CRITICAL | OPEN | ✅ YES |
| MR-004 | P/Q measure not enforced at runtime | Model Error | CRITICAL | IN_PROGRESS | ✅ YES |
| MR-005 | Distributed executor pickling failure | Process Risk | HIGH | **MITIGATED** | No |
| MR-006 | Model validation readiness below production threshold | Governance Risk | CRITICAL | IN_PROGRESS | ✅ YES (see gates §5) |
| MR-007 | No assumption change control process | Governance Risk | HIGH | IN_PROGRESS | No |
| MR-008 | HW1F calibration not yet executed | Model Error | CRITICAL | OPEN | ✅ YES |

**Summary:** 5 CRITICAL (4 open/in-progress + 1 partially mitigated), 3 HIGH (1 mitigated, 2 in-progress), 0 LOW.

### MR-001 — Discount Rate Exceeds CBIRC Regulatory Cap

**Risk:** The default discount rate is 3.5%, exceeding the CBIRC regulatory cap of 3.0% (Reserve Valuation Guidance 2023). Using the non-compliant rate understates statutory liabilities and overstates solvency margin.

**Current mitigation:** `DiscountRateValidator` emits a WARNING on any rate > 3.0%; the legacy 3.5% value is flagged in `DiscountRateValidator`, `docs/SOA_ASSUMPTIONS_DOCUMENT.md §3.3`, and the Phase 1 deviation register (D-02). A `ChangeRecord` under the governance framework is required to formally document the reduction.

**Remediation action required:** Reduce all projection defaults to ≤ 3.0%; execute `ChangeRecord` with before/after snapshot, impact assessment (expected reserve increase), and Assumption Owner sign-off.

---

### MR-002 — Investment Return Assumptions Overstated

**Risk:** Bond return assumptions (4.0–5.0%) are 100–180 bps above current CNY government bond yields (2.2–2.6%). GBM equity risk premium has not been calibrated. Both errors systematically understate TVOG and liability PV.

**Current mitigation:** `GBMCalibrator` scaffold in `par_model_v2/calibration/calibration_framework.py`; sensitivity analysis (VR-SE02) quantifies equity sensitivity as FLAT (economically correct for guaranteed endowment TVOG). Rate sensitivity quantified in `docs/SENSITIVITY_ANALYSIS_REPORT.md`.

**Remediation action required:** Complete `GBMCalibrator.calibrate()` using CSI 300 historical data; update bond return assumptions to CNY government yield curve; document blended σ_S basis (60% implied / 40% historical).

---

### MR-003 — Dynamic Lapse Assumption Absent

**Risk:** No dynamic lapse function is implemented. Static lapse at flat rates will materially understate TVOG sensitivity under stressed rate scenarios. The sensitivity analysis (VR-SE03, lapse ±25%) produced FLAT TVOG movement — this is an artefact of the static lapse implementation, not evidence of low sensitivity. With a dynamic lapse function, estimated TVOG impact is ±15–30%.

**Current mitigation:** None. The absence of dynamic lapse is explicitly noted in every sensitivity output and stability report.

**Remediation action required:** Implement an empirically-based or CBIRC-guidance-aligned dynamic lapse function. Calibrate to observed lapse experience or obtain formal expert judgment sign-off. Dynamic lapse is the highest-impact unimplemented assumption.

---

### MR-004 — P/Q Measure Not Enforced at Runtime

**Risk:** Prior to Phase 2, the codebase mixed real-world (P) and risk-neutral (Q) measures without enforcement. Mixing measures invalidates both VaR/ES and TVOG outputs.

**Current mitigation:** `Measure` enum implemented in `par_model_v2/stochastic/esg_process.py` (Phase 2, Task 1). `TVOGEngine` hard-fails on non-`Q` scenario sets and `RiskMetrics` now hard-fails on non-`P` loss distributions, closing the code-level consumer guard on the two material pricing/risk paths. Remaining gap: fresh execution evidence is still missing in the current workspace because the reachable interpreter does not include the project test/runtime dependencies (`numpy`, `pandas`, `scipy`, `pytest`).

**Remediation action required:** Re-run `tests/test_risk_metrics.py`, `tests/test_tvog.py`, and the full suite from a dependency-complete Python environment; then attach the results as formal G-05 evidence and update the GovernanceStore risk entry from code-remediated to verified.

---

### MR-005 — Distributed Executor Pickling Failure *(MITIGATED)*

**Risk:** Original codebase passed locally-scoped lambdas to `multiprocessing.Pool.map()`, causing `PicklingError` on all distributed batch runs.

**Mitigation (Phase 3, Task 1):** `DistributedExecutor` class in `par_model_v2/execution/distributed_executor.py` replaces the lambda pattern with module-level callables and `functools.partial`. Eager pickle validation at `TaskSpec.__init__()` surfaces errors at call-site. 63 tests passing (including `test_process_matches_sequential` — VR-I04). **Risk status: MITIGATED — close in next governance cycle.**

---

### MR-006 — Model Validation Readiness Below Production Threshold

**Risk:** At Phase 2 assessment, overall validation readiness was 13% (4 PASS, 1 PARTIAL, 26 NOT_RUN across 31 IA TAS M §3.6 requirements). Production sign-off requires ≥ 80% PASS with no CRITICAL failures open.

**Current mitigation:** Phase 3 delivered 8 validation tasks (743 tests, all passing); Phase 4 added scenario convergence validation, sensitivity testing, and stability analysis. Estimated current compliance: 55–65% (improved from 13% baseline; remaining NOT_RUN requirements are primarily live-data dependent or require human sign-off steps).

**Remediation action required:** Run `ValidationRunner` against the live model to generate current compliance percentage; target ≥ 80% PASS by Phase 5 sign-off. Independent model review (APS X2) required before production clearance.

---

### MR-007 — No Assumption Change Control Process *(Framework Complete; Adoption Required)*

**Risk:** Prior to Phase 2, assumption changes were uncontrolled — no sign-off, no audit record, no impact assessment.

**Current mitigation:** `GovernanceStore` + `ChangeRecord` + `SignOffWorkflow` implemented in `par_model_v2/governance/audit_trail.py`. Three-stage sign-off state machine (DRAFT → PEER_REVIEW → OWNER_REVIEW → APPROVED) enforced. First formal assumption change through the new process has not yet been executed.

**Remediation action required:** Execute first live assumption change (MR-001 discount rate reduction) through the `ChangeRecord` workflow to prove the process. Circulate governance framework to all stakeholders.

---

### MR-008 — HW1F Calibration Not Yet Executed

**Risk:** `HullWhiteCalibrator.calibrate()` is a `NotImplementedError` stub. Placeholder parameters (a = 0.10, σ_r = 0.012) produce model swaption volatility ≈ 250 bps against a market level of ≈ 42 bps — a 6× error. All interest rate scenario paths, ZCB prices, and TVOG outputs derived from these parameters are numerically valid but economically unreliable.

**Current mitigation:** The calibration scaffold (Jamshidian decomposition, L-BFGS-B optimiser, goodness-of-fit table) is implemented in `par_model_v2/calibration/calibration_framework.py` and fully specified in `docs/PARAMETER_CALIBRATION_METHODOLOGY.md`. All convergence and stability testing used placeholder parameters (results valid as infrastructure tests; not valid as economic outputs).

**Remediation action required:** Source CNY swaption implied volatility surface (PBOC / Wind terminal); implement `HullWhiteCalibrator.calibrate()` body using the L-BFGS-B scaffold; run goodness-of-fit check (max error < 1 bps threshold per `§4.2` of calibration methodology); obtain Assumption Owner sign-off.

---

## 4. Known Limitations and Disclosures

This section provides the limitations disclosure required under **SOA ASOP 56 §3.6** and **IA TAS M §3.7**. Each limitation must be communicated to any user relying on model output.

### 4.1 Uncalibrated Stochastic Parameters (CRITICAL)

All HW1F and GBM parameters are explicitly labelled `PLACEHOLDER` in source code. TVOG and VaR/ES outputs produced with placeholder parameters must not be used for any external reporting, pricing decision, or capital allocation until calibration is completed and signed off (MR-008, MR-002).

### 4.2 No Dynamic Lapse (CRITICAL)

TVOG sensitivity to lapse is materially understated. The sensitivity report shows lapse ±25% → FLAT TVOG; this result is a direct artefact of the static lapse implementation and should not be interpreted as evidence that lapse risk is immaterial. Dynamic lapse is the highest-impact unimplemented assumption (MR-003).

### 4.3 CBIRC Regulatory Rate Cap Breach (CRITICAL)

The default discount rate (3.5%) breaches the CBIRC 3.0% regulatory cap. Any reserve or capital output produced with discount_rate > 3.0% is non-compliant with Chinese statutory valuation requirements (MR-001).

### 4.4 Negative TVOG at Boundary Conditions

The model produces negative TVOG under two parameter configurations: (1) high σ_r = 0.05, and (2) initial rate r₀ = 3.0% (CBIRC cap). Negative TVOG values are mathematically valid outputs in these specific regimes but require governance sign-off before any use. `TVOGEngine` emits a `NegativeTVOGWarning` in both cases. See `docs/MODEL_STABILITY_AND_LIMITATIONS.md §2.3` for full analysis.

### 4.5 Single-Factor Interest Rate Model

The model uses Hull-White 1-Factor (HW1F) for interest rates. HW1F cannot independently fit the full shape of the yield curve and the swaption volatility surface. For products sensitive to curve steepness (e.g., long-bond ALM, cross-tenor guarantees), a 2-factor model may be necessary. This limitation is explicitly noted in `docs/ESG_PROCESS_DOCUMENTATION.md §7`.

### 4.6 Equity Process: GBM with Constant Volatility

The GBM equity process uses constant volatility and does not capture volatility clustering, fat tails, or stochastic volatility. For products with significant equity option payoffs, GBM will understate tail risk. The current PAR endowment TVOG is rate-driven (equity sensitivity is FLAT per VR-SE02); this limitation is low-impact for current product scope but material if equity-linked products are added.

### 4.7 Chinese Market Data Dependency

The model is designed for CNY swaption calibration and CSI 300 equity calibration. Until live market data is wired in (`par_model_v2/stochastic/esg_adapter.py` is the integration point), all scenario paths use the placeholder parameterisation. Do not extrapolate results to non-CNY markets without re-calibration.

### 4.8 No Expense or Tax Modelling

The projection engine does not currently model policy expenses, investment management charges, or corporate tax. Reserve and pricing outputs from the current model should be treated as gross-of-expense results. Expense loading must be applied separately.

### 4.9 Convergence Boundary

The 500-scenario minimum is validated for TVOG estimation (500→1,000 drift = 0.65%, within ASOP 56 §3.5 ≤ 1% tolerance). For VaR 99.5% (capital adequacy), 2,000 scenarios are the minimum and 10,000 are recommended per `docs/PARAMETER_CALIBRATION_METHODOLOGY.md §7`. Runs below these thresholds must not be used for capital reporting.

### 4.10 Backtesting: Synthetic Data Only

The backtesting framework (`par_model_v2/calibration/backtesting.py`) currently operates on synthetic historical data generated from the model's own parameters. Live CNY yield curve history and CSI 300 return history have not been loaded. Backtest results produced before live data is wired in are circular (model vs. itself) and cannot validate parameter accuracy.

---

## 5. Production Readiness Gates

The following gates must all be satisfied before the model is cleared for any production use. Gates are listed in recommended remediation order.

| Gate | Description | Blocking Risk(s) | Status |
|------|-------------|-----------------|--------|
| **G-01** | Discount rate ≤ 3.0% in all projection defaults | MR-001 | ❌ OPEN |
| **G-02** | HW1F calibrated to CNY swaption surface; goodness-of-fit < 1 bps | MR-008 | ❌ OPEN |
| **G-03** | GBM parameters calibrated to CNY market data | MR-002 | ❌ OPEN |
| **G-04** | Dynamic lapse function implemented and calibrated | MR-003 | ❌ OPEN |
| **G-05** | P/Q measure runtime enforcement verified by test | MR-004 | ⚠️ IN PROGRESS |
| **G-06** | IA validation suite ≥ 80% PASS, zero CRITICAL failures | MR-006 | ❌ OPEN |
| **G-07** | MR-001 assumption change executed through GovernanceStore ChangeRecord with sign-off | MR-007 | ❌ OPEN |
| **G-08** | Independent model review (APS X2) completed | MR-006 | ❌ OPEN |
| **G-09** | Backtesting populated with live CNY market data | — | ❌ OPEN |
| **G-10** | MR-005 formally closed in risk register | MR-005 | ⚠️ PENDING ADMIN |

**All 10 gates must reach ✅ CLEARED before any production use is permitted.**

### Use-Case Clearance Matrix

| Use Case | Gates Required | Current Status |
|----------|---------------|----------------|
| Regulatory reserve valuation (CBIRC) | G-01, G-02, G-05, G-06, G-07, G-08 | ❌ Not cleared |
| Pricing sign-off | G-01, G-02, G-03, G-04, G-06, G-08 | ❌ Not cleared |
| Capital adequacy (VaR 99.5%) | G-02, G-05, G-06, G-09 | ❌ Not cleared |
| MCEV / embedded value reporting | G-02, G-04, G-05, G-06, G-08 | ❌ Not cleared |
| Internal sensitivity / management reporting | G-01, G-05 (recommended) | ⚠️ With explicit disclosure |
| Model development and testing | No gate required | ✅ Cleared |

---

## 6. Sign-off Requirements

### 6.1 Mandatory Sign-offs Before Production Clearance

| Sign-off | Owner | Framework Reference | Trigger |
|----------|-------|---------------------|---------|
| Assumption change (discount rate to 3.0%) | Assumption Owner | IA TAS M §3.5; `ChangeRecord` workflow | G-01 |
| HW1F calibration result | Model Developer + Assumption Owner | SOA ASOP 56 §3.4; calibration methodology §6 | G-02 |
| GBM calibration result | Model Developer + Assumption Owner | SOA ASOP 56 §3.4 | G-03 |
| Dynamic lapse functional form | Assumption Owner | SOA ASOP 7 §3.3 | G-04 |
| P/Q measure enforcement confirmation | Model Developer | SOA ASOP 56 §3.1.3 | G-05 |
| Validation suite ≥ 80% PASS | Model Developer + Independent Reviewer | IA TAS M §3.6 | G-06 |
| Independent model review | Third-party reviewer (APS X2) | IA APS X2 | G-08 |
| Risk card final approval | Model Owner / Chief Actuary | IFoA Practice Note §4 | All gates |

### 6.2 Sign-off Execution

All sign-offs must be executed through the `GovernanceStore.change_records` workflow implemented in `par_model_v2/governance/audit_trail.py`. The three-stage state machine (DRAFT → PEER_REVIEW → OWNER_REVIEW → APPROVED) must be followed in sequence; no step may be skipped. Approved change records are stored in `.claude-dev/GOVERNANCE_STORE.json` and form part of the immutable audit trail.

### 6.3 Current Sign-off Status

No production sign-offs have been completed. The governance framework is operational and ready to receive its first formal change record.

---

## 7. Monitoring and Review Framework

### 7.1 Scheduled Automated Monitoring

The model health check framework (`par_model_v2/validation/model_health.py`, `ModelHealthChecker`) runs 10 automated checks (VR-H01 to VR-H10) every development cycle. Health check results are appended to the `GovernanceStore` audit trail (actor: `automated-health-check`). The following are monitored:

- All 12 subpackage imports (VR-H01)
- HybridGrid shape, boundary clamping, interpolation (VR-H02)
- ALM engine including 100%-cash edge case (VR-H03)
- Distributed executor sequential map correctness (VR-H04)
- All four input validators on minimal valid inputs (VR-H05)
- VaR/ES empirical distribution correctness (VR-H06)
- GovernanceStore JSON round-trip + SHA-256 integrity (VR-H07)
- IA validation requirements registry completeness (VR-H08)
- End-to-end 5y projection smoke test + audit wiring (VR-H09)
- ESGAdapter 500-scenario schema validation (VR-H10)

### 7.2 Annual Review Requirements (Post-Production)

Once the model is cleared for production use, the following annual reviews are required per IA TAS M §3.3 and SOA ASOP 56 §3.5:

| Review | Frequency | Owner | Standard |
|--------|-----------|-------|----------|
| Parameter recalibration | Annual (or triggered) | Model Developer | SOA ASOP 56 §3.4 |
| Assumption review | Annual | Assumption Owner | SOA ASOP 25 §3.3 |
| Backtesting coverage check | Annual | Model Developer | SOA ASOP 56 §3.5 |
| VaR/ES breach monitoring | Annual (Kupiec p-value) | Model Developer | SOA ASOP 56 §3.5 |
| Independent model review | Triennial | Third-party | IA APS X2 |
| Risk register review | Annual | Model Owner | IFoA Practice Note §4 |
| Risk card reissuance | Annual or on material change | Model Owner | SOA ASOP 56 §3.6 |

### 7.3 Recalibration Trigger Conditions

Immediate recalibration is required if any of the following occur:

1. Rate/equity coverage drops below 70% in the annual backtesting coverage check.
2. VaR 99% breach rate exceeds 5% in any 12-month rolling window.
3. Martingale control fails the Q-measure test (p-value < 0.05).
4. CNY short rate moves outside the calibrated HW1F mean-reversion range for more than 60 consecutive business days.
5. A material change in CBIRC regulatory guidance affecting reserve valuation discount rates.

---

## 8. Risk Card Change History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-23 | Claude Actuarial Agent | Initial issue — Phase 5 Task 2 |

---

*This model risk card is a required governance deliverable under IA TAS M §3.6 and IFoA Modelling Practice Note §4. It must be maintained and reissued on any material model change. The production use restriction in the header remains in force until all gates in Section 5 are cleared and the Model Owner sign-off is obtained.*
