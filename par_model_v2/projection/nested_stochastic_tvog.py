"""
Nested-Stochastic / LSMC TVOG Proxy for Capital Metrics
=======================================================

Phase 14 Task 6.  Adds a *capital-metric* layer on top of the Phase 4
``TVOGEngine``: the time-value of the guarantee is re-valued at a future
*capital horizon* and its distribution across real-world (outer) scenarios is
turned into VaR / Expected-Shortfall capital figures.

Two engines are provided plus a diagnostic harness:

1. ``NestedStochasticTVOGEngine`` — the brute-force "ground truth".
   Outer (real-world / P-measure by default) scenarios are projected to the
   capital horizon ``H``.  At every outer node the residual guarantee is
   re-valued with a *fresh inner* set of risk-neutral (Q-measure) scenarios
   conditioned on that node's short rate.  Cost = ``N_outer x n_inner`` inner
   valuations — accurate but expensive.

2. ``LSMCProxyEngine`` — a Longstaff-Schwartz least-squares Monte-Carlo proxy.
   A small set of *fitting* outer states each receive **one** noisy inner
   pathwise payoff; a polynomial conditional-expectation surface
   ``L_hat(x) = phi(x) . beta`` is regressed on those noisy samples and then
   evaluated cheaply across the full outer distribution.  Cost = ``N_fit``
   single-path inner valuations — a fraction of the nested cost.

3. ``NestedStochasticDiagnostics`` — convergence (inner standard-error decay,
   outer VaR/ES stability), reproducibility (seed-determinism SHA-256), and
   proxy-vs-nested agreement (R^2, max abs relative error, unbiasedness).

Capital-metric framing
----------------------
Let ``L(x)`` be the conditional Q-measure value, *as of the capital horizon
H*, of the residual guaranteed cashflows, conditioned on the outer short rate
``x = r_H``.  Across the outer distribution we obtain the random variable
``L = L(r_H)``.  For a guarantee, an *increase* in value is the insurer's loss,
so capital is driven by the upper tail:

    VaR_alpha      = quantile_alpha( L )
    ES_alpha       = E[ L | L >= VaR_alpha ]
    SCR_proxy      = VaR_alpha( L ) - E[ L ]            (excess over the mean)

This mirrors a 1-year-VaR economic-capital view (e.g. Solvency II SCR horizon)
but is an **educational proxy**, not a regulatory calculation.

Why a proxy at all
------------------
Full nested stochastic valuation is ``N_outer x n_inner`` inner valuations.
For a 99.5% capital metric the outer count must be large (>= 2,000), and each
inner valuation needs many Q paths to converge — quickly reaching millions of
inner simulations.  LSMC replaces the inner nest with a regression fitted to a
handful of noisy single-path samples, recovering the conditional-expectation
surface at a tiny fraction of the cost.  This is standard proxy-model practice
(Longstaff & Schwartz 2001; IFoA proxy-model working-party guidance).

ASOP / IA Standards
-------------------
- SOA ASOP 56 §3.1.3 — stochastic model documentation & output governance
- SOA ASOP 56 §3.5   — scenario adequacy & convergence diagnostics
- SOA ASOP 25 §3.3   — scenario generation adequacy
- IA TAS M §3.2      — market-consistent valuation
- IA TAS M §3.6      — model validation, convergence, reproducibility
- IFoA MCEV Principles §7 — TVOG methodology

Model-use restrictions (see ``model_use_restrictions()``)
---------------------------------------------------------
EDUCATIONAL ONLY.  Single risk driver (short rate) — no equity / lapse / credit
risk in the capital tail.  Placeholder HW1F parameters.  The LSMC surface is a
low-order polynomial valid only across the *fitted* state range; extrapolation
beyond it is unsupported.  Not a regulatory SCR.  Independent review pending.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import (TYPE_CHECKING, Callable, Dict, List, Optional,
                    Sequence, Tuple)

import numpy as np

if TYPE_CHECKING:
    from par_model_v2.governance.audit_trail import GovernanceStore

from par_model_v2.projection.monthly_projection import (
    ParEndowmentProduct,
    monthly_mortality_qx,
    _base_annual_qx,
)
from par_model_v2.projection.tvog import _scenario_discount_factors
from par_model_v2.stochastic.esg_process import (
    HullWhiteParams,
    HullWhiteRateProcess,
    Measure,
    RiskFreeCurve,
    ScenarioSet,
    _antithetic_normals,
)


# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

#: Default capital horizon in months (1-year VaR / SCR style).
DEFAULT_CAPITAL_HORIZON_MONTHS = 12

#: Default capital confidence level (Solvency II SCR is 99.5%).
DEFAULT_CONFIDENCE_LEVEL = 0.995

#: Outer scenario minimum for a 99.5% capital metric (ASOP 56 §3.5 guidance).
CAPITAL_OUTER_MINIMUM = 2_000

#: Default LSMC polynomial degree for the conditional-expectation surface.
DEFAULT_LSMC_DEGREE = 3


# ---------------------------------------------------------------------------
# Residual guarantee valuation (conditional value at the capital horizon)
# ---------------------------------------------------------------------------

def _residual_guaranteed_pv(
    product: ParEndowmentProduct,
    h_month: int,
    disc_from_h: np.ndarray,
    annual_qx_fn: Optional[Callable] = None,
) -> float:
    """PV *as of month H* of guaranteed cashflows over months H+1 .. T.

    Conditional on an in-force policy at the capital horizon ``h_month`` (so
    survival to H is normalised to 1.0).  Mortality is deterministic (expected
    cashflows); the randomness comes from the discount path supplied.

    Parameters
    ----------
    product : ParEndowmentProduct
    h_month : int
        Capital-horizon month H (0 < H < term_months).
    disc_from_h : np.ndarray, shape (rem + 1,)
        Cumulative discount factors from month H, where ``rem = T - H``;
        ``disc_from_h[0] == 1.0`` and ``disc_from_h[k]`` discounts month H+k
        back to H.
    annual_qx_fn : callable(age, gender) -> float, optional

    Returns
    -------
    float
        PV at H of the residual guaranteed death + maturity benefits.
    """
    T = product.term_months
    rem = T - h_month
    if rem <= 0:
        return 0.0
    surv = 1.0
    pv = 0.0
    for k in range(1, rem + 1):
        m = h_month + k
        age_at_m = product.issue_age + (m - 1) // 12
        if annual_qx_fn is not None:
            ann_qx = annual_qx_fn(age_at_m, product.gender)
        else:
            ann_qx = _base_annual_qx(age_at_m, product.gender)
        qx_m = monthly_mortality_qx(ann_qx)
        death_prob = surv * qx_m
        pv += product.sum_assured * death_prob * disc_from_h[k]
        surv *= (1.0 - qx_m)
        if m == T:
            pv += product.sum_assured * surv * disc_from_h[rem]
    return pv


def _residual_cashflow_vector(
    product: ParEndowmentProduct,
    h_month: int,
    annual_qx_fn: Optional[Callable] = None,
) -> np.ndarray:
    """Expected guaranteed cashflow per month, aligned to disc index 0..rem.

    Mortality is deterministic, so the expected guaranteed cashflow at each
    future month is identical across inner paths — precompute it once and reuse
    for the whole inner nest.  ``cf[k]`` is the expected cashflow at month H+k
    (``cf[0] == 0``); the maturity benefit is folded into ``cf[rem]``.  The
    pathwise PV is then ``disc_from_h @ cf`` — numerically identical to the
    per-month loop in ``_residual_guaranteed_pv`` but fully vectorisable.
    """
    T = product.term_months
    rem = T - h_month
    cf = np.zeros(rem + 1, dtype=float)
    if rem <= 0:
        return cf
    surv = 1.0
    for k in range(1, rem + 1):
        m = h_month + k
        age_at_m = product.issue_age + (m - 1) // 12
        if annual_qx_fn is not None:
            ann_qx = annual_qx_fn(age_at_m, product.gender)
        else:
            ann_qx = _base_annual_qx(age_at_m, product.gender)
        qx_m = monthly_mortality_qx(ann_qx)
        cf[k] += product.sum_assured * surv * qx_m            # death benefit
        surv *= (1.0 - qx_m)
        if m == T:
            cf[rem] += product.sum_assured * surv             # maturity benefit
    return cf


def _vectorised_discount_factors(rate_paths: np.ndarray) -> np.ndarray:
    """Cumulative monthly discount factors for a (n, rem+1) short-rate matrix.

    ``d[:, 0] == 1`` and ``d[:, m] = prod_{k<m} 1/(1 + r[:, k]/12)`` — the
    vectorised equivalent of ``_scenario_discount_factors`` applied row-wise.
    """
    n, cols = rate_paths.shape
    monthly = rate_paths[:, : cols - 1] / 12.0
    d = np.ones((n, cols), dtype=float)
    d[:, 1:] = np.cumprod(1.0 / (1.0 + monthly), axis=1)
    return d


def _inner_q_process(x: float, base_hw_params: HullWhiteParams) -> HullWhiteRateProcess:
    """Build a Q-measure HW1F process conditioned on outer short rate ``x``.

    The inner valuation starts at short rate ``x`` and is fitted to a flat
    risk-free curve at ``x`` so the Q-measure drift mean-reverts around the
    conditioning state.  Volatility / mean-reversion are inherited from the
    outer parameters; only the level is re-anchored.
    """
    inner_params = HullWhiteParams(
        mean_reversion_speed=base_hw_params.mean_reversion_speed,
        short_rate_vol=base_hw_params.short_rate_vol,
        initial_short_rate=float(x),
        long_run_rate_p=base_hw_params.long_run_rate_p,
        market_price_of_risk=base_hw_params.market_price_of_risk,
        cbirc_rate_cap=base_hw_params.cbirc_rate_cap,
        short_rate_floor=base_hw_params.short_rate_floor,
        short_rate_ceiling=base_hw_params.short_rate_ceiling,
    )
    curve = RiskFreeCurve.flat(float(x))
    return HullWhiteRateProcess(inner_params, initial_curve=curve)


def _inner_pathwise_pvs(
    x: float,
    n_inner: int,
    rem_months: int,
    product: ParEndowmentProduct,
    base_hw_params: HullWhiteParams,
    h_month: int,
    seed: int,
    annual_qx_fn: Optional[Callable] = None,
) -> np.ndarray:
    """Return the ``n_inner`` pathwise residual-PV samples at state ``x``.

    Each sample is an unbiased draw of ``L(x) = E^Q[ residual PV | r_H = x ]``.
    Antithetic normals are used for inner variance reduction (ASOP 56 §3.5).
    """
    rng = np.random.default_rng(seed)
    shocks = _antithetic_normals(rng, n_inner, rem_months)
    hw = _inner_q_process(x, base_hw_params)
    rate_paths = hw._simulate_array(n_inner, rem_months, Measure.Q, shocks)
    cf = _residual_cashflow_vector(product, h_month, annual_qx_fn)
    disc = _vectorised_discount_factors(rate_paths)   # (n_inner, rem+1)
    return disc @ cf


# ---------------------------------------------------------------------------
# Capital-metric helper
# ---------------------------------------------------------------------------

@dataclass
class CapitalMetrics:
    """VaR / ES capital metrics derived from an outer liability distribution.

    All figures are stated *at the capital horizon H* (not deflated to t=0).
    """
    confidence_level: float
    mean_liability: float
    var_liability: float
    es_liability: float
    scr_proxy: float
    n_outer: int
    capital_horizon_months: int

    def summary(self) -> dict:
        return {
            "confidence_level": self.confidence_level,
            "mean_liability": round(self.mean_liability, 4),
            "var_liability": round(self.var_liability, 4),
            "es_liability": round(self.es_liability, 4),
            "scr_proxy": round(self.scr_proxy, 4),
            "n_outer": self.n_outer,
            "capital_horizon_months": self.capital_horizon_months,
        }


def capital_metrics_from_liabilities(
    liabilities: np.ndarray,
    confidence_level: float,
    capital_horizon_months: int,
) -> CapitalMetrics:
    """Compute VaR/ES/SCR-proxy from a sample of conditional liability values.

    For a guarantee an *increase* in value is the loss, so the capital tail is
    the **upper** tail of ``liabilities``.
    """
    liabilities = np.asarray(liabilities, dtype=float)
    mean_l = float(liabilities.mean())
    var_l = float(np.quantile(liabilities, confidence_level))
    tail = liabilities[liabilities >= var_l]
    es_l = float(tail.mean()) if tail.size else var_l
    return CapitalMetrics(
        confidence_level=confidence_level,
        mean_liability=mean_l,
        var_liability=var_l,
        es_liability=es_l,
        scr_proxy=var_l - mean_l,
        n_outer=int(liabilities.size),
        capital_horizon_months=capital_horizon_months,
    )


# ---------------------------------------------------------------------------
# Outer-state sampling (shared by both engines)
# ---------------------------------------------------------------------------

def _outer_states(
    n_outer: int,
    capital_horizon_months: int,
    measure: Measure,
    hw_params: HullWhiteParams,
    initial_curve: Optional[RiskFreeCurve],
    seed: int,
) -> np.ndarray:
    """Project ``n_outer`` outer paths to H and return the short rate at H.

    Uses the governed ``ScenarioSet.generate`` path so the outer driver shares
    the model's measure-enforcement and parameter-snapshot machinery.
    """
    scen = ScenarioSet.generate(
        n=n_outer,
        T_months=capital_horizon_months,
        measure=measure,
        hw_params=hw_params,
        initial_curve=initial_curve,
        seed=seed,
    )
    pivot = scen.data.pivot(index="scenario_id", columns="month", values="r_short")
    return pivot[capital_horizon_months].to_numpy(dtype=float)


# ---------------------------------------------------------------------------
# 1. Nested-stochastic engine (ground truth)
# ---------------------------------------------------------------------------

@dataclass
class NestedTVOGResult:
    """Result of a full nested-stochastic capital run."""
    capital: CapitalMetrics
    outer_states: np.ndarray
    conditional_liabilities: np.ndarray   # L(x_i), one per outer node
    inner_standard_errors: np.ndarray     # SE of each L(x_i)
    n_outer: int
    n_inner: int
    total_inner_valuations: int
    run_id: str
    duration_seconds: float
    audit_entry_id: Optional[str] = None
    inner_estimator: str = "fixed"
    mlmc_diagnostics: Optional[dict] = None

    def summary(self) -> dict:
        out = {
            "capital": self.capital.summary(),
            "n_outer": self.n_outer,
            "n_inner": self.n_inner,
            "total_inner_valuations": self.total_inner_valuations,
            "mean_inner_se": round(float(self.inner_standard_errors.mean()), 6),
            "run_id": self.run_id,
            "duration_seconds": round(self.duration_seconds, 4),
        }
        # ADDITIVE: only surfaced for an opt-in MLMC run; fixed runs are
        # byte-identical to the pre-stage-3 summary (mlmc_diagnostics is None).
        if self.mlmc_diagnostics is not None:
            out["inner_estimator"] = self.inner_estimator
            out["mlmc_diagnostics"] = self.mlmc_diagnostics
        return out


class NestedStochasticTVOGEngine:
    """Brute-force nested-stochastic capital engine (the ground truth).

    Outer real-world scenarios → state ``x_i = r_H`` → fresh inner Q nest per
    node → ``L(x_i)`` → capital metrics.  Expensive but unbiased; used to
    benchmark the LSMC proxy.

    SOA ASOP 56 §3.1.3/§3.5; IA TAS M §3.2/§3.6.
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
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
        self.initial_curve = initial_curve
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
        actor: str = "NestedStochasticTVOGEngine",
        phase: str = "Phase 14: Production Residual Closure and Model Sophistication",
        inner_estimator: str = "fixed",
        mlmc_n0: int = 16,
        mlmc_M: int = 2,
        mlmc_L: int = 4,
        mlmc_n_outer_per_level: Optional[Sequence[int]] = None,
    ) -> NestedTVOGResult:
        # OPT-IN inner estimator. "fixed" (default) is the governed single-level
        # nested estimator and is byte-identical to every prior run. "mlmc"
        # additionally attaches mean-liability efficiency diagnostics (stage 3);
        # it NEVER changes the governed SCR/VaR/ES headline, which is a quantile
        # and stays fixed single-level (MLMC-as-default is owner-gated stage 5).
        if inner_estimator not in ("fixed", "mlmc"):
            raise ValueError(
                "inner_estimator must be 'fixed' or 'mlmc', got "
                + repr(inner_estimator))
        t0 = time.monotonic()
        run_id = "nested-" + uuid.uuid4().hex[:8]
        rem = self.product.term_months - self.capital_horizon_months

        outer_x = _outer_states(
            n_outer, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.initial_curve, seed,
        )
        # Deterministic per-node inner seeds derived from the master seed so the
        # whole run is reproducible (SeedSequence.spawn).
        child_seeds = np.random.SeedSequence(seed).spawn(len(outer_x))
        cond_l = np.empty(len(outer_x), dtype=float)
        inner_se = np.empty(len(outer_x), dtype=float)
        for i, x in enumerate(outer_x):
            inner_seed = int(child_seeds[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs(
                float(x), n_inner, rem, self.product, self.hw_params,
                self.capital_horizon_months, inner_seed, self.annual_qx_fn,
            )
            cond_l[i] = float(pvs.mean())
            inner_se[i] = float(pvs.std(ddof=1) / np.sqrt(n_inner)) if n_inner > 1 else 0.0

        capital = capital_metrics_from_liabilities(
            cond_l, self.confidence_level, self.capital_horizon_months
        )

        # OPT-IN MLMC mean-liability diagnostics (additive; does not alter any
        # governed figure above). Computed AFTER the governed capital so a
        # diagnostic failure can never affect the headline path.
        mlmc_diag = None
        if inner_estimator == "mlmc":
            from par_model_v2.projection.mlmc_inner_estimator import (
                engine_mean_liability_diagnostics,
            )
            mlmc_diag = engine_mean_liability_diagnostics(
                product=self.product, hw_params=self.hw_params,
                capital_horizon_months=self.capital_horizon_months,
                outer_measure=self.outer_measure,
                initial_curve=self.initial_curve,
                annual_qx_fn=self.annual_qx_fn,
                n_inner=n_inner, seed=seed,
                fixed_mean_liability=float(cond_l.mean()),
                fixed_n_outer=len(outer_x),
                n0=mlmc_n0, M=mlmc_M, L=mlmc_L,
                n_outer_per_level=mlmc_n_outer_per_level,
            )
        duration = time.monotonic() - t0

        audit_entry_id = None
        if governance_store is not None:
            from par_model_v2.governance.audit_trail import AuditEntry

            entry = AuditEntry.model_run(
                actor=actor, phase=phase, run_id=run_id,
                scenario_count=n_outer * n_inner,
                duration_seconds=round(duration, 4), outcome="PASS",
                files_changed=["par_model_v2/projection/nested_stochastic_tvog.py"],
                test_summary=(
                    "nested VaR{:.1f}%={:.2f}; ES={:.2f}; SCR_proxy={:.2f}; "
                    "N_outer={}; n_inner={}".format(
                        self.confidence_level * 100, capital.var_liability,
                        capital.es_liability, capital.scr_proxy, n_outer, n_inner)
                ),
            )
            governance_store.audit_trail.append(entry)
            audit_entry_id = entry.entry_id

        return NestedTVOGResult(
            capital=capital, outer_states=outer_x, conditional_liabilities=cond_l,
            inner_standard_errors=inner_se, n_outer=len(outer_x), n_inner=n_inner,
            total_inner_valuations=len(outer_x) * n_inner, run_id=run_id,
            duration_seconds=duration, audit_entry_id=audit_entry_id,
            inner_estimator=inner_estimator, mlmc_diagnostics=mlmc_diag,
        )


# ---------------------------------------------------------------------------
# 2. LSMC proxy engine
# ---------------------------------------------------------------------------

def _poly_basis(x: np.ndarray, degree: int) -> np.ndarray:
    """Vandermonde-style polynomial basis ``[1, x, x^2, ...]`` (degree+1 cols).

    ``x`` is expected to be centred/scaled by the caller for numerical
    conditioning; here we just raise powers.
    """
    x = np.asarray(x, dtype=float)
    return np.vander(x, N=degree + 1, increasing=True)


@dataclass
class LSMCProxyResult:
    """Result of an LSMC proxy capital run."""
    capital: CapitalMetrics
    beta: np.ndarray                  # fitted regression coefficients
    x_center: float
    x_scale: float
    degree: int
    fit_r2: float                     # in-sample R^2 on noisy fitting samples
    n_fit: int
    n_outer_eval: int
    fitted_liabilities: np.ndarray    # L_hat(x) over the evaluation outer set
    fit_states: np.ndarray
    fit_payoffs: np.ndarray
    run_id: str
    duration_seconds: float
    audit_entry_id: Optional[str] = None

    def predict(self, x) -> np.ndarray:
        xs = (np.asarray(x, dtype=float) - self.x_center) / self.x_scale
        return _poly_basis(xs, self.degree) @ self.beta

    def summary(self) -> dict:
        return {
            "capital": self.capital.summary(),
            "degree": self.degree,
            "fit_r2": round(self.fit_r2, 6),
            "n_fit": self.n_fit,
            "n_outer_eval": self.n_outer_eval,
            "beta": [round(float(b), 6) for b in self.beta],
            "run_id": self.run_id,
            "duration_seconds": round(self.duration_seconds, 4),
        }


class LSMCProxyEngine:
    """Longstaff-Schwartz least-squares Monte-Carlo capital proxy.

    Fits ``L_hat(x) = phi(x) . beta`` from ``N_fit`` noisy single-inner-path
    samples, then evaluates the surface across a large (cheap) outer set.  The
    regression averages out the single-path inner noise, recovering the
    conditional expectation at ``N_fit`` inner valuations instead of
    ``N_outer x n_inner``.

    Longstaff & Schwartz (2001); IFoA proxy-model working-party guidance.
    SOA ASOP 56 §3.5; IA TAS M §3.6.
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        initial_curve: Optional[RiskFreeCurve] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        outer_measure: Measure = Measure.P,
        degree: int = DEFAULT_LSMC_DEGREE,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        if not (0 < capital_horizon_months < product.term_months):
            raise ValueError("capital_horizon_months must satisfy 0 < H < term_months")
        if degree < 1:
            raise ValueError("LSMC polynomial degree must be >= 1")
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.initial_curve = initial_curve
        self.capital_horizon_months = int(capital_horizon_months)
        self.confidence_level = float(confidence_level)
        self.outer_measure = Measure(outer_measure)
        self.degree = int(degree)
        self.annual_qx_fn = annual_qx_fn

    def fit_and_run(
        self,
        n_fit: int = 1_000,
        n_outer_eval: int = 5_000,
        seed: int = 42,
        governance_store: Optional["GovernanceStore"] = None,
        actor: str = "LSMCProxyEngine",
        phase: str = "Phase 14: Production Residual Closure and Model Sophistication",
    ) -> LSMCProxyResult:
        t0 = time.monotonic()
        run_id = "lsmc-" + uuid.uuid4().hex[:8]
        rem = self.product.term_months - self.capital_horizon_months

        # --- fitting set: N_fit outer states, ONE inner path each -----------
        fit_x = _outer_states(
            n_fit, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.initial_curve, seed,
        )
        child_seeds = np.random.SeedSequence(seed + 1).spawn(len(fit_x))
        fit_y = np.empty(len(fit_x), dtype=float)
        for i, x in enumerate(fit_x):
            inner_seed = int(child_seeds[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs(
                float(x), 1, rem, self.product, self.hw_params,
                self.capital_horizon_months, inner_seed, self.annual_qx_fn,
            )
            fit_y[i] = float(pvs[0])

        # --- regression (centred/scaled for conditioning) -------------------
        x_center = float(fit_x.mean())
        x_scale = float(fit_x.std(ddof=0)) or 1.0
        xs = (fit_x - x_center) / x_scale
        design = _poly_basis(xs, self.degree)
        beta, _resid, _rank, _sv = np.linalg.lstsq(design, fit_y, rcond=None)
        y_hat = design @ beta
        ss_res = float(np.sum((fit_y - y_hat) ** 2))
        ss_tot = float(np.sum((fit_y - fit_y.mean()) ** 2)) or 1.0
        fit_r2 = 1.0 - ss_res / ss_tot

        # --- evaluation: large cheap outer set, fitted surface --------------
        eval_x = _outer_states(
            n_outer_eval, self.capital_horizon_months, self.outer_measure,
            self.hw_params, self.initial_curve, seed + 2,
        )
        eval_xs = (eval_x - x_center) / x_scale
        fitted_l = _poly_basis(eval_xs, self.degree) @ beta

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
                files_changed=["par_model_v2/projection/nested_stochastic_tvog.py"],
                test_summary=(
                    "LSMC VaR{:.1f}%={:.2f}; ES={:.2f}; SCR_proxy={:.2f}; "
                    "R2={:.4f}; N_fit={}; deg={}".format(
                        self.confidence_level * 100, capital.var_liability,
                        capital.es_liability, capital.scr_proxy, fit_r2,
                        n_fit, self.degree)
                ),
            )
            governance_store.audit_trail.append(entry)
            audit_entry_id = entry.entry_id

        return LSMCProxyResult(
            capital=capital, beta=beta, x_center=x_center, x_scale=x_scale,
            degree=self.degree, fit_r2=fit_r2, n_fit=len(fit_x),
            n_outer_eval=len(eval_x), fitted_liabilities=fitted_l,
            fit_states=fit_x, fit_payoffs=fit_y, run_id=run_id,
            duration_seconds=duration, audit_entry_id=audit_entry_id,
        )


# ---------------------------------------------------------------------------
# 3. Convergence & reproducibility diagnostics
# ---------------------------------------------------------------------------

@dataclass
class ConvergencePoint:
    n_inner: int
    mean_liability: float
    standard_error: float


@dataclass
class ProxyAgreement:
    max_abs_rel_error: float
    rmse: float
    r2_vs_nested: float
    grid_x: np.ndarray
    nested_l: np.ndarray
    proxy_l: np.ndarray


class NestedStochasticDiagnostics:
    """Convergence, reproducibility, and proxy-vs-nested agreement evidence.

    SOA ASOP 56 §3.5 (convergence); IA TAS M §3.6 (validation & reproducibility).
    """

    def __init__(
        self,
        product: ParEndowmentProduct,
        hw_params: Optional[HullWhiteParams] = None,
        capital_horizon_months: int = DEFAULT_CAPITAL_HORIZON_MONTHS,
        annual_qx_fn: Optional[Callable] = None,
    ) -> None:
        self.product = product
        self.hw_params = hw_params if hw_params is not None else HullWhiteParams()
        self.capital_horizon_months = int(capital_horizon_months)
        self.annual_qx_fn = annual_qx_fn

    # -- inner Monte-Carlo convergence: SE ~ 1/sqrt(n_inner) -----------------
    def inner_convergence(
        self,
        x: Optional[float] = None,
        inner_counts: Tuple[int, ...] = (64, 256, 1_024, 4_096),
        seed: int = 7,
    ) -> List[ConvergencePoint]:
        """Estimate L(x) at increasing inner counts; SE should decay ~1/sqrt(n)."""
        if x is None:
            x = self.hw_params.initial_short_rate
        rem = self.product.term_months - self.capital_horizon_months
        pts: List[ConvergencePoint] = []
        for n_inner in inner_counts:
            pvs = _inner_pathwise_pvs(
                float(x), n_inner, rem, self.product, self.hw_params,
                self.capital_horizon_months, seed, self.annual_qx_fn,
            )
            se = float(pvs.std(ddof=1) / np.sqrt(n_inner))
            pts.append(ConvergencePoint(int(n_inner), float(pvs.mean()), se))
        return pts

    @staticmethod
    def standard_error_decays(points: List[ConvergencePoint]) -> bool:
        """True iff inner standard error is monotonically non-increasing."""
        ses = [p.standard_error for p in points]
        return all(b <= a + 1e-12 for a, b in zip(ses, ses[1:]))

    # -- proxy vs nested across a deterministic state grid -------------------
    def proxy_vs_nested(
        self,
        proxy: LSMCProxyResult,
        grid: Optional[np.ndarray] = None,
        n_inner: int = 4_096,
        seed: int = 11,
    ) -> ProxyAgreement:
        """Compare the LSMC surface to high-accuracy nested L(x) on a grid."""
        if grid is None:
            lo = float(proxy.fit_states.min())
            hi = float(proxy.fit_states.max())
            grid = np.linspace(lo, hi, 9)
        rem = self.product.term_months - self.capital_horizon_months
        child = np.random.SeedSequence(seed).spawn(len(grid))
        nested = np.empty(len(grid), dtype=float)
        for i, x in enumerate(grid):
            s = int(child[i].generate_state(1)[0])
            pvs = _inner_pathwise_pvs(
                float(x), n_inner, rem, self.product, self.hw_params,
                self.capital_horizon_months, s, self.annual_qx_fn,
            )
            nested[i] = float(pvs.mean())
        proxy_l = proxy.predict(grid)
        denom = np.where(np.abs(nested) > 1e-9, np.abs(nested), 1.0)
        rel = np.abs(proxy_l - nested) / denom
        rmse = float(np.sqrt(np.mean((proxy_l - nested) ** 2)))
        ss_res = float(np.sum((nested - proxy_l) ** 2))
        ss_tot = float(np.sum((nested - nested.mean()) ** 2)) or 1.0
        return ProxyAgreement(
            max_abs_rel_error=float(rel.max()), rmse=rmse,
            r2_vs_nested=1.0 - ss_res / ss_tot, grid_x=grid,
            nested_l=nested, proxy_l=proxy_l,
        )

    # -- reproducibility: identical seed -> identical bytes ------------------
    @staticmethod
    def reproducibility_digest(arr: np.ndarray) -> str:
        """SHA-256 of a float array rounded to 1e-9 (seed-determinism check)."""
        rounded = np.round(np.asarray(arr, dtype=float), 9)
        return hashlib.sha256(rounded.tobytes()).hexdigest()


# ---------------------------------------------------------------------------
# Model-use restrictions (governance disclosure)
# ---------------------------------------------------------------------------

def model_use_restrictions() -> Dict[str, object]:
    """Structured model-use restrictions for the nested/LSMC capital proxy.

    Returned as a dict so it can be embedded in a limitation card, audit
    entry, or reporting pack.  SOA ASOP 56 §3.5.1; IA TAS M §3.6.
    """
    return {
        "module": "par_model_v2/projection/nested_stochastic_tvog.py",
        "classification": "EDUCATIONAL ONLY — NOT a regulatory capital model",
        "single_risk_driver": (
            "Capital tail is driven by the short rate at the horizon only. "
            "Equity, lapse, credit-spread, and FX risks are NOT in the tail; "
            "the figure is a one-factor educational proxy."
        ),
        "placeholder_parameters": (
            "capital magnitudes are illustrative, not calibrated."
        ),
        "lsmc_extrapolation": (
            "The polynomial surface L_hat(x) is valid only across the fitted "
            "state range [min(fit_states), max(fit_states)]. Extrapolation "
            "beyond it is unsupported and may be unstable at high degree."
        ),
        "convergence_requirements": (
            "Inner standard error decays ~1/sqrt(n_inner); 99.5% capital "
            "requires N_outer >= {} (ASOP 56 §3.5). Diagnostics must be run "
            "and reviewed before any figure is cited.".format(CAPITAL_OUTER_MINIMUM)
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
        ],
    }


def model_use_restrictions_json() -> str:
    return json.dumps(model_use_restrictions(), indent=2, sort_keys=True)


__all__ = [
    "DEFAULT_CAPITAL_HORIZON_MONTHS",
    "DEFAULT_CONFIDENCE_LEVEL",
    "CAPITAL_OUTER_MINIMUM",
    "DEFAULT_LSMC_DEGREE",
    "CapitalMetrics",
    "capital_metrics_from_liabilities",
    "NestedTVOGResult",
    "NestedStochasticTVOGEngine",
    "LSMCProxyResult",
    "LSMCProxyEngine",
    "ConvergencePoint",
    "ProxyAgreement",
    "NestedStochasticDiagnostics",
    "model_use_restrictions",
    "model_use_restrictions_json",
    "_residual_guaranteed_pv",
    "_residual_cashflow_vector",
    "_vectorised_discount_factors",
    "_inner_pathwise_pvs",
]
