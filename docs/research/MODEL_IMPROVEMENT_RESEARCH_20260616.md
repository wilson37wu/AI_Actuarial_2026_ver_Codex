# Model-improvement research — owner-decision support (2026-06-16, claude)

**Purpose.** The auto-admissible development frontier is exhausted (efficiency/diagnostic
pool MR-CAL-1 + MR-VR-1 + MR-VR-2 closed under the Phase 30 stop-rule; both VR studies
surfaced on the zero-install RESULTS UI at contract 1.23.0). Per the standing instruction
to "research further improvement and update the task prompt for next execution," this note
converts the open owner pivot into a **researched, prioritised recommendation**. No
model-form change is made here; everything below requires an explicit owner choice
before a cycle may start it.

**Model context.** PAR Endowment stochastic ALM & TVOG model. Current risk drivers:
stochastic rates (G2++/HW), equity, credit/spread, and a frozen-t dependence structure
(copula sophistication is barred by the Phase 30 stop-rule). Governed SCR headline
39,975.654628199336. Variance-reduction (Sobol-RQMC / stratified / RQMC+CV) already
delivers ~500x on the SCR tail.

---

## Ranked recommendation

### 1 (RECOMMENDED) — MR-LONGEV-1: add longevity/mortality as a 5th stochastic driver
**Model-FORM change → REQUIRES owner sign-off.** Highest actuarial materiality for a PAR
endowment book, whose liability is dominated by survival/maturity cash flows.

- **Method.** Standard, well-evidenced choices: **Lee-Carter** (single period factor,
  simplest to calibrate and explain) or **Cairns-Blake-Dowd (CBD)** two-factor period
  model (better at pensioner/older ages, the relevant range for endowment maturities).
  Both are the established benchmarks in the capital-modelling literature for mortality
  and longevity trend + idiosyncratic risk.
- **Integration.** Add a mortality-improvement state to the outer scenario set, feed
  survival probabilities into the existing projection engine, re-aggregate SCR with the
  current dependence structure. Keep it as an **additive driver** so the no-longevity
  path remains bit-identical (matches the project's backward-compatibility gate).
- **Effort/risk.** ~2–4 cycles (design-note → calibration → integration → SCR
  re-aggregation + governance ChangeRecord). Risk: re-baselines the governed headline →
  needs explicit owner sign-off and a fresh frozen reference.
- **Caveat to present:** opposing view is that adding a driver invites scope-creep the
  Phase 30 stop-rule was written to prevent; mitigant is the additive/sign-off discipline.

### 2 — LSMC proxy for SCR (efficiency, model-FORM-adjacent → sign-off)
**Least-Squares Monte Carlo** proxy to replace/accelerate the nested Value-at-Risk
calculation. Current literature (incl. 2025 ML/transformer extensions) shows large
runtime savings vs. full nested simulation while preserving SCR accuracy. Distinct from
the closed VR pool because it changes *how* SCR is computed (proxy regression), not just
sampling — so it is owner-gated, not auto-run. Good fit if the owner wants faster
end-to-end runs for the Phase IGUI "run the model" path.

### 3 — Phase IGUI resumption (NON-model-form, auto-runnable once confirmed)
Owner previously named Phase IGUI (actuarial Input & Run GUI) the exclusive next
priority. It relaxes zero-install for the *input* GUI only; the RESULTS UI stays
zero-install. Lowest model risk, directly user-facing, design-note-first. **This is the
safest productive pivot** if the owner does not want to re-baseline the headline.

### 4 — Packaging A/B/C (NON-model-form, auto-runnable once selected)
Build-spec + CI release-matrix + reproducible distribution. Pure delivery hardening; no
model effect. Lowest value to model quality, but unblocks handover/production-readiness.

### 5 — Freeze
Declare the auto-development frontier complete; cycles switch to maintenance/verification
only. Appropriate if the owner judges the model feature-complete for its purpose.

---

## Housekeeping the owner should also rule on (currently flagged, not auto-fixed)
1. `test_phase36_task5_phase_summary::test_contract_inventory` is RED on origin — frozen
   report pins contract 1.21.0 vs test ≥1.22.0 (now 1.23.0). One-line owner call:
   refresh the frozen report or relax the pin. Auto-fixable in <1 cycle if approved.
2. MR-016 / MR-017 copula-form residual disclosure — owner-pending decision.
3. ~29 pytest collection errors are environmental (numpy/scipy absent in CI sandbox),
   not regressions.

## Recommendation in one line
If willing to re-baseline → **MR-LONGEV-1 (Lee-Carter, additive)**. If not →
**resume Phase IGUI** as the safest productive pivot; clear the contract-inventory
test-gate drift opportunistically.
