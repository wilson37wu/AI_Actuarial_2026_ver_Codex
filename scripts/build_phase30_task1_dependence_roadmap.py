"""Phase 30 Task 1 - post-vine dependence roadmap design-note builder.

DECISION (design-note-first discipline): OPTION A - tree-3 vine deepening
(one additional governed C-vine tree over the archived Phase 29 candidate),
with option D embedded as a pre-registered conditional STOP-RULE and option C
scheduled as the post-Phase-30 owner decision package regardless of outcome.
Option B (nested-aware calibration) is rejected this cycle on
leakage/circularity grounds.

Outputs:
  docs/validation/PHASE30_TASK1_DESIGN_NOTE.{json,md}
  docs/DEPENDENCE_ROADMAP_DECISION_CARD.md
  optional governance ChangeRecord (--governance)
"""

from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore
from par_model_v2.projection.dependence_roadmap import (
    MAX_VINE_TREES_P30,
    MR016_RISK_ID,
    MR017_RISK_ID,
    SELECTED_OPTION,
    THIRD_TREE_EDGES,
    UI_CONTRACT_FROM,
    UI_CONTRACT_TO,
    VINE2_BOOTSTRAP_CI95,
    VINE2_COMPONENT_SCR_BOOTSTRAP_MEAN,
    VINE2_COMPONENT_SCR_POINT,
    VINE2_COPULA_FORM_RESIDUAL_POINT,
    VINE2_OVERFIT_HOLDOUT_TO_FIT_RATIO,
    dependence_roadmap_option_study,
    dependence_roadmap_use_restrictions,
    mr016_closure_headroom,
    tree3_truncation_pre_study,
    validate_roadmap_envelope,
)
from par_model_v2.projection.vine_copula_upgrade import (
    BOOTSTRAP_N_SIM_GATE,
    BOOTSTRAP_REPLICATES_GATE,
    BOOTSTRAP_SE_GATE,
    DF_REMATCH_TOL,
    DRIVER_NAMES,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    PAIR_FAMILY_CANDIDATES,
    RANK_INVARIANCE_DF,
    REAGG_MATERIALITY_DISCLOSURE_THRESHOLD,
    RHO_FROZEN_TOL,
    VINE_BOUNDARY_RECOVERY_TOL,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE30_TASK1_DESIGN_NOTE.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE30_TASK1_DESIGN_NOTE.md")
CARD_PATH = os.path.join("docs", "DEPENDENCE_ROADMAP_DECISION_CARD.md")

CHANGE_TITLE = (
    "Phase 30 Task 1 - design note: post-vine dependence roadmap decision "
    "(option A tree-3 vine deepening selected; stop-rule pre-registered)"
)

STANDARD_REFERENCES = [
    "Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence",
    "Bedford & Cooke (2002), Vines - a new graphical model for dependent random variables",
    "Solvency II Delegated Regulation Article 234 (aggregation including tail behaviour)",
    "Solvency II Delegated Regulation Article 124 (validation standards: independence of validation data)",
    "SOA ASOP 56 sections 3.1.3, 3.4, 3.5",
    "SOA ASOP 25 section 3.3",
    "IA TAS M sections 3.2, 3.6, 3.7",
    "McNeil, Frey & Embrechts (2015), Quantitative Risk Management ch. 7",
]

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/dependence_roadmap.py (NEW, tested helper module)",
    "tests/test_phase30_task1_dependence_roadmap.py",
    "scripts/build_phase30_task1_dependence_roadmap.py",
    "docs/validation/PHASE30_TASK1_DESIGN_NOTE.{json,md}",
    "docs/DEPENDENCE_ROADMAP_DECISION_CARD.md",
]


