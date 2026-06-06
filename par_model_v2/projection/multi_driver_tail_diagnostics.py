"""
Tail-Convergence and Stability Diagnostics for the 99.5% Capital Metric
=======================================================================

Phase 15 Task 4.  Adds the convergence, sampling-error, and variance-reduction
diagnostics that SOA ASOP 56 §3.5 and IA TAS M §3.6 require before any tail
capital figure (the 99.5% VaR / ES of the multi-driver liability) may be cited.

The module is **additive** — it consumes the Phase 15 Task 1 bivariate
(rate + equity) LSMC capital surface
(:class:`par_model_v2.projection.multi_driver_capital.MultiDriverLSMCProxyEngine`)
and the Task 6 ``capital_metrics_from_liabilities`` helper, and modifies no
existing file.

Why a proxy surface makes these diagnostics feasible
----------------------------------------------------
A brute-force nested run costs ``N_outer x n_inner`` inner valuations, so
sweeping ``N_outer`` up to tens of thousands, or bootstrapping the estimator
thousands of times, is intractable.  The Longstaff-Schwartz conditional-
expectation surface ``L_hat(r, S)`` is fitted **once** (at ``n_fit`` inner
valuations) and then evaluated for the cost of a polynomial, so the *outer*
sampling error — the part of capital uncertainty these diagnostics target — can
be measured at scale.  The residual *proxy* error is bounded separately by the
Task 1 proxy-vs-nested and Task 2 out-of-sample reports; this module quantifies
the orthogonal Monte-Carlo (outer-sampling) uncertainty.

Three diagnostics
-----------------
1. **Outer-count convergence.**  VaR/ES of ``L_hat`` over independent outer sets
   of increasing size ``N_outer``; reports the successive relative change and the
   smallest ``N_outer`` at which it falls below ``convergence_tol`` (ASOP 56
   §3.5 scenario-count adequacy).

2. **Bootstrap confidence interval.**  Non-parametric bootstrap of the 99.5%
   VaR and ES estimators at a fixed large outer set, giving a percentile CI and
   the estimator standard error — the sampling uncertainty of the *reported*
   capital number (IA TAS M §3.6 model-uncertainty disclosure).

3. **Variance reduction.**  Compares the variance of the VaR estimator under
   (a) crude pseudo-random outer sampling, (b) antithetic-variate sampling, and
   (c) a scrambled-Sobol quasi-Monte-Carlo sequence, over a common
   *pilot-anchored Gaussian-copula* outer distribution (so the three schemes
   target an identical distribution and the variance ratio is a like-for-like
   efficiency measure).  Reports the variance-reduction ratio for each scheme.

The variance-reduction study deliberately operates on a smooth surrogate of the
horizon-state distribution — a Gaussian copula whose correlation is the governed
ESG rate/equity ``rho`` and whose margins are the *empirical* (order-statistic)
margins of a pilot run of the governed outer model.  Antithetic and QMC schemes
are only meaningful on a controllable normal/uniform driver, which the surrogate
provides; the convergence and bootstrap diagnostics use the **real** governed
outer states.  This separation is disclosed in the use restrictions.

ASOP / IA standards
-------------------
- SOA ASOP 56 §3.5   — scenario adequacy, convergence, variance reduction
- SOA ASOP 56 §3.1.3 — stochastic model documentation
- SOA ASOP 25 §3.3   — correlated scenario generation
- IA TAS M §3.6      — model validation, convergence, reproducibility, uncertainty
- L'Ecuyer (2018) "Randomized Quasi-Monte Carlo"; Glasserman (2003) §4 (antithetic / QMC)

Model-use restrictions: see :func:`tail_diagnostics_use_restrictions`.
EDUCATIONAL ONLY — placeholder parameters, two risk drivers, proxy-based outer
sampling; independent APS X2 review pending.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
# --- lazy scipy proxy: keeps this module importable without scipy; the real
# scipy submodule is imported on first attribute access (only if used). ---
class _LazyScipy:
    def __init__(self, _modname):
        object.__setattr__(self, "_modname", _modname)
        object.__setattr__(self, "_mod", None)
    def __getattr__(self, _name):
        if object.__getattribute__(self, "_mod") is None:
            import importlib
            object.__setattr__(self, "_mod",
                               importlib.import_module(object.__getattribute__(self, "_modname")))
        return getattr(object.__getattribute__(self, "_mod"), _name)
stats = _LazyScipy("scipy.stats")
qmc = _LazyScipy("scipy.stats.qmc")

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.nested_stochastic_tvog import (
    CapitalMetrics,
    DEFAULT_CAPITAL_HORIZON_MONTHS,
    DEFAULT_CONFIDENCE_LEVEL,
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.multi_driver_capital import (
    EquityGuaranteeSpec,
    MultiDriverLSMCProxyEngine,
    MultiDriverLSMCResult,
    _outer_states_2d,
)
from par_model_v2.projection.multi_driver_capital_3d import (
    CreditExposureSpec,
    DEFAULT_MAX_INTERACTION_ORDER,
    ThreeDriverCorrelation,
    ThreeDriverLSMCProxyEngine,
    ThreeDriverLSMCResult,
    _outer_states_3d,
)
from par_model_v2.stochastic.credit_spread import CreditSpreadParams
from par_model_v2.stochastic.esg_process import (
    GBMParams,
    HullWhiteParams,
    Measure,
    RiskFreeCurve,
)


#: Default outer-count grid for the convergence sweep.
DEFAULT_OUTER_GRID: Tuple[int, ...] = (500, 1_000, 2_000, 4_000, 8_000, 16_000)
#: Successive-relative-change tolerance on the 99.5% VaR for "converged".
DEFAULT_CONVERGENCE_TOL = 0.02
#: Bootstrap resamples for the VaR/ES confidence interval.
DEFAULT_N_BOOTSTRAP = 2_000
#: Outer set size at which the bootstrap CI is computed.
DEFAULT_BOOTSTRAP_N_OUTER = 8_000
#: Replications used to estimate the VaR-estimator variance per sampling scheme.
DEFAULT_VR_REPLICATIONS = 200
#: Outer set size per replication in the variance-reduction study (power of 2
#: so antithetic and Sobol are exactly balanced).
DEFAULT_VR_N_OUTER = 4_096
#: Pilot outer-set size used to fit the empirical copula margins.
DEFAULT_VR_PILOT_N = 8_000


def _var_es(liab: np.ndarray, cl: float) -> Tuple[float, float]:
    """Return (VaR, ES) on the *upper* tail (a liability increase is the loss)."""
    liab = np.asarray(liab, dtype=float)
    var = float(np.quantile(liab, cl))
    tail = liab[liab >= var]
    es = float(tail.mean()) if tail.size else var
    return var, es


def _rel(a: float, b: float) -> float:
    denom = abs(b) if abs(b) > 1e-9 else 1.0
    return abs(a - b) / denom


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class TailDiagnosticsConfig:
    """Configuration for the Phase 15 Task 4 tail-diagnostics run."""

    n_fit: int = 1_500
    lsmc_degree: int = 2
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS
    outer_measure: Measure = Measure.P
    seed: int = 42

    outer_grid: Tuple[int, ...] = DEFAULT_OUTER_GRID
    convergence_tol: float = DEFAULT_CONVERGENCE_TOL

    n_bootstrap: int = DEFAULT_N_BOOTSTRAP
    bootstrap_n_outer: int = DEFAULT_BOOTSTRAP_N_OUTER
    bootstrap_ci_level: float = 0.95

    vr_replications: int = DEFAULT_VR_REPLICATIONS
    vr_n_outer: int = DEFAULT_VR_N_OUTER
    vr_pilot_n: int = DEFAULT_VR_PILOT_N

    def __post_init__(self) -> None:
        if self.n_fit < 50:
            raise ValueError("n_fit must be >= 50")
        if self.lsmc_degree < 1:
            raise ValueError("lsmc_degree must be >= 1")
        if not (0.5 < self.confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0.5, 1.0)")
        if self.capital_horizon_months <= 0:
            raise ValueError("capital_horizon_months must be positive")
        if len(self.outer_grid) < 2:
            raise ValueError("outer_grid must contain at least two sizes")
        if any(n <= 0 for n in self.outer_grid):
            raise ValueError("outer_grid sizes must be positive")
        if list(self.outer_grid) != sorted(self.outer_grid):
            raise ValueError("outer_grid must be ascending")
        if self.convergence_tol <= 0:
            raise ValueError("convergence_tol must be positive")
        if self.n_bootstrap < 100:
            raise ValueError("n_bootstrap must be >= 100")
        if self.bootstrap_n_outer < 100:
            raise ValueError("bootstrap_n_outer must be >= 100")
        if not (0.5 < self.bootstrap_ci_level < 1.0):
            raise ValueError("bootstrap_ci_level must be in (0.5, 1.0)")
        if self.vr_replications < 10:
            raise ValueError("vr_replications must be >= 10")
        if self.vr_n_outer < 64 or (self.vr_n_outer & (self.vr_n_outer - 1)) != 0:
            raise ValueError("vr_n_outer must be a power of two >= 64")
        if self.vr_pilot_n < 200:
            raise ValueError("vr_pilot_n must be >= 200")
        self.outer_measure = Measure(self.outer_measure)
        self.outer_grid = tuple(int(n) for n in self.outer_grid)

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_fit": self.n_fit,
            "lsmc_degree": self.lsmc_degree,
            "confidence_level": self.confidence_level,
            "capital_horizon_months": self.capital_horizon_months,
            "outer_measure": self.outer_measure.value,
            "seed": self.seed,
            "outer_grid": list(self.outer_grid),
            "convergence_tol": self.convergence_tol,
            "n_bootstrap": self.n_bootstrap,
            "bootstrap_n_outer": self.bootstrap_n_outer,
            "bootstrap_ci_level": self.bootstrap_ci_level,
            "vr_replications": self.vr_replications,
            "vr_n_outer": self.vr_n_outer,
            "vr_pilot_n": self.vr_pilot_n,
        }


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class OuterConvergence:
    """Outer-count convergence of the 99.5% VaR / ES."""

    n_outer_grid: Tuple[int, ...]
    var_path: Tuple[float, ...]
    es_path: Tuple[float, ...]
    var_successive_rel_change: Tuple[float, ...]   # len = grid-1, change vs prev
    es_successive_rel_change: Tuple[float, ...]
    converged: bool
    recommended_n_outer: int
    final_var: float
    final_es: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_outer_grid": list(self.n_outer_grid),
            "var_path": [round(v, 4) for v in self.var_path],
            "es_path": [round(v, 4) for v in self.es_path],
            "var_successive_rel_change": [round(v, 6) for v in self.var_successive_rel_change],
            "es_successive_rel_change": [round(v, 6) for v in self.es_successive_rel_change],
            "converged": self.converged,
            "recommended_n_outer": self.recommended_n_outer,
            "final_var": round(self.final_var, 4),
            "final_es": round(self.final_es, 4),
        }


@dataclass
class BootstrapInterval:
    """Non-parametric bootstrap CI on the 99.5% VaR / ES estimators."""

    n_outer: int
    n_bootstrap: int
    ci_level: float
    var_point: float
    var_ci_low: float
    var_ci_high: float
    var_standard_error: float
    es_point: float
    es_ci_low: float
    es_ci_high: float
    es_standard_error: float

    @property
    def var_ci_rel_halfwidth(self) -> float:
        hw = 0.5 * (self.var_ci_high - self.var_ci_low)
        return _rel(hw, 0.0) if self.var_point == 0 else hw / abs(self.var_point)

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_outer": self.n_outer,
            "n_bootstrap": self.n_bootstrap,
            "ci_level": self.ci_level,
            "var_point": round(self.var_point, 4),
            "var_ci_low": round(self.var_ci_low, 4),
            "var_ci_high": round(self.var_ci_high, 4),
            "var_standard_error": round(self.var_standard_error, 4),
            "var_ci_rel_halfwidth": round(self.var_ci_rel_halfwidth, 6),
            "es_point": round(self.es_point, 4),
            "es_ci_low": round(self.es_ci_low, 4),
            "es_ci_high": round(self.es_ci_high, 4),
            "es_standard_error": round(self.es_standard_error, 4),
        }


@dataclass
class SchemeVariance:
    """VaR-estimator variance for one sampling scheme."""

    scheme: str
    n_outer: int
    n_replications: int
    var_mean: float
    var_std: float
    es_mean: float
    es_std: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "scheme": self.scheme,
            "n_outer": self.n_outer,
            "n_replications": self.n_replications,
            "var_mean": round(self.var_mean, 4),
            "var_std": round(self.var_std, 6),
            "es_mean": round(self.es_mean, 4),
            "es_std": round(self.es_std, 6),
        }


@dataclass
class VarianceReduction:
    """Variance-reduction comparison across sampling schemes."""

    crude: SchemeVariance
    antithetic: SchemeVariance
    sobol: SchemeVariance
    antithetic_var_ratio: float       # Var(crude)/Var(antithetic) on the VaR estimator
    sobol_var_ratio: float
    antithetic_es_ratio: float
    sobol_es_ratio: float
    copula_rho: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "crude": self.crude.to_dict(),
            "antithetic": self.antithetic.to_dict(),
            "sobol": self.sobol.to_dict(),
            "antithetic_var_ratio": round(self.antithetic_var_ratio, 4),
            "sobol_var_ratio": round(self.sobol_var_ratio, 4),
            "antithetic_es_ratio": round(self.antithetic_es_ratio, 4),
            "sobol_es_ratio": round(self.sobol_es_ratio, 4),
            "copula_rho": round(self.copula_rho, 6),
        }


@dataclass
class TailDiagnosticsReport:
    """Full structured Phase 15 Task 4 tail-diagnostics report."""

    config: TailDiagnosticsConfig
    lsmc_summary: Dict[str, object]
    convergence: OuterConvergence
    bootstrap: BootstrapInterval
    variance_reduction: VarianceReduction
    run_id: str
    duration_seconds: float
    verdict: str
    reproducibility_digest: str
    notes: List[str] = field(default_factory=list)
    audit_entry_id: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict,
            "lsmc_summary": self.lsmc_summary,
            "convergence": self.convergence.to_dict(),
            "bootstrap": self.bootstrap.to_dict(),
            "variance_reduction": self.variance_reduction.to_dict(),
            "reproducibility_digest": self.reproducibility_digest,
            "duration_seconds": round(self.duration_seconds, 4),
            "config": self.config.to_dict(),
            "notes": list(self.notes),
            "audit_entry_id": self.audit_entry_id,
            "standards": [
                "SOA ASOP 56 §3.5",
                "SOA ASOP 56 §3.1.3",
                "SOA ASOP 25 §3.3",
                "IA TAS M §3.6",
                "L'Ecuyer (2018) RQMC",
                "Glasserman (2003) §4",
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        c = self.convergence
        b = self.bootstrap
        v = self.variance_reduction
        lines = [
            "# Phase 15 Task 4 — Tail-Convergence & Stability Diagnostics",
            "",
            "**Verdict:** {}".format(self.verdict),
            "",
            "Run `{}` | {} s | digest `{}`".format(
                self.run_id, round(self.duration_seconds, 2),
                self.reproducibility_digest[:12]),
            "",
            "## 1. Outer-count convergence (99.5% VaR / ES)",
            "",
            "| N_outer | VaR | ES | ΔVaR (rel) |",
            "|--------:|----:|---:|-----------:|",
        ]
        changes = (None,) + c.var_successive_rel_change
        for n, var, es, ch in zip(c.n_outer_grid, c.var_path, c.es_path, changes):
            chs = "—" if ch is None else "{:.3%}".format(ch)
            lines.append("| {:,} | {:,.1f} | {:,.1f} | {} |".format(n, var, es, chs))
        lines += [
            "",
            "Converged: **{}** (tol {:.2%}); recommended N_outer ≥ **{:,}**.".format(
                c.converged, self.config.convergence_tol, c.recommended_n_outer),
            "",
            "## 2. Bootstrap {:.0%} CI (N_outer={:,}, B={:,})".format(
                b.ci_level, b.n_outer, b.n_bootstrap),
            "",
            "- VaR {:,.1f}  CI [{:,.1f}, {:,.1f}]  SE {:,.1f}  (±{:.2%} of point)".format(
                b.var_point, b.var_ci_low, b.var_ci_high, b.var_standard_error,
                b.var_ci_rel_halfwidth),
            "- ES  {:,.1f}  CI [{:,.1f}, {:,.1f}]  SE {:,.1f}".format(
                b.es_point, b.es_ci_low, b.es_ci_high, b.es_standard_error),
            "",
            "## 3. Variance reduction (VaR estimator, {} reps × N={:,}, copula ρ={:.3f})".format(
                v.crude.n_replications, v.crude.n_outer, v.copula_rho),
            "",
            "| Scheme | VaR estimator SD | Variance-reduction ratio |",
            "|--------|-----------------:|-------------------------:|",
            "| Crude (pseudo-random) | {:,.2f} | 1.00× |".format(v.crude.var_std),
            "| Antithetic | {:,.2f} | {:.2f}× |".format(v.antithetic.var_std, v.antithetic_var_ratio),
            "| Sobol QMC | {:,.2f} | {:.2f}× |".format(v.sobol.var_std, v.sobol_var_ratio),
            "",
            "## Notes",
            "",
        ]
        lines += ["- {}".format(n) for n in self.notes]
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Pilot-anchored Gaussian-copula surrogate (variance-reduction study only)
# ---------------------------------------------------------------------------

def _correlate(z: np.ndarray, rho: float) -> np.ndarray:
    """Apply a 2x2 Cholesky factor so two standard-normal columns get corr rho."""
    rho = float(np.clip(rho, -0.999, 0.999))
    w0 = z[:, 0]
    w1 = rho * z[:, 0] + np.sqrt(1.0 - rho ** 2) * z[:, 1]
    return np.column_stack([w0, w1])


def _states_from_normals(
    w: np.ndarray, r_pilot_sorted: np.ndarray, s_pilot_sorted: np.ndarray
) -> np.ndarray:
    """Map correlated standard normals to (r, S) via the empirical pilot margins.

    Uses inverse-transform sampling through the pilot order statistics so the
    surrogate reproduces the pilot marginal distributions exactly (no parametric
    margin assumption) while the Gaussian copula injects the correlation.
    """
    u = stats.norm.cdf(w)
    u = np.clip(u, 1e-9, 1.0 - 1e-9)
    r = np.quantile(r_pilot_sorted, u[:, 0])
    s = np.quantile(s_pilot_sorted, u[:, 1])
    return np.column_stack([r, s])


def _draw_normals(scheme: str, n: int, seed: int) -> np.ndarray:
    """Standard-normal driver (n, 2) for a sampling scheme."""
    if scheme == "crude":
        rng = np.random.default_rng(seed)
        return rng.standard_normal((n, 2))
    if scheme == "antithetic":
        rng = np.random.default_rng(seed)
        half = n // 2
        base = rng.standard_normal((half, 2))
        z = np.vstack([base, -base])
        if z.shape[0] < n:                       # odd n (not used by default)
            z = np.vstack([z, rng.standard_normal((n - z.shape[0], 2))])
        return z
    if scheme == "sobol":
        engine = qmc.Sobol(d=2, scramble=True, seed=seed)
        m = int(round(np.log2(n)))
        u = engine.random_base2(m) if (1 << m) == n else engine.random(n)
        u = np.clip(u, 1e-9, 1.0 - 1e-9)
        return stats.norm.ppf(u)
    raise ValueError("unknown scheme {!r}".format(scheme))


def _nearest_correlation_matrix(corr: np.ndarray) -> np.ndarray:
    """Return a positive-definite correlation matrix by eigenvalue clipping."""
    C = np.asarray(corr, dtype=float)
    C = 0.5 * (C + C.T)
    np.fill_diagonal(C, 1.0)
    try:
        np.linalg.cholesky(C)
        return C
    except np.linalg.LinAlgError:
        w, V = np.linalg.eigh(C)
        w = np.clip(w, 1e-8, None)
        C = V @ np.diag(w) @ V.T
        d = np.sqrt(np.diag(C))
        C = C / np.outer(d, d)
        np.fill_diagonal(C, 1.0)
        return C


def _correlate_nd(z: np.ndarray, corr: np.ndarray) -> np.ndarray:
    """Apply a Cholesky factor to standard normals for an arbitrary dimension."""
    C = _nearest_correlation_matrix(corr)
    return np.asarray(z, dtype=float) @ np.linalg.cholesky(C).T


def _states_from_normals_nd(w: np.ndarray, pilot_sorted: Tuple[np.ndarray, ...]) -> np.ndarray:
    """Map correlated normals to empirical pilot margins dimension-by-dimension."""
    w = np.asarray(w, dtype=float)
    if w.ndim != 2 or w.shape[1] != len(pilot_sorted):
        raise ValueError("normal driver dimension does not match pilot margins")
    u = np.clip(stats.norm.cdf(w), 1e-9, 1.0 - 1e-9)
    cols = [
        np.quantile(np.asarray(pilot_sorted[j], dtype=float), u[:, j])
        for j in range(w.shape[1])
    ]
    return np.column_stack(cols)


def _draw_normals_nd(scheme: str, n: int, dim: int, seed: int) -> np.ndarray:
    """Standard-normal driver (n, dim) for crude, antithetic, or Sobol schemes."""
    if dim <= 0:
        raise ValueError("dim must be positive")
    if scheme == "crude":
        rng = np.random.default_rng(seed)
        return rng.standard_normal((n, dim))
    if scheme == "antithetic":
        rng = np.random.default_rng(seed)
        half = n // 2
        base = rng.standard_normal((half, dim))
        z = np.vstack([base, -base])
        if z.shape[0] < n:
            z = np.vstack([z, rng.standard_normal((n - z.shape[0], dim))])
        return z
    if scheme == "sobol":
        engine = qmc.Sobol(d=dim, scramble=True, seed=seed)
        m = int(round(np.log2(n)))
        u = engine.random_base2(m) if (1 << m) == n else engine.random(n)
        return stats.norm.ppf(np.clip(u, 1e-9, 1.0 - 1e-9))
    raise ValueError("unknown scheme {!r}".format(scheme))


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class MultiDriverTailDiagnostics:
    """Convergence, bootstrap-CI, and variance-reduction diagnostics for the
    multi-driver 99.5% capital metric, built on the Task 1 LSMC surface."""

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.annual_qx_fn = annual_qx_fn

    # -- fitted surface -----------------------------------------------------
    def _fit_surface(self, cfg: TailDiagnosticsConfig) -> MultiDriverLSMCResult:
        engine = MultiDriverLSMCProxyEngine(
            self.product,
            hw_params=self.hw_params,
            gbm_params=self.gbm_params,
            initial_curve=self.initial_curve,
            equity_guarantee=self.equity_guarantee,
            capital_horizon_months=cfg.capital_horizon_months,
            confidence_level=cfg.confidence_level,
            outer_measure=cfg.outer_measure,
            degree=cfg.lsmc_degree,
            annual_qx_fn=self.annual_qx_fn,
        )
        # Small evaluation set — we re-evaluate the surface ourselves below.
        return engine.fit_and_run(n_fit=cfg.n_fit, n_outer_eval=1_000, seed=cfg.seed)

    def _outer_liabilities(
        self, surface: MultiDriverLSMCResult, n_outer: int, cfg: TailDiagnosticsConfig, seed: int
    ) -> np.ndarray:
        states = _outer_states_2d(
            n_outer, cfg.capital_horizon_months, cfg.outer_measure,
            self.hw_params, self.gbm_params, self.initial_curve, seed,
        )
        return surface.predict(states)

    # -- 1. convergence -----------------------------------------------------
    def _convergence(
        self, surface: MultiDriverLSMCResult, cfg: TailDiagnosticsConfig
    ) -> OuterConvergence:
        var_path: List[float] = []
        es_path: List[float] = []
        for k, n in enumerate(cfg.outer_grid):
            liab = self._outer_liabilities(surface, n, cfg, seed=cfg.seed + 1_000 + 7 * k)
            var, es = _var_es(liab, cfg.confidence_level)
            var_path.append(var)
            es_path.append(es)
        var_chg = tuple(_rel(var_path[i], var_path[i - 1]) for i in range(1, len(var_path)))
        es_chg = tuple(_rel(es_path[i], es_path[i - 1]) for i in range(1, len(es_path)))

        recommended = cfg.outer_grid[-1]
        converged = bool(var_chg and var_chg[-1] <= cfg.convergence_tol)
        for i, ch in enumerate(var_chg):
            if ch <= cfg.convergence_tol:
                recommended = cfg.outer_grid[i + 1]
                break
        return OuterConvergence(
            n_outer_grid=tuple(cfg.outer_grid),
            var_path=tuple(var_path), es_path=tuple(es_path),
            var_successive_rel_change=var_chg, es_successive_rel_change=es_chg,
            converged=converged, recommended_n_outer=int(recommended),
            final_var=var_path[-1], final_es=es_path[-1],
        )

    # -- 2. bootstrap CI ----------------------------------------------------
    def _bootstrap(
        self, surface: MultiDriverLSMCResult, cfg: TailDiagnosticsConfig
    ) -> BootstrapInterval:
        liab = self._outer_liabilities(
            surface, cfg.bootstrap_n_outer, cfg, seed=cfg.seed + 500
        )
        n = liab.size
        var_pt, es_pt = _var_es(liab, cfg.confidence_level)
        rng = np.random.default_rng(cfg.seed + 999)
        var_bs = np.empty(cfg.n_bootstrap, dtype=float)
        es_bs = np.empty(cfg.n_bootstrap, dtype=float)
        for b in range(cfg.n_bootstrap):
            idx = rng.integers(0, n, n)
            var_bs[b], es_bs[b] = _var_es(liab[idx], cfg.confidence_level)
        alpha = 1.0 - cfg.bootstrap_ci_level
        lo_q, hi_q = alpha / 2.0, 1.0 - alpha / 2.0
        return BootstrapInterval(
            n_outer=n, n_bootstrap=cfg.n_bootstrap, ci_level=cfg.bootstrap_ci_level,
            var_point=var_pt,
            var_ci_low=float(np.quantile(var_bs, lo_q)),
            var_ci_high=float(np.quantile(var_bs, hi_q)),
            var_standard_error=float(var_bs.std(ddof=1)),
            es_point=es_pt,
            es_ci_low=float(np.quantile(es_bs, lo_q)),
            es_ci_high=float(np.quantile(es_bs, hi_q)),
            es_standard_error=float(es_bs.std(ddof=1)),
        )

    # -- 3. variance reduction ---------------------------------------------
    def _variance_reduction(
        self, surface: MultiDriverLSMCResult, cfg: TailDiagnosticsConfig
    ) -> VarianceReduction:
        # Pilot run of the governed outer model -> empirical copula margins.
        pilot = _outer_states_2d(
            cfg.vr_pilot_n, cfg.capital_horizon_months, cfg.outer_measure,
            self.hw_params, self.gbm_params, self.initial_curve, seed=cfg.seed + 321,
        )
        r_sorted = np.sort(pilot[:, 0])
        s_sorted = np.sort(pilot[:, 1])
        rho = float(np.corrcoef(pilot[:, 0], pilot[:, 1])[0, 1])
        if not np.isfinite(rho):
            rho = 0.0

        def scheme_stats(scheme: str) -> SchemeVariance:
            vars_, ess_ = [], []
            for rep in range(cfg.vr_replications):
                z = _draw_normals(scheme, cfg.vr_n_outer, seed=cfg.seed + 10_000 + rep)
                w = _correlate(z, rho)
                states = _states_from_normals(w, r_sorted, s_sorted)
                liab = surface.predict(states)
                var, es = _var_es(liab, cfg.confidence_level)
                vars_.append(var)
                ess_.append(es)
            vars_ = np.asarray(vars_)
            ess_ = np.asarray(ess_)
            return SchemeVariance(
                scheme=scheme, n_outer=cfg.vr_n_outer, n_replications=cfg.vr_replications,
                var_mean=float(vars_.mean()), var_std=float(vars_.std(ddof=1)),
                es_mean=float(ess_.mean()), es_std=float(ess_.std(ddof=1)),
            )

        crude = scheme_stats("crude")
        anti = scheme_stats("antithetic")
        sob = scheme_stats("sobol")

        def ratio(base: float, other: float) -> float:
            return float((base ** 2) / (other ** 2)) if other > 1e-12 else float("inf")

        return VarianceReduction(
            crude=crude, antithetic=anti, sobol=sob,
            antithetic_var_ratio=ratio(crude.var_std, anti.var_std),
            sobol_var_ratio=ratio(crude.var_std, sob.var_std),
            antithetic_es_ratio=ratio(crude.es_std, anti.es_std),
            sobol_es_ratio=ratio(crude.es_std, sob.es_std),
            copula_rho=rho,
        )

    # -- orchestration ------------------------------------------------------
    def run(
        self,
        config: Optional[TailDiagnosticsConfig] = None,
        governance_store: Optional[object] = None,
        actor: str = "MultiDriverTailDiagnostics",
        phase: str = "Phase 15: Multi-Risk Economic Capital and Proxy-Model Validation",
    ) -> TailDiagnosticsReport:
        cfg = config or TailDiagnosticsConfig()
        if cfg.capital_horizon_months >= self.product.term_months:
            raise ValueError("capital_horizon_months must be less than product term")

        t0 = time.monotonic()
        run_id = "md-tail-" + uuid.uuid4().hex[:8]

        surface = self._fit_surface(cfg)
        convergence = self._convergence(surface, cfg)
        bootstrap = self._bootstrap(surface, cfg)
        vr = self._variance_reduction(surface, cfg)

        notes: List[str] = [
            "Outer-count convergence and the bootstrap CI use the GOVERNED outer "
            "states (ScenarioSet.generate) with the once-fitted LSMC surface; "
            "they isolate outer Monte-Carlo (sampling) error, not proxy error.",
            "Proxy error is bounded separately by the Task 1 proxy-vs-nested "
            "(R^2=0.9936) and Task 2 out-of-sample reports.",
            "The variance-reduction study uses a pilot-anchored Gaussian copula "
            "(governed ESG rho; empirical pilot margins) so crude / antithetic / "
            "Sobol target an identical distribution and the ratio is like-for-like.",
            "Antithetic uses negated normal pairs; Sobol uses a scrambled base-2 "
            "sequence (n is a power of two for exact balance).",
        ]
        verdict = self._verdict(cfg, convergence, bootstrap, vr, notes)

        digest = hashlib.sha256(
            np.round(
                np.concatenate([
                    np.asarray(convergence.var_path, dtype=float),
                    np.asarray(convergence.es_path, dtype=float),
                    np.array([bootstrap.var_point, bootstrap.es_point,
                              bootstrap.var_standard_error, bootstrap.es_standard_error],
                             dtype=float),
                    np.array([vr.crude.var_std, vr.antithetic.var_std, vr.sobol.var_std,
                              vr.copula_rho], dtype=float),
                ]),
                6,
            ).tobytes()
        ).hexdigest()

        duration = time.monotonic() - t0
        audit_entry_id = None
        if governance_store is not None:
            try:
                from par_model_v2.governance.audit_trail import AuditEntry

                entry = AuditEntry.model_run(
                    actor=actor, phase=phase, run_id=run_id,
                    scenario_count=cfg.outer_grid[-1] + cfg.bootstrap_n_outer
                    + cfg.vr_replications * cfg.vr_n_outer,
                    duration_seconds=round(duration, 4),
                    outcome=verdict.split()[0],
                    files_changed=[
                        "par_model_v2/projection/multi_driver_tail_diagnostics.py"
                    ],
                    test_summary=(
                        "VaR{:.1f}%={:.1f}; converged={}; rec_N>={}; CI=[{:.1f},{:.1f}]; "
                        "SE={:.1f}; anti_ratio={:.2f}; sobol_ratio={:.2f}".format(
                            cfg.confidence_level * 100, convergence.final_var,
                            convergence.converged, convergence.recommended_n_outer,
                            bootstrap.var_ci_low, bootstrap.var_ci_high,
                            bootstrap.var_standard_error,
                            vr.antithetic_var_ratio, vr.sobol_var_ratio)
                    ),
                )
                governance_store.audit_trail.append(entry)
                audit_entry_id = entry.entry_id
            except Exception as exc:  # pragma: no cover - governance optional
                notes.append("Governance audit append skipped: {}".format(exc))

        return TailDiagnosticsReport(
            config=cfg, lsmc_summary=surface.summary(),
            convergence=convergence, bootstrap=bootstrap, variance_reduction=vr,
            run_id=run_id, duration_seconds=duration, verdict=verdict,
            reproducibility_digest=digest, notes=notes, audit_entry_id=audit_entry_id,
        )

    @staticmethod
    def _verdict(
        cfg: TailDiagnosticsConfig,
        convergence: OuterConvergence,
        bootstrap: BootstrapInterval,
        vr: VarianceReduction,
        notes: List[str],
    ) -> str:
        var_in_ci = bootstrap.var_ci_low <= convergence.final_var <= bootstrap.var_ci_high
        # Variance-reduction objective: demonstrate that an effective scheme
        # exists for the 99.5% estimator. QMC is the relevant scheme for a
        # smooth low-dimensional integrand; antithetic variates are known to be
        # ineffective for an extreme order statistic (they decorrelate the mean,
        # not the tail quantile), so a ratio ~1 there is expected, not a defect.
        best_ratio = max(vr.antithetic_var_ratio, vr.sobol_var_ratio)
        checks = [
            convergence.converged,
            var_in_ci,
            best_ratio > 1.0,
        ]
        if not convergence.converged:
            notes.append("99.5% VaR not converged within outer_grid; extend N_outer.")
        if not var_in_ci:
            notes.append("Convergence VaR lies outside the bootstrap CI (independent samples); review.")
        if vr.antithetic_var_ratio < 1.0:
            notes.append(
                "Antithetic variates do not reduce the 99.5% VaR-estimator variance "
                "(ratio {:.2f}<1) — expected for an extreme quantile; QMC is the "
                "effective scheme here (ratio {:.2f}).".format(
                    vr.antithetic_var_ratio, vr.sobol_var_ratio))
        if vr.sobol_var_ratio < 1.0:
            notes.append("Sobol QMC did not reduce VaR-estimator variance for this surface.")
        if all(checks):
            return "PASS - 99.5% capital metric converges, is bounded by a bootstrap CI, and benefits from variance reduction"
        return "PARTIAL - tail diagnostics generated with review items"


# ---------------------------------------------------------------------------
# Model-use restrictions (governance disclosure)
# ---------------------------------------------------------------------------

def tail_diagnostics_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the tail-diagnostics module.

    SOA ASOP 56 §3.5.1; IA TAS M §3.6.
    """
    return {
        "module": "par_model_v2/projection/multi_driver_tail_diagnostics.py",
        "classification": "EDUCATIONAL ONLY — NOT a regulatory capital model",
        "scope": (
            "Quantifies the OUTER Monte-Carlo (sampling) uncertainty of the "
            "99.5% VaR/ES of the two-driver (rate+equity) liability via the "
            "once-fitted Task 1 LSMC surface: outer-count convergence, a "
            "non-parametric bootstrap CI, and a crude/antithetic/Sobol "
            "variance-reduction comparison."
        ),
        "what_it_does_NOT_cover": (
            "Proxy (LSMC fit) error — bounded separately by Task 1 "
            "proxy-vs-nested and Task 2 out-of-sample validation; and all risk "
            "drivers beyond rates+equity (lapse, credit, mortality trend, FX)."
        ),
        "variance_reduction_surrogate": (
            "The variance-reduction ratios are measured on a pilot-anchored "
            "Gaussian-copula surrogate of the horizon state (governed ESG rho; "
            "empirical pilot margins) — the controllable normal/uniform driver "
            "that antithetic and QMC require. Convergence and bootstrap use the "
            "real governed outer states. Ratios are indicative of relative "
            "estimator efficiency, not an absolute capital figure."
        ),
        "placeholder_parameters": (
            "HW1F and GBM parameters are illustrative placeholders; capital "
            "magnitudes are NOT calibrated."
        ),
        "governance": (
            "Independent APS X2 review pending; production sign-off withheld. "
            "Use only for education, methodology demonstration, and testing."
        ),
        "standards": [
            "SOA ASOP 56 §3.1.3", "SOA ASOP 56 §3.5", "SOA ASOP 25 §3.3",
            "IA TAS M §3.6", "L'Ecuyer (2018) RQMC", "Glasserman (2003) §4",
        ],
    }


