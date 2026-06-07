# Phase 23 Task 4 -- Aggregation + Tail Read-Outs WITH Management Actions

**Verdict: PASS** (4/4 fixed pre-registered gates PASS;
governance gate G5 reported separately below).

EDUCATIONAL ONLY. The governed Phase 23 Task 3 bonus-cut rule (trigger
1.10, floor 0.90, PRE floor
60%, max relief 12.0%,
A_ref 129916.5) applied to the seven-driver realised
standalone losses and the nested benchmark (n_obs=160).

## Benchmarks (99.5% 1y SCR): with vs without actions

| Aggregation | without | WITH actions | delta | rel err vs nested (with) |
|---|---|---|---|---|
| Nested ground truth | 48707.4 | 33117.8 | -15589.7 | -- |
| Var-covar (ESG factor) | 28990.9 | 14428.7 | -14562.2 | 56.4% (MR-010) |
| Gaussian copula (same-seed) | 41472.4 | 23921.8 | -17550.6 | 27.8% |
| **t(df=2.95) tail-matched** | **46756.0** | **25652.9** | **-21103.0** | **22.5%** |

Action active on 46.9% of outer nodes (7.5% at/below floor).

## Standalone SCRs by driver

| Driver | without | WITH actions | delta |
|---|---|---|---|
| rate | 14486.3 | 7299.4 | -7186.9 |
| equity | 15931.6 | 8026.7 | -7904.9 |
| credit | 4713.9 | 3091.0 | -1622.9 |
| lapse | 22538.9 | 11131.8 | -11407.2 |
| mortality | 387.2 | 387.2 | +0.0 |
| fx | 4286.4 | 2919.3 | -1367.1 |
| liquidity | 45.1 | 45.1 | -0.0 |

## Fixed pre-registered gates

- G1_t_copula_with_actions_gate: PASS
- G2_nested_with_le_without: PASS
- G3_all_standalone_with_le_without: PASS
- G4_df_rank_invariance: PASS
- G5_governance_verify_all: True

## Disclosures

- Anchoring convention: standalone with-actions level vector V_k = L_fit + (vec_k - mean_k); the action responds to the TOTAL coverage ratio under a single-driver stress. Standalone SCRs are translation-invariant; the anchor only sets where the action triggers.
- Rank invariance: the rule is a monotone marginal transform, so the empirical copula, Kendall taus and tail-matched df are IDENTICAL with and without actions (G4); only marginal quantiles change.
- Without-actions primitives reused bit-identically from the Phase 23 Task 2 stage; 13 archive cross-checks PASS before any with-actions work.
- MATERIAL FINDING: copula rel errors GROW with actions (t: 4.0% -> 22.5%; gaussian: 14.9% -> 27.8%). Aggregating standalone WITH-ACTIONS losses understates the nested-with-actions benchmark: the action SATURATES (max relief 12%) in the joint tail where the total liability is largest, while standalone tails sit in the steeper partial-cut band. The nested run remains the capital reference; copula read-outs are diagnostics on the with-actions basis (MR-010 notes refreshed accordingly).
- Rule parameters are educational placeholders pending credentialled management-practice data + APS X2 review.
- Small-driver columns (mortality, liquidity) sit at CR = 1.12 > trigger 1.10 under the anchor, so the action never triggers on them standalone: their SCRs are unchanged by construction.

Digest `0db4bcd1560aa69c`; run `tcopula-tailmatch-a989f91c`; seed 20260607, n_sim 200000, thresholds [0.8, 0.85, 0.9].

Standards: Solvency II Delegated Regulation Article 23 (future management actions); Solvency II Delegated Regulation Article 234 (aggregation); SOA ASOP 56 section 3.1.3/3.4/3.5; IA TAS M section 3.2/3.6; IFoA Life Aggregation & Simulation working party; Demarta-McNeil 2005; McNeil-Frey-Embrechts 2015 ch.7.
