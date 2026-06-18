# Design Note — Multilevel Monte Carlo (MLMC) for the nested SCR inner loop

**Window:** W57 (claude, 2026-06-18, 18:00Z window). **Status:** DESIGN-NOTE-FIRST (no
implementation this cycle). **Classification:** efficiency / estimator-only — **NOT a
model-form change**, **NO contract bump**, **NO headline re-baseline**. This note is the
design-note-first prerequisite the model-improvement research matrix
(`MODEL_IMPROVEMENT_RESEARCH_20260617.md`, Option 3) names for the MLMC pivot, written so
the owner (or a later cycle, once confirmed) can move straight to a gated implementation.

It exists to **break the W49–W56 verification-heartbeat loop with forward research** while
respecting the standing discipline: additive only, gates stay green, governed artifacts
byte-unchanged, headline `39,975.65` bit-identical.

---

## 1. Problem statement

The governed SCR is produced by a **nested** estimator: an outer set of real-world
scenarios, each re-valued by an inner set of risk-neutral paths. In the code the inner
cost is the dominant term and is parametrised by `nested_n_inner` (eval benchmark = **256**
inner paths; see `multi_driver_proxy_validation_6d_remediation.py`, estimator
`nested_stochastic_tvog.capital_metrics_from_liabilities`). Cost scales roughly as
`n_outer × nested_n_inner`. The existing closed variance-reduction (VR) pool
(Sobol-RQMC / stratified / RQMC+CV, ~500× on the SCR tail) optimises the **outer**
sampling; it does **not** reduce the per-state inner cost. The inner loop is therefore the
remaining lever for runtime headroom **without** changing the model or the headline.

## 2. Approach — MLMC over inner-path resolution

Replace the single fixed-`nested_n_inner` inner estimator with a **telescoping multilevel
estimator** over a geometric ladder of inner-path counts
`N_ℓ = N_0 · M^ℓ`, ℓ = 0..L (e.g. `N_0 = 16`, `M = 2` → 16, 32, 64, 128, 256). The
conditional liability for an outer state is estimated as

```
E[Y] ≈ E[P_0] + Σ_{ℓ=1..L} E[P_ℓ − P_{ℓ−1}]
```

where `P_ℓ` is the inner-path liability estimate at level ℓ. Most of the work is spent at
the cheap coarse levels; only a few outer states need the expensive fine level to control
the correction-term variance. **Antithetic inner sampling** (2025 optimised-MLMC-for-
nested-simulations parametrisation, arXiv 2510.18995) couples the fine and coarse inner
estimators on each level so the difference `P_ℓ − P_{ℓ−1}` has small variance, which is
what makes the telescoping cheap. Per-level path budgets are set by the standard MLMC
cost-variance optimal allocation.

Crucially, the telescoped expectation **converges to the same conditional liability** as
the fixed `N_L = 256` inner estimator (the finest level is identical to the current
benchmark). MLMC re-organises *how* the inner expectation is accumulated; it leaves the
model, the loss-distribution definition, and the governed SCR definition **unchanged**.

## 3. Why this is auto-admissible (not sign-off)

| Dimension | LSMC proxy (Option 2) | **MLMC inner (Option 3)** |
|---|---|---|
| Changes *how* SCR is computed? | Yes — regression proxy replaces re-valuation | **No — same re-valuation, re-organised estimator** |
| Re-baselines the headline? | Possibly | **No (equivalence-gated to current SCR)** |
| Owner sign-off? | Required | **Not required if equivalence gate passes** |
| Governance analogue in repo | OOS proxy-validation (Phase 22) | Same OOS/equivalence discipline, tighter |

MLMC is therefore the **lowest-risk productive pivot** the research matrix identified: it
needs only a design-note-first cycle (this note) and a same-headline equivalence gate.

## 4. Integration points (no model-form change)

- Estimator entry point: `nested_stochastic_tvog.capital_metrics_from_liabilities` —
  introduce an **optional** `inner_estimator="fixed"|"mlmc"` argument; default stays
  `"fixed"` so every governed run, and the frozen reference, are **byte-identical** until
  the owner flips the default.
- Seeds: reuse the slice-stable CRN protocol already in the codebase
  (`SeedSequence(seed).spawn(...)`), assigning disjoint sub-streams per level so the coarse
  estimator inside `P_ℓ` reuses the first `N_{ℓ−1}` of the level-ℓ draws (antithetic
  coupling), keeping staged == monolithic reproducibility.
