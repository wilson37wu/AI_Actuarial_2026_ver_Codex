# Parameter Calibration Methodology
## PAR Fund Stochastic ALM & TVOG Model — ESG Parameter Calibration

**Document Version:** 1.0  
**Date:** 2026-05-18  
**Prepared by:** Claude Actuarial Agent (Automated Cycle 10 — Phase 2, Task 3)  
**Standards Reference:** SOA ASOP 56 §3.4, ASOP 25, ASOP 7; IA TAS M §3.5; ERM Framework  
**Status:** DRAFT — Pending Assumption Owner sign-off  
**Supersedes:** ESG_PROCESS_DOCUMENTATION.md §5 (Calibration Summary, Phase 2)

---

## 1. Purpose and Scope

This document specifies the **complete parameter calibration methodology** for the Economic Scenario Generator (ESG) used in the PAR Fund Stochastic ALM & TVOG model. It satisfies the calibration documentation requirement of **SOA ASOP 56 §3.4**:

> *"The actuary should document the methods used to select the parameters of the model. The documentation should include the data used and the calibration process."*

And the credibility requirement of **SOA ASOP 25 §3.3**:

> *"The actuary should select a credibility procedure appropriate for the intended purpose and document the basis for the procedure selected."*

**Stochastic risk factors covered:**

| Risk Factor | Model | Measure | Parameters to Calibrate |
|-------------|-------|---------|-------------------------|
| CNY nominal interest rates | Hull-White 1-factor (HW1F) | P and Q | a (mean-reversion speed), σ_r (vol), λ_r (market price of risk), r(0) (initial short rate) |
| CNY equity returns (CSI 300 proxy) | Geometric Brownian Motion (GBM) | P and Q | σ_S (equity vol), δ (dividend yield), λ_S (equity risk premium source) |
| Cross-asset correlation | Pearson / Cholesky | Both | ρ_{r,S} (rate-equity correlation) |

**Out of scope:** Credit spread stochastic calibration, inflation calibration, mortality improvement calibration (addressed in separate assumption documents).

**Relationship to other documents:**

| Document | Role |
|----------|------|
| `docs/ESG_PROCESS_DOCUMENTATION.md` | Mathematical process specification (what the model is) |
| `docs/PARAMETER_CALIBRATION_METHODOLOGY.md` | **This document** — how parameters are estimated |
| `docs/ASSUMPTIONS_REGISTER.md` | Assumption inventory and compliance status |
| `docs/IA_GOVERNANCE_REQUIREMENTS.md` | Governance workflow and sign-off requirements |
| `.claude-dev/CALIBRATION_CHANGE_LOG.md` | Versioned record of every calibration update (Phase 4) |

---

## 2. Regulatory and Standards Alignment

### 2.1 Applicable Standards

| Standard | Section | Requirement | How This Document Addresses It |
|----------|---------|-------------|-------------------------------|
| SOA ASOP 56 | §3.4 | Document calibration methods and data sources | Full data source table (§4), calibration procedures (§5–6) |
| SOA ASOP 56 | §3.5 | Scenario adequacy — validate scenario count for intended use | Scenario count requirements (§7) |
| SOA ASOP 25 | §3.3 | Document credibility procedure and its basis | Credibility hierarchy (§3), data quality assessment (§4.3) |
| SOA ASOP 7 | §3.3 | Document assumptions for cash flow testing | Integration with projection engine (§8) |
| IA TAS M | §3.5 | Assumption appropriateness: set process, documentation, sign-off | Governance workflow (§9) |
| IA TAS M | §3.7 | Model change control: log all assumption changes | Change log protocol (§9.3) |
| ERM Framework | — | Tail risk metrics at defined confidence levels | Scenario adequacy for VaR/ES (§7) |
| CBIRC Guidelines | — | Interest rate assumption ≤ 3.0% for regulatory reserves | Discount rate constraint (§5.1, Note A) |

