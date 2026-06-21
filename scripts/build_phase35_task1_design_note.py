"""Phase 35 Task 1 - offline UI accessibility & evidence-integrity design note.

Renders the pre-registered design note (measured baseline + prioritised gap
list + acceptance criteria, see
par_model_v2.viewer.ui_accessibility_integrity), runs the Task 1 gate
(structural + LIVE repo cross-checks), and writes:

  docs/validation/PHASE35_TASK1_DESIGN_NOTE.{json,md}
  docs/UI_ACCESSIBILITY_INTEGRITY_DESIGN_CARD.md

Pure governance_change (--governance), left in OWNER_REVIEW.
NO model parameter changes; the Phase 30 binding stop-rule stands; the
MR-016/MR-017 owner decision is not pre-empted.
"""

from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore
from par_model_v2.viewer.ui_accessibility_integrity import (
    DOC_ID,
    DOC_VERSION,
    design_note,
    validate_design_note,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE35_TASK1_DESIGN_NOTE.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE35_TASK1_DESIGN_NOTE.md")
CARD_PATH = os.path.join("docs", "UI_ACCESSIBILITY_INTEGRITY_DESIGN_CARD.md")

CHANGE_TITLE = (
    "Phase 35 Task 1 - offline UI accessibility & evidence-integrity design "
    "note; baseline audit green (8 self-tests 340/11/27/9/9/10/18/21 = 445 "
    "checks, 0 network / 0 JS errors, 0 external refs, contract 1.18.0, 18 "
    "tabs); 3 gaps pre-registered (A1 WCAG AA keyboard+contrast pass, A2 "
    "per-section cryptographic digest in H1 panel, A3 one-page printable "
    "model-card cover)"
)

STANDARD_REFERENCES = [
    "WCAG 2.1 AA: 1.4.3 contrast (minimum), 1.4.11 non-text contrast, "
    "2.1.1 keyboard, 2.4.3 focus order, 2.4.7 focus visible (A1 reference)",
    "SOA ASOP 41 (actuarial communications - clarity for the intended user; "
    "model-card cover, A3 reference)",
    "SOA ASOP 56 sections 3.1.3, 3.4, 3.6 (model risk, reliance, "
    "documentation; evidence integrity, A2 reference)",
    "IFoA Model Practice Note (MPN) section 4 (documentation and communication)",
    "NIST FIPS 180-4 SHA-256 (per-section digest algorithm, A2 reference)",
]

AFFECTED_COMPONENTS = [
    "par_model_v2/viewer/ui_accessibility_integrity.py",
    "tests/test_phase35_task1_design_note.py",
    "scripts/build_phase35_task1_design_note.py",
    "docs/validation/PHASE35_TASK1_DESIGN_NOTE.{json,md}",
    "docs/UI_ACCESSIBILITY_INTEGRITY_DESIGN_CARD.md",
]


def _md(note: dict, gate: dict) -> str:
    md, base = note["metadata"], note["baseline_audit"]
    lines = [
        "# Offline UI Accessibility & Evidence-Integrity - Design Note (Phase 35 Task 1)",
        "",
        f"**Doc** `{md['doc_id']}` v{md['doc_version']} | {md['phase']} | "
        f"classification {md['classification']} | model parameter changes: "
        f"{'NONE' if md['no_model_parameter_changes'] else 'YES'} | "
        f"gate: **{'PASS' if gate['ok'] else 'FAIL'}** ({gate['n_checks']} checks)",
        "",
        "## Standing directive",
        "",
        md["directive"],
        "",
        "## (a) Baseline audit (measured, frozen as cross-check targets)",
        "",
        f"- measured at {base['measured_at_utc']}",
    ]
    for k in ("ui_app_self_test", "offline_viewer_self_test",
              "combined_gui_self_test", "ui_app_userrun_fallback_test",
              "ui_app_distribution_fallback_test", "ui_app_integrity_fallback_test",
              "ui_app_search_deeplink_test", "ui_app_bundle_printall_test"):
        st = base[k]
        lines.append(
            f"- `{k}`: ok **{st['ok']}**, {st['n_checks']} checks, "
            f"{st['network_calls']} network calls, {st['js_errors']} JS errors")
    lines.extend([
        f"- self-test checks total: **{base['self_test_checks_total']}**",
        f"- external references across {len(base['artifacts'])} HTML artifacts: "
        f"**{base['external_refs_total']}**",
        f"- embedded ui_data contract: **{base['contract_version']}**",
        f"- tabs ({base['tab_count']}): " + ", ".join(base["tabs"]),
        "- artifacts: " + "; ".join(
            f"`{n}` {a['bytes']:,} bytes" for n, a in base["artifacts"].items()),
        f"- governance store: {base['governance_store']['change_records']} ChangeRecords, "
        f"{base['governance_store']['audit_entries']} audit entries, "
        f"{base['governance_store']['risk_register']} risk-register items",
        "",
        "## (b) Gap list vs the directive (priority order, ONE gap per cycle)",
        "",
    ])
    for g in note["gaps"]:
        lines.extend([
            f"### {g['gap_id']} (priority {g['priority']}) - {g['title']}",
            "",
            g["description"],
            "",
            f"- contract change: {g['contract_change']}",
            "",
            "**(c) Pre-registered acceptance criteria:**",
            "",
        ])
        lines.extend(f"- {c}" for c in g["acceptance_criteria"])
        lines.append("")
    ep = note["execution_plan"]
    lines.extend([
        "## Execution plan",
        "",
        f"- {ep['ordering']}",
        f"- completion: {ep['completion']}",
        f"- governance: {ep['governance']}",
        "",
        "## Task 1 gate",
        "",
        f"- ok: **{gate['ok']}** ({gate['n_checks']} checks)",
    ])
    lines.extend(f"- {k}: {v}" for k, v in gate["checks"].items())
    lines.extend(["", "*Generated by scripts/build_phase35_task1_design_note.py.*", ""])
    return "\n".join(lines)


def _card(note: dict, gate: dict) -> str:
    base = note["baseline_audit"]
    return "\n".join([
        "# UI Accessibility & Evidence-Integrity Design Card (Phase 35)",
        "",
        f"- Design note: `{DOC_ID}` v{DOC_VERSION} - gate "
        f"{'PASS' if gate['ok'] else 'FAIL'} ({gate['n_checks']} checks)",
        f"- Baseline: 8 offline self-tests green ({base['ui_app_self_test']['n_checks']}"
        f"/{base['offline_viewer_self_test']['n_checks']}"
        f"/{base['combined_gui_self_test']['n_checks']}"
        f"/{base['ui_app_userrun_fallback_test']['n_checks']}"
        f"/{base['ui_app_distribution_fallback_test']['n_checks']}"
        f"/{base['ui_app_integrity_fallback_test']['n_checks']}"
        f"/{base['ui_app_search_deeplink_test']['n_checks']}"
        f"/{base['ui_app_bundle_printall_test']['n_checks']} = "
        f"{base['self_test_checks_total']} checks), 0 network, 0 JS errors, 0 "
        f"external refs, contract {base['contract_version']}, "
        f"{base['tab_count']} tabs",
        "- Gaps (one per cycle): A1 formal WCAG 2.1 AA keyboard + contrast "
        "conformance pass (ADDITIVE a11y_audit, CSS focus + build-time "
        "contrast table); A2 per-section cryptographic digest in the H1 "
        "integrity panel (ADDITIVE manifest section_digests; in-browser "
        "SHA-256 verify, no network); A3 one-page printable model-card cover "
        "(presentation only, bit-for-bit, blank decision)",
        "- Constraints: additive-only contract changes; zero-install "
        "preserved; display layer never recomputes (a hash is not a model "
        "figure); NO model parameter changes; Phase 30 binding stop-rule "
        "stands; MR-016/MR-017 owner decision pending and not pre-empted",
        "- Detail: `docs/validation/PHASE35_TASK1_DESIGN_NOTE.{json,md}`",
        "",
    ])


def apply_governance(store: GovernanceStore, note: dict, gate: dict) -> dict:
    actor = "Phase35Task1AccessibilityIntegrityDesign"
    phase = "Phase 35: Offline UI Accessibility & Evidence-Integrity Deepening"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    base = note["baseline_audit"]
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Pre-registered the Phase 35 offline-UI accessibility & "
            "evidence-integrity deepening pass per the standing scheduled-task "
            "directive. (a) Baseline audit measured and frozen: ui_app (340 "
            "checks) / offline_viewer (11) / combined_gui (27) / "
            "userrun-fallback (9) / distribution-fallback (9) / "
            "integrity-fallback (10) / search-deeplink (18) / bundle-printall "
            "(21) self-tests all ok:true with 0 network calls and 0 JS errors "
            "(445 checks total); 0 external references across the three HTML "
            "artifacts; embedded contract 1.18.0 (23 top-level keys); 18 "
            "tabs; governance store 92/120/17. (b) Three gaps pre-registered "
            "in priority order, one per cycle: A1 formal WCAG 2.1 AA keyboard "
            "+ contrast conformance pass (ADDITIVE a11y_audit key; CSS-only "
            ":focus-visible on every control + build-time measured contrast "
            "table for both themes); A2 per-section cryptographic digest in "
            "the H1 integrity panel (ADDITIVE manifest section_digests + "
            "root_digest; in-browser SHA-256 recompute with no network / no "
            "storage API; tamper-evident per-section table); A3 one-page "
            "printable model-card cover (presentation only; bit-for-bit from "
            "the embedded snapshot; decision field BLANK; provenance-stamped). "
            "(c) Acceptance criteria pre-registered per gap + common criteria "
            "(eight self-tests green, additive-only, zero-install, no "
            "recomputation in display layer - a hash over the embedded bytes "
            "is not a model figure). Gate PASS with LIVE repo cross-checks. "
            "NO model parameter changes; binding stop-rule honoured; owner "
            "decision not pre-empted."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "design_note_exists": False,
            "ui_contract": base["contract_version"],
            "phase34": "COMPLETE (H1-H4 closed; contract 1.18.0; 18 tabs)",
        },
        after_snapshot={
            "design_note_exists": True,
            "doc_id": DOC_ID,
            "doc_version": DOC_VERSION,
            "gate_ok": gate["ok"],
            "gate_checks": gate["n_checks"],
            "gaps_preregistered": [g["gap_id"] for g in note["gaps"]],
            "ui_contract": base["contract_version"],
            "ui_contract_bump": False,
        },
        impact_assessment=(
            "Governance only. No artifact, contract, or model change this "
            "cycle; the note binds Tasks 2-5 to additive-only, zero-install, "
            "display-only changes with pre-registered acceptance criteria. "
            "The governed frozen-t headline is untouched."
        ),
        author=actor,
        phase=phase,
        quantitative_impact=(
            "None (design note). Baseline frozen: contract 1.18.0; 18 tabs; "
            "self-test checks 340/11/27/9/9/10/18/21 = 445; external refs 0. "
            "No governed capital figure changed."
        ),
    )
    rec.submit_for_peer_review(
        actor=actor,
        comments="Design note: gate PASS incl. live repo cross-checks; tests added.")
    rec.submit_to_owner(
        actor=actor,
        comments=(
            "Owner review: accessibility / evidence-integrity scope and gap "
            "priority (A1 WCAG AA pass first). No model or contract change "
            "until Task 2."
        ),
    )
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor,
        phase=phase,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 35 Task 1 accessibility/integrity design note",
        details={"record_id": rec.record_id, "change_type": "governance_change",
                 "status": rec.status.value, "affected_components": AFFECTED_COMPONENTS},
    ))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main(use_governance: bool = False) -> dict:
    note = design_note()
    gate = validate_design_note(note, repo_root=".")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump({"design_note": note, "task1_gate": gate}, fh, indent=1, default=float)
    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_md(note, gate))
    with open(CARD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_card(note, gate))
    out = {"verdict": "PASS" if gate["ok"] else "FAIL", "gate_ok": gate["ok"],
           "n_checks": gate["n_checks"],
           "failed": [k for k, v in gate["checks"].items() if not v],
           "json": JSON_PATH, "md": MD_PATH, "card": CARD_PATH}
    if use_governance and gate["ok"]:
        store = GovernanceStore.from_json(open(GOV_PATH).read())
        gov = apply_governance(store, note, gate)
        if gov.get("added"):
            with open(GOV_PATH, "w", encoding="utf-8") as fh:
                fh.write(store.to_json())
        gov["audit_entries"] = len(store.audit_trail.all())
        gov["audit_integrity_ok"] = store.audit_trail.verify_all()
        gov["change_records_total"] = len(store.change_records)
        out["governance"] = gov
    return out


if __name__ == "__main__":
    print(json.dumps(main(use_governance="--governance" in sys.argv), indent=1, default=str))
