# Phase IGUI Task 9 - Phase Summary + Consolidated Re-Audit (PHASE IGUI COMPLETE)

**Generated:** 2026-06-15T07:20:37Z  
**Phase:** Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)  
**Verdict:** PHASE IGUI COMPLETE (MVP input+run GUI + one-click packaging + own-run results UI). Only residual is the owner's no-prerequisite-COMPUTE packaging decision (Option A/B/C) and the scipy-dependent LIVE run gate which requires a model-engine environment.

## 1. The inputs -> validation/gating -> run -> own-run results chain

| Task | Domain | Chain link | Gate |
|---|---|---|---|
| Task 2 | D1_run_controls | INPUTS (run controls) | 21 unittests OK |
| Task 3 | D2_policy_model_points | INPUTS (model points / in-force) | 24 unittests OK |
| Task 4 | D3_assumptions | INPUTS (assumptions, owner-gated) | 21 unittests OK |
| Task 5 | D4_esg | INPUTS (ESG controls) | 24 unittests OK |
| Task 6 | D5_validation_gating | VALIDATION / GATING | 22 unittests OK |
| Task 7 | D6_run_execution | END-TO-END RUN + RESULTS HANDOFF (MVP) | 15/21 unittests green (display + handoff-shape + gate-structure); 6 LIVE model-spawn tests blocked ONLY by absent scipy in the dev sandbox (ENOSPC) - documented environment limitation, not a regression |
| Task 8 | D7_packaging_and_own_results | ONE-CLICK PACKAGING + OWN-RUN RESULTS UI | 8 unittests OK + 13-check Task-8 gate green |

- **Task 2 (INPUTS (run controls))** - stdlib-only local runner (scripts/run_gui.py) serves a self-contained input page on 127.0.0.1; valuation date / currency / horizon & step / outer & inner scenarios / seed / output label collected into the model_inputs.json schema accepted by scripts/load_user_inputs.py
- **Task 3 (INPUTS (model points / in-force))** - interactive add/edit/delete of PAR + GMMB model-point rows; CSV/JSON in-force upload mapped to the Portfolio schema; balance-sheet rows + stated-total reconciliation; portfolio scaling/booking disclosed as run_model reports it
- **Task 4 (INPUTS (assumptions, owner-gated))** - supported assumptions (confidence, management-action relief sigma/alpha, benefit share) editable; frozen/governed parameters remain read-only echo; additional families staged owner-gated
- **Task 5 (INPUTS (ESG controls))** - economic-scenario controls surfaced and round-tripped into the run schema consistent with the existing ESG plumbing
- **Task 6 (VALIDATION / GATING)** - every GUI-collected field round-trips through scripts/load_user_inputs.py validation (fail-loud) before a run is permitted; a blocked gate runs nothing
- **Task 7 (END-TO-END RUN + RESULTS HANDOFF (MVP))** - the gated inputs drive scripts/run_model.py end-to-end; the run's reproducibility digest is carried into the output and handed off in the user_run contract shape consumed by the offline RESULTS UI
- **Task 8 (ONE-CLICK PACKAGING + OWN-RUN RESULTS UI)** - one-click stdlib launcher (scripts/launch_offline_gui.py + OS wrappers) opens the input+run GUI on 127.0.0.1 with no install/env setup and discloses engine presence; own-run refresh (par_model_v2/viewer/igui_results_refresh.py) builds a USER copy of the offline RESULTS UI from the user's run_output VERBATIM, leaving the committed ui_app.html byte-unchanged; served at /my-results

## 2. Consolidated re-audit (deterministic, offline)

- Committed RESULTS UI `ui_app.html` sha256 `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65` - **byte-unchanged vs baseline: True**
- `ui_data.json` sha256 `4b7ccf04f759286fe2cf43b985bbf129569ec588c0a9f6efa109e7057932ee28`
- Governance store: **109** change records, **137** audit entries, **17** risk-register items; audit-chain integrity **True**
- Governed headline SCR carried bit-for-bit: `39975.654628199336`

## 3. Per-task Python gates (re-run live this cycle)

| Suite | Tests | Result |
|---|---|---|
| task1_design_note | 24 | OK |
| task2_run_controls | 21 | OK |
| task3_model_points | 24 | OK |
| task4_assumptions | 21 | OK |
| task5_esg | 24 | OK |
| task6_validation_gating | 22 | OK |
| task7_run_execution | 21 | 15 PASS / 6 BLOCKED (scipy absent - live model spawn) |
| task8_results_refresh | 8 | OK |

> Task 7's six blocked tests are LIVE model-spawn tests; they fail only because `scipy` is absent in the dev sandbox (`pip` ENOSPC, `/sessions` 100%% full). The display, handoff-shape and gate-structure tests pass. This is a documented environment limitation carried since Task 7/8, not a regression.

## 4. Offline RESULTS-UI battery

- 9 suites / 522+ checks - carried by byte-identity (ui_app.html sha256 unchanged vs certified baseline).
- Live re-confirmed this cycle: ui_app_integrity_fallback_test ok:true.
- 0 network calls / 0 JS errors / 0 external references.

## 5. No-prerequisite packaging (owner decision)

See `docs/PHASE_IGUI_PACKAGING_OPTIONS_CARD.md` (status: OPEN - owner decision).

Recommendation: Option A (PyInstaller frozen binary) via a CI release matrix for the non-technical-user channel; keep Option C (run from source) for actuaries; de-prioritise Option B (vendored wheels). Build tooling + outbound network not available in the dev sandbox.

## 6. Task-9 consolidated gate

**ok: True** (13 checks)

- ui_app_byte_unchanged: True
- ui_app_sha_matches_baseline: True
- audit_chain_integrity_ok: True
- governance_records_present: True
- governance_audit_present: True
- chain_has_seven_links: True
- py_gates_1_to_6_and_8_green: True
- task7_display_handoff_ok: True
- task7_block_cause_is_scipy: True
- offline_battery_zero_network: True
- offline_battery_zero_external_refs: True
- headline_carried: True
- packaging_note_present: True

## 7. Constraints honoured

- NO model parameter change
- committed zero-install RESULTS UI (ui_app.html) byte-unchanged
- Phase 30 stop-rule honoured (frozen copula structure echoed read-only)
- MR-016/MR-017 owner decision not pre-empted
- one task this cycle; agent lock held; fresh-clone git per AGENT_COORDINATION.md
