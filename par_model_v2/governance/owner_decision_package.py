"""Phase 31 Task 1 - owner decision package (dependence): pre-registration.

Pure-GOVERNANCE module: NO model calculation, NO parameter changes, NO new
copula-structure candidates (the Phase 30 binding stop-rule ended
dependence-FORM escalation under MR-016).  Everything here is a
pre-registration of the owner decision package that Phase 31 will assemble:

* :func:`evidence_pack_registry` - the fixed table of contents of the
  evidence pack, each figure cross-checked bit-for-bit against the frozen
  archived references in the projection modules (single source of truth).
* :func:`owner_options` - the THREE pre-registered owner options with fixed
  acceptance criteria (design-note-first discipline: criteria are frozen
  BEFORE the pack is assembled and BEFORE the owner sees it).
* :func:`signoff_workflow` - the ordered sign-off workflow per IFoA MPN
  section 4 and ASOP 56 (documentation, independent review, owner decision,
  risk-register disposition, disclosure).
* :func:`validate_owner_package` - the envelope/consistency gate.

Classification: EDUCATIONAL.  The governed headline remains the frozen
single-df t component SCR; nothing in Phase 31 changes any capital figure.
"""

from __future__ import annotations

from typing import Dict, List

from par_model_v2.projection.dependence_roadmap import (
    MR016_RISK_ID,
    MR017_RISK_ID,
    VINE2_BOOTSTRAP_CI95,
    VINE2_COMPONENT_SCR_BOOTSTRAP_MEAN,
    VINE2_COMPONENT_SCR_POINT,
    VINE2_COPULA_FORM_RESIDUAL_POINT,
    VINE2_GAP_TOTAL_POINT,
)
from par_model_v2.projection.grouped_t_upgrade import (
    COPULA_FORM_RESIDUAL_ABS as FROZEN_T_COPULA_FORM_RESIDUAL_ABS,
)
from par_model_v2.projection.vine_copula_upgrade import (
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
)
from par_model_v2.projection.vine_tree3_tail_diagnostics import (
    P30T3_TREE3_CI_HI,
    P30T3_TREE3_CI_LO,
    P30T3_TREE3_COMPONENT_MEAN,
    TREE3_COPULA_FORM_RESIDUAL_POINT,
)

#: Phase 31 owner option identifiers (pre-registered; fixed order).
OWNER_OPTION_IDS = (
    "O1_adopt_disclosed_vine_readout",
    "O2_accept_residual_with_monitoring",
    "O3_fund_second_independent_nested_run",
)

#: The only escalation path the Phase 30 stop-rule left open (former
#: roadmap option B - a SECOND, independent nested path-wise run).
ESCALATION_OPTION_ID = "O3_fund_second_independent_nested_run"

#: Phase 31 changes no parameters and adds no copula-structure candidates.
NO_MODEL_PARAMETER_CHANGES = True

#: Stop-rule record carried into the pack (Phase 30 Task 4 outcome).
STOP_RULE_RECORD = {
    "trigger": (
        "nested path-wise reference outside the tree-3 candidate 95% "
        "bootstrap CI at Phase 30 Task 4"
    ),
    "trigger_met": True,
    "applied": True,
    "effect": "dependence-FORM escalation under MR-016 ENDS",
    "mr016_disposition": "KEEP OPEN (quantified residual disclosed)",
    "mr017_disposition": "KEEP OPEN (vine-form limitations)",
    "governed_headline_move_pct": 0.0,
    "tree3_zero_strength": True,
    "tree3_bit_identical_to_vine2": True,
}

#: P26 -> P30 dependence escalation history (form, residual, outcome).
ESCALATION_HISTORY = (
    {"phase": "Phase 26", "form": "frozen single-df t (path-wise re-aggregation)",
     "copula_form_residual_abs": FROZEN_T_COPULA_FORM_RESIDUAL_ABS,
     "outcome": "baseline quantified residual"},
    {"phase": "Phase 27", "form": "skew-t copula",
     "copula_form_residual_abs": SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
     "outcome": "no material closure vs frozen-t; not adopted"},
    {"phase": "Phase 28", "form": "grouped-t / heterogeneous tail",
     "copula_form_residual_abs": GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
     "outcome": "residual WIDENED; rejected"},
    {"phase": "Phase 29", "form": "truncated 2-tree credit-root C-vine",
     "copula_form_residual_abs": VINE2_COPULA_FORM_RESIDUAL_POINT,
     "outcome": "first POSITIVE result; nested still outside 95% CI; "
                "DISCLOSED, not adopted"},
    {"phase": "Phase 30", "form": "tree-3 C-vine deepening",
     "copula_form_residual_abs": TREE3_COPULA_FORM_RESIDUAL_POINT,
     "outcome": "all four pre-registered third-tree pairs fitted zero "
                "strength; BIT-IDENTICAL to 2-tree vine; binding stop-rule "
                "APPLIED"},
)


