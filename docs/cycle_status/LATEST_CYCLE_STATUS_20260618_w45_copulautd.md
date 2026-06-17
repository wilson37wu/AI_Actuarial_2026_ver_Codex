# Cycle status — Window #45 (claude) — W45 copula upper-tail-dependence strip

**Status:** COMPLETE — additive, decision-neutral offline-UI graphic shipped.
**Scope:** offline UI only. NO model-form change, NO governed-artifact change, NO contract bump.

## What shipped
Added a zero-install, zero-network inline-SVG **"Copula tail dependence — fitted candidates (upper)"**
(`svg id="copulautd"`) to `offline_home.html`. It DISPLAYS the three already-governed fitted
full-copula candidates' upper-tail-dependence coefficients (λ_U), read verbatim from
`capital.copula.copulas[].upper_tail_dependence`, on one shared scale:

| Copula | λ_U (governed, verbatim) | baked bar width (px) |
|---|---|---|
| Gaussian | 0.0000 | 0.0 |
| Student-t | 0.0046 | 109.7 |
| Survival Clayton | 0.0151 | 360.0 |

**Decision-neutral:** no bar is marked/selected — the model selects its aggregation copula by
**AIC, not by this metric**, and the governed headline stays the frozen-t basis. The 13th governed
landing-page graphic; complements W44 (fitted-candidate aggregated SCRs) by showing the same fitted
copulas' tail dependence. Derives no new number (each bar = value/max scaling of a governed number).

## Verification (all green)
- `build_offline_home_validate` **147/147** ok:true (was 137; +10 copulautd checks)
- `offline_home_loader_parity` **10/10**
- `tests/test_offline_home_validate` **4/4** (stdlib unittest)
- both inline `<script>` blocks `node --check` clean
- geometry parity EXACT: baked `cubar` widths (0.0 / 109.7 / 360.0) reproduced by JS `redrawCopulaUtd`
- governed artifacts (`ui_data.json`, `ui_app.html`, `combined_model_app.html`,
  `model_summary_card.html`, `model_result_viewer.html`) **byte-unchanged** (git status clean)
- headline **39,975.65** intact (1 occ); contract **1.23.0** unchanged; 0 external refs
- `offline_home.html` md5 `240ffd910ab9d6a7025d936ff5c36d7a`

## Files changed
`offline_home.html`, `scripts/build_offline_home.py`, `scripts/build_offline_home_validate.py`

## Next-execution pointer
Offline-UI graphic pool is now VERY rich (13 graphics). **STRONG RECOMMENDATION:** owner declares the
offline-UI graphical track COMPLETE and pivots to the MODEL frontier (MR-LONGEV-1 longevity 5th driver /
LSMC / MLMC sign-off; Packaging A/B/C; or freeze) or to Phase IGUI. If continuing the offline track,
one further auto-admissible decision-neutral graphic remains possible (e.g. a copula AIC/log-likelihood
strip reading `capital.copula.copulas[].aic`/`loglik`), additive only, gates green.
