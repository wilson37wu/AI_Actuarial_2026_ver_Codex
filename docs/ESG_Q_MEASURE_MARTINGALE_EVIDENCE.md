# ESG Q-Measure Martingale Evidence

**Phase:** 7 - Interest Rate and Yield Curve ESG
**Task:** Add Q-measure martingale evidence for discount factors
**Status:** Development acceptance contract
**Date:** 2026-05-31

---

## Purpose

`QMeasureMartingaleValidator` provides reviewable evidence that Q-measure
zero-coupon bond outputs are internally consistent with the supplied initial
risk-free curve.

For each supported generated bond price `P(t,T)`, the validator estimates:

```text
E_Q[D(0,t) * P(t,T)] ~= P(0,T)
```

where `D(0,t)` is the money-market discount factor accumulated from simulated
monthly short rates. This is a development diagnostic for HW1F discount-factor
logic. It is not a production market-consistency sign-off.

---

## API

```python
from par_model_v2.stochastic import (
    HullWhiteParams,
    Measure,
    QMeasureMartingaleValidator,
    ScenarioSet,
    starter_risk_free_curve,
)

curve = starter_risk_free_curve("USD", valuation_date="2026-05-31")
params = HullWhiteParams(
    initial_short_rate=curve.instantaneous_forward(0.0),
    short_rate_floor=None,
)
scenarios = ScenarioSet.generate(
    n=1000,
    T_months=120,
    measure=Measure.Q,
    hw_params=params,
    initial_curve=curve,
    base_currency="USD",
    valuation_date="2026-05-31",
    seed=42,
    cap_zcb_at_par=False,
)

report = QMeasureMartingaleValidator().validate(curve, scenarios.data)

if not report.passed:
    raise ValueError(report.failed_checks())
```

`report.to_dict()` is JSON-ready for audit storage and reporting appendices.

---

## Validation Checks

| Check ID | Severity | Requirement |
| --- | --- | --- |
| `QME-COLUMNS` | Error | scenario data includes `scenario_id`, `month`, `r_short`, `measure`, `zcb_1y`, and `zcb_10y` |
| `QME-MEASURE-Q` | Error | all rows are labelled Q-measure |
| `QME-UNIQUE-PATH-GRID` | Error | each scenario/month pair appears once |
| `QME-COMPLETE-MONTH-GRID` | Error | months are contiguous from zero |
| `QME-FINITE-RATE-GRID` | Error | short-rate grid is complete and finite |
| `QME-ZCB_1Y-FINITE` / `QME-ZCB_10Y-FINITE` | Error | generated zero-coupon bond prices are finite and positive |
| `QME-MARTINGALE-ZCB_1Y` / `QME-MARTINGALE-ZCB_10Y` | Error | average discounted bond prices reconcile to the initial curve within tolerance |
| `QME-SAMPLING-ERROR-ZCB_1Y` / `QME-SAMPLING-ERROR-ZCB_10Y` | Warning | sampling error is small enough for reviewable evidence |

Warnings are included in `failed_checks()` but do not make `report.passed`
false. Error failures do.

---

## Tolerance Basis

The default tolerance is the larger of:

- 35 bps absolute price error; or
- 3.5% relative price error.

The tolerance is deliberately wider than a production calibration target
because the current implementation uses monthly discretisation, educational
placeholder parameters, and starter curves. Tight production thresholds should
be set only after governed calibration and convergence criteria are approved.

---

## Governance Notes

- The validator rejects P-measure scenarios; risk-neutral martingale evidence
  is only meaningful for Q-measure paths.
- Runs intended to evidence negative-rate markets should use
  `cap_zcb_at_par=False`; par caps can distort bond-price evidence.
- Evidence should be stored with the scenario metadata, parameter snapshot,
  valuation date, seed, scenario count, and model version.
- Passing evidence does not validate swaption calibration, full yield-curve
  dynamics, or production market consistency.
