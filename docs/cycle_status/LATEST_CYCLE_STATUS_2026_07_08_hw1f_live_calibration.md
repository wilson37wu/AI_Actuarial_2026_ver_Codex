# Cycle Status — 2026-07-08 — Roadmap 4.1 #2: HW1F swaption calibration on live/proxy quote set

**Agent:** claude (scheduled task `actuarial-model-daily-improvement`)
**Item:** §4.1 #2 — Execute HW1F swaption calibration on live/proxy quote set; parameter card with fit diagnostics (MR-001, MR-008)
**Status:** DONE — tests green, params UNSIGNED pending owner approval (per DoD)

## What shipped

- `par_model_v2/calibration/hw1f_live_calibration.py` — NEW:
  - `validate_swaption_surface_payload` — full-document schema validation
    (grid, curve arrays, r0, cap, currency) shared by all provenance tiers.
  - `SwaptionSurfaceLoader` — roadmap-#1 three-tier provenance
    (live_fetch / cached_snapshot / file_fixture) extended to swaption
    surfaces; SHA-256-sealed snapshots, tamper detection, live-tier
    validation FAIL-LOUD (never silently falls back to fixture),
    lineage approver `UNSIGNED_pending_owner_approval` for live fetches.
  - `DictSwaptionSource` — routes the resolved payload through the SAME
    `LiveSwaptionDataLoader` validation/assembly the Phase 13 path uses.
  - `run_hw1f_live_calibration()` — `calibrate()` end-to-end per market;
    PARAMETER CARD (JSON+MD) with SSE (bps², weighted), RMSE bps, max abs
    error bps, convergence (incl. documented Nelder-Mead polish stage when
    scipy>=1.15 L-BFGS-B ends ABNORMAL; governed calibrator untouched),
    params-at-bounds flags, fit table, gates G-02/G-12, lineage, inputs
    digest (idempotent), `"unsigned": true` + reason. Repository
    GovernanceStore never loaded/mutated.
- `scripts/build_hw1f_live_calibration_card.py` — NEW evidence builder.
- `docs/validation/HW1F_LIVE_CALIBRATION_PARAMETER_CARD.{json,md}` —
  committed evidence card (fixture tier).
- `docs/ESG_CALIBRATION_DATA_INTERFACES.md` — swaption live-path section.
- `tests/test_hw1f_live_calibration.py` — 18 new tests.

## Headline diagnostics (fixture tier, educational proxies)

| Market | a | sigma_r | RMSE (bps) | SSE (bps²) | Converged | At bound |
|---|---|---|---|---|---|---|
| CNY | 3.000000 | 0.033818 | 8.90 | 1.512e+03 | True (L-BFGS-B + NM polish) | a |
| HKD | 3.000000 | 0.041887 | 13.33 | 3.394e+03 | True (L-BFGS-B + NM polish) | a |

Gates: G-02 PASS (RMSE ≤ 25 bps both markets, not placeholder);
G-12 PASS (lineage + SHA-256 both markets).

`a` at the upper optimizer bound (3.0) is DISCLOSED on the card — the fit
prefers still-faster mean reversion; a known HW1F one-factor limitation, the
G2++ promotion (roadmap #7) is the structural fix.

## Tests

- New: `tests/test_hw1f_live_calibration.py` — 18 passed.
- Regression: `test_phase13_hw1f_calibration.py`, `test_live_market_data_pipeline.py`,
  `test_gui3_calibration_console.py`, `test_calibration.py`,
  `test_agent_lock_identity.py` — **146 passed / 0 failed** combined.
- Governed headline figures untouched (purely additive change set; no
  existing file modified except the docs above).

## Blockers / next

- Parameters remain **UNSIGNED** pending Model Owner approval of a
  credentialled vendor quote source (roadmap #1 restriction) — per the
  item's own DoD, so the item is DONE, sign-off is a standing owner action.
- Next queued OPEN item: §4.1 #3 — CBIRC 3.0% discount-cap remediation
  (validator ERROR above cap without approved ChangeRecord).

**Sandbox note:** the outputs-mount Edit-truncation failure mode recurred
while authoring (file tail truncated mid-line); repaired in the clone and
verified via `ast.parse` + full test rerun. Reinforces the standing rule:
edit in the clone, `cp` back, verify.