def build_design_note(fast: bool = False) -> dict:
    pre = tree3_truncation_pre_study(seed=30, n_scen=40_000 if fast else 200_000)
    study = dependence_roadmap_option_study(pre)
    envelope = validate_roadmap_envelope()
    head = study["headroom"]
    note = {
        "title": "Phase 30 Task 1 - Design Note: Post-Vine Dependence Roadmap Decision",
        "verdict": "PASS" if (pre["mechanism_demonstrated"] and study["selection_ok"] and envelope["envelope_ok"]) else "FAIL",
        "classification": "EDUCATIONAL",
        "selected_option": study["selected_option"],
        "problem": (
            "Phase 29 closed with the first POSITIVE dependence result: the "
            "truncated 2-tree credit-root C-vine narrowed the copula-form "
            "residual to 3,637.3 (-65.33% vs grouped-t 10,491.5; -40.52% vs "
            "skew-t 6,114.9) and lifted the disclosed component SCR to "
            "42,458.6 (bootstrap mean 41,917.6), but the nested path-wise "
            "reference 46,638.9 stayed OUTSIDE the 95% CI [38,654.7, 45,284.3]. "
            "MR-016 remains OPEN and MR-017 tracks the residual vine-FORM "
            "limitations - by construction, dependence the 2-tree truncation "
            "cannot represent. The roadmap decision is which escalation, if "
            "any, is justified next."
        ),
        "headroom_analysis": head,
        "option_study": study["options"],
        "decision_rule": study["decision_rule"],
        "stop_rule": study["stop_rule"],
        "pre_registered_structure": {
            "max_vine_trees": MAX_VINE_TREES_P30,
            "third_tree_edges": [
                [DRIVER_NAMES[a], DRIVER_NAMES[b], [DRIVER_NAMES[c] for c in cond]]
                for a, b, cond in THIRD_TREE_EDGES
            ],
            "third_tree_edges_idx": [[a, b, list(c)] for a, b, c in THIRD_TREE_EDGES],
            "family_candidates": list(PAIR_FAMILY_CANDIDATES),
            "envelope_checks": envelope,
        },
        "pre_study_tree3_truncation": pre,
        "pre_study_disclosure": (
            "The synthetic pre-study is not a calibration. It demonstrates that "
            "(i) joint-conditional (tree-3) tail dependence leaves a positive "
            "VaR99.5 gap against a 2-tree truncation, (ii) a single governed "
            "tree-3 strength fitted leakage-free on a fit half closes a "
            "quantified share of that gap on the holdout half, and (iii) zero "
            "tree-3 strength recovers the 2-tree leg exactly. Real-data "
            "magnitude is reserved for Tasks 2-4."
        ),
        "task2_acceptance_criteria": [
            f"Dual boundary: reproduce frozen-t component {FROZEN_T_COMPONENT_SCR_REFERENCE:,.6f} AND archived 2-tree vine candidate {VINE2_COMPONENT_SCR_POINT:,.6f} bit-identically before any tree-3 computation; boundary max deviation <= {VINE_BOUNDARY_RECOVERY_TOL:.0e}.",
            f"Rank invariance: Sigma max|diff| <= {RHO_FROZEN_TOL}; homogeneous df remains {RANK_INVARIANCE_DF} within {DF_REMATCH_TOL}; standalone margins bit-identical.",
            "Implement ONLY the four pre-registered third-tree conditional pairs; first/second-tree fits FROZEN from Phase 29 Task 2.",
            f"Pair-family search limited to {list(PAIR_FAMILY_CANDIDATES)}; no new families or rotations.",
            "Leakage control: tree-3 family/parameter selection on fit rows only; holdout diagnostics disclosed.",
            "Retain single-df t, grouped-t and 2-tree vine comparison variants on common random numbers.",
            "code_change ChangeRecord OWNER_REVIEW.",
        ],
        "task3_acceptance_criteria": [
            f"Tree-3 vine margin bootstrap: >= {BOOTSTRAP_REPLICATES_GATE} replicates x {BOOTSTRAP_N_SIM_GATE:,} sims; SE <= {BOOTSTRAP_SE_GATE:.0%} of mean.",
            f"HEADLINE: nested {NESTED_PATHWISE_SCR_REFERENCE:,.1f} inside the tree-3 vine 95% CI OR the stop-rule TRIGGERS (recorded in the report; no gate-shopping).",
            "Paired CRN deltas (tree-3 minus 2-tree vine; tree-3 minus frozen-t) with sign and CI.",
            "Seeds/config/digests recorded; idempotent re-run digest-identical.",
            "methodology_change ChangeRecord OWNER_REVIEW.",
        ],
        "task4_acceptance_criteria": [
            "Per-pair tail diagnostics including the four tree-3 conditional pairs; holdout pairs disclosed with CIs.",
            f"Overfit check: holdout-to-fit max-lift ratio disclosed (P29 reference {VINE2_OVERFIT_HOLDOUT_TO_FIT_RATIO:.3f}); concentration gate as P29 T4.",
            f"MR decision: mitigate {MR016_RISK_ID}/{MR017_RISK_ID} ONLY if nested is inside the CI AND the residual shrinks below {VINE2_COPULA_FORM_RESIDUAL_POINT:,.1f}; otherwise KEEP OPEN and APPLY THE STOP-RULE.",
            f"MR-010/MR-014 refresh only if the governed headline moves > {REAGG_MATERIALITY_DISCLOSURE_THRESHOLD:.0%} (it must not: headline stays frozen-t).",
            "governance_change ChangeRecord OWNER_REVIEW; risk-register update idempotent.",
        ],
        "task5_plan": (
            f"Offline-UI propagation only after Tasks 2-4: additive contract "
            f"{UI_CONTRACT_FROM} -> {UI_CONTRACT_TO} with tree-3 vs 2-tree vs "
            "frozen vs nested SCR, tree-3 pair diagnostics, stop-rule status, "
            "and MR-016/MR-017 decisions."
        ),
        "post_phase30_commitment": (
            "Phase 31 is the owner decision package (option C) REGARDLESS of "
            "outcome: adopt-the-disclosed-read-out vs accept-residual vs fund "
            "option B with a second independent nested run."
        ),
        "limitations": [
            "This cycle is design-only; no capital figure changes.",
            "The synthetic pre-study demonstrates mechanism and leakage-free closure on synthetic data, not real-data magnitude.",
            "A tree-3 C-vine may STILL not bring the nested reference inside the CI; the pre-registered stop-rule makes that outcome terminal for dependence-form escalation.",
            "Production sign-off remains blocked by credentialled data and independent APS X2 review.",
        ],
        "use_restrictions": dependence_roadmap_use_restrictions(),
        "standard_references": STANDARD_REFERENCES,
        "affected_components": AFFECTED_COMPONENTS,
    }
    return note


