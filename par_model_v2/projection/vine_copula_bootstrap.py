"""
Phase 29 Task 3 - vine / pair-copula margin bootstrap on the component basis.

Pre-registered design (Phase 29 Task 1 design note, Task 3 block):

* at least 200 x 20,000 bootstrap replicates (P26T3 / P27T3 / P28T3 pattern);
* HEADLINE: the nested path-wise truth 46,638.9 lies inside the vine-candidate
  component-basis 95% bootstrap CI, OR the residual gap is RE-decomposed with
  the CHANGE of the copula-form residual quantified against BOTH the grouped-t
  residual 10,491.5 (Phase 28 Task 3) and the skew-t-reconfirmed residual
  6,114.9 (Phase 27 Task 3) -- the re-decomposition is itself an accepted,
  pre-registered outcome;
* bootstrap SE <= 5% of the mean vine-candidate component SCR.

The bootstrap resamples the realised standalone-loss rows ONLY (joint row
resample WITH replacement, preserving the realised cross-driver pairing). The
copula stays FROZEN inside every replicate: frozen Sigma, homogeneous df
2.9451, and the FROZEN Phase 29 Task 2 leakage-free pair-family fit
(families / strengths / structure). The governed relief scalars
(sigma / alpha / beta_fit) are similarly frozen (SII Art. 234).

The vine candidate and the frozen-t boundary are evaluated on COMMON random
numbers: both modes consume the SAME base single-df t-copula draw (the
candidate applies only deterministic pair-link tail tilts plus re-ranking on
top of that draw), so the per-replicate (vine - frozen-t) difference isolates
the pair-link dependence effect. EDUCATIONAL ONLY.
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
from par_model_v2.projection.vine_copula_pair_aggregation import (
    VinePairFit,
    simulate_vine_pair_copula_uniforms,
)
from par_model_v2.projection.vine_copula_upgrade import (
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
)

VINE_BOOTSTRAP_REPLICATES = 200
VINE_BOOTSTRAP_N_SIM = 20_000
VINE_BOOTSTRAP_MASTER_SEED = 20260610
SE_GATE_FRACTION = 0.05                # bootstrap SE <= 5% of mean component SCR

#: Archived Phase 29 Task 2 candidate component read-out (200k, seed 20260607)
#: -- the bit-identical archive cross-check target alongside the frozen-t
#: reference 39,975.654628199336.
VINE_CANDIDATE_COMPONENT_SCR_POINT = 42_458.5527095696


def _replicate_seeds(master_seed: int,
                     n_replicates: int) -> List[np.random.SeedSequence]:
    """Chunk-independent per-replicate seed sequences (resume-safe)."""
    return list(np.random.SeedSequence(int(master_seed)).spawn(int(n_replicates)))


def _draw_uniforms_both(
    cop_seed: int,
    n_sim: int,
    correlation: np.ndarray,
    fit: VinePairFit,
) -> Tuple[np.ndarray, np.ndarray]:
    """Draw vine-candidate AND frozen-t boundary uniforms on COMMON random
    numbers.

    Both modes seed a fresh generator with the SAME ``cop_seed``; the first
    (and only) stochastic step in either mode is the identical base single-df
    t-copula draw on the frozen Sigma / df 2.9451. The candidate then applies
    only deterministic conditional pair-link tail tilts and re-ranking, so the
    boundary draw IS the candidate's latent base (CRN by construction).
    """
    R = np.asarray(correlation, dtype=float)
    rng_c = np.random.default_rng(int(cop_seed))
    U_cand = simulate_vine_pair_copula_uniforms(
        rng_c, int(n_sim), R, RANK_INVARIANCE_DF, fit, mode="candidate")
    rng_f = np.random.default_rng(int(cop_seed))
    U_frz = simulate_vine_pair_copula_uniforms(
        rng_f, int(n_sim), R, RANK_INVARIANCE_DF, fit, mode="frozen_t_boundary")
    return U_cand, U_frz


def _component_scr_from_uniforms(
    agg: JointActionAggregator,
    U: np.ndarray,
    sigma: float,
    alpha: float,
    benefit_share: float,
    confidence: float,
) -> Tuple[float, float]:
    """(scr_without, scr_component) from a copula-uniform draw via the P26
    composition machinery (identical to composition_vine_pair_readout)."""
    comp = split_joint_composition(agg, U)
    V = comp["V"]
    v_cut = comp["V_cut"]
    pw = composition_with_actions(
        agg.rule, V, v_cut, agg.a_ref, sigma, alpha, benefit_share)
    m_wo = capital_metrics_from_liabilities(V, float(confidence), 12)
    m_cp = capital_metrics_from_liabilities(
        np.asarray(pw["W"], dtype=float), float(confidence), 12)
    return float(m_wo.scr_proxy), float(m_cp.scr_proxy)


def vine_margin_bootstrap(
    losses_without: Dict[str, np.ndarray],
    correlation: np.ndarray,
    rule: ManagementActionRule,
    l_fit: float,
    anchor_means: Dict[str, float],
    fit: VinePairFit,
    sigma: float,
    alpha: float,
    benefit_share: float,
    n_replicates: int = VINE_BOOTSTRAP_REPLICATES,
    n_sim: int = VINE_BOOTSTRAP_N_SIM,
    master_seed: int = VINE_BOOTSTRAP_MASTER_SEED,
    confidence: float = 0.995,
    replicate_start: int = 0,
    replicate_stop: Optional[int] = None,
) -> Dict[str, object]:
    """Run replicates [replicate_start, replicate_stop) of the vine bootstrap.

    Returns the per-replicate vine-candidate and frozen-t boundary (CRN)
    component SCRs plus the vine without-actions SCR. Concatenate ``records``
    across chunks (ordered by ``replicate_index``) to recover the full
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
        U_cand, U_frz = _draw_uniforms_both(cop_seed, int(n_sim), R, fit)
        wo_v, comp_v = _component_scr_from_uniforms(
            agg_b, U_cand, sigma, alpha, benefit_share, confidence)
        _, comp_f = _component_scr_from_uniforms(
            agg_b, U_frz, sigma, alpha, benefit_share, confidence)
        records.append({
            "replicate_index": int(r),
            "scr_component_vine": float(comp_v),
            "scr_component_frozen_t": float(comp_f),
            "scr_without_vine": float(wo_v),
            "vine_minus_frozen": float(comp_v - comp_f),
            "cop_seed": cop_seed,
        })
    return {
        "n_obs": n_obs,
        "n_sim_per_replicate": int(n_sim),
        "master_seed": int(master_seed),
        "replicate_start": int(replicate_start),
        "replicate_stop": stop,
        "df_frozen": float(RANK_INVARIANCE_DF),
        "fit_structure": fit.structure,
        "resampling": (
            "joint row resample WITH replacement (preserves realised "
            "cross-driver pairing); copula Sigma + homogeneous df + Phase 29 "
            "Task 2 pair-family fit FROZEN (SII Art. 234); vine candidate vs "
            "frozen-t boundary on COMMON base t-copula draw (the candidate "
            "tilt is deterministic given the base); per-replicate "
            "SeedSequence spawn (chunk-independent)"),
        "records": records,
    }


