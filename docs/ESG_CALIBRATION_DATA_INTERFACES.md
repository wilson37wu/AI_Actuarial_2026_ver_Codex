# ESG Calibration Data Interfaces

**Document ID:** `ESG-CALIBRATION-DATA-INTERFACES`  
**Created:** 2026-05-29  
**Phase:** Phase 6, Task 3  
**Status:** Implemented baseline for governed calibration input contracts  
**Applies to:** `par_model_v2.stochastic.esg_process`

## 1. Purpose

This document defines the Phase 6 calibration data interfaces for the expanded
multi-market ESG. The interfaces sit between raw market or historical data and
`ParameterSnapshot` records, so each stochastic parameter package can identify
the required source tables, column semantics, credibility rules, and approval
expectations before downstream TVOG, ALM, VaR/ES, or reporting use.

The implemented traceability chain is:

`CalibrationDataInterface` -> `CalibrationSource` -> `ParameterSnapshot` -> `ScenarioMetadata`

## 2. Implemented Interface Objects

The implementation adds two frozen dataclasses:

| Object | Purpose |
| --- | --- |
| `CalibrationFieldSpec` | Defines a required or optional column, expected type, value range, unit, and allowed values. |
| `CalibrationDataInterface` | Defines a full source-table contract for one source type, market, currency, measure scope, history depth, provider rule, and approval requirement. |

The helper `default_phase6_calibration_interfaces()` returns the starter
interfaces for USD, EUR, HKD, CNY, JPY, Asia ex-Japan equity, credit spreads,
FX, and cross-factor correlations.

## 3. Source Types

| Source type | Starter use | Required core fields |
| --- | --- | --- |
| `curve` | Risk-free curve and discount-factor calibration | `date`, `tenor_years`, `zero_rate` |
| `equity_index` | Equity volatility, drift, dividend, and backtest inputs | `date`, `index_level` |
| `fx` | Currency translation and FX return calibration | `date`, `pair`, `spot_rate`, `quotation` |
| `credit_spread` | Spread scenarios, default-loss proxies, and stress calibration | `date`, `rating`, `tenor_years`, `spread_bp` |
| `correlation` | Cross-factor Cholesky input and PSD validation evidence | `as_of_date`, `factor_id_1`, `factor_id_2`, `correlation`, `matrix_version` |

`parameter_placeholder` remains valid only for legacy educational
`CalibrationSource` records created from current default process parameters. It
is not accepted as a real `CalibrationDataInterface` source type.

## 4. Validation Rules

Each interface can validate an in-memory `pandas.DataFrame` through
`validate_frame(...)`.

Minimum checks:

1. Required columns must be present.
2. Required numeric fields must parse to finite numbers.
3. Numeric range bounds are enforced where specified.
4. Date fields must parse as dates.
5. Required string fields must be non-blank.
6. Enumerated strings, such as FX quotation convention, must match allowed
   values.
7. Minimum observation counts are enforced for historical inputs.
8. Duplicate field names within one interface are rejected.

The checks are intentionally structural in Phase 6. Later phases should add
domain-specific validators for curve monotonicity, discount-factor consistency,
FX quotation inversion, credit spread transitions, and correlation matrix
positive-semidefinite status.

## 5. Parameter Snapshot Linkage

`ParameterSnapshot` now carries optional `calibration_interfaces` alongside
`sources`. For generated placeholder scenarios, the default Phase 6 interface
set is attached automatically so reports can distinguish:

- source records actually used by the current educational placeholder run; and
- governed input contracts that future market-calibrated snapshots must satisfy.

This keeps current v1-compatible scenarios operational while making the
upgrade path explicit for Phase 7 and Phase 8 implementation.

## 6. Governance Notes

- SOA ASOP 56 calibration documentation is supported through explicit source
  types, parameter snapshot links, value-range checks, and provider
  requirements.
- IA TAS M traceability is supported by stable interface IDs, source IDs,
  approval flags, and JSON-ready `to_dict()` output.
- P-measure and Q-measure requirements remain separate through each
  interface's `measure_scope`.
- Placeholder sources remain blocked from production use by
  `ParameterSnapshot.is_placeholder`.

## 7. Acceptance Evidence

Targeted tests are in `tests/test_esg_process.py`:

- default interfaces cover curve, equity index, FX, credit spread, and
  correlation source types;
- curve data validates required fields and rejects out-of-range zero rates;
- FX data rejects invalid quotation conventions;
- correlation data rejects values outside `[-1, 1]`;
- duplicate field specs are rejected;
- generated parameter snapshots include default Phase 6 interface IDs.

## 8. Consumer Mapping Linkage

Phase 6 Task 4 is implemented in
`docs/ESG_OUTPUT_CONSUMER_MAPPING.md` and
`par_model_v2.stochastic.esg_process`.

The consumer mapping layer defines factor selections, wide-view requirements,
measure guardrails, ALM return proxies, and audit metadata propagation for
TVOG, VaR/ES, DynamicALMEngine, and reporting consumers. The next Phase 6 task
should add design documentation and acceptance tests for schema compatibility
across all Phase 6 contracts.


## 10. Live Market-Data Pipeline (Roadmap #1, MR-006 — added 2026-07-03)

`par_model_v2/calibration/live_market_data_pipeline.py` implements the first
governed ingestion path from raw market data into the Section-2 contracts:

| Loader | Contract | Fixture (offline default) |
| --- | --- | --- |
| `CNYYieldCurveLoader` (`cny_yield_curve`) | `CalibrationDataInterface.risk_free_curve("CN","CNY")` | `fixtures/cny_yield_curve_20260101.json` (11 tenors, all ≤ 3.0% CBIRC cap) |
| `CSI300IndexLoader` (`csi300_index`) | `CalibrationDataInterface.equity_index("CN","CNY")` | `fixtures/csi300_index_history_20260101.json` (522 seeded-proxy daily closes) |

**Provenance tiers** resolved by `load(as_of, refresh)`, in order:

1. `live_fetch` — injected `fetcher(as_of) -> list[dict]` vendor adapter
   (Wind / ChinaBond / Bloomberg). Payloads are schema-validated **before**
   caching; failed validation is never cached. Lineage `approved_by` is
   `UNSIGNED_PENDING_OWNER_APPROVAL` — live sources are never self-approved.
2. `cached_snapshot` — SHA-256-sealed JSON snapshots (`SnapshotCache`);
   integrity re-verified on every read, tamper raises
   `SnapshotIntegrityError` and the loader falls through to the fixture tier.
3. `file_fixture` — versioned educational fixtures (CI/offline default).

Every load returns a `MarketDataResult` (validated DataFrame + snapshot path
+ payload SHA-256 + `DataLineageRecord`), keeping the
`CalibrationDataInterface → CalibrationSource → ParameterSnapshot` chain
traceable per IA TAS M §3.6. Structural checks beyond the field contract:
single as-of date, ≥4 strictly-increasing unique tenors (curve); monotonic
unique dates, strictly positive levels, ≥252 observations (equity).

Tests: `tests/test_live_market_data_pipeline.py` (12 cases: three tiers,
tamper detection, refresh semantics, schema/structural rejection paths).

**Production restriction:** no credentialled vendor adapter ships in-repo;
fixtures remain educational proxies until the Model Owner approves a live
source (then item #2 swaption calibration and #6 backtesting consume this
pipeline).
