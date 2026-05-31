# Economic Scenario Generator (ESG) — Stochastic Process Documentation

**Model:** PAR Fund Stochastic ALM & TVOG (Python)  
**Document Version:** 1.0  
**Date:** 2026-05-18  
**Prepared by:** Claude Actuarial Agent (Automated Cycle 8 — Phase 2, Task 1)  
**Standards Reference:** SOA ASOP 56 §3.1.3, ASOP 25, ASOP 7; IA TAS M §3.5; ERM Framework  
**Status:** Approved for development use — not yet peer-reviewed (APS X2 peer review pending Phase 5)

---

## 1. Purpose and Scope

This document satisfies the stochastic process documentation requirement of **SOA ASOP 56 §3.1.3**:

> *"The actuary should document the model in sufficient detail that another actuary qualified in the same practice area could evaluate the appropriateness of the model."*

For stochastic models, this requires explicit documentation of:
- The mathematical process assumed for each stochastic risk factor
- The distinction between real-world (P-measure) and risk-neutral (Q-measure) formulations
- All parameters and their calibration basis
- Limitations and known deficiencies

**Risk factors covered by this ESG:**

| Risk Factor | Process Type | Measure | Status |
|-------------|-------------|---------|--------|
| CNY nominal interest rates | Hull-White 1-factor | Both P and Q | Stub — not yet implemented |
| CNY equity returns (CSI 300 proxy) | Geometric Brownian Motion | Both P and Q | Stub — not yet implemented |
| Credit spreads | Deterministic add-on | N/A | Not in scope for Phase 2 |
| Inflation | CPI-linked overlay | P only | Not in scope for Phase 2 |

**Out of scope for Phase 2:** Credit spread stochastic modelling, foreign exchange, real estate.

---

## 2. Regulatory and Standards Context

### 2.1 Applicable Standards

| Standard | Requirement | How Addressed |
|----------|------------|---------------|
| SOA ASOP 56 §3.1.3 | Document stochastic process type and parameters | This document |
| SOA ASOP 56 §3.4 | Document parameter calibration methodology | Section 5 of this document |
| SOA ASOP 25 | Credibility of assumption bases | Section 5.3 — calibration data sources |
| SOA ASOP 7 | Cash flow analysis under stochastic scenarios | Integration with projection engine (Phase 4) |
| IA TAS M §3.5 | Assumption documentation and sign-off | Section 5 (calibration basis); sign-off pending |
| VM-20 / VM-21 | Scenario generation for stochastic reserves | Informational reference; not directly applicable (CN jurisdiction) |
| CBIRC Guidelines | Interest rate assumptions ≤ 3.0% for regulatory reserves | Section 3.1 — Note B |

### 2.2 Measure Distinction — P vs. Q (ASOP 56 Deviation D-04 Remediation)

**This is a critical distinction identified in the Phase 1 SOA Standards Deviation Report as Critical Deviation D-04.**

| Concept | Real-World (P-Measure) | Risk-Neutral (Q-Measure) |
|---------|----------------------|------------------------|
| Purpose | ALM simulation, ERM, VaR/ES, stress testing, bonus projection | TVOG (Time Value of Options and Guarantees), market-consistent embedded value (MCEV) |
| Drift | Calibrated to historical returns / market consensus | Risk-free rate only (no excess return) |
| Discount rate | Stochastic risk-free path + credit spread | Stochastic risk-free path (same) |
| Equity drift | μ_equity = historical excess return + r_f | μ_equity = r_f (risk-neutral drift) |
| Interest rate drift | Mean-reversion to long-run economic rate | Mean-reversion to risk-neutral forward curve |
| Martingale test | Not applicable | All assets must price to par under Q (critical validation) |
| SOA requirement | ASOP 7 (cash flow testing) | VM-20 §7, MCEV principles |

**Implementation rule:** Every simulation function must accept a `measure: Literal["P", "Q"]` parameter and adjust drift accordingly. Mixing measures is a critical error.

