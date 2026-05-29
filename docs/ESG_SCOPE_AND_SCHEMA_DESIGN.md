# ESG Scope and Scenario Schema Design

**Document ID:** `ESG-SCOPE-SCHEMA-DESIGN`  
**Created:** 2026-05-29  
**Phase:** Phase 6, Task 1  
**Status:** Design baseline for post-v1 ESG expansion  
**Applies to:** `ScenarioSet`, `ESGAdapter`, `TVOGEngine`, `RiskMetrics`, and ALM projection consumers

## 1. Purpose

This document defines the first post-v1 economic scenario generator (ESG)
scope and scenario schema. The goal is to support multi-market, multi-risk
factor scenario sets without breaking existing v1 consumers that expect the
current `ScenarioSet.data` DataFrame columns:

- `scenario_id`
- `month`
- `r_short`
- `zcb_1y`
- `zcb_10y`
- `equity_index`
- `equity_return_1m`
- `measure`

The Phase 6 design principle is to keep current consumers working through a
legacy-compatible wide view while adding enough schema structure for later
interest-rate, equity, FX, credit, asset, liability, and reporting expansion.

## 2. Scope Requirements

### 2.1 Supported Measures

Every scenario set must declare exactly one probability measure.

| Measure | Use | Consumer guardrail |
| --- | --- | --- |
| `P` | Real-world ALM, ERM, VaR/ES, bonus and management action analysis | Required by `RiskMetrics`; unsuitable for market-consistent TVOG |
| `Q` | Risk-neutral TVOG, MCEV-style option valuation, market-consistent pricing | Required by `TVOGEngine`; unsuitable for VaR/ES |

Mixed-measure scenario sets are not permitted. If a reporting pack requires
both `P` and `Q`, it must hold two separate scenario sets with separate
metadata, parameter snapshots, validation evidence, and run identifiers.

### 2.2 Starter Markets and Currencies

The initial multi-market scope is deliberately narrow enough for educational
use while covering the major risk dimensions needed by the roadmap.

| Market group | Currency | Initial use |
| --- | --- | --- |
| United States | USD | Risk-free curve, equity, FX translation reference |
| Eurozone / Europe | EUR | Risk-free curve, equity, FX translation |
| Hong Kong | HKD | Risk-free curve, HK participating liability reporting, peg/basis note |
| Mainland China | CNY | Continuity with v1 examples and CNY liability projections |
| Japan | JPY | Risk-free curve, equity, low/negative-rate examples |
| Asia ex-Japan | Mixed / USD proxy | Equity return proxy and regional correlation example |

The schema must not assume that the base reporting currency equals the factor
currency. `base_currency` belongs at scenario-set level; `currency` belongs at
risk-factor level.

### 2.3 Starter Risk Factors

| Factor type | Examples | Minimum scenario fields |
| --- | --- | --- |
| Risk-free rates | USD short rate, HKD discount curve node, JPY forward rate | annualized rate, curve tenor, compounding basis |
| Discount factors | 1Y and 10Y zero-coupon prices | price, tenor |
| Public equity | US equity index, HK/China equity index | index level, monthly return, dividend yield basis |
| FX | USD/HKD, USD/CNY, EUR/USD, USD/JPY | spot rate, monthly return, quotation convention |
| Credit spreads | Corporate spread by rating or broad index | spread, rating bucket, tenor |
| Correlation | Cross-factor correlation matrix | factor IDs, matrix version, validation status |

Phase 6 Task 1 only defines the scenario schema. Later phases implement richer
generators, calibrators, and validation routines against this contract.

## 3. Canonical Scenario Package

A complete scenario package should contain four logical tables. They may live
as DataFrames, CSV files, Parquet files, JSON documents, or in-memory objects,
but the semantics should be stable.

### 3.1 `scenario_set`

One row per generated scenario set.