### 2.2 Calibration Status by Parameter

| Parameter | Symbol | Current Value | Status | Calibration Phase |
|-----------|--------|---------------|--------|-------------------|
| HW1F mean-reversion speed | a | 0.10 | 🔴 Placeholder | Phase 4 |
| HW1F short rate volatility | σ_r | 0.012 (1.2% p.a.) | 🔴 Placeholder | Phase 4 |
| HW1F market price of risk | λ_r | 0.0 (not yet set) | 🔴 Placeholder | Phase 4 |
| HW1F initial short rate | r(0) | 0.025 (2.5%) | 🟠 Approximate | Phase 4 |
| GBM equity volatility | σ_S | 0.22 (22% p.a.) | 🔴 Placeholder | Phase 4 |
| GBM dividend yield | δ | 0.025 (2.5%) | 🟠 Approximate | Phase 4 |
| GBM equity risk premium | ERP | 0.045 (4.5%) | 🔴 Placeholder | Phase 4 |
| Rate-equity correlation | ρ_{r,S} | −0.15 | 🔴 Placeholder | Phase 4 |

**⚠️ Production Use Restriction:** All parameters marked 🔴 Placeholder are illustrative only. They must not be used for regulatory reporting, pricing, or external disclosure. Production calibration is a **Phase 4 deliverable**.

---

## 3. Calibration Philosophy and Credibility Hierarchy

### 3.1 Measure-Specific Calibration Requirements

Calibration methodology differs by probability measure, per the P/Q distinction established in `ESG_PROCESS_DOCUMENTATION.md §2.2`:

| Aspect | Q-Measure (Risk-Neutral) | P-Measure (Real-World) |
|--------|------------------------|----------------------|
| Purpose | TVOG, MCEV, market-consistent pricing | ALM, ERM, VaR/ES, stress testing, bonus projection |
| Calibration target | Market prices of liquid derivatives (no-arbitrage) | Historical return distributions (maximum-likelihood) |
| Primary data | Swaption implied vols, equity option implied vols | CNY government bond yield history, CSI 300 return history |
| Validation test | Martingale test — all assets price to par under Q | Historical backtesting — scenario fan chart vs realised returns |
| ASOP reference | ASOP 56 §3.4 (market-consistent approach) | ASOP 25 §3.3 (credibility, historical estimation) |

**Critical rule:** Q-measure parameters are calibrated to market prices. P-measure parameters are estimated from historical data. The two sets are linked only through the market price of risk (Girsanov kernel). Mixing calibration targets across measures is a critical error.

### 3.2 Credibility Hierarchy (ASOP 25 §3.3)

When multiple data sources are available, the following hierarchy applies:

1. **Market-implied** (highest credibility): Where liquid derivatives markets exist — use implied parameters. Required for Q-measure calibration.
2. **Historical estimation** (credible): Use maximum-likelihood estimation from ≥10 years of daily return history. Required for P-measure ERP and correlation parameters.
3. **Peer model benchmarks** (supplementary): Cross-validate against published actuarial model calibrations for CNY market (e.g., PBOC working papers, published re/insurance group MCEV disclosures).
4. **Expert judgment** (lowest credibility, requires documentation): Applied only where data is sparse (e.g., ERP in low-rate environments). Must be explicitly documented with rationale, supported by sensitivity analysis, and approved by the Assumption Owner.

### 3.3 Parameter Stability Requirement

Per ASOP 56 §3.4 practice note guidance: calibrated parameters should be tested for stability across calibration sub-periods. A parameter is considered stable if it varies by less than ±20% across any rolling 3-year sub-window. If instability is detected, the reason must be documented and the Assumption Owner must decide whether to use:
- A time-averaged parameter (with stability dampening), or
- Regime-conditional parameters (bull/bear or high/low vol regimes).

---

## 4. Data Sources and Quality Requirements

### 4.1 Data Source Registry