def tail_diagnostics_use_restrictions_json() -> str:
    return json.dumps(tail_diagnostics_use_restrictions(), indent=2, sort_keys=True)


__all__ = [
    "DEFAULT_OUTER_GRID",
    "DEFAULT_CONVERGENCE_TOL",
    "DEFAULT_N_BOOTSTRAP",
    "DEFAULT_BOOTSTRAP_N_OUTER",
    "DEFAULT_VR_REPLICATIONS",
    "DEFAULT_VR_N_OUTER",
    "DEFAULT_VR_PILOT_N",
    "TailDiagnosticsConfig",
    "OuterConvergence",
    "BootstrapInterval",
    "SchemeVariance",
    "VarianceReduction",
    "TailDiagnosticsReport",
    "MultiDriverTailDiagnostics",
    "tail_diagnostics_use_restrictions",
    "tail_diagnostics_use_restrictions_json",
    "_var_es",
    "_draw_normals",
    "_correlate",
    "_states_from_normals",
]


# ===========================================================================
# Phase 17 Task 4 — THREE-DRIVER (rate + equity + credit spread) tail diagnostics
# ===========================================================================
#
# Additive extension of the Phase 15 Task 4 two-driver diagnostics above to the
# Phase 17 Task 1 trivariate (r, S, s) LSMC capital surface
# (:class:`ThreeDriverLSMCProxyEngine`).  Same three diagnostics — outer-count
# convergence, non-parametric bootstrap CI, and a crude/antithetic/Sobol
# variance-reduction comparison — now over the credit-augmented liability, with
# the governed 3x3 ESG correlation carried through the convergence/bootstrap
# (real governed outer states) and the variance-reduction surrogate (pilot-
# anchored Gaussian copula with the realised 3x3 outer-state correlation and
# empirical pilot margins).  SOA ASOP 56 §3.5/§3.1.3; SOA ASOP 25 §3.3;
# IA TAS M §3.6.  EDUCATIONAL ONLY — placeholder parameters; APS X2 pending.