def evidence_pack_registry() -> Dict:
    """The pre-registered table of contents of the Phase 31 evidence pack.

    Every figure is sourced from the frozen archived constants - the pack
    assembler (Task 2) MUST reproduce these bit-for-bit; the validator gate
    enforces it.  No figure is recomputed here.
    """
    return {
        "governed_headline": {
            "label": "governed component SCR headline (frozen single-df t)",
            "value": FROZEN_T_COMPONENT_SCR_REFERENCE,
            "rank_invariance_df": RANK_INVARIANCE_DF,
            "move_pct_through_p27_p30": 0.0,
            "status": "GOVERNED - unchanged by every escalation P27->P30",
        },
        "disclosed_candidates": {
            "vine2": {
                "label": "truncated 2-tree credit-root C-vine (Phase 29)",
                "component_scr_point": VINE2_COMPONENT_SCR_POINT,
                "bootstrap_mean": VINE2_COMPONENT_SCR_BOOTSTRAP_MEAN,
                "bootstrap_ci95": list(VINE2_BOOTSTRAP_CI95),
                "adopted": False,
            },
            "tree3": {
                "label": "tree-3 C-vine candidate (Phase 30; zero strength)",
                "component_scr_point": VINE2_COMPONENT_SCR_POINT,
                "bootstrap_mean": P30T3_TREE3_COMPONENT_MEAN,
                "bootstrap_ci95": [P30T3_TREE3_CI_LO, P30T3_TREE3_CI_HI],
                "bit_identical_to_vine2": True,
                "adopted": False,
            },
        },
        "nested_reference": {
            "label": "nested path-wise SCR reference (single run)",
            "value": NESTED_PATHWISE_SCR_REFERENCE,
            "inside_vine2_ci95": bool(
                VINE2_BOOTSTRAP_CI95[0]
                <= NESTED_PATHWISE_SCR_REFERENCE
                <= VINE2_BOOTSTRAP_CI95[1]
            ),
            "inside_tree3_ci95": bool(
                P30T3_TREE3_CI_LO
                <= NESTED_PATHWISE_SCR_REFERENCE
                <= P30T3_TREE3_CI_HI
            ),
            "single_run_caveat": (
                "ONE nested run only; its own sampling error is unquantified "
                "- the motivation for option O3"
            ),
        },
        "residual_ladder": [
            {"form": "grouped-t (P28)",
             "copula_form_residual_abs": GROUPED_T_COPULA_FORM_RESIDUAL_ABS},
            {"form": "frozen single-df t (P26)",
             "copula_form_residual_abs": FROZEN_T_COPULA_FORM_RESIDUAL_ABS},
            {"form": "skew-t (P27)",
             "copula_form_residual_abs": SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS},
            {"form": "2-tree / tree-3 vine (P29/P30)",
             "copula_form_residual_abs": VINE2_COPULA_FORM_RESIDUAL_POINT},
        ],
        "gap_decomposition": {
            "total_gap_point": VINE2_GAP_TOTAL_POINT,
            "copula_form_part": VINE2_COPULA_FORM_RESIDUAL_POINT,
        },
        "risk_register_status": {
            MR016_RISK_ID: "OPEN - quantified copula-form residual disclosed",
            MR017_RISK_ID: "OPEN - vine-form limitations (truncation)",
            "stop_rule_record": dict(STOP_RULE_RECORD),
        },
        "escalation_history": [dict(e) for e in ESCALATION_HISTORY],
    }


