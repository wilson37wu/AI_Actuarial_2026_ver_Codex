# Fixed-Income Instrument Library

**Document ID:** `PHASE9-FIXED-INCOME-INSTRUMENT-LIBRARY`  
**Created:** 2026-06-01  
**Status:** Phase 9 task 1 implementation note  
**Scope:** Educational fixed-income instruments for ALM asset modelling.

## Purpose

Phase 9 starts the asset-class expansion by adding instrument-level fixed-income
records.  The legacy monthly projection still accepts broad `AssetPosition`
objects for compatibility, while the new fixed-income library records coupon,
duration, spread, downgrade, and default-loss assumptions explicitly.

## Implemented Contract

The implementation is in `par_model_v2/projection/fixed_income.py`.

`FixedIncomeInstrument` captures:

| Field | Purpose |
|---|---|
| `instrument_id` | Stable holding identifier for audit trail and reports |
| `asset_class` | Government, Corporate, or other fixed-income grouping |
| `market_value`, `book_value` | Current valuation basis |
| `coupon_rate` | Annual contractual coupon income rate |
| `duration_years` | First-order interest-rate / spread sensitivity |
| `spread_bps` | Credit or liquidity spread diagnostic |
| `downgrade_notches` | Current downgrade stress severity in notches |
| `annual_default_probability` | Placeholder default-frequency assumption |
| `recovery_rate` | Expected recovery used to derive default loss |
| `maturity_years` | Bullet principal repayment timing |
| `credit_rating`, `currency` | Reporting and calibration dimensions |
| `source_id`, `limitation_id` | Governance traceability fields |

`project_fixed_income_cashflows(...)` returns monthly rows with coupon income,
spread carry, expected default loss, net income, principal repayment, discounted
net income, and market-value roll-forward.  The result also includes instrument
records and class summaries for reporting.

`fixed_income_market_value_after_shock(...)` applies a transparent first-order
duration approximation:

```text
MV_shocked = MV * (1 - duration * total_yield_shift)
total_yield_shift = rate_shift + spread_shift + downgrade_notches * spread_per_notch
```

The stressed value is floored at zero.

## Starter Fixtures

`default_phase9_fixed_income_instruments()` provides two educational examples:

- `HK_GOVT_10Y_EDU`: HKD government bond with coupon and duration fields.
- `HK_CORP_A_7Y_EDU`: HKD A-rated corporate bond with credit spread, one
  downgrade notch, default probability, and recovery assumption.

These are placeholder educational holdings.  They are not calibrated market
data and must not be used for production valuation.

## Governance Notes

- SOA ASOP 7 / ASOP 56: asset cashflow assumptions now expose income, duration,
  spread, downgrade, and default-loss drivers separately instead of hiding them
  in one deterministic return.
- IA TAS M: each instrument has source and limitation identifiers, and monthly
  projection output is reconstructable from instrument-level fields.
- ERM: the first-order duration shock is suitable for teaching and screening,
  but it omits convexity, option-adjusted spread, liquidity haircuts, transition
  matrices, stochastic default timing, and issuer concentration.

## Validation

Targeted tests in `tests/test_fixed_income_projection.py` cover:

- required coupon, duration, spread, downgrade, and default-loss fields;
- validation of default probability and recovery ranges;
- conversion back to the legacy `AssetPosition` contract;
- monthly coupon, spread, expected default-loss, and principal repayment output;
- class-level reporting summaries;
- duration-based repricing under rate, spread, and downgrade shocks.

## Next Phase 9 Task

The next task is to add private credit, private equity, and infrastructure
educational asset models.  Those models should reuse the same governance style:
explicit cash yield, valuation basis, impairment / default treatment, liquidity
lags, limitation identifiers, and targeted tests.
