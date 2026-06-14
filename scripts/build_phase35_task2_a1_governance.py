#!/usr/bin/env python3
"""Phase 35 Task 2 (gap A1) - governance for the WCAG 2.1 AA keyboard + contrast
conformance pass on the zero-install offline UI.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry recording the
ADDITIVE contract bump 1.18.0 -> 1.19.0 (new a11y_audit key only) and the
CSS-only :focus-visible coverage + in-UI read-only WCAG audit panel. Idempotent.

NO model parameter changes; the binding Phase 30 stop-rule stands; the
MR-016/MR-017 owner decision is not pre-empted. A contrast ratio is not a model
figure; every governed read-out renders bit-identically.

Run:  PYTHONPATH=. python3 scripts/build_phase35_task2_a1_governance.py
"""
from __future__ import annotations
import json
from pathlib import Path
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase 35: Offline UI Accessibility & Evidence-Integrity Deepening"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase 35 Task 2 (gap A1) - formal WCAG 2.1 AA keyboard + "
                "contrast conformance pass on the zero-install offline UI")
AFFECTED_COMPONENTS = [
    "scripts/build_phase35_task2_a1_wcag.py",
    "scripts/ui_app_self_test.cjs",
    "ui_data.json",
    "ui_app.html",
]
STANDARD_REFERENCES = [
    "WCAG 2.1 AA 1.4.3 (contrast minimum - normal text >=4.5:1)",
    "WCAG 2.1 AA 1.4.11 (non-text contrast - UI components / focus >=3:1)",
    "WCAG 2.1 AA 2.1.1 (keyboard) / 2.4.7 (focus visible) / 4.1.2 (name, role, value)",
    "SOA ASOP 41 s3.2 (clear communication of actuarial findings)",
]


def apply(store: GovernanceStore, audit_summary: dict, ui_checks: int) -> dict:
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        for r in store.change_records:
            if r.title == CHANGE_TITLE:
                return {"added": False, "record_id": r.record_id,
                        "status": r.status.value, "reason": "idempotent"}
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Closed gap A1 of the Phase 35 design note: a formal WCAG 2.1 AA "
            "keyboard + contrast conformance pass on the zero-install offline "
            "UI. (1) A comprehensive CSS-only :focus-visible rule now draws a "
            "2px accent outline on EVERY interactive control type "
            "(tab/sub-nav/toolbar/CSV/print buttons, search box + result rows, "
            "filter inputs/selects, the distribution slider, the high-contrast "
            "and print-all toggles, expandable disclosures) - no JavaScript and "
            "no model figure involved; focus order follows reading order. (2) "
            "scripts/build_phase35_task2_a1_wcag.py embeds an ADDITIVE "
            "build-time a11y_audit key carrying MEASURED contrast ratios for "
            "the default and high-contrast themes (relative-luminance contrast "
            "per WCAG 2.x over the exact :root and html.hc palettes; 10 pairs "
            "per theme, all >=AA: body text >=4.5:1, UI/focus >=3:1) plus a "
            "keyboard-operability inventory; the contract bumps 1.18.0 -> "
            "1.19.0 (a11y_audit is the ONLY new top-level key; every pre-"
            "existing ui_data key renders bit-identically - verified by an "
            "additive diff). (3) ui_app.html gained a display-only "
            "renderA11yAuditHtml() that renders the embedded audit as two "
            "read-only tables in the Integrity (H1) panel and recomputes NO "
            "model figure (a contrast ratio is not a model figure). (4) Tests: "
            "10 new ui_app self-test checks (340 -> 350 checks, ok:true, 0 "
            "network / 0 JS errors) covering focus-visible coverage, the "
            "embedded all-pass audit, the keyboard inventory, and the rendered "
            "tables; all eight offline self-tests remain ok:true 0/0 "
            "(ui_app/offline_viewer/combined_gui/userrun/distribution/"
            "integrity/search-deeplink/bundle-printall). Zero-install preserved "
            "(0 external refs, single self-contained HTML). NO model parameter "
            "changes; binding stop-rule honoured; owner decision not pre-empted."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "ui_contract": "1.18.0",
            "a11y_audit": False,
            "focus_visible_scope": "tab/segbtn/tbtn/rrow/crow/panel only",
            "ui_app_self_test_checks": 340,
            "offline_self_tests": 8,
        },
        after_snapshot={
            "ui_contract": "1.19.0",
            "a11y_audit": True,
            "focus_visible_scope": "every interactive control type (CSS-only)",
            "contrast_pairs_per_theme": audit_summary.get("pairs_checked"),
            "themes_measured": audit_summary.get("themes"),
            "min_contrast_ratio": audit_summary.get("min_ratio"),
            "all_pass_AA": audit_summary.get("all_pass"),
            "ui_app_self_test_checks": ui_checks,
            "offline_self_tests": 8,
        },
        impact_assessment=(
            "Display-layer accessibility pass only. ADDITIVE contract change "
            "(a11y_audit); the display layer recomputes no model figure and the "
            "governed frozen-t headline and every other governed read-out are "
            "bit-identical. The MR-016/MR-017 dependence decision is not pre-"
            "empted. Zero-install invariants preserved (0 external refs, single "
            "self-contained HTML)."
        ),
        quantitative_impact=(
            "No governed capital figure changed. Contract 1.18.0 -> 1.19.0 "
            "(additive a11y_audit). Measured AA contrast: 10 pairs per theme x 2 "
            "themes, all pass (min ratio %s:1). ui_app self-test 340 -> %d "
            "checks ok:true 0/0; all 8 offline self-tests green. External refs "
            "remain 0." % (audit_summary.get("min_ratio"), ui_checks)
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: additive contract 1.18.0 -> 1.19.0 (a11y_audit only; pre-"
        "existing keys bit-identical via additive diff); MEASURED AA contrast "
        "all-pass in both themes; CSS-only :focus-visible on every interactive "
        "control type; ui_app self-test 350 checks ok:true 0/0 plus 7 other "
        "offline suites green; 0 external refs; display layer recomputes "
        "nothing; no model parameter changes.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Gap A1 of the Phase 35 design note is closed: "
        "the offline UI now carries a formal, build-time-MEASURED WCAG 2.1 AA "
        "contrast record (default + high-contrast themes) and CSS-only "
        ":focus-visible on every interactive control, rendered read-only in the "
        "Integrity panel. PRESENTATION/ROBUSTNESS ONLY - the MR-016/MR-017 "
        "dependence decision remains PENDING and entirely with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase 35 Task 2 WCAG 2.1 AA "
               "keyboard + contrast pass (gap A1); additive contract 1.18.0 -> "
               "1.19.0 (a11y_audit only); governed figures bit-identical"),
        details={"record_id": rec.record_id, "contract": "1.18.0->1.19.0",
                 "ui_app_self_test_checks": ui_checks,
                 "affected_components": AFFECTED_COMPONENTS}))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main() -> int:
    data = json.load(open("ui_data.json", encoding="utf-8"))
    summary = data["a11y_audit"]["summary"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_chg, n_aud = len(store.change_records), len(store.audit_trail.all())
    res = apply(store, summary, ui_checks=350)
    if not store.audit_trail.verify_all():
        print("AUDIT INTEGRITY FAILED - store NOT saved")
        return 1
    if res.get("added"):
        GOV_PATH.write_text(store.to_json(), encoding="utf-8")
    print(json.dumps({
        "governance": res,
        "change_records": f"{n_chg} -> {len(store.change_records)}",
        "audit_entries": f"{n_aud} -> {len(store.audit_trail.all())}",
        "audit_integrity_ok": store.audit_trail.verify_all(),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
