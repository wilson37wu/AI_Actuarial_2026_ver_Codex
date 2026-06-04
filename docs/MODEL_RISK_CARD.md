# Model Risk Card
## AI Actuarial 2026 — PAR Endowment Stochastic ALM, TVOG & ESG Model

**Document ID:** `MRC-PAR-2026-v2.0`  
**Issue Date:** 2026-06-04  
**Supersedes:** MRC-PAR-2026-v1.0 (2026-05-23)  
**Status:** DRAFT — Pending Model Owner Sign-off  
**Author:** Claude Actuarial Agent (Automated Development Cycle — Phase 12, Task 5)  
**Review Owner:** Model Owner / Chief Actuary  
**Standards References:** SOA ASOP 25, 56; IA TAS M §3.6–3.9; IA(HK) GL16; IFoA Modelling Practice Note §4; CBIRC C-ROSS; ERM framework

---

## ⚠️ Production Use Restriction

> **THIS MODEL IS NOT CLEARED FOR PRODUCTION USE.**  
> Open CRITICAL model risks (MR-001, MR-003, MR-004, MR-008) and 2 CRITICAL limitation cards
> (ESG-LC-001: uncalibrated ESG parameters; HK-LC-003: placeholder HK liability assumptions)
> must be formally remediated before any output may be used for regulatory reserve valuation,
> pricing sign-off, capital adequacy reporting, MCEV / embedded value reporting, or any
> external purpose.  See Section 5 for the gate checklist.

---

## Table of Contents