| Data Item | Description | Primary Source | Fallback Source | Frequency | Min History Required |
|-----------|-------------|----------------|-----------------|-----------|---------------------|
| CNY government bond yields | Benchmark spot rates (1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 15Y, 20Y, 30Y) | PBOC / Wind Financial Terminal (series: `CGBxY` where x = tenor) | Bloomberg (ticker: `CNXXX Index`) | Daily close | 10 years minimum |
| CNY swaption implied volatility | ATM swaption vol surface (1Y×1Y, 1Y×5Y, 5Y×1Y, 5Y×5Y, 10Y×10Y tenors) | Bloomberg (field: `USSV_CNY` equivalents) | Citigroup / HSBC CNY desk quotes | Weekly | 5 years minimum |
| CSI 300 index level | Daily close; total return index (dividends reinvested) | Wind (ticker: `000300.SH`) | Bloomberg (`SHSZ300 Index`) | Daily close | 15 years minimum |
| CSI 300 implied volatility | ATM 30-day implied vol from 50ETF options (proxy) | Shanghai Stock Exchange (SSE 50ETF options) | Wind option analytics | Daily close | 5 years minimum |
| CSI 300 dividend yield | 12-month trailing dividend yield | CSI Index Company / Wind | Bloomberg | Monthly | 5 years minimum |
| CNY CPI (for inflation overlay) | National CPI index (year-on-year % change) | NBS (National Bureau of Statistics) / Wind | Bloomberg | Monthly | 10 years minimum |
| CNY SHIBOR 1M / 3M / 1Y | Interbank offered rate (proxy for short rate r(0)) | CFETS / Wind (`SHIB1M`, `SHIB3M`, `SHIB1Y`) | Bloomberg | Daily close | 5 years minimum |

### 4.2 Data Acquisition Protocol

Before calibration, the data team must:

1. **Extract** the required series over the specified history window (extend by 1 year as out-of-sample test set).
2. **Validate** the raw data against the quality checks in §4.3.
3. **Document** the extraction date, data version, and source system in `CALIBRATION_CHANGE_LOG.md`.
4. **Store** the cleaned calibration dataset in `.claude-dev/calibration_data/` with filename format `{source}_{series}_{YYYYMMDD}.csv` (version-controlled in git).

### 4.3 Data Quality Assessment

Each data series must pass the following quality checks before use in calibration:

| Check | Rule | Action if Failed |
|-------|------|------------------|
| Missing values | < 2% of observations missing | Interpolate linearly for isolated gaps (≤5 days); flag for manual review if gap > 5 consecutive days |
| Outlier detection | |z-score| > 5 σ flagged as potential data error | Investigate source; exclude if confirmed data error; retain if confirmed genuine market event |
| Level-range check | Yield curve: 0% ≤ r ≤ 10% for CNY (regulatory bounds: floor at 0%, ceiling at 10%) | Flag values outside range; manual sign-off required |
| Monotonicity (yield curve) | Spot curve should be broadly monotone above 3Y tenor | Document inversion periods (e.g., COVID-19, CBIRC policy); do not delete |
| Time alignment | All series must align to same calendar (trading days) | Use last-available-value carry-forward for bank holiday gaps; document in change log |
| Source consistency | Rates from different sources must agree within 5bps for same tenor | Escalate to data governance; use primary source as authoritative |

---

## 5. Hull-White 1-Factor (HW1F) Calibration

### 5.1 Initial Short Rate r(0)

**Definition:** r(0) is the instantaneous short rate at the calibration date. It represents the current level of interest rates.

**Calibration procedure:**
1. Extract SHIBOR 1M and SHIBOR 3M on the calibration date.
2. Take the weighted average: `r(0) = 0.5 × SHIBOR_1M + 0.5 × SHIBOR_3M`.
3. Cross-check against the 1Y PBOC benchmark lending rate.
4. **Regulatory constraint (Note A):** For regulatory reserve calculations, if `r(0) > 3.0%`, truncate to `3.0%` per CBIRC guidelines. Document the override in the change log.

