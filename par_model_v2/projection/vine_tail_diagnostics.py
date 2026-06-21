"""Phase 29 Task 4 - vine pair-level tail diagnostics, fit-vs-holdout overfit
check, and the MR-016 remediation DECISION.

This task introduces NO new model parameter.  It REPORTS the per-pair upper
(lambda_U proxy) and lower (lambda_L proxy) tail co-dependence of the FROZEN
Phase 29 Task 2 vine-pair candidate draw against the frozen single-df t
boundary on COMMON random numbers, for

* the six FIRST-tree (credit-root) links (unconditional pair events),
* the five SECOND-tree links (events conditional on the root upper tail,
  matching the leakage-free fit's conditioning), and
* the three pre-registered HOLDOUT pairs (never used in family selection),

re-drawn replicate-by-replicate at the Phase 29 Task 3 bootstrap seeds (the
per-replicate SeedSequence spawn of master seed 20260610 is reproduced
exactly, so the recomputed vine / frozen-t component SCRs cross-check
BIT-identically against the archived Task 3 records and aggregate CI).

Fit-vs-holdout OVERFIT check (pre-registered, Task 4 block of the Phase 29
Task 1 design note): the candidate must NOT improve the fitted tail pairs
while silently degrading the holdout disclosure.  Operationalised at the
canonical level p = 0.90 as

  (a) DISCLOSURE: all three holdout pairs are reported with upper AND lower
      lift (candidate - frozen, CRN) and a 95% CI at every grid level; and
  (b) CONCENTRATION: the largest holdout-pair |mean lift| (upper or lower)
      does not exceed the largest fitted-pair |mean lift| - the pair-link
      tilt must act through the fitted links, not through an untracked
      distortion of never-fitted pairs.

MR-016 remediation DECISION (pre-registered criteria, Phase 29 Task 1 design
note): close/mitigate ONLY IF the copula-form residual materially shrinks AND
the nested path-wise truth 46,638.9 lies INSIDE the Task 3 vine 95% bootstrap
CI.  The residual DOES shrink (3,637.3 = -65.33% vs grouped-t 10,491.5,
-40.52% vs skew-t 6,114.9) but nested 46,638.9 is NOT inside the CI
(hi 45,284.3), so MR-016 stays OPEN with the narrowing DISCLOSED, and MR-017
is opened for the remaining vine-FORM limitations (the truncated credit-root
rank-preserving tilt prototype cannot represent the residual nested
inner-path joint dynamics).  MR-010 / MR-014 are refreshed ONLY IF the
GOVERNED headline (frozen single-df t 39,975.654628199336) moves > 1%: it
does NOT move (the boundary is recovered bit-identically; the vine is NOT
adopted without owner sign-off), so NO refresh.

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
from par_model_v2.projection.vine_copula_bootstrap import (
    VINE_BOOTSTRAP_MASTER_SEED,
    VINE_BOOTSTRAP_N_SIM,
    VINE_BOOTSTRAP_REPLICATES,
    VINE_CANDIDATE_COMPONENT_SCR_POINT,
    _component_scr_from_uniforms,
    _draw_uniforms_both,
    _replicate_seeds,
)
from par_model_v2.projection.vine_copula_pair_aggregation import (
    TAIL_LEVEL_P,
    VinePairFit,
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
    VINE_ROOT_DRIVER,
)

# ---------------------------------------------------------------------------
# Pre-registered diagnostics design (Phase 29 Task 4)
# ---------------------------------------------------------------------------
# Tail-threshold grid: the canonical Task 2/3 level 0.90 (the cross-check
# anchor) plus a symmetric spread (P28T4 precedent).
TAIL_LEVEL_GRID = (0.80, 0.85, 0.90, 0.95)

# Archived Phase 29 Task 3 bootstrap statistics (200 x 20,000, master seed
# 20260610) - the MR-decision references and the aggregate bit-identical
# cross-check targets (docs/validation/PHASE29_TASK3_VINE_MARGIN_BOOTSTRAP_
# REPORT.json).
P29T3_VINE_COMPONENT_MEAN = 41917.634842687556
P29T3_VINE_CI_LO = 38654.68530800363
P29T3_VINE_CI_HI = 45284.252553628474
P29T3_FROZEN_T_COMPONENT_MEAN = 39603.22039796022
P29T3_BOOTSTRAP_DIGEST = "e277f58b57f8"

# Archived copula-form residuals (point basis; Task 3 re-decomposition).
VINE_COPULA_FORM_RESIDUAL_POINT = 3637.298487404965

MR_REFRESH_TRIGGER = 0.01
CROSSCHECK_TOL = 1e-12

# Overfit (fit-vs-holdout) gate constants - see module docstring.
OVERFIT_CANONICAL_P = TAIL_LEVEL_P  # 0.90
N_HOLDOUT_PAIRS_REQUIRED = len(HOLDOUT_TAIL_PAIRS)


def _p_key(p: float) -> str:
    return f"{int(round(float(p) * 100)):02d}"


def _pair_groups() -> Dict[str, List[Tuple[Tuple[int, int], Optional[int]]]]:
    """The three pre-registered pair groups with their conditioning driver."""
    first = [(tuple(sorted((int(a), int(b)))), None) for a, b in FIRST_TREE_EDGES]
    second = [(tuple(sorted((int(a), int(b)))), int(c))
              for a, b, c in SECOND_TREE_EDGES]
    holdout = [(tuple(int(x) for x in pair), None) for pair in HOLDOUT_TAIL_PAIRS]
    return {"first_tree": first, "second_tree": second, "holdout": holdout}


def pair_tail_grid_for_uniforms(
    U_cand: np.ndarray,
    U_frz: np.ndarray,
    p_grid: Sequence[float] = TAIL_LEVEL_GRID,
) -> Dict[str, object]:
    """Per-pair upper/lower tail co-dependence of the candidate vs the
    frozen-t boundary draw (CRN) for the three pre-registered pair groups.

    Second-tree links are evaluated CONDITIONAL on the root (credit) upper
    tail of the respective draw, matching the leakage-free fit's
    conditioning; first-tree and holdout pairs are unconditional.
    """
    groups = _pair_groups()
    out: Dict[str, object] = {}
    for p in p_grid:
        p = float(p)
        block: Dict[str, List[Dict[str, object]]] = {}
        for gname, pairs in groups.items():
            rows = []
            for pair, cond in pairs:
                m_c = _conditional_mask(U_cand, cond, p)
                m_f = _conditional_mask(U_frz, cond, p)
                cu = _tail_codependence(U_cand, pair, p, True, m_c)
                cl = _tail_codependence(U_cand, pair, p, False, m_c)
                fu = _tail_codependence(U_frz, pair, p, True, m_f)
                fl = _tail_codependence(U_frz, pair, p, False, m_f)
                rows.append({
                    "pair": list(pair),
                    "condition_on": cond,
                    "cand_upper": cu, "cand_lower": cl,
                    "frz_upper": fu, "frz_lower": fl,
                    "lift_upper": cu - fu, "lift_lower": cl - fl,
                })
            block[gname] = rows
        out[_p_key(p)] = block
    return out


def replicate_pair_tail_records(
    losses_without: Dict[str, np.ndarray],
    correlation: np.ndarray,
    rule: ManagementActionRule,
    l_fit: float,
    anchor_means: Dict[str, float],
    fit: VinePairFit,
    sigma: float,
    alpha: float,
    benefit_share: float,
    archived_records: Optional[Dict[int, Dict[str, float]]] = None,
    n_replicates: int = VINE_BOOTSTRAP_REPLICATES,
    n_sim: int = VINE_BOOTSTRAP_N_SIM,
    master_seed: int = VINE_BOOTSTRAP_MASTER_SEED,
    confidence: float = 0.995,
    replicate_start: int = 0,
    replicate_stop: Optional[int] = None,
    p_grid: Sequence[float] = TAIL_LEVEL_GRID,
) -> Dict[str, object]:
    """Reproduce Task 3 bootstrap replicates [start, stop) and attach the
    per-pair tail grids.

    Each replicate reproduces the Task 3 row resample + ``cop_seed`` exactly
    (same SeedSequence spawn), recomputes the vine-candidate and frozen-t
    boundary component SCRs (cross-checked BIT-identically against the
    archived Task 3 records when supplied), and reads the per-pair tail grids
    off the SAME uniforms (CRN).
    """
    drivers = list(losses_without.keys())
    n_obs = int(np.asarray(losses_without[drivers[0]]).size)
    stop = int(n_replicates) if replicate_stop is None else int(replicate_stop)
    seeds = _replicate_seeds(master_seed, n_replicates)
    R = np.asarray(correlation, dtype=float)
    records: List[Dict[str, object]] = []
    max_abs_dev = 0.0
    for r in range(int(replicate_start), stop):
        child = np.random.default_rng(seeds[r])
        idx = child.integers(0, n_obs, size=n_obs)
        res_losses = {k: np.asarray(losses_without[k], float)[idx]
                      for k in drivers}
        agg_b = JointActionAggregator(
            standalone_losses=res_losses, correlation=R,
            rule=rule, l_fit=l_fit, anchor_means=anchor_means)
        cop_seed = int(child.integers(0, 2**31 - 1))
        U_cand, U_frz = _draw_uniforms_both(cop_seed, int(n_sim), R, fit)
        _, comp_v = _component_scr_from_uniforms(
            agg_b, U_cand, sigma, alpha, benefit_share, confidence)
        _, comp_f = _component_scr_from_uniforms(
            agg_b, U_frz, sigma, alpha, benefit_share, confidence)
        rec: Dict[str, object] = {
            "replicate_index": int(r),
            "cop_seed": cop_seed,
            "scr_component_vine": float(comp_v),
            "scr_component_frozen_t": float(comp_f),
            "tail_grid": pair_tail_grid_for_uniforms(U_cand, U_frz, p_grid),
        }
        if archived_records is not None and int(r) in archived_records:
            a = archived_records[int(r)]
            dev = max(
                abs(float(comp_v) - float(a["scr_component_vine"])),
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
        "records": records,
    }


def summarise_pair_tail_diagnostics(
    records: Sequence[Dict[str, object]],
    p_grid: Sequence[float] = TAIL_LEVEL_GRID,
) -> Dict[str, object]:
    """Per-pair, per-level 95% CI summaries of the candidate / frozen tail
    co-dependence and the (candidate - frozen) CRN lift."""
    recs = sorted(records, key=lambda x: int(x["replicate_index"]))
    groups = _pair_groups()
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
                rows.append({
                    "pair": list(pair),
                    "condition_on": cond,
                    **{m: summarise_metric(v) for m, v in vals.items()},
                })
            block[gname] = rows
        out[key] = block
    return out


def overfit_fit_vs_holdout_check(
    summary: Dict[str, object],
    fit_dict: Dict[str, object],
    canonical_p: float = OVERFIT_CANONICAL_P,
) -> Dict[str, object]:
    """Pre-registered fit-vs-holdout overfit check at the canonical level.

    See module docstring: (a) holdout disclosure complete; (b) the largest
    holdout-pair |mean lift| must not exceed the largest fitted-pair
    |mean lift| (tilt concentrated on fitted links).  Also DISCLOSES the
    realised-data fit-vs-holdout tail gap of the FROZEN leakage-free fit
    itself (sampling-stability context; not gated).
    """
    key = _p_key(float(canonical_p))
    block = summary[key]
    fit_rows = list(block["first_tree"]) + list(block["second_tree"])
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

    sel = list(fit_dict["selections"])
    realised_gaps = [abs(float(s["fit_upper"]) - float(s["holdout_upper"]))
                     for s in sel]
    return {
        "canonical_p": float(canonical_p),
        "n_fit_pairs": len(fit_rows),
        "n_holdout_pairs": len(hold_rows),
        "max_fit_pair_abs_mean_lift": max_fit,
        "max_holdout_pair_abs_mean_lift": max_hold,
        "holdout_to_fit_max_lift_ratio":
            float(max_hold / max_fit) if max_fit > 0.0 else 0.0,
        "holdout_disclosure_complete": disclosure_complete,
        "concentration_ok": concentration_ok,
        "overfit_gate_pass": bool(disclosure_complete and concentration_ok),
        "realised_fit_vs_holdout_abs_gap_mean":
            float(np.mean(realised_gaps)),
        "realised_fit_vs_holdout_abs_gap_max":
            float(np.max(realised_gaps)),
        "note": ("Holdout pairs were never used in family selection (fit rows "
                 "only); their candidate-vs-frozen lifts are DISCLOSED with "
                 "CIs at every grid level. The gate requires the largest "
                 "holdout |mean lift| <= the largest fitted-pair |mean lift| "
                 "(tilt concentrated on fitted links) AND complete holdout "
                 "disclosure."),
    }


def mr016_remediation_decision(
    boundary_scr_recomputed: float,
    vine_ci_lo: float = P29T3_VINE_CI_LO,
    vine_ci_hi: float = P29T3_VINE_CI_HI,
    nested_scr: float = NESTED_PATHWISE_SCR_REFERENCE,
    vine_residual: float = VINE_COPULA_FORM_RESIDUAL_POINT,
    grouped_residual: float = GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    skewt_residual: float = SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
    governed_reference: float = FROZEN_T_COMPONENT_SCR_REFERENCE,
    trigger: float = MR_REFRESH_TRIGGER,
) -> Dict[str, object]:
    """The pre-registered MR-016 remediation decision + MR-010/MR-014 refresh
    decision.

    Close/mitigate MR-016 ONLY IF the copula-form residual materially shrinks
    AND nested lies INSIDE the Task 3 vine 95% bootstrap CI.  Refresh
    MR-010/MR-014 ONLY IF the GOVERNED headline (frozen single-df t) moves
    > 1% - the vine candidate is NOT adopted without owner sign-off, and the
    boundary is recovered bit-identically, so the governed move is 0.
    """
    nested_inside_ci = bool(float(vine_ci_lo) <= float(nested_scr)
                            <= float(vine_ci_hi))
    shrink_vs_grouped = float(vine_residual) / float(grouped_residual) - 1.0
    shrink_vs_skewt = float(vine_residual) / float(skewt_residual) - 1.0
    residual_materially_shrinks = bool(shrink_vs_grouped < 0.0
                                       and shrink_vs_skewt < 0.0)
    close_criteria_met = bool(residual_materially_shrinks and nested_inside_ci)
    governed_move = (float(boundary_scr_recomputed)
                     - float(governed_reference)) / float(governed_reference)
    refresh_required = bool(abs(governed_move) > float(trigger))
    return {
        "existing_risk_id": EXISTING_RISK_ID,
        "next_risk_id": NEXT_RISK_ID,
        "nested_scr": float(nested_scr),
        "vine_ci": [float(vine_ci_lo), float(vine_ci_hi)],
        "nested_inside_ci": nested_inside_ci,
        "vine_copula_form_residual": float(vine_residual),
        "residual_change_vs_grouped_t_rel": float(shrink_vs_grouped),
        "residual_change_vs_skewt_rel": float(shrink_vs_skewt),
        "residual_materially_shrinks": residual_materially_shrinks,
        "close_criteria_met": close_criteria_met,
        "mr016_decision": "CLOSE_OR_MITIGATE" if close_criteria_met
                          else "KEEP_OPEN",
        "open_mr017": bool(not close_criteria_met),
        "governed_headline_reference": float(governed_reference),
        "boundary_scr_recomputed": float(boundary_scr_recomputed),
        "governed_headline_relative_move": float(governed_move),
        "mr_refresh_trigger": float(trigger),
        "mr010_mr014_refresh_required": refresh_required,
        "rationale": (
            "The vine candidate is the FIRST dependence candidate to NARROW "
            "the copula-form residual below BOTH baselines "
            "({:+.2%} vs grouped-t, {:+.2%} vs skew-t), but the nested "
            "path-wise truth {:.1f} is NOT inside the Task 3 vine 95% "
            "bootstrap CI [{:.1f}, {:.1f}], so the pre-registered close/"
            "mitigate criteria are NOT met: MR-016 stays OPEN with the "
            "narrowing DISCLOSED, and MR-017 is opened for the remaining "
            "vine-FORM limitations. The GOVERNED headline remains the frozen "
            "single-df t {:.1f} (recovered bit-identically, move {:.4%}), so "
            "MR-010/MR-014 quantifications are unchanged - the vine is NOT "
            "adopted without owner sign-off.".format(
                shrink_vs_grouped, shrink_vs_skewt, float(nested_scr),
                float(vine_ci_lo), float(vine_ci_hi),
                float(governed_reference), governed_move)),
    }


def vine_tail_diagnostics_digest(records: Sequence[Dict[str, object]]) -> str:
    """Order-independent SHA-256 over the per-replicate canonical-level
    (p = 0.90) candidate/frozen upper-tail vectors + recomputed SCRs."""
    key = _p_key(OVERFIT_CANONICAL_P)
    rows = []
    for r in sorted(records, key=lambda x: int(x["replicate_index"])):
        grid = r["tail_grid"][key]
        flat: List[float] = [float(r["scr_component_vine"]),
                             float(r["scr_component_frozen_t"])]
        for gname in ("first_tree", "second_tree", "holdout"):
            for row in grid[gname]:
                flat.extend([float(row["cand_upper"]), float(row["frz_upper"]),
                             float(row["cand_lower"]), float(row["frz_lower"])])
        rows.append([int(r["replicate_index"])] + flat)
    payload = json.dumps(rows, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:12]


def vine_tail_diagnostics_use_restrictions() -> Dict[str, object]:
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "Diagnostics + governance only: no governed parameter changes; the copula Sigma, homogeneous df 2.9451, the FROZEN Task 2 pair-family fit and the governed relief scalars stay frozen.",
            "The per-pair tail read-outs are co-exceedance proxies at finite p, not asymptotic tail-dependence coefficients.",
            "Second-tree read-outs are CONDITIONAL on the root (credit) upper tail, matching the leakage-free fit's conditioning; they are not unconditional pair statements.",
            "The fit-vs-holdout overfit gate is pre-registered (disclosure + concentration); holdout pairs were never used in family selection.",
            "MR-016 stays OPEN per the pre-registered criteria (nested outside the Task 3 CI); the residual narrowing is DISCLOSED, not a closure.",
            "The vine candidate is NOT adopted into the governed headline without owner sign-off; MR-010/MR-014 are unchanged.",
            "Production use remains prohibited pending credentialled data and independent APS X2 review.",
        ],
        "references": {
            "existing_risk": EXISTING_RISK_ID,
            "next_risk": NEXT_RISK_ID,
            "nested_pathwise_reference": NESTED_PATHWISE_SCR_REFERENCE,
            "frozen_t_component_reference": FROZEN_T_COMPONENT_SCR_REFERENCE,
            "vine_candidate_component_reference":
                VINE_CANDIDATE_COMPONENT_SCR_POINT,
            "vine_bootstrap_ci": [P29T3_VINE_CI_LO, P29T3_VINE_CI_HI],
            "vine_copula_form_residual": VINE_COPULA_FORM_RESIDUAL_POINT,
            "grouped_t_residual_reference": GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
            "skewt_residual_reference":
                SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
        },
    }
