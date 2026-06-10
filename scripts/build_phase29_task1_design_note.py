"""Phase 29 Task 1 - vine / pair-copula design-note builder.

Candidate CHOSEN (design-note-first discipline): a governance-limited truncated
C-vine / pair-copula prototype (Aas et al. 2009) with credit as the first-tree
root, frozen standalone margins, frozen Sigma / df boundary recovery, a capped
pair-family search envelope, leakage-free fit/holdout gates, and explicit
MR-016 remediation criteria.

Outputs:
  docs/validation/PHASE29_TASK1_DESIGN_NOTE.{json,md}
  docs/VINE_COPULA_DESIGN_CARD.md
  optional governance ChangeRecord (--governance)
"""

from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore
from par_model_v2.projection.vine_copula_upgrade import (
    BOOTSTRAP_N_SIM_GATE,
    BOOTSTRAP_REPLICATES_GATE,
    BOOTSTRAP_SE_GATE,
    DF_REMATCH_TOL,
    DRIVER_NAMES,
    EXISTING_RISK_ID,
    FIRST_TREE_EDGES,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_BOOTSTRAP_CI95,
    GROUPED_T_COMPONENT_SCR_BOOTSTRAP_MEAN,
    GROUPED_T_COMPONENT_SCR_POINT,
    GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    GROUPED_T_DF_FIN,
    GROUPED_T_DF_NONFIN,
    GROUPED_T_P90_CROSS_BLOCK_DILUTION,
    MAX_VINE_TREES,
    NESTED_PATHWISE_SCR_REFERENCE,
    NEXT_RISK_ID,
    PAIR_FAMILY_CANDIDATES,
    PRE_REGISTERED_TAIL_PAIRS,
    RANK_INVARIANCE_DF,
    REAGG_MATERIALITY_DISCLOSURE_THRESHOLD,
    RHO_FROZEN_TOL,
    SECOND_TREE_EDGES,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
    VINE_BOUNDARY_RECOVERY_TOL,
    VINE_ROOT_DRIVER,
    VINE_STRUCTURE,
    all_pre_registered_pairs,
    validate_vine_design_envelope,
    vine_copula_upgrade_use_restrictions,
    vine_pair_copula_pre_study,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE29_TASK1_DESIGN_NOTE.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE29_TASK1_DESIGN_NOTE.md")
CARD_PATH = os.path.join("docs", "VINE_COPULA_DESIGN_CARD.md")

CHANGE_TITLE = (
    "Phase 29 Task 1 - design note: vine / pair-copula dependence upgrade "
    "(truncated credit-root C-vine on frozen standalone margins)"
)

STANDARD_REFERENCES = [
    "Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence",
    "Bedford & Cooke (2002), Vines - a new graphical model for dependent random variables",
    "Solvency II Delegated Regulation Article 234 (aggregation including tail behaviour)",
    "Solvency II Delegated Regulation Article 23 (future management actions)",
    "SOA ASOP 56 sections 3.1.3, 3.4, 3.5",
    "SOA ASOP 25 section 3.3",
    "IA TAS M sections 3.2, 3.6, 3.7",
    "McNeil, Frey & Embrechts (2015), Quantitative Risk Management ch. 7",
]

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/vine_copula_upgrade.py (NEW, tested helper module)",
    "tests/test_phase29_task1_design_note.py",
    "scripts/build_phase29_task1_design_note.py",
    "docs/validation/PHASE29_TASK1_DESIGN_NOTE.{json,md}",
    "docs/VINE_COPULA_DESIGN_CARD.md",
]


