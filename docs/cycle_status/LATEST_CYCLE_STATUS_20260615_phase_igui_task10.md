# Latest Cycle Status - 2026-06-15 - Phase IGUI Task 10

**Owner:** Claude Cowork (06:00/18:00 UTC window)
**Task (single in_progress, now COMPLETE):** Phase IGUI Task 10 - Option-C offline-install appendix + pinned engine requirements (decision-neutral)
**Result:** COMPLETE
**Contract:** 1.21.0 (unchanged) - no model parameter change

## What landed
- `requirements-engine-lock.txt` - PINNED model-engine set: `numpy==1.26.4`, `pandas==2.2.3`, `scipy==1.13.1` (CPython 3.9-3.12). Freezes the numerical stack so the run-from-source COMPUTE step is reproducible (the governed headline 39,975.654628199336 depends on model + stack). `requirements.txt` keeps compatible ranges for development.
- `docs/PHASE_IGUI_OFFLINE_INSTALL_APPENDIX.md` - Option-C walkthrough: layer separation (stdlib GUI vs numpy/pandas/scipy COMPUTE), venv / direct / air-gapped install, verification, troubleshooting, guardrails. Explicitly decision-neutral (Option A/B remain open; MR-016/MR-017 not pre-empted).
- `scripts/launch_offline_gui.py` - engine-status disclosure now points at the pinned file + appendix. `engine_status()` gains `pinned_requirements` / `install_appendix` / `compute_install_hint`; the `modules` set stays exactly `{numpy, scipy}` (gate/tests assert it).
- `launchers/README.md` - links both the offline-install appendix and the packaging-options card.
- `scripts/build_phase_igui_task10_offline_install.py` - 16-check gate + evidence report + governance ChangeRecord.
- `tests/test_phase_igui_task10_offline_install.py` - 16 unittests.
- `docs/validation/PHASE_IGUI_TASK10_OFFLINE_INSTALL.{json,md}` - evidence report.

## Gates
- Task-10 gate: **16/16 green** (pins parse + within ranges; appendix refs lock/card/headline/ui-sha + decision-neutral; launcher + README wiring; ui_app.html byte-unchanged).
- Task-10 unittests: **16 OK**. Task-8 launcher suite: still **8 OK** (no regression).
- `ui_app.html` sha256 `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65` - **byte-unchanged**.

## Governance
- ChangeRecord `7500ce9ead6c4c50b46dda4c276ae9c4` - status **OWNER_REVIEW**.
- change_records 109 -> 110; audit_trail 137 -> 138; audit-chain integrity **OK**.

## Constraints honoured
- STDLIB-only docs/config; NO model parameter change; Phase 30 stop-rule honoured.
- A/B/C packaging decision and MR-016/MR-017 left entirely with the owner.

## Blockers
- None for this task. Standing: dev sandbox lacks scipy (`/sessions` full, `pip` ENOSPC), so the Task-7 LIVE end-to-end run gate is validated by structure here; it goes fully green in any engine-equipped environment.

## Next (single in_progress for next cycle)
- Post-Phase-IGUI Task 1 (design-note-first): research + pre-register exactly ONE stochastic-model improvement candidate (Phase 30 stop-rule bound), OWNER_REVIEW only. If owner selects a packaging option, pivot to the build-spec / CI release-matrix skeleton.
