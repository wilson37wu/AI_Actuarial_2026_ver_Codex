# ESG Metadata and Parameter Snapshot Design

**Document ID:** `ESG-METADATA-PARAMETER-SNAPSHOT-DESIGN`  
**Created:** 2026-05-29  
**Phase:** Phase 6, Task 2  
**Status:** Implemented baseline for v1-compatible `ScenarioSet` metadata  
**Applies to:** `par_model_v2.stochastic.esg_process.ScenarioSet`

## 1. Purpose

This document defines the scenario metadata and parameter snapshot structure
used by the post-v1 ESG expansion. The design keeps the existing wide
`ScenarioSet.data` table unchanged for TVOG, risk, ALM, and adapter consumers,
while adding governed metadata records that make a generated scenario package
traceable.

The minimum traceability chain is:

`ScenarioSet` -> `ScenarioMetadata` -> `ParameterSnapshot` -> `CalibrationSource`

## 2. Scenario Metadata

`ScenarioMetadata` is a scenario-set level record. It describes the package
that downstream consumers are using, not the individual path observations.

Required fields:

| Field | Purpose |
| --- | --- |
| `scenario_set_id` | Stable package identifier for audit trail and reports |
| `model_version` | Model version or commit identifier |
| `measure` | Single `P` or `Q` measure for the whole set |
| `base_currency` | Reporting currency used by the v1-compatible wide view |
| `valuation_date` | Time-zero date for the scenario set |
| `projection_months` | Maximum projection horizon |
| `time_step_months` | Scenario time grid spacing; currently `1` |
| `n_scenarios` | Number of paths generated |
| `seed_policy` | Reproducibility rule, for example `fixed-seed:42` |
| `parameter_snapshot_id` | Link to the parameter basis used for generation |
| `generator_name` | Generator implementation name |
| `generator_version` | Generator contract version |
| `limitations_id` | Link to limitations and unsuitable-use disclosures |

Validation rules:

- `measure` is coerced to the model `Measure` enum and must be `P` or `Q`.
- `base_currency` must be an ISO-style three-letter code.
- `projection_months` must be a non-negative integer.
- `time_step_months` and `n_scenarios` must be positive integers.
- If a `ParameterSnapshot` is attached, its snapshot ID, measure, and base
  currency must match the scenario metadata record.

## 3. Parameter Snapshot

`ParameterSnapshot` is the governed parameter basis used to generate a scenario
set. It is separate from `ScenarioMetadata` so a snapshot can be approved,
reused, compared, or retired independently of a specific simulation run.

Required fields:

| Field | Purpose |
| --- | --- |
| `snapshot_id` | Stable parameter package identifier |
| `calibration_date` | As-of date for all included parameters |
| `measure` | `P` or `Q`; must match the scenario set using it |
| `base_currency` | Currency basis for the wide view and selected curve |
| `parameters` | Named finite parameter values |
| `sources` | Calibration or placeholder data sources |
| `created_at` | UTC creation timestamp |
| `owner` | Assumption or model owner |
| `approver` | Optional approval owner |
| `approval_status` | `draft`, `approved`, `retired`, or local workflow value |
| `model_equation_refs` | Code references for equations using the parameters |
| `discretisation` | Time-step and numerical method description |
| `limitations_id` | Link to known limitations |
| `is_placeholder` | Blocks production use when true |

The current implementation adds `ParameterSnapshot.from_process_params(...)`
to build a placeholder snapshot from the existing `HullWhiteParams` and
`GBMParams` dataclasses. This keeps Phase 6 design compatible with the current
educational ESG while preserving a path to later market-calibrated snapshots.

## 4. Calibration Source

`CalibrationSource` is a governed reference to a curve, equity index, FX,
credit spread, correlation matrix, or placeholder parameter source.

Required fields:

| Field | Purpose |
| --- | --- |
| `source_id` | Stable source identifier |
| `source_type` | Curve, equity, FX, spread, correlation, or placeholder |
| `market` | Market group, for example `HK`, `US`, `CN`, or `JPY` |
| `currency` | Three-letter currency code where applicable |
| `as_of_date` | Source data date |
| `provider` | Vendor, public source, or internal owner |
| `dataset_name` | Named dataset or table |
| `version` | Dataset version |
| `reliability_tier` | Credibility and governance tier |
| `approval_status` | Source approval state |

## 5. Compatibility

`ScenarioSet.generate(...)` now accepts optional metadata inputs:

- `scenario_set_id`
- `model_version`
- `base_currency`
- `valuation_date`
- `parameter_snapshot`

All existing positional calls remain valid. If no parameter snapshot is
provided, the generator creates a placeholder snapshot from the supplied
process parameters and attaches both:

- `ScenarioSet.metadata`
- `ScenarioSet.parameter_snapshot`

The wide `ScenarioSet.data` columns are unchanged. Existing consumers can
continue to operate without reading the new metadata fields.

## 6. Governance Notes

- Q-measure metadata supports TVOG and market-consistent pricing workflows.
- P-measure metadata supports ALM, VaR/ES, bonus, and management-action
  workflows.
- Mixed-measure packages remain disallowed by consumer guardrails and by the
  scenario metadata/snapshot consistency checks.
- Placeholder snapshots must not be used for production reporting. They are
  educational scaffolding until Phase 7 and later calibration interfaces add
  market data sources.

## 7. Acceptance Evidence

The targeted metadata tests are in `tests/test_esg_process.py`:

- Generated `ScenarioSet` objects include `ScenarioMetadata`.
- Generated metadata links to the attached `ParameterSnapshot`.
- Custom base currency, valuation date, model version, and scenario-set ID are
  preserved.
- Bad currency codes are rejected.
- Empty parameter snapshots are rejected.
- Metadata rejects parameter snapshots with mismatched measure or currency.
- `to_dict()` outputs are JSON-ready for later audit trail and report storage.

## 8. Next Task

The next Phase 6 task is to define calibration data interfaces for curves,
equity indices, FX, credit spreads, and correlations. That task should replace
the placeholder source with explicit input contracts for market data and
historical data loaders.
