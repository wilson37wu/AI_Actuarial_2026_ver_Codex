"""Phase 33 Task 1 - offline UI interactive analytics & usability DESIGN NOTE.

The standing scheduled-task directive remains in effect: the calculation
chain is complete, so development continues on the zero-install offline
user interface.  The UI consumes ONLY model-output JSON (no
pre-installation requirement, no network).  Phase 32 consolidated the
governed read-outs (contract 1.16.0, 15 tabs); Phase 33 extends
INTERACTIVITY and USABILITY.  This module pre-registers the pass:

(a) BASELINE AUDIT (measured 2026-06-11, frozen here as cross-check
    targets): ui_app (232 checks) / offline_viewer (11) / combined_gui
    (27) / ui_app_userrun_fallback (9) self-tests all ok:true with zero
    network calls and zero JS errors; zero external references in any of
    the three HTML artifacts; embedded ui_data contract 1.16.0; 15 tabs;
    governance store 84 ChangeRecords / 112 audit entries / 17 risk items.

(b) GAP LIST vs the directive, in priority order (ONE gap per cycle):
    G1 interactive cross-phase SCR comparator (display layer only - every
       figure already embedded; no contract change expected),
    G2 embedded-distribution drill-down (precomputed quantile/CDF grids
       embedded by build_ui_data.py - ADDITIVE contract bump),
    G3 printable owner sign-off / report pack (print CSS + CSV export
       completeness for the MR-016/MR-017 workflow),
    G4 accessibility & usability pass (keyboard navigation, ARIA roles,
       state-persistent tab selection via URL hash - zero-install safe).

(c) PRE-REGISTERED ACCEPTANCE CRITERIA per gap plus criteria common to
    all gaps (self-tests green 0 network / 0 JS errors, additive-only
    contract changes, zero-install preserved, NO model parameter changes,
    display layer never recomputes model figures).

Priority rationale: G1 first because it carries zero data risk (pure
display interactivity over already-embedded figures) and the highest
analytic value; G2 second because it needs a build-time data addition
(strictly precomputed, display recomputes NOTHING); G3 third because it
directly supports the pending MR-016/MR-017 owner sign-off workflow; G4
last so the accessibility pass also covers the surfaces added by G1-G3.

Pure ``governance_change``: NO model parameter changes; NO new
copula-structure candidates (the Phase 30 binding stop-rule stands); the
MR-016/MR-017 owner decision on the Phase 31 pack remains pending and is
not pre-empted by anything in this note.

The Task 1 gate (:func:`validate_design_note`) mixes STRUCTURAL checks on
the note with LIVE checks against the repository (external-ref scan,
embedded contract version, tab inventory, artifact size, governance-store
counts), so the pre-registration cannot drift from the artifact it
describes.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

DOC_ID = "PHASE33_TASK1_DESIGN_NOTE"
DOC_VERSION = "1.0.0"

#: Frozen baseline measurements (2026-06-11 cycle, lock 2026-06-11T18:07Z).
BASELINE = {
    "measured_at_utc": "2026-06-11T18:12:00Z",
    "ui_app_self_test": {"ok": True, "n_checks": 232, "js_errors": 0, "network_calls": 0},
    "offline_viewer_self_test": {"ok": True, "n_checks": 11, "js_errors": 0, "network_calls": 0},
    "combined_gui_self_test": {"ok": True, "n_checks": 27, "js_errors": 0, "network_calls": 0},
    "ui_app_userrun_fallback_test": {"ok": True, "n_checks": 9, "js_errors": 0, "network_calls": 0},
    "external_refs_total": 0,
    "artifacts": {
        "ui_app.html": {"bytes": 572915, "embedded_contract": "1.16.0"},
        "model_result_viewer.html": {"bytes": 142620},
        "combined_model_app.html": {"bytes": 456204},
    },
    "contract_version": "1.16.0",
    "tab_count": 15,
    "tabs": [
        "Overview", "Inventory & Contract", "Calibrations", "Capital & Tail",
        "Management Actions", "Joint Actions (P24)", "Path-wise Actions (P25)",
        "Full Re-Agg (P26)", "Skew-t Tail (P27)", "Grouped-t Tail (P28)",
        "Vine Tail (P29)", "Stop-Rule (P30)", "Owner Decision (P31)",
        "User Run (UIL)", "Governance",
    ],
    "governance_store": {"change_records": 84, "audit_entries": 112, "risk_register": 17},
}

HTML_ARTIFACTS = ["ui_app.html", "model_result_viewer.html", "combined_model_app.html"]

_COMMON_CRITERIA = [
    "ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change",
    "ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically",
    "zero-install preserved: 0 external references, single self-contained HTML file",
    "NO model parameter changes; the display layer never recomputes model figures",
    "offline_viewer + combined_gui + userrun-fallback self-tests remain ok:true",
]


def design_note() -> Dict[str, Any]:
    """Return the pre-registered Phase 33 interactive-analytics design note."""
    return {
        "metadata": {
            "doc_id": DOC_ID,
            "doc_version": DOC_VERSION,
            "phase": "Phase 33: Offline UI Interactive Analytics & Usability",
            "task": "Task 1 - design note (measured baseline, prioritised gap list, acceptance criteria)",
            "classification": "educational",
            "no_model_parameter_changes": True,
            "stop_rule_honoured": True,
            "owner_decision_pending": True,
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
                "title": "Interactive cross-phase SCR comparator",
                "description": (
                    "Every dependence-structure SCR estimate (frozen-t, "
                    "grouped-t, skew-t, vine, tree-3, nested) plus bootstrap "
                    "CIs is already embedded in ui_data 1.16.0, but the tabs "
                    "present them phase-by-phase only. Add an interactive "
                    "comparator: user-selectable baseline structure, signed "
                    "delta table vs the baseline, and a CI overlay chart - "
                    "all rendered from ALREADY-EMBEDDED figures; the display "
                    "layer recomputes nothing beyond subtraction for the "
                    "displayed deltas, which must be labelled as display "
                    "arithmetic, never as new model output."
                ),
                "contract_change": (
                    "NONE expected (pure display layer on contract 1.16.0); "
                    "any unforeseen key addition must be ADDITIVE (1.16.0 -> 1.17.0)"
                ),
                "acceptance_criteria": [
                    "every comparator figure traces bit-for-bit to a key already embedded in ui_data 1.16.0 (no new build-time data)",
                    "governed frozen-t headline 39,975.654628199336 remains the default baseline and is never re-labelled by the comparator",
                    "comparator is neutral: structures listed in registry order, no adoption/steering language (MR-016/MR-017 decision stays with the owner)",
                    "new self-test checks cover baseline switching, delta signs, and CI overlay rendering; suite stays ok:true 0/0",
                ] + _COMMON_CRITERIA,
            },
            {
                "gap_id": "G2",
                "priority": 2,
                "title": "Embedded-distribution drill-down (precomputed grids)",
                "description": (
                    "The UI shows headline quantiles but offers no "
                    "distribution-level drill-down. Extend build_ui_data.py "
                    "to embed PRECOMPUTED quantile/CDF grids (fixed grid, "
                    "computed at build time from archived model output); the "
                    "display layer renders an interactive distribution "
                    "explorer (hover/readout/zoom) over those grids and "
                    "recomputes NOTHING."
                ),
                "contract_change": "ADDITIVE bump (current contract -> next minor, e.g. 1.16.0 -> 1.17.0)",
                "acceptance_criteria": [
                    "grids are computed ONLY at build time by build_ui_data.py from archived model output (provenance stamped); display layer never interpolates beyond the embedded grid resolution without labelling it as display interpolation",
                    "embedded grid values reproducible from the archived run artefacts (spot-checked in the validation report)",
                    "graceful neutral fallback when grids are absent from an older ui_data payload (no JS errors, no blank panel)",
                    "new self-test checks cover grid presence, readout values, and fallback; suite stays ok:true 0/0",
                ] + _COMMON_CRITERIA,
            },
            {
                "gap_id": "G3",
                "priority": 3,
                "title": "Printable owner sign-off / report pack",
                "description": (
                    "The MR-016/MR-017 owner decision pack is browsable "
                    "(Phase 32 G1) but not print-ready, and CSV export "
                    "coverage is partial. Add print CSS (page breaks, "
                    "print-legible tables, suppressed navigation) so the "
                    "Owner Decision and Governance surfaces print to a "
                    "sign-off-ready pack, and complete CSV export coverage "
                    "for every governed read-out table."
                ),
                "contract_change": "NONE expected (presentation only); any key addition must be ADDITIVE",
                "acceptance_criteria": [
                    "printed pack preserves neutrality: options in registry order, decision record rendered BLANK until the owner decides",
                    "every governed read-out table has a CSV export; exported values bit-for-bit equal to the rendered (embedded) values",
                    "print stylesheet adds no external resources (zero-install preserved in print path)",
                    "new self-test checks cover export coverage and print-CSS presence; suite stays ok:true 0/0",
                ] + _COMMON_CRITERIA,
            },
            {
                "gap_id": "G4",
                "priority": 4,
                "title": "Accessibility & usability pass",
                "description": (
                    "The tab strip and tables lack keyboard navigation and "
                    "ARIA semantics, and the selected tab resets on reload. "
                    "Add keyboard navigation (arrow/home/end on the tab "
                    "strip), ARIA roles/labels (tablist/tab/tabpanel, table "
                    "captions), focus-visible styling, and state-persistent "
                    "tab selection via URL hash (zero-install safe; no "
                    "storage APIs). Scheduled last so the pass also covers "
                    "surfaces added by G1-G3."
                ),
                "contract_change": "NONE expected (markup/behaviour only); any key addition must be ADDITIVE",
                "acceptance_criteria": [
                    "tab strip operable by keyboard alone (arrow/home/end + enter/space) with correct ARIA tablist/tab/tabpanel roles and aria-selected state",
                    "selected tab survives reload via URL hash only (no localStorage/sessionStorage; file:// safe)",
                    "no regression in rendered figures: all pre-existing self-test checks still pass bit-identically",
                    "new self-test checks cover keyboard activation, ARIA attributes, and hash persistence; suite stays ok:true 0/0",
                ] + _COMMON_CRITERIA,
            },
        ],
        "execution_plan": {
            "ordering": (
                "one gap per cycle in priority order: Task 2 = G1, Task 3 = G2, "
                "Task 4 = G3, Task 5 = G4"
            ),
            "completion": (
                "Task 6 - phase summary + final consolidated baseline re-audit "
                "(self-tests, external-ref scan, contract inventory) and PHASE 33 "
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
    checks["owner_decision_not_preempted"] = md.get("owner_decision_pending") is True
    checks["four_gaps"] = len(gaps) == 4
    checks["gap_ids_unique_ordered"] = [g.get("gap_id") for g in gaps] == [
        "G1", "G2", "G3", "G4"] and [g.get("priority") for g in gaps] == [1, 2, 3, 4]
    checks["each_gap_has_criteria"] = all(
        len(g.get("acceptance_criteria", [])) >= len(_COMMON_CRITERIA) + 3 for g in gaps)
    checks["each_gap_additive_only"] = all(
        "ADDITIVE" in g.get("contract_change", "") for g in gaps)
    checks["g1_headline_frozen"] = any(
        "39,975.654628199336" in c for c in gaps[0].get("acceptance_criteria", [])) if gaps else False
    checks["g1_no_new_data"] = any(
        "no new build-time data" in c for c in gaps[0].get("acceptance_criteria", [])) if gaps else False
    checks["g2_precomputed_only"] = any(
        "build time" in c for c in gaps[1].get("acceptance_criteria", [])) if len(gaps) > 1 else False
    checks["g3_neutral_blank_decision"] = any(
        "BLANK" in c for c in gaps[2].get("acceptance_criteria", [])) if len(gaps) > 2 else False
    checks["g4_no_storage_apis"] = any(
        "localStorage" in c for c in gaps[3].get("acceptance_criteria", [])) if len(gaps) > 3 else False
    checks["one_gap_per_cycle"] = "one gap per cycle" in note.get(
        "execution_plan", {}).get("ordering", "")

    # --- baseline self-tests all green ---
    for key in ("ui_app_self_test", "offline_viewer_self_test",
                "combined_gui_self_test", "ui_app_userrun_fallback_test"):
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