def build_design_note(fast: bool = False) -> dict:
    pre = vine_pair_copula_pre_study(seed=42, n_scen=40_000 if fast else 200_000)
    envelope = validate_vine_design_envelope()
    note = {
        "title": "Phase 29 Task 1 - Design Note: Vine / Pair-Copula Dependence Upgrade",
        "verdict": "PASS" if pre["mechanism_demonstrated"] else "FAIL",
        "classification": "EDUCATIONAL",
        "candidate_chosen": (
            "truncated credit-root C-vine / pair-copula prototype (Aas et al. "
            "2009): first tree rooted on credit, second tree conditional on "
            "credit, at most two trees, and a capped family set "
            f"{list(PAIR_FAMILY_CANDIDATES)}. The implementation must retain a "
            "frozen_t_boundary leg that dispatches to the governed single-df t "
            "sampler and reproduces the frozen read-out exactly before any vine "
            "candidate is evaluated."
        ),
        "candidates_not_chosen": {
            "full_unrestricted_r_vine": (
                "Rejected for this cycle: too many structure/family/parameter "
                "degrees of freedom to govern as one additive educational change. "
                "A larger R-vine would need its own design note after the limited "
                "credit-root prototype is tested."
            ),
            "adopt_grouped_t_down_move": (
                "Rejected: Phase 28 grouped-t moved SCR down by diluting "
                "cross-block co-movement; it is disclosed but not adopted into "
                "the governed headline because it is non-conservative and did not "
                "close MR-016."
            ),
            "credentialled_data_calibration": (
                "Still blocked on credentialled market / management-practice data "
                "and independent APS X2 review. This remains the production "
                "sign-off residual."
            ),
        },
        "motivation": {
            "nested_pathwise_reference": NESTED_PATHWISE_SCR_REFERENCE,
            "frozen_t_component_scr": FROZEN_T_COMPONENT_SCR_REFERENCE,
            "skewt_reconfirmed_copula_form_residual": SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
            "grouped_t_point_scr": GROUPED_T_COMPONENT_SCR_POINT,
            "grouped_t_bootstrap_mean": GROUPED_T_COMPONENT_SCR_BOOTSTRAP_MEAN,
            "grouped_t_bootstrap_ci95": list(GROUPED_T_BOOTSTRAP_CI95),
            "grouped_t_copula_form_residual": GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
            "grouped_t_p90_cross_block_dilution": GROUPED_T_P90_CROSS_BLOCK_DILUTION,
            "grouped_t_df_nonfin": GROUPED_T_DF_NONFIN,
            "grouped_t_df_fin": GROUPED_T_DF_FIN,
            "existing_risk": EXISTING_RISK_ID,
        },
        "problem": (
            "Phase 27 and Phase 28 are now two negative super-set results. The "
            "skew-t upper-tail scalar fitted to the standalone margins pinned at "
            "gamma near zero and left the copula-form residual at 6,114.9. The "
            "grouped-t per-block df fit found no standalone within-carve-out tail "
            "concentration; it diluted cross-block co-movement, moved the disclosed "
            "component SCR down, and widened the residual to 10,491.5. MR-016 "
            "therefore cannot be treated as a single-copula parameter problem on "
            "standalone margins. The next governed escalation is a pair-copula "
            "construction that can localise conditional dependencies in the "
            "credit / FX / liquidity / action corner while preserving the frozen "
            "single-df t comparison leg."
        ),
        "method": (
            "Task 2 must implement the selected prototype only inside the envelope "
            "pre-registered here: a truncated credit-root C-vine with first-tree "
            "credit links, second-tree links conditioned on credit, no more than "
            f"{MAX_VINE_TREES} trees, and pair families limited to "
            f"{list(PAIR_FAMILY_CANDIDATES)}. Margins, Sigma and homogeneous df "
            "stay frozen. The search uses a fit set for family/parameter selection "
            "and a disjoint holdout set for tail diagnostics. Single-df t and "
            "grouped-t comparison variants are retained on common random numbers. "
            "The frozen_t_boundary mode must be evaluated first and must reproduce "
            "the archived frozen-t component read-out before the candidate result "
            "is considered."
        ),
        "pre_registered_structure": {
            "structure": VINE_STRUCTURE,
            "root_driver_index": VINE_ROOT_DRIVER,
            "root_driver_name": DRIVER_NAMES[VINE_ROOT_DRIVER],
            "max_vine_trees": MAX_VINE_TREES,
            "first_tree_edges": [list(e) for e in FIRST_TREE_EDGES],
            "second_tree_edges": [list(e) for e in SECOND_TREE_EDGES],
            "pre_registered_tail_pairs": [list(e) for e in PRE_REGISTERED_TAIL_PAIRS],
            "all_pairs": [list(e) for e in all_pre_registered_pairs()],
            "family_candidates": list(PAIR_FAMILY_CANDIDATES),
            "envelope_checks": envelope,
        },
        "pre_study_vine_pair_copula": pre,
        "pre_study_disclosure": (
            "The synthetic pre-study is not a calibration. It shows that, on common "
            "random numbers with frozen margins, a conditional pair-link shock can "
            "raise the pre-registered credit / FX / liquidity tail-pair dependence "
            "more than unrelated holdout pairs, while the zero-strength boundary "
            "recovers the frozen leg exactly. The real acceptance evidence is "
            "reserved for Tasks 2-4."
        ),
        "task2_acceptance_criteria": [
            f"Frozen boundary: reproduce frozen-t component {FROZEN_T_COMPONENT_SCR_REFERENCE:,.6f} before any vine computation; boundary max deviation <= {VINE_BOUNDARY_RECOVERY_TOL:.0e}.",
            f"Rank invariance: Sigma max|diff| <= {RHO_FROZEN_TOL}; homogeneous df remains {RANK_INVARIANCE_DF} within {DF_REMATCH_TOL}; standalone margins bit-identical.",
            "Implement only the pre-registered truncated credit-root C-vine envelope; no unrestricted structure search.",
            "Pair-family search limited to gaussian, student_t, survival_clayton, and survival_gumbel; no rotations or additional families without a new design note.",
            "Leakage control: family/parameter selection on fit rows only; holdout tail diagnostics reported separately.",
            "Retain single-df t and grouped-t comparison variants on common random numbers.",
            "Report candidate SCR direction vs frozen-t and grouped-t; direction disclosed, not gate-shopped.",
            "code_change ChangeRecord OWNER_REVIEW.",
        ],
        "task3_acceptance_criteria": [
            f"Vine margin bootstrap: >= {BOOTSTRAP_REPLICATES_GATE} replicates x {BOOTSTRAP_N_SIM_GATE:,} sims.",
            f"HEADLINE: nested {NESTED_PATHWISE_SCR_REFERENCE:,.1f} inside the vine 95% CI OR residual re-decomposed with the change vs grouped-t residual {GROUPED_T_COPULA_FORM_RESIDUAL_ABS:,.1f} and skew-t residual {SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS:,.1f} quantified.",
            f"Bootstrap SE <= {BOOTSTRAP_SE_GATE:.0%} of mean SCR.",
            "Common-random-number candidate minus frozen and candidate minus grouped-t differences reported with sign and confidence interval.",
            "Seeds/config/digests recorded; idempotent re-run digest-identical.",
            "methodology_change ChangeRecord OWNER_REVIEW.",
        ],
        "task4_acceptance_criteria": [
            "Tail diagnostics: per-pair upper/lower tail dependence for first-tree and second-tree links, plus holdout pairs.",
            "Fit-vs-holdout overfit check: candidate must not improve fit-set tail pairs while degrading holdout residual disclosure silently.",
            f"MR-016 remediation decision: close/mitigate only if residual materially shrinks and nested reference is inside CI; otherwise keep MR-016 OPEN and open {NEXT_RISK_ID} for remaining vine-form limitations if needed.",
            f"MR-010/MR-014 refresh if candidate SCR moves more than {REAGG_MATERIALITY_DISCLOSURE_THRESHOLD:.0%} from the governed frozen-t headline.",
            "Governance ChangeRecord OWNER_REVIEW; risk-register update idempotent.",
        ],
        "task5_plan": (
            "Offline-UI propagation only after Tasks 2-4: additive contract "
            "1.10.0 -> 1.11.0 with vine vs frozen vs grouped vs nested SCR, "
            "family selections, tail diagnostics, bootstrap CI, and MR-016 status."
        ),
        "limitations": [
            "This cycle is design-only; no vine capital figure is adopted.",
            "The synthetic pre-study demonstrates conditional-pair targeting and exact zero-strength boundary recovery, not real-data magnitude.",
            "A truncated credit-root C-vine may still be too simple for nested inner-path joint dynamics; failure is informative and must be disclosed.",
            "The family envelope is intentionally capped for governance; expanding it needs a new design note.",
            "Production sign-off remains blocked by credentialled data and independent APS X2 review.",
        ],
        "use_restrictions": vine_copula_upgrade_use_restrictions(),
        "standard_references": STANDARD_REFERENCES,
        "affected_components": AFFECTED_COMPONENTS,
    }
    return note


