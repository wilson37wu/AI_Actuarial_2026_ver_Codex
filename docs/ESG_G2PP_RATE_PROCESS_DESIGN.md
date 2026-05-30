# ESG G2++ Rate Process Prototype Design

**Document ID:** `ESG-G2PP-RATE-PROCESS-DESIGN`  
**Phase:** 7 - Interest Rate and Yield Curve ESG  
**Status:** Prototype for educational use; not production calibrated  
**Created:** 2026-05-30

## Purpose

Phase 7 Task 2 adds a two-factor Gaussian G2++ prototype so the ESG can
represent yield-curve twist behaviour that a one-factor Hull-White model cannot
capture. The prototype is intentionally narrow: it provides v1-compatible
short-rate and zero-coupon outputs plus diagnostic factor paths, while leaving
full swaption-surface calibration and martingale evidence to later tasks.

## Model Form

The process is:

```text
r(t) = phi(t) + x(t) + y(t)
dx(t) = -a x(t) dt + sigma dW_x(t)
dy(t) = -b y(t) dt + eta dW_y(t)
corr(dW_x, dW_y) = rho
```

`G2PlusParams` holds:

| Parameter | Meaning |
| --- | --- |
| `mean_reversion_x`, `mean_reversion_y` | Factor mean-reversion speeds |
| `vol_x`, `vol_y` | Annual factor volatilities |
| `factor_correlation` | Brownian correlation between the two rate factors |
| `initial_x`, `initial_y` | Initial factor states |
| `long_run_rate_p` | Educational P-measure target level |
| `market_price_of_risk_x`, `market_price_of_risk_y` | Placeholder P-measure risk-premium terms |
| `short_rate_floor`, `short_rate_ceiling` | Optional diagnostic clipping bounds |

## Measure Treatment

Under Q-measure, `phi(t)` is fitted to the supplied `RiskFreeCurve`
instantaneous forward curve. At time zero, when `x(0) = y(0) = 0`, the
prototype zero-coupon price matches the supplied curve discount factor.

Under P-measure, the deterministic shift uses the educational long-run rate
plus placeholder market-price-of-risk terms. These values are not calibrated
and must not be used for production assumption setting.

## Output Contract

`G2PlusRateProcess.simulate(...)` returns:

| Column | Meaning |
| --- | --- |
| `scenario_id`, `month`, `measure` | Standard v1 ESG grid and measure fields |
| `r_short` | Simulated short rate after optional bounds |
| `zcb_1y`, `zcb_10y` | Curve-fitted prototype zero-coupon prices |
| `g2pp_x`, `g2pp_y` | Diagnostic factor states for validation and curve-shape analysis |

`zcb_1y` and `zcb_10y` are capped at par by default to preserve the v1
`ESGAdapter` range contract. Set `cap_zcb_at_par=False` for negative-rate
diagnostics where discount factors above 1.0 are expected.

## Validation Added

Targeted tests in `tests/test_esg_process.py` cover:

- v1-compatible output columns plus G2++ factor diagnostics;
- time-zero Q-measure fit to an explicit initial curve;
- empirical positive factor-increment correlation;
- negative-rate curve diagnostics with uncapped discount factors above par;
- validation rejection for invalid factor correlations.

## Limitations and Next Steps

- The bond price is a prototype curve-fit expression and omits the full G2++
  convexity adjustment required for market-consistent production pricing.
- Parameters are placeholders and are not calibrated to a swaption volatility
  surface.
- `ScenarioSet.generate(...)` still defaults to HW1F plus GBM. Integration of
  G2++ into combined multi-asset scenario generation should follow after
  starter curve fixtures and validation evidence are in place.
- Q-measure martingale evidence remains a later Phase 7 task.

