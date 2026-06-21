# Cycle Status — 2026-06-18 Window #46 (claude)

**Task (one):** W46 — additive, decision-neutral offline-UI graphic: "Copula model-selection criterion — fitted candidates (AIC)".

**Status:** COMPLETE. Gates green. Lock held by claude for this cycle, released at end.

## What shipped
Added a zero-install, zero-network inline-SVG mini bar set (`svg id="copulaaic"`) to `offline_home.html` that DISPLAYS the three GOVERNED fitted full-copula candidates' AIC, read verbatim from `capital.copula.copulas[].aic`:

| Copula | AIC (governed, verbatim) | Bar width (px) |
|---|---|---|
| Gaussian (AIC-selected) | -332.6774 | 360.0 |
| Student-t | -324.2924 | 350.9 |
| Survival Clayton | -12.0279 | 13.0 |

Bar length = `|aic| / max(|aic|)` scaled to 360px; the signed AIC is printed verbatim (4dp). AIC IS the model's governed copula-selection criterion (lower = better, Solvency II Art. 234), so — unlike the W45 upper-tail-dependence metric — the GOVERNED minimum-AIC / `selected_copula` (Gaussian) is marked "▸ AIC-selected". The tag DISPLAYS the governed selection; it derives nothing. The 14th governed landing-page graphic.

## Verification
- `build_offline_home_validate`: **158/158** ok:true (was 147; +11 copulaaic checks)
- `offline_home_loader_parity`: **10/10**
- `tests/test_offline_home_validate`: **4/4** (stdlib unittest)
- Both inline `<script>` blocks: `node --check` clean
- Geometry parity: EXACT — baked SVG widths reproduced by the JS `redrawCopulaAic` mirror (uses `Math.abs`)
- Governed artifacts (`ui_data.json`, `ui_app.html`, `combined_model_app.html`, `model_summary_card.html`, `model_result_viewer.html`): **byte-unchanged** (git status clean)
- Headline **39,975.65** intact (1 occ); contract **1.23.0** unchanged
- `offline_home.html` md5 now `19a307df68fc9f7f669f0cae90adbb23`

## Git hygiene
All git in a fresh `/tmp` ext4 clone of `origin/main`; mounted `.git` untouched. Builder regenerated `offline_home.html` in the ext4 clone to avoid the documented virtiofs in-place-editor truncation.

## STRONG RECOMMENDATION (unchanged, escalating)
The offline-UI graphic pool is now VERY rich (FOURTEEN governed graphics). The owner should **declare the offline-UI graphical track COMPLETE** and pivot to either (a) the MODEL frontier (MR-LONGEV-1 longevity 5th driver / LSMC / MLMC sign-off; Packaging A/B/C; or freeze) — decision matrix `docs/research/MODEL_IMPROVEMENT_RESEARCH_20260617.md`, or (b) the owner-directed EXCLUSIVE Phase IGUI (Actuarial Input & Run GUI; design-note first). Continuing to add near-duplicate landing-page graphics is low marginal value.