def owner_options() -> Dict[str, Dict]:
    """The THREE pre-registered owner options with fixed acceptance criteria."""
    return {
        "O1_adopt_disclosed_vine_readout": {
            "what": (
                "Adopt the disclosed 2-tree vine read-out "
                f"({VINE2_COMPONENT_SCR_POINT:,.1f}) as the governed "
                "component-SCR headline, replacing the frozen single-df t "
                f"({FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f})."
            ),
            "capital_effect_abs": VINE2_COMPONENT_SCR_POINT - FROZEN_T_COMPONENT_SCR_REFERENCE,
            "acceptance_criteria": [
                "explicit owner sign-off recorded in a governance ChangeRecord "
                "(model_change) BEFORE any headline switch",
                f"a written {MR017_RISK_ID} mitigation plan for the residual "
                "vine-form limitations (truncation; nested outside 95% CI)",
                "full re-run of the UI/state propagation chain so every "
                "disclosure surface shows the new governed basis",
                "risk-register update: MR-016 re-pointed at the REMAINING "
                f"residual {VINE2_COPULA_FORM_RESIDUAL_POINT:,.1f}, not closed",
            ],
            "escalation_path_open": False,
            "governance_risk": "HIGH - adopts a candidate whose 95% CI excludes the nested reference",
        },
        "O2_accept_residual_with_monitoring": {
            "what": (
                "Keep the frozen single-df t headline; formally ACCEPT the "
                f"quantified copula-form residual {VINE2_COPULA_FORM_RESIDUAL_POINT:,.1f} "
                "as a documented model limitation."
            ),
            "capital_effect_abs": 0.0,
            "acceptance_criteria": [
                "a documented residual TOLERANCE (absolute and as % of the "
                "governed headline) signed by the owner",
                "a pre-registered MONITORING TRIGGER (re-open MR-016 "
                "escalation if a future recalibration moves the residual "
                "beyond tolerance)",
                "annual re-affirmation entry in the risk register "
                f"({MR016_RISK_ID}/{MR017_RISK_ID} stay OPEN with ACCEPTED disposition)",
            ],
            "escalation_path_open": False,
            "governance_risk": "MEDIUM - residual persists but is quantified, disclosed and monitored",
        },
        "O3_fund_second_independent_nested_run": {
            "what": (
                "Fund former roadmap option B: a SECOND, independent nested "
                "path-wise run (fresh seeds, independent implementation "
                "checks) to quantify the sampling error of the nested "
                f"reference {NESTED_PATHWISE_SCR_REFERENCE:,.1f} - the only "
                "escalation path the Phase 30 binding stop-rule left open."
            ),
            "capital_effect_abs": 0.0,
            "acceptance_criteria": [
                "pre-registered design note BEFORE the run (seeds, scenario "
                "count, acceptance gates) - no peeking at the existing "
                "nested figure when fixing gates",
                "the run is INDEPENDENT: new random seeds and an independent "
                "reviewer of the run configuration (ASOP 56 s3.5 reliance)",
                "decision rule fixed in advance: if the two nested runs "
                "bracket the vine CI differently, the owner package is "
                "re-issued with the pooled estimate; copula-FORM escalation "
                "stays ENDED either way",
            ],
            "escalation_path_open": True,
            "governance_risk": "LOW - adds information only; no model change",
        },
    }


