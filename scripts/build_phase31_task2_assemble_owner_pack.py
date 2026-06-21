"""Phase 31 Task 2 - assemble the owner decision pack (dependence).

Assembles the pack EXACTLY per the Task 1 frozen registry
(``evidence_pack_registry`` / ``owner_options`` / ``signoff_workflow``),
wraps it in the self-containment material (purpose, reading guide, figure
provenance, glossary, blank decision record) and re-runs BOTH gates:

* the frozen Task 1 envelope gate (21 checks) against the ASSEMBLED pack,
* the Task 2 assembly gate (bit-for-bit reproduction, neutrality,
  self-containment; 16 checks).

Pure governance: NO model parameter changes; NO new copula-structure
candidates (Phase 30 binding stop-rule).

Outputs:
  docs/validation/PHASE31_TASK2_OWNER_DECISION_PACK.{json,md}
  optional governance ChangeRecord (--governance), change_type
  governance_change, left in OWNER_REVIEW.
"""

from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore
from par_model_v2.governance.owner_decision_package import (
    OWNER_OPTION_IDS,
    PACK_DOC_ID,
    PACK_DOC_VERSION,
    assemble_owner_pack,
    validate_assembled_pack,
)
from par_model_v2.projection.vine_copula_upgrade import (
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE31_TASK2_OWNER_DECISION_PACK.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE31_TASK2_OWNER_DECISION_PACK.md")

CHANGE_TITLE = (
    "Phase 31 Task 2 - assemble the owner decision pack (dependence) "
    "exactly per the Task 1 frozen registry; dual gate PASS"
)

STANDARD_REFERENCES = [
    "IFoA Model Practice Note (MPN) section 4 (documentation, independent review, communication)",
    "SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation of decisions)",
    "SOA ASOP 41 (actuarial communications)",
    "Solvency II Delegated Regulation Article 124 (validation standards)",
]

AFFECTED_COMPONENTS = [
    "par_model_v2/governance/owner_decision_package.py (Task 2 assembly + gate additions)",
    "tests/test_phase31_task2_owner_pack_assembly.py",
    "scripts/build_phase31_task2_assemble_owner_pack.py",
    "docs/validation/PHASE31_TASK2_OWNER_DECISION_PACK.{json,md}",
]


def _md(doc: dict, gate: dict) -> str:
    ev = doc["evidence_pack"]
    gh = ev["governed_headline"]
    v2 = ev["disclosed_candidates"]["vine2"]
    t3 = ev["disclosed_candidates"]["tree3"]
    nr = ev["nested_reference"]
    lines = [
        "# Owner Decision Pack - Dependence (Phase 31 Task 2)",
        "",
        f"**Pack** `{doc['metadata']['pack_id']}` v{doc['metadata']['pack_version']} | "
        f"classification {doc['metadata']['classification']} | "
        "model parameter changes: "
        f"{'NONE' if doc['metadata']['no_model_parameter_changes'] else 'YES'} | "
        f"assembly gate: **{'PASS' if gate['ok'] else 'FAIL'}** ({gate['n_checks']} checks)",
        "",
        "## 1. Purpose",
        "",
        doc["purpose"],
        "",
        "## 2. How to read this pack",
        "",
    ]
    lines.extend(f"- {h}" for h in doc["how_to_read"])
    lines.extend([
        "",
        "## 3. Evidence",
        "",
        f"- Governed headline (frozen single-df t): **{gh['value']:,.6f}** "
        f"(df {gh['rank_invariance_df']}; move through P27-P30: "
        f"{gh['move_pct_through_p27_p30']:.4%}) - {gh['status']}",
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
    ])
    lines.extend(
        f"  - {r['form']}: {r['copula_form_residual_abs']:,.1f}"
        for r in ev["residual_ladder"])
    lines.extend([
        "",
        f"- Gap decomposition: total {ev['gap_decomposition']['total_gap_point']:,.1f}; "
        f"copula-form part {ev['gap_decomposition']['copula_form_part']:,.1f}",
        f"- Risk register: MR-016 {ev['risk_register_status']['MR-016']}; "
        f"MR-017 {ev['risk_register_status']['MR-017']}",
        "- Escalation history:",
        "",
    ])
    lines.extend(
        f"  - {e['phase']} ({e['form']}): residual "
        f"{e['copula_form_residual_abs']:,.1f} - {e['outcome']}"
        for e in ev["escalation_history"])
    lines.extend(["", "## 4. Figure provenance (frozen archived constants)", ""])
    lines.extend(f"- **{k}**: {v}" for k, v in doc["figure_provenance"].items())
    lines.extend(["", "## 5. The three options (registry order, not preference order)", ""])
    for oid in doc["owner_option_order"]:
        o = doc["owner_options"][oid]
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
    lines.extend(["## 6. Sign-off workflow", ""])
    lines.extend(
        f"{s['step']}. **{s['actor']}** - {s['action']} [{'; '.join(s['standards'])}]"
        for s in doc["signoff_workflow"])
    lines.extend([
        "", "## 7. Decision record (blank - for the owner at step 4)", "",
        "```json", json.dumps(doc["decision_record_template"], indent=1), "```",
        "", "## 8. Glossary", "",
    ])
    lines.extend(f"- **{t}**: {d}" for t, d in doc["glossary"].items())
    lines.extend(["", "## 9. Limitations", ""])
    lines.extend(f"- {l}" for l in doc["limitations"])
    lines.extend(["", "## 10. Standards", ""])
    lines.extend(f"- {s}" for s in doc["standard_references"])
    lines.extend(["", "## 11. Assembly gate", "",
                  f"- ok: **{gate['ok']}** ({gate['n_checks']} checks)"])
    lines.extend(f"- {k}: {v}" for k, v in gate["checks"].items())
    lines.extend(["", "*Generated by scripts/build_phase31_task2_assemble_owner_pack.py.*", ""])
    return "\n".join(lines)


def apply_governance(store: GovernanceStore, doc: dict, gate: dict) -> dict:
    actor = "Phase31Task2OwnerPackAssembly"
    phase = "Phase 31: Owner Decision Package (Dependence)"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Assembled the Phase 31 owner decision pack exactly per the "
            "Task 1 frozen registry: evidence pack, three options and "
            "sign-off workflow reproduced bit-for-bit, wrapped with purpose, "
            "reading guide, figure provenance, glossary and a blank decision "
            "record for self-containment (IFoA MPN s4). Dual gate PASS: "
            "Task 1 envelope gate (21 checks) re-run on the assembled pack "
            "plus the Task 2 assembly gate (16 checks: reproduction, "
            "neutrality, self-containment). No capital output changed."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "pack_assembled": False,
            "registry_frozen": "Phase 31 Task 1 design note (21-gate PASS)",
            "next_task": "Phase 31 Task 2 assemble the owner decision pack",
        },
        after_snapshot={
            "pack_assembled": True,
            "pack_id": PACK_DOC_ID,
            "pack_version": PACK_DOC_VERSION,
            "assembly_gate_ok": gate["ok"],
            "assembly_gate_checks": gate["n_checks"],
            "owner_option_ids": list(OWNER_OPTION_IDS),
            "decision_recorded": False,
        },
        impact_assessment=(
            "Governance only. The pack is now ready for workflow step 2 "
            "(independent peer review) and step 3-4 (owner review and "
            "decision). The governed frozen-t headline is unchanged and no "
            "model parameter moves."
        ),
        author=actor,
        phase=phase,
        quantitative_impact=(
            f"Pack figures (assembled, bit-for-bit): governed headline "
            f"{FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f}; disclosed vine point "
            f"{doc['evidence_pack']['disclosed_candidates']['vine2']['component_scr_point']:,.1f}; "
            f"nested {NESTED_PATHWISE_SCR_REFERENCE:,.1f}; residual "
            f"{doc['evidence_pack']['gap_decomposition']['copula_form_part']:,.1f}. "
            "No governed capital figures changed."
        ),
    )
    rec.submit_for_peer_review(
        actor=actor,
        comments="Assembled pack: dual gate PASS (21 envelope + 16 assembly checks); tests added.",
    )
    rec.submit_to_owner(
        actor=actor,
        comments=(
            "Owner review: the assembled, neutral decision pack. The owner "
            "decides O1/O2/O3 at workflow step 4; nothing is pre-selected."
        ),
    )
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor,
        phase=phase,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 31 Task 2 owner decision pack assembled",
        details={"record_id": rec.record_id, "change_type": "governance_change",
                 "status": rec.status.value, "affected_components": AFFECTED_COMPONENTS},
    ))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main(use_governance: bool = False) -> dict:
    doc = assemble_owner_pack()
    gate = validate_assembled_pack(doc)
    payload = {"pack": doc, "assembly_gate": gate}
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_md(doc, gate))
    out = {"verdict": "PASS" if gate["ok"] else "FAIL",
           "gate_ok": gate["ok"], "n_checks": gate["n_checks"],
           "json": JSON_PATH, "md": MD_PATH}
    if use_governance:
        store = GovernanceStore.from_json(open(GOV_PATH).read())
        gov = apply_governance(store, doc, gate)
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
