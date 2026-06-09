# Grouped-t Copula Card (Phase 28 Task 2)

- Grouped-t copula: per-block df_g on the FROZEN Sigma; homogeneous boundary (all df_g=2.9451, shared mixing) recovers
  the frozen single-df t EXACTLY (recovery dev 0e+00).
- Partition (pre-registered): FIN/carve-out {credit,FX,liquidity} idx {2,5,6}; NON-FIN {rate,equity,lapse,mortality} idx {0,1,3,4}.
- df_g fitted leakage-free to within-block upper co-exceedances: **df_NONFIN 37.866, df_FIN 8.506**.
- grouped-t component SCR 35604.4 (frozen-t 39975.7, -10.93%, down); gap to nested 46638.9: -23.66%.
- Two-sided lever (within-block concentration vs cross-block dilution); direction DISCLOSED, not gated.
- Verdict: PASS — bootstrap + residual re-decomposition at Task 3.
