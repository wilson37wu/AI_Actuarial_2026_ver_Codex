# Hong Kong Cash Dividend Product Mechanics

**Document ID:** `PHASE10-HK-CASH-DIVIDEND-MECHANICS`  
**Created:** 2026-06-03  
**Status:** Phase 10 task 1 implementation note  
**Scope:** Educational Hong Kong participating cash dividend product definition and sample policy data.

## Purpose

Phase 10 starts the liability expansion by defining a Hong Kong-style
participating endowment with annual non-guaranteed cash dividends.  This task
does not yet implement dividend declaration governance or stochastic
supportability.  It creates the auditable product mechanics and starter policy
data needed by those later tasks.

The implementation is in `par_model_v2/projection/hk_participating.py`.  The
sample policy fixture is
`par_model_v2/projection/fixtures/hk_cash_dividend_policies.json`.

## Implemented Contract

`HKCashDividendMechanics` captures the product-level contract terms:

| Field | Purpose |
|---|---|
| `product_code`, `product_name` | Stable product identity for policy data and reporting |
| `market`, `currency` | Hong Kong / HKD scope marker |
| `issue_age_min`, `issue_age_max` | Educational issue-age eligibility |
| `terms_years` | Projection-supported terms; currently 5, 10, and 20 years |
| `min_sum_assured`, `max_sum_assured` | Sample issue-size boundaries |
| `premium_mode` | Annual premium fixture convention |
| `dividend_option` | Cash dividend treatment |
| `annual_cash_dividend_rate` | Placeholder illustrated annual cash dividend rate |
| `guaranteed_maturity_multiple`, `death_benefit_multiple` | Guaranteed base benefit convention |
| `surrender_value_pct` | Current deterministic surrender-value proxy |
| `source_id`, `limitation_id` | Governance traceability fields |

Cash dividends are defined as non-guaranteed annual cash payments:

```text
annual_cash_dividend = sum_assured * annual_cash_dividend_rate
```

They do not vest, do not increase the guaranteed maturity benefit, and do not
increase the guaranteed death benefit.  This differs from a reversionary bonus
product, where declared bonuses become vested policyholder benefits.  The
reversionary bonus mechanics are the next Phase 10 task.

## Starter Policy Data

`sample_hk_cash_dividend_policies()` loads three governed sample policies:

| Policy ID | Term | Issue Age | Gender | Sum Assured | Annual Premium | Policy Year |
|---|---:|---:|---|---:|---:|---:|
| `HKCD000001` | 10 | 35 | M | 500,000 | 43,000 | 1 |
| `HKCD000002` | 20 | 42 | F | 800,000 | 38,500 | 5 |
| `HKCD000003` | 5 | 55 | M | 300,000 | 58,500 | 3 |

`sample_hk_cash_dividend_policy_table()` returns these records as a DataFrame
with market, currency, illustrated annual cash dividend, source, and limitation
fields.  `validate_hk_cash_dividend_policy_table(...)` checks required columns,
unique policy IDs, product-code consistency, term support, age eligibility,
sum-assured range, premium mode, and dividend option.

## Projection Compatibility

`HKCashDividendPolicy.to_projection_product(...)` converts a sample policy to
the current deterministic `ParEndowmentProduct` for the guaranteed base.  It
sets `rb_rate_annual = 0` and `terminal_bonus_pct = 0` so that cash dividends
remain separate from reversionary bonus and terminal bonus fields.

`annual_cash_dividend_schedule(...)` returns annual non-guaranteed cash
dividend rows by policy year and month.  The schedule is intentionally separate
from the existing liability cash-flow engine until the Phase 10 declaration and
asset-share supportability tasks consume the explicit declaration assumption
record and sensitivity hooks.

## Governance Notes

- SOA ASOP 56: product mechanics, placeholder dividend rate, and unsupported
  production use are disclosed explicitly rather than embedded as undocumented
  projection constants.
- IA TAS M: policy fixtures preserve product code, policy ID, source ID, and
  limitation ID for audit reconstruction.
- ERM: the current cash dividend rate is an educational illustration.  It is
  not a PRE policy, board-approved declaration basis, insurer filing, or
  calibrated supportability assumption.

## Validation

Targeted tests in `tests/test_hk_participating_products.py` cover:

- default mechanics and cash dividend amount calculation;
- rejection of unsupported terms and invalid policy records;
- JSON fixture loading and stable sample policy IDs;
- conversion to the current deterministic projection product;
- sample policy table governance fields and duplicate-ID checks;
- annual non-guaranteed cash dividend schedule construction.

## Next Phase 10 Task

The declaration assumption task is implemented in
`docs/HK_DECLARATION_ASSUMPTIONS_AND_SENSITIVITIES.md`.  The next task is to
add asset-share support tests for cash dividend and reversionary bonus variants.
