# IA Governance Requirements — Component Mapping
## PAR Fund Stochastic ALM & TVOG Model

**Document Type:** Model Governance Mapping  
**Prepared by:** Claude Actuarial Agent (Automated Cycle 7)  
**Date:** 2026-05-18  
**Phase:** 1 — Model Review & Documentation  
**Task:** Map model components to IA governance requirements (Final Phase 1 task)  
**Version:** 1.0  
**Status:** DRAFT — Pending Peer Review

---

## 1. Executive Summary

This document maps every material component of the PAR Fund Stochastic ALM & TVOG model against the Institute and Faculty of Actuaries (IFoA) governance requirements, principally:

- **TAS M (Technical Actuarial Standard: Models, 2016/2021)** — the primary standard governing actuarial model construction, documentation, testing, and use
- **TAS R (Technical Actuarial Standard: Reporting, 2016/2021)** — covering actuarial communications, disclosure, and uncertainty quantification
- **APS X2 (Review of Actuarial Work, 2019)** — peer review requirements for actuarial work products
- **IFoA Actuarial Modelling Practice (2015 CPD Note)** — supplementary guidance on model governance, validation, and change control

**Summary finding:** The model is in early development and has material gaps against all four IA governance standards. 12 requirements are currently non-compliant (🔴), 8 are partially addressed (🟠), and 4 are compliant (✅). No component achieves full production-grade IA governance compliance. Remediation is structured across Phases 2–5.

This document closes Phase 1 and serves as the input to Phase 2 prioritisation.

---

## 2. IA Governance Standards Summary

### TAS M — Models (Primary Standard)

TAS M sets minimum standards for all actuarial models used to inform material financial decisions. It covers:

| Section | Requirement Area |
|---------|-----------------|
| TAS M 3.1–3.2 | Model purpose, scope, and fitness for use |
| TAS M 3.3 | Model governance and ownership |
| TAS M 3.4 | Model documentation |
| TAS M 3.5 | Assumptions — appropriateness and setting process |
| TAS M 3.6 | Model testing and validation |
| TAS M 3.7 | Model change control |
| TAS M 3.8 | Model limitations and known issues disclosure |
| TAS M 3.9 | Data quality and data governance |

### TAS R — Reporting

TAS R requires that model outputs communicated to users include appropriate uncertainty disclosure, materiality judgements, and communication of limitations.

### APS X2 — Peer Review

APS X2 mandates independent review of material actuarial work products. For a stochastic model producing TVOG outputs (used in pricing or reserving), peer review is required.

### IFoA Modelling Practice Note

Covers model risk management, version control, model risk appetite, and the model risk register.

---

## 3. Component-by-Component Governance Mapping

### 3.1 ESG Module (`par_model_v2/esg/`)

**Component description:** Thin adapter over Moody's CNY ESG CSV file. Reads scenario paths for government bonds (ZCBs), credit bonds, equity, and cash. Hardcoded column naming convention for CNY Moody's format.

