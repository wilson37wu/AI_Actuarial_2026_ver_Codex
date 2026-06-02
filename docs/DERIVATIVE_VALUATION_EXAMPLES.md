# Derivative Valuation Examples

**Document ID:** `PHASE9-DERIVATIVE-VALUATION-EXAMPLES`  
**Created:** 2026-06-02  
**Status:** Phase 9 task 3 implementation note  
**Scope:** Educational interest rate swap and bond forward valuation examples.

## Purpose

Phase 9 now includes transparent derivative examples for ALM teaching and
governance workflows.  The implementation is deliberately narrow: it values a
plain-vanilla fixed-vs-floating interest rate swap and a coupon-bond forward
from an explicit risk-free discount curve.

These examples are not production derivative valuation models.  They are
designed to expose valuation measure, discounting basis, settlement mechanics,
source identifiers, and limitation identifiers in a form that downstream asset
roll-forward and stress reporting can consume.

## Implemented Contract

The implementation is in `par_model_v2/projection/derivatives.py`.

### Interest Rate Swap

`InterestRateSwapContract` captures:

| Field | Purpose |
|---|---|
| `swap_id` | Stable derivative identifier |
| `notional` | Swap notional |
| `fixed_rate` | Contractual fixed leg rate |
| `maturity_years`, `start_years` | Projection and valuation dates |
| `pay_fixed` | Direction flag: pay fixed / receive floating if true |
| `payment_frequency_per_year` | Fixed and floating payment frequency |
| `currency` | Reporting currency |
| `collateral_basis` | Discounting convention disclosure |
| `source_id`, `limitation_id` | Governance traceability fields |

`value_interest_rate_swap(...)` uses the supplied `RiskFreeCurve` and returns
fixed-leg PV, floating-leg PV, par fixed rate, market value, valuation measure,
curve source, collateral basis, and limitation ID.

The floating leg uses the standard single-curve par approximation:

```text
Floating PV = Notional * (P(0, start) - P(0, maturity))
```

The fixed leg uses the discounted fixed coupon annuity:

```text
Fixed PV = Notional * fixed_rate * sum(accrual_i * P(0, T_i))
```

For a pay-fixed swap, market value is `floating_leg_pv - fixed_leg_pv`.

### Bond Forward

`BondForwardContract` captures:

| Field | Purpose |
|---|---|
| `forward_id` | Stable derivative identifier |
| `notional` | Bond face amount |
| `spot_dirty_price` | Current bond dirty price per 100 face |
| `contract_forward_price` | Contracted delivery price per 100 face |
| `bond_coupon_rate` | Underlying bond coupon rate |
| `bond_maturity_years` | Underlying bond maturity |
| `forward_maturity_years` | Forward delivery / settlement date |
| `long_forward` | Direction flag: long forward if true |
| `coupon_frequency_per_year` | Underlying coupon frequency |
| `settlement_basis` | Cash / physical settlement disclosure |
| `source_id`, `limitation_id` | Governance traceability fields |

`value_bond_forward(...)` uses cost-of-carry mechanics:

```text
Fair forward price = (spot dirty price - PV(coupons before delivery)) / P(0, T)
Long value = face / 100 * (fair forward price - contract price) * P(0, T)
```

The result exposes fair forward price, coupon carry before delivery, delivery
discount factor, market value, valuation measure, curve source, settlement
basis, and limitation ID.

## Starter Fixtures

`default_phase9_derivative_examples()` provides:

- `HKD_PAY_FIXED_5Y_EDU`: five-year HKD pay-fixed interest rate swap.
- `HK_GOVT_10Y_FORWARD_1Y_EDU`: one-year forward on a ten-year HKD government
  bond example.

`value_derivative_portfolio(...)` values both sets of contracts against one
discount curve and returns:

- derivative-level valuation records;
- coupon, swap payment, and settlement schedule rows;
- total derivative market value.

## Governance Notes

- SOA ASOP 7 / ASOP 56: derivative valuation now discloses valuation measure,
  curve source, fixed/floating leg mechanics, coupon carry, and settlement
  timing rather than folding hedge value into an aggregate return.
- IA TAS M: every derivative record carries source and limitation identifiers,
  and valuation records can be reconstructed from contract terms plus the
  discount curve.
- ERM: these examples support first-order hedge and ALM reporting education,
  but omit multi-curve CSA discounting, day-count calendars, reset lag, convexity
  adjustments, optionality, margining, collateral liquidity, counterparty credit
  valuation adjustment, and legal enforceability analysis.

## Validation

Targeted tests in `tests/test_derivative_valuation.py` cover:

- par swap fixed-rate valuation near zero;
- pay-fixed and receive-fixed directionality;
- bond forward fair price valuation near zero;
- long and short bond-forward directionality;
- input validation for notional, dates, prices, and maturity ordering;
- starter fixture coverage and portfolio-level market value aggregation.

## Downstream Reporting

The derivative valuation records now feed
`aggregate_asset_rollforward(...)` in `par_model_v2/projection/asset_reporting.py`.
That report maps swap and bond-forward scheduled settlements into monthly
asset-class attribution while keeping derivative market value separate from
cash settlement activity.