---

## 3. Interest Rate Process — Hull-White 1-Factor (HW1F)

### 3.1 Mathematical Specification

The short rate r(t) follows the Hull-White 1-factor (extended Vasicek) process:

```
dr(t) = [θ(t) − a·r(t)] dt + σ_r · dW_r(t)
```

Where:
- `r(t)` — instantaneous short rate at time t
- `θ(t)` — time-dependent drift function, calibrated to fit the initial yield curve
- `a` — mean-reversion speed (> 0); controls how quickly rates return to the long-run level
- `σ_r` — short rate volatility (annual basis)
- `dW_r(t)` — standard Wiener process increment under the appropriate measure

**Measure adjustment:**

Under **Q-measure** (risk-neutral):
```
θ_Q(t) = ∂f(0,t)/∂t + a·f(0,t) + (σ_r²/2a)·(1 − e^{−2at})
```
where `f(0,t)` is the initial instantaneous forward rate curve.

Under **P-measure** (real-world), add a market price of risk λ_r:
```
θ_P(t) = θ_Q(t) + σ_r · λ_r
```

**Discretisation (monthly timestep, Δt = 1/12):**
```
r(t+Δt) = r(t)·e^{−a·Δt} + (θ/a)·(1 − e^{−a·Δt}) + σ_r·√((1−e^{−2aΔt})/(2a)) · Z_r
```
where `Z_r ~ N(0,1)` i.i.d.

**Zero-coupon bond price formula (closed-form):**
```
P(t, T) = A(t,T) · exp(−B(t,T) · r(t))

B(t,T) = (1/a) · (1 − e^{−a(T−t)})

ln A(t,T) = ln(P(0,T)/P(0,t)) + B(t,T)·f(0,t) − (σ_r²/(4a))·B(t,T)²·(1 − e^{−2at})
```

### 3.2 Parameterisation

| Parameter | Symbol | Indicative Value | Calibration Basis | Status |
|-----------|--------|-----------------|-------------------|--------|
| Mean-reversion speed | a | 0.10 | Typical CNY market; to be calibrated to swaption vols | **Placeholder** |
| Short rate volatility | σ_r | 0.012 (1.2% p.a.) | Historical CNY 1Y rate vol; to be calibrated | **Placeholder** |
| Initial short rate | r(0) | 0.020 (2.0%) | CNY 1Y benchmark rate (approx. May 2026) | **Indicative** |
| Long-run rate (P) | θ_∞ | 0.025 (2.5%) | Consensus CNY 10Y rate expectation | **Placeholder** |
| Market price of risk | λ_r | −0.15 | Calibrated to match P→Q spread; provisional | **Placeholder** |

**Note A:** Placeholder values are illustrative. Production calibration (Phase 4) will use CNY government bond yield curves and swaption implied volatilities.

**Note B (CBIRC Compliance):** The regulatory cap on discount rates for reserve calculations is **3.0%** per CBIRC guidance. When using simulated short rates for regulatory reserve computation, paths must be floored at a compliance minimum or the discount rate applied to liability valuation must use the regulatory rate, not the simulated rate. This distinction must be maintained in all liability projection code.

**Phase 7 update:** `HullWhiteRateProcess` now accepts an explicit
`RiskFreeCurve` input for Q-measure initial-curve fitting and zero-coupon
pricing. Negative zero rates are supported for low-rate market examples, and
the default v1 wide-view output still caps `zcb_1y` and `zcb_10y` at par unless
`cap_zcb_at_par=False` is selected for diagnostics. See
`docs/ESG_HULL_WHITE_CURVE_INPUT_DESIGN.md`.

**Phase 7 starter curves:** USD, EUR, HKD, CNY, and JPY illustrative
continuously compounded zero curves are available in
`par_model_v2/stochastic/fixtures/risk_free_curves.json` through
`starter_risk_free_curve(...)` and `default_phase7_starter_curves(...)`. These
fixtures are for development and validation examples only; they remain
placeholder inputs pending governed market-data calibration. See
`docs/ESG_STARTER_CURVE_FIXTURES.md`.

