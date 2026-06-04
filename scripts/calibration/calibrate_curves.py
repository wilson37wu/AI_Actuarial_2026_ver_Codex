"""
calibrate_curves.py — Hull-White 1F Yield Curve Calibration
=============================================================

Demonstrates Hull-White 1-Factor parameter calibration for five starter
markets: USD, EUR, HKD, CNY, and JPY. Uses synthetic ATM swaption quotes
that are consistent with the Phase 7 starter yield curves.

EDUCATIONAL NOTE
----------------
All market quotes in this script are illustrative placeholders. In production,
replace the SwaptionMarketQuotes dataclasses with live market data sourced from
a Bloomberg/Refinitiv feed and reviewed by the Assumption Owner per
docs/PARAMETER_CALIBRATION_METHODOLOGY.md §4.

Standards Addressed
-------------------
SOA ASOP 56 §3.4   — calibration methodology and documentation
SOA ASOP 56 §3.5   — model validation (fit diagnostics)
IA TAS M §3.5      — assumption appropriateness sign-off
docs/PARAMETER_CALIBRATION_METHODOLOGY.md §5 — HW1F calibration spec

Usage
-----
    python scripts/calibration/calibrate_curves.py
    python scripts/calibration/calibrate_curves.py --output outputs/curve_calibration.json
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

# ---------------------------------------------------------------------------
# Ensure repo root is on path when run as a script
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from par_model_v2.calibration import (
    CalibrationResult,
    HullWhiteCalibrationInputs,
    HullWhiteCalibrator,
    SwaptionQuote,
)

# ---------------------------------------------------------------------------
# 1.  Synthetic Swaption Market Quotes  (illustrative — not production data)
# ---------------------------------------------------------------------------

VALUATION_DATE = date(2026, 5, 30)

# Each entry: (expiry_years, swap_tenor_years, normal_vol_bps, weight)
# Normal vol (Bachelier) is used throughout because HKD/CNY/JPY rates can be
# near-zero; log-normal Black vol is inappropriate in low-rate regimes.
# SOA ASOP 56 §3.4 Note: document vol convention and source for each quote.

_SWAPTION_GRIDS: Dict[str, List[Tuple[float, float, float, float]]] = {
    "USD": [
        # (expiry, tenor, normal_vol_bps, weight)
        (1.0, 1.0, 62.0, 1.0),
        (1.0, 5.0, 68.0, 1.0),
        (2.0, 5.0, 70.0, 1.0),
        (5.0, 5.0, 72.0, 1.0),
        (5.0, 10.0, 74.0, 1.0),
        (10.0, 10.0, 76.0, 0.8),  # lower weight: 10y×10y less liquid
    ],
    "EUR": [
        (1.0, 1.0, 48.0, 1.0),
        (1.0, 5.0, 52.0, 1.0),
        (2.0, 5.0, 54.0, 1.0),
        (5.0, 5.0, 55.0, 1.0),
        (5.0, 10.0, 57.0, 1.0),
        (10.0, 10.0, 58.0, 0.8),
    ],
    "HKD": [
        # HKD moves with USD via currency board; similar vol but slightly lower
        (1.0, 1.0, 55.0, 1.0),
        (1.0, 5.0, 60.0, 1.0),
        (2.0, 5.0, 62.0, 1.0),
        (5.0, 5.0, 63.0, 1.0),
        (5.0, 10.0, 65.0, 0.9),
        (10.0, 10.0, 66.0, 0.7),
    ],
    "CNY": [
        # CNY: lower vol; PBOC manages rate corridor tightly
        (1.0, 1.0, 35.0, 1.0),
        (1.0, 5.0, 38.0, 1.0),
        (2.0, 5.0, 40.0, 1.0),
        (5.0, 5.0, 42.0, 1.0),
        (5.0, 10.0, 44.0, 0.8),
        (10.0, 10.0, 45.0, 0.5),  # 10y×10y: limited CNY liquidity
    ],
    "JPY": [
        # JPY: very low vol in the ultra-low rate environment
        (1.0, 1.0, 12.0, 1.0),
        (1.0, 5.0, 15.0, 1.0),
        (2.0, 5.0, 17.0, 1.0),
        (5.0, 5.0, 20.0, 1.0),
        (5.0, 10.0, 22.0, 1.0),
        (10.0, 10.0, 25.0, 0.8),
    ],
}

# Initial short rates from Phase 7 starter curves (continuously compounded r(0))
_INITIAL_SHORT_RATES: Dict[str, float] = {
    "USD": 0.043,
    "EUR": 0.018,
    "HKD": 0.036,
    "CNY": 0.016,
    "JPY": -0.001,  # negative short rate; HW1F supports this
}

# Spot curves: tenor → zero rate (continuously compounded)
_SPOT_CURVES: Dict[str, Dict[float, float]] = {
    "USD": {0.25: 0.0425, 0.5: 0.0420, 1.0: 0.0410, 2.0: 0.0390, 5.0: 0.0370, 10.0: 0.0380, 20.0: 0.0400, 30.0: 0.0410},
    "EUR": {0.25: 0.0170, 0.5: 0.0160, 1.0: 0.0150, 2.0: 0.0140, 5.0: 0.0160, 10.0: 0.0190, 20.0: 0.0230, 30.0: 0.0250},
    "HKD": {0.25: 0.0350, 0.5: 0.0340, 1.0: 0.0330, 2.0: 0.0310, 5.0: 0.0300, 10.0: 0.0320, 20.0: 0.0340, 30.0: 0.0350},
    "CNY": {0.25: 0.0165, 0.5: 0.0170, 1.0: 0.0180, 2.0: 0.0200, 5.0: 0.0230, 10.0: 0.0260, 20.0: 0.0280, 30.0: 0.0290},
    "JPY": {0.25: -0.0005, 0.5: 0.0000, 1.0: 0.0020, 2.0: 0.0050, 5.0: 0.0090, 10.0: 0.0130, 20.0: 0.0170, 30.0: 0.0190},
}

# Regulatory rate caps (CBIRC/local regulator maximums for reserve discounting)
_REGULATORY_CAPS: Dict[str, float] = {
    "USD": 0.05,
    "EUR": 0.04,
    "HKD": 0.05,
    "CNY": 0.030,   # CBIRC actuarial rate cap
    "JPY": 0.03,
}


# ---------------------------------------------------------------------------
# 2.  Calibration Helper — build inputs from synthetic data
# ---------------------------------------------------------------------------


def _build_hw_inputs(currency: str) -> HullWhiteCalibrationInputs:
    """Construct HullWhiteCalibrationInputs for a given currency."""
    grid = _SWAPTION_GRIDS[currency]
    quotes = [
        SwaptionQuote(
            expiry_years=e,
            swap_tenor_years=s,
            normal_vol_bps=v,
            weight=w,
        )
        for e, s, v, w in grid
    ]
    spot_series = pd.Series(_SPOT_CURVES[currency])
    return HullWhiteCalibrationInputs(
        calibration_date=VALUATION_DATE,
        initial_short_rate=_INITIAL_SHORT_RATES[currency],
        spot_curve=spot_series,
        swaption_quotes=quotes,
        regulatory_rate_cap=_REGULATORY_CAPS[currency],
    )


# ---------------------------------------------------------------------------
# 3.  Run Calibration for All Currencies
# ---------------------------------------------------------------------------


@dataclass
class CurveCalibrationSummary:
    """Summary of HW1F calibration results for all currencies."""

    calibration_date: date
    run_timestamp: str
    results: Dict[str, dict] = field(default_factory=dict)
    all_converged: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "calibration_date": self.calibration_date.isoformat(),
            "run_timestamp": self.run_timestamp,
            "results": self.results,
            "all_converged": self.all_converged,
            "notes": self.notes,
            "standards": {
                "SOA ASOP 56 s3.4": "Calibration methodology: L-BFGS-B minimisation of weighted normal-vol errors",
                "SOA ASOP 56 s3.5": "Fit diagnostics: RMSE and max error reported per market",
                "IA TAS M s3.5": "Assumption sign-off required before production use",
            },
        }


def calibrate_all_curves(verbose: bool = True) -> CurveCalibrationSummary:
    """Run HW1F calibration for all five starter markets.

    Parameters
    ----------
    verbose : bool
        If True, print per-market calibration summaries.

    Returns
    -------
    CurveCalibrationSummary
        Aggregated calibration results.
    """
    run_ts = datetime.now(tz=timezone.utc).isoformat()
    summary = CurveCalibrationSummary(
        calibration_date=VALUATION_DATE,
        run_timestamp=run_ts,
    )

    all_ok = True

    for ccy in ["USD", "EUR", "HKD", "CNY", "JPY"]:
        if verbose:
            print(f"\n{'='*60}")
            print(f"  Calibrating HW1F — {ccy}")
            print(f"{'='*60}")

        try:
            inputs = _build_hw_inputs(ccy)
            calibrator = HullWhiteCalibrator(inputs)

            with warnings.catch_warnings(record=True) as caught_warnings:
                warnings.simplefilter("always")
                result = calibrator.calibrate()

            if verbose:
                print(result.summary())
                if result.swaption_fit_table is not None:
                    print("\nSwaption Fit Table:")
                    print(result.swaption_fit_table.to_string(index=False))

            # Build result record
            fit_ok = (result.swaption_rmse_bps is not None and
                      result.swaption_rmse_bps < 2.0)

            record = {
                "currency": ccy,
                "is_placeholder": result.is_placeholder,
                "hw1f_params": result.to_hw_params_dict(),
                "fit": {
                    "swaption_rmse_bps": result.swaption_rmse_bps,
                    "max_swaption_error_bps": result.max_swaption_error_bps,
                    "fit_acceptable": fit_ok,
                    "threshold_rmse_bps": 2.0,
                },
                "warnings": [str(w.message) for w in caught_warnings],
                "notes": result.notes,
            }

            summary.results[ccy] = record

            if result.is_placeholder:
                all_ok = False
                if verbose:
                    print(f"  [WARNING] {ccy}: calibration returned placeholder result.")

        except Exception as exc:  # noqa: BLE001
            all_ok = False
            summary.results[ccy] = {
                "currency": ccy,
                "error": str(exc),
                "is_placeholder": True,
            }
            if verbose:
                print(f"  [ERROR] {ccy} calibration failed: {exc}")

    summary.all_converged = all_ok
    summary.notes = (
        "All five HW1F calibrations completed. "
        "is_placeholder=True means the calibrate() method raised NotImplementedError "
        "because live swaption data is not available in this educational environment. "
        "Replace synthetic quotes with live market data before production use. "
        "SOA ASOP 56 s3.4: methodology is documented; "
        "IA TAS M s3.5: Assumption Owner sign-off required."
    )

    if verbose:
        print(f"\n{'='*60}")
        print("  CURVE CALIBRATION SUMMARY")
        print(f"{'='*60}")
        print(f"  Markets calibrated: {list(summary.results.keys())}")
        print(f"  All converged:      {summary.all_converged}")
        print(f"  Run timestamp:      {summary.run_timestamp}")

    return summary


# ---------------------------------------------------------------------------
# 4.  Diagnostic: Yield Curve Fit Plot (text-based)
# ---------------------------------------------------------------------------


def print_curve_diagnostics(summary: CurveCalibrationSummary) -> None:
    """Print text-based curve diagnostics for each market."""
    print("\n\nYIELD CURVE CALIBRATION DIAGNOSTICS")
    print("=" * 70)
    print(f"{'CCY':<8} {'a':>8} {'sigma_r':>10} {'r0':>8} {'RMSE(bps)':>12} {'Status':<12}")
    print("-" * 70)

    for ccy, rec in summary.results.items():
        if "error" in rec:
            print(f"{ccy:<8} {'ERROR':>8} {'':>10} {'':>8} {'':>12} {'FAILED':<12}")
            continue
        params = rec.get("hw1f_params", {})
        fit = rec.get("fit", {})
        a = params.get("a", float("nan"))
        sr = params.get("sigma_r", float("nan"))
        r0 = params.get("r0", float("nan"))
        rmse = fit.get("swaption_rmse_bps")
        rmse_str = f"{rmse:.2f}" if rmse is not None else "N/A"
        status = "PLACEHOLDER" if rec.get("is_placeholder") else "OK"
        print(f"{ccy:<8} {a:>8.4f} {sr:>10.4f} {r0:>8.4f} {rmse_str:>12} {status:<12}")

    print("-" * 70)
    print()
    print("Notes:")
    print("  a        = HW1F mean-reversion speed (annualised)")
    print("  sigma_r  = HW1F short rate volatility (annualised)")
    print("  r0       = Initial short rate (continuously compounded)")
    print("  RMSE     = Root mean squared swaption vol error (basis points)")
    print("  Status   = PLACEHOLDER until live swaption data is wired in")
    print()
    print("SOA ASOP 56 s3.4 — All parameters documented with source and methodology.")
    print("IA TAS M s3.5    — Assumption Owner sign-off required before production use.")


# ---------------------------------------------------------------------------
# 5.  CLI Entry Point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hull-White 1F yield curve calibration — Phase 12 educational script."
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write JSON calibration results (default: stdout only).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose per-market output.",
    )
    args = parser.parse_args(argv)

    summary = calibrate_all_curves(verbose=not args.quiet)
    print_curve_diagnostics(summary)

    result_dict = summary.to_dict()

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result_dict, fh, indent=2, default=str)
        print(f"\nResults written to: {out_path}")

    # Non-zero exit if any market failed
    return 0 if summary.all_converged else 1


if __name__ == "__main__":
    sys.exit(main())
