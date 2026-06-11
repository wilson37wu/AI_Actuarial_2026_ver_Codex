# Cycle Status - 2026-06-11 (interactive repo cleanup) [claude]

**User-requested housekeeping; no model code changed. Consistent with the 2026-06-11 restructure conventions.**

- Tracked probe/junk files REMOVED from git (65 paths): root write-probes (`_perm_test_wt`, `_probe_write_2.tmp`, `_writeprobe.tmp`, `_wtest_2`, `_wtest_2.tmp`), agent scratch (`.claude-dev/_tmp/5lsmm54n`), temp self-test (`scripts/_tmp_selftest.cjs`), 44 `docs/G05_ENVIRONMENT_PROBE_*.json` + 11 `docs/G05_VENV_PROBE_*.txt` diagnostic snapshots, and 4 generated daily-briefing artifacts (`outputs/HK_Insurance_Daily_Briefing_*`; regenerable via `scripts/build_hk_insurance_briefing*.mjs`, which stay).
- `render_test.cjs` MOVED from the repo root to `scripts/` (unreferenced jsdom GUI self-test; joins the other `*_self_test.cjs` scripts; root reserved for docs/config per the restructure convention).
- `.gitignore` EXTENDED to guard re-entry: `docs/G05_ENVIRONMENT_PROBE_*.json`, `docs/G05_VENV_PROBE_*.txt`, `outputs/HK_Insurance_Daily_Briefing_*`, `.claude-dev/_tmp/`.
- KEPT: `outputs/phase11_reconciliation.json` (referenced by `par_model_v2/projection/chunk_processor.py` and `docs/DEPLOYMENT_READINESS_CHECKLIST.md`); all cycle-status files already live in `docs/cycle_status/` (none left in root).
- Model-dev state untouched: next scheduled task remains Phase 30 Task 5 (offline-UI propagation).
- NOTE: the mounted working folder forbids deletes, so the purged files may linger as untracked copies on the local folder; they are gitignored and will not re-enter the repo.
