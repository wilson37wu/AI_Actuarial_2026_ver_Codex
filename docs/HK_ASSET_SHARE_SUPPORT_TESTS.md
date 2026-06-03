# Hong Kong Asset-Share Support Tests

**Document ID:** `PHASE10-HK-ASSET-SHARE-SUPPORT-TESTS`  
**Created:** 2026-06-03  
**Status:** Phase 10 task 4 implementation note  
**Scope:** Deterministic educational asset-share support tests for Hong Kong cash dividend and reversionary bonus product variants.

## Purpose

This Phase 10 task connects the Hong Kong participating product variants to
the existing monthly asset-share recursion.  The support tests are deterministic
diagnostics for the educational fixtures.  They are not board declaration
rules, PRE policy, regulatory supportability evidence, or stochastic TVOG.

The implementation is in `par_model_v2/projection/hk_participating.py`.

## Implemented API

The support layer adds:

| Helper | Purpose |
|---|---|
| `default_hk_asset_share_fund_positions()` | Starter deterministic ALM fund mix used by the support tests |
| `HKAssetShareSupportReport` | JSON-ready report wrapper with final margin, ratio, and pass/fail status |
| `hk_cash_dividend_asset_share_support_test(...)` | Runs a cash dividend policy through deterministic asset share and compares annual asset share to cumulative declared cash dividends |
| `hk_reversionary_bonus_asset_share_support_test(...)` | Runs a reversionary bonus policy through deterministic asset share and compares annual asset share to vested bonus plus maturity terminal bonus target |

The support basis ID is
`PHASE10-HK-ASSET-SHARE-SUPPORT-BASE-2026`.

## Cash Dividend Test

Cash dividends are non-guaranteed annual cash payments.  The support test:

1. converts the sample cash dividend policy to the deterministic guaranteed
   base projection product;
2. runs the existing monthly asset-share recursion;
3. builds the declaration-aware annual cash dividend schedule;
4. compares each annual asset-share value with cumulative declared cash
   dividends.

```text
support_obligation = cumulative declared cash dividends
support_margin = asset_share_eom - support_obligation
support_ratio = asset_share_eom / support_obligation
```

## Reversionary Bonus Test

Reversionary bonuses vest after declaration.  Terminal bonus remains
non-guaranteed and is tested only at maturity in this deterministic layer.

```text
terminal_bonus_support_target =
    asset_share_eom * declared_terminal_bonus_pct at maturity, otherwise 0

support_obligation =
    vested_bonus_balance + terminal_bonus_support_target
```

The annual rows keep `vested_bonus_balance`, terminal bonus target, support
margin, support ratio, declaration assumption ID, sensitivity label, mechanics
source ID, and limitation ID.

## Sensitivity Use

The support tests consume `HKDeclarationAssumption`.  A lower declared dividend
or bonus assumption reduces the support obligation without mutating product
mechanics:

```python
down = hk_declaration_sensitivity(
    "BONUS_DOWN",
    reversionary_bonus_rate_multiplier=0.80,
    terminal_bonus_pct_multiplier=0.50,
)
report = hk_reversionary_bonus_asset_share_support_test(policy, declaration_assumption=down)
```

## Governance Notes

- SOA ASOP 56: support diagnostics are linked to explicit product mechanics,
  declaration assumptions, and deterministic projection outputs.
- IA TAS M: support rows preserve policy ID, product code, assumption ID,
  source ID, sensitivity label, and limitation ID for audit reconstruction.
- ERM: this is a first-order deterministic test only.  It does not prove
  stochastic supportability, management-action feasibility, liquidity, PRE
  consistency, or policyholder-behaviour impacts.

## Validation

Targeted tests in `tests/test_hk_participating_products.py` cover:

- default fund mix construction;
- cash dividend support obligations matching cumulative declared dividends;
- cash dividend down-sensitivity improving support margin;
- reversionary bonus support obligations including vested bonus and maturity
  terminal bonus target;
- reversionary bonus down-sensitivity improving support margin.

## Follow-on Reporting Views

The liability reporting views for reserves, TVOG, bonus supportability, and
management summaries are documented in
`docs/HK_LIABILITY_REPORTING_VIEWS.md`.  They consume
`HKAssetShareSupportReport` rather than recalculating support margins.