@dataclass
class ThreeDriverTailConfig:
    """Configuration for the Phase 17 Task 4 three-driver tail-diagnostics run."""

    n_fit: int = 1_500
    lsmc_degree: int = 2
    max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS
    outer_measure: Measure = Measure.P
    seed: int = 42

    outer_grid: Tuple[int, ...] = DEFAULT_OUTER_GRID
    convergence_tol: float = DEFAULT_CONVERGENCE_TOL

    n_bootstrap: int = DEFAULT_N_BOOTSTRAP
    bootstrap_n_outer: int = DEFAULT_BOOTSTRAP_N_OUTER
    bootstrap_ci_level: float = 0.95

    vr_replications: int = DEFAULT_VR_REPLICATIONS
    vr_n_outer: int = DEFAULT_VR_N_OUTER
    vr_pilot_n: int = DEFAULT_VR_PILOT_N

    def __post_init__(self) -> None:
        if self.n_fit < 50:
            raise ValueError("n_fit must be >= 50")
        if self.lsmc_degree < 1:
            raise ValueError("lsmc_degree must be >= 1")
        if self.max_interaction_order < 0:
            raise ValueError("max_interaction_order must be >= 0")
        if not (0.5 < self.confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0.5, 1.0)")
        if self.capital_horizon_months <= 0:
            raise ValueError("capital_horizon_months must be positive")
        if len(self.outer_grid) < 2:
            raise ValueError("outer_grid must contain at least two sizes")
        if any(n <= 0 for n in self.outer_grid):
            raise ValueError("outer_grid sizes must be positive")
        if list(self.outer_grid) != sorted(self.outer_grid):
            raise ValueError("outer_grid must be ascending")
        if self.convergence_tol <= 0:
            raise ValueError("convergence_tol must be positive")
        if self.n_bootstrap < 100:
            raise ValueError("n_bootstrap must be >= 100")
        if self.bootstrap_n_outer < 100:
            raise ValueError("bootstrap_n_outer must be >= 100")
        if not (0.5 < self.bootstrap_ci_level < 1.0):
            raise ValueError("bootstrap_ci_level must be in (0.5, 1.0)")
        if self.vr_replications < 10:
            raise ValueError("vr_replications must be >= 10")
        if self.vr_n_outer < 64 or (self.vr_n_outer & (self.vr_n_outer - 1)) != 0:
            raise ValueError("vr_n_outer must be a power of two >= 64")
        if self.vr_pilot_n < 200:
            raise ValueError("vr_pilot_n must be >= 200")
        self.outer_measure = Measure(self.outer_measure)
        self.outer_grid = tuple(int(n) for n in self.outer_grid)

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_fit": self.n_fit,
            "lsmc_degree": self.lsmc_degree,
            "max_interaction_order": self.max_interaction_order,
            "confidence_level": self.confidence_level,
            "capital_horizon_months": self.capital_horizon_months,
            "outer_measure": self.outer_measure.value,
            "seed": self.seed,
            "outer_grid": list(self.outer_grid),
            "convergence_tol": self.convergence_tol,
            "n_bootstrap": self.n_bootstrap,
            "bootstrap_n_outer": self.bootstrap_n_outer,
            "bootstrap_ci_level": self.bootstrap_ci_level,
            "vr_replications": self.vr_replications,
            "vr_n_outer": self.vr_n_outer,
            "vr_pilot_n": self.vr_pilot_n,
        }


@dataclass
class VarianceReduction3D:
    """Variance-reduction comparison across sampling schemes (three drivers).

    Identical structure to :class:`VarianceReduction` except the copula is now
    three-dimensional, so the controlling correlation is the realised 3x3
    outer-state correlation matrix (rate, equity, credit-spread) rather than a
    single scalar rho.
    """

    crude: SchemeVariance
    antithetic: SchemeVariance
    sobol: SchemeVariance
    antithetic_var_ratio: float
    sobol_var_ratio: float
    antithetic_es_ratio: float
    sobol_es_ratio: float
    copula_corr: Tuple[Tuple[float, ...], ...]   # realised 3x3 outer-state corr

    def to_dict(self) -> Dict[str, object]:
        return {
            "crude": self.crude.to_dict(),
            "antithetic": self.antithetic.to_dict(),
            "sobol": self.sobol.to_dict(),
            "antithetic_var_ratio": round(self.antithetic_var_ratio, 4),
            "sobol_var_ratio": round(self.sobol_var_ratio, 4),
            "antithetic_es_ratio": round(self.antithetic_es_ratio, 4),
            "sobol_es_ratio": round(self.sobol_es_ratio, 4),
            "copula_corr": [[round(x, 6) for x in row] for row in self.copula_corr],
        }


