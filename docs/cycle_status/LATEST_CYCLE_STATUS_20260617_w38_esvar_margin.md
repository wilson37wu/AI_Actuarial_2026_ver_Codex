# Cycle status — 2026-06-17 Window #38 (claude)

**Task:** Offline-UI W38 — add a 6th decision-neutral, zero-install inline-SVG graphic (VaR-vs-ES tail-thickness margin strip) to `offline_home.html`.

**Status:** COMPLETE. Additive, decision-neutral, zero-network. No model-form / governed-artifact / contract change.

## What shipped
- New inline-SVG `id="esvarmargin"` on the offline landing page: the governed 99.5% VaR ($158,701) and ES ($163,080) shown as two markers on one shared scale, with the gap between them shaded as the tail-thickness margin.
- Pure display — every coordinate is value/range scaling of a governed number; the ES−VaR gap is graphical only (the diff string `4,379` is gate-asserted ABSENT, so no number is derived).
- Redrawn by the snapshot-loader (`redrawEsVarMargin`); Reset restores the built-in snapshot.

## Verification
- `build_offline_home_validate.py`: **80/80** ok:true (+8 esvar checks).
- `offline_home_loader_parity.cjs`: **10/10** ok:true.
- `py_compile` clean; both inline `<script>` blocks `node --check` clean.
- Baked SVG geometry node-verified vs the redraw mirror (gap x=124.0/w=300.0; VaR x=124.0; ES x=424.0 — exact match).
- Governed artifacts (`ui_data.json`, `ui_app.html`, `combined_model_app.html`, `model_summary_card.html`, `model_result_viewer.html`) BYTE-UNCHANGED vs HEAD.
- Headline `39,975.65` intact (1 occ); contract `1.23.0` unchanged.
- `offline_home.html` md5: `b6c19b78811a87577158adb14672f28c`.

## Next
Offline-UI graphical track stays OPEN. Next single auto-admissible item: a diversification waterfall (standalone_sum → correlated_scr → nested_scr, div_benefit_nested labelled) or a neutral copula-family mini-comparison. MODEL frontier remains OWNER PIVOT.
