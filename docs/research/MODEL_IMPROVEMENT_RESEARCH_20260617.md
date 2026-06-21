# Model-improvement research v2 — owner-decision support (2026-06-17, claude)

**Supersedes (extends, does not replace):** `docs/research/MODEL_IMPROVEMENT_RESEARCH_20260616.md`.
This v2 keeps the prior ranked recommendation intact and adds (a) current-literature
(2025) grounding for the two model-form candidates, (b) a refinement of the longevity
recommendation toward a **multi-population / basis-risk-aware** design, and (c) one
**new efficiency candidate** (Multilevel Monte Carlo for the nested SCR loop) that was
not in v1. **No model-form change is made here.** Everything below is documentation only
and requires an explicit owner choice before any cycle may start it.

**Why this cycle produced research and not code.** The auto-admissible development
frontier is exhausted: the offline-UI decision-neutral pool (a)–(g) is closed (contract
1.23.0, offline_home gate 28/28), and the efficiency/diagnostic pool
(MR-CAL-1 + MR-VR-1 + MR-VR-2) is closed under the Phase 30 stop-rule. The task prompt's
standing rule is that, until the owner picks a pivot, a run should **produce a status
report and NOT start a model-form change**. The owner's standing instruction is, in that
state, to **research further improvement and update the task prompt for next execution** —
which is exactly this note. Governed headline **39,975.654628199336** untouched; no
artifact rebuild; no contract bump.

---

## Refreshed ranked recommendation (unchanged order; #1 and #2 deepened, #3 is new-efficiency)

### 1 (RECOMMENDED) — MR-LONGEV-1: longevity/mortality as a 5th stochastic driver
**Model-FORM change → REQUIRES owner sign-off.** Highest actuarial materiality for a PAR
endowment book, whose liability is dominated by survival/maturity cash flows.

- **Method choice — refine v1.** v1 named Lee-Carter (LC) or Cairns-Blake-Dowd (CBD) as
  the calibrate-and-explain benchmarks; both remain valid (LC: single period factor,
  most parsimonious; CBD: two-factor period model, better at the older/pensioner ages
  that dominate endowment maturities). The 2025 literature pushes one refinement worth
  putting to the owner: for a Hong Kong book, single-population LC/CBD ignores
  **longevity basis risk** between the book's experience and the reference population
  used to calibrate. A **two-population / Li-Lee common-factor** structure (global
  age-period factor + population-specific factor) is the established way to capture this,
  and continuous-time **affine multi-cohort** mortality models give closed-form survival
  probabilities that integrate cleanly with the existing outer-scenario engine.
  Recommendation: **start with single-population LC as the additive 5th driver
  (lowest-risk, explainable), and document two-population/affine as the v2 extension** so
  the design note does not over-commit on first pass.
- **Integration (unchanged).** Add a mortality-improvement state to the outer scenario
  set, feed survival probabilities into the existing projection engine, re-aggregate SCR
  with the current dependence structure. Keep it **additive** so the no-longevity path
  stays bit-identical (matches the backward-compatibility gate).
- **Effort/risk.** ~2–4 cycles (design-note → calibration → integration → SCR
  re-aggregation + governance ChangeRecord). Re-baselines the governed headline → needs
  explicit owner sign-off and a fresh frozen reference.
- **Opposing view (must be presented).** Adding a driver invites the scope-creep the
  Phase 30 stop-rule exists to prevent; mitigant is the additive/sign-off discipline and
  staging the multi-population extension behind the simpler single-population first pass.

### 2 — LSMC proxy for SCR (efficiency, model-FORM-adjacent → sign-off)
**Least-Squares Monte Carlo** proxy to accelerate/replace the nested Value-at-Risk
calculation. v1 noted large runtime savings vs full nested simulation; the 2025
literature now adds two concrete data points worth citing to the owner: (i) **machine-
learning LSMC** (neural-network proxy functions) is an established extension at internal-
model data scale, and (ii) **transformer-based LSMC** (2025) reports improved accuracy in
approximating the liability-to-risk-factor map, i.e. a better proxy at the SCR tail. The
governance hook is unchanged: a proxy must pass an **out-of-sample validation gate**
before it is used for the full loss-distribution forecast — which fits this project's
existing OOS-validation discipline (Phase 22 seven-driver OOS). Owner-gated because it
changes *how* SCR is computed (proxy regression), not just the sampling.

