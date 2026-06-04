# Phase 12 Task 2: Model Limitation Cards

**Module:** `par_model_v2/governance/limitation_cards.py`  
**Tests:** `tests/test_limitation_cards.py`  
**Source ID:** `PHASE12-T2-LIMITATION-CARDS`

## Purpose

Phase 12 adds short, structured limitation cards for every material ESG and
Hong Kong participating liability component.  The cards are designed for model
governance review: each one names the component, limitation, severity,
unsuitable uses, current mitigation, required upgrade, owner role, and standards
reference.

## Covered Components

### ESG

- Hull-White 1F rate process
- G2++ rate prototype
- Regional equity GBM factors
- FX translation factors
- Static correlation matrix
- P-measure backtest scaffold

### Liability

- HK cash dividend mechanics
- HK reversionary bonus mechanics
- Declaration assumption hooks
- Asset-share support tests
- Liability reporting views

## Usage

```python
from par_model_v2.governance import write_default_limitation_cards

report = write_default_limitation_cards("outputs/phase12_limitations")
print(report.open_critical_count)
```

This writes:

- `phase12_model_limitation_cards.json`
- `phase12_model_limitation_cards.md`

## Governance Notes

- **SOA ASOP 56 Sections 3.5-3.6:** limitations and unsuitable uses are explicit
  at component level.
- **IA TAS M Sections 3.5-3.6:** each card assigns an owner role and identifies
  the required upgrade before production reliance.
- **ERM:** critical ESG and declaration assumptions remain open until calibrated
  market or experience data and owner sign-off are available.

## Current Status

The limitation-card catalogue is complete for the current Phase 8-10 ESG and
liability modules.  It does not replace the broader model risk card; it is a
component-level supplement intended for tutorials, reporting packs, and model
governance review.