def signoff_workflow() -> List[Dict]:
    """Ordered sign-off workflow per IFoA MPN section 4 / ASOP 56."""
    return [
        {"step": 1, "actor": "preparer (model development)",
         "action": "assemble the evidence pack EXACTLY per "
                   "evidence_pack_registry(); bit-for-bit consistency gate "
                   "against the frozen archived references",
         "standards": ["ASOP 56 s3.1.3 (understanding the model)",
                       "IFoA MPN s4 (documentation sufficient for a "
                       "technically competent third party)"]},
        {"step": 2, "actor": "independent peer reviewer",
         "action": "review pack completeness, figure provenance and the "
                   "neutral presentation of all three options (no "
                   "recommendation embedded)",
         "standards": ["ASOP 56 s3.4 (reliance on others)",
                       "IFoA MPN s4.3 (independent review proportionate to "
                       "materiality)"]},
        {"step": 3, "actor": "model owner",
         "action": "owner review meeting: walk through governed headline, "
                   "disclosed candidates, residual ladder, stop-rule record "
                   "and the three options with their pre-registered "
                   "acceptance criteria",
         "standards": ["ASOP 56 s3.5 (evaluation and mitigation of model risk)",
                       "IFoA MPN s4.4 (communication of limitations to the "
                       "decision maker)"]},
        {"step": 4, "actor": "model owner",
         "action": "record the decision (O1/O2/O3) and its rationale in a "
                   "governance ChangeRecord; the decision is NOT made by "
                   "the model developer or any agent",
         "standards": ["ASOP 56 s3.6 (documentation of decisions)",
                       "IFoA MPN s4.5 (clear ownership of the decision)"]},
        {"step": 5, "actor": "preparer (model development)",
         "action": "execute the selected option's acceptance criteria; "
                   f"update {MR016_RISK_ID}/{MR017_RISK_ID} dispositions "
                   "accordingly",
         "standards": ["ASOP 56 s3.5", "IFoA MPN s4.6 (follow-up actions)"]},
        {"step": 6, "actor": "preparer (model development)",
         "action": "propagate any NEW disclosure surface to the offline UI "
                   "(additive contract bump only) and archive the pack",
         "standards": ["IFoA MPN s4 (audit trail)",
                       "ASOP 41 (actuarial communications)"]},
    ]


def validate_owner_package(pack: Dict, options: Dict, workflow: List[Dict]) -> Dict:
    """Envelope gate: the pack/options/workflow are internally consistent
    and bit-for-bit tied to the frozen archived references."""
    checks = {}
    gh = pack["governed_headline"]
    checks["headline_matches_frozen_t"] = gh["value"] == FROZEN_T_COMPONENT_SCR_REFERENCE
    checks["headline_move_zero"] = gh["move_pct_through_p27_p30"] == 0.0
    v2 = pack["disclosed_candidates"]["vine2"]
    t3 = pack["disclosed_candidates"]["tree3"]
    checks["vine2_point_matches"] = v2["component_scr_point"] == VINE2_COMPONENT_SCR_POINT
    checks["tree3_bit_identical"] = (
        t3["component_scr_point"] == v2["component_scr_point"]
        and t3["bit_identical_to_vine2"] is True
    )
    checks["no_candidate_adopted"] = (not v2["adopted"]) and (not t3["adopted"])
    nr = pack["nested_reference"]
    checks["nested_matches"] = nr["value"] == NESTED_PATHWISE_SCR_REFERENCE
    checks["nested_outside_both_cis"] = (not nr["inside_vine2_ci95"]) and (not nr["inside_tree3_ci95"])
    ladder = [r["copula_form_residual_abs"] for r in pack["residual_ladder"]]
    checks["residual_ladder_descending"] = all(a > b for a, b in zip(ladder, ladder[1:]))
    checks["residual_ladder_endpoints"] = (
        ladder[0] == GROUPED_T_COPULA_FORM_RESIDUAL_ABS
        and ladder[-1] == VINE2_COPULA_FORM_RESIDUAL_POINT
    )
    rr = pack["risk_register_status"]
    checks["mr_status_open"] = (
        rr[MR016_RISK_ID].startswith("OPEN") and rr[MR017_RISK_ID].startswith("OPEN")
    )
    sr = rr["stop_rule_record"]
    checks["stop_rule_applied"] = sr["applied"] is True and sr["trigger_met"] is True
    checks["history_complete_p26_p30"] = [e["phase"] for e in pack["escalation_history"]] == [
        "Phase 26", "Phase 27", "Phase 28", "Phase 29", "Phase 30"]
    checks["exactly_three_options"] = tuple(options.keys()) == OWNER_OPTION_IDS
    checks["each_option_has_criteria"] = all(
        len(o["acceptance_criteria"]) >= 3 for o in options.values())
    open_paths = [k for k, o in options.items() if o["escalation_path_open"]]
    checks["single_escalation_path_is_o3"] = open_paths == [ESCALATION_OPTION_ID]
    checks["o2_zero_capital_effect"] = options["O2_accept_residual_with_monitoring"]["capital_effect_abs"] == 0.0
    checks["workflow_ordered"] = [s["step"] for s in workflow] == list(range(1, len(workflow) + 1))
    checks["workflow_has_owner_decision"] = any(
        s["actor"] == "model owner" and "record the decision" in s["action"] for s in workflow)
    checks["workflow_has_independent_review"] = any(
        "independent" in s["actor"] for s in workflow)
    checks["every_step_has_standards"] = all(len(s["standards"]) >= 1 for s in workflow)
    checks["no_parameter_changes"] = NO_MODEL_PARAMETER_CHANGES is True
    return {"checks": checks, "ok": all(checks.values()), "n_checks": len(checks)}


