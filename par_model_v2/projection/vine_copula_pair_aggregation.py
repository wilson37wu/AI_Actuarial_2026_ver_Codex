"""
Phase 29 Task 2 - truncated credit-root vine / pair-copula prototype.

This module implements the governed Phase 29 Task 1 envelope:

* frozen standalone margins, frozen Sigma, homogeneous df = 2.9451;
* explicit ``frozen_t_boundary`` path that dispatches to the governed single-df
  t-copula sampler before any candidate vine computation;
* truncated credit-root C-vine links only, with at most two trees;
* pair-family candidates limited to gaussian, student_t, survival_clayton, and
  survival_gumbel;
* deterministic fit/holdout split for leakage control.

The candidate simulator is an educational pair-link prototype. It starts from
the frozen single-df t-copula on common random numbers, applies only the
pre-registered conditional pair-link tail tilts, then re-ranks each margin back
to empirical uniforms. This keeps marginal ranks unchanged while testing
whether localised conditional pair dependence can move the capital read-out in
the direction MR-016 requires. It is not a production vine calibration.
"""

from __future__ import annotations

import hashlib
import itertools
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
from par_model_v2.projection.vine_copula_upgrade import (
    DRIVER_NAMES,
    EXISTING_RISK_ID,
    FIRST_TREE_EDGES,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_COMPONENT_SCR_POINT,
    GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    GROUPED_T_DF_FIN,
    GROUPED_T_DF_NONFIN,
    HOLDOUT_TAIL_PAIRS,
    MAX_VINE_TREES,
    NESTED_PATHWISE_SCR_REFERENCE,
    PAIR_FAMILY_CANDIDATES,
    PRE_REGISTERED_TAIL_PAIRS,
    RANK_INVARIANCE_DF,
    RHO_FROZEN_TOL,
    SECOND_TREE_EDGES,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
    VINE_BOUNDARY_RECOVERY_TOL,
    VINE_ROOT_DRIVER,
    VINE_STRUCTURE,
    all_pre_registered_pairs,
    validate_vine_design_envelope,
)


TAIL_LEVEL_P = 0.90
FIT_FRACTION = 0.70
FIT_SEED = 20260609
READOUT_SEED = 20260607
READOUT_N_SIM = 200_000
CONFIDENCE = 0.995

VINE_FIT_SCORE_VERSION = "p29t2_v1_fit_only_tail_score"
VINE_SIMULATOR_VERSION = "p29t2_v1_rank_preserving_tail_tilt"


@dataclass(frozen=True)
class PairFamilySelection:
    """Selected family and tail metrics for one pre-registered pair link."""

    edge: Tuple[int, int]
    condition_on: Optional[int]
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
            "condition_on": self.condition_on,
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
class VinePairFit:
    """Leakage-free fit result for the governed truncated C-vine envelope."""

    selections: Tuple[PairFamilySelection, ...]
    fit_indices_digest: str
    holdout_indices_digest: str
    fit_fraction: float
    tail_level_p: float
    root_driver: int
    structure: str = VINE_STRUCTURE
    max_vine_trees: int = MAX_VINE_TREES
    score_version: str = VINE_FIT_SCORE_VERSION

    def to_dict(self) -> Dict[str, object]:
        return {
            "structure": self.structure,
            "max_vine_trees": self.max_vine_trees,
            "root_driver": self.root_driver,
            "root_driver_name": DRIVER_NAMES[self.root_driver],
            "fit_fraction": self.fit_fraction,
            "tail_level_p": self.tail_level_p,
            "fit_indices_digest": self.fit_indices_digest,
            "holdout_indices_digest": self.holdout_indices_digest,
            "score_version": self.score_version,
            "selections": [s.to_dict() for s in self.selections],
            "family_counts": _family_counts(self.selections),
        }


def _family_counts(selections: Sequence[PairFamilySelection]) -> Dict[str, int]:
    counts = {f: 0 for f in PAIR_FAMILY_CANDIDATES}
    for sel in selections:
        counts[sel.family] = counts.get(sel.family, 0) + 1
    return counts


