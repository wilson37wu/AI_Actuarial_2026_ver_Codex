# Industry Benchmark Review — PAR Stochastic ALM / TVOG Model

**Document ID:** `INDUSTRY-BENCHMARK-REVIEW-2026`
**Date:** 2026-06-23
**Subject model:** `par_model_v2` v1.0.0-dev (PAR Endowment Stochastic ALM & TVOG Model)
**Benchmark targets:** FIS / RNA **Prophet** (incl. ALS asset–liability module), Moody's **AXIS**
**Status of subject model:** Development-grade; *not cleared for production, regulatory, or external actuarial use* (10 open production gates)

---

## 1. Executive summary

`par_model_v2` is a ~83k-LOC Python package (plus ~41k LOC across 164 test files) implementing a
**monthly, seriatim, nested-stochastic ALM & TVOG engine for Hong Kong / China participating (par)
endowments**, wrapped in an unusually complete governance/validation scaffold and an offline HTML GUI.

**Verdict.** On *methodology and numerics* the model is at or above typical commercial practice in
several areas (copula tail-aggregation, MLMC/LSMC TVOG, P/Q measure discipline). On *coverage,
calibration to live data, financial reporting, scale, and independent sign-off* it sits at roughly
**development-grade (≈2/5 maturity)** relative to a production Prophet/AXIS deployment. It is best
described as a **credible internal-model prototype with production-grade *bones*** — not a production
platform.

The gap to "industry standard" is concentrated in five places, in priority order:

1. **No live market calibration** — parameters are placeholders, data are synthetic fixtures (MR-001).
2. **Assets are decoupled from the ESG** — asset returns / reinvestment do not follow the simulated
   scenario paths; only liability discounting does.
3. **One product line and no statutory / IFRS-17 / SII balance sheet** — the output is economic
   (TVOG, VaR/TVaR), not the reserves, capital and financial statements an insurer files.
4. **Validation chain incomplete and no human independent review** — Layers 3–5 largely `NOT_RUN`;
   gates G-08/G-09 open.
5. **Scale / performance unproven** — pure-Python nested stochastic on a real in-force is likely
   infeasible without the (fit-sample-limited) proxy path.

---

## 2. Scope of the assessment

The review covers the five subsystems that define a stochastic life model:

| Subsystem | Key modules reviewed |
|---|---|
| Economic Scenario Generator (ESG) | `stochastic/esg_process.py`, `g2pp*.py`, `credit_spread.py`, `mortality_trend.py`, `lapse_behaviour.py`, `esg_adapter.py` |
| Liability projection & ALM | `projection/monthly_projection.py`, `hk_participating.py`, `dynamic_alm.py`, `fixed_income.py`, `derivatives.py`, `private_assets.py` |
| TVOG / capital | `projection/tvog.py`, `nested_stochastic_tvog.py`, `mlmc_inner_estimator.py`, `risk/risk_metrics.py`, `stress_testing.py` |
| Risk aggregation / dependence | `projection/*copula*.py`, `*vine*.py`, `tail_dependence*.py`, `multi_driver_capital_{2..7}d*.py` |
| Calibration, validation, governance | `calibration/*`, `validation/*`, `governance/*`, `tests/` (164 files), `docs/` |

It is a desk review of source, tests and documentation, not an independent re-run or numerical
re-validation.

---

## 3. Capability scorecard

Legend: ✅ comparable to commercial standard · 🟡 partial / prototype · ❌ absent.

