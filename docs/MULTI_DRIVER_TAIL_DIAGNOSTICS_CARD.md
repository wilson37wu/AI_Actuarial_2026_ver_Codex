# Model-Limitation Card — Multi-Driver Tail-Convergence & Stability Diagnostics

**Module:** `par_model_v2/projection/multi_driver_tail_diagnostics.py`
**Phase / Task:** Phase 15 Task 4
**Classification:** EDUCATIONAL ONLY — NOT a regulatory capital model
**Governance status:** ChangeRecord `820c6fe4` at OWNER_REVIEW (production sign-off
withheld; independent APS X2 review pending)

## Purpose

Quantifies the **outer Monte-Carlo (sampling) uncertainty** of the 99.5% VaR/ES
of the two-driver (short-rate + equity) liability, using the once-fitted Phase 15
Task 1 LSMC capital surface so the diagnostics are computationally feasible:

1. **Outer-count convergence** — VaR/ES over independent outer sets of increasing
   size; reports the successive relative change and the smallest `N_outer` at
   which it falls below `convergence_tol` (default 2%).
2. **Bootstrap confidence interval** — non-parametric bootstrap of the 99.5% VaR
   and ES estimators at a fixed large outer set; percentile CI + estimator SE.
3. **Variance reduction** — variance of the VaR estimator under crude pseudo-random,
   antithetic, and scrambled-Sobol QMC sampling over a common pilot-anchored
   Gaussian-copula distribution.

## Reference evidence (seed = 42, 10y / age-40 M / SA 100k)

| Diagnostic | Result |
|---|---|
| Outer-count convergence | Converged True; ΔVaR ≤ 0.58% by N_outer = 2,000; recommended N_outer ≥ 2,000 |
| Bootstrap 95% CI on VaR | [149,402, 154,391], SE ≈ 1,486 (±1.66% of point) |
| Sobol QMC variance-reduction ratio | **7.1× / 7.6×** on the VaR estimator |
| Antithetic variance-reduction ratio | ≈ 0.8–1.2× (ineffective on the tail quantile — expected) |
| Reproducibility | same-seed digest bit-identical |

## What it does NOT cover (limitations)

- **Proxy (LSMC fit) error** is *not* measured here — it is bounded separately by
  the Task 1 proxy-vs-nested report (R² = 0.9936 vs nested) and the Task 2
  out-of-sample validation. This module isolates the orthogonal outer-sampling error.
- **Risk drivers** beyond rates + equity (lapse, credit spread, mortality trend,
  FX, liquidity, management action) are still outside the tail.
- **Variance-reduction surrogate.** The crude/antithetic/Sobol comparison runs on a
  *pilot-anchored Gaussian copula* (governed ESG ρ; empirical pilot margins) — the
  controllable normal/uniform driver that antithetic and QMC require. Convergence
  and the bootstrap CI use the **real** governed outer states. The VR ratios are
  indicative of relative *estimator efficiency*, not an absolute capital figure.
- **Antithetic variates** are theory-consistently ineffective for an extreme 99.5%
  quantile (they decorrelate the mean, not the tail order statistic); QMC is the
  effective scheme. Do not rely on antithetic for tail-capital variance reduction.
- **Placeholder parameters.** HW1F/GBM parameters are illustrative; capital
  magnitudes are not calibrated.

## Standards

SOA ASOP 56 §3.1.3 / §3.5 (scenario adequacy, convergence, variance reduction);
SOA ASOP 25 §3.3 (correlated scenario generation); IA TAS M §3.6 (model validation,
convergence, reproducibility, uncertainty disclosure); L'Ecuyer (2018) Randomized
Quasi-Monte Carlo; Glasserman (2003) §4 (antithetic / QMC).

## Reproduce

```
PYTHONPATH=. python3 scripts/build_phase15_task4_evidence.py [--governance]
```
Writes `docs/validation/PHASE15_TAIL_DIAGNOSTICS_REPORT.{json,md}`.
