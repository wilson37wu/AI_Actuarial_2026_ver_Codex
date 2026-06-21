# PHASE_IGUI_TASK1_DESIGN_NOTE (v1.0.0)

**Phase:** Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)  
**Task:** Task 1 - design note (architecture decision, input-schema coverage map, pre-registered acceptance criteria + gate)  
**Classification:** educational  
**Measured baseline:** 2026-06-14T22:19:06Z (PHASE 36 COMPLETE)

> Owner-directed exclusive workstream: a GUI to enter every actuarial / data input typical of a valuation process AND run the stochastic model end-to-end. The owner relaxed the strict no-pre-install constraint for THIS input+run front end ONLY; the offline RESULTS UI (ui_app.html) stays zero-install and unchanged.

## Discipline (binding)

- NO model parameter changes: **True**
- Phase 30 stop-rule honoured: **True**
- MR-016/MR-017 owner decision not pre-empted: **True**
- RESULTS UI (ui_app.html) stays zero-install & unchanged: **True**

## Baseline audit (frozen cross-check targets)

- 9 offline self-test suites, all ok:true, **522 checks**, 0 network / 0 JS errors
- contract **1.21.0**, 25 top-level keys, 19 tabs, **0 external references**
- governance: 100 ChangeRecords / 128 audit entries / 17 risk items

## (b) Architecture decision

**Chosen: `L2_stdlib_local_runner`.** The owner relaxed zero-install for the input+run front end because the model itself cannot be run without Python + numpy/pandas/scipy - so a pure-browser writer (L1) cannot satisfy 'one button to supply inputs AND compute'. L2 adds the SMALLEST possible footprint: a standard-library local runner that reuses the existing loader + orchestrator and adds NO new third-party dependency, while the RESULTS UI stays strictly zero-install. L3 (frozen binary) is deferred as an optional future packaging layer because it adds non-reproducible, per-OS build infrastructure unsuited to this auditable educational repo.

### L1_browser_only_writer — Pure-browser zero-install form that only WRITES model_inputs.json
*Verdict:* rejected - does not meet the end-to-end run requirement

