# ESG Hull-White Curve Input Design

**Document ID:** `ESG-HW1F-CURVE-INPUT-DESIGN`  
**Phase:** 7 - Interest Rate and Yield Curve ESG  
**Status:** Implemented for educational use; not production calibrated  
**Created:** 2026-05-30

## Purpose

Phase 7 Task 1 enhances the HW1F rate generator so it can accept an explicit
risk-free zero curve instead of relying only on a flat `initial_short_rate`.
This is the first implementation step toward multi-market USD, EUR, HKD, CNY,
and JPY curve support.

## Implemented Contract

`RiskFreeCurve` is the governed curve input used by `HullWhiteRateProcess` and
`ScenarioSet.generate`.

Required curve fields:

| Field | Meaning |
| --- | --- |
| `tenors_years` | Strictly increasing non-negative tenor grid |
| `zero_rates` | Continuously compounded zero rates; negative rates allowed down to -10% |
| `currency` | Three-letter currency code |
| `market` | Market or region identifier |
| `valuation_date` | Curve as-of date |
| `curve_id` | Stable identifier for lineage |
| `source_id` | Calibration-source identifier |

The curve exposes:

- `zero_rate(T)` for linear zero-rate interpolation;
- `discount_factor(T)` for continuously compounded `P(0,T)`;
- `instantaneous_forward(t)` using piecewise secants of `z(t) * t`;
- `to_dict()` for JSON-ready governance payloads.

## HW1F Use

Under Q-measure, monthly short rates mean-revert toward the explicit initial
forward curve. Under P-measure, the model keeps the existing educational
real-world long-run-rate target plus market-price-of-risk adjustment.

Zero-coupon prices use the HW1F affine curve-fit expression:

```text
P(t,T) = P(0,T) / P(0,t)
         * exp(-B(t,T) * (r(t) - f(0,t)) - variance_adjustment)
```

where:

```text
B(t,T) = (1 - exp(-a * (T - t))) / a
```

At `t = 0`, when `r(0)` equals the curve short forward rate, `zcb_price`
matches the supplied curve discount factor.

## Negative-Rate Treatment

HW1F is a Gaussian short-rate model and can naturally produce negative rates.
Phase 7 adds configurable `short_rate_floor` and `short_rate_ceiling` to
`HullWhiteParams`:

- existing v1-compatible defaults remain `[-2%, 15%]`;
- setting `short_rate_floor=None` permits uncapped negative-rate paths;
- negative zero curves may produce discount factors above par.

For backward compatibility, `simulate(...)` and `ScenarioSet.generate(...)`
cap `zcb_1y` and `zcb_10y` at `1.0` by default because the v1 `ESGAdapter`
schema expects `(0, 1]`. Set `cap_zcb_at_par=False` for Phase 7 diagnostics
that need true negative-rate discount factors.

## Validation Added

Targeted tests in `tests/test_esg_process.py` cover:

- negative zero-rate discount factors above par;
- curve tenor validation;
- HW1F `zcb_price` matching the explicit flat curve at time zero;
- negative-rate path generation without floor clipping;
- `ScenarioSet.generate` accepting an explicit curve and recording curve
  zero rates in the `ParameterSnapshot`.

## Limitations

- Curve interpolation is deliberately simple and educational.
- P-measure dynamics do not yet use market-specific curve risk premia.
- Multi-currency starter fixtures are not included until the next Phase 7
  tasks.
- Q-measure martingale evidence remains a later Phase 7 task.
