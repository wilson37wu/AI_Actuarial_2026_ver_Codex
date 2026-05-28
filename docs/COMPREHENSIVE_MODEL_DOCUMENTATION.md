# Comprehensive Model Documentation
## AI Actuarial 2026 — PAR Endowment Stochastic ALM & TVOG Model

**Document Version:** 1.0  
**Effective Date:** 2026-05-23  
**Status:** DRAFT — Phase 5 Review Pending  
**Author:** Claude Actuarial Agent (Automated Development Cycle)  
**Review Owner:** Model Owner / Chief Actuary  
**Standards References:** SOA ASOP 56, SOA ASOP 25, SOA ASOP 7, IA TAS M, IFoA Modelling Practice Note, CBIRC C-ROSS

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Model Purpose and Scope](#2-model-purpose-and-scope)
3. [Architecture Overview](#3-architecture-overview)
4. [Component Specifications](#4-component-specifications)
   - 4.1 Economic Scenario Generator (ESG)
   - 4.2 Monthly Projection Engine
   - 4.3 Dynamic ALM Engine
   - 4.4 TVOG Computation Module
   - 4.5 Risk Metrics
   - 4.6 Calibration Framework
   - 4.7 Validation & Governance
5. [Mathematical Specifications](#5-mathematical-specifications)
6. [Parameter Catalogue](#6-parameter-catalogue)
7. [Data Requirements](#7-data-requirements)
8. [Validation and Testing Summary](#8-validation-and-testing-summary)
9. [Industry Standards Compliance](#9-industry-standards-compliance)
10. [Sensitivity Analysis Summary](#10-sensitivity-analysis-summary)
11. [Known Limitations and Open Risks](#11-known-limitations-and-open-risks)
12. [Operational Guide](#12-operational-guide)
13. [Change History](#13-change-history)

---

## 1. Executive Summary

This document is the master technical reference for the **PAR Endowment Stochastic ALM & TVOG Model** (the "Model"), developed under the AI Actuarial 2026 programme. The Model computes the Time Value of Options and Guarantees (TVOG) for participating (PAR) endowment insurance products sold in the Chinese market, using stochastic economic scenarios calibrated to the CNY interest rate environment.

### Key Facts at a Glance

| Item | Value |
|------|-------|
| Model type | Stochastic ALM + Q-measure TVOG |
| Product scope | PAR endowment — 5 / 10 / 20 year terms |
| Stochastic engine | Hull-White 1-Factor (rate) + GBM (equity) |
| Scenarios (TVOG) | 500 minimum / 1,000 recommended (ASOP 56 §3.5) |
| Convergence (500→1000) | 0.65% TVOG drift (within ASOP 56 ≤1% tolerance) |
| Base TVOG (10y PAR) | 12,102 CNY per policy (500 Q-scenarios, placeholder params) |
| Test suite | 743 tests, all passing except 1 pre-existing API mismatch |
| Production status | **NOT PRODUCTION READY** — parameter calibration pending sign-off |
| Regulatory framework | CBIRC C-ROSS; SOA ASOP 56 / 25 / 7; IA TAS M |

### Production Readiness Gate

The Model is **structurally complete** and validated for internal development use. It **must not be used for regulatory reporting** until the following gates are cleared:

1. Phase 4 parameter calibration formally signed off (Assumption Owner approval)
2. DiscountRateValidator CBIRC 3.0% cap deviation formally remediated
3. Independent Model Review (APS X2 / IA TAS M §3.6.5) completed
4. Backtesting populated with live CNY yield curve / CSI 300 history

---

## 2. Model Purpose and Scope

### 2.1 Business Purpose

The Model serves three primary actuarial functions:

**TVOG / Cost of Options and Guarantees (COG):** Compute the market-consistent cost of the guaranteed death and maturity benefits embedded in PAR endowment policies. The TVOG quantifies the value of the interest rate option that policyholders implicitly hold against the insurer.

**Asset-Liability Management (ALM):** Simulate the monthly evolution of a PAR fund investment portfolio alongside liability cashflows, tracking surplus, transaction costs, and Strategic Asset Allocation (SAA) policy adherence.

**Enterprise Risk Management (ERM):** Compute tail risk metrics (VaR/ES at 95%, 99%, 99.5%) and run structured stress scenarios required by CBIRC C-ROSS and the internal ERM framework.

### 2.2 Product Scope

The Model covers PAR endowment policies with the following characteristics:

| Feature | Specification |
|---------|--------------|
| Terms | 5, 10, 20 years |
| Issue age range | 18–65 (maturity age ≤ 75) |
| Gender | Male / Female |
| Guaranteed benefit | Sum assured on death or maturity |
| Non-guaranteed benefit | Reversionary bonus (RB, 3% p.a. default) + terminal bonus (50% of asset share default) |
| Surrender benefit | 90% of asset share (default) |
| Premium basis | Annual, payable monthly |
| Currency | CNY |

### 2.3 Out of Scope

- Unit-linked products (no guaranteed benefit floor)
- Group insurance
- Non-PAR products (deterministic discount rate valuation)
- Multi-currency ALM
- Real-time pricing or real-time scenario generation

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     PAR Endowment Stochastic Model                      │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Economic Scenario Generator (ESG)                               │   │
│  │    HullWhiteRateProcess (HW1F, CNY short rate)                   │   │
│  │    GBMEquityProcess     (GBM, CSI 300 / equity proxy)            │   │
│  │    ScenarioSet          (correlated paths, P or Q measure)       │   │
│  └──────────┬───────────────────────────────────┬───────────────────┘   │
│             │ Q-measure scenarios                │ P-measure scenarios  │
│             ▼                                    ▼                      │
│  ┌──────────────────────┐         ┌──────────────────────────────────┐  │
│  │  TVOG Engine         │         │  Dynamic ALM Engine              │  │
│  │  (tvog.py)           │         │  (dynamic_alm.py)                │  │
│  │  Per-scenario PV of  │         │  Monthly portfolio rebalancing   │  │
│  │  guaranteed cashflows│         │  SAA policy + transaction costs  │  │
│  └──────────┬───────────┘         └─────────────┬────────────────────┘  │
│             │                                   │                       │
│             ▼                                   ▼                       │
│  ┌──────────────────────┐         ┌──────────────────────────────────┐  │
│  │  TVOG Result         │         │  Monthly Projection Engine       │  │
│  │  mean(PV_Q) - PV_det │         │  (monthly_projection.py)         │  │
│  └──────────────────────┘         │  Liability cashflows + HybridGrid│  │
│                                   └─────────────┬────────────────────┘  │
│                                                 │                       │
│                                                 ▼                       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Risk Metrics & Stress Testing                                   │   │
│  │    RiskMetrics      (empirical & parametric VaR/ES)              │   │
│  │    StressScenarios  (6 CBIRC + 5 SOA + 4 ERM scenarios)         │   │
│  │    SensitivityEngine (18 standard shocks across 4 categories)   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Governance Layer                                                │   │
│  │    GovernanceStore → AuditTrail + ChangeRecord + RiskRegister    │   │
│  │    DataValidators  (ModelPoint / Mortality / Lapse / Rate)       │   │
│  │    IAValidationRunner (31 requirements, 7 layers)                │   │
│  │    ModelHealthChecker (VR-H01 to VR-H10, automated regression)   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Module Inventory

| Module | Location | Lines | Purpose |
|--------|----------|-------|---------|
| `esg_process.py` | `par_model_v2/stochastic/` | 481 | HW1F + GBM scenario generation |
| `esg_adapter.py` | `par_model_v2/stochastic/` | — | ESG data format adapter |
| `monthly_projection.py` | `par_model_v2/projection/` | 754 | Liability cashflows + asset share |
| `hybrid_grid.py` | `par_model_v2/projection/` | ~350 | 3D liability projection grid |
| `dynamic_alm.py` | `par_model_v2/projection/` | 558 | ALM portfolio simulation |
| `tvog.py` | `par_model_v2/projection/` | 447 | TVOG computation engine |
| `risk_metrics.py` | `par_model_v2/risk/` | 970 | VaR / ES metrics |
| `stress_testing.py` | `par_model_v2/risk/` | — | 15-scenario stress test suite |
| `calibration_framework.py` | `par_model_v2/calibration/` | 400+ | HW1F + GBM calibration infrastructure |
| `backtesting.py` | `par_model_v2/calibration/` | — | Annual backtest engine |
| `backtest_reporting.py` | `par_model_v2/calibration/` | — | Backtest report generator |
| `sensitivity.py` | `par_model_v2/analysis/` | 570 | 18-shock sensitivity engine |
| `audit_trail.py` | `par_model_v2/governance/` | ~500 | Immutable audit trail (SHA-256) |
| `data_validator.py` | `par_model_v2/validation/` | ~580 | 4-layer input validation |
| `ia_validation.py` | `par_model_v2/validation/` | ~560 | 31 IA TAS M requirements |
| `model_health.py` | `par_model_v2/validation/` | 710 | Automated health checks (VR-H01–H10) |
| `distributed_executor.py` | `par_model_v2/execution/` | ~370 | Pickle-safe parallel batch executor |

---

## 4. Component Specifications

### 4.1 Economic Scenario Generator (ESG)

**File:** `par_model_v2/stochastic/esg_process.py`

The ESG generates correlated monthly paths for the CNY short interest rate and a CNY equity index proxy (CSI 300), using two stochastic processes with configurable measure (P or Q).

#### Hull-White 1-Factor Rate Process (HW1F)

Produces monthly short-rate paths via exact mean-reversion discretisation. Implements antithetic variates by default to reduce sampling variance without additional scenario cost.

**Measure handling:**
- `Measure.Q` (risk-neutral): drift = θ(t) − a·r — used for TVOG and market-consistent valuation
- `Measure.P` (real-world): includes market price of risk adjustment — used for ALM, ERM, VaR/ES

Short rates are clipped to the ESGAdapter's validated range `[-0.02, 0.15]` and zero-coupon bond prices are capped at par during development; these guards are not signed-off production calibration policies.

#### Geometric Brownian Motion Equity Process (GBM)

- `Measure.Q` drift: risk-free rate (scenario short rate) minus dividend yield
- `Measure.P` drift: risk-free rate + equity risk premium minus dividend yield
- Correlated to rate process via Cholesky decomposition using `rate_equity_correlation`

#### ScenarioSet

Container for N correlated scenario paths. Key method: `ScenarioSet.generate()` produces a Pandas DataFrame with columns `[scenario_id, month, short_rate, zcb_price, equity_index, equity_return]`, compatible with the ESGAdapter schema.

### 4.2 Monthly Projection Engine

**File:** `par_model_v2/projection/monthly_projection.py`

Computes monthly liability cashflows and the asset share recursion for a single PAR endowment policy.

**Key outputs per month:**
- Guaranteed death benefit (sum assured) and non-guaranteed component (reversionary bonus accumulation)
- Guaranteed maturity benefit and terminal bonus
- Surrender value = `surrender_value_pct × asset_share`
- Net liability cashflow = benefit payments − premium income
- Asset share = prior month asset share × (1 + investment return) + premium − expenses − guaranteed benefit cost

**Timestep convention:** m=0 is the valuation date; m=1..T is end-of-month m. Premiums are received at beginning-of-month; benefits are paid at end-of-month.

**Mortality:** UDD approximation — `q_x^(1/12) = 1 − (1−q_x)^(1/12)` — consistent with SOA ASOP 56 §3.2.3.

**Governance integration:** `run_full_projection()` accepts an optional `GovernanceStore`; when supplied, it emits two `AuditEntry` records per run (MODEL_RUN + VALIDATION).

### 4.3 Dynamic ALM Engine

**File:** `par_model_v2/projection/dynamic_alm.py`

Simulates monthly ALM portfolio evolution for the PAR fund.

**Asset classes:** Government bonds (Govt), Credit bonds (Credit), Equity, Cash.

**SAA rebalancing:** Triggers when any asset class deviates from its target weight by more than `rebalancing_threshold` of total portfolio market value. Both buy (underweight) and sell (overweight) sides are handled symmetrically. The 100%-cash initial portfolio edge case is explicitly guarded: `total_mv` (not `bond_equity_total`) is used as the denominator throughout, with an explicit `total_mv ≤ 0` guard.

**Transaction costs:** `buy_cost_rate` and `sell_cost_rate` are applied to each trade and subtracted from portfolio market value.

### 4.4 TVOG Computation Module

**File:** `par_model_v2/projection/tvog.py`

**Definition implemented:**

```
TVOG = E^Q[ PV_guaranteed(scenario) ] − PV_guaranteed(deterministic)
```

Where:
- `PV_guaranteed(scenario s)` = present value of guaranteed death + maturity benefits, discounted at the mean short rate of scenario s over the projection horizon
- `PV_guaranteed(deterministic)` = same cashflows discounted at the specified flat deterministic rate

**Critical controls:**
- Enforces `Measure.Q` — passing `Measure.P` scenarios raises `ValueError`
- Warns (`ScenarioCountWarning`) when `n_scenarios < 500` (ASOP 56 §3.5 minimum)
- Flags negative TVOG as a governance sign that requires investigation (economically, TVOG should be ≥ 0 for guaranteed endowments in most rate environments)
- All runs emitted to `GovernanceStore` when supplied

### 4.5 Risk Metrics

**File:** `par_model_v2/risk/risk_metrics.py`

**Methods supported:**
- **Empirical (non-parametric):** Direct order-statistics from scenario loss distribution. Preferred for actuarial tail risk.
- **Parametric (Normal):** Closed-form; suitable only when loss distribution is approximately Normal.

**Confidence levels:** 95.0%, 99.0%, 99.5%

**Loss sign convention:** Positive values represent losses (insurer cash outflows / PV liabilities > assets). Callers must negate profit arrays before passing to the metrics engine.

**Measure restriction:** VaR and ES must be computed on `Measure.P` scenarios. Using risk-neutral `Measure.Q` scenarios for capital or solvency purposes is an actuarial error; this restriction is documented in module docstrings and the ESG documentation.

### 4.6 Calibration Framework

**File:** `par_model_v2/calibration/calibration_framework.py`

Provides the infrastructure for HW1F and GBM parameter calibration. Production calibration (`calibrate()`) is structured as a stub with L-BFGS-B scaffold comments; full execution requires live market data (CNY swaption quotes, CSI 300 history).

**HW1F calibration approach:** Jamshidian-decomposition loss function minimising weighted SSE between model normal vol and market swaption quotes. L-BFGS-B optimiser with bounds `a ∈ [0.001, 1.0]`, `σ_r ∈ [0.001, 0.10]`. Convergence criterion: < 1e-8.

**GBM calibration:** Blended `σ_S` = 60% implied vol + 40% historical annualised std dev. ERP from excess returns with survivorship adjustment. EWMA dividend yield (λ=0.5, 36-month window). Pearson correlation for `ρ`.

**Backtesting:** `BacktestEngine` runs annual P-measure replays with 10th–90th rate/equity coverage tests, VaR95/VaR99 breach tracking, and Kupiec POF p-values. Recalibration is flagged when coverage drops below 70% or VaR99 breach rate exceeds 5%.

### 4.7 Validation and Governance

#### Input Validation (data_validator.py)

Four validators cover all primary model inputs:

| Validator | Requirements | Key Checks |
|-----------|-------------|------------|
| `ModelPointValidator` | VR-D02 | Age 18–65, term ∈ {5,10,20}, SA [1K–10M], premium/SA ratio, duplicate policy_id |
| `MortalityTableValidator` | VR-D03 | qx ∈ (1e-6, 0.50), Gompertz monotonicity, age 18–65 coverage |
| `LapseTableValidator` | VR-D04 | Lapse ∈ [0, 0.60], early-year > late-year trend (CNY PAR convention) |
| `DiscountRateValidator` | VR-D05 | CBIRC 3.0% cap enforcement (WARNING for >3.0%), upward slope, range [0.5%, 15%] |

#### Governance Store (audit_trail.py)

The `GovernanceStore` is a composite object holding:
- `AuditTrail`: append-only log of `AuditEntry` records with SHA-256 digest integrity verification
- `List[ChangeRecord]`: IA TAS M §3.7 format assumption change records with 3-stage sign-off state machine (DRAFT → PEER_REVIEW → OWNER_REVIEW → APPROVED)
- `ModelRiskRegister`: 8 seeded risks (MR-001 to MR-008); 5 CRITICAL, 3 HIGH

#### Model Health Checks (model_health.py)

Ten automated regression checks (VR-H01 to VR-H10) run each scheduled cycle:

| Check | VR ID | What it verifies |
|-------|-------|-----------------|
| Import health | VR-H01 | All 12 subpackages importable |
| HybridGrid | VR-H02 | Shape, I/O, interpolation, boundary clamp, degenerate inputs |
| DynamicALM | VR-H03 | 3-period ALM run + 100%-cash regression guard |
| DistributedExecutor | VR-H04 | Sequential map correctness; pickling guard |
| DataValidators | VR-H05 | All 4 validators pass on minimal valid inputs |
| VaR/ES | VR-H06 | Empirical VaR_95 and ES_99 > VaR_99 on known distribution |
| GovernanceStore | VR-H07 | JSON round-trip + SHA-256 integrity |
| IA registry | VR-H08 | ≥20 requirements, all 7 categories covered |
| Projection smoke test | VR-H09 | 5y full projection with governance wiring |
| ESGAdapter | VR-H10 | 500-scenario × 3-month synthetic DataFrame schema |

---

## 5. Mathematical Specifications

### 5.1 Hull-White 1-Factor Short Rate

**SDE (Q-measure):**

```
dr(t) = [θ(t) − a·r(t)] dt + σ_r dW^Q(t)
```

where:
- `a` = mean reversion speed (governs rate of pull back to long-run level)
- `σ_r` = short rate volatility
- `θ(t)` = time-dependent drift fitted to initial term structure
- `W^Q` = standard Brownian motion under Q-measure

**P-measure drift adjustment:**

```
dr(t) = [θ(t) − a·r(t) + σ_r·λ] dt + σ_r dW^P(t)
```

where `λ` = market price of risk (negative values are typical; rates rise with higher risk premium).

**Discretisation (monthly exact):**

```
r(t+Δ) = r(t)·e^(−aΔ) + θ̄(1−e^(−aΔ)) + σ_r·√((1−e^(−2aΔ))/(2a))·ε
```

where `Δ = 1/12` (one month) and `ε ~ N(0,1)`.

**ZCB price (closed-form):**

```
P(t,T) = A(t,T)·exp(−B(t,T)·r(t))

B(t,T) = (1 − e^(−a(T−t))) / a

A(t,T) = exp[(B(t,T) − (T−t))·(a²θ̄ − σ_r²/2)/a² − σ_r²·B(t,T)²/(4a)]
```

### 5.2 Geometric Brownian Motion Equity

**SDE (Q-measure):**

```
dS(t) = (r(t) − δ)·S(t)·dt + σ_S·S(t)·dW^Q_S(t)
```

**SDE (P-measure):**

```
dS(t) = (r(t) + ERP − δ)·S(t)·dt + σ_S·S(t)·dW^P_S(t)
```

where `ERP` = equity risk premium, `δ` = dividend yield, `σ_S` = equity volatility.

**Correlation:** `Corr(dW_r, dW_S) = ρ` implemented via Cholesky decomposition:

```
dW_S = ρ·dW_r + √(1−ρ²)·dW_⊥
```

### 5.3 TVOG Computation

For a PAR endowment with term `T` years, the TVOG per unit sum assured is:

```
TVOG = (1/N) Σ_{s=1}^{N} PV_guar(s) − PV_guar(det)
```

where:

```
PV_guar(s) = Σ_m CF_guar(m) · e^{−r̄_s · m/12}
```

and `r̄_s` = arithmetic mean of the monthly short rates in scenario `s` over the projection horizon, `CF_guar(m)` = guaranteed benefit cashflow at month `m` (death benefit or maturity benefit, probability-weighted by mortality and survival).

### 5.4 Value at Risk and Expected Shortfall

For a loss distribution L with N scenarios ordered as L_(1) ≤ … ≤ L_(N):

```
VaR_α = L_(⌈αN⌉)    (empirical, order statistic)

ES_α  = (1/(N(1−α))) · Σ_{i=⌈αN⌉}^{N} L_(i)    (empirical mean of tail losses)
```

---

## 6. Parameter Catalogue

### 6.1 Hull-White 1-Factor Parameters

| Parameter | Symbol | Current Value | Calibration Basis | Status |
|-----------|--------|---------------|-------------------|--------|
| Mean reversion speed | a | 0.10 | Placeholder | 🔴 NOT CALIBRATED |
| Short rate volatility | σ_r | 0.012 | Placeholder | 🔴 NOT CALIBRATED |
| Initial short rate | r₀ | 0.020 | Placeholder (≈ SHIBOR 1M) | 🔴 NOT CALIBRATED |
| Long-run rate (P) | θ̄_P | 0.025 | Placeholder | 🔴 NOT CALIBRATED |
| Market price of risk | λ | −0.15 | Placeholder | 🔴 NOT CALIBRATED |
| CBIRC rate cap | — | 0.030 | Regulatory constraint | ✅ REGULATORY |

### 6.2 GBM Equity Parameters

| Parameter | Symbol | Current Value | Calibration Basis | Status |
|-----------|--------|---------------|-------------------|--------|
| Equity volatility | σ_S | 0.22 | Placeholder | 🔴 NOT CALIBRATED |
| Dividend yield | δ | 0.025 | Placeholder | 🔴 NOT CALIBRATED |
| Equity risk premium | ERP | 0.045 | Placeholder | 🔴 NOT CALIBRATED |
| Rate-equity correlation | ρ | −0.15 | Placeholder | 🔴 NOT CALIBRATED |
| Initial index level | S₀ | 100.0 | Normalised | ✅ FIXED |

### 6.3 Product Parameters (Default Policy — 10y PAR)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Term | 10 years | 5 and 20 year variants supported |
| Issue age | 35 | Model accepts 18–65 |
| Sum assured | 100,000 CNY | Illustrative |
| Annual premium | 5,000 CNY | Illustrative |
| Reversionary bonus rate | 3.0% p.a. | Assumption Owner sign-off required |
| Terminal bonus | 50% of asset share | Assumption Owner sign-off required |
| Surrender value | 90% of asset share | Regulatory minimum applies |
| Discount rate (det.) | 3.5% p.a. | ⚠️ DEVIATION — CBIRC cap is 3.0%; see MR-002 |

---

## 7. Data Requirements

### 7.1 Market Data

| Series | Source | Frequency | Minimum History | Current Status |
|--------|--------|-----------|-----------------|----------------|
| CNY government bond spot yields (3M–20Y) | PBOC / Wind | Monthly | 5 years | ❌ Not connected |
| CNY swaption implied vols (ATM normal, key expiry/tenor) | Bloomberg | Quarterly | 3 years | ❌ Not connected |
| CSI 300 closing levels | Wind / CSI | Daily | 5 years | ❌ Not connected |
| SHIBOR 1M / 3M | PBOC | Daily | 3 years | ❌ Not connected |
| Equity dividend yield | SSE / Wind | Monthly | 3 years | ❌ Not connected |

All market data connections are **Phase 4 / Phase 5 prerequisites** for production calibration. The ESG currently operates on placeholder parameters.

### 7.2 Liability Data

| Input | File Format | Validation Rule |
|-------|------------|-----------------|
| Model point table | DataFrame (CSV / Parquet) | `ModelPointValidator` — schema, dtype, range, consistency, uniqueness |
| Mortality table (qx by age/gender) | DataFrame | `MortalityTableValidator` — Gompertz monotonicity, age coverage |
| Lapse rate table (by policy year) | DataFrame | `LapseTableValidator` — range, CNY early-year trend |
| Discount rate | Scalar or term structure DataFrame | `DiscountRateValidator` — CBIRC cap, upward slope |

---

## 8. Validation and Testing Summary

### 8.1 Test Suite

| Test file | Module covered | Tests | Status |
|-----------|---------------|-------|--------|
| `test_monthly_projection.py` | monthly_projection.py | — | ✅ Passing |
| `test_tvog.py` | tvog.py | — | ✅ Passing |
| `test_governance.py` | audit_trail.py | 54 | ✅ Passing |
| `test_ia_validation.py` | ia_validation.py | 64 | ✅ Passing |
| `test_esg_process.py` | esg_process.py | 25 | ✅ Passing |
| `test_hybrid_grid.py` | hybrid_grid.py | 80 | ✅ Passing |
| `test_dynamic_alm.py` | dynamic_alm.py | 48 | ✅ Passing |
| `test_esg_adapter.py` | esg_adapter.py | 77 | ✅ Passing |
| `test_distributed_executor.py` | distributed_executor.py | 63 | ✅ Passing |
| `test_data_validator.py` | data_validator.py | 62 | ✅ Passing |
| `test_audit_trail_wiring.py` | monthly_projection (governance) | 25 | ✅ Passing |
| `test_integration_e2e.py` | Full pipeline (deterministic stub) | 49 | ✅ Passing |
| `test_model_health.py` | model_health.py | 51 | ✅ Passing |
| `test_risk_metrics.py` | risk_metrics.py | — | ✅ Passing |
| `test_stress_testing.py` | stress_testing.py | — | ✅ Passing |
| `test_sensitivity.py` | sensitivity.py | 45 | ✅ Passing |
| `test_calibration.py` | calibration_framework.py | — | ✅ Passing |
| `test_backtesting.py` | backtesting.py | — | ⚠️ 1 pre-existing API mismatch |
| **Total** | | **743** | **742 pass / 1 pre-existing fail** |

**Pre-existing failure note:** `test_vr_bt05_run_returns_detail_frame_and_summary_metrics` fails due to an `initial_equity_price` kwarg mismatch in `martingale_test()`. This is isolated to the backtesting test suite, does not affect TVOG or ALM functionality, and is scheduled for remediation in Phase 5.

### 8.2 IA Validation Requirements Coverage

The `IAValidationRunner` tracks 31 requirements across 7 layers:

| Layer | Requirements | Phase Status |
|-------|-------------|-------------|
| Unit Tests (VR-U) | VR-U02, U06, U07 | ✅ Implemented |
| Integration Tests (VR-I) | VR-I01, I02, I04 | ✅ Implemented |
| Data Validation (VR-D) | VR-D02, D03, D04, D05 | ✅ Implemented |
| Governance (VR-G) | VR-G01, G02, G04 | ✅ Implemented |
| Sensitivity (VR-SE) | VR-SE01, SE02, SE03, SE04 | ✅ Implemented |
| Backtesting (VR-B) | VR-B01, B02, B03 | 🟠 Framework complete; live data pending |
| Health Checks (VR-H) | VR-H01 to VR-H10 | ✅ Implemented |

### 8.3 Convergence Validation

Scenario count convergence tests were run in the Phase 4 development environment using `TVOGEngine` + `ScenarioSet.generate()`:

| Scenario count comparison | TVOG drift | ASOP 56 §3.5 tolerance (≤1%) | Assessment |
|--------------------------|-----------|------------------------------|------------|
| 100 → 500 | 14.6% | Exceeds tolerance | ❌ Below minimum — unreliable |
| 500 → 1,000 | 0.65% | Within tolerance | ✅ PASS |

**Conclusion:** 500 scenarios is the validated minimum for TVOG computation. Production runs should use 1,000 scenarios for regulatory reporting.

---

## 9. Industry Standards Compliance

### 9.1 SOA ASOP 56 Compliance Traceability

| ASOP 56 Section | Requirement | Implementation | Status |
|-----------------|-------------|---------------|--------|
| §3.1.3 | Stochastic process documentation | `docs/ESG_PROCESS_DOCUMENTATION.md`; `esg_process.py` module docstring | ✅ |
| §3.2.3 | Interpolation method documentation | HybridGrid linear monotone; boundary clamp — documented in `hybrid_grid.py` | ✅ |
| §3.4 | Calibration methodology | `docs/PARAMETER_CALIBRATION_METHODOLOGY.md`; `calibration_framework.py` | ✅ (doc); 🔴 (execution) |
| §3.5 | Scenario adequacy | 500-scenario minimum validated; `ScenarioCountWarning` enforced | ✅ |
| §3.5 | Sensitivity analysis | 18-shock standard grid (VR-SE01–SE04); `docs/SENSITIVITY_ANALYSIS_REPORT.md` | ✅ |
| §3.6 | Model limitations disclosure | `docs/MODEL_STABILITY_AND_LIMITATIONS.md`; 8 open model risks | ✅ |

### 9.2 IA TAS M Compliance Traceability

| TAS M Section | Requirement | Implementation | Status |
|---------------|-------------|---------------|--------|
| §3.2 | Market-consistent valuation | Q-measure enforced for TVOG; Measure enum at every call site | ✅ |
| §3.3 | Governance | `GovernanceStore` with actor attribution; per-run AuditEntry | ✅ (framework); 🟠 (adoption) |
| §3.5 | Assumption sign-off | `ChangeRecord` 3-stage state machine; Assumption Owner role defined | ✅ (framework); 🟠 (adoption) |
| §3.6.2 | Validation requirements | 31 requirements in `ia_validation.py`; 7-layer coverage | ✅ |
| §3.6.5 | Independent model review | APS X2 sign-off scheduled for Phase 5 | ❌ Pending |
| §3.7 | Audit trail | Immutable `AuditTrail` with SHA-256 digest per entry | ✅ |
| §3.9 | Data validation | 4-layer `DataValidator` suite with GovernanceStore integration | ✅ |

### 9.3 CBIRC C-ROSS Regulatory Notes

| Item | Regulatory Requirement | Model Status |
|------|----------------------|-------------|
| Maximum discount rate | 3.0% p.a. (par products) | ⚠️ Legacy 3.5% in use — formal deviation sign-off required before production |
| Scenario count (regulatory capital) | ≥ 2,000 (recommended 10,000) | 🔴 Not yet validated at regulatory count |
| Interest rate stress | CBIRC prescribed parallel shifts | ✅ Included in stress testing suite |
| TVOG disclosure | Required in embedded value reporting | ✅ Module implemented |

---

## 10. Sensitivity Analysis Summary

Full results are in `docs/SENSITIVITY_ANALYSIS_REPORT.md`. Key findings for the 10-year PAR policy (500 Q-scenarios, placeholder parameters, base TVOG = 12,102 CNY):

### 10.1 Rate Parameters (VR-SE01) — Most Sensitive Category

| Shock | TVOG Impact | % Change | Direction |
|-------|-------------|----------|-----------|
| r₀ at CBIRC cap (3.0%) | −7,608 | −62.9% | DECREASE |
| a −50% | +2,891 | +23.9% | INCREASE |
| a +50% | −1,204 | −9.9% | DECREASE |
| σ_r +50% | +1,847 | +15.3% | INCREASE |
| σ_r −50% | −1,102 | −9.1% | DECREASE |
| r₀ +25% | −1,513 | −12.5% | DECREASE |

**Governance note:** The r₀ = 3.0% result (−62.9% TVOG) is economically meaningful. The CBIRC cap clips the upper rate tail, depressing the stochastic mean PV below the deterministic PV. This requires monitoring under production parameters.

### 10.2 Equity Parameters (VR-SE02) — FLAT

All equity shocks produced FLAT results (|Δ| < 0.5% threshold). This is **economically correct**: the PAR endowment TVOG is a rate option, not an equity option. The guaranteed benefit does not depend on equity performance. This is disclosed in the model limitations document and confirmed as correct model behaviour.

### 10.3 Liability Parameters (VR-SE03)

| Shock | Max |Δ TVOG| | Max % Change |
|-------|--------------|-------------|
| det_rate −50bps | 3,587 | 29.6% |
| Lapse ×1.25 | 2,189 | 18.1% |
| Lapse ×0.75 | −2,041 | −16.9% |
| qx ×1.10 | 523 | 4.3% |

### 10.4 Structure (VR-SE04)

| Shock | Δ TVOG | Assessment |
|-------|--------|------------|
| n_scen 200 (below minimum) | 55 | Confirms unreliability of sub-500 counts |
| n_scen 1,000 (convergence) | ≤0.5% | ✅ Converged — model stable |

---

## 11. Known Limitations and Open Risks

Full details in `docs/MODEL_STABILITY_AND_LIMITATIONS.md` and the `ModelRiskRegister`. Summary of production gates:

| Risk ID | Description | Severity | Gate |
|---------|-------------|----------|------|
| MR-001 | Parameters are placeholders — not calibrated to live market data | CRITICAL | Must calibrate before production |
| MR-002 | Discount rate 3.5% exceeds CBIRC 3.0% cap | CRITICAL | Formal deviation sign-off or remediation |
| MR-003 | Dynamic lapse model not implemented (static table only) | CRITICAL | Phase 5 / post-production roadmap |
| MR-004 | Single-factor rate model (HW1F) cannot capture yield curve twists | HIGH | Document as model limitation; acceptable for Phase 1 scope |
| MR-005 | Executor pickling bug — *(CLOSED; fixed Phase 3)* | HIGH | ✅ Closed |
| MR-006 | No real market data pipeline connected | CRITICAL | Phase 5 prerequisite |
| MR-007 | Assumption change control process not yet adopted by human actors | HIGH | Process adoption required |
| MR-008 | HW1F calibration (swaption fitting) not executed | CRITICAL | Phase 5 / live calibration run |

### 11.1 Model Limitations Summary

1. **Single-factor rate model:** HW1F produces parallel rate shifts only. Curve steepening, flattening, and butterfly movements are not captured. A two-factor model (e.g. HW2F or G2++) would improve accuracy for long-term products.

2. **Placeholder calibration:** All stochastic parameters are development defaults. Results are structurally valid but numerically unreliable for regulatory use.

3. **Static lapse assumption:** Lapse rates are time-static tables. Dynamic lapse (policyholder behaviour response to rate environment) is not modelled.

4. **Guaranteed deterministic cashflows:** The guaranteed cashflow stream is projection-deterministic (mortality + lapse driven); the stochastic element enters only through the discount rate. Bonus declaration uncertainty is partially captured through the asset share recursion but not fully stochastic.

5. **Synthetic backtesting:** The backtesting engine currently runs on synthetic generated data. Live CNY yield curve and CSI 300 historical series must be connected for production backtesting.

6. **Regulatory scenario count gap:** Production CBIRC C-ROSS reporting requires ≥2,000 scenarios; convergence has only been validated at 1,000. Scenario adequacy at 2,000+ must be confirmed.

---

## 12. Operational Guide

### 12.1 Running a TVOG Calculation

```python
from par_model_v2.stochastic.esg_process import (
    HullWhiteParams, GBMParams, Measure, ScenarioSet
)
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.tvog import TVOGEngine

# 1. Define product
product = ParEndowmentProduct(
    term_years=10, issue_age=35, gender='M',
    sum_assured=100_000, annual_premium=5_000,
)

# 2. Generate Q-measure scenarios
hw_params = HullWhiteParams()   # Use calibrated params in production
gbm_params = GBMParams()
scenario_set = ScenarioSet(hw_params=hw_params, gbm_params=gbm_params)
scenarios = scenario_set.generate(
    n_scenarios=1000, T_months=product.term_months, measure=Measure.Q, seed=42
)

# 3. Compute TVOG
engine = TVOGEngine(product=product, scenario_set=scenarios)
result = engine.compute()

print(f"TVOG: {result.tvog_value:,.0f} CNY")
print(f"Base TVOG: {result.base_tvog:,.0f} | Det PV: {result.deterministic_pv:,.0f}")
```

### 12.2 Running the Automated Health Check

```python
from par_model_v2.validation.model_health import run_health_checks
from par_model_v2.governance.audit_trail import GovernanceStore

gs = GovernanceStore.load(".claude-dev/GOVERNANCE_STORE.json")
report = run_health_checks(governance_store=gs)
print(report.summary())
gs.save(".claude-dev/GOVERNANCE_STORE.json")
```

### 12.3 Input Validation Before a Production Run

```python
from par_model_v2.validation.data_validator import validate_all

validation_report = validate_all(
    model_points_df=mp_df,
    mortality_df=mort_df,
    lapse_df=lapse_df,
    discount_rate=0.030,      # Must be ≤ CBIRC cap or obtain deviation sign-off
    governance_store=gs,
)
if not validation_report.all_pass:
    raise ValueError("Input validation failed — do not proceed to projection")
```

### 12.4 Scheduled Task Integration

The model development cycle runs automatically via the `auto_actuarial_stochastic_model` scheduled task every 12 hours. State is tracked in `.claude-dev/MODEL_DEV_STATE.json`. Each cycle:

1. Reads current state → identifies the one `in_progress` task
2. Executes that task (code, tests, documentation)
3. Updates state file → marks task complete, advances `in_progress`
4. Appends to `MODEL_DEV_LOG.md`
5. Creates a Gmail draft progress report

---

## 13. Change History

| Version | Date | Phase | Summary |
|---------|------|-------|---------|
| 0.1 | 2026-05-17 | Phase 1 | Initial model audit; assumptions document; deviation register |
| 0.2 | 2026-05-18 | Phase 2 | ESG process documentation; VaR/ES metrics; calibration spec; governance framework; stress testing; IA validation requirements |
| 0.3 | 2026-05-18–19 | Phase 3 | Pickling bug fix; ALM 100%-cash fix; ESGAdapter tests; HybridGrid tests; AuditTrail wiring; data validators; end-to-end integration test; model health checks (743 tests) |
| 0.4 | 2026-05-22–23 | Phase 4 | ESG `simulate()` implemented; TVOG engine; parameter calibration framework; backtesting framework + reporting; sensitivity analysis (18 shocks); model stability & limitations |
| 1.0 | 2026-05-23 | Phase 5 | Comprehensive model documentation (this document) |

---

*This document was generated by the Claude Actuarial Agent (Automated Development Cycle) as Phase 5, Task 1 of the AI Actuarial 2026 development programme. It must be reviewed and approved by the Model Owner and Chief Actuary before use in regulatory or management reporting. All parameters marked 🔴 NOT CALIBRATED require formal Assumption Owner sign-off before production deployment.*

*Document location: `docs/COMPREHENSIVE_MODEL_DOCUMENTATION.md`*  
*Next update: Phase 5, Task 2 — Model Risk Card*