| Capability | This model | Prophet / ALS / AXIS | Assessment |
|---|---|---|---|
| Projection granularity | Monthly, seriatim, guaranteed/non-guaranteed split (ASOP 56) | Monthly/configurable, seriatim + model-point compression | ✅ design; 🟡 no compression |
| Product coverage | 2 products: HK cash-dividend & reversionary-bonus endowment; single currency | Hundreds of templates: WL, term, UL/VUL, annuities, riders, group, health; multi-currency | ❌ **largest gap** |
| ESG drivers | HW1F + G2++ rates, GBM/Merton equity, CIR++ credit, OU lapse & mortality, lognormal FX (6–7 drivers) | Full Moody's/B&H-class ESG: 2-factor+ rates, stochastic vol, inflation/real, regime/jumps, many economies | 🟡 classic models, single-vol, no inflation/regime |
| Real-world / risk-neutral + martingale | Explicit P/Q enum, runtime measure guard, ZCB-martingale validator, P-measure backtest | Standard; validated economy libraries | ✅ design; 🟡 Q equity/FX evidence incomplete |
| TVOG | Nested stochastic + LSMC proxy + **MLMC inner estimator** | Nested stochastic, LSMC / replicating portfolios | ✅ method (MLMC ahead of typical default) |
| Dynamic policyholder behaviour | 3-component dynamic lapse (rate-driven + shock), calibrated to synthetic data | Dynamic lapse / annuitisation / premium libraries | ✅ lapse; 🟡 narrow |
| Management actions | Coverage-ratio bonus-cut rule (pathwise + inner-path) | Full rule engines: crediting, bonus, rebalancing, hedging | 🟡 single deterministic rule |
| Asset modelling / ALM | Fixed income, swaps/forwards, private credit/equity/infra; **flat/static yields** | ALS/AXIS: full asset library, dynamic rebalancing, stochastic reinvestment on ESG curves, hedging | 🟡 assets decoupled from ESG |
| Capital aggregation | VaR/TVaR @95/99/99.5; t / skew-t / grouped-t / **vine** copulas; 2D→7D; tail-dependence calibration | Correlation-matrix or copula aggregation; internal-model SCR | ✅ **copula suite exceeds most vendor defaults** |
| Variance reduction | Antithetics, control variates, scrambled Sobol QMC, stratified tail, CRN | Generally CRN + some QMC | ✅ broader (currently "report-not-apply") |
| Calibration to live instruments | HW1F→swaption (L-BFGS-B), CIR++→OAS (OLS); equity/FX placeholders; **synthetic fixtures** | Live swaption/cap/equity-option surfaces; vendor ESG calibration | ❌ **critical (MR-001)** |
| Solvency regime output | CBIRC C-ROSS stress library; SII references | SII SCR/MCR, ICS, HK RBC, C-ROSS, US VM-20/21; statutory & IFRS-17 | ❌ no statutory/IFRS-17 financials |
| Performance / scale | Python/numpy; chunked + distributed-executor prototype | Compiled/grid/cloud; millions of policies × thousands of scenarios overnight | ❌ orders of magnitude |
| Governance / model risk | Immutable audit trail, sign-off workflow, limitation cards, IA TAS-M/ASOP/APS-X2 mapping | Vendor change control + firm MRM (SR 11-7 / TAS) | ✅ scaffold genuinely strong |
| Validation depth | Layers 1–2 strong; Layers 3–5 largely `NOT_RUN`; no human independent review | Full independent validation, benchmarking, attribution | 🟡 chain incomplete |
| Testing | 164 files, ~1,600 tests, integration + regression | Vendor QA + client UAT | ✅ strong for the size |

---

## 4. Where the model meets or beats industry standard

- **Copula / tail-dependence aggregation.** The progression t → skew-t → grouped-t → C-vine, with
  empirical upper-tail (λ_U) calibration and bootstrap confidence intervals, is **more sophisticated
  than the single correlation-matrix aggregation most insurers run in production**. Solvency II
  Art. 234 rank-invariance is explicitly governed (`skew_t_copula_aggregation.py`).
- **TVOG numerics.** Nested stochastic *plus* an MLMC inner estimator (`mlmc_inner_estimator.py`) and
  an LSMC proxy — MLMC is leading-edge and uncommon in production vendor stacks.
- **Measure discipline.** A runtime P/Q guard with a discounted-ZCB martingale validator
  (`esg_process.py`) is better hygiene than many production decks.
- **Governance-as-code.** Append-only SHA-256 audit trail, limitation cards, and a model-risk register
  mapped to IA TAS-M / ASOP / APS X2 — the artifact set a reviewer wants and bespoke models usually lack.
- **Reproducibility.** `SeedSequence`-spawned RNG, byte-identical build checks, 38 documented dev cycles.

These are genuine differentiators worth preserving and pushing.

---

## 5. The gaps that matter most

Ranked by impact on production credibility.

1. **No live calibration / real market data (MR-001).** TVOG, SCR and dynamic lapse all rest on
   placeholder parameters and synthetic fixtures (`calibration/market_data_source.py:21`). This alone
   precludes regulatory/financial use regardless of model elegance. *See `DEEP_DIVE_ESG_CALIBRATION.md`.*
2. **Assets decoupled from the ESG.** Asset-share growth uses a flat `r_proxy`
   (`monthly_projection.py:234-277`); `project_asset_cashflows` uses static yields
   (`monthly_projection.py:382-468`); `DynamicALMEngine.step/run` apply a single static `annual_returns`
   dict each period (`dynamic_alm.py:300-360`). Only liability discounting follows the scenario path.
   Real ALM requires assets and liabilities driven by the *same* paths. *See `DESIGN_ASSET_ESG_COUPLING.md`.*
