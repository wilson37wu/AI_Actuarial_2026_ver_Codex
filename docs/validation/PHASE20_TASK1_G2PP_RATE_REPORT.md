# Phase 20 Task 1 - Enhanced G2++ Rates Driver

**Run timestamp:** 2026-06-06T07:10:34.440811+00:00

**Gate:** `G-RATE2` - **PASS**

## Diagnostics

| Metric | Value |
| --- | ---: |
| Initial-curve fit max abs error | 0 |
| Bond-option variance | 0.00362003208426 |
| Call price | 0.0777637196517 |
| Put price | 0.000999649363252 |
| Put-call parity error | 0 |
| Empirical factor correlation | -0.700801650494 |
| Negative-rate one-year discount factor | 1.00501252086 |

## G-RATE2 Checks

- **G-RATE2-01**: PASS (observed `0.0`, threshold `<= 1e-12 absolute price error`)
- **G-RATE2-02**: PASS (observed `0.0036200320842598444`, threshold `> 0`)
- **G-RATE2-03**: PASS (observed `0.0`, threshold `<= 1e-10`)
- **G-RATE2-04**: PASS (observed `-0.000999649363252475`, threshold `call in [0,P(0,S)] and put >= 0`)
- **G-RATE2-05**: PASS (observed `-0.7008016504939039`, threshold `within 3.5 percentage points of configured rho`)
- **G-RATE2-06**: PASS (observed `1.005012520859401`, threshold `> 1.0 for a -50 bp one-year flat curve`)

## Governance

- ChangeRecord: `1d7737af2f634c438b4f84a9d76e2b00` - **OWNER_REVIEW**
- MR-013: **IN_PROGRESS** (added)
- Audit integrity: **True**

## Production Restriction

Educational only until Phase 20 Tasks 2-4 calibrate and validate the G2++ driver
against a swaption surface, market-consistency martingale checks, and the
five-driver capital stack.
