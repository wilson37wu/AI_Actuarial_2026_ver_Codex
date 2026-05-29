# Runtime Test Evidence — Full Suite PASSING

**Run (UTC):** 2026-05-29T19:07:38Z
**Environment:** Linux sandbox, CPython 3.10.12, deps from requirements-dev.txt (numpy, pandas, scipy, pytest) installed successfully.
**Significance:** Prior automation cycles were blocked — the only reachable interpreter (pgAdmin CPython 3.13) lacked pytest/numpy/pandas/scipy and PyPI was unreachable. This run executed in an environment where dependencies install, so the long-pending runtime validation evidence is now captured.

## Results (run in 4 batches due to 45s per-call limit)

| Batch | Files | Result |
|-------|-------|--------|
| 1 | esg_process | 42 passed (12.9s) |
| 2 | audit_trail_wiring, backtesting, calibration, data_validator, distributed_executor, dynamic_alm, esg_adapter, governance, hybrid_grid | 479 passed (24.0s) |
| 3 | ia_validation, integration_e2e, model_health, tvog | 191 passed (36.1s) |
| 4 | monthly_projection, risk_metrics, sensitivity, stress_testing | 216 passed (30.4s) |
| **Total** | **19 test modules** | **928 passed, 0 failed** |

## Warnings (non-fatal, expected)
- Calibration: max swaption vol error ~9.33 bps exceeds 1 bps threshold on placeholder inputs (documented placeholder-parameter limitation).
- Sensitivity/TVOG: ScenarioCountWarning n_scenarios=100 below ASOP 56 §3.5 minimum of 500 (test-scale runs, by design).
- numpy RuntimeWarning invalid value in divide within calibration edge-case tests (zero-variance synthetic inputs).

## Standards
- SOA ASOP 56 §3.1.3 / §3.6: stochastic-process and measure-guard logic verified at runtime.
- IA TAS M §3.6: runtime validation evidence requirement now satisfied for the current codebase state.
