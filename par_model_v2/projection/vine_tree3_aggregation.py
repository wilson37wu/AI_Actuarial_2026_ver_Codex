"""
Phase 30 Task 2 - governed tree-3 deepening of the truncated credit-root C-vine.

Implements ONLY the pre-registered Phase 30 Task 1 envelope:

* the FROZEN Phase 29 2-tree fit (first/second-tree families, strengths and
  fit/holdout digests are loaded, never re-selected);
* exactly FOUR third-tree conditional pairs:
    fx-rate | credit, liquidity
    rate-lapse | credit, liquidity
    lapse-mortality | credit, liquidity
    equity-liquidity | credit, fx
* the same four pair-family candidates (gaussian, student_t, survival_clayton,
  survival_gumbel); no new families or rotations;
* DUAL boundary recovery: the ``frozen_t_boundary`` leg must reproduce the
  governed single-df t component 39,975.654628199336 and the ``vine2_boundary``
  leg must reproduce the archived 2-tree vine candidate 42,458.5527095696
  bit-identically BEFORE any tree-3 candidate run;
* leakage-free fit/holdout: tree-3 family/parameter selection on fit rows only.

The tree-3 tilt is applied on top of the 2-tree tilted latent scores and is
activated by the JOINT conditional tail of the two conditioners (elementwise
minimum), so it adds dependence only where BOTH conditioning drivers are
simultaneously stressed - exactly the joint-conditional corner the 2-tree
truncation cannot represent. Zero tree-3 strength recovers the 2-tree leg
exactly. EDUCATIONAL ONLY; the governed headline remains the frozen single-df t.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats

from par_model_v2.projection.grouped_t_copula_aggregation import (
    BLOCKS as GROUPED_T_BLOCKS,
    composition_grouped_t_readout,
)
from par_model_v2.projection.joint_action_aggregation import JointActionAggregator
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.pathwise_composition_transform import (
    composition_joint_readout,
    composition_with_actions,
    split_joint_composition,
)
from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    simulate_t_copula_uniforms,
)
from par_model_v2.projection.vine_copula_pair_aggregation import (
    FIT_FRACTION,
    FIT_SEED,
    TAIL_LEVEL_P,
    VinePairFit,
    _conditional_mask,
    _digest_indices,
    _family_direction,
    _family_strength,
    _family_tail_scale,
    _rank_pit,
    _rerank_uniforms,
    _select_family,
    _split_fit_holdout,
    _tail_codependence,
    fit_vine_pair_families,
    pair_tail_diagnostics,
    vine_pair_fit_from_dict,
)
from par_model_v2.projection.vine_copula_upgrade import (
    DRIVER_NAMES,
    FIRST_TREE_EDGES,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_DF_FIN,
    GROUPED_T_DF_NONFIN,
    NESTED_PATHWISE_SCR_REFERENCE,
    PAIR_FAMILY_CANDIDATES,
    RANK_INVARIANCE_DF,
    RHO_FROZEN_TOL,
    SECOND_TREE_EDGES,
    VINE_BOUNDARY_RECOVERY_TOL,
    VINE_ROOT_DRIVER,
    validate_vine_design_envelope,
)


# ----------------------------------------------------------------------------
# Pre-registered Phase 30 envelope (PHASE30_TASK1_DESIGN_NOTE section 5)
# ----------------------------------------------------------------------------

MAX_VINE_TREES_P30 = 3
VINE2_COMPONENT_SCR_REFERENCE = 42_458.5527095696
VINE2_BOOTSTRAP_MEAN_REFERENCE = 41_917.6
VINE2_COPULA_FORM_RESIDUAL_ABS = 3_637.3
P29_HOLDOUT_TO_FIT_MAX_LIFT_REFERENCE = 0.049

# (pair_source, pair_target, (conditioner_1, conditioner_2)); tilt lands on
# pair_target. Order is the pre-registered design-note order.
THIRD_TREE_EDGES: Tuple[Tuple[int, int, Tuple[int, int]], ...] = (
    (5, 0, (2, 6)),  # fx-rate | credit, liquidity
    (0, 3, (2, 6)),  # rate-lapse | credit, liquidity
    (3, 4, (2, 6)),  # lapse-mortality | credit, liquidity
    (1, 6, (2, 5)),  # equity-liquidity | credit, fx
)

TREE3_FIT_SCORE_VERSION = "p30t2_v1_fit_only_joint_conditional_tail_score"
TREE3_SIMULATOR_VERSION = "p30t2_v1_rank_preserving_joint_conditional_tilt"

CONFIDENCE = 0.995
READOUT_SEED = 20260607
READOUT_N_SIM = 200_000

# Archived digests of the frozen Phase 29 Task 2 fit/holdout split.
P29_FIT_INDICES_DIGEST = "e21ca13d365e"
P29_HOLDOUT_INDICES_DIGEST = "962d65338b8e"


def _frozen_tree_digest() -> str:
    payload = json.dumps(
        {
            "first": [list(e) for e in FIRST_TREE_EDGES],
            "second": [list(e) for e in SECOND_TREE_EDGES],
            "families": list(PAIR_FAMILY_CANDIDATES),
        },
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


# Archived at design time; any change to tree-1/tree-2 or the family set breaks
# the envelope check below.
FROZEN_TREE12_DIGEST_REFERENCE = _frozen_tree_digest()


def validate_tree3_design_envelope() -> Dict[str, object]:
    """Static checks for the pre-registered Phase 30 tree-3 envelope."""
    base = validate_vine_design_envelope()
    pairs12 = {tuple(sorted(e)) for e in FIRST_TREE_EDGES}
    pairs12.update(tuple(sorted((a, b))) for a, b, _ in SECOND_TREE_EDGES)
    pairs3 = [tuple(sorted((a, b))) for a, b, _ in THIRD_TREE_EDGES]
    cond_ok = all(
        len(set(c)) == 2 and VINE_ROOT_DRIVER in c and a not in c and b not in c
        for a, b, c in THIRD_TREE_EDGES
    )
    checks = {
        "max_vine_trees_p30": MAX_VINE_TREES_P30,
        "third_tree_edge_count": len(THIRD_TREE_EDGES),
        "third_tree_edges_ok": bool(
            len(THIRD_TREE_EDGES) == 4
            and cond_ok
            and all(p not in pairs12 for p in pairs3)
        ),
        "third_tree_edges_unique": len(set(pairs3)) == len(pairs3),
        "first_second_tree_unchanged":
            _frozen_tree_digest() == FROZEN_TREE12_DIGEST_REFERENCE,
        "pair_families_unchanged": set(PAIR_FAMILY_CANDIDATES) == {
            "gaussian", "student_t", "survival_clayton", "survival_gumbel",
        },
        "base_envelope_ok": bool(base["envelope_ok"]),
    }
    checks["envelope_ok"] = bool(
        checks["third_tree_edges_ok"]
        and checks["third_tree_edges_unique"]
        and checks["first_second_tree_unchanged"]
        and checks["pair_families_unchanged"]
        and checks["base_envelope_ok"]
        and MAX_VINE_TREES_P30 == 3
    )
    return checks


# ----------------------------------------------------------------------------
# Tree-3 fit (leakage-free, fit rows only)
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Tree3PairSelection:
    """Selected family and tail metrics for one tree-3 conditional pair."""

    edge: Tuple[int, int]
    condition_on: Tuple[int, int]
    family: str
    strength: float
    fit_upper: float
    fit_lower: float
    holdout_upper: float
    holdout_lower: float
    fit_score: float
    candidate_scores: Dict[str, float]
    n_fit: int
    n_holdout: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "edge": list(self.edge),
            "condition_on": list(self.condition_on),
            "family": self.family,
            "strength": self.strength,
            "fit_upper": self.fit_upper,
            "fit_lower": self.fit_lower,
            "holdout_upper": self.holdout_upper,
            "holdout_lower": self.holdout_lower,
            "fit_score": self.fit_score,
            "candidate_scores": dict(self.candidate_scores),
            "n_fit": self.n_fit,
            "n_holdout": self.n_holdout,
        }


@dataclass(frozen=True)
class Tree3VineFit:
    """Tree-3 selections layered over the FROZEN Phase 29 2-tree fit."""

    frozen_fit: VinePairFit
    tree3_selections: Tuple[Tree3PairSelection, ...]
    fit_indices_digest: str
    holdout_indices_digest: str
    tail_level_p: float
    score_version: str = TREE3_FIT_SCORE_VERSION

    def to_dict(self) -> Dict[str, object]:
        return {
            "structure": "truncated_c_vine_credit_root_tree3",
            "max_vine_trees": MAX_VINE_TREES_P30,
            "frozen_tree12_fit": self.frozen_fit.to_dict(),
            "frozen_tree12_digest": _frozen_tree_digest(),
            "tail_level_p": self.tail_level_p,
            "fit_indices_digest": self.fit_indices_digest,
            "holdout_indices_digest": self.holdout_indices_digest,
            "score_version": self.score_version,
            "tree3_selections": [s.to_dict() for s in self.tree3_selections],
            "tree3_family_counts": _tree3_family_counts(self.tree3_selections),
        }


def _tree3_family_counts(selections: Sequence[Tree3PairSelection]) -> Dict[str, int]:
    counts = {f: 0 for f in PAIR_FAMILY_CANDIDATES}
    for sel in selections:
        counts[sel.family] = counts.get(sel.family, 0) + 1
    return counts


def _joint_conditional_mask(
    U: np.ndarray, conditioners: Tuple[int, int], p: float
) -> np.ndarray:
    c1, c2 = conditioners
    return (U[:, c1] > p) & (U[:, c2] > p)


def fit_tree3_pairs(
    losses: Dict[str, np.ndarray],
    drivers: Sequence[str],
    frozen_fit: VinePairFit,
    fit_fraction: float = FIT_FRACTION,
    seed: int = FIT_SEED,
    p: float = TAIL_LEVEL_P,
) -> Tree3VineFit:
    """Fit the four tree-3 conditional pairs on fit rows only.

    The first/second-tree selections in ``frozen_fit`` are NEVER re-selected.
    The fit/holdout split reuses the Phase 29 seed so the split digests match
    the archived Phase 29 Task 2 fit exactly.
    """
    checks = validate_tree3_design_envelope()
    if not checks["envelope_ok"]:
        raise ValueError("pre-registered tree-3 design envelope is invalid")
    U = _rank_pit(losses, drivers)
    fit_idx, hold_idx = _split_fit_holdout(U.shape[0], fit_fraction, seed)
    U_fit = U[fit_idx]
    U_hold = U[hold_idx]

    selections: List[Tree3PairSelection] = []
    for a, b, cond in THIRD_TREE_EDGES:
        pair = (int(a), int(b))
        fit_mask = _joint_conditional_mask(U_fit, cond, p)
        hold_mask = _joint_conditional_mask(U_hold, cond, p)
        spair = tuple(sorted(pair))
        fit_upper = _tail_codependence(U_fit, spair, p, True, fit_mask)
        fit_lower = _tail_codependence(U_fit, spair, p, False, fit_mask)
        hold_upper = _tail_codependence(U_hold, spair, p, True, hold_mask)
        hold_lower = _tail_codependence(U_hold, spair, p, False, hold_mask)
        family, scores = _select_family(fit_upper, fit_lower)
        selections.append(Tree3PairSelection(
            edge=pair,
            condition_on=(int(cond[0]), int(cond[1])),
            family=family,
            strength=_family_strength(family, fit_upper, fit_lower),
            fit_upper=fit_upper,
            fit_lower=fit_lower,
            holdout_upper=hold_upper,
            holdout_lower=hold_lower,
            fit_score=float(scores[family]),
            candidate_scores={k: float(v) for k, v in scores.items()},
            n_fit=int(np.sum(fit_mask)),
            n_holdout=int(np.sum(hold_mask)),
        ))

    return Tree3VineFit(
        frozen_fit=frozen_fit,
        tree3_selections=tuple(selections),
        fit_indices_digest=_digest_indices(fit_idx),
        holdout_indices_digest=_digest_indices(hold_idx),
        tail_level_p=float(p),
    )


def _tree3_selection_from_dict(d: Dict[str, object]) -> Tree3PairSelection:
    return Tree3PairSelection(
        edge=tuple(int(x) for x in d["edge"]),
        condition_on=tuple(int(x) for x in d["condition_on"]),
        family=str(d["family"]),
        strength=float(d["strength"]),
        fit_upper=float(d["fit_upper"]),
        fit_lower=float(d["fit_lower"]),
        holdout_upper=float(d["holdout_upper"]),
        holdout_lower=float(d["holdout_lower"]),
        fit_score=float(d["fit_score"]),
        candidate_scores={str(k): float(v) for k, v in d["candidate_scores"].items()},
        n_fit=int(d["n_fit"]),
        n_holdout=int(d["n_holdout"]),
    )


def tree3_vine_fit_from_dict(d: Dict[str, object]) -> Tree3VineFit:
    return Tree3VineFit(
        frozen_fit=vine_pair_fit_from_dict(d["frozen_tree12_fit"]),
        tree3_selections=tuple(
            _tree3_selection_from_dict(x) for x in d["tree3_selections"]
        ),
        fit_indices_digest=str(d["fit_indices_digest"]),
        holdout_indices_digest=str(d["holdout_indices_digest"]),
        tail_level_p=float(d["tail_level_p"]),
        score_version=str(d.get("score_version", TREE3_FIT_SCORE_VERSION)),
    )


# ----------------------------------------------------------------------------
# Simulator: frozen-t boundary -> 2-tree boundary -> tree-3 candidate
# ----------------------------------------------------------------------------


def _vine2_tilted_scores(base: np.ndarray, fit: VinePairFit) -> np.ndarray:
    """Exact transcription of the Phase 29 candidate tilt loop.

    Returns the tilted normal scores BEFORE re-ranking, so the tree-3 layer can
    be applied on top. ``clip(_rerank_uniforms(result))`` is bit-identical to
    ``simulate_vine_pair_copula_uniforms(..., mode='candidate')`` on the same
    base uniforms.
    """
    x = stats.norm.ppf(np.clip(base, 1e-12, 1.0 - 1e-12))
    root = VINE_ROOT_DRIVER
    root_tail = np.maximum(x[:, root] - np.quantile(x[:, root], 0.90), 0.0)

    for sel in fit.selections:
        i, j = sel.edge
        if root in sel.edge:
            source = root
            target = j if i == root else i
            activation = root_tail
        else:
            source = sel.condition_on if sel.condition_on is not None else i
            source_tail = np.maximum(
                x[:, source] - np.quantile(x[:, source], 0.90), 0.0
            )
            pair_tail = np.maximum(x[:, i] - np.quantile(x[:, i], 0.90), 0.0)
            activation = 0.65 * source_tail + 0.35 * pair_tail
            target = j

        scale = _family_tail_scale(sel.family)
        direction = _family_direction(sel.family)
        if np.std(activation) > 1e-12:
            activation = activation / np.std(activation)
        x[:, target] += direction * scale * sel.strength * activation

    return x


def _apply_tree3_tilts(x: np.ndarray, fit3: Tree3VineFit) -> np.ndarray:
    """Joint-conditional tree-3 tilts on top of the 2-tree tilted scores.

    Activation is the elementwise MINIMUM of the two conditioner tail
    excesses - non-zero only when both conditioning drivers are stressed
    together - blended 0.65/0.35 with the pair-source tail per the Phase 29
    convention. Zero strength (or a gaussian selection, scale 0) leaves x
    unchanged, which is the vine2 boundary-recovery contract.
    """
    for sel in fit3.tree3_selections:
        a, b = sel.edge
        c1, c2 = sel.condition_on
        c1_tail = np.maximum(x[:, c1] - np.quantile(x[:, c1], 0.90), 0.0)
        c2_tail = np.maximum(x[:, c2] - np.quantile(x[:, c2], 0.90), 0.0)
        joint_tail = np.minimum(c1_tail, c2_tail)
        pair_tail = np.maximum(x[:, a] - np.quantile(x[:, a], 0.90), 0.0)
        activation = 0.65 * joint_tail + 0.35 * pair_tail

        scale = _family_tail_scale(sel.family)
        direction = _family_direction(sel.family)
        if np.std(activation) > 1e-12:
            activation = activation / np.std(activation)
        x[:, b] += direction * scale * sel.strength * activation
    return x


def simulate_tree3_vine_uniforms(
    rng: np.random.Generator,
    n_sim: int,
    correlation: np.ndarray,
    df: float,
    fit3: Tree3VineFit,
    mode: str = "candidate",
) -> np.ndarray:
    """Draw uniforms for the dual boundaries or the tree-3 candidate."""
    if mode not in {"frozen_t_boundary", "vine2_boundary", "candidate"}:
        raise ValueError(
            "mode must be 'frozen_t_boundary', 'vine2_boundary' or 'candidate'"
        )
    base = simulate_t_copula_uniforms(rng, int(n_sim), correlation, float(df))
    if mode == "frozen_t_boundary":
        return base
    x = _vine2_tilted_scores(base, fit3.frozen_fit)
    if mode == "candidate":
        x = _apply_tree3_tilts(x, fit3)
    return np.clip(_rerank_uniforms(x), 1e-12, 1.0 - 1e-12)


# ----------------------------------------------------------------------------
# Composition read-out and Task 2 gate runner
# ----------------------------------------------------------------------------


def tree3_pair_tail_diagnostics(U: np.ndarray, p: float = TAIL_LEVEL_P) -> Dict[str, object]:
    rows = []
    for a, b, cond in THIRD_TREE_EDGES:
        mask = _joint_conditional_mask(U, cond, p)
        spair = tuple(sorted((int(a), int(b))))
        rows.append({
            "pair": [int(a), int(b)],
            "condition_on": [int(cond[0]), int(cond[1])],
            "n_conditional": int(np.sum(mask)),
            "conditional_upper": _tail_codependence(U, spair, p, True, mask),
            "conditional_lower": _tail_codependence(U, spair, p, False, mask),
            "unconditional_upper": _tail_codependence(U, spair, p, True),
            "unconditional_lower": _tail_codependence(U, spair, p, False),
        })
    return {"level_p": float(p), "tree3_pairs": rows}


def composition_tree3_readout(
    agg: JointActionAggregator,
    n_sim: int,
    seed: int,
    fit3: Tree3VineFit,
    sigma: float,
    alpha: float,
    benefit_share: float,
    confidence: float = CONFIDENCE,
    mode: str = "candidate",
) -> Dict[str, object]:
    """Run a boundary leg or the tree-3 candidate through P26 composition."""
    rng = np.random.default_rng(int(seed))
    U = simulate_tree3_vine_uniforms(
        rng, int(n_sim), agg.correlation, RANK_INVARIANCE_DF, fit3, mode=mode
    )
    comp = split_joint_composition(agg, U)
    V = comp["V"]
    v_cut = comp["V_cut"]
    pw = composition_with_actions(
        agg.rule, V, v_cut, agg.a_ref, sigma, alpha, benefit_share
    )
    m_wo = capital_metrics_from_liabilities(V, float(confidence), 12)
    m_cp = capital_metrics_from_liabilities(
        np.asarray(pw["W"], dtype=float), float(confidence), 12
    )
    out = {
        "config": {
            "n_sim": int(n_sim),
            "seed": int(seed),
            "mode": mode,
            "df": RANK_INVARIANCE_DF,
            "structure": "truncated_c_vine_credit_root_tree3",
            "simulator_version": TREE3_SIMULATOR_VERSION,
            "confidence": float(confidence),
            "sigma": float(sigma),
            "alpha": float(alpha),
            "benefit_share_fit": float(benefit_share),
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
        "pair_tail_diagnostics": pair_tail_diagnostics(U, fit3.tail_level_p),
        "tree3_pair_tail_diagnostics":
            tree3_pair_tail_diagnostics(U, fit3.tail_level_p),
        "composition_reconstruction_max_abs_err": comp["reconstruction_max_abs_err"],
    }
    out["digest"] = hashlib.sha256(json.dumps(
        {
            "config": out["config"],
            "scr_without": out["scr_without"],
            "scr_component": out["scr_component"],
            "tree3_pair_tail_diagnostics": out["tree3_pair_tail_diagnostics"],
        },
        sort_keys=True,
        default=float,
    ).encode()).hexdigest()[:12]
    return out


def run_phase30_task2_readouts(
    agg: JointActionAggregator,
    losses: Dict[str, np.ndarray],
    drivers: Sequence[str],
    sigma: float,
    alpha: float,
    benefit_share: float,
    frozen_fit_dict: Dict[str, object],
    n_sim: int = READOUT_N_SIM,
    seed: int = READOUT_SEED,
) -> Dict[str, object]:
    """Dual-boundary verification first, then the tree-3 candidate on CRN."""
    fit2 = vine_pair_fit_from_dict(frozen_fit_dict)
    refit2 = fit_vine_pair_families(losses, drivers)
    frozen_fit_consistent = refit2.to_dict() == fit2.to_dict()

    # Tree-3 fit (leakage-free; fit rows only).
    fit3 = fit_tree3_pairs(losses, drivers, fit2)

    # Dual boundary legs FIRST (design-note hard precondition).
    frozen = composition_joint_readout(
        agg, n_sim, seed, RANK_INVARIANCE_DF, sigma, alpha, benefit_share, CONFIDENCE
    )
    boundary_t = composition_tree3_readout(
        agg, n_sim, seed, fit3, sigma, alpha, benefit_share, CONFIDENCE,
        mode="frozen_t_boundary",
    )
    boundary_v2 = composition_tree3_readout(
        agg, n_sim, seed, fit3, sigma, alpha, benefit_share, CONFIDENCE,
        mode="vine2_boundary",
    )
    boundary_t_dev = abs(boundary_t["scr_component"] - frozen["scr_component"])
    boundary_t_archive_dev = abs(
        frozen["scr_component"] - FROZEN_T_COMPONENT_SCR_REFERENCE
    )
    boundary_v2_dev = abs(
        boundary_v2["scr_component"] - VINE2_COMPONENT_SCR_REFERENCE
    )
    dual_boundary_ok = bool(
        boundary_t_dev <= VINE_BOUNDARY_RECOVERY_TOL
        and boundary_t_archive_dev <= VINE_BOUNDARY_RECOVERY_TOL
        and boundary_v2_dev <= VINE_BOUNDARY_RECOVERY_TOL
    )
    if not dual_boundary_ok:
        raise RuntimeError(
            "DUAL boundary recovery failed; refusing to run the tree-3 "
            f"candidate (t_dev={boundary_t_dev:.3e}, "
            f"t_archive_dev={boundary_t_archive_dev:.3e}, "
            f"vine2_dev={boundary_v2_dev:.3e})"
        )

    # Candidate and comparison variants on common random numbers.
    candidate = composition_tree3_readout(
        agg, n_sim, seed, fit3, sigma, alpha, benefit_share, CONFIDENCE,
        mode="candidate",
    )
    grouped = composition_grouped_t_readout(
        agg, n_sim, seed, [GROUPED_T_DF_NONFIN, GROUPED_T_DF_FIN],
        GROUPED_T_BLOCKS, sigma, alpha, benefit_share, CONFIDENCE,
        shared_mixing=False,
    )

    envelope = validate_tree3_design_envelope()
    gates = {
        "G1_dual_boundary_bit_identical": dual_boundary_ok,
        "G2_frozen_t_archive_reference_first":
            bool(frozen["scr_component"] == FROZEN_T_COMPONENT_SCR_REFERENCE),
        "G3_vine2_archive_reference_recovered":
            bool(boundary_v2["scr_component"] == VINE2_COMPONENT_SCR_REFERENCE),
        "G4_rank_invariance_constants_frozen":
            bool(RANK_INVARIANCE_DF == 2.9451 and RHO_FROZEN_TOL <= 1e-12),
        "G5_tree12_fit_frozen_from_phase29":
            bool(frozen_fit_consistent
                 and fit2.fit_indices_digest == P29_FIT_INDICES_DIGEST
                 and fit2.holdout_indices_digest == P29_HOLDOUT_INDICES_DIGEST),
        "G6_pre_registered_tree3_envelope_only": bool(envelope["envelope_ok"]),
        "G7_family_set_capped":
            bool(set(PAIR_FAMILY_CANDIDATES) == {
                "gaussian", "student_t", "survival_clayton", "survival_gumbel",
            }),
        "G8_leakage_free_fit_holdout_recorded":
            bool(fit3.fit_indices_digest != fit3.holdout_indices_digest
                 and fit3.fit_indices_digest == P29_FIT_INDICES_DIGEST),
        "G9_comparison_variants_retained_crn":
            bool(grouped is not None and frozen is not None
                 and boundary_v2 is not None),
        "G10_directional_disclosed_not_gated": True,
    }
    return {
        "fit": fit3.to_dict(),
        "envelope": envelope,
        "frozen_fit_consistent_with_refit": frozen_fit_consistent,
        "frozen_t_boundary_readout": boundary_t,
        "frozen_t_component_reference_readout": frozen,
        "vine2_boundary_readout": boundary_v2,
        "grouped_t_comparison_readout": grouped,
        "tree3_candidate_readout": candidate,
        "boundary_t_recovery_dev": boundary_t_dev,
        "boundary_t_archive_dev": boundary_t_archive_dev,
        "boundary_vine2_recovery_dev": boundary_v2_dev,
        "candidate_vs_frozen_t_rel":
            candidate["scr_component"] / frozen["scr_component"] - 1.0,
        "candidate_vs_vine2_rel":
            candidate["scr_component"] / boundary_v2["scr_component"] - 1.0,
        "candidate_vs_grouped_t_rel":
            candidate["scr_component"] / grouped["scr_component"] - 1.0,
        "candidate_gap_to_nested_rel":
            candidate["scr_component"] / NESTED_PATHWISE_SCR_REFERENCE - 1.0,
        "candidate_residual_abs":
            abs(NESTED_PATHWISE_SCR_REFERENCE - candidate["scr_component"]),
        "vine2_residual_abs_reference": VINE2_COPULA_FORM_RESIDUAL_ABS,
        "gates": gates,
        "material_finding": material_finding_text(
            candidate, boundary_v2, frozen, grouped
        ),
    }


def material_finding_text(
    candidate: Dict[str, object],
    vine2: Dict[str, object],
    frozen: Dict[str, object],
    grouped: Dict[str, object],
) -> str:
    return (
        "The Phase 30 Task 2 tree-3 vine candidate deepens the FROZEN Phase 29 "
        "2-tree credit-root C-vine with the four pre-registered joint-conditional "
        "third-tree pairs. The candidate component SCR is {:.1f} vs 2-tree vine "
        "{:.1f}, frozen-t {:.1f} and grouped-t {:.1f}; direction is disclosed and "
        "is not a pass/fail gate. Both boundary legs reproduced their archived "
        "references bit-identically before the candidate ran. The frozen-t "
        "boundary remains the governed headline; Task 3 bootstrap decides whether "
        "the nested reference {:.1f} enters the candidate 95% CI or the "
        "pre-registered stop-rule triggers.".format(
            float(candidate["scr_component"]),
            float(vine2["scr_component"]),
            float(frozen["scr_component"]),
            float(grouped["scr_component"]),
            NESTED_PATHWISE_SCR_REFERENCE,
        )
    )


def tree3_vine_use_restrictions() -> Dict[str, object]:
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "The candidate is the governed tree-3 deepening of the Phase 29 truncated credit-root pair-link prototype, not an unrestricted R-vine.",
            "BOTH boundary legs (frozen single-df t AND archived 2-tree vine) must reproduce their archived read-outs bit-identically before any tree-3 output is considered.",
            "First/second-tree fits are FROZEN from Phase 29 Task 2; only the four pre-registered third-tree conditional pairs are fitted.",
            "Standalone margins, frozen Sigma and homogeneous df 2.9451 remain frozen; the candidate alters only rank dependence.",
            "Tree-3 family selection uses fit rows only; holdout diagnostics are reported but never enter selection.",
            "The candidate SCR direction is disclosed, not gate-shopped; adoption requires Task 3 bootstrap and Task 4 MR-016/MR-017 governance, subject to the pre-registered stop-rule.",
            "Production use remains prohibited pending credentialled data and independent APS X2 review.",
        ],
        "references": {
            "existing_risks": ["MR-016", "MR-017"],
            "nested_pathwise_reference": NESTED_PATHWISE_SCR_REFERENCE,
            "frozen_t_component_reference": FROZEN_T_COMPONENT_SCR_REFERENCE,
            "vine2_component_reference": VINE2_COMPONENT_SCR_REFERENCE,
            "vine2_residual_reference": VINE2_COPULA_FORM_RESIDUAL_ABS,
            "stop_rule": (
                "If the Phase 30 tree-3 vine still leaves nested 46,638.9 outside "
                "its 95% bootstrap CI at Task 4, dependence-FORM escalation under "
                "MR-016 ENDS; Phase 31 becomes the owner decision package."
            ),
        },
    }
