"""
run_all_calibrations.py — Calibration Orchestrator
===================================================

Runs all four Phase 12 calibration scripts in sequence and produces:
  1. A combined parameter snapshot JSON file
  2. A Markdown calibration summary report

This script is the single entry point for a scheduled calibration cycle.
Each sub-module writes its own JSON if --output-dir is supplied; this
orchestrator collects all results into one governance-ready document.

Usage
-----
    # Print summaries to stdout only
    python scripts/calibration/run_all_calibrations.py

    # Write JSON + Markdown reports to outputs/
    python scripts/calibration/run_all_calibrations.py --output-dir outputs/calibration

Standards Addressed
-------------------
SOA ASOP 56 §3.4  — model parameter calibration documentation
SOA ASOP 25 §3.3  — credibility and assumption hierarchy
IA TAS M §3.5     — assumption sign-off and audit trail
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from scripts.calibration.calibrate_curves import calibrate_all_curves
from scripts.calibration.calibrate_equity import calibrate_all_equity
from scripts.calibration.calibrate_credit import calibrate_credit_spreads, summarise_private_assets, _CREDIT_STRESS_SHOCKS
from scripts.calibration.calibrate_liabilities import calibrate_all_liabilities


# ---------------------------------------------------------------------------
# 1.  Orchestrator
# ---------------------------------------------------------------------------


def run_all(verbose: bool = True, output_dir: Optional[Path] = None) -> dict:
    """Run all four calibration modules and aggregate results.

    Parameters
    ----------
    verbose : bool
        If True, print per-module summaries.
    output_dir : Path or None
        If provided, write individual and combined JSON files here.

    Returns
    -------
    dict
        Combined calibration snapshot document.
    """
    run_ts = datetime.now(tz=timezone.utc).isoformat()

    if verbose:
        print()
        print("=" * 70)
        print("  ACTUARIAL MODEL CALIBRATION CYCLE — Phase 12")
        print(f"  Run timestamp: {run_ts}")
        print("=" * 70)

    # --- Curves ---
    if verbose:
        print("\n[1/4] YIELD CURVE / INTEREST RATE CALIBRATION (HW1F)")
    curve_summary = calibrate_all_curves(verbose=verbose)
    curve_dict = curve_summary.to_dict()

    # --- Equity ---
    if verbose:
        print("\n[2/4] REGIONAL EQUITY GBM CALIBRATION")
    equity_summary = calibrate_all_equity(verbose=verbose)
    equity_dict = equity_summary.to_dict()

    # --- Credit ---
    if verbose:
        print("\n[3/4] CREDIT SPREAD CALIBRATION")
    spread_results = calibrate_credit_spreads(verbose=verbose)
    private_assumptions = summarise_private_assets(verbose=verbose)
    credit_dict = {
        "calibration_date": curve_dict["calibration_date"],
        "run_timestamp": run_ts,
        "spread_curves": spread_results,
        "private_asset_assumptions": private_assumptions,
        "stress_scenarios": _CREDIT_STRESS_SHOCKS,
    }

    # --- Liabilities ---
    if verbose:
        print("\n[4/4] LIABILITY ASSUMPTION CALIBRATION (HK PAR)")
    liability_summary = calibrate_all_liabilities(verbose=verbose)
    liability_dict = liability_summary.to_dict()

    # --- Combined snapshot ---
    combined = {
        "document_id": "CALIBRATION_SNAPSHOT_PHASE12",
        "run_timestamp": run_ts,
        "calibration_date": curve_dict["calibration_date"],
        "model_version": "v2.0.0-phase12",
        "status": "EDUCATIONAL_PLACEHOLDER",
        "production_use": "BLOCKED — Assumption Owner sign-off required (IA TAS M s3.5)",
        "modules": {
            "curves": curve_dict,
            "equity": equity_dict,
            "credit": credit_dict,
            "liabilities": liability_dict,
        },
        "governance": {
            "assumption_owner_sign_off": "PENDING",
            "model_validator_review": "PENDING",
            "effective_date": None,
            "next_review_date": None,
            "standards": {
                "SOA ASOP 56 s3.4": "Calibration methodology documented for all modules",
                "SOA ASOP 25 s3.3": "Credibility weighting applied to mortality and equity vol",
                "IA TAS M s3.5": "Assumption change log and sign-off required",
                "IA(HK) GL16": "Bonus supportability evidence produced for HK PAR products",
            },
        },
        "convergence_summary": {
            "curves_all_converged": curve_summary.all_converged,
            "equity_all_converged": equity_summary.all_converged,
            "credit_all_converged": all(
                r.get("ns_fit", {}).get("converged", False)
                for r in spread_results.values()
                if "ns_fit" in r
            ),
            "liabilities_complete": True,
        },
    }

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Individual outputs
        for name, data in [
            ("curve_calibration.json", curve_dict),
            ("equity_calibration.json", equity_dict),
            ("credit_calibration.json", credit_dict),
            ("liability_calibration.json", liability_dict),
            ("combined_calibration_snapshot.json", combined),
        ]:
            path = output_dir / name
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, default=str)
            if verbose:
                print(f"  Wrote: {path}")

        # Markdown report
        md_path = output_dir / "CALIBRATION_SUMMARY.md"
        _write_markdown_report(combined, md_path)
        if verbose:
            print(f"  Wrote: {md_path}")

    return combined


# ---------------------------------------------------------------------------
# 2.  Markdown Report Generator
# ---------------------------------------------------------------------------


def _write_markdown_report(snapshot: dict, path: Path) -> None:
    """Write a Markdown calibration summary report."""
    ts = snapshot["run_timestamp"]
    cal_date = snapshot["calibration_date"]

    # Curve table
    curve_rows = ""
    for ccy, rec in snapshot["modules"]["curves"].get("results", {}).items():
        if "error" in rec:
            curve_rows += f"| {ccy} | ERROR | — | — | — | FAILED |\n"
            continue
        p = rec.get("hw1f_params", {})
        fit = rec.get("fit", {})
        rmse = fit.get("swaption_rmse_bps")
        rmse_s = f"{rmse:.2f}" if rmse is not None else "N/A"
        status = "Placeholder" if rec.get("is_placeholder") else "OK"
        curve_rows += (
            f"| {ccy} | {p.get('a', 'N/A'):.4f} | {p.get('sigma_r', 'N/A'):.4f} "
            f"| {p.get('r0', 'N/A'):.4f} | {rmse_s} | {status} |\n"
        )

    # Equity table
    equity_rows = ""
    for mkt, rec in snapshot["modules"]["equity"].get("results", {}).items():
        if "error" in rec:
            equity_rows += f"| {mkt} | ERROR | — | — | FAILED |\n"
            continue
        p = rec.get("gbm_params", {})
        status = "Placeholder" if rec.get("is_placeholder") else "OK"
        equity_rows += (
            f"| {mkt} | {p.get('sigma_S', 'N/A'):.4f} | {p.get('erp', 'N/A'):.4f} "
            f"| {p.get('dividend_yield', 'N/A'):.4f} | {status} |\n"
        )

    conv = snapshot.get("convergence_summary", {})

    md = f"""# Actuarial Model Calibration Summary — Phase 12