**Current value:** 2.5% (placeholder — to be replaced by market rate at calibration date).

### 5.2 Q-Measure Parameters: a and σ_r (Swaption Calibration)

**Objective:** Minimise the weighted sum of squared pricing errors between model-implied swaption prices and market swaption prices across the ATM swaption grid.

**Loss function:**
```
L(a, σ_r) = Σ_{i,j} w_{ij} × [V_model(a, σ_r, T_i, S_j) − V_market(T_i, S_j)]²
```

Where:
- `T_i` = option expiry tenor ∈ {1Y, 2Y, 3Y, 5Y, 7Y, 10Y}
- `S_j` = swap tenor ∈ {1Y, 2Y, 5Y, 10Y}
- `V_model(a, σ_r, T, S)` = HW1F analytical ATM payer swaption price (Jamshidian decomposition)
- `V_market(T, S)` = market mid ATM payer swaption price (Normal vol × annuity)
- `w_{ij}` = calibration weight (default: equal weight; review if liquidity differs across tenors)

**HW1F analytical swaption price (Jamshidian decomposition):**

For a payer swaption with expiry T on a swap with payment dates T₁, T₂, ..., T_n (T < T₁):

```
V_payer(T, K) = Σ_i c_i × P(0, T_i) × N(h_i + σ_p(T, T_i)) − Σ_i c_i × P(0, T_i) × N(h_i)

Where:
  c_i      = coupon payment at T_i (including notional at T_n)
  K*       = strike rate solving Σ c_i × P*(T, T_i) = 1 (ZCB prices at T under forward measure)
  r*       = unique short rate at T such that P(T, T_i | r*) = K*
  h_i      = [ln(P(0,T_i)/P(0,T) × 1/K*)] / σ_p(T, T_i) − σ_p(T, T_i)/2
  σ_p(T,S) = σ_r × B(T,S) × sqrt[(1−e^{−2aT}) / (2a)]
  B(T,S)   = (1/a) × (1 − e^{−a(S−T)})
```

**Optimization algorithm:** L-BFGS-B with analytical gradient (see `par_model_v2/calibration/calibration_framework.py`).

**Parameter bounds:**
- `a ∈ [0.001, 1.0]` (mean-reversion speed must be positive; cap at 1.0 for numerical stability)
- `σ_r ∈ [0.001, 0.10]` (short rate vol must be positive; cap at 10% p.a. for CNY market)

**Starting values:** `a₀ = 0.10`, `σ_r₀ = 0.012` (current placeholders serve as warm start).

**Convergence criterion:** Loss function value < 1e-8 (equivalent to < 0.01bps average pricing error across the grid). If convergence fails, document and escalate to the Assumption Owner.

**Goodness-of-fit reporting:** The calibration routine must produce a table of model vs market swaption prices for all calibrated tenors, and flag any absolute pricing error > 1bps for review.

### 5.3 P-Measure Parameter: λ_r (Market Price of Interest Rate Risk)

**Definition:** λ_r is the Girsanov kernel that adjusts the Q-measure drift to the P-measure drift:
```
θ_P(t) = θ_Q(t) + σ_r × λ_r
```

**Calibration procedure:**
1. Extract the historical P-measure drift from historical CNY yield curve data:
   - Estimate the average annual change in the 1Y government bond yield over the sample period.
   - This is `μ_P(r)`, the historical drift under P.
2. Compute the Q-measure drift `θ_Q` at the initial curve from the calibrated Q-measure parameters.
3. Solve for λ_r:
   ```
   λ_r = [μ_P(r) − θ_Q] / σ_r
   ```
4. Cross-validate: λ_r should be negative for a normal yield curve (positive risk premium → higher yields under P than Q). A positive λ_r in a low-rate environment with curve flattening should be documented.

