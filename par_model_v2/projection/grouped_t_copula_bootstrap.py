"""Phase 28 Task 3 - grouped t-copula margin bootstrap on the FULL re-aggregated
(component) basis + residual-gap RE-decomposition.

Non-parametric bootstrap over the realised standalone-loss observations (joint
row resample WITH replacement, preserving the realised cross-driver pairing);
the copula correlation Sigma, the homogeneous df, AND the fitted per-BLOCK
degrees of freedom ``block_dfs`` (df_NONFIN, df_FIN) stay FROZEN inside every
replicate (Solvency II Art. 234 - the governed dependence basis, now including
the Phase 28 Task 2 grouped-t per-block lever, is NOT re-tuned).  Each replicate
re-runs the Phase 28 Task 2 grouped-t component re-aggregation and, on COMMON
RANDOM NUMBERS (the SAME latent Gaussian draw on the frozen Sigma), the nested
single-df t variant (all df_g = the frozen df with one shared mixing variate),
so the per-replicate (grouped-t minus single-t) difference isolates the
per-block-df heterogeneity effect.

Common random numbers
---------------------
The grouped-t lever IS the radial mixing structure (independent per block vs one
shared variate), so a perfect CRN on the mixing is impossible by construction.
The defensible CRN here shares the GAUSSIAN copula latent ``Z = N(0, Sigma)``:
both variants are drawn from two generators seeded with the SAME per-replicate
``cop_seed`` and call the IDENTICAL
:func:`...grouped_t_copula_aggregation.simulate_grouped_t_copula_uniforms`, whose
first action is the shared ``rng.standard_normal((n, d)) @ chol.T`` draw.  The
grouped-t variant then draws INDEPENDENT per-block chi-square mixing (block 0
reuses the rng position the single-t shared mixing occupies); the single-t
variant draws ONE shared chi-square.  The shared Gaussian latent makes the
(grouped-t minus single-t) contrast a clean common-random-number comparison of
the heterogeneity lever, exactly mirroring the Phase 27 Task 3 skew-t pattern
(which shared Z and W and varied only gamma).

Determinism / resumability: replicate ``r`` always draws from
``SeedSequence(master_seed).spawn(n_replicates)[r]`` regardless of how the
replicate range is chunked, so partial stages concatenate to a
chunk-independent, digest-identical result (resume-safe under the
wall-clock-limited shell).  The per-replicate draws are bit-identical to the
tested :func:`...grouped_t_copula_aggregation.simulate_grouped_t_copula_uniforms`.

HEADLINE gate (pre-registered, Phase 28 Task 1 design note s5): the nested
path-wise truth 46,638.9 lies INSIDE the grouped-t component-basis 95% bootstrap
CI; ELSE the residual gap to nested MUST be RE-decomposed (copula-form vs
relief-surface) and the CHANGE vs the skew-t-reconfirmed copula-form residual
6,114.9 (and the frozen-t baseline 6,120.2) quantified - no silent acceptance.
Given the Task 2 material finding (the fitted per-block df DILUTE cross-block
co-movement, moving the component SCR DOWN to 35,604.4), the prior expectation
is the residual WIDENS; a widening is INFORMATIVE (it confirms the standalone
margins carry no within-block tail concentration and escalates to the vine /
pair-copula, Aas et al. 2009, Phase 29) and is DISCLOSED, NOT gate-failed.
DIRECTIONAL diagnostic: the per-replicate (grouped-t minus single-t) sign is
reported on common random numbers and disclosed, not gated (the grouped-t is a
genuinely two-sided heterogeneity lever).

EDUCATIONAL MODEL: educational placeholders pending credentialled data and
independent APS X2 review.  NOT for production capital decisions.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from par_model_v2.projection.grouped_t_copula_aggregation import (
    BLOCKS,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    FROZEN_T_COPULA_FORM_RESIDUAL_ABS,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
    TAIL_LEVEL_P,
    _cross_pairs,
    _within_pairs,
    simulate_grouped_t_copula_uniforms,
)
from par_model_v2.projection.joint_action_aggregation import (
    JointActionAggregator,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.pathwise_composition_transform import (
    composition_with_actions,
    split_joint_composition,
)

# ---------------------------------------------------------------------------
# Pre-registered bootstrap design (Phase 28 Task 1 design note s5; P26T3/P27T3
# pattern - IDENTICAL replicate/sim counts, seed, and SE gate).
# ---------------------------------------------------------------------------
GROUPED_T_BOOTSTRAP_REPLICATES = 200
GROUPED_T_BOOTSTRAP_N_SIM = 20_000
GROUPED_T_BOOTSTRAP_MASTER_SEED = 20260608
SE_GATE_FRACTION = 0.05            # bootstrap SE <= 5% of mean component SCR

# Governed relief-surface relative SCR error (P25T3 OOS) - the SAME value used
# in the Phase 26/27 Task 3 re-decompositions; reused FROZEN (no re-tuning).
RELIEF_SURFACE_REL_ERR_SOURCE = 0.01164368805922599


def _replicate_seeds(master_seed: int,
                     n_replicates: int) -> List[np.random.SeedSequence]:
    """Chunk-independent per-replicate seed sequences (resume-safe)."""
    return list(np.random.SeedSequence(int(master_seed)).spawn(int(n_replicates)))


def _draw_uniforms_both(
    cop_seed: int,
    n_sim: int,
    correlation: np.ndarray,
    block_dfs: Sequence[float],
    blocks: Sequence[Sequence[int]],
    homogeneous_df: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Draw grouped-t (per-block df) AND single-df t (homogeneous boundary)
    uniforms on COMMON random numbers (the SAME latent Gaussian draw on the
    frozen Sigma).

    Both variants call the tested
    :func:`...grouped_t_copula_aggregation.simulate_grouped_t_copula_uniforms`
    with generators seeded by the SAME ``cop_seed``; the shared first draw is the
    Gaussian copula latent ``Z = standard_normal @ chol.T``.  The grouped-t
    variant then uses independent per-block chi-square mixing; the single-t
    variant (``shared_mixing=True``, all df = ``homogeneous_df``) uses one shared
    chi-square and recovers the frozen single-df t exactly.
    """
    R = np.asarray(correlation, dtype=float)
    rng_g = np.random.default_rng(int(cop_seed))
    U_grp = simulate_grouped_t_copula_uniforms(
        rng_g, int(n_sim), R, [float(g) for g in block_dfs], blocks,
        shared_mixing=False)
    rng_s = np.random.default_rng(int(cop_seed))
    U_sng = simulate_grouped_t_copula_uniforms(
        rng_s, int(n_sim), R, [float(homogeneous_df)] * len(list(blocks)),
        blocks, shared_mixing=True)
    return U_grp, U_sng


