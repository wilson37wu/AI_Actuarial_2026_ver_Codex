# Cycle Status — Window #47 (claude) — 2026-06-18T01:14:05Z

**Task:** W47 offline-UI copula goodness-of-fit (log-likelihood) strip — ADDITIVE, decision-neutral.

## Outcome
Shipped a zero-install, zero-network inline-SVG **"Copula goodness-of-fit — fitted candidates (log-likelihood)"** strip (`svg id="copulall"`) to `offline_home.html`. Displays the three GOVERNED fitted full-copula candidates' maximised log-likelihood read verbatim from `capital.copula.copulas[].loglik`:

| Copula | log-likelihood | bar width (px) |
|---|---|---|
| Gaussian | 187.3387 | 360.0 |
| Student-t | 184.1462 | 353.9 |
| Survival Clayton | 7.0140 | 13.5 |

Bar length = `loglik/max(loglik)` on one shared scale; value printed verbatim (4dp). Companion to the W46 AIC strip (AIC = −2·loglik + 2k) — shows the raw fit **before** the parameter penalty. **DECISION-NEUTRAL** (like W45 upper-tail-dependence): the model selects its aggregation copula by **AIC, not raw log-likelihood**, so **NO bar is marked**; governed headline stays the frozen-t basis. 15th governed landing-page graphic.

## Verification (all green)
- `build_offline_home_validate` **169/169** ok:true (was 158; +11 copulall checks)
- `offline_home_loader_parity` **10/10**
- `tests/test_offline_home_validate` **4/4** (stdlib unittest)
- `node --check` clean on both inline `<script>` blocks
- Geometry parity **EXACT** (cllbar widths 360.0 / 353.9 / 13.5 reproduced exactly by JS `redrawCopulaLogLik` mirror)
- Governed artifacts (`ui_data.json`, `ui_app.html`, `combined_model_app.html`, `model_summary_card.html`, `model_result_viewer.html`) **byte-unchanged** (git status clean)
- Headline **39,975.65** (1 occ); contract **1.23.0** unchanged
- `offline_home.html` md5 `061ecdfae13182d70ff2bbba9ce9a238`

## Recommendation
Offline-UI graphic pool now very rich (**15 graphics**); the natural governed copula fit/selection metrics (aggregated SCR, AIC, upper-tail-dependence, log-likelihood) are **all** now shown. Auto-admissible offline-UI candidates are **EXHAUSTED**. Owner should declare the offline-UI graphical track **COMPLETE** and pivot to the MODEL frontier (MR-LONGEV-1 / LSMC / MLMC sign-off; Packaging A/B/C; or freeze) or Phase IGUI. Model-FORM changes require owner sign-off (not auto-run).

## Environment notes
- `/sessions` mount is **100% full (0 bytes free)** — all work done in a fresh /tmp ext4 clone; mount `.git` untouched. State/source committed/pushed from the clone (origin = source of truth).
