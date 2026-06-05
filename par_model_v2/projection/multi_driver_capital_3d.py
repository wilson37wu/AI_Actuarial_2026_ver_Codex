"""
Three-Driver (Rates + Equity + Credit Spread) Nested / LSMC Capital Proxy
=========================================================================

Phase 17 Task 1.  Generalises the Phase 15 *two-driver* (rates + equity) nested
/ LSMC economic-capital proxy
(:mod:`par_model_v2.projection.multi_driver_capital`) to **three correlated
risk drivers**:

    x = (r_H, S_H, s_H)  — the short rate, the equity-index level, AND the
                           credit spread at the capital horizon H.

This directly extends the documented Phase 15 limitation ("lapse, **credit-
spread**, mortality-trend and FX risks are still NOT in the tail").  The credit
spread is supplied by the new CIR++ driver
(:mod:`par_model_v2.stochastic.credit_spread`), P- and Q-measure consistent.

Three-driver liability
----------------------
The conditional horizon-H Q-value of the residual obligation now has THREE
components valued on the **same** correlated inner ``(rate, equity, spread)``
paths:

1. *Guaranteed benefits* (rate-driven) — identical to the two-driver module;
   recovered exactly when the equity guarantee and credit exposure are off.
2. *Equity-linked maturity guarantee* (rates + equity) — the GMMB / put on the
   policyholder fund, identical to the two-driver module.
3. *Credit loss on spread-sensitive backing assets* (rates + credit).  The
   insurer backs the obligation with a notional ``credit_exposure_rate *
   sum_assured`` of spread-sensitive (e.g. corporate / private-credit) assets.
   Interpreting the spread as a reduced-form ``hazard × LGD`` proxy
   (Duffie-Singleton), the conditional expected credit-loss PV is

       credit_pv = disc(H,T) . notional . (1 - exp(-∫_H^T s(u) du))

   valued on the inner spread path started at the conditioning level ``s_H`` and
   discounted along the inner short-rate path.  A *wider* horizon spread raises
   the loss, so capital is the upper tail of ``L`` across the outer (P)
   distribution of ``(r_H, S_H, s_H)``.

So

    L(r_H, S_H, s_H) = guaranteed_pv(r_H)
                     + equity_guarantee_pv(r_H, S_H)
                     + credit_loss_pv(r_H, s_H)

Trivariate LSMC surface (pairwise + capped three-way interactions)
------------------------------------------------------------------
The Longstaff-Schwartz conditional-expectation surface is a **trivariate
total-degree polynomial** with controlled interaction order:

    L_hat(r, S, s) = sum_{(a,b,c) in P} beta_{abc} . r_c^a . S_c^b . s_c^c

where ``P`` contains every exponent triple with ``a + b + c <= degree``, EXCEPT
genuine three-way cross terms (all of ``a, b, c >= 1``) are *capped*: they are
admitted only while ``a + b + c <= max_interaction_order`` (default 3, i.e. only
the single ``r·S·s`` term enters at degree>=3).  Pairwise interactions (exactly
one zero exponent) are retained up to the full degree.  This keeps the design
matrix lean and well-conditioned as drivers grow — the recommended proxy-basis
discipline of the IFoA proxy-modelling working party.

Engines (mirror the two-driver / Task 6 API)
--------------------------------------------
1. ``ThreeDriverNestedEngine``    — brute-force three-driver ground truth.
2. ``ThreeDriverLSMCProxyEngine`` — trivariate-polynomial LSMC proxy.
3. ``ThreeDriverDiagnostics``     — proxy-vs-nested agreement on a 3-D state
   grid, reproducibility digest, inner-SE convergence.

ASOP / IA standards
-------------------
- SOA ASOP 56 §3.1.3 / §3.4 / §3.5 — model documentation, calibration, adequacy
- SOA ASOP 25 §3.3   — scenario generation adequacy (correlated drivers)
- IA TAS M §3.2 / §3.6 — market-consistent valuation, validation, reproducibility
- IFoA MCEV Principles §7; IFoA proxy-model working party
- Longstaff & Schwartz (2001); Duffie-Singleton (1999); CIR (1985)

Model-use restrictions (see ``three_driver_use_restrictions()``)
----------------------------------------------------------------
EDUCATIONAL ONLY.  Three risk drivers (rates + equity + credit spread) — lapse,
mortality-trend and FX risks are still NOT in the tail.  Placeholder
HW1F / GBM / CIR++ parameters; credit is a single systemic spread proxy with no
rating migration or default jump.  The trivariate polynomial surface is valid
only across the *fitted* 3-D state region; extrapolation is unsupported.  Not a
regulatory SCR.  Independent APS X2 review pending.
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
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.stochastic.esg_process import (
    GBMParams,
    GBMEquityProcess,
    HullWhiteParams,
    HullWhiteRateProcess,
    Measure,
    RiskFreeCurve,
    _antithetic_normals,
)
from par_model_v2.stochastic.credit_spread import (
    CreditSpreadParams,
    CreditSpreadProcess,
    _inner_q_spread_process,
)


#: Default total polynomial degree for the trivariate LSMC surface.
DEFAULT_TRI_LSMC_DEGREE = 2

#: Default cap on the *combined* order of genuine three-way (a,b,c all>=1) terms.
DEFAULT_MAX_INTERACTION_ORDER = 3


# ---------------------------------------------------------------------------
# Credit-exposure specification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CreditExposureSpec:
    """Educational spread-sensitive backing-asset exposure.

    The insurer is assumed to back the obligation with a notional
    ``exposure_rate * sum_assured`` of spread-sensitive assets whose expected
    credit-loss PV over ``[H, T]`` is driven by the horizon spread via the
    reduced-form ``1 - exp(-∫ s du)`` hazard×LGD proxy (Duffie-Singleton 1999).

    Parameters
    ----------
    exposure_rate : float
        Fraction of ``sum_assured`` held in spread-sensitive assets (>= 0).
    """
    exposure_rate: float = 1.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.exposure_rate <= 10.0):
            raise ValueError("exposure_rate must be in [0, 10]; got {}".format(self.exposure_rate))

    def notional(self, sum_assured: float) -> float:
        return float(self.exposure_rate) * float(sum_assured)


# ---------------------------------------------------------------------------
# Cross-driver correlation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThreeDriverCorrelation:
    """3x3 ESG correlation among (rate, equity, credit-spread) Brownian shocks.

    ``rate_equity`` defaults to ``None`` -> inherit the GBM's
    ``rate_equity_correlation``.  ``rate_spread`` is typically negative
    (flight-to-quality: rates fall as spreads widen); ``equity_spread`` is
    typically negative (equities fall as spreads widen).
    """
    rate_equity: Optional[float] = None
    rate_spread: float = -0.20
    equity_spread: float = -0.30

    def matrix(self, gbm_rate_equity: float) -> np.ndarray:
        r_se = self.rate_equity if self.rate_equity is not None else gbm_rate_equity
        C = np.array([
            [1.0, r_se, self.rate_spread],
            [r_se, 1.0, self.equity_spread],
            [self.rate_spread, self.equity_spread, 1.0],
        ], dtype=float)
        return C

    def cholesky(self, gbm_rate_equity: float) -> np.ndarray:
        """Lower-triangular Cholesky factor; nearest-PD fallback if needed.

        Placeholder correlations can violate positive-definiteness; we project
        to the nearest PD matrix by clipping eigenvalues (Higham-style) so the
        scheme stays well-defined (ASOP 25 §3.3).
        """
        C = self.matrix(gbm_rate_equity)
        try:
            return np.linalg.cholesky(C)
        except np.linalg.LinAlgError:
            w, V = np.linalg.eigh(C)
            w = np.clip(w, 1e-8, None)
            C_pd = V @ np.diag(w) @ V.T
            d = np.sqrt(np.diag(C_pd))
            C_pd = C_pd / np.outer(d, d)
            return np.linalg.cholesky(C_pd)


# ---------------------------------------------------------------------------
# Three correlated shock arrays
# ---------------------------------------------------------------------------

def _correlated_shocks_3(
    rng: np.random.Generator,
    n: int,
    steps: int,
    chol: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return three (n, steps) correlated antithetic-normal shock arrays.

    Independent antithetic normals are combined by the Cholesky factor so the
    per-step cross-sectional correlation matches ``chol @ chol.T`` (ASOP 56
    §3.5 variance reduction + ASOP 25 §3.3 correlation).
    """
    z0 = _antithetic_normals(rng, n, steps)
    z1 = _antithetic_normals(rng, n, steps)
    z2 = _antithetic_normals(rng, n, steps)
    zr = chol[0, 0] * z0
    zs = chol[1, 0] * z0 + chol[1, 1] * z1
    zc = chol[2, 0] * z0 + chol[2, 1] * z1 + chol[2, 2] * z2
    return zr, zs, zc


