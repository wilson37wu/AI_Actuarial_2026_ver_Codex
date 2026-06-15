# Phase IGUI Task 10 - Option-C Offline-Install Appendix + Pinned Engine Requirements

**Generated:** 2026-06-15T08:14:40Z  
**Phase:** Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)  
**Classification:** educational / install documentation  
**Decision-neutral:** True

## 1. What this task delivered

- Pinned engine lock `requirements-engine-lock.txt`: `numpy==1.26.4, pandas==2.2.3, scipy==1.13.1`
- Option-C offline-install appendix `docs/PHASE_IGUI_OFFLINE_INSTALL_APPENDIX.md`
- Engine-status disclosure wired in `scripts/launch_offline_gui.py` (pinned-reqs + appendix pointers)
- Launcher README links the appendix + the packaging-options card
- Supported interpreters: CPython 3.9 - 3.12 (scipy 1.13.x wheel coverage)

## 2. Reproducibility rationale

The governed headline SCR 39975.654628199336 is a property of the model AND the numerical stack; pinning numpy/pandas/scipy freezes the stack so a run-from-source COMPUTE step is bit-for-bit reproducible. requirements.txt keeps compatible ranges for development; this lock is the reproducibility anchor for a run.

## 3. Decision neutrality

Supports Option C (run from source). Pre-empts nothing: Option A (frozen binary) and Option B (vendored wheels) remain open and can reuse the same pins. MR-016/MR-017 dependence decision untouched; Phase 30 stop-rule honoured.

## 4. Task-10 gate

**ok: True** (16 checks)

- lock_file_exists: True
- lock_has_three_pins: True
- lock_pins_match_expected: True
- lock_pins_within_requirements_ranges: True
- appendix_exists: True
- appendix_refs_lock_file: True
- appendix_refs_packaging_card: True
- appendix_carries_headline: True
- appendix_refs_committed_ui_sha: True
- appendix_decision_neutral: True
- launcher_discloses_pinned_reqs: True
- launcher_discloses_appendix: True
- launcher_modules_set_unchanged: True
- readme_links_appendix: True
- readme_links_packaging_card: True
- ui_app_byte_unchanged: True

## 5. Consolidated re-audit

- Committed RESULTS UI `ui_app.html` sha256 `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65` - byte-unchanged vs baseline: **True**
- Governance store: **109** change records, **137** audit entries; integrity **True**
- Governed headline SCR carried: `39975.654628199336`

## 6. Constraints honoured

- STDLIB-only docs/config; no third-party dependency added to the GUI/runner
- NO model parameter change
- committed zero-install RESULTS UI (ui_app.html) byte-unchanged
- Phase 30 stop-rule honoured; MR-016/MR-017 owner decision not pre-empted
- decision-neutral: Option A/B remain fully open
- one task this cycle; agent lock held; fresh-clone git per AGENT_COORDINATION.md
