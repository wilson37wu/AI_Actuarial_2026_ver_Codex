# Post-Phase-IGUI Task 5 — Offline-UI MR-VR-1 Variance-Reduction Efficiency Panel

**Verdict: PASS.** ADDITIVE offline-UI surface for the governed MR-VR-1 inner-path
variance-reduction study; data contract **1.21.0 → 1.22.0** (one new top-level key
`postigui_vr`). Display-only — every figure is carried bit-for-bit from
`docs/validation/POSTIGUI_TASK4_VARIANCE_REDUCTION.json` (study digest
`cc0c2fea…`); nothing is recomputed in the layer or in the browser.

## What was surfaced (new "Variance Reduction (MR-VR-1)" tab)

- **Work-normalised VR ratios with 95% CIs and the ≥1.5× useful bar:** antithetic
  1.882× [1.456, 2.403] useful; CRN 18.93× [14.67, 24.30] useful; Sobol-RQMC
  2241.11× [1841.07, 2729.70] useful.
- **Effective sample size:** antithetic 7,709; CRN 77,533; Sobol-RQMC ≈ 9.18 M.
- **Inner-path count n\* for target SE_rel = 1%:** crude 19,064; antithetic 10,129;
  CRN 1,007; Sobol-RQMC ≈ 8.5.
- **Unbiasedness:** all estimators within 0.5% of the analytic / crude reference.
- **Antithetic at 99.5% — INEFFECTIVE (disclosed):** work-normalised ratio 1.314×
  [1.037, 1.692], below the 1.5× bar, consistent with the recorded outer-basis
  precedents (0.72× / 0.78×).
- **Governed-headline invariance:** frozen-t component SCR 39,975.654628199336
  BIT-IDENTICAL; indicated adoption dSCR −1.38e-05 rel is immaterial → REPORTED,
  NOT applied.

## Verification

- `scripts/ui_app_self_test.cjs` → **ok:true, 421 checks, tabCount 20, 0 network /
  0 JS errors** (+16 new VR checks).
- New pure-Python suite `tests/test_postigui_task5_vr_panel.py` — 13 checks PASS.
- `offline_viewer_self_test.cjs` (11) and `combined_gui_self_test.cjs` (27) remain
  ok:true (unchanged artifacts).
- `scripts/build_ui_pipeline.py --check` — chain validates contiguously to 1.22.0;
  embedded payload equals standalone `ui_data.json`; A2 per-section SHA-256 digests
  recomputed (new `postigui_vr` section digested, root recomputed) and re-verified
  via Node; **0 external references**.
- Updated layer-aware tests advanced to 1.22.0: H1 contract guard, A2 digests,
  E3 evidence pack, pipeline reconcile (phase-summary literal advanced; pytest
  absent in dev sandbox so executed structurally).

## Governance

ChangeRecord `16d987632ecc42569f4d4665dd56582e` (code_change) **OWNER_REVIEW**;
records 114 → 115; audit 142 → 143; 17 risk items; audit integrity OK.

## Constraints honoured

Variance reduction is a numerical-efficiency change (admissible under the binding
Phase 30 stop-rule — not a copula-structure candidate). NO model parameter changes;
governed headline unchanged; MR-016 / MR-017 dependence decision not pre-empted;
zero-install invariants preserved (single self-contained `file://` HTML, no storage
API, 0 external refs).
