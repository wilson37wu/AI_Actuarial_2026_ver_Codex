"""
Multi-Driver (Rates + Equity) Nested / LSMC Economic-Capital Proxy
==================================================================

Phase 15 Task 1.  Generalises the *single-factor* (short-rate-only) nested /
LSMC capital proxy of Phase 14 Task 6
(:mod:`par_model_v2.projection.nested_stochastic_tvog`) to **two correlated
risk drivers**:

    x = (r_H, S_H)   — the short rate AND the equity-index level at the
                       capital horizon H.

This directly closes the documented single-risk-driver limitation of the
Task 6 proxy ("Equity, lapse, credit-spread, and FX risks are NOT in the
tail").  The capital tail is now driven by *both* the interest-rate level and
the equity level at the horizon, with their ESG correlation ``rho`` carried
through the outer projection AND the inner Q nest.

Two-driver liability
--------------------
The conditional, horizon-H Q-value of the residual guarantee now has two
components valued on the **same** correlated inner (rate, equity) paths:

1. *Guaranteed benefits* (rate-driven).  Residual death + maturity guaranteed
   cashflows, discounted along the inner short-rate path.  Identical to the
   Task 6 liability — recovered exactly when the equity guarantee is switched
   off.

2. *Equity-linked maturity guarantee* (a GMMB / put-style guarantee, both
   drivers).  The policyholder fund holds ``units = sum_assured / S0`` units of
   the equity index.  At maturity ``T`` the insurer tops the fund up to a
   guaranteed floor ``G = guarantee_rate * sum_assured``:

       equity_guarantee_payoff(T) = max( G - units * S_T , 0 )

   discounted from T back to H along the inner rate path.  Because the inner
   equity process is started at the conditioning level ``S_H`` and drifts at
   the inner short rate under Q (``mu^Q = r - q``), the put value depends on
   **both** ``r_H`` (discounting + risk-neutral drift) and ``S_H`` (moneyness).

So

    L(r_H, S_H) = E^Q[ disc(H,T) . guaranteed_cf | r_H ]
                + E^Q[ disc(H,T) . max(G - units S_T, 0) | r_H, S_H ]

For a guarantee an *increase* in value is the insurer's loss, so capital is the
upper tail of ``L`` across the outer (real-world / P) distribution of
``(r_H, S_H)`` — exactly as in Task 6 but over a 2-D state.

Multivariate LSMC surface
-------------------------
The Longstaff-Schwartz conditional-expectation surface is now a **bivariate
total-degree polynomial**

    L_hat(r, S) = sum_{a+b <= degree} beta_{a,b} . r_c^a . S_c^b

where ``r_c``/``S_c`` are the per-dimension centred/scaled states (for
numerical conditioning).  The basis has ``(degree+1)(degree+2)/2`` terms.  As
in Task 6 the regression averages out single-inner-path noise, recovering the
two-driver conditional expectation at ``N_fit`` inner valuations instead of
``N_outer x n_inner``.

Engines (mirror the Task 6 API)
-------------------------------
1. ``MultiDriverNestedEngine``      — brute-force two-driver ground truth.
2. ``MultiDriverLSMCProxyEngine``   — bivariate-polynomial LSMC proxy.
3. ``MultiDriverDiagnostics``       — proxy-vs-nested agreement on a 2-D state
   grid, reproducibility digest, and (reused) inner-SE convergence.

ASOP / IA standards
-------------------
- SOA ASOP 56 §3.1.3 — stochastic model documentation & output governance
- SOA ASOP 56 §3.5   — scenario adequacy & convergence diagnostics
- SOA ASOP 25 §3.3   — scenario generation adequacy (correlated drivers)
- IA TAS M §3.2      — market-consistent valuation
- IA TAS M §3.6      — model validation, convergence, reproducibility
- IFoA MCEV Principles §7 — TVOG / guarantee methodology
- Longstaff & Schwartz (2001) — least-squares Monte-Carlo

Model-use restrictions (see ``multi_driver_use_restrictions()``)
----------------------------------------------------------------
EDUCATIONAL ONLY.  Two risk drivers (rates + equity) — lapse, credit-spread,
mortality-trend and FX risks are still NOT in the tail.  Placeholder HW1F/GBM
parameters.  The bivariate polynomial surface is valid only across the *fitted*
2-D state region; extrapolation is unsupported.  Not a regulatory SCR.
Independent APS X2 review pending.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

import numpy as np

if TYPE_CHECKING:
    from par_model_v2.governance.audit_trail import GovernanceStore

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.nested_stochastic_tvog import (
    CapitalMetrics,
    capital_metrics_from_liabilities,
    _inner_q_process,
    _residual_cashflow_vector,
    _vectorised_discount_factors,
    DEFAULT_CAPITAL_HORIZON_MONTHS,
    DEFAULT_CONFIDENCE_LEVEL,
    CAPITAL_OUTER_MINIMUM,
)
from par_model_v2.stochastic.esg_process import (
    GBMParams,
    GBMEquityProcess,
    HullWhiteParams,
    Measure,
    RiskFreeCurve,
    ScenarioSet,
    _antithetic_normals,
)


#: Default total polynomial degree for the bivariate LSMC surface.
DEFAULT_MULTI_LSMC_DEGREE = 2


# ---------------------------------------------------------------------------
# Equity-linked maturity-guarantee specification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EquityGuaranteeSpec:
    """Educational equity-linked maturity guarantee (GMMB / put-style).

    The policyholder fund holds ``units = sum_assured / initial_index_level``
    units of the equity index from issue.  At maturity the insurer guarantees a
    floor ``G = guarantee_rate * sum_assured`` on the fund, i.e. it pays the
    shortfall ``max(G - units * S_T, 0)``.  This is a European put on the fund.

    Parameters
    ----------
    guarantee_rate : float
        Guaranteed fraction of ``sum_assured`` at maturity (1.0 = money-back).
    initial_index_level : float
        Equity-index level at issue used to size ``units`` (matches the ESG's
        ``GBMParams.initial_index_level`` default of 100.0).
    """
    guarantee_rate: float = 1.0
    initial_index_level: float = 100.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.guarantee_rate <= 5.0):
            raise ValueError("guarantee_rate must be in [0, 5]; got {}".format(self.guarantee_rate))
        if self.initial_index_level <= 0.0:
            raise ValueError("initial_index_level must be positive")

    def units(self, sum_assured: float) -> float:
        return float(sum_assured) / float(self.initial_index_level)

    def floor(self, sum_assured: float) -> float:
        return float(self.guarantee_rate) * float(sum_assured)


# ---------------------------------------------------------------------------
# Two-driver inner valuation: L(r_H, S_H)
# ---------------------------------------------------------------------------

def _inner_pathwise_pvs_2d(
    r: float,
    s: float,
    n_inner: int,
    rem_months: int,
    product: ParEndowmentProduct,
    base_hw_params: HullWhiteParams,
    gbm_params: GBMParams,
    h_month: int,
    seed: int,
    equity_guarantee: EquityGuaranteeSpec,
    annual_qx_fn: Optional[Callable] = None,
) -> np.ndarray:
    """Return ``n_inner`` pathwise residual-PV samples at state ``(r, s)``.

    Each sample is an unbiased draw of
    ``L(r, s) = E^Q[ guaranteed-benefit PV + equity-guarantee PV | r_H=r, S_H=s ]``.

    The inner rate and equity shocks are correlated by
    ``gbm_params.rate_equity_correlation`` via the same Cholesky construction
    used by :meth:`ScenarioSet.generate`
    (``z_S = rho z_r + sqrt(1-rho^2) z_indep``).  Antithetic normals provide
    inner variance reduction (ASOP 56 §3.5).
    """
    rng = np.random.default_rng(seed)
    z_rate = _antithetic_normals(rng, n_inner, rem_months)
    z_indep = _antithetic_normals(rng, n_inner, rem_months)
    rho = float(gbm_params.rate_equity_correlation)
    z_equity = rho * z_rate + np.sqrt(1.0 - rho ** 2) * z_indep

    # Inner Q processes conditioned on the outer state.
    hw = _inner_q_process(r, base_hw_params)
    inner_gbm_params = GBMParams(
        equity_vol=gbm_params.equity_vol,
        dividend_yield=gbm_params.dividend_yield,
        equity_risk_premium=gbm_params.equity_risk_premium,
        rate_equity_correlation=gbm_params.rate_equity_correlation,
        initial_index_level=float(s),          # condition on S_H
    )
    gbm = GBMEquityProcess(inner_gbm_params, rate_process=hw)

    rate_paths = hw._simulate_array(n_inner, rem_months, Measure.Q, z_rate)       # (n, rem+1)
    equity_paths, _ret = gbm._simulate_array(
        n_inner, rem_months, Measure.Q, rate_paths, z_equity                       # (n, rem+1)
    )
    disc = _vectorised_discount_factors(rate_paths)                                # (n, rem+1)

    # Component 1 — guaranteed death + maturity benefits (rate-driven).
    cf = _residual_cashflow_vector(product, h_month, annual_qx_fn)                 # (rem+1,)
    guaranteed_pv = disc @ cf                                                       # (n,)

    # Component 2 — equity-linked maturity guarantee (rates + equity).
    units = equity_guarantee.units(product.sum_assured)
    floor = equity_guarantee.floor(product.sum_assured)
    fund_T = units * equity_paths[:, rem_months]
    eq_payoff = np.maximum(floor - fund_T, 0.0)
    eq_guarantee_pv = disc[:, rem_months] * eq_payoff                              # (n,)

    return guaranteed_pv + eq_guarantee_pv


# ---------------------------------------------------------------------------
# Two-driver outer-state sampling
# ---------------------------------------------------------------------------

def _outer_states_2d(
    n_outer: int,
    capital_horizon_months: int,
    measure: Measure,
    hw_params: HullWhiteParams,
    gbm_params: GBMParams,
    initial_curve: Optional[RiskFreeCurve],
    seed: int,
) -> np.ndarray:
    """Project ``n_outer`` outer paths to H; return an (n, 2) array of (r_H, S_H).

    Uses the governed :meth:`ScenarioSet.generate` path so the correlated
    rate/equity outer drivers share the model's measure-enforcement, Cholesky
    correlation, and parameter-snapshot machinery.
    """
    scen = ScenarioSet.generate(
        n=n_outer,
        T_months=capital_horizon_months,
        measure=measure,
        hw_params=hw_params,
        gbm_params=gbm_params,
        initial_curve=initial_curve,
        seed=seed,
    )
    rate_pivot = scen.data.pivot(index="scenario_id", columns="month", values="r_short")
    eq_pivot = scen.data.pivot(index="scenario_id", columns="month", values="equity_index")
    r_h = rate_pivot[capital_horizon_months].to_numpy(dtype=float)
    s_h = eq_pivot[capital_horizon_months].to_numpy(dtype=float)
    return np.column_stack([r_h, s_h])


# ---------------------------------------------------------------------------
# Bivariate total-degree polynomial basis
# ---------------------------------------------------------------------------

def _multi_poly_powers(degree: int) -> List[Tuple[int, int]]:
    """Exponent pairs (a, b) with a + b <= degree, ordered by total degree.

    e.g. degree 2 -> [(0,0),(1,0),(0,1),(2,0),(1,1),(0,2)] (6 terms).
    """
    powers: List[Tuple[int, int]] = []
    for total in range(degree + 1):
        for a in range(total + 1):
            powers.append((a, total - a))
    return powers


def _multi_poly_basis(X: np.ndarray, degree: int) -> np.ndarray:
    """Bivariate total-degree design matrix for X of shape (n, 2).

    Column j is ``X[:,0]**a * X[:,1]**b`` for the j-th (a, b) in
    :func:`_multi_poly_powers`.  Returns shape (n, n_terms).
    """
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[1] != 2:
        raise ValueError("X must have shape (n, 2); got {}".format(X.shape))
    powers = _multi_poly_powers(degree)
    cols = [X[:, 0] ** a * X[:, 1] ** b for (a, b) in powers]
    return np.column_stack(cols)


def _n_basis_terms(degree: int) -> int:
    return (degree + 1) * (degree + 2) // 2


# ---------------------------------------------------------------------------
# 1. Two-driver nested-stochastic engine (ground truth)
# ---------------------------------------------------------------------------

@dataclass
class MultiDriverNestedResult:
    """Result of a full two-driver nested-stochastic capital run."""
    capital: CapitalMetrics
    outer_states: np.ndarray              # (n_outer, 2): columns r_H, S_H
    conditional_liabilities: np.ndarray   # L(r_i, S_i), one per outer node
    inner_standard_errors: np.ndarray
    n_outer: int
    n_inner: int
    total_inner_valuations: int
    run_id: str
    duration_seconds: float
    audit_entry_id: Optional[str] = None

    def summary(self) -> dict:
        return {
            "capital": self.capital.summary(),
            "n_outer": self.n_outer,
            "n_inner": self.n_inner,
            "total_inner_valuations": self.total_inner_valuations,
            "mean_inner_se": round(float(self.inner_standard_errors.mean()), 6),
            "drivers": ["short_rate", "equity_level"],
            "run_id": self.run_id,
            "duration_seconds": round(self.duration_seconds, 4),
        }


class MultiDriverNestedEngine:
    """Brute-force two-driver nested-stochastic capital engine (ground truth).

    Outer real-world scenarios → state ``(r_H, S_H)`` → fresh correlated inner
    (rate, equity) Q nest per node → ``L(r_H, S_H)`` → capital metrics.
    Expensive but unbiased; benchmarks the bivariate LSMC proxy.

    SOA ASOP 56 §3.1.3/§3.5; IA TAS M §3.2/§3.6; ASOP 25 §3.3 (correlation).
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        outer_measure: Measure = Measure.P,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        if not (0 < capital_horizon_months < product.term_months):
            raise ValueError(
                "capital_horizon_months ({}) must satisfy 0 < H < term_months "
                "({})".format(capital_horizon_months, product.term_months)
            )
        if not (0.5 < confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0.5, 1.0)")
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.capital_horizon_months = int(capital_horizon_months)
        self.confidence_level = float(confidence_level)
        self.outer_measure = Measure(outer_measure)
        self.annual_qx_fn = annual_qx_fn

    def run(
        self,
        n_outer: int = CAPITAL_OUTER_MINIMUM,
        n_inner: int = 256,
        seed: int = 42,
        governance_store: Optional["GovernanceStore"] = None,
        actor: str = "MultiDriverNestedEngine",
        phase: str = "Phase 15: Multi-Risk Economic Capital and Proxy-Model Validation",
    ) -> MultiDriverNestedResult:
        t0 = time.monotonic()
        run_id = "md-nested-" + uuid.uuid4().hex[:8]
        rem = self.product.term_months - self.capital_horizon_months

        outer = _outer_states_2d(
            n_outer, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.initial_curve, seed,
        )
        child_seeds = np.random.SeedSequence(seed).spawn(len(outer))
        cond_l = np.empty(len(outer), dtype=float)
        inner_se = np.empty(len(outer), dtype=float)
        for i, (r, s) in enumerate(outer):
            inner_seed = int(child_seeds[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_2d(
                float(r), float(s), n_inner, rem, self.product, self.hw_params,
                self.gbm_params, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.annual_qx_fn,
            )
            cond_l[i] = float(pvs.mean())
            inner_se[i] = float(pvs.std(ddof=1) / np.sqrt(n_inner)) if n_inner > 1 else 0.0

        capital = capital_metrics_from_liabilities(
            cond_l, self.confidence_level, self.capital_horizon_months
        )
        duration = time.monotonic() - t0

        audit_entry_id = None
        if governance_store is not None:
            from par_model_v2.governance.audit_trail import AuditEntry

            entry = AuditEntry.model_run(
                actor=actor, phase=phase, run_id=run_id,
                scenario_count=n_outer * n_inner,
                duration_seconds=round(duration, 4), outcome="PASS",
                files_changed=["par_model_v2/projection/multi_driver_capital.py"],
                test_summary=(
                    "2D-nested VaR{:.1f}%={:.2f}; ES={:.2f}; SCR_proxy={:.2f}; "
                    "N_outer={}; n_inner={}; drivers=r,S".format(
                        self.confidence_level * 100, capital.var_liability,
                        capital.es_liability, capital.scr_proxy, n_outer, n_inner)
                ),
            )
            governance_store.audit_trail.append(entry)
            audit_entry_id = entry.entry_id

        return MultiDriverNestedResult(
            capital=capital, outer_states=outer, conditional_liabilities=cond_l,
            inner_standard_errors=inner_se, n_outer=len(outer), n_inner=n_inner,
            total_inner_valuations=len(outer) * n_inner, run_id=run_id,
            duration_seconds=duration, audit_entry_id=audit_entry_id,
        )


# ---------------------------------------------------------------------------
# 2. Two-driver LSMC proxy engine
# ---------------------------------------------------------------------------

@dataclass
class MultiDriverLSMCResult:
    """Result of a bivariate-polynomial LSMC proxy capital run."""
    capital: CapitalMetrics
    beta: np.ndarray
    centers: np.ndarray                # (2,) per-driver centring
    scales: np.ndarray                 # (2,) per-driver scaling
    degree: int
    powers: List[Tuple[int, int]]
    fit_r2: float
    n_fit: int
    n_outer_eval: int
    fitted_liabilities: np.ndarray
    fit_states: np.ndarray             # (n_fit, 2)
    fit_payoffs: np.ndarray
    run_id: str
    duration_seconds: float
    audit_entry_id: Optional[str] = None

    def predict(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        Xs = (X - self.centers) / self.scales
        return _multi_poly_basis(Xs, self.degree) @ self.beta

    def summary(self) -> dict:
        return {
            "capital": self.capital.summary(),
            "degree": self.degree,
            "n_basis_terms": len(self.powers),
            "fit_r2": round(self.fit_r2, 6),
            "n_fit": self.n_fit,
            "n_outer_eval": self.n_outer_eval,
            "drivers": ["short_rate", "equity_level"],
            "run_id": self.run_id,
            "duration_seconds": round(self.duration_seconds, 4),
        }


class MultiDriverLSMCProxyEngine:
    """Bivariate Longstaff-Schwartz least-squares Monte-Carlo capital proxy.

    Fits ``L_hat(r, S) = phi(r, S) . beta`` (total-degree bivariate polynomial)
    from ``N_fit`` noisy single-inner-path samples, then evaluates the surface
    across a large (cheap) correlated outer set.  Recovers the two-driver
    conditional expectation at ``N_fit`` inner valuations instead of
    ``N_outer x n_inner``.

    Longstaff & Schwartz (2001); IFoA proxy-model working-party guidance.
    SOA ASOP 56 §3.5; IA TAS M §3.6; ASOP 25 §3.3 (correlated drivers).
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        outer_measure: Measure = Measure.P,
        degree: int = DEFAULT_MULTI_LSMC_DEGREE,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        if not (0 < capital_horizon_months < product.term_months):
            raise ValueError("capital_horizon_months must satisfy 0 < H < term_months")
        if degree < 1:
            raise ValueError("LSMC polynomial degree must be >= 1")
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.capital_horizon_months = int(capital_horizon_months)
        self.confidence_level = float(confidence_level)
        self.outer_measure = Measure(outer_measure)
        self.degree = int(degree)
        self.annual_qx_fn = annual_qx_fn

    def _fit_payoffs(self, fit_X: np.ndarray, seed: int) -> np.ndarray:
        rem = self.product.term_months - self.capital_horizon_months
        child_seeds = np.random.SeedSequence(seed + 1).spawn(len(fit_X))
        fit_y = np.empty(len(fit_X), dtype=float)
        for i, (r, s) in enumerate(fit_X):
            inner_seed = int(child_seeds[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_2d(
                float(r), float(s), 1, rem, self.product, self.hw_params,
                self.gbm_params, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.annual_qx_fn,
            )
            fit_y[i] = float(pvs[0])
        return fit_y

    def fit_and_run(
        self,
        n_fit: int = 2_000,
        n_outer_eval: int = 5_000,
        seed: int = 42,
        governance_store: Optional["GovernanceStore"] = None,
        actor: str = "MultiDriverLSMCProxyEngine",
        phase: str = "Phase 15: Multi-Risk Economic Capital and Proxy-Model Validation",
    ) -> MultiDriverLSMCResult:
        t0 = time.monotonic()
        run_id = "md-lsmc-" + uuid.uuid4().hex[:8]

        # --- fitting set: N_fit correlated outer states, ONE inner path each
        fit_X = _outer_states_2d(
            n_fit, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.initial_curve, seed,
        )
        fit_y = self._fit_payoffs(fit_X, seed)

        # --- regression (per-dimension centred/scaled for conditioning) -----
        centers = fit_X.mean(axis=0)
        scales = fit_X.std(axis=0, ddof=0)
        scales = np.where(scales > 0, scales, 1.0)
        Xs = (fit_X - centers) / scales
        design = _multi_poly_basis(Xs, self.degree)
        beta, _resid, _rank, _sv = np.linalg.lstsq(design, fit_y, rcond=None)
        y_hat = design @ beta
        ss_res = float(np.sum((fit_y - y_hat) ** 2))
        ss_tot = float(np.sum((fit_y - fit_y.mean()) ** 2)) or 1.0
        fit_r2 = 1.0 - ss_res / ss_tot

        # --- evaluation: large cheap correlated outer set ------------------
        eval_X = _outer_states_2d(
            n_outer_eval, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.initial_curve, seed + 2,
        )
        eval_Xs = (eval_X - centers) / scales
        fitted_l = _multi_poly_basis(eval_Xs, self.degree) @ beta

        capital = capital_metrics_from_liabilities(
            fitted_l, self.confidence_level, self.capital_horizon_months
        )
        duration = time.monotonic() - t0

        audit_entry_id = None
        if governance_store is not None:
            from par_model_v2.governance.audit_trail import AuditEntry

            entry = AuditEntry.model_run(
                actor=actor, phase=phase, run_id=run_id, scenario_count=n_fit,
                duration_seconds=round(duration, 4), outcome="PASS",
                files_changed=["par_model_v2/projection/multi_driver_capital.py"],
                test_summary=(
                    "2D-LSMC VaR{:.1f}%={:.2f}; ES={:.2f}; SCR_proxy={:.2f}; "
                    "R2={:.4f}; N_fit={}; deg={}; terms={}".format(
                        self.confidence_level * 100, capital.var_liability,
                        capital.es_liability, capital.scr_proxy, fit_r2,
                        n_fit, self.degree, _n_basis_terms(self.degree))
                ),
            )
            governance_store.audit_trail.append(entry)
            audit_entry_id = entry.entry_id

        return MultiDriverLSMCResult(
            capital=capital, beta=beta, centers=centers, scales=scales,
            degree=self.degree, powers=_multi_poly_powers(self.degree),
            fit_r2=fit_r2, n_fit=len(fit_X), n_outer_eval=len(eval_X),
            fitted_liabilities=fitted_l, fit_states=fit_X, fit_payoffs=fit_y,
            run_id=run_id, duration_seconds=duration, audit_entry_id=audit_entry_id,
        )


# ---------------------------------------------------------------------------
# 3. Two-driver diagnostics
# ---------------------------------------------------------------------------

@dataclass
class MultiDriverProxyAgreement:
    """Proxy-vs-nested agreement on a 2-D state grid."""
    max_abs_rel_error: float
    rmse: float
    r2_vs_nested: float
    grid_states: np.ndarray   # (m, 2)
    nested_l: np.ndarray
    proxy_l: np.ndarray

    def summary(self) -> dict:
        return {
            "max_abs_rel_error": round(self.max_abs_rel_error, 6),
            "rmse": round(self.rmse, 6),
            "r2_vs_nested": round(self.r2_vs_nested, 6),
            "n_grid": int(self.grid_states.shape[0]),
        }


class MultiDriverDiagnostics:
    """Proxy-vs-nested agreement, reproducibility, and inner SE for 2-D state.

    SOA ASOP 56 §3.5 (convergence); IA TAS M §3.6 (validation & reproducibility).
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.capital_horizon_months = int(capital_horizon_months)
        self.annual_qx_fn = annual_qx_fn

    def nested_liability(self, r: float, s: float, n_inner: int = 4_096, seed: int = 11) -> float:
        """High-accuracy nested L(r, S) at a single state (for grid benchmarks)."""
        rem = self.product.term_months - self.capital_horizon_months
        pvs = _inner_pathwise_pvs_2d(
            float(r), float(s), n_inner, rem, self.product, self.hw_params,
            self.gbm_params, self.capital_horizon_months, seed,
            self.equity_guarantee, self.annual_qx_fn,
        )
        return float(pvs.mean())

    def proxy_vs_nested(
        self,
        proxy: MultiDriverLSMCResult,
        grid_per_dim: int = 4,
        n_inner: int = 4_096,
        seed: int = 11,
    ) -> MultiDriverProxyAgreement:
        """Compare the bivariate LSMC surface to nested L on a 2-D state grid.

        The grid spans the 10-90 percentile box of the fitted states (robust to
        outer-tail outliers) so the comparison stays inside the fitted region.
        """
        r_states = proxy.fit_states[:, 0]
        s_states = proxy.fit_states[:, 1]
        r_lo, r_hi = np.quantile(r_states, [0.1, 0.9])
        s_lo, s_hi = np.quantile(s_states, [0.1, 0.9])
        r_grid = np.linspace(r_lo, r_hi, grid_per_dim)
        s_grid = np.linspace(s_lo, s_hi, grid_per_dim)
        grid = np.array([[r, s] for r in r_grid for s in s_grid], dtype=float)

        child = np.random.SeedSequence(seed).spawn(len(grid))
        nested = np.empty(len(grid), dtype=float)
        rem = self.product.term_months - self.capital_horizon_months
        for i, (r, s) in enumerate(grid):
            sd = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_2d(
                float(r), float(s), n_inner, rem, self.product, self.hw_params,
                self.gbm_params, self.capital_horizon_months, sd,
                self.equity_guarantee, self.annual_qx_fn,
            )
            nested[i] = float(pvs.mean())
        proxy_l = proxy.predict(grid)
        denom = np.where(np.abs(nested) > 1e-9, np.abs(nested), 1.0)
        rel = np.abs(proxy_l - nested) / denom
        rmse = float(np.sqrt(np.mean((proxy_l - nested) ** 2)))
        ss_res = float(np.sum((nested - proxy_l) ** 2))
        ss_tot = float(np.sum((nested - nested.mean()) ** 2)) or 1.0
        return MultiDriverProxyAgreement(
            max_abs_rel_error=float(rel.max()), rmse=rmse,
            r2_vs_nested=1.0 - ss_res / ss_tot, grid_states=grid,
            nested_l=nested, proxy_l=proxy_l,
        )

    @staticmethod
    def reproducibility_digest(arr: np.ndarray) -> str:
        """SHA-256 of a float array rounded to 1e-9 (seed-determinism check)."""
        rounded = np.round(np.asarray(arr, dtype=float), 9)
        return hashlib.sha256(rounded.tobytes()).hexdigest()


# ---------------------------------------------------------------------------
# Model-use restrictions (governance disclosure)
# ---------------------------------------------------------------------------

def multi_driver_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the two-driver capital proxy.

    SOA ASOP 56 §3.5.1; IA TAS M §3.6.
    """
    return {
        "module": "par_model_v2/projection/multi_driver_capital.py",
        "classification": "EDUCATIONAL ONLY — NOT a regulatory capital model",
        "risk_drivers": (
            "Capital tail is driven by TWO correlated drivers at the horizon: "
            "the short rate r_H and the equity level S_H (ESG correlation rho "
            "carried through outer and inner). Lapse, credit-spread, "
            "mortality-trend, and FX risks are still NOT in the tail."
        ),
        "improvement_over_task6": (
            "Closes the documented single-risk-driver limitation of the Phase "
            "14 Task 6 proxy by adding the equity driver and an equity-linked "
            "maturity guarantee (GMMB / put) to the conditional liability."
        ),
        "placeholder_parameters": (
            "HW1F and GBM parameters are illustrative placeholders; capital "
            "magnitudes are NOT calibrated."
        ),
        "lsmc_extrapolation": (
            "The bivariate polynomial surface L_hat(r, S) is valid only across "
            "the fitted 2-D state region (interquartile box). Extrapolation "
            "beyond it is unsupported and may be unstable at high degree."
        ),
        "convergence_requirements": (
            "Inner standard error decays ~1/sqrt(n_inner); 99.5% capital "
            "requires N_outer >= {} (ASOP 56 §3.5). Proxy-vs-nested agreement "
            "must be reviewed before any figure is cited.".format(CAPITAL_OUTER_MINIMUM)
        ),
        "no_management_actions": (
            "No dynamic management actions, bonus reactions, or asset "
            "rebalancing are modelled in the inner valuation."
        ),
        "governance": (
            "Independent APS X2 review pending; production sign-off withheld. "
            "Use only for education, methodology demonstration, and testing."
        ),
        "standards": [
            "SOA ASOP 56 §3.1.3", "SOA ASOP 56 §3.5", "SOA ASOP 25 §3.3",
            "IA TAS M §3.2", "IA TAS M §3.6", "IFoA MCEV Principles §7",
            "Longstaff & Schwartz (2001)",
        ],
    }


def multi_driver_use_restrictions_json() -> str:
    return json.dumps(multi_driver_use_restrictions(), indent=2, sort_keys=True)


__all__ = [
    "DEFAULT_MULTI_LSMC_DEGREE",
    "EquityGuaranteeSpec",
    "MultiDriverNestedResult",
    "MultiDriverNestedEngine",
    "MultiDriverLSMCResult",
    "MultiDriverLSMCProxyEngine",
    "MultiDriverProxyAgreement",
    "MultiDriverDiagnostics",
    "multi_driver_use_restrictions",
    "multi_driver_use_restrictions_json",
    "_inner_pathwise_pvs_2d",
    "_outer_states_2d",
    "_multi_poly_basis",
    "_multi_poly_powers",
    "_n_basis_terms",
]