**Typical range for CNY market:** λ_r ∈ [−0.5, 0.5] (dimensionless). Values outside this range indicate likely data or estimation error.

**Current value:** 0.0 (placeholder — no P-measure calibration yet performed).

### 5.4 Initial Yield Curve θ(t)

**Purpose:** The time-dependent drift `θ(t)` is not a free parameter — it is determined analytically to ensure the model exactly fits the observed initial yield curve (i.e., the model prices all ZCBs consistently with market prices at t=0).

**Procedure:**
1. Bootstrap the instantaneous forward curve `f(0, t)` from the CNY government bond spot curve.
2. Compute `θ_Q(t)` analytically:
   ```
   θ_Q(t) = ∂f(0,t)/∂t + a × f(0,t) + (σ_r²/2a) × (1 − e^{−2at})
   ```
3. Store the discretised forward curve as a lookup table in the calibration output.

---

## 6. Geometric Brownian Motion (GBM) Equity Calibration

### 6.1 Q-Measure Drift

Under Q, the GBM equity drift is fully determined by the risk-free rate and dividend yield:
```
dS/S = (r(t) − δ) dt + σ_S dW_S^Q(t)
```

No free parameters in the Q-measure drift — only σ_S and δ require calibration. The risk-free rate `r(t)` is the stochastic short rate from the HW1F model.

### 6.2 Equity Volatility σ_S

**Two-source calibration (blended estimate):**

| Source | Weight | Method |
|--------|--------|--------|
| Historical (realised) | 40% | Annualised std dev of daily log-returns of CSI 300 total return index over trailing 5-year window. `σ_hist = std(ln(S_{t}/S_{t-1})) × sqrt(252)` |
| Implied (forward-looking) | 60% | ATM 30-day implied vol from 50ETF options (closest-expiry ATM strike). Extract at calibration date. |

**Blended estimate:**
```
σ_S = 0.40 × σ_hist + 0.60 × σ_implied
```

**Rationale for weighting:** Forward-looking information (implied vol) is a better predictor of near-term risk, which is most relevant for TVOG computation. The 60/40 weighting is subject to Assumption Owner review and may be adjusted based on empirical analysis (Phase 4).

**Current placeholder:** 22% p.a. (approximate CSI 300 long-run historical vol; academic literature consensus for Chinese equity market). This is consistent with the range reported in published MCEV disclosures for CNY equity portfolios (18%–28%).

**Parameter bounds:** `σ_S ∈ [0.05, 0.60]` (5% floor to avoid degenerate paths; 60% cap to prevent extreme scenario generation).

### 6.3 Dividend Yield δ

**Calibration procedure:**
1. Extract the trailing 12-month dividend yield of the CSI 300 index from CSI Index Company or Wind.
2. Apply a 3-year exponentially weighted moving average (λ = 0.5) to smooth recent fluctuations:
   ```
   δ̂ = Σ_{k=0}^{35} λ^k × δ_{t-k} / Σ_{k=0}^{35} λ^k
   ```
3. Review for structural breaks (e.g., regulatory changes to dividend policy).

**Current placeholder:** 2.5% p.a. (consistent with approximate CSI 300 dividend yield as of 2025).

### 6.4 P-Measure Drift: Equity Risk Premium (ERP)

**Definition:** Under P-measure, the equity drift includes the equity risk premium:
```
dS/S = (r(t) + ERP − δ) dt + σ_S dW_S^P(t)
```

**Calibration procedure (historical maximum-likelihood):**
1. Compute annual excess returns of CSI 300 over the CNY risk-free rate (1Y government bond) for each year in the sample.
2. Take the sample mean: `ERP_hist = mean(r_equity − r_f)`.
3. Adjust for survivorship bias using a 0.5%–1.0% downward correction (per Dimson, Marsh, and Staunton, 2024, for emerging market equities).
4. Cross-validate against consensus survey forecasts (Bloomberg ERP survey, if available for CNY).
5. Apply an upper bound of 5.0% for CNY market (consistent with published Chinese insurer MCEV disclosures).