def _component_scr_from_uniforms(
    agg: JointActionAggregator,
    U: np.ndarray,
    sigma: float,
    alpha: float,
    benefit_share: float,
    confidence: float,
) -> Tuple[float, float]:
    """(scr_without, scr_component) from a copula-uniform draw - the P26T2
    relief machinery, identical to
    :func:`...grouped_t_copula_aggregation.composition_grouped_t_readout`."""
    comp = split_joint_composition(agg, U)
    V = comp["V"]
    v_cut = comp["V_cut"]
    pw = composition_with_actions(
        agg.rule, V, v_cut, agg.a_ref, sigma, alpha, benefit_share)
    m_wo = capital_metrics_from_liabilities(V, float(confidence), 12)
    m_cp = capital_metrics_from_liabilities(
        np.asarray(pw["W"], dtype=float), float(confidence), 12)
    return float(m_wo.scr_proxy), float(m_cp.scr_proxy)


def _avg_pairwise_over(U: np.ndarray, p: float,
                       pairs: Sequence[Tuple[int, int]], upper: bool) -> float:
    if not pairs:
        return float("nan")
    if upper:
        vals = [float(((U[:, i] > p) & (U[:, j] > p)).mean()) / (1.0 - p)
                for i, j in pairs]
    else:
        q = 1.0 - p
        vals = [float(((U[:, i] < q) & (U[:, j] < q)).mean()) / (1.0 - p)
                for i, j in pairs]
    return float(np.mean(vals))