def redecompose_vine_residual_gap(
    scr_component_vine: float,
    scr_component_frozen_t: float,
    nested_scr: float = NESTED_PATHWISE_SCR_REFERENCE,
    relief_surface_rel_err: float = RELIEF_SURFACE_REL_ERR_SOURCE,
    copula_form_residual_grouped_t: float = GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    copula_form_residual_skewt: float =
        SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
) -> Dict[str, object]:
    """RE-decompose the residual SCR gap (nested - vine candidate component)
    into a relief-surface part (bounded by the governed P25T3 OOS SCR rel
    error) and a copula-form residual, and quantify the CHANGE of the
    copula-form residual vs BOTH the grouped-t baseline 10,491.5 (Phase 28
    Task 3) and the skew-t-reconfirmed baseline 6,114.9 (Phase 27 Task 3).
    A NARROWING confirms the pre-registered pair-link escalation direction;
    either sign is DISCLOSED, not gate-failed.
    """
    nested = float(nested_scr)
    comp_v = float(scr_component_vine)
    comp_f = float(scr_component_frozen_t)
    gap_total = nested - comp_v
    relief_part = float(relief_surface_rel_err) * nested
    copula_form_residual = gap_total - relief_part
    change_vs_grouped = copula_form_residual - float(copula_form_residual_grouped_t)
    change_vs_skewt = copula_form_residual - float(copula_form_residual_skewt)
    vine_lift = comp_v - comp_f            # pair-link effect on CRN
    narrowed_vs_skewt = bool(change_vs_skewt < 0.0)
    return {
        "nested_scr": nested,
        "scr_component_vine": comp_v,
        "scr_component_frozen_t": comp_f,
        "gap_total_abs": gap_total,
        "gap_total_rel_to_nested": gap_total / nested,
        "relief_surface_rel_err_source": float(relief_surface_rel_err),
        "relief_surface_part_abs": relief_part,
        "relief_surface_share_of_gap": relief_part / gap_total,
        "copula_form_residual_abs": copula_form_residual,
        "copula_form_share_of_gap": copula_form_residual / gap_total,
        "copula_form_residual_grouped_t": float(copula_form_residual_grouped_t),
        "copula_form_residual_skewt": float(copula_form_residual_skewt),
        "copula_form_residual_change_vs_grouped_t_abs": change_vs_grouped,
        "copula_form_residual_change_vs_grouped_t_rel":
            change_vs_grouped / float(copula_form_residual_grouped_t),
        "copula_form_residual_change_vs_skewt_abs": change_vs_skewt,
        "copula_form_residual_change_vs_skewt_rel":
            change_vs_skewt / float(copula_form_residual_skewt),
        "vine_minus_frozen_lift": vine_lift,
        "copula_form_residual_narrowed_vs_skewt": narrowed_vs_skewt,
        "copula_form_dominant": bool(copula_form_residual > relief_part),
        "residual_closed_by_vine": bool(copula_form_residual <= relief_part),
        "interpretation": (
            "The truncated credit-root pair-link candidate lifts the component "
            "SCR by {:+.1f} vs the frozen-t boundary on common random numbers. "
            "The copula-form residual moves from the grouped-t 10,491.5 / "
            "skew-t-reconfirmed 6,114.9 baselines to {:.1f} (change vs "
            "grouped-t {:+.1f} = {:+.2%}; vs skew-t {:+.1f} = {:+.2%}). The "
            "residual {} the skew-t baseline -- the FIRST dependence candidate "
            "to move the margin-aggregation read-out TOWARD the nested "
            "path-wise truth; the remaining residual lives in the nested "
            "inner-path joint dynamics and is a disclosed model-form "
            "limitation (MR-016), decided in Task 4."
        ).format(
            vine_lift, copula_form_residual,
            change_vs_grouped,
            change_vs_grouped / float(copula_form_residual_grouped_t),
            change_vs_skewt,
            change_vs_skewt / float(copula_form_residual_skewt),
            ("NARROWS below" if narrowed_vs_skewt else "does NOT narrow below"),
        ),
    }


