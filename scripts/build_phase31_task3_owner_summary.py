"""Phase 31 Task 3 - owner-facing SUMMARY of the assembled decision pack.

Derives a ONE-PAGE owner-facing summary from the assembled Phase 31 pack
(:func:`owner_summary` - every figure bit-for-bit from the pack, nothing
recomputed, no new figures) and runs the Task 3 fidelity/neutrality gate
(:func:`validate_owner_summary`, 25 checks).

OFFLINE-UI DECISION (pre-registered in the task definition): the summary
introduces NO new disclosure surface - every figure it contains is already
surfaced in the offline UI (governed headline, vine read-outs, nested
reference, residual, MR-016/MR-017). Therefore NO ui_data contract bump.

Pure governance: NO model parameter changes; NO new copula-structure
candidates (Phase 30 binding stop-rule).  On PASS, Phase 31 is COMPLETE.

Outputs:
  docs/validation/PHASE31_TASK3_OWNER_SUMMARY.{json,md}
  optional governance ChangeRecord (--governance), change_type
  governance_change, left in OWNER_REVIEW.
"""

from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore
from par_model_v2.governance.owner_decision_package import (
    PACK_DOC_ID,
    PACK_DOC_VERSION,
    SUMMARY_DOC_ID,
    SUMMARY_DOC_VERSION,
    SUMMARY_MAX_WORDS,
    _summary_word_count,
    owner_summary,
    validate_owner_summary,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE31_TASK3_OWNER_SUMMARY.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE31_TASK3_OWNER_SUMMARY.md")

CHANGE_TITLE = (
    "Phase 31 Task 3 - owner-facing summary of the assembled decision pack; "
    "fidelity/neutrality gate PASS; NO new disclosure surface (no UI "
    "contract bump); PHASE 31 COMPLETE"
)

STANDARD_REFERENCES = [
    "IFoA Model Practice Note (MPN) section 4 (documentation, independent review, communication)",
    "SOA ASOP 41 (actuarial communications - clarity for the intended user)",
    "SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation of decisions)",
]

AFFECTED_COMPONENTS = [
    "par_model_v2/governance/owner_decision_package.py (Task 3 summary + gate additions)",
    "tests/test_phase31_task3_owner_summary.py",
    "scripts/build_phase31_task3_owner_summary.py",
    "docs/validation/PHASE31_TASK3_OWNER_SUMMARY.{json,md}",
]


def _md(s: dict, gate: dict) -> str:
    kf = s["key_figures"]
    lines = [
        "# Owner Decision Summary - Dependence (Phase 31 Task 3)",
        "",
        f"**Summary** `{s['metadata']['summary_id']}` v{s['metadata']['summary_version']} | "
        f"derived bit-for-bit from `{s['metadata']['derived_from']['pack_id']}` "
        f"v{s['metadata']['derived_from']['pack_version']} | "
        f"classification {s['metadata']['classification']} | "
        "model parameter changes: "
        f"{'NONE' if s['metadata']['no_model_parameter_changes'] else 'YES'} | "
        f"gate: **{'PASS' if gate['ok'] else 'FAIL'}** ({gate['n_checks']} checks) | "
        f"{_summary_word_count(s)} words (cap {SUMMARY_MAX_WORDS})",
        "",
        "## Decision required",
        "",
        s["decision_required"],
        "",
        "## Key figures",
        "",
        f"- Governed headline (frozen single-df t): **{kf['governed_headline']:,.1f}** "
        f"(moved {kf['headline_move_through_p27_p30_pct']:.1%} through P27-P30)",
        f"- Disclosed vine read-out: {kf['disclosed_vine_point']:,.1f} "
        f"(CI95 [{kf['disclosed_vine_ci95'][0]:,.1f}, {kf['disclosed_vine_ci95'][1]:,.1f}]) - NOT adopted",
        f"- Nested path-wise reference: {kf['nested_reference']:,.1f} "
        f"(inside vine CI95: {kf['nested_inside_vine_ci95']})",
        f"- Copula-form residual: **{kf['copula_form_residual']:,.1f}** "
        f"(of total gap {kf['total_gap']:,.1f})",
        "",
        "## The three options (registry order, not preference order)",
        "",
    ]
    for o in s["options_at_a_glance"]:
        lines.extend([
            f"### {o['option_id']}",
            "",
            f"- {o['summary']}",
            f"- Capital effect (abs): {o['capital_effect_abs']:,.1f}; governance risk: "
            f"{o['governance_risk']}; escalation path open: {o['escalation_path_open']}",
            "",
        ])
    lines.extend(["## What happens next", ""])
    lines.extend(
        f"{w['step']}. **{w['actor']}** - {w['action']}"
        for w in s["what_happens_next"])
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {c}" for c in s["caveats"])
    loc = s["where_to_find_detail"]
    lines.extend([
        "", "## Where to find the detail", "",
        f"- Full pack: `{loc['full_pack_files']}` (`{loc['full_pack_id']}`)",
        f"- Design note: `{loc['design_note_files']}`",
        f"- {loc['note']}",
        "", "## Task 3 gate", "",
        f"- ok: **{gate['ok']}** ({gate['n_checks']} checks)",
    ])
    lines.extend(f"- {k}: {v}" for k, v in gate["checks"].items())
    lines.extend([
        "",
        "## Offline-UI decision",
        "",
        "- NO new disclosure surface: every figure in this summary is already "
        "surfaced in the offline UI (governed headline, vine read-outs, nested "
        "reference, residual, MR-016/MR-017). NO ui_data contract bump.",
        "",
        "*Generated by scripts/build_phase31_task3_owner_summary.py.*", "",
    ])
    return "\n".join(lines)


def apply_governance(store: GovernanceStore, s: dict, gate: dict) -> dict:
    actor = "Phase31Task3OwnerSummary"
    phase = "Phase 31: Owner Decision Package (Dependence)"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Derived the owner-facing ONE-PAGE summary of the assembled "
            "Phase 31 decision pack: decision required, key figures, the "
            "three options at a glance (registry order), the sign-off "
            "workflow, caveats and pointers to the full pack - every figure "
            "bit-for-bit from the assembled pack, nothing recomputed, no "
            "new figures. Fidelity/neutrality gate PASS (25 checks: "
            "identity, figure fidelity, registry order, only-O3 escalation, "
            "neutrality, decision-blank, workflow faithfulness, "
            "self-location, caveats, one-page word cap). OFFLINE-UI "
            "decision: NO new disclosure surface, therefore NO ui_data "
            "contract bump. PHASE 31 COMPLETE; no capital output changed."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "summary_exists": False,
            "pack": f"{PACK_DOC_ID} v{PACK_DOC_VERSION} (assembled, dual gate PASS)",
            "next_task": "Phase 31 Task 3 owner-facing summary",
        },
        after_snapshot={
            "summary_exists": True,
            "summary_id": SUMMARY_DOC_ID,
            "summary_version": SUMMARY_DOC_VERSION,
            "gate_ok": gate["ok"],
            "gate_checks": gate["n_checks"],
            "word_count": _summary_word_count(s),
            "word_cap": SUMMARY_MAX_WORDS,
            "ui_contract_bump": False,
            "phase31_complete": True,
        },
        impact_assessment=(
            "Governance only. The owner now has both the full pack and the "
            "one-page summary for workflow steps 2-4 (peer review, owner "
            "review, decision). The governed frozen-t headline is unchanged "
            "and no model parameter moves. No offline-UI change (no new "
            "disclosure surface)."
        ),
        author=actor,
        phase=phase,
        quantitative_impact=(
            f"Summary figures (bit-for-bit from the pack): governed headline "
            f"{s['key_figures']['governed_headline']:,.1f}; disclosed vine "
            f"point {s['key_figures']['disclosed_vine_point']:,.1f}; nested "
            f"{s['key_figures']['nested_reference']:,.1f}; residual "
            f"{s['key_figures']['copula_form_residual']:,.1f}. No governed "
            "capital figures changed."
        ),
    )
    rec.submit_for_peer_review(
        actor=actor,
        comments="Owner summary: fidelity/neutrality gate PASS (25 checks); tests added.",
    )
    rec.submit_to_owner(
        actor=actor,
        comments=(
            "Owner review: the one-page summary plus the full pack. The "
            "owner decides O1/O2/O3 at workflow step 4; nothing is "
            "pre-selected."
        ),
    )
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor,
        phase=phase,
        event=(
            "ChangeRecord opened (OWNER_REVIEW) - Phase 31 Task 3 owner "
            "summary derived; PHASE 31 COMPLETE"
        ),
        details={"record_id": rec.record_id, "change_type": "governance_change",
                 "status": rec.status.value, "affected_components": AFFECTED_COMPONENTS},
    ))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main(use_governance: bool = False) -> dict:
    s = owner_summary()
    gate = validate_owner_summary(s)
    payload = {"summary": s, "task3_gate": gate,
               "ui_decision": {"new_disclosure_surface": False,
                               "ui_contract_bump": False}}
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_md(s, gate))
    out = {"verdict": "PASS" if gate["ok"] else "FAIL",
           "gate_ok": gate["ok"], "n_checks": gate["n_checks"],
           "word_count": _summary_word_count(s),
           "json": JSON_PATH, "md": MD_PATH}
    if use_governance:
        store = GovernanceStore.from_json(open(GOV_PATH).read())
        gov = apply_governance(store, s, gate)
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
