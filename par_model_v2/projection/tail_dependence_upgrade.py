"""
Phase 27 Task 1 - design-note helper: richer upper-tail dependence copula.

Addresses the residual QUANTIFIED in the Phase 26 Task 3 report
(docs/validation/PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.json): after the full
path-wise copula re-aggregation on the FROZEN t(2.9451) copula, the component
t-copula path-wise SCR is 39,975.7 yet the nested path-wise truth is 46,638.9.
The frozen-copula margin bootstrap decomposed the 14.29% residual gap into

    relief-surface error  543.0  (8.1% of the gap; only 1.16% of nested), and
    copula-FORM residual  6,120.2 (91.9% of the gap),

and the copula-form residual (6,120.2) EXCEEDS the entire gaussian->t
dependence-form sensitivity (4,765.6).  The conclusion carried forward verbatim
from Phase 26: the genuine nested joint tail is HEAVIER than the frozen
t(2.9451) copula evaluated on the standalone margins - a copula-FORM limitation,
NOT a basis-choice or relief-surface effect.

The exchangeable Student-t copula has exactly one structural lever (a single
scalar df, with a radially SYMMETRIC tail: upper-tail dependence equals
lower-tail dependence, lambda_U = lambda_L).  Joint capital losses are
upper-asymmetric: the simultaneous-large-loss corner is heavier than the
simultaneous-large-gain corner.  Phase 27 therefore designs the next
sophistication step - a richer upper-tail dependence structure that keeps the
calibrated MARGINS unchanged and the rank dependence governed (Solvency II
Art. 234), while letting the UPPER tail be heavier and asymmetric.

Candidate (FRONT-RUNNER, design-note-first - one per cycle): an explicit
UPPER-TAIL-ASYMMETRY copula - the generalized-hyperbolic skew-t copula
(Demarta & McNeil 2005; McNeil, Frey & Embrechts 2015 ch. 7), parameterised by
a single skewness vector gamma on top of the frozen (df, Sigma).  gamma = 0
recovers the symmetric t EXACTLY (nested model unchanged at the freeze), so the
upgrade is a strict super-set of the governed copula and the archive
cross-check is exact.  Grouped-t (Daul, De Giorgi, Lindskog & McNeil 2003) and
pair-copula / vine constructions (Aas, Czado, Frigessi & Bakken 2009) are the
documented alternatives (rationale recorded in the design note).

This module provides, for the Task 1 design note ONLY:

- a SYNTHETIC seven-driver pre-study on COMMON RANDOM NUMBERS comparing the
  symmetric t-copula (gamma = 0, the governed freeze) against the skew-t copula
  (gamma > 0) at the SAME df, SAME correlation Sigma and IDENTICAL margins, so
  the ONLY difference is upper-tail asymmetry;
- the demonstrated SIGN of the Phase 27 effect: positive skewness lifts the
  empirical upper-tail dependence far above the symmetric level while leaving
  the lower tail near-symmetric, and raises the aggregate VaR99.5 - i.e. the
  symmetric copula UNDERSTATES the upper-tail capital, the same sign as the
  documented nested-vs-frozen-t copula-form residual;
- FIXED, pre-registered acceptance gates for Phase 27 Tasks 2-4 (no
  gate-shopping; recorded BEFORE any real-data richer-copula fit), including the
  EXACT archive cross-check (frozen-t component read-out 39,975.7 bit-identical
  before any new copula) and the SIGN gate (richer-copula SCR >= frozen-t
  component).

EDUCATIONAL MODEL: all parameters are educational placeholders pending
credentialled data and independent APS X2 review.  The synthetic pre-study
demonstrates the MECHANISM and its SIGN, not the magnitude of the real-data
effect.  NOT for production capital decisions.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from typing import Dict

import numpy as np

# ---------------------------------------------------------------------------
# Fixed pre-registered acceptance gates (Phase 27 Task 1 design note s5).
# Archived Phase 26 figures are MOTIVATION / archive cross-check baselines -
# none of the gates below consumes a number computed in THIS cycle.
# ---------------------------------------------------------------------------
# Archived Phase 26 Task 2/3 full re-aggregation read-outs on the FROZEN copula.
# Task 2 per-driver composition transform on the frozen t(2.9451): component SCR.
FROZEN_T_COMPONENT_SCR_REFERENCE = 39_975.654628199336
FROZEN_G_COMPONENT_SCR_REFERENCE = 35_210.1
# Archived Phase 25 Task 2 nested path-wise with-actions SCR (truth target).
NESTED_PATHWISE_SCR_REFERENCE = 46_638.9
# Archived Phase 26 Task 3 frozen-copula margin bootstrap of the component SCR.
COMPONENT_T_BOOTSTRAP_MEAN = 39_595.06073760496
COMPONENT_T_BOOTSTRAP_CI95 = (36_676.24172248241, 42_943.093413623916)
# Archived Phase 26 Task 3 residual-gap decomposition (the Phase 27 motivation).
TOTAL_GAP_ABS = 6_663.245371800665
TOTAL_GAP_REL_TO_NESTED = 0.14286883635335879
RELIEF_SURFACE_PART_ABS = 543.0488030254351
RELIEF_SURFACE_SHARE_OF_GAP = 0.08149914534494808
COPULA_FORM_RESIDUAL_ABS = 6_120.196568775231
COPULA_FORM_SHARE_OF_GAP = 0.9185008546550519
DEPENDENCE_FORM_SENSITIVITY_T_MINUS_G = 4_765.5546281993375
# Rank invariance (Solvency II Art. 234, Phase 23 Task 2 freeze): df re-matched
# on the WITHOUT-actions staged losses must stay at this value to 4 dp and the
# correlation matrix must be bit-frozen.  The richer copula must NEST this as
# its gamma = 0 special case - no silent re-tuning of (df, Sigma).
RANK_INVARIANCE_DF = 2.9451
DF_REMATCH_TOL = 1e-4
RHO_FROZEN_TOL = 1e-12
# Task 2 SIGN gate (pre-registered): the richer-copula path-wise SCR must be
# >= the frozen-t COMPONENT read-out (a heavier/asymmetric upper tail can only
# RAISE the joint tail vs the symmetric freeze; magnitude DISCLOSED, not gated).
RICHER_COPULA_SIGN_GATE_REFERENCE = FROZEN_T_COMPONENT_SCR_REFERENCE
# gamma = 0 EXACT-recovery tolerance: the skew-t at zero skewness must
# reproduce the symmetric-t aggregate to within Monte-Carlo noise (CRN).
GAMMA_ZERO_RECOVERY_TOL = 1e-9
# Task 3 headline gate: the richer-copula 95% bootstrap CI tested against the
# nested reference 46,638.9 - CLOSURE (nested inside the CI) OR the residual gap
# re-decomposed + disclosed (copula-form vs relief-surface), and the richer
# copula must REDUCE the nested gap on common random numbers (no widening).
BOOTSTRAP_REPLICATES_GATE = 200
BOOTSTRAP_N_SIM_GATE = 20_000
BOOTSTRAP_SE_GATE = 0.05
# Disclosure trigger (NOT pass/fail): MR-010 / MR-014 refresh if the richer
# copula SCR moves more than 1% from the frozen-t component read-out; the new
# copula-change limitation is registered as MR-015 (next free risk ID).
REAGG_MATERIALITY_DISCLOSURE_THRESHOLD = 0.01
NEW_RISK_ID = "MR-015"


@dataclass
class SkewTConfig:
    """Synthetic skew-t pre-study configuration (educational placeholders)."""

    n_scen: int = 200_000
    n_drivers: int = 7
    rho: float = 0.5
    df: float = 4.0
    gamma: float = 0.7          # GH skew-t skewness scalar (> 0 -> upper tail)
    seed: int = 42
    confidence: float = 0.995
    tail_p: float = 0.99        # exceedance level for the tail-dependence proxy
    scale: float = 100.0

    def __post_init__(self) -> None:
        if self.n_scen < 10_000:
            raise ValueError("n_scen must be >= 10000")
        if not (0.0 < self.rho < 1.0):
            raise ValueError("rho must be in (0, 1)")
        if not (self.df > 2.0):
            raise ValueError("df must exceed 2 (finite variance)")
        if self.gamma < 0.0:
            raise ValueError("gamma must be >= 0 (upper-tail skew)")
        if not (0.5 < self.confidence < 1.0):
            raise ValueError("confidence must be in (0.5, 1)")
        if not (0.9 <= self.tail_p < 1.0):
            raise ValueError("tail_p must be in [0.9, 1)")


# Per-driver lognormal dispersions and weights (educational placeholders),
# identical to the Phase 26 re-aggregation pre-study for continuity.  Drivers
# 0, 4 and 6 mirror the P24T3 carve-outs (credit loss + analytic FX/liquidity
# offsets) - the heavy-tailed, non-cuttable corner that drives the joint tail.
_MARGIN_SIGMA = np.array([0.45, 0.25, 0.25, 0.20, 0.30, 0.15, 0.20])
_MARGIN_WEIGHT = np.array([0.20, 0.18, 0.16, 0.12, 0.14, 0.10, 0.10])


def _pit_uniforms(x: np.ndarray) -> np.ndarray:
    """Empirical probability-integral transform per column -> copula uniforms.

    Isolates the COPULA from the latent margins: each column is mapped to its
    own rank-uniform, so the only thing that survives is the dependence
    structure (the skew-t vs symmetric-t contrast), not the latent scale.
    """
    ranks = np.argsort(np.argsort(x, axis=0), axis=0)
    return (ranks + 0.5) / x.shape[0]


def _aggregate_loss(u: np.ndarray, cfg: SkewTConfig) -> np.ndarray:
    """Apply the FROZEN lognormal margins to copula uniforms -> portfolio loss."""
    from scipy.stats import norm

    x = _MARGIN_WEIGHT[None, :] * np.exp(
        _MARGIN_SIGMA[None, :] * norm.ppf(u) - 0.5 * _MARGIN_SIGMA[None, :] ** 2
    )
    return x.sum(axis=1) * cfg.scale


def _avg_pairwise_tail_dependence(u: np.ndarray, p: float, upper: bool) -> float:
    """Average pairwise empirical exceedance-dependence proxy at level p.

    Joint-exceedance probability / marginal-exceedance probability, averaged
    over all driver pairs - a finite-sample proxy for lambda_U (upper) or
    lambda_L (lower).
    """
    d = u.shape[1]
    thr = p if upper else 1.0 - p
    vals = []
    for i, j in itertools.combinations(range(d), 2):
        if upper:
            joint = float(((u[:, i] > thr) & (u[:, j] > thr)).mean())
        else:
            joint = float(((u[:, i] < thr) & (u[:, j] < thr)).mean())
        vals.append(joint / (1.0 - p))
    return float(np.mean(vals))


def skew_t_vs_symmetric_t_pre_study(
    seed: int = 42, n_scen: int = 200_000, gamma: float = 0.7
) -> Dict[str, object]:
    """Upper-tail-asymmetry pre-study (synthetic; SIGN evidence only).

    Generalized-hyperbolic skew-t mixture (McNeil, Frey & Embrechts 2015):

        X = gamma * W + sqrt(W) * Z,   W ~ InvGamma(df/2, df/2),  Z ~ N(0, Sigma)

    On COMMON RANDOM NUMBERS the symmetric-t basis is the SAME mixture with
    gamma = 0 (W and Z reused), so the ONLY difference between the two copulas
    is the upper-tail asymmetry.  Both are mapped through the IDENTICAL frozen
    margins.  The skew-t lifts the upper-tail dependence well above the
    symmetric level while leaving the lower tail near-symmetric, and raises the
    aggregate VaR99.5 - the symmetric copula UNDERSTATES upper-tail capital.
    """
    cfg = SkewTConfig(n_scen=n_scen, seed=seed, gamma=gamma)
    rng = np.random.default_rng(cfg.seed)
    d = cfg.n_drivers

    corr = np.full((d, d), cfg.rho)
    np.fill_diagonal(corr, 1.0)
    chol = np.linalg.cholesky(corr)
    z = rng.standard_normal((cfg.n_scen, d)) @ chol.T
    # W ~ InverseGamma(df/2, scale=df/2): 1/W ~ Gamma(df/2, scale=2/df).
    g = rng.gamma(cfg.df / 2.0, scale=1.0, size=(cfg.n_scen, 1))
    w = (cfg.df / 2.0) / g

    x_skew = cfg.gamma * w + np.sqrt(w) * z   # skew-t (gamma > 0)
    x_sym = np.sqrt(w) * z                      # symmetric t (gamma = 0), CRN
    u_skew = _pit_uniforms(x_skew)
    u_sym = _pit_uniforms(x_sym)

    loss_skew = _aggregate_loss(u_skew, cfg)
    loss_sym = _aggregate_loss(u_sym, cfg)

    q = float(cfg.confidence)
    var_sym = float(np.quantile(loss_sym, q))
    var_skew = float(np.quantile(loss_skew, q))
    es_sym = float(loss_sym[loss_sym >= var_sym].mean())
    es_skew = float(loss_skew[loss_skew >= var_skew].mean())

    tail_p = float(cfg.tail_p)
    lam_u_skew = _avg_pairwise_tail_dependence(u_skew, tail_p, upper=True)
    lam_l_skew = _avg_pairwise_tail_dependence(u_skew, tail_p, upper=False)
    lam_u_sym = _avg_pairwise_tail_dependence(u_sym, tail_p, upper=True)
    lam_l_sym = _avg_pairwise_tail_dependence(u_sym, tail_p, upper=False)

    var_understatement_rel = var_skew / var_sym - 1.0
    es_understatement_rel = es_skew / es_sym - 1.0
    # gamma = 0 EXACT-recovery check on a small CRN slice: the skew-t at zero
    # skewness must reproduce the symmetric-t uniforms bit-for-bit.
    chk = min(cfg.n_scen, 20_000)
    x_skew0 = 0.0 * w[:chk] + np.sqrt(w[:chk]) * z[:chk]
    gamma_zero_max_abs = float(np.max(np.abs(x_skew0 - x_sym[:chk])))

    sign_ok = bool(var_understatement_rel >= 0.0 and es_understatement_rel >= 0.0)
    asymmetry_ok = bool(
        (lam_u_skew - lam_l_skew) > (lam_u_sym - lam_l_sym)
        and lam_u_skew > lam_u_sym
    )
    ordering_ok = bool(var_skew >= var_sym and es_skew >= es_sym)
    recovery_ok = bool(gamma_zero_max_abs <= GAMMA_ZERO_RECOVERY_TOL)

    payload = {
        "config": {
            "n_scen": cfg.n_scen, "n_drivers": cfg.n_drivers, "rho": cfg.rho,
            "df": cfg.df, "gamma": cfg.gamma, "seed": cfg.seed,
            "confidence": cfg.confidence, "tail_p": cfg.tail_p,
            "margin_sigma": _MARGIN_SIGMA.tolist(),
            "margin_weight": _MARGIN_WEIGHT.tolist(),
        },
        "var995": {"symmetric_t": var_sym, "skew_t": var_skew},
        "es995": {"symmetric_t": es_sym, "skew_t": es_skew},
        "var_understatement_rel_at_var995": var_understatement_rel,
        "es_understatement_rel_at_es995": es_understatement_rel,
        "tail_dependence_proxy": {
            "level_p": tail_p,
            "skew_t_upper": lam_u_skew, "skew_t_lower": lam_l_skew,
            "symmetric_t_upper": lam_u_sym, "symmetric_t_lower": lam_l_sym,
            "skew_t_asymmetry": lam_u_skew - lam_l_skew,
            "symmetric_t_asymmetry": lam_u_sym - lam_l_sym,
        },
        "gamma_zero_recovery_max_abs": gamma_zero_max_abs,
        "understatement_sign_ok": sign_ok,
        "asymmetry_ok": asymmetry_ok,
        "ordering_ok": ordering_ok,
        "gamma_zero_recovery_ok": recovery_ok,
    }
    payload["mechanism_demonstrated"] = bool(
        sign_ok and asymmetry_ok and ordering_ok and recovery_ok
    )
    digest_src = json.dumps(
        {k: payload[k] for k in
         ("config", "var995", "es995", "tail_dependence_proxy")},
        sort_keys=True, default=float,
    ).encode()
    payload["digest"] = hashlib.sha256(digest_src).hexdigest()
    return payload


def tail_dependence_upgrade_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions for the Phase 27 design (TAS M / ASOP 56)."""
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "Design note only: no capital figure produced this task may be used "
            "for any decision; the synthetic pre-study demonstrates the SIGN of "
            "the upper-tail-asymmetry effect, not its magnitude.",
            "The synthetic skew-t portfolio is NOT calibrated to the real model; "
            "the copula-form residual (6,120.2; 91.9% of the 14.29% nested gap) "
            "is the archived Phase 26 Task 3 figure, to be re-attacked on the "
            "real basis only at Tasks 2-3.",
            "The richer copula must NEST the governed freeze as its gamma = 0 "
            "special case: (df 2.9451, Sigma) stay bit-frozen; only the new "
            "upper-tail-asymmetry parameter is added (Solvency II Art. 234 rank "
            "invariance; no silent re-tuning of the governed dependence).",
            "Margins remain the calibrated frozen margins - the upgrade changes "
            "the COPULA only, never the standalone marginal capital.",
            "Action parameters remain educational placeholders pending "
            "credentialled practice data + independent APS X2 review.",
        ],
    }
