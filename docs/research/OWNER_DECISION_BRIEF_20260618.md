# Owner Decision Brief — Auto-Actuarial Model (2026-06-18, W56, claude)

**Bottom line:** the auto-development frontier is genuinely complete. Eight consecutive
cycles (W49–W56) have produced no admissible work other than re-verifying green gates.
Every remaining step requires **one owner decision**. Until that decision arrives, further
auto-cycles add no value. This brief states the decision and recommends a default.

---

## 1. What is DONE (no further auto-work admissible)

- **Stochastic model:** PAR Endowment ALM & TVOG, 4 governed risk drivers (rates G2++/HW,
  equity, credit/spread, frozen-t dependence). Governed SCR headline **39,975.654628199336**.
  Variance reduction already ~500× on the SCR tail. Contract **1.23.0**.
- **Offline interactive RESULTS UI — fulfils the owner directive** ("UI uses only model
  output to display the result graphically and interactively, zero pre-install"):
  `offline_home.html` is **zero-install, zero-network, self-contained**. It surfaces
  **every** governed figure in `ui_data.json` verbatim across **15 inline-SVG charts**
  (capital bridge, SCR-by-driver, tail convergence, VaR/ES CIs, nested-vs-copula CI,
  ES-vs-VaR margin, copula family/AIC/log-likelihood/tail-dependence, with-actions ladder,
  management-action relief, aggregation-method margin, diversification overlay) **plus** an
  accessible "Jump to a chart" navigator, a **drag-and-drop snapshot loader** (re-renders
  every chart from a different model-output JSON, fully client-side via FileReader) and a
  **Reset**. Companion full apps: `ui_app.html`, `model_result_viewer.html`,
  `combined_model_app.html`, `model_summary_card.html`.
- **Why the chart pool is exhausted:** the discipline is decision-neutral, verbatim display
  of governed output. There are no remaining un-surfaced governed figures to chart. Any
  further chart would duplicate or derive — both barred by the Phase-30 stop-rule.

## 2. The ONE decision (pick a single option)

| # | Option | Type | Auto-runnable? | Effort | When to pick |
|---|---|---|---|---|---|
| A | **MR-LONGEV-1** — add longevity/mortality as a 5th stochastic driver (Lee-Carter or CBD) | Model-FORM change → **re-baselines the headline** | No — sign-off | ~2–4 cycles | Highest actuarial materiality for an endowment book |
| B | **LSMC** least-squares-MC SCR proxy | Model-FORM-adjacent (changes how SCR is computed) | No — sign-off | ~2–3 cycles | Want faster end-to-end runs |
| C | **Phase IGUI** — actuarial Input & Run GUI (relaxes zero-install for INPUT only; results UI stays zero-install) | Non-model-form | **Yes, once confirmed** | design-note first | Want user-facing progress, no headline re-baseline |
| D | **Packaging A/B/C** — code-sign + CI release matrix + reproducible distribution | Non-model-form | **Yes, once selected** | ~1–2 cycles | Want production/handover hardening |
| E | **FREEZE** — declare the auto-development frontier complete; cycles switch to verification-only | — | Yes | n/a | Model is feature-complete for its purpose |

**Recommendation (absent other priorities): C (Phase IGUI) or E (Freeze).**
C is the safest *productive* pivot — directly user-facing, no headline re-baseline, and you
already named it the exclusive next priority on 2026-06-14. E is correct if you judge the
model feature-complete. A is the highest-value *model* step but re-baselines the governed
headline and must not run without your explicit sign-off.

## 3. What I need from you (one line back is enough)

> "Do **A / B / C / D / E**." (Optionally: a sign-off sentence for A or B.)

Until then, auto-cycles will continue verification-only to avoid any unsanctioned change.

## 4. Standing ops note
The `/sessions` Cowork workspace mount has repeatedly read **100% full** at cycle start.
All git is done in a fresh `/tmp` clone of `origin/main` (origin = source of truth), so this
does not block development, but the mount needs housekeeping.

*Full ranked analysis: `docs/research/MODEL_IMPROVEMENT_RESEARCH_20260617.md`.*
