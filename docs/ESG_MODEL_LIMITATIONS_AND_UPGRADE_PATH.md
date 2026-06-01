# ESG Model Limitations and Upgrade Path

**Phase:** 8 - Equity, FX, and Correlation ESG
**Status:** Phase 8 exit documentation for educational development use
**Date:** 2026-06-01

## Purpose

This document records the model limitations introduced or confirmed by the
Phase 8 regional equity, FX, and correlation work. It also defines the upgrade
path from the current transparent GBM / lognormal starter models to stochastic
volatility, jump diffusion, and richer correlation models.

The current implementation is suitable for governed educational examples and
development validation. It is not approved for pricing, regulatory reporting,
hedging, capital allocation, or external disclosure.

## Current Phase 8 Model Boundary

Phase 8 keeps the v1-compatible scenario shape while adding:

- regional equity factor fixtures for US, Europe, Hong Kong / China, Japan, and
  Asia ex-Japan;
- optional HKD-reporting FX translation factors for USD, EUR, CNY, and JPY;
- correlation matrix validation, PSD repair evidence, and scenario diagnostics;
- a P-measure backtest scaffold for equity distribution and correlation
  stability review.

The current equity and FX processes are deliberately simple. They are used to
exercise scenario metadata, parameter traceability, validation reports, and
consumer compatibility before adding more complex stochastic dynamics.

## Limitation Register

| ID | Area | Limitation | Risk | Current Mitigation |
| --- | --- | --- | --- | --- |
| ESG-LIM-08-01 | Equity | Regional equity returns use constant-volatility GBM. Volatility clustering, mean-reverting variance, skew, and smile dynamics are not captured. | High | Disclose placeholder status, run P-measure distribution diagnostics, and use deterministic stresses for ERM examples. |
| ESG-LIM-08-02 | Equity | GBM lognormal tails underrepresent crash clustering and abrupt market discontinuities. | High | Compare generated tails to reference data in `PMeasureBacktestValidator`; supplement with stress scenarios until jump models are implemented. |
| ESG-LIM-08-03 | Equity | Only one regional equity factor is generated through the v1 wide columns at a time. | Medium | Parameter snapshots record the selected factor; full multi-equity vector generation is deferred to the multi-asset expansion. |
| ESG-LIM-08-04 | FX | FX uses a single-pair lognormal process with placeholder drift and volatility. Peg breaks, basis, central-bank intervention, and interest-rate-parity calibration are outside the starter fixture. | High | FX is optional, source-tagged, and limited to educational HKD reporting examples. |
| ESG-LIM-08-05 | Correlation | Correlations are static over the scenario horizon. Stress-period correlation breaks and regime changes are not modelled. | High | `CorrelationMatrixValidator` validates input matrices and `PMeasureBacktestValidator` records stability warnings. |
| ESG-LIM-08-06 | Correlation | PSD repair is an evidence tool, not an approved automatic override. Large repairs can materially change dependency assumptions. | Medium | Repair reports keep original and repaired matrices plus maximum adjustment diagnostics for model-owner review. |
| ESG-LIM-08-07 | Backtesting | The P-measure backtest is a scaffold. It does not fetch, clean, approve, or version historical market data. | High | Callers must supply governed reference data from the Phase 6 calibration data interface. |
| ESG-LIM-08-08 | Calibration | Starter equity, FX, and correlation parameters are illustrative placeholders. | Critical | Scenario parameter snapshots preserve source IDs and placeholder status; production use remains prohibited. |
| ESG-LIM-08-09 | Measure | Q-measure market-consistency evidence currently focuses on rate discount factors. Equity and FX martingale checks are not yet complete for all translated market examples. | High | Keep P/Q measure segregation explicit and require future Q-measure equity / FX validation before TVOG use with foreign assets. |

## Upgrade Path

### Stage 1 - Data and Calibration Readiness

Before changing the stochastic process, the model owner should approve:

- historical equity and FX total-return series by market;
- corporate-action, dividend, holiday, survivorship, and currency treatment;
- implied-volatility sources where available;
- correlation estimation windows, frequency, and stress-period overrides;
- data lineage records that can be attached to `ParameterSnapshot`.

This stage keeps the current GBM process but replaces placeholder parameters
with governed calibration packs.

### Stage 2 - Stochastic Volatility

The first volatility upgrade candidate is a Heston-style equity process:

```text
dS(t) / S(t) = mu(t) dt + sqrt(v(t)) dW_S(t)
dv(t) = kappa * (theta - v(t)) dt + xi * sqrt(v(t)) dW_v(t)
corr(dW_S, dW_v) = rho_sv
```

Required validation evidence:

- non-negative variance handling and discretisation choice;
- variance mean-reversion and long-run variance reasonableness;
- P-measure distribution and drawdown diagnostics versus history;
- Q-measure martingale tests for equity total-return processes;
- option-smile or implied-volatility calibration evidence where market data is
  available;
- sensitivity of TVOG, VaR, ES, and ALM outputs to `xi` and `rho_sv`.

Use stochastic volatility when option/guarantee values are materially sensitive
to volatility clustering, volatility skew, or vol-of-vol.

### Stage 3 - Jump Diffusion

The first jump upgrade candidate is a Merton-style jump diffusion:

```text
dS(t) / S(t) = (mu(t) - lambda * k) dt + sigma dW(t) + (J - 1) dN(t)
```

where `lambda` is jump intensity, `J` is the jump multiplier, and `k = E[J - 1]`.

Required validation evidence:

- jump intensity, mean jump size, and jump volatility calibration basis;
- tail percentile, drawdown, and expected-shortfall comparisons to history;
- stress-period backtests and exception counts;
- Q-measure compensator treatment for pricing / TVOG use;
- scenario diagnostics that separate diffusion losses from jump losses.

Use jump diffusion when historical or stress evidence shows discontinuous tail
losses that the GBM or stochastic-volatility model cannot explain.

### Stage 4 - Regime and Correlation Extensions

Correlation upgrades should follow process upgrades. Candidate approaches are:

- regime-switching equity / FX parameters for normal and stressed markets;
- dynamic conditional correlation or rolling-window correlation calibration;
- factor-copula models for nonlinear tail dependence;
- multi-equity vector generation with cross-market equity and FX correlations.

Required validation evidence:

- positive-semidefinite matrix validation in every regime;
- transition probability or regime trigger documentation;
- tail-dependence diagnostics and stress-period correlation tests;
- governance approval for any PSD repair or expert-judgment override.

### Stage 5 - Consumer Integration

No richer process should be marked complete until downstream consumers have an
explicit compatibility check:

- TVOG: Q-measure martingale and discounting evidence.
- VaR / ES: P-measure distribution and tail diagnostics.
- ALM: asset market value roll-forward and currency translation handling.
- Reporting: parameter snapshot, seed, measure, market, currency, and source
  lineage in output packs.

## Decision Gates

| Gate | Continue with Current GBM | Upgrade Trigger |
| --- | --- | --- |
| Educational examples | Transparent parameters explain the workflow clearly. | Teaching objective requires volatility clustering, skew, or jump tails. |
| TVOG materiality | Volatility simplification has immaterial effect under sensitivity testing. | Option / guarantee value changes materially under vol-of-vol or jump stresses. |
| ERM tail risk | Deterministic stresses adequately cover tail scenarios. | VaR / ES or drawdown backtests show systematic tail understatement. |
| Calibration data | Approved history and implied-volatility data are not available. | Governed data sources and owner-approved calibration packs are available. |
| Governance | Model owner has not approved the added complexity. | Model owner approves validation criteria and documentation updates. |

## Required Documentation Updates for Future Upgrades

Any stochastic-volatility, jump-diffusion, or regime-correlation upgrade must
update:

- `docs/ESG_PROCESS_DOCUMENTATION.md` with model equations and measure rules;
- `docs/PARAMETER_CALIBRATION_METHODOLOGY.md` with calibration sources and
  objective functions;
- `docs/ESG_P_MEASURE_BACKTEST_SCAFFOLD.md` or successor validation reports
  with new diagnostics;
- `docs/MODEL_RISK_CARD.md` and release notes with changed limitations;
- `.claude-dev/MODEL_DEV_STATE.json` with task status and next governance step.

## Standards Alignment

- SOA ASOP 56 Sections 3.1.3 and 3.6: documents process limitations,
  unsuitable uses, and known model risk from simplified stochastic dynamics.
- SOA ASOP 56 Section 3.5: defines validation evidence required before richer
  stochastic processes can support model output reliance.
- IA TAS M Sections 3.5 and 3.6: records assumption limitations, data lineage
  dependencies, and model-owner review points.