# ---------------------------------------------------------------------------
# Three-driver inner valuation: L(r_H, S_H, s_H)
# ---------------------------------------------------------------------------

def _inner_pathwise_pvs_3d(
    r: float,
    s: float,
    spread: float,
    n_inner: int,
    rem_months: int,
    product: ParEndowmentProduct,
    base_hw_params: HullWhiteParams,
    gbm_params: GBMParams,
    spread_params: CreditSpreadParams,
    correlation: ThreeDriverCorrelation,
    h_month: int,
    seed: int,
    equity_guarantee: EquityGuaranteeSpec,
    credit_exposure: CreditExposureSpec,
    annual_qx_fn: Optional[Callable] = None,
) -> np.ndarray:
    """Return ``n_inner`` pathwise residual-PV samples at state ``(r, s, spread)``.

    Each sample is an unbiased draw of
    ``L = E^Q[ guaranteed PV + equity-guarantee PV + credit-loss PV
              | r_H=r, S_H=s, s_H=spread ]`` on one correlated inner
    ``(rate, equity, spread)`` triple.
    """
    rng = np.random.default_rng(seed)
    chol = correlation.cholesky(gbm_params.rate_equity_correlation)
    z_rate, z_equity, z_spread = _correlated_shocks_3(rng, n_inner, rem_months, chol)

    # --- inner Q processes conditioned on the outer state -----------------
    hw = _inner_q_process(r, base_hw_params)
    inner_gbm_params = GBMParams(
        equity_vol=gbm_params.equity_vol,
        dividend_yield=gbm_params.dividend_yield,
        equity_risk_premium=gbm_params.equity_risk_premium,
        rate_equity_correlation=gbm_params.rate_equity_correlation,
        initial_index_level=float(s),
    )
    gbm = GBMEquityProcess(inner_gbm_params, rate_process=hw)
    csp = _inner_q_spread_process(spread, spread_params)

    rate_paths = hw._simulate_array(n_inner, rem_months, Measure.Q, z_rate)
    equity_paths, _ret = gbm._simulate_array(
        n_inner, rem_months, Measure.Q, rate_paths, z_equity
    )
    spread_paths = csp._simulate_array(n_inner, rem_months, Measure.Q, z_spread)
    disc = _vectorised_discount_factors(rate_paths)

    # Component 1 — guaranteed death + maturity benefits (rate-driven).
    cf = _residual_cashflow_vector(product, h_month, annual_qx_fn)
    guaranteed_pv = disc @ cf

    # Component 2 — equity-linked maturity guarantee (rates + equity).
    units = equity_guarantee.units(product.sum_assured)
    floor = equity_guarantee.floor(product.sum_assured)
    fund_T = units * equity_paths[:, rem_months]
    eq_payoff = np.maximum(floor - fund_T, 0.0)
    eq_guarantee_pv = disc[:, rem_months] * eq_payoff

    # Component 3 — credit loss on spread-sensitive backing assets
    # (rates discount + credit hazard). Reduced-form 1 - exp(-∫ s du), realised
    # at maturity and discounted from T back to H along the inner rate path.
    notional = credit_exposure.notional(product.sum_assured)
    dt = 1.0 / 12.0
    cum_hazard = spread_paths[:, :rem_months].sum(axis=1) * dt
    loss_fraction = 1.0 - np.exp(-cum_hazard)
    credit_loss_pv = disc[:, rem_months] * notional * loss_fraction

    return guaranteed_pv + eq_guarantee_pv + credit_loss_pv


