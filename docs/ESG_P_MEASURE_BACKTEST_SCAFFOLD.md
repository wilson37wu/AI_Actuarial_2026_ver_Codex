# ESG P-Measure Backtest Scaffold

Phase 8 adds a scaffold for real-world scenario backtesting through:

- `PMeasureBacktestValidator`
- `PMeasureBacktestReport`
- `PMeasureBacktestCheck`

The scaffold is intentionally source-agnostic. It does not fetch market history
or approve calibration data. Callers supply generated P-measure scenarios plus,
when available, a prepared historical or reference return table.

## Scope

The validator covers two evidence areas for the current v1-compatible ESG
scenario set:

1. Equity return distribution diagnostics for `equity_return_1m`.
2. Correlation stability across short-rate changes, equity returns, and optional
   FX returns.

The scenario input must include `scenario_id`, `month`, `equity_return_1m`, and
`measure`. The scaffold rejects non-P-measure scenario sets because real-world
distribution backtests are not valid on risk-neutral Q-measure paths.

## Distribution Evidence

For generated scenarios, the report records:

- observation count;
- monthly mean and volatility;
- annualised mean and volatility;
- 1st, 5th, 50th, 95th, and 99th percentiles;
- minimum and maximum monthly returns.

If `historical_data` is supplied with `equity_return_1m`, the same distribution
metrics are calculated for the reference data. Mean, volatility, and tail
differences are emitted as warning-level checks so early educational fixtures
can produce evidence before final production thresholds are approved.

## Correlation Stability

The scaffold can test correlation stability in two ways:

- compare generated scenario empirical correlations to an expected matrix, such
  as `phase8_rate_equity_fx_correlation_matrix(...)`;
- compare generated correlations to historical/reference correlations when the
  reference table supplies `rate_short_change` or `r_short`, `equity_return_1m`,
  and optional `fx_return_1m`.

The report keeps JSON-ready scenario and historical correlation matrices with
factor IDs. The current factor IDs are:

| Factor ID | Meaning |
| --- | --- |
| `RATE_SHORT_CHANGE` | Monthly change in generated short rates |
| `EQUITY_RETURN_1M` | Monthly equity return |
| `FX_RETURN_1M` | Monthly FX return, when supplied |

## Governance Notes

- Historical data preparation remains outside this scaffold and must be
  controlled by the Phase 6 calibration data interfaces.
- Warning-level distribution and correlation failures do not block the scaffold
  report; they identify model-owner review items.
- Error-level failures cover missing columns, non-P-measure scenarios,
  insufficient observations, non-finite returns, and impossible equity returns
  below -100%.

## Standards Alignment

- SOA ASOP 56 Sections 3.1.3 and 3.5: records real-world scenario distribution
  diagnostics, empirical correlation evidence, sampling counts, and limitations.
- IA TAS M Sections 3.5 and 3.6: creates an audit-ready report format that can
  be attached to calibration packs and scenario validation evidence.

## Limitations

- Starter equity and FX parameters remain educational placeholders.
- The scaffold does not yet perform rolling-window regime tests, formal
  goodness-of-fit tests, drawdown backtests, or exceptions analysis.
- Historical data source approval, cleaning, survivorship-bias controls, and
  benchmark selection remain required before production use.
