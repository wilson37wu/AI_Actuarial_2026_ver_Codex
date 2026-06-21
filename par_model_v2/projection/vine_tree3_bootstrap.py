"""
Phase 30 Task 3 - tree-3 vine margin bootstrap on the component basis.

Pre-registered design (PHASE30_TASK1_DESIGN_NOTE, task3_acceptance_criteria):

* >= 200 x 20,000 bootstrap replicates (P26T3 / P27T3 / P28T3 / P29T3
  pattern); SE <= 5% of the mean tree-3 candidate component SCR;
* HEADLINE: the nested path-wise truth 46,638.9 lies inside the tree-3
  candidate component-basis 95% bootstrap CI, OR the pre-registered
  STOP-RULE TRIGGER is recorded in the report (no gate-shopping) - the
  formal stop-rule DECISION is Task 4;
* paired CRN deltas (tree-3 minus 2-tree vine; tree-3 minus frozen-t) with
  sign and CI.

The bootstrap resamples the realised standalone-loss rows ONLY (joint row
resample WITH replacement, preserving the realised cross-driver pairing).
Everything else stays FROZEN inside every replicate: copula Sigma,
homogeneous df 2.9451, the FROZEN Phase 29 Task 2 leakage-free 2-tree
pair-family fit, the FROZEN Phase 30 Task 2 tree-3 selections (all four
pre-registered pairs gaussian / zero strength under n_fit <= 3
joint-conditional support), and the governed relief scalars
(sigma / alpha / beta_fit) - SII Art. 234.

All THREE legs are evaluated on COMMON random numbers: the tree-3 candidate,
the 2-tree vine boundary and the frozen-t boundary consume the SAME base
single-df t-copula draw (the tilts on top of it are deterministic), so the
per-replicate paired deltas isolate (a) the incremental tree-3 effect
(expected EXACTLY zero given the zero-strength fit - the bit-identity
contract) and (b) the total pair-link effect vs the frozen-t boundary.
EDUCATIONAL ONLY.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from par_model_v2.projection.joint_action_aggregation import JointActionAggregator
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.pathwise_composition_transform import (
    composition_with_actions,
    split_joint_composition,
)
from par_model_v2.projection.grouped_t_copula_bootstrap import (
    RELIEF_SURFACE_REL_ERR_SOURCE,
    summarise_ci,
)
from par_model_v2.projection.vine_copula_bootstrap import (
    SE_GATE_FRACTION,
    VINE_CANDIDATE_COMPONENT_SCR_POINT,
)
from par_model_v2.projection.vine_copula_upgrade import (
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
)
from par_model_v2.projection.vine_tree3_aggregation import (
    Tree3VineFit,
    simulate_tree3_vine_uniforms,
)

TREE3_BOOTSTRAP_REPLICATES = 200
TREE3_BOOTSTRAP_N_SIM = 20_000
TREE3_BOOTSTRAP_MASTER_SEED = 20260611

#: Archived Phase 30 Task 2 tree-3 candidate component read-out (200k, seed
#: 20260607) -- bit-identical to the 2-tree vine reference because all four
#: pre-registered tree-3 pairs fitted gaussian / zero strength.
TREE3_CANDIDATE_COMPONENT_SCR_POINT = 42_458.5527095696

#: Phase 29 Task 3 archived vine-2 bootstrap CI (the expected reproduction
#: target given the zero-strength tree-3 layer).
P29T3_VINE2_BOOTSTRAP_CI_REFERENCE = (38_654.68530800363, 45_284.252553628474)
P29T3_VINE2_BOOTSTRAP_MEAN_REFERENCE = 41_917.634842687556


def _replicate_seeds(master_seed: int,
                     n_replicates: int) -> List[np.random.SeedSequence]:
    """Chunk-independent per-replicate seed sequences (resume-safe)."""
    return list(np.random.SeedSequence(int(master_seed)).spawn(int(n_replicates)))


def _draw_uniforms_three(
    cop_seed: int,
    n_sim: int,
    correlation: np.ndarray,
    fit3: Tree3VineFit,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Draw tree-3 candidate, 2-tree vine boundary AND frozen-t boundary
    uniforms on COMMON random numbers.

    All three modes seed a fresh generator with the SAME ``cop_seed``; the
    first (and only) stochastic step in every mode is the identical base
    single-df t-copula draw on the frozen Sigma / df 2.9451. The vine tilts
    are deterministic given the base, so the boundary draws ARE the
    candidate's latent base (CRN by construction).
    """
    R = np.asarray(correlation, dtype=float)
    U_t3 = simulate_tree3_vine_uniforms(
        np.random.default_rng(int(cop_seed)), int(n_sim), R,
        RANK_INVARIANCE_DF, fit3, mode="candidate")
    U_v2 = simulate_tree3_vine_uniforms(
        np.random.default_rng(int(cop_seed)), int(n_sim), R,
        RANK_INVARIANCE_DF, fit3, mode="vine2_boundary")
    U_frz = simulate_tree3_vine_uniforms(
        np.random.default_rng(int(cop_seed)), int(n_sim), R,
        RANK_INVARIANCE_DF, fit3, mode="frozen_t_boundary")
    return U_t3, U_v2, U_frz