### 3 (NEW in v2) — Multilevel Monte Carlo (MLMC) for the nested SCR loop (efficiency)
Not in v1. The closed VR pool (Sobol-RQMC / stratified / RQMC+CV, ~500x on the SCR tail)
optimises the **outer** sampling. **MLMC with antithetic inner sampling** (2025 work on
optimised MLMC parametrisation for nested simulations) instead attacks the **inner**
nested cost by combining many cheap low-inner-path estimates with few expensive
high-inner-path estimates — complementary to, not overlapping with, the closed pool, and
**not a model-form change** (it re-organises the estimator, leaving the model and the
governed headline definition intact). This makes it the **most auto-admissible of the
efficiency candidates** if the owner wants more runtime headroom without re-baselining;
it would still warrant a design-note-first cycle and a same-headline equivalence gate.

### 4 — Phase IGUI resumption (NON-model-form, auto-runnable once confirmed)
Unchanged from v1. Owner previously named Phase IGUI the exclusive next priority; it
relaxes zero-install for the *input* GUI only (RESULTS UI stays zero-install). Lowest
model risk, directly user-facing, design-note-first. **Safest productive pivot** if the
owner does not want to re-baseline the headline.

### 5 — Packaging A/B/C / Freeze (unchanged)
Packaging A/B/C: pure delivery hardening, no model effect, auto-runnable once selected.
Freeze: declare the frontier complete; cycles switch to maintenance/verification.

---

## Decision matrix (for the owner)

| Option | Model-form change? | Re-baselines headline? | Auto-runnable w/o sign-off? | Primary value |
|---|---|---|---|---|
| 1 MR-LONGEV-1 | Yes (additive 5th driver) | Yes | No (sign-off) | Actuarial completeness |
| 2 LSMC proxy | Adjacent (proxy compute) | No (if gated) | No (sign-off) | Runtime at SCR tail |
| 3 MLMC nested (new) | No (estimator only) | No (equivalence-gated) | Closest to auto-admissible | Inner-loop runtime |
| 4 Phase IGUI | No | No | Yes (confirm scope) | User-facing input/run |
| 5 Packaging / Freeze | No | No | Yes (packaging) / n/a | Delivery / closure |

## Housekeeping the owner should also rule on (unchanged from v1, still open)
1. `test_phase36_task5_phase_summary::test_contract_inventory` RED on origin — frozen
   report pins contract 1.21.0 vs test ≥1.22.0 (now 1.23.0). One-line owner call; auto-
   fixable in <1 cycle if approved.
2. MR-016 / MR-017 copula-form residual disclosure — owner-pending.
3. ~29 pytest collection errors are environmental (numpy/scipy absent in CI sandbox), not
   regressions.

## Recommendation in one line
If willing to re-baseline → **MR-LONGEV-1 (single-population Lee-Carter additive first;
two-population/affine staged behind it)**. If not → **MLMC nested-loop efficiency** is the
new lowest-risk productive pivot (no re-baseline, equivalence-gated), with **Phase IGUI**
the safest non-model alternative; clear the contract-inventory test-gate drift
opportunistically either way.

---

### Sources (2025 literature consulted this cycle)
- Transformers-based Least Square Monte Carlo for Solvency Calculation in Life Insurance (ScienceDirect, 2025): https://www.sciencedirect.com/science/article/abs/pii/S0167668725001106
- Neural networks meet least squares Monte Carlo at internal model data (European Actuarial Journal): https://link.springer.com/article/10.1007/s13385-022-00321-5
- Optimized Multi-Level Monte Carlo Parametrization and Antithetic Sampling for Nested Simulations (arXiv 2510.18995, 2025): https://arxiv.org/pdf/2510.18995
- A Two-Population Mortality Model to Assess Longevity Basis Risk (Risks, MDPI): https://www.mdpi.com/2227-9091/9/2/44
- A continuous-time stochastic model for the mortality surface of multiple populations (ScienceDirect): https://www.sciencedirect.com/science/article/abs/pii/S0167668716302906
- A stochastic model for capital requirement assessment for mortality and longevity risk (Annals of Actuarial Science, Cambridge): https://www.cambridge.org/core/journals/annals-of-actuarial-science/article/stochastic-model-for-capital-requirement-assessment-for-mortality-and-longevity-risk-focusing-on-idiosyncratic-and-trend-components/62B089D7E27B53F1B893EC081982DF90
