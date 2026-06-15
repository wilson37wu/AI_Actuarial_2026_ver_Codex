# Cycle Status - Post-Phase-IGUI Task 2 (2026-06-15, Claude Cowork)

**Task:** Implement candidate **MR-CAL-1** - credentialled-data calibration-residual
diagnostics on the seven FROZEN standalone risk-driver margins {rate, equity,
credit, lapse, mortality, fx, liquidity} - under the six pre-registered gates
G1-G6 (frozen in `docs/validation/POSTIGUI_TASK1_DESIGN_NOTE.md`).

**Result: COMPLETE - gate 16/16 (G1-G6) green; 11/11 unit tests PASS.**

## What landed

- `par_model_v2/calibration/credentialled_residual_diagnostics.py` (NEW) -
  diagnostics-only, dependency-light (numpy + stdlib): `math.erf` normal CDF,
  Acklam normal quantile, closed-form KS and Anderson-Darling (the dev sandbox
  has no scipy).
- `scripts/build_postigui_task2_diagnostics.py` (NEW) - report builder + governance.
- `tests/test_postigui_task2_diagnostics.py` (NEW) - 11 tests (both credibility branches).
- `docs/validation/POSTIGUI_TASK2_DIAGNOSTICS.{json,md}`, result card.

## Findings (EDUCATIONAL; synthetic credentialled-reference stub)

- **G1** Frozen margins + governed frozen-t headline `39,975.654628199336`
  recovered **BIT-IDENTICAL** (max abs dev **0.0**, tol 1e-9).
- **G4** Gap vs nested `46,638.9` decomposes EXACTLY (reconciliation error 0):
  total `6,663.245` = copula-FORM `6,120.197` (**91.85%**) + margin-calibration
  `543.049` (**8.15%**). The copula FORM dominates - consistent with Phase 26-29;
  margin calibration is the minor contributor.
- **G5** Limited-fluctuation credibility Z + credibility-weighted indicated dSCR
  **0.904%** of headline (< 1% threshold) -> **IMMATERIAL, REPORTED, NOT applied**;
  no new model-risk opened. (A monkeypatched large-perturbation test confirms the
  MATERIAL branch DOES open an OPEN model-risk entry.)
- **G6** Idempotent digest `1a3119de177b4dcd01fbb5212f36ff8623ed2100dc827411d6801f3b31f5661a`;
  report-only (no offline-UI surface added; `ui_app.html` byte-unchanged).

## Governance

- ChangeRecord `a6b09b75418741af8d6468febb87a77d` - `governance_change`, **OWNER_REVIEW**.
- Records 111 -> 112; audit 139 -> 140; integrity OK; contract `1.21.0` unchanged.

## Constraints honoured

NO model parameter change; NO copula structure (Phase 30 binding stop-rule);
MR-016 / MR-017 and the A/B/C packaging decision NOT pre-empted; one task per cycle;
fresh-clone git per `AGENT_COORDINATION.md`; end-of-run owner email.

## Next

**Post-Phase-IGUI Task 3** - design-note pre-register the next candidate **MR-VR-1**
(inner-path antithetic / CRN variance reduction for TVOG) with fixed gates; OR pivot
to the packaging A/B/C build-spec if the owner selects one; OR offline-UI usability
per the standing UI directive.

## Open owner decisions (unchanged)

1. No-prerequisite COMPUTE packaging path - Option A (frozen binary, recommended) /
   B (vendored wheels) / C (status quo, documented).
2. MR-016 / MR-017 dependence decision.
