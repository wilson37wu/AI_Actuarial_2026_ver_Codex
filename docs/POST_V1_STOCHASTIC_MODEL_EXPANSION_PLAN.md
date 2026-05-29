# Post-v1 Stochastic Model Expansion Plan

**Document ID:** `POST-V1-STOCH-EXPANSION-PLAN`  
**Created:** 2026-05-29  
**Repository:** https://github.com/wilson37wu/AI_Actuarial_2026_ver_Codex  
**Status:** Draft development roadmap for staged scope expansion  
**Purpose:** Expand the v1 PAR stochastic ALM / TVOG model into a broader educational actuarial reporting model that better illustrates real reporting cycles, multi-market economic scenarios, richer asset classes, Hong Kong participating-product liability mechanics, and high-volume policy processing.

---

## 1. Guiding Principles

The expansion should proceed one topic at a time. Each phase must leave behind code, tests, documentation, and a clear governance note before moving on.

1. **Educational first, production disciplined.** The model should teach how actuarial reporting works in practice, but the implementation should still use model governance, validation, audit trail, and limitation disclosures.
2. **Stochastic assumptions must be explicit.** Every generator must document measure, time step, calibration source, parameter date, random seed policy, correlation basis, and known limitations.
3. **Market realism should be layered.** Start with transparent models and calibration stubs; add richer models only after interfaces, validation, and reporting are stable.
4. **Hong Kong product features first on liabilities.** Prioritise cash dividend and reversionary bonus mechanics commonly seen in Hong Kong participating business before expanding to other jurisdictions.
5. **Scale is a design requirement.** The target educational batch size is 100,000 policies, so data structures, chunking, checkpointing, and run monitoring must be part of the design rather than a late optimisation.
6. **Scope remains adjustable.** Each phase has a decision checkpoint so the Model Owner can narrow, pause, or redirect the next slice based on development outcomes.

---

## 2. Expanded Industry Standards Context

### 2.1 Stochastic Economic Scenario Generation

The ESG must support both real-world (P-measure) and risk-neutral (Q-measure) workflows. Minimum governance requirements:

- Document risk factor universe, model equations, discretisation method, calibration date, market data source, and parameter ownership.
- Keep P/Q measure segregation explicit at scenario-set and consumer level.
- Validate economic plausibility: yield curve shape, negative-rate behaviour, equity return distribution, correlation stability, and tail events.
- Support reproducibility through seed control, scenario metadata, and archived parameter snapshots.
- Provide backtests for P-measure scenarios and martingale / market-consistency checks for Q-measure scenarios.

### 2.2 Interest Rate Models

The initial post-v1 target is a contemporary interest-rate framework that can represent low and negative interest-rate regimes.

Candidate sequence:

1. Hull-White 1-factor enhancement for multi-curve and negative-rate support.
2. G2++ / two-factor Gaussian rates for richer curve dynamics.
3. Optional shifted lognormal or normal market models for swaption-linked calibration examples.

The framework should cover risk-free curves for USD, EUR, HKD, CNY, JPY, and major Asia markets where practical. HKD should include an explicit note on USD peg and basis considerations.

### 2.3 Equity and Multi-Market Returns

The ESG should begin with broad regional equity indices:

- US equity.
- Eurozone / European equity.
- Major Asia markets: Hong Kong / China, Japan, and one broad Asia ex-Japan proxy.

The first implementation can use GBM or regime-aware GBM, but the design should allow later stochastic volatility, jump diffusion, and correlation regime extensions.

### 2.4 Asset Class Coverage

The asset model should be expanded in layers:

- Fixed income: government bonds, corporate bonds, credit spreads, duration, convexity, defaults, and downgrades.
- Public equity: total return indices by region and currency.
- Private credit: spread income, default loss, recovery, liquidity lag, and valuation smoothing.
- Private equity: capital calls, distributions, NAV smoothing, J-curve behaviour, and lagged valuation.
- Infrastructure: inflation linkage, long-duration cash yield, availability / revenue shocks.
- Derivatives: interest rate swaps, bond forwards, and simple hedging instruments with collateral / valuation conventions where relevant.

### 2.5 Liability Product Expansion

The liability model should prioritise Hong Kong participating products:

- Cash dividend products: annual dividend declaration, cash payout / accumulation options, policyholder behaviour, and dividend scale sensitivity.
- Reversionary bonus products: annual declared bonus additions, guaranteed vs non-guaranteed benefit split, terminal bonus treatment, and asset-share support.
- Common reporting views: best estimate liability, TVOG, CSM / risk adjustment illustration where applicable, source-of-earnings style bridge, and management reporting summaries.

### 2.6 High-Volume Processing

The educational scale target is 100,000 policies. The model must demonstrate:

- Policy data validation and grouping.
- Chunked projection and checkpoint restart.
- Deterministic and stochastic run modes.
- Runtime health reporting, failed-chunk handling, and reconciliation.
- Summary reporting that distinguishes policy-level, cohort-level, and portfolio-level outputs.

---

## 3. Development Phases

### Phase 6: ESG Scope and Architecture

**Goal:** Define the expanded ESG architecture before coding deeper models.

Tasks:

1. Define multi-market ESG requirements, scenario schema, supported measures, currencies, regions, and risk factors.
2. Design scenario metadata and parameter snapshot structure.
3. Define calibration data interfaces for curves, equity indices, FX, credit spreads, and correlations.
4. Map ESG outputs to existing TVOG, VaR/ES, ALM, and reporting consumers.
5. Add design documentation and acceptance tests for schema compatibility.

