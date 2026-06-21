"""Post-Phase-IGUI Task 6 - pre-registration scaffold for ONE stochastic-model
improvement candidate: **RQMC + control-variates variance reduction for the OUTER
capital (SCR) loop** (candidate id ``MR-VR-2``).

Design-note-first discipline (mirrors Phase 23..31 Task 1 builders, the
Post-Phase-IGUI Task 1 ``credentialled_residual_design`` and Task 3
``variance_reduction_design`` modules): this module holds ONLY the *pre-registered
specification* - the candidate identity, the frozen cross-check references, the
fixed acceptance gates, and a ``validate_design_note`` self-consistency check.  It
performs **no model computation, no simulation, and no parameter change**.
Implementation (the actual outer-loop variance-reduction study) is deferred to the
FOLLOWING cycle, gated by the criteria frozen here.

Why MR-VR-2 now (sequencing of the owner-named pool):
  * MR-CAL-1 (credentialled-data calibration-residual diagnostics) is **COMPLETE**
    (Post-Phase-IGUI Task 2): margin-calibration residual = 8.15% of the nested gap,
    copula-FORM dominates at 91.85%, indicated dSCR 0.90% immaterial (not applied).
  * MR-VR-1 (inner-path antithetic / CRN / RQMC variance reduction for the TVOG
    estimator) is **COMPLETE** (Post-Phase-IGUI Task 4, surfaced offline at Task 5):
    Sobol-RQMC 2241x / CRN 18.9x / antithetic 1.88x on the mean-TVOG target; the
    99.5% quantile was where antithetic went INEFFECTIVE (1.31x).  MR-VR-1 attacked
    the INNER path; it explicitly did NOT address the OUTER capital loop whose target
    IS the 99.5% quantile.
  * MR-VR-2 (this candidate) is the recorded **NEXT** efficiency candidate: it
    attacks the OUTER capital / SCR loop - the 99.5% tail estimator over the governed
    outer scenario set - with the two levers that *do* help a tail target: scrambled
    Sobol randomised-QMC on the outer scenario grid and a CONTROL VARIATE built from
    the cheap closed-form / proxy SCR that is already computed alongside the nested
    estimate.  It improves COMPUTE COST and estimator variance, **not** model
    credibility - so the governed headline must stay BIT-IDENTICAL and the study is a
    DISCLOSED efficiency report, never a silent re-estimation of capital.
  * MR-LONGEV-1 (mortality-trend / longevity 5th driver) stays **DEFERRED**: it is a
    model-FORM / parameter-adding change (new driver + new correlation dimension)
    needing its own owner sign-off.

Stop-rule compliance (Phase 30, BINDING): this candidate touches **no copula
structure** and **no model parameter**.  MR-016 / MR-017 remain untouched owner
decisions; the governed frozen-t component headline 39,975.654628199336 is frozen.
An outer-loop variance-reduction estimator is admissible because it only changes the
*Monte Carlo sampling scheme* (RQMC point set) and adds an unbiased *control variate*
to an existing estimator, not the model's distributional or dependence form.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# --------------------------------------------------------------------------- #
# Candidate identity                                                          #
# --------------------------------------------------------------------------- #
CANDIDATE_ID = "MR-VR-2"
CANDIDATE_TITLE = (
    "RQMC + control-variates variance reduction for the OUTER capital (SCR) loop"
)
CANDIDATE_CLASSIFICATION = "EFFICIENCY"          # numerical-efficiency; no parameter change
CHANGE_TYPE = "governance_change"                # design-note pre-registration only
NO_MODEL_PARAMETER_CHANGES = True
TOUCHES_COPULA_STRUCTURE = False                 # Phase 30 stop-rule compliant
IMPLEMENTATION_DEFERRED = True

# The variance-reduction techniques this candidate would compare on the OUTER loop
# (the SCR / 99.5% tail estimator is the unit under study; baseline is crude i.i.d.
# MC over the governed outer scenario set).  Antithetic is deliberately NOT a primary
# lever here: MR-VR-1 already recorded it as INEFFECTIVE at the 99.5% quantile, which
# is exactly the OUTER-loop target.
VR_TECHNIQUES: Tuple[str, ...] = (
    "crude_iid",          # baseline: i.i.d. MC over the governed outer scenario set
    "sobol_rqmc",         # scrambled Sobol randomised-QMC outer scenario grid
    "control_variate",    # cheap closed-form / proxy SCR as an unbiased control variate
    "stratified",         # proportional stratification of the outer tail (cross-check, optional)
)

# --------------------------------------------------------------------------- #
# Frozen cross-check references (bit-identical recovery is gate G1)           #
# --------------------------------------------------------------------------- #
FROZEN_T_COMPONENT_SCR_REFERENCE = 39_975.654628199336
NESTED_PATHWISE_SCR_REFERENCE = 46_638.9

# Variance-reduction efficacy already MEASURED by the completed MR-VR-1 inner-path
# study (Post-Phase-IGUI Task 4).  These are the empirical anchors the outer-loop
# study's efficacy gate (G3) is sequenced against - and the reason antithetic is not
# a primary outer-loop lever (it went ineffective at the 99.5% quantile):
INNER_LOOP_VR_RESULTS: Dict[str, float] = {
    "sobol_rqmc_mean_tvog": 2241.0,   # MR-VR-1 Sobol-RQMC, mean-TVOG target
    "crn_mean_tvog": 18.9,            # MR-VR-1 CRN, mean-TVOG target
    "antithetic_mean_tvog": 1.88,     # MR-VR-1 antithetic, mean-TVOG target
    "antithetic_q995": 1.31,          # MR-VR-1 antithetic at 99.5% quantile (INEFFECTIVE, <1.5x)
}

# Outer-basis RQMC precedents recorded across earlier phases (work-normalised,
# crude=1.0): scrambled-Sobol has consistently helped on the OUTER aggregation basis.
OUTER_RQMC_PRECEDENTS: Dict[str, float] = {
    "sobol_qmc_p16": 7.1,
    "sobol_qmc_p18": 2.76,
    "sobol_qmc_p19_4d": 3.28,
    "sobol_qmc_p21": 4.80,
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
COMPLETED_PRIOR_CANDIDATE_ID = "MR-VR-1"  # inner-path antithetic/CRN/RQMC variance reduction (DONE)
COMPLETED_POOL: Tuple[str, ...] = ("MR-CAL-1", "MR-VR-1")  # both prior efficiency/diagnostic candidates


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
                "untouched. The outer-loop RQMC / control-variate estimator is "
                "ADDITIVE / DISCLOSED and never silently replaces the governed "
                "production estimator."
            ),
        },
        {
            "id": "G2",
            "name": "Estimator unbiasedness (control variate + RQMC)",
            "criterion": (
                "The control-variate estimator is demonstrated UNBIASED for the SCR / "
                "99.5% tail target - the control coefficient beta is estimated on a "
                "held-out pilot so the variate adds NO bias - and the scrambled-Sobol "
                "RQMC mean over "
                f">= {BOOTSTRAP_REPLICATES_GATE} independent scramble seeds agrees with "
                f"the crude estimator within {UNBIASEDNESS_TOL_REL:.1%} of the crude mean "
                "(no systematic shift introduced by the sampling-scheme transform)."
            ),
        },
        {
            "id": "G3",
            "name": "Variance-reduction efficacy with CIs (tail target)",
            "criterion": (
                "Work-normalised variance-reduction ratios (crude vs scrambled-Sobol "
                "RQMC vs control-variate vs optional stratified) for the OUTER 99.5% "
                "SCR target are reported with "
                f">= {BOOTSTRAP_REPLICATES_GATE}-replicate CIs and an effective-sample-size "
                f"/ efficiency read-out; >= {MIN_VARIANCE_REDUCTION_RATIO:g}x on at least one "
                "technique to be declared useful. Because the OUTER target IS the 99.5% "
                "quantile - where MR-VR-1 recorded antithetic as INEFFECTIVE (1.31x) - "
                "the study MEASURES, never assumes, tail efficacy; the control-variate "
                "correlation rho and realised reduction 1/(1-rho^2) are disclosed."
            ),
        },
        {
            "id": "G4",
            "name": "Slice-stable RQMC reproducibility",
            "criterion": (
                "Scrambled-Sobol outer point sets drawn via slice-stable SeedSequence "
                "spawn (SeedSequence(seed).spawn(n)[i0:i1]) so staged builds are "
                "bit-reproducible; the scramble seed, Sobol dimension, and outer/inner "
                "grid are documented and version-pinned; an idempotent run digest is "
                "emitted."
            ),
        },
        {
            "id": "G5",
            "name": "Adoption materiality - report not apply",
            "criterion": (
                "Any indicated change to the governed SCR from ADOPTING the "
                "variance-reduced outer estimator as production is REPORTED as an "
                "information item but NOT applied. If |indicated dSCR| > "
                f"{MATERIALITY_THRESHOLD_REL:.0%} of the governed headline, a new "
                "model-risk entry is OPENED rather than auto-switching the production "
                "estimator (which stays governed unless the owner adopts)."
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
        "(control variates) and ch. 5 (quasi-Monte Carlo)",
        "L'Ecuyer (1994) Efficiency improvement and variance reduction; RQMC",
        "Owen (1997) Scrambled net variance for integrals of smooth functions",
        "Bauer, Reuss & Singer (2012) On the calculation of the Solvency Capital "
        "Requirement based on nested simulations (outer-loop efficiency)",
        "SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation)",
        "IFoA Model Practice Note (MPN) section 4 (documentation, independent review)",
        "Solvency II Delegated Regulation Article 124 (validation standards)",
    ]


def affected_components() -> List[str]:
    return [
        "par_model_v2/projection/outer_loop_efficiency_design.py (NEW, this scaffold)",
        "tests/test_postigui_task6_design_note.py",
        "scripts/build_postigui_task6_design_note.py",
        "docs/validation/POSTIGUI_TASK6_DESIGN_NOTE.{json,md}",
        "docs/POSTIGUI_OUTER_LOOP_EFFICIENCY_DESIGN_CARD.md",
    ]


def design_note() -> Dict[str, Any]:
    """Assemble the pre-registration design-note dict (no computation)."""
    return {
        "title": "Post-Phase-IGUI Task 6 - Design Note: "
                 "RQMC + Control-Variates Variance Reduction for the OUTER Capital (SCR) Loop",
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
            "inner_loop_vr_results": INNER_LOOP_VR_RESULTS,
            "outer_rqmc_precedents": OUTER_RQMC_PRECEDENTS,
        },
        "context": (
            "Both prior diagnostics/efficiency candidates are COMPLETE: MR-CAL-1 "
            "(credentialled-data calibration residuals, Task 2) and MR-VR-1 (inner-path "
            "antithetic/CRN/RQMC variance reduction for the TVOG estimator, Task 4, "
            "surfaced offline at Task 5). MR-VR-1 delivered large gains on the MEAN-TVOG "
            "target (Sobol-RQMC 2241x, CRN 18.9x, antithetic 1.88x) but explicitly left "
            "the OUTER capital loop untouched, and recorded that antithetic is "
            "INEFFECTIVE (1.31x) precisely at the 99.5% quantile - which is the OUTER "
            "loop's target. The remaining admissible numerical gain is therefore on the "
            "OUTER SCR estimator: the 99.5% tail over the governed outer scenario set. "
            "Two levers suit a tail target without introducing bias: scrambled-Sobol "
            "randomised-QMC over the outer scenario grid (precedented at 2.76x-7.1x on "
            "the outer aggregation basis), and a CONTROL VARIATE formed from the cheap "
            "closed-form / proxy SCR already computed alongside the nested estimate "
            "(variance falls by 1/(1-rho^2) for control-target correlation rho, with NO "
            "bias once beta is fit out-of-sample). With model FORM frozen under the "
            "Phase 30 binding stop-rule, this is a NUMERICAL improvement only: the study "
            "must MEASURE - with CIs - whether RQMC and the control variate actually cut "
            "outer-loop variance at the 99.5% quantile, and the governed production "
            "estimator and headline SCR stay BIT-IDENTICAL."
        ),
        "scope_deferred_next_cycle": [
            "A DISCLOSED efficiency study on the OUTER capital / SCR loop comparing "
            "crude i.i.d. MC against scrambled-Sobol RQMC, a closed-form/proxy control "
            "variate, and (optional) proportional tail stratification - all targeting "
            "the governed 99.5% SCR over the SAME governed model.",
            "Unbiasedness evidence: control-variate beta fit on a held-out pilot so it "
            "adds no bias, and the RQMC mean over >= 200 independent scramble seeds "
            "agrees with crude within 0.5%.",
            "Work-normalised variance-reduction ratios and effective-sample-size with "
            ">= 200-replicate CIs at the 99.5% target; the outer scenario count n* needed "
            "for a target SCR standard error under each scheme; the disclosed "
            "control-target correlation rho and realised reduction 1/(1-rho^2).",
            "A DISCLOSED report + optional ADDITIVE offline-UI surface; the governed "
            "production estimator and headline SCR stay bit-identical (NOT an adoption).",
        ],
        "acceptance_gates": acceptance_gates(),
        "candidate_sequencing": {
            "selected_now": CANDIDATE_ID,
            "completed_prior": COMPLETED_PRIOR_CANDIDATE_ID,
            "completed_pool": list(COMPLETED_POOL),
            "next_candidate": NEXT_CANDIDATE_ID,
            "rationale": (
                "(c) OUTER-loop RQMC + control-variates is the recorded NEXT efficiency "
                "candidate after MR-VR-1 completed the INNER path; it is "
                "diagnostics/efficiency-only (cleanest stop-rule compliance, no parameter "
                "change, no copula structure) and it directly attacks the 99.5% tail "
                "target that the inner-path antithetic lever could not. (a) longevity "
                "5th-driver (MR-LONGEV-1) remains a parameter-adding model-FORM change "
                "deferred to a dedicated owner-sign-off cycle; (b) a packaging A/B/C "
                "pivot remains available to the owner but is not a model-improvement "
                "candidate."
            ),
        },
        "stop_rule_compliance": (
            "No copula structure and no model parameter touched; only the Monte Carlo "
            "sampling scheme (RQMC point set) of an existing estimator changes and an "
            "unbiased control variate is added; MR-016/MR-017 untouched; governed "
            "headline frozen. Admissible under the Phase 30 binding stop-rule (which "
            "bars new copula-structure candidates only)."
        ),
        "owner_decision_note": (
            "The diagnostics/efficiency pool is NOT yet exhausted: MR-VR-2 (this "
            "candidate) is a clean, admissible numerical-efficiency improvement on the "
            "outer loop. After MR-VR-2, the pool of stop-rule-admissible "
            "efficiency/diagnostic work narrows materially, and the next substantive "
            "model improvement (MR-LONGEV-1 longevity 5th driver) is a parameter-adding "
            "model-FORM change requiring explicit owner sign-off - it is NOT auto-run. "
            "Owner options recorded for the cycle after MR-VR-2: (1) sign off MR-LONGEV-1; "
            "(2) pivot to packaging A/B/C build-spec / CI release-matrix; (3) declare the "
            "auto-development frontier complete and freeze."
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
    checks["rqmc_present"] = "sobol_rqmc" in note.get("vr_techniques", [])
    checks["control_variate_present"] = "control_variate" in note.get("vr_techniques", [])
    fr = note.get("frozen_references", {})
    checks["headline_frozen"] = (
        fr.get("frozen_t_component_scr") == FROZEN_T_COMPONENT_SCR_REFERENCE
    )
    checks["nested_ref"] = fr.get("nested_pathwise_scr") == NESTED_PATHWISE_SCR_REFERENCE
    checks["inner_loop_results_present"] = len(fr.get("inner_loop_vr_results", {})) >= 4
    checks["antithetic_q995_ineffective"] = (
        fr.get("inner_loop_vr_results", {}).get("antithetic_q995", 9.9)
        < MIN_VARIANCE_REDUCTION_RATIO
    )
    checks["outer_precedents_present"] = len(fr.get("outer_rqmc_precedents", {})) >= 4
    gates = note.get("acceptance_gates", [])
    checks["six_gates"] = len(gates) == 6
    checks["gate_ids"] = [g["id"] for g in gates] == ["G1", "G2", "G3", "G4", "G5", "G6"]
    checks["g1_invariance"] = any(
        "BIT-IDENTICAL" in g["criterion"] and g["id"] == "G1" for g in gates
    )
    checks["g2_unbiasedness"] = any(
        g["id"] == "G2" and "UNBIASED" in g["criterion"] for g in gates
    )
    seq = note.get("candidate_sequencing", {})
    checks["sequencing_present"] = bool(seq)
    checks["completed_prior_vr1"] = seq.get("completed_prior") == COMPLETED_PRIOR_CANDIDATE_ID
    checks["next_longev"] = seq.get("next_candidate") == NEXT_CANDIDATE_ID
    checks["standards_cited"] = len(note.get("standard_references", [])) >= 5
    ok = all(bool(v) for v in checks.values())
    return {"ok": ok, "n_checks": len(checks), "checks": checks}