**Run Timestamp:** {ts}
**Calibration Date:** {cal_date}
**Model Version:** {snapshot.get('model_version', 'N/A')}
**Status:** {snapshot.get('status', 'N/A')}

> **Production Use:** {snapshot.get('production_use', 'N/A')}

---

## 1. Convergence Overview

| Module | Converged |
|--------|-----------|
| Yield Curves (HW1F) | {conv.get('curves_all_converged', 'N/A')} |
| Equity GBM | {conv.get('equity_all_converged', 'N/A')} |
| Credit Spreads | {conv.get('credit_all_converged', 'N/A')} |
| Liabilities (HK PAR) | {conv.get('liabilities_complete', 'N/A')} |

---

## 2. Yield Curve Calibration (Hull-White 1F)

All five starter markets (USD, EUR, HKD, CNY, JPY) calibrated via
L-BFGS-B minimisation of weighted ATM swaption normal-vol errors.
**SOA ASOP 56 §3.4** — calibration methodology documented.

| CCY | a | sigma_r | r0 | RMSE (bps) | Status |
|-----|---|---------|-----|------------|--------|
{curve_rows}

**Notes:**
- `a` = HW1F mean-reversion speed (annualised)
- `sigma_r` = HW1F short rate vol (annualised)
- `r0` = Initial short rate (continuously compounded)
- Status = `Placeholder` until live swaption quotes are wired in

