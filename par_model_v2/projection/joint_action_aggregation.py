"""Joint-scenario (action-after-aggregation) copula re-aggregation (Phase 24 Task 1).

EDUCATIONAL ONLY -- not a regulatory capital model.

Motivation (Phase 23 Task 4 MATERIAL FINDING, disclosed)
--------------------------------------------------------
Phase 23 Task 4 aggregated standalone WITH-ACTIONS losses with the
tail-matched t(2.9451) copula and found the copula read-out understates the
nested with-actions benchmark by 22.5% (vs 4.0% without actions).  Root
cause: the governed management action SATURATES (max liability relief 12%)
in the JOINT tail where the total liability is largest, while each
standalone tail sits in the steeper partial-cut band -- so applying the rule
to the marginals before aggregation double-counts relief exactly where
capital is measured.

This module implements the Phase 24 design hypothesis: aggregate the
WITHOUT-actions dependence structure first, anchor the simulated JOINT
liability, and apply the governed ``ManagementActionRule`` ONCE to the joint
liability (action-after-aggregation):

    V_joint = L_fit + sum_k (Q_k(U_k) - mean_k_fit)        (anchored joint level)
    W_joint = rule.apply_to_liabilities(V_joint, A_ref)    (single joint action)

with Q_k the empirical margin of the without-actions standalone loss vector
of driver k, U a copula sample (t(df_matched) or Gaussian), and
L_fit / A_ref IDENTICAL (leakage-free) to the Phase 23 Task 3/4 convention.

FIXED pre-registered acceptance gates for Phase 24 (recorded in
PHASE24_TASK1_DESIGN_NOTE before any joint-action benchmark error vs the
nested with-actions reference is computed on REAL staged data -- no
gate-shopping; see design note s5):
  * Task 2: t(df_matched) JOINT-action SCR rel err vs nested-with-actions
    <= JOINT_REL_ERROR_GATE (10%), AND strictly below the disclosed
    Phase 23 Task 4 standalone-action rel err (22.5%); rank invariance
    (df re-matched on the without-actions losses unchanged at 2.9451).
  * Task 3: inner-path action prototype OOS R^2 >= 0.95 and VaR rel err
    <= 10% (Phase 22 gates), action monotonicity preserved.
  * Task 4: joint-vs-standalone and with-vs-without capital deltas
    disclosed at every level; var-covar understatement refreshed; MR-010 /
    MR-014 notes refreshed.

The synthetic pre-study below proves the MECHANISM on data with a known
ground truth (no real benchmark consumed): when the action saturates in the
joint tail, action-on-marginals understates true with-actions capital while
action-after-aggregation recovers it.

Standards: Solvency II Delegated Reg. Art. 23 (objective/verifiable
management actions, effect quantified) and Art. 234; SOA ASOP 56 s3.1.3/
s3.4/s3.5; SOA ASOP 25 s3.3; IA TAS M s3.2/s3.6; IFoA Life Aggregation &
Simulation WP.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.multi_driver_copula_aggregation import (
    _EmpiricalMargin,
    _nearest_correlation,
)
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    simulate_t_copula_uniforms,
)

__all__ = [
    "JOINT_REL_ERROR_GATE",
    "STANDALONE_ACTION_REL_ERROR_BASELINE",
    "INNER_PATH_OOS_R2_GATE",
    "INNER_PATH_VAR_REL_ERROR_GATE",
    "JointActionConfig",
    "JointActionResult",
    "JointActionAggregator",
    "simulate_gaussian_copula_uniforms",
    "synthetic_saturation_pre_study",
]

#: FIXED Phase 24 pre-registered gates (design note s5; set this cycle,
#: BEFORE the Task 2 real-data joint-action benchmark is computed).
JOINT_REL_ERROR_GATE = 0.10
#: Disclosed Phase 23 Task 4 standalone-action t-copula rel err (the figure
#: the joint basis must strictly beat).  Archived value, not a tunable.
STANDALONE_ACTION_REL_ERROR_BASELINE = 0.225
#: Task 3 (inner-path prototype) gates -- unchanged Phase 22 OOS gates.
INNER_PATH_OOS_R2_GATE = 0.95
INNER_PATH_VAR_REL_ERROR_GATE = 0.10


def simulate_gaussian_copula_uniforms(
    rng: np.random.Generator,
    n_sim: int,
    correlation: np.ndarray,
) -> np.ndarray:
    """Draw n_sim uniform vectors from a Gaussian copula(correlation)."""
    from scipy import stats

    R = np.asarray(correlation, dtype=float)
    chol = np.linalg.cholesky(R)
    Z = rng.standard_normal((int(n_sim), R.shape[0])) @ chol.T
    return stats.norm.cdf(Z)


@dataclass(frozen=True)
class JointActionConfig:
    """Configuration for one joint-action re-aggregation run."""

    n_sim: int = 200_000
    seed: int = 42
    df: Optional[float] = None          # None -> Gaussian copula
    confidence: float = 0.995

    def __post_init__(self) -> None:
        if self.n_sim < 1_000:
            raise ValueError("n_sim must be >= 1000 for a 99.5% tail read-out")
        if self.df is not None and not (self.df > 0.0):
            raise ValueError("df must be positive when provided")
        if not (0.5 < self.confidence < 1.0):
            raise ValueError("confidence must be in (0.5, 1)")

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_sim": self.n_sim,
            "seed": self.seed,
            "df": self.df,
            "copula": "gaussian" if self.df is None else f"t({self.df:g})",
            "confidence": self.confidence,
        }


@dataclass
class JointActionResult:
    """Capital read-outs of one joint-action re-aggregation run."""

    config: Dict[str, object]
    var_joint_with: float
    es_joint_with: float
    scr_joint_with: float
    mean_joint_with: float
    var_joint_without: float
    scr_joint_without: float
    active_share: float
    floor_share: float
    l_fit: float
    a_ref: float
    digest: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "config": self.config,
            "var_joint_with": self.var_joint_with,
            "es_joint_with": self.es_joint_with,
            "scr_joint_with": self.scr_joint_with,
            "mean_joint_with": self.mean_joint_with,
            "var_joint_without": self.var_joint_without,
            "scr_joint_without": self.scr_joint_without,
            "active_share": self.active_share,
            "floor_share": self.floor_share,
            "l_fit": self.l_fit,
            "a_ref": self.a_ref,
            "digest": self.digest,
        }


class JointActionAggregator:
    """Action-after-aggregation copula re-aggregation on anchored joint levels.

    Parameters
    ----------
    standalone_losses : mapping driver -> WITHOUT-actions standalone loss
        vector (the Phase 23 Task 2 staged primitives), all the same length.
    correlation : governed driver correlation matrix (repaired to the
        nearest valid correlation internally).
    rule : the governed ``ManagementActionRule`` (Phase 23 Task 3).
    l_fit : fit-sample mean liability (anchor level; leakage-free).
    anchor_means : mapping driver -> mean of the ORIGINAL staged loss vector
        (the Task 4 anchoring convention; defaults to the sample means of
        ``standalone_losses``).
    """

    def __init__(
        self,
        standalone_losses: Dict[str, np.ndarray],
        correlation: np.ndarray,
        rule: ManagementActionRule,
        l_fit: float,
        anchor_means: Optional[Dict[str, float]] = None,
    ) -> None:
        if not standalone_losses:
            raise ValueError("standalone_losses must be non-empty")
        self.drivers: List[str] = list(standalone_losses.keys())
        lengths = {np.asarray(v).size for v in standalone_losses.values()}
        if len(lengths) != 1:
            raise ValueError("all standalone loss vectors must share a length")
        self.losses = {
            k: np.asarray(v, dtype=float) for k, v in standalone_losses.items()
        }
        R = np.asarray(correlation, dtype=float)
        if R.shape != (len(self.drivers), len(self.drivers)):
            raise ValueError("correlation shape must match driver count")
        self.correlation = _nearest_correlation(R)
        self.rule = rule
        self.l_fit = float(l_fit)
        if not (self.l_fit > 0.0):
            raise ValueError("l_fit must be positive")
        self.anchor_means = {
            k: float(anchor_means[k]) if anchor_means else float(np.mean(self.losses[k]))
            for k in self.drivers
        }
        self.margins = {k: _EmpiricalMargin(self.losses[k]) for k in self.drivers}
        self.a_ref = rule.reference_assets(self.l_fit)

    # ------------------------------------------------------------------
    def joint_levels(self, U: np.ndarray) -> np.ndarray:
        """Anchored joint liability levels V = L_fit + sum_k (Q_k(u_k) - mean_k)."""
        if U.ndim != 2 or U.shape[1] != len(self.drivers):
            raise ValueError("U must be (n_sim, n_drivers)")
        V = np.full(U.shape[0], self.l_fit, dtype=float)
        for j, k in enumerate(self.drivers):
            V += self.margins[k].ppf(U[:, j]) - self.anchor_means[k]
        return V

    def run(self, config: Optional[JointActionConfig] = None) -> JointActionResult:
        cfg = config or JointActionConfig()
        rng = np.random.default_rng(cfg.seed)
        if cfg.df is None:
            U = simulate_gaussian_copula_uniforms(rng, cfg.n_sim, self.correlation)
        else:
            U = simulate_t_copula_uniforms(rng, cfg.n_sim, self.correlation, cfg.df)
        V = self.joint_levels(U)
        if np.any(V <= 0.0):
            raise ValueError(
                "non-positive anchored joint level encountered; "
                "anchoring convention violated"
            )
        W = self.rule.apply_to_liabilities(V, self.a_ref)
        cr = self.rule.coverage_ratio(V, self.a_ref)
        cut = self.rule.cut_factor(cr)
        active = float(np.mean(cut < 1.0))
        floored = float(np.mean(cut <= 0.0))
        m_with = capital_metrics_from_liabilities(W, cfg.confidence, 12)
        m_without = capital_metrics_from_liabilities(V, cfg.confidence, 12)
        digest_src = json.dumps(
            {
                "cfg": cfg.to_dict(),
                "drivers": self.drivers,
                "l_fit": self.l_fit,
                "a_ref": self.a_ref,
                "var_with": float(m_with.var_liability),
                "es_with": float(m_with.es_liability),
            },
            sort_keys=True,
        ).encode()
        return JointActionResult(
            config=cfg.to_dict(),
            var_joint_with=float(m_with.var_liability),
            es_joint_with=float(m_with.es_liability),
            scr_joint_with=float(m_with.scr_proxy),
            mean_joint_with=float(np.mean(W)),
            var_joint_without=float(m_without.var_liability),
            scr_joint_without=float(m_without.scr_proxy),
            active_share=active,
            floor_share=floored,
            l_fit=self.l_fit,
            a_ref=self.a_ref,
            digest=hashlib.sha256(digest_src).hexdigest()[:12],
        )


# ----------------------------------------------------------------------
def synthetic_saturation_pre_study(
    seed: int = 42,
    n_truth: int = 200_000,
    n_outer: int = 4_000,
    n_sim: int = 200_000,
    rho: float = 0.6,
    df_true: float = 4.0,
) -> Dict[str, object]:
    """Mechanism pre-study on SYNTHETIC data with a known ground truth.

    Two drivers with lognormal margins and a t(df_true) copula; the governed
    rule shape (trigger 1.10 / floor 0.90 / bonus 30% / PRE 60%) applied (a)
    to the TRUE joint liability (ground truth), (b) per-marginal then
    aggregated (the Phase 23 Task 4 standalone-action basis), and (c) by
    action-after-aggregation on the joint level (the Phase 24 design).

    No real model output or archived nested benchmark is consumed -- the
    pre-study demonstrates the saturation mechanism and that basis (c)
    recovers the truth while basis (b) understates it.
    """
    rng = np.random.default_rng(seed)
    rule = ManagementActionRule()
    l_fit = 100_000.0
    a_ref = rule.reference_assets(l_fit)
    R = np.array([[1.0, rho], [rho, 1.0]])

    # --- truth: large-sample joint components under the t-copula
    U_truth = simulate_t_copula_uniforms(rng, n_truth, R, df_true)
    from scipy import stats

    sig1, sig2 = 0.50, 0.60
    q1 = stats.lognorm.ppf(U_truth[:, 0], s=sig1, scale=15_000.0)
    q2 = stats.lognorm.ppf(U_truth[:, 1], s=sig2, scale=12_000.0)
    V_true = l_fit + (q1 - np.mean(q1)) + (q2 - np.mean(q2))
    W_true = rule.apply_to_liabilities(V_true, a_ref)
    m_true = capital_metrics_from_liabilities(W_true, 0.995, 12)

    # --- observed 'outer' sample (what the capital model would hold)
    idx = rng.choice(n_truth, size=n_outer, replace=False)
    comp = {"d1": q1[idx], "d2": q2[idx]}
    anchor = {k: float(np.mean(v)) for k, v in comp.items()}

    # (b) standalone-action basis: rule applied to each anchored marginal,
    #     then t-copula aggregation of the with-actions standalone losses.
    losses_with = {}
    for k, v in comp.items():
        v_anch = l_fit + (v - anchor[k])
        w = rule.apply_to_liabilities(v_anch, a_ref)
        losses_with[k] = w  # with-actions standalone level vector
    agg_b = JointActionAggregator(
        standalone_losses=losses_with,
        correlation=R,
        rule=rule,
        l_fit=l_fit,
    )
    # aggregate the WITH-actions marginals WITHOUT a second action:
    rng_b = np.random.default_rng(seed + 1)
    U_b = simulate_t_copula_uniforms(rng_b, n_sim, R, df_true)
    V_b = agg_b.joint_levels(U_b)
    m_b = capital_metrics_from_liabilities(V_b, 0.995, 12)

    # (c) joint-action basis: aggregate WITHOUT-actions marginals, apply the
    #     rule once to the joint level (this module's design).
    agg_c = JointActionAggregator(
        standalone_losses=comp,
        correlation=R,
        rule=rule,
        l_fit=l_fit,
        anchor_means=anchor,
    )
    res_c = agg_c.run(JointActionConfig(n_sim=n_sim, seed=seed + 1, df=df_true))

    def _rel(x: float, ref: float) -> float:
        return abs(x - ref) / abs(ref)

    out = {
        "seed": seed,
        "n_truth": n_truth,
        "n_outer": n_outer,
        "n_sim": n_sim,
        "rho": rho,
        "df_true": df_true,
        "truth_var995_with": float(m_true.var_liability),
        "standalone_action_var995": float(m_b.var_liability),
        "joint_action_var995": float(res_c.var_joint_with),
        "standalone_action_rel_err": _rel(float(m_b.var_liability), float(m_true.var_liability)),
        "joint_action_rel_err": _rel(float(res_c.var_joint_with), float(m_true.var_liability)),
        "truth_active_share": float(np.mean(rule.cut_factor(rule.coverage_ratio(V_true, a_ref)) < 1.0)),
        "joint_action_active_share": res_c.active_share,
        "digest": res_c.digest,
    }
    out["understatement_sign_ok"] = bool(
        out["standalone_action_var995"] <= out["truth_var995_with"] + 1e-9
    )
    out["joint_recovers_truth"] = bool(
        out["joint_action_rel_err"] < out["standalone_action_rel_err"]
    )
    return out


def joint_action_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions (IA TAS M s3.2; SOA ASOP 56 s3.5)."""
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "NOT for production or regulatory capital decisions.",
            "Joint anchoring V = L_fit + sum_k (Q_k - mean_k) is a first-order "
            "level approximation; cross-driver liability non-linearities beyond "
            "the action are not represented.",
            "Action parameters are educational placeholders pending credentialled "
            "management-practice data and independent APS X2 review.",
            "The copula consumes realised standalone losses; sampling noise at "
            "n_outer=160 propagates into the joint read-out (disclosed).",
        ],
        "standards": [
            "Solvency II Delegated Reg. Art. 23 / Art. 234",
            "SOA ASOP 56 s3.1.3/s3.4/s3.5",
            "IA TAS M s3.2/s3.6",
        ],
    }