def _md(note: dict) -> str:
    pre = note["pre_study_tree3_truncation"]
    head = note["headroom_analysis"]
    lines = [
        f"# {note['title']}",
        "",
        f"**Verdict: {note['verdict']}** - selected option: **{note['selected_option']}**. EDUCATIONAL ONLY.",
        "",
        "## 1. Problem",
        "",
        note["problem"],
        "",
        "## 2. Headroom analysis (archived Phase 29 constants)",
        "",
        f"- Needed bootstrap-mean lift for nested to enter the CI: {head['needed_mean_lift_abs']:,.1f} ({head['needed_mean_lift_rel']:+.2%}) = {head['needed_share_of_point_residual']:.1%} of the point residual {VINE2_COPULA_FORM_RESIDUAL_POINT:,.1f}.",
        f"- Max addressable share of the total gap by ANY dependence option: {head['max_addressable_share_of_total_gap']:.1%} (relief-surface part {head['relief_surface_part_not_addressable']:,.1f} is NOT dependence-addressable).",
        "",
        "## 3. Option study",
        "",
    ]
    for oid, o in note["option_study"].items():
        lines.append(f"### {oid}")
        lines.append("")
        lines.append(f"- {o['what']}")
        lines.append(f"- Expected residual closure (max abs): {o['expected_residual_closure_abs_max']:,.1f}; cost: {o.get('cost_cycles', 'n/a')} cycle(s); governance risk: {o['governance_risk']}.")
        if not o["eligible"]:
            lines.append(f"- NOT selected: {o['ineligible_reason']}")
        lines.append("")
    lines.extend([
        "## 4. Decision rule (pre-registered)", "",
    ])
    lines.extend(f"- {r}" for r in note["decision_rule"])
    lines.extend(["", f"**Stop-rule:** {note['stop_rule']}", "",
                  f"**Post-Phase-30 commitment:** {note['post_phase30_commitment']}", "",
                  "## 5. Pre-registered tree-3 structure", ""])
    for e in note["pre_registered_structure"]["third_tree_edges"]:
        lines.append(f"- {e[0]}-{e[1]} | {', '.join(e[2])}")
    lines.extend([
        f"- Families: {note['pre_registered_structure']['family_candidates']}; max trees: {note['pre_registered_structure']['max_vine_trees']}",
        f"- Envelope checks: {json.dumps(note['pre_registered_structure']['envelope_checks'], default=float)}",
        "",
        "## 6. Synthetic tree-3 truncation pre-study",
        "",
        f"- n_scen={pre['config']['n_scen']:,}; seed={pre['config']['seed']}; tree3_strength(truth)={pre['config']['tree3_strength']}",
        f"- Holdout VaR99.5: truth {pre['var995_holdout']['truth_tree3']:.2f}; 2-tree truncated {pre['var995_holdout']['vine2_truncated']:.2f}; tree-3 fitted {pre['var995_holdout']['tree3_fitted']:.2f}",
        f"- Truncation gap {pre['truncation_gap_rel']:+.2%}; leakage-free holdout closure share {pre['holdout_closure_share']:.1%} (fitted s3={pre['fitted_tree3_strength']})",
        f"- Joint triple-tail lift {pre['joint_triple_tail']['lift']:+.3f} vs holdout pair drift {pre['holdout_pair_drift']:.4f}",
        f"- 2-tree boundary exact recovery: {pre['boundary_recovery_max_abs']:.1e}; digest {pre['digest']}",
        "",
        note["pre_study_disclosure"],
        "",
        "## 7. Acceptance criteria (fixed before implementation)",
        "",
        "**Task 2:**", "",
    ])
    lines.extend(f"- {c}" for c in note["task2_acceptance_criteria"])
    lines.extend(["", "**Task 3:**", ""])
    lines.extend(f"- {c}" for c in note["task3_acceptance_criteria"])
    lines.extend(["", "**Task 4:**", ""])
    lines.extend(f"- {c}" for c in note["task4_acceptance_criteria"])
    lines.extend(["", f"**Task 5 plan:** {note['task5_plan']}", "", "## 8. Limitations", ""])
    lines.extend(f"- {l}" for l in note["limitations"])
    lines.extend(["", "## 9. Standards", ""])
    lines.extend(f"- {s}" for s in note["standard_references"])
    lines.extend(["", "*Generated by scripts/build_phase30_task1_dependence_roadmap.py.*", ""])
    return "\n".join(lines)


