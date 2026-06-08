"""Path-wise tail diagnostics + capital-delta matrix (Phase 25 Task 4).

EDUCATIONAL ONLY -- not a regulatory capital model.

Phase 25 Task 2 moved the governed bonus-cut decision INTO the inner paths
of the nested truth (path-wise declaration); Task 3 gave the LSMC proxy the
MATCHING analytic basis (smoothed-relief response surface, two FIT-only
scalars sigma/alpha).  The path-wise basis relieves LESS capital in the
tail than the horizon-level basis (nested SCR 46,638.9 vs 40,852.1,
+14.17% -- the MR-010/MR-014 refresh trigger, MET at Task 2).

This module supplies the Task 4 deliverables fixed in the Phase 25 Task 1
design note (s5, pre-registered -- no gate-shopping):

  * with-vs-without and PATHWISE-vs-HORIZON capital deltas at VaR/ES/SCR
    for every level (nested, t-copula, gaussian, var-covar);
  * tail diagnostics ON the path-wise with-actions basis: confidence sweep
    with the action-saturation profile, prefix-subsample convergence,
    copula-seed stability and a margin bootstrap over the n_obs realised
    standalone losses (frozen copula, SII Art. 234);
  * var-covar understatement refreshed on the path-wise basis (MR-010);
  * rank invariance: df re-matched on the WITHOUT-actions staged losses
    must remain 2.9451 with the copula parameters FROZEN (Art. 234 -- no
    silent re-tuning when the action basis changes).

The t/gaussian path-wise read-outs are an ANALYTIC RE-ANCHORING of the
joint copula level: the Phase 24 Task 2 anchored joint liability V is
transformed ONCE with the IDENTICAL node-level path-wise envelope
transform used by the truth and the proxy
(:func:`apply_pathwise_declaration_node`), with the relieved amount

    relieved_hat = alpha * phi_sigma(CR(V)) * clip(beta_fit * V, 0, V),

where (sigma, alpha) are the governed Phase 25 Task 3 FIT-only calibration
and beta_fit is the FIT-sample mean benefit share (ONE additional FIT-only
scalar; leakage-free; no tuning to any nested benchmark).  This is NOT a
full path-wise copula re-aggregation -- that is the documented NEXT-phase
candidate (design note s0/s4); the read-outs here quantify the basis delta
under the frozen dependence structure and are DISCLOSED evidence.

No new acceptance thresholds are introduced: the Task 4 pre-registered
gates are completeness/cross-check, refresh, rank-invariance and
reproducibility gates (design note s5).

Standards: Solvency II Delegated Reg. Art. 23 / Art. 234; SOA ASOP 56
s3.1.3/s3.4/s3.5; SOA ASOP 25 s3.3; IA TAS M s3.2/s3.6; IFoA Life
Aggregation & Simulation WP; McNeil-Frey-Embrechts 2015 ch.7.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional, Sequence

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
from par_model_v2.projection.pathwise_proxy_basis import (
    smoothed_relief_response,
)
from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    simulate_t_copula_uniforms,
)

__all__ = [
    "PATHWISE_DISCLOSURE_THRESHOLD",
    "PW_CONFIDENCE_SWEEP",
    "PW_CONVERGENCE_PREFIXES",
    "PW_SEED_STABILITY_SEEDS",
    "PW_BOOTSTRAP_REPLICATES",
    "PW_BOOTSTRAP_N_SIM",
    "pathwise_joint_with_actions",
    "pathwise_joint_readout",
    "pathwise_confidence_sweep",
    "pathwise_prefix_convergence",
    "pathwise_seed_stability",
    "pathwise_bootstrap_margin_ci",
    "build_pathwise_delta_matrix",
    "pathwise_diagnostics_digest",
    "pathwise_tail_use_restrictions",
]

#: MR-010/MR-014 refresh disclosure trigger (design note s5: REQUIRED when
#: |pathwise - horizon| SCR delta > 1% of the horizon-basis SCR; the Task 2
#: result +14.17% MET this trigger -- recorded, not a tunable).
PATHWISE_DISCLOSURE_THRESHOLD = 0.01

#: Diagnostic configuration constants (identical to the Phase 24 Task 4
#: conventions; DIAGNOSTIC settings, not acceptance thresholds).
PW_CONFIDENCE_SWEEP = (0.90, 0.95, 0.99, 0.995, 0.999)
PW_CONVERGENCE_PREFIXES = (25_000, 50_000, 100_000, 200_000)
PW_SEED_STABILITY_SEEDS = (20260607, 11, 1234, 777, 424242)
PW_BOOTSTRAP_REPLICATES = 200
PW_BOOTSTRAP_N_SIM = 20_000


def pathwise_joint_with_actions(
    rule: ManagementActionRule,
    joint_levels: np.ndarray,
    reference_assets: float,
    sigma: float,
    alpha: float,
    benefit_share: float,
) -> Dict[str, object]:
    """Path-wise with-actions transform of anchored joint liability levels.

    Applies the IDENTICAL node-level envelope transform used by the truth
    and the proxy (:func:`apply_pathwise_declaration_node`):

        B_hat        = clip(benefit_share * V, 0, V)
        relieved_hat = alpha * phi_sigma(CR(V)) * B_hat
        W            = V - clip(relieved_hat, 0, max_relief * B_hat)

    ``benefit_share`` is the FIT-sample mean benefit share (leakage-free
    scalar); a constant share is a disclosed first-order approximation at
    the joint level (the per-node share spread is reported by the build).
    Returns the with-actions levels plus diagnostics.
    """
    if not (0.0 < float(benefit_share) <= 1.0):
        raise ValueError("benefit_share must be in (0, 1]")
    V = np.asarray(joint_levels, dtype=float)
    if np.any(V <= 0.0):
        raise ValueError("joint levels must be positive (anchoring violated)")
    b_hat = float(benefit_share) * V
    cr = rule.coverage_ratio(V, reference_assets)
    frac = float(alpha) * smoothed_relief_response(rule, cr, float(sigma))
    relieved = frac * np.clip(b_hat, 0.0, V)
    W, clip_share = apply_pathwise_declaration_node(rule, V, b_hat, relieved)
    return {
        "W": W,
        "clip_binding_share": float(clip_share),
        "relieved": relieved,
        "relief_fraction_smoothed": frac,
        "active_share": float(np.mean(relieved > 1e-9)),
    }


def _draw_joint_levels(
    agg: JointActionAggregator,
    n_sim: int,
    seed: int,
    df: Optional[float],
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if df is None:
        U = simulate_gaussian_copula_uniforms(rng, n_sim, agg.correlation)
    else:
        U = simulate_t_copula_uniforms(rng, n_sim, agg.correlation, df)
    return agg.joint_levels(U)


def pathwise_joint_readout(
    agg: JointActionAggregator,
    n_sim: int,
    seed: int,
    df: Optional[float],
    sigma: float,
    alpha: float,
    benefit_share: float,
    confidence: float = 0.995,
) -> Dict[str, object]:
    """One copula draw -> horizon AND path-wise with-actions read-outs.

    Both bases are evaluated on the SAME anchored joint levels (common
    random numbers), so the pathwise-vs-horizon delta is free of
    Monte-Carlo draw noise.  The horizon basis is the archived Phase 24
    Task 2 joint-action transform ``rule.apply_to_liabilities``.
    """
    V = _draw_joint_levels(agg, int(n_sim), int(seed), df)
    W_hz = agg.rule.apply_to_liabilities(V, agg.a_ref)
    pw = pathwise_joint_with_actions(
        agg.rule, V, agg.a_ref, sigma, alpha, benefit_share)
    W_pw = pw["W"]
    m_pw = capital_metrics_from_liabilities(W_pw, float(confidence), 12)
    m_hz = capital_metrics_from_liabilities(W_hz, float(confidence), 12)
    m_wo = capital_metrics_from_liabilities(V, float(confidence), 12)
    out = {
        "config": {
            "n_sim": int(n_sim), "seed": int(seed),
            "df": None if df is None else float(df),
            "copula": "gaussian" if df is None else "t({:g})".format(df),
            "confidence": float(confidence),
            "sigma": float(sigma), "alpha": float(alpha),
            "benefit_share_fit": float(benefit_share),
        },
        "var_pathwise": float(m_pw.var_liability),
        "es_pathwise": float(m_pw.es_liability),
        "scr_pathwise": float(m_pw.scr_proxy),
        "mean_pathwise": float(np.mean(W_pw)),
        "var_horizon": float(m_hz.var_liability),
        "es_horizon": float(m_hz.es_liability),
        "scr_horizon": float(m_hz.scr_proxy),
        "var_without": float(m_wo.var_liability),
        "es_without": float(m_wo.es_liability),
        "scr_without": float(m_wo.scr_proxy),
        "clip_binding_share": pw["clip_binding_share"],
        "active_share_pathwise": pw["active_share"],
        "pathwise_minus_horizon_scr": float(m_pw.scr_proxy - m_hz.scr_proxy),
    }
    out["digest"] = hashlib.sha256(json.dumps(
        {k: out[k] for k in ("config", "var_pathwise", "es_pathwise",
                             "scr_pathwise", "var_horizon", "scr_horizon")},
        sort_keys=True).encode()).hexdigest()[:12]
    return out


def pathwise_confidence_sweep(
    agg: JointActionAggregator,
    n_sim: int,
    seed: int,
    df: float,
    sigma: float,
    alpha: float,
    benefit_share: float,
    confidences: Sequence[float] = PW_CONFIDENCE_SWEEP,
) -> List[Dict[str, float]]:
    """VaR/ES/SCR sweep with the action-saturation profile in each tail.

    The tail at confidence c is the set of scenarios with WITHOUT-actions
    joint level V above VaR_c(V) (the Phase 24 Task 4 convention).  The
    saturation share uses the RAW governed cut factor (cut <= 0, i.e. CR
    at/below the floor) so the figure is directly comparable to the
    archived joint-action profile; the smoothed path-wise relief fraction
    in the same tail is reported alongside.
    """
    V = _draw_joint_levels(agg, int(n_sim), int(seed), float(df))
    W_hz = agg.rule.apply_to_liabilities(V, agg.a_ref)
    pw = pathwise_joint_with_actions(
        agg.rule, V, agg.a_ref, sigma, alpha, benefit_share)
    W_pw = pw["W"]
    cut = agg.rule.cut_factor(agg.rule.coverage_ratio(V, agg.a_ref))
    frac = np.asarray(pw["relief_fraction_smoothed"], dtype=float)
    rows: List[Dict[str, float]] = []
    for c in confidences:
        m_p = capital_metrics_from_liabilities(W_pw, float(c), 12)
        m_h = capital_metrics_from_liabilities(W_hz, float(c), 12)
        m_v = capital_metrics_from_liabilities(V, float(c), 12)
        tail = V >= float(np.quantile(V, c))
        rows.append({
            "confidence": float(c),
            "var_pathwise": float(m_p.var_liability),
            "es_pathwise": float(m_p.es_liability),
            "scr_pathwise": float(m_p.scr_proxy),
            "var_horizon": float(m_h.var_liability),
            "scr_horizon": float(m_h.scr_proxy),
            "var_without": float(m_v.var_liability),
            "scr_without": float(m_v.scr_proxy),
            "tail_active_share": float(np.mean(cut[tail] < 1.0)),
            "tail_saturation_share": float(np.mean(cut[tail] <= 0.0)),
            "tail_mean_smoothed_relief_fraction": float(np.mean(frac[tail])),
            "relief_at_var_pathwise":
                float(m_v.var_liability - m_p.var_liability),
            "relief_at_var_horizon":
                float(m_v.var_liability - m_h.var_liability),
            "pathwise_minus_horizon_scr":
                float(m_p.scr_proxy - m_h.scr_proxy),
        })
    return rows


def pathwise_prefix_convergence(
    agg: JointActionAggregator,
    seed: int,
    df: float,
    sigma: float,
    alpha: float,
    benefit_share: float,
    prefixes: Sequence[int] = PW_CONVERGENCE_PREFIXES,
    confidence: float = 0.995,
) -> List[Dict[str, float]]:
    """Convergence of the path-wise 99.5% read-out on prefix subsamples
    (single draw, common random numbers; no re-draw)."""
    n_full = int(max(prefixes))
    V = _draw_joint_levels(agg, n_full, int(seed), float(df))
    W = pathwise_joint_with_actions(
        agg.rule, V, agg.a_ref, sigma, alpha, benefit_share)["W"]
    full = capital_metrics_from_liabilities(W, float(confidence), 12)
    rows: List[Dict[str, float]] = []
    for n in sorted(int(p) for p in prefixes):
        m = capital_metrics_from_liabilities(W[:n], float(confidence), 12)
        rows.append({
            "n_sim": n,
            "var_pathwise": float(m.var_liability),
            "scr_pathwise": float(m.scr_proxy),
            "var_rel_delta_vs_full": float(
                abs(m.var_liability - full.var_liability)
                / abs(full.var_liability)),
            "scr_rel_delta_vs_full": float(
                abs(m.scr_proxy - full.scr_proxy) / abs(full.scr_proxy)),
        })
    return rows


def pathwise_seed_stability(
    agg: JointActionAggregator,
    df: float,
    n_sim: int,
    sigma: float,
    alpha: float,
    benefit_share: float,
    seeds: Sequence[int] = PW_SEED_STABILITY_SEEDS,
    confidence: float = 0.995,
) -> Dict[str, object]:
    """Path-wise SCR across independent copula seeds (MC-path stability)."""
    rows = []
    for sd in seeds:
        r = pathwise_joint_readout(
            agg, int(n_sim), int(sd), float(df), sigma, alpha,
            benefit_share, confidence)
        rows.append({"seed": int(sd), "scr_pathwise": r["scr_pathwise"],
                     "var_pathwise": r["var_pathwise"]})
    scrs = np.array([r["scr_pathwise"] for r in rows])
    return {
        "rows": rows,
        "scr_mean": float(np.mean(scrs)),
        "scr_max_rel_spread": float(
            (np.max(scrs) - np.min(scrs)) / np.mean(scrs)),
    }


def pathwise_bootstrap_margin_ci(
    losses_without: Dict[str, np.ndarray],
    correlation: np.ndarray,
    rule: ManagementActionRule,
    l_fit: float,
    anchor_means: Dict[str, float],
    df: float,
    sigma: float,
    alpha: float,
    benefit_share: float,
    n_replicates: int = PW_BOOTSTRAP_REPLICATES,
    n_sim: int = PW_BOOTSTRAP_N_SIM,
    seed: int = 20260608,
    confidence: float = 0.995,
) -> Dict[str, object]:
    """Bootstrap over the realised standalone-loss observations.

    Joint row resample WITH replacement (preserves realised cross-driver
    pairing); the copula df/rho stay FROZEN (SII Art. 234 -- the governed
    dependence basis is not re-tuned inside replicates).  Identical
    conventions to the archived Phase 24 Task 4 bootstrap; percentile CI +
    SE on the path-wise VaR/ES/SCR are DISCLOSED diagnostics.
    """
    drivers = list(losses_without.keys())
    n_obs = int(np.asarray(losses_without[drivers[0]]).size)
    rng = np.random.default_rng(int(seed))
    var_b, es_b, scr_b = [], [], []
    for _ in range(int(n_replicates)):
        idx = rng.integers(0, n_obs, size=n_obs)
        res_losses = {k: np.asarray(losses_without[k], float)[idx]
                      for k in drivers}
        agg_b = JointActionAggregator(
            standalone_losses=res_losses, correlation=correlation,
            rule=rule, l_fit=l_fit, anchor_means=anchor_means)
        sub_seed = int(rng.integers(0, 2**31 - 1))
        r = pathwise_joint_readout(
            agg_b, int(n_sim), sub_seed, float(df), sigma, alpha,
            benefit_share, confidence)
        var_b.append(r["var_pathwise"])
        es_b.append(r["es_pathwise"])
        scr_b.append(r["scr_pathwise"])

    def _ci(x: List[float]) -> Dict[str, float]:
        a = np.asarray(x, dtype=float)
        return {
            "mean": float(np.mean(a)),
            "se": float(np.std(a, ddof=1)),
            "ci_lo_95": float(np.quantile(a, 0.025)),
            "ci_hi_95": float(np.quantile(a, 0.975)),
        }

    return {
        "n_replicates": int(n_replicates),
        "n_sim_per_replicate": int(n_sim),
        "n_obs": n_obs,
        "seed": int(seed),
        "resampling": "joint row resample (preserves realised cross-driver "
                      "pairing); copula df/rho frozen (SII Art. 234)",
        "var_pathwise": _ci(var_b),
        "es_pathwise": _ci(es_b),
        "scr_pathwise": _ci(scr_b),
    }


def build_pathwise_delta_matrix(
    without: Dict[str, Dict[str, Optional[float]]],
    with_horizon: Dict[str, Dict[str, Optional[float]]],
    with_pathwise: Dict[str, Dict[str, Optional[float]]],
) -> Dict[str, object]:
    """Assemble the with-vs-without / pathwise-vs-horizon delta matrix.

    Inputs are mappings level -> {var, es, scr} (entries may be None where
    a level has no analogue on a basis -- e.g. the var-covar formula has
    no path-wise analogue, DISCLOSED).  Deltas are reported wherever both
    sides expose the metric.
    """
    levels = ["nested", "t_copula", "gaussian", "var_covar"]
    matrix: Dict[str, object] = {}
    for lv in levels:
        w0 = without[lv]
        hz = with_horizon.get(lv)
        pw = with_pathwise.get(lv)
        row: Dict[str, object] = {
            "without": w0,
            "with_horizon": hz,
            "with_pathwise": pw,
        }
        for name, basis in (("with_horizon", hz), ("with_pathwise", pw)):
            if basis is None:
                continue
            d: Dict[str, float] = {}
            for metric in ("var", "es", "scr"):
                a, b = basis.get(metric), w0.get(metric)
                if a is not None and b is not None:
                    d[metric + "_delta"] = float(a - b)
                    d[metric + "_delta_pct"] = float((a - b) / abs(b))
            row[name + "_minus_without"] = d
        if hz is not None and pw is not None:
            d2: Dict[str, float] = {}
            for metric in ("var", "es", "scr"):
                a, b = pw.get(metric), hz.get(metric)
                if a is not None and b is not None:
                    d2[metric + "_delta"] = float(a - b)
                    d2[metric + "_delta_pct"] = float((a - b) / abs(b))
            if d2:
                row["pathwise_minus_horizon"] = d2
        matrix[lv] = row
    return matrix


def pathwise_diagnostics_digest(payload: Dict[str, object]) -> str:
    """Deterministic SHA-256 digest of a diagnostics payload."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=float).encode("utf-8")
    ).hexdigest()


def pathwise_tail_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions (IA TAS M s3.2; SOA ASOP 56 s3.5)."""
    return {
        "classification": "EDUCATIONAL_DEMONSTRATION_ONLY",
        "approved_uses": [
            "Methodology demonstration of tail diagnostics and capital-"
            "delta reporting when a management-action basis changes "
            "(horizon-level -> path-wise) under a frozen dependence "
            "structure (Solvency II Art. 23 / Art. 234)",
            "Quantification of the path-wise vs horizon-level recognition-"
            "lag effect at the aggregate level",
        ],
        "prohibited_uses": [
            "Production capital or solvency decisions",
            "Policyholder bonus declarations",
            "Regulatory submissions",
        ],
        "rationale": (
            "The t/gaussian path-wise read-outs are an analytic "
            "re-anchoring of the joint copula level with the governed "
            "smoothed-relief surface and a constant FIT-sample benefit "
            "share -- NOT a full path-wise copula re-aggregation (the "
            "documented next-phase candidate). Action parameters remain "
            "educational placeholders pending credentialled management-"
            "practice data and independent APS X2 review; n_obs-level "
            "margin sampling noise is disclosed via the bootstrap."
        ),
    }