Pros: keeps the strict zero-install posture (single HTML file, file:// safe); no runtime beyond a browser to COLLECT and validate inputs; reuses the established offline-UI self-test harness

Cons: CANNOT run the model: the user still has to invoke python load_user_inputs/run_model by hand; fails the owner's explicit end-to-end requirement ('press one button to supply inputs AND compute'); browser cannot write a file to a known path without a download step; no in-process validation against the real loader

### L2_stdlib_local_runner — Stdlib-only local runner (scripts/run_gui.py): http.server + self-contained input HTML, runs the model in-process
*Verdict:* CHOSEN - minimal additional footprint that satisfies end-to-end run; results UI untouched

Pros: meets the end-to-end requirement: one launch -> collect+validate inputs -> run load_user_inputs/run_model -> open ui_app.html with results; introduces ZERO new pre-install: the model ALREADY requires Python+numpy/pandas/scipy to compute, and the GUI server layer uses only the Python standard library (http.server, webbrowser, json) - no Flask/Django/Node added; binds 127.0.0.1 only, makes NO outbound network call (offline / air-gap safe), no storage API; can BYPASS the openpyxl/Excel dependency for input by writing model_inputs.json directly in the loader's schema (Excel template stays an optional import path); reuses scripts/load_user_inputs.py validation + scripts/run_model.py orchestration verbatim (no model-math duplication)

Cons: still requires a Python interpreter present (acceptable: identical to the requirement already imposed by running the model itself); a localhost server, while standard, is a heavier surface than a static file (mitigated: stdlib only, localhost-bound, no third-party deps, no network)

### L3_frozen_binary_bundle — Frozen single-file binary (PyInstaller / pyoxidizer / briefcase) bundling Python + deps
*Verdict:* deferred - optional FUTURE packaging step layered ON TOP of L2 once the L2 runner is complete and owner-approved

Pros: truly no-pre-install for the end user (double-click executable); best non-technical-user ergonomics

Cons: adds platform-specific build infrastructure (per-OS binaries) that this educational repo and its CI cannot reproduce or audit; large multi-hundred-MB artifacts that defeat the repo's reproducibility/diff discipline and cannot be committed; obscures the auditable Python source the governance trail relies on; out of scope for an educational, source-auditable model pending credentialled data + independent review

## (c) Input-schema coverage map

Integration chain: `GUI inputs -> model_inputs.json -> scripts/load_user_inputs.py + scripts/run_model.py -> scripts/build_ui_data.py -> ui_data.json -> existing offline RESULTS UI ui_app.html (zero-install, unchanged)`

| Domain | Current coverage | Target | Gap | Closes in |
|---|---|---|---|---|
| Run controls | Run Settings tab -> n_sim, bootstrap_replicates, horizon_months, seed, output_label<br>Currency tab -> currency code, amount scale, thousands separator<br>Assumptions tab -> confidence level (SCR) | valuation date; currency; projection horizon & step; # outer / # inner scenarios (explicit); seeds & reproducibility digest; output labels | valuation date field; explicit projection STEP; explicit outer vs inner scenario split (today n_sim maps to the governed outer/inner only via run_model defaults); a surfaced per-run reproducibility digest | Task 2 (run controls + scaffolding) |
| Policy / model-point data | Portfolio tab rows -> product type {HKCD_PAR_2026, HKRB_PAR_2026, GMMB_EQ_2026}, issue age, gender, term, sum assured, annual premium, policy count, vested bonus<br>Balance Sheet tab -> asset rows / market values with stated-total reconciliation | ingest OR edit model points (PAR + GMMB); in-force file upload (CSV/JSON); portfolio scaling / booking | interactive add/edit/delete of model-point rows; in-force file UPLOAD path (today: Excel template only); explicit portfolio scaling / booking controls beyond run_model's disclosed linear scaling | Task 3 (model points + in-force ingest) |
| Assumptions | Assumptions tab -> confidence, management-action relief sigma & alpha, benefit share (beta_fit)<br>governed/frozen read-back echo -> copula df, grouped-t dfs (NEVER user-settable) | mortality (base + improvement); lapse/surrender incl. dynamic policyholder behaviour; expenses (per-policy / %-premium / inflation); premiums/contributions; discount rate / yield curve; bonus/crediting & bonus-declaration strategy; management-action rules; reinsurance | mortality base+improvement inputs; lapse/surrender incl. dynamic behaviour; expense bases; discount/yield-curve inputs; bonus-crediting & declaration-strategy controls; richer management-action rules; reinsurance - ALL gated behind owner sign-off (no model-parameter change without it) | Task 4 (assumptions - surfaced incrementally, owner-gated) |
| Economic scenarios / ESG inputs & calibration | frozen governed ESG dependence parameters echoed read-only (copula df, grouped-t dfs, Sigma) for provenance | rate model (G2++/HW); equity; FX; correlations; credit spread; liquidity; calibration targets & market data | user-facing ESG / calibration-target inputs - bounded by the Phase 30 stop-rule (NO new copula-structure candidates) and the pending MR-016/MR-017 owner decision; surfaced as DISCLOSED/echo first, settable only on owner sign-off | Task 5 (ESG / calibration inputs, stop-rule-bounded) |
| Validation & governance gating | scripts/load_user_inputs.py fail-loud validation: per-tab/row/field range + completeness + reconciliation checks, all issues listed before non-zero exit | completeness / consistency / range checks + governance gating BEFORE a run is allowed; reproducibility digest on every run | surface the loader's validation results in the GUI and BLOCK the run button until clean; a governance gate (ChangeRecord/provenance) recorded before each run; a reproducibility digest emitted per run | Task 6 (validation + governance gating) |
| Integration / results handoff | model_inputs.json schema (loader_schema_version 1.0.0)<br>scripts/run_model.py -> RUN_MODEL_AGGREGATION_REPORT.json / RUN_MODEL_SUMMARY.json in the Phase 22 Task 4 aggregation shape<br>scripts/build_ui_data.py parses that shape; ui_app.html consumes ui_data.json (drag-drop or rebuild) | GUI writes model_inputs.json -> drives run_model.py + UIL loader -> model output -> surfaced through the existing offline RESULTS UI in one flow | wire the GUI 'Run' action to load_user_inputs->run_model->build_ui_data->open ui_app.html end-to-end; the RESULTS UI itself stays zero-install and BYTE-UNCHANGED | Task 7 (end-to-end run + results handoff -> Phase IGUI MVP) |

## Staged tasks (one input domain per cycle)

### Task 2 — Run controls + GUI scaffolding (stdlib local runner skeleton) (`D1_run_controls`)
- a stdlib-only local runner (scripts/run_gui.py) serves a self-contained input page on 127.0.0.1 and opens it; no third-party dep, no outbound network
- run controls (valuation date, currency, horizon & step, outer/inner scenarios, seed, output label) are collected and written into the model_inputs.json schema accepted by scripts/load_user_inputs.py
- new self-tests cover the runner launch, the run-controls form, and schema round-trip
- the existing zero-install RESULTS UI (ui_app.html) stays byte-unchanged unless a SEPARATE additive-only contract change is explicitly recorded; all nine offline self-tests remain ok:true (522+ checks), 0 network / 0 JS errors, 0 external references
- the input+run GUI adds NO third-party runtime dependency beyond the model's existing numpy/pandas/scipy: its server/UI layer is Python standard library only; it binds 127.0.0.1 and makes NO outbound network call
- NO model parameter changes without explicit owner sign-off; the Phase 30 stop-rule is honoured and the MR-016/MR-017 owner decision is not pre-empted
- every GUI-collected field round-trips through scripts/load_user_inputs.py validation (fail-loud) before a run is permitted; the model_inputs.json schema version is respected
- each task carries its own governance ChangeRecord (OWNER_REVIEW) and new self-tests / validation; the governed headline 39,975.654628199336 is carried bit-for-bit wherever displayed

### Task 3 — Model points + in-force ingest (`D2_policy_model_points`)
- interactive add/edit/delete of PAR + GMMB model-point rows and a CSV/JSON in-force upload path that maps to the Portfolio schema
- balance-sheet asset rows + stated-total reconciliation surfaced; portfolio scaling/booking disclosed exactly as run_model reports it
- new self-tests cover row editing, file ingest, and reconciliation validation
- the existing zero-install RESULTS UI (ui_app.html) stays byte-unchanged unless a SEPARATE additive-only contract change is explicitly recorded; all nine offline self-tests remain ok:true (522+ checks), 0 network / 0 JS errors, 0 external references
- the input+run GUI adds NO third-party runtime dependency beyond the model's existing numpy/pandas/scipy: its server/UI layer is Python standard library only; it binds 127.0.0.1 and makes NO outbound network call
- NO model parameter changes without explicit owner sign-off; the Phase 30 stop-rule is honoured and the MR-016/MR-017 owner decision is not pre-empted
- every GUI-collected field round-trips through scripts/load_user_inputs.py validation (fail-loud) before a run is permitted; the model_inputs.json schema version is respected
- each task carries its own governance ChangeRecord (OWNER_REVIEW) and new self-tests / validation; the governed headline 39,975.654628199336 is carried bit-for-bit wherever displayed

### Task 4 — Assumptions (owner-gated, incremental) (`D3_assumptions`)
- currently-supported assumptions (confidence, management-action relief sigma/alpha, benefit share) are editable; frozen/governed parameters remain read-only echo
- additional assumption families (mortality, lapse incl. dynamic, expenses, discount/yield curve, bonus declaration, reinsurance) are surfaced as DISCLOSED inputs and become settable ONLY behind explicit owner sign-off (no model-parameter change otherwise)
- new self-tests cover editable vs read-only gating and the no-parameter-change-without-sign-off guard
- the existing zero-install RESULTS UI (ui_app.html) stays byte-unchanged unless a SEPARATE additive-only contract change is explicitly recorded; all nine offline self-tests remain ok:true (522+ checks), 0 network / 0 JS errors, 0 external references
- the input+run GUI adds NO third-party runtime dependency beyond the model's existing numpy/pandas/scipy: its server/UI layer is Python standard library only; it binds 127.0.0.1 and makes NO outbound network call
- NO model parameter changes without explicit owner sign-off; the Phase 30 stop-rule is honoured and the MR-016/MR-017 owner decision is not pre-empted
- every GUI-collected field round-trips through scripts/load_user_inputs.py validation (fail-loud) before a run is permitted; the model_inputs.json schema version is respected
- each task carries its own governance ChangeRecord (OWNER_REVIEW) and new self-tests / validation; the governed headline 39,975.654628199336 is carried bit-for-bit wherever displayed

### Task 5 — ESG / calibration inputs (stop-rule-bounded) (`D4_esg_economic`)
- ESG / calibration-target inputs surfaced as read-only echo first; the Phase 30 stop-rule is honoured (NO new copula-structure candidates) and MR-016/MR-017 is not pre-empted
- any settable ESG input is bounded and owner-gated; governed dependence parameters stay frozen
- new self-tests cover stop-rule guard and provenance echo
- the existing zero-install RESULTS UI (ui_app.html) stays byte-unchanged unless a SEPARATE additive-only contract change is explicitly recorded; all nine offline self-tests remain ok:true (522+ checks), 0 network / 0 JS errors, 0 external references
- the input+run GUI adds NO third-party runtime dependency beyond the model's existing numpy/pandas/scipy: its server/UI layer is Python standard library only; it binds 127.0.0.1 and makes NO outbound network call
- NO model parameter changes without explicit owner sign-off; the Phase 30 stop-rule is honoured and the MR-016/MR-017 owner decision is not pre-empted
- every GUI-collected field round-trips through scripts/load_user_inputs.py validation (fail-loud) before a run is permitted; the model_inputs.json schema version is respected
- each task carries its own governance ChangeRecord (OWNER_REVIEW) and new self-tests / validation; the governed headline 39,975.654628199336 is carried bit-for-bit wherever displayed

### Task 6 — Validation surfacing + governance gating before run (`D5_validation_gating`)
- the loader's fail-loud validation results are surfaced in the GUI and the Run button is BLOCKED until inputs validate clean
- a governance gate (provenance/ChangeRecord) is recorded before each run and a reproducibility digest is emitted per run
- new self-tests cover the run-block-on-invalid behaviour and the per-run digest
- the existing zero-install RESULTS UI (ui_app.html) stays byte-unchanged unless a SEPARATE additive-only contract change is explicitly recorded; all nine offline self-tests remain ok:true (522+ checks), 0 network / 0 JS errors, 0 external references
- the input+run GUI adds NO third-party runtime dependency beyond the model's existing numpy/pandas/scipy: its server/UI layer is Python standard library only; it binds 127.0.0.1 and makes NO outbound network call
- NO model parameter changes without explicit owner sign-off; the Phase 30 stop-rule is honoured and the MR-016/MR-017 owner decision is not pre-empted
- every GUI-collected field round-trips through scripts/load_user_inputs.py validation (fail-loud) before a run is permitted; the model_inputs.json schema version is respected
- each task carries its own governance ChangeRecord (OWNER_REVIEW) and new self-tests / validation; the governed headline 39,975.654628199336 is carried bit-for-bit wherever displayed

### Task 7 — End-to-end run + results handoff (Phase IGUI MVP) (`D6_integration`)
- one 'Run' action threads load_user_inputs -> run_model -> build_ui_data -> opens ui_app.html with the fresh results
- the RESULTS UI stays zero-install and byte-unchanged; the handoff adds no external reference
- an end-to-end self-test proves inputs -> model_inputs.json -> run -> ui_data.json -> RESULTS UI on a small deterministic config
- the existing zero-install RESULTS UI (ui_app.html) stays byte-unchanged unless a SEPARATE additive-only contract change is explicitly recorded; all nine offline self-tests remain ok:true (522+ checks), 0 network / 0 JS errors, 0 external references
- the input+run GUI adds NO third-party runtime dependency beyond the model's existing numpy/pandas/scipy: its server/UI layer is Python standard library only; it binds 127.0.0.1 and makes NO outbound network call
- NO model parameter changes without explicit owner sign-off; the Phase 30 stop-rule is honoured and the MR-016/MR-017 owner decision is not pre-empted
- every GUI-collected field round-trips through scripts/load_user_inputs.py validation (fail-loud) before a run is permitted; the model_inputs.json schema version is respected
- each task carries its own governance ChangeRecord (OWNER_REVIEW) and new self-tests / validation; the governed headline 39,975.654628199336 is carried bit-for-bit wherever displayed

## Execution plan

design-note-first this cycle; then one input domain / capability per cycle in order: Task 2 run controls -> Task 3 model points -> Task 4 assumptions -> Task 5 ESG -> Task 6 validation/gating -> Task 7 end-to-end run + results handoff (Phase IGUI MVP)

Completion: Phase IGUI MVP = a usable input+run GUI that drives the model end-to-end into the existing offline RESULTS UI

## Task 1 gate

**ok = True**, 35 checks.

- PASS — doc_identity
- PASS — no_model_parameter_changes
- PASS — stop_rule_honoured
- PASS — owner_decision_not_preempted
- PASS — results_ui_zero_install_preserved
- PASS — architecture_three_options
- PASS — architecture_chosen_valid
- PASS — architecture_no_new_deps
- PASS — architecture_offline
- PASS — architecture_each_option_has_verdict
- PASS — coverage_six_domains_ordered
- PASS — coverage_each_domain_complete
- PASS — coverage_integration_chain_present
- PASS — staged_tasks_present
- PASS — staged_tasks_map_domains
- PASS — staged_tasks_have_criteria
- PASS — one_domain_per_cycle
- PASS — headline_carried_bit_for_bit
- PASS — baseline_ui_app_self_test_green
- PASS — baseline_ui_app_evidence_pack_fallback_test_green
- PASS — baseline_ui_app_integrity_fallback_test_green
- PASS — baseline_ui_app_distribution_fallback_test_green
- PASS — baseline_ui_app_userrun_fallback_test_green
- PASS — baseline_ui_app_search_deeplink_test_green
- PASS — baseline_ui_app_bundle_printall_test_green
- PASS — baseline_offline_viewer_self_test_green
- PASS — baseline_combined_gui_self_test_green
- PASS — baseline_checks_total_consistent
- PASS — live_zero_external_refs
- PASS — live_contract_version_floor
- PASS — live_tab_inventory_floor
- PASS — live_ui_app_size_floor
- PASS — live_loader_present
- PASS — live_orchestrator_present
- PASS — live_governance_counts_floor
