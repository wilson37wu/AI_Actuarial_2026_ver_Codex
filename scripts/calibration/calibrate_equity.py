"""
calibrate_equity.py — Regional Equity GBM Calibration
=======================================================

Demonstrates GBM parameter calibration for five regional equity markets:
US (S&P 500), Europe (Euro Stoxx), Hong Kong/China (HSI/CSI), Japan (TOPIX),
and Asia ex-Japan (MSCI Asia ex-JP). Uses synthetic historical return series
consistent with the Phase 8 starter equity factor fixtures.

EDUCATIONAL NOTE
----------------
Synthetic return histories are generated from the illustrative parameters in
par_model_v2/stochastic/fixtures/regional_equity_factors.json. In production,
replace with actual historical daily log-returns sourced from an approved data
vendor, reviewed by the Assumption Owner (IA TAS M §3.5).

Standards Addressed
-------------------
SOA ASOP 56 §3.4   — parameter calibration and documentation
SOA ASOP 25 §3.3   — credibility weighting (historical vs. implied vol)
IA TAS M §3.5      — assumption appropriateness sign-off
ESG limitation doc — docs/ESG_MODEL_LIMITATIONS_AND_UPGRADE_PATH.md

Usage
-----
    python scripts/calibration/calibrate_equity.py
    python scripts/calibration/calibrate_equity.py --output outputs/equity_calibration.json
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import optimize as scipy_optimize

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from par_model_v2.calibration import (
    CalibrationResult,
    GBMCalibrationInputs,
    GBMCalibrator,
)

# ---------------------------------------------------------------------------
# 1.  Synthetic Market Data Parameters
# ---------------------------------------------------------------------------

VALUATION_DATE = date(2026, 5, 30)
HISTORY_YEARS = 10        # synthetic history length
TRADING_DAYS_PER_YEAR = 252
RNG_SEED = 20260530       # reproducibility

# Market parameters used to GENERATE synthetic history
# (In production these are unknown — we calibrate to discover them)
_MARKET_PARAMS: Dict[str, dict] = {
    "US": {
        "sigma_annual": 0.185,
        "mu_annual": 0.085,   # total return (rf + erp + dividend)
        "dividend_yield": 0.016,
        "rf_annual": 0.043,
        "rate_equity_corr": -0.20,
        "implied_vol": 0.185,   # ATM 1y implied vol on valuation date
        "index_name": "S&P 500 TR proxy",
        "currency": "USD",
    },
    "EU": {
        "sigma_annual": 0.205,
        "mu_annual": 0.078,
        "dividend_yield": 0.028,
        "rf_annual": 0.018,
        "rate_equity_corr": -0.18,
        "implied_vol": 0.210,
        "index_name": "Euro Stoxx TR proxy",
        "currency": "EUR",
    },
    "HK_CN": {
        "sigma_annual": 0.260,
        "mu_annual": 0.090,
        "dividend_yield": 0.035,
        "rf_annual": 0.036,
        "rate_equity_corr": -0.12,
        "implied_vol": 0.265,
        "index_name": "HSI/CSI blend TR proxy",
        "currency": "HKD",
    },
    "JP": {
        "sigma_annual": 0.215,
        "mu_annual": 0.070,
        "dividend_yield": 0.022,
        "rf_annual": -0.001,
        "rate_equity_corr": -0.10,
        "implied_vol": 0.220,
        "index_name": "TOPIX TR proxy",
        "currency": "JPY",
    },
    "ASIA_EX_JP": {
        "sigma_annual": 0.240,
        "mu_annual": 0.086,
        "dividend_yield": 0.026,
        "rf_annual": 0.036,
        "rate_equity_corr": -0.14,
        "implied_vol": 0.245,
        "index_name": "MSCI Asia ex-JP TR proxy",
        "currency": "USD",
    },
}


# ---------------------------------------------------------------------------
# 2.  Synthetic History Generator
# ---------------------------------------------------------------------------


def _generate_synthetic_history(market: str, seed: int = RNG_SEED) -> GBMCalibrationInputs:
    """Generate synthetic daily log-return history for a market.

    The series is reproducible (fixed seed) and consistent with the market
    parameters in _MARKET_PARAMS. In production, replace this with actual
    historical data loaded from a CSV or data-vendor API.

    Parameters
    ----------
    market : str
        Market key from _MARKET_PARAMS.
    seed : int
        RNG seed for reproducibility.

    Returns
    -------
    GBMCalibrationInputs
        Calibration inputs ready for GBMCalibrator.
    """
    p = _MARKET_PARAMS[market]
    n_days = HISTORY_YEARS * TRADING_DAYS_PER_YEAR
    rng = np.random.default_rng(seed + hash(market) % 10_000)

    dt = 1.0 / TRADING_DAYS_PER_YEAR
    sigma_daily = p["sigma_annual"] * np.sqrt(dt)
    mu_daily = (p["mu_annual"] - 0.5 * p["sigma_annual"] ** 2) * dt

    # Equity log-returns
    equity_log_returns = rng.normal(mu_daily, sigma_daily, size=n_days)
    # Risk-free daily rate (flat constant — educational simplification)
    rf_daily = np.full(n_days, p["rf_annual"] * dt)

    # Monthly trailing dividend yield (illustrative: slight upward trend)
    n_months = HISTORY_YEARS * 12
    dy_monthly = np.linspace(
        p["dividend_yield"] * 0.85,
        p["dividend_yield"] * 1.05,
        n_months,
    )

    dates_daily = pd.date_range(end="2026-05-30", periods=n_days, freq="B")
    dates_monthly = pd.date_range(end="2026-05-30", periods=n_months, freq="ME")

    return GBMCalibrationInputs(
        calibration_date=VALUATION_DATE,
        equity_returns=pd.Series(equity_log_returns, index=dates_daily),
        rf_returns=pd.Series(rf_daily, index=dates_daily),
        dividend_yield_monthly=pd.Series(dy_monthly, index=dates_monthly),
        implied_vol_atm=p["implied_vol"],
        implied_vol_weight=0.60,     # 60% implied, 40% historical (SOA ASOP 25 credibility)
        erp_survivorship_adjustment=0.007,
        erp_upper_bound=0.06,
    )


# ---------------------------------------------------------------------------
# 3.  Calibration with Blended Vol and ERP Calculation
# ---------------------------------------------------------------------------


def _calibrate_single_market(market: str, verbose: bool = True) -> dict:
    """Calibrate GBM parameters for one market.

    Returns a result record dict.
    """
    p = _MARKET_PARAMS[market]
    inputs = _generate_synthetic_history(market)

    try:
        calibrator = GBMCalibrator(inputs)
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            result = calibrator.calibrate()

        if verbose:
            print(result.summary())

        # Blended vol diagnostic
        hist_vol = result.equity_vol_hist if result.equity_vol_hist else float("nan")
        impl_vol = result.equity_vol_implied if result.equity_vol_implied else float("nan")
        blended_vol = (
            inputs.implied_vol_weight * impl_vol
            + (1 - inputs.implied_vol_weight) * hist_vol
            if not (np.isnan(impl_vol) or np.isnan(hist_vol))
            else hist_vol
        )

        record = {
            "market": market,
            "index_name": p["index_name"],
            "currency": p["currency"],
            "is_placeholder": result.is_placeholder,
            "gbm_params": {
                "sigma_S": result.sigma_S,
                "erp": result.erp,
                "dividend_yield": result.dividend_yield,
                "rho": result.rho,
            },
            "calibration_diagnostics": {
                "historical_vol": round(hist_vol, 5),
                "implied_vol_atm": round(impl_vol, 5) if not np.isnan(impl_vol) else None,
                "blended_vol": round(blended_vol, 5) if not np.isnan(blended_vol) else None,
                "implied_vol_weight": inputs.implied_vol_weight,
                "survivorship_bias_adjustment": inputs.erp_survivorship_adjustment,
                "erp_upper_bound_applied": inputs.erp_upper_bound,
            },
            "warnings": [str(w.message) for w in caught_warnings],
            "notes": result.notes,
        }

    except Exception as exc:  # noqa: BLE001
        record = {
            "market": market,
            "index_name": p["index_name"],
            "currency": p["currency"],
            "error": str(exc),
            "is_placeholder": True,
        }

    return record


# ---------------------------------------------------------------------------
# 4.  Run All Markets
# ---------------------------------------------------------------------------


@dataclass
class EquityCalibrationSummary:
    """Aggregated equity calibration results."""
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
                "SOA ASOP 56 s3.4": "GBM calibration: historical vol + ATM implied vol blend (60/40 default)",
                "SOA ASOP 25 s3.3": "Credibility weighting: 60% implied vol; survivorship-bias adjustment -0.7%",
                "IA TAS M s3.5": "Assumption Owner sign-off required before production use",
            },
        }


def calibrate_all_equity(verbose: bool = True) -> EquityCalibrationSummary:
    """Run GBM calibration for all five regional equity markets."""
    run_ts = datetime.now(tz=timezone.utc).isoformat()
    summary = EquityCalibrationSummary(
        calibration_date=VALUATION_DATE,
        run_timestamp=run_ts,
    )

    all_ok = True

    for market in ["US", "EU", "HK_CN", "JP", "ASIA_EX_JP"]:
        if verbose:
            print(f"\n{'='*60}")
            print(f"  Calibrating GBM Equity — {market}")
            print(f"{'='*60}")

        record = _calibrate_single_market(market, verbose=verbose)
        summary.results[market] = record

        if record.get("is_placeholder") or "error" in record:
            all_ok = False

    summary.all_converged = all_ok
    summary.notes = (
        "GBM equity calibration complete for all five markets. "
        "is_placeholder=True means GBMCalibrator returned placeholder parameters "
        "because live historical data is not available in this educational environment. "
        "Replace synthetic history with live data before production use. "
        "SOA ASOP 25 s3.3 credibility weighting: 60% implied vol, 40% historical vol. "
        "Survivorship bias adjustment of -0.7% applied to raw ERP estimates."
    )

    if verbose:
        print(f"\n{'='*60}")
        print("  EQUITY CALIBRATION SUMMARY")
        print(f"{'='*60}")
        _print_equity_diagnostics(summary)

    return summary


def _print_equity_diagnostics(summary: EquityCalibrationSummary) -> None:
    """Print text-based equity calibration diagnostics."""
    print(f"\n{'MARKET':<14} {'sigma_S':>8} {'ERP':>8} {'DivYld':>8} {'rho':>7} {'Vol(hist)':>10} {'Status':<12}")
    print("-" * 75)
    for market, rec in summary.results.items():
        if "error" in rec:
            print(f"{market:<14} {'ERROR'}")
            continue
        params = rec.get("gbm_params", {})
        diag = rec.get("calibration_diagnostics", {})
        sigma = params.get("sigma_S", float("nan"))
        erp = params.get("erp", float("nan"))
        dy = params.get("dividend_yield", float("nan"))
        rho = params.get("rho", float("nan"))
        hvol = diag.get("historical_vol", float("nan"))
        status = "PLACEHOLDER" if rec.get("is_placeholder") else "OK"
        print(f"{market:<14} {sigma:>8.4f} {erp:>8.4f} {dy:>8.4f} {rho:>7.4f} {hvol:>10.4f} {status:<12}")
    print("-" * 75)
    print()
    print("Notes:")
    print("  sigma_S    = Calibrated equity vol (blended historical + implied, annualised)")
    print("  ERP        = Equity risk premium (P-measure excess return, bias-adjusted)")
    print("  DivYld     = Calibrated dividend yield (trailing 12-month average)")
    print("  rho        = Rate-equity correlation (Pearson)")
    print("  Vol(hist)  = Realised historical vol (annualised)")
    print()
    print("SOA ASOP 56 s3.4 — Parameters documented with source and calibration method.")
    print("SOA ASOP 25 s3.3 — Credibility weighting applied; survivorship bias -0.7%.")


# ---------------------------------------------------------------------------
# 5.  CLI Entry Point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regional equity GBM calibration — Phase 12 educational script."
    )
    parser.add_argument("--output", default=None, help="Path to write JSON results.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    summary = calibrate_all_equity(verbose=not args.quiet)

    if not args.quiet:
        print(f"\nAll converged: {summary.all_converged}")

    result_dict = summary.to_dict()

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result_dict, fh, indent=2, default=str)
        print(f"Results written to: {out_path}")

    return 0 if summary.all_converged else 1


if __name__ == "__main__":
    sys.exit(main())
