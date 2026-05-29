# ESG Output Consumer Mapping

**Document ID:** `ESG-OUTPUT-CONSUMER-MAPPING`  
**Created:** 2026-05-30  
**Phase:** Phase 6, Task 4  
**Status:** Implemented baseline for v1-compatible consumer mappings  
**Applies to:** `ScenarioSet`, `TVOGEngine`, `RiskMetrics`, `DynamicALMEngine`, and reporting packs

## 1. Purpose

This document defines how Phase 6 ESG outputs are routed to the model's
current downstream consumers. The implementation keeps the v1 wide
`ScenarioSet.data` columns stable while adding a governed mapping layer in
`par_model_v2.stochastic.esg_process`.

The implemented chain is:

`ScenarioSet` -> `ConsumerOutputMapping` -> `consumer_wide_view` / ALM return mapping / report traceability attrs

## 2. Implemented Mapping Object

`ConsumerOutputMapping` is a frozen dataclass that records:

| Field | Purpose |
| --- | --- |
| `consumer_id` | Stable machine ID, such as `tvog` or `risk_metrics` |
| `consumer_name` | Human-readable consumer name |
| `accepted_measures` | Permitted P/Q measure set |
| `required_columns` | v1 wide scenario columns required before use |
| `factor_ids` | Canonical factor IDs selected for each v1 consumer column |
| `propagated_metadata_fields` | Metadata attrs that reports must carry |
| `output_contract` | Summary of the consumer-facing contract |
| `notes` | Guardrails and implementation notes |

The helper `default_phase6_consumer_mappings(...)` returns the current mapping
set. The helper `phase6_consumer_mapping(...)` returns a single mapping by ID.

## 3. Consumer Contracts

| Consumer ID | Existing consumer | Measure rule | Primary ESG fields |
| --- | --- | --- | --- |
| `tvog` | `TVOGEngine` | `Q` only | `scenario_id`, `month`, `r_short`, `measure` |
| `risk_metrics` | `RiskMetrics` / `LossDistribution` | `P` only | v1 wide view plus projection loss lineage |
| `dynamic_alm` | `DynamicALMEngine` | `P` only | `r_short`, `equity_return_1m` |
| `reporting` | Reporting and audit packs | `P` or `Q`, one set at a time | v1 wide view plus metadata attrs |

Mixed-measure packages remain invalid. Reporting can include both P and Q
outputs only by carrying separate scenario sets, each with its own metadata and
parameter snapshot.

## 4. Wide View and Traceability

`ScenarioSet.consumer_wide_view(consumer_id)` returns a copy of
`ScenarioSet.data` after validating:

1. scenario measure is permitted for the requested consumer;
2. required wide columns are present;
3. `ScenarioMetadata` is attached;
4. `ParameterSnapshot` is attached; and
5. metadata and snapshot IDs match.

The returned DataFrame carries `attrs` for audit and reporting:

- `consumer_id`
- `measure`
- `scenario_set_id`
- `model_version`
- `base_currency`
- `valuation_date`
- `projection_months`
- `n_scenarios`
- `seed_policy`
- `parameter_snapshot_id`
- `calibration_date`
- `approval_status`
- `is_placeholder`
- `limitations_id`

These attrs are deliberately redundant with `ScenarioMetadata` so that report
builders and projected loss tables can preserve ESG lineage even after they
aggregate or transform scenario rows.

## 5. Dynamic ALM Return Mapping

`ScenarioSet.alm_annual_returns(scenario_id, month)` maps one P-measure
scenario-month row into the annual return dictionary expected by
`DynamicALMEngine.step(...)`.

Current educational proxies:

| ALM class | ESG source | Rule |
| --- | --- | --- |
| `Cash` | `r_short` | annual short-rate proxy |
| `Govt` | `r_short` | annual government bond proxy until curve returns are added |
| `Credit` | `r_short` | annual proxy until credit spread/default factors are added |
| `Equity` | `equity_return_1m` | annualized as `(1 + monthly_return)^12 - 1` |

These proxies are suitable for v1 compatibility and tests. Phase 9 should
replace the credit and fixed-income proxies with richer asset-class factors.

## 6. Governance Notes

- SOA ASOP 56 scenario documentation is supported by explicit factor IDs,
  measure rules, model version, seed policy, parameter snapshot ID, and
  limitation references.
- IA TAS M traceability is supported by preserving scenario metadata through
  DataFrame attrs and consumer-specific validation before use.
- Placeholder parameter snapshots still block production use through
  `is_placeholder=True`; the mapping layer does not override that restriction.
- `RiskMetrics` must continue to reject Q-measure loss distributions. The
  mapping layer catches invalid ESG lineage before projected losses are built.

## 7. Acceptance Evidence

Targeted tests are in `tests/test_esg_process.py`:

- default mappings cover TVOG, risk metrics, dynamic ALM, and reporting;
- TVOG accepts Q-measure scenarios and rejects P-measure scenarios;
- risk metrics accepts P-measure scenarios and rejects Q-measure scenarios;
- consumer wide views preserve scenario-set and parameter-snapshot attrs;
- dynamic ALM returns are derived from the correct scenario row; and
- mapping serialization is JSON-ready for audit records.

## 8. Next Task

The next Phase 6 task is to add design documentation and acceptance tests for
schema compatibility. That task should connect the metadata, calibration
interface, and consumer mapping contracts into one compatibility test plan
covering v1 wide views, P/Q guardrails, metadata propagation, and monthly grid
completeness.