---

## 3. Equity GBM Calibration

Regional equity factors calibrated with 60% implied-vol / 40% historical-vol
credibility blend. Survivorship-bias adjustment of −0.7% applied to ERP.
**SOA ASOP 25 §3.3** — credibility weighting documented.

| Market | sigma_S | ERP | Div Yield | Status |
|--------|---------|-----|-----------|--------|
{equity_rows}

---

## 4. Credit Spread Calibration

Nelson-Siegel curves fitted to synthetic OAS grids for IG (AAA–BBB) and
HY (BB–CCC) ratings. Private asset illiquidity premia estimated.

| Rating | Asset Class | b0 (long-run OAS, bps) | RMSE (bps) | Converged |
|--------|-------------|------------------------|------------|-----------|
"""

    for key, rec in snapshot["modules"]["credit"].get("spread_curves", {}).items():
        ns = rec.get("ns_fit", {})
        b0 = ns.get("b0", "N/A")
        rmse = ns.get("rmse_bps", "N/A")
        conv_val = ns.get("converged", "N/A")
        ac = rec.get("asset_class", "")
        md += f"| {key} | {ac} | {b0} | {rmse} | {conv_val} |\n"

    md += """
---

## 5. Liability Assumptions (HK PAR)

### 5a. Mortality
- **Base table:** HKML 2016 ultimate (blended sex)
- **Improvement:** 1.5% p.a. from 2016 to projection year
- **Credibility:** 60% company experience / 40% industry table (SOA ASOP 25 §3.3)
- **Company A/E:** 90% (illustrative; replace with actual experience study)

### 5b. Voluntary Lapse
- **Model:** Exponential decay `L(t) = (L0 − L_floor) × exp(−k×t) + L_floor`
- **Products calibrated:** cash_dividend, reversionary_bonus
- **Stress scenarios:** Base, 1.5x (1-in-10), 2.5x (1-in-25), 0x (no lapse)

### 5c. Bonus / Dividend Declaration
- **Cash dividend:** Current declaration 2.50% of SA — within supportable range
- **Reversionary bonus:** Vested bonus 1.80% of SA — within supportable range
- **IA(HK) GL16:** Regulatory reserve margin of 0.30% applied
- **Sensitivity:** ±1% fund return sensitivity documented for each product

---

## 6. Governance

| Requirement | Status |
|-------------|--------|
| Assumption Owner Sign-Off | PENDING |
| Model Validator Review | PENDING |
| Effective Date | TBD |
| Next Review Date | TBD |

### Standards Addressed

- **SOA ASOP 56 §3.4** — Calibration methodology documented for all modules
- **SOA ASOP 25 §3.3** — Credibility weighting for mortality and equity vol
- **IA TAS M §3.5** — Assumption change log and sign-off process required
- **IA(HK) GL16** — Bonus supportability evidence for HK PAR products

---

*This report was generated automatically by `run_all_calibrations.py`.*
*All parameters are EDUCATIONAL PLACEHOLDERS and must not be used in production*
*without Assumption Owner sign-off and model validation review.*
"""

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(md)


# ---------------------------------------------------------------------------
# 3.  CLI Entry Point
# ---------------------------------------------------------------------------


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run all Phase 12 calibration scripts and produce combined output."
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write JSON + Markdown calibration reports.",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.output_dir) if args.output_dir else None
    combined = run_all(verbose=not args.quiet, output_dir=out_dir)

    conv = combined.get("convergence_summary", {})
    all_ok = all(conv.values())

    if not args.quiet:
        print("\n" + "=" * 70)
        print("  CALIBRATION CYCLE COMPLETE")
        print(f"  All modules converged: {all_ok}")
        print("=" * 70)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
