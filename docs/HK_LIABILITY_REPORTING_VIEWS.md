# Hong Kong Liability Reporting Views

**Document ID:** `PHASE10-HK-LIABILITY-REPORTING-VIEWS`  
**Created:** 2026-06-04  
**Status:** Phase 10 task 5 implementation note  
**Scope:** Educational liability reporting views for Hong Kong participating cash dividend and reversionary bonus variants.

## Purpose

This Phase 10 task adds portfolio-level reporting views over the Hong Kong
participating product fixtures.  The views consume the deterministic
asset-share support reports from the previous task and organize the output into
reserve, TVOG, supportability, and management-summary tables.

The implementation is in `par_model_v2/projection/hk_participating.py`.

## Implemented API

| Helper | Purpose |
|---|---|
| `HKLiabilityReportingPack` | JSON-ready wrapper for the four reporting views |
| `hk_liability_reserve_view(...)` | Policy-level deterministic reserve view from projection summaries |
| `hk_liability_tvog_view(...)` | Policy-level TVOG view using supplied Q-measure results when available |
| `hk_bonus_supportability_view(...)` | Final supportability rows consumed from `HKAssetShareSupportReport` |
| `hk_liability_management_summary(...)` | Product-variant aggregate management summary |
| `build_hk_liability_reporting_pack(...)` | Builds the starter reporting pack for sample HK policies |

The reporting basis ID is `PHASE10-HK-LIABILITY-REPORTING-BASE-2026`.

## Reserve View

The reserve view is deterministic and educational.  It reports:

- present value of premiums;
- present value of guaranteed benefits;
- present value of non-guaranteed benefits;
- present value of expenses;
- deterministic reserve proxy;
- asset share at maturity;
- policy, product, declaration assumption, support basis, and limitation IDs.

It is not a statutory reserving basis, HKRBC valuation, IFRS 17 fulfilment cash
flow, or production actuarial reserve.

## TVOG View

The TVOG view deliberately separates reporting shape from stochastic execution.
If a Q-measure TVOG result is supplied for a policy ID, the row is marked
`SUPPLIED_Q_MEASURE_TVOG` and records the TVOG amount, stochastic guaranteed
PV, percentiles, scenario count, and run ID.

If no stochastic result is supplied, the row is marked
`NOT_RUN_Q_MEASURE_REQUIRED`.  This avoids reporting a deterministic proxy as
TVOG and preserves the SOA / IA requirement that market-consistent option value
evidence use Q-measure scenarios.

## Bonus Supportability View

The supportability view consumes `HKAssetShareSupportReport` and does not
recalculate margins.  For each policy it reports the final asset share,
support obligation, support margin, support ratio, support status, declaration
assumption ID, sensitivity label, and support basis.

## Management Summary

The management summary aggregates by product variant:

- policy count;
- total sum assured and premium;
- deterministic reserve and guaranteed-benefit PV;
- reported TVOG total when supplied;
- missing Q-measure TVOG count;
- supported and unsupported policy counts;
- minimum support margin and ratio;
- management status.

Rows are marked `REVIEW_REQUIRED` when any policy lacks supplied Q-measure TVOG
or fails supportability.  Rows are marked `READY_FOR_MANAGEMENT_REVIEW` only
when all policies have supplied TVOG evidence and pass supportability.

## Governance Notes

- SOA ASOP 56: report rows keep product mechanics, declaration assumption, and
  option-value basis explicit.
- IA TAS M: reserve, TVOG, and supportability views retain policy-level
  lineage needed for audit reconstruction.
- ERM: this is an educational deterministic reporting pack.  It does not prove
  stochastic bonus supportability, liquidity adequacy, PRE consistency,
  management-action feasibility, or production reporting readiness.

## Validation

Targeted tests in `tests/test_hk_participating_products.py` cover:

- default reporting pack shape across reserve, TVOG, supportability, and
  management summary views;
- explicit missing-Q-measure TVOG status;
- supportability view reuse of support report final values;
- supplied TVOG-result handling.

## Next Phase 11 Task

The next task is to generate or ingest a 100,000-policy synthetic Hong Kong PAR
portfolio.  That portfolio should feed these reporting views after grouping,
chunking, checkpointing, and reconciliation are added.
