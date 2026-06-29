# Cycle Status — 2026-06-29 — Phase 38 Task 2 (AUTO, claude)

**Verdict: PASS.** Phase 38 Task 2 executed and fully verified. 5yr & 10yr governed
PAR-endowment reference runs generated and surfaced in `cashflow_products.html` behind a
product/term selector. Display-only, traceable, governed bytes unchanged.

- **Cycle:** Claude auto 18:00 UTC window · lock `2026-06-29T19:43Z-ae4f` · one task only.
- **Admissibility:** auto-admissible (new reference-run JSON + offline-UI display work; no
  model-form change, no contract bump, governed headline byte-identical).

## What shipped
| File | Change |
|---|---|
| `scripts/build_projection_reference.py` | Refactor → `build_product(term)`, `assemble_reference_run(term)`, `write_reference(term, out)`; `main()`=20yr. 20yr output byte-identical (modulo `generated_utc`). |
| `scripts/build_projection_reference_terms.py` | **New.** Reuses `write_reference` → `PROJECTION_REFERENCE_RUN_5YR.json` (60mo) + `_10YR.json` (120mo). |
| `docs/validation/PROJECTION_REFERENCE_RUN_5YR.json` | **New** governed term-variant run. |
| `docs/validation/PROJECTION_REFERENCE_RUN_10YR.json` | **New** governed term-variant run. |
| `scripts/build_cashflow_products_view.py` | Reads all three runs; embeds keyed 5/10/20; adds product/term selector (default 20yr); re-renders on switch. Still 0-calc, 0 external refs. |
| `cashflow_products.html` | Regenerated (89,701 bytes; 5/10/20yr embedded; 0 external refs). |

20yr governed file `PROJECTION_REFERENCE_RUN.json` **not touched**.

## Reference-run numbers (governed engine; single-policy fund preset)
| Term | Months | PV prem | PV guar | PV net liab | AS @ maturity |
|---|---|---|---|---|---|
| 5yr  | 60  | 224,336 | 590,269 | 476,189 | 207,375 |
| 10yr | 120 | 375,205 | 440,432 | 238,539 | 387,881 |
| 20yr | 240 | 579,170 | 288,852 | −41,079 | 754,361 |

## Verification — all GREEN
- Refactor reproduces 20yr **byte-for-byte** (diff modulo `generated_utc`).
- `node --check` clean · HTML stdlib-parsed · **render-smoke + term-switch PASS** (panels populate, `<svg>` emitted, 5/10/20 → 60/120/240 months).
- **Data traceability 96/96 PASS** across 5/10/20 (every asset/liability/net series + PV strip == source; benefit aggregates = sum of displayed rounded components). 0 external refs. JSON re-parsed after write.
- **Governed byte-stable:** `offline_home.html` `03d6538d…` · `ui_app.html` `d82c65ec…` · `ui_data.json` contract `1.23.0` · headline `39975.654628199336`.
- **Gate C:** `self_test_ok:true` + `engine_ready:true`; `run_model` smoke bit-match **49657.9 / 37499.0 / 30267.9**.
- **Integrity:** offline_home **177/177** · pytest **4/4** · loader-parity **10/10** · MLMC **53/53**.
- **Gate D:** spec AST · workflow YAML · `offline_bootstrap --self-test` · `build_phase_pkg_task1_validate` — all ok.

## Next / blockers
- **Phase 38 Task 3 (ui_app cutover) is OWNER-GATED.** Folding Cash Flows + Products + Phase 37
  Scenario Explorer into the byte-pinned `ui_app.html` requires (a) a `ui_data` **contract bump** +
  **sha256 re-baseline** across ~10 gate scripts (owner sign-off) and (b) a **jsdom-equipped env**
  for `ui_app_self_test.cjs` (absent in-sandbox). All auto-admissible Phase 38 UI work is complete.
- If the next auto-run finds Task 3 still gated, per standing instruction: verification + mount-sync
  pass + one researched improvement (no near-duplicate graphics, no model-form change).