def _card(note: dict) -> str:
    pre = note["pre_study_tree3_truncation"]
    head = note["headroom_analysis"]
    return "\n".join([
        "# Post-Vine Dependence Roadmap - Decision Card (Phase 30)",
        "",
        f"**Verdict: {note['verdict']}** - selected: **{note['selected_option']}**. EDUCATIONAL ONLY.",
        "",
        "## Decision",
        "",
        "Phase 30 implements ONE final governed dependence escalation: a third",
        "C-vine tree (four pre-registered conditional pairs) over the FROZEN",
        "Phase 29 2-tree fit, same four pair families, dual boundary recovery",
        f"(frozen-t {FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f} and 2-tree vine {VINE2_COMPONENT_SCR_POINT:,.1f}).",
        "",
        "## Why",
        "",
        f"- Vine narrowed the residual to {VINE2_COPULA_FORM_RESIDUAL_POINT:,.1f} but nested {NESTED_PATHWISE_SCR_REFERENCE:,.1f} sits outside CI {list(VINE2_BOOTSTRAP_CI95)}.",
        f"- Entering the CI needs only {head['needed_mean_lift_abs']:,.1f} (+{head['needed_mean_lift_rel']:.2%}) on the bootstrap mean = {head['needed_share_of_point_residual']:.1%} of the remaining residual.",
        f"- Synthetic pre-study: leakage-free holdout closure {pre['holdout_closure_share']:.1%}; boundary recovery {pre['boundary_recovery_max_abs']:.1e}; digest {pre['digest'][:12]}.",
        "- Option B (nested-aware calibration) rejected: circular without a second nested run. Options C/D embedded: owner package follows Phase 30 regardless; stop-rule pre-registered.",
        "",
        "## Stop-rule",
        "",
        note["stop_rule"],
        "",
        "*Generated by scripts/build_phase30_task1_dependence_roadmap.py.*",
        "",
    ])


