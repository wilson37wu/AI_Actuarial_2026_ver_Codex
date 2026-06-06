# Phase 20 Task 4 -- Capital Re-Aggregation with the Two-Factor G2++ Rates Driver

**Run:** 2026-06-06T10:25:50.364534+00:00

**Verdict (G2++):** PASS - five-driver copula aggregation (selected: gaussian) reconciles to nested capital within 12.4% vs var-covar 39.7%; MR-010 five-driver mitigation confirmed

## 1. What changed

The single-factor Hull-White (HW1F) rate driver in the OUTER real-world state was
replaced by the swaption-calibrated two-factor **G2++** driver
(a=0.0345, b=0.9583, sigma=0.00637, eta=0.00240, rho=-0.9082), anchored to the
same initial curve. The horizon short-rate dispersion falls from ~114 bps (HW1F
placeholder) to ~49 bps (calibrated G2++): the swaption-calibrated factor vols are
lower and the strong negative factor correlation rho=-0.91 suppresses the
combined level variance while adding a slope/curvature axis the endowment liability
is less exposed to. The inner conditional valuation reuses the governed HW1F Q nest
(real-world-outer / risk-neutral-inner; a fully G2++-consistent inner nest is a
documented residual).

## 2. HW1F vs G2++ standalone capital (same config, n_outer=240, n_inner=48)

| Driver | HW1F SCR | G2++ SCR | Delta | Rel |
|--------|---------:|---------:|------:|----:|
| rate | 33,268 | 14,925 | -18,343 | -55.1% |
| equity | 32,995 | 18,846 | -14,149 | -42.9% |
| credit | 9,491 | 4,785 | -4,706 | -49.6% |
| lapse | 28,307 | 25,888 | -2,418 | -8.5% |
| mortality | 351 | 321 | -30 | -8.4% |

## 3. Aggregation vs nested (G2++ rate driver)

| Method | Aggregate SCR | Rel. error vs nested |
|--------|--------------:|---------------------:|
| Var-covar (5x5 ESG) | 33,227 | 39.7% |
| Copula (gaussian, realised losses) | 48,293 | 12.4% |
| **Nested ground truth** | **55,116** | - |

- HW1F var-covar understated nested by 52.5%; G2++ var-covar understates by 39.7% (MR-010 refreshed).
- HW1F copula reconciled within 10.3%; G2++ copula reconciles within 12.4% (MR-012 refreshed).
- Nested capital moves from 104,132 (HW1F) to 55,116 (G2++): -49,016 (-47.1%).

## 4. Notes

- RATE DRIVER = two-factor G2++ r(t)=phi(t)+x(t)+y(t) (Phase 20 Task 2 swaption calibration: a=0.0345, b=0.9583, sigma=0.00637, eta=0.00240, rho=-0.9082), anchored to the same initial curve as the HW1F baseline; only the rate dynamics differ.
- Dominant factor x carries the governed 5x5 ESG cross-correlation (same z_rate as HW1F); second factor y is correlated to x by rho and otherwise orthogonal - a new curve-shape tail axis (ASOP 25 §3.3).
- SCOPE: the two-factor driver enters the OUTER real-world rate marginal/tail; the INNER conditional liability L(.) reuses the governed HW1F Q nest at the realised r_H (standard real-world-outer / risk-neutral-inner decomposition, ASOP 56 §3.5). A fully G2++-consistent inner nest is a documented residual.
- Var-covar aggregation uses the governed 5x5 ESG driver correlation; MR-010 (the var-covar understatement of the diversified nested capital) refreshed under the 2F rate driver: understatement 39.7%.
- Copula-on-realised-losses (selected: gaussian) reconciles to nested capital within 12.4% - the MR-010 mitigation, re-confirmed with the 2F rate driver (MR-012 tail-aggregation governance).
- CRN additive decomposition leaves a -7.8%-of-nested interaction residual (multiplicative in-force x equity-guarantee and in-force x mortality-G cross-terms); unchanged in kind by the 2F rate driver.