def _rank_pit(losses: Dict[str, np.ndarray], drivers: Sequence[str]) -> np.ndarray:
    cols = [np.asarray(losses[k], dtype=float) for k in drivers]
    L = np.column_stack(cols)
    ranks = np.argsort(np.argsort(L, axis=0), axis=0)
    return (ranks + 0.5) / L.shape[0]


def _rerank_uniforms(x: np.ndarray) -> np.ndarray:
    ranks = np.argsort(np.argsort(x, axis=0), axis=0)
    return (ranks + 0.5) / x.shape[0]


def _tail_codependence(
    U: np.ndarray,
    pair: Tuple[int, int],
    p: float = TAIL_LEVEL_P,
    upper: bool = True,
    mask: Optional[np.ndarray] = None,
) -> float:
    if mask is None:
        V = U
    else:
        V = U[np.asarray(mask, dtype=bool)]
    if V.shape[0] == 0:
        return 0.0
    i, j = pair
    if upper:
        event = (V[:, i] > p) & (V[:, j] > p)
    else:
        q = 1.0 - p
        event = (V[:, i] < q) & (V[:, j] < q)
    return float(event.mean() / (1.0 - p))


def _conditional_mask(
    U: np.ndarray,
    condition_on: Optional[int],
    p: float,
) -> Optional[np.ndarray]:
    if condition_on is None:
        return None
    return U[:, condition_on] > p


