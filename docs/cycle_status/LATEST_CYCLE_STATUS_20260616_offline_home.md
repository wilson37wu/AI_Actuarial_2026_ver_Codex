# Cycle status — 2026-06-16 (claude, window #18): offline-UI landing page

**Status:** GREEN — one additive, decision-neutral offline-UI task shipped.
**Frontier:** still OWNER PIVOT for the *model* (no model-form change auto-ran).

## What changed
Built `offline_home.html` — a zero-install landing page giving the user one entry
point that links all four offline result views + the Input&Run launcher and shows
governed headline figures read verbatim from `ui_data.json`. Recomputes nothing;
`ui_app.html` byte-unchanged; no `ui_data` contract change.

New files: `offline_home.html`, `scripts/build_offline_home.py`,
`scripts/build_offline_home_validate.py`, `scripts/offline_home_self_test.cjs`,
`docs/validation/OFFLINE_HOME_DESIGN_NOTE.md`.

## Verification
- build_offline_home.py → OK, 0 external refs
- build_offline_home_validate.py (stdlib gate) → ok:true **14/14**
- html.parser structural check → **15/15** (links + figures match ui_data exactly)
- PKG Task1 stdlib gate → 26/26; py_compile par_model_v2+tests clean; JSON re-parse 4/4 clean
- ui_app.html sha256 **d82c65ec… BYTE-UNCHANGED**; governed headline 39975.654628199336 present; contract 1.23.0
- jsdom live self-tests (offline_home + ui_app) NOT runnable in sandbox (virtiofs `require(jsdom)` >40s; `/sessions` 100% full) — env cap, not a regression; .cjs shipped for CI/owner.

## Owner actions still pending (unchanged, now 18 windows)
1. MR-LONGEV-1 longevity 5th driver — model-form change, **needs sign-off**.
2. LSMC inner-loop replacement — **needs sign-off**.
3. Option-A frozen-binary publish — **code-signing cert + publish channel** (owner/infra).
4. Extend offline UI with NEW model output — owner-gated (needs new compute).
5. Or declare the auto-development frontier complete and **freeze**.
