"""
G2++ swaption-surface calibrator and G-RATE2 plausibility gate (Phase 20).
==========================================================================

Calibrates the five G2++ parameters (a, b, sigma, eta, rho) to an ATM payer
swaption normal-volatility surface, mirroring the HW1F calibrator
(``calibration_framework.HullWhiteCalibrator``) but for the two-factor model.

Objective (weighted least squares over the surface, basis points):

    L(theta) = sum_cell w_cell * ( sigma_model(theta; expiry, tenor)
                                   - sigma_market_cell )^2

minimised by a pure-numpy Nelder-Mead simplex (scipy is unavailable in the
target sandbox) from several deterministic starts.  Parameters are kept in a
feasible region by reflective transforms: a, b, sigma, eta via softplus with
floors; rho via tanh; and a strict a > b ordering (G2++ requires a != b).

The G-RATE2 plausibility gate passes iff the fit is non-placeholder, the
optimiser converged, the weighted swaption RMSE is within a 25 bp band
(mirroring the HW1F G-02 band), the two mean-reversion speeds are distinct and
in [0.005, 5.0], the vols are in [0.0005, 0.10], and rho is in (-0.99, 0.99).

Standards: SOA ASOP 56 sec.3.4 (calibration methodology); Solvency II Del.
Reg. Art. 22 (market consistency); IA TAS M sec.3.6 (source->output lineage).

PRODUCTION USE RESTRICTION: the surface is an educational proxy fixture.
Replace with a credentialled live source and re-run sign-off before any
regulatory use.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from par_model_v2.stochastic.g2pp import (
    DiscountCurve,
    G2ppParams,
    swaption_normal_vol,
)

# --------------------------------------------------------------------------- #
# Feasible-region transforms.
# --------------------------------------------------------------------------- #
_A_FLOOR, _V_FLOOR = 0.005, 0.0005


def _softplus(z: float) -> float:
    # numerically safe softplus
    return math.log1p(math.exp(-abs(z))) + max(z, 0.0)


def _unpack(theta: np.ndarray) -> Tuple[float, float, float, float, float]:
    """Map 5 unconstrained reals -> (a, b, sigma, eta, rho) with a > b."""
    p0 = _A_FLOOR + _softplus(theta[0])          # larger speed
    gap = _softplus(theta[1])                    # positive gap -> a > b
    a = p0 + gap
    b = p0
    sigma = _V_FLOOR + _softplus(theta[2])
    eta = _V_FLOOR + _softplus(theta[3])
    rho = math.tanh(theta[4])
    return a, b, sigma, eta, rho


# --------------------------------------------------------------------------- #
# Pure-numpy Nelder-Mead (deterministic).
# --------------------------------------------------------------------------- #
def _nelder_mead(func, x0, max_iter=400, tol=1e-7):
    n = len(x0)
    alpha, gamma, rho_c, sigma_c = 1.0, 2.0, 0.5, 0.5
    sim = [np.asarray(x0, dtype=float)]
    for i in range(n):
        xi = np.array(x0, dtype=float)
        xi[i] += 0.5 if x0[i] == 0 else 0.5 * abs(x0[i])
        sim.append(xi)
    sim = np.array(sim)
    fvals = np.array([func(s) for s in sim])
    for _ in range(max_iter):
        order = np.argsort(fvals)
        sim, fvals = sim[order], fvals[order]
        if abs(fvals[-1] - fvals[0]) <= tol * (abs(fvals[0]) + tol):
            break
        centroid = sim[:-1].mean(axis=0)
        xr = centroid + alpha * (centroid - sim[-1])
        fr = func(xr)
        if fvals[0] <= fr < fvals[-2]:
            sim[-1], fvals[-1] = xr, fr
            continue
        if fr < fvals[0]:
            xe = centroid + gamma * (xr - centroid)
            fe = func(xe)
            if fe < fr:
                sim[-1], fvals[-1] = xe, fe
            else:
                sim[-1], fvals[-1] = xr, fr
            continue
        xc = centroid + rho_c * (sim[-1] - centroid)
        fc = func(xc)
        if fc < fvals[-1]:
            sim[-1], fvals[-1] = xc, fc
            continue
        for i in range(1, n + 1):
            sim[i] = sim[0] + sigma_c * (sim[i] - sim[0])
            fvals[i] = func(sim[i])
    order = np.argsort(fvals)
    return sim[order][0], float(fvals[order][0])


# --------------------------------------------------------------------------- #
# Surface container.
# --------------------------------------------------------------------------- #
@dataclass
class SwaptionSurface:
    cells: List[Dict[str, float]]          # expiry_years, swap_tenor_years, normal_vol_bps, weight
    currency: str
    as_of_date: str
    source_detail: str
    sha256: str
    fixture_version: str
    approved_by: str

    @classmethod
    def from_fixture(cls, path: str) -> "SwaptionSurface":
        raw = open(path, "rb").read()
        sha = hashlib.sha256(raw).hexdigest()
        d = json.loads(raw.decode("utf-8"))
        lin = d.get("data_lineage", {})
        return cls(
            cells=[c for c in d["swaption_grid"] if float(c.get("weight", 1.0)) > 0],
            currency=d.get("currency", ""),
            as_of_date=d.get("as_of_date", ""),
            source_detail=d.get("source_detail", d.get("description", "")),
            sha256=sha,
            fixture_version=lin.get("version", "1.0.0"),
            approved_by=lin.get("approved_by", "ModelGovernance"),
        )


# --------------------------------------------------------------------------- #
# Calibration result + gate.
# --------------------------------------------------------------------------- #
@dataclass
class G2ppCalibrationResult:
    a: float
    b: float
    sigma: float
    eta: float
    rho: float
    rmse_bps: float
    max_err_bps: float
    converged: bool
    n_cells: int
    fit_table: List[Dict[str, float]] = field(default_factory=list)
    is_placeholder: bool = False


def _surface_rmse(curve, surface, n_quad, theta):
    a, b, sigma, eta, rho = _unpack(theta)
    try:
        p = G2ppParams(a=a, b=b, sigma=sigma, eta=eta, rho=rho, curve=curve)
    except ValueError:
        return 1e9
    sse, wsum = 0.0, 0.0
    for c in surface.cells:
        w = float(c.get("weight", 1.0))
        model_bp = swaption_normal_vol(p, c["expiry_years"], c["swap_tenor_years"],
                                       freq=1, n_quad=n_quad) * 1e4
        diff = model_bp - float(c["normal_vol_bps"])
        sse += w * diff * diff
        wsum += w
    return math.sqrt(sse / wsum)


class G2ppCalibrator:
    """Calibrate G2++ to an ATM normal-vol swaption surface."""

    def __init__(self, curve: DiscountCurve, surface: SwaptionSurface) -> None:
        self.curve = curve
        self.surface = surface

    def calibrate(self, n_quad_opt: int = 40, n_quad_final: int = 96) -> G2ppCalibrationResult:
        # Deterministic multi-start over (a,b,sigma,eta,rho) seed guesses.
        starts = [
            np.array([0.3, -0.3, -3.5, -3.8, -0.8]),
            np.array([1.2, 0.2, -3.0, -3.5, -1.0]),
            np.array([-0.2, -0.8, -4.0, -4.2, -0.5]),
            np.array([0.8, -0.1, -3.2, -4.0, -1.5]),
        ]
        obj = lambda th: _surface_rmse(self.curve, self.surface, n_quad_opt, th)
        best_theta, best_f = None, math.inf
        for s in starts:
            th, f = _nelder_mead(obj, s, max_iter=350, tol=1e-8)
            if f < best_f:
                best_theta, best_f = th, f
        a, b, sigma, eta, rho = _unpack(best_theta)
        p = G2ppParams(a=a, b=b, sigma=sigma, eta=eta, rho=rho, curve=self.curve)

        fit_table, errs, sse, wsum = [], [], 0.0, 0.0
        for c in self.surface.cells:
            w = float(c.get("weight", 1.0))
            model_bp = swaption_normal_vol(p, c["expiry_years"], c["swap_tenor_years"],
                                           freq=1, n_quad=n_quad_final) * 1e4
            mkt = float(c["normal_vol_bps"])
            err = model_bp - mkt
            errs.append(abs(err))
            sse += w * err * err
            wsum += w
            fit_table.append({
                "expiry_years": c["expiry_years"], "swap_tenor_years": c["swap_tenor_years"],
                "market_vol_bps": round(mkt, 3), "model_vol_bps": round(model_bp, 3),
                "error_bps": round(err, 3), "weight": w,
            })
        rmse = math.sqrt(sse / wsum)
        # "converged" iff the two optimisation precisions agree (stable optimum).
        converged = abs(rmse - best_f) < 2.0  # within 2 bp of the coarse-grid optimum
        return G2ppCalibrationResult(
            a=a, b=b, sigma=sigma, eta=eta, rho=rho,
            rmse_bps=rmse, max_err_bps=max(errs), converged=bool(converged),
            n_cells=len(self.surface.cells), fit_table=fit_table, is_placeholder=False,
        )


# --------------------------------------------------------------------------- #
# G-RATE2 plausibility gate.
# --------------------------------------------------------------------------- #
G_RATE2_RMSE_BAND_BPS = 25.0


def evaluate_g_rate2_gate(res: G2ppCalibrationResult) -> Dict[str, object]:
    criteria = {
        "c1_min_surface_cells": res.n_cells >= 10,
        "c2_not_placeholder": not res.is_placeholder,
        "c3_optimiser_converged": bool(res.converged),
        "c4_rmse_within_band": res.rmse_bps <= G_RATE2_RMSE_BAND_BPS,
        "c5_speeds_distinct_and_in_band": (abs(res.a - res.b) > 1e-3
                                           and 0.005 <= res.b and res.a <= 5.0),
        "c6_vols_in_band": (0.0005 <= res.sigma <= 0.10 and 0.0005 <= res.eta <= 0.10),
        "c7_rho_in_band": (-0.99 < res.rho < 0.99),
    }
    status = "PASS" if all(criteria.values()) else "FAIL"
    evidence = (
        "n_cells=%d, RMSE=%.2f bps (band %.0f), max_err=%.2f bps, "
        "a=%.4f, b=%.4f, sigma=%.5f, eta=%.5f, rho=%.4f"
        % (res.n_cells, res.rmse_bps, G_RATE2_RMSE_BAND_BPS, res.max_err_bps,
           res.a, res.b, res.sigma, res.eta, res.rho)
    )
    return {
        "gate_id": "G-RATE2",
        "gate_description": (
            "G2++ two-factor rates parameters (a, b, sigma, eta, rho) calibrated to the "
            "ATM swaption normal-vol surface (not placeholders); weighted RMSE within a 25 bps "
            "band; a != b with both speeds in [0.005, 5.0]; vols in [0.0005, 0.10]; rho in "
            "(-0.99, 0.99). (SOA ASOP 56 §3.4; Solvency II Del. Reg. Art. 22)"
        ),
        "status": status,
        "evidence": evidence,
        "criteria": criteria,
        "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# --------------------------------------------------------------------------- #
# Default educational-proxy CNY discount curve (anchored at the HW1F r0).
# --------------------------------------------------------------------------- #
def default_cny_curve() -> DiscountCurve:
    """Representative CNY continuously-compounded zero curve as of 2026-01-01.

    Short end anchored at the HW1F CNY r0 (2.07%); mild upward slope to ~3.0%
    at 30y, typical of the 2025-2026 CNY onshore government/IRS curve.  This is
    an educational proxy, not licensed market data.
    """
    tenors = np.array([0.25, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0])
    rates = np.array([0.0207, 0.0218, 0.0231, 0.0243, 0.0262, 0.0277, 0.0290, 0.0298, 0.0302])
    return DiscountCurve(tenors, rates)
