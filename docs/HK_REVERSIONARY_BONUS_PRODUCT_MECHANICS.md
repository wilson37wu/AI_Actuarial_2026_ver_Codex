# Hong Kong Reversionary Bonus Product Mechanics

**Document ID:** `PHASE10-HK-REVERSIONARY-BONUS-MECHANICS`  
**Created:** 2026-06-03  
**Status:** Phase 10 task 2 implementation note  
**Scope:** Educational Hong Kong participating reversionary bonus product definition, vested bonus schedule, terminal bonus treatment, and guarantee split.

## Purpose

This Phase 10 task adds a Hong Kong-style participating endowment where
declared reversionary bonuses become vested policyholder benefits.  It is the
second starter liability product slice after cash dividends.  The task defines
mechanics and sample policy data only; declaration governance, stochastic
supportability, and sensitivity hooks remain the next Phase 10 task.

The implementation is in `par_model_v2/projection/hk_participating.py`.  The
sample policy fixture is
`par_model_v2/projection/fixtures/hk_reversionary_bonus_policies.json`.

## Implemented Contract

`HKReversionaryBonusMechanics` captures the product-level terms:

| Field | Purpose |
|---|---|
| `product_code`, `product_name` | Stable product identity for policy data and reporting |
| `market`, `currency` | Hong Kong / HKD scope marker |
| `issue_age_min`, `issue_age_max` | Educational issue-age eligibility |
| `terms_years` | Projection-supported terms; currently 5, 10, and 20 years |
| `min_sum_assured`, `max_sum_assured` | Sample issue-size boundaries |
| `premium_mode` | Annual premium fixture convention |
| `bonus_option` | Vested reversionary bonus treatment |
| `annual_reversionary_bonus_rate` | Placeholder annual declared vested-bonus addition |
| `terminal_bonus_pct` | Placeholder non-guaranteed terminal bonus percentage |
| `guaranteed_base_multiple` | Guaranteed base maturity and death benefit convention |
| `death_benefit_vested_bonus_multiple` | Vested bonus multiple for death guarantee split |
| `maturity_vested_bonus_multiple` | Vested bonus multiple for maturity guarantee split |
| `surrender_value_pct` | Current deterministic surrender-value proxy |
| `source_id`, `limitation_id` | Governance traceability fields |

The illustrated annual vested bonus addition is:

```text
annual_vested_bonus_addition = sum_assured * annual_reversionary_bonus_rate
```

The starter guarantee split treats the base sum assured and vested
reversionary bonus as guaranteed after declaration.  Terminal bonus remains
non-guaranteed and payable at maturity only in this educational contract.

## Starter Policy Data

`sample_hk_reversionary_bonus_policies()` loads three governed sample policies:

| Policy ID | Term | Issue Age | Gender | Sum Assured | Annual Premium | Policy Year | Initial Vested Bonus |
|---|---:|---:|---|---:|---:|---:|---:|
| `HKRB000001` | 10 | 32 | F | 600,000 | 51,000 | 1 | 0 |
| `HKRB000002` | 20 | 46 | M | 900,000 | 44,500 | 6 | 112,500 |
| `HKRB000003` | 5 | 58 | F | 350,000 | 68,500 | 3 | 35,000 |

`sample_hk_reversionary_bonus_policy_table()` returns these records as a
DataFrame with market, currency, annual reversionary bonus rate, terminal bonus
percentage, projected vested bonus, total guaranteed maturity benefit, source,
and limitation fields.

`validate_hk_reversionary_bonus_policy_table(...)` checks required columns,
unique policy IDs, product-code consistency, term support, age eligibility,
sum-assured range, premium mode, and bonus option.

## Projection Compatibility

`HKReversionaryBonusPolicy.to_projection_product(...)` converts a sample policy
to the current deterministic `ParEndowmentProduct`:

- `rb_rate_annual` maps to the placeholder annual reversionary bonus rate.
- `terminal_bonus_pct` maps to the placeholder terminal bonus percentage.
- `initial_rb_accum` maps to the policy's initial vested bonus balance.

The existing deterministic liability engine reports reversionary-bonus outgo
through non-guaranteed columns.  Phase 10 therefore also adds explicit
guarantee-split helpers so downstream reporting can distinguish base guarantee,
vested declared bonus, and non-guaranteed terminal bonus without changing the
legacy projection schema in this task.

## Schedule and Guarantee Split

`annual_reversionary_bonus_schedule(...)` returns one annual row per policy
year with:

- annual vested bonus addition;
- cumulative vested bonus balance;
- guaranteed base benefit;
- guaranteed death and maturity benefits after vested bonus;
- terminal bonus percentage and non-guaranteed status;
- source and limitation IDs.

`reversionary_bonus_guarantee_split(...)` returns the maturity split:

```text
total_guaranteed_maturity_benefit =
    guaranteed_base_benefit + vested_reversionary_bonus
```

Terminal bonus is intentionally separate and non-guaranteed.

## Governance Notes

- SOA ASOP 56: product mechanics, placeholder bonus rates, terminal bonus
  status, and unsupported production use are disclosed explicitly.
- IA TAS M: product records preserve policy ID, product code, source ID,
  limitation ID, and reconstructable guarantee split fields.
- ERM: the current bonus and terminal bonus percentages are educational
  illustrations.  They are not a PRE policy, board-approved declaration basis,
  supportability result, insurer filing, or calibrated management action.

## Validation

Targeted tests in `tests/test_hk_participating_products.py` cover:

- default mechanics and invalid terminal bonus percentage rejection;
- annual vested bonus calculation;
- fixture loading and stable sample policy IDs;
- conversion to the deterministic projection product;
- invalid policy bonus option rejection;
- sample policy table governance and duplicate-ID checks;
- annual vested bonus schedule construction;
- maturity guarantee split across base, vested bonus, and terminal bonus.

## Next Phase 10 Task

The next task is to implement dividend and bonus declaration assumptions and
sensitivity hooks.  That should connect cash dividends and reversionary bonus
declarations to explicit assumption records before the later asset-share
supportability and reporting tasks consume them.