def _md(note: dict) -> str:
    pre = note["pre_study_vine_pair_copula"]
    td = pre["tail_dependence_proxy"]
    lines = [
        f"# {note['title']}",
        "",
        f"**Verdict: {note['verdict']}** (design note + tested helper module). EDUCATIONAL ONLY.",
        "",
        "## 0. Candidate selection",
        "",
        f"**Chosen:** {note['candidate_chosen']}",
        "",
        f"- Full unrestricted R-vine: {note['candidates_not_chosen']['full_unrestricted_r_vine']}",
        f"- Adopt grouped-t down move: {note['candidates_not_chosen']['adopt_grouped_t_down_move']}",
        f"- Credentialled data: {note['candidates_not_chosen']['credentialled_data_calibration']}",
        "",
        "## 1. Problem",
        "",
        note["problem"],
        "",
        f"Archived motivation: nested {NESTED_PATHWISE_SCR_REFERENCE:,.1f}; frozen-t {FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f}; grouped-t bootstrap mean {GROUPED_T_COMPONENT_SCR_BOOTSTRAP_MEAN:,.1f} with CI {GROUPED_T_BOOTSTRAP_CI95}; grouped-t residual {GROUPED_T_COPULA_FORM_RESIDUAL_ABS:,.1f}; MR-016 open.",
        "",
        "## 2. Method",
        "",
        note["method"],
        "",
        "## 3. Pre-registered structure",
        "",
        f"- Structure: {VINE_STRUCTURE}; root: {DRIVER_NAMES[VINE_ROOT_DRIVER]}; max trees: {MAX_VINE_TREES}",
        f"- First-tree edges: {note['pre_registered_structure']['first_tree_edges']}",
        f"- Second-tree edges: {note['pre_registered_structure']['second_tree_edges']}",
        f"- Family candidates: {list(PAIR_FAMILY_CANDIDATES)}",
        f"- Envelope checks: {json.dumps(note['pre_registered_structure']['envelope_checks'], default=float)}",
        "",
        "## 4. Synthetic mechanism pre-study",
        "",
        f"- n_scen={pre['config']['n_scen']:,}; seed={pre['config']['seed']}; conditional_tail_strength={pre['config']['conditional_tail_strength']}",
        f"- Target upper-tail dependence: frozen {td['target_upper_frozen']:.4f}; vine {td['target_upper_vine']:.4f}; lift {pre['target_upper_tail_lift']:+.4f}",
        f"- Holdout upper-tail dependence: frozen {td['holdout_upper_frozen']:.4f}; vine {td['holdout_upper_vine']:.4f}; lift {pre['holdout_upper_tail_lift']:+.4f}",
        f"- VaR99.5: frozen proxy {pre['var995']['frozen_t_proxy']:.2f}; vine proxy {pre['var995']['vine_pair_proxy']:.2f}; relative move {pre['var_lift_rel_at_var995']:+.2%}",
        f"- Frozen-boundary exact recovery: {pre['boundary_recovery_max_abs']:.1e}; digest {pre['digest']}",
        "",
        note["pre_study_disclosure"],
        "",
        "## 5. Acceptance criteria (fixed before implementation)",
        "",
        "**Task 2:**",
        "",
    ]
    lines.extend(f"- {c}" for c in note["task2_acceptance_criteria"])
    lines.extend(["", "**Task 3:**", ""])
    lines.extend(f"- {c}" for c in note["task3_acceptance_criteria"])
    lines.extend(["", "**Task 4:**", ""])
    lines.extend(f"- {c}" for c in note["task4_acceptance_criteria"])
    lines.extend(["", f"**Task 5 plan:** {note['task5_plan']}", "", "## 6. Limitations", ""])
    lines.extend(f"- {l}" for l in note["limitations"])
    lines.extend(["", "## 7. Standards", ""])
    lines.extend(f"- {s}" for s in note["standard_references"])
    lines.extend(["", "*Generated by scripts/build_phase29_task1_design_note.py.*", ""])
    return "\n".join(lines)


