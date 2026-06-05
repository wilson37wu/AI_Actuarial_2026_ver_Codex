# Phase 18 Task 4 - Four-Driver Aggregation Governance Refresh

**Classification:** EDUCATIONAL ONLY - placeholder parameters; not a regulatory capital model.

**Task:** Phase 18 Task 4 - four-driver tail-dependent risk aggregation + tail diagnostics
**Drivers:** short_rate, equity_guarantee, credit_spread, lapse_behaviour.

## Governance actions

- **MR-010** refreshed: True - status **MITIGATED** (four-driver var-covar understatement 47.4%; copula `gaussian` rel. error 9.4%).
- **MR-012** refreshed: True - status **MITIGATED** (proxy now four drivers; mortality-trend / FX / liquidity still omitted).
- **ChangeRecord** added: True - status **OWNER_REVIEW** (production sign-off withheld).
- **Interaction residual (multiplicative lapse):** -11.1% of nested.
- **Four-driver tail metric:** converged True (rec N_outer >= 16000); bootstrap VaR 231,150 CI [226,371, 239,438]; Sobol var-reduction 3.3x.
- **Audit chain:** 37 entries; integrity verified: True.
- **Risk register:** 12 total ({'OPEN': 1, 'IN_PROGRESS': 4, 'MITIGATED': 5, 'ACCEPTED': 0, 'CLOSED': 2}).
- **Limitation card:** `docs/MULTI_DRIVER_4D_AGGREGATION_CARD.md`.

## Residual (production sign-off blocker)

Lapse-behaviour index is a single systemic OU factor with placeholder parameters; mortality-trend / FX / liquidity drivers still omitted; copula marginals do not extrapolate; credentialled calibration + independent APS X2 review pending.

## Standards

SOA ASOP 56 §3.5, SOA ASOP 56 §3.1.3, SOA ASOP 25 §3.3, SOA ASOP 7 §3.3, IA TAS M §3.2, IA TAS M §3.6, Solvency II Delegated Reg. Art. 234, IFoA Life Aggregation & Simulation working party, L'Ecuyer (2018) RQMC.
