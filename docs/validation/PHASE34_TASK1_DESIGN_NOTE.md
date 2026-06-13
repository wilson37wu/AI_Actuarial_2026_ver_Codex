# Offline UI Usability Hardening - Design Note (Phase 34 Task 1)

**Doc** `PHASE34_TASK1_DESIGN_NOTE` v1.0.0 | Phase 34: Offline UI Usability Hardening | classification educational | model parameter changes: NONE | gate: **PASS** (26 checks)

## Standing directive

Calculation chain complete; the UI uses only the stochastic model's output JSON to display results graphically and interactively, with no pre-installation requirement.

## (a) Baseline audit (measured, frozen as cross-check targets)

- measured at 2026-06-13T23:20:00Z
- `ui_app_self_test`: ok **True**, 297 checks, 0 network calls, 0 JS errors
- `offline_viewer_self_test`: ok **True**, 11 checks, 0 network calls, 0 JS errors
- `combined_gui_self_test`: ok **True**, 27 checks, 0 network calls, 0 JS errors
- `ui_app_userrun_fallback_test`: ok **True**, 9 checks, 0 network calls, 0 JS errors
- `ui_app_distribution_fallback_test`: ok **True**, 9 checks, 0 network calls, 0 JS errors
- external references across 3 HTML artifacts: **0**
- embedded ui_data contract: **1.17.0**
- tabs (17): Overview, Inventory & Contract, Calibrations, Capital & Tail, Management Actions, Joint Actions (P24), Path-wise Actions (P25), Full Re-Agg (P26), Skew-t Tail (P27), Grouped-t Tail (P28), Vine Tail (P29), Stop-Rule (P30), SCR Comparator (P33), Distribution Explorer (P33), Owner Decision (P31), User Run (UIL), Governance
- artifacts: `ui_app.html` 619,761 bytes; `model_result_viewer.html` 142,620 bytes; `combined_model_app.html` 456,204 bytes
- governance store: 90 ChangeRecords, 118 audit entries, 17 risk-register items

## (b) Gap list vs the directive (priority order, ONE gap per cycle)

### H1 (priority 1) - Self-describing data-contract guard + in-UI schema/integrity panel

The UI assumes a well-formed ui_data payload: a missing or mismatched key currently degrades silently to a blank or partial panel with no signal to the user. Embed a build-time contract MANIFEST (expected contract version + required top-level keys, written by build_ui_data.py) and add a load-time validator that renders an integrity/schema panel: contract version match, per-key present/absent table, and a NEUTRAL degraded-mode banner when the payload is incomplete or the contract version is unexpected. The validator inspects ONLY the embedded payload and recomputes no model figure.

- contract change: ADDITIVE bump (1.17.0 -> 1.18.0): new contract_manifest key ONLY; every pre-existing key renders bit-identically

**(c) Pre-registered acceptance criteria:**

- manifest is written ONLY at build time by build_ui_data.py (expected version + required key list); display layer reads it and computes nothing model-related
- validator reports PASS on the current 1.17.0/1.18.0 payload (all required keys present, contract matches) with no JS errors
- neutral degraded-mode banner shown for a payload missing a required key or carrying an unexpected contract version - no blank panel, no steering language
- new self-test checks cover manifest presence, validator PASS on the full payload, and the degraded-mode banner via a dedicated jsdom fallback test; suite stays ok:true 0/0
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures
- offline_viewer + combined_gui + userrun-fallback + distribution-fallback self-tests remain ok:true

### H2 (priority 2) - Global cross-tab search + deep-linkable read-outs

With 17 tabs the surface is hard to navigate: there is no way to find a specific governed figure or table without clicking through tabs. Add a global search box that indexes ONLY already-rendered text (tab titles, table captions, headline labels) and jumps to the match, plus URL-hash deep links that restore tab + in-tab section (extending the Phase 33 G4 hash mechanism). Pure display layer; no storage APIs; file:// safe.

- contract change: NONE expected (pure display layer); any unforeseen key addition must be ADDITIVE

**(c) Pre-registered acceptance criteria:**