def _card(note: dict) -> str:
    pre = note["pre_study_vine_pair_copula"]
    td = pre["tail_dependence_proxy"]
    return "\n".join([
        "# Vine / Pair-Copula Dependence Upgrade - Design Card (Phase 29)",
        "",
        f"**Verdict: {note['verdict']}**. EDUCATIONAL ONLY.",
        "",
        "## What changes",
        "",
        "Phase 29 selects a truncated credit-root C-vine / pair-copula prototype.",
        "It keeps standalone margins, Sigma and the homogeneous df frozen, and",
        "requires an explicit frozen_t_boundary leg that reproduces the governed",
        "single-df t read-out before any candidate result is evaluated.",
        "",
        "## Why",
        "",
        f"- Skew-t residual remained {SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS:,.1f}; grouped-t residual widened to {GROUPED_T_COPULA_FORM_RESIDUAL_ABS:,.1f}.",
        f"- Grouped-t moved SCR down ({GROUPED_T_COMPONENT_SCR_POINT:,.1f} point; bootstrap mean {GROUPED_T_COMPONENT_SCR_BOOTSTRAP_MEAN:,.1f}) by cross-block dilution, so it is disclosed but not adopted.",
        f"- MR-016 is open; mitigation path is vine / pair-copula conditional dependence.",
        "",
        "## Pre-registered gates",
        "",
        f"- Frozen-t component {FROZEN_T_COMPONENT_SCR_REFERENCE:,.6f} reproduced before vine computation; boundary tolerance {VINE_BOUNDARY_RECOVERY_TOL:.0e}.",
        f"- Search envelope: root={DRIVER_NAMES[VINE_ROOT_DRIVER]}, max trees={MAX_VINE_TREES}, families={list(PAIR_FAMILY_CANDIDATES)}.",
        "- Leakage-free fit/holdout selection; retain frozen single-df t and grouped-t comparison variants.",
        f"- Bootstrap: at least {BOOTSTRAP_REPLICATES_GATE} x {BOOTSTRAP_N_SIM_GATE:,}; SE <= {BOOTSTRAP_SE_GATE:.0%}.",
        f"- MR-016 may be mitigated only if residual materially shrinks and nested {NESTED_PATHWISE_SCR_REFERENCE:,.1f} is inside the candidate CI; otherwise keep open and escalate.",
        "",
        "## Synthetic mechanism check",
        "",
        f"- Target upper-tail lift {pre['target_upper_tail_lift']:+.4f} vs holdout lift {pre['holdout_upper_tail_lift']:+.4f}; boundary recovery {pre['boundary_recovery_max_abs']:.1e}.",
        f"- Target frozen/vine upper-tail dependence {td['target_upper_frozen']:.4f}/{td['target_upper_vine']:.4f}.",
        f"- Digest {pre['digest']}.",
        "",
        "*Generated by scripts/build_phase29_task1_design_note.py.*",
        "",
    ])


