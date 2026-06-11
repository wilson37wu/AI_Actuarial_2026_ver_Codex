# Cycle Status - 2026-06-11 (interactive repo cleanup) [claude]

**User-requested housekeeping; no model code changed. Consistent with the 2026-06-11 restructure conventions.**

- Tracked probe/junk files REMOVED from git (65 paths): root write-probes (`_perm_test_wt`, `_probe_write_2.tmp`, `_writeprobe.tmp`, `_wtest_2`, `_wtest_2.tmp`), agent scratch (`.claude-dev/_tmp/5lsmm54n`), temp self-test (`scripts/_tmp_selftest.cjs`), 44 `docs/G05_ENVIRONMENT_PROBE_*.json` + 11 `docs/G05_VENV_PROBE_*.txt` diagnostic snapshots, and 4 generated daily-briefing artifacts (`outputs/HK_Insurance_Daily_Briefing_*`; regenerable via `scripts/build_hk_insurance_briefing*.mjs`, which stay).
- `render_test.cjs` MOVED from the repo root to `scripts/` (unreferenced jsdom GUI self-test; joins the other `*_self_test.cjs` scripts; root reserved for docs/config per the restructure convention).
- `.gitignore` EXTENDED to guard re-entry: `docs/G05_ENVIRONMENT_PROBE_*.json`, `docs/G05_VENV_PROBE_*.txt`, `outputs/HK_Insurance_Daily_Briefing_*`, `.claude-dev/_tmp/`.
- KEPT: `outputs/phase11_reconciliation.json` (referenced by `par_model_v2/projection/chunk_processor.py` and `docs/DEPLOYMENT_READINESS_CHECKLIST.md`); all cycle-status files already live in `docs/cycle_status/` (none left in root).
- Model-dev state untouched: next scheduled task remains Phase 30 Task 5 (offline-UI propagation).
- NOTE: the mounted working folder forbids deletes, so the purged files may linger as untracked copies on the local folder; they are gitignored and will not re-enter the repo.

## Pass 2 — G05 snapshot-log prune (same session)

- 199 repetitive timestamped G05 monitoring snapshots REMOVED (hourly/3-hourly 2026-05-25..28 loops): COMPILEALL (33), PYTEST_FULL (34), PYTEST_RISK_METRICS (38), PYTEST_TVOG (38), STATIC_GUARD_REPORT (39), PIP_DRY_RUN (11), GIT_STATUS (3), RUN_SUMMARY (3). Git history retains all of them.
- KEPT tracked: the LATEST snapshot of each family (2026-05-28T180400Z) as representative gate evidence, plus every cited file: `G05_MEASURE_GUARD_EVIDENCE.md` (phase13_ia_tas_m.py), `G05_RUNTIME_EVIDENCE_2026-06-04T103044Z.json` (governance store), `G05_RUNTIME_TEST_EVIDENCE_2026-05-29*` (ESG acceptance), `G05_MEASURE_GUARD_STATIC_REPORT_2026-05-25*`, `G05_RUNTIME_ENFORCEMENT_PHASE14.md`, `G05_CURRENT_RUN_TIMESTAMP.txt`.
- RESTORED `docs/G05_ENVIRONMENT_PROBE_2026-05-26T053325Z.json` (cited by DEPLOYMENT_READINESS_CHECKLIST.md; it was inside the pass-1 wildcard delete) with a `!` gitignore exemption.
- `.gitignore` extended with the G05 snapshot families + `!` exemptions for the kept evidence.