def apply_governance(store: GovernanceStore, note: dict) -> dict:
    actor = "Phase30Task1RoadmapDecision"
    phase = "Phase 30: Post-Vine Dependence Roadmap Decision"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    pre = note["pre_study_tree3_truncation"]
    head = note["headroom_analysis"]
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Design note deciding the post-vine dependence roadmap: option A "
            "(tree-3 vine deepening) selected under a pre-registered decision "
            "rule; option B rejected for circularity; option C scheduled as the "
            "post-Phase-30 owner package; option D embedded as a binding "
            "conditional stop-rule. No capital output changed this cycle."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "mr016": "OPEN (narrowing disclosed); MR-017 OPEN (vine-form limitations)",
            "next_task": "Phase 30 Task 1 roadmap decision",
        },
        after_snapshot={
            "selected_option": note["selected_option"],
            "third_tree_edges": note["pre_registered_structure"]["third_tree_edges_idx"],
            "stop_rule_registered": True,
            "holdout_closure_share": pre["holdout_closure_share"],
            "needed_mean_lift_abs": head["needed_mean_lift_abs"],
            "verdict": note["verdict"],
        },
        impact_assessment=(
            "Design and governance only. Fixes the Phase 30 envelope, dual "
            "boundary contract, gates and the binding stop-rule before any "
            "implementation; the governed frozen-t headline is unchanged."
        ),
        author=actor,
        phase=phase,
        quantitative_impact=(
            f"Headroom: needed mean lift {head['needed_mean_lift_abs']:,.1f} "
            f"({head['needed_mean_lift_rel']:+.2%}); synthetic holdout closure "
            f"{pre['holdout_closure_share']:.1%}; boundary recovery "
            f"{pre['boundary_recovery_max_abs']:.1e}. No governed capital figures changed."
        ),
    )
    rec.submit_for_peer_review(actor=actor, comments="Option study + decision rule + stop-rule pre-registered; helper tests added.")
    rec.submit_to_owner(actor=actor, comments="Owner review: educational design only; implementation deferred to Task 2.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor,
        phase=phase,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 30 Task 1 post-vine dependence roadmap decision",
        details={"record_id": rec.record_id, "change_type": "governance_change", "status": rec.status.value, "affected_components": AFFECTED_COMPONENTS},
    ))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main(use_governance: bool = False, fast: bool = False) -> dict:
    note = build_design_note(fast=fast)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(note, fh, indent=1, default=float)
    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_md(note))
    with open(CARD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_card(note))
    out = {"verdict": note["verdict"], "selected_option": note["selected_option"],
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
    res = main(use_governance="--governance" in sys.argv, fast="--fast" in sys.argv)
    print(json.dumps(res, indent=1, default=str))