def _block_tail_summary(U: np.ndarray, blocks: Sequence[Sequence[int]],
                        p: float) -> Dict[str, object]:
    """Within/cross-block upper co-exceedance + heterogeneity of one draw."""
    within_u = [_avg_pairwise_over(U, p, _within_pairs(blk), True)
                for blk in blocks]
    cross_pairs: List[Tuple[int, int]] = []
    for a in range(len(blocks)):
        for b in range(a + 1, len(blocks)):
            cross_pairs += _cross_pairs(blocks[a], blocks[b])
    cross_u = _avg_pairwise_over(U, p, cross_pairs, True)
    return {
        "within_block_upper": [float(x) for x in within_u],
        "cross_block_upper": float(cross_u),
        "heterogeneity_upper": float(max(within_u) - cross_u),
    }


def grouped_t_margin_bootstrap(
    losses_without: Dict[str, np.ndarray],
    correlation: np.ndarray,
    rule: ManagementActionRule,
    l_fit: float,
    anchor_means: Dict[str, float],
    block_dfs: Sequence[float],
    homogeneous_df: float,
    sigma: float,
    alpha: float,
    benefit_share: float,
    blocks: Sequence[Sequence[int]] = BLOCKS,
    n_replicates: int = GROUPED_T_BOOTSTRAP_REPLICATES,
    n_sim: int = GROUPED_T_BOOTSTRAP_N_SIM,
    master_seed: int = GROUPED_T_BOOTSTRAP_MASTER_SEED,
    confidence: float = 0.995,
    replicate_start: int = 0,
    replicate_stop: Optional[int] = None,
) -> Dict[str, object]:
    """Run replicates [replicate_start, replicate_stop) of the grouped-t bootstrap.

    Returns the per-replicate grouped-t and single-df-t (homogeneous boundary,
    CRN) component SCRs plus the grouped-t without-actions SCR and the realised
    within/cross-block upper tail-dependence of the draw.  Concatenate
    ``records`` across chunks (ordered by ``replicate_index``) to recover the
    full chunk-independent distribution.
    """
    drivers = list(losses_without.keys())
    n_obs = int(np.asarray(losses_without[drivers[0]]).size)
    stop = int(n_replicates) if replicate_stop is None else int(replicate_stop)
    seeds = _replicate_seeds(master_seed, n_replicates)
    R = np.asarray(correlation, dtype=float)
    blocks = [tuple(int(i) for i in blk) for blk in blocks]
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
        U_grp, U_sng = _draw_uniforms_both(
            cop_seed, int(n_sim), R, block_dfs, blocks, homogeneous_df)
        wo_grp, comp_grp = _component_scr_from_uniforms(
            agg_b, U_grp, sigma, alpha, benefit_share, confidence)
        _, comp_sng = _component_scr_from_uniforms(
            agg_b, U_sng, sigma, alpha, benefit_share, confidence)
        tail = _block_tail_summary(U_grp, blocks, TAIL_LEVEL_P)
        records.append({
            "replicate_index": int(r),
            "scr_component_grouped_t": float(comp_grp),
            "scr_component_single_t": float(comp_sng),
            "scr_without_grouped_t": float(wo_grp),
            "grouped_minus_single": float(comp_grp - comp_sng),
            "within_block_upper_nonfin": float(tail["within_block_upper"][0]),
            "within_block_upper_fin": float(tail["within_block_upper"][1]),
            "cross_block_upper": float(tail["cross_block_upper"]),
            "heterogeneity_upper": float(tail["heterogeneity_upper"]),
            "cop_seed": cop_seed,
        })
    return {
        "n_obs": n_obs,
        "n_sim_per_replicate": int(n_sim),
        "master_seed": int(master_seed),
        "replicate_start": int(replicate_start),
        "replicate_stop": stop,
        "block_dfs_frozen": [float(g) for g in block_dfs],
        "homogeneous_df_frozen": float(homogeneous_df),
        "blocks": [list(map(int, b)) for b in blocks],
        "resampling": (
            "joint row resample WITH replacement (preserves realised "
            "cross-driver pairing); copula Sigma + homogeneous df + per-block "
            "df_g FROZEN (SII Art. 234); grouped-t vs single-df t on COMMON "
            "Gaussian latent (shared Z; per-block-mixing IS the lever); "
            "per-replicate SeedSequence spawn (chunk-independent)"),
        "records": records,
    }


