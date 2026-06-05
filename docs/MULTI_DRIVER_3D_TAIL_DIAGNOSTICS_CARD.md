# Three-Driver Tail-Convergence & Stability Diagnostics — Model Card

**Phase 17 Task 4.**  EDUCATIONAL ONLY — placeholder parameters; NOT a
regulatory capital model.  Independent APS X2 review pending; production
sign-off withheld.

## Purpose

Provides the convergence, sampling-error, and variance-reduction evidence that
SOA ASOP 56 §3.5 and IA TAS M §3.6 require before the **three-driver** 99.5%
economic-capital figure (VaR / ES of the rate + equity + credit-spread
liability) may be cited.  It is the three-driver counterpart of the Phase 15
Task 4 two-driver diagnostics and extends the documented Phase 17 limitation
that prior tail-stability evidence covered only rates + equity.

## What it measures

Built **additively** on the Phase 17 Task 1 trivariate Longstaff-Schwartz
capital surface `L_hat(r, S, s)` (`ThreeDriverLSMCProxyEngine`), which is fitted
**once** and then evaluated for the cost of a polynomial, so the *outer*
sampling error can be probed at scale without a brute-force nested re-run.

1. **Outer-count convergence.**  99.5% VaR/ES of `L_hat` over independent,
   genuinely 3-factor-correlated outer sets of increasing size; reports the
   successive relative change and the smallest `N_outer` at which it falls
   below tolerance (ASOP 56 §3.5 scenario-count adequacy).

2. **Bootstrap confidence interval.**  Non-parametric bootstrap of the 99.5%
   VaR and ES estimators at a fixed large outer set — the sampling uncertainty
   of the *reported* capital number (IA TAS M §3.6 model-uncertainty
   disclosure).

3. **Variance reduction.**  Crude vs antithetic vs scrambled-Sobol QMC variance
   of the VaR estimator, over a common pilot-anchored Gaussian-copula surrogate
   whose controlling correlation is the realised **3×3** outer-state
   correlation (rate/equity/credit) and whose margins are the empirical pilot
   margins, so the three schemes target an identical distribution and the ratio
   is like-for-like (Glasserman 2003 §4; L'Ecuyer 2018 RQMC).

## Scope and limitations

| Aspect | Position |
|---|---|
| Risk drivers in the tail | THREE: short rate `r_H`, equity level `S_H`, credit spread `s_H`. Lapse, mortality-trend, and FX risk are still NOT in the tail. |
| Proxy (fit) error | NOT measured here — bounded separately by the Phase 17 Task 1 proxy-vs-nested (3-D grid R²≈0.964) and Task 2 out-of-sample (OOS R²=0.9751) reports. This module isolates the orthogonal outer Monte-Carlo (sampling) error. |
| Variance-reduction surrogate | Ratios are measured on a smooth Gaussian-copula surrogate of the horizon state (the controllable normal/uniform driver antithetic and QMC require). Convergence and bootstrap use the REAL governed 3-factor outer states. Ratios are indicative of relative estimator efficiency, not an absolute capital figure. |
| Antithetic on the 99.5% quantile | Expected to be ineffective (ratio ≈ 1): antithetic variates decorrelate the mean, not an extreme order statistic. A ratio near 1 is theory-consistent, not a defect; QMC is the effective scheme. |
| Parameters | HW1F / GBM / CIR++ are illustrative placeholders; capital magnitudes are NOT calibrated. |
| Governance | Independent APS X2 review pending; production sign-off withheld. |

## Reproducibility

The report carries a SHA-256 reproducibility digest over the VaR/ES convergence
paths, the bootstrap point/SE estimates, the per-scheme VaR estimator SDs, and
the realised 3×3 copula correlation; identical config + seed reproduces the
digest bit-for-bit.

## Code / evidence

- Engine: `par_model_v2/projection/multi_driver_tail_diagnostics.py`
  (`ThreeDriverTailDiagnostics`, `ThreeDriverTailConfig`,
  `ThreeDriverTailReport`, `VarianceReduction3D`) — additive; the two-driver
  `MultiDriverTailDiagnostics` and the Phase 17 Task 1/2/3 modules are untouched.
- Evidence builder: `scripts/build_phase17_task4_tail_diagnostics.py`
- Report: `docs/validation/PHASE17_TAIL_DIAGNOSTICS_REPORT.{json,md}`
- Tests: `tests/test_phase17_tail_diagnostics.py`

## Standards

SOA ASOP 56 §3.1.3 / §3.5; SOA ASOP 25 §3.3; IA TAS M §3.6;
L'Ecuyer (2018) "Randomized Quasi-Monte Carlo"; Glasserman (2003) §4.
