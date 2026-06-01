# Phase 8 Regional Equity Factors

**Status:** Implemented for educational development use. Not production
calibration data.

## Scope

Phase 8 adds governed starter equity factors for:

| Market | Region | Currency | Factor ID |
|--------|--------|----------|-----------|
| US | United States | USD | `EQUITY_US` |
| EU | Europe | EUR | `EQUITY_EU` |
| HK_CN | Hong Kong / China | HKD | `EQUITY_HK_CN` |
| JP | Japan | JPY | `EQUITY_JP` |
| ASIA_EX_JP | Asia ex-Japan | USD | `EQUITY_ASIA_EX_JP` |

The fixtures live in
`par_model_v2/stochastic/fixtures/regional_equity_factors.json` and are loaded
through:

- `available_starter_equity_markets()`
- `starter_equity_factor(market, valuation_date=None)`
- `default_phase8_equity_factors(valuation_date=None)`

Each `RegionalEquityFactor` carries market, region, currency, index name,
source ID, factor ID, valuation date, and a `GBMParams` object. Existing v1
consumers continue to receive the same `equity_index` and
`equity_return_1m` columns.

Foreign-currency markets can be paired with the Phase 8 FX fixtures documented
in `docs/ESG_FX_RETURN_FACTORS.md`. For example, `EQUITY_JP` can be generated
with `JPYHKD` when the reporting base is HKD.

## Process

The current implementation keeps the existing GBM process:

```
dS(t) = mu_S(t) * S(t) dt + sigma_S * S(t) dW_S(t)
```

Under Q-measure, drift is `r(t) - dividend_yield`. Under P-measure, drift is
`r(t) + equity_risk_premium - dividend_yield`.

The regional factor selects the GBM parameter set. It does not yet create a
multi-equity vector in one scenario set. The Phase 8 correlation validator now
checks the rate/equity/FX matrix used by the v1-compatible generator and records
empirical scenario diagnostics; full multi-equity vector generation remains a
future extension.

## Traceability

When `ScenarioSet.generate(..., equity_factor=...)` is used, the generated
`ParameterSnapshot` records:

- the regional equity source as an `equity_index` `CalibrationSource`;
- the generic `equity.gbm.*` parameters used by v1 consumers; and
- market-qualified parameters such as
  `equity.gbm.HK_CN.equity_vol`.

This maintains an audit trail from output scenario columns back to the selected
regional equity assumption basis.

## Limitations

- Parameter values are illustrative placeholders.
- The process is constant-volatility GBM and does not capture stochastic
  volatility, jumps, regime changes, or volatility skew.
- Regional equity factors are generated one at a time through the v1 wide
  equity columns.
- Rate/equity/FX correlation validation is implemented in
  `docs/ESG_CORRELATION_VALIDATION.md`; cross-equity matrix calibration remains
  a future extension.
- The governed limitation register and upgrade path to stochastic volatility,
  jump diffusion, and regime-aware equity models is documented in
  `docs/ESG_MODEL_LIMITATIONS_AND_UPGRADE_PATH.md`.
