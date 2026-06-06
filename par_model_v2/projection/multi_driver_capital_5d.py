"""
Five-Driver (Rates + Equity + Credit + Lapse + Mortality-Trend) Nested / LSMC Proxy
===================================================================================

Phase 19 Task 3.  Generalises the Phase 18 *four-driver* (rates + equity +
credit-spread + lapse-behaviour) nested / LSMC economic-capital proxy
(:mod:`par_model_v2.projection.multi_driver_capital_4d`) to a **fifth, second
non-financial** driver — a stochastic mortality-trend (mortality-level) index:

    x = (r_H, S_H, s_H, b_H, m_H)
        — short rate, equity-index level, credit spread, lapse-behaviour index,
          AND the mortality-trend index at the capital horizon H.

This directly closes the documented Phase 18 limitation ("mortality-trend and FX
risks are still NOT in the tail") by adding the *second* non-financial proxy
driver, completing the IFoA proxy-modelling working party's financial AND
non-financial driver set bar FX / liquidity.  The mortality-trend index is
supplied by the new OU driver (:mod:`par_model_v2.stochastic.mortality_trend`);
its horizon **mortality multiplier** ``G = exp(m_H)`` scales the central
mortality basis ``q_x`` of the guaranteed death / maturity benefits.

Five-driver liability
---------------------
The conditional horizon-H Q-value keeps the four Phase-18 components and folds
the mortality driver into the *guaranteed-benefit* component through a
mortality-scaled cashflow vector.  Given the horizon mortality multiplier
``G = exp(theta * m_H)`` (``theta`` the exposure sensitivity), every annual
``q_x`` used to build the residual death / maturity cashflows is scaled:

    q_x^scaled = clip( q_x^base * G,  0,  q_cap )

A positive ``m_H`` (excess-mortality / pandemic-shaped trend) raises ``q_x``,
which pulls the sum-assured death benefit *earlier* (less discounting) and
shrinks the surviving maturity benefit; a negative ``m_H`` (longevity trend) does
the reverse.  For an endowment whose death and maturity benefits both equal the
sum assured the net effect is a *timing* (discounting) effect, modest relative to
the rate / equity / lapse drivers — mortality is a genuinely orthogonal SMALL
driver, exactly as expected for this product.  The full liability is:

    L(r_H,S_H,s_H,b_H,m_H)
        = IF(r_H,b_H) * [ guaranteed_pv(r_H, G(m_H))
                        + equity_guarantee_pv(r_H,S_H) ]
        + credit_loss_pv(r_H,s_H)

where ``guaranteed_pv`` now depends on the mortality multiplier ``G(m_H)`` and the
in-force factor ``IF`` and credit loss are unchanged from the four-driver model.
The mortality driver enters deterministically through the horizon multiplier (set
at H and applied over ``[H, T]``), like the lapse in-force factor.

Quintivariate LSMC surface (pairwise + capped higher-order interactions)
------------------------------------------------------------------------
The Longstaff-Schwartz surface is a **five-variate total-degree polynomial**:

    L_hat(r,S,s,b,m) = sum_{(a,b,c,d,e) in P} beta . r^a S^b s^c b^d m^e

where ``P`` holds every exponent quint with ``a+..+e <= degree`` EXCEPT genuine
higher-order interactions (three or more non-zero exponents) are *capped* at
combined order ``<= max_interaction_order`` (default 3).  Pairwise interactions
(exactly two non-zero exponents) are retained up to the full degree.  This is the
lean-basis discipline of the IFoA proxy-modelling working party, essential as the
driver count grows.

Engines (mirror the four-driver / Task 3 API)
---------------------------------------------
1. ``FiveDriverNestedEngine``    — brute-force five-driver ground truth.
2. ``FiveDriverLSMCProxyEngine`` — quintivariate-polynomial LSMC proxy.
3. ``FiveDriverDiagnostics``     — proxy-vs-nested agreement on a 5-D state grid,
   reproducibility digest, inner-SE convergence.

ASOP / IA standards
-------------------
- SOA ASOP 7  §3.3   — dynamic / behavioural lapse modelling
- SOA ASOP 25 §3.3   — correlated driver / mortality-basis adequacy
- SOA ASOP 56 §3.1.3 / §3.4 / §3.5 — documentation, calibration, adequacy
- IA TAS M §3.2 / §3.5 / §3.6 — valuation, assumption basis, validation
- IFoA proxy-modelling working party — financial AND non-financial drivers
- Lee & Carter (1992); Longstaff & Schwartz (2001); Duffie-Singleton (1999)

Model-use restrictions (see ``five_driver_use_restrictions()``)
---------------------------------------------------------------
EDUCATIONAL ONLY.  Five risk drivers (rates + equity + credit + lapse +
mortality-trend) — FX and liquidity risks are still NOT in the tail.  Placeholder
HW1F / GBM / CIR++ / OU-behaviour / OU-mortality parameters; the mortality-trend
index is a single systemic level factor with no age / period / cohort structure.
The quintivariate polynomial surface is valid only across the fitted 5-D state
region; extrapolation is unsupported.  Not a regulatory SCR.  Independent
APS X2 review pending.
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

from par_model_v2.projection.monthly_projection import (
    ParEndowmentProduct,
    _base_annual_qx,
)
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
from par_model_v2.projection.multi_driver_capital_3d import CreditExposureSpec
from par_model_v2.projection.multi_driver_capital_4d import (
    LapseExposureSpec,
    FourDriverCorrelation,
)
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
from par_model_v2.stochastic.lapse_behaviour import (
    LapseBehaviourParams,
    LapseBehaviourProcess,
)
from par_model_v2.stochastic.mortality_trend import (
    MortalityTrendParams,
    MortalityTrendProcess,
)


#: Default total polynomial degree for the quintivariate LSMC surface.
DEFAULT_QUINT_LSMC_DEGREE = 2

#: Default cap on the combined order of genuine higher-order (>=3 non-zero
#: exponents) interaction terms.
DEFAULT_MAX_INTERACTION_ORDER_5D = 3

#: Hard cap on a scaled annual mortality rate (numerical safety; UDD monthly
#: conversion already clips at 0.9999).
DEFAULT_MORTALITY_QX_CAP = 0.9999


# ---------------------------------------------------------------------------
# Mortality exposure / mortality-scaling specification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MortalityExposureSpec:
    """Couples the mortality-trend driver to the guaranteed-benefit cashflows.

    The horizon mortality multiplier ``G = exp(trend_sensitivity * m_H)`` scales
    the central annual ``q_x`` used to build the residual death / maturity
    cashflow vector.  At ``m_H = 0`` the multiplier is 1 (backward compatible
    with the four-driver model).

    Parameters
    ----------
    trend_sensitivity :
        ``theta`` — exposure of ``q_x`` to the mortality-trend index (default 1;
        multiplier ``exp(theta * m)``).
    qx_cap :
        Hard cap on the scaled annual mortality rate.
    """

    trend_sensitivity: float = 1.0
    qx_cap: float = DEFAULT_MORTALITY_QX_CAP

    def __post_init__(self) -> None:
        if self.trend_sensitivity <= 0:
            raise ValueError(
                "trend_sensitivity must be > 0; got {}".format(self.trend_sensitivity)
            )
        if not (0.0 < self.qx_cap <= 1.0):
            raise ValueError("qx_cap must be in (0, 1]; got {}".format(self.qx_cap))

    def multiplier(self, m_h: float) -> float:
        """Mortality multiplier ``G = exp(theta * m_H)`` at the horizon."""
        return float(np.exp(self.trend_sensitivity * float(m_h)))

    def scaled_qx_fn(
        self, m_h: float, base_annual_qx_fn: Optional[Callable] = None
    ) -> Callable:
        """Return ``q_x`` builder scaled by the horizon mortality multiplier.

        Wraps the supplied (or default China-Life-shape) base ``q_x`` function so
        each annual rate is multiplied by ``G(m_H)`` and clipped to ``qx_cap``.
        The result is a deterministic, mortality-state-dependent function passed
        to :func:`_residual_cashflow_vector`.
        """
        g = self.multiplier(m_h)
        cap = self.qx_cap
        base = base_annual_qx_fn

        def _fn(age, gender):
            raw = base(age, gender) if base is not None else _base_annual_qx(age, gender)
            return min(max(raw * g, 0.0), cap)

        return _fn


# ---------------------------------------------------------------------------
# Cross-driver correlation (5x5)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FiveDriverCorrelation:
    """5x5 ESG correlation among (rate, equity, credit, lapse, mortality) shocks.

    The (rate, equity, spread, lapse) 4x4 block is inherited from the governed
    :class:`FourDriverCorrelation`.  Mortality trend is **non-financial**: by
    default it is uncorrelated with every other shock (``mortality_* = 0``), so it
    injects a second orthogonal axis into the tail.  Non-zero couplings are
    configurable (e.g. a mild positive mortality-credit co-movement in stress).
    """

    four_driver: FourDriverCorrelation = None  # type: ignore[assignment]
    mortality_rate: float = 0.0
    mortality_equity: float = 0.0
    mortality_spread: float = 0.0
    mortality_lapse: float = 0.0

    def __post_init__(self) -> None:
        if self.four_driver is None:
            object.__setattr__(self, "four_driver", FourDriverCorrelation())
        for name in (
            "mortality_rate", "mortality_equity", "mortality_spread", "mortality_lapse",
        ):
            v = getattr(self, name)
            if not (-1.0 <= v <= 1.0):
                raise ValueError("{} must be in [-1, 1]; got {}".format(name, v))

    def matrix(self, gbm_rate_equity: float) -> np.ndarray:
        c4 = self.four_driver.matrix(gbm_rate_equity)
        C = np.eye(5, dtype=float)
        C[:4, :4] = c4
        mor = np.array(
            [self.mortality_rate, self.mortality_equity,
             self.mortality_spread, self.mortality_lapse],
            dtype=float,
        )
        C[4, :4] = mor
        C[:4, 4] = mor
        return C

    def cholesky(self, gbm_rate_equity: float) -> np.ndarray:
        """Lower-triangular Cholesky factor; nearest-PD fallback if needed.

        Placeholder correlations can violate positive-definiteness; project to the
        nearest PD matrix by clipping eigenvalues (Higham-style) so the scheme
        stays well defined (ASOP 25 §3.3).
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
# Five correlated shock arrays
# ---------------------------------------------------------------------------