def _component_scr_from_uniforms(
    agg: JointActionAggregator,
    U: np.ndarray,
    sigma: float,
    alpha: float,
    benefit_share: float,
    confidence: float,
) -> Tuple[float, float]:
    """(scr_without, scr_component) from a copula-uniform draw via the P26
    composition machinery (identical to composition_tree3_readout)."""
    comp = split_joint_composition(agg, U)
    V = comp["V"]
    v_cut = comp["V_cut"]
    pw = composition_with_actions(
        agg.rule, V, v_cut, agg.a_ref, sigma, alpha, benefit_share)
    m_wo = capital_metrics_from_liabilities(V, float(confidence), 12)
    m_cp = capital_metrics_from_liabilities(
        np.asarray(pw["W"], dtype=float), float(confidence), 12)
    return float(m_wo.scr_proxy), float(m_cp.scr_proxy)


def tree3_margin_bootstrap(
    losses_without: Dict[str, np.ndarray],
    correlation: np.ndarray,
    rule: ManagementActionRule,
    l_fit: float,
    anchor_means: Dict[str, float],
    fit3: Tree3VineFit,
    sigma: float,
    alpha: float,
    benefit_share: float,
    n_replicates: int = TREE3_BOOTSTRAP_REPLICATES,
    n_sim: int = TREE3_BOOTSTRAP_N_SIM,
    master_seed: int = TREE3_BOOTSTRAP_MASTER_SEED,
    confidence: float = 0.995,
    replicate_start: int = 0,
    replicate_stop: Optional[int] = None,
) -> Dict[str, object]:
    """Run replicates [replicate_start, replicate_stop) of the tree-3 vine
    bootstrap.

    Returns the per-replicate tree-3 candidate, 2-tree vine boundary and
    frozen-t boundary (all CRN) component SCRs plus the tree-3
    without-actions SCR and the paired deltas. Concatenate ``records`` across
    chunks (ordered by ``replicate_index``) to recover the full
    chunk-independent distribution.
    """
    drivers = list(losses_without.keys())
    n_obs = int(np.asarray(losses_without[drivers[0]]).size)
    stop = int(n_replicates) if replicate_stop is None else int(replicate_stop)
    seeds = _replicate_seeds(master_seed, n_replicates)
    R = np.asarray(correlation, dtype=float)
    records: List[Dict[str, float]] = []
    for r in range(int(replicate_start), stop):
        child = np.random.default_rng(seeds[r])
        idx = child.integers(0, n_obs, size=n_obs)
        res_losses = {k: np.asarray(losses_without[k], float)[idx]
                      for k in drivers}
        agg_b = JointActionAggregator(
            standalone_losses=res_losses, correlation=R,
            rule=rule, l_fit=l_fit, anchor_means=anchor_means)
        cop_seed = int(child.integers(0, 2**31 - 1))
        U_t3, U_v2, U_frz = _draw_uniforms_three(
            cop_seed, int(n_sim), R, fit3)
        wo_t3, comp_t3 = _component_scr_from_uniforms(
            agg_b, U_t3, sigma, alpha, benefit_share, confidence)
        _, comp_v2 = _component_scr_from_uniforms(
            agg_b, U_v2, sigma, alpha, benefit_share, confidence)
        _, comp_f = _component_scr_from_uniforms(
            agg_b, U_frz, sigma, alpha, benefit_share, confidence)
        records.append({
            "replicate_index": int(r),
            "scr_component_tree3": float(comp_t3),
            "scr_component_vine2": float(comp_v2),
            "scr_component_frozen_t": float(comp_f),
            "scr_without_tree3": float(wo_t3),
            "tree3_minus_vine2": float(comp_t3 - comp_v2),
            "tree3_minus_frozen": float(comp_t3 - comp_f),
            "cop_seed": cop_seed,
        })
    return {
        "n_obs": n_obs,
        "n_sim_per_replicate": int(n_sim),
        "master_seed": int(master_seed),
        "replicate_start": int(replicate_start),
        "replicate_stop": stop,
        "df_frozen": float(RANK_INVARIANCE_DF),
        "tree3_structure": "truncated_c_vine_credit_root_tree3",
        "resampling": (
            "joint row resample WITH replacement (preserves realised "
            "cross-driver pairing); copula Sigma + homogeneous df + frozen "
            "Phase 29 Task 2 pair-family fit + frozen Phase 30 Task 2 "
            "tree-3 selections (gaussian / zero strength) all FROZEN "
            "(SII Art. 234); tree-3 candidate vs 2-tree vine vs frozen-t "
            "boundary on COMMON base t-copula draw; per-replicate "
            "SeedSequence spawn (chunk-independent)"),
        "records": records,
    }