**Phase 7 yield-curve validation:** `YieldCurveValidator` now produces
JSON-ready reports for curve discount factors, adjacent-tenor forwards,
parallel up/down rate stresses, generated path discount factors, and optional
negative-rate evidence using uncapped above-par discount factors. See
`docs/ESG_YIELD_CURVE_VALIDATION.md`.

**Phase 7 Q-measure martingale evidence:** `QMeasureMartingaleValidator`
checks that discounted Q-measure `zcb_1y` and `zcb_10y` outputs reconcile to
the initial risk-free curve within a documented development tolerance. See
`docs/ESG_Q_MEASURE_MARTINGALE_EVIDENCE.md`.

### 3.2b G2++ Two-Factor Prototype

Phase 7 Task 2 adds `G2PlusRateProcess` as an educational two-factor Gaussian
rate prototype:

```
r(t) = phi(t) + x(t) + y(t)
dx(t) = -a*x(t) dt + sigma*dW_x(t)
dy(t) = -b*y(t) dt + eta*dW_y(t)
corr(dW_x, dW_y) = rho
```

Under Q-measure, `phi(t)` is fitted to the supplied `RiskFreeCurve`
instantaneous forward curve. Under P-measure, the prototype uses an
educational long-run-rate target plus placeholder market-price-of-risk terms.
The output keeps the v1-compatible `r_short`, `zcb_1y`, `zcb_10y`, and
`measure` fields while adding diagnostic `g2pp_x` and `g2pp_y` factor columns.

See `docs/ESG_G2PP_RATE_PROCESS_DESIGN.md` for the implemented contract,
validation scope, and limitations. The G2++ process is not yet integrated into
`ScenarioSet.generate(...)` by default and is not calibrated to a swaption
surface.

### 3.3 Limitations

- **1-factor model:** Cannot independently control the short-end and long-end volatility. If spread dynamics between short and long rates are material (e.g., yield curve twists), a 2-factor model (Hull-White 2F or G2++) should be considered.
- **Gaussian short rates:** HW1F allows negative rates, which is economically plausible in some markets but requires careful treatment in CNY context (rates have rarely gone negative).
- **Flat initial curve fallback:** If market yield curve data is unavailable, the model falls back to a flat initial curve at r(0). This degrades Q-measure calibration quality.

---

## 4. Equity Process — Geometric Brownian Motion (GBM)

### 4.1 Mathematical Specification

The equity index level S(t) follows GBM:

```
dS(t) = μ_S(t) · S(t) dt + σ_S · S(t) · dW_S(t)
```

Where:
- `S(t)` — equity index level at time t (CSI 300 proxy)
- `μ_S(t)` — drift parameter (measure-dependent; see below)
- `σ_S` — equity return volatility (annual)
- `dW_S(t)` — standard Wiener process increment, correlated with interest rate Wiener process

**Measure-dependent drift:**

Under **Q-measure** (risk-neutral):
```
μ_S^Q(t) = r(t) − q_S
```
where `r(t)` is the stochastic short rate and `q_S` is the dividend yield.

Under **P-measure** (real-world):
```
μ_S^P = r(t) + ERP − q_S
```
where ERP is the equity risk premium (historical excess return above risk-free).

**Log-normal discretisation (monthly timestep):**
```
S(t+Δt) = S(t) · exp[(μ_S − σ_S²/2)·Δt + σ_S·√Δt · Z_S]
```
where `Z_S ~ N(0,1)` correlated with `Z_r` via correlation `ρ_{r,S}`.

