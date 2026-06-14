# Offline UI Accessibility & Evidence-Integrity - Design Note (Phase 35 Task 1)

**Doc** `PHASE35_TASK1_DESIGN_NOTE` v1.0.0 | Phase 35: Offline UI Accessibility & Evidence-Integrity Deepening | classification educational | model parameter changes: NONE | gate: **PASS** (29 checks)

## Standing directive

Calculation chain complete; the UI uses only the stochastic model's output JSON to display results graphically and interactively, with no pre-installation requirement.

## (a) Baseline audit (measured, frozen as cross-check targets)

- measured at 2026-06-14T05:10:00Z
- `ui_app_self_test`: ok **True**, 340 checks, 0 network calls, 0 JS errors
- `offline_viewer_self_test`: ok **True**, 11 checks, 0 network calls, 0 JS errors
- `combined_gui_self_test`: ok **True**, 27 checks, 0 network calls, 0 JS errors
- `ui_app_userrun_fallback_test`: ok **True**, 9 checks, 0 network calls, 0 JS errors
- `ui_app_distribution_fallback_test`: ok **True**, 9 checks, 0 network calls, 0 JS errors
- `ui_app_integrity_fallback_test`: ok **True**, 10 checks, 0 network calls, 0 JS errors
- `ui_app_search_deeplink_test`: ok **True**, 18 checks, 0 network calls, 0 JS errors
- `ui_app_bundle_printall_test`: ok **True**, 21 checks, 0 network calls, 0 JS errors
- self-test checks total: **445**
- external references across 3 HTML artifacts: **0**
- embedded ui_data contract: **1.18.0**
- tabs (18): Overview, Inventory & Contract, Calibrations, Capital & Tail, Management Actions, Joint Actions (P24), Path-wise Actions (P25), Full Re-Agg (P26), Skew-t Tail (P27), Grouped-t Tail (P28), Vine Tail (P29), Stop-Rule (P30), SCR Comparator (P33), Distribution Explorer (P33), Owner Decision (P31), User Run (UIL), Governance, Integrity (H1)
- artifacts: `ui_app.html` 655,866 bytes; `model_result_viewer.html` 142,620 bytes; `combined_model_app.html` 456,204 bytes
- governance store: 92 ChangeRecords, 120 audit entries, 17 risk-register items

## (b) Gap list vs the directive (priority order, ONE gap per cycle)

### A1 (priority 1) - Formal WCAG 2.1 AA keyboard + contrast conformance pass

Phase 33 G4 added keyboard tab routing and Phase 34 H4 a high-contrast toggle, but there is no formal, MEASURED WCAG 2.1 AA conformance record. Add (i) a CSS-only :focus-visible indicator on every interactive control (tab buttons, sub-nav segmented buttons, search box + results, sliders, export/print buttons, high-contrast and print-all toggles), (ii) full keyboard operability of the controls not yet exercised by the suite, with a logical focus order, and (iii) a build-time measured contrast-audit table (ratios for body text >=4.5:1 and large-text / UI components >=3:1 in BOTH the default and high-contrast themes) embedded read-only. The display layer renders the audit and recomputes no model figure.

- contract change: ADDITIVE bump (1.18.0 -> 1.19.0): new a11y_audit key (build-time measured contrast/keyboard evidence) ONLY; every pre-existing key renders bit-identically

**(c) Pre-registered acceptance criteria:**

- every interactive control is reachable and operable by keyboard alone (Tab / Shift-Tab / Enter / Space / Arrow) with a visible :focus-visible indicator; focus order follows reading order
- measured AA contrast: all body text >=4.5:1 and large-text / UI-component boundaries >=3:1 in BOTH the default and high-contrast themes, embedded as a build-time read-only audit table
- contrast / keyboard audit numbers are written ONLY at build time by build_ui_data.py; the display layer renders them and computes nothing model-related
- new self-test checks cover :focus-visible presence, keyboard operability of the previously-uncovered controls, and the embedded contrast-audit table; suite stays ok:true 0/0
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures (a cryptographic hash over the embedded bytes is not a model figure)
- all eight offline self-tests (ui_app + offline_viewer + combined_gui + userrun-fallback + distribution-fallback + integrity-fallback + search-deeplink + bundle-printall) remain ok:true

### A2 (priority 2) - Per-section cryptographic digest in the H1 integrity panel

