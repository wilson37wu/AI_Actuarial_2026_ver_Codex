# ESG Scenario Schema Compatibility — Acceptance Design (Phase 6, Task 5)

**Status:** Implemented
**Owner:** Automated model development cycle
**Module under test:** `par_model_v2.stochastic.esg_process`
**Acceptance suite:** `tests/test_schema_compatibility.py`
**Standards:** SOA ASOP 56 §3.1.3 / §3.4 / §3.5; IA TAS M §3.5 / §3.6 / §3.9

## 1. Purpose

Phase 6 added three contracts to the economic scenario generator:

1. scenario metadata + parameter snapshot (`ScenarioMetadata`, `ParameterSnapshot`),
2. calibration data interfaces (`CalibrationDataInterface`, `default_phase6_calibration_interfaces`), and
3. consumer output mappings (`ConsumerOutputMapping`, `default_phase6_consumer_mappings`).

These additions must not break the v1 wide-view contract that the existing
TVOG, RiskMetrics, DynamicALM, reporting, and ESGAdapter consumers depend on.
This document defines the acceptance test plan that proves backward
compatibility and closes Phase 6.

## 2. Compatibility Invariants

| # | Invariant | Acceptance check |
| - | --------- | ---------------- |
| I1 | Generated scenario sets retain all v1 wide columns (`_V1_WIDE_COLUMNS`). | `TestV1WideViewBackwardCompatibility::test_generated_set_contains_all_v1_columns` |
| I2 | Generated output still passes the v1 `ESGAdapter` schema/dtype/range validation. | `..::test_generated_set_passes_v1_esg_adapter` |
| I3 | Every consumer wide view remains v1-schema valid. | `..::test_consumer_wide_views_pass_v1_adapter` |
| I4 | TVOG accepts Q only; RiskMetrics and DynamicALM accept P only; reporting accepts both. | `TestMeasureGuardrails::*` |
| I5 | All traceability fields propagate into consumer view `attrs`. | `TestMetadataPropagation::test_all_traceability_fields_present_in_view_attrs` |
| I6 | Metadata/parameter-snapshot ID mismatch is rejected before consumer use. | `..::test_metadata_snapshot_id_consistency_enforced` |
| I7 | Monthly grid is complete: `n*(T+1)` rows, months `0..T` per scenario, single measure label. | `TestGridCompleteness::*` |
| I8 | Calibration interfaces are JSON-serialisable and expose required columns. | `TestCalibrationInterfaceConsistency::*` |
| I9 | DynamicALM annual returns derive from the correct scenario row with the documented equity annualisation. | `TestDynamicALMReturns::*` |
| I10 | Default mappings cover all v1 consumers. | `test_default_mappings_cover_all_v1_consumers` |

## 3. Why ESGAdapter is the compatibility oracle

`ESGAdapter._REQUIRED_COLUMNS` is the canonical v1 input contract every
downstream consumer ultimately relies on. The acceptance suite feeds Phase 6
generated output (and each consumer wide view) back through
`ESGAdapter.load_from_dataframe`. A pass proves the expanded schema is a
strict superset of the v1 contract — new metadata is carried out-of-band (in
`DataFrame.attrs` and the metadata/snapshot objects), never by mutating the
v1 column set or dtypes.

## 4. Measure Guardrails

The suite asserts the P/Q separation required by ASOP 56 Deviation D-04
remediation: market-consistent TVOG consumes Q only, real-world RiskMetrics
and DynamicALM consume P only, and reporting may carry either measure but each
set remains single-measure and separately traced.

## 5. Test Scale and Determinism

Acceptance runs use `N_SCEN=8`, `T_MONTHS=6`, `seed=7`, with adapter
scenario-adequacy warnings disabled (unit scale, not production). Production
scenario-count minimums (ASOP 56 §3.5: 500 TVOG / 2000 VaR) remain enforced by
the default `ESGAdapterConfig` and are unchanged by this suite.

## 6. Result

`tests/test_schema_compatibility.py`: 18 passed. Full repository suite: 928
passed, 0 failed (see `docs/G05_RUNTIME_TEST_EVIDENCE_*.md`). Phase 6 is
complete; Phase 7 (negative-rate-capable interest-rate ESG) is next.
