# Latest Cycle Status — 2026-07-09 — Scenario-Adequacy Convergence Study

**Roadmap item:** §4.1 #5 — *Scenario adequacy at 2,000+ scenarios: convergence study
500→1,000→2,000→5,000 with CI bands* (C-ROSS gap #6) — **DONE**.
**Agent:** Claude Cowork (`actuarial-model-daily-improvement`).
**Lock:** acquired `2026-07-09T12:07Z` (cycle `2026-07-09T12:07Z-2833`), released at cycle end.
**Governed headline:** UNTOUCHED (purely-additive diagnostic).

## What shipped
- **Engine** `par_model_v2/analysis/scenario_adequacy.py` (numpy-only): runs the governed
  `TVOGEngine` unchanged across a scenario ladder and returns, per count, the TVOG point
  estimate with **95% CI bands**, a **runtime benchmark**, and an analytic scenario-count
  **recommendation** reconciled against the CBIRC C-ROSS ≥ 2,000 floor. Exposes
  `run_convergence_study(...)`, `ConvergenceStudyResult`, `ConvergencePoint`; SHA-256 inputs
  digest; injectable `tvog_runner` (resumable builds / fast tests).
- **Two error models.** The governed ESG draws **antithetic** shocks, so the naive iid error
  `σ_PV/√N` overstates the true Monte-Carlo error ~10×. The module reports both the naive-iid SE
  and an **empirical antithetic-aware SE** (std of TVOG across independent governed seeds), bases
  CI/sizing on the empirical model, and reports the realised **variance-reduction factor**.
- **Artifacts** `docs/SCENARIO_ADEQUACY_CONVERGENCE_STUDY.md` + `.json`
  (schema `scenario-adequacy-convergence-1.0`, UNSIGNED banner) via builder
  `scripts/build_scenario_adequacy_study.py`.
- **Pointer** added to `docs/MODEL_STABILITY_AND_LIMITATIONS.md` §2.1.

## Result (full ladder, replications=8, seed 42, deterministic discount 3.0% CBIRC cap)
| N | TVOG | iid SE | effective SE (antithetic-aware) | 95% CI | rel. CI |
|---:|---:|---:|---:|:--|---:|
| 500 | 8,514.5 | 571.9 | 47.6 | [8,421, 8,608] | 1.10% |
| 1,000 | 8,528.5 | 405.0 | 42.9 | [8,444, 8,613] | 0.99% |
| 2,000 | 8,489.6 | 280.8 | 27.7 | [8,435, 8,544] | 0.64% |
| 5,000 | 8,461.1 | 174.1 | 17.3 | [8,427, 8,495] | 0.40% |

- Point estimate **stable from N=500** (each rung inside the previous rung's 95% CI).
- MC error scaling exponent **−0.460** vs theoretical −0.500 (confirms 1/√N convergence).
- Realised antithetic **variance-reduction ≈ 10.0×**.

## Recommendation
**Recommended production scenario count = 2,000.** At the CBIRC C-ROSS ≥ 2,000 floor the 95% CI
half-width is already ~0.63% of |TVOG| (target ≤ 2%), so the **regulatory floor — not precision —
is the binding constraint**. Ignoring the antithetic variance reduction (naive iid) would
over-provision to ~20,341 scenarios. Diagnostic/UNSIGNED; re-baselining any governed figure onto a
revised count stays owner-gated.

## Verification
- NEW `tests/test_scenario_adequacy.py` — **24/24 GREEN** (unittest, numpy-only): iid SE identity,
  empirical error model + variance-reduction, CI construction, 1/√N diagnostics, analytic sizing vs
  the CBIRC floor, determinism, SHA-256 digest sensitivity, input validation, injected-runner, and
  the JSON/markdown deliverables.
- Regression `tests/test_sensitivity.py` — **45/45 GREEN** via a minimal pytest shim
  (scipy/pytest unavailable in the network-restricted sandbox; established prior-cycle pattern).

## Files changed
- A `par_model_v2/analysis/scenario_adequacy.py`
- M `par_model_v2/analysis/__init__.py` (exports)
- A `tests/test_scenario_adequacy.py`
- A `scripts/build_scenario_adequacy_study.py`
- A `docs/SCENARIO_ADEQUACY_CONVERGENCE_STUDY.md`, `docs/SCENARIO_ADEQUACY_CONVERGENCE_STUDY.json`
- M `docs/MODEL_STABILITY_AND_LIMITATIONS.md` (§2.1 pointer)
- M `docs/CONTINUOUS_IMPROVEMENT_ROADMAP.md` (§4.1 #5 → DONE; §5 Cycle Log row)

## Next queued
§4.1 **#6** — Backtest on real history (Kupiec POF + coverage on ≥10y CNY curve / CSI 300;
depends on item #1 live pipeline).
