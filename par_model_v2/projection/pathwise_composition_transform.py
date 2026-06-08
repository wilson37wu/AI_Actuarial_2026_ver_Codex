"""
Phase 26 Task 2 - per-driver composition transform on the FROZEN copula.

Replaces the Phase 25 Task 4 LEVEL transform (governed smoothed-relief
surface + ONE constant FIT benefit share applied to the anchored joint
TOTAL liability level) with the full path-wise copula re-aggregation
designed in the Phase 26 Task 1 note: for each joint copula scenario the
per-driver loss composition is recovered from the FROZEN empirical margins,
the scenario is split into a CUTTABLE sub-level (base liability plus the
rate / equity / lapse / mortality deviations) and a CARVE-OUT remainder
(credit loss and the analytic FX / liquidity offsets - not relievable by a
bonus cut, P24T3 convention), and the governed relief is applied to the
scenario's cuttable component ONLY, with the per-scenario ``max_relief``
envelope clip (the node-level envelope preserved per scenario via
:func:`apply_pathwise_declaration_node`).

Anchoring identity (Phase 23 Task 4 convention, unchanged):

    V      = L_fit + sum_k (Q_k(U_k) - mean_k)          (joint total)
    V_cut  = L_fit + sum_{k in CUTTABLE} (Q_k(U_k) - mean_k)
    B_comp = clip(beta_fit * V_cut, 0, V)               (component benefit base)
    frac   = alpha * phi_sigma(CR(V))                   (governed surface, frozen)
    W      = V - clip(frac * B_comp, 0, max_relief * B_comp)

The LEVEL variant (B_level = clip(beta_fit * V, 0, V)) is RETAINED on
common random numbers as the comparison basis (P24T3 convention): the ONLY
difference between the two bases is whether the benefit base sees the
scenario's cuttable composition.  Calibration scalars sigma / alpha /
beta_fit are the governed Phase 25 Task 3 FIT-sample values - NO re-tuning
(pre-registered gate).  Copula parameters are FROZEN (df 2.9451
tail-matched on the without-actions basis; correlation bit-frozen,
Solvency II Art. 234 rank invariance).

EDUCATIONAL MODEL: all parameters are educational placeholders pending
credentialled data and independent APS X2 review.  NOT for production
capital decisions.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, Optional, Tuple

import numpy as np

from par_model_v2.projection.inner_path_action_dynamics import (
    apply_pathwise_declaration_node,
)
from par_model_v2.projection.joint_action_aggregation import (
    JointActionAggregator,
    simulate_gaussian_copula_uniforms,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.pathwise_proxy_basis import smoothed_relief_response
from par_model_v2.projection.pathwise_tail_diagnostics import (
    pathwise_joint_with_actions,
)
from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    simulate_t_copula_uniforms,
)

# Carve-out split (P24T3 convention): credit loss and the analytic FX /
# liquidity offsets are NOT relievable by the governed bonus cut.
CUTTABLE_DRIVERS: Tuple[str, ...] = ("rate", "equity", "lapse", "mortality")
CARVEOUT_DRIVERS: Tuple[str, ...] = ("credit", "fx", "liquidity")


def split_joint_composition(
    agg: JointActionAggregator, U: np.ndarray
) -> Dict[str, object]:
    """Recover the per-driver composition of each joint copula scenario.

    Returns the joint totals ``V`` (computed by ``agg.joint_levels`` so the
    totals are BIT-IDENTICAL to the archived level-basis draw on the same
    uniforms), the cuttable sub-level ``V_cut`` and the carve-out deviation
    sum, plus the reconstruction error of the anchoring identity
    (diagnostic; the identity holds to floating-point accumulation order).
    """
    unknown = [k for k in agg.drivers
               if k not in CUTTABLE_DRIVERS + CARVEOUT_DRIVERS]
    if unknown:
        raise ValueError("drivers without a carve-out classification: "
                         + ", ".join(unknown))
    V = agg.joint_levels(U)
    dev_cut = np.zeros(U.shape[0], dtype=float)
    dev_carve = np.zeros(U.shape[0], dtype=float)
    for j, k in enumerate(agg.drivers):
        dev = agg.margins[k].ppf(U[:, j]) - agg.anchor_means[k]
        if k in CUTTABLE_DRIVERS:
            dev_cut += dev
        else:
            dev_carve += dev
    v_cut = agg.l_fit + dev_cut
    recon = agg.l_fit + dev_cut + dev_carve
    return {
        "V": V,
        "V_cut": v_cut,
        "dev_carve": dev_carve,
        "reconstruction_max_abs_err": float(np.max(np.abs(recon - V))),
    }


def composition_with_actions(
    rule: ManagementActionRule,
    joint_levels: np.ndarray,
    cuttable_levels: np.ndarray,
    reference_assets: float,
    sigma: float,
    alpha: float,
    benefit_share: float,
) -> Dict[str, object]:
    """Component-basis with-actions transform (per-scenario cuttable base).

    Identical envelope machinery to the truth / proxy / level bases
    (:func:`apply_pathwise_declaration_node`); the ONLY change vs the level
    transform is the benefit base ``B = clip(beta * V_cut, 0, V)`` instead
    of ``B = clip(beta * V, 0, V)``.
    """
    if not (0.0 < float(benefit_share) <= 1.0):
        raise ValueError("benefit_share must be in (0, 1]")
    V = np.asarray(joint_levels, dtype=float)
    if np.any(V <= 0.0):
        raise ValueError("joint levels must be positive (anchoring violated)")
    v_cut = np.asarray(cuttable_levels, dtype=float)
    if v_cut.shape != V.shape:
        raise ValueError("cuttable levels misaligned with joint levels")
    b_comp = np.clip(float(benefit_share) * v_cut, 0.0, V)
    cr = rule.coverage_ratio(V, reference_assets)
    frac = float(alpha) * smoothed_relief_response(rule, cr, float(sigma))
    relieved = frac * b_comp
    W, clip_share = apply_pathwise_declaration_node(rule, V, b_comp, relieved)
    return {
        "W": W,
        "clip_binding_share": float(clip_share),
        "relieved": relieved,
        "relief_fraction_smoothed": frac,
        "benefit_base": b_comp,
        "active_share": float(np.mean(relieved > 1e-9)),
    }


def composition_joint_readout(
    agg: JointActionAggregator,
    n_sim: int,
    seed: int,
    df: Optional[float],
    sigma: float,
    alpha: float,
    benefit_share: float,
    confidence: float = 0.995,
) -> Dict[str, object]:
    """One frozen-copula draw -> component AND level with-actions read-outs.

    Common random numbers: the level variant consumes the SAME joint totals
    as the archived Phase 25 Task 4 read-out (identical rng stream), so the
    component-vs-level delta is free of Monte-Carlo draw noise and the
    level read-out doubles as a bit-identity cross-check against the
    archived figures.
    """
    rng = np.random.default_rng(int(seed))
    if df is None:
        U = simulate_gaussian_copula_uniforms(rng, int(n_sim), agg.correlation)
    else:
        U = simulate_t_copula_uniforms(rng, int(n_sim), agg.correlation,
                                       float(df))
    comp = split_joint_composition(agg, U)
    V = comp["V"]
    v_cut = comp["V_cut"]

    pw_level = pathwise_joint_with_actions(
        agg.rule, V, agg.a_ref, sigma, alpha, benefit_share)
    pw_comp = composition_with_actions(
        agg.rule, V, v_cut, agg.a_ref, sigma, alpha, benefit_share)

    m_wo = capital_metrics_from_liabilities(V, float(confidence), 12)
    m_lv = capital_metrics_from_liabilities(
        np.asarray(pw_level["W"], dtype=float), float(confidence), 12)
    m_cp = capital_metrics_from_liabilities(
        np.asarray(pw_comp["W"], dtype=float), float(confidence), 12)

    # composition-heterogeneity diagnostics (design-note s3 analogues)
    share = np.clip(v_cut, 0.0, V) / V
    tail = V >= float(m_wo.var_liability)
    share_mean = float(np.mean(share))
    share_tail = float(np.mean(share[tail]))

    out = {
        "config": {
            "n_sim": int(n_sim), "seed": int(seed),
            "df": None if df is None else float(df),
            "copula": "gaussian" if df is None else "t({:g})".format(df),
            "confidence": float(confidence),
            "sigma": float(sigma), "alpha": float(alpha),
            "benefit_share_fit": float(benefit_share),
            "cuttable_drivers": list(CUTTABLE_DRIVERS),
            "carveout_drivers": list(CARVEOUT_DRIVERS),
        },
        "var_without": float(m_wo.var_liability),
        "es_without": float(m_wo.es_liability),
        "scr_without": float(m_wo.scr_proxy),
        "var_level": float(m_lv.var_liability),
        "es_level": float(m_lv.es_liability),
        "scr_level": float(m_lv.scr_proxy),
        "var_component": float(m_cp.var_liability),
        "es_component": float(m_cp.es_liability),
        "scr_component": float(m_cp.scr_proxy),
        "mean_component": float(np.mean(pw_comp["W"])),
        "mean_level": float(np.mean(pw_level["W"])),
        "component_minus_level_scr": float(m_cp.scr_proxy - m_lv.scr_proxy),
        "clip_binding_share_level": float(pw_level["clip_binding_share"]),
        "clip_binding_share_component": float(pw_comp["clip_binding_share"]),
        "active_share_level": float(pw_level["active_share"]),
        "active_share_component": float(pw_comp["active_share"]),
        "cuttable_share_mean": share_mean,
        "cuttable_share_tail_mean": share_tail,
        "tail_cuttable_share_depression": share_mean - share_tail,
        "mean_relief_level": float(np.mean(pw_level["relieved"])),
        "mean_relief_component": float(np.mean(
            np.minimum(np.maximum(np.asarray(pw_comp["relieved"]), 0.0),
                       agg.rule.max_relief
                       * np.asarray(pw_comp["benefit_base"])))),
        "composition_reconstruction_max_abs_err":
            comp["reconstruction_max_abs_err"],
    }
    out["digest"] = hashlib.sha256(json.dumps(
        {k: out[k] for k in ("config", "var_without", "scr_without",
                             "var_level", "scr_level", "var_component",
                             "scr_component")},
        sort_keys=True).encode()).hexdigest()[:12]
    return out


def composition_transform_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions (TAS M s3.2 / ASOP 56 s3.5)."""
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "The component basis consumes the governed P25T3 FIT-sample "
            "scalars (sigma, alpha, beta_fit) without re-tuning; residual "
            "relief-surface error is decomposed at Task 3 if the bootstrap "
            "CI gate fails.",
            "Per-driver composition recovery is exact only at the driver "
            "margin level used by the benchmark; node-level heterogeneity "
            "below the driver level remains aggregated (design note s6).",
            "Copula parameters are FROZEN (df 2.9451; correlation "
            "bit-frozen); the transform must NOT re-tune them "
            "(Solvency II Art. 234 rank invariance).",
            "Action parameters remain educational placeholders pending "
            "credentialled practice data + independent APS X2 review.",
        ],
    }