- search index is built ONLY from text already embedded/rendered in the artifact (no new build-time data, no network)
- governed frozen-t headline 39,975.654628199336 is findable and is never re-labelled by search/highlight
- deep links restore both the selected tab and the in-tab section via URL hash only (no localStorage/sessionStorage; file:// safe)
- new self-test checks cover search hit/restore, deep-link tab+section restore, and no-storage-API compliance; suite stays ok:true 0/0
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures
- offline_viewer + combined_gui + userrun-fallback + distribution-fallback self-tests remain ok:true

### H3 (priority 3) - One-click full evidence bundle export + print-all pack

Phase 33 G3 added per-table CSV exports and a print sign-off cover, but assembling the complete evidence set still requires many clicks. Add a single action that exports EVERY governed read-out to one provenance-stamped bundle (multi-section CSV/JSON with contract version + build stamp + governed headline) and a print-all mode that lays out all governed surfaces for a single sign-off print. Values are taken bit-for-bit from the embedded snapshot; nothing is recomputed.

- contract change: NONE expected (presentation/export only); any key addition must be ADDITIVE

**(c) Pre-registered acceptance criteria:**

- every value in the bundle is bit-for-bit equal to the embedded snapshot; governed headline 39,975.654628199336 carried exactly and never re-labelled
- bundle is provenance-stamped (contract version + build stamp); decision record exported BLANK (owner decision not pre-empted)
- export and print-all paths add no external resources (zero-install preserved); options stay in registry order
- new self-test checks cover bundle section coverage, bit-for-bit headline, blank decision record, and print-all CSS presence; suite stays ok:true 0/0
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures
- offline_viewer + combined_gui + userrun-fallback + distribution-fallback self-tests remain ok:true

### H4 (priority 4) - Responsive / small-screen + high-contrast usability pass

The layout targets a wide desktop viewport and a single colour scheme. Add a responsive pass (no horizontal scroll on narrow viewports, legible charts/tables), prefers-reduced-motion support, and a CSS-only high-contrast toggle persisted via URL hash. Scheduled last so the pass also covers the surfaces added by H1-H3. Markup/CSS/behaviour only; no storage APIs.

- contract change: NONE expected (markup/CSS/behaviour only); any key addition must be ADDITIVE

**(c) Pre-registered acceptance criteria:**

- no horizontal overflow at a narrow (<=768px) viewport; tables/charts remain legible and operable
- high-contrast toggle is CSS-only and persists via URL hash only (no localStorage/sessionStorage); prefers-reduced-motion honoured
- no regression in rendered figures: all pre-existing self-test checks still pass bit-identically
- new self-test checks cover narrow-viewport layout, the high-contrast toggle, and reduced-motion handling; suite stays ok:true 0/0
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures
- offline_viewer + combined_gui + userrun-fallback + distribution-fallback self-tests remain ok:true

## Execution plan

- one gap per cycle in priority order: Task 2 = H1, Task 3 = H2, Task 4 = H3, Task 5 = H4
- completion: Task 6 - phase summary + final consolidated baseline re-audit (self-tests, external-ref scan, contract inventory) and PHASE 34 COMPLETE documentation
- governance: each task carries its own ChangeRecord left in OWNER_REVIEW

## Task 1 gate

- ok: **True** (26 checks)
- doc_identity: True
- no_model_parameter_changes: True
- stop_rule_honoured: True
- owner_decision_not_preempted: True
- four_gaps: True
- gap_ids_unique_ordered: True
- each_gap_has_criteria: True
- each_gap_additive_only: True
- h1_manifest_build_time_only: True
- h1_neutral_degraded_banner: True
- h2_headline_frozen: True
- h2_no_storage_apis: True
- h3_headline_bit_for_bit: True
- h3_blank_decision: True
- h4_no_storage_apis: True
- one_gap_per_cycle: True
- baseline_ui_app_self_test_green: True
- baseline_offline_viewer_self_test_green: True
- baseline_combined_gui_self_test_green: True
- baseline_ui_app_userrun_fallback_test_green: True
- baseline_ui_app_distribution_fallback_test_green: True
- live_zero_external_refs: True
- live_contract_version_match: True
- live_tab_inventory_match: True
- live_single_file_size_match: True
- live_governance_counts_match: True

*Generated by scripts/build_phase34_task1_design_note.py.*
