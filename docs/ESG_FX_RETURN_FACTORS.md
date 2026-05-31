# ESG FX Return Factors

## Purpose

Phase 8 adds governed starter FX return factors for translating foreign-currency
market factors into the reporting currency. The first reference base currency is
HKD for Hong Kong participating-business examples.

The starter translation pairs are:

- `USDHKD` - US dollar assets and USD-denominated Asia ex-Japan equity to HKD.
- `EURHKD` - Europe equity and EUR curve examples to HKD.
- `CNYHKD` - China exposure examples to HKD.
- `JPYHKD` - Japan equity and JPY rate examples to HKD.

These fixtures are educational placeholders. They are not production calibration
data and must not be used for regulatory reporting, pricing, hedging, or capital
allocation.

## Fixture Contract

Starter FX assumptions live in
`par_model_v2/stochastic/fixtures/fx_return_factors.json` and are loaded through:

- `available_starter_fx_pairs()`
- `starter_fx_factor(pair, valuation_date=None)`
- `fx_factor_for_translation(foreign_currency, base_currency="HKD", valuation_date=None)`
- `default_phase8_fx_factors(valuation_date=None)`

Each `FXReturnFactor` records the currency pair, foreign currency, base currency,
quotation convention, source ID, valuation date, factor ID, and `FXParams`.
Spot is quoted as base-currency units per one foreign-currency unit; for example,
`USDHKD` means HKD per USD.

## Model Form

The FX spot process is lognormal:

```text
dX(t) / X(t) = mu_fx dt + sigma_fx dW_fx(t)
```

where:

- `X(t)` is the spot exchange rate in base currency per foreign currency.
- `sigma_fx` is the annual FX volatility.
- Under P-measure, `mu_fx` is the placeholder real-world FX drift.
- Under Q-measure, `mu_fx` is the placeholder domestic-minus-foreign rate spread.

`ScenarioSet.generate(..., fx_factor=...)` adds:

- `fx_rate`
- `fx_return_1m`
- `fx_pair`

The v1 rate/equity columns are unchanged. Existing TVOG, risk, ALM, and reporting
consumers can ignore the optional FX columns until their mappings are expanded.

## Traceability

When an FX factor is supplied, `ParameterSnapshot` records:

- the FX source as an `fx` `CalibrationSource`;
- market-qualified parameter keys such as `fx.gbm.JPYHKD.fx_vol`; and
- the valuation date and placeholder limitation status.

This preserves the SOA / IA audit trail from scenario output back to the FX
assumption source.

## Limitations

- The starter factors are single-pair GBM placeholders, not calibrated time
  series models.
- The current `ScenarioSet` supports one optional FX factor at a time.
- Rate/equity/FX correlation validation and empirical scenario diagnostics are
  implemented in `docs/ESG_CORRELATION_VALIDATION.md`; currency basis,
  interest-rate parity calibration, central-bank regimes, pegged-currency break
  risk, and multi-FX basket correlation remain future calibration work.
- Translation effects are exposed as separate columns; asset cashflow and market
  value roll-forward consumers will integrate them in Phase 9 and Phase 11.
