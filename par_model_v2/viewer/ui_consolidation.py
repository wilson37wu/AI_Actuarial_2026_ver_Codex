"""Phase 32 Task 1 - zero-install offline UI consolidation DESIGN NOTE.

The standing scheduled-task directive is now in effect: the calculation
chain is complete, so development focus shifts to the zero-install offline
user interface.  The UI consumes ONLY model-output JSON (no pre-installation
requirement, no network).  This module pre-registers the consolidation pass:

(a) BASELINE AUDIT (measured 2026-06-11, frozen here as cross-check targets):
    ui_app / offline_viewer / combined_gui self-tests all ok:true with zero
    network calls and zero JS errors; zero external references in any of the
    three HTML artifacts; embedded ui_data contract 1.13.0; 13 tabs.

(b) GAP LIST vs the directive, in priority order (ONE gap per cycle):
    G1 owner-decision-pack surface (contract 1.13.0 -> 1.14.0 ADDITIVE),
    G2 user-input run-result surface (next additive bump),
    G3 governed read-out completeness sweep (inventory-driven, additive).

(c) PRE-REGISTERED ACCEPTANCE CRITERIA per gap plus criteria common to all
    gaps (self-test green, additive-only contract change, zero-install
    preserved, NO model parameter changes, display layer never recomputes).

Pure ``governance_change``: NO model parameter changes; NO new
copula-structure candidates (the Phase 30 binding stop-rule stands).

The Task 1 gate (:func:`validate_design_note`) mixes STRUCTURAL checks on
the note with LIVE checks against the repository (external-ref scan,
embedded contract version, tab inventory, governance-store counts), so the
pre-registration cannot drift from the artifact it describes.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

DOC_ID = "PHASE32_TASK1_DESIGN_NOTE"
DOC_VERSION = "1.0.0"

#: Frozen baseline measurements (2026-06-11 cycle, lock 2026-06-11T13:08Z).
BASELINE = {
    "measured_at_utc": "2026-06-11T13:15:00Z",
    "ui_app_self_test": {"ok": True, "n_checks": 172, "js_errors": 0, "network_calls": 0},
    "offline_viewer_self_test": {"ok": True, "n_checks": 11, "js_errors": 0, "network_calls": 0},
    "combined_gui_self_test": {"ok": True, "n_checks": 27, "js_errors": 0, "network_calls": 0},
    "external_refs_total": 0,
    "artifacts": {
        "ui_app.html": {"bytes": 490846, "embedded_contract": "1.13.0"},
        "model_result_viewer.html": {"bytes": 142620},
        "combined_model_app.html": {"bytes": 456204},
    },
    "contract_version": "1.13.0",
    "tab_count": 13,
    "tabs": [
        "Overview", "Inventory & Contract", "Calibrations", "Capital & Tail",
        "Management Actions", "Joint Actions (P24)", "Path-wise Actions (P25)",
        "Full Re-Agg (P26)", "Skew-t Tail (P27)", "Grouped-t Tail (P28)",
        "Vine Tail (P29)", "Stop-Rule (P30)", "Governance",
    ],
    "governance_store": {"change_records": 79, "audit_entries": 107, "risk_register": 17},
}

HTML_ARTIFACTS = ["ui_app.html", "model_result_viewer.html", "combined_model_app.html"]

_COMMON_CRITERIA = [
    "ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change",
    "ADDITIVE-only contract change: every pre-existing ui_data key renders bit-identically",
    "zero-install preserved: 0 external references, single self-contained HTML file",
    "NO model parameter changes; the display layer never recomputes model figures",
    "offline_viewer + combined_gui self-tests remain ok:true",
]


def design_note() -> Dict[str, Any]:
    """Return the pre-registered Phase 32 consolidation design note."""
    return {
        "metadata": {
            "doc_id": DOC_ID,
            "doc_version": DOC_VERSION,
            "phase": "Phase 32: Zero-Install Offline UI Consolidation",
            "task": "Task 1 - design note (baseline audit, gap list, acceptance criteria)",
            "classification": "educational",
            "no_model_parameter_changes": True,
            "stop_rule_honoured": True,
            "directive": (
                "Calculation chain complete; the UI uses only the stochastic "
                "model's output JSON to display results graphically and "
                "interactively, with no pre-installation requirement."
            ),
        },
        "baseline_audit": BASELINE,
        "gaps": [
            {
                "gap_id": "G1",
                "priority": 1,
                "title": "Owner-decision-pack surface (browsable Phase 31 pack)",
                "description": (
                    "The Phase 31 owner decision pack and one-page summary are "
                    "governance documents only; the offline UI mentions the "
                    "owner decision but offers no browsable surface. Add an "
                    "additive 'Owner Decision (P31)' surface: evidence pack "
                    "key figures, the three options (registry order, neutral, "
                    "no default), sign-off workflow position, and the "
                    "decision-record status (BLANK until the owner decides)."
                ),
                "contract_change": "1.13.0 -> 1.14.0 ADDITIVE",
                "acceptance_criteria": [
                    "every displayed figure bit-for-bit from PHASE31_TASK2_OWNER_DECISION_PACK.json (nothing recomputed)",
                    "neutrality preserved: options in registry order, no steering language, decision record rendered BLANK",
                    "new self-test checks cover the surface; suite stays ok:true 0/0",
                ] + _COMMON_CRITERIA,
            },
            {
                "gap_id": "G2",
                "priority": 2,
                "title": "User-input run-result surface (Phase UIL outputs)",
                "description": (
                    "Phase UIL wired currency/output_label into the GUI, but "
                    "the user-input run itself (RUN_MODEL_SUMMARY.json: run "
                    "configuration, model-point counts, input provenance "
                    "model_inputs.json -> loader -> run_model) has no panel. "
                    "Add an additive run-results surface with graceful "
                    "fallback when no user run is embedded."
                ),
                "contract_change": "next ADDITIVE bump after G1 (1.14.0 -> 1.15.0)",
                "acceptance_criteria": [
                    "renders exclusively from embedded model-output JSON (run summary embedded at build time)",
                    "graceful neutral fallback when no user-input run exists (no JS errors, no blank tab)",
                    "currency/output_label provenance disclosed exactly as stamped by build_ui_data.py",
                ] + _COMMON_CRITERIA,
            },
            {
                "gap_id": "G3",
                "priority": 3,
                "title": "Governed read-out completeness sweep",
                "description": (
                    "Inventory-driven sweep: diff the governance store "
                    "(ChangeRecords, audit trail, model-risk register) and "
                    "the validation-report registry against the ui_data "
                    "governance section; surface any governed read-out not "
                    "yet visible (e.g. full MR register with statuses, "
                    "ChangeRecord status counts) additively."
                ),
                "contract_change": "ADDITIVE bump only if the sweep finds missing read-outs",
                "acceptance_criteria": [
                    "documented inventory diff committed with the change (what was missing, what was added)",
                    "surfaced figures bit-for-bit from the governance store / archived reports",
                ] + _COMMON_CRITERIA,
            },
        ],
        "execution_plan": {
            "ordering": "one gap per cycle in priority order: Task 2 = G1, Task 3 = G2, Task 4 = G3",
            "completion": (
                "Task 5 - phase summary + final consolidated baseline re-audit "
                "(self-tests, external-ref scan, contract inventory) and PHASE 32 "
                "COMPLETE documentation"
            ),
            "governance": "each task carries its own ChangeRecord left in OWNER_REVIEW",
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
    """Task 1 gate: structural checks on the note + live checks on the repo."""
    checks: Dict[str, bool] = {}
    md, base = note.get("metadata", {}), note.get("baseline_audit", {})
    gaps: List[Dict[str, Any]] = note.get("gaps", [])

    # --- structural ---
    checks["doc_identity"] = md.get("doc_id") == DOC_ID and md.get("doc_version") == DOC_VERSION
    checks["no_model_parameter_changes"] = md.get("no_model_parameter_changes") is True
    checks["stop_rule_honoured"] = md.get("stop_rule_honoured") is True
    checks["three_gaps"] = len(gaps) == 3
    checks["gap_ids_unique_ordered"] = [g.get("gap_id") for g in gaps] == ["G1", "G2", "G3"] and [
        g.get("priority") for g in gaps] == [1, 2, 3]
    checks["each_gap_has_criteria"] = all(
        len(g.get("acceptance_criteria", [])) >= len(_COMMON_CRITERIA) + 2 for g in gaps)
    checks["each_gap_additive_only"] = all(
        "ADDITIVE" in g.get("contract_change", "") for g in gaps)
    checks["g1_neutrality_pinned"] = any(
        "neutrality" in c.lower() and "blank" in c.lower()
        for c in gaps[0].get("acceptance_criteria", [])) if gaps else False
    checks["g1_bit_for_bit_pack"] = any(
        "PHASE31_TASK2_OWNER_DECISION_PACK" in c
        for c in gaps[0].get("acceptance_criteria", [])) if gaps else False
    checks["one_gap_per_cycle"] = "one gap per cycle" in note.get(
        "execution_plan", {}).get("ordering", "")

    # --- baseline self-tests all green ---
    for key in ("ui_app_self_test", "offline_viewer_self_test", "combined_gui_self_test"):
        st = base.get(key, {})
        checks[f"baseline_{key}_green"] = (
            st.get("ok") is True and st.get("js_errors") == 0 and st.get("network_calls") == 0)

    # --- live repo cross-checks ---
    try:
        checks["live_zero_external_refs"] = _live_external_ref_count(repo_root) == 0 and \
            base.get("external_refs_total") == 0
    except OSError:
        checks["live_zero_external_refs"] = False
    try:
        with open(os.path.join(repo_root, "ui_app.html"), encoding="utf-8") as fh:
            html = fh.read()
        checks["live_contract_version_match"] = (
            f'"contract_version": "{base.get("contract_version")}"' in html)
        checks["live_tab_inventory_match"] = all(t in html for t in base.get("tabs", [])) and \
            len(base.get("tabs", [])) == base.get("tab_count")
        checks["live_single_file_size_match"] = (
            os.path.getsize(os.path.join(repo_root, "ui_app.html"))
            == base.get("artifacts", {}).get("ui_app.html", {}).get("bytes"))
    except OSError:
        checks["live_contract_version_match"] = False
        checks["live_tab_inventory_match"] = False
        checks["live_single_file_size_match"] = False
    try:
        with open(os.path.join(repo_root, ".claude-dev", "GOVERNANCE_STORE.json"),
                  encoding="utf-8") as fh:
            gov = json.load(fh)
        gb = base.get("governance_store", {})
        # The store only grows (this task's own ChangeRecord lands after the
        # gate), so the live store must contain AT LEAST the baseline counts.
        checks["live_governance_counts_match"] = (
            len(gov.get("change_records", [])) >= gb.get("change_records", 10**9)
            and len(gov.get("audit_trail", [])) >= gb.get("audit_entries", 10**9)
            and len(gov.get("risk_register", [])) == gb.get("risk_register"))
    except (OSError, json.JSONDecodeError):
        checks["live_governance_counts_match"] = False

    return {"ok": all(checks.values()), "n_checks": len(checks), "checks": checks}
