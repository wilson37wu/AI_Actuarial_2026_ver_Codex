"""Tail-dependence utilities for copula-based capital aggregation (Phase 23 Task 1).

EDUCATIONAL ONLY — design-note support module; not a regulatory capital model.

Motivation (MR-010 residual)
----------------------------
The Phase 18-22 copula aggregation selects its copula by AIC on pseudo-
observations.  Under AIC/MLE the Student-t degrees-of-freedom parameter is
repeatedly pinned at the top of the search grid, collapsing the t-copula
toward the Gaussian — which has ZERO asymptotic upper-tail dependence
(lambda_U = 0).  Joint capital losses, however, co-move strongly in the tail
(realised loss correlations +0.5..+0.8).  Phase 23 Task 2 will therefore
calibrate the t-copula df by **tail-dependence matching**: estimate the
empirical pairwise upper-tail-dependence coefficients of the realised
standalone capital-loss vectors and invert the closed-form t-copula
tail-dependence formula for the implied df.

Key formula (Demarta & McNeil 2005; McNeil, Frey & Embrechts 2015, ch. 7):

    lambda_U(nu, rho) = 2 * t_{nu+1}( -sqrt( (nu+1)(1-rho) / (1+rho) ) )

which is strictly decreasing in nu (for fixed rho < 1) and strictly
increasing in rho, so the inversion for nu is well-posed by bisection.

Standard references: SOA ASOP 56 §3.5; SOA ASOP 25 §3.3; IA TAS M §3.6;
Solvency II Delegated Reg. Art. 234 (empirically justified diversification);
IFoA Life Aggregation & Simulation working party; Demarta-McNeil 2005;
Schmidt & Stadtmueller 2006 (non-parametric tail-dependence estimation).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from scipy import stats

__all__ = [
    "t_copula_upper_tail_dependence",
    "implied_t_df_from_tail_dependence",
    "empirical_upper_tail_dependence",
    "pairwise_upper_tail_dependence",
    "TailDependenceMatch",
    "match_t_df_to_losses",
]

#: Df search interval for the bisection inversion.  The upper cap mirrors the
#: existing copula-aggregation t_df_grid ceiling; hitting it is DISCLOSED.
DF_LO_DEFAULT = 1.0
DF_HI_DEFAULT = 200.0


def t_copula_upper_tail_dependence(df: float, rho: float) -> float:
    """Closed-form upper-tail dependence lambda_U of a bivariate t-copula.

    lambda_U = 2 * t_{df+1}(-sqrt((df+1)(1-rho)/(1+rho))).
    For rho -> 1 this tends to 1; for df -> inf it tends to 0 (Gaussian limit).
    """
    if df <= 0.0:
        raise ValueError(f"df must be positive, got {df}")
    if not -1.0 < rho <= 1.0:
        raise ValueError(f"rho must be in (-1, 1], got {rho}")
    if rho == 1.0:
        return 1.0
    arg = -np.sqrt((df + 1.0) * (1.0 - rho) / (1.0 + rho))
    return float(2.0 * stats.t.cdf(arg, df + 1.0))


def implied_t_df_from_tail_dependence(
    lambda_u: float,
    rho: float,
    df_lo: float = DF_LO_DEFAULT,
    df_hi: float = DF_HI_DEFAULT,
    tol: float = 1e-10,
    max_iter: int = 200,
) -> tuple[float, bool]:
    """Invert lambda_U(nu, rho) for nu by bisection.

    Returns ``(df, capped)``.  ``capped`` is True when the requested lambda_u
    lies outside the attainable range on [df_lo, df_hi] and the bound was
    returned instead (a disclosure flag, mirroring the lambda clamp of the
    liquidity calibrator).  lambda_U is strictly decreasing in df, so:
      lambda_u >= lambda_U(df_lo) -> (df_lo, True)   [more tail dep than df_lo allows]
      lambda_u <= lambda_U(df_hi) -> (df_hi, True)   [Gaussian-like; df pinned at cap]
    """
    if not 0.0 <= lambda_u <= 1.0:
        raise ValueError(f"lambda_u must be in [0, 1], got {lambda_u}")
    lam_lo_df = t_copula_upper_tail_dependence(df_lo, rho)   # largest lambda
    lam_hi_df = t_copula_upper_tail_dependence(df_hi, rho)   # smallest lambda
    if lambda_u >= lam_lo_df:
        return float(df_lo), True
    if lambda_u <= lam_hi_df:
        return float(df_hi), True
    lo, hi = df_lo, df_hi
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        # lambda_U is strictly decreasing in df: bisect on the df interval.
        # (A lambda-based exit is unsafe - the surface is nearly flat in df
        # for large df / negative rho, which would stop the search early.)
        if t_copula_upper_tail_dependence(mid, rho) > lambda_u:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol * max(1.0, mid):
            break
    return float(0.5 * (lo + hi)), False


def empirical_upper_tail_dependence(
    u: np.ndarray,
    v: np.ndarray,
    threshold: float = 0.95,
) -> float:
    """Non-parametric threshold estimator of lambda_U on pseudo-observations.

    lambda_hat_U(q) = P(U > q, V > q) / (1 - q)   (Schmidt-Stadtmueller-style
    empirical tail copula at finite threshold q; consistent as q -> 1 with
    n(1-q) -> inf).  Inputs must already be uniform pseudo-observations
    (ranks / (n+1)).  Sampling-noisy by construction — callers should report
    the threshold and sample size alongside the estimate.
    """
    u = np.asarray(u, dtype=float)
    v = np.asarray(v, dtype=float)
    if u.shape != v.shape or u.ndim != 1:
        raise ValueError("u and v must be 1-D arrays of equal length")
    if not 0.5 < threshold < 1.0:
        raise ValueError(f"threshold must be in (0.5, 1), got {threshold}")
    joint = np.mean((u > threshold) & (v > threshold))
    return float(joint / (1.0 - threshold))


def pairwise_upper_tail_dependence(
    pseudo_obs: np.ndarray,
    threshold: float = 0.95,
) -> np.ndarray:
    """Symmetric d x d matrix of empirical lambda_U over all driver pairs."""
    U = np.asarray(pseudo_obs, dtype=float)
    if U.ndim != 2:
        raise ValueError("pseudo_obs must be 2-D (n_obs, n_drivers)")
    d = U.shape[1]
    lam = np.eye(d)
    for i in range(d):
        for j in range(i + 1, d):
            val = empirical_upper_tail_dependence(U[:, i], U[:, j], threshold)
            lam[i, j] = lam[j, i] = val
    return lam


@dataclass
class TailDependenceMatch:
    """Result of matching a single pooled t-copula df to realised losses."""

    threshold: float
    n_obs: int
    lambda_matrix: list = field(default_factory=list)
    rho_matrix: list = field(default_factory=list)
    pairwise_df: list = field(default_factory=list)      # (i, j, df, capped)
    pooled_df: float = float("nan")                       # median of pair dfs
    pooled_df_capped_share: float = 0.0                   # share of pairs at a bound
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "threshold": self.threshold,
            "n_obs": self.n_obs,
            "lambda_matrix": self.lambda_matrix,
            "rho_matrix": self.rho_matrix,
            "pairwise_df": [
                {"i": i, "j": j, "df": df, "capped": capped}
                for (i, j, df, capped) in self.pairwise_df
            ],
            "pooled_df": self.pooled_df,
            "pooled_df_capped_share": self.pooled_df_capped_share,
            "note": self.note,
        }


def match_t_df_to_losses(
    losses: np.ndarray,
    threshold: float = 0.95,
    df_lo: float = DF_LO_DEFAULT,
    df_hi: float = DF_HI_DEFAULT,
) -> TailDependenceMatch:
    """Tail-dependence-matched pooled t-copula df from realised loss vectors.

    Steps: rank-transform losses to pseudo-observations; estimate the
    empirical pairwise lambda_U at ``threshold``; take Kendall-tau-implied
    elliptical correlations rho = sin(pi/2 * tau) (robust to marginals);
    invert lambda_U(nu, rho) per pair; pool by the MEDIAN pair df (robust to
    the noisiest pairs).  Pairs whose inversion hits a bound are flagged and
    counted in ``pooled_df_capped_share`` (disclosure, not silent clamping).
    """
    L = np.asarray(losses, dtype=float)
    if L.ndim != 2 or L.shape[1] < 2:
        raise ValueError("losses must be 2-D (n_obs, n_drivers>=2)")
    n, d = L.shape
    ranks = np.empty_like(L)
    for k in range(d):
        ranks[:, k] = stats.rankdata(L[:, k]) / (n + 1.0)
    lam = pairwise_upper_tail_dependence(ranks, threshold)
    tau = np.eye(d)
    for i in range(d):
        for j in range(i + 1, d):
            t_ij = stats.kendalltau(L[:, i], L[:, j]).statistic
            tau[i, j] = tau[j, i] = 0.0 if np.isnan(t_ij) else t_ij
    rho = np.sin(0.5 * np.pi * tau)
    np.fill_diagonal(rho, 1.0)
    pair_dfs: list[tuple[int, int, float, bool]] = []
    for i in range(d):
        for j in range(i + 1, d):
            df_ij, capped = implied_t_df_from_tail_dependence(
                min(max(lam[i, j], 0.0), 1.0), float(np.clip(rho[i, j], -0.999, 0.999)),
                df_lo=df_lo, df_hi=df_hi,
            )
            pair_dfs.append((i, j, df_ij, capped))
    dfs = np.array([p[2] for p in pair_dfs])
    capped_share = float(np.mean([p[3] for p in pair_dfs]))
    return TailDependenceMatch(
        threshold=threshold,
        n_obs=n,
        lambda_matrix=lam.round(6).tolist(),
        rho_matrix=rho.round(6).tolist(),
        pairwise_df=pair_dfs,
        pooled_df=float(np.median(dfs)),
        pooled_df_capped_share=capped_share,
        note=(
            "Pooled df is the MEDIAN pairwise tail-dependence-matched df. "
            "Finite-threshold estimator is sampling-noisy; report threshold "
            "sensitivity. Capped pairs are disclosed, not hidden."
        ),
    )