def summarise_ci(values: Sequence[float],
                 ci_level: float = 0.95) -> Dict[str, float]:
    """Percentile bootstrap CI + SE for a replicate vector."""
    a = np.asarray(list(values), dtype=float)
    lo_q = (1.0 - float(ci_level)) / 2.0
    hi_q = 1.0 - lo_q
    return {
        "n": int(a.size),
        "mean": float(np.mean(a)),
        "se": float(np.std(a, ddof=1)),
        "se_frac_of_mean": float(np.std(a, ddof=1) / np.mean(a)),
        "ci_level": float(ci_level),
        "ci_lo": float(np.quantile(a, lo_q)),
        "ci_hi": float(np.quantile(a, hi_q)),
        "min": float(np.min(a)),
        "max": float(np.max(a)),
    }


def redecompose_residual_gap(
    scr_component_grouped_t: float,
    scr_component_single_t: float,
    nested_scr: float,
    relief_surface_rel_err: float,
    copula_form_residual_skewt_reconfirmed: float =
        SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
    copula_form_residual_frozen_t: float = FROZEN_T_COPULA_FORM_RESIDUAL_ABS,
) -> Dict[str, object]:
    """RE-decompose the residual SCR gap (nested - grouped-t component) into a
    relief-surface part (bounded by the governed P25T3 OOS SCR rel error) and a
    copula-form residual, and quantify the CHANGE of the copula-form residual vs
    BOTH the skew-t-reconfirmed baseline 6,114.9 (Phase 27 Task 3) and the
    frozen-t baseline 6,120.2 attributable to the per-block-df heterogeneity
    lever.  A WIDENING (positive change) is INFORMATIVE - it confirms the
    standalone margins carry no within-block tail concentration and escalates to
    the vine (Phase 29); it is disclosed, NOT gate-failed.
    """
    nested = float(nested_scr)
    comp_g = float(scr_component_grouped_t)
    comp_s = float(scr_component_single_t)
    gap_total = nested - comp_g
    relief_part = float(relief_surface_rel_err) * nested
    copula_form_residual = gap_total - relief_part
    change_vs_skewt = copula_form_residual - float(
        copula_form_residual_skewt_reconfirmed)
    change_vs_frozen_t = copula_form_residual - float(
        copula_form_residual_frozen_t)
    grouped_lift = comp_g - comp_s          # heterogeneity effect on CRN
    widened = bool(change_vs_skewt > 0.0)
    return {
        "nested_scr": nested,
        "scr_component_grouped_t": comp_g,
        "scr_component_single_t": comp_s,
        "gap_total_abs": gap_total,
        "gap_total_rel_to_nested": gap_total / nested,
        "relief_surface_rel_err_source": float(relief_surface_rel_err),
        "relief_surface_part_abs": relief_part,
        "relief_surface_share_of_gap": relief_part / gap_total,
        "copula_form_residual_abs": copula_form_residual,
        "copula_form_share_of_gap": copula_form_residual / gap_total,
        "copula_form_residual_skewt_reconfirmed":
            float(copula_form_residual_skewt_reconfirmed),
        "copula_form_residual_frozen_t": float(copula_form_residual_frozen_t),
        "copula_form_residual_change_vs_skewt_abs": change_vs_skewt,
        "copula_form_residual_change_vs_skewt_rel":
            change_vs_skewt / float(copula_form_residual_skewt_reconfirmed),
        "copula_form_residual_change_vs_frozen_t_abs": change_vs_frozen_t,
        "copula_form_residual_change_vs_frozen_t_rel":
            change_vs_frozen_t / float(copula_form_residual_frozen_t),
        "grouped_minus_single_lift": grouped_lift,
        "copula_form_residual_widened_vs_skewt": widened,
        "copula_form_dominant": bool(copula_form_residual > relief_part),
        "residual_closed_by_grouped_t": bool(copula_form_residual <= relief_part),
        "interpretation": (
            "The per-block df_g fitted leakage-free to the standalone "
            "within-block upper co-exceedances DILUTE cross-block co-movement "
            "(Task 2 material finding: df_NONFIN 37.866, df_FIN 8.506, both "
            "ABOVE the frozen 2.9451; the single-df t shares ONE mixing variate "
            "and is the maximal-cross-block-dependence boundary). On common "
            "random numbers the grouped-t lifts the component SCR by {:+.1f} vs "
            "the single-df t; the copula-form residual moves from the "
            "skew-t-reconfirmed {:.1f} to {:.1f} (a change of {:+.1f}, "
            "{:+.2%}). The residual {} - {} a single copula on the standalone "
            "margins (whether asymmetric, skew-t, or block-heterogeneous, "
            "grouped-t) does NOT close the UPWARD nested residual; it lives in "
            "the nested inner-path joint dynamics. The vine / pair-copula (Aas "
            "et al. 2009) remains the general fallback (Phase 29)."
        ).format(
            grouped_lift,
            float(copula_form_residual_skewt_reconfirmed),
            copula_form_residual, change_vs_skewt,
            change_vs_skewt / float(copula_form_residual_skewt_reconfirmed),
            ("WIDENS (informative -> vine escalation)" if widened
             else "narrows but is not closed"),
            "confirming that"),
    }


