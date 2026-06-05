# Model-Limitation Card — Multi-Driver Economic-Capital Proxy (consolidated)

**Modules (Phase 15 Tasks 1–4):**
- `par_model_v2/projection/multi_driver_capital.py` — two-driver (short-rate r + equity level S) nested ground truth + bivariate-polynomial LSMC capital surface (Task 1)
- `par_model_v2/projection/multi_driver_proxy_validation.py` — out-of-sample proxy-model validation (Task 2)
- `par_model_v2/projection/multi_driver_risk_aggregation.py` — correlated standalone-to-diversified capital aggregation (Task 3)
- `par_model_v2/projection/multi_driver_tail_diagnostics.py` — 99.5% tail convergence / bootstrap CI / variance reduction (Task 4)

**Phase / Task:** Phase 15 Task 5 (governance consolidation of Tasks 1–4)
**Classification:** **EDUCATIONAL ONLY — NOT a regulatory or internal economic-capital model**
**Governance status:** ChangeRecord *"Phase 15 Task 5 — multi-driver economic-capital proxy governance refresh"* at **OWNER_REVIEW** (production sign-off withheld; independent APS X2 review pending). Risk register entry **MR-011** opened (HIGH, IN_PROGRESS).
**Standards:** IA TAS M §3.6/§3.7; APS X2 §3; SOA ASOP 56 §3.5; SOA ASOP 25 §3.3; IFoA Modelling Practice Note §4.

## Purpose

Provides a single governance reference for the Phase 15 multi-driver economic-capital
proxy. The proxy estimates the 99.5% VaR / ES and an SCR-proxy of a Hong Kong
participating endowment liability driven by **two correlated risk factors** — the
short rate (HW1F) and the equity level (GBM, optionally Merton jump-diffusion) —
revalued on a market-consistent (Q-measure) inner nest, with a Longstaff–Schwartz
LSMC surface standing in for the inner nest so the calculation is feasible.

## Validated scope and evidence (seed = 42, 10y / age-40 M / SA 100k)

| Dimension | Result | Source |
|---|---|---|
| Proxy fit vs nested ground truth | R² = 0.9936, max abs rel err 2.67% on a 5×5 (r,S) grid | Task 1 |
| Out-of-sample proxy skill | OOS R² = 0.9704; VaR rel err 3.21%; ES rel err 2.60%; leakage-free; overfit onset = degree 2 | Task 2 |
| Correlated aggregation vs nested | var-cov formula SCR 29,031 vs nested 43,251; rel err 32.9% (< 35% tol) → PASS | Task 3 |
| Outer-sampling convergence | converged True; ΔVaR ≤ 0.58% by N_outer = 2,000 | Task 4 |
| Bootstrap 95% CI on 99.5% VaR | [149,402, 154,391]; SE ≈ 1,486 (±1.66%) | Task 4 |
| Variance reduction | Sobol QMC ≈ 7.1×; antithetic ineffective on the tail (expected) | Task 4 |
| Reproducibility | same-seed digests bit-identical across all four modules | Tasks 1–4 |

## What it does NOT cover (limitations)

- **Placeholder calibration.** HW1F and GBM parameters are educational defaults, not
  calibrated to credentialled market data. All capital figures are illustrative.
- **Omitted risk drivers.** Only rates + equity are in the tail. Lapse, mortality /
  longevity trend, credit spread, FX, liquidity, and management-action risk are
  excluded — so diversification and aggregate capital are both understated relative
  to a full internal model.
- **Aggregation gap (MR-010).** Variance–covariance aggregation fed the raw ESG factor
  correlation (−0.15) understates the fully-diversified nested tail capital by ~33%,
  because the realised capital-loss correlation under joint down-rate / down-equity
  stress is +0.55. Aggregated figures must be benchmarked to the Task 3 nested run.
- **Single educational guarantee.** One equity-linked maturity guarantee (GMMB-style
  put) plus rate-driven guaranteed benefits; no rider, surrender-value, or
  paid-up-option optionality.
- **Proxy vs sampling error are bounded separately.** Task 1/2 bound the LSMC fit
  error; Task 4 bounds the orthogonal outer-sampling error. Neither replaces a full
  nested run for a production sign-off.
- **No independent review.** No APS X2 independent review has been performed.

## Model-use restrictions

1. Use for **education, methodology demonstration, and internal benchmarking of the
   proxy technique only.** Do not use for regulatory capital, pricing, reserving,
   or any external reporting.
2. Always **report alongside the limitation evidence** above; do not quote a single
   capital number without its proxy-error and sampling-error bounds.
3. **Benchmark aggregated capital to the nested ground truth** (Task 3) before use;
   do not rely on the variance–covariance formula alone (MR-010).
4. Treat all figures as conditional on **placeholder parameters**; re-run after any
   credentialled-data calibration.
5. Production use requires closing **MR-011** (and the linked MR-006 / MR-008): a
   credentialled-data calibration, the omitted drivers brought into the tail, and an
   **independent APS X2 review** sign-off.

## Residual model risk (to production)

| Residual | Tracked by | Status |
|---|---|---|
| Educational classification / placeholder params / no independent review | **MR-011** | IN_PROGRESS (HIGH) |
| Validation readiness below production threshold | MR-006 | IN_PROGRESS |
| HW1F calibration to credentialled data | MR-008 | OPEN |
| Aggregation diversification gap | MR-010 | MITIGATED (benchmark-to-nested) |

Estimated remediation: credentialled-data calibration + independent APS X2 review
(see `MODEL_RISK_CARD.md` and `docs/DEPLOYMENT_READINESS_CHECKLIST.md`).
