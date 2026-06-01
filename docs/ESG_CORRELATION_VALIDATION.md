# ESG Correlation Matrix Validation

Phase 8 adds a governed validation layer for cross-risk-factor correlation
inputs and generated scenario diagnostics. The implementation is in
`par_model_v2/stochastic/esg_process.py` through:

- `phase8_rate_equity_fx_correlation_matrix(...)`
- `CorrelationMatrixValidator`
- `CorrelationMatrixValidationReport`
- `CorrelationMatrixValidationCheck`

## Scope

The validator covers correlation matrices used for rate, equity, and FX shock
generation. It is deliberately model-agnostic so later credit-spread, private
asset, and liability-behaviour factors can use the same evidence format.

Current v1-compatible factor IDs are:

| Factor ID | Meaning |
| --- | --- |
| `RATE_SHORT_CHANGE` | Monthly short-rate change from generated rate paths |
| `EQUITY_RETURN_1M` | Monthly equity return from the GBM equity process |
| `FX_RETURN_1M` | Monthly FX spot return when currency translation is enabled |

## Input Matrix Checks

`CorrelationMatrixValidator.validate_matrix(...)` produces JSON-ready evidence
for:

- finite entries;
- unit diagonal;
- symmetry;
- entry range in `[-1, 1]`;
- positive-semidefinite status using eigenvalue diagnostics.

`reject_invalid(...)` raises `ValueError` for matrices that fail error-level
checks. This is the default governance action when a matrix is an approved
calibration input and no model-owner repair has been approved.

## PSD Repair

`validate_matrix(..., repair=True)` applies an eigenvalue-floor repair and
rescales the result back to a correlation matrix. The report keeps both the
original matrix and repaired matrix, plus:

- original minimum eigenvalue;
- repaired minimum eigenvalue;
- maximum absolute entry adjustment;
- warning if the adjustment exceeds the review threshold.

The repair is an evidence-producing review tool, not an automatic production
override. A repaired matrix should be approved by the model owner before use in
pricing, valuation, capital, or external reporting.

## Scenario Diagnostics

`validate_scenario_diagnostics(...)` computes empirical correlations from
generated scenario output:

- short-rate changes from `r_short`;
- equity returns from `equity_return_1m`;
- optional FX returns from `fx_return_1m`.

When an expected matrix is supplied, the validator records the maximum absolute
difference between empirical and configured correlations. The default tolerance
is intentionally review-oriented because finite Monte Carlo samples, nonlinear
rate dynamics, and return transformations can move empirical correlations away
from input shock correlations.

## Phase 8 Generator Basis

`ScenarioSet.generate(...)` currently constructs equity and FX shocks from one
rate shock plus independent residual shocks. If both equity and FX are present,
the implied correlation matrix is:

```text
Corr(rate, equity) = rho_rate_equity
Corr(rate, FX)     = rho_rate_fx
Corr(equity, FX)   = rho_rate_equity * rho_rate_fx
```

`phase8_rate_equity_fx_correlation_matrix(...)` returns this implied matrix for
the configured `GBMParams` and optional `FXParams`.

## Standards Alignment

- SOA ASOP 56 Sections 3.1.3 and 3.4: documents the correlation basis,
  validation diagnostics, and limitations of placeholder calibration inputs.
- SOA ASOP 56 Section 3.5: adds reproducible scenario diagnostics for generated
  paths and sampling review.
- IA TAS M Sections 3.5 and 3.6: preserves an audit-ready validation report,
  repair evidence, and model-owner review points.

## Limitations

- Starter correlations are educational placeholders, not calibrated market
  assumptions.
- The current generator uses static correlations; time-varying, regime-switching,
  stochastic-volatility, and jump-correlation models remain future upgrades.
- Empirical scenario diagnostics do not replace historical backtesting. The next
  Phase 8 task added `PMeasureBacktestValidator`; see
  `docs/ESG_P_MEASURE_BACKTEST_SCAFFOLD.md` for the real-world equity
  distribution and correlation stability scaffold.
