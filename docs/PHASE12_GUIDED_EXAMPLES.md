# Phase 12 — Guided Examples: Educational Actuarial Model Walkthroughs

**Module:** `par_model_v2/examples/guided_examples.py`  
**Phase:** 12 — Governance, Calibration, and Educational Packaging  
**Task:** Task 3 of 5 — Add guided examples for pricing, valuation, TVOG, ALM, stress, and reporting close  
**Standards:** SOA ASOP 56, SOA ASOP 25, IA TAS M §3.2/§3.6, ERM framework  

---

## Model-Use Restriction

> **EDUCATIONAL ONLY.**  All parameter values are illustrative placeholders.  
> This module must not be used for regulatory capital, MCEV reporting,
> dividend declarations, or any other decision requiring calibrated actuarial inputs.  
> See `docs/PHASE12_MODEL_LIMITATION_CARDS.md` for per-component limitation cards.

---

## Overview

`guided_examples.py` provides six self-contained, runnable example functions that
walk through the complete educational actuarial workflow:

| Section | Function | Concepts |
|---------|----------|----------|
| 1 | `example_fixed_income_pricing()` | Risk-free curve, bond pricing, duration, rate shock |
| 2 | `example_hk_liability_valuation()` | HK cash dividend & reversionary bonus mechanics |
| 3 | `example_tvog_computation()` | Q-measure scenarios, TVOG engine, convergence |
| 4 | `example_alm_projection()` | SAA policy, 12-month rebalancing, VR-U02 fix |
| 5 | `example_stress_testing()` | Asset stress scenarios, correlation PSD validation |
| 6 | `example_reporting_close()` | Assumption lock → run → validation → sign-off pack |

---

## Quick Start

```python
# Run all six sections
from par_model_v2.examples.guided_examples import run_all_examples
results = run_all_examples()

# Run a single section
from par_model_v2.examples.guided_examples import example_tvog_computation
tvog = example_tvog_computation()
print(f"TVOG: {tvog['tvog_base']:.2f}")

# CLI with JSON output
python par_model_v2/examples/guided_examples.py --sections tvog alm --json
```

---

## Section Descriptions

### Section 1 — Fixed Income Pricing

Demonstrates present-value pricing using the Phase 7 USD `RiskFreeCurve` and
Phase 9 `FixedIncomeInstrument`.

- Builds a starter USD yield curve and reads discount factors at 1, 5, 10 years.
- Computes dirty price, modified duration, and convexity for a 10-year government bond.
- Applies a +100 bps parallel rate shock and compares the dollar impact to the
  duration approximation to quantify convexity.
- Prices a 10-year liability annuity-certain against the same curve.

**SOA/IA alignment:** ASOP 56 §3.1 (curve metadata documented); TAS M §3.2
(risk-free discount, illiquidity premium omitted and flagged).

---

### Section 2 — HK Participating Liability Valuation

Demonstrates Phase 10 HK PAR product valuation for both product lines.

- Loads sample `HKCashDividendPolicy` and `HKReversionaryBonusPolicy` objects.
- Builds annual dividend/bonus declaration schedules using
  `default_hk_declaration_assumption()`.
- Computes the guaranteed vs non-guaranteed cashflow split for the reversionary
  bonus line (key ERM metric: higher non-guaranteed fraction = more ALM discretion).
- Runs the Phase 10 asset-share support tests for both product lines.

**SOA/IA alignment:** ASOP 56 §3.1 (product mechanics and guarantee split documented);
TAS M §3.6 (policy ID → assumption → cashflow schedule → support status audit chain).

---

### Section 3 — TVOG Computation

Demonstrates the Phase 4 Q-measure TVOG engine.

- Generates 1,000 Q-measure (risk-neutral) scenarios via `ScenarioSet.generate()`.
- Runs `TVOGEngine.compute()` for a 10-year PAR endowment (SA=100,000).
- Interprets the TVOG as the cost of the embedded interest-rate guarantee.
- Performs a sensitivity: recomputes TVOG at a 50 bps lower deterministic discount
  rate to show TVOG direction under low-rate environment.
- Convergence check: compares 500 vs 1,000 scenario TVOG to evidence scenario adequacy.

**SOA/IA alignment:** ASOP 25 §3.3 (scenario adequacy); ASOP 56 §3.5 (TVOG
convergence evidence); TAS M §3.2 (Q-measure enforced); IFoA MCEV §7 (TVOG definition).

---

### Section 4 — ALM Projection