# ---------------------------------------------------------------------------
# Three-driver outer-state sampling
# ---------------------------------------------------------------------------

def _outer_states_3d(
    n_outer: int,
    capital_horizon_months: int,
    measure: Measure,
    hw_params: HullWhiteParams,
    gbm_params: GBMParams,
    spread_params: CreditSpreadParams,
    correlation: ThreeDriverCorrelation,
    initial_curve: Optional[RiskFreeCurve],
    seed: int,
) -> np.ndarray:
    """Project ``n_outer`` outer paths to H; return an (n, 3) array (r_H,S_H,s_H).

    Drives the three building-block processes (HW1F rate, GBM equity, CIR++
    spread) directly off a SHARED, 3-factor Cholesky-correlated antithetic
    normal draw, so the outer ``(r, S, s)`` joint is genuinely correlated under
    the governed 3x3 ESG matrix (ASOP 25 §3.3).  Equivalent to the governed
    ``ScenarioSet.generate`` rate/equity path when the credit factor is removed.
    """
    rng = np.random.default_rng(seed)
    chol = correlation.cholesky(gbm_params.rate_equity_correlation)
    z_rate, z_equity, z_spread = _correlated_shocks_3(
        rng, n_outer, capital_horizon_months, chol
    )
    curve = initial_curve if initial_curve is not None else RiskFreeCurve.flat(
        hw_params.initial_short_rate
    )
    hw = HullWhiteRateProcess(hw_params, initial_curve=curve)
    gbm = GBMEquityProcess(gbm_params, rate_process=hw)
    csp = CreditSpreadProcess(spread_params)

    rate_paths = hw._simulate_array(n_outer, capital_horizon_months, measure, z_rate)
    equity_paths, _ret = gbm._simulate_array(
        n_outer, capital_horizon_months, measure, rate_paths, z_equity
    )
    spread_paths = csp._simulate_array(n_outer, capital_horizon_months, measure, z_spread)

    r_h = rate_paths[:, capital_horizon_months]
    s_h = equity_paths[:, capital_horizon_months]
    c_h = spread_paths[:, capital_horizon_months]
    return np.column_stack([r_h, s_h, c_h])


