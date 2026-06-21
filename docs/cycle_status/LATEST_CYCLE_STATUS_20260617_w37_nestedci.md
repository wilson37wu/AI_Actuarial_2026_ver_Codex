# Cycle Status — 2026-06-17 Window #37 (claude)

**Task:** Offline-UI graphic — "Nested vs copula-simulated VaR — confidence intervals" (additive, decision-neutral).
**Outcome:** SHIPPED. No model-form / governed-artifact / contract change.

## What shipped
Added a zero-install, zero-network inline-SVG comparison (`svg id="nestedci"`) to `offline_home.html`.
It displays the governed 99.5% VaR estimate as a Monte-Carlo confidence band from two governed
estimators on one shared scale:

- **Copula-simulated** band — `tail.var_ci` = [158,421; 158,961] (tight; the converged estimator)
- **Nested** band — `tail.nested_var_ci` = [155,619; 165,809] (wide; computed at only
  `tail.nested_n_outer` = 160 outer scenarios)
- Both rows mark the **same** governed point `tail.final_var` = $158,701, which lies inside both bands.

Pure display: every x-coordinate is a value/range scaling of a governed number; nothing is derived.
It complements the W36 VaR/ES CI strip by isolating estimator-choice sampling uncertainty for VaR
(the nested band, 350px, visibly dwarfs the copula band, 18.5px).

## Files changed
- `offline_home.html` (regenerated; md5 `80261ee38545c62e70d3b73272cc3429`)
- `scripts/build_offline_home.py` (+`_nestedci_svg`, +CSS/geo consts, +`redrawNestedCI` loader JS, +Reset restore)
- `scripts/build_offline_home_validate.py` (+11 nested-CI gate checks)

## Verification
- `py_compile` clean (both scripts)
- build OK 43,270 bytes, **0 external refs**
- `build_offline_home_validate` **72/72** ok:true (was 61; +11)
- `offline_home_loader_parity` **10/10** ok:true
- both inline `<script>` blocks `node --check` clean
- baked SVG geometry node-verified: ncicopula x=212.2/w=18.5, ncinested x=116.0/w=350.0, point x=221.9 — reproduced exactly by `redrawNestedCI`
- governed headline 39,975.654628199336 intact (1 occ); contract 1.23.0 unchanged
- `ui_data.json` / `ui_app.html` / `combined_model_app.html` / `model_summary_card.html` / `model_result_viewer.html` **byte-unchanged** (git diff clean vs HEAD)

## Env notes
- jsdom self-test unrunnable (gitignored `node_modules`; W23/W29) — mirrored by the stdlib 72/72 gate + executed loader-parity + node --check + node geometry-parity.
- All git in a fresh /tmp clone of origin/main; mount `.git` untouched; edits applied programmatically in the ext4 clone (11 anchor groups, count-asserted) to avoid the documented virtiofs in-place-editor truncation.

## Next
Offline-UI graphical track stays OPEN (now 5 governed graphics). Next single auto-admissible item:
one more decision-neutral graphic reading only governed output (e.g. selected-copula family mini-comparison,
or an ES-vs-VaR margin strip). MODEL frontier remains OWNER PIVOT.
