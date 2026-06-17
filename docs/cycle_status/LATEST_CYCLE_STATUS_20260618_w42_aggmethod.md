# Cycle status — W42 (claude) — Offline-UI aggregation-method margin strip

**When:** 2026-06-17T19:20:00Z
**Type:** Additive, decision-neutral offline-UI inline-SVG graphic. No model-form change, no governed-artifact change, no contract bump.

## What shipped
Added a zero-install, zero-network inline-SVG **"Var-covar vs nested SCR — aggregation-method margin"** strip (`svg id="aggmethod"`) to `offline_home.html`. It displays two already-governed 99.5% SCR figures as two point markers on one shared scale:

- **Var-covar / correlated SCR** (`capital.correlated_scr` = $47,293)
- **Nested-simulation SCR** (`capital.nested_scr` = $48,707)

The region between them is shaded as the **aggregation-method margin** (how far the full nested simulation sits from the linear var-covar approximation). Both endpoints are read verbatim; the margin is shown purely graphically and **derives no new number** — the would-be diff string `1,415` is gate-asserted ABSENT. Decision-neutral: both are governed bases shown neutrally, the governed headline stays the frozen-t basis and no basis is selected. The 10th governed graphic on the landing page.

Snapshot-loader parity: each `<rect>/<line>/<text>` carries a namespaced `data-series` (`agmvarcov`/`agmnested`/`agmgap`, no collision with W33–W41); `redrawAggMethod` (mirroring `_aggmethod_svg`) redraws on snapshot load and Reset restores it.

## Files changed
- `offline_home.html` (md5 `36c3e68ca4c0671ca261f8fbdf2c2c43`)
- `scripts/build_offline_home.py`
- `scripts/build_offline_home_validate.py` (+9 checks)

## Verification
- `python -m py_compile` clean; `build()` OK 64,810 bytes, 0 external refs
- `build_offline_home_validate` **115/115** ok:true (was 106; +9 aggmethod checks)
- `offline_home_loader_parity` **10/10** ok:true
- both inline `<script>` blocks `node --check` clean
- baked SVG geometry node-verified: varcov x=124.0 / nested x=424.0 / gap x=124.0 w=300.0 reproduced exactly by the `redrawAggMethod` mirror (loader/Reset parity, values verbatim)
- governed artifacts byte-unchanged (git-diff clean): `ui_data.json`, `ui_app.html`, `combined_model_app.html`, `model_summary_card.html`, `model_result_viewer.html`
- headline **39,975.65** intact (1 occ); contract **1.23.0** unchanged
- git in a fresh /tmp ext4 clone; mounted `.git` untouched; edits applied programmatically (avoids virtiofs in-place-editor truncation)

## Next
Offline-UI graphical track stays OPEN per owner directive. MODEL frontier remains OWNER PIVOT (MR-LONGEV-1 / LSMC / MLMC sign-off; Packaging A/B/C; or declare frontier complete & freeze).
