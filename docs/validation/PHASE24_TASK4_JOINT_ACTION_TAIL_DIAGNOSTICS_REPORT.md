# Phase 24 Task 4 -- Joint-Action Tail Diagnostics + Capital-Delta Matrix

**Verdict: PASS** (3/3 fixed pre-registered gates PASS;
governance gate G4 reported separately below).

EDUCATIONAL ONLY. Tail diagnostics and the full with-vs-without /
joint-vs-standalone capital-delta matrix on the JOINT-action
(action-after-aggregation) basis established by Phase 24 Task 2, under the
frozen t(2.9451) / Gaussian copulas on the archived Phase 23 Task 2
dependence basis (seed 20260607, n_sim 200,000, n_obs 160).

## 99.5% 1y SCR delta matrix

| Level | Without | With (standalone-action) | With (joint-action) | Joint vs without | Joint vs standalone |
|---|---|---|---|---|---|
| Nested (reference) | 48,707.4 | 33,117.8 | 33,117.8 | -32.0% | 0.0% |
| t(2.9451) | 46,756.0 | 25,652.9 | 31,001.8 | -33.7% | 20.9% |
| Gaussian | 41,472.4 | 23,921.8 | 26,267.1 | -36.7% | 9.8% |
| Var-covar | 28,990.9 | 14,428.7 | n/a | n/a | n/a |

Nested has no standalone/joint split (rule on the full conditional
liability; reference for both bases). Var-covar has no joint-action
analogue (formula on standalone marginals; DISCLOSED). Standalone-action
t/Gaussian VaR/ES from P23T4 use a different (summed) level convention --
SCR-only in the matrix (DISCLOSED).

## Var-covar understatement refreshed (MR-010)

- vs nested-with-actions 33,117.8: **56.4%**
- vs t joint-action read-out: **53.5%**
- without-actions baseline (P22T4): 40.5%

## Confidence sweep with action-saturation profile (t joint-action)

| Conf | VaR_with | ES_with | SCR_with | Tail active | Tail saturated | Relief at VaR |
|---|---|---|---|---|---|---|
| 0.900 | 124,305 | 129,528 | 11,625 | 100.0% | 44.0% | 12,034 |
| 0.950 | 126,641 | 133,712 | 13,961 | 100.0% | 88.0% | 16,568 |
| 0.990 | 138,941 | 144,807 | 26,260 | 100.0% | 100.0% | 18,946 |
| 0.995 | 143,682 | 148,496 | 31,002 | 100.0% | 100.0% | 19,593 |
| 0.999 | 151,468 | 154,255 | 38,787 | 100.0% | 100.0% | 20,655 |

Saturation share in the 99.5% tail: **100.0%** -- the joint tail
sits predominantly at maximum relief, the mechanism behind the Phase 23
Task 4 finding, now quantified on the joint basis.

## Prefix-subsample convergence (common random numbers, 99.5%)

| n_sim | VaR_with | SCR_with | SCR rel delta vs full |
|---|---|---|---|
| 25,000 | 143,980 | 31,317 | 1.02% |
| 50,000 | 144,038 | 31,366 | 1.17% |
| 100,000 | 143,614 | 30,944 | 0.19% |
| 200,000 | 143,682 | 31,002 | 0.00% |

## Copula-seed stability + margin bootstrap (DISCLOSED diagnostics)

- SCR max rel spread across 5 copula seeds at n_sim 200,000: **1.98%**
- Margin bootstrap (200 replicates x 20,000 sims; joint row resample of the 160 realised outer losses; copula frozen, SII Art. 234):
  SCR_with mean 30,406, SE 1,752
  (5.8% of mean), 95% CI
  [26,471, 33,637]
- Nested-with-actions reference inside the bootstrap 95% CI: **True**
- VaR sweep monotone in confidence: True

The bootstrap quantifies the DISCLOSED Task 1 limitation that n_obs=160
margin sampling noise propagates into the joint read-out; the nested run
remains the capital reference.

## Fixed pre-registered gates (Task 1 design note s5; no gate-shopping)

- G1_delta_matrix_complete_and_crosschecked: PASS
- G2_var_covar_understatement_refreshed: PASS
- G3_reproducibility_recorded: PASS
- G4_governance_verify_all: True

## Reproducibility

- Bit-identical reproduction of the archived Phase 24 Task 2 read-outs:
  t/g SCR abs diff 0.00e+00 / 0.00e+00; digests match
  (True/True).
- 27 archive cross-checks PASS before any new computation.
- Digest `dd89036a3371f6a1`; seed 20260607; n_sim 200,000; bootstrap seed 20260608.

Standards: Solvency II Delegated Regulation Article 23 (future management actions); Solvency II Delegated Regulation Article 234 (aggregation); SOA ASOP 56 section 3.1.3/3.4/3.5; SOA ASOP 25 section 3.3; IA TAS M section 3.2/3.6; IFoA Life Aggregation & Simulation working party; McNeil-Frey-Embrechts 2015 ch.7.
