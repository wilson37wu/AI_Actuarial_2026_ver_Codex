# Private Asset Educational Models

**Document ID:** `PHASE9-PRIVATE-ASSET-MODELS`  
**Created:** 2026-06-02  
**Status:** Phase 9 task 2 implementation note  
**Scope:** Educational private credit, private equity, and infrastructure asset models.

## Purpose

Phase 9 extends the asset library beyond public bonds and listed equity by
adding transparent private asset examples.  The implementation is not a
production valuation model.  It is designed to make the core actuarial ALM
drivers visible in monthly cashflow, NAV, and reporting summaries.

## Implemented Contract

The implementation is in `par_model_v2/projection/private_assets.py`.

### Private Credit

`PrivateCreditAsset` captures:

| Field | Purpose |
|---|---|
| `asset_id`, `strategy` | Stable holding and strategy identifiers |
| `market_value`, `book_value` | Current valuation basis |
| `cash_yield`, `spread_bps` | Income and spread carry assumptions |
| `annual_default_probability`, `recovery_rate` | Expected loss basis |
| `liquidity_lag_months` | Delay between maturity and principal receipt |
| `valuation_smoothing_months` | Lagged reporting NAV recognition |
| `maturity_years`, `currency` | Projection and reporting dimensions |
| `source_id`, `limitation_id` | Governance traceability fields |

Monthly projection rows expose cash income, spread income, expected default
loss, lagged principal repayment, economic NAV, and smoothed reported NAV.

### Private Equity

`PrivateEquityAsset` captures funded NAV, unfunded commitment, annual capital
call rate, distribution rate, NAV growth, J-curve drag, valuation lag, and NAV
smoothing.  Monthly rows expose capital calls, distributions, J-curve-adjusted
NAV growth, net cashflow, economic NAV, and smoothed reported NAV.

### Infrastructure

`InfrastructureAsset` captures cash yield, inflation linkage, inflation
assumption, availability factor, revenue shock, duration, concession term, and
valuation smoothing.  Monthly rows expose cash income, inflation uplift, revenue
shock loss diagnostics, economic NAV, and smoothed reported NAV.

## Starter Fixtures

`default_phase9_private_assets()` provides three governed educational examples:

- `HK_PC_DIRECT_LENDING_EDU`: senior secured direct lending private credit.
- `HK_PE_BUYOUT_EDU`: diversified buyout private equity fund.
- `HK_INFRA_AVAILABILITY_EDU`: availability-based infrastructure asset.

Each fixture includes placeholder source and limitation identifiers.  They are
not calibrated market assumptions.

## Governance Notes

- SOA ASOP 7 / ASOP 56: asset cashflow assumptions are explicit, including
  default loss, liquidity lag, valuation smoothing, capital calls,
  distributions, inflation linkage, and revenue shock treatment.
- IA TAS M: every private asset record includes source and limitation IDs, and
  projection outputs are reconstructable from asset-level fields.
- ERM: private asset limitations remain material.  The models omit stochastic
  default timing, manager dispersion, fee waterfalls, vintage diversification,
  appraisal uncertainty, liquidity haircuts, covenant tests, and scenario
  dependent exits.

## Validation

Targeted tests in `tests/test_private_asset_projection.py` cover:

- private credit loss, spread, liquidity lag, and governance fields;
- private equity capital calls, distributions, and J-curve behaviour;
- infrastructure inflation linkage, availability, and revenue stress;
- input validation for probability and smoothing ranges;
- class-level reporting summaries and starter fixture coverage.

## Next Phase 9 Task

The next task is to add interest rate swap valuation and bond forward valuation
examples.  Those examples should state valuation measure, discounting basis,
collateral assumptions, cash settlement timing, and educational limitations.
