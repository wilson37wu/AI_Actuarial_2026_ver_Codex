"""Phase 31 Task 1 - owner decision package (dependence) DESIGN NOTE builder.

Pure governance (design-note-first discipline): pre-registers the evidence
pack contents, the THREE owner options with fixed acceptance criteria, and
the sign-off workflow per IFoA MPN s4 / ASOP 56 - BEFORE the pack is
assembled (Task 2).  NO model parameter changes; NO new copula-structure
candidates (Phase 30 binding stop-rule).

Outputs:
  docs/validation/PHASE31_TASK1_DESIGN_NOTE.{json,md}
  docs/OWNER_DECISION_PACKAGE_CARD.md
  optional governance ChangeRecord (--governance), change_type
  governance_change, left in OWNER_REVIEW.
"""

from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore
from par_model_v2.governance.owner_decision_package import (
    ESCALATION_OPTION_ID,
    NO_MODEL_PARAMETER_CHANGES,
    OWNER_OPTION_IDS,
    STOP_RULE_RECORD,
    evidence_pack_registry,
    owner_options,
    signoff_workflow,
    validate_owner_package,
)
from par_model_v2.projection.vine_copula_upgrade import (
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE31_TASK1_DESIGN_NOTE.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE31_TASK1_DESIGN_NOTE.md")
CARD_PATH = os.path.join("docs", "OWNER_DECISION_PACKAGE_CARD.md")

CHANGE_TITLE = (
    "Phase 31 Task 1 - design note: owner decision package (dependence) "
    "pre-registration (evidence pack, three options, sign-off workflow)"
)

STANDARD_REFERENCES = [
    "IFoA Model Practice Note (MPN) section 4 (documentation, independent review, communication)",
    "SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation of decisions)",
    "SOA ASOP 41 (actuarial communications)",
    "Solvency II Delegated Regulation Article 124 (validation standards)",
    "Solvency II Delegated Regulation Article 234 (aggregation including tail behaviour)",
]

AFFECTED_COMPONENTS = [
    "par_model_v2/governance/owner_decision_package.py (NEW, tested helper module)",
    "tests/test_phase31_task1_owner_decision_package.py",
    "scripts/build_phase31_task1_owner_decision_design_note.py",
    "docs/validation/PHASE31_TASK1_DESIGN_NOTE.{json,md}",
    "docs/OWNER_DECISION_PACKAGE_CARD.md",
]


def build_design_note() -> dict:
    pack = evidence_pack_registry()
    options = owner_options()
    workflow = signoff_workflow()
    gate = validate_owner_package(pack, options, workflow)
    return {
        "title": "Phase 31 Task 1 - Design Note: Owner Decision Package (Dependence)",
        "verdict": "PASS" if gate["ok"] else "FAIL",
        "classification": "EDUCATIONAL",
        "change_type": "governance_change",
        "no_model_parameter_changes": NO_MODEL_PARAMETER_CHANGES,
        "context": (
            "Phase 30 applied the BINDING STOP-RULE: the tree-3 vine candidate "
            "fitted zero third-tree strength (bit-identical to the 2-tree "
            "vine) and the nested path-wise reference "
            f"{NESTED_PATHWISE_SCR_REFERENCE:,.1f} stayed outside the 95% "
            "bootstrap CI, so dependence-FORM escalation under MR-016 ENDS. "
            "Phase 31 is pre-registered roadmap option C: hand the owner a "
            "complete, neutral decision package. This note FREEZES the pack "
            "contents, the three options with acceptance criteria, and the "
            "sign-off workflow before the pack is assembled (Task 2)."
        ),
        "evidence_pack_registry": pack,
        "owner_options": options,
        "escalation_option_id": ESCALATION_OPTION_ID,
        "stop_rule_record": dict(STOP_RULE_RECORD),
        "signoff_workflow": workflow,
        "validation_gate": gate,
        "task2_acceptance_criteria": [
            "assembled pack reproduces every registered figure bit-for-bit "
            "(validate_owner_package ok:true re-run against the assembled pack)",
            "pack presents all three options NEUTRALLY - no recommendation, "
            "no default option",
            "pack is self-contained: a technically competent third party can "
            "follow it without repo access (IFoA MPN s4)",
            "governance ChangeRecord (governance_change) OWNER_REVIEW; "
            "audit integrity verify_all true",
        ],
        "task3_plan": (
            "Owner-facing summary; offline-UI propagation ONLY IF a new "
            "disclosure surface is added (additive contract bump). After "
            "Phase 31 the standing directive applies: focus shifts to the "
            "zero-install offline user interface."
        ),
        "limitations": [
            "the nested reference is a SINGLE run; its sampling error is "
            "unquantified (motivates option O3)",
            "acceptance criteria constrain but cannot bind the owner; the "
            "owner may request variations, which would re-open this note "
            "via a new ChangeRecord",
            "the residual ladder compares copula FORMS on a fixed margin/"
            "calibration basis; margin-side model risk is tracked separately",
        ],
        "standard_references": STANDARD_REFERENCES,
    }


def _md(note: dict) -> str:
    pack = note["evidence_pack_registry"]
    gh = pack["governed_headline"]
    v2 = pack["disclosed_candidates"]["vine2"]
    t3 = pack["disclosed_candidates"]["tree3"]
    nr = pack["nested_reference"]
    lines = [
        f"# {note['title']}",
        "",
        f"**Verdict: {note['verdict']}** | classification {note['classification']} | "
        f"change type `{note['change_type']}` | model parameter changes: "
        f"{'NONE' if note['no_model_parameter_changes'] else 'YES'}",
        "",
        "## 1. Context",
        "",
        note["context"],
        "",
        "## 2. Pre-registered evidence pack contents",
        "",
        f"- Governed headline (frozen single-df t): **{gh['value']:,.6f}** "
        f"(df {gh['rank_invariance_df']}; move through P27-P30: {gh['move_pct_through_p27_p30']:.4%})",
        f"- Disclosed 2-tree vine: point {v2['component_scr_point']:,.4f}; "
        f"bootstrap mean {v2['bootstrap_mean']:,.1f}; CI95 "
        f"[{v2['bootstrap_ci95'][0]:,.1f}, {v2['bootstrap_ci95'][1]:,.1f}] - NOT adopted",
        f"- Tree-3 candidate: BIT-IDENTICAL point {t3['component_scr_point']:,.4f}; "
        f"bootstrap mean {t3['bootstrap_mean']:,.1f}; CI95 "
        f"[{t3['bootstrap_ci95'][0]:,.1f}, {t3['bootstrap_ci95'][1]:,.1f}] - NOT adopted",
        f"- Nested reference: {nr['value']:,.1f} (inside vine2 CI: "
        f"{nr['inside_vine2_ci95']}; inside tree-3 CI: {nr['inside_tree3_ci95']}). "
        f"{nr['single_run_caveat']}.",
        "- Residual ladder (copula-form residual, abs):",
        "",
    ]
    for r in pack["residual_ladder"]:
        lines.append(f"  - {r['form']}: {r['copula_form_residual_abs']:,.1f}")
    lines.extend([
        "",
        f"- Gap decomposition: total {pack['gap_decomposition']['total_gap_point']:,.1f}; "
        f"copula-form part {pack['gap_decomposition']['copula_form_part']:,.1f}",
        f"- Risk register: MR-016 {pack['risk_register_status']['MR-016']}; "
        f"MR-017 {pack['risk_register_status']['MR-017']}",
        f"- Stop-rule record: {json.dumps(note['stop_rule_record'])}",
        "- Escalation history:",
        "",
    ])
    for e in pack["escalation_history"]:
        lines.append(f"  - {e['phase']} ({e['form']}): residual "
                     f"{e['copula_form_residual_abs']:,.1f} - {e['outcome']}")
    lines.extend(["", "## 3. The three owner options (pre-registered)", ""])
    for oid in OWNER_OPTION_IDS:
        o = note["owner_options"][oid]
        lines.extend([
            f"### {oid}",
            "",
            f"- {o['what']}",
            f"- Capital effect (abs): {o['capital_effect_abs']:,.1f}; governance risk: "
            f"{o['governance_risk']}; escalation path open: {o['escalation_path_open']}",
            "- Acceptance criteria:",
            "",
        ])
        lines.extend(f"  - {c}" for c in o["acceptance_criteria"])
        lines.append("")
    lines.extend(["## 4. Sign-off workflow (IFoA MPN s4 / ASOP 56)", ""])
    for s in note["signoff_workflow"]:
        lines.append(f"{s['step']}. **{s['actor']}** - {s['action']} "
                     f"[{'; '.join(s['standards'])}]")
    lines.extend(["", "## 5. Validation gate", "",
                  f"- ok: **{note['validation_gate']['ok']}** "
                  f"({note['validation_gate']['n_checks']} checks)"])
    lines.extend(f"- {k}: {v}" for k, v in note["validation_gate"]["checks"].items())
    lines.extend(["", "## 6. Task 2 acceptance criteria (frozen now)", ""])
    lines.extend(f"- {c}" for c in note["task2_acceptance_criteria"])
    lines.extend(["", f"**Task 3 plan:** {note['task3_plan']}", "",
                  "## 7. Limitations", ""])
    lines.extend(f"- {l}" for l in note["limitations"])
    lines.extend(["", "## 8. Standards", ""])
    lines.extend(f"- {s}" for s in note["standard_references"])
    lines.extend(["", "*Generated by scripts/build_phase31_task1_owner_decision_design_note.py.*", ""])
    return "\n".join(lines)


def _card(note: dict) -> str:
    pack = note["evidence_pack_registry"]
    return "\n".join([
        "# Owner Decision Package (Dependence) - Card (Phase 31)",
        "",
        f"**Verdict: {note['verdict']}** - pure governance; NO parameter changes. EDUCATIONAL ONLY.",
        "",
        "## What the owner decides",
        "",
        f"Governed headline stays **{FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f}** unless the owner says otherwise.",
        f"Disclosed vine read-out {pack['disclosed_candidates']['vine2']['component_scr_point']:,.1f}; "
        f"nested reference {NESTED_PATHWISE_SCR_REFERENCE:,.1f}; "
        f"quantified residual {pack['gap_decomposition']['copula_form_part']:,.1f}.",
        "",
        "Three pre-registered options:",
        "",
        "1. **O1 adopt** the disclosed vine read-out (owner sign-off + MR-017 mitigation plan).",
        "2. **O2 accept** the residual (documented tolerance + monitoring trigger).",
        "3. **O3 fund** a second independent nested run (the ONLY escalation path left open).",
        "",
        "## Why now",
        "",
        "Phase 30 binding stop-rule APPLIED: dependence-FORM escalation under "
        "MR-016 ENDS; MR-016/MR-017 KEEP OPEN; candidates DISCLOSED, not adopted.",
        "",
        "*Generated by scripts/build_phase31_task1_owner_decision_design_note.py.*",
        "",
    ])


def apply_governance(store: GovernanceStore, note: dict) -> dict:
    actor = "Phase31Task1OwnerDecisionPackage"
    phase = "Phase 31: Owner Decision Package (Dependence)"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Design note pre-registering the Phase 31 owner decision package: "
            "evidence-pack contents (governed headline, disclosed vine/tree-3 "
            "read-outs with CIs, nested reference, residual ladder, MR-016/"
            "MR-017 + stop-rule record, P26->P30 escalation history), the "
            "three owner options with fixed acceptance criteria, and the "
            "sign-off workflow per IFoA MPN s4 / ASOP 56. No capital output "
            "changed; no new copula-structure candidates (binding stop-rule)."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "mr016": "OPEN (stop-rule applied; dependence-FORM escalation ended)",
            "mr017": "OPEN (vine-form limitations)",
            "next_task": "Phase 31 Task 1 owner decision package design note",
        },
        after_snapshot={
            "evidence_pack_registered": True,
            "owner_option_ids": list(OWNER_OPTION_IDS),
            "escalation_option_id": ESCALATION_OPTION_ID,
            "signoff_workflow_steps": len(note["signoff_workflow"]),
            "validation_gate_ok": note["validation_gate"]["ok"],
            "verdict": note["verdict"],
        },
        impact_assessment=(
            "Governance only. Freezes the owner decision package contents, "
            "options and acceptance criteria before assembly (Task 2); the "
            "governed frozen-t headline is unchanged and no model parameter "
            "moves."
        ),
        author=actor,
        phase=phase,
        quantitative_impact=(
            f"Registered figures: governed headline "
            f"{FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f}; disclosed vine point "
            f"{note['evidence_pack_registry']['disclosed_candidates']['vine2']['component_scr_point']:,.1f}; "
            f"nested {NESTED_PATHWISE_SCR_REFERENCE:,.1f}; residual "
            f"{note['evidence_pack_registry']['gap_decomposition']['copula_form_part']:,.1f}. "
            "No governed capital figures changed."
        ),
    )
    rec.submit_for_peer_review(
        actor=actor,
        comments="Pack registry + three options + workflow pre-registered; helper tests added.",
    )
    rec.submit_to_owner(
        actor=actor,
        comments="Owner review: pure governance pre-registration; pack assembly deferred to Task 2.",
    )
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor,
        phase=phase,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 31 Task 1 owner decision package design note",
        details={"record_id": rec.record_id, "change_type": "governance_change",
                 "status": rec.status.value, "affected_components": AFFECTED_COMPONENTS},
    ))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main(use_governance: bool = False) -> dict:
    note = build_design_note()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(note, fh, indent=1, default=float)
    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_md(note))
    with open(CARD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_card(note))
    out = {"verdict": note["verdict"], "gate_ok": note["validation_gate"]["ok"],
           "n_checks": note["validation_gate"]["n_checks"],
           "json": JSON_PATH, "md": MD_PATH, "card": CARD_PATH}
    if use_governance:
        store = GovernanceStore.from_json(open(GOV_PATH).read())
        gov = apply_governance(store, note)
        if gov.get("added"):
            with open(GOV_PATH, "w", encoding="utf-8") as fh:
                fh.write(store.to_json())
        gov["audit_entries"] = len(store.audit_trail.all())
        gov["audit_integrity_ok"] = store.audit_trail.verify_all()
        gov["change_records_total"] = len(store.change_records)
        out["governance"] = gov
    return out


if __name__ == "__main__":
    res = main(use_governance="--governance" in sys.argv)
    print(json.dumps(res, indent=1, default=str))
