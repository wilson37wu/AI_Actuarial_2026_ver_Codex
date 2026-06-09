# Skew-t Copula Card (Phase 27 Task 2)

- GH skew-t copula: one scalar gamma on the FROZEN t(2.9451, Sigma); gamma=0 recovers
  the frozen t EXACTLY (recovery dev 0e+00).
- gamma fitted leakage-free to standalone upper-tail co-exceedances: **gamma_hat 6.24e-05**
  (realised upper co-exceedance 0.152 < symmetric-t 0.236 -> no asymmetry to capture).
- skew-t component SCR 39981.0 (frozen-t 39975.7, +0.01%); gap to nested 46638.9: -14.28%.
- FINDING: copula-form residual is NOT a standalone-driver upper-tail asymmetry effect;
  escalate to grouped-t (heterogeneous tail dep) / nested-structure at Phase 28.
- Verdict: PASS — bootstrap + residual re-decomposition at Task 3.