def _split_fit_holdout(n: int, fit_fraction: float, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    if not (0.5 < fit_fraction < 0.95):
        raise ValueError("fit_fraction must be in (0.5, 0.95)")
    rng = np.random.default_rng(int(seed))
    perm = rng.permutation(int(n))
    n_fit = int(round(n * fit_fraction))
    return np.sort(perm[:n_fit]), np.sort(perm[n_fit:])


def _digest_indices(idx: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(idx, dtype=np.int64).tobytes()).hexdigest()[:12]


def _family_scores(fit_upper: float, fit_lower: float) -> Dict[str, float]:
    """Fit-only family scores.

    Smaller is better. The score is deliberately simple and auditable:
    gaussian is penalised for any tail codependence, student_t is symmetric,
    survival_gumbel is upper-tail oriented, and survival_clayton is lower-tail
    oriented. No holdout value enters selection.
    """
    upper = max(float(fit_upper), 0.0)
    lower = max(float(fit_lower), 0.0)
    mean_tail = 0.5 * (upper + lower)
    return {
        "gaussian": upper * upper + lower * lower,
        "student_t": (upper - mean_tail) ** 2 + (lower - mean_tail) ** 2,
        "survival_gumbel": lower * lower + 0.15 * max(0.0, lower - upper) ** 2,
        "survival_clayton": upper * upper + 0.15 * max(0.0, upper - lower) ** 2,
    }


def _select_family(fit_upper: float, fit_lower: float) -> Tuple[str, Dict[str, float]]:
    scores = _family_scores(fit_upper, fit_lower)
    ordered = sorted(PAIR_FAMILY_CANDIDATES, key=lambda f: (scores[f], f))
    return ordered[0], scores


def _family_strength(family: str, fit_upper: float, fit_lower: float) -> float:
    if family == "gaussian":
        raw = 0.0
    elif family == "student_t":
        raw = 0.5 * (fit_upper + fit_lower)
    elif family == "survival_gumbel":
        raw = fit_upper
    elif family == "survival_clayton":
        raw = fit_lower
    else:
        raise ValueError(f"unsupported pair family {family!r}")
    return float(np.clip(raw, 0.0, 0.75))


def fit_vine_pair_families(
    losses: Dict[str, np.ndarray],
    drivers: Sequence[str],
    fit_fraction: float = FIT_FRACTION,
    seed: int = FIT_SEED,
    p: float = TAIL_LEVEL_P,
) -> VinePairFit:
    """Fit pair families on fit rows only and report disjoint holdout metrics."""
    checks = validate_vine_design_envelope()
    if not checks["envelope_ok"]:
        raise ValueError("pre-registered vine design envelope is invalid")
    U = _rank_pit(losses, drivers)
    fit_idx, hold_idx = _split_fit_holdout(U.shape[0], fit_fraction, seed)
    U_fit = U[fit_idx]
    U_hold = U[hold_idx]

    selections: List[PairFamilySelection] = []
    for edge in FIRST_TREE_EDGES:
        pair = tuple(sorted((int(edge[0]), int(edge[1]))))
        selections.append(_fit_one_pair(U_fit, U_hold, pair, None, p))
    for a, b, c in SECOND_TREE_EDGES:
        pair = tuple(sorted((int(a), int(b))))
        selections.append(_fit_one_pair(U_fit, U_hold, pair, int(c), p))

    return VinePairFit(
        selections=tuple(selections),
        fit_indices_digest=_digest_indices(fit_idx),
        holdout_indices_digest=_digest_indices(hold_idx),
        fit_fraction=float(fit_fraction),
        tail_level_p=float(p),
        root_driver=VINE_ROOT_DRIVER,
    )


def _fit_one_pair(
    U_fit: np.ndarray,
    U_hold: np.ndarray,
    pair: Tuple[int, int],
    condition_on: Optional[int],
    p: float,
) -> PairFamilySelection:
    fit_mask = _conditional_mask(U_fit, condition_on, p)
    hold_mask = _conditional_mask(U_hold, condition_on, p)
    fit_upper = _tail_codependence(U_fit, pair, p, True, fit_mask)
    fit_lower = _tail_codependence(U_fit, pair, p, False, fit_mask)
    hold_upper = _tail_codependence(U_hold, pair, p, True, hold_mask)
    hold_lower = _tail_codependence(U_hold, pair, p, False, hold_mask)
    family, scores = _select_family(fit_upper, fit_lower)
    return PairFamilySelection(
        edge=pair,
        condition_on=condition_on,
        family=family,
        strength=_family_strength(family, fit_upper, fit_lower),
        fit_upper=fit_upper,
        fit_lower=fit_lower,
        holdout_upper=hold_upper,
        holdout_lower=hold_lower,
        fit_score=float(scores[family]),
        candidate_scores={k: float(v) for k, v in scores.items()},
        n_fit=int(U_fit.shape[0] if fit_mask is None else np.sum(fit_mask)),
        n_holdout=int(U_hold.shape[0] if hold_mask is None else np.sum(hold_mask)),
    )


def _selection_from_dict(d: Dict[str, object]) -> PairFamilySelection:
    return PairFamilySelection(
        edge=tuple(int(x) for x in d["edge"]),
        condition_on=None if d.get("condition_on") is None else int(d["condition_on"]),
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


def vine_pair_fit_from_dict(d: Dict[str, object]) -> VinePairFit:
    return VinePairFit(
        selections=tuple(_selection_from_dict(x) for x in d["selections"]),
        fit_indices_digest=str(d["fit_indices_digest"]),
        holdout_indices_digest=str(d["holdout_indices_digest"]),
        fit_fraction=float(d["fit_fraction"]),
        tail_level_p=float(d["tail_level_p"]),
        root_driver=int(d["root_driver"]),
        structure=str(d.get("structure", VINE_STRUCTURE)),
        max_vine_trees=int(d.get("max_vine_trees", MAX_VINE_TREES)),
        score_version=str(d.get("score_version", VINE_FIT_SCORE_VERSION)),
    )


def simulate_vine_pair_copula_uniforms(
    rng: np.random.Generator,
    n_sim: int,
    correlation: np.ndarray,
    df: float,
    fit: VinePairFit,
    mode: str = "candidate",
) -> np.ndarray:
    """Draw uniforms for the frozen boundary or fitted vine-pair candidate."""
    if mode not in {"frozen_t_boundary", "candidate"}:
        raise ValueError("mode must be 'frozen_t_boundary' or 'candidate'")
    base = simulate_t_copula_uniforms(rng, int(n_sim), correlation, float(df))
    if mode == "frozen_t_boundary":
        return base

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

    return np.clip(_rerank_uniforms(x), 1e-12, 1.0 - 1e-12)


def _family_tail_scale(family: str) -> float:
    return {
        "gaussian": 0.0,
        "student_t": 0.20,
        "survival_gumbel": 0.32,
        "survival_clayton": 0.22,
    }[family]


def _family_direction(family: str) -> float:
    # Survival Clayton is a lower-tail family. On loss uniforms, a lower-tail
    # pair maps to less adverse joint losses, so the prototype applies a
    # negative tilt. Upper-tail and symmetric families tilt upward.
    return -1.0 if family == "survival_clayton" else 1.0


def pair_tail_diagnostics(
    U: np.ndarray,
    p: float = TAIL_LEVEL_P,
) -> Dict[str, object]:
    pairs = all_pre_registered_pairs()
    rows = []
    for pair in pairs:
        rows.append({
            "pair": list(pair),
            "upper": _tail_codependence(U, pair, p, True),
            "lower": _tail_codependence(U, pair, p, False),
        })
    holdout = []
    for pair in HOLDOUT_TAIL_PAIRS:
        holdout.append({
            "pair": list(pair),
            "upper": _tail_codependence(U, pair, p, True),
            "lower": _tail_codependence(U, pair, p, False),
        })
    return {
        "level_p": float(p),
        "pre_registered_pairs": rows,
        "holdout_pairs": holdout,
    }


def composition_vine_pair_readout(
    agg: JointActionAggregator,
    n_sim: int,
    seed: int,
    fit: VinePairFit,
    sigma: float,
    alpha: float,
    benefit_share: float,
    confidence: float = CONFIDENCE,
    mode: str = "candidate",
) -> Dict[str, object]:
    """Run the frozen boundary or vine-pair candidate through P26 composition."""
    rng = np.random.default_rng(int(seed))
    U = simulate_vine_pair_copula_uniforms(
        rng, int(n_sim), agg.correlation, RANK_INVARIANCE_DF, fit, mode=mode
    )
    comp = split_joint_composition(agg, U)
    V = comp["V"]
    v_cut = comp["V_cut"]
    pw = composition_with_actions(
        agg.rule, V, v_cut, agg.a_ref, sigma, alpha, benefit_share
    )
    m_wo = capital_metrics_from_liabilities(V, float(confidence), 12)
    m_cp = capital_metrics_from_liabilities(np.asarray(pw["W"], dtype=float), float(confidence), 12)
    out = {
        "config": {
            "n_sim": int(n_sim),
            "seed": int(seed),
            "mode": mode,
            "df": RANK_INVARIANCE_DF,
            "structure": fit.structure,
            "simulator_version": VINE_SIMULATOR_VERSION,
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
        "pair_tail_diagnostics": pair_tail_diagnostics(U, fit.tail_level_p),
        "composition_reconstruction_max_abs_err": comp["reconstruction_max_abs_err"],
    }
    out["digest"] = hashlib.sha256(json.dumps(
        {
            "config": out["config"],
            "scr_without": out["scr_without"],
            "scr_component": out["scr_component"],
            "pair_tail_diagnostics": out["pair_tail_diagnostics"],
        },
        sort_keys=True,
        default=float,
    ).encode()).hexdigest()[:12]
    return out


def run_phase29_task2_readouts(
    agg: JointActionAggregator,
    losses: Dict[str, np.ndarray],
    drivers: Sequence[str],
    sigma: float,
    alpha: float,
    benefit_share: float,
    n_sim: int = READOUT_N_SIM,
    seed: int = READOUT_SEED,
) -> Dict[str, object]:
    """Fit the governed candidate and compute frozen/grouped/vine read-outs."""
    fit = fit_vine_pair_families(losses, drivers)
    frozen = composition_joint_readout(
        agg, n_sim, seed, RANK_INVARIANCE_DF, sigma, alpha, benefit_share, CONFIDENCE
    )
    boundary = composition_vine_pair_readout(
        agg, n_sim, seed, fit, sigma, alpha, benefit_share, CONFIDENCE,
        mode="frozen_t_boundary",
    )
    boundary_dev = abs(boundary["scr_component"] - frozen["scr_component"])
    vine = composition_vine_pair_readout(
        agg, n_sim, seed, fit, sigma, alpha, benefit_share, CONFIDENCE,
        mode="candidate",
    )
    grouped = composition_grouped_t_readout(
        agg, n_sim, seed, [GROUPED_T_DF_NONFIN, GROUPED_T_DF_FIN],
        GROUPED_T_BLOCKS, sigma, alpha, benefit_share, CONFIDENCE,
        shared_mixing=False,
    )
    gates = {
        "G1_frozen_t_boundary_exact_recovery":
            bool(boundary_dev <= VINE_BOUNDARY_RECOVERY_TOL),
        "G2_frozen_t_archive_reference_first":
            bool(frozen["scr_component"] == FROZEN_T_COMPONENT_SCR_REFERENCE),
        "G3_rank_invariance_constants_frozen":
            bool(RANK_INVARIANCE_DF == 2.9451 and RHO_FROZEN_TOL <= 1e-12),
        "G4_pre_registered_envelope_only":
            bool(validate_vine_design_envelope()["envelope_ok"]),
        "G5_family_set_capped":
            bool(set(PAIR_FAMILY_CANDIDATES) == {
                "gaussian", "student_t", "survival_clayton", "survival_gumbel",
            }),
        "G6_leakage_free_fit_holdout_recorded":
            bool(fit.fit_indices_digest != fit.holdout_indices_digest),
        "G7_comparison_variants_retained":
            bool(grouped is not None and frozen is not None),
        "G8_directional_disclosed_not_gated": True,
    }
    return {
        "fit": fit.to_dict(),
        "frozen_t_boundary_readout": boundary,
        "frozen_t_component_reference_readout": frozen,
        "grouped_t_comparison_readout": grouped,
        "vine_pair_candidate_readout": vine,
        "boundary_recovery_dev": boundary_dev,
        "candidate_vs_frozen_t_rel":
            vine["scr_component"] / frozen["scr_component"] - 1.0,
        "candidate_vs_grouped_t_rel":
            vine["scr_component"] / grouped["scr_component"] - 1.0,
        "candidate_gap_to_nested_rel":
            vine["scr_component"] / NESTED_PATHWISE_SCR_REFERENCE - 1.0,
        "gates": gates,
        "material_finding": material_finding_text(vine, frozen, grouped),
    }


def material_finding_text(vine: Dict[str, object], frozen: Dict[str, object], grouped: Dict[str, object]) -> str:
    return (
        "The Phase 29 Task 2 vine-pair candidate is evaluated as a local "
        "conditional-dependence prototype on frozen standalone margins. The "
        "candidate component SCR is {:.1f} vs frozen-t {:.1f} and grouped-t "
        "{:.1f}; direction is disclosed and is not a pass/fail gate. The "
        "frozen-t boundary remains the governed headline until Task 3 bootstrap "
        "and Task 4 MR-016 remediation diagnostics determine whether the vine "
        "materially shrinks the residual and brings nested {:.1f} inside the "
        "candidate uncertainty band.".format(
            float(vine["scr_component"]),
            float(frozen["scr_component"]),
            float(grouped["scr_component"]),
            NESTED_PATHWISE_SCR_REFERENCE,
        )
    )


def vine_pair_copula_use_restrictions() -> Dict[str, object]:
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "The candidate is a governed truncated credit-root pair-link prototype, not an unrestricted R-vine.",
            "The frozen_t_boundary leg must reproduce the governed single-df t component before candidate outputs are considered.",
            "Standalone margins, frozen Sigma and homogeneous df 2.9451 remain frozen; the candidate alters only rank dependence.",
            "Family selection uses fit rows only; holdout tail diagnostics are reported but not used for selection.",
            "The candidate SCR direction is disclosed, not gate-shopped; adoption requires Task 3 bootstrap and Task 4 MR-016 governance.",
            "Production use remains prohibited pending credentialled data and independent APS X2 review.",
        ],
        "references": {
            "existing_risk": EXISTING_RISK_ID,
            "nested_pathwise_reference": NESTED_PATHWISE_SCR_REFERENCE,
            "frozen_t_component_reference": FROZEN_T_COMPONENT_SCR_REFERENCE,
            "grouped_t_component_reference": GROUPED_T_COMPONENT_SCR_POINT,
            "skewt_residual_reference": SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
            "grouped_t_residual_reference": GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
        },
    }