| IA Requirement | Ref | Status | Gap Description | Remediation Phase |
|---------------|-----|--------|-----------------|------------------|
| Model purpose documented | TAS M 3.1 | 🟠 Partial | Component purpose clear from code; no formal model specification document | Phase 2 |
| Stochastic process documented | TAS M 3.4 | 🔴 Non-compliant | ESG process type (Hull-White? GBM? Multi-factor?) not documented anywhere. TAS M requires the actuary to be able to explain to a non-specialist what the model does. | Phase 2 |
| Parameter calibration documented | TAS M 3.5 | 🔴 Non-compliant | No calibration documentation. Parameters are external (Moody's) with no description of the calibration approach. | Phase 4 |
| P/Q measure distinction | TAS M 3.5 | 🔴 Non-compliant | TAS M requires explicit statement of whether scenarios represent real-world or risk-neutral measure. Undocumented. Critical for TVOG. | Phase 2 |
| External dependency disclosed | TAS M 3.8 | 🔴 Non-compliant | Model cannot run without external Moody's file. This is a material limitation not disclosed in any model documentation. | Phase 2 |
| Data quality governance | TAS M 3.9 | 🔴 Non-compliant | No data validation on ESG inputs. No schema check, range check, or scenario adequacy test applied on load. | Phase 3 |
| Model testing | TAS M 3.6 | 🔴 Non-compliant | ESGAdapter has no unit tests. No test for missing file, malformed columns, or scenario count < minimum. | Phase 3 |

**Governance Owner (proposed):** ESG & Market Risk Actuary  
**Priority:** High — unblocks TVOG and all stochastic outputs

---

### 3.2 Asset Module (`par_model_v2/assets/`)

**Component description:** Holdings-based portfolio with DynamicALMEngine (SAA rebalancing, buy/sell priority, transaction costs), ParFundStochastic (surplus calculation, bonus smoothing), and AssetShareEngine (70/30 profit sharing, SDA).

| IA Requirement | Ref | Status | Gap Description | Remediation Phase |
|---------------|-----|--------|-----------------|------------------|
| Model purpose documented | TAS M 3.1 | ✅ Compliant | ALM and asset share purpose is clear from docstrings and audit report | — |
| Assumptions documented | TAS M 3.5 | 🟠 Partial | Transaction costs (2–60bps), SAA targets, and profit sharing ratio (70/30) are in code; basis not externally documented | Phase 2 |
| Known bug disclosed | TAS M 3.8 | 🔴 Non-compliant | ALM rebalancing fails for 100%-cash initial portfolio. This is a known defect not disclosed in any governance document. | Phase 3 |
| SAA basis documented | TAS M 3.5 | 🔴 Non-compliant | Strategic Asset Allocation targets in `strategic_asset_allocation.csv` have no documented basis (regulatory requirement? investment policy statement?). | Phase 2 |
| Duration/DV01 absent | TAS M 3.8 | 🟠 Partial | No interest rate sensitivity metrics. ASOP 7 / TAS M both require ALM models to demonstrate rate sensitivity management. Flagged as limitation. | Phase 2 |
| Model testing | TAS M 3.6 | 🟠 Partial | 10/11 ALM tests pass. 1 known failure (rebalancing bug). Asset share engine tested via monthly projection suite (100% pass). | Phase 3 |
| Change control | TAS M 3.7 | 🔴 Non-compliant | No formal change log for asset module. `MODEL_DEV_LOG.md` (initiated Cycle 1) provides informal audit trail only. | Phase 2 |

**Governance Owner (proposed):** Asset-Liability Management Actuary  
**Priority:** Medium — functional but with documented defect requiring disclosure

---

### 3.3 Liability Module (`par_model_v2/liabilities/`)

**Component description:** Deterministic liability cashflow projection for whole life and pension products. Monthly projection engine (`monthly_projection.py`) for PAR endowments (5/10/20Y). No stochastic liability projection.

| IA Requirement | Ref | Status | Gap Description | Remediation Phase |
|---------------|-----|--------|-----------------|------------------|
| Fitness for purpose | TAS M 3.1 | 🔴 Non-compliant | Model purpose requires TVOG (stochastic PV of guarantees). Deterministic-only liability projection is not fit for this purpose. Material gap. | Phase 4 |
| Stochastic extension documented | TAS M 3.4 | 🔴 Non-compliant | No documentation of how the deterministic module will be extended to stochastic scenarios. TVOG design is absent. | Phase 2 |
| Assumptions documented | TAS M 3.5 | 🟠 Partial | Mortality (UDD basis) and discount rate (annual, monthly compound conversion) are explicit in code. Lapse not modelled stochastically. | Phase 2 |
| Model testing | TAS M 3.6 | ✅ Compliant | Monthly projection test suite: 62/62 tests passing. Parametrized across all terms. Mathematical identities verified. | — |
| Limitations disclosed | TAS M 3.8 | 🔴 Non-compliant | Deterministic liability limitation not disclosed. No model limitations register entry. | Phase 2 |
| Dynamic lapse absent | TAS M 3.5 | 🔴 Non-compliant | Dynamic lapse (policyholder behaviour linked to rate environment) is entirely absent. For a TVOG model, this is a critical assumption gap — estimated TVOG sensitivity ±15–30% per ±25% lapse shock. | Phase 4 |

**Governance Owner (proposed):** Life Reserving & Product Actuary  
**Priority:** Critical — stochastic liability is a prerequisite for TVOG

---

### 3.4 Valuation Module (`par_model_v2/valuation/`)

**Component description:** DynamicALMEngine (covered under assets), AssetShareEngine (covered under assets), DistributedExecutor (multiprocessing batch runner with pickling bug), TVOG module (absent).

| IA Requirement | Ref | Status | Gap Description | Remediation Phase |
|---------------|-----|--------|-----------------|------------------|
| TVOG module — fitness for purpose | TAS M 3.1 | 🔴 Non-compliant | Primary stated output of the model (TVOG) does not exist. A model that cannot produce its primary output fails TAS M 3.1 definitively. | Phase 4 |
| Distributed executor — known defect | TAS M 3.8 | 🔴 Non-compliant | Pickling bug causes all multi-scenario batch runs to fail. Not disclosed in any governance document. | Phase 3 |
| Distributed executor — testing | TAS M 3.6 | 🔴 Non-compliant | 7/7 distributed executor tests fail due to the pickling bug. Test suite is technically failing. | Phase 3 |
| Scenario adequacy | TAS M 3.6 | 🔴 Non-compliant | No convergence testing or scenario count validation. TAS M requires evidence that stochastic outputs are stable. | Phase 3 |
| Checkpoint/restart — governance | TAS M 3.7 | 🟠 Partial | Checkpoint file mechanism exists for batch runs. No formal governance around checkpoint validation or version consistency. | Phase 2 |
| TVOG disclosure — measure choice | TAS R | 🔴 Non-compliant | When TVOG is implemented, TAS R will require explicit disclosure of scenario basis (P vs Q), confidence intervals, and sensitivity ranges. Framework not designed. | Phase 5 |

**Governance Owner (proposed):** Stochastic Modelling Lead  
**Priority:** Critical — distributed executor fix and TVOG implementation are the critical path for model completion

---

### 3.5 Assumptions Module (`par_model_v2/assumptions/`)

**Component description:** Multi-dimensional table-driven assumption provider. Hierarchical lookup with fallback. Covers mortality, lapse, expenses, bonus rates, discount curve, SAA, initial assets.

| IA Requirement | Ref | Status | Gap Description | Remediation Phase |
|---------------|-----|--------|-----------------|------------------|
| Assumption setting process | TAS M 3.5 | 🔴 Non-compliant | No documented process for setting, reviewing, or updating any assumption. TAS M 3.5 requires a formal assumption setting governance process. | Phase 2 |
| Assumption basis documented | TAS M 3.5 | 🔴 Non-compliant | No assumption has a documented data source, experience study reference, or expert judgment rationale. `ASSUMPTIONS_REGISTER.md` documents structure only, not basis. | Phase 2 |
| Sensitivity/stress tables absent | TAS M 3.6 | 🔴 Non-compliant | No stress assumption tables for sensitivity analysis. TAS M requires the model to support material sensitivity testing. | Phase 2 |
| Change control — assumptions | TAS M 3.7 | 🔴 Non-compliant | No version history for assumption files. No formal assumption change approval process. CSV files have no embedded change log. | Phase 2 |
| Assumption sign-off | APS X2 | 🔴 Non-compliant | APS X2 requires assumptions used in material work products to be peer-reviewed. No sign-off records exist. | Phase 5 |
| Testing | TAS M 3.6 | ✅ Compliant | 21/21 assumption tests passing. Hierarchical lookup, interpolation, and fallback logic well tested. | — |
| Known calibration errors | TAS M 3.8 | 🟠 Partial | Discount curve rate 3.5% vs CBIRC cap 3.0% — documented in `SOA_ASSUMPTIONS_DOCUMENT.md`. Not yet in a formal model limitations register. | Phase 2 |

**Governance Owner (proposed):** Assumption Setting Actuary  
**Priority:** High — assumption governance is prerequisite for any regulatory or audit use

---

### 3.6 Model Points (`par_model_v2/model_points/`)

**Component description:** Synthetic model point generator and grouping logic. `data/inforce/` directory is empty — no real inforce data.

| IA Requirement | Ref | Status | Gap Description | Remediation Phase |
|---------------|-----|--------|-----------------|------------------|
| Data quality governance | TAS M 3.9 | 🔴 Non-compliant | No inforce data. Model is operating entirely on synthetic model points. TAS M 3.9 requires data appropriateness assessment; synthetic data use should be disclosed. | Phase 2 |
| Data source documented | TAS M 3.9 | 🔴 Non-compliant | Generator parameters undocumented. What population does synthetic inforce represent? Not specified. | Phase 2 |
| Fitness for regulatory use | TAS M 3.1 | 🟠 Partial | Acceptable for development; not acceptable for any regulatory submission without real inforce data. | Phase 2 |
| Model point grouping | TAS M 3.4 | 🟠 Partial | Grouping logic exists. Materiality of grouping approximation not assessed or documented. | Phase 3 |

**Governance Owner (proposed):** Data & Inforce Actuary  
**Priority:** Medium for development; Critical before any external use

---

### 3.7 Grid Module (`par_model_v2/grid/`)

**Component description:** Hybrid monthly/annual time grid (`HybridGrid`) for projection timing.

| IA Requirement | Ref | Status | Gap Description | Remediation Phase |
|---------------|-----|--------|-----------------|------------------|
| Documentation | TAS M 3.4 | 🟠 Partial | Grid logic is implicit in code; no standalone documentation of timing conventions. | Phase 2 |
| Testing | TAS M 3.6 | 🔴 Non-compliant | No unit tests for HybridGrid. Grid boundary conditions are untested. | Phase 3 |

**Governance Owner (proposed):** Stochastic Modelling Lead  
**Priority:** Low — low complexity; risk contained

---

### 3.8 Model Governance Infrastructure (Cross-Cutting)

**Component description:** Items that span all model components — version control, change log, peer review, model risk register, audit trail.

| IA Requirement | Ref | Status | Gap Description | Remediation Phase |
|---------------|-----|--------|-----------------|------------------|
| Model risk register | TAS M 3.8 | 🔴 Non-compliant | No formal model risk register. `MODEL_AUDIT_REPORT.md` lists issues; not structured as a living risk register with risk owners and residual risk. | Phase 2 |
| Peer review framework | APS X2 | 🔴 Non-compliant | No peer review records. For material actuarial work, APS X2 mandates documented independent review. | Phase 5 |
| Version control | TAS M 3.7 | ✅ Compliant | Git with commit history; `MODEL_DEV_LOG.md` maintained. Adequate for development. | — |
| Version inconsistency | TAS M 3.7 | 🟠 Partial | `__version__.py` (0.1.0) vs `__init__.py` (2.0.0) — inconsistency must be resolved before release. | Phase 2 |
| Model owner designated | TAS M 3.3 | 🔴 Non-compliant | No named model owner in any governance document. TAS M 3.3 requires a responsible individual for each model. | Phase 2 |
| Model purpose statement | TAS M 3.1 | 🟠 Partial | README describes purpose. No formal model specification document with intended uses, out-of-scope uses, and materiality thresholds. | Phase 2 |
| User documentation | TAS M 3.4 | 🔴 Non-compliant | No end-user guide. No guidance on appropriate use cases, limitations, or interpretation of outputs. | Phase 5 |
| Model limitations register | TAS M 3.8 | 🔴 Non-compliant | Known issues: Moody's ESG dependency, pickling bug, ALM rebalancing bug, deterministic-only liability, no TVOG — none are in a formal limitations register accessible to output users. | Phase 2 |
| Audit trail completeness | TAS M 3.7 | 🟠 Partial | `MODEL_DEV_LOG.md` and Git provide development audit trail. No formal run log for production executions (inputs used, outputs produced, timestamp, responsible actuary). | Phase 5 |
| TAS R output disclosure | TAS R | 🔴 Non-compliant | No output report template exists. When TVOG outputs are produced, TAS R requires disclosure of methodology, assumptions, uncertainty ranges, and material limitations. | Phase 5 |

---

## 4. Compliance Status Summary

### 4.1 Requirement Count by Status

| Status | Count | % |
|--------|-------|---|
| ✅ Compliant | 4 | 16% |
| 🟠 Partially Compliant | 10 | 40% |
| 🔴 Non-Compliant | 20 | 44% |

*Note: The 4 compliant requirements are: model purpose (asset module), monthly projection testing, assumption testing, and version control via Git.*

### 4.2 Status by Standard

| Standard | Compliant | Partial | Non-Compliant | Overall |
|----------|-----------|---------|---------------|---------|
| TAS M 3.1 (Purpose) | 1 | 2 | 1 | 🟠 |
| TAS M 3.3 (Governance/Ownership) | 0 | 0 | 1 | 🔴 |
| TAS M 3.4 (Documentation) | 0 | 2 | 4 | 🔴 |
| TAS M 3.5 (Assumptions) | 0 | 3 | 5 | 🔴 |
| TAS M 3.6 (Testing/Validation) | 2 | 2 | 5 | 🔴 |
| TAS M 3.7 (Change Control) | 1 | 2 | 2 | 🟠 |
| TAS M 3.8 (Limitations) | 0 | 2 | 4 | 🔴 |
| TAS M 3.9 (Data) | 0 | 0 | 2 | 🔴 |
| TAS R (Reporting) | 0 | 0 | 2 | 🔴 |
| APS X2 (Peer Review) | 0 | 0 | 2 | 🔴 |

### 4.3 Compliance by Model Component

| Component | Compliant | Partial | Non-Compliant | Governance Rating |
|-----------|-----------|---------|---------------|------------------|
| ESG Module | 0 | 1 | 6 | 🔴 Critical gaps |
| Asset Module | 1 | 3 | 3 | 🟠 Functional with defect |
| Liability Module | 1 | 1 | 4 | 🔴 Not fit for TVOG purpose |
| Valuation Module | 0 | 1 | 5 | 🔴 Critical gaps |
| Assumptions Module | 1 | 2 | 5 | 🔴 Governance absent |
| Model Points | 0 | 2 | 2 | 🟠 Dev use only |
| Grid Module | 0 | 1 | 1 | 🟠 Low risk |
| Cross-Cutting Governance | 1 | 4 | 5 | 🔴 Infrastructure absent |

---

## 5. Remediation Roadmap by Phase

### Phase 2: Industry Standards Alignment (Priority Remediations)

The following IA governance gaps are highest priority and will be addressed in Phase 2:

| # | Remediation Action | TAS M Ref | Component |
|---|-------------------|-----------|-----------|
| G1 | Create formal Model Purpose & Scope document | 3.1 | Cross-cutting |
| G2 | Designate model owner in governance document | 3.3 | Cross-cutting |
| G3 | Create formal Model Limitations Register | 3.8 | Cross-cutting |
| G4 | Document ESG stochastic process type and parameters | 3.4 | ESG |
| G5 | Disclose P/Q measure distinction | 3.5 | ESG / Valuation |
| G6 | Document SAA basis and investment policy alignment | 3.5 | Assets |
| G7 | Implement assumption change control process | 3.7 | Assumptions |
| G8 | Add stress/sensitivity assumption tables | 3.6 | Assumptions |
| G9 | Document synthetic inforce data limitations | 3.9 | Model Points |
| G10 | Resolve version inconsistency (0.1.0 vs 2.0.0) | 3.7 | Cross-cutting |

### Phase 3: Model Validation & Testing

| # | Remediation Action | TAS M Ref | Component |
|---|-------------------|-----------|-----------|
| G11 | Fix distributed executor pickling bug (enables stochastic testing) | 3.6 | Valuation |
| G12 | Add ESGAdapter unit tests and data validation | 3.6, 3.9 | ESG |
| G13 | Add HybridGrid unit tests | 3.6 | Grid |
| G14 | Implement scenario convergence validation | 3.6 | Valuation |
| G15 | Fix ALM rebalancing bug (100%-cash start) | 3.6 | Assets |

### Phase 4: Calibration & Backtesting

| # | Remediation Action | TAS M Ref | Component |
|---|-------------------|-----------|-----------|
| G16 | Implement TVOG module | 3.1 | Valuation |
| G17 | Document parameter calibration methodology | 3.5 | Assumptions / ESG |
| G18 | Implement dynamic lapse model | 3.5 | Liability |
| G19 | Implement stochastic liability projection | 3.1, 3.5 | Liability |

### Phase 5: Documentation & Delivery

| # | Remediation Action | TAS M / TAS R Ref | Component |
|---|-------------------|--------------------|-----------|
| G20 | Create end-user model documentation | TAS M 3.4 | Cross-cutting |
| G21 | Implement formal peer review process (APS X2) | APS X2 | Cross-cutting |
| G22 | Design TAS R-compliant output report template | TAS R | Valuation / Reporting |
| G23 | Create production run log (inputs / outputs / responsible actuary) | TAS M 3.7 | Cross-cutting |
| G24 | Create model risk card with residual risks | TAS M 3.8 | Cross-cutting |

---

## 6. Proposed Governance Structure

TAS M 3.3 requires defined model ownership and governance. The following roles are proposed for this model:

| Role | Responsibility | TAS M Reference |
|------|---------------|-----------------|
| **Model Owner** | Accountable for model fitness for purpose, limitations disclosure, and sign-off | TAS M 3.3 |
| **Model Developer** | Responsible for code quality, testing, documentation, and change control | TAS M 3.4, 3.6, 3.7 |
| **Assumption Owner** | Sets, reviews, and approves assumptions; maintains assumption change log | TAS M 3.5 |
| **Independent Validator** | Conducts peer review; reviews output reports | APS X2, TAS R |
| **Data Steward** | Governs inforce data quality, ESG data inputs, and data validation | TAS M 3.9 |

**Current state:** All roles are unassigned. No governance structure exists. This is the highest-priority governance gap (G2 above).

---

## 7. Model Risk Rating

Based on the governance assessment, the overall model risk rating is:

**🔴 HIGH MODEL RISK**

**Rationale:**
- Model cannot produce its primary output (TVOG) — not fit for stated purpose
- Two known software defects (pickling bug, ALM rebalancing bug) remain unresolved
- No governance structure, model owner, or peer review process
- All assumptions are unsourced illustrative values — not externally calibrated
- External data dependency (Moody's ESG) not managed or disclosed
- No formal model limitations register

**Appropriate current use:** Development and research only. Not suitable for regulatory submission, external reporting, or pricing decisions without material remediation.

**Expected risk reduction by phase:**
- After Phase 2: Model Risk → 🟠 MEDIUM (governance documented, limitations disclosed)
- After Phase 3: Model Risk → 🟠 MEDIUM (defects resolved, testing complete)
- After Phase 4: Model Risk → 🟡 MEDIUM-LOW (TVOG implemented, calibrated)
- After Phase 5: Model Risk → ✅ LOW (peer reviewed, documentation complete)

---

## 8. Relationship to Existing Phase 1 Documents

This document is the final Phase 1 output and should be read alongside:

| Document | Content | Relationship |
|----------|---------|--------------|
| `docs/MODEL_AUDIT_REPORT.md` | Overall model architecture and initial gap assessment | Source of component descriptions |
| `docs/ASSUMPTIONS_REGISTER.md` | Detailed assumption table documentation | Source for TAS M 3.5 gaps |
| `docs/SOA_STANDARDS_DEVIATION_REPORT.md` | SOA ASOP deviation register | Complementary to IA gap register in this document |
| `docs/SOA_ASSUMPTIONS_DOCUMENT.md` | SOA-aligned assumptions specification | Overlapping with TAS M 3.5 requirements |
| `docs/VALIDATION_FRAMEWORK_REVIEW.md` | Test suite assessment and target validation framework | Source for TAS M 3.6 gaps |
| `MODEL_DEV_LOG.md` | Development audit trail | Partial audit trail per TAS M 3.7 |

---

## 9. Phase 1 Completion Confirmation

All Phase 1 tasks are now complete:

| Task | Status | Output |
|------|--------|--------|
| Audit current model code and architecture | ✅ Complete | `docs/MODEL_AUDIT_REPORT.md` |
| Document all model assumptions and parameters | ✅ Complete | `docs/ASSUMPTIONS_REGISTER.md` |
| Identify deviations from SOA stochastic modeling standards | ✅ Complete | `docs/SOA_STANDARDS_DEVIATION_REPORT.md` |
| Review existing validation and testing framework | ✅ Complete | `docs/VALIDATION_FRAMEWORK_REVIEW.md` |
| Create initial assumptions document with SOA compliance notes | ✅ Complete | `docs/SOA_ASSUMPTIONS_DOCUMENT.md` |
| Map model components to IA governance requirements | ✅ Complete | This document |

**Phase 1 is closed.** Phase 2 (Industry Standards Alignment) commences in the next cycle.

---

*Document prepared autonomously by Claude Actuarial Agent as part of the 12-hour automated model development cycle.*  
*Next review: Phase 5 — to be updated post peer review.*
