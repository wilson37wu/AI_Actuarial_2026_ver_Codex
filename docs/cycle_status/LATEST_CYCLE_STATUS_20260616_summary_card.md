# Cycle status — 2026-06-16 (claude, window #20): printable model summary card

**Status:** GREEN — one additive, decision-neutral offline-UI task shipped.
**Frontier:** still OWNER PIVOT for the *model* (no model-form change auto-ran).

## What changed
Shipped `model_summary_card.html` — a printable one-page **model summary card**
generated from the model-output snapshot `ui_data.json` (NEXT-EXECUTION pointer
option (b)). It lays out, print-optimised (A4 `@page` + `@media print`, with an
embedded "Print / Save as PDF" button calling `window.print()`):

- the governed headline SCR component (frozen single-df t, df 2.9451);
- the capital basis (nested / tail-matched t-copula / selected-copula / var-covar /
  standalone sum / diversification benefit);
- the seven standalone risk-driver SCRs (rate, equity, credit, lapse, mortality, FX,
  liquidity);
- tail & convergence metrics (99.5% / 12m, VaR & ES point, convergence verdict);
- a validation + governance scorecard (gates 12/12, verdicts PASS count, tasks 118/118,
  audit 81/81 verified) and a curated "key validated results" list.

Every number is copied **verbatim** from the snapshot — the card recomputes nothing.
The card was also surfaced on `offline_home.html` as one extra zero-install "Open a
view" card for discoverability (`offline_home` rebuilt deterministically).

New files: `model_summary_card.html`, `scripts/build_model_summary_card.py`,
`scripts/build_model_summary_card_validate.py`,
`docs/cycle_status/LATEST_CYCLE_STATUS_20260616_summary_card.md`.
Modified: `scripts/build_offline_home.py` (+1 VIEWS entry), `offline_home.html` (rebuilt).

## Verification
- build_model_summary_card.py → OK, 0 external refs
- build_model_summary_card_validate.py (stdlib gate) → ok:true **25/25**
  (headline + capital + all 7 drivers + tail + scorecard verbatim; print affordance;
  `@media print`/`@page`; self-contained; 0 external refs)
- build_offline_home_validate.py (stdlib gate) → ok:true **19/19**
- offline_home_loader_parity.cjs (node) → ok:true **10/10**
- py_compile clean on all three scripts
- `ui_app.html` sha256 **d82c65ec… BYTE-UNCHANGED**; governed headline
  39975.654628199336 present; `ui_data` contract 1.23.0 (unchanged)

## Incident (recovered, no impact on shipped artifacts)
The in-place file editor corrupted the **mount** copy of `build_offline_home.py`
mid-write (the documented virtiofs no-rename hazard). Recovered by re-doing the edit
inside the `/tmp` clone and `cp`-ing the clean file back to the mount; the mount was
then verified byte-identical to the clone (sha match on all five touched files).
Lesson reinforced: edit large existing files in the clone, not in place on the mount.

## Owner actions still pending (unchanged)
1. MR-LONGEV-1 longevity 5th driver — model-form change, **needs sign-off**.
2. LSMC inner-loop replacement — **needs sign-off**.
3. Option-A frozen-binary publish — **code-signing cert + publish channel** (owner/infra).
4. Phase PKG Task 2 — onedir-vs-onefile final call + publish channel (owner/infra).
5. Or declare the auto-development frontier complete and **freeze**.

## Next auto-admissible offline-UI task
Option (c): consolidate the four result views' descriptions + a short "which view do
I want?" chooser on `offline_home.html` (decision-neutral, additive, zero-network).
