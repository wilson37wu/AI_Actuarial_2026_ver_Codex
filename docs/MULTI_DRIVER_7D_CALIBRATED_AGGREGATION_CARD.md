# Model Card - Seven-Driver Aggregation with CALIBRATED Liquidity Inputs (Phase 22 Task 4)

**What changed vs the Phase 21 Task 4 card:** the liquidity exposure notional and the six 7x7
liquidity couplings are no longer educational placeholders - they are the Phase 22 Task 3
G-LIQX-gated calibrated values (reproducible balance-sheet notional 22000 =
100,000 x 0.55 x 0.40; couplings recovered by the CIR transition-residual estimator,
PSD-validated).

**Evidence (seed 42, n_outer 160 x n_inner 24):** standalone sum 62389; var-covar
28991; copula (gaussian) 41604; nested 48707; understatement 40.5%; copula
rel 14.6%; liquidity standalone SCR 45.1 (placeholder run: 63.32111662161069). Tail: CONVERGED,
Sobol-RQMC 3.6x. Verdict **PASS**.

**CRN reuse:** outer columns 0-5 and the five-driver component liabilities are bit-identical
to the Phase 21 Task 4 run (Cholesky rows 0-5 depend only on the unchanged 6x6 block; liquidity
shock drawn last) - verified before slice reuse.

**Finding (refreshed):** the liquidity driver remains SMALL and net-diversifying at this scale;
the calibrated notional (22,000 < 30,000) and couplings keep the one-year 99.5% liquidity
translation risk modest on a hold-to-maturity book - a documented, honest finding.

**Remaining residual (disclosed):** educational-proxy market data pending credentialled
sources; independent APS X2 review. Single systemic liquidity factor (no asset-class
segmentation / funding ladder). Nested n_outer small for a 99.5% metric - nested bootstrap CI
wide and disclosed. Not for pricing, reserving, or regulatory capital.

*Standards: SOA ASOP 56 3.1.3/3.4/3.5; ASOP 25 3.3; IA TAS M 3.2/3.5/3.6;
Solvency II Del. Reg. Art. 234; EIOPA VA methodology; L'Ecuyer 2018.*
