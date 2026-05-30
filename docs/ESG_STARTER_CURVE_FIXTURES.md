# ESG Starter Risk-Free Curve Fixtures

**Document ID:** `ESG-STARTER-CURVE-FIXTURES`  
**Phase:** 7 - Interest Rate and Yield Curve ESG  
**Status:** Implemented for educational use; not production calibrated  
**Created:** 2026-05-30

## Purpose

Phase 7 Task 3 adds governed starter zero-curve fixtures for the first
multi-market interest-rate scope:

- USD / US
- EUR / EU
- HKD / HK
- CNY / CN
- JPY / JP

The fixtures live in
`par_model_v2/stochastic/fixtures/risk_free_curves.json` and are loaded through
the public helpers:

- `available_starter_curve_currencies()`
- `starter_risk_free_curve(currency, valuation_date=None)`
- `default_phase7_starter_curves(valuation_date=None)`

## Fixture Contract

Each fixture provides a continuously compounded zero curve with:

| Field | Meaning |
| --- | --- |
| `currency` | Three-letter currency code |
| `market` | Market or region identifier |
| `valuation_date` | Fixture as-of date |
| `curve_id_prefix` | Stable prefix used to build a dated curve ID |
| `source_id` | Calibration-source lineage identifier |
| `tenors_years` | Strictly increasing tenor grid from 0Y to 30Y |
| `zero_rates` | Continuously compounded zero rates |

`starter_risk_free_curve(...)` returns a validated `RiskFreeCurve`, so the
same interpolation, discount-factor, forward-rate, and JSON serialization
rules used by HW1F and G2++ apply to the fixtures.

## Governance Status

These curves are deliberately labelled as educational placeholders. They are
stable fixtures for development, examples, and validation tests. They are not
market data snapshots and must not be used for pricing, regulatory reporting,
capital reporting, or assumption sign-off.

`ParameterSnapshot.from_process_params(...)` records a fixture curve as a
`curve` source when the returned `RiskFreeCurve` is supplied to
`ScenarioSet.generate(...)`, preserving:

- source ID;
- market and currency;
- valuation date;
- curve ID; and
- compounding basis.

## Validation Added

Targeted tests in `tests/test_esg_process.py` verify:

- all five starter currencies are available;
- every loaded curve has the expected 0Y to 30Y tenor grid;
- discount factors are finite and positive;
- the JPY fixture supports a negative short-end zero rate;
- unknown currencies are rejected; and
- a USD starter curve can drive `ScenarioSet.generate(...)` with traceable
  parameter snapshot output.

## Limitations

- Curve shapes are illustrative, not vendor-sourced market closes.
- Interpolation remains linear in zero rates for educational transparency.
- Market-specific P-measure risk premia are not yet calibrated.
- Yield-curve consistency diagnostics and Q-measure martingale evidence remain
  separate Phase 7 tasks.
