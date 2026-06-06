# Phase 19 Task 4 - Five-Driver Aggregation Governance Refresh

**Classification:** EDUCATIONAL ONLY - placeholder parameters; not a regulatory capital model.

**Task:** Phase 19 Task 4 - five-driver tail-dependent risk aggregation (mortality-trend added as 5th capital driver).
**Drivers:** short_rate, equity_guarantee, credit_spread, lapse_behaviour, mortality_trend.

## Governance actions

- **MR-010** refreshed: True - status **MITIGATED** (five-driver var-covar understatement 48.8%; copula `gaussian` rel. error 6.5%).
- **MR-012** refreshed: True - status **MITIGATED** (proxy now FIVE drivers incl. mortality-trend; FX / liquidity / management-action still omitted).
- **ChangeRecord** added: True - status **OWNER_REVIEW** (production sign-off withheld).
- **Interaction residual (multiplicative lapse x mortality on guaranteed leg):** -8.1% of nested.
- **Standalone SCRs:** rate 33,329; equity 30,196; credit 9,771; lapse 26,973; mortality 413 (mortality is the SMALLEST - confirming a genuinely orthogonal, non-financial second tail axis).
- **Nested five-driver SCR:** 92,449; var-covar 47,293; copula 86,444.
- **Reproducibility digest:** `50ca08d617fe`.
- **Limitation card:** `docs/MULTI_DRIVER_5D_AGGREGATION_CARD.md`.

## Residual (production sign-off blocker)

Mortality-trend index is a single systemic Lee-Carter-style OU factor with placeholder parameters and no age/cohort/basis-risk structure; lapse-behaviour index likewise a single systemic OU factor; FX / liquidity / management-action drivers still omitted; copula marginals do not extrapolate; credentialled calibration + independent APS X2 review pending.

## Standards

SOA ASOP 56 §3.5, SOA ASOP 56 §3.1, SOA ASOP 25 §3.3, SOA ASOP 7 §3.3, IA TAS M §3.2, IA TAS M §3.5, IA TAS M §3.6, Solvency II Delegated Reg. Art. 234, IFoA Life Aggregation & Simulation working party, Lee & Carter (1992).

