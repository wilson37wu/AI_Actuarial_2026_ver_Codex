# Cycle Status — Window #24 (Claude Cowork)

**Date:** 2026-06-16 (scheduled claude 18:00-window run)
**Task:** Offline-UI option (f) — promote the link-existence check into the standing stdlib gate
**Owner of lock:** claude • **Result:** COMPLETE / pushed

## What shipped
Promoted the link-existence assertion that previously lived only inside
`build_offline_home.build()` (option (e), W23) into the standing, rebuild-independent
gate `scripts/build_offline_home_validate.py`. The gate now parses the **shipped**
`offline_home.html` and, for every card href, asserts the target resolves to a real
file on disk under `ROOT`. A shipped landing page can therefore never link to a missing
view — even when no rebuild has occurred. Cards ARE the VIEWS, and chooser hrefs are a
build-time-asserted subset of VIEWS, so the single card-target existence check
transitively covers every chooser target.

## Properties
- Additive, decision-neutral. **No governed-artifact rebuild.**
- `offline_home.html`, `ui_app.html`, `ui_data.json` **byte-unchanged**.
- Governed headline `39975.654628199336` intact; data contract stays `1.23.0`; 0 external refs.
- Stdlib only — no network, no new runtime JS, no jsdom/node dependency.
- Failing-check label embeds the offending missing href(s) → self-describing `failed` list.
- **One file changed:** `scripts/build_offline_home_validate.py`.

## Verification (executed in /tmp clone)
- File written via bash heredoc to bypass the known editor mid-write corruption, then
  md5-verified byte-identical across /tmp source + clone + mount (`e61be31cc642a4a1c8a0dbe9441edd06`).
- `py_compile`: clean.
- POSITIVE: `build_offline_home_validate.py` → **28/28** checks `ok:true` (was 27; the new
  existence check is the 28th).
- NEGATIVE: injecting a bogus missing card href fails **exactly** the new check
  (`every card link target exists on disk (missing: MISSING_VIEW_ZZZ.html)`), `ok:false`,
  exit 1; restores to `ok:true`.
- Companion `offline_home_loader_parity.cjs`: **10/10** `ok:true` (node).

## Next pointer
Offline-UI option (g): collect `build_offline_home_validate.py` into the pytest suite
(thin `tests/test_offline_home_validate.py` asserting `main()==0`) so the standing gate
runs automatically under the existing test runner — additive, stdlib, no governed-artifact
or contract change. MODEL frontier remains OWNER PIVOT (MR-LONGEV-1 / LSMC sign-off;
Option-A publish cert+channel; or declare the frontier complete & freeze).