| Field | Required | Description |
| --- | --- | --- |
| `scenario_set_id` | Yes | Stable ID linking data, metadata, parameters, and reports |
| `model_version` | Yes | Model release or commit identifier |
| `measure` | Yes | `P` or `Q`; one value per scenario set |
| `base_currency` | Yes | Reporting currency, for example `HKD` or `CNY` |
| `valuation_date` | Yes | Date at time 0 |
| `projection_months` | Yes | Maximum projection horizon in months |
| `time_step_months` | Yes | Time grid spacing; v1 consumers use `1` |
| `n_scenarios` | Yes | Number of scenario paths |
| `seed_policy` | Yes | Seed value or policy for reproducibility |
| `parameter_snapshot_id` | Yes | Link to calibration and parameter snapshot |
| `generator_name` | Yes | ESG implementation name |
| `generator_version` | Yes | ESG implementation version |
| `limitations_id` | Yes | Link to known limitations and unsuitable uses |

### 3.2 `risk_factor_catalog`

One row per modeled risk factor.

| Field | Required | Description |
| --- | --- | --- |
| `factor_id` | Yes | Stable machine name, for example `RATE_SHORT_HKD` |
| `factor_type` | Yes | `rate`, `discount_factor`, `equity`, `fx`, `credit_spread`, or `correlation` |
| `market` | Yes | Market group such as `HK`, `US`, `EU`, `CN`, `JP`, `ASIA_EX_JP` |
| `currency` | Conditional | Required unless factor is a pure correlation object |
| `unit` | Yes | `decimal_rate`, `index_level`, `price`, `fx_rate`, `spread_bp`, etc. |
| `tenor` | Conditional | Required for curve, spread, and discount-factor fields |
| `quotation` | Conditional | Required for FX pairs and spread conventions |
| `description` | Yes | Human-readable factor description |

### 3.3 `scenario_observation`

Long-form table with one row per scenario, month, and factor observation.

| Field | Required | Description |
| --- | --- | --- |
| `scenario_set_id` | Yes | Parent scenario set |
| `scenario_id` | Yes | 1-based integer scenario identifier |
| `month` | Yes | 0-based projection month |
| `time_years` | Yes | `month / 12` for monthly grids |
| `measure` | Yes | Repeated guard field; must match `scenario_set.measure` |
| `factor_id` | Yes | Link to `risk_factor_catalog.factor_id` |
| `value_type` | Yes | `level`, `return_1m`, `discount_factor`, `shock`, etc. |
| `value` | Yes | Numeric value |
| `source_model` | Yes | Generator/process that produced the value |
| `parameter_snapshot_id` | Yes | Repeated traceability guard |

This long-form table is the canonical multi-market structure because it can
add markets, tenors, and risk factors without adding new hardcoded DataFrame
columns for each expansion.

### 3.4 `consumer_wide_view`

Existing v1 consumers should receive a derived wide view with stable columns.
The first compatibility view is:

| Column | Source factor |
| --- | --- |
| `scenario_id` | `scenario_observation.scenario_id` |
| `month` | `scenario_observation.month` |
| `r_short` | Selected base-currency short-rate factor |
| `zcb_1y` | Selected base-currency 1Y discount factor |
| `zcb_10y` | Selected base-currency 10Y discount factor |
| `equity_index` | Selected reference equity index level |
| `equity_return_1m` | Selected reference equity monthly return |
| `measure` | `scenario_set.measure` |

For v1 compatibility, the default selected factors should continue to represent
the CNY single-market example unless a caller explicitly asks for another
market view.

## 4. Minimum Schema Rules

1. `scenario_id` must be positive, integer-compatible, and dense within a
   scenario set.
2. `month` must be non-negative, integer-compatible, and include month 0 for
   every scenario.
3. `measure` must be either `P` or `Q`; no nulls and no mixed measures within a
   scenario set.
4. `base_currency` and factor `currency` must use ISO-style three-letter
   currency codes where applicable.
5. Every observation must link to a declared `factor_id`.
6. Every scenario set must link to a parameter snapshot before it is consumed
   by TVOG, ALM, risk, or reporting.
7. Long-form observations must be convertible to the v1 `consumer_wide_view`
   whenever the selected factor set includes short rate, 1Y discount factor,
   10Y discount factor, equity index, and equity monthly return.
8. Q-measure wide views must be accepted by `TVOGEngine` and rejected for
   `RiskMetrics` VaR/ES use.
9. P-measure wide views must be accepted for ALM and `RiskMetrics` use and
   rejected for market-consistent TVOG.
10. Scenario packages used in reporting must preserve model version,
    valuation date, calibration date, generator version, seed policy, and
    known limitations for audit trail reconstruction.

