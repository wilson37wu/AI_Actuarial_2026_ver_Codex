# Zero-Install Offline UI Consolidation - Design Note (Phase 32 Task 1)

**Doc** `PHASE32_TASK1_DESIGN_NOTE` v1.0.0 | Phase 32: Zero-Install Offline UI Consolidation | classification educational | model parameter changes: NONE | gate: **PASS** (18 checks)

## Standing directive

Calculation chain complete; the UI uses only the stochastic model's output JSON to display results graphically and interactively, with no pre-installation requirement.

## (a) Baseline audit (measured, frozen as cross-check targets)

- measured at 2026-06-11T13:15:00Z
- `ui_app_self_test`: ok **True**, 172 checks, 0 network calls, 0 JS errors
- `offline_viewer_self_test`: ok **True**, 11 checks, 0 network calls, 0 JS errors
- `combined_gui_self_test`: ok **True**, 27 checks, 0 network calls, 0 JS errors
- external references across 3 HTML artifacts: **0**
- embedded ui_data contract: **1.13.0**
- tabs (13): Overview, Inventory & Contract, Calibrations, Capital & Tail, Management Actions, Joint Actions (P24), Path-wise Actions (P25), Full Re-Agg (P26), Skew-t Tail (P27), Grouped-t Tail (P28), Vine Tail (P29), Stop-Rule (P30), Governance
- artifacts: `ui_app.html` 490,846 bytes; `model_result_viewer.html` 142,620 bytes; `combined_model_app.html` 456,204 bytes
- governance store: 79 ChangeRecords, 107 audit entries, 17 risk-register items

## (b) Gap list vs the directive (priority order, ONE gap per cycle)

### G1 (priority 1) - Owner-decision-pack surface (browsable Phase 31 pack)

The Phase 31 owner decision pack and one-page summary are governance documents only; the offline UI mentions the owner decision but offers no browsable surface. Add an additive 'Owner Decision (P31)' surface: evidence pack key figures, the three options (registry order, neutral, no default), sign-off workflow position, and the decision-record status (BLANK until the owner decides).

- contract change: 1.13.0 -> 1.14.0 ADDITIVE

**(c) Pre-registered acceptance criteria:**

- every displayed figure bit-for-bit from PHASE31_TASK2_OWNER_DECISION_PACK.json (nothing recomputed)
- neutrality preserved: options in registry order, no steering language, decision record rendered BLANK
- new self-test checks cover the surface; suite stays ok:true 0/0
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change: every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures
- offline_viewer + combined_gui self-tests remain ok:true

### G2 (priority 2) - User-input run-result surface (Phase UIL outputs)

Phase UIL wired currency/output_label into the GUI, but the user-input run itself (RUN_MODEL_SUMMARY.json: run configuration, model-point counts, input provenance model_inputs.json -> loader -> run_model) has no panel. Add an additive run-results surface with graceful fallback when no user run is embedded.

- contract change: next ADDITIVE bump after G1 (1.14.0 -> 1.15.0)

**(c) Pre-registered acceptance criteria:**

- renders exclusively from embedded model-output JSON (run summary embedded at build time)
- graceful neutral fallback when no user-input run exists (no JS errors, no blank tab)
- currency/output_label provenance disclosed exactly as stamped by build_ui_data.py
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change: every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures
- offline_viewer + combined_gui self-tests remain ok:true

### G3 (priority 3) - Governed read-out completeness sweep

Inventory-driven sweep: diff the governance store (ChangeRecords, audit trail, model-risk register) and the validation-report registry against the ui_data governance section; surface any governed read-out not yet visible (e.g. full MR register with statuses, ChangeRecord status counts) additively.

- contract change: ADDITIVE bump only if the sweep finds missing read-outs

**(c) Pre-registered acceptance criteria:**

- documented inventory diff committed with the change (what was missing, what was added)
- surfaced figures bit-for-bit from the governance store / archived reports
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change: every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures
- offline_viewer + combined_gui self-tests remain ok:true

## Execution plan

- one gap per cycle in priority order: Task 2 = G1, Task 3 = G2, Task 4 = G3
- completion: Task 5 - phase summary + final consolidated baseline re-audit (self-tests, external-ref scan, contract inventory) and PHASE 32 COMPLETE documentation
- governance: each task carries its own ChangeRecord left in OWNER_REVIEW

## Task 1 gate

- ok: **True** (18 checks)
- doc_identity: True
- no_model_parameter_changes: True
- stop_rule_honoured: True
- three_gaps: True
- gap_ids_unique_ordered: True
- each_gap_has_criteria: True
- each_gap_additive_only: True
- g1_neutrality_pinned: True
- g1_bit_for_bit_pack: True
- one_gap_per_cycle: True
- baseline_ui_app_self_test_green: True
- baseline_offline_viewer_self_test_green: True
- baseline_combined_gui_self_test_green: True
- live_zero_external_refs: True
- live_contract_version_match: True
- live_tab_inventory_match: True
- live_single_file_size_match: True
- live_governance_counts_match: True

*Generated by scripts/build_phase32_task1_design_note.py.*
