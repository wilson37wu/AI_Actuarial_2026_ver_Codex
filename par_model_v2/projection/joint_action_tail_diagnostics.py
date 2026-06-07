"""Joint-action tail diagnostics + capital-delta matrix (Phase 24 Task 4).

EDUCATIONAL ONLY -- not a regulatory capital model.

Phase 24 Task 2 established the JOINT-action (action-after-aggregation)
basis as the standing with-actions copula read-out (t(2.9451) SCR rel err
vs the nested-with-actions reference 22.54% -> 6.39%).  This module supplies
the Task 4 deliverables fixed in the Phase 24 Task 1 design note (s5):

  * with-vs-without and joint-vs-standalone capital deltas at VaR / ES /
    SCR for every level (nested, t-copula, gaussian, var-covar);
  * tail diagnostics ON the joint-action basis: confidence sweep with
    action-saturation profile, prefix-subsample convergence of the 99.5%
    read-out, copula-seed stability, and a bootstrap over the n_obs=160
    realised standalone losses (the dominant sampling-noise source,
    disclosed in the Task 1 design note) giving SE + percentile CI on the
    joint-with VaR/ES/SCR;
  * var-covar understatement refreshed on the joint-action basis.

No new acceptance thresholds are introduced: the Task 4 pre-registered
gates are completeness/cross-check, refresh, and reproducibility gates
(design note s5) -- the diagnostics below are DISCLOSED evidence, not
post-hoc numeric gates (no gate-shopping).

Standards: Solvency II Delegated Reg. Art. 23 / Art. 234; SOA ASOP 56
s3.1.3/s3.4/s3.5; SOA ASOP 25 s3.3; IA TAS M s3.2/s3.6; IFoA Life
Aggregation & Simulation WP; McNeil-Frey-Embrechts 2015 ch.7.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional, Sequence

import numpy as np

from par_model_v2.projection.joint_action_aggregation import (
    JointActionAggregator,
    JointActionConfig,
    simulate_gaussian_copula_uniforms,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.multi_driver_copula_aggregation import _EmpiricalMargin
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    simulate_t_copula_uniforms,
)

__all__ = [
    "CONFIDENCE_SWEEP",
    "CONVERGENCE_PREFIXES",
    "SEED_STABILITY_SEEDS",
    "BOOTSTRAP_REPLICATES",
    "BOOTSTRAP_N_SIM",
    "confidence_sweep_with_saturation",
    "prefix_convergence",
    "seed_stability",
    "bootstrap_margin_ci",
    "build_delta_matrix",
]

#: Diagnostic configuration constants (recorded for reproducibility; these
#: are DIAGNOSTIC settings, not acceptance thresholds).
CONFIDENCE_SWEEP = (0.90, 0.95, 0.99, 0.995, 0.999)
CONVERGENCE_PREFIXES = (25_000, 50_000, 100_000, 200_000)
SEED_STABILITY_SEEDS = (20260607, 11, 1234, 777, 424242)
BOOTSTRAP_REPLICATES = 200
BOOTSTRAP_N_SIM = 20_000


def _joint_with_without(
    agg: JointActionAggregator,
    n_sim: int,
    seed: int,
    df: Optional[float],
) -> Dict[str, np.ndarray]:
    """One copula draw -> anchored joint levels V and with-actions W."""
    rng = np.random.default_rng(seed)
    if df is None:
        U = simulate_gaussian_copula_uniforms(rng, n_sim, agg.correlation)
    else:
        U = simulate_t_copula_uniforms(rng, n_sim, agg.correlation, df)
    V = agg.joint_levels(U)
    W = agg.rule.apply_to_liabilities(V, agg.a_ref)
    cut = agg.rule.cut_factor(agg.rule.coverage_ratio(V, agg.a_ref))
    return {"V": V, "W": W, "cut": cut}


def confidence_sweep_with_saturation(
    agg: JointActionAggregator,
    n_sim: int,
    seed: int,
    df: float,
    confidences: Sequence[float] = CONFIDENCE_SWEEP,
) -> List[Dict[str, float]]:
    """VaR/ES/SCR sweep with the action-saturation profile in each tail.

    For each confidence level c the tail is the set of scenarios with
    WITHOUT-actions joint level V above VaR_c(V); the saturation share is
    the fraction of those tail scenarios where the governed cut factor is
    at the floor (maximum relief) -- the Phase 23 Task 4 saturation
    mechanism, now quantified on the joint basis.
    """
    s = _joint_with_without(agg, n_sim, seed, df)
    V, W, cut = s["V"], s["W"], s["cut"]
    out: List[Dict[str, float]] = []
    for c in confidences:
        m_w = capital_metrics_from_liabilities(W, float(c), 12)
        m_v = capital_metrics_from_liabilities(V, float(c), 12)
        var_v = float(np.quantile(V, c))
        tail = V >= var_v
        out.append({
            "confidence": float(c),
            "var_with": float(m_w.var_liability),
            "es_with": float(m_w.es_liability),
            "scr_with": float(m_w.scr_proxy),
            "var_without": float(m_v.var_liability),
            "es_without": float(m_v.es_liability),
            "scr_without": float(m_v.scr_proxy),
            "tail_active_share": float(np.mean(cut[tail] < 1.0)),
            "tail_saturation_share": float(np.mean(cut[tail] <= 0.0)),
            "tail_mean_cut_factor": float(np.mean(cut[tail])),
            "relief_at_var": float(m_v.var_liability - m_w.var_liability),
        })
    return out


def prefix_convergence(
    agg: JointActionAggregator,
    seed: int,
    df: float,
    prefixes: Sequence[int] = CONVERGENCE_PREFIXES,
    confidence: float = 0.995,
) -> List[Dict[str, float]]:
    """Convergence of the joint-with 99.5% read-out on prefix subsamples.

    A single copula draw of max(prefixes) scenarios is evaluated on its
    prefixes, so the sequence differs only by Monte-Carlo sample size
    (common random numbers; no re-draw).
    """
    n_full = int(max(prefixes))
    s = _joint_with_without(agg, n_full, seed, df)
    W = s["W"]
    full = capital_metrics_from_liabilities(W, confidence, 12)
    rows: List[Dict[str, float]] = []
    for n in sorted(int(p) for p in prefixes):
        m = capital_metrics_from_liabilities(W[:n], confidence, 12)
        rows.append({
            "n_sim": n,
            "var_with": float(m.var_liability),
            "es_with": float(m.es_liability),
            "scr_with": float(m.scr_proxy),
            "var_rel_delta_vs_full":
                float(abs(m.var_liability - full.var_liability)
                      / abs(full.var_liability)),
            "scr_rel_delta_vs_full":
                float(abs(m.scr_proxy - full.scr_proxy)
                      / abs(full.scr_proxy)),
        })
    return rows


def seed_stability(
    agg: JointActionAggregator,
    df: float,
    n_sim: int,
    seeds: Sequence[int] = SEED_STABILITY_SEEDS,
    confidence: float = 0.995,
) -> Dict[str, object]:
    """Joint-with SCR across independent copula seeds (MC-path stability)."""
    rows = []
    for sd in seeds:
        res = agg.run(JointActionConfig(n_sim=n_sim, seed=int(sd), df=df,
                                        confidence=confidence))
        rows.append({"seed": int(sd), "scr_with": res.scr_joint_with,
                     "var_with": res.var_joint_with})
    scrs = np.array([r["scr_with"] for r in rows])
    return {
        "rows": rows,
        "scr_mean": float(np.mean(scrs)),
        "scr_max_rel_spread": float((np.max(scrs) - np.min(scrs))
                                    / np.mean(scrs)),
    }


def bootstrap_margin_ci(
    losses_without: Dict[str, np.ndarray],
    correlation: np.ndarray,
    rule: ManagementActionRule,
    l_fit: float,
    anchor_means: Dict[str, float],
    df: float,
    n_replicates: int = BOOTSTRAP_REPLICATES,
    n_sim: int = BOOTSTRAP_N_SIM,
    seed: int = 20260608,
    confidence: float = 0.995,
) -> Dict[str, object]:
    """Bootstrap over the realised standalone-loss observations.

    The Task 1 design note discloses that empirical margins built from the
    n_obs=160 realised losses are sampling-noisy and that the joint
    read-out inherits this.  Each replicate resamples the outer
    observations WITH replacement (jointly across drivers, preserving
    realised cross-driver pairing), rebuilds the empirical margins, and
    recomputes the joint-with VaR/ES/SCR under the frozen copula
    (df NOT re-matched -- the dependence basis is governed and frozen;
    SII Art. 234).  Percentile CI + SE are DISCLOSED diagnostics.
    """
    drivers = list(losses_without.keys())
    n_obs = int(np.asarray(losses_without[drivers[0]]).size)
    rng = np.random.default_rng(seed)
    var_b, es_b, scr_b = [], [], []
    for _ in range(int(n_replicates)):
        idx = rng.integers(0, n_obs, size=n_obs)
        res_losses = {k: np.asarray(losses_without[k], float)[idx]
                      for k in drivers}
        agg_b = JointActionAggregator(
            standalone_losses=res_losses,
            correlation=correlation,
            rule=rule,
            l_fit=l_fit,
            anchor_means=anchor_means,
        )
        sub_seed = int(rng.integers(0, 2**31 - 1))
        res = agg_b.run(JointActionConfig(n_sim=n_sim, seed=sub_seed, df=df,
                                          confidence=confidence))
        var_b.append(res.var_joint_with)
        es_b.append(res.es_joint_with)
        scr_b.append(res.scr_joint_with)
    var_a, es_a, scr_a = (np.array(var_b), np.array(es_b), np.array(scr_b))

    def _ci(x: np.ndarray) -> Dict[str, float]:
        return {
            "mean": float(np.mean(x)),
            "se": float(np.std(x, ddof=1)),
            "ci_lo_95": float(np.quantile(x, 0.025)),
            "ci_hi_95": float(np.quantile(x, 0.975)),
        }

    return {
        "n_replicates": int(n_replicates),
        "n_sim_per_replicate": int(n_sim),
        "n_obs": n_obs,
        "seed": int(seed),
        "resampling": "joint row resample (preserves realised cross-driver "
                      "pairing); copula df/rho frozen (SII Art. 234)",
        "var_with": _ci(var_a),
        "es_with": _ci(es_a),
        "scr_with": _ci(scr_a),
    }


def build_delta_matrix(
    without: Dict[str, Dict[str, float]],
    standalone_action: Dict[str, Dict[str, float]],
    joint_action: Dict[str, Dict[str, float]],
) -> Dict[str, object]:
    """Assemble the with-vs-without / joint-vs-standalone delta matrix.

    Inputs are mappings level -> {var, es, scr} (es/var may be None for the
    var-covar formula level).  Deltas are reported at SCR for every level
    and at VaR/ES where both sides expose them.  The nested level has no
    standalone/joint split: the nested-with-actions run applies the rule to
    the full conditional liability and is the reference for both bases.
    """
    levels = ["nested", "t_copula", "gaussian", "var_covar"]
    matrix: Dict[str, object] = {}
    for lv in levels:
        w0 = without[lv]
        sa = standalone_action.get(lv)
        ja = joint_action.get(lv)
        row: Dict[str, object] = {
            "without": w0,
            "standalone_action": sa,
            "joint_action": ja,
        }
        for basis_name, basis in (("standalone_action", sa),
                                  ("joint_action", ja)):
            if basis is None:
                continue
            d: Dict[str, float] = {}
            for metric in ("var", "es", "scr"):
                a, b = basis.get(metric), w0.get(metric)
                if a is not None and b is not None:
                    d[metric + "_delta"] = float(a - b)
                    d[metric + "_delta_pct"] = float((a - b) / abs(b))
            row[basis_name + "_minus_without"] = d
        if sa is not None and ja is not None and sa.get("scr") is not None \
                and ja.get("scr") is not None:
            row["joint_minus_standalone_scr"] = float(ja["scr"] - sa["scr"])
            row["joint_minus_standalone_scr_pct"] = float(
                (ja["scr"] - sa["scr"]) / abs(sa["scr"]))
        matrix[lv] = row
    return matrix


def diagnostics_digest(payload: Dict[str, object]) -> str:
    """Deterministic SHA-256 digest of a diagnostics payload."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=float).encode("utf-8")
    ).hexdigest()