**Phase 8 regional equity factors:** Starter GBM factor fixtures now cover US,
Europe, Hong Kong / China, Japan, and Asia ex-Japan. The v1 scenario schema
still exposes one `equity_index` and `equity_return_1m` pair at a time, but
`ScenarioSet.generate(..., equity_factor=...)` records the selected regional
equity source and market-qualified GBM parameters in the `ParameterSnapshot`.
See `docs/ESG_REGIONAL_EQUITY_FACTORS.md`.

### 4.2 Correlated Brownian Motions (Cholesky Decomposition)

The interest rate and equity Wiener processes are correlated. Simulate via:

```python
# Cholesky factorisation of correlation matrix
# [dW_r, dW_S] ~ N(0, Σ), Σ = [[1, ρ], [ρ, 1]]
Z1 = N(0,1)                     # independent
Z2 = ρ·Z1 + √(1−ρ²)·N(0,1)    # correlated
dW_r = Z1
dW_S = Z2
```

### 4.3 Parameterisation

| Parameter | Symbol | Indicative Value | Calibration Basis | Status |
|-----------|--------|-----------------|-------------------|--------|
| Equity volatility | σ_S | 0.22 (22% p.a.) | Historical CSI 300 30-day realised vol | **Placeholder** |
| Dividend yield | q_S | 0.025 (2.5%) | CSI 300 trailing dividend yield | **Indicative** |
| Equity risk premium (P) | ERP | 0.045 (4.5%) | Long-run historical CNY equity ERP estimate | **Placeholder** |
| Rate-equity correlation | ρ_{r,S} | −0.15 | Historically observed negative correlation (CNY) | **Placeholder** |
| Initial index level | S(0) | 100 (normalised) | Normalised; relative returns only | **Fixed** |

**Note C (ASOP 56 §3.4 compliance):** The equity risk premium of 4.5% is a placeholder derived from academic literature for emerging markets. Production calibration will use bootstrapped historical CNY equity returns (2000–2025) adjusted for survivorship bias, and cross-validated against current implied risk premia from options markets.

**Note D:** For TVOG computation (Phase 4), only the Q-measure process is used. The ERP is excluded from TVOG scenarios. Mixing ERP into Q-measure paths is a critical error that overstates embedded value.

### 4.4 Limitations

- **Constant volatility:** GBM assumes constant σ_S. In practice, equity volatility is stochastic and exhibits mean-reversion (volatility clustering). A Heston stochastic volatility model may be warranted if PAR bonus guarantees are materially sensitive to vol-of-vol. This is flagged for Phase 5 review.
- **No jump component:** Tail events (crashes) are underrepresented under GBM. For ERM stress testing, discrete jump scenarios should supplement the GBM distribution.
- **Lognormal asset returns:** The model assumes log-normally distributed equity returns. Fat tails (excess kurtosis) are not captured.

---

## 5. Calibration Methodology (ASOP 56 §3.4 / ASOP 25)

### 5.1 Calibration Philosophy

All parameters must be calibrated to observable market data or credible historical data before production use. The following hierarchy applies (per ASOP 25):

1. **Market-implied:** Where liquid derivatives markets exist (e.g., swaptions for σ_r, equity options for σ_S), use implied parameters for Q-measure calibration.
2. **Historical estimation:** For P-measure parameters (ERP, λ_r), use maximum-likelihood estimation from historical return series.
3. **Expert judgment (with documentation):** Where data is sparse or unreliable, expert judgment may be applied. This must be explicitly documented with rationale and sensitivity tested.

### 5.2 Data Sources (Target — Phase 4 Calibration)

| Parameter | Data Source | Frequency | Min History |
|-----------|-------------|-----------|-------------|
| CNY yield curve | PBOC / Wind / Bloomberg CNY government bond benchmark rates | Daily | 10 years |
| Swaption implied vol | Bloomberg CNY swaption vol cube | Weekly | 5 years |
| CSI 300 historical returns | Wind / CSI (China Securities Index) | Daily | 15 years |
| CSI 300 implied vol (50ETF options) | Shanghai Stock Exchange | Daily | 5 years |
| Dividend yield | CSI Index Co. / Bloomberg | Monthly | 5 years |
| CNY CPI | NBS (National Bureau of Statistics) | Monthly | 10 years |

