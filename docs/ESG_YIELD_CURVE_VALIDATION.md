# ESG Yield Curve Validation

**Phase:** 7 - Interest Rate and Yield Curve ESG  
**Task:** Add yield curve validation for discount factors, forwards, negative-rate paths, and stresses  
**Status:** Development acceptance contract  
**Date:** 2026-05-31

---

## Purpose

`YieldCurveValidator` provides a reusable validation report for risk-free curve
inputs and generated rate paths. It is designed for Phase 7 HW1F and G2++
development evidence, not production curve approval.

The validator covers:

- curve discount factors are finite and strictly positive;
- adjacent-tenor continuously compounded forward rates are finite and within
  configured bounds;
- adjacent forward-rate jumps are flagged for review;
- parallel up/down rate shocks move discount factors monotonically;
- optional scenario path checks confirm finite positive `zcb_1y` and
  `zcb_10y` outputs;
- optional negative-rate evidence confirms negative short-rate rows and
  uncapped above-par discount factors.

---

## API

```python
from par_model_v2.stochastic import (
    HullWhiteParams,
    HullWhiteRateProcess,
    Measure,
    YieldCurveValidator,
    starter_risk_free_curve,
)

curve = starter_risk_free_curve("JPY", valuation_date="2026-05-31")
params = HullWhiteParams(
    initial_short_rate=curve.instantaneous_forward(0.0),
    short_rate_floor=None,
)
paths = HullWhiteRateProcess(params, initial_curve=curve).simulate(
    n_scenarios=100,
    T_months=120,
    measure=Measure.Q,
    seed=42,
    cap_zcb_at_par=False,
)

report = YieldCurveValidator().validate(
    curve,
    scenario_data=paths,
    require_negative_rate_evidence=True,
)

if not report.passed:
    raise ValueError(report.failed_checks())
```

`report.to_dict()` is JSON-ready for audit storage and documentation appendices.

---

## Validation Checks

| Check ID | Severity | Requirement |
| --- | --- | --- |
| `YC-DF-POSITIVE` | Error | all curve discount factors are finite and greater than zero |
| `YC-FWD-RANGE` | Error | adjacent forward rates stay within validator bounds |
| `YC-FWD-SMOOTHNESS` | Warning | adjacent forward-rate jumps stay within the configured warning threshold |
| `YC-STRESS-MONOTONIC` | Error | up shocks lower discount factors and down shocks raise them |
| `YC-PATH-COLUMNS` | Error | path data includes `month`, `r_short`, `zcb_1y`, and `zcb_10y` |
| `YC-PATH-DF-FINITE` | Error | path discount factors are finite and positive |
| `YC-PATH-RATE-FINITE` | Error | path short rates are finite |
| `YC-PATH-NEGATIVE-RATE-EVIDENCE` | Error | when requested, paths include negative rates and above-par uncapped discount factors |

Warnings are included in `failed_checks()` but do not make `report.passed`
false. Error failures do.

---

## Stress Basis

The default parallel stress is +/-100 bps applied to the input zero curve.
For all positive tenors, the validator requires:

- `discount_factor(up_shift) < discount_factor(base)`;
- `discount_factor(down_shift) > discount_factor(base)`.

This is a deterministic curve-mechanics check. It does not replace stochastic
convergence testing. Q-measure martingale evidence is handled separately by
`QMeasureMartingaleValidator`; see
`docs/ESG_Q_MEASURE_MARTINGALE_EVIDENCE.md`.

---

## Governance Notes

- Starter curves remain educational placeholders until governed market data is
  approved.
- Negative-rate validation should be run with `cap_zcb_at_par=False`; capped
  v1 compatibility views hide above-par discount-factor evidence.
- Forward smoothness warnings require actuarial review if they arise from real
  market curves rather than deliberately stressed fixtures.