# ---------------------------------------------------------------------------
# Trivariate total-degree polynomial basis (pairwise + capped 3-way)
# ---------------------------------------------------------------------------

def _tri_poly_powers(
    degree: int,
    max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER,
) -> List[Tuple[int, int, int]]:
    """Exponent triples (a,b,c), a+b+c <= degree, with capped 3-way interactions.

    A *genuine three-way* term (all of a,b,c >= 1) is admitted only while
    ``a + b + c <= max_interaction_order``.  Constant, single-driver and pairwise
    (exactly one zero exponent) terms are retained up to the full ``degree``.
    Ordered by total degree then lexicographically for stable column layout.
    """
    if degree < 0:
        raise ValueError("degree must be >= 0")
    powers: List[Tuple[int, int, int]] = []
    for total in range(degree + 1):
        for a in range(total + 1):
            for b in range(total - a + 1):
                c = total - a - b
                three_way = (a >= 1 and b >= 1 and c >= 1)
                if three_way and total > max_interaction_order:
                    continue
                powers.append((a, b, c))
    return powers


def _tri_poly_basis(
    X: np.ndarray,
    degree: int,
    max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER,
) -> np.ndarray:
    """Trivariate design matrix for X of shape (n, 3)."""
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[1] != 3:
        raise ValueError("X must have shape (n, 3); got {}".format(X.shape))
    powers = _tri_poly_powers(degree, max_interaction_order)
    cols = [X[:, 0] ** a * X[:, 1] ** b * X[:, 2] ** c for (a, b, c) in powers]
    return np.column_stack(cols)


def _n_tri_basis_terms(
    degree: int,
    max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER,
) -> int:
    return len(_tri_poly_powers(degree, max_interaction_order))


# ---------------------------------------------------------------------------
# 1. Three-driver nested-stochastic engine (ground truth)
# ---------------------------------------------------------------------------

@dataclass
class ThreeDriverNestedResult:
    capital: CapitalMetrics
    outer_states: np.ndarray              # (n_outer, 3): r_H, S_H, s_H
    conditional_liabilities: np.ndarray
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
            "drivers": ["short_rate", "equity_level", "credit_spread"],
            "run_id": self.run_id,
            "duration_seconds": round(self.duration_seconds, 4),
        }