@dataclass
class ThreeDriverTailReport:
    """Full structured Phase 17 Task 4 three-driver tail-diagnostics report."""

    config: ThreeDriverTailConfig
    lsmc_summary: Dict[str, object]
    convergence: OuterConvergence
    bootstrap: BootstrapInterval
    variance_reduction: VarianceReduction3D
    run_id: str
    duration_seconds: float
    verdict: str
    reproducibility_digest: str
    drivers: Tuple[str, ...] = ("short_rate", "equity_level", "credit_spread")
    notes: List[str] = field(default_factory=list)
    audit_entry_id: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict,
            "drivers": list(self.drivers),
            "lsmc_summary": self.lsmc_summary,
            "convergence": self.convergence.to_dict(),
            "bootstrap": self.bootstrap.to_dict(),
            "variance_reduction": self.variance_reduction.to_dict(),
            "reproducibility_digest": self.reproducibility_digest,
            "duration_seconds": round(self.duration_seconds, 4),
            "config": self.config.to_dict(),
            "notes": list(self.notes),
            "audit_entry_id": self.audit_entry_id,
            "standards": [
                "SOA ASOP 56 §3.5",
                "SOA ASOP 56 §3.1.3",
                "SOA ASOP 25 §3.3",
                "IA TAS M §3.6",
                "L'Ecuyer (2018) RQMC",
                "Glasserman (2003) §4",
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        c = self.convergence
        b = self.bootstrap
        v = self.variance_reduction
        lines = [
            "# Phase 17 Task 4 — Three-Driver Tail-Convergence & Stability Diagnostics",
            "",
            "**Drivers:** {}".format(", ".join(self.drivers)),
            "",
            "**Verdict:** {}".format(self.verdict),
            "",
            "Run `{}` | {} s | digest `{}`".format(
                self.run_id, round(self.duration_seconds, 2),
                self.reproducibility_digest[:12]),
            "",
            "## 1. Outer-count convergence (99.5% VaR / ES)",
            "",
            "| N_outer | VaR | ES | ΔVaR (rel) |",
            "|--------:|----:|---:|-----------:|",
        ]
        changes = (None,) + c.var_successive_rel_change
        for n, var, es, ch in zip(c.n_outer_grid, c.var_path, c.es_path, changes):
            chs = "—" if ch is None else "{:.3%}".format(ch)
            lines.append("| {:,} | {:,.1f} | {:,.1f} | {} |".format(n, var, es, chs))
        lines += [
            "",
            "Converged: **{}** (tol {:.2%}); recommended N_outer ≥ **{:,}**.".format(
                c.converged, self.config.convergence_tol, c.recommended_n_outer),
            "",
            "## 2. Bootstrap {:.0%} CI (N_outer={:,}, B={:,})".format(
                b.ci_level, b.n_outer, b.n_bootstrap),
            "",
            "- VaR {:,.1f}  CI [{:,.1f}, {:,.1f}]  SE {:,.1f}  (±{:.2%} of point)".format(
                b.var_point, b.var_ci_low, b.var_ci_high, b.var_standard_error,
                b.var_ci_rel_halfwidth),
            "- ES  {:,.1f}  CI [{:,.1f}, {:,.1f}]  SE {:,.1f}".format(
                b.es_point, b.es_ci_low, b.es_ci_high, b.es_standard_error),
            "",
            "## 3. Variance reduction (VaR estimator, {} reps × N={:,})".format(
                v.crude.n_replications, v.crude.n_outer),
            "",
            "Copula correlation (realised 3x3 outer-state, rate/equity/credit): {}".format(
                v.copula_corr),
            "",
            "| Scheme | VaR estimator SD | Variance-reduction ratio |",
            "|--------|-----------------:|-------------------------:|",
            "| Crude (pseudo-random) | {:,.2f} | 1.00× |".format(v.crude.var_std),
            "| Antithetic | {:,.2f} | {:.2f}× |".format(v.antithetic.var_std, v.antithetic_var_ratio),
            "| Sobol QMC | {:,.2f} | {:.2f}× |".format(v.sobol.var_std, v.sobol_var_ratio),
            "",
            "## Notes",
            "",
        ]
        lines += ["- {}".format(n) for n in self.notes]
        return "\n".join(lines) + "\n"


class ThreeDriverTailDiagnostics:
    """Convergence, bootstrap-CI, and variance-reduction diagnostics for the
    THREE-driver (rate + equity + credit-spread) 99.5% capital metric, built on
    the Phase 17 Task 1 trivariate LSMC surface (additive; no existing file
    touched)."""

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        spread_params: Optional[CreditSpreadParams] = None,
        correlation: Optional[ThreeDriverCorrelation] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        credit_exposure: Optional[CreditExposureSpec] = None,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.spread_params = spread_params if spread_params is not None else CreditSpreadParams()
        self.correlation = correlation if correlation is not None else ThreeDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.annual_qx_fn = annual_qx_fn

    # -- fitted surface -----------------------------------------------------
    def _fit_surface(self, cfg: ThreeDriverTailConfig) -> ThreeDriverLSMCResult:
        engine = ThreeDriverLSMCProxyEngine(
            self.product,
            hw_params=self.hw_params,
            gbm_params=self.gbm_params,
            spread_params=self.spread_params,
            correlation=self.correlation,
            initial_curve=self.initial_curve,
            equity_guarantee=self.equity_guarantee,
            credit_exposure=self.credit_exposure,
            capital_horizon_months=cfg.capital_horizon_months,
            confidence_level=cfg.confidence_level,
            outer_measure=cfg.outer_measure,
            degree=cfg.lsmc_degree,
            max_interaction_order=cfg.max_interaction_order,
            annual_qx_fn=self.annual_qx_fn,
        )
        return engine.fit_and_run(n_fit=cfg.n_fit, n_outer_eval=1_000, seed=cfg.seed)

    def _outer_states(
        self, n_outer: int, cfg: ThreeDriverTailConfig, seed: int
    ) -> np.ndarray:
        return _outer_states_3d(
            n_outer, cfg.capital_horizon_months, cfg.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params,
            self.correlation, self.initial_curve, seed,
        )

    def _outer_liabilities(
        self, surface: ThreeDriverLSMCResult, n_outer: int,
        cfg: ThreeDriverTailConfig, seed: int,
    ) -> np.ndarray:
        return surface.predict(self._outer_states(n_outer, cfg, seed))

    # -- 1. convergence -----------------------------------------------------
    def _convergence(
        self, surface: ThreeDriverLSMCResult, cfg: ThreeDriverTailConfig
    ) -> OuterConvergence:
        var_path: List[float] = []
        es_path: List[float] = []
        for k, n in enumerate(cfg.outer_grid):
            liab = self._outer_liabilities(surface, n, cfg, seed=cfg.seed + 1_000 + 7 * k)
            var, es = _var_es(liab, cfg.confidence_level)
            var_path.append(var)
            es_path.append(es)
        var_chg = tuple(_rel(var_path[i], var_path[i - 1]) for i in range(1, len(var_path)))
        es_chg = tuple(_rel(es_path[i], es_path[i - 1]) for i in range(1, len(es_path)))

        recommended = cfg.outer_grid[-1]
        converged = bool(var_chg and var_chg[-1] <= cfg.convergence_tol)
        for i, ch in enumerate(var_chg):
            if ch <= cfg.convergence_tol:
                recommended = cfg.outer_grid[i + 1]
                break
        return OuterConvergence(
            n_outer_grid=tuple(cfg.outer_grid),
            var_path=tuple(var_path), es_path=tuple(es_path),
            var_successive_rel_change=var_chg, es_successive_rel_change=es_chg,
            converged=converged, recommended_n_outer=int(recommended),
            final_var=var_path[-1], final_es=es_path[-1],
        )

    # -- 2. bootstrap CI ----------------------------------------------------
    def _bootstrap(
        self, surface: ThreeDriverLSMCResult, cfg: ThreeDriverTailConfig
    ) -> BootstrapInterval:
        liab = self._outer_liabilities(
            surface, cfg.bootstrap_n_outer, cfg, seed=cfg.seed + 500
        )
        n = liab.size
        var_pt, es_pt = _var_es(liab, cfg.confidence_level)
        rng = np.random.default_rng(cfg.seed + 999)
        var_bs = np.empty(cfg.n_bootstrap, dtype=float)
        es_bs = np.empty(cfg.n_bootstrap, dtype=float)
        for b in range(cfg.n_bootstrap):
            idx = rng.integers(0, n, n)
            var_bs[b], es_bs[b] = _var_es(liab[idx], cfg.confidence_level)
        alpha = 1.0 - cfg.bootstrap_ci_level
        lo_q, hi_q = alpha / 2.0, 1.0 - alpha / 2.0
        return BootstrapInterval(
            n_outer=n, n_bootstrap=cfg.n_bootstrap, ci_level=cfg.bootstrap_ci_level,
            var_point=var_pt,
            var_ci_low=float(np.quantile(var_bs, lo_q)),
            var_ci_high=float(np.quantile(var_bs, hi_q)),
            var_standard_error=float(var_bs.std(ddof=1)),
            es_point=es_pt,
            es_ci_low=float(np.quantile(es_bs, lo_q)),
            es_ci_high=float(np.quantile(es_bs, hi_q)),
            es_standard_error=float(es_bs.std(ddof=1)),
        )

    # -- 3. variance reduction ---------------------------------------------
    def _variance_reduction(
        self, surface: ThreeDriverLSMCResult, cfg: ThreeDriverTailConfig
    ) -> VarianceReduction3D:
        pilot = self._outer_states(cfg.vr_pilot_n, cfg, seed=cfg.seed + 321)
        margins = tuple(np.sort(pilot[:, j]) for j in range(3))
        corr = np.corrcoef(pilot, rowvar=False)
        if not np.all(np.isfinite(corr)):
            corr = np.eye(3)
        corr = _nearest_correlation_matrix(corr)

        def scheme_stats(scheme: str) -> SchemeVariance:
            vars_, ess_ = [], []
            for rep in range(cfg.vr_replications):
                z = _draw_normals_nd(scheme, cfg.vr_n_outer, 3, seed=cfg.seed + 10_000 + rep)
                w = _correlate_nd(z, corr)
                states = _states_from_normals_nd(w, margins)
                liab = surface.predict(states)
                var, es = _var_es(liab, cfg.confidence_level)
                vars_.append(var)
                ess_.append(es)
            vars_ = np.asarray(vars_)
            ess_ = np.asarray(ess_)
            return SchemeVariance(
                scheme=scheme, n_outer=cfg.vr_n_outer, n_replications=cfg.vr_replications,
                var_mean=float(vars_.mean()), var_std=float(vars_.std(ddof=1)),
                es_mean=float(ess_.mean()), es_std=float(ess_.std(ddof=1)),
            )

        crude = scheme_stats("crude")
        anti = scheme_stats("antithetic")
        sob = scheme_stats("sobol")

        def ratio(base: float, other: float) -> float:
            return float((base ** 2) / (other ** 2)) if other > 1e-12 else float("inf")

        return VarianceReduction3D(
            crude=crude, antithetic=anti, sobol=sob,
            antithetic_var_ratio=ratio(crude.var_std, anti.var_std),
            sobol_var_ratio=ratio(crude.var_std, sob.var_std),
            antithetic_es_ratio=ratio(crude.es_std, anti.es_std),
            sobol_es_ratio=ratio(crude.es_std, sob.es_std),
            copula_corr=tuple(tuple(float(x) for x in row) for row in np.round(corr, 6)),
        )

    # -- orchestration ------------------------------------------------------
    def run(
        self,
        config: Optional[ThreeDriverTailConfig] = None,
        governance_store: Optional[object] = None,
        actor: str = "ThreeDriverTailDiagnostics",
        phase: str = "Phase 17: Third Risk Driver (Credit Spread) in the Economic-Capital Proxy",
    ) -> ThreeDriverTailReport:
        cfg = config or ThreeDriverTailConfig()
        if cfg.capital_horizon_months >= self.product.term_months:
            raise ValueError("capital_horizon_months must be less than product term")

        t0 = time.monotonic()
        run_id = "td3-tail-" + uuid.uuid4().hex[:8]

        surface = self._fit_surface(cfg)
        convergence = self._convergence(surface, cfg)
        bootstrap = self._bootstrap(surface, cfg)
        vr = self._variance_reduction(surface, cfg)

        notes: List[str] = [
            "Three-driver (rate+equity+credit) extension of the Phase 15 Task 4 "
            "two-driver tail diagnostics; built on the Phase 17 Task 1 trivariate "
            "LSMC surface (no Task 1/2/3 module modified).",
            "Outer-count convergence and the bootstrap CI use the GOVERNED 3-factor "
            "correlated outer states (_outer_states_3d) with the once-fitted LSMC "
            "surface; they isolate outer Monte-Carlo (sampling) error, not proxy error.",
            "Proxy error is bounded separately by the Phase 17 Task 1 proxy-vs-nested "
            "(R^2=0.964) and Task 2 out-of-sample (OOS R^2=0.9751) reports.",
            "The variance-reduction study uses a pilot-anchored Gaussian copula whose "
            "controlling correlation is the realised 3x3 outer-state correlation "
            "(rate/equity/credit) and whose margins are the empirical pilot margins, "
            "so crude / antithetic / Sobol target an identical distribution and the "
            "ratio is like-for-like.",
            "Antithetic uses negated normal triples; Sobol uses a scrambled base-2 "
            "sequence in 3 dimensions (n is a power of two for exact balance).",
        ]
        verdict = self._verdict(cfg, convergence, bootstrap, vr, notes)

        digest = hashlib.sha256(
            np.round(
                np.concatenate([
                    np.asarray(convergence.var_path, dtype=float),
                    np.asarray(convergence.es_path, dtype=float),
                    np.array([bootstrap.var_point, bootstrap.es_point,
                              bootstrap.var_standard_error, bootstrap.es_standard_error],
                             dtype=float),
                    np.array([vr.crude.var_std, vr.antithetic.var_std, vr.sobol.var_std],
                             dtype=float),
                    np.asarray(vr.copula_corr, dtype=float).reshape(-1),
                ]),
                6,
            ).tobytes()
        ).hexdigest()

        duration = time.monotonic() - t0
        audit_entry_id = None
        if governance_store is not None:
            try:
                from par_model_v2.governance.audit_trail import AuditEntry

                entry = AuditEntry.model_run(
                    actor=actor, phase=phase, run_id=run_id,
                    scenario_count=cfg.outer_grid[-1] + cfg.bootstrap_n_outer
                    + cfg.vr_replications * cfg.vr_n_outer,
                    duration_seconds=round(duration, 4),
                    outcome=verdict.split()[0],
                    files_changed=[
                        "par_model_v2/projection/multi_driver_tail_diagnostics.py"
                    ],
                    test_summary=(
                        "3D VaR{:.1f}%={:.1f}; converged={}; rec_N>={}; CI=[{:.1f},{:.1f}]; "
                        "SE={:.1f}; anti_ratio={:.2f}; sobol_ratio={:.2f}".format(
                            cfg.confidence_level * 100, convergence.final_var,
                            convergence.converged, convergence.recommended_n_outer,
                            bootstrap.var_ci_low, bootstrap.var_ci_high,
                            bootstrap.var_standard_error,
                            vr.antithetic_var_ratio, vr.sobol_var_ratio)
                    ),
                )
                governance_store.audit_trail.append(entry)
                audit_entry_id = entry.entry_id
            except Exception as exc:  # pragma: no cover - governance optional
                notes.append("Governance audit append skipped: {}".format(exc))

        return ThreeDriverTailReport(
            config=cfg, lsmc_summary=surface.summary(),
            convergence=convergence, bootstrap=bootstrap, variance_reduction=vr,
            run_id=run_id, duration_seconds=duration, verdict=verdict,
            reproducibility_digest=digest, notes=notes, audit_entry_id=audit_entry_id,
        )

    @staticmethod
    def _verdict(
        cfg: ThreeDriverTailConfig,
        convergence: OuterConvergence,
        bootstrap: BootstrapInterval,
        vr: VarianceReduction3D,
        notes: List[str],
    ) -> str:
        var_in_ci = bootstrap.var_ci_low <= convergence.final_var <= bootstrap.var_ci_high
        best_ratio = max(vr.antithetic_var_ratio, vr.sobol_var_ratio)
        checks = [
            convergence.converged,
            var_in_ci,
            best_ratio > 1.0,
        ]
        if not convergence.converged:
            notes.append("99.5% VaR not converged within outer_grid; extend N_outer.")
        if not var_in_ci:
            notes.append("Convergence VaR lies outside the bootstrap CI (independent samples); review.")
        if vr.antithetic_var_ratio < 1.0:
            notes.append(
                "Antithetic variates do not reduce the 99.5% VaR-estimator variance "
                "(ratio {:.2f}<1) - expected for an extreme quantile; QMC is the "
                "effective scheme here (ratio {:.2f}).".format(
                    vr.antithetic_var_ratio, vr.sobol_var_ratio))
        if vr.sobol_var_ratio < 1.0:
            notes.append("Sobol QMC did not reduce VaR-estimator variance for this surface.")
        if all(checks):
            return "PASS - three-driver 99.5% capital metric converges, is bounded by a bootstrap CI, and benefits from variance reduction"
        return "PARTIAL - three-driver tail diagnostics generated with review items"


def three_driver_tail_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the three-driver tail diagnostics.

    SOA ASOP 56 §3.5.1; IA TAS M §3.6.
    """
    return {
        "module": "par_model_v2/projection/multi_driver_tail_diagnostics.py (ThreeDriverTailDiagnostics)",
        "classification": "EDUCATIONAL ONLY — NOT a regulatory capital model",
        "scope": (
            "Quantifies the OUTER Monte-Carlo (sampling) uncertainty of the "
            "99.5% VaR/ES of the THREE-driver (rate+equity+credit-spread) "
            "liability via the once-fitted Phase 17 Task 1 trivariate LSMC "
            "surface: outer-count convergence, a non-parametric bootstrap CI, "
            "and a crude/antithetic/Sobol variance-reduction comparison."
        ),
        "what_it_does_NOT_cover": (
            "Proxy (LSMC fit) error - bounded separately by Phase 17 Task 1 "
            "proxy-vs-nested and Task 2 out-of-sample validation; and all risk "
            "drivers beyond rates+equity+credit (lapse, mortality trend, FX)."
        ),
        "variance_reduction_surrogate": (
            "The variance-reduction ratios are measured on a pilot-anchored "
            "Gaussian-copula surrogate of the horizon state whose controlling "
            "correlation is the realised 3x3 outer-state correlation and whose "
            "margins are the empirical pilot margins - the controllable normal/"
            "uniform driver that antithetic and QMC require. Convergence and "
            "bootstrap use the real governed 3-factor outer states. Ratios are "
            "indicative of relative estimator efficiency, not an absolute capital figure."
        ),
        "placeholder_parameters": (
            "HW1F, GBM, and CIR++ parameters are illustrative placeholders; "
            "capital magnitudes are NOT calibrated."
        ),
        "governance": (
            "Independent APS X2 review pending; production sign-off withheld. "
            "Use only for education, methodology demonstration, and testing."
        ),
        "standards": [
            "SOA ASOP 56 §3.1.3", "SOA ASOP 56 §3.5", "SOA ASOP 25 §3.3",
            "IA TAS M §3.6", "L'Ecuyer (2018) RQMC", "Glasserman (2003) §4",
        ],
    }


def three_driver_tail_use_restrictions_json() -> str:
    return json.dumps(three_driver_tail_use_restrictions(), indent=2, sort_keys=True)


__all__ += [
    "ThreeDriverTailConfig",
    "VarianceReduction3D",
    "ThreeDriverTailReport",
    "ThreeDriverTailDiagnostics",
    "three_driver_tail_use_restrictions",
    "three_driver_tail_use_restrictions_json",
    "_draw_normals_nd",
    "_correlate_nd",
    "_states_from_normals_nd",
    "_nearest_correlation_matrix",
]


# ===========================================================================
# Phase 18 Task 4 — FOUR-driver (rate + equity + credit + lapse) tail diagnostics
# ===========================================================================
#
# Additive extension: the two-driver ``MultiDriverTailDiagnostics`` and the
# three-driver ``ThreeDriverTailDiagnostics`` above are untouched.  The fourth
# (non-financial) driver is the OU lapse-behaviour index of Phase 18 Task 3; the
# diagnostics are built on the Phase 18 Task 3 *quadrivariate* LSMC surface so
# the outer (Monte-Carlo) sampling error of the 99.5% four-driver capital metric
# can be probed at scale.  The N-D copula / scheme helpers (_draw_normals_nd,
# _correlate_nd, _states_from_normals_nd, _nearest_correlation_matrix) are
# dimension-agnostic and reused directly with dim=4.

from par_model_v2.projection.multi_driver_capital_4d import (  # noqa: E402
    DEFAULT_MAX_INTERACTION_ORDER_4D,
    DEFAULT_QUAD_LSMC_DEGREE,
    FourDriverCorrelation,
    FourDriverLSMCProxyEngine,
    FourDriverLSMCResult,
    LapseExposureSpec,
    _outer_states_4d,
)
from par_model_v2.stochastic.lapse_behaviour import LapseBehaviourParams  # noqa: E402


@dataclass
class FourDriverTailConfig:
    """Configuration for the Phase 18 Task 4 four-driver tail-diagnostics run."""

    n_fit: int = 1_500
    lsmc_degree: int = DEFAULT_QUAD_LSMC_DEGREE
    max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER_4D
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS
    outer_measure: Measure = Measure.P
    seed: int = 42

    outer_grid: Tuple[int, ...] = DEFAULT_OUTER_GRID
    convergence_tol: float = DEFAULT_CONVERGENCE_TOL

    n_bootstrap: int = DEFAULT_N_BOOTSTRAP
    bootstrap_n_outer: int = DEFAULT_BOOTSTRAP_N_OUTER
    bootstrap_ci_level: float = 0.95

    vr_replications: int = DEFAULT_VR_REPLICATIONS
    vr_n_outer: int = DEFAULT_VR_N_OUTER
    vr_pilot_n: int = DEFAULT_VR_PILOT_N

    def __post_init__(self) -> None:
        if self.n_fit < 50:
            raise ValueError("n_fit must be >= 50")
        if self.lsmc_degree < 1:
            raise ValueError("lsmc_degree must be >= 1")
        if self.max_interaction_order < 0:
            raise ValueError("max_interaction_order must be >= 0")
        if not (0.5 < self.confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0.5, 1.0)")
        if self.capital_horizon_months <= 0:
            raise ValueError("capital_horizon_months must be positive")
        if len(self.outer_grid) < 2:
            raise ValueError("outer_grid must contain at least two sizes")
        if any(n <= 0 for n in self.outer_grid):
            raise ValueError("outer_grid sizes must be positive")
        if list(self.outer_grid) != sorted(self.outer_grid):
            raise ValueError("outer_grid must be ascending")
        if self.convergence_tol <= 0:
            raise ValueError("convergence_tol must be positive")
        if self.n_bootstrap < 100:
            raise ValueError("n_bootstrap must be >= 100")
        if self.bootstrap_n_outer < 100:
            raise ValueError("bootstrap_n_outer must be >= 100")
        if not (0.5 < self.bootstrap_ci_level < 1.0):
            raise ValueError("bootstrap_ci_level must be in (0.5, 1.0)")
        if self.vr_replications < 10:
            raise ValueError("vr_replications must be >= 10")
        if self.vr_n_outer < 64 or (self.vr_n_outer & (self.vr_n_outer - 1)) != 0:
            raise ValueError("vr_n_outer must be a power of two >= 64")
        if self.vr_pilot_n < 200:
            raise ValueError("vr_pilot_n must be >= 200")
        self.outer_measure = Measure(self.outer_measure)
        self.outer_grid = tuple(int(n) for n in self.outer_grid)

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_fit": self.n_fit,
            "lsmc_degree": self.lsmc_degree,
            "max_interaction_order": self.max_interaction_order,
            "confidence_level": self.confidence_level,
            "capital_horizon_months": self.capital_horizon_months,
            "outer_measure": self.outer_measure.value,
            "seed": self.seed,
            "outer_grid": list(self.outer_grid),
            "convergence_tol": self.convergence_tol,
            "n_bootstrap": self.n_bootstrap,
            "bootstrap_n_outer": self.bootstrap_n_outer,
            "bootstrap_ci_level": self.bootstrap_ci_level,
            "vr_replications": self.vr_replications,
            "vr_n_outer": self.vr_n_outer,
            "vr_pilot_n": self.vr_pilot_n,
        }


@dataclass
class VarianceReduction4D:
    """Variance-reduction comparison across sampling schemes (four drivers).

    Identical structure to :class:`VarianceReduction3D` except the controlling
    copula is now four-dimensional, so ``copula_corr`` is the realised 4x4
    outer-state correlation (rate, equity, credit-spread, lapse-behaviour).
    """

    crude: SchemeVariance
    antithetic: SchemeVariance
    sobol: SchemeVariance
    antithetic_var_ratio: float
    sobol_var_ratio: float
    antithetic_es_ratio: float
    sobol_es_ratio: float
    copula_corr: Tuple[Tuple[float, ...], ...]   # realised 4x4 outer-state corr

    def to_dict(self) -> Dict[str, object]:
        return {
            "crude": self.crude.to_dict(),
            "antithetic": self.antithetic.to_dict(),
            "sobol": self.sobol.to_dict(),
            "antithetic_var_ratio": round(self.antithetic_var_ratio, 4),
            "sobol_var_ratio": round(self.sobol_var_ratio, 4),
            "antithetic_es_ratio": round(self.antithetic_es_ratio, 4),
            "sobol_es_ratio": round(self.sobol_es_ratio, 4),
            "copula_corr": [[round(x, 6) for x in row] for row in self.copula_corr],
        }


@dataclass
class FourDriverTailReport:
    """Full structured Phase 18 Task 4 four-driver tail-diagnostics report."""

    config: FourDriverTailConfig
    lsmc_summary: Dict[str, object]
    convergence: OuterConvergence
    bootstrap: BootstrapInterval
    variance_reduction: VarianceReduction4D
    run_id: str
    duration_seconds: float
    verdict: str
    reproducibility_digest: str
    drivers: Tuple[str, ...] = (
        "short_rate", "equity_level", "credit_spread", "lapse_behaviour")
    notes: List[str] = field(default_factory=list)
    audit_entry_id: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict,
            "drivers": list(self.drivers),
            "lsmc_summary": self.lsmc_summary,
            "convergence": self.convergence.to_dict(),
            "bootstrap": self.bootstrap.to_dict(),
            "variance_reduction": self.variance_reduction.to_dict(),
            "reproducibility_digest": self.reproducibility_digest,
            "duration_seconds": round(self.duration_seconds, 4),
            "config": self.config.to_dict(),
            "notes": list(self.notes),
            "audit_entry_id": self.audit_entry_id,
            "standards": [
                "SOA ASOP 56 §3.5",
                "SOA ASOP 56 §3.1.3",
                "SOA ASOP 25 §3.3",
                "SOA ASOP 7 §3.3",
                "IA TAS M §3.6",
                "L'Ecuyer (2018) RQMC",
                "Glasserman (2003) §4",
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        c = self.convergence
        b = self.bootstrap
        v = self.variance_reduction
        lines = [
            "# Phase 18 Task 4 — Four-Driver Tail-Convergence & Stability Diagnostics",
            "",
            "**Drivers:** {}".format(", ".join(self.drivers)),
            "",
            "**Verdict:** {}".format(self.verdict),
            "",
            "Run `{}` | {} s | digest `{}`".format(
                self.run_id, round(self.duration_seconds, 2),
                self.reproducibility_digest[:12]),
            "",
            "## 1. Outer-count convergence (99.5% VaR / ES)",
            "",
            "| N_outer | VaR | ES | ΔVaR (rel) |",
            "|--------:|----:|---:|-----------:|",
        ]
        changes = (None,) + c.var_successive_rel_change
        for n, var, es, ch in zip(c.n_outer_grid, c.var_path, c.es_path, changes):
            chs = "—" if ch is None else "{:.3%}".format(ch)
            lines.append("| {:,} | {:,.1f} | {:,.1f} | {} |".format(n, var, es, chs))
        lines += [
            "",
            "Converged: **{}** (tol {:.2%}); recommended N_outer ≥ **{:,}**.".format(
                c.converged, self.config.convergence_tol, c.recommended_n_outer),
            "",
            "## 2. Bootstrap {:.0%} CI (N_outer={:,}, B={:,})".format(
                b.ci_level, b.n_outer, b.n_bootstrap),
            "",
            "- VaR {:,.1f}  CI [{:,.1f}, {:,.1f}]  SE {:,.1f}  (±{:.2%} of point)".format(
                b.var_point, b.var_ci_low, b.var_ci_high, b.var_standard_error,
                b.var_ci_rel_halfwidth),
            "- ES  {:,.1f}  CI [{:,.1f}, {:,.1f}]  SE {:,.1f}".format(
                b.es_point, b.es_ci_low, b.es_ci_high, b.es_standard_error),
            "",
            "## 3. Variance reduction (VaR estimator, {} reps × N={:,})".format(
                v.crude.n_replications, v.crude.n_outer),
            "",
            "Copula correlation (realised 4x4 outer-state, rate/equity/credit/lapse): {}".format(
                v.copula_corr),
            "",
            "| Scheme | VaR estimator SD | Variance-reduction ratio |",
            "|--------|-----------------:|-------------------------:|",
            "| Crude (pseudo-random) | {:,.2f} | 1.00× |".format(v.crude.var_std),
            "| Antithetic | {:,.2f} | {:.2f}× |".format(v.antithetic.var_std, v.antithetic_var_ratio),
            "| Sobol QMC | {:,.2f} | {:.2f}× |".format(v.sobol.var_std, v.sobol_var_ratio),
            "",
            "## Notes",
            "",
        ]
        lines += ["- {}".format(n) for n in self.notes]
        return "\n".join(lines) + "\n"


class FourDriverTailDiagnostics:
    """Convergence, bootstrap-CI, and variance-reduction diagnostics for the
    FOUR-driver (rate + equity + credit-spread + lapse-behaviour) 99.5% capital
    metric, built on the Phase 18 Task 3 quadrivariate LSMC surface (additive;
    no existing diagnostics class touched)."""

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        spread_params: Optional[CreditSpreadParams] = None,
        lapse_params: Optional[LapseBehaviourParams] = None,
        correlation: Optional[FourDriverCorrelation] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        credit_exposure: Optional[CreditExposureSpec] = None,
        lapse_exposure: Optional[LapseExposureSpec] = None,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.spread_params = spread_params if spread_params is not None else CreditSpreadParams()
        self.lapse_params = lapse_params if lapse_params is not None else LapseBehaviourParams()
        self.correlation = correlation if correlation is not None else FourDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.lapse_exposure = lapse_exposure or LapseExposureSpec()
        self.annual_qx_fn = annual_qx_fn

    # -- fitted surface -----------------------------------------------------
    def _fit_surface(self, cfg: FourDriverTailConfig) -> FourDriverLSMCResult:
        engine = FourDriverLSMCProxyEngine(
            self.product,
            hw_params=self.hw_params,
            gbm_params=self.gbm_params,
            spread_params=self.spread_params,
            lapse_params=self.lapse_params,
            correlation=self.correlation,
            initial_curve=self.initial_curve,
            equity_guarantee=self.equity_guarantee,
            credit_exposure=self.credit_exposure,
            lapse_exposure=self.lapse_exposure,
            capital_horizon_months=cfg.capital_horizon_months,
            confidence_level=cfg.confidence_level,
            outer_measure=cfg.outer_measure,
            degree=cfg.lsmc_degree,
            max_interaction_order=cfg.max_interaction_order,
            annual_qx_fn=self.annual_qx_fn,
        )
        return engine.fit_and_run(n_fit=cfg.n_fit, n_outer_eval=1_000, seed=cfg.seed)

    def _outer_states(
        self, n_outer: int, cfg: FourDriverTailConfig, seed: int
    ) -> np.ndarray:
        return _outer_states_4d(
            n_outer, cfg.capital_horizon_months, cfg.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params, self.lapse_params,
            self.correlation, self.initial_curve, seed,
        )

    def _outer_liabilities(
        self, surface: FourDriverLSMCResult, n_outer: int,
        cfg: FourDriverTailConfig, seed: int,
    ) -> np.ndarray:
        return surface.predict(self._outer_states(n_outer, cfg, seed))

    # -- 1. convergence -----------------------------------------------------
    def _convergence(
        self, surface: FourDriverLSMCResult, cfg: FourDriverTailConfig
    ) -> OuterConvergence:
        var_path: List[float] = []
        es_path: List[float] = []
        for k, n in enumerate(cfg.outer_grid):
            liab = self._outer_liabilities(surface, n, cfg, seed=cfg.seed + 1_000 + 7 * k)
            var, es = _var_es(liab, cfg.confidence_level)
            var_path.append(var)
            es_path.append(es)
        var_chg = tuple(_rel(var_path[i], var_path[i - 1]) for i in range(1, len(var_path)))
        es_chg = tuple(_rel(es_path[i], es_path[i - 1]) for i in range(1, len(es_path)))

        recommended = cfg.outer_grid[-1]
        converged = bool(var_chg and var_chg[-1] <= cfg.convergence_tol)
        for i, ch in enumerate(var_chg):
            if ch <= cfg.convergence_tol:
                recommended = cfg.outer_grid[i + 1]
                break
        return OuterConvergence(
            n_outer_grid=tuple(cfg.outer_grid),
            var_path=tuple(var_path), es_path=tuple(es_path),
            var_successive_rel_change=var_chg, es_successive_rel_change=es_chg,
            converged=converged, recommended_n_outer=int(recommended),
            final_var=var_path[-1], final_es=es_path[-1],
        )

    # -- 2. bootstrap CI ----------------------------------------------------
    def _bootstrap(
        self, surface: FourDriverLSMCResult, cfg: FourDriverTailConfig
    ) -> BootstrapInterval:
        liab = self._outer_liabilities(
            surface, cfg.bootstrap_n_outer, cfg, seed=cfg.seed + 500
        )
        n = liab.size
        var_pt, es_pt = _var_es(liab, cfg.confidence_level)
        rng = np.random.default_rng(cfg.seed + 999)
        var_bs = np.empty(cfg.n_bootstrap, dtype=float)
        es_bs = np.empty(cfg.n_bootstrap, dtype=float)
        for b in range(cfg.n_bootstrap):
            idx = rng.integers(0, n, n)
            var_bs[b], es_bs[b] = _var_es(liab[idx], cfg.confidence_level)
        alpha = 1.0 - cfg.bootstrap_ci_level
        lo_q, hi_q = alpha / 2.0, 1.0 - alpha / 2.0
        return BootstrapInterval(
            n_outer=n, n_bootstrap=cfg.n_bootstrap, ci_level=cfg.bootstrap_ci_level,
            var_point=var_pt,
            var_ci_low=float(np.quantile(var_bs, lo_q)),
            var_ci_high=float(np.quantile(var_bs, hi_q)),
            var_standard_error=float(var_bs.std(ddof=1)),
            es_point=es_pt,
            es_ci_low=float(np.quantile(es_bs, lo_q)),
            es_ci_high=float(np.quantile(es_bs, hi_q)),
            es_standard_error=float(es_bs.std(ddof=1)),
        )

    # -- 3. variance reduction ---------------------------------------------
    def _variance_reduction(
        self, surface: FourDriverLSMCResult, cfg: FourDriverTailConfig
    ) -> VarianceReduction4D:
        pilot = self._outer_states(cfg.vr_pilot_n, cfg, seed=cfg.seed + 321)
        margins = tuple(np.sort(pilot[:, j]) for j in range(4))
        corr = np.corrcoef(pilot, rowvar=False)
        if not np.all(np.isfinite(corr)):
            corr = np.eye(4)
        corr = _nearest_correlation_matrix(corr)

        def scheme_stats(scheme: str) -> SchemeVariance:
            vars_, ess_ = [], []
            for rep in range(cfg.vr_replications):
                z = _draw_normals_nd(scheme, cfg.vr_n_outer, 4, seed=cfg.seed + 10_000 + rep)
                w = _correlate_nd(z, corr)
                states = _states_from_normals_nd(w, margins)
                liab = surface.predict(states)
                var, es = _var_es(liab, cfg.confidence_level)
                vars_.append(var)
                ess_.append(es)
            vars_ = np.asarray(vars_)
            ess_ = np.asarray(ess_)
            return SchemeVariance(
                scheme=scheme, n_outer=cfg.vr_n_outer, n_replications=cfg.vr_replications,
                var_mean=float(vars_.mean()), var_std=float(vars_.std(ddof=1)),
                es_mean=float(ess_.mean()), es_std=float(ess_.std(ddof=1)),
            )

        crude = scheme_stats("crude")
        anti = scheme_stats("antithetic")
        sob = scheme_stats("sobol")

        def ratio(base: float, other: float) -> float:
            return float((base ** 2) / (other ** 2)) if other > 1e-12 else float("inf")

        return VarianceReduction4D(
            crude=crude, antithetic=anti, sobol=sob,
            antithetic_var_ratio=ratio(crude.var_std, anti.var_std),
            sobol_var_ratio=ratio(crude.var_std, sob.var_std),
            antithetic_es_ratio=ratio(crude.es_std, anti.es_std),
            sobol_es_ratio=ratio(crude.es_std, sob.es_std),
            copula_corr=tuple(tuple(float(x) for x in row) for row in np.round(corr, 6)),
        )

    # -- orchestration ------------------------------------------------------
    def run(
        self,
        config: Optional[FourDriverTailConfig] = None,
        governance_store: Optional[object] = None,
        actor: str = "FourDriverTailDiagnostics",
        phase: str = "Phase 18: Tail-Dependent Risk Aggregation and Driver/Calibration Sophistication",
    ) -> FourDriverTailReport:
        cfg = config or FourDriverTailConfig()
        if cfg.capital_horizon_months >= self.product.term_months:
            raise ValueError("capital_horizon_months must be less than product term")

        t0 = time.monotonic()
        run_id = "td4-tail-" + uuid.uuid4().hex[:8]

        surface = self._fit_surface(cfg)
        convergence = self._convergence(surface, cfg)
        bootstrap = self._bootstrap(surface, cfg)
        vr = self._variance_reduction(surface, cfg)

        notes: List[str] = [
            "Four-driver (rate+equity+credit+lapse) extension of the Phase 17 Task 4 "
            "three-driver tail diagnostics; built on the Phase 18 Task 3 quadrivariate "
            "LSMC surface (no two-/three-driver diagnostics class modified).",
            "The fourth driver is the NON-FINANCIAL OU lapse-behaviour index; it is "
            "orthogonal to the financial drivers in the governed 4x4 ESG matrix but its "
            "realised liability impact still co-moves in the tail (anti-selection).",
            "Outer-count convergence and the bootstrap CI use the GOVERNED 4-factor "
            "correlated outer states (_outer_states_4d) with the once-fitted LSMC surface; "
            "they isolate outer Monte-Carlo (sampling) error, not proxy error.",
            "Proxy error is bounded separately by the Phase 18 Task 3 four-driver "
            "out-of-sample validation (OOS R^2=0.9638) report.",
            "The variance-reduction study uses a pilot-anchored Gaussian copula whose "
            "controlling correlation is the realised 4x4 outer-state correlation "
            "(rate/equity/credit/lapse) and whose margins are the empirical pilot margins, "
            "so crude / antithetic / Sobol target an identical distribution and the ratio "
            "is like-for-like.",
            "Antithetic uses negated normal quadruples; Sobol uses a scrambled base-2 "
            "sequence in 4 dimensions (n is a power of two for exact balance).",
        ]
        verdict = self._verdict(cfg, convergence, bootstrap, vr, notes)

        digest = hashlib.sha256(
            np.round(
                np.concatenate([
                    np.asarray(convergence.var_path, dtype=float),
                    np.asarray(convergence.es_path, dtype=float),
                    np.array([bootstrap.var_point, bootstrap.es_point,
                              bootstrap.var_standard_error, bootstrap.es_standard_error],
                             dtype=float),
                    np.array([vr.crude.var_std, vr.antithetic.var_std, vr.sobol.var_std],
                             dtype=float),
                    np.asarray(vr.copula_corr, dtype=float).reshape(-1),
                ]),
                6,
            ).tobytes()
        ).hexdigest()

        duration = time.monotonic() - t0
        audit_entry_id = None
        if governance_store is not None:
            try:
                from par_model_v2.governance.audit_trail import AuditEntry

                entry = AuditEntry.model_run(
                    actor=actor, phase=phase, run_id=run_id,
                    scenario_count=cfg.outer_grid[-1] + cfg.bootstrap_n_outer
                    + cfg.vr_replications * cfg.vr_n_outer,
                    duration_seconds=round(duration, 4),
                    outcome=verdict.split()[0],
                    files_changed=[
                        "par_model_v2/projection/multi_driver_tail_diagnostics.py"
                    ],
                    test_summary=(
                        "4D VaR{:.1f}%={:.1f}; converged={}; rec_N>={}; CI=[{:.1f},{:.1f}]; "
                        "SE={:.1f}; anti_ratio={:.2f}; sobol_ratio={:.2f}".format(
                            cfg.confidence_level * 100, convergence.final_var,
                            convergence.converged, convergence.recommended_n_outer,
                            bootstrap.var_ci_low, bootstrap.var_ci_high,
                            bootstrap.var_standard_error,
                            vr.antithetic_var_ratio, vr.sobol_var_ratio)
                    ),
                )
                governance_store.audit_trail.append(entry)
                audit_entry_id = entry.entry_id
            except Exception as exc:  # pragma: no cover - governance optional
                notes.append("Governance audit append skipped: {}".format(exc))

        return FourDriverTailReport(
            config=cfg, lsmc_summary=surface.summary(),
            convergence=convergence, bootstrap=bootstrap, variance_reduction=vr,
            run_id=run_id, duration_seconds=duration, verdict=verdict,
            reproducibility_digest=digest, notes=notes, audit_entry_id=audit_entry_id,
        )

    @staticmethod
    def _verdict(
        cfg: FourDriverTailConfig,
        convergence: OuterConvergence,
        bootstrap: BootstrapInterval,
        vr: VarianceReduction4D,
        notes: List[str],
    ) -> str:
        var_in_ci = bootstrap.var_ci_low <= convergence.final_var <= bootstrap.var_ci_high
        best_ratio = max(vr.antithetic_var_ratio, vr.sobol_var_ratio)
        checks = [
            convergence.converged,
            var_in_ci,
            best_ratio > 1.0,
        ]
        if not convergence.converged:
            notes.append("99.5% VaR not converged within outer_grid; extend N_outer.")
        if not var_in_ci:
            notes.append("Convergence VaR lies outside the bootstrap CI (independent samples); review.")
        if vr.antithetic_var_ratio < 1.0:
            notes.append(
                "Antithetic variates do not reduce the 99.5% VaR-estimator variance "
                "(ratio {:.2f}<1) - expected for an extreme quantile; QMC is the "
                "effective scheme here (ratio {:.2f}).".format(
                    vr.antithetic_var_ratio, vr.sobol_var_ratio))
        if vr.sobol_var_ratio < 1.0:
            notes.append("Sobol QMC did not reduce VaR-estimator variance for this surface.")
        if all(checks):
            return "PASS - four-driver 99.5% capital metric converges, is bounded by a bootstrap CI, and benefits from variance reduction"
        return "PARTIAL - four-driver tail diagnostics generated with review items"


def four_driver_tail_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the four-driver tail diagnostics.

    SOA ASOP 56 §3.5.1; SOA ASOP 7 §3.3; IA TAS M §3.6.
    """
    return {
        "module": "par_model_v2/projection/multi_driver_tail_diagnostics.py",
        "component": "FourDriverTailDiagnostics",
        "classification": "EDUCATIONAL ONLY - NOT a regulatory capital model",
        "risk_drivers": ["short rate", "equity level", "credit spread", "lapse behaviour"],
        "method": (
            "Outer-count convergence, non-parametric bootstrap CI/SE on the 99.5% "
            "VaR/ES, and a crude/antithetic/Sobol variance-reduction comparison for the "
            "four-driver 99.5% capital metric, built on the Phase 18 Task 3 quadrivariate "
            "LSMC surface (the outer-sampling error is probed; proxy error is bounded "
            "separately by the four-driver OOS proxy-validation report)."
        ),
        "limitations": [
            "Outer sampling and bootstrap diagnostics probe Monte-Carlo error only; the proxy (surface) error is bounded separately by the four-driver OOS validation.",
            "The variance-reduction study runs on a smooth pilot-anchored Gaussian-copula surrogate of the horizon-state distribution, NOT the raw governed processes; antithetic/QMC require a controllable normal/uniform driver.",
            "Four drivers only (rates + equity + credit + lapse); mortality-trend, FX, and liquidity remain outside the tail.",
            "Lapse behaviour is a single systemic OU index with placeholder parameters; the in-force coupling is multiplicative and educational.",
            "Independent APS X2 review and credentialled calibration data are still required before any production use.",
        ],
        "standards": [
            "SOA ASOP 56 §3.5",
            "SOA ASOP 56 §3.1.3",
            "SOA ASOP 25 §3.3",
            "SOA ASOP 7 §3.3",
            "IA TAS M §3.6",
            "L'Ecuyer (2018) RQMC",
        ],
    }


def four_driver_tail_use_restrictions_json() -> str:
    return json.dumps(four_driver_tail_use_restrictions(), indent=2, sort_keys=True)


# ===========================================================================
# Phase 19 Task 4 (remaining) -- FIVE-DRIVER tail-convergence & stability
# diagnostics.  Additive: extends the four-driver diagnostics with a second
# NON-FINANCIAL driver -- the OU mortality-trend index m(t) (Lee-Carter-style
# single systemic time index).  Built on the Phase 19 Task 3 *quintivariate*
# LSMC surface so the outer (Monte-Carlo) sampling error of the 99.5% five-driver
# capital metric can be probed at scale.  The N-D copula / scheme helpers
# (_draw_normals_nd, _correlate_nd, _states_from_normals_nd,
# _nearest_correlation_matrix) are dimension-agnostic and reused with dim=5.
# No two-/three-/four-driver diagnostics class is modified.

from par_model_v2.projection.multi_driver_capital_5d import (  # noqa: E402
    DEFAULT_MAX_INTERACTION_ORDER_5D,
    DEFAULT_QUINT_LSMC_DEGREE,
    FiveDriverCorrelation,
    FiveDriverLSMCProxyEngine,
    FiveDriverLSMCResult,
    MortalityExposureSpec,
    _outer_states_5d,
)
from par_model_v2.stochastic.mortality_trend import MortalityTrendParams  # noqa: E402


@dataclass
class FiveDriverTailConfig:
    """Configuration for the Phase 19 Task 4 five-driver tail-diagnostics run."""

    n_fit: int = 1_500
    lsmc_degree: int = DEFAULT_QUINT_LSMC_DEGREE
    max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER_5D
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS
    outer_measure: Measure = Measure.P
    seed: int = 42

    outer_grid: Tuple[int, ...] = DEFAULT_OUTER_GRID
    convergence_tol: float = DEFAULT_CONVERGENCE_TOL

    n_bootstrap: int = DEFAULT_N_BOOTSTRAP
    bootstrap_n_outer: int = DEFAULT_BOOTSTRAP_N_OUTER
    bootstrap_ci_level: float = 0.95

    vr_replications: int = DEFAULT_VR_REPLICATIONS
    vr_n_outer: int = DEFAULT_VR_N_OUTER
    vr_pilot_n: int = DEFAULT_VR_PILOT_N

    def __post_init__(self) -> None:
        if self.n_fit < 50:
            raise ValueError("n_fit must be >= 50")
        if self.lsmc_degree < 1:
            raise ValueError("lsmc_degree must be >= 1")
        if self.max_interaction_order < 0:
            raise ValueError("max_interaction_order must be >= 0")
        if not (0.5 < self.confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0.5, 1.0)")
        if self.capital_horizon_months <= 0:
            raise ValueError("capital_horizon_months must be positive")
        if len(self.outer_grid) < 2:
            raise ValueError("outer_grid must contain at least two sizes")
        if any(n <= 0 for n in self.outer_grid):
            raise ValueError("outer_grid sizes must be positive")
        if list(self.outer_grid) != sorted(self.outer_grid):
            raise ValueError("outer_grid must be ascending")
        if self.convergence_tol <= 0:
            raise ValueError("convergence_tol must be positive")
        if self.n_bootstrap < 100:
            raise ValueError("n_bootstrap must be >= 100")
        if self.bootstrap_n_outer < 100:
            raise ValueError("bootstrap_n_outer must be >= 100")
        if not (0.5 < self.bootstrap_ci_level < 1.0):
            raise ValueError("bootstrap_ci_level must be in (0.5, 1.0)")
        if self.vr_replications < 10:
            raise ValueError("vr_replications must be >= 10")
        if self.vr_n_outer < 64 or (self.vr_n_outer & (self.vr_n_outer - 1)) != 0:
            raise ValueError("vr_n_outer must be a power of two >= 64")
        if self.vr_pilot_n < 200:
            raise ValueError("vr_pilot_n must be >= 200")
        self.outer_measure = Measure(self.outer_measure)
        self.outer_grid = tuple(int(n) for n in self.outer_grid)

    def to_dict(self) -> Dict[str, object]:
        return {
            "n_fit": self.n_fit,
            "lsmc_degree": self.lsmc_degree,
            "max_interaction_order": self.max_interaction_order,
            "confidence_level": self.confidence_level,
            "capital_horizon_months": self.capital_horizon_months,
            "outer_measure": self.outer_measure.value,
            "seed": self.seed,
            "outer_grid": list(self.outer_grid),
            "convergence_tol": self.convergence_tol,
            "n_bootstrap": self.n_bootstrap,
            "bootstrap_n_outer": self.bootstrap_n_outer,
            "bootstrap_ci_level": self.bootstrap_ci_level,
            "vr_replications": self.vr_replications,
            "vr_n_outer": self.vr_n_outer,
            "vr_pilot_n": self.vr_pilot_n,
        }


@dataclass
class VarianceReduction5D:
    """Variance-reduction comparison across sampling schemes (five drivers).

    Identical structure to :class:`VarianceReduction4D` except the controlling
    copula is now five-dimensional, so ``copula_corr`` is the realised 5x5
    outer-state correlation (rate, equity, credit-spread, lapse-behaviour,
    mortality-trend).
    """

    crude: SchemeVariance
    antithetic: SchemeVariance
    sobol: SchemeVariance
    antithetic_var_ratio: float
    sobol_var_ratio: float
    antithetic_es_ratio: float
    sobol_es_ratio: float
    copula_corr: Tuple[Tuple[float, ...], ...]   # realised 5x5 outer-state corr

    def to_dict(self) -> Dict[str, object]:
        return {
            "crude": self.crude.to_dict(),
            "antithetic": self.antithetic.to_dict(),
            "sobol": self.sobol.to_dict(),
            "antithetic_var_ratio": round(self.antithetic_var_ratio, 4),
            "sobol_var_ratio": round(self.sobol_var_ratio, 4),
            "antithetic_es_ratio": round(self.antithetic_es_ratio, 4),
            "sobol_es_ratio": round(self.sobol_es_ratio, 4),
            "copula_corr": [[round(x, 6) for x in row] for row in self.copula_corr],
        }


@dataclass
class FiveDriverTailReport:
    """Full structured Phase 19 Task 4 five-driver tail-diagnostics report."""

    config: FiveDriverTailConfig
    lsmc_summary: Dict[str, object]
    convergence: OuterConvergence
    bootstrap: BootstrapInterval
    variance_reduction: VarianceReduction5D
    run_id: str
    duration_seconds: float
    verdict: str
    reproducibility_digest: str
    drivers: Tuple[str, ...] = (
        "short_rate", "equity_level", "credit_spread",
        "lapse_behaviour", "mortality_trend")
    notes: List[str] = field(default_factory=list)
    audit_entry_id: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict,
            "drivers": list(self.drivers),
            "lsmc_summary": self.lsmc_summary,
            "convergence": self.convergence.to_dict(),
            "bootstrap": self.bootstrap.to_dict(),
            "variance_reduction": self.variance_reduction.to_dict(),
            "reproducibility_digest": self.reproducibility_digest,
            "duration_seconds": round(self.duration_seconds, 4),
            "config": self.config.to_dict(),
            "notes": list(self.notes),
            "audit_entry_id": self.audit_entry_id,
            "standards": [
                "SOA ASOP 56 §3.5",
                "SOA ASOP 56 §3.1.3",
                "SOA ASOP 25 §3.3",
                "SOA ASOP 7 §3.3",
                "IA TAS M §3.6",
                "L'Ecuyer (2018) RQMC",
                "Glasserman (2003) §4",
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        c = self.convergence
        b = self.bootstrap
        v = self.variance_reduction
        lines = [
            "# Phase 19 Task 4 — Five-Driver Tail-Convergence & Stability Diagnostics",
            "",
            "**Drivers:** {}".format(", ".join(self.drivers)),
            "",
            "**Verdict:** {}".format(self.verdict),
            "",
            "Run `{}` | {} s | digest `{}`".format(
                self.run_id, round(self.duration_seconds, 2),
                self.reproducibility_digest[:12]),
            "",
            "## 1. Outer-count convergence (99.5% VaR / ES)",
            "",
            "| N_outer | VaR | ES | ΔVaR (rel) |",
            "|--------:|----:|---:|-----------:|",
        ]
        changes = (None,) + c.var_successive_rel_change
        for n, var, es, ch in zip(c.n_outer_grid, c.var_path, c.es_path, changes):
            chs = "—" if ch is None else "{:.3%}".format(ch)
            lines.append("| {:,} | {:,.1f} | {:,.1f} | {} |".format(n, var, es, chs))
        lines += [
            "",
            "Converged: **{}** (tol {:.2%}); recommended N_outer ≥ **{:,}**.".format(
                c.converged, self.config.convergence_tol, c.recommended_n_outer),
            "",
            "## 2. Bootstrap {:.0%} CI (N_outer={:,}, B={:,})".format(
                b.ci_level, b.n_outer, b.n_bootstrap),
            "",
            "- VaR {:,.1f}  CI [{:,.1f}, {:,.1f}]  SE {:,.1f}  (±{:.2%} of point)".format(
                b.var_point, b.var_ci_low, b.var_ci_high, b.var_standard_error,
                b.var_ci_rel_halfwidth),
            "- ES  {:,.1f}  CI [{:,.1f}, {:,.1f}]  SE {:,.1f}".format(
                b.es_point, b.es_ci_low, b.es_ci_high, b.es_standard_error),
            "",
            "## 3. Variance reduction (VaR estimator, {} reps × N={:,})".format(
                v.crude.n_replications, v.crude.n_outer),
            "",
            "Copula correlation (realised 5x5 outer-state, rate/equity/credit/lapse/mortality): {}".format(
                v.copula_corr),
            "",
            "| Scheme | VaR estimator SD | Variance-reduction ratio |",
            "|--------|-----------------:|-------------------------:|",
            "| Crude (pseudo-random) | {:,.2f} | 1.00× |".format(v.crude.var_std),
            "| Antithetic | {:,.2f} | {:.2f}× |".format(v.antithetic.var_std, v.antithetic_var_ratio),
            "| Sobol QMC | {:,.2f} | {:.2f}× |".format(v.sobol.var_std, v.sobol_var_ratio),
            "",
            "## Notes",
            "",
        ]
        lines += ["- {}".format(n) for n in self.notes]
        return "\n".join(lines) + "\n"


class FiveDriverTailDiagnostics:
    """Convergence, bootstrap-CI, and variance-reduction diagnostics for the
    FIVE-driver (rate + equity + credit-spread + lapse-behaviour +
    mortality-trend) 99.5% capital metric, built on the Phase 19 Task 3
    quintivariate LSMC surface (additive; no existing diagnostics class
    touched)."""

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        spread_params: Optional[CreditSpreadParams] = None,
        lapse_params: Optional[LapseBehaviourParams] = None,
        mortality_params: Optional[MortalityTrendParams] = None,
        correlation: Optional[FiveDriverCorrelation] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        credit_exposure: Optional[CreditExposureSpec] = None,
        lapse_exposure: Optional[LapseExposureSpec] = None,
        mortality_exposure: Optional[MortalityExposureSpec] = None,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.spread_params = spread_params if spread_params is not None else CreditSpreadParams()
        self.lapse_params = lapse_params if lapse_params is not None else LapseBehaviourParams()
        self.mortality_params = (
            mortality_params if mortality_params is not None else MortalityTrendParams())
        self.correlation = correlation if correlation is not None else FiveDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.lapse_exposure = lapse_exposure or LapseExposureSpec()
        self.mortality_exposure = mortality_exposure or MortalityExposureSpec()
        self.annual_qx_fn = annual_qx_fn

    # -- fitted surface -----------------------------------------------------
    def _fit_surface(self, cfg: FiveDriverTailConfig) -> FiveDriverLSMCResult:
        engine = FiveDriverLSMCProxyEngine(
            self.product,
            hw_params=self.hw_params,
            gbm_params=self.gbm_params,
            spread_params=self.spread_params,
            lapse_params=self.lapse_params,
            mortality_params=self.mortality_params,
            correlation=self.correlation,
            initial_curve=self.initial_curve,
            equity_guarantee=self.equity_guarantee,
            credit_exposure=self.credit_exposure,
            lapse_exposure=self.lapse_exposure,
            mortality_exposure=self.mortality_exposure,
            capital_horizon_months=cfg.capital_horizon_months,
            confidence_level=cfg.confidence_level,
            outer_measure=cfg.outer_measure,
            degree=cfg.lsmc_degree,
            max_interaction_order=cfg.max_interaction_order,
            annual_qx_fn=self.annual_qx_fn,
        )
        return engine.fit_and_run(n_fit=cfg.n_fit, n_outer_eval=1_000, seed=cfg.seed)

    def _outer_states(
        self, n_outer: int, cfg: FiveDriverTailConfig, seed: int
    ) -> np.ndarray:
        return _outer_states_5d(
            n_outer, cfg.capital_horizon_months, cfg.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params, self.lapse_params,
            self.mortality_params, self.correlation, self.initial_curve, seed,
        )

    def _outer_liabilities(
        self, surface: FiveDriverLSMCResult, n_outer: int,
        cfg: FiveDriverTailConfig, seed: int,
    ) -> np.ndarray:
        return surface.predict(self._outer_states(n_outer, cfg, seed))

    # -- 1. convergence -----------------------------------------------------
    def _convergence(
        self, surface: FiveDriverLSMCResult, cfg: FiveDriverTailConfig
    ) -> OuterConvergence:
        var_path: List[float] = []
        es_path: List[float] = []
        for k, n in enumerate(cfg.outer_grid):
            liab = self._outer_liabilities(surface, n, cfg, seed=cfg.seed + 1_000 + 7 * k)
            var, es = _var_es(liab, cfg.confidence_level)
            var_path.append(var)
            es_path.append(es)
        var_chg = tuple(_rel(var_path[i], var_path[i - 1]) for i in range(1, len(var_path)))
        es_chg = tuple(_rel(es_path[i], es_path[i - 1]) for i in range(1, len(es_path)))

        recommended = cfg.outer_grid[-1]
        converged = bool(var_chg and var_chg[-1] <= cfg.convergence_tol)
        for i, ch in enumerate(var_chg):
            if ch <= cfg.convergence_tol:
                recommended = cfg.outer_grid[i + 1]
                break
        return OuterConvergence(
            n_outer_grid=tuple(cfg.outer_grid),
            var_path=tuple(var_path), es_path=tuple(es_path),
            var_successive_rel_change=var_chg, es_successive_rel_change=es_chg,
            converged=converged, recommended_n_outer=int(recommended),
            final_var=var_path[-1], final_es=es_path[-1],
        )

    # -- 2. bootstrap CI ----------------------------------------------------
    def _bootstrap(
        self, surface: FiveDriverLSMCResult, cfg: FiveDriverTailConfig
    ) -> BootstrapInterval:
        liab = self._outer_liabilities(
            surface, cfg.bootstrap_n_outer, cfg, seed=cfg.seed + 500
        )
        n = liab.size
        var_pt, es_pt = _var_es(liab, cfg.confidence_level)
        rng = np.random.default_rng(cfg.seed + 999)
        var_bs = np.empty(cfg.n_bootstrap, dtype=float)
        es_bs = np.empty(cfg.n_bootstrap, dtype=float)
        for b in range(cfg.n_bootstrap):
            idx = rng.integers(0, n, n)
            var_bs[b], es_bs[b] = _var_es(liab[idx], cfg.confidence_level)
        alpha = 1.0 - cfg.bootstrap_ci_level
        lo_q, hi_q = alpha / 2.0, 1.0 - alpha / 2.0
        return BootstrapInterval(
            n_outer=n, n_bootstrap=cfg.n_bootstrap, ci_level=cfg.bootstrap_ci_level,
            var_point=var_pt,
            var_ci_low=float(np.quantile(var_bs, lo_q)),
            var_ci_high=float(np.quantile(var_bs, hi_q)),
            var_standard_error=float(var_bs.std(ddof=1)),
            es_point=es_pt,
            es_ci_low=float(np.quantile(es_bs, lo_q)),
            es_ci_high=float(np.quantile(es_bs, hi_q)),
            es_standard_error=float(es_bs.std(ddof=1)),
        )

    # -- 3. variance reduction ---------------------------------------------
    def _variance_reduction(
        self, surface: FiveDriverLSMCResult, cfg: FiveDriverTailConfig
    ) -> VarianceReduction5D:
        pilot = self._outer_states(cfg.vr_pilot_n, cfg, seed=cfg.seed + 321)
        margins = tuple(np.sort(pilot[:, j]) for j in range(5))
        corr = np.corrcoef(pilot, rowvar=False)
        if not np.all(np.isfinite(corr)):
            corr = np.eye(5)
        corr = _nearest_correlation_matrix(corr)

        def scheme_stats(scheme: str) -> SchemeVariance:
            vars_, ess_ = [], []
            for rep in range(cfg.vr_replications):
                z = _draw_normals_nd(scheme, cfg.vr_n_outer, 5, seed=cfg.seed + 10_000 + rep)
                w = _correlate_nd(z, corr)
                states = _states_from_normals_nd(w, margins)
                liab = surface.predict(states)
                var, es = _var_es(liab, cfg.confidence_level)
                vars_.append(var)
                ess_.append(es)
            vars_ = np.asarray(vars_)
            ess_ = np.asarray(ess_)
            return SchemeVariance(
                scheme=scheme, n_outer=cfg.vr_n_outer, n_replications=cfg.vr_replications,
                var_mean=float(vars_.mean()), var_std=float(vars_.std(ddof=1)),
                es_mean=float(ess_.mean()), es_std=float(ess_.std(ddof=1)),
            )

        crude = scheme_stats("crude")
        anti = scheme_stats("antithetic")
        sob = scheme_stats("sobol")

        def ratio(base: float, other: float) -> float:
            return float((base ** 2) / (other ** 2)) if other > 1e-12 else float("inf")

        return VarianceReduction5D(
            crude=crude, antithetic=anti, sobol=sob,
            antithetic_var_ratio=ratio(crude.var_std, anti.var_std),
            sobol_var_ratio=ratio(crude.var_std, sob.var_std),
            antithetic_es_ratio=ratio(crude.es_std, anti.es_std),
            sobol_es_ratio=ratio(crude.es_std, sob.es_std),
            copula_corr=tuple(tuple(float(x) for x in row) for row in np.round(corr, 6)),
        )

    # -- orchestration ------------------------------------------------------
    def run(
        self,
        config: Optional[FiveDriverTailConfig] = None,
        governance_store: Optional[object] = None,
        actor: str = "FiveDriverTailDiagnostics",
        phase: str = "Phase 19: Recovery Completion and Driver Expansion",
    ) -> FiveDriverTailReport:
        cfg = config or FiveDriverTailConfig()
        if cfg.capital_horizon_months >= self.product.term_months:
            raise ValueError("capital_horizon_months must be less than product term")

        t0 = time.monotonic()
        run_id = "td5-tail-" + uuid.uuid4().hex[:8]

        surface = self._fit_surface(cfg)
        convergence = self._convergence(surface, cfg)
        bootstrap = self._bootstrap(surface, cfg)
        vr = self._variance_reduction(surface, cfg)

        notes: List[str] = [
            "Five-driver (rate+equity+credit+lapse+mortality) extension of the "
            "Phase 18 Task 4 four-driver tail diagnostics; built on the Phase 19 "
            "Task 3 quintivariate LSMC surface (no two-/three-/four-driver "
            "diagnostics class modified).",
            "The fifth driver is the SECOND NON-FINANCIAL axis -- an OU "
            "mortality-trend index m(t) (Lee-Carter-style single systemic time "
            "index); it is orthogonal to the financial drivers AND to lapse in the "
            "governed 5x5 ESG matrix, but its realised liability impact still "
            "perturbs the tail through benefit timing on the sum-assured endowment.",
            "Outer-count convergence and the bootstrap CI use the GOVERNED 5-factor "
            "correlated outer states (_outer_states_5d) with the once-fitted LSMC "
            "surface; they isolate outer Monte-Carlo (sampling) error, not proxy error.",
            "Proxy error is bounded separately by the Phase 19 Task 3 five-driver "
            "out-of-sample validation (OOS R^2=0.9616) report.",
            "The variance-reduction study uses a pilot-anchored Gaussian copula whose "
            "controlling correlation is the realised 5x5 outer-state correlation "
            "(rate/equity/credit/lapse/mortality) and whose margins are the empirical "
            "pilot margins, so crude / antithetic / Sobol target an identical "
            "distribution and the ratio is like-for-like.",
            "Antithetic uses negated normal quintuples; Sobol uses a scrambled base-2 "
            "sequence in 5 dimensions (n is a power of two for exact balance).",
        ]
        verdict = self._verdict(cfg, convergence, bootstrap, vr, notes)

        digest = hashlib.sha256(
            np.round(
                np.concatenate([
                    np.asarray(convergence.var_path, dtype=float),
                    np.asarray(convergence.es_path, dtype=float),
                    np.array([bootstrap.var_point, bootstrap.es_point,
                              bootstrap.var_standard_error, bootstrap.es_standard_error],
                             dtype=float),
                    np.array([vr.crude.var_std, vr.antithetic.var_std, vr.sobol.var_std],
                             dtype=float),
                    np.asarray(vr.copula_corr, dtype=float).reshape(-1),
                ]),
                6,
            ).tobytes()
        ).hexdigest()

        duration = time.monotonic() - t0
        audit_entry_id = None
        if governance_store is not None:
            try:
                from par_model_v2.governance.audit_trail import AuditEntry

                entry = AuditEntry.model_run(
                    actor=actor, phase=phase, run_id=run_id,
                    scenario_count=cfg.outer_grid[-1] + cfg.bootstrap_n_outer
                    + cfg.vr_replications * cfg.vr_n_outer,
                    duration_seconds=round(duration, 4),
                    outcome=verdict.split()[0],
                    files_changed=[
                        "par_model_v2/projection/multi_driver_tail_diagnostics.py"
                    ],
                    test_summary=(
                        "5D VaR{:.1f}%={:.1f}; converged={}; rec_N>={}; CI=[{:.1f},{:.1f}]; "
                        "SE={:.1f}; anti_ratio={:.2f}; sobol_ratio={:.2f}".format(
                            cfg.confidence_level * 100, convergence.final_var,
                            convergence.converged, convergence.recommended_n_outer,
                            bootstrap.var_ci_low, bootstrap.var_ci_high,
                            bootstrap.var_standard_error,
                            vr.antithetic_var_ratio, vr.sobol_var_ratio)
                    ),
                )
                governance_store.audit_trail.append(entry)
                audit_entry_id = entry.entry_id
            except Exception as exc:  # pragma: no cover - governance optional
                notes.append("Governance audit append skipped: {}".format(exc))

        return FiveDriverTailReport(
            config=cfg, lsmc_summary=surface.summary(),
            convergence=convergence, bootstrap=bootstrap, variance_reduction=vr,
            run_id=run_id, duration_seconds=duration, verdict=verdict,
            reproducibility_digest=digest, notes=notes, audit_entry_id=audit_entry_id,
        )

    @staticmethod
    def _verdict(
        cfg: FiveDriverTailConfig,
        convergence: OuterConvergence,
        bootstrap: BootstrapInterval,
        vr: VarianceReduction5D,
        notes: List[str],
    ) -> str:
        var_in_ci = bootstrap.var_ci_low <= convergence.final_var <= bootstrap.var_ci_high
        best_ratio = max(vr.antithetic_var_ratio, vr.sobol_var_ratio)
        checks = [
            convergence.converged,
            var_in_ci,
            best_ratio > 1.0,
        ]
        if not convergence.converged:
            notes.append("99.5% VaR not converged within outer_grid; extend N_outer.")
        if not var_in_ci:
            notes.append("Convergence VaR lies outside the bootstrap CI (independent samples); review.")
        if vr.antithetic_var_ratio < 1.0:
            notes.append(
                "Antithetic variates do not reduce the 99.5% VaR-estimator variance "
                "(ratio {:.2f}<1) - expected for an extreme quantile; QMC is the "
                "effective scheme here (ratio {:.2f}).".format(
                    vr.antithetic_var_ratio, vr.sobol_var_ratio))
        if vr.sobol_var_ratio < 1.0:
            notes.append("Sobol QMC did not reduce VaR-estimator variance for this surface.")
        if all(checks):
            return "PASS - five-driver 99.5% capital metric converges, is bounded by a bootstrap CI, and benefits from variance reduction"
        return "PARTIAL - five-driver tail diagnostics generated with review items"


def five_driver_tail_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the five-driver tail diagnostics.

    SOA ASOP 56 §3.5.1; SOA ASOP 7 §3.3; SOA ASOP 25 §3.3; IA TAS M §3.6.
    """
    return {
        "module": "par_model_v2/projection/multi_driver_tail_diagnostics.py",
        "component": "FiveDriverTailDiagnostics",
        "classification": "EDUCATIONAL ONLY - NOT a regulatory capital model",
        "risk_drivers": [
            "short rate", "equity level", "credit spread",
            "lapse behaviour", "mortality trend"],
        "method": (
            "Outer-count convergence, non-parametric bootstrap CI/SE on the 99.5% "
            "VaR/ES, and a crude/antithetic/Sobol variance-reduction comparison for the "
            "five-driver 99.5% capital metric, built on the Phase 19 Task 3 quintivariate "
            "LSMC surface (the outer-sampling error is probed; proxy error is bounded "
            "separately by the five-driver OOS proxy-validation report)."
        ),
        "limitations": [
            "Outer sampling and bootstrap diagnostics probe Monte-Carlo error only; the proxy (surface) error is bounded separately by the five-driver OOS validation.",
            "The variance-reduction study runs on a smooth pilot-anchored Gaussian-copula surrogate of the horizon-state distribution, NOT the raw governed processes; antithetic/QMC require a controllable normal/uniform driver.",
            "Five drivers only (rates + equity + credit + lapse + mortality-trend); FX and liquidity remain outside the tail.",
            "Mortality trend is a single systemic OU index (Lee-Carter-style) with placeholder parameters; the benefit coupling is educational.",
            "Lapse behaviour is a single systemic OU index with placeholder parameters; the in-force coupling is multiplicative and educational.",
            "Independent APS X2 review and credentialled calibration data are still required before any production use.",
        ],
        "standards": [
            "SOA ASOP 56 §3.5",
            "SOA ASOP 56 §3.1.3",
            "SOA ASOP 25 §3.3",
            "SOA ASOP 7 §3.3",
            "IA TAS M §3.6",
            "L'Ecuyer (2018) RQMC",
        ],
    }


def five_driver_tail_use_restrictions_json() -> str:
    return json.dumps(five_driver_tail_use_restrictions(), indent=2, sort_keys=True)