Phase 34 H1 embedded a contract manifest and an integrity panel that proves each required key is PRESENT, but not that its CONTENT was unaltered. Add a build-time per-section SHA-256 digest (one per top-level ui_data section) plus a root digest, written into contract_manifest by build_ui_data.py, and a load-time verifier that recomputes each digest IN-BROWSER from the embedded payload with NO network and NO storage API (file:// safe), surfacing a per-section verified/altered table and an overall tamper-evident badge in the H1 panel. The digest is over the embedded bytes only; no model figure is recomputed (a hash is not a model figure).

- contract change: ADDITIVE bump (1.19.0 -> 1.20.0): contract_manifest gains section_digests + digest_algo + root_digest ONLY; every pre-existing key renders bit-identically

**(c) Pre-registered acceptance criteria:**

- per-section SHA-256 digests + a root digest are written ONLY at build time by build_ui_data.py into contract_manifest; the algorithm and digests are display-read-only
- the in-browser verifier recomputes each section digest from the embedded payload with NO network and no storage API (file:// safe) and reports per-section verified/altered plus an overall tamper-evident badge
- on the intact full payload every section verifies (overall = verified); a single altered byte in any section flips that section and the overall badge to 'altered' with a neutral, non-steering message
- a hash is not a model figure: the governed headline 39,975.654628199336 and all governed read-outs render bit-identically and the verifier recomputes no model quantity
- new self-test checks cover digest presence, full-payload verify-all, and the altered-section mismatch via a dedicated jsdom fallback test; suite stays ok:true 0/0
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures (a cryptographic hash over the embedded bytes is not a model figure)
- all eight offline self-tests (ui_app + offline_viewer + combined_gui + userrun-fallback + distribution-fallback + integrity-fallback + search-deeplink + bundle-printall) remain ok:true

### A3 (priority 3) - One-page printable model-card cover

Phase 33 G3 added a sign-off print cover and Phase 34 H3 a print-all pack, but there is no single-page, ASOP-41-style MODEL CARD for a reviewer who wants one page: model identity, scope, governed headline, top limitations, Phase 30 stop-rule status, and the owner-decision-pending state. Add a CSS-print one-page model-card cover assembled bit-for-bit from the embedded snapshot, with the owner-decision field rendered BLANK (decision not pre-empted) and a provenance stamp (contract version + build stamp). Nothing is recomputed.

- contract change: NONE expected (presentation / print only); any key addition must be ADDITIVE

**(c) Pre-registered acceptance criteria:**

- the model-card cover fits one page in print and is assembled bit-for-bit from the embedded snapshot; governed headline 39,975.654628199336 carried exactly and never re-labelled
- it states model identity, scope, governed headline, top limitations, Phase 30 stop-rule status, and renders the owner-decision field BLANK (MR-016/MR-017 not pre-empted)
- the cover is provenance-stamped (contract version + build stamp) and adds no external resource (zero-install preserved)
- new self-test checks cover the model-card cover presence, the bit-for-bit headline, the blank decision field, and the one-page print CSS; suite stays ok:true 0/0
- ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change
- ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically
- zero-install preserved: 0 external references, single self-contained HTML file
- NO model parameter changes; the display layer never recomputes model figures (a cryptographic hash over the embedded bytes is not a model figure)
- all eight offline self-tests (ui_app + offline_viewer + combined_gui + userrun-fallback + distribution-fallback + integrity-fallback + search-deeplink + bundle-printall) remain ok:true

## Execution plan

- one gap per cycle in priority order: Task 2 = A1, Task 3 = A2, Task 4 = A3
- completion: Task 5 - phase summary + final consolidated baseline re-audit (self-tests, external-ref scan, contract inventory) and PHASE 35 COMPLETE documentation
- governance: each task carries its own ChangeRecord left in OWNER_REVIEW

## Task 1 gate

- ok: **True** (29 checks)
- doc_identity: True
- no_model_parameter_changes: True
- stop_rule_honoured: True
- owner_decision_not_preempted: True
- three_gaps: True
- gap_ids_unique_ordered: True
- each_gap_has_criteria: True
- each_gap_additive_only: True
- a1_focus_visible: True
- a1_contrast_aa: True
- a2_section_digest: True
- a2_no_network_verify: True
- a2_headline_frozen: True
- a3_headline_bit_for_bit: True
- a3_blank_decision: True
- one_gap_per_cycle: True
- baseline_ui_app_self_test_green: True
- baseline_offline_viewer_self_test_green: True
- baseline_combined_gui_self_test_green: True
- baseline_ui_app_userrun_fallback_test_green: True
- baseline_ui_app_distribution_fallback_test_green: True
- baseline_ui_app_integrity_fallback_test_green: True
- baseline_ui_app_search_deeplink_test_green: True
- baseline_ui_app_bundle_printall_test_green: True
- live_zero_external_refs: True
- live_contract_version_match: True
- live_tab_inventory_match: True
- live_single_file_size_match: True
- live_governance_counts_match: True

*Generated by scripts/build_phase35_task1_design_note.py.*
