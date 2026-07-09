"""
Dynamic Lapse Model — Interest-Rate-Dependent Policyholder Behaviour
=====================================================================

Phase 13 Task 2 (production gates **G-04** and **G-11**).

The legacy projection engine used a *static* duration-only lapse table
(``_base_annual_lapse``).  Static lapse cannot capture the single most
material policyholder-behaviour driver for Hong Kong participating (PAR)
endowment business: the incentive to surrender when prevailing market
rates rise above the rate effectively credited to the policy.  While lapse
is static, TVOG lapse sensitivity is FLAT — an artefact of the design, not
evidence the risk is immaterial (Deployment Readiness G-04, MR-003).

This module implements a calibrated **dynamic lapse function** blending the
three functional forms named in the G-04 design note:

* **Option C — duration base.**  Declining duration-dependent base lapse,
  identical to the legacy static schedule, so the dynamic model reduces
  to approximately the legacy behaviour (within a small baseline
  mass-lapse term) when market = credited rate.
* **Option A — policyholder efficiency.**  Bounded ``arctan`` multiplier on
  the base rate: in-the-money guarantee (market < credited) lowers lapse;
  out-of-the-money (market > credited) raises it.
* **Option B — rate-induced mass / shock lapse.**  Smooth logistic term
  adding shock lapses once the market-over-credited spread breaches a
  threshold (CBIRC C-ROSS mass-lapse driver).

Functional form
---------------
Let ``s = market_rate - credited_rate`` (annualised; ``s > 0`` ⇒ outside
option more attractive ⇒ higher lapse).

    base(t)     = duration-dependent base annual lapse                 [Opt C]
    mult(s)     = 1 + beta * (2/pi) * arctan(s / kappa)                [Opt A]
                  (bounded in (1 - beta, 1 + beta))
    shock(s)    = shock_max / (1 + exp(-(s - tau) / width))            [Opt B]
    lapse(t, s) = clip(base(t) * mult(s) + shock(s), floor, cap)

At ``s = 0``: ``mult = 1`` and (for ``tau > 0``) ``shock ≈ 0``, so
``lapse(t, 0) ≈ base(t)`` — backward compatible.

Calibration (G-11)
------------------
``calibrate_dynamic_lapse`` fits ``(beta, kappa, shock_max, tau)`` by
exposure-weighted non-linear least squares to a synthetic Hong Kong PAR
experience study (:func:`build_hk_par_experience_study`).  ``width`` is held
fixed for identifiability.  Diagnostics (RMSE, R², residuals) accompany the
fitted assumption.

Standards
---------
SOA ASOP 7  §3.3   — modelling behaviour responsive to economic conditions
SOA ASOP 25 §3.3   — credibility hierarchy for the experience basis
SOA ASOP 56 §3.1   — assumption documentation / dynamic-behaviour basis
IA TAS M    §3.5    — assumption appropriateness and sign-off
IA TAS M    §3.6    — traceability: experience → parameter → output
IFoA APS X2 §4.2    — independent review of material assumption changes

PRODUCTION USE RESTRICTION
--------------------------
The experience study here is *synthetic / educational*.  Before regulatory
or pricing use, replace :func:`build_hk_par_experience_study` with a credible
HK PAR lapse experience study and re-run calibration and sign-off.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:  # SciPy is optional; a deterministic fallback optimiser is provided.
    from scipy.optimize import least_squares  # type: ignore

    _HAVE_SCIPY = True
except Exception:  # pragma: no cover - exercised only on minimal installs
    _HAVE_SCIPY = False


# ---------------------------------------------------------------------------
# 1. Duration base schedule (Option C) — matches legacy static table
# ---------------------------------------------------------------------------

def base_annual_lapse(policy_year: int) -> float:
    """Duration-dependent base annual lapse (legacy static schedule).

    Identical to ``monthly_projection._base_annual_lapse``; with no rate
    stress the dynamic model closely reproduces the prior results (exactly
    when the baseline mass-lapse term is negligible).
    """
    if policy_year <= 1:
        return 0.12
    elif policy_year == 2:
        return 0.09
    elif policy_year == 3:
        return 0.07
    elif policy_year <= 5:
        return 0.05
    elif policy_year <= 10:
        return 0.03
    else:
        return 0.015


# ---------------------------------------------------------------------------
# 2. Dynamic lapse assumption
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DynamicLapseAssumption:
    """Calibrated dynamic-lapse parameters and evaluation methods.

    Parameters
    ----------
    credited_rate :
        Baseline rate effectively credited to the policy (guaranteed +
        expected reversionary support); default reference for the spread.
    beta :
        Efficiency sensitivity (Option A); bounds the multiplier within
        ``(1 - beta, 1 + beta)``.  Must be in ``[0, 1)``.
    kappa :
        Spread scale (annualised) controlling response speed; smaller ⇒
        sharper.
    shock_max :
        Maximum additive mass-lapse rate (Option B) at very large spreads.
    tau :
        Spread threshold (annualised) at which the mass-lapse logistic is at
        half of ``shock_max``.
    width :
        Logistic width of the mass-lapse transition (annualised).
    lapse_floor, lapse_cap :
        Hard clamps on the resulting annual lapse rate.
    """

    credited_rate: float = 0.025
    beta: float = 0.55
    kappa: float = 0.020
    shock_max: float = 0.18
    tau: float = 0.030
    width: float = 0.010
    lapse_floor: float = 0.0
    lapse_cap: float = 1.0

    methodology: str = (
        "Blended duration base (Opt C) x bounded arctan efficiency "
        "multiplier (Opt A) + logistic rate-induced mass lapse (Opt B)"
    )
    calibration_basis: str = "Synthetic HK PAR endowment lapse experience study"
    calibration_date: str = field(default_factory=lambda: date.today().isoformat())
    standard_references: Tuple[str, ...] = (
        "SOA ASOP 7 §3.3", "SOA ASOP 25 §3.3", "SOA ASOP 56 §3.1",
        "IA TAS M §3.5", "IA TAS M §3.6", "IFoA APS X2 §4.2",
    )

    # -- validation ----------------------------------------------------------
    def __post_init__(self) -> None:
        if not (0.0 <= self.beta < 1.0):
            raise ValueError(f"beta must be in [0, 1); got {self.beta}")
        if self.kappa <= 0:
            raise ValueError(f"kappa must be > 0; got {self.kappa}")
        if self.width <= 0:
            raise ValueError(f"width must be > 0; got {self.width}")
        if self.shock_max < 0:
            raise ValueError(f"shock_max must be >= 0; got {self.shock_max}")
        if not (0.0 <= self.lapse_floor <= self.lapse_cap <= 1.0):
            raise ValueError(
                "require 0 <= lapse_floor <= lapse_cap <= 1; got "
                f"floor={self.lapse_floor}, cap={self.lapse_cap}"
            )

    # -- components ----------------------------------------------------------
    def efficiency_multiplier(self, spread: float) -> float:
        """Option A bounded arctan multiplier on the base rate."""
        return 1.0 + self.beta * (2.0 / math.pi) * math.atan(spread / self.kappa)

    def mass_lapse(self, spread: float) -> float:
        """Option B logistic rate-induced mass / shock lapse term."""
        z = -(spread - self.tau) / self.width
        if z > 50.0:
            return 0.0
        if z < -50.0:
            return self.shock_max
        return self.shock_max / (1.0 + math.exp(z))

    def annual_rate(
        self,
        policy_year: int,
        market_rate: float,
        credited_rate: Optional[float] = None,
        base_fn: Callable[[int], float] = base_annual_lapse,
    ) -> float:
        """Dynamic annual lapse rate for ``policy_year`` at ``market_rate``.

        Accepts economic inputs (rate level and in-force duration), per
        G-04 verification criterion 1.
        """
        cr = self.credited_rate if credited_rate is None else credited_rate
        spread = market_rate - cr
        base = base_fn(policy_year)
        raw = base * self.efficiency_multiplier(spread) + self.mass_lapse(spread)
        return float(min(max(raw, self.lapse_floor), self.lapse_cap))

    # -- marginal response / bounded elasticity (roadmap §4.1 #4, MR-003) -----
    def efficiency_multiplier_slope(self, spread: float) -> float:
        """``d/ds`` of the Option-A arctan multiplier ``mult(s)``.

        ``mult'(s) = beta * (2/pi) * (1/kappa) / (1 + (s/kappa)**2)`` — strictly
        positive, maximised at ``s = 0`` where it equals ``beta*2/(pi*kappa)``.
        """
        x = spread / self.kappa
        return self.beta * (2.0 / math.pi) * (1.0 / self.kappa) / (1.0 + x * x)

    def mass_lapse_slope(self, spread: float) -> float:
        """``d/ds`` of the Option-B logistic mass-lapse term ``shock(s)``.

        ``shock'(s) = shock_max * sig*(1-sig) / width`` with
        ``sig = logistic((s-tau)/width)`` — positive, maximised at ``s = tau``
        where it equals ``shock_max/(4*width)``.
        """
        z = (spread - self.tau) / self.width
        if z > 50.0 or z < -50.0:
            return 0.0
        sig = 1.0 / (1.0 + math.exp(-z))
        return self.shock_max * sig * (1.0 - sig) / self.width

    def marginal_response(
        self,
        spread: float,
        base: Optional[float] = None,
        policy_year: int = 1,
        base_fn: Callable[[int], float] = base_annual_lapse,
    ) -> float:
        """Analytic ``d lapse / d spread`` — the marginal lapse response.

        Derivative of the *pre-clip* lapse ``base*mult(s) + shock(s)`` w.r.t. the
        rate differential ``s = market_rate - credited_rate``.  The clip only
        flattens the curve, so this is also an upper bound on the derivative of
        the clipped rate.  Always ``>= 0`` (lapse rises with the spread).
        """
        b = base_fn(policy_year) if base is None else base
        return b * self.efficiency_multiplier_slope(spread) + self.mass_lapse_slope(spread)

    def marginal_response_bound(
        self,
        base: Optional[float] = None,
        base_fn: Callable[[int], float] = base_annual_lapse,
    ) -> float:
        """Closed-form Lipschitz bound on ``marginal_response`` over all spreads.

        ``sup_s (d lapse/ds) = base * beta*2/(pi*kappa) + shock_max/(4*width)``
        (the arctan slope peaks at ``s=0``; the logistic slope peaks at
        ``s=tau``).  A finite bound proves the rate-differential lapse response
        has **bounded elasticity**: lapse cannot react arbitrarily fast to a
        rate move — a well-posedness requirement for a dynamic-lapse assumption
        (SOA ASOP 7 §3.3; IA TAS M §3.5).  ``base`` defaults to the year-1
        (largest) base lapse so the returned bound is global across durations.
        """
        b = base_fn(1) if base is None else base
        return b * self.beta * (2.0 / math.pi) / self.kappa + self.shock_max / (4.0 * self.width)

    def semi_elasticity(
        self,
        spread: float,
        policy_year: int = 1,
        base_fn: Callable[[int], float] = base_annual_lapse,
    ) -> float:
        """Semi-elasticity ``d ln(lapse) / d spread`` at ``spread``.

        Fractional change in the annual lapse rate per unit change in the rate
        differential (a per-bp figure is this value ``* 1e-4``).  Uses the
        pre-clip lapse in the denominator; returns ``0.0`` where lapse is 0.
        """
        base = base_fn(policy_year)
        lapse_pre = base * self.efficiency_multiplier(spread) + self.mass_lapse(spread)
        if lapse_pre <= 0.0:
            return 0.0
        return self.marginal_response(spread, base=base) / lapse_pre

    def to_dict(self) -> Dict[str, object]:
        d = asdict(self)
        d["standard_references"] = list(self.standard_references)
        return d


def default_hk_par_dynamic_lapse(credited_rate: float = 0.025) -> DynamicLapseAssumption:
    """Pre-calibrated default dynamic-lapse assumption for HK PAR endowments."""
    return DynamicLapseAssumption(credited_rate=credited_rate)


# ---------------------------------------------------------------------------
# 3. Synthetic HK PAR experience study (calibration target, G-11)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LapseExperiencePoint:
    """One observed cell of a lapse experience study."""

    policy_year: int
    market_rate: float
    credited_rate: float
    observed_annual_lapse: float
    exposure_years: float = 1000.0  # credibility weight (policy-years)

    @property
    def spread(self) -> float:
        return self.market_rate - self.credited_rate


def build_hk_par_experience_study(
    credited_rate: float = 0.025,
) -> List[LapseExperiencePoint]:
    """Deterministic synthetic HK PAR endowment lapse experience study.

    Cells span early/mid/late durations and a grid of market-rate
    environments around the credited rate.  Observed rates encode three
    stylised facts the dynamic model must reproduce:

    1. Lapse declines with duration (surrender-charge run-off, inertia).
    2. Lapse rises smoothly as market rate exceeds credited (efficiency).
    3. A super-linear "mass lapse" jump once the spread is large.

    Educational only.
    """
    base_by_year = {1: 0.12, 2: 0.09, 3: 0.07, 4: 0.05, 7: 0.03, 12: 0.015}
    spreads = [-0.020, -0.010, 0.0, 0.010, 0.020, 0.030, 0.040, 0.050]

    gen_beta, gen_kappa = 0.55, 0.020
    gen_shock, gen_tau, gen_width = 0.18, 0.030, 0.010

    pts: List[LapseExperiencePoint] = []
    for year, base in base_by_year.items():
        for s in spreads:
            mult = 1.0 + gen_beta * (2.0 / math.pi) * math.atan(s / gen_kappa)
            shock = gen_shock / (1.0 + math.exp(-(s - gen_tau) / gen_width))
            obs = base * mult + shock
            # Deterministic experience "noise" (not random — reproducible).
            obs *= 1.0 + 0.01 * math.cos(7.0 * s + 0.3 * year)
            obs = min(max(obs, 0.0), 1.0)
            expo = 1000.0 * math.exp(-abs(s) * 6.0)
            pts.append(
                LapseExperiencePoint(
                    policy_year=year,
                    market_rate=credited_rate + s,
                    credited_rate=credited_rate,
                    observed_annual_lapse=round(obs, 6),
                    exposure_years=round(expo, 2),
                )
            )
    return pts


# ---------------------------------------------------------------------------
# 4. Calibration (G-11)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LapseCalibrationDiagnostics:
    """Goodness-of-fit and provenance for a dynamic-lapse calibration."""

    n_points: int
    rmse: float
    weighted_rmse: float
    r_squared: float
    max_abs_residual: float
    fitted_params: Dict[str, float]
    optimizer: str
    converged: bool
    calibration_date: str
    experience_basis: str
    standard_references: Tuple[str, ...] = (
        "SOA ASOP 25 §3.3", "IA TAS M §3.5", "IA TAS M §3.6",
    )

    def to_dict(self) -> Dict[str, object]:
        d = asdict(self)
        d["standard_references"] = list(self.standard_references)
        return d


def _predict(params: Sequence[float], years, spreads, bases) -> np.ndarray:
    beta, kappa, shock_max, tau = params
    width = 0.010  # fixed for identifiability
    mult = 1.0 + beta * (2.0 / math.pi) * np.arctan(spreads / kappa)
    z = -(spreads - tau) / width
    z = np.clip(z, -50.0, 50.0)
    shock = shock_max / (1.0 + np.exp(z))
    return np.clip(bases * mult + shock, 0.0, 1.0)


def calibrate_dynamic_lapse(
    experience: Optional[Sequence[LapseExperiencePoint]] = None,
    credited_rate: float = 0.025,
    base_fn: Callable[[int], float] = base_annual_lapse,
) -> Tuple[DynamicLapseAssumption, LapseCalibrationDiagnostics]:
    """Fit a :class:`DynamicLapseAssumption` to a lapse experience study.

    Fits ``(beta, kappa, shock_max, tau)`` by exposure-weighted non-linear
    least squares (SciPy ``least_squares`` when available; else a
    deterministic coordinate-descent fallback).  ``width`` held fixed.
    """
    if experience is None:
        experience = build_hk_par_experience_study(credited_rate)

    years = np.array([p.policy_year for p in experience], dtype=float)
    spreads = np.array([p.spread for p in experience], dtype=float)
    obs = np.array([p.observed_annual_lapse for p in experience], dtype=float)
    expo = np.array([p.exposure_years for p in experience], dtype=float)
    bases = np.array([base_fn(int(y)) for y in years], dtype=float)
    w = np.sqrt(expo / expo.sum())

    p0 = np.array([0.40, 0.025, 0.15, 0.035])
    lo = np.array([0.0, 1e-3, 0.0, 0.0])
    hi = np.array([0.99, 0.20, 0.60, 0.10])

    if _HAVE_SCIPY:
        def resid(p):
            return w * (_predict(p, years, spreads, bases) - obs)

        sol = least_squares(resid, p0, bounds=(lo, hi), method="trf", max_nfev=5000)
        params = sol.x
        optimizer = "scipy.optimize.least_squares (trf)"
        converged = bool(sol.success)
    else:  # pragma: no cover - minimal-install fallback
        params = p0.copy()
        optimizer = "coordinate-descent fallback"
        converged = True
        for _ in range(200):
            for j in range(len(params)):
                grid = np.linspace(lo[j], hi[j], 41)
                best, best_sse = params[j], np.inf
                for g in grid:
                    trial = params.copy()
                    trial[j] = g
                    sse = float(np.sum((w * (_predict(trial, years, spreads, bases) - obs)) ** 2))
                    if sse < best_sse:
                        best_sse, best = sse, g
                params[j] = best

    pred = _predict(params, years, spreads, bases)
    resid_unw = pred - obs
    rmse = float(np.sqrt(np.mean(resid_unw ** 2)))
    wrmse = float(np.sqrt(np.sum((w * resid_unw) ** 2)))
    ss_res = float(np.sum(resid_unw ** 2))
    ss_tot = float(np.sum((obs - obs.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    beta, kappa, shock_max, tau = (float(x) for x in params)
    assumption = DynamicLapseAssumption(
        credited_rate=credited_rate,
        beta=beta,
        kappa=kappa,
        shock_max=shock_max,
        tau=tau,
        width=0.010,
        calibration_basis="Synthetic HK PAR endowment lapse experience study",
    )
    diag = LapseCalibrationDiagnostics(
        n_points=len(experience),
        rmse=rmse,
        weighted_rmse=wrmse,
        r_squared=r2,
        max_abs_residual=float(np.max(np.abs(resid_unw))),
        fitted_params={"beta": beta, "kappa": kappa, "shock_max": shock_max,
                       "tau": tau, "width": 0.010},
        optimizer=optimizer,
        converged=converged,
        calibration_date=datetime.now(timezone.utc).isoformat(),
        experience_basis="Synthetic HK PAR endowment lapse experience study",
    )
    return assumption, diag


__all__ = [
    "base_annual_lapse",
    "DynamicLapseAssumption",
    "default_hk_par_dynamic_lapse",
    "LapseExperiencePoint",
    "build_hk_par_experience_study",
    "LapseCalibrationDiagnostics",
    "calibrate_dynamic_lapse",
]