# ---------------------------------------------------------------------------
# Phase 31 Task 2 - pack ASSEMBLY (exactly per the Task 1 registry)
# ---------------------------------------------------------------------------

#: Version of the assembled owner pack document (Task 2).
PACK_DOC_VERSION = "1.0.0"

#: Stable identifier of the assembled pack document.
PACK_DOC_ID = "PHASE31_OWNER_DECISION_PACK"

#: Phrases that would break the pre-registered NEUTRALITY requirement
#: (the pack must present the options without steering the owner).
NEUTRALITY_FORBIDDEN_PHRASES = (
    "we recommend",
    "is recommended",
    "recommended option",
    "preferred option",
    "we prefer",
    "best option",
    "default option",
    "you should choose",
    "the owner should choose",
)

#: Sections an assembled pack MUST contain to be self-contained
#: (IFoA MPN s4: usable by a technically competent third party
#: without repo access).
REQUIRED_PACK_SECTIONS = (
    "metadata",
    "purpose",
    "how_to_read",
    "evidence_pack",
    "figure_provenance",
    "owner_options",
    "signoff_workflow",
    "decision_record_template",
    "glossary",
    "limitations",
    "standard_references",
)

#: Glossary terms the pack must define for self-containment.
REQUIRED_GLOSSARY_TERMS = (
    "component SCR",
    "governed headline",
    "copula-form residual",
    "nested path-wise reference",
    "bootstrap CI95",
    "C-vine copula",
    "binding stop-rule",
    "MR-016",
    "MR-017",
)


def decision_record_template() -> Dict:
    """Blank decision record for the owner to complete (step 4 of the
    sign-off workflow).  All decision fields are EMPTY by construction -
    the pack pre-fills nothing (neutrality)."""
    return {
        "decision_option_id": "",
        "rationale": "",
        "decided_by": "",
        "decided_at": "",
        "peer_reviewer": "",
        "follow_up_change_record_id": "",
        "instructions": (
            "To be completed by the model owner at workflow step 4. Select "
            "exactly one of O1/O2/O3, record the rationale, and open a "
            "governance ChangeRecord referencing this pack."
        ),
    }


def _glossary() -> Dict[str, str]:
    return {
        "component SCR": (
            "the 99.5th-percentile one-year loss for the modelled risk "
            "aggregation component, before diversification with other "
            "balance-sheet components"
        ),
        "governed headline": (
            "the component SCR figure currently approved for use - the "
            "frozen single-df t-copula read-out "
            f"{FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f}; it has not moved "
            "through any escalation P27->P30"
        ),
        "copula-form residual": (
            "the absolute difference between a copula candidate's component "
            "SCR and the nested path-wise reference, holding margins and "
            "calibration fixed - it isolates the dependence-FORM effect"
        ),
        "nested path-wise reference": (
            "a full nested stochastic re-simulation that applies the "
            "governed management-action rule inside every joint scenario "
            f"({NESTED_PATHWISE_SCR_REFERENCE:,.1f}); ONE run exists, so "
            "its own sampling error is unquantified"
        ),
        "bootstrap CI95": (
            "the 95% confidence interval for a candidate's component SCR "
            "obtained by resampling the joint scenario set"
        ),
        "C-vine copula": (
            "a vine copula built from a cascade of bivariate copulas "
            "around root nodes; 'truncated 2-tree' means only the first "
            "two trees carry fitted dependence"
        ),
        "binding stop-rule": (
            "the pre-registered Phase 30 rule that ENDS dependence-form "
            "escalation once an added vine tree fits zero strength while "
            "the nested reference stays outside the candidate's 95% CI"
        ),
        "MR-016": (
            "model-risk register item: quantified copula-form residual "
            "(dependence form) - OPEN, disclosed"
        ),
        "MR-017": (
            "model-risk register item: vine-form limitations (truncation; "
            "nested outside 95% CI) - OPEN, disclosed"
        ),
    }


