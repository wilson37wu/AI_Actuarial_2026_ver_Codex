# Phase 18 Task 1 — Copula-Aggregation Governance Refresh

**Classification:** EDUCATIONAL ONLY — placeholder parameters; not a regulatory capital model.

**Task:** Phase 18 Task 1 - copula-based tail-dependent risk aggregation
**Drivers:** short_rate, equity_guarantee, credit_spread.

## Governance actions

- **MR-010** refreshed: True — status **MITIGATED** (mitigation now implemented as a copula engine, not just documented).
- **ChangeRecord** added: True — status **OWNER_REVIEW** (production sign-off withheld).
- **Selected copula:** `gaussian`; rel. error vs nested 1.43% vs var-covar 34.5%.
- **Audit chain:** 32 entries; integrity verified: True.
- **Risk register:** 12 total ({'OPEN': 1, 'IN_PROGRESS': 5, 'MITIGATED': 4, 'ACCEPTED': 0, 'CLOSED': 2}).
- **Limitation card:** `docs/COPULA_AGGREGATION_CARD.md`.

## Residual (production sign-off blocker)

Empirical marginals cannot extrapolate beyond simulated component loss ranges; tail-dependence estimates are sampling-noisy; copulas impose a single exchangeable/elliptical tail structure; credentialled calibration + independent APS X2 review pending.

## Standards

SOA ASOP 56 §3.5, SOA ASOP 25 §3.3, IA TAS M §3.6, Solvency II Delegated Reg. Art. 234, IFoA Life Aggregation & Simulation working party, Demarta-McNeil 2005 (t-copula).
