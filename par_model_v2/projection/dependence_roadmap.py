"""Phase 30 Task 1 - post-vine dependence roadmap decision (design-note-first).

Phase 29 closed with MR-016 KEEP OPEN and MR-017 OPENED: the truncated
credit-root C-vine was the FIRST dependence candidate to narrow the
copula-form residual below both prior baselines (-65.33% vs grouped-t,
-40.52% vs skew-t), but the nested path-wise reference 46,638.9 remained
outside the vine 95% bootstrap CI [38,654.7, 45,284.3]. This module fixes,
BEFORE any implementation, the quantified option study and the single
selected next step for Phase 30, together with a pre-registered stop-rule.

Options studied (state-file mandate):
  A. tree-3 vine deepening (relax the 2-tree truncation inside a capped envelope)
  B. nested-aware dependence calibration (calibrate to the nested reference)
  C. owner adoption decision package for the disclosed vine read-out
  D. stop-rule (diminishing returns; credentialled-data priority)

Selected: OPTION A, with option D embedded as a pre-registered conditional
stop-rule and option C scheduled as the post-Phase-30 owner package
regardless of outcome. Option B is rejected THIS cycle on leakage grounds
(it would consume the only independent nested benchmark) and is retained
only as a possible owner-approved escalation AFTER the stop-rule fires.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from par_model_v2.projection.vine_copula_upgrade import (
    DRIVER_NAMES,
    FIRST_TREE_EDGES,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    HOLDOUT_TAIL_PAIRS,
    NESTED_PATHWISE_SCR_REFERENCE,
    PAIR_FAMILY_CANDIDATES,
    RANK_INVARIANCE_DF,
    SECOND_TREE_EDGES,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
    VINE_BOUNDARY_RECOVERY_TOL,
    VINE_ROOT_DRIVER,
)

# ---------------------------------------------------------------------------
# Archived Phase 29 references (pinned; cross-checked against the committed
# Task 3 / Task 4 validation reports by the Phase 30 Task 1 tests).
# ---------------------------------------------------------------------------
VINE2_COMPONENT_SCR_POINT = 42_458.5527095696
VINE2_COMPONENT_SCR_BOOTSTRAP_MEAN = 41_917.634842687556
VINE2_BOOTSTRAP_CI95 = (38_654.68530800363, 45_284.252553628474)
VINE2_BOOTSTRAP_SE = 1_694.2416034048445
VINE2_BOOTSTRAP_SE_FRAC = 0.04041834921658041
VINE2_COPULA_FORM_RESIDUAL_POINT = 3_637.298487404965
VINE2_COPULA_FORM_RESIDUAL_BOOT_MEAN = 4_178.216354287011
VINE2_GAP_TOTAL_POINT = 4_180.3472904304
RELIEF_SURFACE_PART_ABS = 543.0488030254351
COPULA_FORM_SHARE_OF_GAP_POINT = 0.870094811436223
VINE2_OVERFIT_HOLDOUT_TO_FIT_RATIO = 0.04858753059314438
VINE2_MAX_FIT_PAIR_LIFT = 0.8514015735106508
VINE2_MAX_HOLDOUT_PAIR_LIFT = 0.04136750000000001
MR016_RISK_ID = "MR-016"
MR017_RISK_ID = "MR-017"

# ---------------------------------------------------------------------------
# Pre-registered Phase 30 envelope: ONE additional C-vine tree, same four
# pair families, no other structure search. Tree-3 edges join second-tree
# edges sharing a node (proximity condition), conditioning sets shown.
# ---------------------------------------------------------------------------
MAX_VINE_TREES_P30 = 3
THIRD_TREE_EDGES: Tuple[Tuple[int, int, Tuple[int, int]], ...] = (
    (5, 0, (2, 6)),  # fx-rate        | credit, liquidity
    (0, 3, (2, 6)),  # rate-lapse     | credit, liquidity
    (3, 4, (2, 6)),  # lapse-mortality| credit, liquidity
    (1, 6, (2, 5)),  # equity-liquidity | credit, fx
)
UI_CONTRACT_FROM = "1.11.0"
UI_CONTRACT_TO = "1.12.0"

OPTION_IDS = ("A_tree3_vine_deepening", "B_nested_aware_calibration",
              "C_owner_adoption_package", "D_stop_rule")
SELECTED_OPTION = "A_tree3_vine_deepening"


@dataclass(frozen=True)
class RoadmapStudyConfig:
    """Synthetic tree-3 truncation pre-study configuration."""

    n_scen: int = 200_000
    n_drivers: int = 7
    rho: float = 0.42
    df_proxy: float = 4.0
    tree12_strength: float = 1.25
    tree3_strength: float = 1.10
    seed: int = 30
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
        if self.tree12_strength < 0.0 or self.tree3_strength < 0.0:
            raise ValueError("strengths must be non-negative")
        if not (0.5 < self.confidence < 1.0):
            raise ValueError("confidence must be in (0.5, 1)")


_MARGIN_SIGMA = np.array([0.28, 0.34, 0.42, 0.20, 0.18, 0.25, 0.30])
_MARGIN_WEIGHT = np.array([0.16, 0.17, 0.20, 0.10, 0.08, 0.13, 0.16])


def _aggregate_loss(latent: np.ndarray) -> np.ndarray:
    x = (latent - latent.mean(axis=0, keepdims=True)) / latent.std(axis=0, keepdims=True)
    loss = _MARGIN_WEIGHT[None, :] * np.exp(
        _MARGIN_SIGMA[None, :] * x - 0.5 * _MARGIN_SIGMA[None, :] ** 2
    )
    return loss.sum(axis=1) * 100.0


def _tree12_shocks(frozen: np.ndarray, s: float) -> np.ndarray:
    """The archived Phase 29 tree-1/tree-2 conditional-tail mechanism."""
    out = frozen.copy()
    root = frozen[:, VINE_ROOT_DRIVER]
    root_tail = np.maximum(root - np.quantile(root, 0.90), 0.0)
    liq_tail = np.maximum(frozen[:, 6] - np.quantile(frozen[:, 6], 0.90), 0.0)
    fx_tail = np.maximum(frozen[:, 5] - np.quantile(frozen[:, 5], 0.90), 0.0)
    out[:, 6] += s * root_tail
    out[:, 5] += 0.90 * s * root_tail + 0.30 * s * liq_tail
    out[:, 0] += 0.35 * s * root_tail + 0.25 * s * liq_tail
    out[:, 1] += 0.30 * s * root_tail + 0.25 * s * fx_tail
    out[:, 3] += 0.18 * s * liq_tail
    out[:, 4] += 0.12 * s * liq_tail
    return out


def _tree3_shocks(base: np.ndarray, frozen: np.ndarray, s3: float) -> np.ndarray:
    """Tree-3 JOINT-conditional shocks: active only when BOTH conditioning
    drivers are in their upper tails - dependence a 2-tree truncation
    cannot represent."""
    out = base.copy()
    root_tail = np.maximum(frozen[:, 2] - np.quantile(frozen[:, 2], 0.90), 0.0)
    liq_tail = np.maximum(frozen[:, 6] - np.quantile(frozen[:, 6], 0.90), 0.0)
    fx_tail = np.maximum(frozen[:, 5] - np.quantile(frozen[:, 5], 0.90), 0.0)
    joint_cl = np.sqrt(root_tail * liq_tail)   # credit AND liquidity tails
    joint_cf = np.sqrt(root_tail * fx_tail)    # credit AND fx tails
    out[:, 5] += 0.80 * s3 * joint_cl
    out[:, 0] += 0.55 * s3 * joint_cl
    out[:, 3] += 0.35 * s3 * joint_cl
    out[:, 4] += 0.25 * s3 * joint_cl
    out[:, 1] += 0.45 * s3 * joint_cf
    return out


def _joint_triple_tail(u: np.ndarray, p: float, triples: List[Tuple[int, int, int]]) -> float:
    vals = []
    for i, j, k in triples:
        thr = p
        joint = ((u[:, i] > thr) & (u[:, j] > thr) & (u[:, k] > thr)).mean()
        vals.append(float(joint / (1.0 - p) ** 2))
    return float(np.mean(vals)) if vals else 0.0


def _pit(x: np.ndarray) -> np.ndarray:
    ranks = np.argsort(np.argsort(x, axis=0), axis=0)
    return (ranks + 0.5) / x.shape[0]


def mr016_closure_headroom() -> Dict[str, float]:
    """Pure-arithmetic headroom from archived Phase 29 constants."""
    needed_mean_lift_abs = NESTED_PATHWISE_SCR_REFERENCE - VINE2_BOOTSTRAP_CI95[1]
    return {
        "nested_reference": NESTED_PATHWISE_SCR_REFERENCE,
        "vine2_ci_hi": VINE2_BOOTSTRAP_CI95[1],
        "needed_mean_lift_abs": needed_mean_lift_abs,
        "needed_mean_lift_rel": needed_mean_lift_abs / VINE2_COMPONENT_SCR_BOOTSTRAP_MEAN,
        "needed_share_of_point_residual": needed_mean_lift_abs / VINE2_COPULA_FORM_RESIDUAL_POINT,
        "max_addressable_share_of_total_gap": COPULA_FORM_SHARE_OF_GAP_POINT,
        "relief_surface_part_not_addressable": RELIEF_SURFACE_PART_ABS,
    }


def tree3_truncation_pre_study(
    seed: int = 30,
    n_scen: int = 200_000,
    tree3_strength: float = 1.10,
) -> Dict[str, object]:
    """Synthetic mechanism study for the tree-3 vine deepening.

    Truth carries tree-1/2 conditional-tail dependence (the archived Phase 29
    mechanism) PLUS tree-3 joint-conditional dependence. The vine2 leg (the
    Phase 29 candidate form) cannot represent the tree-3 term, leaving a
    positive VaR99.5 truncation gap. A tree-3 leg with strength fitted on a
    FIT half (1-D grid; leakage-free) closes a quantified share of that gap
    on the disjoint HOLDOUT half. tree3_strength=0 recovers the vine2 leg
    exactly - the boundary contract Task 2 must preserve against the real
    archived vine candidate 42,458.5527095696.
    """
    cfg = RoadmapStudyConfig(n_scen=n_scen, seed=seed, tree3_strength=tree3_strength)
    rng = np.random.default_rng(cfg.seed)
    d = cfg.n_drivers
    corr = np.full((d, d), cfg.rho)
    np.fill_diagonal(corr, 1.0)
    z = rng.standard_normal((cfg.n_scen, d)) @ np.linalg.cholesky(corr).T
    radial = np.sqrt((cfg.df_proxy / 2.0) / rng.gamma(cfg.df_proxy / 2.0, 1.0, cfg.n_scen))
    frozen = z * radial[:, None]

    vine2 = _tree12_shocks(frozen, cfg.tree12_strength)
    truth = _tree3_shocks(vine2, frozen, cfg.tree3_strength)

    # Boundary contract: zero tree-3 strength == vine2 leg exactly.
    boundary = _tree3_shocks(vine2, frozen, 0.0)
    boundary_recovery_max_abs = float(np.max(np.abs(boundary - vine2)))

    q = cfg.confidence
    fit = np.arange(cfg.n_scen) % 2 == 0
    hold = ~fit

    def var_q(loss: np.ndarray, mask: np.ndarray) -> float:
        return float(np.quantile(loss[mask], q))

    loss_truth = _aggregate_loss(truth)
    loss_vine2 = _aggregate_loss(vine2)

    # Leakage-free 1-D fit of the tree-3 strength on the FIT half only.
    grid = [round(0.25 * k, 2) for k in range(0, 9)]  # 0.00 .. 2.00
    target_fit = var_q(loss_truth, fit)
    best_s, best_err = 0.0, float("inf")
    for s in grid:
        cand = _aggregate_loss(_tree3_shocks(vine2, frozen, s))
        err = abs(var_q(cand, fit) - target_fit)
        if err < best_err:
            best_s, best_err = s, err
    loss_fitted = _aggregate_loss(_tree3_shocks(vine2, frozen, best_s))

    # Holdout evaluation.
    var_truth_h = var_q(loss_truth, hold)
    var_vine2_h = var_q(loss_vine2, hold)
    var_fit_h = var_q(loss_fitted, hold)
    gap2 = var_truth_h - var_vine2_h
    gap3 = abs(var_truth_h - var_fit_h)
    closure = 1.0 - gap3 / gap2 if gap2 > 0 else 0.0

    u_truth = _pit(truth)
    u_vine2 = _pit(vine2)
    triples = [(2, 6, 5), (2, 6, 0), (2, 5, 1)]
    holdout_pairs = list(HOLDOUT_TAIL_PAIRS)
    tt_truth = _joint_triple_tail(u_truth, cfg.tail_p, triples)
    tt_vine2 = _joint_triple_tail(u_vine2, cfg.tail_p, triples)

    def _pair_upper(u: np.ndarray, pairs) -> float:
        vals = [
            float(((u[:, i] > cfg.tail_p) & (u[:, j] > cfg.tail_p)).mean() / (1 - cfg.tail_p))
            for i, j in pairs
        ]
        return float(np.mean(vals))

    holdout_drift = abs(_pair_upper(u_truth, holdout_pairs) - _pair_upper(u_vine2, holdout_pairs))
    triple_lift = tt_truth - tt_vine2

    payload: Dict[str, object] = {
        "config": {
            "n_scen": cfg.n_scen, "n_drivers": cfg.n_drivers, "rho": cfg.rho,
            "df_proxy": cfg.df_proxy, "tree12_strength": cfg.tree12_strength,
            "tree3_strength": cfg.tree3_strength, "seed": cfg.seed,
            "confidence": cfg.confidence, "tail_p": cfg.tail_p,
            "third_tree_edges": [[a, b, list(c)] for a, b, c in THIRD_TREE_EDGES],
            "fit_grid": grid,
        },
        "var995_holdout": {
            "truth_tree3": var_truth_h,
            "vine2_truncated": var_vine2_h,
            "tree3_fitted": var_fit_h,
        },
        "truncation_gap_rel": gap2 / var_vine2_h,
        "fitted_tree3_strength": best_s,
        "holdout_closure_share": closure,
        "joint_triple_tail": {"truth": tt_truth, "vine2": tt_vine2, "lift": triple_lift},
        "holdout_pair_drift": holdout_drift,
        "boundary_recovery_max_abs": boundary_recovery_max_abs,
        "boundary_recovery_ok": boundary_recovery_max_abs <= VINE_BOUNDARY_RECOVERY_TOL,
        "truncation_gap_positive": bool(gap2 > 0.0),
        "closure_demonstrated": bool(closure >= 0.5),
        "targeting_ok": bool(triple_lift > max(0.05, 10.0 * holdout_drift)),
    }
    payload["mechanism_demonstrated"] = bool(
        payload["boundary_recovery_ok"]
        and payload["truncation_gap_positive"]
        and payload["closure_demonstrated"]
        and payload["targeting_ok"]
    )
    digest_src = json.dumps(
        {k: payload[k] for k in ("config", "var995_holdout", "joint_triple_tail",
                                 "fitted_tree3_strength", "holdout_closure_share")},
        sort_keys=True, default=float,
    ).encode()
    payload["digest"] = hashlib.sha256(digest_src).hexdigest()
    return payload


def dependence_roadmap_option_study(pre: Dict[str, object]) -> Dict[str, object]:
    """Quantified option study + pre-registered decision rule (applied)."""
    head = mr016_closure_headroom()
    options = {
        "A_tree3_vine_deepening": {
            "what": (
                "ONE additional governed C-vine tree (the four pre-registered "
                "third-tree conditional pairs), same four pair families, frozen "
                "margins/Sigma/df, vine2 AND frozen-t boundary legs reproduced "
                "bit-identically before any candidate run."
            ),
            "expected_residual_closure_abs_max": VINE2_COPULA_FORM_RESIDUAL_POINT,
            "synthetic_holdout_closure_share": pre["holdout_closure_share"],
            "needed_mean_lift_to_enter_ci": head["needed_mean_lift_abs"],
            "cost_cycles": 4,
            "compute": "P29-scale (200x20k bootstrap); proven feasible in this environment",
            "governance_risk": "LOW: additive, disclosed, frozen-headline preserved",
            "eligible": True,
        },
        "B_nested_aware_calibration": {
            "what": (
                "Calibrate dependence parameters directly against the nested "
                "path-wise reference."
            ),
            "expected_residual_closure_abs_max": VINE2_COPULA_FORM_RESIDUAL_POINT,
            "in_sample_closure_by_construction": 1.0,
            "validation_validity": (
                "INVALID as specified: the nested run 46,638.9 is the ONLY "
                "independent benchmark; using it as the calibration target "
                "forfeits out-of-sample validation (circularity). A valid "
                "variant needs a SECOND independent nested run (fresh seeds) - "
                "the most expensive artifact in the repo."
            ),
            "cost_cycles": 6,
            "compute": "one full additional nested simulator run + calibration cycles",
            "governance_risk": "HIGH: circular calibration to the validation benchmark",
            "eligible": False,
            "ineligible_reason": "leakage/circularity without a new nested run; deferred as post-stop owner-approved escalation",
        },
        "C_owner_adoption_package": {
            "what": "Decision package: adopt the disclosed vine read-out, or accept residual with MR-016 OPEN.",
            "expected_residual_closure_abs_max": 0.0,
            "cost_cycles": 1,
            "governance_risk": "NONE: no model change",
            "eligible": False,
            "ineligible_reason": "zero residual closure; scheduled REGARDLESS as the post-Phase-30 owner package",
        },
        "D_stop_rule": {
            "what": "Stop dependence-form escalation; redirect to credentialled-data priority (human-blocked).",
            "expected_residual_closure_abs_max": 0.0,
            "cost_cycles": 0,
            "governance_risk": "NONE",
            "eligible": False,
            "ineligible_reason": "zero closure as a primary action; embedded as the pre-registered conditional stop-rule",
        },
    }
    decision_rule = [
        "R1: exclude options with zero expected residual closure as PRIMARY actions (C, D) - they are scheduled/embedded, not lost.",
        "R2: exclude options that re-use the only independent nested benchmark for calibration (B) unless the owner funds a second nested run.",
        "R3: the remaining option (A) is selected ONLY if the synthetic pre-study demonstrates boundary recovery, a positive truncation gap, holdout closure share >= 0.5, and tree-3 targeting above holdout drift.",
    ]
    stop_rule = (
        "STOP-RULE (pre-registered): if the Phase 30 tree-3 vine still leaves the "
        f"nested reference {NESTED_PATHWISE_SCR_REFERENCE:,.1f} outside its 95% "
        "bootstrap CI at Task 4, dependence-FORM escalation under MR-016 ENDS. "
        "No further copula-structure candidates may be opened without owner "
        "sign-off; Phase 31 becomes the owner decision package (option C), with "
        "option B available only as an owner-approved escalation funding a second "
        "independent nested run."
    )
    selected = SELECTED_OPTION if pre["mechanism_demonstrated"] else "D_stop_rule"
    return {
        "headroom": head,
        "options": options,
        "decision_rule": decision_rule,
        "stop_rule": stop_rule,
        "selected_option": selected,
        "selection_ok": selected == SELECTED_OPTION,
    }


def validate_roadmap_envelope() -> Dict[str, object]:
    """Static checks for the pre-registered Phase 30 search envelope."""
    second_nodes = {tuple(sorted((a, b))) for a, b, _ in SECOND_TREE_EDGES}

    def edge_ok(a: int, b: int, cond: Tuple[int, int]) -> bool:
        # Proximity: both conditioned pairs must extend second-tree edges and
        # condition on the credit root plus one second-tree node.
        return VINE_ROOT_DRIVER in cond and a != b and a not in cond and b not in cond

    third_ok = all(edge_ok(a, b, c) for a, b, c in THIRD_TREE_EDGES)
    third_unique = len({(tuple(sorted((a, b))), tuple(sorted(c))) for a, b, c in THIRD_TREE_EDGES}) == len(THIRD_TREE_EDGES)
    no_new_families = len(PAIR_FAMILY_CANDIDATES) <= 4
    return {
        "max_vine_trees_p30": MAX_VINE_TREES_P30,
        "third_tree_edge_count": len(THIRD_TREE_EDGES),
        "third_tree_edges_ok": third_ok,
        "third_tree_edges_unique": third_unique,
        "first_second_tree_unchanged": len(FIRST_TREE_EDGES) == 6 and len(second_nodes) == 5,
        "pair_families_unchanged": no_new_families,
        "ui_contract": [UI_CONTRACT_FROM, UI_CONTRACT_TO],
        "envelope_ok": bool(third_ok and third_unique and no_new_families
                            and MAX_VINE_TREES_P30 == 3 and len(THIRD_TREE_EDGES) == 4),
    }


def dependence_roadmap_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions for the Phase 30 Task 1 design note."""
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "Design note only: no capital figure produced in Phase 30 Task 1 is a production SCR or decision basis.",
            "Task 2 may implement ONLY the pre-registered tree-3 deepening: the four third-tree conditional pairs, the same four pair families, frozen margins/Sigma/df 2.9451.",
            f"Task 2 must reproduce BOTH boundaries bit-identically before any candidate run: frozen-t {FROZEN_T_COMPONENT_SCR_REFERENCE:,.6f} and the archived 2-tree vine candidate {VINE2_COMPONENT_SCR_POINT:,.6f}.",
            "Family/parameter selection on fit rows only; holdout tail diagnostics disclosed with CIs; single-df t, grouped-t and 2-tree vine comparison variants retained on common random numbers.",
            "The stop-rule is binding: if the nested reference remains outside the tree-3 vine 95% CI, dependence-form escalation ends and Phase 31 is the owner decision package.",
            "Nested-aware calibration (option B) is PROHIBITED without an owner-approved second independent nested run.",
            "Credentialled calibration data and independent APS X2 review remain required before production sign-off.",
        ],
    }
