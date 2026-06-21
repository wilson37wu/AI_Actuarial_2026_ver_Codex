# Cycle status — 2026-06-11 (Claude, 06:00 UTC window, cycle 28) — Phase UIL Task 4 (B4+A1)

**Status: COMPLETE — Phase UIL finished; pointer → Phase 30 Task 4.**

- GUI currency wire-through LIVE: `build_ui_data.py` stamps `meta.currency` (+`currency_source`, `output_label`); `ui_app.html` routes all 153 monetary renders through one `fmtMoney` formatter; header currency/run badges; offline contract 1.11.0 → 1.12.0 **additive**.
- Source priority (disclosed): `model_inputs.json` → `RUN_MODEL_SUMMARY.json` → neutral default (bit-identical bare numbers).
- Tests: 9/9 new (`test_ui_currency_meta.py`); UI regression 336/336; run_model 23/23; broader selections 402+533+363+64 — 0 failures; `ui_app_self_test.cjs` ok:true (0 net / 0 err); compileall clean. P29T5 contract pin updated additively (disclosed).
- Docs: `production_run/README.md` + `USER_MANUAL_run_and_inputs.md` — template → loader → run_model → GUI chain documented LIVE end-to-end.
- Governance: ChangeRecord `f20b5a1b0b6f4432841f9d8ee4a3acd8` code_change OWNER_REVIEW; audit 101→102; changes 73→74; verify_all True. Capital impact none (display-only).
- Env: scipy → /tmp/pylibs_scipy (pip ENOSPC: /sessions ~100% full — standing ask); one virtiofs mid-write truncation caught by ast.parse and recovered off-mount.
- Next: **Phase 30 Task 4** — tree-3 tail diagnostics + binding stop-rule / MR-016/MR-017 decision (expected outcome per Task 3: KEEP OPEN + stop-rule applied; Phase 31 = owner decision package).
