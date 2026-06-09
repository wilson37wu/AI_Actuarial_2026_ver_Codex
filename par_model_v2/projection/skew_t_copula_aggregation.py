"""
Phase 27 Task 2 - GH skew-t copula re-aggregation on the FROZEN copula.

Implements the richer UPPER-TAIL-ASYMMETRY copula designed in the Phase 27
Task 1 note (docs/validation/PHASE27_TASK1_DESIGN_NOTE.md): the
generalized-hyperbolic skew-t copula (Demarta & McNeil 2005; McNeil, Frey &
Embrechts 2015 ch. 7) layered on the governed frozen Student-t copula
(df 2.9451, correlation Sigma).  ONE new structural lever - a scalar
skewness gamma - is added on top of the frozen (df, Sigma); the calibrated
MARGINS and the governed rank dependence are UNCHANGED (Solvency II
Art. 234 rank invariance).

GH skew-t mixture (mean-variance Normal mixture; McNeil-Frey-Embrechts 7.3.2):

    X = gamma * W + sqrt(W) * Z,   W ~ InvGamma(df/2, df/2),  Z ~ N(0, Sigma)

with the SAME mixing variate W and Gaussian Z used by the frozen symmetric
t-copula simulator (:func:`...t_copula_tail_matched_aggregation.simulate_t_copula_uniforms`),
so that gamma = 0 recovers the symmetric t copula EXACTLY on common random
numbers (a strict super-set; the freeze is nested as the gamma = 0 boundary
case, so the archive cross-check is exact).

Construction detail guaranteeing the EXACT gamma = 0 recovery
------------------------------------------------------------
The frozen symmetric simulator draws ``Z = standard_normal @ chol.T`` then
``W_chi = chisquare(df) / df`` and forms ``X_sym = Z / sqrt(W_chi)`` and
``U = t_df.cdf(X_sym)``.  Writing the inverse-gamma mixing variate as
``W = 1 / W_chi`` (1/W_chi ~ Gamma(df/2, 2/df) = chi2(df)/df, the exact
relation), the GH skew-t latent is

    X_skew = gamma * (1 / W_chi) + Z / sqrt(W_chi)

drawn from the IDENTICAL rng stream (same ``Z``, same ``W_chi``).  At
gamma = 0 this is ``Z / sqrt(W_chi) = X_sym`` bit-for-bit, and the copula
uniforms ``U = G(X_skew; df, gamma)`` short-circuit to ``t_df.cdf`` (the
exact gamma = 0 limit of the univariate GH skew-t marginal CDF), so the
gamma = 0 uniforms are bit-identical to the symmetric-t uniforms.

For gamma > 0 the univariate GH skew-t marginal CDF
``G(x) = E_W[ Phi( (x - gamma * w) / sqrt(w) ) ]`` (the scalar mixing
variate w ~ InvGamma(df/2, df/2) integrated out, gamma scalar so all d
margins share G) is evaluated by Gauss-Laguerre quadrature on a fine x-grid
and monotone-interpolated, giving copula uniforms that are uniform per
margin (the frozen empirical margins are never modified) while the joint
upper tail is heavier and asymmetric.

EDUCATIONAL MODEL: all parameters are educational placeholders pending
credentialled data and independent APS X2 review.  NOT for production
capital decisions.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from typing import Dict, Optional, Tuple

import numpy as np
from scipy import stats

from par_model_v2.projection.joint_action_aggregation import (
    JointActionAggregator,
)
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.pathwise_composition_transform import (
    composition_with_actions,
    split_joint_composition,
)

# ---------------------------------------------------------------------------
# Frozen / archived references consumed as GATE baselines (none computed here).
# ---------------------------------------------------------------------------
# Archived Phase 26 Task 2 frozen-t COMPONENT path-wise SCR (the sign-gate
# reference and the gamma = 0 exact-recovery target).
FROZEN_T_COMPONENT_SCR_REFERENCE = 39_975.654628199336
# Archived Phase 25 Task 2 nested path-wise with-actions SCR (truth target).
NESTED_PATHWISE_SCR_REFERENCE = 46_638.9
# Rank invariance (Solvency II Art. 234, Phase 23 Task 2 freeze).
RANK_INVARIANCE_DF = 2.9451
DF_REMATCH_TOL = 1e-4
RHO_FROZEN_TOL = 1e-12
# gamma = 0 EXACT-recovery tolerance (pre-registered Task 2 gate 1).
GAMMA_ZERO_RECOVERY_TOL = 1e-9
# Upper-tail co-exceedance level for the gamma fit / diagnostics.
TAIL_LEVEL_P = 0.90
# Sign gate reference (pre-registered Task 2 gate 5).
SKEWT_SIGN_GATE_REFERENCE = FROZEN_T_COMPONENT_SCR_REFERENCE


# ===========================================================================
# Univariate GH skew-t marginal CDF (gamma scalar; df, gamma shared by margins)
# ===========================================================================
def _gamma_quadrature_nodes(df: float, n_nodes: int = 192
                           ) -> Tuple[np.ndarray, np.ndarray]:
    """Quadrature nodes/weights for E_g[.] with g = chi2(df)/df ~ Gamma(k, th).

    The frozen chi-square mixing variate is g = chisquare(df)/df, i.e.
    Gamma(shape=df/2, scale=2/df).  Generalised Gauss-Laguerre (alpha = k-1)
    integrates ``int_0^inf u^{k-1} e^{-u} h(u) du = sum w_i h(node_i)``; with
    the substitution g = u / rate (rate = 1/scale = df/2) the Gamma density
    normalisation is absorbed so that ``sum_i weight_i f(g_i)`` equals
    ``E_g[f(g)]`` to quadrature accuracy.  The univariate GH skew-t marginal
    integrates the INVERSE-gamma variate w = 1/g (see ``skew_t_marginal_cdf``).
    """
    shape = df / 2.0                 # k
    rate = df / 2.0                  # 1 / scale, scale = 2/df
    xa, wa = _gen_laguerre(shape - 1.0, int(n_nodes))
    from scipy.special import gammaln
    nodes_g = xa / rate
    weights = wa / np.exp(gammaln(shape))
    return nodes_g, weights


def _gen_laguerre(alpha: float, n: int) -> Tuple[np.ndarray, np.ndarray]:
    """Generalised Gauss-Laguerre nodes/weights via the Golub-Welsch eigenproblem.

    Integrates ``int_0^inf x^{alpha} e^{-x} f(x) dx ~ sum w_i f(x_i)``.
    """
    i = np.arange(n, dtype=float)
    a = 2.0 * i + alpha + 1.0           # diagonal
    b = np.sqrt(i[1:] * (i[1:] + alpha))  # off-diagonal
    from scipy.special import gamma as gammafn
    J = np.diag(a) + np.diag(b, 1) + np.diag(b, -1)
    vals, vecs = np.linalg.eigh(J)
    mu0 = gammafn(alpha + 1.0)          # int x^alpha e^{-x} dx = Gamma(alpha+1)
    w = mu0 * (vecs[0, :] ** 2)
    order = np.argsort(vals)
    return vals[order], w[order]


def skew_t_marginal_cdf(x: np.ndarray, df: float, gamma: float,
                        n_nodes: int = 192) -> np.ndarray:
    """Univariate GH skew-t marginal CDF G(x; df, gamma).

    gamma == 0 returns the EXACT Student-t CDF (the symmetric limit), so the
    copula uniforms coincide bit-for-bit with the frozen symmetric simulator.
    """
    x = np.asarray(x, dtype=float)
    if gamma == 0.0:
        return stats.t.cdf(x, df)
    # GH skew-t marginal: X = gamma * w + sqrt(w) * Z, w = 1/g ~ InvGamma(df/2,
    # df/2), g = chi2(df)/df ~ Gamma(df/2, 2/df).  Conditional on g,
    #   X | g ~ N(gamma / g, 1 / g)  =>  Phi( (x - gamma/g) * sqrt(g) ).
    # Integrate the Gamma variate g out (gamma scalar -> all d margins share G).
    # At gamma = 0 this is E_g[Phi(x sqrt(g))] = t_df.cdf(x) (handled above).
    nodes_g, weights = _gamma_quadrature_nodes(df, n_nodes)
    sqrt_g = np.sqrt(nodes_g)
    arg = (x[:, None] - gamma / nodes_g[None, :]) * sqrt_g[None, :]
    cdf = stats.norm.cdf(arg) @ weights
    return np.clip(cdf, 0.0, 1.0)


def _skew_t_cdf_interpolant(df: float, gamma: float, n_grid: int = 12001,
                            x_lo: float = -60.0, x_hi: float = 60.0,
                            n_nodes: int = 192
                            ) -> Tuple[np.ndarray, np.ndarray]:
    """Fine monotone (x, G(x)) grid for fast vectorised PIT of the latent X."""
    xg = np.linspace(x_lo, x_hi, int(n_grid))
    Gg = skew_t_marginal_cdf(xg, df, gamma, n_nodes)
    # enforce strict monotonicity for safe inversion / interpolation
    Gg = np.maximum.accumulate(Gg)
    return xg, Gg


# ===========================================================================
# Skew-t copula uniform simulator (gamma = 0 == frozen symmetric t, CRN-exact)
# ===========================================================================
def simulate_skew_t_copula_uniforms(
    rng: np.random.Generator,
    n_sim: int,
    correlation: np.ndarray,
    df: float,
    gamma: float,
    n_nodes: int = 192,
) -> np.ndarray:
    """Draw n_sim uniform vectors from a GH skew-t copula(correlation, df, gamma).

    The rng draw ORDER (Z then W_chi) is IDENTICAL to the frozen symmetric
    t-copula simulator, so at gamma = 0 the returned uniforms are
    bit-identical to ``simulate_t_copula_uniforms(rng, n_sim, R, df)``.
    """
    if df <= 0.0:
        raise ValueError(f"df must be positive, got {df}")
    if gamma < 0.0:
        raise ValueError("gamma must be >= 0 (upper-tail skew)")
    R = np.asarray(correlation, dtype=float)
    chol = np.linalg.cholesky(R)
    d = R.shape[0]
    Z = rng.standard_normal((n_sim, d)) @ chol.T          # same as symmetric
    W_chi = rng.chisquare(df, size=n_sim) / df            # same as symmetric
    if gamma == 0.0:
        X = Z / np.sqrt(W_chi)[:, None]
        return stats.t.cdf(X, df)                          # exact symmetric path
    # GH skew-t latent with W = 1/W_chi (InvGamma(df/2, df/2)).
    X = gamma * (1.0 / W_chi)[:, None] + Z / np.sqrt(W_chi)[:, None]
    xg, Gg = _skew_t_cdf_interpolant(df, gamma, n_nodes=n_nodes)
    U = np.interp(X.ravel(), xg, Gg).reshape(X.shape)
    return np.clip(U, 1e-12, 1.0 - 1e-12)


# ===========================================================================
# Upper-tail co-exceedance: realised target + model-implied (for the gamma fit)
# ===========================================================================
def _avg_pairwise_upper_codependence(U: np.ndarray, p: float) -> float:
    """Average pairwise empirical upper co-exceedance proxy at level p.

    P(U_i > p, U_j > p) / (1 - p), averaged over all driver pairs - a
    finite-sample proxy for the average pairwise upper-tail dependence.
    """
    d = U.shape[1]
    thr = p
    vals = []
    for i, j in itertools.combinations(range(d), 2):
        joint = float(((U[:, i] > thr) & (U[:, j] > thr)).mean())
        vals.append(joint / (1.0 - p))
    return float(np.mean(vals))


def realised_upper_tail_codependence(
    losses: Dict[str, np.ndarray], drivers, p: float = TAIL_LEVEL_P
) -> float:
    """Realised upper-tail co-exceedance of the standalone loss vectors.

    Rank-PIT each standalone loss vector to copula uniforms (margins
    irrelevant), then average the pairwise upper co-exceedance proxy - the
    fit TARGET (leakage-free: only standalone losses, no nested truth).
    """
    cols = [np.asarray(losses[k], dtype=float) for k in drivers]
    L = np.column_stack(cols)
    ranks = np.argsort(np.argsort(L, axis=0), axis=0)
    U = (ranks + 0.5) / L.shape[0]
    return _avg_pairwise_upper_codependence(U, p)


def model_upper_tail_codependence(
    correlation: np.ndarray, df: float, gamma: float, p: float = TAIL_LEVEL_P,
    n_sim: int = 200_000, seed: int = 20260608,
) -> float:
    """Model-implied upper-tail co-exceedance of the skew-t copula at gamma."""
    rng = np.random.default_rng(int(seed))
    U = simulate_skew_t_copula_uniforms(rng, int(n_sim), correlation, df, gamma)
    return _avg_pairwise_upper_codependence(U, p)


def fit_gamma_to_upper_tail(
    losses: Dict[str, np.ndarray], drivers, correlation: np.ndarray,
    df: float, p: float = TAIL_LEVEL_P, n_sim: int = 200_000,
    seed: int = 20260608, gamma_hi: float = 4.0,
) -> Dict[str, object]:
    """Fit the scalar gamma so the skew-t upper-tail co-exceedance matches the
    realised standalone-loss target (df, Sigma FROZEN; margins untouched).

    Bounded 1-D root find on the monotone (gamma -> model co-exceedance) map.
    """
    from scipy.optimize import minimize_scalar

    target = realised_upper_tail_codependence(losses, drivers, p)
    base = model_upper_tail_codependence(correlation, df, 0.0, p, n_sim, seed)

    def obj(g: float) -> float:
        m = model_upper_tail_codependence(correlation, df, float(g), p,
                                          n_sim, seed)
        return (m - target) ** 2

    res = minimize_scalar(obj, bounds=(0.0, gamma_hi), method="bounded",
                          options={"xatol": 1e-4})
    gamma_hat = float(max(res.x, 0.0))
    model_at_hat = model_upper_tail_codependence(correlation, df, gamma_hat, p,
                                                 n_sim, seed)
    return {
        "gamma_hat": gamma_hat,
        "tail_level_p": float(p),
        "target_realised_codependence": float(target),
        "model_codependence_at_gamma0": float(base),
        "model_codependence_at_gamma_hat": float(model_at_hat),
        "fit_residual_abs": float(abs(model_at_hat - target)),
        "fit_n_sim": int(n_sim),
        "fit_seed": int(seed),
        "fit_converged": bool(res.success),
        "upper_tail_lift_vs_symmetric": float(model_at_hat - base),
    }


# ===========================================================================
# Component-basis re-aggregation on the skew-t copula (mirrors P26T2 readout)
# ===========================================================================
def composition_skewt_readout(
    agg: JointActionAggregator,
    n_sim: int,
    seed: int,
    df: float,
    gamma: float,
    sigma: float,
    alpha: float,
    benefit_share: float,
    confidence: float = 0.995,
) -> Dict[str, object]:
    """One skew-t-copula draw -> component with-actions read-out (P26T2 basis).

    Identical relief machinery to the frozen-t component read-out
    (:func:`...pathwise_composition_transform.composition_joint_readout`); the
    ONLY change is the copula uniform sampler (skew-t with skewness gamma).
    At gamma = 0 the uniforms are bit-identical to the symmetric t draw, so
    this read-out reproduces the frozen-t component basis exactly.
    """
    rng = np.random.default_rng(int(seed))
    U = simulate_skew_t_copula_uniforms(rng, int(n_sim), agg.correlation,
                                        float(df), float(gamma))
    comp = split_joint_composition(agg, U)
    V = comp["V"]
    v_cut = comp["V_cut"]
    pw = composition_with_actions(
        agg.rule, V, v_cut, agg.a_ref, sigma, alpha, benefit_share)
    m_wo = capital_metrics_from_liabilities(V, float(confidence), 12)
    m_cp = capital_metrics_from_liabilities(
        np.asarray(pw["W"], dtype=float), float(confidence), 12)
    # upper/lower tail-dependence proxies of the realised copula draw
    lam_u = _avg_pairwise_upper_codependence(U, TAIL_LEVEL_P)
    lam_l = float(np.mean([
        ((U[:, i] < 1.0 - TAIL_LEVEL_P) & (U[:, j] < 1.0 - TAIL_LEVEL_P)).mean()
        / (1.0 - TAIL_LEVEL_P)
        for i, j in itertools.combinations(range(U.shape[1]), 2)]))
    out = {
        "config": {
            "n_sim": int(n_sim), "seed": int(seed), "df": float(df),
            "gamma": float(gamma),
            "copula": "skew_t({:g}, gamma={:g})".format(df, gamma),
            "confidence": float(confidence), "sigma": float(sigma),
            "alpha": float(alpha), "benefit_share_fit": float(benefit_share),
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
        "upper_tail_codependence": lam_u,
        "lower_tail_codependence": lam_l,
        "radial_asymmetry": float(lam_u - lam_l),
        "composition_reconstruction_max_abs_err":
            comp["reconstruction_max_abs_err"],
    }
    out["digest"] = hashlib.sha256(json.dumps(
        {k: out[k] for k in ("config", "var_without", "scr_without",
                             "var_component", "scr_component")},
        sort_keys=True).encode()).hexdigest()[:12]
    return out


def skew_t_copula_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions for the Phase 27 skew-t copula (TAS M / ASOP 56)."""
    return {
        "classification": "EDUCATIONAL",
        "restrictions": [
            "The skew-t copula adds ONE scalar upper-tail-asymmetry parameter "
            "(gamma) on the FROZEN (df 2.9451, Sigma); gamma = 0 recovers the "
            "governed symmetric t EXACTLY (Solvency II Art. 234 rank "
            "invariance; no re-tuning of df/Sigma/margins).",
            "gamma is fitted to the realised UPPER-TAIL co-exceedances of the "
            "standalone loss vectors only (leakage-free; a finite-sample "
            "estimate whose sampling error is propagated through the Task 3 "
            "bootstrap).",
            "The univariate GH skew-t marginal CDF is evaluated by "
            "Gauss-Laguerre quadrature on a fine grid for gamma > 0; the "
            "gamma = 0 path short-circuits to the exact Student-t CDF.",
            "If the residual needs heterogeneous tail dependence ACROSS "
            "drivers, the grouped-t escalation (deferred) is next; the vine "
            "copula is the general fallback.",
            "Action parameters remain educational placeholders pending "
            "credentialled practice data + independent APS X2 review.",
        ],
    }