def apply_governance(store: GovernanceStore, note: dict) -> dict:
    actor = "Phase29Task1DesignNote"
    phase = "Phase 29: Vine / Pair-Copula Dependence Upgrade"
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        return {"added": False, "reason": "already applied (idempotent)"}
    pre = note["pre_study_vine_pair_copula"]
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Design note for Phase 29 vine / pair-copula dependence upgrade: a "
            "truncated credit-root C-vine candidate with frozen standalone margins, "
            "explicit frozen single-df t boundary recovery, capped family search, "
            "leakage-free fit/holdout gates, bootstrap gates, and MR-016 remediation "
            "criteria. No capital output changed this cycle."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "mr016": "OPEN; grouped-t widened residual to 10,491.5 and moved SCR down by cross-block dilution",
            "next_task": "Phase 29 Task 1 design note",
        },
        after_snapshot={
            "selected_candidate": VINE_STRUCTURE,
            "root_driver": DRIVER_NAMES[VINE_ROOT_DRIVER],
            "family_candidates": list(PAIR_FAMILY_CANDIDATES),
            "boundary_recovery_max_abs": pre["boundary_recovery_max_abs"],
            "mechanism_demonstrated": pre["mechanism_demonstrated"],
            "verdict": note["verdict"],
        },
        impact_assessment=(
            "Design and governance only. The note fixes the candidate envelope and "
            "gates before implementation, preserving the governed frozen-t boundary "
            "and retaining grouped-t and single-t comparison variants."
        ),
        author=actor,
        phase=phase,
        quantitative_impact=(
            f"Synthetic pre-study target upper-tail lift "
            f"{pre['target_upper_tail_lift']:+.4f}; holdout lift "
            f"{pre['holdout_upper_tail_lift']:+.4f}; boundary recovery "
            f"{pre['boundary_recovery_max_abs']:.1e}. No governed capital figures changed."
        ),
    )
    rec.submit_for_peer_review(actor=actor, comments="Design note + helper tests; frozen boundary and leakage gates pre-registered.")
    rec.submit_to_owner(actor=actor, comments="Owner review: educational design only; implementation deferred to Task 2.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=actor,
        phase=phase,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 29 Task 1 vine / pair-copula design note",
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
    out = {"verdict": note["verdict"], "json": JSON_PATH, "md": MD_PATH, "card": CARD_PATH}
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
