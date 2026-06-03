# Hong Kong Declaration Assumptions and Sensitivities

**Document ID:** `PHASE10-HK-DECLARATION-ASSUMPTIONS`  
**Created:** 2026-06-03  
**Status:** Phase 10 task 3 implementation note  
**Scope:** Educational declaration assumptions and sensitivity hooks for Hong Kong cash dividend and reversionary bonus products.

## Purpose

This Phase 10 task separates product mechanics from run-level declarations.
Cash dividend and reversionary bonus mechanics still define the illustrated
contract rates, but `HKDeclarationAssumption` now controls the rates declared
for a model run.  This gives later asset-share supportability, TVOG, and
management-reporting tasks an explicit assumption record to consume.

The implementation is in `par_model_v2/projection/hk_participating.py`.

## Implemented Assumption Record

`HKDeclarationAssumption` contains:

| Field | Purpose |
|---|---|
| `assumption_id` | Stable identifier for the declaration basis |
| `basis_name` | Human-readable basis name |
| `sensitivity_label` | Scenario or stress label, such as `BASE` or `DIV_DOWN_50` |
| `cash_dividend_rate_multiplier`, `cash_dividend_rate_shift` | Cash dividend sensitivity hooks |
| `reversionary_bonus_rate_multiplier`, `reversionary_bonus_rate_shift` | Reversionary bonus sensitivity hooks |
| `terminal_bonus_pct_multiplier`, `terminal_bonus_pct_shift` | Terminal bonus sensitivity hooks |
| `min_declared_rate`, `max_declared_rate` | Declaration rate floor and cap |
| `min_terminal_bonus_pct`, `max_terminal_bonus_pct` | Terminal bonus floor and cap |
| `source_id`, `limitation_id` | Audit trail and limitation markers |

The base declaration preserves current illustrated mechanics:

```text
declared_cash_dividend_rate = annual_cash_dividend_rate
declared_reversionary_bonus_rate = annual_reversionary_bonus_rate
declared_terminal_bonus_pct = terminal_bonus_pct
```

Sensitivity hooks apply a multiplier and additive shift, then enforce the
assumption floor and cap:

```text
declared_rate = min(max(base_rate * multiplier + shift, floor), cap)
```

## Schedule Integration

The following helpers now accept an optional `declaration_assumption` argument:

- `sample_hk_cash_dividend_policy_table(...)`
- `annual_cash_dividend_schedule(...)`
- `sample_hk_reversionary_bonus_policy_table(...)`
- `annual_reversionary_bonus_schedule(...)`
- `reversionary_bonus_guarantee_split(...)`

When no assumption is supplied, `default_hk_declaration_assumption()` is used.
This preserves existing base-case outputs while adding declaration traceability
columns including assumption ID, basis name, sensitivity label, declared rate,
and declaration source ID.

## Sensitivity Examples

`hk_declaration_sensitivity(...)` creates a named copy of the base basis:

```python
dividend_down = hk_declaration_sensitivity(
    "DIV_DOWN_50",
    cash_dividend_rate_multiplier=0.50,
)
```

For the starter `HKCD000001` cash dividend policy, this reduces the declared
annual cash dividend rate from 1.20% to 0.60%, while preserving the non-
guaranteed cash dividend status.

```python
bonus_down = hk_declaration_sensitivity(
    "BONUS_DOWN",
    reversionary_bonus_rate_multiplier=0.80,
    terminal_bonus_pct_multiplier=0.50,
)
```

For the starter `HKRB000001` reversionary bonus policy, this reduces the
annual vested bonus declaration from 2.50% to 2.00% and terminal bonus from
35.00% to 17.50%.

## Governance Notes

- SOA ASOP 56: declaration assumptions are explicit, bounded, source-tagged,
  and separated from product mechanics.
- IA TAS M: the assumption ID, source ID, sensitivity label, and limitation ID
  are included in schedule outputs for audit reconstruction.
- ERM: the current declaration basis remains educational.  It is not calibrated
  to PRE policy, board minutes, insurer filings, or supportability analysis.

## Validation

Targeted tests in `tests/test_hk_participating_products.py` cover:

- base declarations preserving mechanics rates;
- invalid negative sensitivity multipliers;
- cash dividend sensitivities flowing into schedules and sample tables;
- reversionary bonus and terminal bonus sensitivities flowing into schedules
  and guarantee splits.

## Next Phase 10 Task

The next task is to add asset-share support tests for cash dividend and
reversionary bonus variants.  Those tests should consume the explicit
declaration assumption record added here rather than changing product mechanics
directly.
