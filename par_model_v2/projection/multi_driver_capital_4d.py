"""
Four-Driver (Rates + Equity + Credit + Lapse Behaviour) Nested / LSMC Proxy
===========================================================================

Phase 18 Task 3.  Generalises the Phase 17 *three-driver* (rates + equity +
credit-spread) nested / LSMC economic-capital proxy
(:mod:`par_model_v2.projection.multi_driver_capital_3d`) to a **fourth, non-
financial** driver — a stochastic policyholder-behaviour (lapse-level) index:

    x = (r_H, S_H, s_H, b_H)
        — short rate, equity-index level, credit spread, AND the behavioural
          lapse-index at the capital horizon H.

This directly extends the documented Phase 17 limitation ("lapse, mortality-
trend and FX risks are still NOT in the tail") by adding the *first* non-
financial proxy driver, the recommended next step of the IFoA proxy-modelling
working party (financial AND non-financial drivers).  The behavioural index is
supplied by the new OU driver
(:mod:`par_model_v2.stochastic.lapse_behaviour`); its horizon **lapse
multiplier** ``M = exp(b_H)`` scales the calibrated dynamic-lapse basis
(:mod:`par_model_v2.projection.dynamic_lapse`).

Four-driver liability
---------------------
The conditional horizon-H Q-value of the residual obligation keeps the three
Phase-17 components and folds the lapse driver into the *policyholder-benefit*
components through an **in-force factor** ``IF(r_H, b_H)`` — the survival-to-
maturity probability under the dynamic + behavioural lapse basis, RELATIVE to
the central basis:

    IF(r_H, b_H) = Prod_k (1 - lapse_dyn_k) / Prod_k (1 - lapse_central_k)

where ``lapse_dyn_k = clip( dynamic_lapse(year_k, market=r_H) * exp(b_H) )`` and
``lapse_central_k`` is the duration-only base lapse at zero rate spread.  So

    L(r_H,S_H,s_H,b_H) = IF(r_H,b_H) * [ guaranteed_pv(r_H)
                                       + equity_guarantee_pv(r_H,S_H) ]
                       + credit_loss_pv(r_H,s_H)

The credit loss sits on the spread-sensitive *backing assets* (asset side) and
is NOT in-force scaled.  IF is decreasing in lapse, so the capital tail (upper
tail of ``L``) is driven by the LOW-lapse corner — the classic anti-selection
where policyholders retain in-the-money guarantees — combined with low rates,
low equity, and wide spreads.  The lapse driver also couples to the rate driver
(dynamic lapse rises with r_H) so its effect is genuinely multi-driver while the
behavioural index ``b_H`` adds an orthogonal non-financial axis.

Quadrivariate LSMC surface (pairwise + capped higher-order interactions)
------------------------------------------------------------------------
The Longstaff-Schwartz surface is a **four-variate total-degree polynomial**:

    L_hat(r,S,s,b) = sum_{(a,b,c,d) in P} beta . r^a S^b s^c b^d

where ``P`` holds every exponent quad with ``a+b+c+d <= degree`` EXCEPT genuine
higher-order interactions (three or four non-zero exponents) are *capped* at
combined order ``<= max_interaction_order`` (default 3).  Pairwise interactions
(exactly two non-zero exponents) are retained up to the full degree.  This is
the lean-basis discipline of the IFoA proxy-modelling working party, essential
as the driver count grows (the unrestricted degree-3 four-driver basis is 35
terms; the capped basis is far smaller).

Engines (mirror the three-driver / Task 1 API)
----------------------------------------------
1. ``FourDriverNestedEngine``    — brute-force four-driver ground truth.
2. ``FourDriverLSMCProxyEngine`` — quadrivariate-polynomial LSMC proxy.
3. ``FourDriverDiagnostics``     — proxy-vs-nested agreement on a 4-D state grid,
   reproducibility digest, inner-SE convergence.

ASOP / IA standards
-------------------
- SOA ASOP 7  §3.3   — dynamic / behavioural lapse modelling
- SOA ASOP 56 §3.1.3 / §3.4 / §3.5 — documentation, calibration, adequacy
- SOA ASOP 25 §3.3   — correlated driver / behavioural-basis adequacy
- IA TAS M §3.2 / §3.5 / §3.6 — valuation, assumption basis, validation
- IFoA proxy-modelling working party — financial AND non-financial drivers
- Longstaff & Schwartz (2001); Duffie-Singleton (1999); CIR (1985)

Model-use restrictions (see ``four_driver_use_restrictions()``)
---------------------------------------------------------------
EDUCATIONAL ONLY.  Four risk drivers (rates + equity + credit + lapse) —
mortality-trend and FX risks are still NOT in the tail.  Placeholder
HW1F / GBM / CIR++ / OU-behaviour parameters; the lapse-behaviour index is a
single systemic factor with no product / cohort structure.  The quadrivariate
polynomial surface is valid only across the fitted 4-D state region;
extrapolation is unsupported.  Not a regulatory SCR.  Independent APS X2 review
pending.
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
from par_model_v2.projection.dynamic_lapse import (
    DynamicLapseAssumption,
    base_annual_lapse,
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
from par_model_v2.projection.multi_driver_capital_3d import (
    CreditExposureSpec,
    ThreeDriverCorrelation,
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


#: Default total polynomial degree for the quadrivariate LSMC surface.
DEFAULT_QUAD_LSMC_DEGREE = 2

#: Default cap on the combined order of genuine higher-order (>=3 non-zero
#: exponents) interaction terms.
DEFAULT_MAX_INTERACTION_ORDER_4D = 3


# ---------------------------------------------------------------------------
# Lapse exposure / in-force specification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LapseExposureSpec:
    """Couples the behavioural lapse driver to the policyholder liability.

    The horizon behavioural multiplier ``M = exp(b_H)`` scales the calibrated
    dynamic-lapse assumption, which itself bends with the horizon short rate
    (anti-selection).  The resulting in-force factor relative to the central
    basis (:meth:`inforce_factor`) multiplies the guaranteed + equity-guarantee
    benefit components.

    Parameters
    ----------
    assumption :
        Calibrated dynamic-lapse assumption (default HK PAR).
    credited_rate :
        Rate effectively credited to the policy (reference for the rate spread).
    lapse_cap :
        Hard cap on the resulting annual lapse rate after the behavioural scale.
    """

    assumption: DynamicLapseAssumption = None  # type: ignore[assignment]
    credited_rate: float = 0.025
    lapse_cap: float = 0.35

    def __post_init__(self) -> None:
        if self.assumption is None:
            # A deliberately MILDER dynamic-lapse parameterisation than the
            # default HK PAR pricing assumption: the capital driver applies the
            # horizon short rate as a *sustained* market rate over the whole
            # remaining term, so the aggressive default mass-lapse cliff would
            # run the book off entirely and make the surface near-exponential
            # (hard to proxy). Smaller beta/shock_max + a moderate lapse_cap
            # keep the rate coupling gentle and the surface polynomial-friendly
            # while the behavioural multiplier M=exp(b) remains the dominant,
            # genuinely non-financial axis. (ASOP 7 3.3 -- behaviour basis.)
            object.__setattr__(
                self, "assumption",
                DynamicLapseAssumption(
                    credited_rate=self.credited_rate,
                    beta=0.40, kappa=0.03, shock_max=0.04, tau=0.05,
                    width=0.02, lapse_cap=self.lapse_cap,
                ),
            )
        if not (0.0 < self.lapse_cap <= 1.0):
            raise ValueError("lapse_cap must be in (0, 1]; got {}".format(self.lapse_cap))

    def inforce_factor(
        self, r_h: float, b_h: float, h_month: int, term_months: int
    ) -> float:
        """Survival-to-maturity factor under dynamic+behavioural lapse / central.

        ``IF = Prod_k (1 - q_dyn_k) / Prod_k (1 - q_central_k)`` over the
        remaining months ``H+1 .. T``.  Monotone decreasing in lapse, so the
        upper tail of the liability is the LOW-lapse corner.  At ``b_h = 0`` and
        ``r_h = credited_rate`` the factor is ~1 (backward compatible).
        """
        mult = float(np.exp(b_h))
        surv_dyn = 1.0
        surv_cen = 1.0
        for k in range(1, term_months - h_month + 1):
            m = h_month + k
            policy_year = (m - 1) // 12 + 1
            base = base_annual_lapse(policy_year)
            cen_ann = min(base, self.lapse_cap)
            dyn_ann = self.assumption.annual_rate(
                policy_year, market_rate=r_h, credited_rate=self.credited_rate
            ) * mult
            dyn_ann = min(max(dyn_ann, 0.0), self.lapse_cap)
            # annual -> monthly survival
            surv_cen *= (1.0 - cen_ann) ** (1.0 / 12.0)
            surv_dyn *= (1.0 - dyn_ann) ** (1.0 / 12.0)
        if surv_cen <= 0.0:
            return 1.0
        return float(surv_dyn / surv_cen)


# ---------------------------------------------------------------------------
# Cross-driver correlation (4x4)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FourDriverCorrelation:
    """4x4 ESG correlation among (rate, equity, credit-spread, lapse) shocks.

    The (rate, equity, spread) 3x3 block is inherited from the governed
    :class:`ThreeDriverCorrelation`.  Lapse behaviour is **non-financial**: by
    default it is uncorrelated with every financial shock (``lapse_* = 0``), so
    it injects an orthogonal axis into the tail.  Non-zero couplings are
    configurable (e.g. mild positive lapse-rate co-movement).
    """

    three_driver: ThreeDriverCorrelation = None  # type: ignore[assignment]
    lapse_rate: float = 0.0
    lapse_equity: float = 0.0
    lapse_spread: float = 0.0

    def __post_init__(self) -> None:
        if self.three_driver is None:
            object.__setattr__(self, "three_driver", ThreeDriverCorrelation())
        for name in ("lapse_rate", "lapse_equity", "lapse_spread"):
            v = getattr(self, name)
            if not (-1.0 <= v <= 1.0):
                raise ValueError("{} must be in [-1, 1]; got {}".format(name, v))

    def matrix(self, gbm_rate_equity: float) -> np.ndarray:
        c3 = self.three_driver.matrix(gbm_rate_equity)
        C = np.eye(4, dtype=float)
        C[:3, :3] = c3
        lap = np.array([self.lapse_rate, self.lapse_equity, self.lapse_spread], dtype=float)
        C[3, :3] = lap
        C[:3, 3] = lap
        return C

    def cholesky(self, gbm_rate_equity: float) -> np.ndarray:
        """Lower-triangular Cholesky factor; nearest-PD fallback if needed.

        Placeholder correlations can violate positive-definiteness; project to
        the nearest PD matrix by clipping eigenvalues (Higham-style) so the
        scheme stays well defined (ASOP 25 §3.3).
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
# Four correlated shock arrays
# ---------------------------------------------------------------------------

