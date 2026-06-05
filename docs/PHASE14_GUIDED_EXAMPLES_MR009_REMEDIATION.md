# Phase 14 Task 3: MR-009 Guided Examples Remediation

## Scope

MR-009 flagged that the educational guided examples had drifted from current
APIs for `RiskFreeCurve`, `FixedIncomeInstrument`, and `TVOGEngine`.

This remediation recreates the guided examples package against the current
contracts:

- `RiskFreeCurve`: uses `valuation_date`, `curve_id`, `source_id`,
  `discount_factor`, `zero_rate`, and starter curve fixtures.
- `FixedIncomeInstrument`: uses the current instrument schema and
  `project_fixed_income_cashflows(instruments, projection_months, ...)`.
- `TVOGEngine`: uses a Q-measure `ScenarioSet.generate(...)` result and current
  `TVOGEngine(product, scenarios, deterministic_discount_rate).compute()`.

## Examples Restored

1. Fixed-income pricing and +100 bps rate sensitivity.
2. Hong Kong cash dividend and reversionary bonus liability valuation.
3. Q-measure TVOG computation with scenario-count convergence evidence.
4. Dynamic ALM projection from a 100 percent cash portfolio to SAA.
5. Asset stress testing plus Phase 8 correlation PSD validation.
6. Compact reporting-cycle close with assumption lock, validation, review, and
   sign-off pack.

## Validation

The regression target is `tests/test_guided_examples.py`.  It verifies:

- current curve and fixed-income API fields are used;
- rate shocks reduce fixed-income market value;
- HK participating schedules and supportability outputs are generated;
- TVOG runs under Q-measure and returns finite metrics;
- ALM rebalances out of a 100 percent cash starting portfolio;
- stress impacts and PSD correlation diagnostics are present;
- reporting close produces an approved governance sign-off pack;
- `run_all_examples()` supports default, subset, and unknown-section behavior.

## Governance Note

The examples remain educational wrappers.  They do not replace the production
reporting engine, independent validation suite, or governed market-data
calibration pipeline.  MR-009 is operational-risk remediation for user-facing
tutorial integrity and API compatibility.
