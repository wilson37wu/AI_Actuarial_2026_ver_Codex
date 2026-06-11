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