def _correlated_shocks_4(
    rng: np.random.Generator,
    n: int,
    steps: int,
    chol: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return four (n, steps) correlated antithetic-normal shock arrays.

    Independent antithetic normals are combined by the lower-triangular Cholesky
    factor so the per-step cross-sectional correlation matches ``chol @ chol.T``
    (ASOP 56 §3.5 variance reduction + ASOP 25 §3.3 correlation).
    """
    z0 = _antithetic_normals(rng, n, steps)
    z1 = _antithetic_normals(rng, n, steps)
    z2 = _antithetic_normals(rng, n, steps)
    z3 = _antithetic_normals(rng, n, steps)
    zr = chol[0, 0] * z0
    zs = chol[1, 0] * z0 + chol[1, 1] * z1
    zc = chol[2, 0] * z0 + chol[2, 1] * z1 + chol[2, 2] * z2
    zb = chol[3, 0] * z0 + chol[3, 1] * z1 + chol[3, 2] * z2 + chol[3, 3] * z3
    return zr, zs, zc, zb


# ---------------------------------------------------------------------------
# Four-driver inner valuation: L(r_H, S_H, s_H, b_H)
# ---------------------------------------------------------------------------

def _inner_pathwise_pvs_4d(
    r: float,
    s: float,
    spread: float,
    b: float,
    n_inner: int,
    rem_months: int,
    product: ParEndowmentProduct,
    base_hw_params: HullWhiteParams,
    gbm_params: GBMParams,
    spread_params: CreditSpreadParams,
    correlation: FourDriverCorrelation,
    h_month: int,
    seed: int,
    equity_guarantee: EquityGuaranteeSpec,
    credit_exposure: CreditExposureSpec,
    lapse_exposure: LapseExposureSpec,
    annual_qx_fn: Optional[Callable] = None,
) -> np.ndarray:
    """Return ``n_inner`` pathwise residual-PV samples at state ``(r,s,spread,b)``.

    Each sample is an unbiased draw of
    ``L = E^Q[ IF(r,b) * (guaranteed PV + equity-guarantee PV) + credit-loss PV ]``
    on one correlated inner ``(rate, equity, spread)`` triple.  The lapse driver
    enters deterministically through the in-force factor ``IF(r, b)`` (the
    behavioural multiplier is set at the horizon and applied over ``[H, T]``).
    """
    rng = np.random.default_rng(seed)
    chol = correlation.cholesky(gbm_params.rate_equity_correlation)
    z_rate, z_equity, z_spread, _z_lapse = _correlated_shocks_4(
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

    # Component 1 — guaranteed death + maturity benefits (rate-driven), in-force
    # scaled by the lapse driver.
    cf = _residual_cashflow_vector(product, h_month, annual_qx_fn)
    guaranteed_pv = inforce * (disc @ cf)

    # Component 2 — equity-linked maturity guarantee (rates + equity), in-force
    # scaled (only in-force policies collect the maturity guarantee).
    units = equity_guarantee.units(product.sum_assured)
    floor = equity_guarantee.floor(product.sum_assured)
    fund_T = units * equity_paths[:, rem_months]
    eq_payoff = np.maximum(floor - fund_T, 0.0)
    eq_guarantee_pv = inforce * (disc[:, rem_months] * eq_payoff)

    # Component 3 — credit loss on spread-sensitive backing assets (asset side;
    # NOT in-force scaled). Reduced-form 1 - exp(-∫ s du), discounted from T.
    notional = credit_exposure.notional(product.sum_assured)
    dt = 1.0 / 12.0
    cum_hazard = spread_paths[:, :rem_months].sum(axis=1) * dt
    loss_fraction = 1.0 - np.exp(-cum_hazard)
    credit_loss_pv = disc[:, rem_months] * notional * loss_fraction

    return guaranteed_pv + eq_guarantee_pv + credit_loss_pv


# ---------------------------------------------------------------------------
# Four-driver outer-state sampling
# ---------------------------------------------------------------------------

def _outer_states_4d(
    n_outer: int,
    capital_horizon_months: int,
    measure: Measure,
    hw_params: HullWhiteParams,
    gbm_params: GBMParams,
    spread_params: CreditSpreadParams,
    lapse_params: LapseBehaviourParams,
    correlation: FourDriverCorrelation,
    initial_curve: Optional[RiskFreeCurve],
    seed: int,
) -> np.ndarray:
    """Project ``n_outer`` outer paths to H; return an (n, 4) array.

    Drives the four building-block processes (HW1F rate, GBM equity, CIR++
    spread, OU lapse-behaviour) off a SHARED 4-factor Cholesky-correlated
    antithetic draw, so the outer ``(r, S, s, b)`` joint is genuinely correlated
    under the governed 4x4 ESG matrix (ASOP 25 §3.3).
    """
    rng = np.random.default_rng(seed)
    chol = correlation.cholesky(gbm_params.rate_equity_correlation)
    z_rate, z_equity, z_spread, z_lapse = _correlated_shocks_4(
        rng, n_outer, capital_horizon_months, chol
    )
    curve = initial_curve if initial_curve is not None else RiskFreeCurve.flat(
        hw_params.initial_short_rate
    )
    hw = HullWhiteRateProcess(hw_params, initial_curve=curve)
    gbm = GBMEquityProcess(gbm_params, rate_process=hw)
    csp = CreditSpreadProcess(spread_params)
    lap = LapseBehaviourProcess(lapse_params)

    rate_paths = hw._simulate_array(n_outer, capital_horizon_months, measure, z_rate)
    equity_paths, _ret = gbm._simulate_array(
        n_outer, capital_horizon_months, measure, rate_paths, z_equity
    )
    spread_paths = csp._simulate_array(n_outer, capital_horizon_months, measure, z_spread)
    lapse_paths = lap._simulate_array(n_outer, capital_horizon_months, measure, z_lapse)

    r_h = rate_paths[:, capital_horizon_months]
    s_h = equity_paths[:, capital_horizon_months]
    c_h = spread_paths[:, capital_horizon_months]
    b_h = lapse_paths[:, capital_horizon_months]
    return np.column_stack([r_h, s_h, c_h, b_h])


# ---------------------------------------------------------------------------
# Quadrivariate total-degree polynomial basis (pairwise + capped higher-order)
# ---------------------------------------------------------------------------

def _quad_poly_powers(
    degree: int,
    max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER_4D,
) -> List[Tuple[int, int, int, int]]:
    """Exponent quads (a,b,c,d), a+b+c+d <= degree, capped higher-order terms.

    A *genuine higher-order* term (three or four non-zero exponents) is admitted
    only while ``a+b+c+d <= max_interaction_order``.  Constant, single-driver and
    pairwise (exactly two non-zero exponents) terms are retained up to the full
    ``degree``.  Ordered by total degree then lexicographically.
    """
    if degree < 0:
        raise ValueError("degree must be >= 0")
    powers: List[Tuple[int, int, int, int]] = []
    for total in range(degree + 1):
        for a in range(total + 1):
            for bb in range(total - a + 1):
                for c in range(total - a - bb + 1):
                    d = total - a - bb - c
                    nonzero = sum(1 for e in (a, bb, c, d) if e >= 1)
                    if nonzero >= 3 and total > max_interaction_order:
                        continue
                    powers.append((a, bb, c, d))
    return powers


def _quad_poly_basis(
    X: np.ndarray,
    degree: int,
    max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER_4D,
) -> np.ndarray:
    """Quadrivariate design matrix for X of shape (n, 4)."""
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[1] != 4:
        raise ValueError("X must have shape (n, 4); got {}".format(X.shape))
    powers = _quad_poly_powers(degree, max_interaction_order)
    cols = [
        X[:, 0] ** a * X[:, 1] ** b * X[:, 2] ** c * X[:, 3] ** d
        for (a, b, c, d) in powers
    ]
    return np.column_stack(cols)


def _n_quad_basis_terms(
    degree: int,
    max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER_4D,
) -> int:
    return len(_quad_poly_powers(degree, max_interaction_order))


# ---------------------------------------------------------------------------
# 1. Four-driver nested-stochastic engine (ground truth)
# ---------------------------------------------------------------------------

@dataclass
class FourDriverNestedResult:
    capital: CapitalMetrics
    outer_states: np.ndarray              # (n_outer, 4): r_H, S_H, s_H, b_H
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
            "drivers": ["short_rate", "equity_level", "credit_spread", "lapse_behaviour"],
            "run_id": self.run_id,
            "duration_seconds": round(self.duration_seconds, 4),
        }


class FourDriverNestedEngine:
    """Brute-force four-driver nested-stochastic capital engine (ground truth).

    Outer real-world scenarios -> state ``(r_H, S_H, s_H, b_H)`` -> fresh
    correlated inner ``(rate, equity, spread)`` Q nest per node (lapse enters
    deterministically through the in-force factor) -> ``L`` -> capital metrics.
    Expensive but unbiased; benchmarks the quadrivariate LSMC proxy.

    SOA ASOP 56 §3.1.3/§3.5; IA TAS M §3.2/§3.6; ASOP 25 §3.3; ASOP 7 §3.3.
    """

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
        self.correlation = correlation if correlation is not None else FourDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.lapse_exposure = lapse_exposure or LapseExposureSpec()
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
        actor: str = "FourDriverNestedEngine",
        phase: str = "Phase 18: Tail-Dependent Risk Aggregation and Driver/Calibration Sophistication",
    ) -> FourDriverNestedResult:
        t0 = time.monotonic()
        run_id = "fd-nested-" + uuid.uuid4().hex[:8]
        rem = self.product.term_months - self.capital_horizon_months

        outer = _outer_states_4d(
            n_outer, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params, self.lapse_params,
            self.correlation, self.initial_curve, seed,
        )
        child_seeds = np.random.SeedSequence(seed).spawn(len(outer))
        cond_l = np.empty(len(outer), dtype=float)
        inner_se = np.empty(len(outer), dtype=float)
        for i, (r, s, c, b) in enumerate(outer):
            inner_seed = int(child_seeds[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_4d(
                float(r), float(s), float(c), float(b), n_inner, rem, self.product,
                self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.credit_exposure, self.lapse_exposure,
                self.annual_qx_fn,
            )
            cond_l[i] = float(pvs.mean())
            inner_se[i] = float(pvs.std(ddof=1) / np.sqrt(n_inner)) if n_inner > 1 else 0.0

        capital = capital_metrics_from_liabilities(
            cond_l, self.confidence_level, self.capital_horizon_months
        )
        duration = time.monotonic() - t0

        audit_entry_id = _maybe_audit(
            governance_store, actor, phase, run_id, n_outer * n_inner, duration,
            "4D-nested VaR{:.1f}%={:.2f}; ES={:.2f}; SCR_proxy={:.2f}; "
            "N_outer={}; n_inner={}; drivers=r,S,s,b".format(
                self.confidence_level * 100, capital.var_liability,
                capital.es_liability, capital.scr_proxy, n_outer, n_inner),
        )

        return FourDriverNestedResult(
            capital=capital, outer_states=outer, conditional_liabilities=cond_l,
            inner_standard_errors=inner_se, n_outer=len(outer), n_inner=n_inner,
            total_inner_valuations=len(outer) * n_inner, run_id=run_id,
            duration_seconds=duration, audit_entry_id=audit_entry_id,
        )


# ---------------------------------------------------------------------------
# 2. Four-driver LSMC proxy engine
# ---------------------------------------------------------------------------

@dataclass
class FourDriverLSMCResult:
    capital: CapitalMetrics
    beta: np.ndarray
    centers: np.ndarray                # (4,)
    scales: np.ndarray                 # (4,)
    degree: int
    max_interaction_order: int
    powers: List[Tuple[int, int, int, int]]
    fit_r2: float
    n_fit: int
    n_outer_eval: int
    fitted_liabilities: np.ndarray
    fit_states: np.ndarray             # (n_fit, 4)
    fit_payoffs: np.ndarray
    run_id: str
    duration_seconds: float
    audit_entry_id: Optional[str] = None

    def predict(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        Xs = (X - self.centers) / self.scales
        return _quad_poly_basis(Xs, self.degree, self.max_interaction_order) @ self.beta

    def summary(self) -> dict:
        return {
            "capital": self.capital.summary(),
            "degree": self.degree,
            "max_interaction_order": self.max_interaction_order,
            "n_basis_terms": len(self.powers),
            "fit_r2": round(self.fit_r2, 6),
            "n_fit": self.n_fit,
            "n_outer_eval": self.n_outer_eval,
            "drivers": ["short_rate", "equity_level", "credit_spread", "lapse_behaviour"],
            "run_id": self.run_id,
            "duration_seconds": round(self.duration_seconds, 4),
        }


class FourDriverLSMCProxyEngine:
    """Quadrivariate Longstaff-Schwartz least-squares Monte-Carlo capital proxy.

    Fits ``L_hat(r,S,s,b) = phi(r,S,s,b) . beta`` (capped quadrivariate
    polynomial) from ``N_fit`` noisy single-inner-path samples, then evaluates
    across a large cheap correlated outer set.  Longstaff & Schwartz (2001);
    IFoA proxy-model WP.  SOA ASOP 56 §3.5; IA TAS M §3.6; ASOP 25 §3.3.
    """

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
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        outer_measure: Measure = Measure.P,
        degree: int = DEFAULT_QUAD_LSMC_DEGREE,
        max_interaction_order: int = DEFAULT_MAX_INTERACTION_ORDER_4D,
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
        self.correlation = correlation if correlation is not None else FourDriverCorrelation()
        self.initial_curve = initial_curve
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.lapse_exposure = lapse_exposure or LapseExposureSpec()
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
        for i, (r, s, c, b) in enumerate(fit_X):
            inner_seed = int(child_seeds[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_4d(
                float(r), float(s), float(c), float(b), 1, rem, self.product,
                self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, inner_seed,
                self.equity_guarantee, self.credit_exposure, self.lapse_exposure,
                self.annual_qx_fn,
            )
            fit_y[i] = float(pvs[0])
        return fit_y

    def fit_and_run(
        self,
        n_fit: int = 2_000,
        n_outer_eval: int = 5_000,
        seed: int = 42,
        governance_store: Optional["GovernanceStore"] = None,
        actor: str = "FourDriverLSMCProxyEngine",
        phase: str = "Phase 18: Tail-Dependent Risk Aggregation and Driver/Calibration Sophistication",
    ) -> FourDriverLSMCResult:
        t0 = time.monotonic()
        run_id = "fd-lsmc-" + uuid.uuid4().hex[:8]

        fit_X = _outer_states_4d(
            n_fit, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params, self.lapse_params,
            self.correlation, self.initial_curve, seed,
        )
        fit_y = self._fit_payoffs(fit_X, seed)

        centers = fit_X.mean(axis=0)
        scales = fit_X.std(axis=0, ddof=0)
        scales = np.where(scales > 0, scales, 1.0)
        Xs = (fit_X - centers) / scales
        design = _quad_poly_basis(Xs, self.degree, self.max_interaction_order)
        beta, _resid, _rank, _sv = np.linalg.lstsq(design, fit_y, rcond=None)
        y_hat = design @ beta
        ss_res = float(np.sum((fit_y - y_hat) ** 2))
        ss_tot = float(np.sum((fit_y - fit_y.mean()) ** 2)) or 1.0
        fit_r2 = 1.0 - ss_res / ss_tot

        eval_X = _outer_states_4d(
            n_outer_eval, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.gbm_params, self.spread_params, self.lapse_params,
            self.correlation, self.initial_curve, seed + 2,
        )
        eval_Xs = (eval_X - centers) / scales
        fitted_l = _quad_poly_basis(eval_Xs, self.degree, self.max_interaction_order) @ beta

        capital = capital_metrics_from_liabilities(
            fitted_l, self.confidence_level, self.capital_horizon_months
        )
        duration = time.monotonic() - t0

        audit_entry_id = _maybe_audit(
            governance_store, actor, phase, run_id, n_fit, duration,
            "4D-LSMC VaR{:.1f}%={:.2f}; ES={:.2f}; SCR_proxy={:.2f}; R2={:.4f}; "
            "N_fit={}; deg={}; max_int={}; terms={}".format(
                self.confidence_level * 100, capital.var_liability,
                capital.es_liability, capital.scr_proxy, fit_r2, n_fit,
                self.degree, self.max_interaction_order,
                _n_quad_basis_terms(self.degree, self.max_interaction_order)),
        )

        return FourDriverLSMCResult(
            capital=capital, beta=beta, centers=centers, scales=scales,
            degree=self.degree, max_interaction_order=self.max_interaction_order,
            powers=_quad_poly_powers(self.degree, self.max_interaction_order),
            fit_r2=fit_r2, n_fit=len(fit_X), n_outer_eval=len(eval_X),
            fitted_liabilities=fitted_l, fit_states=fit_X, fit_payoffs=fit_y,
            run_id=run_id, duration_seconds=duration, audit_entry_id=audit_entry_id,
        )


# ---------------------------------------------------------------------------
# 3. Four-driver diagnostics
# ---------------------------------------------------------------------------

@dataclass
class FourDriverProxyAgreement:
    max_abs_rel_error: float
    rmse: float
    r2_vs_nested: float
    grid_states: np.ndarray   # (m, 4)
    nested_l: np.ndarray
    proxy_l: np.ndarray

    def summary(self) -> dict:
        return {
            "max_abs_rel_error": round(self.max_abs_rel_error, 6),
            "rmse": round(self.rmse, 6),
            "r2_vs_nested": round(self.r2_vs_nested, 6),
            "n_grid": int(self.grid_states.shape[0]),
        }


class FourDriverDiagnostics:
    """Proxy-vs-nested agreement, reproducibility, and inner SE for 4-D state.

    SOA ASOP 56 §3.5; IA TAS M §3.6.
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        gbm_params: Optional[GBMParams] = None,
        spread_params: Optional[CreditSpreadParams] = None,
        lapse_params: Optional[LapseBehaviourParams] = None,
        correlation: Optional[FourDriverCorrelation] = None,
        equity_guarantee: Optional[EquityGuaranteeSpec] = None,
        credit_exposure: Optional[CreditExposureSpec] = None,
        lapse_exposure: Optional[LapseExposureSpec] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.gbm_params = gbm_params if gbm_params is not None else GBMParams()
        self.spread_params = spread_params if spread_params is not None else CreditSpreadParams()
        self.lapse_params = lapse_params if lapse_params is not None else LapseBehaviourParams()
        self.correlation = correlation if correlation is not None else FourDriverCorrelation()
        self.equity_guarantee = equity_guarantee or EquityGuaranteeSpec()
        self.credit_exposure = credit_exposure or CreditExposureSpec()
        self.lapse_exposure = lapse_exposure or LapseExposureSpec()
        self.capital_horizon_months = int(capital_horizon_months)
        self.annual_qx_fn = annual_qx_fn

    def nested_liability(
        self, r: float, s: float, spread: float, b: float,
        n_inner: int = 4_096, seed: int = 11,
    ) -> float:
        rem = self.product.term_months - self.capital_horizon_months
        pvs = _inner_pathwise_pvs_4d(
            float(r), float(s), float(spread), float(b), n_inner, rem, self.product,
            self.hw_params, self.gbm_params, self.spread_params, self.correlation,
            self.capital_horizon_months, seed, self.equity_guarantee,
            self.credit_exposure, self.lapse_exposure, self.annual_qx_fn,
        )
        return float(pvs.mean())

    def proxy_vs_nested(
        self,
        proxy: FourDriverLSMCResult,
        grid_per_dim: int = 2,
        n_inner: int = 4_096,
        seed: int = 11,
    ) -> FourDriverProxyAgreement:
        """Compare the quadrivariate LSMC surface to nested L on a 4-D grid.

        The grid spans the 10-90 percentile box of the fitted states per
        dimension (robust to outer-tail outliers).  ``grid_per_dim**4`` nested
        valuations (default 2 -> 16 nodes) keeps the diagnostic affordable.
        """
        lo_hi = [np.quantile(proxy.fit_states[:, dd], [0.1, 0.9]) for dd in range(4)]
        axes = [np.linspace(lo, hi, grid_per_dim) for (lo, hi) in lo_hi]
        grid = np.array(
            [[a, b, c, d] for a in axes[0] for b in axes[1]
             for c in axes[2] for d in axes[3]],
            dtype=float,
        )
        child = np.random.SeedSequence(seed).spawn(len(grid))
        nested = np.empty(len(grid), dtype=float)
        rem = self.product.term_months - self.capital_horizon_months
        for i, (r, s, c, b) in enumerate(grid):
            sd = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs_4d(
                float(r), float(s), float(c), float(b), n_inner, rem, self.product,
                self.hw_params, self.gbm_params, self.spread_params,
                self.correlation, self.capital_horizon_months, sd,
                self.equity_guarantee, self.credit_exposure, self.lapse_exposure,
                self.annual_qx_fn,
            )
            nested[i] = float(pvs.mean())
        proxy_l = proxy.predict(grid)
        denom = np.where(np.abs(nested) > 1e-9, np.abs(nested), 1.0)
        rel = np.abs(proxy_l - nested) / denom
        rmse = float(np.sqrt(np.mean((proxy_l - nested) ** 2)))
        ss_res = float(np.sum((nested - proxy_l) ** 2))
        ss_tot = float(np.sum((nested - nested.mean()) ** 2)) or 1.0
        return FourDriverProxyAgreement(
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
        files_changed=["par_model_v2/projection/multi_driver_capital_4d.py"],
        test_summary=summary,
    )
    governance_store.audit_trail.append(entry)
    return entry.entry_id


def four_driver_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the four-driver capital proxy.

    SOA ASOP 56 §3.5.1; IA TAS M §3.6.
    """
    return {
        "module": "par_model_v2/projection/multi_driver_capital_4d.py",
        "classification": "EDUCATIONAL ONLY — NOT a regulatory capital model",
        "risk_drivers": (
            "Capital tail is driven by FOUR correlated drivers at the horizon: "
            "the short rate r_H, the equity level S_H, the credit spread s_H, "
            "AND the non-financial lapse-behaviour index b_H (governed 4x4 ESG "
            "correlation carried through outer and inner). Mortality-trend and "
            "FX risks are still NOT in the tail."
        ),
        "improvement_over_phase17": (
            "Closes the documented LAPSE limitation of the Phase 17 three-driver "
            "proxy by adding the first NON-FINANCIAL driver: an OU lapse-"
            "behaviour index whose horizon multiplier M=exp(b) scales the "
            "calibrated dynamic-lapse basis through an in-force factor on the "
            "policyholder-benefit components."
        ),
        "lapse_model": (
            "Single systemic OU behavioural index; lapse multiplier exp(b) on "
            "the calibrated dynamic-lapse assumption (rate-responsive). No "
            "product / cohort structure, no mortality-trend interaction. "
            "In-force factor scales guaranteed + equity-guarantee benefits only; "
            "credit loss (asset side) is not in-force scaled."
        ),
        "placeholder_parameters": (
            "HW1F, GBM, CIR++, and OU-behaviour parameters are illustrative "
            "placeholders; capital magnitudes are NOT calibrated. The lapse "
            "kappa_b/sigma_b are not fitted to a lapse-experience time series."
        ),
        "lsmc_extrapolation": (
            "The quadrivariate polynomial surface L_hat(r,S,s,b) is valid only "
            "across the fitted 4-D state region (interquartile box). Higher-"
            "order (>=3-way) interaction terms are capped (default order 3). "
            "Extrapolation is unsupported and may be unstable at high degree."
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
            "SOA ASOP 7 §3.3", "SOA ASOP 56 §3.1.3", "SOA ASOP 56 §3.4",
            "SOA ASOP 56 §3.5", "SOA ASOP 25 §3.3", "IA TAS M §3.2",
            "IA TAS M §3.5", "IA TAS M §3.6", "IFoA proxy-modelling WP",
            "Longstaff & Schwartz (2001)", "Duffie & Singleton (1999)",
            "Cox-Ingersoll-Ross (1985)",
        ],
    }


def four_driver_use_restrictions_json() -> str:
    return json.dumps(four_driver_use_restrictions(), indent=2, sort_keys=True)


__all__ = [
    "DEFAULT_QUAD_LSMC_DEGREE",
    "DEFAULT_MAX_INTERACTION_ORDER_4D",
    "LapseExposureSpec",
    "FourDriverCorrelation",
    "FourDriverNestedResult",
    "FourDriverNestedEngine",
    "FourDriverLSMCResult",
    "FourDriverLSMCProxyEngine",
    "FourDriverProxyAgreement",
    "FourDriverDiagnostics",
    "four_driver_use_restrictions",
    "four_driver_use_restrictions_json",
    "_inner_pathwise_pvs_4d",
    "_outer_states_4d",
    "_correlated_shocks_4",
    "_quad_poly_basis",
    "_quad_poly_powers",
    "_n_quad_basis_terms",
]