Demonstrates the Phase 3 DynamicALMEngine with a 12-month rebalancing simulation.

- Defines an SAA policy: 40% Govt / 25% Credit / 25% Equity / 10% Cash.
- Starts from a 100% Cash portfolio (the VR-U02 bug-fix scenario — verifies the
  symmetric BUY branch fires in period 1).
- Runs 12 monthly ALM steps with constant annual returns per asset class.
- Reports per-period SAA deviations, rebalancing decisions, and transaction costs.
- Computes portfolio growth net of transaction costs.

**SOA/IA alignment:** ASOP 56 §3.1 (rebalancing assumptions documented); ERM
(SAA drift evidence; transaction cost drag quantified).

---

### Section 5 — Stress Testing

Demonstrates the Phase 9 asset-class deterministic stress suite and Phase 8
correlation matrix validation.

- Loads the default Phase 9 stress scenarios (rate shock, credit spread widen,
  equity crash, combined).
- Runs `run_asset_class_stress_tests()` over the full Phase 9 instrument set.
- Aggregates results by scenario and identifies the worst-case total market-value
  impact.
- Drills into the top 5 impacted instruments in the worst scenario.
- Validates the Phase 8 multi-market correlation matrix for positive semi-definiteness.

**SOA/IA alignment:** ASOP 46 (stress scenario documentation); TAS M §3.6
(scenario_id linkage for audit trail); ERM (worst-case scenario flagging for
governance escalation).

---

### Section 6 — Reporting Close

Demonstrates the Phase 11 five-stage reporting-cycle governance workflow.

1. **Assumption lock** — snapshots all projection assumptions into an immutable,
   SHA-256-signed, time-stamped record.
2. **Model run record** — links the run to the assumption lock, model version,
   and portfolio metadata.
3. **Validation suite** — runs post-run checks (movement, reconciliation, reserve
   movement bounds, TVOG reasonableness, seed stability).
4. **Output review** — builds a human-readable review record referencing the
   validation results.
5. **Sign-off pack** — assembles JSON + Markdown governance evidence with a
   9-item sign-off checklist.

**SOA/IA alignment:** ASOP 56 §3.2 (validation required before use); ASOP 56 §3.3
(limitations documented); TAS M §3.6 (full assumption-to-output traceability chain).

---

## Test Coverage

`tests/test_guided_examples.py` provides 45+ tests covering:

- Structural: each function returns a dict with all expected keys.
- Sign checks: rate shock reduces bond MV; stress impacts are non-positive;
  portfolio grows under positive returns.
- Range checks: TVOG is finite; guaranteed fraction in [0, 100]%; final weights
  sum to ≈100%.
- Functional: 100% Cash portfolio triggers rebalancing in period 1 (VR-U02 fix);
  correlation matrix is PSD after Phase 8 validation.
- Integration: `run_all_examples()` completes all six sections without error.
- Subset: `run_all_examples(sections=["alm","stress"])` returns only those sections.

---

## Industry Standards Map

| Requirement | Standard | Implementation |
|---|---|---|
| Stochastic model documentation | SOA ASOP 56 §3.1 | Module docstring + per-section SOA/IA notes |
| Scenario adequacy for TVOG | SOA ASOP 25 §3.3 | Section 3 convergence check; ASOP 56 §3.5 minimum warning |
| Market-consistent valuation (Q-measure) | IA TAS M §3.2 | Section 3 Q-measure enforced; Section 1 risk-free curve |
| Assumption-to-output traceability | IA TAS M §3.6 | Section 6 full lock→run→validation→review→pack chain |
| Stress scenario documentation | SOA ASOP 46 | Section 5 scenario IDs and descriptions |
| Governance sign-off evidence | ERM framework | Section 6 sign-off pack with checklist |
| Model limitation disclosure | ASOP 56 §3.3 | Module header + each section + limitation cards |

---

## Limitations

- **Placeholder parameters throughout.** All calibration values are illustrative.
- **Constant ALM returns.** Section 4 uses fixed annual returns; production ALM
  should use Phase 7–8 ESG stochastic paths.
- **No persistence.** Examples print to stdout and return dicts; they do not
  write outputs to disk unless modified.
- **TVOG convergence.** 1,000 scenarios is above the ASOP 56 minimum (500) but
  below production quality (5,000+); standard error is not reported.
- **Sign-off pack is local.** Production deployments require a regulated workflow
  system with access controls.

See `docs/PHASE12_MODEL_LIMITATION_CARDS.md` for per-component limitation cards.