### 5.3 Calibration Procedures (Planned — Phase 4)

**Interest rates (Hull-White parameters a, σ_r):**
```
Objective: minimise sum of squared errors between model-implied swaption prices and market swaption prices

min_{a, σ_r} Σ_i (V_model(a, σ_r, T_i, K_i) − V_market(T_i, K_i))²
```

**Equity parameters (σ_S):**
```
Historical: σ_S = annualised std dev of daily log-returns over rolling 252-day window
Implied:    σ_S = VIX equivalent from 50ETF ATM option implied vol
Production: weighted average (60% implied / 40% historical) — to be confirmed by assumption owner
```

**Market price of risk (λ_r):**
```
Estimated from P→Q Girsanov transformation by matching:
  E_P[r(T)] = E_Q[r(T)] + λ_r · σ_r · B(0,T)
using observed forward rates (Q) and consensus rate forecasts (P)
```

### 5.4 Calibration Governance

Per IA TAS M §3.5 and the proposed governance structure (docs/IA_GOVERNANCE_REQUIREMENTS.md):

- Calibration must be approved by the **Assumption Owner** before use in production
- Calibration review frequency: **annual** (or triggered by material market movements > 2 standard deviations)
- Calibration change log must be maintained in `.claude-dev/CALIBRATION_CHANGE_LOG.md` (to be created in Phase 4)
- Back-testing of calibrated parameters against out-of-sample returns required annually (Phase 4 deliverable)

---

## 6. Scenario Generation Specification

### 6.1 Scenario Count Requirements

Per SOA ASOP 56 §3.5 and Practice Note guidance:

| Use Case | Minimum Scenarios | Recommended | Convergence Criterion |
|----------|-------------------|-------------|----------------------|
| TVOG computation | 500 | 1,000 | TVOG std error < 1% of mean TVOG |
| VaR 99.5% | 2,000 | 5,000 | VaR std error < 5% of mean VaR |
| Expected Shortfall 99% | 2,000 | 5,000 | ES std error < 5% of mean ES |
| Stress testing | Deterministic | N/A | N/A (deterministic scenarios) |
| Convergence testing | 50–5,000 (range) | N/A | Produce convergence chart |

**Phase 3 deliverable:** `scripts/scenario_convergence_test.py` — convergence chart as function of N (50, 100, 250, 500, 1,000, 2,000 scenarios). Required before production TVOG runs.

### 6.2 Random Number Generation

- **Library:** `numpy.random.default_rng(seed)` — PCG64 algorithm (cryptographically strong, reproducible)
- **Antithetic variates:** Enabled by default for variance reduction. For each seed-derived draw Z, include −Z in the scenario set.
- **Seed management:** Each scenario batch must be seeded with a documented seed value stored in the scenario metadata. Seed = 42 for development/testing; production seed generated from run timestamp and stored in scenario file header.

### 6.3 Output Format

Each scenario run produces a `pd.DataFrame` with:

| Column | Description |
|--------|-------------|
| `scenario_id` | Integer 1..N |
| `month` | Month index 0..T |
| `r_short` | Simulated short rate |
| `zcb_1y` | 1-year zero-coupon bond rate (derived from short rate) |
| `zcb_10y` | 10-year zero-coupon bond rate |
| `equity_index` | Equity index level (S(t)/S(0)) |
| `equity_return_1m` | Monthly equity return |
| `measure` | "P" or "Q" (must be explicit in every row) |

---

## 7. Integration with Projection Engine

### 7.1 Consumption by Monthly Projection Engine

The `MonthlyProjectionEngine` (par_model_v2/projection/monthly_projection.py) currently accepts a single deterministic `discount_rate_annual` parameter. Integration with stochastic scenarios will require:

1. **Scenario-conditioned projection:** Accept a single scenario path (DataFrame of monthly r(t), S(t)) as input
2. **Vectorised batch runner:** Run projection for all N scenarios via the fixed `DistributedExecutor` (Phase 3)
3. **Output aggregation:** Collect NPV, TVOG, asset share at maturity across N scenarios for statistical analysis

**Phase 4 integration point:**
```python
# Planned API (not yet implemented)
from par_model_v2.stochastic.esg_process import ScenarioSet
from par_model_v2.projection.monthly_projection import run_full_projection

scenarios = ScenarioSet.generate(n=1000, T_months=240, measure="Q", seed=42)
results = [run_full_projection(product, scenarios.path(i)) for i in range(1000)]
tvog = np.mean([r.pv_guarantees for r in results])
```

### 7.2 TVOG Computation Formula

```
TVOG = E_Q[PV of guaranteed benefit cashflows] − PV of guaranteed cashflows under risk-free scenario

TVOG = (1/N) · Σ_{i=1}^{N} PV_Q(scenario_i) − PV_det(r_f flat)
```

Per ASOP 7 and TAS M §3.1 fitness-for-purpose requirement — TVOG is the **primary output** of this model.

---

## 8. Sensitivity Analysis Requirements (ASOP 56 §3.5)

The following sensitivities must be produced when the stochastic module is operational (Phase 3/4):

| Sensitivity | Shock | Expected Direction | Priority |
|-------------|-------|-------------------|----------|
| TVOG to σ_r | ±25% | TVOG increases with higher σ_r | High |
| TVOG to σ_S | ±25% | TVOG increases with higher σ_S | High |
| TVOG to correlation ρ_{r,S} | ±0.20 | Ambiguous (model-specific) | Medium |
| TVOG to mean-reversion a | ±50% | Increases with lower a (slower mean-reversion) | Medium |
| TVOG to scenario count N | 100, 500, 1000, 2000 | Should converge — convergence chart | High |
| VaR 99.5% to ERP | ±100bps | VaR increases with lower ERP | High |

---

## 9. Known Limitations and Model Risk Disclosures

Per SOA ASOP 56 §3.6 and IA TAS M §3.7 (disclosure requirements):

| # | Limitation | Risk Level | Mitigation |
|---|-----------|-----------|------------|
| L1 | GBM does not capture equity volatility clustering or fat tails | 🟠 High | Supplement with deterministic stress scenarios for ERM |
| L2 | HW1F cannot independently control short/long rate vol | 🟡 Medium | Flag if spread dynamics are material; consider HW2F in Phase 5 |
| L3 | Constant correlation ρ_{r,S} — in reality time-varying | 🟡 Medium | Sensitivity test across ρ range; document |
| L4 | No credit spread stochastic component | 🟠 High | Credit spread deterministic add-on is a known approximation |
| L5 | Moody's ESG calibration parameters unavailable | 🔴 Critical | Phase 2 internal ESG (this module) removes this dependency for testing |
| L6 | Placeholder parameters — not yet market-calibrated | 🔴 Critical | Production use prohibited until Phase 4 calibration complete |
| L7 | Dynamic lapse not modelled (lapse independent of rates) | 🔴 Critical | Understates TVOG by est. 15–30%; Phase 2 priority |

**⚠️ Production Use Restriction:** This ESG module uses placeholder parameters (Section 3.2, 4.3). It must not be used for regulatory reporting, pricing decisions, or external disclosure until Phase 4 calibration is complete and signed off by the Assumption Owner per docs/IA_GOVERNANCE_REQUIREMENTS.md.

---

## 10. Document Revision History

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-05-18 | Claude Actuarial Agent | Initial document — Phase 2, Task 1 |
| — | TBD | Assumption Owner | Phase 4 calibration review and sign-off |
| — | TBD | Independent Validator | APS X2 peer review — Phase 5 |

---

*End of Document — ESG_PROCESS_DOCUMENTATION.md v1.0*
