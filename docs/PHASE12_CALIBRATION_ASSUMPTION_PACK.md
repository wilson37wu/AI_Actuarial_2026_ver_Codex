# Phase 12 Task 1: Calibration Scripts for Curves, Equity, Credit, and Liability Assumptions

**Module:** `par_model_v2/calibration/phase12_calibration_pack.py`  
**Script:** `scripts/build_phase12_calibration_pack.py`  
**Tests:** `tests/test_phase12_calibration_pack.py`  
**Source ID:** `PHASE12-T1-CALIBRATION-PACK`  
**Limitation ID:** `PHASE12-T1-CALIBRATION-PACK-LIMIT`

## Purpose

Phase 12 starts the educational packaging layer by creating a governed
calibration assumption pack.  The pack consolidates starter inputs for:

- risk-free curves from the Phase 7 multi-currency curve fixtures;
- regional equity factors from the Phase 8 equity fixtures;
- public and private credit spread / expected-loss assumptions from Phase 9;
- Hong Kong participating declaration assumptions from Phase 10.

The pack is deliberately labelled `EDUCATIONAL_PLACEHOLDER`.  It is a workflow
and review artefact, not a market calibration result.

## How to Build

```powershell
python scripts\build_phase12_calibration_pack.py --output-dir outputs\phase12_calibration
```

The script writes:

- `phase12_calibration_pack.json`
- `phase12_calibration_pack.md`

Optional category filters are available:

```powershell
python scripts\build_phase12_calibration_pack.py --category curve --category liability
```

## Pack Contents

Each `CalibrationAssumptionCard` includes:

- category (`curve`, `equity`, `credit`, or `liability`);
- assumption ID and name;
- basis and numeric value;
- unit, source ID, and limitation ID;
- owner role and validation status;
- metadata needed to trace back to the source fixture or product mechanics.

The pack also runs structural checks for category coverage, unique assumption
IDs, finite values, and placeholder disclosure.

## Standards Alignment

- **SOA ASOP 56 Section 3.4:** parameter sources, calibration basis, and
  limitations are explicitly recorded.
- **IA TAS M Sections 3.5-3.6:** the pack gives a traceable assumption-to-output
  record for review and sign-off.
- **ERM:** credit, market, and liability assumptions are separated by owner role,
  supporting escalation and periodic recalibration governance.

## Limitations

The pack uses starter fixtures and educational product mechanics.  It is not
calibrated to live yield curves, option surfaces, credit indices, insurer
experience data, PRE policy, board minutes, or regulator-approved assumptions.
Production use remains blocked until every card is replaced by approved data and
signed off by the relevant assumption owner.
