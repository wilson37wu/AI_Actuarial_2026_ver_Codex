"""
calibrate_credit.py — Credit Spread Calibration
================================================

Demonstrates credit spread calibration for the Phase 9 asset library:
  - Investment-grade (IG) and high-yield (HY) corporate bond OAS curves
  - Private credit illiquidity premium estimation
  - Private equity / infrastructure expected return assumptions

All market data is synthetic and illustrative. In production, replace with
data from an approved credit analytics provider (e.g., ICE BofA OAS indices,
Bloomberg BVAL spreads) reviewed by the Assumption Owner.

Standards Addressed
-------------------
SOA ASOP 56 §3.4   — calibration methodology documentation
ERM framework      — credit risk factor calibration and stress testing
IA TAS M §3.5      — assumption appropriateness sign-off
docs/ASSET_CLASS_STRESS_TESTS_AND_GOVERNANCE.md — governance notes

Usage
-----
    python scripts/calibration/calibrate_credit.py
    python scripts/calibration/calibrate_credit.py --output outputs/credit_calibration.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import optimize as scipy_optimize

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

VALUATION_DATE = date(2026, 5, 30)

# ---------------------------------------------------------------------------
# 1.  Credit Spread Market Data (synthetic/illustrative)
# ---------------------------------------------------------------------------
# OAS (Option-Adjusted Spread) in basis points, vs. USD Treasury curve.
# Tenors: 1y, 2y, 3y, 5y, 7y, 10y, 15y, 20y, 30y

_IG_SPREAD_GRID: Dict[str, Dict[str, List]] = {
    # Rating : {tenor: OAS bps}
    "AAA": {
        "tenors": [1, 2, 3, 5, 7, 10, 15, 20, 30],
        "oas_bps": [18, 22, 26, 32, 36, 40, 44, 46, 48],
    },
    "AA": {
        "tenors": [1, 2, 3, 5, 7, 10, 15, 20, 30],
        "oas_bps": [28, 34, 40, 50, 57, 63, 68, 72, 76],
    },
    "A": {
        "tenors": [1, 2, 3, 5, 7, 10, 15, 20, 30],
        "oas_bps": [45, 55, 65, 80, 92, 103, 112, 118, 122],
    },
    "BBB": {
        "tenors": [1, 2, 3, 5, 7, 10, 15, 20, 30],
        "oas_bps": [90, 110, 130, 160, 182, 202, 222, 232, 240],
    },
}

_HY_SPREAD_GRID: Dict[str, Dict[str, List]] = {
    "BB": {
        "tenors": [1, 2, 3, 5, 7, 10],
        "oas_bps": [210, 250, 290, 350, 390, 420],
    },
    "B": {
        "tenors": [1, 2, 3, 5, 7, 10],
        "oas_bps": [380, 450, 520, 620, 690, 750],
    },
    "CCC": {
        "tenors": [1, 2, 3, 5],
        "oas_bps": [800, 950, 1100, 1250],
    },
}

# Private asset illiquidity premium assumptions (basis points, annualised)
# = total expected return above equivalent-duration public market
_PRIVATE_ASSET_ASSUMPTIONS: Dict[str, dict] = {
    "private_credit_senior": {
        "description": "Senior secured direct lending; floating rate",
        "typical_all_in_spread_bps": 550,         # SOFR + 550 bps illustrative
        "public_IG_equivalent_oas_bps": 200,       # BBB 5y proxy
        "illiquidity_premium_bps": 150,            # 350 - 200 (net of structuring)
        "expected_loss_bps": 80,                   # annual expected loss (PD x LGD)
        "net_credit_spread_bps": 270,              # all-in - losses - il. premium
        "duration_years": 3.5,                     # typical direct lending
        "recovery_rate": 0.65,
        "default_probability_annual": 0.022,
    },
    "private_credit_mezzanine": {
        "description": "Mezzanine / unitranche",
        "typical_all_in_spread_bps": 900,
        "public_HY_equivalent_oas_bps": 500,
        "illiquidity_premium_bps": 175,
        "expected_loss_bps": 200,
        "net_credit_spread_bps": 225,
        "duration_years": 4.0,
        "recovery_rate": 0.45,
        "default_probability_annual": 0.045,
    },
    "private_equity": {
        "description": "Diversified PE fund (buyout); total return basis",
        "expected_total_return_pct": 12.5,         # IRR target, illustrative
        "public_equity_return_pct": 8.5,           # US large-cap total return
        "illiquidity_premium_pct": 2.5,            # 12.5 - 8.5 - 1.5 fee drag
        "fee_drag_pct": 1.5,
        "j_curve_years": 3,
        "typical_fund_life_years": 10,
        "pmulti_expected": 2.0,                    # expected gross MOIC
    },
    "infrastructure": {
        "description": "Core infrastructure (greenfield + brownfield blend)",
        "expected_total_return_pct": 8.5,
        "inflation_linkage_pct": 0.70,             # 70% of CPI pass-through
        "real_return_pct": 5.5,
        "illiquidity_premium_pct": 1.8,
        "public_infra_proxy_return_pct": 6.5,
        "typical_fund_life_years": 15,
    },
}


# ---------------------------------------------------------------------------
# 2.  Nelson-Siegel Spread Curve Fitting
# ---------------------------------------------------------------------------
# Fit Nelson-Siegel model to OAS grid: OAS(T) = b0 + b1*(1-e^(-T/tau))/((T/tau)) + b2*(same - e^(-T/tau))
# This gives a smooth spread curve usable for interpolation and stress scenarios.


def _nelson_siegel(T: np.ndarray, b0: float, b1: float, b2: float, tau: float) -> np.ndarray:
    """Nelson-Siegel spread curve functional form."""
    x = T / tau
    with np.errstate(divide="ignore", invalid="ignore"):
        factor1 = np.where(x < 1e-8, 1.0, (1.0 - np.exp(-x)) / x)
        factor2 = factor1 - np.exp(-x)
    return b0 + b1 * factor1 + b2 * factor2


def fit_nelson_siegel(tenors: List[float], oas_bps: List[float]) -> dict:
    """Fit Nelson-Siegel to an OAS term structure.

    Returns
    -------
    dict
        NS parameters (b0, b1, b2, tau) and fit diagnostics.
    """
    T = np.array(tenors, dtype=float)
    y = np.array(oas_bps, dtype=float)

    def residuals(params):
        b0, b1, b2, tau = params
        if tau <= 0 or b0 <= 0:
            return np.full_like(y, 1e6)
        return _nelson_siegel(T, b0, b1, b2, tau) - y

    # Initial guess: flat spread at mean level
    mean_y = float(np.mean(y))
    x0 = [mean_y, -mean_y * 0.3, mean_y * 0.1, 3.0]
    bounds = ([0, -500, -500, 0.5], [2000, 500, 500, 30.0])

    try:
        res = scipy_optimize.least_squares(residuals, x0, bounds=bounds, method="trf")
        b0, b1, b2, tau = res.x
        y_fit = _nelson_siegel(T, b0, b1, b2, tau)
        rmse = float(np.sqrt(np.mean((y_fit - y) ** 2)))
        return {
            "b0": round(b0, 4),
            "b1": round(b1, 4),
            "b2": round(b2, 4),
            "tau": round(tau, 4),
            "rmse_bps": round(rmse, 3),
            "converged": bool(res.success),
            "fitted_oas_bps": dict(zip(tenors, [round(v, 2) for v in y_fit])),
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "converged": False}


# ---------------------------------------------------------------------------
# 3.  Calibrate All Spread Curves
# ---------------------------------------------------------------------------


def calibrate_credit_spreads(verbose: bool = True) -> dict:
    """Fit Nelson-Siegel to all IG and HY spread grids.

    Returns
    -------
    dict
        Nested dict: {rating: NS fit result}
    """
    results: dict = {}

    if verbose:
        print("\nINVESTMENT GRADE SPREAD CURVE CALIBRATION")
        print("=" * 60)

    for rating, data in _IG_SPREAD_GRID.items():
        fit = fit_nelson_siegel(data["tenors"], data["oas_bps"])
        results[f"IG_{rating}"] = {
            "rating": rating,
            "asset_class": "investment_grade",
            "input_tenors": data["tenors"],
            "input_oas_bps": data["oas_bps"],
            "ns_fit": fit,
        }
        if verbose:
            ok = "OK" if fit.get("converged") else "FAIL"
            rmse = fit.get("rmse_bps", float("nan"))
            b0 = fit.get("b0", float("nan"))
            print(f"  {rating:<5}: b0={b0:.1f} bps (long-run), RMSE={rmse:.2f} bps [{ok}]")

    if verbose:
        print("\nHIGH YIELD SPREAD CURVE CALIBRATION")
        print("=" * 60)

    for rating, data in _HY_SPREAD_GRID.items():
        fit = fit_nelson_siegel(data["tenors"], data["oas_bps"])
        results[f"HY_{rating}"] = {
            "rating": rating,
            "asset_class": "high_yield",
            "input_tenors": data["tenors"],
            "input_oas_bps": data["oas_bps"],
            "ns_fit": fit,
        }
        if verbose:
            ok = "OK" if fit.get("converged") else "FAIL"
            rmse = fit.get("rmse_bps", float("nan"))
            b0 = fit.get("b0", float("nan"))
            print(f"  {rating:<5}: b0={b0:.1f} bps (long-run), RMSE={rmse:.2f} bps [{ok}]")

    return results


# ---------------------------------------------------------------------------
# 4.  Private Asset Assumption Summary
# ---------------------------------------------------------------------------


def summarise_private_assets(verbose: bool = True) -> dict:
    """Tabulate private asset spread / return assumptions."""
    if verbose:
        print("\nPRIVATE ASSET CALIBRATION ASSUMPTIONS")
        print("=" * 60)
        print(f"{'Asset':<30} {'All-in Spd':>12} {'Illiq Prem':>12} {'Exp Loss':>11}")
        print("-" * 70)

        for asset, p in _PRIVATE_ASSET_ASSUMPTIONS.items():
            all_in = p.get("typical_all_in_spread_bps", p.get("expected_total_return_pct", "N/A"))
            illiq = p.get("illiquidity_premium_bps", p.get("illiquidity_premium_pct", "N/A"))
            exp_loss = p.get("expected_loss_bps", "N/A")
            print(f"  {asset:<28} {str(all_in):>12} {str(illiq):>12} {str(exp_loss):>11}")

        print("-" * 70)
        print()
        print("Notes:")
        print("  All-in Spd = OAS or total return expectation (bps or %)")
        print("  Illiq Prem = Illiquidity premium over comparable public assets (bps or %)")
        print("  Exp Loss   = Annual expected loss allowance (PD x LGD, bps)")
        print()
        print("ERM: Credit risk factors include PD, LGD, illiquidity, J-curve, and")
        print("     correlation with public market risk factors.")
        print("SOA ASOP 56 s3.4: All assumptions documented; production sign-off required.")

    return _PRIVATE_ASSET_ASSUMPTIONS


# ---------------------------------------------------------------------------
# 5.  Credit Stress Scenario Diagnostics
# ---------------------------------------------------------------------------

_CREDIT_STRESS_SHOCKS: Dict[str, dict] = {
    "CS01": {
        "name": "Moderate spread widening",
        "ig_shock_bps": +50,
        "hy_shock_bps": +150,
        "private_credit_shock_bps": +80,
        "description": "1-in-5 year mild recession scenario",
    },
    "CS02": {
        "name": "Severe spread widening (GFC-like)",
        "ig_shock_bps": +200,
        "hy_shock_bps": +600,
        "private_credit_shock_bps": +300,
        "description": "1-in-25 year stress consistent with 2008/9 levels",
    },
    "CS03": {
        "name": "IG downgrade wave",
        "ig_shock_bps": +100,
        "hy_shock_bps": +250,
        "private_credit_shock_bps": +150,
        "downgrade_notch": 1,
        "description": "BBB cliff risk: 20% of IG portfolio migrates to HY",
    },
}


def print_credit_stress_table(verbose: bool = True) -> None:
    """Print the credit stress scenario table."""
    if verbose:
        print("\nCREDIT STRESS SCENARIOS")
        print("=" * 60)
        print(f"{'Scenario':<8} {'Name':<35} {'IG Shock':>10} {'HY Shock':>10}")
        print("-" * 68)
        for sid, s in _CREDIT_STRESS_SHOCKS.items():
            ig_s = f"+{s['ig_shock_bps']}bps"
            hy_s = f"+{s['hy_shock_bps']}bps"
            print(f"  {sid:<8} {s['name']:<35} {ig_s:>10} {hy_s:>10}")
        print("-" * 68)
        print()
        print("ERM: Stress scenarios CS01-CS03 are pre-defined governance tests.")
        print("     Run asset_stress.py for full asset class stress integration.")


# ---------------------------------------------------------------------------
# 6.  CLI Entry Point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Credit spread calibration — Phase 12 educational script."
    )
    parser.add_argument("--output", default=None, help="Path to write JSON results.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    verbose = not args.quiet

    spread_results = calibrate_credit_spreads(verbose=verbose)
    private_assumptions = summarise_private_assets(verbose=verbose)
    print_credit_stress_table(verbose=verbose)

    all_converged = all(
        r.get("ns_fit", {}).get("converged", False)
        for r in spread_results.values()
        if "ns_fit" in r
    )

    output_doc = {
        "calibration_date": VALUATION_DATE.isoformat(),
        "run_timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "spread_curves": spread_results,
        "private_asset_assumptions": private_assumptions,
        "stress_scenarios": _CREDIT_STRESS_SHOCKS,
        "all_converged": all_converged,
        "standards": {
            "SOA ASOP 56 s3.4": "NS curve fitting: scipy least_squares, trf method. RMSE < 2 bps target.",
            "ERM": "Stress scenarios CS01-CS03 cover moderate, severe, and downgrade-wave events.",
            "IA TAS M s3.5": "Assumption Owner sign-off required before production use.",
        },
        "notes": (
            "Nelson-Siegel fitted to synthetic OAS grids for IG (AAA–BBB) and HY (BB–CCC). "
            "Private asset illiquidity premia are illustrative; replace with manager-reported "
            "returns and regulatory guidance before production use."
        ),
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(output_doc, fh, indent=2, default=str)
        if verbose:
            print(f"\nResults written to: {out_path}")

    return 0 if all_converged else 1


if __name__ == "__main__":
    sys.exit(main())
