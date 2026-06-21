"""Phase 34 Task 1 - offline UI usability hardening DESIGN NOTE.

The standing scheduled-task directive remains in effect: the calculation
chain is complete, so development continues on the zero-install offline
user interface.  The UI consumes ONLY model-output JSON (no
pre-installation requirement, no network).  Phase 33 closed gaps G1-G4
(interactive cross-phase SCR comparator, embedded-distribution
drill-down, printable owner sign-off / report pack, accessibility &
usability pass) and consolidated the artifact at contract 1.17.0 with 17
tabs.  Phase 34 HARDENS robustness and usability of that surface.

(a) BASELINE AUDIT (measured 2026-06-13, frozen here as cross-check
    targets): FIVE offline self-tests all ok:true with zero network calls
    and zero JS errors - ui_app (297 checks), offline_viewer (11),
    combined_gui (27), ui_app_userrun_fallback (9), and the
    ui_app_distribution_fallback test added in Phase 33 (9); zero external
    references in any of the three HTML artifacts; embedded ui_data
    contract 1.17.0 (22 top-level keys incl. distribution_explorer); 17
    tabs; governance store 90 ChangeRecords / 118 audit entries / 17 risk
    items.

(b) GAP LIST vs the directive, in priority order (ONE gap per cycle):
    H1 self-describing data-contract guard + in-UI schema/integrity panel
       (robustness: embed a contract manifest, validate the payload at
       load, show a NEUTRAL degraded-mode banner instead of a silent
       partial render - ADDITIVE manifest key),
    H2 global cross-tab search + deep-linkable read-outs (usability:
       discoverability across the 17-tab surface; URL-hash deep links to
       tab+section, extending the Phase 33 G4 hash mechanism - no storage
       APIs),
    H3 one-click full evidence bundle export + print-all pack (export
       completeness: every governed read-out to a single provenance-
       stamped bundle and a print-all mode, building on Phase 33 G3 - all
       values bit-for-bit from the embedded snapshot),
    H4 responsive / small-screen + high-contrast usability pass
       (accessibility cont.: narrow-viewport layout, prefers-reduced-
       motion, CSS high-contrast toggle - zero-install, no storage APIs;
       scheduled last so it also covers H1-H3 surfaces).

(c) PRE-REGISTERED ACCEPTANCE CRITERIA per gap plus criteria common to
    all gaps (self-tests green 0 network / 0 JS errors, additive-only
    contract changes, zero-install preserved, NO model parameter changes,
    display layer never recomputes model figures).

Priority rationale: H1 first because integrity/robustness has the highest
assurance value and is strictly additive (a build-time manifest) - it
protects every other surface against silent payload drift; H2 second
because discoverability is the biggest usability gap now that the surface
spans 17 tabs; H3 third because it completes the owner-facing evidence /
sign-off export story (MR-016/MR-017 workflow); H4 last so the responsive
and high-contrast pass also covers the surfaces added by H1-H3.

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

DOC_ID = "PHASE34_TASK1_DESIGN_NOTE"
DOC_VERSION = "1.0.0"

#: Governed headline SCR (frozen single-df t), bit-for-bit invariant.
GOVERNED_HEADLINE = "39,975.654628199336"

#: Frozen baseline measurements (2026-06-13 cycle, lock 2026-06-13T23:07Z).
BASELINE = {
    "measured_at_utc": "2026-06-13T23:20:00Z",
    "ui_app_self_test": {"ok": True, "n_checks": 297, "js_errors": 0, "network_calls": 0},
    "offline_viewer_self_test": {"ok": True, "n_checks": 11, "js_errors": 0, "network_calls": 0},
    "combined_gui_self_test": {"ok": True, "n_checks": 27, "js_errors": 0, "network_calls": 0},
    "ui_app_userrun_fallback_test": {"ok": True, "n_checks": 9, "js_errors": 0, "network_calls": 0},
    "ui_app_distribution_fallback_test": {"ok": True, "n_checks": 9, "js_errors": 0, "network_calls": 0},
    "external_refs_total": 0,
    "artifacts": {
        "ui_app.html": {"bytes": 619761, "embedded_contract": "1.17.0"},
        "model_result_viewer.html": {"bytes": 142620},
        "combined_model_app.html": {"bytes": 456204},
    },
    "contract_version": "1.17.0",
    "tab_count": 17,
    "tabs": [
        "Overview", "Inventory & Contract", "Calibrations", "Capital & Tail",
        "Management Actions", "Joint Actions (P24)", "Path-wise Actions (P25)",
        "Full Re-Agg (P26)", "Skew-t Tail (P27)", "Grouped-t Tail (P28)",
        "Vine Tail (P29)", "Stop-Rule (P30)", "SCR Comparator (P33)",
        "Distribution Explorer (P33)", "Owner Decision (P31)",
        "User Run (UIL)", "Governance",
    ],
    "governance_store": {"change_records": 90, "audit_entries": 118, "risk_register": 17},
}

HTML_ARTIFACTS = ["ui_app.html", "model_result_viewer.html", "combined_model_app.html"]

_COMMON_CRITERIA = [
    "ui_app_self_test.cjs ok:true with 0 network calls and 0 JS errors after the change",
    "ADDITIVE-only contract change (if any): every pre-existing ui_data key renders bit-identically",
    "zero-install preserved: 0 external references, single self-contained HTML file",
    "NO model parameter changes; the display layer never recomputes model figures",
    "offline_viewer + combined_gui + userrun-fallback + distribution-fallback self-tests remain ok:true",
]


def design_note() -> Dict[str, Any]:
    """Return the pre-registered Phase 34 usability-hardening design note."""
    return {
        "metadata": {
            "doc_id": DOC_ID,
            "doc_version": DOC_VERSION,
            "phase": "Phase 34: Offline UI Usability Hardening",
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
                "gap_id": "H1",
                "priority": 1,
                "title": "Self-describing data-contract guard + in-UI schema/integrity panel",
                "description": (
                    "The UI assumes a well-formed ui_data payload: a missing "
                    "or mismatched key currently degrades silently to a blank "
                    "or partial panel with no signal to the user. Embed a "
                    "build-time contract MANIFEST (expected contract version "
                    "+ required top-level keys, written by build_ui_data.py) "
                    "and add a load-time validator that renders an "
                    "integrity/schema panel: contract version match, "
                    "per-key present/absent table, and a NEUTRAL degraded-mode "
                    "banner when the payload is incomplete or the contract "
                    "version is unexpected. The validator inspects ONLY the "
                    "embedded payload and recomputes no model figure."
                ),
                "contract_change": (
                    "ADDITIVE bump (1.17.0 -> 1.18.0): new contract_manifest "
                    "key ONLY; every pre-existing key renders bit-identically"
                ),
                "acceptance_criteria": [
                    "manifest is written ONLY at build time by build_ui_data.py (expected version + required key list); display layer reads it and computes nothing model-related",
                    "validator reports PASS on the current 1.17.0/1.18.0 payload (all required keys present, contract matches) with no JS errors",
                    "neutral degraded-mode banner shown for a payload missing a required key or carrying an unexpected contract version - no blank panel, no steering language",
                    "new self-test checks cover manifest presence, validator PASS on the full payload, and the degraded-mode banner via a dedicated jsdom fallback test; suite stays ok:true 0/0",
                ] + _COMMON_CRITERIA,
            },
            {
                "gap_id": "H2",
                "priority": 2,
                "title": "Global cross-tab search + deep-linkable read-outs",
                "description": (
                    "With 17 tabs the surface is hard to navigate: there is "
                    "no way to find a specific governed figure or table "
                    "without clicking through tabs. Add a global search box "
                    "that indexes ONLY already-rendered text (tab titles, "
                    "table captions, headline labels) and jumps to the match, "
                    "plus URL-hash deep links that restore tab + in-tab "
                    "section (extending the Phase 33 G4 hash mechanism). Pure "
                    "display layer; no storage APIs; file:// safe."
                ),
                "contract_change": "NONE expected (pure display layer); any unforeseen key addition must be ADDITIVE",
                "acceptance_criteria": [
                    "search index is built ONLY from text already embedded/rendered in the artifact (no new build-time data, no network)",
                    "governed frozen-t headline " + GOVERNED_HEADLINE + " is findable and is never re-labelled by search/highlight",
                    "deep links restore both the selected tab and the in-tab section via URL hash only (no localStorage/sessionStorage; file:// safe)",
                    "new self-test checks cover search hit/restore, deep-link tab+section restore, and no-storage-API compliance; suite stays ok:true 0/0",
                ] + _COMMON_CRITERIA,
            },
            {
                "gap_id": "H3",
                "priority": 3,
                "title": "One-click full evidence bundle export + print-all pack",
                "description": (
                    "Phase 33 G3 added per-table CSV exports and a print "
                    "sign-off cover, but assembling the complete evidence set "
                    "still requires many clicks. Add a single action that "
                    "exports EVERY governed read-out to one provenance-stamped "
                    "bundle (multi-section CSV/JSON with contract version + "
                    "build stamp + governed headline) and a print-all mode "
                    "that lays out all governed surfaces for a single sign-off "
                    "print. Values are taken bit-for-bit from the embedded "
                    "snapshot; nothing is recomputed."
                ),
                "contract_change": "NONE expected (presentation/export only); any key addition must be ADDITIVE",
                "acceptance_criteria": [
                    "every value in the bundle is bit-for-bit equal to the embedded snapshot; governed headline " + GOVERNED_HEADLINE + " carried exactly and never re-labelled",
                    "bundle is provenance-stamped (contract version + build stamp); decision record exported BLANK (owner decision not pre-empted)",
                    "export and print-all paths add no external resources (zero-install preserved); options stay in registry order",
                    "new self-test checks cover bundle section coverage, bit-for-bit headline, blank decision record, and print-all CSS presence; suite stays ok:true 0/0",
                ] + _COMMON_CRITERIA,
            },
            {
                "gap_id": "H4",
                "priority": 4,
                "title": "Responsive / small-screen + high-contrast usability pass",
                "description": (
                    "The layout targets a wide desktop viewport and a single "
                    "colour scheme. Add a responsive pass (no horizontal "
                    "scroll on narrow viewports, legible charts/tables), "
                    "prefers-reduced-motion support, and a CSS-only "
                    "high-contrast toggle persisted via URL hash. Scheduled "
                    "last so the pass also covers the surfaces added by "
                    "H1-H3. Markup/CSS/behaviour only; no storage APIs."
                ),
                "contract_change": "NONE expected (markup/CSS/behaviour only); any key addition must be ADDITIVE",
                "acceptance_criteria": [
                    "no horizontal overflow at a narrow (<=768px) viewport; tables/charts remain legible and operable",
                    "high-contrast toggle is CSS-only and persists via URL hash only (no localStorage/sessionStorage); prefers-reduced-motion honoured",
                    "no regression in rendered figures: all pre-existing self-test checks still pass bit-identically",
                    "new self-test checks cover narrow-viewport layout, the high-contrast toggle, and reduced-motion handling; suite stays ok:true 0/0",
                ] + _COMMON_CRITERIA,
            },
        ],
        "execution_plan": {
            "ordering": (
                "one gap per cycle in priority order: Task 2 = H1, Task 3 = H2, "
                "Task 4 = H3, Task 5 = H4"
            ),
            "completion": (
                "Task 6 - phase summary + final consolidated baseline re-audit "
                "(self-tests, external-ref scan, contract inventory) and PHASE 34 "
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
        "H1", "H2", "H3", "H4"] and [g.get("priority") for g in gaps] == [1, 2, 3, 4]
    checks["each_gap_has_criteria"] = all(
        len(g.get("acceptance_criteria", [])) >= len(_COMMON_CRITERIA) + 3 for g in gaps)
    checks["each_gap_additive_only"] = all(
        "ADDITIVE" in g.get("contract_change", "") for g in gaps)
    checks["h1_manifest_build_time_only"] = any(
        "build time" in c for c in gaps[0].get("acceptance_criteria", [])) if gaps else False
    checks["h1_neutral_degraded_banner"] = any(
        "degraded-mode banner" in c for c in gaps[0].get("acceptance_criteria", [])) if gaps else False
    checks["h2_headline_frozen"] = any(
        GOVERNED_HEADLINE in c for c in gaps[1].get("acceptance_criteria", [])) if len(gaps) > 1 else False
    checks["h2_no_storage_apis"] = any(
        "localStorage" in c for c in gaps[1].get("acceptance_criteria", [])) if len(gaps) > 1 else False
    checks["h3_headline_bit_for_bit"] = any(
        GOVERNED_HEADLINE in c for c in gaps[2].get("acceptance_criteria", [])) if len(gaps) > 2 else False
    checks["h3_blank_decision"] = any(
        "BLANK" in c for c in gaps[2].get("acceptance_criteria", [])) if len(gaps) > 2 else False
    checks["h4_no_storage_apis"] = any(
        "localStorage" in c for c in gaps[3].get("acceptance_criteria", [])) if len(gaps) > 3 else False
    checks["one_gap_per_cycle"] = "one gap per cycle" in note.get(
        "execution_plan", {}).get("ordering", "")

    # --- baseline self-tests all green (five suites) ---
    for key in ("ui_app_self_test", "offline_viewer_self_test",
                "combined_gui_self_test", "ui_app_userrun_fallback_test",
                "ui_app_distribution_fallback_test"):
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
