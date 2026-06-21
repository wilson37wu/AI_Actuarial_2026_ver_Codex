"""Phase 35 Task 1 - offline UI accessibility & evidence-integrity DESIGN NOTE.

The standing scheduled-task directive remains in effect: the calculation
chain is complete, so development continues on the zero-install offline
user interface.  The UI consumes ONLY model-output JSON (no
pre-installation requirement, no network).  Phase 33 closed gaps G1-G4,
and Phase 34 closed gaps H1-H4 (self-describing contract guard + in-UI
integrity panel, global cross-tab search + deep links, one-click evidence
bundle + print-all, responsive + high-contrast pass), consolidating the
artifact at contract 1.18.0 with 18 tabs.  Phase 35 DEEPENS the
accessibility and the evidence-integrity assurance of that surface.

(a) BASELINE AUDIT (re-measured 2026-06-14 at Phase 35 completion / Task 5,
    refreshed here as cross-check targets after gaps A1/A2/A3 landed): EIGHT
    offline self-tests all ok:true with zero network calls and zero JS
    errors - ui_app (368 checks), offline_viewer (11), combined_gui (27),
    ui_app_userrun_fallback (9), ui_app_distribution_fallback (9),
    ui_app_integrity_fallback (10), ui_app_search_deeplink (18), and
    ui_app_bundle_printall (21); 473 checks total; zero external references
    in any of the three HTML artifacts; embedded ui_data contract 1.20.0
    (24 top-level keys incl. a11y_audit + contract_manifest); 18 tabs;
    governance store 96 ChangeRecords / 124 audit entries / 17 risk items.

(b) GAP LIST vs the directive, in priority order (ONE gap per cycle):
    A1 formal WCAG 2.1 AA keyboard + contrast conformance pass
       (accessibility: a measured, recorded conformance pass - visible
       :focus-visible indicator on every interactive control, full
       keyboard operability of the controls not yet exercised, logical
       focus order, and measured AA contrast ratios in BOTH the default
       and the high-contrast theme, embedded as a build-time read-only
       audit table - ADDITIVE a11y_audit key),
    A2 per-section cryptographic digest in the H1 integrity panel
       (evidence integrity: a build-time per-section SHA-256 digest +
       root digest written into the contract manifest, recomputed
       IN-BROWSER from the embedded payload with no network so a reviewer
       can confirm the snapshot was not altered offline - tamper-evident
       per-section verified/altered table - ADDITIVE manifest fields),
    A3 one-page printable model-card cover (communication: a single-page
       ASOP-41-style model card - identity, scope, governed headline, top
       limitations, stop-rule status, owner-decision-pending - assembled
       bit-for-bit from the embedded snapshot, decision field BLANK,
       provenance-stamped - print/presentation only).

(c) PRE-REGISTERED ACCEPTANCE CRITERIA per gap plus criteria common to
    all gaps (eight self-tests green 0 network / 0 JS errors,
    additive-only contract changes, zero-install preserved, NO model
    parameter changes, display layer never recomputes model figures - a
    cryptographic hash over the embedded bytes is NOT a model figure).

Priority rationale: A1 first because a formal, measured accessibility
conformance record has the broadest reviewer-assurance value and is
strictly additive (CSS focus treatment + a build-time audit table); A2
second because a per-section digest closes the remaining
evidence-integrity gap left by Phase 34 H1 (the manifest proved keys were
PRESENT, not that their CONTENT was unaltered); A3 last because the
one-page model card is presentation-only and naturally summarises the
surfaces hardened by A1-A2.

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

DOC_ID = "PHASE35_TASK1_DESIGN_NOTE"
DOC_VERSION = "1.0.0"

#: Governed headline SCR (frozen single-df t), bit-for-bit invariant.
GOVERNED_HEADLINE = "39,975.654628199336"

#: Frozen baseline measurements (2026-06-14 cycle, lock 2026-06-14T05:08Z).
BASELINE = {
    "measured_at_utc": "2026-06-14T09:10:00Z",
    "ui_app_self_test": {"ok": True, "n_checks": 368, "js_errors": 0, "network_calls": 0},
    "offline_viewer_self_test": {"ok": True, "n_checks": 11, "js_errors": 0, "network_calls": 0},
    "combined_gui_self_test": {"ok": True, "n_checks": 27, "js_errors": 0, "network_calls": 0},
    "ui_app_userrun_fallback_test": {"ok": True, "n_checks": 9, "js_errors": 0, "network_calls": 0},
    "ui_app_distribution_fallback_test": {"ok": True, "n_checks": 9, "js_errors": 0, "network_calls": 0},
    "ui_app_integrity_fallback_test": {"ok": True, "n_checks": 10, "js_errors": 0, "network_calls": 0},
    "ui_app_search_deeplink_test": {"ok": True, "n_checks": 18, "js_errors": 0, "network_calls": 0},
    "ui_app_bundle_printall_test": {"ok": True, "n_checks": 21, "js_errors": 0, "network_calls": 0},
    "self_test_checks_total": 473,
    "external_refs_total": 0,
    "artifacts": {
        "ui_app.html": {"bytes": 678921, "embedded_contract": "1.20.0"},
        "model_result_viewer.html": {"bytes": 142620},
        "combined_model_app.html": {"bytes": 456204},
    },
    "contract_version": "1.20.0",
    "tab_count": 18,
    "tabs": [
        "Overview", "Inventory & Contract", "Calibrations", "Capital & Tail",
        "Management Actions", "Joint Actions (P24)", "Path-wise Actions (P25)",
        "Full Re-Agg (P26)", "Skew-t Tail (P27)", "Grouped-t Tail (P28)",
        "Vine Tail (P29)", "Stop-Rule (P30)", "SCR Comparator (P33)",
        "Distribution Explorer (P33)", "Owner Decision (P31)",
        "User Run (UIL)", "Governance", "Integrity (H1)",
    ],
    "governance_store": {"change_records": 96, "audit_entries": 124, "risk_register": 17},
}

HTML_ARTIFACTS = ["ui_app.html", "model_result_viewer.html", "combined_model_app.html"]

_COMMON_CRITERIA = [
    "ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change",
    "ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically",
    "zero-install preserved: 0 external references, single self-contained HTML file",
    "NO model parameter changes; the display layer never recomputes model figures (a cryptographic hash over the embedded bytes is not a model figure)",
    "all eight offline self-tests (ui_app + offline_viewer + combined_gui + userrun-fallback + distribution-fallback + integrity-fallback + search-deeplink + bundle-printall) remain ok:true",
]


def design_note() -> Dict[str, Any]:
    """Return the pre-registered Phase 35 accessibility/integrity design note."""
    return {
        "metadata": {
            "doc_id": DOC_ID,
            "doc_version": DOC_VERSION,
            "phase": "Phase 35: Offline UI Accessibility & Evidence-Integrity Deepening",
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
                "gap_id": "A1",
                "priority": 1,
                "title": "Formal WCAG 2.1 AA keyboard + contrast conformance pass",
                "description": (
                    "Phase 33 G4 added keyboard tab routing and Phase 34 H4 "
                    "a high-contrast toggle, but there is no formal, MEASURED "
                    "WCAG 2.1 AA conformance record. Add (i) a CSS-only "
                    ":focus-visible indicator on every interactive control "
                    "(tab buttons, sub-nav segmented buttons, search box + "
                    "results, sliders, export/print buttons, high-contrast "
                    "and print-all toggles), (ii) full keyboard operability "
                    "of the controls not yet exercised by the suite, with a "
                    "logical focus order, and (iii) a build-time measured "
                    "contrast-audit table (ratios for body text >=4.5:1 and "
                    "large-text / UI components >=3:1 in BOTH the default and "
                    "high-contrast themes) embedded read-only. The display "
                    "layer renders the audit and recomputes no model figure."
                ),
                "contract_change": (
                    "ADDITIVE bump (1.18.0 -> 1.19.0): new a11y_audit key "
                    "(build-time measured contrast/keyboard evidence) ONLY; "
                    "every pre-existing key renders bit-identically"
                ),
                "acceptance_criteria": [
                    "every interactive control is reachable and operable by keyboard alone (Tab / Shift-Tab / Enter / Space / Arrow) with a visible :focus-visible indicator; focus order follows reading order",
                    "measured AA contrast: all body text >=4.5:1 and large-text / UI-component boundaries >=3:1 in BOTH the default and high-contrast themes, embedded as a build-time read-only audit table",
                    "contrast / keyboard audit numbers are written ONLY at build time by build_ui_data.py; the display layer renders them and computes nothing model-related",
                    "new self-test checks cover :focus-visible presence, keyboard operability of the previously-uncovered controls, and the embedded contrast-audit table; suite stays ok:true 0/0",
                ] + _COMMON_CRITERIA,
            },
            {
                "gap_id": "A2",
                "priority": 2,
                "title": "Per-section cryptographic digest in the H1 integrity panel",
                "description": (
                    "Phase 34 H1 embedded a contract manifest and an "
                    "integrity panel that proves each required key is "
                    "PRESENT, but not that its CONTENT was unaltered. Add a "
                    "build-time per-section SHA-256 digest (one per top-level "
                    "ui_data section) plus a root digest, written into "
                    "contract_manifest by build_ui_data.py, and a load-time "
                    "verifier that recomputes each digest IN-BROWSER from the "
                    "embedded payload with NO network and NO storage API "
                    "(file:// safe), surfacing a per-section verified/altered "
                    "table and an overall tamper-evident badge in the H1 "
                    "panel. The digest is over the embedded bytes only; no "
                    "model figure is recomputed (a hash is not a model "
                    "figure)."
                ),
                "contract_change": (
                    "ADDITIVE bump (1.19.0 -> 1.20.0): contract_manifest "
                    "gains section_digests + digest_algo + root_digest ONLY; "
                    "every pre-existing key renders bit-identically"
                ),
                "acceptance_criteria": [
                    "per-section SHA-256 digests + a root digest are written ONLY at build time by build_ui_data.py into contract_manifest; the algorithm and digests are display-read-only",
                    "the in-browser verifier recomputes each section digest from the embedded payload with NO network and no storage API (file:// safe) and reports per-section verified/altered plus an overall tamper-evident badge",
                    "on the intact full payload every section verifies (overall = verified); a single altered byte in any section flips that section and the overall badge to 'altered' with a neutral, non-steering message",
                    "a hash is not a model figure: the governed headline " + GOVERNED_HEADLINE + " and all governed read-outs render bit-identically and the verifier recomputes no model quantity",
                    "new self-test checks cover digest presence, full-payload verify-all, and the altered-section mismatch via a dedicated jsdom fallback test; suite stays ok:true 0/0",
                ] + _COMMON_CRITERIA,
            },
            {
                "gap_id": "A3",
                "priority": 3,
                "title": "One-page printable model-card cover",
                "description": (
                    "Phase 33 G3 added a sign-off print cover and Phase 34 H3 "
                    "a print-all pack, but there is no single-page, "
                    "ASOP-41-style MODEL CARD for a reviewer who wants one "
                    "page: model identity, scope, governed headline, top "
                    "limitations, Phase 30 stop-rule status, and the "
                    "owner-decision-pending state. Add a CSS-print one-page "
                    "model-card cover assembled bit-for-bit from the embedded "
                    "snapshot, with the owner-decision field rendered BLANK "
                    "(decision not pre-empted) and a provenance stamp "
                    "(contract version + build stamp). Nothing is recomputed."
                ),
                "contract_change": "NONE expected (presentation / print only); any key addition must be ADDITIVE",
                "acceptance_criteria": [
                    "the model-card cover fits one page in print and is assembled bit-for-bit from the embedded snapshot; governed headline " + GOVERNED_HEADLINE + " carried exactly and never re-labelled",
                    "it states model identity, scope, governed headline, top limitations, Phase 30 stop-rule status, and renders the owner-decision field BLANK (MR-016/MR-017 not pre-empted)",
                    "the cover is provenance-stamped (contract version + build stamp) and adds no external resource (zero-install preserved)",
                    "new self-test checks cover the model-card cover presence, the bit-for-bit headline, the blank decision field, and the one-page print CSS; suite stays ok:true 0/0",
                ] + _COMMON_CRITERIA,
            },
        ],
        "execution_plan": {
            "ordering": (
                "one gap per cycle in priority order: Task 2 = A1, Task 3 = A2, "
                "Task 4 = A3"
            ),
            "completion": (
                "Task 5 - phase summary + final consolidated baseline re-audit "
                "(self-tests, external-ref scan, contract inventory) and PHASE 35 "
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
    checks["three_gaps"] = len(gaps) == 3
    checks["gap_ids_unique_ordered"] = [g.get("gap_id") for g in gaps] == [
        "A1", "A2", "A3"] and [g.get("priority") for g in gaps] == [1, 2, 3]
    checks["each_gap_has_criteria"] = all(
        len(g.get("acceptance_criteria", [])) >= len(_COMMON_CRITERIA) + 3 for g in gaps)
    checks["each_gap_additive_only"] = all(
        "ADDITIVE" in g.get("contract_change", "") for g in gaps)
    checks["a1_focus_visible"] = any(
        "focus-visible" in c for c in gaps[0].get("acceptance_criteria", [])) if gaps else False
    checks["a1_contrast_aa"] = any(
        "4.5:1" in c for c in gaps[0].get("acceptance_criteria", [])) if gaps else False
    checks["a2_section_digest"] = any(
        "SHA-256" in c for c in gaps[1].get("acceptance_criteria", [])) if len(gaps) > 1 else False
    checks["a2_no_network_verify"] = any(
        "NO network" in c for c in gaps[1].get("acceptance_criteria", [])) if len(gaps) > 1 else False
    checks["a2_headline_frozen"] = any(
        GOVERNED_HEADLINE in c for c in gaps[1].get("acceptance_criteria", [])) if len(gaps) > 1 else False
    checks["a3_headline_bit_for_bit"] = any(
        GOVERNED_HEADLINE in c for c in gaps[2].get("acceptance_criteria", [])) if len(gaps) > 2 else False
    checks["a3_blank_decision"] = any(
        "BLANK" in c for c in gaps[2].get("acceptance_criteria", [])) if len(gaps) > 2 else False
    checks["one_gap_per_cycle"] = "one gap per cycle" in note.get(
        "execution_plan", {}).get("ordering", "")

    # --- baseline self-tests all green (eight suites) ---
    for key in ("ui_app_self_test", "offline_viewer_self_test",
                "combined_gui_self_test", "ui_app_userrun_fallback_test",
                "ui_app_distribution_fallback_test", "ui_app_integrity_fallback_test",
                "ui_app_search_deeplink_test", "ui_app_bundle_printall_test"):
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
        # Frozen historical snapshot vs a moving repo: contract versions and the
        # single-file bundle only ever grow under the additive-only contract, so
        # these are MONOTONIC regression guards (catch a downgrade / shrink /
        # deletion) rather than exact point-in-time matches. Mirrors the grow-only
        # logic already used for live_tab_inventory_match and
        # live_governance_counts_match. (Owner finding 2026-06-14: frozen
        # design-note gates must not live-match an exact contract/byte size, which
        # otherwise reds out at every later additive phase.)
        def _ver(text):
            return tuple(int(p) for p in str(text).split(".") if p.isdigit())
        _m = re.search(r'"contract_version":\s*"(\d+(?:\.\d+)*)"', html)
        _live_ver = _ver(_m.group(1)) if _m else ()
        _base_ver = _ver(base.get("contract_version", ""))
        checks["live_contract_version_match"] = bool(_live_ver) and _live_ver >= _base_ver
        checks["live_tab_inventory_match"] = all(t in html for t in base.get("tabs", [])) and \
            len(base.get("tabs", [])) == base.get("tab_count")
        checks["live_single_file_size_match"] = (
            os.path.getsize(os.path.join(repo_root, "ui_app.html"))
            >= base.get("artifacts", {}).get("ui_app.html", {}).get("bytes", 10**18))
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