**Typical range:** ERP ∈ [2.5%, 5.0%] for CNY equity market. Current placeholder (4.5%) is at the high end — likely to be revised downward in Phase 4 calibration.

**Sensitivity requirement (SOA ASOP 7):** The TVOG result must be tested with ERP = 0% (risk-neutral as a control), ERP = 2.5%, and ERP = 5.0%. The range of TVOG outcomes across these scenarios must be disclosed.

### 6.5 Rate-Equity Correlation ρ_{r,S}

**Calibration procedure:**
1. Compute monthly log-returns of the CSI 300 index.
2. Compute monthly first differences of the CNY 10Y government bond yield.
3. Pearson correlation over the trailing 10-year window.
4. Typical result for CNY market: ρ ∈ [−0.30, −0.05] (negative correlation — rising rates depress equity in most regimes).

**Cholesky decomposition:** The correlated Brownian increments are constructed using:
```
dW_S = ρ × dW_r + sqrt(1 − ρ²) × dW_S_indep
```

Where `dW_r` and `dW_S_indep` are independent standard Normal increments.

**Current placeholder:** −0.15 (within typical CNY range; to be replaced by data-based estimate in Phase 4).

---

## 7. Scenario Adequacy Requirements (ASOP 56 §3.5)

### 7.1 Minimum Scenario Counts by Use Case

| Use Case | Minimum | Recommended | Convergence Criterion | Notes |
|----------|---------|-------------|----------------------|-------|
| TVOG computation | 500 | 1,000 | TVOG std error < 1% of mean TVOG | Antithetic variates halve the required count |
| ALM projection (P-measure) | 200 | 500 | Mean portfolio value std error < 0.5% | Not tail-sensitive — fewer scenarios sufficient |
| VaR 95.0% | 500 | 1,000 | VaR std error < 5% of mean VaR | Empirical method |
| VaR 99.0% | 1,000 | 5,000 | VaR std error < 5% of mean VaR | Empirical method |
| VaR 99.5% (solvency) | 2,000 | 10,000 | VaR std error < 2% of mean VaR | Regulatory use — tighter tolerance |
| Expected Shortfall 99.0% | 2,000 | 5,000 | ES std error < 5% of mean ES | |
| Stress testing | Deterministic | N/A | N/A | Scenario-by-scenario, not stochastic |
| Convergence testing | 50–5,000 (range) | N/A | Visual fan chart convergence | Phase 3 deliverable |

### 7.2 Martingale Test (Q-Measure Validation)

Before any TVOG computation using Q-measure scenarios, a martingale test must pass:

**Test:** For each asset class, the average discounted asset price at each time horizon must equal the initial price (within sampling error):
```
E_Q[e^{−∫₀ᵀ r(s)ds} × S(T)] = S(0)    for all T ∈ {1, 5, 10, 20} years
```

**Acceptance criterion:** Absolute relative error < 1% at all test horizons (tighter than VaR tolerance because TVOG is a ratio metric).

**Action if test fails:** Do not use scenarios for TVOG. Investigate calibration, re-run simulation with higher scenario count, or escalate to Assumption Owner.

**Implementation:** `par_model_v2/calibration/calibration_framework.py::martingale_test()` (Phase 3 — after ESG `simulate()` is implemented).

### 7.3 Variance Reduction Techniques

The following techniques are available in `esg_process.py` (to be implemented in Phase 3):

| Technique | Applies To | Benefit |
|-----------|-----------|---------|
| Antithetic variates | All Monte Carlo | Halves variance for symmetric payoffs; effectively doubles scenario count |
| Quasi-random (Sobol / Halton) | TVOG | Better convergence rate O(1/N) vs O(1/√N) for smooth payoffs |
| Control variates | Specific | Use ZCB prices (known analytically) as control; reduce TVOG variance |

