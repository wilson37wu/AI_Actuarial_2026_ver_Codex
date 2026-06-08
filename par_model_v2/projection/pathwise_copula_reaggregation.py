"""
Phase 26 Task 1 - design-note helper: full path-wise copula re-aggregation.

Addresses the residual QUANTIFIED in the Phase 25 Task 4 report
(docs/validation/PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.json): the
t/gaussian path-wise capital read-outs are an ANALYTIC RE-ANCHORING - the
governed smoothed-relief surface (sigma 0.225, alpha 0.7567) plus ONE
constant FIT-sample benefit share (beta_fit 0.8450) applied to the anchored
joint TOTAL liability level per copula scenario.  The frozen-copula margin
bootstrap showed the nested path-wise reference 46,638.9 sits OUTSIDE the
re-anchoring 95% CI [35,793, 42,496]: the re-anchoring understates nested by
14.7% BEYOND margin noise.  Phase 26 designs the refinement in which the
relief is applied to the per-driver COMPOSITION of each joint scenario
(full path-wise copula re-aggregation) instead of once to its total level.

This module provides, for the Task 1 design note ONLY:

- a SYNTHETIC seven-driver t-copula portfolio with carve-out (non-cuttable)
  drivers, so that NO real archived nested benchmark is consumed before the
  Task 2 gates;
- two with-actions read-outs on common random numbers: ``level`` (the
  Phase 25 Task 4 convention - relief from the aggregate level with a
  CONSTANT mean cuttable share) and ``component`` (relief applied to the
  per-scenario cuttable composition - the full re-aggregation analogue);
- the composition-heterogeneity pre-study: the tail of the joint loss is
  disproportionately driven by the heavy-tailed NON-cuttable (carve-out)
  drivers, so the constant-share level transform OVERSTATES the relief
  available in the tail and UNDERSTATES the with-actions capital - the
  pre-registered SIGN of the Phase 26 effect;
- FIXED pre-registered acceptance gates for Phase 26 Tasks 2-4 (no
  gate-shopping; recorded BEFORE any real-data full re-aggregation).

EDUCATIONAL MODEL: all parameters are educational placeholders pending
credentialled data and independent APS X2 review.  NOT for production
capital decisions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict

import numpy as np

from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.pathwise_proxy_basis import smoothed_relief_response

# ---------------------------------------------------------------------------
# Fixed pre-registered acceptance gates (Phase 26 Task 1 design note s5).
# Archived Phase 25 figures are MOTIVATION/comparison baselines - none of the
# gates below consumes a number computed in THIS cycle.
# ---------------------------------------------------------------------------
# Archived Phase 25 Task 2 nested path-wise with-actions SCR (truth target).
NESTED_PATHWISE_SCR_REFERENCE = 46_638.9
# Archived Phase 25 Task 4 analytic re-anchoring read-outs (to be superseded).
T_COPULA_REANCHORED_READOUT = 39_794.3
GAUSSIAN_REANCHORED_READOUT = 35_210.1
# Archived Phase 25 Task 4 frozen-copula margin bootstrap 95% CI of the
# re-anchored t-copula SCR (200 x 20k): nested reference sits OUTSIDE it.
REANCHORING_BOOTSTRAP_CI95 = (35_793.0, 42_496.0)
REANCHORING_UNDERSTATEMENT_REL = 0.147  # nested vs re-anchored, beyond noise
# Rank invariance (Solvency II Art. 234, Phase 23 Task 2 freeze): df re-matched
# on the WITHOUT-actions staged losses must stay at this value to 4 dp and the
# correlation matrix must be bit-frozen - no silent re-tuning on the new basis.
RANK_INVARIANCE_DF = 2.9451
DF_REMATCH_TOL = 1e-4
RHO_FROZEN_TOL = 1e-12
# Task 2 sign gate: the FULL re-aggregated t-copula path-wise SCR must be >=
# the analytic re-anchored read-out (heterogeneity can only reduce tail relief
# vs the constant-share level transform; magnitude DISCLOSED, not gated).
FULL_REAGG_SIGN_GATE_REFERENCE = T_COPULA_REANCHORED_READOUT
# Task 3 headline gate: nested path-wise reference INSIDE the full
# re-aggregation 95% bootstrap CI (closure of the beyond-noise understatement)
# OR the residual gap decomposed + disclosed (copula-form vs relief-surface).
BOOTSTRAP_REPLICATES_GATE = 200
BOOTSTRAP_N_SIM_GATE = 20_000
BOOTSTRAP_SE_GATE = 0.05
# Disclosure trigger (NOT pass/fail): MR-010/MR-014 refresh if the full
# re-aggregated SCR moves more than 1% from the re-anchored read-out.
REAGG_MATERIALITY_DISCLOSURE_THRESHOLD = 0.01


@dataclass
class SyntheticReaggConfig:
    """Synthetic pre-study configuration (educational placeholders)."""

    n_scen: int = 200_000
    n_drivers: int = 7
    rho: float = 0.5
    df: float = 3.0
    seed: int = 42
    confidence: float = 0.995
    relief_sigma: float = 0.225   # governed P25T3 surface dispersion
    relief_alpha: float = 0.757   # governed P25T3 level factor
    scale: float = 100.0

    def __post_init__(self) -> None:
        if self.n_scen < 10_000:
            raise ValueError("n_scen must be >= 10000")
        if not (0.0 < self.rho < 1.0):
            raise ValueError("rho must be in (0, 1)")
        if not (self.df > 2.0):
            raise ValueError("df must exceed 2 (finite variance)")
        if not (0.5 < self.confidence < 1.0):
            raise ValueError("confidence must be in (0.5, 1)")


# Per-driver lognormal dispersions and weights (educational placeholders).
# Driver 0 is the credit-like heavy-tail driver; drivers 0, 4 and 6 mirror
# the P24T3 carve-outs (credit loss + analytic FX/liquidity offsets): they
# are NOT cuttable by the governed bonus rule.
_MARGIN_SIGMA = np.array([0.45, 0.25, 0.25, 0.20, 0.30, 0.15, 0.20])
_MARGIN_WEIGHT = np.array([0.20, 0.18, 0.16, 0.12, 0.14, 0.10, 0.10])
_CUTTABLE_MASK = np.array([0.0, 1.0, 1.0, 1.0, 0.0, 1.0, 0.0])


def _t_copula_uniforms(rng: np.random.Generator, cfg: SyntheticReaggConfig) -> np.ndarray:
    """Equicorrelated t-copula uniforms via the normal/chi-square mixture."""
    from scipy.stats import t as tdist

    d = cfg.n_drivers
    corr = np.full((d, d), cfg.rho)
    np.fill_diagonal(corr, 1.0)
    chol = np.linalg.cholesky(corr)
    z = rng.standard_normal((cfg.n_scen, d)) @ chol.T
    w = rng.chisquare(cfg.df, size=(cfg.n_scen, 1))
    return np.asarray(tdist.cdf(z * np.sqrt(cfg.df / w), cfg.df))


def synthetic_level_vs_component_pre_study(
    seed: int = 42, n_scen: int = 200_000
) -> Dict[str, object]:
    """Composition-heterogeneity pre-study (synthetic; sign evidence only).

    Common random numbers; the ONLY difference between the two with-actions
    bases is whether the relief sees the per-scenario cuttable composition
    (``component``) or a constant mean cuttable share applied to the total
    level (``level`` - the Phase 25 Task 4 analytic re-anchoring convention).
    """
    from scipy.stats import norm

    cfg = SyntheticReaggConfig(n_scen=n_scen, seed=seed)
    rng = np.random.default_rng(cfg.seed)
    u = _t_copula_uniforms(rng, cfg)
    x = _MARGIN_WEIGHT[None, :] * np.exp(
        _MARGIN_SIGMA[None, :] * norm.ppf(u) - 0.5 * _MARGIN_SIGMA[None, :] ** 2
    )
    v = x.sum(axis=1) * cfg.scale                       # joint total loss level
    cuttable = (x * _CUTTABLE_MASK[None, :]).sum(axis=1) * cfg.scale

    rule = ManagementActionRule()
    a_ref = rule.reference_coverage * float(v.mean())
    frac = cfg.relief_alpha * smoothed_relief_response(
        rule, rule.coverage_ratio(v, a_ref), cfg.relief_sigma
    )
    beta_mean = float((cuttable / v).mean())
    mr = rule.max_relief

    relieved_level = np.minimum(frac * beta_mean * v, mr * beta_mean * v)
    relieved_component = np.minimum(frac * cuttable, mr * cuttable)
    w_level = v - relieved_level
    w_component = v - relieved_component

    q = float(cfg.confidence)
    var_without = float(np.quantile(v, q))
    var_level = float(np.quantile(w_level, q))
    var_component = float(np.quantile(w_component, q))
    tail = v >= var_without
    beta_tail = float((cuttable / v)[tail].mean())

    understatement_rel = var_component / var_level - 1.0
    sign_ok = bool(understatement_rel >= 0.0)
    ordering_ok = bool(var_without >= var_component >= var_level)
    bounds_ok = bool(
        np.all(relieved_component >= -1e-12)
        and np.all(relieved_component <= mr * cuttable + 1e-9)
        and np.all(relieved_level <= mr * beta_mean * v + 1e-9)
    )
    payload = {
        "config": {
            "n_scen": cfg.n_scen, "n_drivers": cfg.n_drivers, "rho": cfg.rho,
            "df": cfg.df, "seed": cfg.seed, "confidence": cfg.confidence,
            "relief_sigma": cfg.relief_sigma, "relief_alpha": cfg.relief_alpha,
            "cuttable_mask": _CUTTABLE_MASK.tolist(),
            "margin_sigma": _MARGIN_SIGMA.tolist(),
            "margin_weight": _MARGIN_WEIGHT.tolist(),
        },
        "var995": {
            "without": var_without,
            "level": var_level,
            "component": var_component,
        },
        "level_understatement_rel_at_var995": understatement_rel,
        "beta_mean": beta_mean,
        "beta_tail_mean": beta_tail,
        "tail_cuttable_share_depression": beta_mean - beta_tail,
        "mean_relief_level": float(relieved_level.mean()),
        "mean_relief_component": float(relieved_component.mean()),
        "understatement_sign_ok": sign_ok,
        "ordering_ok": ordering_ok,
        "bounds_ok": bounds_ok,
    }
    payload["mechanism_demonstrated"] = bool(sign_ok and ordering_ok and bounds_ok)
    digest_src = json.dumps(
        {k: payload[k] for k in ("config", "var995", "beta_mean", "beta_tail_mean")},
        sort_keys=True, default=float,
    ).encode()
    payload["digest"] = hashlib.sha256(digest_src).hexdigest()
    return payload


def pathwise_reaggregation_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions for the Phase 26 design (TAS M / ASOP 56)."""
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "Design note only: no capital figure produced this task may be used "
            "for any decision; the synthetic pre-study demonstrates the SIGN of "
            "the composition-heterogeneity effect, not its magnitude.",
            "The synthetic portfolio is NOT calibrated to the real model; the "
            "14.7% beyond-noise understatement is the archived Phase 25 Task 4 "
            "figure, quantified only on the real basis at Task 2/3.",
            "Copula parameters are FROZEN (df 2.9451 tail-matched on the "
            "without-actions basis, Phase 23 Task 2); the full re-aggregation "
            "must NOT re-tune them (Solvency II Art. 234 rank invariance).",
            "Action parameters remain educational placeholders pending "
            "credentialled practice data + independent APS X2 review.",
        ],
    }