def vine_bootstrap_digest(records: Sequence[Dict[str, float]]) -> str:
    """Order-independent SHA-256 over the replicate SCR vectors."""
    ordered = sorted(records, key=lambda d: d["replicate_index"])
    payload = [
        [int(d["replicate_index"]),
         round(float(d["scr_component_vine"]), 6),
         round(float(d["scr_component_frozen_t"]), 6),
         round(float(d["scr_without_vine"]), 6)]
        for d in ordered
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def vine_fit_digest(fit_dict: Dict[str, object]) -> str:
    """Canonical digest of the FROZEN Phase 29 Task 2 pair-family fit."""
    return hashlib.sha256(json.dumps(
        fit_dict, sort_keys=True, default=float).encode()).hexdigest()[:12]


def vine_bootstrap_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions (TAS M s3.2 / ASOP 56 s3.5)."""
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "The bootstrap resamples the realised standalone-loss rows only; "
            "it does NOT re-fit the vine (structure / families / strengths "
            "FROZEN at the Phase 29 Task 2 leakage-free fit), the copula "
            "Sigma / df, or the governed relief scalars (sigma/alpha/beta_fit) "
            "- SII Art. 234.",
            "Percentile CI/SE quantify Monte-Carlo + finite-sample uncertainty "
            "of the FROZEN vine-candidate component SCR; they do NOT quantify "
            "copula-form (margin-aggregation vs nested-dynamics) model error, "
            "which is RE-decomposed and disclosed separately.",
            "The vine vs frozen-t contrast shares the base t-copula draw "
            "(CRN); the deterministic pair-link tilt IS the dependence lever "
            "and therefore differs by construction. The per-replicate lift "
            "sign is disclosed, not gated.",
            "The nested reference 46,638.9 is the single-path proxy nested "
            "truth (P25T2/P25T3); the residual gap to it is a disclosed "
            "model-form limitation (MR-016). The remediation decision is "
            "Phase 29 Task 4, not this bootstrap.",
            "Action / copula parameters remain educational placeholders "
            "pending credentialled data + independent APS X2 review.",
        ],
    }
