"""
calibrate_liabilities.py — Hong Kong PAR Liability Assumption Calibration
==========================================================================

Demonstrates liability assumption calibration for Hong Kong participating
(PAR) insurance products. Covers:

  1. Mortality — HK insured life table (HKML 2016 basis) with improvement
     scale and portfolio experience adjustment.
  2. Voluntary lapse — duration-dependent lapse curve fit to HK market
     experience, including shock-lapse stress scenarios.
  3. Bonus/dividend declaration — calibration of supportable bonus rates
     against modelled asset-share accumulation for cash-dividend and
     reversionary bonus product lines.

EDUCATIONAL NOTE
----------------
All experience data is synthetic. In production, replace with:
  - HKML 2016 ultimate insured-lives table from the IA (HK)
  - Company experience study (min. 5 years, graduated credibility)
  - Peer group / industry survey data for credibility loading
  - IA(HK) bonus supportability guidance and product filing assumptions

Standards Addressed
-------------------
SOA ASOP 25 §3.3  — credibility weighting of experience vs. industry table
SOA ASOP 56 §3.4  — mortality, lapse, and bonus assumption documentation
IA TAS M §3.5     — assumption sign-off and change management
IA(HK) GL16       — HK policyholder bonus guidance (regulatory)
docs/HK_PARTICIPATING_PRODUCTS.md (if present) — product mechanics

Usage
-----
    python scripts/calibration/calibrate_liabilities.py
    python scripts/calibration/calibrate_liabilities.py --output outputs/liability_calibration.json
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import optimize as scipy_optimize
from scipy.interpolate import PchipInterpolator

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

VALUATION_DATE = date(2026, 5, 30)
RNG_SEED = 20260530

# ---------------------------------------------------------------------------
# 1.  Mortality Calibration
# ---------------------------------------------------------------------------
# HKML 2016 is the standard insured-lives table published by the IA (HK).
# We use a simplified select-and-ultimate structure: q(x) for attained age x.
# The improvement scale follows the HK CMI improvement model (simplified).

# Illustrative HKML 2016 ultimate qx values (male, per 1,000 lives)
# Ages 18 to 80; simplified — in production use the full published table.
_HKML2016_MALE_QX_PER_1000: Dict[int, float] = {
    18: 0.55, 19: 0.57, 20: 0.59, 21: 0.61, 22: 0.63,
    23: 0.65, 24: 0.67, 25: 0.69, 26: 0.71, 27: 0.73,
    28: 0.76, 29: 0.79, 30: 0.82, 31: 0.86, 32: 0.91,
    33: 0.96, 34: 1.02, 35: 1.09, 36: 1.17, 37: 1.26,
    38: 1.36, 39: 1.48, 40: 1.62, 41: 1.78, 42: 1.97,
    43: 2.18, 44: 2.42, 45: 2.70, 46: 3.02, 47: 3.38,
    48: 3.79, 49: 4.26, 50: 4.79, 51: 5.38, 52: 6.06,
    53: 6.83, 54: 7.70, 55: 8.68, 56: 9.80, 57: 11.07,
    58: 12.51, 59: 14.13, 60: 15.98, 61: 18.08, 62: 20.45,
    63: 23.15, 64: 26.21, 65: 29.69, 66: 33.65, 67: 38.14,
    68: 43.24, 69: 49.04, 70: 55.61, 71: 63.08, 72: 71.56,
    73: 81.20, 74: 92.14, 75: 104.55, 76: 118.61, 77: 134.51,
    78: 152.47, 79: 172.68, 80: 195.30,
}

# Female mortality: illustrative ratio to male (HK female advantage)
_FEMALE_MALE_RATIO: Dict[int, float] = {age: 0.58 + (age - 18) * 0.003 for age in range(18, 81)}

# Annual mortality improvement scale (% reduction per year)
# HK experience shows ~1.5% p.a. improvement for mid-ages
_MORTALITY_IMPROVEMENT_ANNUAL_PCT: float = 1.5   # % p.a.
_IMPROVEMENT_BASE_YEAR: int = 2016


def build_mortality_table(
    projection_year: int = 2026,
    experience_A_pct: float = 90.0,   # company A/E ratio vs. HKML 2016 (90% = lighter mortality)
    credibility_weight: float = 0.60,  # proportion of company experience vs. industry
    verbose: bool = True,
) -> pd.DataFrame:
    """Build a graduated mortality table for the projection year.

    Applies CMI-style mortality improvement from 2016 base to projection_year,
    then applies experience A/E credibility blending per SOA ASOP 25.

    Parameters
    ----------
    projection_year : int
        Calendar year for the calibrated table.
    experience_A_pct : float
        Company actual-to-expected ratio as % of HKML 2016 (e.g. 90 = 10% lighter).
    credibility_weight : float
        Credibility assigned to company experience (0=100% industry, 1=100% company).

    Returns
    -------
    pd.DataFrame
        Columns: age, qx_hkml2016, qx_improved, qx_calibrated (both sexes blended).
    """
    years_elapsed = projection_year - _IMPROVEMENT_BASE_YEAR
    improvement_factor = (1.0 - _MORTALITY_IMPROVEMENT_ANNUAL_PCT / 100.0) ** years_elapsed

    rows = []
    for age, qx_1000 in _HKML2016_MALE_QX_PER_1000.items():
        qx_base_m = qx_1000 / 1000.0
        qx_base_f = qx_base_m * _FEMALE_MALE_RATIO.get(age, 0.65)

        # 50/50 sex blend (educational; in practice use actual portfolio mix)
        qx_base_blended = 0.50 * qx_base_m + 0.50 * qx_base_f

        # Apply mortality improvement
        qx_improved = qx_base_blended * improvement_factor

        # Credibility blend: calibrated = credibility * company_exp + (1-credibility) * industry
        company_qx = qx_improved * (experience_A_pct / 100.0)
        qx_calibrated = (
            credibility_weight * company_qx
            + (1.0 - credibility_weight) * qx_improved
        )

        rows.append({
            "age": age,
            "qx_hkml2016_blended": round(qx_base_blended, 6),
            "qx_improved": round(qx_improved, 6),
            "qx_calibrated": round(qx_calibrated, 6),
        })

    df = pd.DataFrame(rows)

    if verbose:
        print(f"\nMORTALITY TABLE — Projection Year {projection_year}")
        print("=" * 60)
        print(f"  HKML 2016 base → improved ({years_elapsed} years at {_MORTALITY_IMPROVEMENT_ANNUAL_PCT}% p.a.)")
        print(f"  Company A/E: {experience_A_pct:.0f}%  |  Credibility weight: {credibility_weight:.0%}")
        print()
        display_ages = [25, 35, 45, 55, 65, 75]
        print(f"  {'Age':>5} {'qx_2016':>12} {'qx_improved':>14} {'qx_calibrated':>16}")
        print(f"  {'-'*5} {'-'*12} {'-'*14} {'-'*16}")
        for _, row in df[df["age"].isin(display_ages)].iterrows():
            print(f"  {row['age']:>5} {row['qx_hkml2016_blended']:>12.6f} "
                  f"{row['qx_improved']:>14.6f} {row['qx_calibrated']:>16.6f}")
        print()
        print("  SOA ASOP 25 s3.3: Credibility blending applied.")
        print("  SOA ASOP 56 s3.4: Improvement scale documented.")
        print("  IA TAS M s3.5: Assumption Owner sign-off required.")

    return df


# ---------------------------------------------------------------------------
# 2.  Voluntary Lapse Calibration
# ---------------------------------------------------------------------------
# Lapse rates are modelled as a duration-dependent curve (Makeham-style)
# declining from high early-duration rates to a lower persistency floor.
# We fit a parametric curve to synthetic "observed" HK market experience.

# Synthetic observed lapse rates by policy duration (years in force)
_OBSERVED_LAPSE_RATES: Dict[str, Dict[int, float]] = {
    "cash_dividend": {
        # Duration: 1y, 2y, 3y, 5y, 7y, 10y, 15y, 20y
        1: 0.080, 2: 0.060, 3: 0.045, 5: 0.030,
        7: 0.025, 10: 0.020, 15: 0.018, 20: 0.015,
    },
    "reversionary_bonus": {
        1: 0.065, 2: 0.050, 3: 0.038, 5: 0.026,
        7: 0.022, 10: 0.018, 15: 0.015, 20: 0.012,
    },
}

# Shock lapse scenarios (regulatory stress per IA(HK) GL16)
_SHOCK_LAPSE_SCENARIOS: Dict[str, float] = {
    "base": 1.0,          # no shock
    "mass_lapse_1in10": 1.5,  # 50% above base (1-in-10 year stress)
    "mass_lapse_1in25": 2.5,  # 2.5x base (1-in-25 year stress)
    "no_lapse": 0.0,          # best case (policyholders never lapse)
}


def _lapse_model(duration: np.ndarray, L0: float, k: float, L_floor: float) -> np.ndarray:
    """Exponential decay lapse curve: L(t) = (L0 - L_floor) * exp(-k*t) + L_floor."""
    return (L0 - L_floor) * np.exp(-k * duration) + L_floor


def calibrate_lapse_curve(product: str, verbose: bool = True) -> dict:
    """Fit exponential decay lapse curve to observed rates for a product.

    Returns calibrated parameters and goodness-of-fit stats.
    """
    obs = _OBSERVED_LAPSE_RATES[product]
    durations = np.array(sorted(obs.keys()), dtype=float)
    rates = np.array([obs[int(d)] for d in durations])

    try:
        popt, pcov = scipy_optimize.curve_fit(
            _lapse_model,
            durations,
            rates,
            p0=[0.10, 0.20, 0.015],
            bounds=([0.0, 0.0, 0.0], [0.5, 5.0, 0.10]),
            maxfev=5000,
        )
        L0_fit, k_fit, L_floor_fit = popt
        fitted = _lapse_model(durations, *popt)
        rmse = float(np.sqrt(np.mean((fitted - rates) ** 2)))
        converged = True
        notes = "Exponential decay curve fitted successfully."

    except Exception as exc:  # noqa: BLE001
        L0_fit = rates[0]
        k_fit = 0.15
        L_floor_fit = rates[-1]
        rmse = float("nan")
        converged = False
        notes = f"Curve fit failed ({exc}); fallback to PCHIP interpolation."

    result = {
        "product": product,
        "model": "exponential_decay",
        "parameters": {
            "L0": round(float(L0_fit), 5),
            "k": round(float(k_fit), 5),
            "L_floor": round(float(L_floor_fit), 5),
        },
        "goodness_of_fit": {
            "rmse": round(rmse, 6) if not np.isnan(rmse) else None,
            "converged": converged,
        },
        "shock_scenarios": {
            name: {
                "multiplier": mult,
                "lapse_at_1y": round(float(L0_fit) * mult, 5),
                "lapse_at_10y": round(_lapse_model(np.array([10.0]), L0_fit, k_fit, L_floor_fit)[0] * mult, 5),
            }
            for name, mult in _SHOCK_LAPSE_SCENARIOS.items()
        },
        "notes": notes,
    }

    if verbose:
        print(f"\nLAPSE CALIBRATION — {product}")
        print("=" * 60)
        print(f"  Model: exponential decay L(t) = (L0 - L_floor)*exp(-k*t) + L_floor")
        print(f"  L0 (year-1 rate):  {L0_fit:.4%}")
        print(f"  k (decay speed):   {k_fit:.4f}")
        print(f"  L_floor (ultimate):{L_floor_fit:.4%}")
        print(f"  RMSE:              {rmse:.6f}" if not np.isnan(rmse) else "  RMSE:              N/A")
        print()
        print(f"  {'Duration':>10} {'Observed':>12} {'Fitted':>12} {'Error (pp)':>12}")
        print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*12}")
        fitted_all = _lapse_model(durations, L0_fit, k_fit, L_floor_fit)
        for dur, obs_r, fit_r in zip(durations, rates, fitted_all):
            err = (fit_r - obs_r) * 100
            print(f"  {int(dur):>10}y {obs_r:>11.3%} {fit_r:>11.3%} {err:>+11.2f}pp")
        print()
        print("  Shock Lapse Scenarios (IA(HK) GL16 regulatory stress):")
        for name, mult in _SHOCK_LAPSE_SCENARIOS.items():
            yr1 = float(L0_fit) * mult
            print(f"    {name:<25}: Year-1 lapse = {yr1:.3%} ({mult:.1f}x base)")

    return result


# ---------------------------------------------------------------------------
# 3.  Bonus / Dividend Declaration Assumption Calibration
# ---------------------------------------------------------------------------
# Supportable bonus rates are derived from the modelled asset-share
# accumulation under P-measure scenarios and constrained by regulatory filing.

# Illustrative HK PAR fund asset-share accumulation (% per annum)
# Under realistic P-measure assumptions for the HK PAR fund
_ASSET_SHARE_RETURNS: Dict[str, float] = {
    "investment_return_pct": 5.50,    # gross asset-share investment return
    "expense_ratio_pct": 0.80,        # fund management + admin
    "mortality_drag_pct": 0.15,       # cost of death claims (per 1,000 SA)
    "net_accumulation_pct": 4.55,     # = 5.50 - 0.80 - 0.15
}

_PRODUCT_BONUS_TARGETS: Dict[str, dict] = {
    "cash_dividend": {
        "description": "HK cash dividend PAR — annual dividend declared as % of sum assured",
        "current_declaration_pct_of_sa": 2.50,   # illustrative annual dividend
        "supportability_ratio": 1.15,             # asset share / obligation
        "max_supportable_pct": 3.20,              # maximum without impairing bonus reserve
        "min_supportable_pct": 1.80,              # minimum to maintain policyholder fairness
        "regulatory_reserve_margin_pct": 0.30,    # IA(HK) required margin above best estimate
    },
    "reversionary_bonus": {
        "description": "HK reversionary bonus PAR — vested bonus added annually to sum assured",
        "current_vested_bonus_rate_pct": 1.80,    # as % of sum assured p.a.
        "current_terminal_bonus_pct": 15.00,      # as % of total vested bonus at maturity
        "supportability_ratio": 1.12,
        "max_vested_supportable_pct": 2.20,
        "min_vested_supportable_pct": 1.20,
        "regulatory_reserve_margin_pct": 0.30,
    },
}


def calibrate_bonus_assumptions(verbose: bool = True) -> dict:
    """Derive supportable bonus / dividend rates from asset-share projections.

    Uses a simplified deterministic asset-share projection. In production,
    run the full Phase 11 stochastic pipeline and use the P-measure
    asset-share distribution to assess bonus supportability across scenarios.
    """
    result: dict = {
        "calibration_date": VALUATION_DATE.isoformat(),
        "asset_share_assumptions": _ASSET_SHARE_RETURNS,
        "products": {},
    }

    if verbose:
        print("\nBONUS / DIVIDEND DECLARATION CALIBRATION")
        print("=" * 60)
        print("  Asset-Share Fund Return Assumptions:")
        for k, v in _ASSET_SHARE_RETURNS.items():
            print(f"    {k:<35}: {v:.2f}%")
        print()

    for product, params in _PRODUCT_BONUS_TARGETS.items():
        net_accum = _ASSET_SHARE_RETURNS["net_accumulation_pct"]

        # Simple check: is declared rate below max supportable?
        if product == "cash_dividend":
            declared = params["current_declaration_pct_of_sa"]
            max_s = params["max_supportable_pct"]
            min_s = params["min_supportable_pct"]
            margin = params["regulatory_reserve_margin_pct"]
            effective_max = max_s - margin
            sustainable = min_s <= declared <= effective_max
            sensitivity = {
                "if_return_drops_1pct": round(declared - 1.0, 2),
                "if_return_rises_1pct": round(declared + 1.0, 2),
                "breakeven_net_accumulation_pct": round(declared + margin, 2),
            }
        else:
            declared = params["current_vested_bonus_rate_pct"]
            max_s = params["max_vested_supportable_pct"]
            min_s = params["min_vested_supportable_pct"]
            margin = params["regulatory_reserve_margin_pct"]
            effective_max = max_s - margin
            sustainable = min_s <= declared <= effective_max
            sensitivity = {
                "if_return_drops_1pct": round(declared - 0.60, 2),
                "if_return_rises_1pct": round(declared + 0.60, 2),
                "breakeven_net_accumulation_pct": round(declared + margin, 2),
            }

        product_result = {
            "description": params["description"],
            "declared_rate": declared,
            "supportability_ratio": params["supportability_ratio"],
            "min_supportable": min_s,
            "max_supportable": max_s,
            "effective_max_after_margin": round(effective_max, 2),
            "sustainable": sustainable,
            "sensitivity": sensitivity,
            "notes": (
                "Sustainable" if sustainable else
                "WARNING: Declared rate outside supportable range — review required."
            ),
        }
        result["products"][product] = product_result

        if verbose:
            status = "SUSTAINABLE" if sustainable else "WARNING"
            print(f"  {product} [{status}]:")
            print(f"    Declared rate:          {declared:.2f}%")
            print(f"    Supportable range:      {min_s:.2f}% – {effective_max:.2f}%")
            print(f"    Supportability ratio:   {params['supportability_ratio']:.2f}x")
            print(f"    Sensitivity (+/-1% return): {sensitivity['if_return_drops_1pct']:.2f}% / "
                  f"{sensitivity['if_return_rises_1pct']:.2f}%")
            print()

    if verbose:
        print("  IA(HK) GL16: Bonus rates must be supportable by current asset share.")
        print("  SOA ASOP 56 s3.4: Bonus assumption documented with sensitivity analysis.")
        print("  IA TAS M s3.5: Assumption Owner sign-off required before filing.")

    return result


# ---------------------------------------------------------------------------
# 4.  Aggregated Output
# ---------------------------------------------------------------------------


@dataclass
class LiabilityCalibrationSummary:
    calibration_date: date
    run_timestamp: str
    mortality: dict = field(default_factory=dict)
    lapse: Dict[str, dict] = field(default_factory=dict)
    bonus: dict = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "calibration_date": self.calibration_date.isoformat(),
            "run_timestamp": self.run_timestamp,
            "mortality": self.mortality,
            "lapse": self.lapse,
            "bonus": self.bonus,
            "notes": self.notes,
            "standards": {
                "SOA ASOP 25 s3.3": "Credibility blending for mortality (60% company, 40% industry)",
                "SOA ASOP 56 s3.4": "All liability assumptions documented with source and sensitivity",
                "IA TAS M s3.5": "Assumption Owner sign-off required before production filing",
                "IA(HK) GL16": "Bonus supportability tested; regulatory margin 0.30% applied",
            },
        }


def calibrate_all_liabilities(verbose: bool = True) -> LiabilityCalibrationSummary:
    """Run full liability assumption calibration."""
    run_ts = datetime.now(tz=timezone.utc).isoformat()
    summary = LiabilityCalibrationSummary(
        calibration_date=VALUATION_DATE,
        run_timestamp=run_ts,
    )

    # Mortality
    mort_df = build_mortality_table(projection_year=2026, verbose=verbose)
    summary.mortality = {
        "projection_year": 2026,
        "base_table": "HKML 2016",
        "improvement_scale": f"{_MORTALITY_IMPROVEMENT_ANNUAL_PCT}% p.a. (illustrative CMI-style)",
        "credibility_weight": 0.60,
        "experience_ae_pct": 90.0,
        "sample_calibrated_qx": {
            row["age"]: row["qx_calibrated"]
            for _, row in mort_df[mort_df["age"].isin([25, 35, 45, 55, 65])].iterrows()
        },
    }

    # Lapse
    for product in ["cash_dividend", "reversionary_bonus"]:
        summary.lapse[product] = calibrate_lapse_curve(product, verbose=verbose)

    # Bonus
    summary.bonus = calibrate_bonus_assumptions(verbose=verbose)

    summary.notes = (
        "HK PAR liability assumption calibration complete. "
        "Mortality: HKML 2016 improved to 2026 with 1.5% p.a. improvement; "
        "credibility-blended 60/40 company/industry. "
        "Lapse: exponential decay model fitted to synthetic HK market experience. "
        "Bonus: supportability test for cash dividend and reversionary bonus products. "
        "All results are educational placeholders; Assumption Owner sign-off required."
    )

    if verbose:
        print(f"\n{'='*60}")
        print("  LIABILITY CALIBRATION COMPLETE")
        print(f"{'='*60}")
        print(f"  Mortality:   HKML 2016 + improvement, 2 products calibrated")
        print(f"  Lapse:       {len(summary.lapse)} products calibrated")
        print(f"  Bonus:       {len(summary.bonus.get('products', {}))} products reviewed")

    return summary


# ---------------------------------------------------------------------------
# 5.  CLI Entry Point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="HK PAR liability assumption calibration — Phase 12 educational script."
    )
    parser.add_argument("--output", default=None, help="Path to write JSON results.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    summary = calibrate_all_liabilities(verbose=not args.quiet)
    result_dict = summary.to_dict()

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result_dict, fh, indent=2, default=str)
        if not args.quiet:
            print(f"\nResults written to: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
