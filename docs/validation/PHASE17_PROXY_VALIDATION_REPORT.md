# Phase 17 Task 2 — Out-of-Sample Trivariate Proxy-Model Validation

**Module:** `par_model_v2/projection/multi_driver_proxy_validation.py` →
`ThreeDriverProxyValidator`
**Validates:** the Phase 17 Task 1 three-driver (short-rate + equity +
credit-spread) Longstaff–Schwartz LSMC economic-capital surface
(`par_model_v2/projection/multi_driver_capital_3d.py`).
**Classification:** EDUCATIONAL ONLY — proxy-model validation evidence, not a
regulatory sign-off. Independent APS X2 review pending.
**Standards:** SOA ASOP 56 §3.5 / §3.1.3; SOA ASOP 25 §3.3; IA TAS M §3.6 / §3.2;
IFoA proxy-modelling working party; Longstaff & Schwartz (2001);
Duffie & Singleton (1999); Cox-Ingersoll-Ross (1985).

## Why a dedicated out-of-sample validation

The Task 1 proxy is fitted by least-squares on `N_fit` *single-inner-path*
liability samples, so its in-sample `fit_r2` is computed against noisy
single-path payoffs and is intrinsically low (~0.19). It is **not** a measure of
how well the surface reproduces the *true* conditional expectation
`L(r,S,s) = E^Q[ residual PV | r_H, S_H, s_H ]`. A defensible proxy validation
requires a genuine hold-out, heavy (high-accuracy) validation targets,
basis-complexity selection by out-of-sample skill, and leakage/overfit
diagnostics. This task delivers all four for the third (credit) driver.

## Method

1. **Disjoint-seed hold-out.** Fit on `n_fit` correlated outer states (one inner
   path each, fit seed 42); validate on an *independent* set of `n_validation`
   states generated from a disjoint seed (20260605), so no validation point can
   leak into the fit. Leakage is verified two ways (exact shared-row count and
   minimum scaled pairwise distance).
2. **Heavy nested validation targets.** At each hold-out state a high-inner-count
   (`n_inner_heavy=512`) nested estimate of the true `L(r,S,s)` is the OOS truth.
3. **Basis-complexity selection over (degree, max-interaction-order).** With
   three drivers the *interaction structure* — not just the polynomial degree —
   is a real complexity lever, so the sweep spans both: degrees 1→4 and the
   capped three-way interaction order (the `r·S·s` term toggles at degree ≥ 3).
   The basis minimising OOS RMSE is selected.
4. **Overfit diagnostics.** Bases are ordered by number of terms; the overfit
   onset is the first basis whose OOS RMSE rises above the previous (simpler)
   one. The in-sample-heavy − OOS R² gap is reported per basis.

## Evidence (fit seed 42; n_fit=1000, n_validation=80, n_inner_heavy=512; 99.5%)

| basis (deg, max_int) | terms | fit R² (noisy) | in-sample-heavy R² | **OOS R²** | OOS RMSE | overfit gap |
|---|---:|---:|---:|---:|---:|---:|
| (1, 3) **← selected** | 4 | 0.185 | 0.978 | **0.9751** | 2 299.7 | 0.0034 |
| (2, 3) | 10 | 0.196 | 0.958 | 0.9360 | 3 685.5 | 0.0225 |
| (3, 2) | 19 | 0.205 | 0.928 | 0.8123 | 6 309.3 | 0.1153 |
| (3, 3) | 20 | 0.208 | 0.925 | 0.7605 | 7 127.8 | 0.1649 |
| (4, 3) | 32 | 0.220 | 0.869 | 0.7593 | 7 145.4 | 0.1098 |

Two textbook signatures are visible. First, the **noisy fit R² (~0.19) is not a
validation metric**: it is far below the in-sample-heavy R² (0.87–0.98), which is
what actually measures fit to the true conditional expectation. Second, a clean
**overfit profile**: OOS R² peaks at the simplest basis (0.9751), then degrades
monotonically as terms are added (0.936 → 0.812 → 0.761 → 0.759) while the
overfit gap widens (0.003 → 0.165). The overfit onset is at 10 terms (degree 2).

The deg-1 selection is expected: across the fitted interquartile state box the
three-driver liability is close to locally affine in `(r, S, s)`, and the
single-inner-path fit cannot resolve the small higher-order curvature against
Monte-Carlo noise, so added terms fit noise and lose OOS skill.

## Capital comparison at the selected basis

| metric | proxy | three-driver nested | rel. error |
|---|---:|---:|---:|
| VaR 99.5% | 151 290 | 162 774 | **7.05%** |
| ES 99.5% | 155 829 | 167 477 | 6.96% |
| SCR proxy | 32 446 | 44 849 | 27.66% |

(nested ground truth: `n_outer=800`, `n_inner=96`.)

VaR/ES rel. error is ~7%, inside the educational ≤10% gate. SCR rel. error is
larger (27.7%) — SCR = VaR − mean is a small difference of two larger numbers,
so it amplifies the residual Monte-Carlo and proxy error; it is **not** a verdict
gate and is consistent with the Phase 15 two-driver precedent.

## Verdict

**PASS** — selected basis (degree 1, max-interaction-order 3) validated
out-of-sample: OOS R² = 0.9751 (≥ 0.95), VaR rel. error = 7.05% (≤ 10%),
hold-out leakage-free (0 shared states, min scaled distance 0.057), overfit gap
= 0.0034 (≤ 0.05). Reproducibility digest `4972795d3931…` (bit-identical on
re-run).

## Limitations / model-use restrictions

Educational only. Validates the three-driver surface across the fitted 3-D
interquartile state region; extrapolation is unsupported. Heavy targets are
nested Monte-Carlo estimates (residual error ~1/√n_inner_heavy). Basis selection
is over the swept grid only. Lapse, mortality-trend, and FX risks remain outside
the proxy; credit is a single systemic CIR++ spread with no rating migration or
default jump. Parameters are illustrative placeholders — capital magnitudes are
NOT calibrated. Production sign-off withheld pending independent APS X2 review.
