# Asset Class Stress Tests and Governance Notes

**Document ID:** `PHASE9-ASSET-STRESS-GOVERNANCE`  
**Created:** 2026-06-02  
**Status:** Phase 9 task 5 implementation note  
**Scope:** Deterministic asset class stress tests and governance disclosures for the Phase 9 educational asset library.

## Purpose

Phase 9 now includes a governed stress-test layer for the expanded asset
examples.  The implementation reports market-value impacts by scenario, source
type, asset class, and instrument so ALM reporting users can see which stress
driver affects each holding.

The implementation is intentionally deterministic and transparent.  It is
appropriate for educational ALM packs, governance evidence, and model-owner
scope review.  It is not a calibrated market-risk capital, statutory solvency,
liquidity-haircut, or derivative CVA model.

## Implemented Contract

The implementation is in `par_model_v2/projection/asset_stress.py`.

`AssetStressScenario` defines the stress inputs:

| Input | Purpose |
|---|---|
| `rate_shift_bps` | Fixed-income duration repricing shock |
| `spread_shift_bps` | Fixed-income credit-spread widening / tightening |
| `downgrade_spread_bps_per_notch` | Spread allowance for instrument downgrade notches |
| `private_credit_default_multiplier` | Multiplier on private credit default probability |
| `private_credit_recovery_shift` | Additive recovery-rate stress for private credit |
| `private_equity_nav_shock` | Funded NAV markdown / uplift |
| `infrastructure_inflation_shift` | Inflation-linked NAV uplift stress |
| `infrastructure_revenue_shock` | Infrastructure cash-yield pressure proxy |
| `derivative_curve_shift_bps` | Curve shift used to revalue swaps and bond forwards |
| `governance_note` | Scenario-specific limitation and use restriction |

`run_asset_class_stress_tests(...)` returns an `AssetStressReport` with:

| Field | Purpose |
|---|---|
| `stress_results` | Instrument-level base MV, stressed MV, impact, driver, and governance note |
| `scenario_summary` | Portfolio-level scenario impact and largest loss attribution |
| `governance_notes` | SOA / IA / ERM limitations for report users |

## Starter Stress Pack

`default_phase9_asset_stress_scenarios()` defines four starter stresses:

| Scenario | Main Risk Driver | Notes |
|---|---|---|
| `HKD_RATE_UP_150BP` | Rate risk | Applies 150 bps duration repricing and derivative curve revaluation |
| `CREDIT_SPREAD_DEFAULT_STRESS` | Credit risk | Widens spreads and increases private credit expected loss |
| `PRIVATE_MARKET_LIQUIDITY_STRESS` | Private asset stress | Applies private equity NAV markdown, private credit loss pressure, and infrastructure revenue pressure |
| `INFLATION_DOWNSIDE_STRESS` | Infrastructure sensitivity | Reduces inflation-linked uplift and stresses infrastructure revenue |

## Stress Attribution

### Fixed Income

Fixed-income stress uses the existing first-order duration repricing function
`fixed_income_market_value_after_shock(...)`.  Rate shifts, spread shifts, and
downgrade spread allowances are disclosed in the `stress_driver` field.

### Private Credit

Private credit stress compares the base expected annual default loss to a
stressed expected loss after applying the scenario default-probability
multiplier and recovery-rate shift.  The incremental expected loss reduces
market value for stress attribution.

### Private Equity

Private equity stress applies a direct funded-NAV shock.  This is a teaching
proxy for appraisal, exit, vintage, and liquidity stresses; those drivers are
not separately calibrated in this Phase 9 slice.

### Infrastructure

Infrastructure stress applies a first-order inflation-linked NAV effect and a
cash-yield revenue pressure proxy.  It does not model project-finance debt
service, concession-specific revenue mechanics, or availability-payment
contract terms.

### Derivatives

Derivative stress revalues interest rate swaps and bond forwards using the
same valuation examples under a parallel-shifted discount curve.  The stress
preserves valuation measure and curve lineage from the derivative examples but
does not include production collateral, margining, CVA, or legal enforceability
effects.

## Governance Notes

- SOA ASOP 56: stress assumptions, drivers, and limitations are explicit at
  scenario and instrument level.
- IA TAS M: stress rows preserve `scenario_id`, `source_type`, `asset_class`,
  `instrument_id`, and `governance_note` for audit-trail reconstruction.
- ERM: rate, credit, private-market, infrastructure, and derivative impacts are
  separated instead of hidden in a single aggregate return shock.
- Production restriction: these stresses are deterministic educational
  examples.  They must not be used as VaR, ES, regulatory capital, statutory
  reserve, or model-owner production sign-off evidence without calibrated data,
  independent review, and formal governance approval.

## Validation

Targeted tests in `tests/test_asset_class_stress.py` cover:

- starter stress pack coverage and governance notes;
- invalid stress input rejection;
- source, scenario, and instrument attribution;
- fixed-income loss under a rate-up stress;
- private-asset markdown under private-market stress;
- derivative revaluation under a curve stress.

## Phase 9 Exit Position

Phase 9 now has code, tests, and documentation for the agreed starter asset
classes, derivative valuation examples, roll-forward reporting, stress testing,
and governance limitations.  The next planned phase is Hong Kong participating
liability product mechanics.
