"""Post-Phase-IGUI Task 1 - pre-registration scaffold for ONE stochastic-model
improvement candidate: **credentialled-data calibration-residual diagnostics on
the frozen margins** (candidate id ``MR-CAL-1``).

Design-note-first discipline (mirrors Phase 23..31 Task 1 builders): this module
holds ONLY the *pre-registered specification* - the candidate identity, the frozen
cross-check references, the fixed acceptance gates, and a ``validate_design_note``
self-consistency check.  It performs **no model computation, no calibration, and
no parameter change**.  Implementation (the actual diagnostics run) is deferred to
the FOLLOWING cycle, gated by the criteria frozen here.

Stop-rule compliance (Phase 30, BINDING): this candidate touches **no copula
structure** and **no model parameter**.  MR-016 / MR-017 remain untouched owner
decisions; the governed frozen-t component headline 39,975.654628199336 is frozen.
The candidate is therefore admissible under the binding stop-rule, which bars new
*copula-structure* candidates only.

Why this candidate (over the other two in the owner-named pool):
  * (a) mortality-trend / longevity 5th-driver extension is a model-FORM /
    parameter-adding change (new driver + new correlation dimension) - higher owner
    risk and a dependence-dimension change; it needs its own owner sign-off and is
    deferred as a future candidate.
  * (c) inner-path variance-reduction (antithetic / CRN) for TVOG is a clean
    numerical-efficiency improvement and the recorded NEXT candidate, but it
    improves compute cost, not model credibility.  The standing roadmap names the
    *credentialled-data calibration priority* as the live priority once the
    dependence-FORM escalation ended at the Phase 30 stop-rule, so (b) is sequenced
    first.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# --------------------------------------------------------------------------- #
# Candidate identity                                                          #
# --------------------------------------------------------------------------- #
CANDIDATE_ID = "MR-CAL-1"
CANDIDATE_TITLE = (
    "Credentialled-data calibration-residual diagnostics on the frozen margins"
)
CANDIDATE_CLASSIFICATION = "EDUCATIONAL"        # diagnostics-only; no parameter change
CHANGE_TYPE = "governance_change"               # design-note pre-registration only
NO_MODEL_PARAMETER_CHANGES = True
TOUCHES_COPULA_STRUCTURE = False                # Phase 30 stop-rule compliant
IMPLEMENTATION_DEFERRED = True

# The seven FROZEN standalone risk-driver margins this candidate would diagnose
# (order per par_model_v2.projection.vine_copula_upgrade.DRIVER_NAMES).
FROZEN_DRIVER_MARGINS: Tuple[str, ...] = (
    "rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity",
)

# --------------------------------------------------------------------------- #
# Frozen cross-check references (bit-identical recovery is gate G1)           #
# --------------------------------------------------------------------------- #
FROZEN_T_COMPONENT_SCR_REFERENCE = 39_975.654628199336
NESTED_PATHWISE_SCR_REFERENCE = 46_638.9

# Copula-FORM residual ladder (abs) - the dependence-form gap already quantified
# across Phases 26-29.  The calibration-residual diagnostics decompose the
# *remaining* gap to nested into a MARGIN-calibration part and this copula-FORM
# part, so the owner can see which side the residual lives on.
COPULA_FORM_RESIDUAL_LADDER: Dict[str, float] = {
    "grouped_t": 10_491.5,
    "frozen_t": 6_120.196568775231,
    "skew_t": 6_114.9,
    "vine2": 3_637.298487404965,
}

# --------------------------------------------------------------------------- #
# Pre-registered materiality / reproducibility thresholds                     #
# --------------------------------------------------------------------------- #
BOOTSTRAP_REPLICATES_GATE = 200
BOOTSTRAP_SE_GATE = 0.05                  # <= 5% of the mean
FROZEN_MARGIN_INVARIANCE_TOL = 1e-9       # bit-identical recovery tolerance
MATERIALITY_THRESHOLD_REL = 0.01          # |indicated dSCR| > 1% of headline -> open MR
NEXT_CANDIDATE_ID = "MR-VR-1"             # inner-path antithetic/CRN variance reduction
DEFERRED_CANDIDATE_ID = "MR-LONGEV-1"     # mortality-trend / longevity 5th driver

# --------------------------------------------------------------------------- #
# Pre-registered acceptance gates (frozen NOW; no gate-shopping next cycle)   #
# --------------------------------------------------------------------------- #
def acceptance_gates() -> List[Dict[str, str]]:
    """The fixed acceptance gates the deferred implementation must meet."""
    return [
        {
            "id": "G1",
            "name": "Frozen-margin + headline invariance",
            "criterion": (
                "Every frozen marginal calibration parameter AND the governed "
                "frozen-t component SCR 39,975.654628199336 recovered BIT-IDENTICAL "
                f"(dev <= {FROZEN_MARGIN_INVARIANCE_TOL:g}) BEFORE and AFTER the "
                "diagnostics run. Diagnostics must not perturb any margin or output."
            ),
        },
        {
            "id": "G2",
            "name": "Credentialled-reference provenance",
            "criterion": (
                "The credentialled reference dataset is documented (source, vintage, "
                "n, credential/licence basis) and version-pinned. If no external "
                "credentialled dataset is available in-sandbox, a clearly-labelled "
                "SYNTHETIC credentialled-reference stub with the same interface is "
                "used and the report is marked EDUCATIONAL/illustrative (GBM ESG-stub "
                "precedent)."
            ),
        },
        {
            "id": "G3",
            "name": "Leakage-free goodness-of-fit",
            "criterion": (
                "PIT/Rosenblatt uniformity, QQ, KS and Anderson-Darling on a "
                "documented fit/holdout split; GoF statistics computed on holdout, "
                f">= {BOOTSTRAP_REPLICATES_GATE} bootstrap replicates, SE "
                f"<= {BOOTSTRAP_SE_GATE:.0%} of the mean, SCR-relevant tail quantiles "
                "reported with CIs."
            ),
        },
        {
            "id": "G4",
            "name": "Residual decomposition reconciliation",
            "criterion": (
                "calibration-residual + copula-FORM residual reconcile to the total "
                "gap vs nested 46,638.9 within a pre-stated tolerance; decomposition "
                "DISCLOSED; the governed headline does NOT move."
            ),
        },
        {
            "id": "G5",
            "name": "Credibility quantification - report not apply",
            "criterion": (
                "Partial-credibility Z (Buhlmann-Straub / limited-fluctuation) and the "
                "credibility-weighted indicated margin shift are REPORTED as an "
                "information item but NOT applied. Any indicated |dSCR| > "
                f"{MATERIALITY_THRESHOLD_REL:.0%} of the governed headline OPENS a new "
                "model-risk entry (OPEN) rather than triggering recalibration."
            ),
        },
        {
            "id": "G6",
            "name": "Governance + offline-UI discipline",
            "criterion": (
                "Idempotent run digest; governance_change / methodology_change "
                "ChangeRecord left OWNER_REVIEW; unit tests added; if an offline-UI "
                "surface is added it is an ADDITIVE contract bump only, self-tests "
                "ok:true 0 network / 0 JS errors, 0 external refs, every pre-existing "
                "key bit-identical."
            ),
        },
    ]


def standard_references() -> List[str]:
    return [
        "SOA ASOP 25 (Credibility Procedures)",
        "SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation)",
        "IFoA Model Practice Note (MPN) section 4 (documentation, independent review)",
        "Solvency II Delegated Regulation Article 124 (validation standards)",
        "Buhlmann & Straub (1970) credibility; limited-fluctuation (Mowbray) credibility",
        "Rosenblatt (1952) PIT; Anderson-Darling / Kolmogorov-Smirnov goodness-of-fit",
    ]


def affected_components() -> List[str]:
    return [
        "par_model_v2/calibration/credentialled_residual_design.py (NEW, this scaffold)",
        "tests/test_postigui_task1_design_note.py",
        "scripts/build_postigui_task1_design_note.py",
        "docs/validation/POSTIGUI_TASK1_DESIGN_NOTE.{json,md}",
        "docs/POSTIGUI_CREDENTIALLED_CALIBRATION_DESIGN_CARD.md",
    ]


def design_note() -> Dict[str, Any]:
    """Assemble the pre-registration design-note dict (no computation)."""
    return {
        "title": "Post-Phase-IGUI Task 1 - Design Note: "
                 "Credentialled-Data Calibration-Residual Diagnostics (frozen margins)",
        "candidate_id": CANDIDATE_ID,
        "candidate_title": CANDIDATE_TITLE,
        "classification": CANDIDATE_CLASSIFICATION,
        "change_type": CHANGE_TYPE,
        "no_model_parameter_changes": NO_MODEL_PARAMETER_CHANGES,
        "touches_copula_structure": TOUCHES_COPULA_STRUCTURE,
        "implementation_deferred": IMPLEMENTATION_DEFERRED,
        "frozen_driver_margins": list(FROZEN_DRIVER_MARGINS),
        "frozen_references": {
            "frozen_t_component_scr": FROZEN_T_COMPONENT_SCR_REFERENCE,
            "nested_pathwise_scr": NESTED_PATHWISE_SCR_REFERENCE,
            "copula_form_residual_ladder": COPULA_FORM_RESIDUAL_LADDER,
        },
        "context": (
            "Phase 30 applied the BINDING STOP-RULE: dependence-FORM escalation under "
            "MR-016 ENDS; MR-016/MR-017 stay OPEN owner decisions; candidates are "
            "DISCLOSED, not adopted. The standing roadmap names the credentialled-data "
            "calibration priority as the live next priority. The seven standalone "
            "risk-driver margins are FROZEN, but the calibration residual of those "
            "frozen margins against a credentialled reference has never been quantified. "
            "Diagnostics-first (exactly as the dependence work was diagnostics-first): "
            "MEASURE the calibration residual before any recalibration could ever be "
            "contemplated."
        ),
        "scope_deferred_next_cycle": [
            "Diagnostics-only module computing each frozen driver margin's calibration "
            "residual against a credentialled reference (credibility framing: the "
            "credentialled dataset is the reference, the model margin is the prior).",
            "Distributional GoF on the frozen margins: PIT/Rosenblatt uniformity, QQ, "
            "KS, Anderson-Darling with bootstrap CIs; SCR-relevant tail quantiles.",
            "Residual decomposition separating margin-calibration residual from the "
            "already-quantified copula-FORM residual, reconciled to the gap vs nested.",
            "A DISCLOSED report + optional ADDITIVE offline-UI surface; frozen margins "
            "stay bit-identical (NOT a recalibration).",
        ],
        "acceptance_gates": acceptance_gates(),
        "candidate_sequencing": {
            "selected_now": CANDIDATE_ID,
            "next_candidate": NEXT_CANDIDATE_ID,
            "deferred_candidate": DEFERRED_CANDIDATE_ID,
            "rationale": (
                "(b) credentialled-data calibration is the live roadmap priority after "
                "the dependence stop-rule, is diagnostics-only (cleanest stop-rule "
                "compliance, no parameter change). (c) inner-path antithetic/CRN "
                "variance reduction is the recorded NEXT candidate. (a) longevity "
                "5th-driver is a parameter-adding model-FORM change deferred to a "
                "dedicated owner-sign-off cycle."
            ),
        },
        "stop_rule_compliance": (
            "No copula structure and no model parameter touched; MR-016/MR-017 "
            "untouched; governed headline frozen. Admissible under the Phase 30 "
            "binding stop-rule (bars new copula-structure candidates only)."
        ),
        "standard_references": standard_references(),
        "affected_components": affected_components(),
    }


def validate_design_note(note: Dict[str, Any]) -> Dict[str, Any]:
    """Self-consistency gate over the pre-registration (no computation)."""
    checks: Dict[str, bool] = {}
    checks["candidate_id"] = note.get("candidate_id") == CANDIDATE_ID
    checks["no_param_change"] = note.get("no_model_parameter_changes") is True
    checks["stop_rule_no_copula"] = note.get("touches_copula_structure") is False
    checks["implementation_deferred"] = note.get("implementation_deferred") is True
    checks["change_type_governance"] = note.get("change_type") == "governance_change"
    checks["seven_frozen_margins"] = len(note.get("frozen_driver_margins", [])) == 7
    fr = note.get("frozen_references", {})
    checks["headline_frozen"] = (
        fr.get("frozen_t_component_scr") == FROZEN_T_COMPONENT_SCR_REFERENCE
    )
    checks["nested_ref"] = fr.get("nested_pathwise_scr") == NESTED_PATHWISE_SCR_REFERENCE
    checks["residual_ladder_4"] = len(fr.get("copula_form_residual_ladder", {})) == 4
    gates = note.get("acceptance_gates", [])
    checks["six_gates"] = len(gates) == 6
    checks["gate_ids"] = [g["id"] for g in gates] == ["G1", "G2", "G3", "G4", "G5", "G6"]
    checks["g1_invariance"] = any(
        "BIT-IDENTICAL" in g["criterion"] and g["id"] == "G1" for g in gates
    )
    checks["sequencing_present"] = bool(note.get("candidate_sequencing"))
    checks["standards_cited"] = len(note.get("standard_references", [])) >= 5
    ok = all(bool(v) for v in checks.values())
    return {"ok": ok, "n_checks": len(checks), "checks": checks}
