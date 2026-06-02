# Asset Roll-Forward Reporting

**Document ID:** `PHASE9-ASSET-ROLLFORWARD-REPORTING`  
**Created:** 2026-06-02  
**Status:** Phase 9 task 4 implementation note  
**Scope:** Asset cashflow aggregation and market-value roll-forward reporting.

## Purpose

Phase 9 now aggregates fixed income, private assets, and derivative examples
into a monthly reporting view suitable for educational ALM attribution.  The
implementation keeps income, principal, losses, capital activity, derivative
settlements, and valuation movement separate so reviewers can trace how each
asset class contributes to the end-of-month market value.

## Implemented Contract

The implementation is in `par_model_v2/projection/asset_reporting.py`.

`aggregate_asset_rollforward(...)` combines already-projected source outputs:

- `FixedIncomeProjectionResult`
- `PrivateAssetProjectionResult`
- `DerivativeValuationResult`

It returns an `AssetRollForwardReport` with:

| Field | Purpose |
|---|---|
| `monthly_rollforward` | Normalized monthly rows by source, instrument, and asset class |
| `by_class_attribution` | Class-level opening MV, ending MV, cashflow, loss, and valuation movement |
| `source_summary` | Fixed income / private asset / derivative roll-up |
| `opening_market_value`, `ending_market_value` | Portfolio-level reported MV anchors |
| `net_cashflow` | Aggregate income, principal, capital, distribution, and derivative cashflow |
| `market_value_change` | Valuation movement after separating explicit cash and loss items |
| `governance_notes` | SOA / IA / ERM disclosure notes for report users |

`project_phase9_asset_rollforward(...)` builds the complete starter report
from the Phase 9 default fixed-income, private-asset, and derivative examples.

## Roll-Forward Identity

Class attribution uses this deterministic reporting identity:

```text
Ending MV =
  Opening MV
  + capital calls
  - distributions
  - principal repayments
  - default losses
  + market value change
```

Cash income and derivative settlements are disclosed separately because they
normally flow through income / hedge-settlement reporting rather than directly
changing holding market value.

## Source Normalisation

### Fixed Income

Fixed-income rows map coupon income, spread income, default loss, principal
repayment, and ending market value from `project_fixed_income_cashflows(...)`.
The deterministic examples treat default loss and principal repayment as direct
market-value reductions.

### Private Assets

Private asset rows map economic NAV, reported NAV, cash income, spread income,
capital calls, distributions, principal repayments, default losses, and
valuation movement from `project_private_asset_cashflows(...)`.  Reported NAV
is retained separately for smoothing / lag disclosure.

### Derivatives

Derivative rows map valuation records and scheduled settlements from
`value_derivative_portfolio(...)`.  Swap and bond-forward scheduled cashflows
are assigned to the nearest payment month using `ceil(payment_time_years * 12)`.
The current educational examples hold derivative market value constant across
the projection unless a new valuation run is supplied.

## Governance Notes

- SOA ASOP 7 / ASOP 56: cashflow drivers and valuation movement are disclosed
  separately rather than hidden in one aggregate investment return.
- IA TAS M: `source_type`, `instrument_id`, and `asset_class` preserve
  traceability from source instrument projections to class-level reports.
- ERM: the report is deterministic and educational.  It excludes stochastic
  default timing, liquidity haircuts, production derivative CVA / collateral
  treatment, statutory accounting classifications, and calibrated market-data
  feeds.

## Validation

Targeted tests in `tests/test_asset_rollforward_reporting.py` cover:

- aggregation of fixed income, private assets, and derivatives;
- class-level roll-forward identity;
- derivative payment schedule mapping to projection months;
- default Phase 9 fixture coverage for asset and derivative classes.

## Next Phase 9 Task

The follow-on Phase 9 task is implemented in
`docs/ASSET_CLASS_STRESS_TESTS_AND_GOVERNANCE.md`.  It adds deterministic rate,
spread, default, private-asset, infrastructure, and derivative stress
attribution with scenario-level governance notes.
