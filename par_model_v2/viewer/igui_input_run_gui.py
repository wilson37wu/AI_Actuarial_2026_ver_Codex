"""Phase IGUI Task 1 - Actuarial Input & Run GUI: DESIGN NOTE.

Owner-directed exclusive workstream (interactive directions 2026-06-14T14:16Z
and 14:22Z, recorded in ``MODEL_DEV_TASK_PROMPT.md``). The stochastic
calculation chain is complete and the zero-install offline RESULTS UI
(``ui_app.html``) is frozen and green. The owner now wants a GUI for a user to
**enter every actuarial / data input typical of a valuation process AND run the
stochastic model end-to-end**, with the flow:

    GUI inputs -> model_inputs.json -> scripts/load_user_inputs.py +
    scripts/run_model.py (Phase-UIL loader / run orchestrator) -> model output
    -> existing offline RESULTS UI (ui_app.html).

This module is the Task-1 DESIGN NOTE ONLY (no GUI code lands this cycle). It:

  (a) records a frozen BASELINE audit of the existing model + offline UI so the
      pre-registration cannot silently drift from the artifact it describes;
  (b) chooses & justifies the **local-runner / bundling architecture** for the
      input+run front end against the (now relaxed) no-pre-install trade-off -
      the owner relaxed zero-install for THIS input+run front end ONLY; the
      RESULTS UI stays zero-install and unchanged;
  (c) lays out the **input-schema coverage map** spanning run controls,
      policy / model-point data, assumptions, ESG / economic-scenario inputs,
      validation / governance gating, and integration, marking what the current
      Phase-UIL template + loader ALREADY cover vs the GAP to the owner's full
      "everything typical in an actuarial valuation process" target;
  (d) pre-registers per-task ACCEPTANCE CRITERIA + a Task-1 gate
      (:func:`validate_design_note`) parallel to the prior design-note gates,
      mixing structural checks on the note with LIVE checks against the repo.

Binding discipline (unchanged): NO model parameter changes; the Phase 30
stop-rule stands (no new copula-structure candidates); the MR-016/MR-017 owner
decision on the Phase 31 dependence pack is not pre-empted; ONE task per cycle;
fresh-clone git per AGENT_COORDINATION.md; the governed headline SCR is carried
bit-for-bit. Pure ``governance_change`` this cycle.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

DOC_ID = "PHASE_IGUI_TASK1_DESIGN_NOTE"
DOC_VERSION = "1.0.0"

#: Governed headline SCR (frozen single-df t), bit-for-bit invariant.
GOVERNED_HEADLINE = "39,975.654628199336"

#: Chosen input+run GUI architecture (see ARCHITECTURE_OPTIONS).
CHOSEN_ARCHITECTURE = "L2_stdlib_local_runner"

#: Frozen baseline measurements (Phase 36 COMPLETE state; re-audit
#: 2026-06-14 cycle 708c, 9/9 offline self-tests = 522 checks).
BASELINE = {
    "measured_at_utc": "2026-06-14T22:19:06Z",
    "phase_status": "PHASE 36 COMPLETE",
    # nine offline self-test suites, all ok:true, 0 network / 0 JS errors
    "ui_app_self_test": {"ok": True, "n_checks": 405, "js_errors": 0, "network_calls": 0},
    "ui_app_evidence_pack_fallback_test": {"ok": True, "n_checks": 12, "js_errors": 0, "network_calls": 0},
    "ui_app_integrity_fallback_test": {"ok": True, "n_checks": 10, "js_errors": 0, "network_calls": 0},
    "ui_app_distribution_fallback_test": {"ok": True, "n_checks": 9, "js_errors": 0, "network_calls": 0},
    "ui_app_userrun_fallback_test": {"ok": True, "n_checks": 9, "js_errors": 0, "network_calls": 0},
    "ui_app_search_deeplink_test": {"ok": True, "n_checks": 18, "js_errors": 0, "network_calls": 0},
    "ui_app_bundle_printall_test": {"ok": True, "n_checks": 21, "js_errors": 0, "network_calls": 0},
    "offline_viewer_self_test": {"ok": True, "n_checks": 11, "js_errors": 0, "network_calls": 0},
    "combined_gui_self_test": {"ok": True, "n_checks": 27, "js_errors": 0, "network_calls": 0},
    "self_test_suites_total": 9,
    "self_test_checks_total": 522,
    "external_refs_total": 0,
    "artifacts": {
        "ui_app.html": {"bytes": 711361, "embedded_contract": "1.21.0"},
        "model_result_viewer.html": {"bytes": 142620},
        "combined_model_app.html": {"bytes": 456204},
    },
    "contract_version": "1.21.0",
    "top_level_keys": 25,
    "tab_count": 19,
    "tabs": [
        "Overview", "Inventory & Contract", "Calibrations", "Capital & Tail",
        "Management Actions", "Joint Actions (P24)", "Path-wise Actions (P25)",
        "Full Re-Agg (P26)", "Skew-t Tail (P27)", "Grouped-t Tail (P28)",
        "Vine Tail (P29)", "Stop-Rule (P30)", "SCR Comparator (P33)",
        "Distribution Explorer (P33)", "Owner Decision (P31)",
        "User Run (UIL)", "Methodology & Glossary", "Governance",
        "Integrity (H1)",
    ],
    "governance_store": {"change_records": 100, "audit_entries": 128, "risk_register": 17},
    # existing input plumbing the GUI must drive (already in-repo)
    "existing_input_plumbing": {
        "template": "production_run/MODEL_INPUTS_TEMPLATE.xlsx",
        "loader": "scripts/load_user_inputs.py",
        "loader_schema_version": "1.0.0",
        "orchestrator": "scripts/run_model.py",
        "contract_json": "model_inputs.json",
        "loader_tabs": ["Currency", "Balance Sheet", "Portfolio", "Assumptions", "Run Settings"],
        "results_handoff": "ui_app.html (drag-drop ui_data.json / rebuild via build_ui_data.py)",
        "runtime_requirements": ["numpy>=1.26,<3.0", "pandas>=2.2,<3.0", "scipy>=1.13,<2.0", "openpyxl (Excel loader path only)"],
    },
}

HTML_ARTIFACTS = ["ui_app.html", "model_result_viewer.html", "combined_model_app.html"]

# --------------------------------------------------------------------------
# (b) ARCHITECTURE DECISION
# --------------------------------------------------------------------------
ARCHITECTURE_OPTIONS = [
    {
        "id": "L1_browser_only_writer",
        "title": "Pure-browser zero-install form that only WRITES model_inputs.json",
        "pros": [
            "keeps the strict zero-install posture (single HTML file, file:// safe)",
            "no runtime beyond a browser to COLLECT and validate inputs",
            "reuses the established offline-UI self-test harness",
        ],
        "cons": [
            "CANNOT run the model: the user still has to invoke python load_user_inputs/run_model by hand",
            "fails the owner's explicit end-to-end requirement ('press one button to supply inputs AND compute')",
            "browser cannot write a file to a known path without a download step; no in-process validation against the real loader",
        ],
        "verdict": "rejected - does not meet the end-to-end run requirement",
    },
    {
        "id": "L2_stdlib_local_runner",
        "title": "Stdlib-only local runner (scripts/run_gui.py): http.server + self-contained input HTML, runs the model in-process",
        "pros": [
            "meets the end-to-end requirement: one launch -> collect+validate inputs -> run load_user_inputs/run_model -> open ui_app.html with results",
            "introduces ZERO new pre-install: the model ALREADY requires Python+numpy/pandas/scipy to compute, and the GUI server layer uses only the Python standard library (http.server, webbrowser, json) - no Flask/Django/Node added",
            "binds 127.0.0.1 only, makes NO outbound network call (offline / air-gap safe), no storage API",
            "can BYPASS the openpyxl/Excel dependency for input by writing model_inputs.json directly in the loader's schema (Excel template stays an optional import path)",
            "reuses scripts/load_user_inputs.py validation + scripts/run_model.py orchestration verbatim (no model-math duplication)",
        ],
        "cons": [
            "still requires a Python interpreter present (acceptable: identical to the requirement already imposed by running the model itself)",
            "a localhost server, while standard, is a heavier surface than a static file (mitigated: stdlib only, localhost-bound, no third-party deps, no network)",
        ],
        "verdict": "CHOSEN - minimal additional footprint that satisfies end-to-end run; results UI untouched",
    },
    {
        "id": "L3_frozen_binary_bundle",
        "title": "Frozen single-file binary (PyInstaller / pyoxidizer / briefcase) bundling Python + deps",
        "pros": [
            "truly no-pre-install for the end user (double-click executable)",
            "best non-technical-user ergonomics",
        ],
        "cons": [
            "adds platform-specific build infrastructure (per-OS binaries) that this educational repo and its CI cannot reproduce or audit",
            "large multi-hundred-MB artifacts that defeat the repo's reproducibility/diff discipline and cannot be committed",
            "obscures the auditable Python source the governance trail relies on",
            "out of scope for an educational, source-auditable model pending credentialled data + independent review",
        ],
        "verdict": "deferred - optional FUTURE packaging step layered ON TOP of L2 once the L2 runner is complete and owner-approved",
    },
]

# --------------------------------------------------------------------------
# (c) INPUT-SCHEMA COVERAGE MAP
#     current = what the Phase-UIL template + loader already accept;
#     target  = the owner's full 'everything typical in a valuation' scope;
#     gap     = what a later staged task must add;
#     task    = the staged Phase-IGUI task that closes the gap.
# --------------------------------------------------------------------------
INPUT_DOMAINS = [
    {
        "id": "D1_run_controls",
        "domain": "Run controls",
        "current_coverage": [
            "Run Settings tab -> n_sim, bootstrap_replicates, horizon_months, seed, output_label",
            "Currency tab -> currency code, amount scale, thousands separator",
            "Assumptions tab -> confidence level (SCR)",
        ],
        "target": [
            "valuation date; currency; projection horizon & step; # outer / # inner scenarios (explicit); seeds & reproducibility digest; output labels",
        ],
        "gap": [
            "valuation date field; explicit projection STEP; explicit outer vs inner scenario split (today n_sim maps to the governed outer/inner only via run_model defaults); a surfaced per-run reproducibility digest",
        ],
        "task": "Task 2 (run controls + scaffolding)",
    },
    {
        "id": "D2_policy_model_points",
        "domain": "Policy / model-point data",
        "current_coverage": [
            "Portfolio tab rows -> product type {HKCD_PAR_2026, HKRB_PAR_2026, GMMB_EQ_2026}, issue age, gender, term, sum assured, annual premium, policy count, vested bonus",
            "Balance Sheet tab -> asset rows / market values with stated-total reconciliation",
        ],
        "target": [
            "ingest OR edit model points (PAR + GMMB); in-force file upload (CSV/JSON); portfolio scaling / booking",
        ],
        "gap": [
            "interactive add/edit/delete of model-point rows; in-force file UPLOAD path (today: Excel template only); explicit portfolio scaling / booking controls beyond run_model's disclosed linear scaling",
        ],
        "task": "Task 3 (model points + in-force ingest)",
    },
    {
        "id": "D3_assumptions",
        "domain": "Assumptions",
        "current_coverage": [
            "Assumptions tab -> confidence, management-action relief sigma & alpha, benefit share (beta_fit)",
            "governed/frozen read-back echo -> copula df, grouped-t dfs (NEVER user-settable)",
        ],
        "target": [
            "mortality (base + improvement); lapse/surrender incl. dynamic policyholder behaviour; expenses (per-policy / %-premium / inflation); premiums/contributions; discount rate / yield curve; bonus/crediting & bonus-declaration strategy; management-action rules; reinsurance",
        ],
        "gap": [
            "mortality base+improvement inputs; lapse/surrender incl. dynamic behaviour; expense bases; discount/yield-curve inputs; bonus-crediting & declaration-strategy controls; richer management-action rules; reinsurance - ALL gated behind owner sign-off (no model-parameter change without it)",
        ],
        "task": "Task 4 (assumptions - surfaced incrementally, owner-gated)",
    },
    {
        "id": "D4_esg_economic",
        "domain": "Economic scenarios / ESG inputs & calibration",
        "current_coverage": [
            "frozen governed ESG dependence parameters echoed read-only (copula df, grouped-t dfs, Sigma) for provenance",
        ],
        "target": [
            "rate model (G2++/HW); equity; FX; correlations; credit spread; liquidity; calibration targets & market data",
        ],
        "gap": [
            "user-facing ESG / calibration-target inputs - bounded by the Phase 30 stop-rule (NO new copula-structure candidates) and the pending MR-016/MR-017 owner decision; surfaced as DISCLOSED/echo first, settable only on owner sign-off",
        ],
        "task": "Task 5 (ESG / calibration inputs, stop-rule-bounded)",
    },
    {
        "id": "D5_validation_gating",
        "domain": "Validation & governance gating",
        "current_coverage": [
            "scripts/load_user_inputs.py fail-loud validation: per-tab/row/field range + completeness + reconciliation checks, all issues listed before non-zero exit",
        ],
        "target": [
            "completeness / consistency / range checks + governance gating BEFORE a run is allowed; reproducibility digest on every run",
        ],
        "gap": [
            "surface the loader's validation results in the GUI and BLOCK the run button until clean; a governance gate (ChangeRecord/provenance) recorded before each run; a reproducibility digest emitted per run",
        ],
        "task": "Task 6 (validation + governance gating)",
    },
    {
        "id": "D6_integration",
        "domain": "Integration / results handoff",
        "current_coverage": [
            "model_inputs.json schema (loader_schema_version 1.0.0)",
            "scripts/run_model.py -> RUN_MODEL_AGGREGATION_REPORT.json / RUN_MODEL_SUMMARY.json in the Phase 22 Task 4 aggregation shape",
            "scripts/build_ui_data.py parses that shape; ui_app.html consumes ui_data.json (drag-drop or rebuild)",
        ],
        "target": [
            "GUI writes model_inputs.json -> drives run_model.py + UIL loader -> model output -> surfaced through the existing offline RESULTS UI in one flow",
        ],
        "gap": [
            "wire the GUI 'Run' action to load_user_inputs->run_model->build_ui_data->open ui_app.html end-to-end; the RESULTS UI itself stays zero-install and BYTE-UNCHANGED",
        ],
        "task": "Task 7 (end-to-end run + results handoff -> Phase IGUI MVP)",
    },
]

INTEGRATION_CHAIN = (
    "GUI inputs -> model_inputs.json -> scripts/load_user_inputs.py + "
    "scripts/run_model.py -> scripts/build_ui_data.py -> ui_data.json -> "
    "existing offline RESULTS UI ui_app.html (zero-install, unchanged)"
)

# Pre-registered acceptance criteria common to EVERY Phase-IGUI implementation task.
_COMMON_CRITERIA = [
    "the existing zero-install RESULTS UI (ui_app.html) stays byte-unchanged unless a SEPARATE additive-only contract change is explicitly recorded; all nine offline self-tests remain ok:true (522+ checks), 0 network / 0 JS errors, 0 external references",
    "the input+run GUI adds NO third-party runtime dependency beyond the model's existing numpy/pandas/scipy: its server/UI layer is Python standard library only; it binds 127.0.0.1 and makes NO outbound network call",
    "NO model parameter changes without explicit owner sign-off; the Phase 30 stop-rule is honoured and the MR-016/MR-017 owner decision is not pre-empted",
    "every GUI-collected field round-trips through scripts/load_user_inputs.py validation (fail-loud) before a run is permitted; the model_inputs.json schema version is respected",
    "each task carries its own governance ChangeRecord (OWNER_REVIEW) and new self-tests / validation; the governed headline " + GOVERNED_HEADLINE + " is carried bit-for-bit wherever displayed",
]


def design_note() -> Dict[str, Any]:
    """Return the pre-registered Phase IGUI Task 1 design note."""
    return {
        "metadata": {
            "doc_id": DOC_ID,
            "doc_version": DOC_VERSION,
            "phase": "Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)",
            "task": "Task 1 - design note (architecture decision, input-schema coverage map, pre-registered acceptance criteria + gate)",
            "classification": "educational",
            "no_model_parameter_changes": True,
            "stop_rule_honoured": True,
            "owner_decision_pending": True,
            "zero_install_results_ui_preserved": True,
            "directive": (
                "Owner-directed exclusive workstream: a GUI to enter every actuarial / "
                "data input typical of a valuation process AND run the stochastic model "
                "end-to-end. The owner relaxed the strict no-pre-install constraint for "
                "THIS input+run front end ONLY; the offline RESULTS UI (ui_app.html) "
                "stays zero-install and unchanged."
            ),
        },
        "baseline_audit": BASELINE,
        "architecture_decision": {
            "chosen": CHOSEN_ARCHITECTURE,
            "options": ARCHITECTURE_OPTIONS,
            "trade_off": (
                "The owner relaxed zero-install for the input+run front end because the "
                "model itself cannot be run without Python + numpy/pandas/scipy - so a "
                "pure-browser writer (L1) cannot satisfy 'one button to supply inputs AND "
                "compute'. L2 adds the SMALLEST possible footprint: a standard-library "
                "local runner that reuses the existing loader + orchestrator and adds NO "
                "new third-party dependency, while the RESULTS UI stays strictly "
                "zero-install. L3 (frozen binary) is deferred as an optional future "
                "packaging layer because it adds non-reproducible, per-OS build "
                "infrastructure unsuited to this auditable educational repo."
            ),
            "results_ui_untouched": True,
            "new_third_party_runtime_deps": 0,
            "network_calls": 0,
        },
        "input_schema_coverage_map": {
            "integration_chain": INTEGRATION_CHAIN,
            "domains": INPUT_DOMAINS,
            "existing_plumbing": BASELINE["existing_input_plumbing"],
        },
        "staged_tasks": [
            {"task": "Task 2", "domain_id": "D1_run_controls",
             "title": "Run controls + GUI scaffolding (stdlib local runner skeleton)",
             "acceptance_criteria": [
                 "a stdlib-only local runner (scripts/run_gui.py) serves a self-contained input page on 127.0.0.1 and opens it; no third-party dep, no outbound network",
                 "run controls (valuation date, currency, horizon & step, outer/inner scenarios, seed, output label) are collected and written into the model_inputs.json schema accepted by scripts/load_user_inputs.py",
                 "new self-tests cover the runner launch, the run-controls form, and schema round-trip",
             ] + _COMMON_CRITERIA},
            {"task": "Task 3", "domain_id": "D2_policy_model_points",
             "title": "Model points + in-force ingest",
             "acceptance_criteria": [
                 "interactive add/edit/delete of PAR + GMMB model-point rows and a CSV/JSON in-force upload path that maps to the Portfolio schema",
                 "balance-sheet asset rows + stated-total reconciliation surfaced; portfolio scaling/booking disclosed exactly as run_model reports it",
                 "new self-tests cover row editing, file ingest, and reconciliation validation",
             ] + _COMMON_CRITERIA},
            {"task": "Task 4", "domain_id": "D3_assumptions",
             "title": "Assumptions (owner-gated, incremental)",
             "acceptance_criteria": [
                 "currently-supported assumptions (confidence, management-action relief sigma/alpha, benefit share) are editable; frozen/governed parameters remain read-only echo",
                 "additional assumption families (mortality, lapse incl. dynamic, expenses, discount/yield curve, bonus declaration, reinsurance) are surfaced as DISCLOSED inputs and become settable ONLY behind explicit owner sign-off (no model-parameter change otherwise)",
                 "new self-tests cover editable vs read-only gating and the no-parameter-change-without-sign-off guard",
             ] + _COMMON_CRITERIA},
            {"task": "Task 5", "domain_id": "D4_esg_economic",
             "title": "ESG / calibration inputs (stop-rule-bounded)",
             "acceptance_criteria": [
                 "ESG / calibration-target inputs surfaced as read-only echo first; the Phase 30 stop-rule is honoured (NO new copula-structure candidates) and MR-016/MR-017 is not pre-empted",
                 "any settable ESG input is bounded and owner-gated; governed dependence parameters stay frozen",
                 "new self-tests cover stop-rule guard and provenance echo",
             ] + _COMMON_CRITERIA},
            {"task": "Task 6", "domain_id": "D5_validation_gating",
             "title": "Validation surfacing + governance gating before run",
             "acceptance_criteria": [
                 "the loader's fail-loud validation results are surfaced in the GUI and the Run button is BLOCKED until inputs validate clean",
                 "a governance gate (provenance/ChangeRecord) is recorded before each run and a reproducibility digest is emitted per run",
                 "new self-tests cover the run-block-on-invalid behaviour and the per-run digest",
             ] + _COMMON_CRITERIA},
            {"task": "Task 7", "domain_id": "D6_integration",
             "title": "End-to-end run + results handoff (Phase IGUI MVP)",
             "acceptance_criteria": [
                 "one 'Run' action threads load_user_inputs -> run_model -> build_ui_data -> opens ui_app.html with the fresh results",
                 "the RESULTS UI stays zero-install and byte-unchanged; the handoff adds no external reference",
                 "an end-to-end self-test proves inputs -> model_inputs.json -> run -> ui_data.json -> RESULTS UI on a small deterministic config",
             ] + _COMMON_CRITERIA},
        ],
        "acceptance_criteria_common": _COMMON_CRITERIA,
        "execution_plan": {
            "ordering": (
                "design-note-first this cycle; then one input domain / capability per cycle "
                "in order: Task 2 run controls -> Task 3 model points -> Task 4 assumptions "
                "-> Task 5 ESG -> Task 6 validation/gating -> Task 7 end-to-end run + results "
                "handoff (Phase IGUI MVP)"
            ),
            "one_domain_per_cycle": True,
            "governance": "each task carries its own ChangeRecord left in OWNER_REVIEW",
            "completion": "Phase IGUI MVP = a usable input+run GUI that drives the model end-to-end into the existing offline RESULTS UI",
        },
    }


def _live_external_ref_count(repo_root: str) -> int:
    """Count http(s) external src/href references across the HTML artifacts."""
    pat = re.compile(r'(?:src|href)="(?:https?:)?//')
    total = 0
    for name in HTML_ARTIFACTS:
        with open(os.path.join(repo_root, name), encoding="utf-8") as fh:
            total += len(pat.findall(fh.read()))
    return total


def validate_design_note(note: Dict[str, Any], repo_root: str = ".") -> Dict[str, Any]:
    """Task 1 gate: structural checks on the note + LIVE checks on the repo."""
    checks: Dict[str, bool] = {}
    md = note.get("metadata", {})
    base = note.get("baseline_audit", {})
    arch = note.get("architecture_decision", {})
    cov = note.get("input_schema_coverage_map", {})
    staged = note.get("staged_tasks", [])

    # --- structural: identity + discipline ---
    checks["doc_identity"] = (
        md.get("doc_id") == DOC_ID and md.get("doc_version") == DOC_VERSION)
    checks["no_model_parameter_changes"] = md.get("no_model_parameter_changes") is True
    checks["stop_rule_honoured"] = md.get("stop_rule_honoured") is True
    checks["owner_decision_not_preempted"] = md.get("owner_decision_pending") is True
    checks["results_ui_zero_install_preserved"] = (
        md.get("zero_install_results_ui_preserved") is True
        and arch.get("results_ui_untouched") is True)

    # --- architecture decision ---
    opt_ids = [o.get("id") for o in arch.get("options", [])]
    checks["architecture_three_options"] = len(opt_ids) == 3 and len(set(opt_ids)) == 3
    checks["architecture_chosen_valid"] = (
        arch.get("chosen") == CHOSEN_ARCHITECTURE and CHOSEN_ARCHITECTURE in opt_ids)
    checks["architecture_no_new_deps"] = arch.get("new_third_party_runtime_deps") == 0
    checks["architecture_offline"] = arch.get("network_calls") == 0
    checks["architecture_each_option_has_verdict"] = all(
        o.get("verdict") for o in arch.get("options", []))

    # --- coverage map: six domains, each with current/target/gap/task ---
    domains = cov.get("domains", [])
    expected_domain_ids = [
        "D1_run_controls", "D2_policy_model_points", "D3_assumptions",
        "D4_esg_economic", "D5_validation_gating", "D6_integration"]
    checks["coverage_six_domains_ordered"] = (
        [d.get("id") for d in domains] == expected_domain_ids)
    checks["coverage_each_domain_complete"] = all(
        d.get("current_coverage") and d.get("target") and d.get("gap") and d.get("task")
        for d in domains)
    checks["coverage_integration_chain_present"] = (
        "model_inputs.json" in cov.get("integration_chain", "")
        and "run_model.py" in cov.get("integration_chain", "")
        and "ui_app.html" in cov.get("integration_chain", ""))

    # --- staged tasks: one domain per cycle, each pre-registers criteria ---
    checks["staged_tasks_present"] = len(staged) == 6
    checks["staged_tasks_map_domains"] = (
        [t.get("domain_id") for t in staged] == expected_domain_ids)
    checks["staged_tasks_have_criteria"] = all(
        len(t.get("acceptance_criteria", [])) >= len(_COMMON_CRITERIA) + 2 for t in staged)
    checks["one_domain_per_cycle"] = note.get(
        "execution_plan", {}).get("one_domain_per_cycle") is True
    checks["headline_carried_bit_for_bit"] = any(
        GOVERNED_HEADLINE in c for c in note.get("acceptance_criteria_common", []))

    # --- baseline self-tests all green (nine suites) ---
    suite_keys = (
        "ui_app_self_test", "ui_app_evidence_pack_fallback_test",
        "ui_app_integrity_fallback_test", "ui_app_distribution_fallback_test",
        "ui_app_userrun_fallback_test", "ui_app_search_deeplink_test",
        "ui_app_bundle_printall_test", "offline_viewer_self_test",
        "combined_gui_self_test")
    for key in suite_keys:
        st = base.get(key, {})
        checks[f"baseline_{key}_green"] = (
            st.get("ok") is True and st.get("js_errors") == 0
            and st.get("network_calls") == 0)
    checks["baseline_checks_total_consistent"] = (
        sum(base.get(k, {}).get("n_checks", 0) for k in suite_keys)
        == base.get("self_test_checks_total"))

    # --- live repo cross-checks (grow-only / monotonic where appropriate) ---
    try:
        checks["live_zero_external_refs"] = (
            _live_external_ref_count(repo_root) == 0
            and base.get("external_refs_total") == 0)
    except OSError:
        checks["live_zero_external_refs"] = False
    try:
        with open(os.path.join(repo_root, "ui_app.html"), encoding="utf-8") as fh:
            html = fh.read()

        def _ver(text):
            return tuple(int(p) for p in str(text).split(".") if p.isdigit())
        _m = re.search(r'"contract_version":\s*"(\d+(?:\.\d+)*)"', html)
        _live_ver = _ver(_m.group(1)) if _m else ()
        checks["live_contract_version_floor"] = (
            bool(_live_ver) and _live_ver >= _ver(base.get("contract_version", "")))
        checks["live_tab_inventory_floor"] = (
            all(t in html for t in base.get("tabs", []))
            and len(base.get("tabs", [])) == base.get("tab_count"))
        checks["live_ui_app_size_floor"] = (
            os.path.getsize(os.path.join(repo_root, "ui_app.html"))
            >= base.get("artifacts", {}).get("ui_app.html", {}).get("bytes", 10**18))
    except OSError:
        checks["live_contract_version_floor"] = False
        checks["live_tab_inventory_floor"] = False
        checks["live_ui_app_size_floor"] = False

    # the GUI must drive REAL, present plumbing
    checks["live_loader_present"] = os.path.exists(
        os.path.join(repo_root, "scripts", "load_user_inputs.py"))
    checks["live_orchestrator_present"] = os.path.exists(
        os.path.join(repo_root, "scripts", "run_model.py"))

    try:
        with open(os.path.join(repo_root, ".claude-dev", "GOVERNANCE_STORE.json"),
                  encoding="utf-8") as fh:
            gov = json.load(fh)
        gb = base.get("governance_store", {})
        checks["live_governance_counts_floor"] = (
            len(gov.get("change_records", [])) >= gb.get("change_records", 10**9)
            and len(gov.get("audit_trail", [])) >= gb.get("audit_entries", 10**9)
            and len(gov.get("risk_register", [])) == gb.get("risk_register"))
    except (OSError, json.JSONDecodeError):
        checks["live_governance_counts_floor"] = False

    return {"ok": all(checks.values()), "n_checks": len(checks), "checks": checks}
