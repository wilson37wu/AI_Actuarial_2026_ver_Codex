# Model-Limitation Card — Three-Driver Economic-Capital Proxy (consolidated)

**Modules (Phase 17 Tasks 1–4):**
- `par_model_v2/stochastic/credit_spread.py` — CIR++ mean-reverting square-root credit-spread driver (full-truncation Euler; P/Q-consistent via the CIR risk premium; reduced-form hazard×LGD loss helper) (Task 1)
- `par_model_v2/projection/multi_driver_capital_3d.py` — three-driver (short-rate r + equity level S + credit spread) nested ground truth + trivariate-polynomial LSMC capital surface (Task 1)
- `par_model_v2/projection/multi_driver_proxy_validation.py` — `ThreeDriverProxyValidator`: out-of-sample trivariate proxy-model validation (Task 2)
- `par_model_v2/projection/multi_driver_risk_aggregation.py` — `ThreeDriverRiskAggregator`: correlated standalone-to-diversified capital aggregation (Task 3)
- `par_model_v2/projection/multi_driver_tail_diagnostics.py` — `ThreeDriverTailDiagnostics`: 99.5% tail convergence / bootstrap CI / variance reduction (Task 4)

**Phase / Task:** Phase 17 Task 5 (governance consolidation of Tasks 1–4)
**Classification:** **EDUCATIONAL ONLY — NOT a regulatory or internal economic-capital model**
**Governance status:** ChangeRecord *"Phase 17 Task 5 — three-driver (rate+equity+credit) economic-capital proxy governance refresh"* at **OWNER_REVIEW** (production sign-off withheld; independent APS X2 review pending). Risk register entry **MR-012** opened (HIGH, IN_PROGRESS).
**Standards:** IA TAS M §3.6/§3.7; APS X2 §3; SOA ASOP 56 §3.5; SOA ASOP 25 §3.3; IFoA proxy-modelling working party.

## Purpose

Provides a single governance reference for the Phase 17 three-driver economic-capital
proxy. The proxy estimates the 99.5% VaR / ES and an SCR-proxy of a Hong Kong
participating endowment liability driven by **three correlated risk factors** — the
short rate (HW1F), the equity level (GBM, optionally Merton jump-diffusion), and the
credit spread (CIR++) — revalued on a market-consistent (Q-measure) inner nest, with a
Longstaff–Schwartz LSMC surface standing in for the inner nest so the calculation is
feasible. It extends the Phase 15 two-driver baseline by adding credit as the third
driver, closing the documented "single-/two-driver" limitation; the asset library
already carries credit spreads / private credit, so credit is the natural third driver.

## Validated scope and evidence (seed = 42, 10y / age-40 M / SA 100k)

| Dimension | Result | Source |
|---|---|---|
| Proxy fit vs nested ground truth | R² = 0.964, max abs rel err 5.5% on the (r,S,spread) grid | Task 1 |
| Out-of-sample proxy skill | OOS R² = 0.9751; selected basis (deg 1, max interaction 3); VaR rel err 7.05%; ES rel err 6.96%; leakage-free (0 shared states, min scaled dist 0.057); overfit onset at 10 terms | Task 2 |
| Correlated aggregation vs nested | var-cov formula SCR 26,829 vs nested 43,753; rel err 38.7% (> 35% tol) → **PARTIAL** (honest) | Task 3 |
| Outer-sampling convergence | converged True; recommended N_outer ≥ 1,000; final VaR 152,297 / ES 155,757 | Task 4 |
| Bootstrap 95% CI on 99.5% VaR | VaR 150,859; 95% CI [149,634, 152,369]; SE 692 (±0.91%) | Task 4 |
| Variance reduction | Sobol QMC ≈ 2.76×; antithetic 0.89× (ineffective on the extreme tail quantile — expected) | Task 4 |
| Reproducibility | same-seed digests bit-identical across all modules | Tasks 1–4 |

## Standalone capital and the diversification finding (99.5%, CRN-isolated)

Standalone SCRs are isolated by **exact common-random-number (CRN) decomposition** of
the conditional liability on a fixed inner seed: rate = guaranteed PV (equity + credit
OFF); equity = L_re − L_rate; credit = L_rc − L_rate. Evidence (N_outer = 800,
n_inner = 128): rate SCR 20,696; equity SCR 22,559; credit SCR 4,460; standalone sum
47,715; var-cov SCR 26,829; nested SCR 43,753.

**MR-010 (three-driver refresh).** Adding the credit driver **widens** the
ESG-factor-formula understatement of diversified nested capital from ~32.9%
(two-driver) to **~38.7%** (three-driver). The governed ESG factor off-diagonals are
negative (rate-equity −0.15, rate-credit −0.20, equity-credit −0.30), but the realised
capital-loss correlations are all strongly positive (rate-equity +0.54, rate-credit
+0.77, equity-credit +0.61), so the second-moment variance–covariance formula on factor
correlations is **non-conservative** for diversified capital. Use the nested benchmark
for the headline capital figure.

## What it does NOT cover (limitations)

- **Placeholder calibration.** HW1F, GBM, and now CIR++ credit parameters (mean-reversion,
  long-run spread, vol, risk premium) plus the reduced-form hazard / LGD assumptions are
  educational defaults, not calibrated to credentialled market data. All capital figures
  are illustrative.
- **Omitted risk drivers.** Only rates + equity + credit spread are in the tail. Lapse,
  mortality / longevity trend, FX, liquidity, and management-action risk are not.
- **Factor-correlation diversification gap (MR-010).** The var-cov formula understates
  diversified nested capital by ~38.7%; the nested benchmark is authoritative.
- **No independent review.** No APS X2 independent peer review has been performed; the
  ChangeRecord is held at OWNER_REVIEW and production sign-off is withheld.
- **Single educational liability.** A single Hong Kong participating endowment with a
  single guarantee + a stylised credit exposure on backing assets; not a full portfolio.

## Model-use restrictions

The three-driver capital proxy output (VaR / ES / SCR-proxy, the diversification
waterfall, and the tail diagnostics) is for **education and methodology demonstration
only**. It must **not** be used for regulatory capital (HK RBC / Solvency), internal
economic-capital reporting, pricing, MCEV, or any financial decision. Residual closure
requires: (1) credentialled-data calibration of the credit (and rate / equity)
parameters; (2) bringing the omitted drivers into the tail; (3) resolving the MR-010
factor-correlation understatement; and (4) an independent APS X2 review. Tracked jointly
with MR-006, MR-008, MR-010, and MR-011.

## Residual risk register

| ID | Title | Rating | Status |
|---|---|---|---|
| MR-006 | Validation / independent-review readiness | — | IN_PROGRESS |
| MR-008 | HW1F calibration (placeholder) | — | IN_PROGRESS |
| MR-010 | Factor-correlation diversification understatement (~38.7%, three-driver) | — | MITIGATED |
| MR-011 | Multi-driver (two-driver) capital proxy is educational | HIGH | IN_PROGRESS |
| MR-012 | Credit-spread driver / three-driver capital proxy is educational | HIGH | IN_PROGRESS |
