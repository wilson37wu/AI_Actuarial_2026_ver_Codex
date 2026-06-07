"""Student-t copula aggregation with tail-dependence-matched df (Phase 23 Task 2).

EDUCATIONAL ONLY -- not a regulatory capital model.

Motivation (MR-010 residual; Phase 23 Task 1 design note)
---------------------------------------------------------
The Phase 18-22 copula aggregation selects its copula by AIC on
pseudo-observations.  AIC is dominated by the BODY of the dependence
structure, so the Student-t df is repeatedly pinned at the top of the MLE
search grid and the selection collapses to the Gaussian copula -- which has
ZERO asymptotic upper-tail dependence, while realised capital losses co-move
strongly in the tail.  This module implements the Task 1 design: calibrate
the t-copula df by **tail-dependence matching** (Demarta-McNeil 2005 closed
form inverted on the empirical pairwise lambda_U of the realised standalone
capital-loss vectors), aggregate with t(df_matched), and benchmark against
the Gaussian-copula baseline and the nested ground truth.

FIXED acceptance gate (recorded in PHASE23_TASK1_DESIGN_NOTE before any
benchmark error was seen -- no gate-shopping):
  * t(df_matched) SCR rel err vs nested <= Gaussian baseline rel err, OR
    <= rel_error_tolerance (25%);
  * lambda_U matrix, threshold sensitivity (>= 3 thresholds), pooled MEDIAN
    df, and capped-share all DISCLOSED in the report.

Honest-disclosure notes baked in: the finite-threshold lambda_U estimator is
sampling-noisy at small n_obs (n_outer=160 realised losses -> thresholds
0.80/0.85/0.90, NOT the 0.97+ of the large-n design-note pre-study); pairs
whose df inversion hits a search bound are counted, not hidden; the pooled
df assumes an exchangeable common-df t-copula.

Standards: SOA ASOP 56 s3.5; SOA ASOP 25 s3.3; IA TAS M s3.6; Solvency II
Delegated Reg. Art. 234 (empirically justified diversification); IFoA Life
Aggregation & Simulation WP; Demarta-McNeil 2005; McNeil-Frey-Embrechts 2015.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats
from scipy.special import gammaln

from par_model_v2.projection.nested_stochastic_tvog import (
    CapitalMetrics,
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.multi_driver_copula_aggregation import (
    _EmpiricalMargin,
    _gaussian_copula,
    _nearest_correlation,
    _pseudo_obs,
)
from par_model_v2.projection.tail_dependence import (
    DF_HI_DEFAULT,
    DF_LO_DEFAULT,
    TailDependenceMatch,
    match_t_df_to_losses,
    t_copula_upper_tail_dependence,
)

__all__ = [
    "TCopulaAggregationConfig",
    "ThresholdSensitivityRow",
    "TCopulaAggregationReport",
    "TailMatchedTCopulaAggregator",
    "simulate_t_copula_uniforms",
]

#: Default finite-threshold grid sized for ~160 realised outer losses:
#: n*(1-q) = 32 / 24 / 16 joint-tail observations.  The design-note pre-study
#: thresholds (0.97-0.99) need n ~ 1e5 and are NOT feasible here; disclosed.
DEFAULT_THRESHOLDS: Tuple[float, ...] = (0.80, 0.85, 0.90)

#: Fixed Phase 23 Task 1 acceptance tolerance (recorded before implementation).
DEFAULT_REL_ERROR_TOLERANCE = 0.25

#: Recommended minimum expected joint-tail count n*(1-q); below it the
#: estimator-noise disclosure is added to the report notes.
MIN_TAIL_OBS_RECOMMENDED = 10.0


def simulate_t_copula_uniforms(
    rng: np.random.Generator,
    n_sim: int,
    correlation: np.ndarray,
    df: float,
) -> np.ndarray:
    """Draw n_sim uniform vectors from a t-copula(correlation, df).

    Standard chi-square mixing construction: X = Z / sqrt(W/df) with
    Z ~ N(0, R) and W ~ chi2(df); U = t_df.cdf(X).  The correlation matrix
    must already be positive definite (callers repair via
    ``_nearest_correlation``).
    """
    if df <= 0.0:
        raise ValueError(f"df must be positive, got {df}")
    R = np.asarray(correlation, dtype=float)
    chol = np.linalg.cholesky(R)
    d = R.shape[0]
    Z = rng.standard_normal((n_sim, d)) @ chol.T
    W = rng.chisquare(df, size=n_sim) / df
    X = Z / np.sqrt(W)[:, None]
    return stats.t.cdf(X, df)


@dataclass
class TCopulaAggregationConfig:
    """Configuration for the tail-matched t-copula aggregation run."""

    thresholds: Tuple[float, ...] = DEFAULT_THRESHOLDS
    n_sim: int = 200_000
    seed: int = 20260607
    confidence_level: float = 0.995
    capital_horizon_months: int = 12
    rel_error_tolerance: float = DEFAULT_REL_ERROR_TOLERANCE
    df_lo: float = DF_LO_DEFAULT
    df_hi: float = DF_HI_DEFAULT

    def __post_init__(self) -> None:
        if len(self.thresholds) < 3:
            raise ValueError("need >= 3 thresholds for the sensitivity table "
                             "(fixed Phase 23 Task 1 gate)")
        if not all(0.5 < q < 1.0 for q in self.thresholds):
            raise ValueError("thresholds must lie in (0.5, 1)")
        if len(set(self.thresholds)) != len(self.thresholds):
            raise ValueError("thresholds must be distinct")
        if self.n_sim < 1_000:
            raise ValueError("n_sim must be >= 1000")
        if not (0.5 < self.confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0.5, 1.0)")
        if self.capital_horizon_months <= 0:
            raise ValueError("capital_horizon_months must be positive")
        if self.rel_error_tolerance < 0:
            raise ValueError("rel_error_tolerance must be non-negative")
        if not (0.0 < self.df_lo < self.df_hi):
            raise ValueError("need 0 < df_lo < df_hi")

    def to_dict(self) -> Dict[str, object]:
        return {
            "thresholds": list(self.thresholds),
            "n_sim": self.n_sim,
            "seed": self.seed,
            "confidence_level": self.confidence_level,
            "capital_horizon_months": self.capital_horizon_months,
            "rel_error_tolerance": self.rel_error_tolerance,
            "df_lo": self.df_lo,
            "df_hi": self.df_hi,
        }


@dataclass
class ThresholdSensitivityRow:
    """One row of the >=3-threshold df-matching sensitivity table."""

    threshold: float
    expected_tail_obs: float          # n_obs * (1 - threshold)
    pooled_df: float
    capped_share: float
    mean_offdiag_lambda: float
    max_offdiag_lambda: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "threshold": self.threshold,
            "expected_tail_obs": round(self.expected_tail_obs, 2),
            "pooled_df": round(self.pooled_df, 4),
            "capped_share": round(self.capped_share, 4),
            "mean_offdiag_lambda": round(self.mean_offdiag_lambda, 6),
            "max_offdiag_lambda": round(self.max_offdiag_lambda, 6),
        }


@dataclass
class TCopulaAggregationReport:
    """Structured Phase 23 Task 2 evidence report."""

    config: TCopulaAggregationConfig
    drivers: Tuple[str, ...]
    n_obs: int
    nested_scr: float
    var_covar_scr: float
    sensitivity: List[ThresholdSensitivityRow]
    df_matched: float
    df_matched_capped_share: float
    central_threshold: float
    rho_matrix: List[List[float]]
    empirical_lambda_matrix: List[List[float]]
    implied_lambda_matrix: List[List[float]]
    gaussian_scr: float
    gaussian_rel_error_vs_nested: float
    gaussian_aic: float
    t_matched_scr: float
    t_matched_rel_error_vs_nested: float
    t_matched_loglik: float
    t_matched_aic: float
    t_capital: Optional[CapitalMetrics]
    gaussian_capital: Optional[CapitalMetrics]
    var_covar_rel_error_vs_nested: float
    verdict: str
    gate: str
    run_id: str
    duration_seconds: float
    reproducibility_digest: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict,
            "gate": self.gate,
            "drivers": list(self.drivers),
            "n_obs": self.n_obs,
            "nested_scr": round(self.nested_scr, 4),
            "var_covar_scr": round(self.var_covar_scr, 4),
            "var_covar_rel_error_vs_nested": round(self.var_covar_rel_error_vs_nested, 6),
            "threshold_sensitivity": [r.to_dict() for r in self.sensitivity],
            "df_matched": round(self.df_matched, 4),
            "df_matched_capped_share": round(self.df_matched_capped_share, 4),
            "central_threshold": self.central_threshold,
            "rho_matrix": self.rho_matrix,
            "empirical_lambda_matrix": self.empirical_lambda_matrix,
            "implied_lambda_matrix": self.implied_lambda_matrix,
            "gaussian_scr": round(self.gaussian_scr, 4),
            "gaussian_rel_error_vs_nested": round(self.gaussian_rel_error_vs_nested, 6),
            "gaussian_aic": round(self.gaussian_aic, 4),
            "t_matched_scr": round(self.t_matched_scr, 4),
            "t_matched_rel_error_vs_nested": round(self.t_matched_rel_error_vs_nested, 6),
            "t_matched_loglik": round(self.t_matched_loglik, 4),
            "t_matched_aic": round(self.t_matched_aic, 4),
            "t_capital": self.t_capital.summary() if self.t_capital else None,
            "gaussian_capital": self.gaussian_capital.summary() if self.gaussian_capital else None,
            "duration_seconds": round(self.duration_seconds, 4),
            "reproducibility_digest": self.reproducibility_digest,
            "config": self.config.to_dict(),
            "notes": list(self.notes),
            "standards": [
                "SOA ASOP 56 s3.5",
                "SOA ASOP 25 s3.3",
                "IA TAS M s3.6",
                "Solvency II Delegated Reg. Art. 234",
                "IFoA Life Aggregation & Simulation WP",
                "Demarta-McNeil 2005 (t-copula tail dependence)",
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def _t_copula_loglik_fixed(U: np.ndarray, R: np.ndarray, df: float) -> float:
    """Log-likelihood of pseudo-observations under a t-copula(R, df)."""
    x = stats.t.ppf(np.clip(U, 1e-12, 1.0 - 1e-12), df)
    Rinv = np.linalg.inv(R)
    _, logdet = np.linalg.slogdet(R)
    d = U.shape[1]
    q = np.einsum("ij,jk,ik->i", x, Rinv, x)
    n = U.shape[0]
    ll = (
        n * (gammaln((df + d) / 2.0) + (d - 1) * gammaln(df / 2.0)
             - d * gammaln((df + 1) / 2.0))
        - 0.5 * n * logdet
        - (df + d) / 2.0 * np.sum(np.log1p(q / df))
        + (df + 1) / 2.0 * np.sum(np.log1p(x ** 2 / df))
    )
    return float(ll)


class TailMatchedTCopulaAggregator:
    """Aggregate realised standalone capital losses with t(df tail-matched).

    Consumes ONLY model outputs already produced by a nested run (the realised
    per-driver standalone capital-loss vectors plus the nested-truth and
    var-covar SCR benchmarks); performs no projection itself, so it is
    unit-testable on synthetic losses and reusable for any driver set.
    """

    def __init__(
        self,
        loss_vectors: Sequence[np.ndarray],
        driver_names: Sequence[str],
        nested_scr: float,
        var_covar_scr: float,
    ) -> None:
        L = np.column_stack([np.asarray(v, dtype=float) for v in loss_vectors])
        if L.shape[1] < 2:
            raise ValueError("need at least two loss vectors to aggregate")
        if len(driver_names) != L.shape[1]:
            raise ValueError("driver_names length must match number of loss vectors")
        self.L = L
        self.driver_names = tuple(driver_names)
        self.nested_scr = float(nested_scr)
        self.var_covar_scr = float(var_covar_scr)

    def run(self, config: Optional[TCopulaAggregationConfig] = None) -> TCopulaAggregationReport:
        cfg = config or TCopulaAggregationConfig()
        t0 = time.monotonic()
        run_id = "tcopula-tailmatch-" + uuid.uuid4().hex[:8]
        n, d = self.L.shape
        conf, hm = cfg.confidence_level, cfg.capital_horizon_months
        notes: List[str] = []

        # ---- 1. Threshold-sensitivity df matching (>= 3 thresholds). ----
        matches: List[TailDependenceMatch] = []
        sens: List[ThresholdSensitivityRow] = []
        for q in sorted(cfg.thresholds):
            m = match_t_df_to_losses(self.L, threshold=q, df_lo=cfg.df_lo, df_hi=cfg.df_hi)
            lam = np.asarray(m.lambda_matrix, dtype=float)
            off = lam[~np.eye(d, dtype=bool)]
            matches.append(m)
            sens.append(ThresholdSensitivityRow(
                threshold=q,
                expected_tail_obs=n * (1.0 - q),
                pooled_df=m.pooled_df,
                capped_share=m.pooled_df_capped_share,
                mean_offdiag_lambda=float(off.mean()),
                max_offdiag_lambda=float(off.max()),
            ))
            if n * (1.0 - q) < MIN_TAIL_OBS_RECOMMENDED:
                notes.append(
                    "DISCLOSURE: threshold {:.2f} leaves only ~{:.0f} expected "
                    "joint-tail observations (n={}) -- the lambda_U estimate at "
                    "this threshold is sampling-noisy.".format(q, n * (1.0 - q), n)
                )

        # Pooled-of-pooled: MEDIAN across thresholds of the per-threshold
        # MEDIAN pairwise df (robust on both axes; per Task 1 design note).
        pooled_dfs = np.array([m.pooled_df for m in matches])
        df_matched = float(np.median(pooled_dfs))
        df_matched_capped_share = float(np.mean([m.pooled_df_capped_share for m in matches]))
        central = sorted(cfg.thresholds)[len(cfg.thresholds) // 2]
        central_match = matches[sorted(cfg.thresholds).index(central)]

        # ---- 2. Dependence matrix: Kendall-tau-implied elliptical rho. ----
        rho = _nearest_correlation(np.asarray(central_match.rho_matrix, dtype=float))

        # ---- 3. Marginals + pseudo-observations (empirical; copula supplies
        #          dependence only -- identical to the governed aggregator). ----
        margins = [_EmpiricalMargin(self.L[:, j]) for j in range(d)]
        U = _pseudo_obs(self.L)

        # ---- 4. Gaussian baseline (the AIC-selected incumbent), fitted by the
        #          SAME machinery as the governed CopulaRiskAggregator. ----
        g_sampler, g_loglik, g_nparams, _g_lam, _g_params = _gaussian_copula(U)
        rng_g = np.random.default_rng([cfg.seed, 0])
        Ug = g_sampler(rng_g, cfg.n_sim)
        agg_g = np.zeros(cfg.n_sim)
        for j in range(d):
            agg_g += margins[j].ppf(Ug[:, j])
        cap_g = capital_metrics_from_liabilities(agg_g, conf, hm)
        gauss_rel = _rel(cap_g.scr_proxy, self.nested_scr)
        gauss_aic = 2.0 * g_nparams - 2.0 * g_loglik

        # ---- 5. Tail-matched t-copula aggregation. ----
        rng_t = np.random.default_rng([cfg.seed, 1])
        Ut = simulate_t_copula_uniforms(rng_t, cfg.n_sim, rho, df_matched)
        agg_t = np.zeros(cfg.n_sim)
        for j in range(d):
            agg_t += margins[j].ppf(Ut[:, j])
        cap_t = capital_metrics_from_liabilities(agg_t, conf, hm)
        t_rel = _rel(cap_t.scr_proxy, self.nested_scr)
        t_ll = _t_copula_loglik_fixed(U, rho, df_matched)
        # df is MATCHED (not MLE-fitted), so it is NOT an extra free parameter
        # estimated from the body; we still count it conservatively.
        t_aic = 2.0 * (g_nparams + 1) - 2.0 * t_ll

        # ---- 6. Implied lambda_U at the matched df (closed form). ----
        implied = np.eye(d)
        for i in range(d):
            for j in range(i + 1, d):
                implied[i, j] = implied[j, i] = t_copula_upper_tail_dependence(
                    df_matched, float(np.clip(rho[i, j], -0.999, 0.999))
                )

        # ---- 7. FIXED gate (Phase 23 Task 1; no gate-shopping). ----
        gate = ("PASS if t(df_matched) SCR rel err <= gaussian baseline rel err "
                "OR <= {:.0%}; lambda_U + threshold sensitivity + capped-share "
                "disclosed".format(cfg.rel_error_tolerance))
        ok = (t_rel <= gauss_rel + 1e-12) or (t_rel <= cfg.rel_error_tolerance)
        verdict = "PASS" if ok else "PARTIAL"

        vc_rel = _rel(self.var_covar_scr, self.nested_scr)
        notes.extend([
            "df matched by tail-dependence inversion (Demarta-McNeil 2005), "
            "NOT by AIC/MLE on the body: pooled MEDIAN pairwise df, median "
            "across {} thresholds.".format(len(cfg.thresholds)),
            "Pooled common-df t-copula is exchangeable in df across pairs -- a "
            "disclosed simplification (per-pair dfs are reported).",
            "Capped-pair share {:.0%} (pairs whose inversion hit a df search "
            "bound; disclosed, not hidden).".format(df_matched_capped_share),
            "Gaussian baseline simulated with the same empirical marginals and "
            "seed family for an apples-to-apples SCR comparison.",
        ])
        if df_matched >= 0.95 * cfg.df_hi:
            notes.append(
                "DISCLOSURE: matched df ~ df_hi cap -- the realised losses show "
                "Gaussian-like (weak) tail dependence at the usable thresholds."
            )

        digest = hashlib.sha256(np.round(np.concatenate([
            self.L.ravel(),
            np.array([self.nested_scr, self.var_covar_scr, df_matched,
                      cap_t.scr_proxy, cap_g.scr_proxy, float(cfg.seed)]),
        ]), 6).tobytes()).hexdigest()

        return TCopulaAggregationReport(
            config=cfg,
            drivers=self.driver_names,
            n_obs=n,
            nested_scr=self.nested_scr,
            var_covar_scr=self.var_covar_scr,
            sensitivity=sens,
            df_matched=df_matched,
            df_matched_capped_share=df_matched_capped_share,
            central_threshold=central,
            rho_matrix=rho.round(6).tolist(),
            empirical_lambda_matrix=central_match.lambda_matrix,
            implied_lambda_matrix=implied.round(6).tolist(),
            gaussian_scr=float(cap_g.scr_proxy),
            gaussian_rel_error_vs_nested=gauss_rel,
            gaussian_aic=gauss_aic,
            t_matched_scr=float(cap_t.scr_proxy),
            t_matched_rel_error_vs_nested=t_rel,
            t_matched_loglik=t_ll,
            t_matched_aic=t_aic,
            t_capital=cap_t,
            gaussian_capital=cap_g,
            var_covar_rel_error_vs_nested=vc_rel,
            verdict=verdict,
            gate=gate,
            run_id=run_id,
            duration_seconds=time.monotonic() - t0,
            reproducibility_digest=digest,
            notes=notes,
        )


def _rel(value: float, reference: float) -> float:
    denom = abs(reference) if abs(reference) > 1e-9 else 1.0
    return float(abs(value - reference) / denom)


def t_copula_aggregation_use_restrictions() -> Dict[str, object]:
    """Model-use restrictions for the tail-matched t-copula aggregation."""
    return {
        "classification": "EDUCATIONAL",
        "permitted_uses": [
            "Teaching tail-dependence-aware capital aggregation",
            "Sensitivity analysis of aggregate SCR to copula tail dependence",
            "Benchmarking against the AIC-selected gaussian incumbent",
        ],
        "prohibited_uses": [
            "Regulatory or statutory capital reporting",
            "Pricing, reserving, or any production actuarial use",
        ],
        "key_limitations": [
            "Finite-threshold lambda_U estimator is sampling-noisy at n~160",
            "Common pooled df (exchangeable t-copula) across all driver pairs",
            "Empirical marginals limited to the realised outer-loss support",
            "Educational-proxy market data; independent APS X2 review pending",
        ],
    }