def _correlated_shocks_5(
    rng: np.random.Generator,
    n: int,
    steps: int,
    chol: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return five (n, steps) correlated antithetic-normal shock arrays.

    Independent antithetic normals are combined by the lower-triangular Cholesky
    factor so the per-step cross-sectional correlation matches ``chol @ chol.T``
    (ASOP 56 §3.5 variance reduction + ASOP 25 §3.3 correlation).
    """
    z0 = _antithetic_normals(rng, n, steps)
    z1 = _antithetic_normals(rng, n, steps)
    z2 = _antithetic_normals(rng, n, steps)
    z3 = _antithetic_normals(rng, n, steps)
    z4 = _antithetic_normals(rng, n, steps)
    zr = chol[0, 0] * z0
    zs = chol[1, 0] * z0 + chol[1, 1] * z1
    zc = chol[2, 0] * z0 + chol[2, 1] * z1 + chol[2, 2] * z2
    zb = chol[3, 0] * z0 + chol[3, 1] * z1 + chol[3, 2] * z2 + chol[3, 3] * z3
    zm = (chol[4, 0] * z0 + chol[4, 1] * z1 + chol[4, 2] * z2
          + chol[4, 3] * z3 + chol[4, 4] * z4)
    return zr, zs, zc, zb, zm


# ---------------------------------------------------------------------------
# Five-driver inner valuation: L(r_H, S_H, s_H, b_H, m_H)
# ---------------------------------------------------------------------------

def _inner_pathwise_pvs_5d(
    r: float,
    s: float,
    spread: float,
    b: float,
    m: float,
    n_inner: int,
    rem_months: int,
    product: ParEndowmentProduct,
    base_hw_params: HullWhiteParams,
    gbm_params: GBMParams,
    spread_params: CreditSpreadParams,
    correlation: FiveDriverCorrelation,
    h_month: int,
    seed: int,
    equity_guarantee: EquityGuaranteeSpec,
    credit_exposure: CreditExposureSpec,
    lapse_exposure: LapseExposureSpec,
    mortality_exposure: MortalityExposureSpec,
    annual_qx_fn: Optional[Callable] = None,
) -> np.ndarray:
    """Return ``n_inner`` pathwise residual-PV samples at ``(r,s,spread,b,m)``.

    Each sample is an unbiased draw of
    ``L = E^Q[ IF(r,b) * (guaranteed PV(G(m)) + equity-guarantee PV) + credit-loss PV ]``
    on one correlated inner ``(rate, equity, spread)`` triple.  The lapse and
    mortality drivers enter deterministically through, respectively, the in-force
    factor ``IF(r, b)`` and the mortality multiplier ``G(m)`` on ``q_x`` (both set
    at the horizon and applied over ``[H, T]``).
    """
    rng = np.random.default_rng(seed)
    chol = correlation.cholesky(gbm_params.rate_equity_correlation)
    z_rate, z_equity, z_spread, _z_lapse, _z_mort = _correlated_shocks_5(
        rng, n_inner, rem_months, chol
    )

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

    # In-force factor from the lapse driver (deterministic given r_H, b_H).
    inforce = lapse_exposure.inforce_factor(
        float(r), float(b), h_month, product.term_months
    )

    # Component 1 — guaranteed death + maturity benefits (rate-driven), with the
    # mortality basis scaled by the mortality-trend multiplier G(m_H), then
    # in-force scaled by the lapse driver.
    scaled_qx = mortality_exposure.scaled_qx_fn(float(m), annual_qx_fn)
    cf = _residual_cashflow_vector(product, h_month, scaled_qx)
    guaranteed_pv = inforce * (disc @ cf)

    # Component 2 — equity-linked maturity guarantee (rates + equity), in-force
    # scaled (only in-force policies collect the maturity guarantee).
    units = equity_guarantee.units(product.sum_assured)
    floor = equity_guarantee.floor(product.sum_assured)
    fund_T = units * equity_paths[:, rem_months]
    eq_payoff = np.maximum(floor - fund_T, 0.0)
    eq_guarantee_pv = inforce * (disc[:, rem_months] * eq_payoff)

    # Component 3 — credit loss on spread-sensitive backing assets (asset side;
    # NOT in-force or mortality scaled). Reduced-form 1 - exp(-∫ s du).
    notional = credit_exposure.notional(product.sum_assured)
    dt = 1.0 / 12.0
    cum_hazard = spread_paths[:, :rem_months].sum(axis=1) * dt
    loss_fraction = 1.0 - np.exp(-cum_hazard)
    credit_loss_pv = disc[:, rem_months] * notional * loss_fraction

    return guaranteed_pv + eq_guarantee_pv + credit_loss_pv


# ---------------------------------------------------------------------------
# Five-driver outer-state sampling
# ---------------------------------------------------------------------------

def _outer_states_5d(
    n_outer: int,
    capital_horizon_months: int,
    measure: Measure,
    hw_params: HullWhiteParams,
    gbm_params: GBMParams,
    spread_params: CreditSpreadParams,
    lapse_params: LapseBehaviourParams,
    mortality_params: MortalityTrendParams,
    correlation: FiveDriverCorrelation,
    initial_curve: Optional[RiskFreeCurve],
    seed: int,
) -> np.ndarray:
    """Project ``n_outer`` outer paths to H; return an (n, 5) array.

    Drives the five building-block processes (HW1F rate, GBM equity, CIR++
    spread, OU lapse-behaviour, OU mortality-trend) off a SHARED 5-factor
    Cholesky-correlated antithetic draw, so the outer ``(r, S, s, b, m)`` joint is
    genuinely correlated under the governed 5x5 ESG matrix (ASOP 25 §3.3).
    """
    rng = np.random.default_rng(seed)
    chol = correlation.cholesky(gbm_params.rate_equity_correlation)
    z_rate, z_equity, z_spread, z_lapse, z_mort = _correlated_shocks_5(
        rng, n_outer, capital_horizon_months, chol
    )
    curve = initial_curve if initial_curve is not None else RiskFreeCurve.flat(
        hw_params.initial_short_rate
    )
    hw = HullWhiteRateProcess(hw_params, initial_curve=curve)
    gbm = GBMEquityProcess(gbm_params, rate_process=hw)
    csp = CreditSpreadProcess(spread_params)
    lap = LapseBehaviourProcess(lapse_params)
    mor = MortalityTrendProcess(mortality_params)

    rate_paths = hw._simulate_array(n_outer, capital_horizon_months, measure, z_rate)
    equity_paths, _ret = gbm._simulate_array(
        n_outer, capital_horizon_months, measure, rate_paths, z_equity
    )
    spread_paths = csp._simulate_array(n_outer, capital_horizon_months, measure, z_spread)
    lapse_paths = lap._simulate_array(n_outer, capital_horizon_months, measure, z_lapse)
    mort_paths = mor._simulate_array(n_outer, capital_horizon_months, measure, z_mort)

    r_h = rate_paths[:, capital_horizon_months]
    s_h = equity_paths[:, capital_horizon_months]
    c_h = spread_paths[:, capital_horizon_months]
    b_h = lapse_paths[:, capital_horizon_months]
    m_h = mort_paths[:, capital_horizon_months]
    return np.column_stack([r_h, s_h, c_h, b_h, m_h])


# ---------------------------------------------------------------------------
# Quintivariate total-degree polynomial basis (pairwise + capped higher-order)
# ---------------------------------------------------------------------------

def _quint_poly_powers(
    degree: int,
    max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER_5D,
) -> List[Tuple[int, int, int, int, int]]:
    """Exponent quints (a,b,c,d,e), sum <= degree, capped higher-order terms.

    A *genuine higher-order* term (three or more non-zero exponents) is admitted
    only while ``a+b+c+d+e <= max_interaction_order``.  Constant, single-driver
    and pairwise (exactly two non-zero exponents) terms are retained up to the
    full ``degree``.  Ordered by total degree then lexicographically.
    """
    if degree < 0:
        raise ValueError("degree must be >= 0")
    powers: List[Tuple[int, int, int, int, int]] = []
    for total in range(degree + 1):
        for a in range(total + 1):
            for bb in range(total - a + 1):
                for c in range(total - a - bb + 1):
                    for d in range(total - a - bb - c + 1):
                        e = total - a - bb - c - d
                        nonzero = sum(1 for ex in (a, bb, c, d, e) if ex >= 1)
                        if nonzero >= 3 and total > max_interaction_order:
                            continue
                        powers.append((a, bb, c, d, e))
    return powers


def _quint_poly_basis(
    X: np.ndarray,
    degree: int,
    max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER_5D,
) -> np.ndarray:
    """Quintivariate design matrix for X of shape (n, 5)."""
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[1] != 5:
        raise ValueError("X must have shape (n, 5); got {}".format(X.shape))
    powers = _quint_poly_powers(degree, max_interaction_order)
    cols = [
        X[:, 0] ** a * X[:, 1] ** b * X[:, 2] ** c * X[:, 3] ** d * X[:, 4] ** e
        for (a, b, c, d, e) in powers
    ]
    return np.column_stack(cols)


def _n_quint_basis_terms(
    degree: int,
    max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER_5D,
) -> int:
    return len(_quint_poly_powers(degree, max_interaction_order))


# ---------------------------------------------------------------------------
# 1. Five-driver nested-stochastic engine (ground truth)
# ---------------------------------------------------------------------------

@dataclass
class FiveDriverNestedResult:
    capital: CapitalMetrics
    outer_states: np.ndarray              # (n_outer, 5): r_H, S_H, s_H, b_H, m_H
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
            "drivers": [
                "short_rate", "equity_level", "credit_spread",
                "lapse_behaviour", "mortality_trend",
            ],
            "run_id": self.run_id,
            "duration_seconds": round(self.duration_seconds, 4),
        }


class FiveDriverNestedEngine:
    """Brute-force five-driver nested-stochastic capital engine (ground truth).

    Outer real-world scenarios -> state ``(r_H, S_H, s_H, b_H, m_H)`` -> fresh
    correlated inner ``(rate, equity, spread)`` Q nest per node (lapse and
    mortality enter deterministically through the in-force factor and the
    mortality multiplier) -> ``L`` -> capital metrics.  Expensive but unbiased;
    benchmarks the quintivariate LSMC proxy.

    SOA ASOP 56 §3.1.3/§3.5; IA TAS M §3.2/§3.6; ASOP 25 §3.3; ASOP 7 §3.3.
    """

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
        self.lapse_params = lapse_params if lapse_params is not None else LapseBehaviourParams()
        self.mortality_params = (
            mortality_params if mortality_params is not None else MortalityTrendParams()
        )
        self.correlation = correlation if correlation is not None else FiveDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.lapse_exposure = lapse_exposure or LapseExposureSpec()
        self.mortality_exposure = mortality_exposure or MortalityExposureSpec()
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
        actor: str = "FiveDriverNestedEngine",
        phase: str = "Phase 19: Recovery Completion and Driver Expansion",
    ) -> FiveDriverNestedResult:
        t0 = time.monotonic()
        run_id = "fv-nested-" + uuid.uuid4().hex[:8]
        rem = self.product.term_months - self.capital_horizon_months

        outer = _outer_states_5d(
            n_outer, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params, self.lapse_params,
            self.mortality_params, self.correlation, self.initial_curve, seed,
        )
        child_seeds = np.random.SeedSequence(seed).spawn(len(outer))
        cond_l = np.empty(len(outer), dtype=float)
        inner_se = np.empty(len(outer), dtype=float)
        for i, (r, s, c, b, m) in enumerate(outer):
            inner_seed = int(child_seeds[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_5d(
                float(r), float(s), float(c), float(b), float(m), n_inner, rem,
                self.product, self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.credit_exposure, self.lapse_exposure,
                self.mortality_exposure, self.annual_qx_fn,
            )
            cond_l[i] = float(pvs.mean())
            inner_se[i] = float(pvs.std(ddof=1) / np.sqrt(n_inner)) if n_inner > 1 else 0.0

        capital = capital_metrics_from_liabilities(
            cond_l, self.confidence_level, self.capital_horizon_months
        )
        duration = time.monotonic() - t0

        audit_entry_id = _maybe_audit(
            governance_store, actor, phase, run_id, n_outer * n_inner, duration,
            "5D-nested VaR{:.1f}%={:.2f}; ES={:.2f}; SCR_proxy={:.2f}; "
            "N_outer={}; n_inner={}; drivers=r,S,s,b,m".format(
                self.confidence_level * 100, capital.var_liability,
                capital.es_liability, capital.scr_proxy, n_outer, n_inner),
        )

        return FiveDriverNestedResult(
            capital=capital, outer_states=outer, conditional_liabilities=cond_l,
            inner_standard_errors=inner_se, n_outer=len(outer), n_inner=n_inner,
            total_inner_valuations=len(outer) * n_inner, run_id=run_id,
            duration_seconds=duration, audit_entry_id=audit_entry_id,
        )


# ---------------------------------------------------------------------------
# 2. Five-driver LSMC proxy engine
# ---------------------------------------------------------------------------

@dataclass
class FiveDriverLSMCResult:
    capital: CapitalMetrics
    beta: np.ndarray
    centers: np.ndarray                # (5,)
    scales: np.ndarray                 # (5,)
    degree: int
    max_interaction_order: int
    powers: List[Tuple[int, int, int, int, int]]
    fit_r2: float
    n_fit: int
    n_outer_eval: int
    fitted_liabilities: np.ndarray
    fit_states: np.ndarray             # (n_fit, 5)
    fit_payoffs: np.ndarray
    run_id: str
    duration_seconds: float
    audit_entry_id: Optional[str] = None

    def predict(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        Xs = (X - self.centers) / self.scales
        return _quint_poly_basis(Xs, self.degree, self.max_interaction_order) @ self.beta

    def summary(self) -> dict:
        return {
            "capital": self.capital.summary(),
            "degree": self.degree,
            "max_interaction_order": self.max_interaction_order,
            "n_basis_terms": len(self.powers),
            "fit_r2": round(self.fit_r2, 6),
            "n_fit": self.n_fit,
            "n_outer_eval": self.n_outer_eval,
            "drivers": [
                "short_rate", "equity_level", "credit_spread",
                "lapse_behaviour", "mortality_trend",
            ],
            "run_id": self.run_id,
            "duration_seconds": round(self.duration_seconds, 4),
        }


class FiveDriverLSMCProxyEngine:
    """Quintivariate Longstaff-Schwartz least-squares Monte-Carlo capital proxy.

    Fits ``L_hat(r,S,s,b,m) = phi(r,S,s,b,m) . beta`` (capped quintivariate
    polynomial) from ``N_fit`` noisy single-inner-path samples, then evaluates
    across a large cheap correlated outer set.  Longstaff & Schwartz (2001); IFoA
    proxy-model WP.  SOA ASOP 56 §3.5; IA TAS M §3.6; ASOP 25 §3.3.
    """

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
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        outer_measure: Measure = Measure.P,
        degree: int = DEFAULT_QUINT_LSMC_DEGREE,
        max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER_5D,
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
        self.lapse_params = lapse_params if lapse_params is not None else LapseBehaviourParams()
        self.mortality_params = (
            mortality_params if mortality_params is not None else MortalityTrendParams()
        )
        self.correlation = correlation if correlation is not None else FiveDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.lapse_exposure = lapse_exposure or LapseExposureSpec()
        self.mortality_exposure = mortality_exposure or MortalityExposureSpec()
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
        for i, (r, s, c, b, m) in enumerate(fit_X):
            inner_seed = int(child_seeds[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_5d(
                float(r), float(s), float(c), float(b), float(m), 1, rem,
                self.product, self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.credit_exposure, self.lapse_exposure,
                self.mortality_exposure, self.annual_qx_fn,
            )
            fit_y[i] = float(pvs[0])
        return fit_y

    def fit_and_run(
        self,
        n_fit: int = 2_000,
        n_outer_eval: int = 5_000,
        seed: int = 42,
        governance_store: Optional["GovernanceStore"] = None,
        actor: str = "FiveDriverLSMCProxyEngine",
        phase: str = "Phase 19: Recovery Completion and Driver Expansion",
    ) -> FiveDriverLSMCResult:
        t0 = time.monotonic()
        run_id = "fv-lsmc-" + uuid.uuid4().hex[:8]

        fit_X = _outer_states_5d(
            n_fit, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params, self.lapse_params,
            self.mortality_params, self.correlation, self.initial_curve, seed,
        )
        fit_y = self._fit_payoffs(fit_X, seed)

        centers = fit_X.mean(axis=0)
        scales = fit_X.std(axis=0, ddof=0)
        scales = np.where(scales > 0, scales, 1.0)
        Xs = (fit_X - centers) / scales
        design = _quint_poly_basis(Xs, self.degree, self.max_interaction_order)
        beta, _resid, _rank, _sv = np.linalg.lstsq(design, fit_y, rcond=None)
        y_hat = design @ beta
        ss_res = float(np.sum((fit_y - y_hat) ** 2))
        ss_tot = float(np.sum((fit_y - fit_y.mean()) ** 2)) or 1.0
        fit_r2 = 1.0 - ss_res / ss_tot

        eval_X = _outer_states_5d(
            n_outer_eval, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params, self.lapse_params,
            self.mortality_params, self.correlation, self.initial_curve, seed + 2,
        )
        eval_Xs = (eval_X - centers) / scales
        fitted_l = _quint_poly_basis(eval_Xs, self.degree, self.max_interaction_order) @ beta

        capital = capital_metrics_from_liabilities(
            fitted_l, self.confidence_level, self.capital_horizon_months
        )
        duration = time.monotonic() - t0

        audit_entry_id = _maybe_audit(
            governance_store, actor, phase, run_id, n_fit, duration,
            "5D-LSMC VaR{:.1f}%={:.2f}; ES={:.2f}; SCR_proxy={:.2f}; R2={:.4f}; "
            "N_fit={}; deg={}; max_int={}; terms={}".format(
                self.confidence_level * 100, capital.var_liability,
                capital.es_liability, capital.scr_proxy, fit_r2, n_fit,
                self.degree, self.max_interaction_order,
                _n_quint_basis_terms(self.degree, self.max_interaction_order)),
        )

        return FiveDriverLSMCResult(
            capital=capital, beta=beta, centers=centers, scales=scales,
            degree=self.degree, max_interaction_order=self.max_interaction_order,
            powers=_quint_poly_powers(self.degree, self.max_interaction_order),
            fit_r2=fit_r2, n_fit=len(fit_X), n_outer_eval=len(eval_X),
            fitted_liabilities=fitted_l, fit_states=fit_X, fit_payoffs=fit_y,
            run_id=run_id, duration_seconds=duration, audit_entry_id=audit_entry_id,
        )


# ---------------------------------------------------------------------------
# 3. Five-driver diagnostics
# ---------------------------------------------------------------------------

@dataclass
class FiveDriverProxyAgreement:
    max_abs_rel_error: float
    rmse: float
    r2_vs_nested: float
    grid_states: np.ndarray   # (m, 5)
    nested_l: np.ndarray
    proxy_l: np.ndarray

    def summary(self) -> dict:
        return {
            "max_abs_rel_error": round(self.max_abs_rel_error, 6),
            "rmse": round(self.rmse, 6),
            "r2_vs_nested": round(self.r2_vs_nested, 6),
            "n_grid": int(self.grid_states.shape[0]),
        }


class FiveDriverDiagnostics:
    """Proxy-vs-nested agreement, reproducibility, and inner SE for 5-D state.

    SOA ASOP 56 §3.5; IA TAS M §3.6.
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        spread_params: Optional[CreditSpreadParams] = None,
        lapse_params: Optional[LapseBehaviourParams] = None,
        mortality_params: Optional[MortalityTrendParams] = None,
        correlation: Optional[FiveDriverCorrelation] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        credit_exposure: Optional[CreditExposureSpec] = None,
        lapse_exposure: Optional[LapseExposureSpec] = None,
        mortality_exposure: Optional[MortalityExposureSpec] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.spread_params = spread_params if spread_params is not None else CreditSpreadParams()
        self.lapse_params = lapse_params if lapse_params is not None else LapseBehaviourParams()
        self.mortality_params = (
            mortality_params if mortality_params is not None else MortalityTrendParams()
        )
        self.correlation = correlation if correlation is not None else FiveDriverCorrelation()
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.lapse_exposure = lapse_exposure or LapseExposureSpec()
        self.mortality_exposure = mortality_exposure or MortalityExposureSpec()
        self.capital_horizon_months = int(capital_horizon_months)
        self.annual_qx_fn = annual_qx_fn

    def nested_liability(
        self, r: float, s: float, spread: float, b: float, m: float,
        n_inner: int = 4_096, seed: int = 11,
    ) -> float:
        rem = self.product.term_months - self.capital_horizon_months
        pvs = _inner_pathwise_pvs_5d(
            float(r), float(s), float(spread), float(b), float(m), n_inner, rem,
            self.product, self.hw_params, self.gbm_params, self.spread_params,
            self.correlation, self.capital_horizon_months, seed,
            self.equity_guarantee, self.credit_exposure, self.lapse_exposure,
            self.mortality_exposure, self.annual_qx_fn,
        )
        return float(pvs.mean())

    def proxy_vs_nested(
        self,
        proxy: FiveDriverLSMCResult,
        grid_per_dim: int = 2,
        n_inner: int = 4_096,
        seed: int = 11,
    ) -> FiveDriverProxyAgreement:
        """Compare the quintivariate LSMC surface to nested L on a 5-D grid.

        The grid spans the 10-90 percentile box of the fitted states per
        dimension (robust to outer-tail outliers).  ``grid_per_dim**5`` nested
        valuations (default 2 -> 32 nodes) keeps the diagnostic affordable.
        """
        lo_hi = [np.quantile(proxy.fit_states[:, dd], [0.1, 0.9]) for dd in range(5)]
        axes = [np.linspace(lo, hi, grid_per_dim) for (lo, hi) in lo_hi]
        grid = np.array(
            [[a, b, c, d, e]
             for a in axes[0] for b in axes[1] for c in axes[2]
             for d in axes[3] for e in axes[4]],
            dtype=float,
        )
        child = np.random.SeedSequence(seed).spawn(len(grid))
        nested = np.empty(len(grid), dtype=float)
        rem = self.product.term_months - self.capital_horizon_months
        for i, (r, s, c, b, m) in enumerate(grid):
            sd = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_5d(
                float(r), float(s), float(c), float(b), float(m), n_inner, rem,
                self.product, self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, sd,
                self.equity_guarantee, self.credit_exposure, self.lapse_exposure,
                self.mortality_exposure, self.annual_qx_fn,
            )
            nested[i] = float(pvs.mean())
        proxy_l = proxy.predict(grid)
        denom = np.where(np.abs(nested) > 1e-9, np.abs(nested), 1.0)
        rel = np.abs(proxy_l - nested) / denom
        rmse = float(np.sqrt(np.mean((proxy_l - nested) ** 2)))
        ss_res = float(np.sum((nested - proxy_l) ** 2))
        ss_tot = float(np.sum((nested - nested.mean()) ** 2)) or 1.0
        return FiveDriverProxyAgreement(
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
        files_changed=["par_model_v2/projection/multi_driver_capital_5d.py"],
        test_summary=summary,
    )
    governance_store.audit_trail.append(entry)
    return entry.entry_id


def five_driver_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the five-driver capital proxy.

    SOA ASOP 56 §3.5.1; IA TAS M §3.6.
    """
    return {
        "module": "par_model_v2/projection/multi_driver_capital_5d.py",
        "classification": "EDUCATIONAL ONLY — NOT a regulatory capital model",
        "risk_drivers": (
            "Capital tail is driven by FIVE correlated drivers at the horizon: "
            "the short rate r_H, the equity level S_H, the credit spread s_H, the "
            "non-financial lapse-behaviour index b_H, AND the non-financial "
            "mortality-trend index m_H (governed 5x5 ESG correlation carried "
            "through outer and inner). FX and liquidity risks are still NOT in the "
            "tail."
        ),
        "improvement_over_phase18": (
            "Closes the documented MORTALITY-TREND limitation of the Phase 18 "
            "four-driver proxy by adding the SECOND non-financial driver: an OU "
            "mortality-trend index whose horizon multiplier G=exp(m) scales the "
            "central mortality basis q_x of the guaranteed death / maturity "
            "benefits (a single-systemic-factor analogue of the Lee-Carter time "
            "index)."
        ),
        "mortality_model": (
            "Single systemic OU mortality-trend index; mortality multiplier "
            "exp(theta*m) on the central q_x. No age / period / cohort structure, "
            "no link to a longevity-hedge asset, no interaction with the lapse "
            "driver beyond the governed correlation. For a sum-assured endowment "
            "(death benefit = maturity benefit) the driver acts mainly through "
            "benefit TIMING, so it is a genuinely orthogonal SMALL driver."
        ),
        "placeholder_parameters": (
            "HW1F, GBM, CIR++, OU-lapse and OU-mortality parameters are "
            "illustrative placeholders; capital magnitudes are NOT calibrated. "
            "The mortality kappa_m/sigma_m are not fitted to a mortality- or "
            "population-experience time series."
        ),
        "lsmc_extrapolation": (
            "The quintivariate polynomial surface L_hat(r,S,s,b,m) is valid only "
            "across the fitted 5-D state region (interquartile box). Higher-order "
            "(>=3-way) interaction terms are capped (default order 3). "
            "Extrapolation is unsupported and may be unstable at high degree."
        ),
        "convergence_requirements": (
            "Inner standard error decays ~1/sqrt(n_inner); 99.5% capital requires "
            "N_outer >= {} (ASOP 56 §3.5). Proxy-vs-nested agreement must be "
            "reviewed before any figure is cited.".format(CAPITAL_OUTER_MINIMUM)
        ),
        "no_management_actions": (
            "No dynamic management actions, bonus reactions, asset rebalancing, or "
            "credit-asset trading are modelled in the inner valuation."
        ),
        "governance": (
            "Independent APS X2 review pending; production sign-off withheld. Use "
            "only for education, methodology demonstration, and testing."
        ),
        "standards": [
            "SOA ASOP 7 §3.3", "SOA ASOP 56 §3.1.3", "SOA ASOP 56 §3.4",
            "SOA ASOP 56 §3.5", "SOA ASOP 25 §3.3", "IA TAS M §3.2",
            "IA TAS M §3.5", "IA TAS M §3.6", "IFoA proxy-modelling WP",
            "Lee & Carter (1992)", "Longstaff & Schwartz (2001)",
            "Duffie & Singleton (1999)", "Cox-Ingersoll-Ross (1985)",
        ],
    }


def five_driver_use_restrictions_json() -> str:
    return json.dumps(five_driver_use_restrictions(), indent=2, sort_keys=True)


__all__ = [
    "DEFAULT_QUINT_LSMC_DEGREE",
    "DEFAULT_MAX_INTERACTION_ORDER_5D",
    "DEFAULT_MORTALITY_QX_CAP",
    "MortalityExposureSpec",
    "FiveDriverCorrelation",
    "FiveDriverNestedResult",
    "FiveDriverNestedEngine",
    "FiveDriverLSMCResult",
    "FiveDriverLSMCProxyEngine",
    "FiveDriverProxyAgreement",
    "FiveDriverDiagnostics",
    "five_driver_use_restrictions",
    "five_driver_use_restrictions_json",
    "_inner_pathwise_pvs_5d",
    "_outer_states_5d",
    "_correlated_shocks_5",
    "_quint_poly_basis",
    "_quint_poly_powers",
    "_n_quint_basis_terms",
]