3. **One product line, no statutory / IFRS-17 / SII balance sheet.** Output is economic (TVOG, VaR/TVaR),
   not reserves, CSM/risk-adjustment, or SCR/MCR financial statements.
4. **Validation chain unfinished, no human independent review.** Layers 3–5 `NOT_RUN`; G-08 (qualified
   independent reviewer) and G-09 (real-data backtest) open. Governance *scaffold* ≠ governance *evidence*.
5. **Performance/scale unproven.** Pure-Python nested stochastic on 100k+ policies × 1–2k outer × inner
   paths is likely infeasible without the proxy path — and proxies are validated only on fit-sample support.
6. **ESG realism gaps.** No stochastic volatility, inflation/real rates, regime switching; ATM-only
   vol surfaces; no cohort/Lee-Carter mortality.

---

## 6. Recommended roadmap

Aligned with the project's own `POST_V1_STOCHASTIC_MODEL_EXPANSION_PLAN.md`.

**Tier 1 — unblock credibility**
- Wire in live market data + calibration (close MR-001). Highest leverage. → `DEEP_DIVE_ESG_CALIBRATION.md`
- Couple assets to ESG paths (reinvestment, coupons, returns as functions of simulated curves/equity).
  → `DESIGN_ASSET_ESG_COUPLING.md`
- Complete validation Layers 3–5: convergence study (CBIRC needs ≥2,000 scenarios; currently ~1,000),
  sensitivity/attribution, real-data out-of-sample backtest (Kupiec/Christoffersen); obtain human
  independent review (G-08).

**Tier 2 — close the coverage gap**
- Add statutory + IFRS 17 + SII/ICS/HK-RBC reporting layers (CSM roll-forward, risk adjustment,
  SCR/MCR balance sheet) on top of the projection.
- Broaden products: whole-life par and a unit-linked / VA line with guarantees (to exercise the TVOG
  machinery the architecture was built for).
- Richer management-action engine: crediting strategy, asset rebalancing, hedging.

**Tier 3 — ESG / numerical uplift**
- Stochastic volatility (Heston/SABR-style) and 2-factor + inflation/real-rate modelling for long-dated
  guarantees; optional regime switching.
- Promote MLMC and the proxy/LSMC path from "report-not-apply" to a *governed production estimator* with
  formal aggregation-error decomposition. Smile/skew calibration rather than ATM-only.

**Tier 4 — engineering / scale**
- Benchmark and harden the distributed executor; vectorise / Numba / GPU the inner loop; add model-point
  compression. Lock a golden regression suite with reference numbers and property-based invariants
  (martingale, monotonicity, put-call/CIP parity).

---

## 7. Bottom line

| Dimension | Verdict |
|---|---|
| Methodology / numerics | **At or above** vendor standard (copulas, TVOG/MLMC, measure discipline) |
| Coverage & financial reporting | **Far below** (one product, no statutory/IFRS-17/SII balance sheet) |
| Calibration to reality | **Not yet** (synthetic data, placeholder params) |
| Governance scaffold | **Strong**, ahead of typical bespoke builds |
| Governance *evidence* / sign-off | **Incomplete** (no independent review; Layers 3–5 open) |
| Scale / performance | **Unproven**; likely the practical blocker |

Order of operations to become "Prophet/AXIS-competitive for a niche (HK par)":
**live calibration → asset–ESG coupling → statutory/IFRS-17 reporting → completed independent
validation → scale.**

---

## 8. References

- Subject model docs: `RELEASE_NOTES.md`, `MODEL_RISK_CARD.md`, `DEPLOYMENT_READINESS_CHECKLIST.md`,
  `COMPREHENSIVE_MODEL_DOCUMENTATION.md`, `POST_V1_STOCHASTIC_MODEL_EXPANSION_PLAN.md`,
  `ESG_MODEL_LIMITATIONS_AND_UPGRADE_PATH.md`.
- Companion deliverables: `DEEP_DIVE_ESG_CALIBRATION.md`, `DESIGN_ASSET_ESG_COUPLING.md`.
- External standards referenced by the model: SOA ASOP 7/25/56, IA (HK) TAS-M, APS X2, Solvency II
  (Art. 124/234), CBIRC C-ROSS (2023).

*Prepared as an independent desk benchmark. Product/vendor names are trademarks of their respective owners
and are used here only for comparison.*
