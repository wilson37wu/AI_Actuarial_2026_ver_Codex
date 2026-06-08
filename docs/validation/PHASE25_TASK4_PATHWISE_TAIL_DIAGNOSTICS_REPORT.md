# Phase 25 Task 4 -- Path-Wise Tail Diagnostics + Capital-Delta Matrix

**Verdict: PASS** (4/4 fixed pre-registered gates PASS;
governance gate G5 reported separately below).

EDUCATIONAL ONLY. Tail diagnostics and the full with-vs-without /
pathwise-vs-horizon capital-delta matrix on the PATH-WISE with-actions
basis established by Phase 25 Tasks 2-3, under the frozen
t(2.9451) / Gaussian copulas on the archived Phase 23 Task 2
dependence basis (seed 20260607, n_sim 200,000, n_obs 160; rank
invariance re-verified: df re-matched 2.9451, rho max|diff|
7.2e-16).

The t/gaussian path-wise read-outs are an ANALYTIC RE-ANCHORING of the
anchored joint level with the governed Task 3 smoothed-relief surface
(sigma 0.225, alpha 0.7567) and the FIT-sample benefit share
(beta 0.8450; leakage-free) -- NOT a full path-wise copula
re-aggregation (documented next-phase candidate). Nested rows are on the
n_eval=500 proxy-validation outer sample (the only basis where the
path-wise nested truth exists); t/gaussian/var-covar rows are on the
n_obs=160 aggregation dependence basis (DISCLOSED).

## 99.5% 1y SCR delta matrix (with-vs-without / pathwise-vs-horizon)

| Level | Without | With (horizon) | With (path-wise) | Path-wise vs without | Path-wise vs horizon |
|---|---|---|---|---|---|
| Nested (reference) | 55,561.2 | 40,852.1 | 46,638.9 | -16.1% | 14.2% |
| t(2.9451) | 46,756.0 | 31,001.8 | 39,794.3 | -14.9% | 28.4% |
| Gaussian | 41,472.4 | 26,267.1 | 35,210.1 | -15.1% | 34.0% |
| Var-covar | 28,990.9 | 14,428.7 | n/a | n/a | n/a |

Var-covar has no path-wise analogue (formula on standalone marginals;
DISCLOSED); its 'with (horizon)' figure is the P23T4 standalone-action
SCR (summed level convention -- SCR-only, P24T4 convention).

## MR-010/MR-014 refresh trigger (design note s5; REQUIRED)

- Nested path-wise vs horizon SCR delta: **+14.17%**
  (threshold 1%; trigger MET: True)
- The path-wise basis relieves LESS capital in the tail (recognition-lag
  effect: bonus restoration on recovering paths); the horizon-level basis
  UNDERSTATES the with-actions SCR at every level of the matrix.

## Var-covar understatement refreshed (MR-010)

- vs nested-with-path-wise 46,638.9: **69.1%**
- vs t path-wise read-out: **63.7%**
- horizon-basis baseline (P24T4): 56.4%

## Confidence sweep with action-saturation profile (t, path-wise basis)

| Conf | VaR_pw | ES_pw | SCR_pw | SCR_hz | Tail active | Tail saturated | Mean smoothed relief frac | Relief at VaR |
|---|---|---|---|---|---|---|---|---|
| 0.900 | 129,906 | 137,564 | 17,346 | 11,625 | 100.0% | 44.0% | 0.065 | 6,434 |
| 0.950 | 135,405 | 142,845 | 22,845 | 13,961 | 100.0% | 88.0% | 0.070 | 7,804 |
| 0.990 | 147,965 | 153,575 | 35,405 | 26,260 | 100.0% | 100.0% | 0.079 | 9,922 |
| 0.995 | 152,354 | 157,171 | 39,794 | 31,002 | 100.0% | 100.0% | 0.081 | 10,921 |
| 0.999 | 160,170 | 162,987 | 47,610 | 38,787 | 100.0% | 100.0% | 0.083 | 11,952 |

Saturation share (raw governed cut at floor) in the 99.5% tail:
**100.0%** -- the joint tail still sits at maximum RAW relief,
but the path-wise smoothed surface caps the realised relief at
alpha * phi_sigma < max_relief (mean smoothed fraction
0.081 vs raw 0.120), so the path-wise basis
relieves less at every confidence level
(True); t path-wise minus horizon SCR
8,793 (+28.4%).

## Prefix-subsample convergence (common random numbers, 99.5%)

| n_sim | VaR_pw | SCR_pw | SCR rel delta vs full |
|---|---|---|---|
| 25,000 | 152,630 | 40,082 | 0.72% |
| 50,000 | 152,684 | 40,126 | 0.83% |
| 100,000 | 152,291 | 39,747 | 0.12% |
| 200,000 | 152,354 | 39,794 | 0.00% |

## Copula-seed stability + margin bootstrap (DISCLOSED diagnostics)

- SCR max rel spread across 5 copula seeds at n_sim 200,000: **1.41%**
- Margin bootstrap (200 replicates x 20,000 sims; joint row resample of the 160 realised outer losses; copula frozen, SII Art. 234):
  SCR_pathwise mean 39,252, SE 1,615
  (4.1% of mean), 95% CI
  [35,793, 42,496]
- Nested path-wise reference inside the bootstrap 95% CI: **False**
- VaR sweep monotone in confidence: True

The bootstrap quantifies the DISCLOSED limitation that n_obs=160
margin sampling noise propagates into the joint read-out; the nested run
remains the capital reference.

## Fixed pre-registered gates (Task 1 design note s5; no gate-shopping)

- G1_delta_matrix_complete_and_crosschecked: PASS
- G2_var_covar_understatement_refreshed_pathwise: PASS
- G3_df_rank_invariance_copula_frozen: PASS
- G4_reproducibility_recorded: PASS
- G5_governance_verify_all: True

## Reproducibility

- Bit-identical reproduction of the archived Phase 24 Task 2 HORIZON
  read-outs: t/g SCR abs diff 0.00e+00 / 0.00e+00; digests match
  (True/True).
- 36 archive cross-checks PASS before any new computation.
- t path-wise vs nested path-wise SCR rel err: 14.7% (DISCLOSED; the
  full path-wise copula re-aggregation is the documented next-phase
  candidate).
- Digest `20bc1f4f5e378b4f`; seed 20260607; n_sim 200,000.

Standards: Solvency II Delegated Regulation Article 23 (future management actions); Solvency II Delegated Regulation Article 234 (aggregation); SOA ASOP 56 section 3.1.3/3.4/3.5; SOA ASOP 25 section 3.3; IA TAS M section 3.2/3.6; IFoA Life Aggregation & Simulation working party; McNeil-Frey-Embrechts 2015 ch.7.
