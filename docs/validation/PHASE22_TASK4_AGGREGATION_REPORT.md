# Phase 22 Task 4 - Seven-Driver Aggregation Re-Run (Calibrated Liquidity Inputs)

Run: 2026-06-07T09:14:22.568476+00:00 | Verdict: **PASS** | seed 42 | n_outer 160 x n_inner 24

## Calibrated inputs consumed (Phase 22 Task 3, G-LIQX PASS)

- Exposure notional: **22000** (placeholder was 30,000); placeholder flag: False
- Liquidity couplings (rate, equity, spread, lapse, mortality, fx): -0.0794, -0.2935, +0.4579, +0.1081, +0.0160, +0.1070; placeholder flag: False

## Aggregation results (calibrated)

| Metric | Value |
|---|---|
| Standalone SCR - rate | 14486.3 |
| Standalone SCR - equity | 15931.6 |
| Standalone SCR - credit | 4713.9 |
| Standalone SCR - lapse | 22538.9 |
| Standalone SCR - mortality | 387.2 |
| Standalone SCR - fx | 4286.4 |
| Standalone SCR - liquidity | 45.1 |
| Standalone sum | 62389.3 |
| Var-covar SCR (7x7 ESG) | 28990.9 |
| Nested SCR (benchmark) | 48707.4 |
| ESG understatement | 40.5% |
| Copula selected | gaussian |
| Copula SCR | 41604.3 (14.6% vs nested) |
| Correlation matrix valid | True |

## Calibrated vs placeholder (archived Phase 21 Task 4 baseline)

| Metric | Placeholder -> Calibrated |
|---|---|
| Liquidity standalone SCR | 63.32111662161069 -> 45.05333401574302 |
| Var-covar SCR | 28996.2 -> 28990.9 (-5.3, -0.02%) |
| Nested SCR | 48694.0 -> 48707.4 (+13.4, +0.03%) |
| Copula SCR | 41592.6 -> 41604.3 (+11.7, +0.03%) |

## Tail diagnostics (re-run on calibrated loss set)

- Convergence: CONVERGED (successive VaR deltas 0.74%, 0.01%, 0.03%, 0.07%)
- Simulated bootstrap 95% VaR CI rel-halfwidth: 0.2%
- Nested small-sample bootstrap 95% VaR CI rel-halfwidth: 3.1% (disclosed; n_outer=160)
- Sobol-RQMC variance-reduction ratio: 3.6x

## Governance

- ChangeRecord: `5a9934acc1c64f91a4c94c77a5ae37fc` (OWNER_REVIEW)
- MR-010: MITIGATED (refreshed); MR-012: MITIGATED (refreshed)
- Audit integrity: True

## Notes

- SEVENTH DRIVER = CIR++ liquidity/funding-spread premium with the Phase 21 Task 3 G-LIQ-calibrated parameters (kappa=0.9345/yr, long-run 63bp, sigma=0.0213, lambda_l=2.00); the EXPOSURE notional (22000) and 7x7 liquidity couplings are the Phase 22 Task 3 G-LIQX-CALIBRATED values (reproducible balance-sheet notional; CIR transition-residual coupling recovery, PSD-validated) - no longer placeholders; residual is credentialled-data quality + APS X2 review.
- Inner Q-nest liquidity conditioning is ANALYTIC and CIR-AFFINE-EXACT: haircut(l_H) = 1 - exp(-phi tau) A(tau) exp(-B(tau) x_H) under the Q-re-anchored long-run level; liability impact is baseline-centred, liq_l = notional (haircut(l_H) - haircut(l_0)).
- First six drivers and the five-driver CRN component liabilities are reproduced bit-for-bit from the Phase 21 Task 1 six-driver engine (liquidity shock drawn last; regression-tested).
- Var-covar (7x7 ESG) understates nested by 40.5%; copula (gaussian) reconciles within 14.6% (MR-010 refresh under seven drivers).
- Liquidity standalone SCR 45.1 is SMALL relative to rate 14486.3 / equity 15931.6: the calibrated mean reversion (half-life 0.74y) pulls the premium back over the 19y workout horizon, so 1-in-200 one-year liquidity translation risk on a hold-to-maturity book is modest — an honest, documented finding, not a wiring defect (the haircut mapping is verified affine-exact).
- MR-012 driver-omission residual is CLOSED at the aggregation level: all seven documented drivers (rate, equity, credit, lapse, mortality, fx, liquidity) now enter the correlated capital aggregation.

*Reproducibility digest: `3ba257f9a02434f7cc444eac451829da9167091f2eb7db289658e74255358036`*

*Standards: SOA ASOP 56 3.1.3/3.4/3.5; ASOP 25 3.3; IA TAS M 3.2/3.5/3.6;
Solvency II Del. Reg. Art. 234; EIOPA VA methodology; L'Ecuyer 2018.*