def _figure_provenance() -> Dict[str, str]:
    """Where every headline figure in the pack comes from (frozen archived
    constants; nothing recomputed at assembly time)."""
    return {
        "governed_headline": (
            "par_model_v2.projection.vine_copula_upgrade."
            "FROZEN_T_COMPONENT_SCR_REFERENCE (frozen at Phase 26; "
            "re-affirmed bit-for-bit every phase through P30)"
        ),
        "vine2_point": (
            "par_model_v2.projection.dependence_roadmap."
            "VINE2_COMPONENT_SCR_POINT (Phase 29 Task 2 archived run)"
        ),
        "vine2_bootstrap": (
            "par_model_v2.projection.dependence_roadmap."
            "VINE2_COMPONENT_SCR_BOOTSTRAP_MEAN / VINE2_BOOTSTRAP_CI95 "
            "(Phase 29 Task 4 archived bootstrap)"
        ),
        "tree3_bootstrap": (
            "par_model_v2.projection.vine_tree3_tail_diagnostics."
            "P30T3_TREE3_COMPONENT_MEAN / P30T3_TREE3_CI_LO / "
            "P30T3_TREE3_CI_HI (Phase 30 Task 3 archived bootstrap)"
        ),
        "nested_reference": (
            "par_model_v2.projection.vine_copula_upgrade."
            "NESTED_PATHWISE_SCR_REFERENCE (Phase 24 archived nested run)"
        ),
        "residual_ladder": (
            "par_model_v2.projection.grouped_t_upgrade.COPULA_FORM_RESIDUAL_ABS "
            "(P26 frozen-t), "
            "vine_copula_upgrade.GROUPED_T_COPULA_FORM_RESIDUAL_ABS (P28), "
            "vine_copula_upgrade.SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS "
            "(P27), dependence_roadmap.VINE2_COPULA_FORM_RESIDUAL_POINT "
            "(P29/P30)"
        ),
        "gap_decomposition": (
            "par_model_v2.projection.dependence_roadmap."
            "VINE2_GAP_TOTAL_POINT / VINE2_COPULA_FORM_RESIDUAL_POINT "
            "(Phase 29 Task 4 archived decomposition)"
        ),
    }


def assemble_owner_pack() -> Dict:
    """Assemble the owner decision pack EXACTLY per the Task 1 registry.

    Pure function of the frozen archived constants: the evidence section IS
    :func:`evidence_pack_registry`, the options ARE :func:`owner_options`,
    the workflow IS :func:`signoff_workflow` - reproduced bit-for-bit, with
    the self-containment material (purpose, reading guide, provenance,
    glossary, blank decision record) wrapped around them.
    """
    return {
        "metadata": {
            "pack_id": PACK_DOC_ID,
            "pack_version": PACK_DOC_VERSION,
            "phase": "Phase 31: Owner Decision Package (Dependence)",
            "task": "Task 2 - assembly per the Task 1 frozen registry",
            "classification": "EDUCATIONAL",
            "no_model_parameter_changes": NO_MODEL_PARAMETER_CHANGES,
            "design_note": "docs/validation/PHASE31_TASK1_DESIGN_NOTE.{json,md}",
        },
        "purpose": (
            "Give the model owner everything needed to decide how to "
            "dispose of the quantified dependence-form residual "
            f"{VINE2_COPULA_FORM_RESIDUAL_POINT:,.1f} between the governed "
            f"frozen single-df t headline {FROZEN_T_COMPONENT_SCR_REFERENCE:,.1f} "
            f"and the nested path-wise reference {NESTED_PATHWISE_SCR_REFERENCE:,.1f}, "
            "after the Phase 30 binding stop-rule ended dependence-FORM "
            "escalation. Three options are presented neutrally; the choice "
            "rests solely with the model owner."
        ),
        "how_to_read": [
            "Section 'evidence_pack' holds every governed and disclosed "
            "figure with its status; nothing in it is a proposal.",
            "Section 'figure_provenance' states the frozen archived source "
            "of each figure; no figure was recomputed at assembly time.",
            "Section 'owner_options' lists the three pre-registered options "
            "in fixed order O1/O2/O3 with their acceptance criteria; the "
            "ordering is registry order, not preference order.",
            "Section 'signoff_workflow' is the six-step decision process; "
            "the owner decides at step 4 using the blank "
            "'decision_record_template'.",
            "The glossary defines every technical term used, so the pack "
            "can be read without access to the model repository.",
        ],
        "evidence_pack": evidence_pack_registry(),
        "figure_provenance": _figure_provenance(),
        "owner_options": owner_options(),
        "owner_option_order": list(OWNER_OPTION_IDS),
        "escalation_option_id": ESCALATION_OPTION_ID,
        "signoff_workflow": signoff_workflow(),
        "decision_record_template": decision_record_template(),
        "glossary": _glossary(),
        "limitations": [
            "the nested reference is a SINGLE run; its sampling error is "
            "unquantified (the subject of option O3)",
            "acceptance criteria constrain but cannot bind the owner; "
            "variations re-open the design note via a new ChangeRecord",
            "the residual ladder compares copula FORMS on a fixed margin/"
            "calibration basis; margin-side model risk is tracked separately",
        ],
        "standard_references": [
            "IFoA Model Practice Note (MPN) section 4 (documentation, "
            "independent review, communication)",
            "SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, "
            "reliance, documentation of decisions)",
            "SOA ASOP 41 (actuarial communications)",
            "Solvency II Delegated Regulation Article 124 (validation "
            "standards)",
        ],
    }


