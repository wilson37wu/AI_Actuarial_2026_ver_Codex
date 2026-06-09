"""
Phase 28 Task 2 - grouped t-copula re-aggregation on the FROZEN copula.

Implements the heterogeneous-tail-dependence copula designed in the Phase 28
Task 1 note (docs/validation/PHASE28_TASK1_DESIGN_NOTE.md): the GROUPED
t-copula (Daul, De Giorgi, Lindskog & McNeil 2003; McNeil, Frey & Embrechts
2015 ch. 7) layered on the governed frozen Student-t copula (df 2.9451,
correlation Sigma).  ONE new structural lever - per-BLOCK degrees of freedom
df_g (heterogeneous tail dependence across driver blocks) - is added on top of
the frozen Sigma; the calibrated MARGINS and the governed rank dependence
(Sigma) are UNCHANGED (Solvency II Art. 234 rank invariance).

Grouped-t construction (McNeil-Frey-Embrechts 7.3.3)
----------------------------------------------------
Partition the d drivers into m blocks.  Draw ONE Gaussian vector on the frozen
correlation, then an INDEPENDENT radial mixing variate per block:

    Z ~ N(0, Sigma)
    W_g = chi2(df_g) / df_g                 independent across blocks g
    X_k = Z_k / sqrt(W_{g(k)})              for driver k in block g
    U_k = t_{df_g}.cdf(X_k)                 per-block t marginal -> uniform

Within a block the pair tail dependence is the t-tail of df_g (shared mixing ->
strong co-crash); across blocks the mixing is independent -> the cross-block
tail dependence is WEAKER.  A single pooled df CANNOT produce within-block >>
cross-block tail dependence.

EXACT homogeneous-boundary recovery of the frozen single-df t
-------------------------------------------------------------
The frozen symmetric simulator
(:func:`...t_copula_tail_matched_aggregation.simulate_t_copula_uniforms`)
draws ``Z = standard_normal @ chol.T`` then ``W = chisquare(df)/df`` and forms
``X = Z / sqrt(W)``, ``U = t_df.cdf(X)``.  The grouped-t simulator below draws
``Z`` with the IDENTICAL call, and in the ``shared_mixing=True`` homogeneous
boundary mode (all df_g equal to the frozen df, ONE shared chi-square mixing
variate drawn with the same ``rng.chisquare(df, size=n_sim)`` call) it
reproduces ``X = Z / sqrt(W)`` and ``U = t_df.cdf(X)`` bit-for-bit.  So the
governed freeze is nested as the m = 1 / fully-pooled boundary (a strict
super-set) and the archive cross-check is EXACT.

For the genuine grouped-t (independent per-block mixing) the draw ORDER is
``Z`` first (identical to the symmetric simulator), then one chi-square draw
per block in block order, so the block-0 mixing reuses the same rng position
the symmetric ``W`` would have occupied.

EDUCATIONAL MODEL: all parameters are educational placeholders pending
credentialled data and independent APS X2 review.  NOT for production capital
decisions.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats

from par_model_v2.projection.joint_action_aggregation import (
    JointActionAggregator,
)
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.pathwise_composition_transform import (
    composition_with_actions,
    split_joint_composition,
)

# ---------------------------------------------------------------------------
# Frozen / archived references consumed as GATE baselines (none computed here).
# ---------------------------------------------------------------------------
# Archived Phase 26 Task 2 frozen-t COMPONENT path-wise SCR (the homogeneous-
# boundary exact-recovery target and the directional disclosure reference).
FROZEN_T_COMPONENT_SCR_REFERENCE = 39_975.654628199336
# Archived Phase 25 Task 2 nested path-wise with-actions SCR (truth target).
NESTED_PATHWISE_SCR_REFERENCE = 46_638.9
# Archived Phase 27 Task 3 skew-t reconfirmation (gamma_hat ~ 0): the copula-
# form residual fell only to this value (0.09% reduction) - the grouped-t is
# tested against it at Task 3.
SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS = 6_114.9
FROZEN_T_COPULA_FORM_RESIDUAL_ABS = 6_120.196568775231
# Rank invariance (Solvency II Art. 234, Phase 23 Task 2 freeze).
RANK_INVARIANCE_DF = 2.9451
DF_REMATCH_TOL = 1e-4
RHO_FROZEN_TOL = 1e-12
# Homogeneous-boundary EXACT-recovery tolerance (pre-registered Task 2 gate).
HOMOGENEOUS_RECOVERY_TOL = 1e-9
# Upper-tail co-exceedance level for the per-block df fit / diagnostics.
TAIL_LEVEL_P = 0.90
# Disclosure trigger (NOT pass/fail): MR refresh if the grouped-t SCR moves
# more than 1% from the frozen-t component read-out.
REAGG_MATERIALITY_DISCLOSURE_THRESHOLD = 0.01

# ---------------------------------------------------------------------------
# PRE-REGISTERED driver-block partition (Phase 28 Task 1 design note s5).
# The design note pins the FIN/carve-out block BY NAME as the heavy
# non-cuttable corner {credit, FX, liquidity}; in the synthetic pre-study these
# were placeholder indices {0,4,6}.  In the REAL driver tuple
#   DRIVERS = (rate, equity, credit, lapse, mortality, fx, liquidity)
# the named carve-out maps to indices {2, 5, 6}; the NON-FIN block is the
# remaining (cuttable) drivers {rate, equity, lapse, mortality} = {0, 1, 3, 4}.
# The partition is fixed here BEFORE any real-data fit (no gate-shopping).
# ---------------------------------------------------------------------------
DRIVER_ORDER: Tuple[str, ...] = (
    "rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity",
)
FIN_BLOCK_NAMES: Tuple[str, ...] = ("credit", "fx", "liquidity")
NONFIN_BLOCK_NAMES: Tuple[str, ...] = ("rate", "equity", "lapse", "mortality")
FIN_BLOCK: Tuple[int, ...] = tuple(DRIVER_ORDER.index(n) for n in FIN_BLOCK_NAMES)
NONFIN_BLOCK: Tuple[int, ...] = tuple(
    DRIVER_ORDER.index(n) for n in NONFIN_BLOCK_NAMES)
# Block list in canonical (sorted-by-first-index) order; block 0 reuses the
# rng position the symmetric single-df mixing variate would have occupied.
BLOCKS: Tuple[Tuple[int, ...], ...] = (
    tuple(sorted(NONFIN_BLOCK)), tuple(sorted(FIN_BLOCK)),
)
BLOCK_LABELS: Tuple[str, ...] = ("NON_FIN", "FIN_CARVE_OUT")


def _validate_blocks(blocks: Sequence[Sequence[int]], d: int) -> None:
    members = sorted(int(i) for blk in blocks for i in blk)
    if members != list(range(d)):
        raise ValueError(
            "blocks must partition all {} drivers exactly; got {}".format(
                d, members))


# ===========================================================================
# Grouped-t copula uniform simulator (homogeneous boundary == frozen t, CRN)
# ===========================================================================
def simulate_grouped_t_copula_uniforms(
    rng: np.random.Generator,
    n_sim: int,
    correlation: np.ndarray,
    block_dfs: Sequence[float],
    blocks: Sequence[Sequence[int]],
    shared_mixing: bool = False,
) -> np.ndarray:
    """Draw n_sim uniform vectors from a grouped t-copula(Sigma, {df_g}).

    Parameters
    ----------
    block_dfs : per-block degrees of freedom (one df_g per block in `blocks`).
    blocks : index-tuples partitioning all d drivers (block order fixes the
        rng draw order; block 0 reuses the symmetric-t mixing rng position).
    shared_mixing : if True (homogeneous-boundary recovery mode) ALL drivers
        share ONE chi-square mixing variate drawn with the SAME
        ``rng.chisquare(df, size=n_sim)`` call as the frozen symmetric
        simulator, so with all df_g equal to the frozen df the returned
        uniforms are bit-identical to
        ``simulate_t_copula_uniforms(rng, n_sim, Sigma, df)``.
    """
    R = np.asarray(correlation, dtype=float)
    d = R.shape[0]
    blocks = [tuple(int(i) for i in blk) for blk in blocks]
    _validate_blocks(blocks, d)
    if len(block_dfs) != len(blocks):
        raise ValueError("block_dfs length must match number of blocks")
    for g in block_dfs:
        if g <= 0.0:
            raise ValueError(f"each df_g must be positive, got {g}")
    chol = np.linalg.cholesky(R)
    Z = rng.standard_normal((n_sim, d)) @ chol.T          # same as symmetric
    U = np.empty((n_sim, d), dtype=float)
    if shared_mixing:
        # Homogeneous boundary: ONE shared mixing variate (frozen symmetric t).
        df0 = float(block_dfs[0])
        W = rng.chisquare(df0, size=n_sim) / df0          # same rng call
        X = Z / np.sqrt(W)[:, None]
        return stats.t.cdf(X, df0)                         # exact symmetric path
    # Genuine grouped-t: independent per-block mixing, in block order.
    for blk, dfg in zip(blocks, block_dfs):
        dfg = float(dfg)
        W = rng.chisquare(dfg, size=n_sim) / dfg
        cols = list(blk)
        Xb = Z[:, cols] / np.sqrt(W)[:, None]
        U[:, cols] = stats.t.cdf(Xb, dfg)
    return np.clip(U, 1e-12, 1.0 - 1e-12)


# ===========================================================================
# Within / cross-block upper-tail co-exceedance proxies (for the df_g fit)
# ===========================================================================
def _avg_pairwise_upper_codependence_over_pairs(
    U: np.ndarray, p: float, pairs: Sequence[Tuple[int, int]]
) -> float:
    """Average pairwise empirical upper co-exceedance proxy at level p.

    P(U_i > p, U_j > p) / (1 - p), averaged over the supplied driver pairs.
    """
    if not pairs:
        return float("nan")
    vals = []
    for i, j in pairs:
        joint = float(((U[:, i] > p) & (U[:, j] > p)).mean())
        vals.append(joint / (1.0 - p))
    return float(np.mean(vals))


def _within_pairs(block: Sequence[int]) -> List[Tuple[int, int]]:
    return list(itertools.combinations(sorted(int(i) for i in block), 2))


def _cross_pairs(
    block_a: Sequence[int], block_b: Sequence[int]
) -> List[Tuple[int, int]]:
    return [(i, j) for i in sorted(int(x) for x in block_a)
            for j in sorted(int(y) for y in block_b)]


def _rank_pit(losses: Dict[str, np.ndarray], drivers: Sequence[str]
              ) -> np.ndarray:
    """Empirical rank-PIT of the standalone loss vectors -> copula uniforms."""
    cols = [np.asarray(losses[k], dtype=float) for k in drivers]
    L = np.column_stack(cols)
    ranks = np.argsort(np.argsort(L, axis=0), axis=0)
    return (ranks + 0.5) / L.shape[0]


def realised_block_codependence(
    losses: Dict[str, np.ndarray], drivers: Sequence[str],
    blocks: Sequence[Sequence[int]], p: float = TAIL_LEVEL_P,
) -> Dict[str, object]:
    """Realised within/cross-block upper co-exceedance of standalone losses.

    Leakage-free: only the standalone loss vectors are used (no nested truth).
    """
    U = _rank_pit(losses, drivers)
    within = [
        _avg_pairwise_upper_codependence_over_pairs(U, p, _within_pairs(blk))
        for blk in blocks
    ]
    cross_pairs: List[Tuple[int, int]] = []
    for a in range(len(blocks)):
        for b in range(a + 1, len(blocks)):
            cross_pairs += _cross_pairs(blocks[a], blocks[b])
    cross = _avg_pairwise_upper_codependence_over_pairs(U, p, cross_pairs)
    return {
        "tail_level_p": float(p),
        "within_block": [float(x) for x in within],
        "cross_block": float(cross),
    }


def model_within_block_codependence(
    correlation: np.ndarray, df: float, block: Sequence[int],
    p: float = TAIL_LEVEL_P, n_sim: int = 200_000, seed: int = 20260608,
) -> float:
    """Model-implied within-block upper co-exceedance at a single df.

    Within a grouped-t block the construction is exactly a single-df t-copula
    (df) on the frozen sub-correlation, so a single-df t draw on the FULL
    frozen Sigma read on the block columns gives the within-block proxy.
    """
    from par_model_v2.projection.t_copula_tail_matched_aggregation import (
        simulate_t_copula_uniforms,
    )
    rng = np.random.default_rng(int(seed))
    U = simulate_t_copula_uniforms(rng, int(n_sim), correlation, float(df))
    return _avg_pairwise_upper_codependence_over_pairs(
        U, p, _within_pairs(block))


def fit_block_df_to_within_codependence(
    losses: Dict[str, np.ndarray], drivers: Sequence[str],
    correlation: np.ndarray, block: Sequence[int], p: float = TAIL_LEVEL_P,
    n_sim: int = 100_000, seed: int = 20260608,
    df_lo: float = 2.05, df_hi: float = 60.0,
) -> Dict[str, object]:
    """Fit one block's df_g leakage-free to its realised within-block upper
    co-exceedance (Sigma FROZEN; margins untouched).

    Bounded 1-D fit on the monotone (df -> within-block co-exceedance) map
    (lower df => heavier tail => higher co-exceedance).
    """
    from scipy.optimize import minimize_scalar

    U_real = _rank_pit(losses, drivers)
    target = _avg_pairwise_upper_codependence_over_pairs(
        U_real, p, _within_pairs(block))
    base = model_within_block_codependence(
        correlation, RANK_INVARIANCE_DF, block, p, n_sim, seed)

    def obj(df: float) -> float:
        m = model_within_block_codependence(
            correlation, float(df), block, p, n_sim, seed)
        return (m - target) ** 2

    res = minimize_scalar(obj, bounds=(df_lo, df_hi), method="bounded",
                          options={"xatol": 1e-3})
    df_hat = float(res.x)
    model_at_hat = model_within_block_codependence(
        correlation, df_hat, block, p, n_sim, seed)
    return {
        "block": [int(i) for i in block],
        "tail_level_p": float(p),
        "target_realised_within_codependence": float(target),
        "model_within_codependence_at_frozen_df": float(base),
        "df_hat": df_hat,
        "model_within_codependence_at_df_hat": float(model_at_hat),
        "fit_residual_abs": float(abs(model_at_hat - target)),
        "fit_n_sim": int(n_sim),
        "fit_seed": int(seed),
        "fit_converged": bool(res.success),
        "df_lo": float(df_lo), "df_hi": float(df_hi),
        "df_at_boundary": bool(
            abs(df_hat - df_lo) <= 1e-3 or abs(df_hat - df_hi) <= 1e-3),
    }


def fit_grouped_t_block_dfs(
    losses: Dict[str, np.ndarray], drivers: Sequence[str],
    correlation: np.ndarray, blocks: Sequence[Sequence[int]],
    p: float = TAIL_LEVEL_P, n_sim: int = 100_000, seed: int = 20260608,
) -> Dict[str, object]:
    """Fit per-block df_g leakage-free to each block's within-block upper
    co-exceedance (one bounded 1-D fit per block; Sigma/margins FROZEN)."""
    fits = [
        fit_block_df_to_within_codependence(
            losses, drivers, correlation, blk, p, n_sim, seed + bi)
        for bi, blk in enumerate(blocks)
    ]
    return {
        "block_dfs_hat": [float(f["df_hat"]) for f in fits],
        "per_block_fit": fits,
        "all_converged": bool(all(f["fit_converged"] for f in fits)),
    }


# ===========================================================================
# Component-basis re-aggregation on the grouped-t copula (mirrors P26T2 readout)
# ===========================================================================
def _tail_dependence_blocks(
    U: np.ndarray, blocks: Sequence[Sequence[int]], p: float = TAIL_LEVEL_P
) -> Dict[str, object]:
    """Within/cross-block upper & lower tail-dependence proxies of a draw."""
    q = 1.0 - p
    within_u, within_l = [], []
    for blk in blocks:
        pr = _within_pairs(blk)
        within_u.append(_avg_pairwise_upper_codependence_over_pairs(U, p, pr))
        if pr:
            within_l.append(float(np.mean([
                ((U[:, i] < q) & (U[:, j] < q)).mean() / q for i, j in pr])))
        else:
            within_l.append(float("nan"))
    cross_pairs: List[Tuple[int, int]] = []
    for a in range(len(blocks)):
        for b in range(a + 1, len(blocks)):
            cross_pairs += _cross_pairs(blocks[a], blocks[b])
    cross_u = _avg_pairwise_upper_codependence_over_pairs(U, p, cross_pairs)
    cross_l = float(np.mean([
        ((U[:, i] < q) & (U[:, j] < q)).mean() / q for i, j in cross_pairs]))
    return {
        "level_p": float(p),
        "within_block_upper": [float(x) for x in within_u],
        "within_block_lower": [float(x) for x in within_l],
        "cross_block_upper": float(cross_u),
        "cross_block_lower": float(cross_l),
        "heterogeneity_upper": float(max(within_u) - cross_u),
    }


def composition_grouped_t_readout(
    agg: JointActionAggregator,
    n_sim: int,
    seed: int,
    block_dfs: Sequence[float],
    blocks: Sequence[Sequence[int]],
    sigma: float,
    alpha: float,
    benefit_share: float,
    confidence: float = 0.995,
    shared_mixing: bool = False,
) -> Dict[str, object]:
    """One grouped-t-copula draw -> component with-actions read-out (P26T2 basis).

    Identical relief machinery to the frozen-t component read-out
    (:func:`...pathwise_composition_transform.composition_joint_readout`); the
    ONLY change is the copula uniform sampler (grouped-t with per-block df_g).
    At the homogeneous boundary (all df_g = frozen df, shared_mixing=True) the
    uniforms are bit-identical to the symmetric t draw, so this read-out
    reproduces the frozen-t component basis exactly.
    """
    rng = np.random.default_rng(int(seed))
    U = simulate_grouped_t_copula_uniforms(
        rng, int(n_sim), agg.correlation, [float(g) for g in block_dfs],
        blocks, shared_mixing=shared_mixing)
    comp = split_joint_composition(agg, U)
    V = comp["V"]
    v_cut = comp["V_cut"]
    pw = composition_with_actions(
        agg.rule, V, v_cut, agg.a_ref, sigma, alpha, benefit_share)
    m_wo = capital_metrics_from_liabilities(V, float(confidence), 12)
    m_cp = capital_metrics_from_liabilities(
        np.asarray(pw["W"], dtype=float), float(confidence), 12)
    td = _tail_dependence_blocks(U, blocks, TAIL_LEVEL_P)
    out = {
        "config": {
            "n_sim": int(n_sim), "seed": int(seed),
            "block_dfs": [float(g) for g in block_dfs],
            "blocks": [list(map(int, b)) for b in blocks],
            "shared_mixing": bool(shared_mixing),
            "copula": "grouped_t(dfs={}, blocks={})".format(
                [round(float(g), 4) for g in block_dfs],
                [list(map(int, b)) for b in blocks]),
            "confidence": float(confidence), "sigma": float(sigma),
            "alpha": float(alpha), "benefit_share_fit": float(benefit_share),
        },
        "var_without": float(m_wo.var_liability),
        "es_without": float(m_wo.es_liability),
        "scr_without": float(m_wo.scr_proxy),
        "var_component": float(m_cp.var_liability),
        "es_component": float(m_cp.es_liability),
        "scr_component": float(m_cp.scr_proxy),
        "mean_component": float(np.mean(pw["W"])),
        "clip_binding_share_component": float(pw["clip_binding_share"]),
        "active_share_component": float(pw["active_share"]),
        "tail_dependence": td,
        "composition_reconstruction_max_abs_err":
            comp["reconstruction_max_abs_err"],
    }
    out["digest"] = hashlib.sha256(json.dumps(
        {k: out[k] for k in ("config", "var_without", "scr_without",
                             "var_component", "scr_component")},
        sort_keys=True).encode()).hexdigest()[:12]
    return out


def grouped_t_copula_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions for the Phase 28 grouped-t copula (TAS M / ASOP 56)."""
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "The grouped-t copula adds per-BLOCK degrees of freedom df_g "
            "(heterogeneous tail dependence across driver blocks) on the FROZEN "
            "Sigma; the homogeneous boundary (all df_g = 2.9451 with a single "
            "shared mixing variate) recovers the governed single-df t EXACTLY "
            "(Solvency II Art. 234 rank invariance; no re-tuning of Sigma/"
            "margins/homogeneous df).",
            "The block partition (FIN/carve-out {credit, FX, liquidity} vs "
            "NON-FIN {rate, equity, lapse, mortality}) is PRE-REGISTERED in the "
            "Phase 28 Task 1 design note before any fit; a different partition "
            "is a new modelling decision requiring its own governed note.",
            "Each block's df_g is fitted leakage-free to that block's realised "
            "WITHIN-block upper co-exceedances of the standalone loss vectors "
            "only (no nested truth; Sigma/margins untouched); the cross-block "
            "tail dependence is then implied and DISCLOSED, not fitted.",
            "The grouped-t is a tail-dependence HETEROGENEITY lever, NOT a "
            "uniform tail-heaviness lever: because the single-df t shares ONE "
            "mixing variate it is the MAXIMAL-cross-block-dependence boundary, "
            "so the grouped-t can dilute cross-block co-movement; its aggregate "
            "SCR effect is genuinely two-sided and DISCLOSED, not pre-gated.",
            "Margins remain the calibrated frozen margins - the upgrade changes "
            "the COPULA only, never the standalone marginal capital.",
            "Action parameters remain educational placeholders pending "
            "credentialled practice data + independent APS X2 review.",
        ],
    }