class ThreeDriverNestedEngine:
    """Brute-force three-driver nested-stochastic capital engine (ground truth).

    Outer real-world scenarios -> state ``(r_H, S_H, s_H)`` -> fresh correlated
    inner ``(rate, equity, spread)`` Q nest per node -> ``L`` -> capital metrics.
    Expensive but unbiased; benchmarks the trivariate LSMC proxy.

    SOA ASOP 56 §3.1.3/§3.5; IA TAS M §3.2/§3.6; ASOP 25 §3.3.
    """

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
        self.spread_params = spread_params if spread_params is not None else CreditSpreadParams()
        self.correlation = correlation if correlation is not None else ThreeDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
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
        actor: str = "ThreeDriverNestedEngine",
        phase: str = "Phase 17: Third Risk Driver (Credit Spread) in the Economic-Capital Proxy",
    ) -> ThreeDriverNestedResult:
        t0 = time.monotonic()
        run_id = "td-nested-" + uuid.uuid4().hex[:8]
        rem = self.product.term_months - self.capital_horizon_months

        outer = _outer_states_3d(
            n_outer, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params,
            self.correlation, self.initial_curve, seed,
        )
        child_seeds = np.random.SeedSequence(seed).spawn(len(outer))
        cond_l = np.empty(len(outer), dtype=float)
        inner_se = np.empty(len(outer), dtype=float)
        for i, (r, s, c) in enumerate(outer):
            inner_seed = int(child_seeds[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_3d(
                float(r), float(s), float(c), n_inner, rem, self.product,
                self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.credit_exposure, self.annual_qx_fn,
            )
            cond_l[i] = float(pvs.mean())
            inner_se[i] = float(pvs.std(ddof=1) / np.sqrt(n_inner)) if n_inner > 1 else 0.0

        capital = capital_metrics_from_liabilities(
            cond_l, self.confidence_level, self.capital_horizon_months
        )
        duration = time.monotonic() - t0

        audit_entry_id = _maybe_audit(
            governance_store, actor, phase, run_id, n_outer * n_inner, duration,
            "3D-nested VaR{:.1f}%={:.2f}; ES={:.2f}; SCR_proxy={:.2f}; "
            "N_outer={}; n_inner={}; drivers=r,S,s".format(
                self.confidence_level * 100, capital.var_liability,
                capital.es_liability, capital.scr_proxy, n_outer, n_inner),
        )

        return ThreeDriverNestedResult(
            capital=capital, outer_states=outer, conditional_liabilities=cond_l,
            inner_standard_errors=inner_se, n_outer=len(outer), n_inner=n_inner,
            total_inner_valuations=len(outer) * n_inner, run_id=run_id,
            duration_seconds=duration, audit_entry_id=audit_entry_id,
        )


# ---------------------------------------------------------------------------
# 2. Three-driver LSMC proxy engine
# ---------------------------------------------------------------------------

@dataclass
class ThreeDriverLSMCResult:
    capital: CapitalMetrics
    beta: np.ndarray
    centers: np.ndarray                # (3,)
    scales: np.ndarray                 # (3,)
    degree: int
    max_interaction_order: int
    powers: List[Tuple[int, int, int]]
    fit_r2: float
    n_fit: int
    n_outer_eval: int
    fitted_liabilities: np.ndarray
    fit_states: np.ndarray             # (n_fit, 3)
    fit_payoffs: np.ndarray
    run_id: str
    duration_seconds: float
    audit_entry_id: Optional[str] = None

    def predict(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        Xs = (X - self.centers) / self.scales
        return _tri_poly_basis(Xs, self.degree, self.max_interaction_order) @ self.beta

    def summary(self) -> dict:
        return {
            "capital": self.capital.summary(),
            "degree": self.degree,
            "max_interaction_order": self.max_interaction_order,
            "n_basis_terms": len(self.powers),
            "fit_r2": round(self.fit_r2, 6),
            "n_fit": self.n_fit,
            "n_outer_eval": self.n_outer_eval,
            "drivers": ["short_rate", "equity_level", "credit_spread"],
            "run_id": self.run_id,
            "duration_seconds": round(self.duration_seconds, 4),
        }


class ThreeDriverLSMCProxyEngine:
    """Trivariate Longstaff-Schwartz least-squares Monte-Carlo capital proxy.

    Fits ``L_hat(r, S, s) = phi(r, S, s) . beta`` (capped trivariate polynomial)
    from ``N_fit`` noisy single-inner-path samples, then evaluates across a large
    cheap correlated outer set.  Longstaff & Schwartz (2001); IFoA proxy-model WP.
    SOA ASOP 56 §3.5; IA TAS M §3.6; ASOP 25 §3.3.
    """

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
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        outer_measure: Measure = Measure.P,
        degree: int = DEFAULT_TRI_LSMC_DEGREE,
        max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        if not (0 < capital_horizon_months < product.term_months):
            raise ValueError("capital_horizon_months must satisfy 0 < H < term_months")
        if degree < 1:
            raise ValueError("LSMC polynomial degree must be >= 1")
        if max_interaction_order < 0:
            raise ValueError("max_interaction_order must be >= 0")
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.spread_params = spread_params if spread_params is not None else CreditSpreadParams()
        self.correlation = correlation if correlation is not None else ThreeDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.capital_horizon_months = int(capital_horizon_months)
        self.confidence_level = float(confidence_level)
        self.outer_measure = Measure(outer_measure)
        self.degree = int(degree)
        self.max_interaction_order = int(max_interaction_order)
        self.annual_qx_fn = annual_qx_fn

    def _fit_payoffs(self, fit_X: np.ndarray, seed: int) -> np.ndarray:
        rem = self.product.term_months - self.capital_horizon_months
        child_seeds = np.random.SeedSequence(seed + 1).spawn(len(fit_X))
        fit_y = np.empty(len(fit_X), dtype=float)
        for i, (r, s, c) in enumerate(fit_X):
            inner_seed = int(child_seeds[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_3d(
                float(r), float(s), float(c), 1, rem, self.product,
                self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.credit_exposure, self.annual_qx_fn,
            )
            fit_y[i] = float(pvs[0])
        return fit_y

    def fit_and_run(
        self,
        n_fit: int = 2_000,
        n_outer_eval: int = 5_000,
        seed: int = 42,
        governance_store: Optional["GovernanceStore"] = None,
        actor: str = "ThreeDriverLSMCProxyEngine",
        phase: str = "Phase 17: Third Risk Driver (Credit Spread) in the Economic-Capital Proxy",
    ) -> ThreeDriverLSMCResult:
        t0 = time.monotonic()
        run_id = "td-lsmc-" + uuid.uuid4().hex[:8]

        fit_X = _outer_states_3d(
            n_fit, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params,
            self.correlation, self.initial_curve, seed,
        )
        fit_y = self._fit_payoffs(fit_X, seed)

        centers = fit_X.mean(axis=0)
        scales = fit_X.std(axis=0, ddof=0)
        scales = np.where(scales > 0, scales, 1.0)
        Xs = (fit_X - centers) / scales
        design = _tri_poly_basis(Xs, self.degree, self.max_interaction_order)
        beta, _resid, _rank, _sv = np.linalg.lstsq(design, fit_y, rcond=None)
        y_hat = design @ beta
        ss_res = float(np.sum((fit_y - y_hat) ** 2))
        ss_tot = float(np.sum((fit_y - fit_y.mean()) ** 2)) or 1.0
        fit_r2 = 1.0 - ss_res / ss_tot

        eval_X = _outer_states_3d(
            n_outer_eval, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params,
            self.correlation, self.initial_curve, seed + 2,
        )
        eval_Xs = (eval_X - centers) / scales
        fitted_l = _tri_poly_basis(eval_Xs, self.degree, self.max_interaction_order) @ beta

        capital = capital_metrics_from_liabilities(
            fitted_l, self.confidence_level, self.capital_horizon_months
        )
        duration = time.monotonic() - t0

        audit_entry_id = _maybe_audit(
            governance_store, actor, phase, run_id, n_fit, duration,
            "3D-LSMC VaR{:.1f}%={:.2f}; ES={:.2f}; SCR_proxy={:.2f}; R2={:.4f}; "
            "N_fit={}; deg={}; max_int={}; terms={}".format(
                self.confidence_level * 100, capital.var_liability,
                capital.es_liability, capital.scr_proxy, fit_r2, n_fit,
                self.degree, self.max_interaction_order,
                _n_tri_basis_terms(self.degree, self.max_interaction_order)),
        )

        return ThreeDriverLSMCResult(
            capital=capital, beta=beta, centers=centers, scales=scales,
            degree=self.degree, max_interaction_order=self.max_interaction_order,
            powers=_tri_poly_powers(self.degree, self.max_interaction_order),
            fit_r2=fit_r2, n_fit=len(fit_X), n_outer_eval=len(eval_X),
            fitted_liabilities=fitted_l, fit_states=fit_X, fit_payoffs=fit_y,
            run_id=run_id, duration_seconds=duration, audit_entry_id=audit_entry_id,
        )


# ---------------------------------------------------------------------------
# 3. Three-driver diagnostics
# ---------------------------------------------------------------------------

@dataclass
class ThreeDriverProxyAgreement:
    max_abs_rel_error: float
    rmse: float
    r2_vs_nested: float
    grid_states: np.ndarray   # (m, 3)
    nested_l: np.ndarray
    proxy_l: np.ndarray

    def summary(self) -> dict:
        return {
            "max_abs_rel_error": round(self.max_abs_rel_error, 6),
            "rmse": round(self.rmse, 6),
            "r2_vs_nested": round(self.r2_vs_nested, 6),
            "n_grid": int(self.grid_states.shape[0]),
        }


class ThreeDriverDiagnostics:
    """Proxy-vs-nested agreement, reproducibility, and inner SE for 3-D state.

    SOA ASOP 56 §3.5; IA TAS M §3.6.
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        spread_params: Optional[CreditSpreadParams] = None,
        correlation: Optional[ThreeDriverCorrelation] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        credit_exposure: Optional[CreditExposureSpec] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.spread_params = spread_params if spread_params is not None else CreditSpreadParams()
        self.correlation = correlation if correlation is not None else ThreeDriverCorrelation()
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.capital_horizon_months = int(capital_horizon_months)
        self.annual_qx_fn = annual_qx_fn

    def nested_liability(
        self, r: float, s: float, spread: float, n_inner: int = 4_096, seed: int = 11
    ) -> float:
        rem = self.product.term_months - self.capital_horizon_months
        pvs = _inner_pathwise_pvs_3d(
            float(r), float(s), float(spread), n_inner, rem, self.product,
            self.hw_params, self.gbm_params, self.spread_params, self.correlation,
            self.capital_horizon_months, seed, self.equity_guarantee,
            self.credit_exposure, self.annual_qx_fn,
        )
        return float(pvs.mean())

    def proxy_vs_nested(
        self,
        proxy: ThreeDriverLSMCResult,
        grid_per_dim: int = 3,
        n_inner: int = 4_096,
        seed: int = 11,
    ) -> ThreeDriverProxyAgreement:
        """Compare the trivariate LSMC surface to nested L on a 3-D state grid.

        The grid spans the 10-90 percentile box of the fitted states per
        dimension (robust to outer-tail outliers), so the comparison stays
        inside the fitted region.  ``grid_per_dim**3`` nested valuations.
        """
        lo_hi = [np.quantile(proxy.fit_states[:, d], [0.1, 0.9]) for d in range(3)]
        axes = [np.linspace(lo, hi, grid_per_dim) for (lo, hi) in lo_hi]
        grid = np.array(
            [[a, b, c] for a in axes[0] for b in axes[1] for c in axes[2]],
            dtype=float,
        )
        child = np.random.SeedSequence(seed).spawn(len(grid))
        nested = np.empty(len(grid), dtype=float)
        rem = self.product.term_months - self.capital_horizon_months
        for i, (r, s, c) in enumerate(grid):
            sd = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_3d(
                float(r), float(s), float(c), n_inner, rem, self.product,
                self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, sd,
                self.equity_guarantee, self.credit_exposure, self.annual_qx_fn,
            )
            nested[i] = float(pvs.mean())
        proxy_l = proxy.predict(grid)
        denom = np.where(np.abs(nested) > 1e-9, np.abs(nested), 1.0)
        rel = np.abs(proxy_l - nested) / denom
        rmse = float(np.sqrt(np.mean((proxy_l - nested) ** 2)))
        ss_res = float(np.sum((nested - proxy_l) ** 2))
        ss_tot = float(np.sum((nested - nested.mean()) ** 2)) or 1.0
        return ThreeDriverProxyAgreement(
            max_abs_rel_error=float(rel.max()), rmse=rmse,
            r2_vs_nested=1.0 - ss_res / ss_tot, grid_states=grid,
            nested_l=nested, proxy_l=proxy_l,
        )

    @staticmethod
    def reproducibility_digest(arr: np.ndarray) -> str:
        rounded = np.round(np.asarray(arr, dtype=float), 9)
        return hashlib.sha256(rounded.tobytes()).hexdigest()


# ---------------------------------------------------------------------------
# Governance helpers
# ---------------------------------------------------------------------------

def _maybe_audit(governance_store, actor, phase, run_id, scenario_count, duration, summary):
    if governance_store is None:
        return None
    from par_model_v2.governance.audit_trail import AuditEntry

    entry = AuditEntry.model_run(
        actor=actor, phase=phase, run_id=run_id, scenario_count=scenario_count,
        duration_seconds=round(duration, 4), outcome="PASS",
        files_changed=["par_model_v2/projection/multi_driver_capital_3d.py"],
        test_summary=summary,
    )
    governance_store.audit_trail.append(entry)
    return entry.entry_id


def three_driver_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the three-driver capital proxy.

    SOA ASOP 56 §3.5.1; IA TAS M §3.6.
    """
    return {
        "module": "par_model_v2/projection/multi_driver_capital_3d.py",
        "classification": "EDUCATIONAL ONLY — NOT a regulatory capital model",
        "risk_drivers": (
            "Capital tail is driven by THREE correlated drivers at the horizon: "
            "the short rate r_H, the equity level S_H, and the credit spread "
            "s_H (governed 3x3 ESG correlation carried through outer and inner). "
            "Lapse, mortality-trend, and FX risks are still NOT in the tail."
        ),
        "improvement_over_phase15": (
            "Closes the documented credit-spread limitation of the Phase 15 "
            "two-driver proxy by adding a CIR++ stochastic spread driver and a "
            "reduced-form credit-loss component to the conditional liability."
        ),
        "credit_model": (
            "Single systemic spread proxy (CIR++); reduced-form hazard×LGD "
            "credit-loss 1-exp(-∫ s du). No rating migration, sector structure, "
            "name concentration, or default jump."
        ),
        "placeholder_parameters": (
            "HW1F, GBM, and CIR++ parameters are illustrative placeholders; "
            "capital magnitudes are NOT calibrated."
        ),
        "lsmc_extrapolation": (
            "The trivariate polynomial surface L_hat(r, S, s) is valid only "
            "across the fitted 3-D state region (interquartile box). Three-way "
            "interaction terms are capped (default order 3). Extrapolation is "
            "unsupported and may be unstable at high degree."
        ),
        "convergence_requirements": (
            "Inner standard error decays ~1/sqrt(n_inner); 99.5% capital "
            "requires N_outer >= {} (ASOP 56 §3.5). Proxy-vs-nested agreement "
            "must be reviewed before any figure is cited.".format(CAPITAL_OUTER_MINIMUM)
        ),
        "no_management_actions": (
            "No dynamic management actions, bonus reactions, asset rebalancing, "
            "or credit-asset trading are modelled in the inner valuation."
        ),
        "governance": (
            "Independent APS X2 review pending; production sign-off withheld. "
            "Use only for education, methodology demonstration, and testing."
        ),
        "standards": [
            "SOA ASOP 56 §3.1.3", "SOA ASOP 56 §3.4", "SOA ASOP 56 §3.5",
            "SOA ASOP 25 §3.3", "IA TAS M §3.2", "IA TAS M §3.6",
            "IFoA MCEV Principles §7", "Longstaff & Schwartz (2001)",
            "Duffie & Singleton (1999)", "Cox-Ingersoll-Ross (1985)",
        ],
    }


def three_driver_use_restrictions_json() -> str:
    return json.dumps(three_driver_use_restrictions(), indent=2, sort_keys=True)


__all__ = [
    "DEFAULT_TRI_LSMC_DEGREE",
    "DEFAULT_MAX_INTERACTION_ORDER",
    "CreditExposureSpec",
    "ThreeDriverCorrelation",
    "ThreeDriverNestedResult",
    "ThreeDriverNestedEngine",
    "ThreeDriverLSMCResult",
    "ThreeDriverLSMCProxyEngine",
    "ThreeDriverProxyAgreement",
    "ThreeDriverDiagnostics",
    "three_driver_use_restrictions",
    "three_driver_use_restrictions_json",
    "_inner_pathwise_pvs_3d",
    "_outer_states_3d",
    "_correlated_shocks_3",
    "_tri_poly_basis",
    "_tri_poly_powers",
    "_n_tri_basis_terms",
]