---

## 8. Integration with Projection Engine

### 8.1 Data Flow

The calibrated ESG parameters feed into the projection engine as follows:

```
Calibration Dataset (§4)
         ↓
  HullWhiteCalibrator         GBMCalibrator
  (par_model_v2/calibration/) (par_model_v2/calibration/)
         ↓                            ↓
  HullWhiteParams             GBMParams
  (par_model_v2/stochastic/)  (par_model_v2/stochastic/)
         ↓                            ↓
         ↓→ HullWhiteRateProcess ←→ GBMEquityProcess ←↓
                    ↓
               ScenarioSet (N paths × T months)
                    ↓
         MonthlyProjectionEngine (per scenario)
              (par_model_v2/projection/)
                    ↓
         RiskMetrics / TVOG (par_model_v2/risk/)
```

### 8.2 Scenario Consumption by Downstream Modules

| Downstream Module | Measure | Scenario Count | Validation Required Before Use |
|------------------|---------|----------------|-------------------------------|
| TVOG computation | Q | ≥ 500 | Martingale test must pass |
| ALM projection | P | ≥ 200 | Fan chart review (manual) |
| VaR/ES (risk_metrics.py) | P | ≥ 2,000 (for 99.5%) | Scenario convergence chart |
| Bonus projection | P | ≥ 500 | Visual reasonableness check |
| Stress testing | Deterministic | N/A | Scenario narrative sign-off |

---

## 9. Governance, Change Control, and Backtesting

### 9.1 Calibration Roles and Responsibilities

| Role | Responsibility |
|------|---------------|
| **Model Developer** | Implement calibration code; run calibration; produce goodness-of-fit report |
| **Assumption Owner** (Chief Actuary or delegate) | Review and sign off calibrated parameters before production use |
| **Independent Validator** (APS X2 peer) | Review calibration methodology and outputs for material model changes |
| **Model Risk Committee** | Annual review of calibration results; approve material assumption changes |

### 9.2 Calibration Frequency and Triggers

**Scheduled calibration:** Annual — to be performed at each financial year-end (31 December). The calibration date is fixed as 31 December to ensure consistency across actuarial reporting cycles.

**Triggered calibration:** Recalibration is required if any of the following conditions are met:
- Interest rate volatility (σ_r) changes by > 25% relative to current calibrated value (e.g., due to PBOC policy shift)
- CSI 300 implied volatility (VIX-equivalent) exceeds 2 standard deviations from its 5-year rolling mean for > 20 consecutive trading days
- CBIRC publishes a material update to interest rate assumption guidelines
- The Model Risk Committee determines that model outputs deviate materially from realised outcomes in backtesting

### 9.3 Calibration Change Log Protocol

Every calibration update must be recorded in `.claude-dev/CALIBRATION_CHANGE_LOG.md` with the following fields:

```markdown
## Calibration Update — {YYYY-MM-DD}

**Reason for Update:** {Scheduled annual / Triggered — specify condition}
**Calibration Date:** {Market data as of date}
**Prepared by:** {Name / System}
**Approved by:** {Assumption Owner name and date}

### Parameter Changes

| Parameter | Old Value | New Value | % Change | Rationale |
|-----------|-----------|-----------|----------|-----------|
| a | 0.10 | 0.09 | −10% | Fitted to updated swaption grid |
| σ_r | 0.012 | 0.011 | −8% | Lower CNY rate vol environment |
| ...

### Goodness-of-Fit Summary

| Swaption (Expiry × Tenor) | Market Vol | Model Vol | Error (bps) |
|--------------------------|------------|-----------|-------------|
| 1Y × 5Y | 45bps | 44.8bps | −0.2bps |
| ...

### Impact Assessment

- TVOG impact: {+/− X% relative to prior calibration}
- VaR 99.5% impact: {+/− X% relative to prior calibration}
- Bonus projection impact: {+/− X% relative to prior calibration}
- Material change (Y/N): {Y if any impact > 5%; triggers APS X2 review if Y}

### Sign-off

- [ ] Assumption Owner: {name} on {date}
- [ ] Independent Validator (if material change): {name} on {date}
```