Exit criteria:

- A documented ESG interface exists.
- Existing scenario consumers have an adapter path.
- P/Q measure metadata is mandatory in schema.
- The next phase can implement rates without redesigning consumers.

### Phase 7: Interest Rate and Yield Curve ESG

**Goal:** Build a richer rate engine that supports negative rates and multi-market curves.

Tasks:

1. Implement enhanced Hull-White 1-factor process with explicit curve input and negative-rate support.
2. Add G2++ design / prototype for two-factor curve dynamics.
3. Support USD, EUR, HKD, CNY, JPY starter curves through parameter files or fixtures.
4. Add yield curve validation: monotonic discount factors, forward-rate diagnostics, negative-rate scenario tests, and stress scenarios.
5. Add Q-measure martingale evidence for discount factors.

Exit criteria:

- Rate scenarios can be generated for at least USD, EUR, HKD, CNY, and JPY.
- Negative short-rate paths are allowed and tested.
- Q-measure discounting checks are documented.

### Phase 8: Equity, FX, and Correlation ESG

**Goal:** Add regional equity returns and cross-risk-factor correlation.

Tasks:

1. Add US, Europe, Hong Kong / China, Japan, and Asia ex-Japan equity factors.
2. Add FX return factors where currency translation is needed.
3. Implement correlation matrix validation, positive-semidefinite repair / rejection, and scenario diagnostics.
4. Add P-measure backtest scaffold for equity return distribution and correlation stability.
5. Document model limitations and upgrade path to stochastic volatility / jump diffusion.

Exit criteria:

- Multi-region equity scenarios can be generated with documented correlation.
- Correlation validation prevents invalid matrices.
- Scenario summaries show annualised return, volatility, drawdown, and tail metrics.

### Phase 9: Asset Class and Derivative Library

**Goal:** Expand asset coverage beyond cash, bonds, and public equity.

Tasks:

1. Add fixed-income instruments with coupon, duration, spread, downgrade, and default loss fields.
2. Add private credit, private equity, and infrastructure educational asset models.
3. Add interest rate swap valuation and bond forward valuation examples.
4. Add asset cashflow aggregation and market value roll-forward reporting.
5. Add asset class stress tests and governance notes.

Exit criteria:

- Asset projection supports the agreed starter asset classes.
- Derivative valuation examples are tested and documented.
- ALM reports can show asset-class attribution.

### Phase 10: Hong Kong Participating Liability Products

**Goal:** Enrich liabilities for Hong Kong-style participating products.

Tasks:

1. Define Hong Kong cash dividend product mechanics and sample policy data.
2. Define reversionary bonus mechanics, including vested bonus, terminal bonus, and guarantee split.
3. Implement dividend / bonus declaration assumptions and sensitivity hooks.
4. Add asset-share support tests for cash dividend and reversionary bonus variants.
5. Add liability reporting views for reserves, TVOG, bonus supportability, and management summaries.

Exit criteria:

- Cash dividend and reversionary bonus products run through deterministic projection.
- Stochastic TVOG can consume the product outputs.
- Documentation explains product mechanics in educational terms.

### Phase 11: 100,000-Policy Processing and Reporting Cycle

**Goal:** Demonstrate a realistic actuarial reporting cycle at educational scale.

Tasks:

1. Generate or ingest a 100,000-policy synthetic Hong Kong PAR portfolio.
2. Add grouping, chunking, checkpoint restart, failed-chunk audit, and reconciliation.
3. Add reporting-cycle workflow: assumption lock, model run, validation checks, output review, sign-off pack.
4. Add performance benchmarks and memory profiling.
5. Create educational reporting pack: model run log, movement analysis, risk metrics, validation exceptions, and sign-off checklist.

Exit criteria:

- 100,000 synthetic policies process successfully in deterministic mode.
- A smaller stochastic sample and grouped stochastic run are supported.
- Reporting pack demonstrates an end-to-end actuarial reporting cycle.

### Phase 12: Governance, Calibration, and Educational Packaging

**Goal:** Turn the expanded model into a coherent educational tool.

Tasks:

1. Add calibration notebooks / scripts for curves, equity, credit, and liability assumptions.
2. Add model limitation cards for every ESG and liability module.
3. Add guided examples for students / actuaries: pricing, valuation, TVOG, ALM, stress, reporting close.
4. Add validation dashboards or markdown reports.
5. Refresh final documentation, release notes, and model risk card.

Exit criteria:

- The model has a coherent tutorial path.
- Governance records describe assumptions, limitations, and reporting cycle.
- Scope is ready for the next Model Owner decision.

---

## 4. Immediate Next Task

The next development task should be:

**Phase 6, Task 1: Define multi-market ESG requirements and scenario schema.**

Deliverables:

- `docs/ESG_SCOPE_AND_SCHEMA_DESIGN.md`
- Scenario schema proposal covering measure, currency, market, risk factor, time grid, metadata, and parameter snapshot.
- Compatibility note for existing `ScenarioSet`, `TVOGEngine`, `RiskMetrics`, and ALM consumers.
- Acceptance test plan for schema validation.

This task is intentionally design-first. It keeps the model from accumulating disconnected generators before the scenario interface is stable.

---

## 5. Scope Checkpoints

At the end of each phase, the Model Owner should decide:

- Continue with the proposed next phase.
- Narrow market coverage.
- Defer complex asset classes.
- Prioritise Hong Kong liability features ahead of ESG breadth.
- Pause implementation and improve documentation / teaching examples.

This keeps the roadmap flexible while preserving a disciplined development trail.
