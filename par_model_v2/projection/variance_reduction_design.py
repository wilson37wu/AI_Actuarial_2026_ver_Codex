"""Post-Phase-IGUI Task 3 - pre-registration scaffold for ONE stochastic-model
improvement candidate: **inner-path antithetic / CRN variance reduction for the
TVOG estimator** (candidate id ``MR-VR-1``).

Design-note-first discipline (mirrors Phase 23..31 Task 1 builders and the
Post-Phase-IGUI Task 1 ``credentialled_residual_design`` module): this module holds
ONLY the *pre-registered specification* - the candidate identity, the frozen
cross-check references, the fixed acceptance gates, and a ``validate_design_note``
self-consistency check.  It performs **no model computation, no simulation, and no
parameter change**.  Implementation (the actual variance-reduction study) is
deferred to the FOLLOWING cycle, gated by the criteria frozen here.

Why MR-VR-1 now (sequencing of the owner-named pool):
  * MR-CAL-1 (credentialled-data calibration-residual diagnostics) is **COMPLETE**
    (Post-Phase-IGUI Task 2): margin-calibration residual = 8.15% of the nested gap,
    copula-FORM dominates at 91.85%, indicated dSCR 0.90% immaterial (not applied).
  * MR-VR-1 (this candidate) is the recorded **NEXT** candidate: a clean
    numerical-efficiency improvement to the inner-path TVOG / nested-stochastic
    estimator.  It improves COMPUTE COST and estimator variance, **not** model
    credibility - so the governed headline must stay BIT-IDENTICAL and the study is
    a DISCLOSED efficiency report, never a silent re-estimation of capital.
  * MR-LONGEV-1 (mortality-trend / longevity 5th driver) stays **DEFERRED**: it is a
    model-FORM / parameter-adding change (new driver + new correlation dimension)
    needing its own owner sign-off.

Stop-rule compliance (Phase 30, BINDING): this candidate touches **no copula
structure** and **no model parameter**.  MR-016 / MR-017 remain untouched owner
decisions; the governed frozen-t component headline 39,975.654628199336 is frozen.
A variance-reduction estimator is admissible because it only changes the *Monte
Carlo sampling scheme* of an existing estimator, not the model's distributional or
dependence form.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# --------------------------------------------------------------------------- #
# Candidate identity                                                          #
# --------------------------------------------------------------------------- #
CANDIDATE_ID = "MR-VR-1"
CANDIDATE_TITLE = (
    "Inner-path antithetic / CRN variance reduction for the TVOG estimator"
)
CANDIDATE_CLASSIFICATION = "EFFICIENCY"          # numerical-efficiency; no parameter change
CHANGE_TYPE = "governance_change"                # design-note pre-registration only
NO_MODEL_PARAMETER_CHANGES = True
TOUCHES_COPULA_STRUCTURE = False                 # Phase 30 stop-rule compliant
IMPLEMENTATION_DEFERRED = True

# The variance-reduction techniques this candidate would compare (the inner-path
# TVOG estimator is the unit under study; the baseline is crude i.i.d. MC).
VR_TECHNIQUES: Tuple[str, ...] = (
    "crude_iid",          # baseline
    "antithetic",         # paired +Z / -Z inner shocks
    "crn",                # common random numbers across guarantee on/off legs
    "sobol_qmc",          # randomised-QMC inner grid (cross-check, optional)
)

# --------------------------------------------------------------------------- #
# Frozen cross-check references (bit-identical recovery is gate G1)           #
# --------------------------------------------------------------------------- #
FROZEN_T_COMPONENT_SCR_REFERENCE = 39_975.654628199336
NESTED_PATHWISE_SCR_REFERENCE = 46_638.9

# Variance-reduction ratio precedents already recorded in the dev log for the
# OUTER aggregation basis (work-normalised, crude=1.0).  These are the empirical
# anchors the inner-path study's efficacy gate (G3) is sanity-checked against:
# Sobol-QMC has consistently helped (2.8x-7.1x), antithetic has been
# expected-INEFFECTIVE at the extreme 99.5% quantile (0.72x-0.78x).
VR_RATIO_PRECEDENTS: Dict[str, float] = {
    "sobol_qmc_p16": 7.1,
    "sobol_qmc_p18": 2.76,
    "sobol_qmc_p19_4d": 3.28,
    "sobol_qmc_p21": 4.80,
    "antithetic_p19_4d": 0.72,
    "antithetic_p21": 0.78,
}

# --------------------------------------------------------------------------- #
# Pre-registered materiality / reproducibility thresholds                     #
# --------------------------------------------------------------------------- #
BOOTSTRAP_REPLICATES_GATE = 200           # >= 200 independent replicate seeds / bootstraps
UNBIASEDNESS_TOL_REL = 0.005              # |mean(VR) - mean(crude)| <= 0.5% of crude (no bias)
ESTIMATOR_INVARIANCE_TOL = 1e-9           # governed headline bit-identical recovery
MIN_VARIANCE_REDUCTION_RATIO = 1.5        # >= 1.5x work-normalised on >=1 technique to "pass useful"
MATERIALITY_THRESHOLD_REL = 0.01          # |indicated dSCR if adopted| > 1% of headline -> open MR
NEXT_CANDIDATE_ID = "MR-LONGEV-1"         # mortality-trend / longevity 5th driver (deferred)
COMPLETED_PRIOR_CANDIDATE_ID = "MR-CAL-1" # credentialled-data calibration diagnostics (DONE)

# --------------------------------------------------------------------------- #
# Pre-registered acceptance gates (frozen NOW; no gate-shopping next cycle)   #
# --------------------------------------------------------------------------- #
def acceptance_gates() -> List[Dict[str, str]]:
    """The fixed acceptance gates the deferred implementation must meet."""
    return [
        {
            "id": "G1",
            "name": "Governed-headline invariance",
            "criterion": (
                "The governed frozen-t component SCR 39,975.654628199336 AND every "
                "governed capital output are recovered BIT-IDENTICAL "
                f"(dev <= {ESTIMATOR_INVARIANCE_TOL:g}) with the production estimator "
                "untouched. The variance-reduction estimator is ADDITIVE / DISCLOSED "
                "and never silently replaces the governed production estimator."
            ),
        },
        {
            "id": "G2",
            "name": "Estimator unbiasedness",
            "criterion": (
                "Antithetic and CRN inner-path estimators are demonstrated UNBIASED "
                "for the TVOG / SCR target: the mean over "
                f">= {BOOTSTRAP_REPLICATES_GATE} independent replicate seeds agrees with "
                f"the crude estimator within {UNBIASEDNESS_TOL_REL:.1%} of the crude mean "
                "(no systematic shift introduced by the sampling-scheme transform)."
            ),
        },
        {
            "id": "G3",
            "name": "Variance-reduction efficacy with CIs",
            "criterion": (
                "Work-normalised variance-reduction ratios (crude vs antithetic vs CRN "
                "vs optional Sobol-RQMC) are reported with "
                f">= {BOOTSTRAP_REPLICATES_GATE}-replicate CIs and an effective-sample-size "
                f"/ efficiency read-out; >= {MIN_VARIANCE_REDUCTION_RATIO:g}x on at least one "
                "technique to be declared useful. Antithetic expected-INEFFECTIVE at the "
                "extreme 99.5% quantile is DISCLOSED, consistent with the recorded "
                "outer-basis precedents (0.72x-0.78x)."
            ),
        },
        {
            "id": "G4",
            "name": "Slice-stable CRN reproducibility",
            "criterion": (
                "Inner shocks drawn via slice-stable SeedSequence spawn "
                "(SeedSequence(seed).spawn(n)[i0:i1]) so staged builds are "
                "bit-reproducible; an idempotent run digest is emitted; all seeds and "
                "the n_inner / n_outer grid are documented and version-pinned."
            ),
        },
        {
            "id": "G5",
            "name": "Adoption materiality - report not apply",
            "criterion": (
                "Any indicated change to the governed SCR from ADOPTING the "
                "variance-reduced estimator as production is REPORTED as an information "
                f"item but NOT applied. If |indicated dSCR| > {MATERIALITY_THRESHOLD_REL:.0%} "
                "of the governed headline, a new model-risk entry is OPENED rather than "
                "auto-switching the production estimator (which stays governed unless the "
                "owner adopts)."
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
        "Glasserman (2004) Monte Carlo Methods in Financial Engineering, ch. 4 "
        "(variance reduction: antithetics, common random numbers)",
        "L'Ecuyer (1994) Efficiency improvement and variance reduction; RQMC",
        "Boyle, Broadie & Glasserman (1997) Monte Carlo methods for security pricing",
        "SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation)",
        "IFoA Model Practice Note (MPN) section 4 (documentation, independent review)",
        "Solvency II Delegated Regulation Article 124 (validation standards)",
    ]


def affected_components() -> List[str]:
    return [
        "par_model_v2/projection/variance_reduction_design.py (NEW, this scaffold)",
        "tests/test_postigui_task3_design_note.py",
        "scripts/build_postigui_task3_design_note.py",
        "docs/validation/POSTIGUI_TASK3_DESIGN_NOTE.{json,md}",
        "docs/POSTIGUI_VARIANCE_REDUCTION_DESIGN_CARD.md",
    ]


def design_note() -> Dict[str, Any]:
    """Assemble the pre-registration design-note dict (no computation)."""
    return {
        "title": "Post-Phase-IGUI Task 3 - Design Note: "
                 "Inner-Path Antithetic / CRN Variance Reduction for the TVOG Estimator",
        "candidate_id": CANDIDATE_ID,
        "candidate_title": CANDIDATE_TITLE,
        "classification": CANDIDATE_CLASSIFICATION,
        "change_type": CHANGE_TYPE,
        "no_model_parameter_changes": NO_MODEL_PARAMETER_CHANGES,
        "touches_copula_structure": TOUCHES_COPULA_STRUCTURE,
        "implementation_deferred": IMPLEMENTATION_DEFERRED,
        "vr_techniques": list(VR_TECHNIQUES),
        "frozen_references": {
            "frozen_t_component_scr": FROZEN_T_COMPONENT_SCR_REFERENCE,
            "nested_pathwise_scr": NESTED_PATHWISE_SCR_REFERENCE,
            "vr_ratio_precedents": VR_RATIO_PRECEDENTS,
        },
        "context": (
            "MR-CAL-1 (credentialled-data calibration-residual diagnostics) COMPLETED at "
            "Post-Phase-IGUI Task 2: the margin-calibration residual is only 8.15% of the "
            "gap to nested, copula-FORM dominates at 91.85%, and the indicated dSCR (0.90%) "
            "was immaterial and not applied. With model FORM frozen under the Phase 30 "
            "binding stop-rule, the next worthwhile improvement is NUMERICAL, not "
            "structural: the inner-path / nested-stochastic TVOG estimator is the most "
            "compute-intensive part of the run, and its Monte Carlo variance directly sets "
            "how many inner paths are needed for a stable SCR. Antithetic pairing and "
            "common-random-numbers (CRN) across the guarantee-on / guarantee-off legs are "
            "the standard, bias-free variance-reduction levers. The recorded outer-basis "
            "precedents show Sobol-RQMC helps (2.8x-7.1x) while antithetic is "
            "expected-ineffective at the extreme 99.5% quantile (0.72x-0.78x) - so the "
            "study must MEASURE, not assume, the inner-path efficacy, with CIs."
        ),
        "scope_deferred_next_cycle": [
            "A DISCLOSED efficiency study on the inner-path TVOG estimator comparing "
            "crude i.i.d. MC against antithetic, CRN, and (optional) Sobol-RQMC inner "
            "sampling, all on the SAME governed outer states.",
            "Unbiasedness evidence: mean over >= 200 independent replicate seeds for each "
            "scheme agrees with crude within 0.5%, so no scheme shifts the estimate.",
            "Work-normalised variance-reduction ratios and effective-sample-size with "
            ">= 200-replicate CIs; the inner-path count n* needed for a target SE under "
            "each scheme.",
            "A DISCLOSED report + optional ADDITIVE offline-UI surface; the governed "
            "production estimator and headline SCR stay bit-identical (NOT an adoption).",
        ],
        "acceptance_gates": acceptance_gates(),
        "candidate_sequencing": {
            "selected_now": CANDIDATE_ID,
            "completed_prior": COMPLETED_PRIOR_CANDIDATE_ID,
            "next_candidate": NEXT_CANDIDATE_ID,
            "rationale": (
                "(c) inner-path antithetic/CRN variance reduction is the recorded NEXT "
                "candidate after MR-CAL-1 completed; it is diagnostics/efficiency-only "
                "(cleanest stop-rule compliance, no parameter change, no copula structure). "
                "(a) longevity 5th-driver (MR-LONGEV-1) remains a parameter-adding "
                "model-FORM change deferred to a dedicated owner-sign-off cycle."
            ),
        },
        "stop_rule_compliance": (
            "No copula structure and no model parameter touched; only the Monte Carlo "
            "sampling scheme of an existing estimator changes; MR-016/MR-017 untouched; "
            "governed headline frozen. Admissible under the Phase 30 binding stop-rule "
            "(bars new copula-structure candidates only)."
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
    checks["four_vr_techniques"] = len(note.get("vr_techniques", [])) == 4
    checks["crude_baseline_present"] = "crude_iid" in note.get("vr_techniques", [])
    fr = note.get("frozen_references", {})
    checks["headline_frozen"] = (
        fr.get("frozen_t_component_scr") == FROZEN_T_COMPONENT_SCR_REFERENCE
    )
    checks["nested_ref"] = fr.get("nested_pathwise_scr") == NESTED_PATHWISE_SCR_REFERENCE
    checks["vr_precedents_present"] = len(fr.get("vr_ratio_precedents", {})) >= 4
    gates = note.get("acceptance_gates", [])
    checks["six_gates"] = len(gates) == 6
    checks["gate_ids"] = [g["id"] for g in gates] == ["G1", "G2", "G3", "G4", "G5", "G6"]
    checks["g1_invariance"] = any(
        "BIT-IDENTICAL" in g["criterion"] and g["id"] == "G1" for g in gates
    )
    checks["g2_unbiasedness"] = any(
        g["id"] == "G2" and "UNBIASED" in g["criterion"] for g in gates
    )
    checks["sequencing_present"] = bool(note.get("candidate_sequencing"))
    checks["standards_cited"] = len(note.get("standard_references", [])) >= 5
    ok = all(bool(v) for v in checks.values())
    return {"ok": ok, "n_checks": len(checks), "checks": checks}