def validate_assembled_pack(doc: Dict) -> Dict:
    """Task 2 gate: the ASSEMBLED pack re-passes the Task 1 envelope gate
    bit-for-bit AND satisfies the assembly-specific acceptance criteria
    frozen in the Task 1 design note (s6)."""
    import json as _json

    checks: Dict[str, bool] = {}

    # -- frozen Task 1 gate, re-run against the assembled pack's own data --
    base = validate_owner_package(
        doc["evidence_pack"], doc["owner_options"], doc["signoff_workflow"])
    checks["task1_gate_ok_on_assembled_pack"] = base["ok"]
    checks["task1_gate_n_checks_21"] = base["n_checks"] == 21

    # -- bit-for-bit reproduction of the registry ------------------------
    checks["evidence_bit_for_bit"] = doc["evidence_pack"] == evidence_pack_registry()
    checks["options_bit_for_bit"] = doc["owner_options"] == owner_options()
    checks["workflow_bit_for_bit"] = doc["signoff_workflow"] == signoff_workflow()
    checks["option_order_is_registry_order"] = (
        tuple(doc["owner_option_order"]) == OWNER_OPTION_IDS
    )

    # -- neutrality -------------------------------------------------------
    text = _json.dumps(doc, default=float).lower()
    checks["no_steering_language"] = not any(
        p in text for p in NEUTRALITY_FORBIDDEN_PHRASES)
    tmpl = doc["decision_record_template"]
    checks["decision_fields_blank"] = all(
        tmpl[k] == "" for k in (
            "decision_option_id", "rationale", "decided_by", "decided_at",
            "peer_reviewer", "follow_up_change_record_id"))
    checks["no_recommended_key"] = not any(
        "recommend" in k.lower() or "preferred" in k.lower()
        for k in doc.keys())

    # -- self-containment (IFoA MPN s4) ------------------------------------
    checks["all_required_sections"] = all(
        s in doc for s in REQUIRED_PACK_SECTIONS)
    checks["glossary_complete"] = all(
        t in doc["glossary"] for t in REQUIRED_GLOSSARY_TERMS)
    checks["provenance_covers_headline_figures"] = all(
        k in doc["figure_provenance"] for k in (
            "governed_headline", "vine2_point", "nested_reference",
            "residual_ladder", "gap_decomposition"))
    checks["standards_cited"] = len(doc["standard_references"]) >= 3
    checks["purpose_states_residual"] = (
        f"{VINE2_COPULA_FORM_RESIDUAL_POINT:,.1f}" in doc["purpose"])

    # -- envelope ----------------------------------------------------------
    md = doc["metadata"]
    checks["pack_identity"] = (
        md["pack_id"] == PACK_DOC_ID and md["pack_version"] == PACK_DOC_VERSION)
    checks["educational_no_param_changes"] = (
        md["classification"] == "EDUCATIONAL"
        and md["no_model_parameter_changes"] is True)

    return {"checks": checks, "ok": all(checks.values()), "n_checks": len(checks)}