def tree3_stop_rule_assessment(
    ci_lo: float,
    ci_hi: float,
    nested_scr: float = NESTED_PATHWISE_SCR_REFERENCE,
) -> Dict[str, object]:
    """Record the pre-registered STOP-RULE TRIGGER status (design-note
    stop_rule block). The formal stop-rule DECISION (ending dependence-FORM
    escalation under MR-016) is taken at Task 4; this function only records
    whether the trigger condition is met, with no gate-shopping.
    """
    nested = float(nested_scr)
    inside = bool(float(ci_lo) <= nested <= float(ci_hi))
    return {
        "nested_pathwise_reference": nested,
        "tree3_ci_lo": float(ci_lo),
        "tree3_ci_hi": float(ci_hi),
        "nested_inside_tree3_95ci": inside,
        "stop_rule_trigger_met": (not inside),
        "stop_rule_decision_stage": "Phase 30 Task 4 (not this bootstrap)",
        "stop_rule_text": (
            "STOP-RULE (pre-registered, PHASE30_TASK1_DESIGN_NOTE): if the "
            "Phase 30 tree-3 vine still leaves the nested reference 46,638.9 "
            "outside its 95% bootstrap CI at Task 4, dependence-FORM "
            "escalation under MR-016 ENDS. No further copula-structure "
            "candidates may be opened without owner sign-off; Phase 31 "
            "becomes the owner decision package (option C), with option B "
            "available only as an owner-approved escalation funding a second "
            "independent nested run."),
        "interpretation": (
            "Nested 46,638.9 {} the tree-3 candidate 95% CI [{:.1f}, "
            "{:.1f}]; the pre-registered stop-rule trigger is {} - recorded "
            "here, decided at Task 4.").format(
            "INSIDE" if inside else "OUTSIDE",
            float(ci_lo), float(ci_hi),
            "NOT met" if inside else "MET"),
    }


def tree3_bootstrap_digest(records: Sequence[Dict[str, float]]) -> str:
    """Order-independent SHA-256 over the replicate SCR vectors."""
    ordered = sorted(records, key=lambda d: d["replicate_index"])
    payload = [
        [int(d["replicate_index"]),
         round(float(d["scr_component_tree3"]), 6),
         round(float(d["scr_component_vine2"]), 6),
         round(float(d["scr_component_frozen_t"]), 6),
         round(float(d["scr_without_tree3"]), 6)]
        for d in ordered
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def tree3_fit_digest(fit3_dict: Dict[str, object]) -> str:
    """Canonical digest of the FROZEN Phase 30 Task 2 tree-3 fit."""
    return hashlib.sha256(json.dumps(
        fit3_dict, sort_keys=True, default=float).encode()).hexdigest()[:12]


def tree3_bootstrap_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions (TAS M s3.2 / ASOP 56 s3.5)."""
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "The bootstrap resamples the realised standalone-loss rows only; "
            "it does NOT re-fit the vine (2-tree fit frozen at Phase 29 "
            "Task 2; tree-3 selections frozen at Phase 30 Task 2 - all four "
            "gaussian / zero strength), the copula Sigma / df, or the "
            "governed relief scalars (sigma/alpha/beta_fit) - SII Art. 234.",
            "Percentile CI/SE quantify Monte-Carlo + finite-sample "
            "uncertainty of the FROZEN tree-3 candidate component SCR; they "
            "do NOT quantify copula-form (margin-aggregation vs "
            "nested-dynamics) model error, which is disclosed separately "
            "(MR-016 / MR-017).",
            "The tree-3 vs 2-tree delta is EXACTLY zero by the bit-identity "
            "contract (zero-strength tree-3 layer); it is computed and "
            "disclosed per replicate, not assumed.",
            "The nested reference 46,638.9 is the single-path proxy nested "
            "truth (P25T2/P25T3); whether it falls outside the tree-3 95% CI "
            "feeds the pre-registered STOP-RULE, which is DECIDED at Phase "
            "30 Task 4, not by this bootstrap.",
            "Action / copula parameters remain educational placeholders "
            "pending credentialled data + independent APS X2 review.",
        ],
    }