### 9.4 Backtesting Framework

**Annual backtesting requirement (per ASOP 56 §3.5 and IA TAS M §3.6):**

1. **Rate path backtesting:** Compare the 1-year-ahead distribution of CNY 10Y yields from the P-measure HW1F scenarios (generated at t=0 using prior year's calibration) against realised yields. Assess whether the realised yield falls within the 10th–90th percentile of the simulated distribution. Flag if < 70% of annual backtest observations fall within this band (indicating model is too narrow or too wide).

2. **Equity return backtesting:** Compare the 1-year-ahead distribution of CSI 300 returns from P-measure GBM scenarios against realised annual returns. Same 10th–90th percentile band test.

3. **Martingale backtest (Q-measure):** Verify that the average scenario-discounted asset price equals the initial price within 0.5% tolerance.

4. **Tail sensitivity:** At each annual backtest, record whether the realised loss (ALM portfolio or TVOG) exceeded the model's 99th percentile loss. A VaR breach should occur roughly 1% of years on average. Track the running breach rate; if it exceeds 5% (i.e., losses exceed VaR_99 more than 5% of years), the model is under-estimating tail risk and recalibration is mandatory.

**Backtest report deliverable (Phase 4):** `docs/CALIBRATION_BACKTEST_REPORT_{YYYY}.md` — produced annually and archived.

---

## 10. Implementation Checklist

### Phase 4 Calibration Deliverables

| # | Deliverable | Owner | Due |
|---|------------|-------|-----|
| C1 | Acquire calibration dataset per §4 data source table | Model Developer | Phase 4 start |
| C2 | Run data quality checks (§4.3); document results in change log | Model Developer | Phase 4 start |
| C3 | Calibrate HW1F (a, σ_r) to swaption grid; produce goodness-of-fit table | Model Developer | Phase 4, task 3 |
| C4 | Calibrate r(0) from SHIBOR data | Model Developer | Phase 4, task 3 |
| C5 | Estimate λ_r from historical yield data | Model Developer | Phase 4, task 3 |
| C6 | Calibrate GBM σ_S (blended implied/historical) | Model Developer | Phase 4, task 3 |
| C7 | Estimate ERP from historical excess returns | Model Developer | Phase 4, task 3 |
| C8 | Estimate ρ_{r,S} from joint return history | Model Developer | Phase 4, task 3 |
| C9 | Bootstrap initial yield curve θ(t) | Model Developer | Phase 4, task 3 |
| C10 | Run martingale test on Q-measure scenarios | Model Developer | Phase 4, task 4 |
| C11 | Run scenario convergence test (Phase 3 prerequisite) | Model Developer | Phase 3 |
| C12 | Produce backtest report (initial) | Model Developer | Phase 4, task 6 |
| C13 | Assumption Owner sign-off on all calibrated parameters | Assumption Owner | Phase 4 completion |
| C14 | APS X2 peer review of calibration methodology | Independent Validator | Phase 5 |
| C15 | Archive calibration dataset and change log in git | Model Developer | Phase 4 completion |

---

## 11. Document History

| Version | Date | Author | Change Summary |
|---------|------|--------|----------------|
| 1.0 | 2026-05-18 | Claude Actuarial Agent (Cycle 10) | Initial version — Phase 2, Task 3. Standalone calibration methodology document. Supersedes ESG_PROCESS_DOCUMENTATION.md §5. |

---

*This document is a living specification. It will be updated in Phase 4 when live calibration is performed. All placeholder values in §2.2 will be replaced with market-calibrated values at that stage.*

*Prepared under SOA ASOP 56 §3.4, ASOP 25 §3.3. Review by Assumption Owner required before production use.*
