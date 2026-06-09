"""Phase 28 Task 4 - grouped-t copula within/cross-block, upper/lower
tail-dependence DIAGNOSTICS, MR-010/MR-014 refresh DECISION, and opening of
MR-016 (heterogeneous-tail / cross-block-dilution copula-FORM residual).

This task introduces NO new model parameter.  It REPORTS the within-block and
cross-block, upper (lambda_U) and lower (lambda_L) tail-dependence proxies and
their asymmetries for the FROZEN grouped-t copula draw (per-block df
df_NONFIN 37.866 / df_FIN 8.506 on the frozen Sigma) against the single-df t
(homogeneous boundary, all df_g = the frozen 2.9451 with one SHARED mixing
variate) on COMMON random numbers, re-drawn at the archived Phase 28 Task 3
per-replicate ``cop_seed`` values (so the canonical level p = 0.90 within/cross
upper read-outs reproduce the cached P28T3 bootstrap records BIT-identically).

Two asymmetries are characterised, both on common random numbers:

  * HETEROGENEITY (within-block vs cross-block): the grouped-t lever's reason
    for being.  ``heterogeneity_upper = max_g(within_block_upper_g) -
    cross_block_upper``.  The single-df t shares ONE radial mixing variate, so
    its within- and cross-block tail dependence are driven by the SAME df and
    Sigma; the grouped-t's independent per-block mixing is what can make
    within >> cross (or, here, dilute cross).
  * RADIAL (upper vs lower): ``radial_asym = lambda_U - lambda_L`` per block and
    cross.  The grouped/single t-copula is radially symmetric within a block, so
    this is a finite-sample / finite-n_sim diagnostic reported with a CI.

The HEADLINE finding (Phase 28 Task 2/3, RE-CONFIRMED here at the tail level):
the realised standalone within-FIN upper co-exceedance (0.125) sits BELOW the
cross-block level (0.172), so the leakage-free per-block df fit pushes df_FIN /
df_NONFIN ABOVE the frozen 2.9451 (lighter within-block tails) and the grouped-t
DILUTES cross-block co-movement relative to the single-df t's
maximal-cross-block boundary -> ``grouped cross_block_upper < single
cross_block_upper`` on CRN, i.e. ``grouped_minus_single_cross_upper < 0``.

MR refresh decision (pre-registered, Phase 28 Task 1 design note s5 / Task 3
hand-off).  MR-010 (var-cov aggregation understates diversified capital) and
MR-014 (management-action omission) are refreshed ONLY IF the GOVERNED HEADLINE
component SCR moves > 1%.  The governed headline basis is the frozen single-df
t (the maximal-cross-block-dependence, CONSERVATIVE boundary); the grouped-t is
a DISCLOSED two-sided diagnostic that moves the component SCR DOWN
(dilution, non-conservative) and is therefore NOT adopted into the governed
headline.  The single-df t homogeneous boundary recovers the frozen-t basis
EXACTLY (move 0.00%), so NO MR-010/MR-014 refresh is required; the DISCLOSED
grouped-t-vs-frozen-t move (-10.93% point / -10.66% bootstrap mean) is
documented, NOT actioned, and is tracked by the NEW MR-016 instead.

EDUCATIONAL MODEL: educational placeholders pending credentialled data and
independent APS X2 review.  NOT for production capital decisions.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Sequence

import numpy as np

from par_model_v2.projection.grouped_t_copula_aggregation import (
    BLOCKS,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
    TAIL_LEVEL_P,
    _tail_dependence_blocks,
)
from par_model_v2.projection.grouped_t_copula_bootstrap import (
    GROUPED_T_BOOTSTRAP_N_SIM,
    _draw_uniforms_both,
)

# ---------------------------------------------------------------------------
# Pre-registered diagnostics design (Phase 28 Task 4)
# ---------------------------------------------------------------------------
# Tail-threshold grid: the canonical Task 2/3 level 0.90 (the cross-check
# anchor) plus a symmetric spread to characterise the tail-level profile of the
# grouped-t vs single-df t draw.
TAIL_LEVEL_GRID = (0.80, 0.85, 0.90, 0.95)

# Archived P28T3 bootstrap means (200 x 20,000) - the MR-decision references.
# The single-df t mean is the frozen-t component basis (P26T3) recovered
# EXACTLY by the homogeneous boundary; the grouped-t mean is the disclosed
# diagnostic.
P28T3_GROUPED_T_COMPONENT_MEAN = 35372.49326229076
P28T3_SINGLE_T_COMPONENT_MEAN = 39595.06073760497
P26T3_FROZEN_T_COMPONENT_MEAN = 39595.06073760497   # == single-df t boundary
# Archived Task 2 point read-outs (the larger, conservative move reference).
TASK2_FROZEN_T_COMPONENT_POINT = FROZEN_T_COMPONENT_SCR_REFERENCE  # 39975.654628199336
TASK2_GROUPED_T_COMPONENT_POINT = 35604.39894619743

# MR refresh trigger: |relative move of the GOVERNED headline component SCR| > 1%.
MR_REFRESH_TRIGGER = 0.01
CROSSCHECK_TOL = 1e-12

_BLOCK_KEYS = ("nonfin", "fin")


def _p_key(p: float) -> str:
    return f"{int(round(float(p) * 100)):02d}"


def block_tail_dependence_grid(
    correlation: np.ndarray,
    block_dfs: Sequence[float],
    cop_seeds: Sequence[int],
    blocks: Sequence[Sequence[int]] = BLOCKS,
    homogeneous_df: float = RANK_INVARIANCE_DF,
    n_sim: int = GROUPED_T_BOOTSTRAP_N_SIM,
    p_grid: Sequence[float] = TAIL_LEVEL_GRID,
) -> Dict[str, object]:
    """Per-replicate within/cross-block upper & lower tail-dependence of the
    grouped-t vs single-df t copula draw over ``p_grid``, re-drawn at the
    archived P28T3 ``cop_seeds`` on COMMON random numbers.

    For each seed the grouped-t (per-block df) and single-df t (homogeneous
    boundary, shared mixing) uniforms are drawn on the SAME latent Gaussian via
    the tested :func:`...grouped_t_copula_bootstrap._draw_uniforms_both`, then
    :func:`...grouped_t_copula_aggregation._tail_dependence_blocks` reads the
    within-block (per block) and cross-block upper/lower co-exceedance proxies
    at each p.  At p = 0.90 the grouped-t within/cross upper read-outs reproduce
    the cached P28T3 records bit-identically.
    """
    R = np.asarray(correlation, dtype=float)
    blocks = [tuple(int(i) for i in blk) for blk in blocks]
    block_dfs = [float(g) for g in block_dfs]
    p_grid = tuple(float(p) for p in p_grid)
    records: List[Dict[str, object]] = []
    for r, seed in enumerate(cop_seeds):
        U_grp, U_sng = _draw_uniforms_both(
            int(seed), int(n_sim), R, block_dfs, blocks, float(homogeneous_df))
        rec: Dict[str, object] = {"replicate_index": int(r), "cop_seed": int(seed)}
        for p in p_grid:
            key = _p_key(p)
            tg = _tail_dependence_blocks(U_grp, blocks, float(p))
            ts = _tail_dependence_blocks(U_sng, blocks, float(p))
            for leg, td in (("grp", tg), ("sng", ts)):
                for bi, bk in enumerate(_BLOCK_KEYS):
                    wu = float(td["within_block_upper"][bi])
                    wl = float(td["within_block_lower"][bi])
                    rec[f"{leg}_within_upper_{bk}_{key}"] = wu
                    rec[f"{leg}_within_lower_{bk}_{key}"] = wl
                    rec[f"{leg}_within_radial_asym_{bk}_{key}"] = wu - wl
                cu = float(td["cross_block_upper"])
                cl = float(td["cross_block_lower"])
                rec[f"{leg}_cross_upper_{key}"] = cu
                rec[f"{leg}_cross_lower_{key}"] = cl
                rec[f"{leg}_cross_radial_asym_{key}"] = cu - cl
                rec[f"{leg}_heterogeneity_upper_{key}"] = float(
                    td["heterogeneity_upper"])
            # CRN contrasts (grouped-t minus single-df t)
            rec[f"grp_minus_sng_cross_upper_{key}"] = (
                rec[f"grp_cross_upper_{key}"] - rec[f"sng_cross_upper_{key}"])
            rec[f"grp_minus_sng_heterogeneity_upper_{key}"] = (
                rec[f"grp_heterogeneity_upper_{key}"]
                - rec[f"sng_heterogeneity_upper_{key}"])
            rec[f"grp_minus_sng_within_upper_fin_{key}"] = (
                rec[f"grp_within_upper_fin_{key}"]
                - rec[f"sng_within_upper_fin_{key}"])
        records.append(rec)
    return {
        "n_replicates": len(records),
        "n_sim_per_replicate": int(n_sim),
        "block_dfs_frozen": list(block_dfs),
        "homogeneous_df_frozen": float(homogeneous_df),
        "blocks": [list(map(int, b)) for b in blocks],
        "block_labels": list(_BLOCK_KEYS),
        "p_grid": list(p_grid),
        "tail_level_anchor": float(TAIL_LEVEL_P),
        "method": (
            "re-draw grouped-t (per-block df) and single-df t (homogeneous "
            "boundary, shared mixing) copula uniforms on COMMON random numbers "
            "(shared Gaussian latent on the frozen Sigma) at the archived P28T3 "
            "per-replicate cop_seeds; average pairwise within-block (per block) "
            "and cross-block upper/lower co-exceedance over the 7C2 pairs, "
            "normalised by (1-p); Sigma/df_g/homogeneous-df FROZEN (SII Art. 234)"),
        "records": records,
    }


def summarise_metric(values: Sequence[float],
                     ci_level: float = 0.95) -> Dict[str, float]:
    """Percentile bootstrap CI + SE for a per-replicate metric vector."""
    a = np.asarray(list(values), dtype=float)
    lo_q = (1.0 - float(ci_level)) / 2.0
    return {
        "n": int(a.size),
        "mean": float(np.mean(a)),
        "se": float(np.std(a, ddof=1)),
        "ci_level": float(ci_level),
        "ci_lo": float(np.quantile(a, lo_q)),
        "ci_hi": float(np.quantile(a, 1.0 - lo_q)),
        "min": float(np.min(a)),
        "max": float(np.max(a)),
    }


# Metrics summarised per p (block-suffixed ones are expanded over _BLOCK_KEYS).
_SCALAR_METRICS = (
    "grp_cross_upper", "grp_cross_lower", "grp_cross_radial_asym",
    "grp_heterogeneity_upper",
    "sng_cross_upper", "sng_cross_lower", "sng_cross_radial_asym",
    "sng_heterogeneity_upper",
    "grp_minus_sng_cross_upper", "grp_minus_sng_heterogeneity_upper",
    "grp_minus_sng_within_upper_fin",
)
_BLOCK_METRICS = (
    "grp_within_upper", "grp_within_lower", "grp_within_radial_asym",
    "sng_within_upper", "sng_within_lower", "sng_within_radial_asym",
)


def summarise_block_tail_diagnostics(
    grid: Dict[str, object],
    p_grid: Sequence[float] = TAIL_LEVEL_GRID,
    ci_level: float = 0.95,
) -> Dict[str, object]:
    """Mean + 95% CI per p for every within/cross, upper/lower, grouped/single
    metric and the CRN grouped-minus-single contrasts."""
    records = grid["records"]
    out: Dict[str, object] = {}
    for p in p_grid:
        key = _p_key(p)
        block: Dict[str, object] = {}
        for metric in _SCALAR_METRICS:
            vals = [rec[f"{metric}_{key}"] for rec in records]
            block[metric] = summarise_metric(vals, ci_level)
        for metric in _BLOCK_METRICS:
            for bk in _BLOCK_KEYS:
                name = f"{metric}_{bk}"
                vals = [rec[f"{name}_{key}"] for rec in records]
                block[name] = summarise_metric(vals, ci_level)
        out[f"p_{key}"] = block
    return out


def crosscheck_against_p28t3(
    grid: Dict[str, object],
    cached_records: Sequence[Dict[str, float]],
    tol: float = CROSSCHECK_TOL,
) -> Dict[str, object]:
    """At the canonical level p = TAIL_LEVEL_P, assert the recomputed
    per-replicate grouped-t within-block (NON-FIN, FIN) upper and cross-block
    upper co-exceedances and the heterogeneity_upper are BIT-identical to the
    cached P28T3 bootstrap records (faithful re-read, not a re-tuned recompute).
    """
    key = _p_key(TAIL_LEVEL_P)
    cached = {int(c["replicate_index"]): c for c in cached_records}
    max_dev_wn = max_dev_wf = max_dev_cu = max_dev_het = 0.0
    for rec in grid["records"]:
        c = cached[int(rec["replicate_index"])]
        max_dev_wn = max(max_dev_wn, abs(
            rec[f"grp_within_upper_nonfin_{key}"]
            - float(c["within_block_upper_nonfin"])))
        max_dev_wf = max(max_dev_wf, abs(
            rec[f"grp_within_upper_fin_{key}"]
            - float(c["within_block_upper_fin"])))
        max_dev_cu = max(max_dev_cu, abs(
            rec[f"grp_cross_upper_{key}"] - float(c["cross_block_upper"])))
        max_dev_het = max(max_dev_het, abs(
            rec[f"grp_heterogeneity_upper_{key}"]
            - float(c["heterogeneity_upper"])))
    max_dev = max(max_dev_wn, max_dev_wf, max_dev_cu, max_dev_het)
    return {
        "anchor_level_p": float(TAIL_LEVEL_P),
        "max_abs_dev_within_upper_nonfin": float(max_dev_wn),
        "max_abs_dev_within_upper_fin": float(max_dev_wf),
        "max_abs_dev_cross_upper": float(max_dev_cu),
        "max_abs_dev_heterogeneity_upper": float(max_dev_het),
        "max_abs_dev": float(max_dev),
        "bit_identical": bool(max_dev <= float(tol)),
    }


def mr_refresh_decision(
    scr_component_single_t: float = P28T3_SINGLE_T_COMPONENT_MEAN,
    scr_component_basis: float = P26T3_FROZEN_T_COMPONENT_MEAN,
    scr_component_grouped_t: float = P28T3_GROUPED_T_COMPONENT_MEAN,
    scr_grouped_t_point: float = TASK2_GROUPED_T_COMPONENT_POINT,
    scr_basis_point: float = TASK2_FROZEN_T_COMPONENT_POINT,
    trigger: float = MR_REFRESH_TRIGGER,
) -> Dict[str, object]:
    """Decide whether MR-010 / MR-014 require a refresh.

    The GOVERNED HEADLINE basis is the frozen single-df t (maximal-cross-block,
    conservative boundary).  The trigger is on the GOVERNED headline move; the
    grouped-t is a DISCLOSED two-sided diagnostic (it moves the component DOWN,
    non-conservative) and is NOT adopted into the headline.  The single-df t
    homogeneous boundary recovers the frozen-t basis EXACTLY, so the governed
    headline move is ~0% -> NO refresh.  The disclosed grouped-t-vs-frozen-t
    move is reported (documented, not actioned; tracked by MR-016).
    """
    move_governed = (float(scr_component_single_t) - float(scr_component_basis)) \
        / float(scr_component_basis)
    move_disclosed_grouped_boot = (
        float(scr_component_grouped_t) - float(scr_component_basis)) \
        / float(scr_component_basis)
    move_disclosed_grouped_point = (
        float(scr_grouped_t_point) - float(scr_basis_point)) \
        / float(scr_basis_point)
    refresh = bool(abs(move_governed) > float(trigger))
    return {
        "governed_headline_basis": "frozen single-df t (maximal-cross-block boundary)",
        "scr_component_single_t_mean": float(scr_component_single_t),
        "scr_component_basis_mean": float(scr_component_basis),
        "governed_headline_relative_move": float(move_governed),
        "scr_component_grouped_t_mean": float(scr_component_grouped_t),
        "disclosed_grouped_vs_basis_move_bootstrap_mean":
            float(move_disclosed_grouped_boot),
        "scr_grouped_t_point": float(scr_grouped_t_point),
        "scr_basis_point": float(scr_basis_point),
        "disclosed_grouped_vs_basis_move_point":
            float(move_disclosed_grouped_point),
        "trigger": float(trigger),
        "refresh_required": refresh,
        "decision": (
            "REFRESH MR-010/MR-014" if refresh else
            "NO refresh required (governed headline move {:.4%} <= 1% trigger)"
            .format(abs(move_governed))),
        "rationale": (
            "The grouped-t per-block df fitted leakage-free to the standalone "
            "within-block upper co-exceedances DILUTE cross-block co-movement "
            "and move the disclosed component SCR DOWN (-10.93% point / -10.66% "
            "bootstrap mean), which is non-conservative; the grouped-t is "
            "therefore DISCLOSED, not adopted into the governed headline. The "
            "governed headline remains the frozen single-df t (recovered "
            "EXACTLY by the homogeneous boundary, move 0.00%), so MR-010 "
            "(var-cov understatement) and MR-014 (management-action omission) "
            "quantifications are unchanged; the heterogeneous-tail / "
            "cross-block-dilution copula-FORM change is tracked by the NEW "
            "MR-016 instead."),
    }


def tail_diagnostics_digest(records: Sequence[Dict[str, object]]) -> str:
    """Order-independent SHA-256 over the per-replicate canonical-level
    grouped-t / single-df t within/cross upper vectors."""
    key = _p_key(TAIL_LEVEL_P)
    ordered = sorted(records, key=lambda d: d["replicate_index"])
    payload = [
        [int(d["replicate_index"]),
         round(float(d[f"grp_within_upper_nonfin_{key}"]), 9),
         round(float(d[f"grp_within_upper_fin_{key}"]), 9),
         round(float(d[f"grp_cross_upper_{key}"]), 9),
         round(float(d[f"sng_within_upper_nonfin_{key}"]), 9),
         round(float(d[f"sng_within_upper_fin_{key}"]), 9),
         round(float(d[f"sng_cross_upper_{key}"]), 9)]
        for d in ordered
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def tail_diagnostics_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions (TAS M s3.2 / ASOP 56 s3.5)."""
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "The diagnostics REPORT the FROZEN grouped-t copula within/cross "
            "tail dependence (Sigma / homogeneous df / per-block df_g FROZEN, "
            "SII Art. 234); no parameter is tuned.",
            "lambda_U / lambda_L are empirical average pairwise tail "
            "co-exceedance proxies over the 7 educational drivers at finite p "
            "and finite n_sim; they are not analytic coefficients of tail "
            "dependence and carry Monte-Carlo noise (CI reported).",
            "The grouped/single t-copula is radially symmetric within a block, "
            "so a non-zero within-block radial asymmetry (lambda_U - lambda_L) "
            "is finite-sample noise (CI spans 0), not a model feature; the "
            "informative asymmetry is HETEROGENEITY (within vs cross), the "
            "grouped-t lever, disclosed on common random numbers.",
            "The grouped-t DILUTES cross-block co-movement vs the single-df t's "
            "maximal-cross-block boundary (grp_minus_sng_cross_upper < 0), so "
            "the disclosed component SCR moves DOWN (non-conservative); the "
            "grouped-t is DISCLOSED, not adopted into the governed headline.",
            "MR-010 / MR-014 are NOT refreshed because the GOVERNED headline "
            "(frozen single-df t) move is 0.00% (< 1% trigger); the disclosed "
            "grouped-t move (-10.93%) is documented and tracked by MR-016.",
            "The copula-FORM residual to the nested truth WIDENS under the "
            "grouped-t (Phase 28 Task 3); it lives in nested inner-path joint "
            "dynamics a copula on standalone margins cannot represent, and "
            "escalates to the vine / pair-copula (Aas et al. 2009), Phase 29.",
            "Educational placeholders pending credentialled data + independent "
            "APS X2 review; NOT for production capital decisions.",
        ],
    }
