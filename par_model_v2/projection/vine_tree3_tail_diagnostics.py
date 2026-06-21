"""Phase 30 Task 4 - tree-3 vine pair-level tail diagnostics, fit-vs-holdout
overfit check, and the binding STOP-RULE / MR-016 / MR-017 decision.

This task introduces NO new model parameter.  It REPORTS the per-pair upper
(lambda_U proxy) and lower (lambda_L proxy) tail co-dependence of the FROZEN
Phase 30 Task 2 tree-3 candidate draw against the frozen single-df t boundary
on COMMON random numbers, for

* the six FIRST-tree (credit-root) links (unconditional pair events),
* the five SECOND-tree links (events conditional on the root upper tail),
* the four THIRD-tree links (events conditional on the JOINT upper tail of
  both pre-registered conditioners, matching the Phase 30 Task 2
  joint-conditional fit), and
* the three pre-registered HOLDOUT pairs (never used in family selection),

re-drawn replicate-by-replicate at the Phase 30 Task 3 bootstrap seeds (the
per-replicate SeedSequence spawn of master seed 20260611 is reproduced
exactly, so the recomputed tree-3 / 2-tree vine / frozen-t component SCRs
cross-check BIT-identically against the archived Task 3 records and the
aggregate CI).  The 2-tree vine boundary leg is carried through every
replicate to RE-VERIFY the zero-strength bit-identity contract (tree-3 ==
2-tree vine, uniforms AND SCRs) across the full bootstrap distribution.

Fit-vs-holdout OVERFIT check (pre-registered, Task 4 block of the Phase 30
Task 1 design note; concentration gate as P29 T4): (a) DISCLOSURE - all
three holdout pairs reported with upper AND lower lift (candidate - frozen,
CRN) and a 95% CI at every grid level; (b) CONCENTRATION - the largest
holdout-pair |mean lift| must not exceed the largest fitted-pair |mean lift|
(fitted = tree-1 + tree-2 + tree-3 links).  The holdout-to-fit max-lift
ratio is DISCLOSED against the P29 reference 0.049.

BINDING STOP-RULE / MR DECISION (pre-registered, PHASE30_TASK1_DESIGN_NOTE):
mitigate MR-016 / MR-017 ONLY IF nested 46,638.9 lies INSIDE the Task 3
tree-3 95% bootstrap CI AND the copula-form residual shrinks STRICTLY below
the 2-tree vine residual 3,637.298487404965 (design-note rounding 3,637.3).
NEITHER criterion is met: the tree-3 candidate is BIT-IDENTICAL to the
2-tree vine (all four pre-registered third-tree pairs fitted gaussian / zero
strength), so the residual is UNCHANGED (not strictly smaller), and nested
46,638.9 is OUTSIDE [38,593.7, 44,556.4].  Therefore MR-016 and MR-017 KEEP
OPEN and the STOP-RULE IS APPLIED: dependence-FORM escalation under MR-016
ENDS - no further copula-structure candidates may be opened without owner
sign-off, and Phase 31 becomes the owner decision package (design-note
option C).  MR-010 / MR-014 are refreshed ONLY IF the GOVERNED headline
(frozen single-df t 39,975.654628199336) moves > 1%: it does NOT move (the
boundary is recovered bit-identically; nothing is adopted), so NO refresh.

EDUCATIONAL MODEL: educational placeholders pending credentialled data and
independent APS X2 review.  NOT for production capital decisions.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from par_model_v2.projection.grouped_t_tail_diagnostics import summarise_metric
from par_model_v2.projection.joint_action_aggregation import JointActionAggregator
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.vine_copula_pair_aggregation import (
    TAIL_LEVEL_P,
    _conditional_mask,
    _tail_codependence,
)
from par_model_v2.projection.vine_copula_upgrade import (
    EXISTING_RISK_ID,
    FIRST_TREE_EDGES,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    HOLDOUT_TAIL_PAIRS,
    NESTED_PATHWISE_SCR_REFERENCE,
    NEXT_RISK_ID,
    SECOND_TREE_EDGES,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
)
from par_model_v2.projection.vine_tail_diagnostics import (
    CROSSCHECK_TOL,
    TAIL_LEVEL_GRID,
    VINE_COPULA_FORM_RESIDUAL_POINT,
)
from par_model_v2.projection.vine_tree3_aggregation import (
    P29_HOLDOUT_TO_FIT_MAX_LIFT_REFERENCE,
    THIRD_TREE_EDGES,
    Tree3VineFit,
    VINE2_COMPONENT_SCR_REFERENCE,
    _joint_conditional_mask,
)
from par_model_v2.projection.vine_tree3_bootstrap import (
    TREE3_BOOTSTRAP_MASTER_SEED,
    TREE3_BOOTSTRAP_N_SIM,
    TREE3_BOOTSTRAP_REPLICATES,
    TREE3_CANDIDATE_COMPONENT_SCR_POINT,
    _component_scr_from_uniforms,
    _draw_uniforms_three,
    _replicate_seeds,
)

# ---------------------------------------------------------------------------
# Archived Phase 30 Task 3 bootstrap statistics (200 x 20,000, master seed
# 20260611) - the MR-decision references and the aggregate bit-identical
# cross-check targets (docs/validation/PHASE30_TASK3_TREE3_MARGIN_BOOTSTRAP_
# REPORT.json).
# ---------------------------------------------------------------------------
P30T3_TREE3_COMPONENT_MEAN = 41751.92733111887
P30T3_TREE3_CI_LO = 38593.73891844572
P30T3_TREE3_CI_HI = 44556.44856853384
P30T3_FROZEN_T_COMPONENT_MEAN = 39448.2149275207
P30T3_BOOTSTRAP_DIGEST = "7b2a0cbcbb35"
P30T2_TREE3_FIT_DIGEST_REFERENCE = "f689e11e81fa"

#: The tree-3 candidate copula-form residual point: BIT-identical to the
#: 2-tree vine residual because all four pre-registered third-tree pairs
#: fitted gaussian / zero strength (P30T2 zero-strength contract).
TREE3_COPULA_FORM_RESIDUAL_POINT = VINE_COPULA_FORM_RESIDUAL_POINT

#: The pre-registered residual-improvement threshold: the EXACT archived
#: 2-tree vine residual (the design note's "3,637.3" is its display
#: rounding).  Mitigation requires the tree-3 residual STRICTLY below this.
RESIDUAL_IMPROVEMENT_THRESHOLD = VINE_COPULA_FORM_RESIDUAL_POINT

MR_REFRESH_TRIGGER = 0.01
OVERFIT_CANONICAL_P = TAIL_LEVEL_P  # 0.90
N_HOLDOUT_PAIRS_REQUIRED = len(HOLDOUT_TAIL_PAIRS)


def _p_key(p: float) -> str:
    return f"{int(round(float(p) * 100)):02d}"


def _tree3_pair_groups() -> Dict[str, List[Tuple[Tuple[int, int], object]]]:
    """The four pre-registered pair groups with their conditioning spec.

    ``cond`` is None (unconditional), an int (root upper-tail conditional,
    tree 2) or a 2-tuple (joint upper-tail conditional, tree 3).
    """
    first = [(tuple(sorted((int(a), int(b)))), None) for a, b in FIRST_TREE_EDGES]
    second = [(tuple(sorted((int(a), int(b)))), int(c))
              for a, b, c in SECOND_TREE_EDGES]
    third = [(tuple(sorted((int(a), int(b)))), (int(c1), int(c2)))
             for a, b, (c1, c2) in THIRD_TREE_EDGES]
    holdout = [(tuple(int(x) for x in pair), None) for pair in HOLDOUT_TAIL_PAIRS]
    return {"first_tree": first, "second_tree": second,
            "third_tree": third, "holdout": holdout}


def _mask_for(U: np.ndarray, cond, p: float) -> Optional[np.ndarray]:
    if cond is None:
        return None
    if isinstance(cond, (tuple, list)):
        return _joint_conditional_mask(U, (int(cond[0]), int(cond[1])), p)
    return _conditional_mask(U, int(cond), p)


def tree3_pair_tail_grid_for_uniforms(
    U_cand: np.ndarray,
    U_frz: np.ndarray,
    p_grid: Sequence[float] = TAIL_LEVEL_GRID,
) -> Dict[str, object]:
    """Per-pair upper/lower tail co-dependence of the tree-3 candidate vs
    the frozen-t boundary draw (CRN) for the four pre-registered pair groups.

    Second-tree links are conditional on the root (credit) upper tail;
    third-tree links are conditional on the JOINT upper tail of both
    pre-registered conditioners (matching the leakage-free joint-conditional
    fit); first-tree and holdout pairs are unconditional.
    """
    groups = _tree3_pair_groups()
    out: Dict[str, object] = {}
    for p in p_grid:
        p = float(p)
        block: Dict[str, List[Dict[str, object]]] = {}
        for gname, pairs in groups.items():
            rows = []
            for pair, cond in pairs:
                m_c = _mask_for(U_cand, cond, p)
                m_f = _mask_for(U_frz, cond, p)
                cu = _tail_codependence(U_cand, pair, p, True, m_c)
                cl = _tail_codependence(U_cand, pair, p, False, m_c)
                fu = _tail_codependence(U_frz, pair, p, True, m_f)
                fl = _tail_codependence(U_frz, pair, p, False, m_f)
                rows.append({
                    "pair": list(pair),
                    "condition_on": (list(cond)
                                     if isinstance(cond, (tuple, list))
                                     else cond),
                    "n_conditional_cand":
                        (int(np.sum(m_c)) if m_c is not None
                         else int(U_cand.shape[0])),
                    "cand_upper": cu, "cand_lower": cl,
                    "frz_upper": fu, "frz_lower": fl,
                    "lift_upper": cu - fu, "lift_lower": cl - fl,
                })
            block[gname] = rows
        out[_p_key(p)] = block
    return out


def replicate_tree3_tail_records(
    losses_without: Dict[str, np.ndarray],
    correlation: np.ndarray,
    rule: ManagementActionRule,
    l_fit: float,
    anchor_means: Dict[str, float],
    fit3: Tree3VineFit,
    sigma: float,
    alpha: float,
    benefit_share: float,
    archived_records: Optional[Dict[int, Dict[str, float]]] = None,
    n_replicates: int = TREE3_BOOTSTRAP_REPLICATES,
    n_sim: int = TREE3_BOOTSTRAP_N_SIM,
    master_seed: int = TREE3_BOOTSTRAP_MASTER_SEED,
    confidence: float = 0.995,
    replicate_start: int = 0,
    replicate_stop: Optional[int] = None,
    p_grid: Sequence[float] = TAIL_LEVEL_GRID,
) -> Dict[str, object]:
    """Reproduce Task 3 bootstrap replicates [start, stop) and attach the
    per-pair tail grids.

    Each replicate reproduces the Task 3 row resample + ``cop_seed`` exactly
    (same SeedSequence spawn), recomputes the tree-3 candidate, 2-tree vine
    boundary and frozen-t boundary component SCRs (cross-checked
    BIT-identically against the archived Task 3 records when supplied),
    re-verifies the zero-strength uniform bit-identity (max |U_t3 - U_v2|),
    and reads the per-pair tail grids off the SAME uniforms (CRN).
    """
    drivers = list(losses_without.keys())
    n_obs = int(np.asarray(losses_without[drivers[0]]).size)
    stop = int(n_replicates) if replicate_stop is None else int(replicate_stop)
    seeds = _replicate_seeds(master_seed, n_replicates)
    R = np.asarray(correlation, dtype=float)
    records: List[Dict[str, object]] = []
    max_abs_dev = 0.0
    max_uniform_dev = 0.0
    for r in range(int(replicate_start), stop):
        child = np.random.default_rng(seeds[r])
        idx = child.integers(0, n_obs, size=n_obs)
        res_losses = {k: np.asarray(losses_without[k], float)[idx]
                      for k in drivers}
        agg_b = JointActionAggregator(
            standalone_losses=res_losses, correlation=R,
            rule=rule, l_fit=l_fit, anchor_means=anchor_means)
        cop_seed = int(child.integers(0, 2**31 - 1))
        U_t3, U_v2, U_frz = _draw_uniforms_three(cop_seed, int(n_sim), R, fit3)
        u_dev = float(np.max(np.abs(U_t3 - U_v2)))
        max_uniform_dev = max(max_uniform_dev, u_dev)
        _, comp_t3 = _component_scr_from_uniforms(
            agg_b, U_t3, sigma, alpha, benefit_share, confidence)
        _, comp_v2 = _component_scr_from_uniforms(
            agg_b, U_v2, sigma, alpha, benefit_share, confidence)
        _, comp_f = _component_scr_from_uniforms(
            agg_b, U_frz, sigma, alpha, benefit_share, confidence)
        rec: Dict[str, object] = {
            "replicate_index": int(r),
            "cop_seed": cop_seed,
            "scr_component_tree3": float(comp_t3),
            "scr_component_vine2": float(comp_v2),
            "scr_component_frozen_t": float(comp_f),
            "tree3_minus_vine2": float(comp_t3 - comp_v2),
            "uniform_bit_identity_max_abs_dev": u_dev,
            "tail_grid": tree3_pair_tail_grid_for_uniforms(U_t3, U_frz, p_grid),
        }
        if archived_records is not None and int(r) in archived_records:
            a = archived_records[int(r)]
            dev = max(
                abs(float(comp_t3) - float(a["scr_component_tree3"])),
                abs(float(comp_v2) - float(a["scr_component_vine2"])),
                abs(float(comp_f) - float(a["scr_component_frozen_t"])),
                abs(float(cop_seed) - float(a["cop_seed"])),
            )
            max_abs_dev = max(max_abs_dev, dev)
            rec["archived_crosscheck_abs_dev"] = dev
        records.append(rec)
    return {
        "n_obs": n_obs,
        "n_sim_per_replicate": int(n_sim),
        "master_seed": int(master_seed),
        "replicate_start": int(replicate_start),
        "replicate_stop": stop,
        "p_grid": [float(p) for p in p_grid],
        "archived_crosscheck_max_abs_dev": float(max_abs_dev),
        "uniform_bit_identity_max_abs_dev": float(max_uniform_dev),
        "records": records,
    }


def summarise_tree3_pair_tail_diagnostics(
    records: Sequence[Dict[str, object]],
    p_grid: Sequence[float] = TAIL_LEVEL_GRID,
) -> Dict[str, object]:
    """Per-pair, per-level 95% CI summaries of the candidate / frozen tail
    co-dependence and the (candidate - frozen) CRN lift."""
    recs = sorted(records, key=lambda x: int(x["replicate_index"]))
    groups = _tree3_pair_groups()
    out: Dict[str, object] = {}
    for p in p_grid:
        key = _p_key(float(p))
        block: Dict[str, List[Dict[str, object]]] = {}
        for gname, pairs in groups.items():
            rows = []
            for k, (pair, cond) in enumerate(pairs):
                vals = {m: [r["tail_grid"][key][gname][k][m] for r in recs]
                        for m in ("cand_upper", "cand_lower", "frz_upper",
                                  "frz_lower", "lift_upper", "lift_lower")}
                n_cond = [r["tail_grid"][key][gname][k]["n_conditional_cand"]
                          for r in recs]
                rows.append({
                    "pair": list(pair),
                    "condition_on": (list(cond)
                                     if isinstance(cond, (tuple, list))
                                     else cond),
                    "n_conditional_cand_mean": float(np.mean(n_cond)),
                    **{m: summarise_metric(v) for m, v in vals.items()},
                })
            block[gname] = rows
        out[key] = block
    return out


def tree3_overfit_check(
    summary: Dict[str, object],
    fit3_dict: Dict[str, object],
    canonical_p: float = OVERFIT_CANONICAL_P,
    p29_reference_ratio: float = P29_HOLDOUT_TO_FIT_MAX_LIFT_REFERENCE,
) -> Dict[str, object]:
    """Pre-registered fit-vs-holdout overfit check at the canonical level.

    (a) holdout disclosure complete; (b) the largest holdout-pair
    |mean lift| must not exceed the largest fitted-pair |mean lift|
    (fitted = tree-1 + tree-2 + tree-3 links).  The holdout-to-fit max-lift
    ratio is DISCLOSED against the P29 Task 4 reference 0.049.  Also
    DISCLOSES the realised-data joint-conditional support of the FROZEN
    tree-3 fit (n_fit per pair; context for the zero-strength selections).
    """
    key = _p_key(float(canonical_p))
    block = summary[key]
    fit_rows = (list(block["first_tree"]) + list(block["second_tree"])
                + list(block["third_tree"]))
    hold_rows = list(block["holdout"])

    fit_abs = [max(abs(r["lift_upper"]["mean"]), abs(r["lift_lower"]["mean"]))
               for r in fit_rows]
    hold_abs = [max(abs(r["lift_upper"]["mean"]), abs(r["lift_lower"]["mean"]))
                for r in hold_rows]
    max_fit = float(max(fit_abs))
    max_hold = float(max(hold_abs))

    disclosure_complete = bool(
        len(hold_rows) == N_HOLDOUT_PAIRS_REQUIRED
        and all(("lift_upper" in r and "lift_lower" in r
                 and "ci_lo" in r["lift_upper"] and "ci_lo" in r["lift_lower"])
                for r in hold_rows))
    concentration_ok = bool(max_hold <= max_fit)
    ratio = float(max_hold / max_fit) if max_fit > 0.0 else 0.0

    sel3 = list(fit3_dict["tree3_selections"])
    return {
        "canonical_p": float(canonical_p),
        "n_fit_pairs": len(fit_rows),
        "n_holdout_pairs": len(hold_rows),
        "max_fit_pair_abs_mean_lift": max_fit,
        "max_holdout_pair_abs_mean_lift": max_hold,
        "holdout_to_fit_max_lift_ratio": ratio,
        "p29_holdout_to_fit_reference": float(p29_reference_ratio),
        "ratio_vs_p29_reference_disclosed": True,
        "holdout_disclosure_complete": disclosure_complete,
        "concentration_ok": concentration_ok,
        "overfit_gate_pass": bool(disclosure_complete and concentration_ok),
        "tree3_fit_support_n_fit": [int(s["n_fit"]) for s in sel3],
        "tree3_fit_all_zero_strength": bool(
            all(float(s["strength"]) == 0.0 for s in sel3)),
        "note": ("Holdout pairs were never used in family selection; their "
                 "candidate-vs-frozen lifts are DISCLOSED with CIs at every "
                 "grid level. The gate requires the largest holdout |mean "
                 "lift| <= the largest fitted-pair |mean lift| (tilt "
                 "concentrated on fitted links; fitted = tree-1 + tree-2 + "
                 "tree-3) AND complete holdout disclosure. The "
                 "holdout-to-fit max-lift ratio is disclosed against the "
                 "P29 Task 4 reference 0.049. The four tree-3 links carry "
                 "ZERO incremental tilt (zero-strength selections under "
                 "n_fit <= 3 joint-conditional support), so the candidate "
                 "tail field is exactly the 2-tree vine's."),
    }


def tree3_stop_rule_mr_decision(
    boundary_scr_recomputed: float,
    tree3_ci_lo: float = P30T3_TREE3_CI_LO,
    tree3_ci_hi: float = P30T3_TREE3_CI_HI,
    nested_scr: float = NESTED_PATHWISE_SCR_REFERENCE,
    tree3_residual: float = TREE3_COPULA_FORM_RESIDUAL_POINT,
    residual_threshold: float = RESIDUAL_IMPROVEMENT_THRESHOLD,
    governed_reference: float = FROZEN_T_COMPONENT_SCR_REFERENCE,
    trigger: float = MR_REFRESH_TRIGGER,
) -> Dict[str, object]:
    """The pre-registered BINDING stop-rule / MR-016 / MR-017 decision.

    Mitigate MR-016 / MR-017 ONLY IF nested lies INSIDE the Task 3 tree-3
    95% bootstrap CI AND the copula-form residual shrinks STRICTLY below the
    2-tree vine residual (design-note threshold "3,637.3" = the exact
    archived 3,637.298487404965).  Neither holds, so both MRs KEEP OPEN and
    the STOP-RULE IS APPLIED: dependence-FORM escalation under MR-016 ENDS;
    Phase 31 is the owner decision package (design-note option C).  Refresh
    MR-010/MR-014 ONLY IF the GOVERNED headline (frozen single-df t) moves
    > 1% - nothing is adopted and the boundary is recovered bit-identically,
    so the governed move is 0.
    """
    nested_inside_ci = bool(float(tree3_ci_lo) <= float(nested_scr)
                            <= float(tree3_ci_hi))
    residual_shrinks_strictly = bool(
        float(tree3_residual) < float(residual_threshold))
    mitigate_criteria_met = bool(nested_inside_ci and residual_shrinks_strictly)
    stop_rule_trigger_met = bool(not nested_inside_ci)
    stop_rule_applied = bool(stop_rule_trigger_met
                             and not mitigate_criteria_met)
    governed_move = (float(boundary_scr_recomputed)
                     - float(governed_reference)) / float(governed_reference)
    refresh_required = bool(abs(governed_move) > float(trigger))
    shrink_vs_grouped = (float(tree3_residual)
                         / float(GROUPED_T_COPULA_FORM_RESIDUAL_ABS) - 1.0)
    shrink_vs_skewt = (float(tree3_residual)
                       / float(SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS)
                       - 1.0)
    return {
        "existing_risk_id": EXISTING_RISK_ID,
        "next_risk_id": NEXT_RISK_ID,
        "nested_scr": float(nested_scr),
        "tree3_ci": [float(tree3_ci_lo), float(tree3_ci_hi)],
        "nested_inside_ci": nested_inside_ci,
        "tree3_copula_form_residual": float(tree3_residual),
        "residual_improvement_threshold": float(residual_threshold),
        "residual_shrinks_strictly": residual_shrinks_strictly,
        "residual_unchanged_vs_vine2": bool(
            float(tree3_residual) == float(residual_threshold)),
        "residual_change_vs_grouped_t_rel": float(shrink_vs_grouped),
        "residual_change_vs_skewt_rel": float(shrink_vs_skewt),
        "mitigate_criteria_met": mitigate_criteria_met,
        "mr016_decision": ("MITIGATE" if mitigate_criteria_met
                           else "KEEP_OPEN"),
        "mr017_decision": ("MITIGATE" if mitigate_criteria_met
                           else "KEEP_OPEN"),
        "stop_rule_trigger_met": stop_rule_trigger_met,
        "stop_rule_applied": stop_rule_applied,
        "dependence_form_escalation_ends": stop_rule_applied,
        "phase31_directive": (
            "Phase 31 = OWNER DECISION PACKAGE (design-note option C): "
            "consolidated read-out of the governed frozen-t headline "
            "39,975.7, the disclosed 2-tree vine / tree-3 candidate "
            "42,458.6, the nested reference 46,638.9 and the quantified "
            "residual 3,637.3, for an owner adoption / escalation / accept "
            "decision. Option B (nested-aware dependence calibration) "
            "remains available ONLY as an owner-approved escalation funding "
            "a second independent nested run."),
        "governed_headline_reference": float(governed_reference),
        "boundary_scr_recomputed": float(boundary_scr_recomputed),
        "governed_headline_relative_move": float(governed_move),
        "mr_refresh_trigger": float(trigger),
        "mr010_mr014_refresh_required": refresh_required,
        "rationale": (
            "The pre-registered mitigation criteria require BOTH nested "
            "{:.1f} INSIDE the tree-3 95% bootstrap CI [{:.1f}, {:.1f}] AND "
            "a STRICT residual improvement below the 2-tree vine residual "
            "{:.1f}. Neither holds: the tree-3 candidate is bit-identical "
            "to the 2-tree vine (all four pre-registered third-tree pairs "
            "zero strength under n_fit <= 3 joint-conditional support), so "
            "the residual is UNCHANGED, and nested remains OUTSIDE the CI. "
            "MR-016 and MR-017 KEEP OPEN and the STOP-RULE IS APPLIED: "
            "dependence-FORM escalation under MR-016 ENDS (no further "
            "copula-structure candidates without owner sign-off); Phase 31 "
            "is the owner decision package. The GOVERNED headline remains "
            "the frozen single-df t {:.1f} (recovered bit-identically, move "
            "{:.4%}), so MR-010/MR-014 quantifications are unchanged."
            .format(float(nested_scr), float(tree3_ci_lo),
                    float(tree3_ci_hi), float(residual_threshold),
                    float(governed_reference), governed_move)),
    }


def tree3_tail_diagnostics_digest(records: Sequence[Dict[str, object]]) -> str:
    """Order-independent SHA-256 over the per-replicate canonical-level
    (p = 0.90) candidate/frozen tail vectors + recomputed SCRs."""
    key = _p_key(OVERFIT_CANONICAL_P)
    rows = []
    for r in sorted(records, key=lambda x: int(x["replicate_index"])):
        grid = r["tail_grid"][key]
        flat: List[float] = [float(r["scr_component_tree3"]),
                             float(r["scr_component_vine2"]),
                             float(r["scr_component_frozen_t"])]
        for gname in ("first_tree", "second_tree", "third_tree", "holdout"):
            for row in grid[gname]:
                flat.extend([float(row["cand_upper"]), float(row["frz_upper"]),
                             float(row["cand_lower"]), float(row["frz_lower"])])
        rows.append([int(r["replicate_index"])] + flat)
    payload = json.dumps(rows, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:12]


def tree3_tail_diagnostics_use_restrictions() -> Dict[str, object]:
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "Diagnostics + governance only: no governed parameter changes; "
            "the copula Sigma, homogeneous df 2.9451, the FROZEN P29T2 "
            "2-tree fit, the FROZEN P30T2 tree-3 selections (all gaussian / "
            "zero strength) and the governed relief scalars stay frozen.",
            "The per-pair tail read-outs are co-exceedance proxies at "
            "finite p, not asymptotic tail-dependence coefficients.",
            "Second-tree read-outs are CONDITIONAL on the root (credit) "
            "upper tail; third-tree read-outs are conditional on the JOINT "
            "upper tail of both pre-registered conditioners; they are not "
            "unconditional pair statements.",
            "The fit-vs-holdout overfit gate is pre-registered (disclosure "
            "+ concentration); holdout pairs were never used in family "
            "selection; the holdout-to-fit ratio is disclosed against the "
            "P29 reference 0.049.",
            "MR-016 and MR-017 KEEP OPEN per the pre-registered criteria; "
            "the STOP-RULE IS APPLIED: dependence-FORM escalation under "
            "MR-016 ENDS; Phase 31 is the owner decision package (option "
            "C); option B only as an owner-approved escalation.",
            "Neither the 2-tree vine nor the tree-3 candidate is adopted "
            "into the governed headline without owner sign-off; "
            "MR-010/MR-014 are unchanged.",
            "Production use remains prohibited pending credentialled data "
            "and independent APS X2 review.",
        ],
        "references": {
            "existing_risk": EXISTING_RISK_ID,
            "next_risk": NEXT_RISK_ID,
            "nested_pathwise_reference": NESTED_PATHWISE_SCR_REFERENCE,
            "frozen_t_component_reference": FROZEN_T_COMPONENT_SCR_REFERENCE,
            "vine2_component_reference": VINE2_COMPONENT_SCR_REFERENCE,
            "tree3_candidate_component_reference":
                TREE3_CANDIDATE_COMPONENT_SCR_POINT,
            "tree3_bootstrap_ci": [P30T3_TREE3_CI_LO, P30T3_TREE3_CI_HI],
            "tree3_copula_form_residual": TREE3_COPULA_FORM_RESIDUAL_POINT,
            "grouped_t_residual_reference":
                GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
            "skewt_residual_reference":
                SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
            "p30t3_bootstrap_digest": P30T3_BOOTSTRAP_DIGEST,
            "p30t2_tree3_fit_digest": P30T2_TREE3_FIT_DIGEST_REFERENCE,
        },
    }
