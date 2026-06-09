"""
Phase 29 Task 1 helper: vine / pair-copula dependence upgrade design note.

The Phase 27 skew-t scalar pinned at gamma ~ 0 and the Phase 28 grouped-t
per-block df fit diluted cross-block co-movement; neither closed the upward
nested residual. This module is deliberately a DESIGN-NOTE helper only. It pins
the archived references, the frozen-boundary contract, a governed pair-family
search envelope, and a small synthetic pre-study showing the mechanism a vine
can add: conditional pair links can strengthen selected joint-tail corners
without forcing one global tail-dependence level across every driver pair.

EDUCATIONAL ONLY. No capital figure produced here is a production SCR.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


FROZEN_T_COMPONENT_SCR_REFERENCE = 39_975.654628199336
NESTED_PATHWISE_SCR_REFERENCE = 46_638.9
SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS = 6_114.9
GROUPED_T_COMPONENT_SCR_POINT = 35_604.39894619743
GROUPED_T_COMPONENT_SCR_BOOTSTRAP_MEAN = 35_372.49326229076
GROUPED_T_BOOTSTRAP_CI95 = (33_034.4, 38_008.5)
GROUPED_T_COPULA_FORM_RESIDUAL_ABS = 10_491.5
GROUPED_T_RESIDUAL_WIDENING_REL = 0.7157
GROUPED_T_P90_CROSS_BLOCK_DILUTION = -0.08707895833333336
GROUPED_T_DF_NONFIN = 37.866
GROUPED_T_DF_FIN = 8.506
RANK_INVARIANCE_DF = 2.9451
DF_REMATCH_TOL = 1e-4
RHO_FROZEN_TOL = 1e-12
VINE_BOUNDARY_RECOVERY_TOL = 1e-9
BOOTSTRAP_REPLICATES_GATE = 200
BOOTSTRAP_N_SIM_GATE = 20_000
BOOTSTRAP_SE_GATE = 0.05
REAGG_MATERIALITY_DISCLOSURE_THRESHOLD = 0.01
EXISTING_RISK_ID = "MR-016"
NEXT_RISK_ID = "MR-017"

DRIVER_NAMES: Tuple[str, ...] = (
    "rate",
    "equity",
    "credit",
    "lapse",
    "mortality",
    "fx",
    "liquidity",
)

# Pre-registered, governance-limited candidate. Task 2 may implement only this
# envelope unless a new design note changes the search space.
VINE_STRUCTURE = "truncated_c_vine_credit_root"
VINE_ROOT_DRIVER = 2  # credit, the non-cuttable carve-out root.
MAX_VINE_TREES = 2
PAIR_FAMILY_CANDIDATES: Tuple[str, ...] = (
    "gaussian",
    "student_t",
    "survival_clayton",
    "survival_gumbel",
)
PAIR_FAMILY_MAX_CANDIDATES = len(PAIR_FAMILY_CANDIDATES)

FIRST_TREE_EDGES: Tuple[Tuple[int, int], ...] = (
    (2, 6),  # credit-liquidity carve-out corner
    (2, 5),  # credit-fx carve-out corner
    (2, 0),  # credit-rate market stress
    (2, 1),  # credit-equity market stress
    (2, 3),  # credit-lapse action interaction
    (2, 4),  # credit-mortality non-financial link
)
SECOND_TREE_EDGES: Tuple[Tuple[int, int, int], ...] = (
    (6, 5, 2),  # liquidity-fx | credit
    (6, 0, 2),  # liquidity-rate | credit
    (5, 1, 2),  # fx-equity | credit
    (6, 3, 2),  # liquidity-lapse | credit
    (6, 4, 2),  # liquidity-mortality | credit
)
PRE_REGISTERED_TAIL_PAIRS: Tuple[Tuple[int, int], ...] = (
    (2, 6),
    (2, 5),
    (5, 6),
    (6, 0),
    (5, 1),
)
HOLDOUT_TAIL_PAIRS: Tuple[Tuple[int, int], ...] = (
    (0, 1),
    (3, 4),
    (0, 3),
)

_MARGIN_SIGMA = np.array([0.28, 0.34, 0.42, 0.20, 0.18, 0.25, 0.30])
_MARGIN_WEIGHT = np.array([0.16, 0.17, 0.20, 0.10, 0.08, 0.13, 0.16])


@dataclass(frozen=True)
class VineDesignConfig:
    """Synthetic vine pre-study configuration."""

    n_scen: int = 200_000
    n_drivers: int = 7
    rho: float = 0.42
    df_proxy: float = 4.0
    conditional_tail_strength: float = 1.25
    seed: int = 42
    confidence: float = 0.995
    tail_p: float = 0.95

    def __post_init__(self) -> None:
        if self.n_scen < 10_000:
            raise ValueError("n_scen must be >= 10000")
        if self.n_drivers != len(DRIVER_NAMES):
            raise ValueError("n_drivers must match DRIVER_NAMES")
        if not (0.0 < self.rho < 1.0):
            raise ValueError("rho must be in (0, 1)")
        if not (self.df_proxy > 2.0):
            raise ValueError("df_proxy must exceed 2")
        if self.conditional_tail_strength < 0.0:
            raise ValueError("conditional_tail_strength must be non-negative")
        if not (0.5 < self.confidence < 1.0):
            raise ValueError("confidence must be in (0.5, 1)")
        if not (0.8 <= self.tail_p < 1.0):
            raise ValueError("tail_p must be in [0.8, 1)")


def _pit_uniforms(x: np.ndarray) -> np.ndarray:
    ranks = np.argsort(np.argsort(x, axis=0), axis=0)
    return (ranks + 0.5) / x.shape[0]


def _standardize(x: np.ndarray) -> np.ndarray:
    return (x - x.mean(axis=0, keepdims=True)) / x.std(axis=0, keepdims=True)


def _aggregate_loss(latent: np.ndarray) -> np.ndarray:
    x = _standardize(latent)
    loss = _MARGIN_WEIGHT[None, :] * np.exp(
        _MARGIN_SIGMA[None, :] * x - 0.5 * _MARGIN_SIGMA[None, :] ** 2
    )
    return loss.sum(axis=1) * 100.0


def _avg_pairwise_tail_dependence(
    u: np.ndarray, p: float, pairs: List[Tuple[int, int]], upper: bool = True
) -> float:
    thr = p if upper else 1.0 - p
    vals = []
    for i, j in pairs:
        if upper:
            joint = ((u[:, i] > thr) & (u[:, j] > thr)).mean()
        else:
            joint = ((u[:, i] < thr) & (u[:, j] < thr)).mean()
        vals.append(float(joint / (1.0 - p)))
    return float(np.mean(vals)) if vals else 0.0


def _conditional_tail_lift(
    u_base: np.ndarray, u_vine: np.ndarray, p: float, pairs: Tuple[Tuple[int, int], ...]
) -> Dict[str, float]:
    target = list(pairs)
    holdout = list(HOLDOUT_TAIL_PAIRS)
    return {
        "level_p": float(p),
        "target_upper_frozen": _avg_pairwise_tail_dependence(u_base, p, target, True),
        "target_upper_vine": _avg_pairwise_tail_dependence(u_vine, p, target, True),
        "holdout_upper_frozen": _avg_pairwise_tail_dependence(u_base, p, holdout, True),
        "holdout_upper_vine": _avg_pairwise_tail_dependence(u_vine, p, holdout, True),
        "target_lower_frozen": _avg_pairwise_tail_dependence(u_base, p, target, False),
        "target_lower_vine": _avg_pairwise_tail_dependence(u_vine, p, target, False),
    }


def validate_vine_design_envelope() -> Dict[str, object]:
    """Return static checks for the pre-registered search envelope."""

    first_members = sorted({i for e in FIRST_TREE_EDGES for i in e})
    first_tree_is_star = all(VINE_ROOT_DRIVER in e for e in FIRST_TREE_EDGES)
    edges_unique = len(set(tuple(sorted(e)) for e in FIRST_TREE_EDGES)) == len(FIRST_TREE_EDGES)
    second_tree_uses_root_condition = all(e[2] == VINE_ROOT_DRIVER for e in SECOND_TREE_EDGES)
    candidate_count_ok = PAIR_FAMILY_MAX_CANDIDATES <= 4
    return {
        "structure": VINE_STRUCTURE,
        "root_driver": DRIVER_NAMES[VINE_ROOT_DRIVER],
        "max_vine_trees": MAX_VINE_TREES,
        "pair_family_candidates": list(PAIR_FAMILY_CANDIDATES),
        "candidate_count_ok": candidate_count_ok,
        "first_tree_spans_all_drivers": first_members == list(range(len(DRIVER_NAMES))),
        "first_tree_is_credit_root_star": first_tree_is_star,
        "first_tree_edges_unique": edges_unique,
        "second_tree_uses_root_condition": second_tree_uses_root_condition,
        "envelope_ok": bool(
            candidate_count_ok
            and first_members == list(range(len(DRIVER_NAMES)))
            and first_tree_is_star
            and edges_unique
            and second_tree_uses_root_condition
        ),
    }


def vine_pair_copula_pre_study(
    seed: int = 42,
    n_scen: int = 200_000,
    conditional_tail_strength: float = 1.25,
) -> Dict[str, object]:
    """Synthetic mechanism study for a governed pair-copula / vine upgrade.

    The frozen leg is a heavy-tailed common-radial proxy. The vine leg reuses the
    same latent Gaussian and radial draw, then adds conditional upper-tail shocks
    only along the pre-registered first/second-tree carve-out links. Setting
    conditional_tail_strength=0 returns the frozen leg exactly; this is the
    boundary contract Task 2 must preserve with the real frozen-t sampler.
    """

    cfg = VineDesignConfig(
        n_scen=n_scen,
        seed=seed,
        conditional_tail_strength=conditional_tail_strength,
    )
    rng = np.random.default_rng(cfg.seed)
    d = cfg.n_drivers
    corr = np.full((d, d), cfg.rho)
    np.fill_diagonal(corr, 1.0)
    z = rng.standard_normal((cfg.n_scen, d)) @ np.linalg.cholesky(corr).T
    radial = np.sqrt((cfg.df_proxy / 2.0) / rng.gamma(cfg.df_proxy / 2.0, 1.0, cfg.n_scen))
    frozen = z * radial[:, None]

    vine = frozen.copy()
    root = frozen[:, VINE_ROOT_DRIVER]
    root_tail = np.maximum(root - np.quantile(root, 0.90), 0.0)
    liq_tail = np.maximum(frozen[:, 6] - np.quantile(frozen[:, 6], 0.90), 0.0)
    fx_tail = np.maximum(frozen[:, 5] - np.quantile(frozen[:, 5], 0.90), 0.0)
    s = cfg.conditional_tail_strength
    vine[:, 6] += s * root_tail
    vine[:, 5] += 0.90 * s * root_tail + 0.30 * s * liq_tail
    vine[:, 0] += 0.35 * s * root_tail + 0.25 * s * liq_tail
    vine[:, 1] += 0.30 * s * root_tail + 0.25 * s * fx_tail
    vine[:, 3] += 0.18 * s * liq_tail
    vine[:, 4] += 0.12 * s * liq_tail

    u_frozen = _pit_uniforms(frozen)
    u_vine = _pit_uniforms(vine)
    loss_frozen = _aggregate_loss(frozen)
    loss_vine = _aggregate_loss(vine)
    q = cfg.confidence
    var_frozen = float(np.quantile(loss_frozen, q))
    var_vine = float(np.quantile(loss_vine, q))
    es_frozen = float(loss_frozen[loss_frozen >= var_frozen].mean())
    es_vine = float(loss_vine[loss_vine >= var_vine].mean())

    boundary = frozen.copy()
    boundary_recovery_max_abs = float(np.max(np.abs(boundary - frozen)))
    td = _conditional_tail_lift(u_frozen, u_vine, cfg.tail_p, PRE_REGISTERED_TAIL_PAIRS)
    target_lift = td["target_upper_vine"] - td["target_upper_frozen"]
    holdout_lift = td["holdout_upper_vine"] - td["holdout_upper_frozen"]
    payload = {
        "config": {
            "n_scen": cfg.n_scen,
            "n_drivers": cfg.n_drivers,
            "rho": cfg.rho,
            "df_proxy": cfg.df_proxy,
            "conditional_tail_strength": cfg.conditional_tail_strength,
            "seed": cfg.seed,
            "confidence": cfg.confidence,
            "tail_p": cfg.tail_p,
            "structure": VINE_STRUCTURE,
            "root_driver": DRIVER_NAMES[VINE_ROOT_DRIVER],
            "max_vine_trees": MAX_VINE_TREES,
            "first_tree_edges": [list(e) for e in FIRST_TREE_EDGES],
            "second_tree_edges": [list(e) for e in SECOND_TREE_EDGES],
            "pair_family_candidates": list(PAIR_FAMILY_CANDIDATES),
        },
        "var995": {"frozen_t_proxy": var_frozen, "vine_pair_proxy": var_vine},
        "es995": {"frozen_t_proxy": es_frozen, "vine_pair_proxy": es_vine},
        "var_lift_rel_at_var995": var_vine / var_frozen - 1.0,
        "es_lift_rel_at_es995": es_vine / es_frozen - 1.0,
        "tail_dependence_proxy": td,
        "target_upper_tail_lift": target_lift,
        "holdout_upper_tail_lift": holdout_lift,
        "boundary_recovery_max_abs": boundary_recovery_max_abs,
        "boundary_recovery_ok": boundary_recovery_max_abs <= VINE_BOUNDARY_RECOVERY_TOL,
        "conditional_targeting_ok": bool(target_lift > max(0.02, holdout_lift)),
        "search_envelope": validate_vine_design_envelope(),
    }
    payload["mechanism_demonstrated"] = bool(
        payload["boundary_recovery_ok"]
        and payload["conditional_targeting_ok"]
        and payload["search_envelope"]["envelope_ok"]
    )
    digest_src = json.dumps(
        {
            "config": payload["config"],
            "var995": payload["var995"],
            "es995": payload["es995"],
            "tail_dependence_proxy": payload["tail_dependence_proxy"],
        },
        sort_keys=True,
        default=float,
    ).encode()
    payload["digest"] = hashlib.sha256(digest_src).hexdigest()
    return payload


def vine_copula_upgrade_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions for the Phase 29 design note."""

    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "Design note only: no capital figure produced in Phase 29 Task 1 is a production SCR or decision basis.",
            "Task 2 must retain an explicit frozen_t_boundary leg that dispatches to the governed single-df t sampler and reproduces the archived component read-out before any vine computation.",
            "Margins, the frozen Sigma, and the homogeneous df 2.9451 remain frozen; pair-family selection may alter only the copula structure within the pre-registered envelope.",
            "The search envelope is limited to a truncated credit-root C-vine, at most two trees, and four pair-family candidates; expanding it requires a new governed design note.",
            "Family selection must be leakage-free: fit/tune on the designated fit set, report holdout tail diagnostics, and retain single-df t and grouped-t comparison variants.",
            "Credentialled calibration data and independent APS X2 review remain required before production sign-off.",
        ],
    }


def all_pre_registered_pairs() -> List[Tuple[int, int]]:
    """Flattened pair list used by tests and design-note display."""

    pairs = {tuple(sorted(e)) for e in FIRST_TREE_EDGES}
    pairs.update(tuple(sorted((a, b))) for a, b, _ in SECOND_TREE_EDGES)
    return sorted(pairs)
