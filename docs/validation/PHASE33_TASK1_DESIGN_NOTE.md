# Offline UI Interactive Analytics & Usability - Design Note (Phase 33 Task 1)

**Doc** `PHASE33_TASK1_DESIGN_NOTE` v1.0.0 | Phase 33: Offline UI Interactive Analytics & Usability | classification educational | model parameter changes: NONE | gate: **PASS** (23 checks)

## Standing directive

Calculation chain complete; the UI uses only the stochastic model's output JSON to display results graphically and interactively, with no pre-installation requirement.

## (a) Baseline audit (measured, frozen as cross-check targets)

- measured at 2026-06-11T18:12:00Z
- `ui_app_self_test`: ok **True**, 232 checks, 0 network calls, 0 JS errors
- `offline_viewer_self_test`: ok **True**, 11 checks, 0 network calls, 0 JS errors
- `combined_gui_self_test`: ok **True**, 27 checks, 0 network calls, 0 JS errors
- `ui_app_userrun_fallback_test`: ok **True**, 9 checks, 0 network calls, 0 JS errors
- external references across 3 HTML artifacts: **0**
- embedded ui_data contract: **1.16.0**
- tabs (15): Overview, Inventory & Contract, Calibrations, Capital & Tail, Management Actions, Joint Actions (P24), Path-wise Actions (P25), Full Re-Agg (P26), Skew-t Tail (P27), Grouped-t Tail (P28), Vine Tail (P29), Stop-Rule (P30), Owner Decision (P31), User Run (UIL), Governance
- artifacts: `ui_app.html` 572,915 bytes; `model_result_viewer.html` 142,620 bytes; `combined_model_app.html` 456,204 bytes
- governance store: 84 ChangeRecords, 112 audit entries, 17 risk-register items

## (b) Gap list vs the directive (priority order, ONE gap per cycle)

### G1 (priority 1) - Interactive cross-phase SCR comparator

Every dependence-structure SCR estimate (frozen-t, grouped-t, skew-t, vine, tree-3, nested) plus bootstrap CIs is already embedded in ui_data 1.16.0, but the tabs present them phase-by-phase only. Add an interactive comparator: user-selectable baseline structure, signed delta table vs the baseline, and a CI overlay chart - all rendered from ALREADY-EMBEDDED figures; the display layer recomputes nothing beyond subtraction for the displayed deltas, which must be labelled as display arithmetic, never as new model output.

- contract change: NONE expected (pure display layer on contract 1.16.0); any unforeseen key addition must be ADDITIVE (1.16.0 -> 1.17.0)

**(c) Pre-registered acceptance criteria:**

- every comparator figure traces bit-for-bit to a key already embedded in ui_data 1.16.0 (no new build-time data)
- governed frozen-t headline 39,975.654628199336 remains the default baseline and is never re-labelled by the comparator
- comparator is neutral: structures listed in registry order, no adoption/steering language (MR-016/MR-017 decision stays with the owner)
- new self-test checks cover baseline switching, delta signs, and CI overlay rendering; suite stays ok:true 0/0
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures
- offline_viewer + combined_gui + userrun-fallback self-tests remain ok:true

### G2 (priority 2) - Embedded-distribution drill-down (precomputed grids)

The UI shows headline quantiles but offers no distribution-level drill-down. Extend build_ui_data.py to embed PRECOMPUTED quantile/CDF grids (fixed grid, computed at build time from archived model output); the display layer renders an interactive distribution explorer (hover/readout/zoom) over those grids and recomputes NOTHING.

- contract change: ADDITIVE bump (current contract -> next minor, e.g. 1.16.0 -> 1.17.0)

**(c) Pre-registered acceptance criteria:**

- grids are computed ONLY at build time by build_ui_data.py from archived model output (provenance stamped); display layer never interpolates beyond the embedded grid resolution without labelling it as display interpolation
- embedded grid values reproducible from the archived run artefacts (spot-checked in the validation report)
- graceful neutral fallback when grids are absent from an older ui_data payload (no JS errors, no blank panel)
- new self-test checks cover grid presence, readout values, and fallback; suite stays ok:true 0/0
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures
- offline_viewer + combined_gui + userrun-fallback self-tests remain ok:true

### G3 (priority 3) - Printable owner sign-off / report pack

The MR-016/MR-017 owner decision pack is browsable (Phase 32 G1) but not print-ready, and CSV export coverage is partial. Add print CSS (page breaks, print-legible tables, suppressed navigation) so the Owner Decision and Governance surfaces print to a sign-off-ready pack, and complete CSV export coverage for every governed read-out table.

- contract change: NONE expected (presentation only); any key addition must be ADDITIVE

**(c) Pre-registered acceptance criteria:**

- printed pack preserves neutrality: options in registry order, decision record rendered BLANK until the owner decides
- every governed read-out table has a CSV export; exported values bit-for-bit equal to the rendered (embedded) values
- print stylesheet adds no external resources (zero-install preserved in print path)
- new self-test checks cover export coverage and print-CSS presence; suite stays ok:true 0/0
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures
- offline_viewer + combined_gui + userrun-fallback self-tests remain ok:true

### G4 (priority 4) - Accessibility & usability pass

The tab strip and tables lack keyboard navigation and ARIA semantics, and the selected tab resets on reload. Add keyboard navigation (arrow/home/end on the tab strip), ARIA roles/labels (tablist/tab/tabpanel, table captions), focus-visible styling, and state-persistent tab selection via URL hash (zero-install safe; no storage APIs). Scheduled last so the pass also covers surfaces added by G1-G3.

- contract change: NONE expected (markup/behaviour only); any key addition must be ADDITIVE

**(c) Pre-registered acceptance criteria:**

- tab strip operable by keyboard alone (arrow/home/end + enter/space) with correct ARIA tablist/tab/tabpanel roles and aria-selected state
- selected tab survives reload via URL hash only (no localStorage/sessionStorage; file:// safe)
- no regression in rendered figures: all pre-existing self-test checks still pass bit-identically
- new self-test checks cover keyboard activation, ARIA attributes, and hash persistence; suite stays ok:true 0/0
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures
- offline_viewer + combined_gui + userrun-fallback self-tests remain ok:true

## Execution plan

- one gap per cycle in priority order: Task 2 = G1, Task 3 = G2, Task 4 = G3, Task 5 = G4
- completion: Task 6 - phase summary + final consolidated baseline re-audit (self-tests, external-ref scan, contract inventory) and PHASE 33 COMPLETE documentation
- governance: each task carries its own ChangeRecord left in OWNER_REVIEW

## Task 1 gate

- ok: **True** (23 checks)
- doc_identity: True
- no_model_parameter_changes: True
- stop_rule_honoured: True
- owner_decision_not_preempted: True
- four_gaps: True
- gap_ids_unique_ordered: True
- each_gap_has_criteria: True
- each_gap_additive_only: True
- g1_headline_frozen: True
- g1_no_new_data: True
- g2_precomputed_only: True
- g3_neutral_blank_decision: True
- g4_no_storage_apis: True
- one_gap_per_cycle: True
- baseline_ui_app_self_test_green: True
- baseline_offline_viewer_self_test_green: True
- baseline_combined_gui_self_test_green: True
- baseline_ui_app_userrun_fallback_test_green: True
- live_zero_external_refs: True
- live_contract_version_match: True
- live_tab_inventory_match: True
- live_single_file_size_match: True
- live_governance_counts_match: True

*Generated by scripts/build_phase33_task1_design_note.py.*