## 5. Compatibility With Existing Consumers

### 5.1 `ScenarioSet`

Current `ScenarioSet` can remain the in-memory compatibility object. In Phase
6, it should be treated as the `consumer_wide_view` plus basic scenario-set
metadata:

- `data`: existing wide DataFrame.
- `n_scenarios`: scenario count.
- `T_months`: projection horizon.
- `measure`: single `Measure` enum value.
- `seed`: reproducibility input.

Future work should add optional `scenario_set_id`, `base_currency`,
`valuation_date`, and `parameter_snapshot_id` without removing current fields.

### 5.2 `ESGAdapter`

`ESGAdapter` currently validates the v1 wide schema. The Phase 6 adapter path is:

1. Keep current wide-schema validation for v1 and vendor-style CNY files.
2. Add a separate validator for canonical long-form packages.
3. Add a deterministic transform from canonical long form to v1 wide view.
4. Require explicit factor selection when more than one market can satisfy a
   consumer column, for example selecting HKD vs CNY `r_short`.

### 5.3 `TVOGEngine`

`TVOGEngine` requires Q-measure scenarios and consumes `r_short` by
`scenario_id` and `month`. The schema must provide a Q-measure wide view with a
base-currency short-rate path covering the product term.

Additional future TVOG variants can consume:

- full discount curves instead of short-rate-only discounting;
- currency-specific discounting for multi-currency benefits;
- equity or credit factors for dynamic bonus and management-action modelling.

### 5.4 `RiskMetrics`

`RiskMetrics` consumes a `LossDistribution`, not raw ESG paths, but it enforces
P-measure use. The scenario schema must carry P-measure metadata through the
projection output so `LossDistribution.from_scenario_pv()` can confirm that the
input loss distribution was derived from P-measure paths.

### 5.5 ALM Consumers

The current `DynamicALMEngine` accepts deterministic annual returns by asset
class. A stochastic adapter can convert scenario observations into per-period
asset-class return dictionaries:

- `Govt`: base-currency risk-free or bond total-return proxy.
- `Credit`: risk-free rate plus credit-spread and default-loss proxy.
- `Equity`: selected regional equity monthly return.
- `Cash`: short-rate or cash account return.

The schema must therefore support both factor-level returns and consumer-level
asset-class mappings.

## 6. Acceptance Test Plan

Phase 6 schema compatibility should be accepted by targeted tests before
deeper model implementation begins.

| Test ID | Purpose | Expected result |
| --- | --- | --- |
| `ESG-SCHEMA-01` | Validate required scenario-set metadata fields | Missing measure, base currency, valuation date, or parameter snapshot fails |
| `ESG-SCHEMA-02` | Reject mixed P/Q measures within one scenario set | Validation error before consumer use |
| `ESG-SCHEMA-03` | Validate long-form factor catalog references | Unknown `factor_id` fails |
| `ESG-SCHEMA-04` | Convert canonical long form to v1 wide view | Wide DataFrame has current `ESGAdapter.required_columns()` plus `equity_return_1m` |
| `ESG-SCHEMA-05` | Feed Q-measure wide view to `TVOGEngine` | Accepted when horizon and scenario count are adequate |
| `ESG-SCHEMA-06` | Feed P-measure wide view to `RiskMetrics` after projection | Accepted for VaR/ES loss distribution |
| `ESG-SCHEMA-07` | Feed Q-measure loss distribution to `RiskMetrics` | Rejected by existing measure guard |
| `ESG-SCHEMA-08` | Select market-specific base curve for a wide view | Ambiguous market selection fails with a clear error |
| `ESG-SCHEMA-09` | Preserve audit traceability fields through view conversion | Scenario set ID and parameter snapshot ID remain attached |
| `ESG-SCHEMA-10` | Validate monthly grid completeness | Missing month 0 or ragged scenario horizon fails |

## 7. Next Design Task

The next Phase 6 task should define the scenario metadata and parameter
snapshot structure in more detail. That task should formalize:

- parameter ownership and approval fields;
- calibration source tables for curves, equity indices, FX, credit spreads, and
  correlations;
- model equation and discretisation references;
- model limitations and unsuitable-use disclosures;
- audit trail fields linking scenario generation to downstream output reports.

