"""Phase 34 Task 1 - offline UI usability-hardening design note builder.

Renders the pre-registered design note (measured baseline + prioritised gap
list + acceptance criteria, see par_model_v2.viewer.ui_usability_hardening),
runs the Task 1 gate (structural + LIVE repo cross-checks), and writes:

  docs/validation/PHASE34_TASK1_DESIGN_NOTE.{json,md}
  docs/UI_USABILITY_HARDENING_DESIGN_CARD.md

Pure governance_change (--governance), left in OWNER_REVIEW.
NO model parameter changes; the Phase 30 binding stop-rule stands; the
MR-016/MR-017 owner decision is not pre-empted.
"""

from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore
from par_model_v2.viewer.ui_usability_hardening import (
    DOC_ID,
    DOC_VERSION,
    design_note,
    validate_design_note,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE34_TASK1_DESIGN_NOTE.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE34_TASK1_DESIGN_NOTE.md")
CARD_PATH = os.path.join("docs", "UI_USABILITY_HARDENING_DESIGN_CARD.md")

CHANGE_TITLE = (
    "Phase 34 Task 1 - offline UI usability-hardening design note; baseline "
    "audit green (5 self-tests 297/11/27/9/9 checks, 0 network / 0 JS "
    "errors, 0 external refs, contract 1.17.0, 17 tabs); 4 gaps "
    "pre-registered (H1 contract guard + integrity panel, H2 global search "
    "+ deep-links, H3 full evidence bundle export, H4 responsive + "
    "high-contrast pass)"
)

STANDARD_REFERENCES = [
    "IFoA Model Practice Note (MPN) section 4 (documentation and communication)",
    "SOA ASOP 41 (actuarial communications - clarity for the intended user)",
    "SOA ASOP 56 sections 3.1.3, 3.4, 3.6 (model risk, reliance, documentation)",
    "WCAG 2.1 AA (responsive reflow 1.4.10, contrast 1.4.3/1.4.11, "
    "reduced motion 2.3.3 - H4 reference standard)",
]

AFFECTED_COMPONENTS = [
    "par_model_v2/viewer/ui_usability_hardening.py",
    "tests/test_phase34_task1_design_note.py",
    "scripts/build_phase34_task1_design_note.py",
    "docs/validation/PHASE34_TASK1_DESIGN_NOTE.{json,md}",
    "docs/UI_USABILITY_HARDENING_DESIGN_CARD.md",
]


def _md(note: dict, gate: dict) -> str:
    md, base = note["metadata"], note["baseline_audit"]
    lines = [
        "# Offline UI Usability Hardening - Design Note (Phase 34 Task 1)",
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
              "ui_app_distribution_fallback_test"):
        st = base[k]
        lines.append(
            f"- `{k}`: ok **{st['ok']}**, {st['n_checks']} checks, "
            f"{st['network_calls']} network calls, {st['js_errors']} JS errors")
    lines.extend([
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
    lines.extend(["", "*Generated by scripts/build_phase34_task1_design_note.py.*", ""])
    return "\n".join(lines)


def _card(note: dict, gate: dict) -> str:
    base = note["baseline_audit"]
    return "\n".join([
        "# UI Usability Hardening Design Card (Phase 34)",
        "",
        f"- Design note: `{DOC_ID}` v{DOC_VERSION} - gate "
        f"{'PASS' if gate['ok'] else 'FAIL'} ({gate['n_checks']} checks)",
        f"- Baseline: 5 offline self-tests green ({base['ui_app_self_test']['n_checks']}"
        f"/{base['offline_viewer_self_test']['n_checks']}"
        f"/{base['combined_gui_self_test']['n_checks']}"
        f"/{base['ui_app_userrun_fallback_test']['n_checks']}"
        f"/{base['ui_app_distribution_fallback_test']['n_checks']} checks), 0 network, "
        f"0 JS errors, 0 external refs, contract {base['contract_version']}, "
        f"{base['tab_count']} tabs",
        "- Gaps (one per cycle): H1 self-describing contract guard + in-UI "
        "integrity/schema panel (ADDITIVE manifest); H2 global cross-tab "
        "search + deep-linkable read-outs (display only, hash deep links); "
        "H3 one-click full evidence bundle export + print-all pack "
        "(presentation only, bit-for-bit); H4 responsive / small-screen + "
        "high-contrast usability pass (CSS/behaviour only, hash-persisted)",
        "- Constraints: additive-only contract changes; zero-install preserved; "
        "display layer never recomputes; NO model parameter changes; "
        "Phase 30 binding stop-rule stands; MR-016/MR-017 owner decision "
        "pending and not pre-empted",
        "- Detail: `docs/validation/PHASE34_TASK1_DESIGN_NOTE.{json,md}`",
        "",
    ])


def apply_governance(store: GovernanceStore, note: dict, gate: dict) -> dict:
    actor = "Phase34Task1UsabilityHardeningDesign"
    phase = "Phase 34: Offline UI Usability Hardening"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    base = note["baseline_audit"]
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Pre-registered the Phase 34 offline-UI usability-hardening pass "
            "per the standing scheduled-task directive. (a) Baseline audit "
            "measured and frozen: ui_app (297 checks) / offline_viewer (11) "
            "/ combined_gui (27) / userrun-fallback (9) / distribution-"
            "fallback (9) self-tests all ok:true with 0 network calls and 0 "
            "JS errors; 0 external references across the three HTML "
            "artifacts; embedded contract 1.17.0 (22 top-level keys); 17 "
            "tabs; governance store 90/118/17. (b) Four gaps pre-registered "
            "in priority order, one per cycle: H1 self-describing "
            "data-contract guard + in-UI schema/integrity panel (ADDITIVE "
            "build-time manifest; neutral degraded-mode banner instead of a "
            "silent partial render); H2 global cross-tab search + "
            "deep-linkable read-outs (display layer over already-rendered "
            "text; URL-hash deep links; no storage APIs); H3 one-click full "
            "evidence bundle export + print-all pack (every value bit-for-bit "
            "from the embedded snapshot; provenance-stamped; decision record "
            "BLANK); H4 responsive / small-screen + high-contrast usability "
            "pass (CSS/behaviour only; URL-hash persistence; no storage "
            "APIs). (c) Acceptance criteria pre-registered per gap + common "
            "criteria (self-tests green, additive-only, zero-install, no "
            "recomputation in display layer). Gate PASS with LIVE repo "
            "cross-checks. NO model parameter changes; binding stop-rule "
            "honoured; owner decision not pre-empted."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "design_note_exists": False,
            "ui_contract": base["contract_version"],
            "phase33": "COMPLETE (G1-G4 closed; contract 1.17.0; 17 tabs)",
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
            "None (design note). Baseline frozen: contract 1.17.0; 17 tabs; "
            "self-test checks 297/11/27/9/9; external refs 0. No governed "
            "capital figure changed."
        ),
    )
    rec.submit_for_peer_review(
        actor=actor,
        comments="Design note: gate PASS incl. live repo cross-checks; tests added.")
    rec.submit_to_owner(
        actor=actor,
        comments=(
            "Owner review: usability-hardening scope and gap priority (H1 "
            "contract guard first). No model or contract change until Task 2."
        ),
    )
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor,
        phase=phase,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 34 Task 1 usability-hardening design note",
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
