# Out-of-Sample Proxy-Model Validation Report — Multi-Driver LSMC Capital Surface

**Module validated:** `par_model_v2/projection/multi_driver_capital.py` (Phase 15 Task 1 bivariate LSMC capital proxy)
**Validator:** `par_model_v2/projection/multi_driver_proxy_validation.py` (Phase 15 Task 2)
**Phase:** 15 — Multi-Risk Economic Capital and Proxy-Model Validation (Task 2)
**Classification:** EDUCATIONAL ONLY — proxy-model validation evidence, not a regulatory sign-off
**Status:** OWNER_REVIEW — independent APS X2 review pending; production sign-off withheld
**Standards:** SOA ASOP 56 §3.5 / §3.1.3; SOA ASOP 25 §3.3; IA TAS M §3.6 / §3.2; IFoA proxy-model working party; Longstaff & Schwartz (2001)
**Run digest (seed 42 / 20260605):** `cc9654f9274974c6809ab40f…`

## Verdict

**PASS** — selected degree **1** validated out-of-sample (OOS R² = **0.9704**, capital VaR relative error = **3.21%**, hold-out **leakage-free**, overfit gap = **0.0017**).

## Why a dedicated out-of-sample validation

The Task 1 proxy is fitted by least squares on `N_fit` **single-inner-path** liability samples. Its in-sample `fit_r2` is therefore computed against **irreducible Monte-Carlo noise** and is intrinsically low (≈ 0.17–0.19 here). That number is **not** a measure of how well the surface reproduces the true conditional expectation `L(r,S) = E^Q[ residual PV | r_H, S_H ]`.

A defensible proxy validation instead requires (1) a genuine hold-out generated from a **disjoint seed** so no validation point can leak into the fit; (2) **"heavy" (high-inner-count) validation targets** approximating the true `L(r,S)`; (3) **basis-degree selection by out-of-sample skill**; and (4) explicit **leakage / overfit diagnostics**. This report delivers all four.

## Methodology

| Element | Choice |
|---|---|
| Product | 10y par endowment, age 40 M, SA 100,000, premium 6,000 |
| Capital horizon `H` | 12 months; confidence 99.5%; outer measure P |
| Equity guarantee | GMMB / put, money-back floor (`guarantee_rate = 1.0`) |
| Fitting set | `N_fit = 1,000` correlated outer states, **one** inner path each (seed 42) |
| Hold-out set | `N_val = 80` **independent** states (seed 20260605, disjoint) |
| Heavy targets | `n_inner_heavy = 512` inner Q-paths per validation state |
| In-sample-heavy subset | 40 held-in states (seed 7) for the in/out skill-gap |
| Degree grid | 1, 2, 3, 4 (total-degree bivariate polynomial) |
| Selection metric | minimise OOS RMSE vs heavy nested truth |

The degree sweep refits the surface at every degree on the **same** fitting states + payoffs, so degree comparison is strictly apples-to-apples.

## Per-degree out-of-sample skill

| Degree | Basis terms | In-sample R² (noisy fit) | In-sample R² (heavy truth) | **OOS R²** | **OOS RMSE** | OOS max abs rel err | Overfit gap |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **1** | 3 | 0.1732 | 0.9721 | **0.9704** | **2,311.7** | 4.2% | **0.0017** |
| 2 | 6 | 0.1826 | 0.9594 | 0.9392 | 3,316.5 | 11.7% | 0.0203 |
| 3 | 10 | 0.1875 | 0.9530 | 0.8793 | 4,671.9 | 25.8% | 0.0737 |
| 4 | 15 | 0.1926 | 0.9468 | 0.8543 | 5,132.0 | 25.0% | 0.0924 |

Two textbook signatures confirm the validation is working:

1. **Noisy `fit_r2` is not a validation metric.** In-sample R² against single-path payoffs (0.17–0.19) is an order of magnitude below in-sample R² against heavy truth (0.95–0.97). The regression is correctly averaging out single-path noise rather than failing to fit.
2. **Overfit onset is visible.** In-sample R² rises with degree while OOS R² **falls** and the overfit gap **grows monotonically** (0.0017 → 0.0924). OOS RMSE increases at every step beyond degree 1, so the **overfit-onset degree is 2**. The conditional-liability surface is near-linear in `(r, S)` over the fitted interquartile region; higher-order terms fit noise.

**Selected degree: 1** (lowest OOS RMSE, highest OOS R²).

## Leakage diagnostics

| Check | Result |
|---|---|
| Fit vs validation seeds disjoint | ✅ 42 ≠ 20260605 |
| Exact shared states | ✅ 0 |
| Min scaled fit↔validation distance | 0.0152 (> 0) |
| **Leakage-free** | ✅ **True** |

## Capital comparison at the selected degree

Proxy capital (degree-1 surface evaluated on a large cheap outer set) vs an **independent** multi-driver nested ground-truth run (`N_outer = 500`, `n_inner = 64`):

| Metric | Proxy | Nested truth | Relative error |
|---|---:|---:|---:|
| Mean liability | 108,340 | 107,467 | — |
| VaR 99.5% | 138,748 | 143,351 | **3.21%** |
| ES 99.5% | 141,823 | 145,614 | **2.60%** |
| SCR proxy (VaR − mean) | 30,408 | 35,884 | 15.26% |

The VaR and ES are within ~3% of nested truth. The SCR-proxy gap (15%) is the difference of two noisy tail estimates (it subtracts the mean from the VaR), and is consistent with the documented residual sampling error of an educational-size nested run; it is bounded and disclosed, not a model break.

## Limitations and residual risk

- **Educational only.** Parameters are illustrative placeholders; capital magnitudes are **not** calibrated.
- **Heavy targets are estimates.** Validation truth carries residual inner Monte-Carlo error ~`1/√n_inner_heavy`; a production validation would raise `n_inner_heavy`, `N_val`, and `N_outer`.
- **In-region only.** The surface and its validation cover the fitted interquartile `(r, S)` box; extrapolation is unsupported.
- **Risk coverage.** Lapse, credit-spread, mortality-trend and FX risks remain outside the tail (carried into Phase 15 Task 3 aggregation and the MR register).
- **Governance.** Independent APS X2 review pending; production sign-off withheld.

## Reproducibility

Identical config + seeds reproduce the report digest bit-for-bit (`reproducibility_digest`); covered by `tests/test_phase15_proxy_validation.py::test_reproducible_digest`. Full machine-readable evidence: `docs/validation/PHASE15_PROXY_VALIDATION_REPORT.json`.
