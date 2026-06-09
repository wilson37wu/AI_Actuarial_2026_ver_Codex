"""Phase 27 Task 4 - skew-t copula upper/lower tail-dependence DIAGNOSTICS
+ MR-010/MR-014 refresh decision.

This module does NOT introduce any new model parameter.  It REPORTS the
upper/lower tail-dependence (lambda_U, lambda_L) and the radial asymmetry
(lambda_U - lambda_L) of the FROZEN skew-t copula draw (df 2.9451, rho,
gamma_hat ~ 6.24e-5) against the symmetric-t (gamma = 0) basis, over a grid
of tail thresholds p, and decides whether the headline SCR moved enough to
trigger an MR-010 / MR-014 refresh.

Reproducibility / archive cross-check.  The Phase 27 Task 3 bootstrap drew, per
replicate r, a copula seed ``cop_seed`` (recorded in the staged per-replicate
records) and called
:func:`...skew_t_copula_bootstrap._draw_uniforms_both` on it to obtain the
skew-t and symmetric-t uniforms on COMMON random numbers.  This module re-draws
at the SAME ``cop_seed`` values with the SAME helper, so at the canonical level
p = 0.90 the recomputed per-replicate lambda_U / lambda_L / radial asymmetry are
BIT-identical to the cached P27T3 records (the C-T4 cross-check gate); the only
new computation is the extension to the additional p in the tail grid (no SCR /
relief machinery is touched, so the diagnostics are cheap).

MR refresh decision (pre-registered, Phase 27 Task 1 design note s5 / Task 3
hand-off).  MR-010 (var-cov aggregation understates diversified capital) and
MR-014 (management-action omission) are refreshed ONLY IF the skew-t headline
component SCR moves > 1% vs the frozen-t component basis.  With gamma_hat ~ 0
the move is +0.01% (skew-t component mean 39,598.2 vs frozen-t component basis
mean 39,595.1; Task 2 point 39,980.96 vs 39,975.65), so NO refresh is required;
the quantified move is documented instead.

EDUCATIONAL MODEL: educational placeholders pending credentialled data and
independent APS X2 review.  NOT for production capital decisions.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from typing import Dict, List, Sequence

import numpy as np

from par_model_v2.projection.skew_t_copula_aggregation import (
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    TAIL_LEVEL_P,
    _skew_t_cdf_interpolant,
)
from par_model_v2.projection.skew_t_copula_bootstrap import (
    SKEWT_BOOTSTRAP_N_SIM,
    _avg_pairwise_lower,
    _avg_pairwise_upper,
    _draw_uniforms_both,
)

# ---------------------------------------------------------------------------
# Pre-registered diagnostics design (Phase 27 Task 4)
# ---------------------------------------------------------------------------
# Tail-threshold grid: the canonical Task 2/3 level 0.90 (the cross-check
# anchor) plus a symmetric spread to characterise the tail-level dependence
# profile of the skew-t vs symmetric-t draw.
TAIL_LEVEL_GRID = (0.80, 0.85, 0.90, 0.95)

# Archived P27T3 cross-check targets (canonical level p = 0.90).
P27T3_RADIAL_ASYMMETRY_MEAN_AT_090 = 0.0004270238095238131
P27T3_SKEWT_COMPONENT_MEAN = 39598.1603351356
P27T3_SYMMETRIC_COMPONENT_MEAN = 39595.06073760497   # = frozen-t basis (P26T3)
P26T3_FROZEN_T_COMPONENT_MEAN = 39595.06073760496

# MR refresh trigger: |relative move of the headline component SCR| > 1%.
MR_REFRESH_TRIGGER = 0.01
# Task 2 archive point read-outs (the larger, conservative move reference).
TASK2_FROZEN_T_COMPONENT_POINT = FROZEN_T_COMPONENT_SCR_REFERENCE   # 39975.654628199336
TASK2_SKEWT_COMPONENT_POINT = 39980.95565911311

CROSSCHECK_TOL = 1e-12


def tail_dependence_grid(
    correlation: np.ndarray,
    df: float,
    gamma: float,
    cop_seeds: Sequence[int],
    n_sim: int = SKEWT_BOOTSTRAP_N_SIM,
    p_grid: Sequence[float] = TAIL_LEVEL_GRID,
) -> Dict[str, object]:
    """Per-replicate upper/lower tail-dependence of the skew-t vs symmetric-t
    copula draw over ``p_grid``, re-drawn at the archived P27T3 ``cop_seeds``.

    For each seed the skew-t (gamma) and symmetric-t (gamma=0) uniforms are
    drawn on COMMON random numbers via the tested
    :func:`...skew_t_copula_bootstrap._draw_uniforms_both` (so the symmetric
    leg is the EXACT Student-t basis and the contrast is an exact CRN
    comparison).  The (df, gamma) marginal-CDF interpolant is built ONCE and
    reused.  Returns one record per replicate with lambda_U / lambda_L for both
    legs at every p (the ``radial_asymmetry`` at TAIL_LEVEL_P reproduces the
    P27T3 cached value bit-identically).
    """
    R = np.asarray(correlation, dtype=float)
    xg, Gg = _skew_t_cdf_interpolant(float(df), float(gamma))   # frozen, reused
    p_grid = tuple(float(p) for p in p_grid)
    records: List[Dict[str, object]] = []
    for r, seed in enumerate(cop_seeds):
        rng = np.random.default_rng(int(seed))
        U_sk, U_sym = _draw_uniforms_both(
            rng, int(n_sim), R, float(df), float(gamma), xg, Gg)
        rec: Dict[str, object] = {"replicate_index": int(r), "cop_seed": int(seed)}
        for p in p_grid:
            lu_sk = _avg_pairwise_upper(U_sk, p)
            ll_sk = _avg_pairwise_lower(U_sk, p)
            lu_sy = _avg_pairwise_upper(U_sym, p)
            ll_sy = _avg_pairwise_lower(U_sym, p)
            key = f"{int(round(p * 100)):02d}"
            rec[f"skewt_lambda_U_{key}"] = float(lu_sk)
            rec[f"skewt_lambda_L_{key}"] = float(ll_sk)
            rec[f"skewt_radial_asym_{key}"] = float(lu_sk - ll_sk)
            rec[f"sym_lambda_U_{key}"] = float(lu_sy)
            rec[f"sym_lambda_L_{key}"] = float(ll_sy)
            rec[f"sym_radial_asym_{key}"] = float(lu_sy - ll_sy)
            rec[f"skewt_minus_sym_radial_asym_{key}"] = float(
                (lu_sk - ll_sk) - (lu_sy - ll_sy))
        records.append(rec)
    return {
        "n_replicates": len(records),
        "n_sim_per_replicate": int(n_sim),
        "df_frozen": float(df),
        "gamma_frozen": float(gamma),
        "p_grid": list(p_grid),
        "tail_level_anchor": float(TAIL_LEVEL_P),
        "method": (
            "re-draw skew-t (gamma) and symmetric-t (gamma=0) copula uniforms on "
            "COMMON random numbers at the archived P27T3 per-replicate cop_seeds; "
            "average pairwise upper/lower tail co-exceedance over all 7C2 pairs, "
            "normalised by (1-p); df/rho/gamma FROZEN (SII Art. 234)"),
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


def summarise_tail_diagnostics(
    grid: Dict[str, object],
    p_grid: Sequence[float] = TAIL_LEVEL_GRID,
    ci_level: float = 0.95,
) -> Dict[str, object]:
    """Mean + 95% CI per p for skew-t / symmetric-t lambda_U, lambda_L, radial
    asymmetry, and the CRN skew-t-minus-symmetric radial-asymmetry lift."""
    records = grid["records"]
    out: Dict[str, object] = {}
    for p in p_grid:
        key = f"{int(round(float(p) * 100)):02d}"
        block: Dict[str, object] = {}
        for metric in (
            "skewt_lambda_U", "skewt_lambda_L", "skewt_radial_asym",
            "sym_lambda_U", "sym_lambda_L", "sym_radial_asym",
            "skewt_minus_sym_radial_asym",
        ):
            vals = [rec[f"{metric}_{key}"] for rec in records]
            block[metric] = summarise_metric(vals, ci_level)
        out[f"p_{key}"] = block
    return out


def crosscheck_against_p27t3(
    grid: Dict[str, object],
    cached_records: Sequence[Dict[str, float]],
    tol: float = CROSSCHECK_TOL,
) -> Dict[str, object]:
    """At the canonical level p = TAIL_LEVEL_P, assert the recomputed
    per-replicate lambda_U / lambda_L / radial asymmetry are BIT-identical to
    the cached P27T3 bootstrap records (the diagnostics are a faithful re-read,
    not a re-tuned recomputation)."""
    key = f"{int(round(TAIL_LEVEL_P * 100)):02d}"
    cached = {int(c["replicate_index"]): c for c in cached_records}
    max_dev_u = 0.0
    max_dev_l = 0.0
    max_dev_ra = 0.0
    for rec in grid["records"]:
        c = cached[int(rec["replicate_index"])]
        max_dev_u = max(max_dev_u, abs(
            rec[f"skewt_lambda_U_{key}"] - float(c["upper_tail_codependence"])))
        max_dev_l = max(max_dev_l, abs(
            rec[f"skewt_lambda_L_{key}"] - float(c["lower_tail_codependence"])))
        max_dev_ra = max(max_dev_ra, abs(
            rec[f"skewt_radial_asym_{key}"] - float(c["radial_asymmetry"])))
    radial_mean = float(np.mean(
        [rec[f"skewt_radial_asym_{key}"] for rec in grid["records"]]))
    return {
        "anchor_level_p": float(TAIL_LEVEL_P),
        "max_abs_dev_lambda_U": float(max_dev_u),
        "max_abs_dev_lambda_L": float(max_dev_l),
        "max_abs_dev_radial_asym": float(max_dev_ra),
        "recomputed_radial_asym_mean": radial_mean,
        "cached_p27t3_radial_asym_mean": float(P27T3_RADIAL_ASYMMETRY_MEAN_AT_090),
        "radial_asym_mean_dev": float(
            abs(radial_mean - P27T3_RADIAL_ASYMMETRY_MEAN_AT_090)),
        "bit_identical": bool(
            max(max_dev_u, max_dev_l, max_dev_ra) <= float(tol)),
    }


def mr_refresh_decision(
    scr_component_skewt: float,
    scr_component_basis: float,
    scr_skewt_point: float = TASK2_SKEWT_COMPONENT_POINT,
    scr_basis_point: float = TASK2_FROZEN_T_COMPONENT_POINT,
    trigger: float = MR_REFRESH_TRIGGER,
) -> Dict[str, object]:
    """Decide whether MR-010 / MR-014 require a refresh: True IFF the absolute
    relative move of the headline component SCR exceeds ``trigger`` (1%).

    Reports the bootstrap-mean move (skew-t component vs frozen-t component
    basis) AND the Task 2 point move (the conservative, larger reference).
    """
    move_boot = (float(scr_component_skewt) - float(scr_component_basis)) \
        / float(scr_component_basis)
    move_point = (float(scr_skewt_point) - float(scr_basis_point)) \
        / float(scr_basis_point)
    max_abs_move = max(abs(move_boot), abs(move_point))
    refresh = bool(max_abs_move > float(trigger))
    return {
        "scr_component_skewt_mean": float(scr_component_skewt),
        "scr_component_basis_mean": float(scr_component_basis),
        "relative_move_bootstrap_mean": float(move_boot),
        "scr_skewt_point": float(scr_skewt_point),
        "scr_basis_point": float(scr_basis_point),
        "relative_move_point": float(move_point),
        "max_abs_relative_move": float(max_abs_move),
        "trigger": float(trigger),
        "refresh_required": refresh,
        "decision": (
            "REFRESH MR-010/MR-014" if refresh else
            "NO refresh required (move {:.4%} <= 1% trigger)".format(max_abs_move)),
        "rationale": (
            "gamma_hat ~ 0 (Task 2 material finding): the skew-t headline "
            "component SCR is economically identical to the frozen-t basis, so "
            "the var-cov-understatement (MR-010) and management-action-omission "
            "(MR-014) quantifications are unchanged within tolerance; the "
            "copula-FORM residual is tracked by the NEW MR-015 instead."),
    }


def tail_diagnostics_digest(records: Sequence[Dict[str, object]]) -> str:
    """Order-independent SHA-256 over the per-replicate tail-grid vectors."""
    key = f"{int(round(TAIL_LEVEL_P * 100)):02d}"
    ordered = sorted(records, key=lambda d: d["replicate_index"])
    payload = [
        [int(d["replicate_index"]),
         round(float(d[f"skewt_lambda_U_{key}"]), 9),
         round(float(d[f"skewt_lambda_L_{key}"]), 9),
         round(float(d[f"sym_lambda_U_{key}"]), 9),
         round(float(d[f"sym_lambda_L_{key}"]), 9)]
        for d in ordered
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def tail_diagnostics_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions (TAS M s3.2 / ASOP 56 s3.5)."""
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "The diagnostics REPORT the FROZEN skew-t copula tail dependence "
            "(df/rho/gamma_hat FROZEN, SII Art. 234); no parameter is tuned.",
            "lambda_U / lambda_L are empirical average pairwise tail "
            "co-exceedance proxies over the 7 educational drivers at finite p "
            "and finite n_sim; they are not analytic coefficients of tail "
            "dependence and carry Monte-Carlo noise (CI reported).",
            "With gamma_hat ~ 0 the skew-t draw is near-radially-symmetric "
            "(radial asymmetry ~ 0 at p = 0.90); the copula-FORM residual to "
            "the nested truth is NOT a standalone-driver tail-asymmetry effect "
            "and is tracked by MR-015 (grouped-t / vine escalation, Phase 28).",
            "MR-010 / MR-014 are NOT refreshed because the headline component "
            "SCR move is +0.01% (< 1% trigger); the move is documented, not "
            "actioned.",
            "Educational placeholders pending credentialled data + independent "
            "APS X2 review; NOT for production capital decisions.",
        ],
    }