1. [Model Identity](#1-model-identity)
2. [Scope Expansion — v1.0 → v2.0](#2-scope-expansion)
3. [Inherent Risk Classification](#3-inherent-risk-classification)
4. [Model Risk Register — Current Status](#4-model-risk-register--current-status)
5. [Known Limitations and Disclosures](#5-known-limitations-and-disclosures)
6. [Production Readiness Gates](#6-production-readiness-gates)
7. [Sign-off Requirements](#7-sign-off-requirements)
8. [Monitoring and Review Framework](#8-monitoring-and-review-framework)
9. [Risk Card Change History](#9-risk-card-change-history)

---

## 1. Model Identity

| Field | Value |
|-------|-------|
| **Model name** | PAR Endowment Stochastic ALM, TVOG & Multi-Market ESG Model |
| **Model ID** | `par_model_v2` |
| **Version** | 2.0.0 (educational; not production-cleared) |
| **Model type** | Stochastic ALM + Q-measure TVOG + Multi-market Economic Scenario Generator |
| **Product scope** | HK cash dividend PAR, HK reversionary bonus PAR; Chinese market base |
| **Liability portfolio** | 100,000-policy synthetic educational portfolio (HK PAR mix) |
| **Primary outputs** | TVOG, P-measure VaR/ES, dynamic ALM surplus, ESG scenarios (7 risk factors, 5 markets) |
| **Intended uses** | Educational actuarial modelling; stochastic ESG research; ALM teaching; internal sensitivity analysis with explicit disclosure |
| **Prohibited uses** | Regulatory reserve filing, regulatory capital submission, external audit, pricing sign-off — until all CRITICAL gates cleared |
| **Development framework** | Python 3.10+, NumPy / SciPy / Pandas / concurrent.futures |
| **Stochastic engine** | HW1F + G2++ (interest rates); GBM (equity); Nelson-Siegel (credit); HKML 2016 (mortality) |
| **ESG markets** | USD, EUR, HKD, CNY, JPY (rates); US, EU, HK/CN, JP, Asia ex-JP (equity); 4 FX pairs |
| **Scenario count (TVOG)** | 500 minimum / 1,000 recommended (ASOP 56 §3.5 validated) |
| **Test suite** | 1,079 tests collected (heavy Monte Carlo suites excluded from automated sweep) |
| **Repository** | https://github.com/wilson37wu/AI_Actuarial_2026_ver_Codex (branch: main) |
| **Model owner** | [Model Owner — to be assigned] |
| **Assumption owner** | [Assumption Owner — to be assigned] |
| **Last updated** | 2026-06-04 |

---

## 2. Scope Expansion — v1.0 → v2.0

v2.0 represents a substantial expansion of the v1.0 (2026-05-23) model.  All additions are
**educational scaffolding** — they do not change the production-use restrictions.

| Phase | Scope Added | Key Deliverables |
|-------|------------|-----------------|
| 6 | ESG architecture | Scenario schema, P/Q metadata, calibration interfaces, ESG consumer mapping |
| 7 | Interest rate ESG | HW1F (negative-rate-capable) + G2++ prototype; USD/EUR/HKD/CNY/JPY starter curves |
| 8 | Equity/FX/correlation | 5-region equity factors, 4 FX pairs, PSD-validated correlation matrix |
| 9 | Asset class library | Fixed income, private credit/equity/infrastructure, IR swaps, bond forwards |
| 10 | HK participating liabilities | Cash dividend and reversionary bonus product mechanics, asset-share support tests |
| 11 | 100k-policy processing | Synthetic portfolio, chunked processor, checkpoint restart, educational reporting pack |
| 12 | Governance packaging | Calibration scripts (4 modules), limitation cards (11), guided examples (6), validation dashboard |

---

## 3. Inherent Risk Classification

### 3.1 Overall Inherent Risk Rating: **HIGH**

The model is classified HIGH inherent risk, consistent with SOA ASOP 56 §3.6 and the
IFoA Model Risk framework.

| Dimension | Rating | Rationale |
|-----------|--------|-----------|
| Model complexity | HIGH | Multi-market stochastic ESG (7 risk factors × 5 markets); Q-measure TVOG; chunked 100k-policy ALM |
| Materiality of outputs | HIGH | TVOG and VaR/ES directly inform reserving, pricing, and capital decisions |
| Calibration certainty | HIGH | ESG parameters are synthetic placeholders; live market calibration not yet executed |
| Regulatory sensitivity | HIGH | HK IA(HK) GL16, CBIRC C-ROSS, HKMA requirements; rate cap and bonus supportability rules |
| Auditability | MEDIUM | Full governance framework, audit trail, limitation cards; no production sign-off cycle completed |
| Test coverage | LOW-MEDIUM | 1,079 tests (up from 743); 10/10 health checks PASS; heavy Monte Carlo suites not in auto-sweep |

### 3.2 Residual Risk

Residual risk remains **HIGH** pending remediation of open CRITICAL risks (MR-001, MR-003,
MR-004, MR-008) and the two CRITICAL limitation cards (ESG-LC-001, HK-LC-003).

---

## 4. Model Risk Register — Current Status

The risk register was seeded in Phase 2 with 8 risks (MR-001 to MR-008).  Status as of
Phase 12 delivery (2026-06-04):

| Risk ID | Title | Category | Inherent | Status | Production Blocker |
|---------|-------|----------|----------|--------|--------------------|
| MR-001 | Discount rate exceeds CBIRC cap (3.5% vs 3.0%) | Assumption Error | CRITICAL | IN_PROGRESS | ✅ YES |
| MR-002 | Investment return assumptions overstated vs market | Assumption Error | HIGH | IN_PROGRESS | No (sensitivity available) |
| MR-003 | Dynamic lapse assumption absent | Model Error | CRITICAL | OPEN | ✅ YES |
| MR-004 | P/Q measure not enforced at runtime | Model Error | CRITICAL | IN_PROGRESS | ✅ YES |
| MR-005 | Distributed executor pickling failure | Process Risk | HIGH | **MITIGATED** | No |
| MR-006 | Model validation readiness below production threshold | Governance Risk | CRITICAL | IN_PROGRESS | ✅ YES |
| MR-007 | No assumption change control process | Governance Risk | HIGH | IN_PROGRESS | No |
| MR-008 | HW1F calibration not yet executed | Model Error | CRITICAL | OPEN | ✅ YES |

**v2.0 additions — Phase 6–12 risks:**

| Risk ID | Title | Category | Inherent | Status | Production Blocker |
|---------|-------|----------|----------|--------|--------------------|
| MR-009 | ESG parameters are synthetic placeholders across all 5 markets | Model Error | CRITICAL | OPEN | ✅ YES (ESG-LC-001) |
| MR-010 | HK liability assumptions (mortality, lapse, bonus) are educational placeholders | Assumption Error | CRITICAL | OPEN | ✅ YES (HK-LC-003) |
| MR-011 | No live HK PAR portfolio — synthetic data only | Data Risk | HIGH | OPEN | No (educational disclosure sufficient) |
| MR-012 | G2++ rate model is a prototype — not production-grade | Model Error | HIGH | OPEN | No (HW1F is primary) |

**Summary:** 6 CRITICAL (5 open/in-progress, 1 in-progress with code guard), 5 HIGH (1 mitigated, 4 open), 0 LOW.

### MR-009 — ESG Parameters are Synthetic Placeholders

**Risk:** All HW1F, GBM, G2++, and Nelson-Siegel parameters for all five rate markets and five
equity regions were estimated from synthetic swaption / option grids.  No live market data
(Bloomberg, Wind, HKMA, PBOC) has been loaded.  Scenario paths are internally consistent but
are not calibrated to current market conditions.

**Current mitigation:** `scripts/calibration/` delivers all four calibration scripts with
explicit L-BFGS-B / TRF / credibility-blend methodology; placeholder status disclosed in every
calibration script header.  See limitation card ESG-LC-001.

**Remediation:** Source live market data; run `scripts/calibration/run_all_calibrations.py`
against live grids; obtain Assumption Owner sign-off on each module's RMSE.

---

### MR-010 — HK Liability Assumptions are Educational Placeholders

**Risk:** Mortality improvement rates (HKML 2016 +1.5% p.a.), lapse curves, and
bonus/dividend declaration rates are educational defaults.  Asset-share support tests
and TVOG outputs derived from these assumptions are illustrative only.

**Current mitigation:** Supportability test disclosed in `scripts/calibration/calibrate_liabilities.py`
and `docs/CALIBRATION_SCRIPTS_GUIDE.md`.  IA(HK) GL16 regulatory margin (0.30%) is applied;
educational limitation explicit in limitation card HK-LC-003.

**Remediation:** Calibrate to HK MPF-aligned mortality experience and observed lapse data;
obtain Assumption Owner and IA(HK) sign-off on declaration assumptions.

---

### MR-001 — Discount Rate Exceeds CBIRC Cap *(unchanged from v1.0)*

Default discount rate (3.5%) exceeds the CBIRC 3.0% regulatory cap.  See v1.0 card for full
analysis.  `DiscountRateValidator` emits a WARNING; formal `ChangeRecord` required.

---

### MR-003 — Dynamic Lapse Assumption Absent *(unchanged from v1.0)*

No dynamic lapse function.  Static lapse produces FLAT TVOG sensitivity — an implementation
artefact.  Estimated true TVOG impact of dynamic lapse: ±15–30%.  See v1.0 card.

---

### MR-004 — P/Q Measure Not Enforced at Runtime *(partially mitigated)*

Code-level consumer guards (TVOGEngine hard-fail on non-Q; RiskMetrics hard-fail on non-P)
implemented in Phase 2.  Q-measure martingale validation added in Phase 7 (QMeasureMartingaleValidator).
Remaining gap: formal execution evidence in a dependency-complete environment pending live
data integration (G-05).

---

### MR-005 — Distributed Executor Pickling Failure *(MITIGATED)*

Module-level callables + `functools.partial`; eager pickle validation at `TaskSpec.__init__()`.
63 tests PASS.  Pending administrative closure in GovernanceStore (G-10).

---

### MR-006 — Model Validation Readiness Below Production Threshold

31 IA TAS M §3.6 requirements defined; all 31 are NOT_RUN (automated stubs requiring live data
and independent review).  10 health checks now 10/10 PASS (up from 6/10 at Phase 12 start after
governance/__init__.py truncation bug fixed this cycle).  Target: ≥ 80% PASS for G-06.

---

### MR-008 — HW1F Calibration Not Yet Executed

`scripts/calibration/calibrate_curves.py` delivers the L-BFGS-B scaffold with documented
acceptance criteria (RMSE < 1 bps per market).  Calibration converged on synthetic swaption
grid; not yet run against live CNY/HKD/EUR/USD/JPY data.  Remaining action: source live data
and re-run.

---

## 5. Known Limitations and Disclosures

Limitations required under SOA ASOP 56 §3.6, IA TAS M §3.7, and IA(HK) GL16.  Full
limitation cards are in `docs/PHASE12_MODEL_LIMITATION_CARDS.md` (11 cards total).

### 5.1 Uncalibrated ESG Parameters — All Markets (CRITICAL)

All HW1F, GBM, G2++, and credit spread parameters are labelled `PLACEHOLDER` in source code
and calibration scripts.  No ESG output — scenario paths, TVOG, VaR/ES — may be used for
any external purpose until calibration is completed with live market data.  (MR-009, ESG-LC-001)

### 5.2 HK Liability Assumptions are Educational Defaults (CRITICAL)

Mortality, lapse, and bonus declaration assumptions use HKML 2016 improvement and heuristic
lapse curves.  Asset-share support tests and TVOG outputs for HK cash dividend and reversionary
bonus products are illustrative only.  (MR-010, HK-LC-003)

### 5.3 Dynamic Lapse Absent (CRITICAL)

Static lapse model produces FLAT TVOG lapse sensitivity — an artefact, not evidence of low
sensitivity.  True impact estimated ±15–30% for participating products.  (MR-003)

### 5.4 CBIRC Regulatory Rate Cap Breach (CRITICAL)

Default discount rate (3.5%) exceeds CBIRC 3.0% cap.  Reserve outputs with rate > 3.0% are
non-compliant with Chinese statutory valuation requirements.  (MR-001)

### 5.5 Negative TVOG at Boundary Conditions

Model produces negative TVOG under: (1) high σ_r = 0.05; (2) initial rate r₀ = 3.0% (CBIRC
cap).  Mathematically valid; require governance sign-off before any use.  `TVOGEngine` emits
`NegativeTVOGWarning`.

### 5.6 HW1F Single-Factor Limitation

HW1F cannot independently fit the full yield curve shape and swaption volatility surface.
G2++ prototype (Phase 7) addresses this but is not yet production-grade.  Cross-tenor guarantee
products require the two-factor model.  (ESG-LC-002)

### 5.7 GBM Constant Volatility Limitation

GBM equity process: constant volatility, no fat tails, no stochastic vol.  For equity-linked
products with option payoffs, GBM understates tail risk.  Current HK PAR TVOG is rate-driven;
this is low-impact for current product scope.  (ESG-LC-003)

### 5.8 Synthetic Portfolio — 100,000 Policies

The 100,000-policy portfolio is synthetically generated from educational distributions.  All
model-point characteristics (age, sum assured, duration) are stochastic placeholders.  No
actual policyholder data is used.  (HK-LC-001)

### 5.9 Private Asset Valuations are Educational Approximations

Private credit, private equity, and infrastructure asset models (Phase 9) use simplified
yield spreads, valuation-smoothing, and capital call schedules.  No mark-to-model discipline
or fair-value governance has been applied.  (ESG-LC-005)

### 5.10 Convergence Boundary

500-scenario minimum validated for TVOG (500→1,000 drift ≤ 0.65%, within ASOP 56 §3.5).
For VaR 99.5% capital, 2,000 scenarios minimum; 10,000 recommended.  Do not use sub-threshold
runs for capital reporting.

### 5.11 Backtesting: Synthetic Data Only

Backtesting operates on synthetic historical data generated from the model's own parameters.
Live CNY yield curve and CSI 300 / HSI history not yet loaded.  Backtest results are circular
and cannot validate parameter accuracy.

---

## 6. Production Readiness Gates

All 10 gates must reach ✅ CLEARED before any production use.

| Gate | Description | Blocking Risk(s) | Status |
|------|-------------|-----------------|--------|
| G-01 | Discount rate ≤ 3.0% in all projection defaults | MR-001 | ❌ OPEN |
| G-02 | HW1F calibrated to live CNY swaption surface; RMSE < 1 bps | MR-008, MR-009 | ❌ OPEN |
| G-03 | GBM parameters calibrated to live CNY/HKD market data | MR-002, MR-009 | ❌ OPEN |
| G-04 | Dynamic lapse function implemented and calibrated | MR-003 | ❌ OPEN |
| G-05 | P/Q measure runtime enforcement verified by test suite | MR-004 | ⚠️ IN PROGRESS |
| G-06 | IA validation suite ≥ 80% PASS; zero CRITICAL failures | MR-006 | ❌ OPEN |
| G-07 | MR-001 assumption change through GovernanceStore ChangeRecord | MR-007 | ❌ OPEN |
| G-08 | Independent model review (APS X2) completed | MR-006 | ❌ OPEN |
| G-09 | Backtesting populated with live market data | — | ❌ OPEN |
| G-10 | MR-005 formally closed in GovernanceStore risk register | MR-005 | ⚠️ PENDING ADMIN |
| G-11 | HK liability assumptions calibrated to live HK experience data | MR-010 | ❌ OPEN |
| G-12 | ESG parameters validated against all 5 live rate markets | MR-009 | ❌ OPEN |

**12 gates total (10 original + 2 v2.0 additions for expanded ESG/HK scope).  All must reach
✅ CLEARED before any production use.**

### Use-Case Clearance Matrix

| Use Case | Gates Required | Current Status |
|----------|---------------|----------------|
| Regulatory reserve valuation (CBIRC / IA HK) | G-01, G-02, G-05, G-06, G-07, G-08, G-11 | ❌ Not cleared |
| HK PAR pricing sign-off | G-01, G-03, G-04, G-06, G-08, G-11 | ❌ Not cleared |
| Capital adequacy (VaR 99.5%) | G-02, G-05, G-06, G-09, G-12 | ❌ Not cleared |
| MCEV / embedded value reporting | G-02, G-04, G-05, G-06, G-08, G-11 | ❌ Not cleared |
| Internal management reporting (with disclosure) | G-01, G-05 recommended | ⚠️ With explicit disclaimer |
| Educational / research use | No gate required | ✅ Cleared — see disclaimer |

---

## 7. Sign-off Requirements

### 7.1 Mandatory Sign-offs Before Production Clearance

| Sign-off | Owner | Reference | Trigger |
|----------|-------|-----------|---------|
| Discount rate change to ≤ 3.0% | Assumption Owner | IA TAS M §3.5; ChangeRecord workflow | G-01 |
| HW1F calibration results (5 markets) | Model Dev + Assumption Owner | ASOP 56 §3.4; calibrate_curves.py | G-02, G-12 |
| GBM calibration (5 markets) | Model Dev + Assumption Owner | ASOP 56 §3.4; calibrate_equity.py | G-03 |
| Dynamic lapse functional form | Assumption Owner | ASOP 7 §3.3 | G-04 |
| P/Q measure enforcement confirmation | Model Dev | ASOP 56 §3.1.3 | G-05 |
| Validation suite ≥ 80% PASS | Model Dev + Independent Reviewer | IA TAS M §3.6 | G-06 |
| HK mortality / lapse calibration | Assumption Owner + IA(HK) reviewer | IA(HK) GL16; calibrate_liabilities.py | G-11 |
| Independent model review | Third-party reviewer (APS X2) | IA APS X2 | G-08 |
| Risk card final approval | Model Owner / Chief Actuary | IFoA Practice Note §4 | All gates |

All sign-offs must use the `GovernanceStore.change_records` workflow (DRAFT → PEER_REVIEW →
OWNER_REVIEW → APPROVED).  Audit trail stored in `.claude-dev/GOVERNANCE_STORE.json`.

---

## 8. Monitoring and Review Framework

### 8.1 Automated Health Checks (Every Cycle)

`par_model_v2/validation/model_health.py` runs VR-H01..VR-H10 each development cycle.
**Current status: 10/10 PASS** (governance/__init__.py truncation bug fixed Phase 12 Task 4).
Results wired to GovernanceStore audit trail.

The **validation dashboard** (`par_model_v2/validation/validation_dashboard.py`) aggregates all
seven evidence streams (health, IA requirements, limitation cards, calibration, tests, phases,
readiness) into a single JSON + Markdown report.  Run `build_validation_dashboard()` on demand.

### 8.2 Annual Review Requirements (Post-Production)

| Review | Frequency | Owner | Standard |
|--------|-----------|-------|----------|
| ESG parameter recalibration (5 markets × 4 modules) | Annual or triggered | Model Developer | ASOP 56 §3.4 |
| HK liability assumption review | Annual | Assumption Owner | IA(HK) GL16 |
| Backtesting coverage check | Annual | Model Developer | ASOP 56 §3.5 |
| VaR/ES breach monitoring (Kupiec p-value) | Annual | Model Developer | ASOP 56 §3.5 |
| Correlation matrix stability review | Annual | Model Developer | Phase 8 PSD validation |
| Independent model review | Triennial | Third-party | IA APS X2 |
| Risk register review | Annual | Model Owner | IFoA Practice Note §4 |
| Risk card reissuance | Annual or on material change | Model Owner | ASOP 56 §3.6 |

### 8.3 Recalibration Trigger Conditions

Immediate recalibration required if any of the following:

1. Rate/equity coverage < 70% in annual backtesting coverage check.
2. VaR 99% breach rate > 5% in any 12-month rolling window.
3. Martingale test fails (p-value < 0.05) on Q-measure discount factors.
4. Any calibrated rate market moves outside HW1F mean-reversion range for > 60 consecutive business days.
5. Material change in CBIRC, HKMA, or IA(HK) regulatory guidance.
6. Correlation matrix eigenvalue < −0.01 in live market correlation estimate (PSD repair trigger).

---

## 9. Risk Card Change History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-23 | Claude Actuarial Agent | Initial issue — Phase 5 Task 2. V1 scope (5 phases, 743 tests, CNY market only). |
| 2.0 | 2026-06-04 | Claude Actuarial Agent | Phase 12 Task 5 refresh. V2 scope: multi-market ESG (5 rate + 5 equity markets), HK PAR liabilities, 100k-policy processing, 1,079 tests. Added MR-009/010/011/012. Added G-11/G-12. Limitation card cross-references added. Health check status updated to 10/10 PASS. |

---

*This model risk card is a required governance deliverable under IA TAS M §3.6 and IFoA
Modelling Practice Note §4.  It must be maintained and reissued on any material model change.
The production use restriction in the header remains in force until all gates in Section 6 are
cleared and the Model Owner sign-off is obtained.*

*Document ID: MRC-PAR-2026-v2.0 | Generated: 2026-06-04 | Source: PHASE12-T5-FINAL-DOCS*
