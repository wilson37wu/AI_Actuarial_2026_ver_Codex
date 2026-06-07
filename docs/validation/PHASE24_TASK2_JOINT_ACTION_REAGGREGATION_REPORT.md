# Phase 24 Task 2 -- Joint-Scenario (Action-After-Aggregation) Re-Aggregation

**Verdict: PASS** (4/4 fixed pre-registered gates PASS;
governance gate G5 reported separately below).

EDUCATIONAL ONLY. The governed Art.-23 bonus-cut rule (trigger
1.10, floor 0.90, PRE floor
60%, A_ref 129916.5) applied ONCE to the
anchored SIMULATED JOINT liability V = L_fit + sum_k (Q_k(U_k) - mean_k)
(action-after-aggregation; Phase 24 Task 1 design), with Q_k the empirical
margins of the WITHOUT-actions Phase 23 Task 2 staged standalone losses,
U from the frozen t(df=2.9451) / Gaussian copulas on the archived
Kendall-tau dependence basis (n_obs=160; seed 20260607; n_sim 200000).

## 99.5% 1y SCR vs nested-with-actions 33117.8

| Basis | SCR | rel err vs nested-with |
|---|---|---|
| **t(2.9451) JOINT-action (this task)** | **31001.8** | **6.4%** |
| Gaussian JOINT-action (comparator) | 26267.1 | 20.7% |
| t standalone-action (P23T4 disclosed baseline) | 25652.9 | 22.5% |
| Gaussian standalone-action (P23T4) | 23921.8 | 27.8% |
| Var-covar with-actions (P23T4, MR-010) | 14428.7 | 56.4% |

Saturation-gap remediation: t-copula rel err **22.5% -> 6.4%**
(gaussian 27.8% -> 20.7%). Action active on
44.0% of joint scenarios (4.4% at/below floor; nested outer-node
active share 46.9%).

## Joint without-actions sanity (not a gate)

t-copula joint WITHOUT-actions SCR 47269.1 vs archived Phase 23
Task 2 t-matched 46756.0 (diff 1.10%; different
seed path, same dependence basis -- Monte-Carlo only).

## Fixed pre-registered gates (Task 1 design note s5; no gate-shopping)

- G1_joint_t_rel_error_le_10pct: PASS
- G2_joint_t_strictly_below_standalone_baseline: PASS
- G3_df_rank_invariance: PASS
- G4_archive_crosschecks_pass: PASS
- G5_governance_verify_all: True

## Disclosures

- The copula is NOT re-tuned on the action basis (SII Art. 234): df re-matched on the WITHOUT-actions staged losses = 2.9451 (frozen 2.9451); dependence matrix bit-compared to the archived Phase 23 Task 2 basis (max|diff| < 1e-06).
- Action-exercise consistency (SII Art. 23): the rule is exercised ONCE on the total (joint) solvency position, matching how management would act; the Phase 23 Task 4 standalone-action basis double-counted relief where each marginal tail sat in the steeper partial-cut band.
- Anchoring V = L_fit + sum_k (Q_k - mean_k) is a first-order level approximation; cross-driver liability non-linearities beyond the action are not represented (Task 3 inner-path prototype addresses path dynamics).
- 25 archive cross-checks PASS before any new computation; staged primitives bit-identical.
- The joint read-out consumes realised standalone losses at n_obs=160; margin sampling noise propagates (disclosed in the module use restrictions).
- Rule parameters are educational placeholders pending credentialled management-practice data + APS X2 review.

Digest `1624d6f9002ec288`; t-run digest `61dab617ed39`; seed 20260607, n_sim 200000.

Standards: Solvency II Delegated Regulation Article 23 (future management actions); Solvency II Delegated Regulation Article 234 (aggregation); SOA ASOP 56 section 3.1.3/3.4/3.5; IA TAS M section 3.2/3.6; IFoA Life Aggregation & Simulation working party; Demarta-McNeil 2005; McNeil-Frey-Embrechts 2015 ch.7.