- The outer VR pool is untouched; MLMC is orthogonal and composes with it.

## 5. Pre-registered gates (must be defined BEFORE any implementation)

Reusing and tightening the existing Phase 22 proxy-validation gate discipline (OOS R²≥0.95
AND VaR/ES/SCR rel-err ≤10% AND leakage-free AND overfit-gap ≤0.05):

1. **Same-headline equivalence (frozen snapshot).** On the governed frozen inputs, the
   MLMC SCR must equal the fixed-256 SCR within the fixed estimator's own bootstrap 95% CI,
   AND the headline `39,975.65` must remain **bit-identical** while `inner_estimator`
   defaults to `"fixed"`. If MLMC is ever made default, re-baseline requires owner sign-off
   (out of scope here).
2. **Tail accuracy.** 99.5% VaR, ES and SCR relative error ≤ **1%** vs the fixed-256
   benchmark (stricter than the 10% proxy gate — MLMC is an unbiased estimator of the SAME
   quantity, not an approximating surface, so a tight band is appropriate).
3. **Variance-decay / cost.** Empirical level variances `V_ℓ` must decay (MLMC theory
   `V_ℓ → 0`); report the achieved cost ratio vs fixed-256 and require a net cost reduction
   ≥ **2×** at equal-or-better SCR CI width, else the candidate is rejected (no value).
4. **Reproducibility.** staged == monolithic, bit-identical under the documented seed
   protocol; both code paths `node`/`pytest` clean.
5. **No spillover.** Governed artifacts (`ui_data.json`, `ui_app.html`,
   `combined_model_app.html`, `model_summary_card.html`, `model_result_viewer.html`,
   `offline_home.html`) byte-unchanged while default = `"fixed"`; contract stays `1.23.0`.

A candidate that fails gate 1 or 2 is rejected outright (correctness). A candidate that
passes 1–2 but fails 3 is **shelved** (correct but not worth the complexity) — recorded,
not merged.

## 6. Staged plan (each stage is one future cycle, gated)

1. **(this note)** Design + pre-registered gates. ✔
2. Prototype MLMC inner estimator behind the opt-in flag; unit-test the telescoping
   identity (`N_L`-only path == fixed-256 bit-for-bit).
3. Equivalence + tail-accuracy validation (gates 1–2) on the frozen snapshot; produce a
   validation card analogous to `SIX_DRIVER_OOS_VALIDATION_CARD.md`.
4. Cost/variance-decay study (gate 3); decide merge-as-opt-in vs shelve.
5. (owner sign-off ONLY) consider making MLMC the default — re-baseline + fresh frozen
   reference.

## 7. Rollback / safety

Because MLMC ships **opt-in with `"fixed"` as default**, every stage up to 4 is a pure
no-op for the governed headline and all governed artifacts; rollback is "delete the
optional branch." No model parameter, copula, or aggregation choice is touched at any
stage. No owner sign-off is consumed until stage 5, which is explicitly out of scope.

## 8. Owner ask (one line)

If you want inner-loop runtime headroom without re-baselining, approve proceeding to
**stage 2** (prototype behind the opt-in flag); otherwise this note simply de-risks the
option and the next cycle returns to the single verification pass + decision brief.

---

### Sources (consulted; carried from the model-improvement research matrix)
- Optimized Multi-Level Monte Carlo Parametrization and Antithetic Sampling for Nested Simulations (arXiv 2510.18995, 2025): https://arxiv.org/pdf/2510.18995
- Transformers-based Least Square Monte Carlo for Solvency Calculation in Life Insurance (ScienceDirect, 2025): https://www.sciencedirect.com/science/article/abs/pii/S0167668725001106
- Neural networks meet least squares Monte Carlo at internal model data (European Actuarial Journal, 2022): https://link.springer.com/article/10.1007/s13385-022-00321-5
- Giles (2008/2015), Multilevel Monte Carlo methods — foundational estimator.
- Repo precedent: Phase 22 six-driver OOS proxy-validation gate (`multi_driver_proxy_validation_6d_remediation.py`); nested estimator `nested_stochastic_tvog.capital_metrics_from_liabilities`.