def bootstrap_digest(records: Sequence[Dict[str, float]]) -> str:
    """Order-independent SHA-256 over the replicate SCR vectors."""
    ordered = sorted(records, key=lambda d: d["replicate_index"])
    payload = [
        [int(d["replicate_index"]),
         round(float(d["scr_component_grouped_t"]), 6),
         round(float(d["scr_component_single_t"]), 6),
         round(float(d["scr_without_grouped_t"]), 6)]
        for d in ordered
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def grouped_t_bootstrap_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions (TAS M s3.2 / ASOP 56 s3.5)."""
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "The bootstrap resamples the realised standalone-loss rows only; "
            "it does NOT re-tune the copula (Sigma / homogeneous df / per-block "
            "df_g FROZEN) or the governed relief scalars (sigma/alpha/beta_fit) "
            "- SII Art. 234.",
            "Percentile CI/SE quantify Monte-Carlo + finite-sample uncertainty "
            "of the FROZEN grouped-t component SCR; they do NOT quantify "
            "copula-form (margin-aggregation vs nested-dynamics) model error, "
            "which is RE-decomposed and disclosed separately.",
            "The grouped-t vs single-df t contrast shares the Gaussian copula "
            "latent (CRN); the per-block radial mixing IS the heterogeneity "
            "lever and therefore differs by construction. The per-replicate "
            "lift sign is disclosed, not gated (the lever is two-sided).",
            "The nested reference 46,638.9 is the single-path proxy nested "
            "truth (P25T2/P25T3); the residual gap to it is a disclosed "
            "model-form limitation. A WIDENING of the copula-form residual is "
            "INFORMATIVE (the standalone margins carry no within-block tail "
            "concentration), not a gate failure; it escalates to the vine / "
            "pair-copula (Aas et al. 2009), Phase 29.",
            "Action / copula parameters remain educational placeholders "
            "pending credentialled data + independent APS X2 review.",
        ],
    }
