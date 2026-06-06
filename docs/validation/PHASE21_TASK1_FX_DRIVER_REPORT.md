# Phase 21 Task 1 -- FX / Currency Sixth Capital Driver (G-FX)

Run: 2026-06-06T21:52:05.965347+00:00

## G-FX gate: PASS (6/6)

| Criterion | Result | Evidence (truncated) |
| --- | --- | --- |
| FX-01-positive-spots | PASS | min_spot=6.172983 |
| FX-02-lognormal-moments | PASS | log_mean_emp=-0.0018; log_mean_theory=-0.0018; z_mean=0.0 |
| FX-03-pq-measure-separation | PASS | terminal_mean_P=8.19895; terminal_mean_Q=7.956634; ratio=1.030455 |
| FX-04-q-cip-martingale | PASS | check_id=MART-FX-CIP; estimate=7.800573; target=7.8 |
| FX-05-correlation-wiring | PASS | realised_rate_fx_corr=-0.15129; target=-0.15; tolerance=0.02 |
| FX-06-exposure-mapping | PASS | impact_at_initial_spot=0.0; monotone_decreasing_in_spot=True; loss_at_20pct_depreciation=6000.0 |

## Six-driver aggregation (verdict: PASS)

| Driver | Standalone SCR |
| --- | --- |
| rate | 14486.3 |
| equity | 15931.6 |
| credit | 4713.9 |
| lapse | 22538.9 |
| mortality | 387.2 |
| fx | 4286.4 |

* Var-covar (6x6): 28992.0; nested: 48737.5; understatement 40.5%
* Copula (gaussian): 41232.0 (rel err vs nested 15.4%)
* Interaction residual (rel): -16.7%
* Reproducibility digest: `7e4cb6e0685b61daebd4fc5b6c4f44019bb63d9bda3d1525101af7d7f6d2f04e`

## Governance

* ChangeRecord: 25e1eac6661a4d9bb74276ee1a2a4b46 (OWNER_REVIEW)
* MR-012: IN_PROGRESS (refreshed)
* Audit integrity: True
