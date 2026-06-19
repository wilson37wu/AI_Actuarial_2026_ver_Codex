# Owner Decision Brief — Auto Actuarial Stochastic Model (W69, 2026-06-19)

**Prepared by:** Claude Cowork autonomous dev agent (window W69)
**Audience:** Project owner (wilsonwukl@gmail.com)
**One-line ask:** Reply with **A / B / C / D / E** to set the next phase. Absent a reply, cycles continue as low-value verification heartbeats.

---

## Bottom line

Both auto-admissible development tracks are **complete**. The model is GREEN, reproducible, and byte-stable; the zero-install offline UI is feature-complete (15 governed charts + interactive viewer). **Every remaining forward step requires an owner decision** — there is no further autonomous work that adds real value. The project is at a clean stopping point and awaits a pivot.

## What is done (verified this cycle, byte-stable)

| Track | Status |
|---|---|
| Model build (Phases 1–36, IGUI, packaging design) | COMPLETE |
| MLMC efficiency frontier (mean: stages 1–3 wired; tail: stages 1–4b wired, opt-in) | COMPLETE, short of owner-gated stage 5 |
| Offline UI — graphical | COMPLETE: 15 inline-SVG governed charts + "jump to a chart" nav + "which view" chooser + drag-drop snapshot loader |
| Offline UI — interactive viewer (`ui_app.html`) | COMPLETE: tabbed, filterable, PNG/CSV/PDF export, ARIA a11y, jsdom 0-network self-test |

Governed anchors (unchanged W52→W69): nested 99.5% SCR headline **39975.654628199336**; `offline_home.html` md5 **03d6538d3cae9efb83062ecbfab096e9**; `ui_data.json` contract **1.23.0**.

W69 verification (throwaway venv numpy 2.2.6 / scipy 1.15.3 / pandas 2.3.3 / pytest 9.1.0):
`build_offline_home_validate` **177/177** · `offline_home_loader_parity` **10/10** · `tests/test_offline_home_validate` **4/4** · MLMC suite **53 passed / 0 failed** · stage-4b re-validation **PASS** (matched-cost VaR 2.620× / ES 2.858× / SCR 2.456×, G3 ≥2× PASS) · git clean after rebuild ⇒ byte-reproducible.

## The decision — five options

**A. MR-LONGEV-1 — add a 5th risk driver (longevity/mortality-trend).** *Model-form change; requires owner sign-off.*
Most material model improvement on the table. Adds a governed longevity SCR component and re-bases the headline. Highest effort, highest analytical value, and the only option that changes what the model measures.

**B. LSMC — Least-Squares Monte Carlo SCR proxy.** *Requires owner sign-off.*
A regression proxy for the nested SCR to cut runtime by ~1–2 orders of magnitude. Valuable if the model will be run repeatedly (e.g., for an input GUI). Does not change the governed answer; it approximates it faster.

**C. Phase IGUI — input + run GUI extensions.** *Auto-runnable.*
Note: the owner's standing directive specifies a **display-only** offline UI ("the calculation is completed with the stochastic model, then the user interface uses only the model output"). That UI already exists and is complete. IGUI (let the user set inputs and trigger a run) needs a compute runtime, which conflicts with the zero-install/display-only intent. Recommend only if the owner now wants an interactive *re-run* capability.

**D. Packaging A/B/C — frozen binary / vendored wheels / status quo.** *Design is auto; build is not.*
Produces a no-prerequisite compute bundle so a non-technical user can re-run the model. Blocked in-sandbox: needs a real build/release environment (PyInstaller or wheelhouse CI) the dev sandbox does not have. Owner or a CI runner must execute the build.

**E. Declare the frontier COMPLETE and FREEZE.** *Auto.*
Stamp the model + UI as done, stop the 12h cycles, archive the version. Cleanest option given both tracks are complete. Cycles can resume on demand.

**Stage 5 (cross-cutting):** making any MLMC tail figure the *governed default* needs owner sign-off **plus** a fresh frozen reference run. Prerequisite for treating the 2.4–2.9× efficiency gains as production, not diagnostic.

## Recommendation

**E (freeze) or B (LSMC), depending on intent.**
- If the model is "done for now" → **E**: freeze and stop burning cycles on verification heartbeats.
- If you intend to *use* the model interactively (re-runs, scenario input) → **B (LSMC)** first, then **D**, then **C** — that sequence makes re-runs fast, packaged, and GUI-driven in a coherent order.
- **A** only if a longevity driver is a genuine analytical requirement; it is the largest single change and re-bases the headline.

## Why no autonomous work was done beyond verification this cycle

The offline-UI graphic pool is saturated (15 charts covering capital, drivers, tail, copula families, management actions, aggregation, diversification, model selection). Adding a 16th would be a near-duplicate — explicitly ruled out by the W61/W68/W69 pointers. All model-form and packaging-build steps are owner-gated or need a build environment. The correct autonomous action was therefore: verify integrity, consolidate this brief, and hold.

## Evidence index

- Decision matrix: `docs/research/MODEL_IMPROVEMENT_RESEARCH_20260617.md`
- MLMC tail VR consumer note: `docs/research/MLMC_TAIL_VR_MODE_CONSUMER_NOTE_20260619.md`
- Stage-4b wiring evidence: `docs/validation/MLMC_TAIL_STAGE4B_WIRING_20260619.md`
- Offline UI: `offline_home.html` (landing) · `ui_app.html` (viewer) · `UI_README.md`
- Authoritative state: `.claude-dev/MODEL_DEV_STATE.json`
