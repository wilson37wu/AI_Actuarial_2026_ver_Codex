"""
Phase 13 HW1F Calibration — Live CNY/HKD Swaption Data Integration
====================================================================

This module closes production gates G-02 and G-12 by:
  1. Loading CNY and HKD swaption surfaces from versioned file fixtures
     (``FileBasedSwaptionSource``), replacing all educational placeholders.
  2. Running ``HullWhiteCalibrator`` for both markets via the
     ``LiveSwaptionDataLoader`` integration layer.
  3. Evaluating production gates G-02 (calibrated parameters) and G-12
     (data lineage) and recording results.
  4. Logging a ``ChangeRecord`` to ``GovernanceStore`` (MR-002 data change).
  5. Writing a calibration report to ``docs/PHASE13_HW1F_CALIBRATION_REPORT.md``.

Entry points
------------
run_phase13_hw1f_calibration()
    Full pipeline.  Returns ``Phase13CalibrationReport``.

Phase13CalibrationReport
    Dataclass holding both markets' results, gate statuses, lineage records,
    and a markdown summary.  Serialisable to JSON.

Standards
---------
SOA ASOP 56 §3.4   — calibration methodology documentation
SOA ASOP 25 §3.3   — credibility hierarchy
IA TAS M §3.5      — assumption appropriateness and sign-off
IA TAS M §3.6      — traceability: source → parameter → output
IFoA APS X2 §4.2   — independent review of material assumption changes

PRODUCTION USE RESTRICTION
--------------------------
Results are based on educational fixture data.  Replace
``FileBasedSwaptionSource`` with a credentialled live-API source and re-run
the full sign-off workflow before any regulatory submission.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from par_model_v2.calibration.calibration_framework import (
    CalibrationResult,
    HullWhiteCalibrator,
)
from par_model_v2.calibration.market_data_source import (
    DataLineageRecord,
    LiveSwaptionDataLoader,
    ProductionGateStatus,
    build_file_based_loader,
    evaluate_g02_gate,
    evaluate_g12_gate,
)
from par_model_v2.governance.audit_trail import ChangeRecord, GovernanceStore


# ---------------------------------------------------------------------------
# 1. Per-market calibration result wrapper
# ---------------------------------------------------------------------------

@dataclass
class MarketCalibrationSummary:
    """Calibration result and metadata for one currency market.

    Attributes
    ----------
    market : str
        "CNY" or "HKD".
    calibration_date : str
        ISO 8601 date.
    a : float
        Calibrated mean-reversion speed.
    sigma_r : float
        Calibrated short-rate volatility.
    r0 : float
        Initial short rate (from market data).
    swaption_rmse_bps : Optional[float]
        Swaption vol RMSE in basis points; None if not computed.
    max_swaption_error_bps : Optional[float]
        Maximum absolute vol error in bps.
    converged : bool
        Whether the L-BFGS-B optimizer converged.
    notes : str
        Calibrator notes (convergence message, warnings).
    is_placeholder : bool
        True if result still relies on placeholder values.
    lineage : DataLineageRecord
        Provenance of the swaption data used.
    """
    market: str
    calibration_date: str
    a: float
    sigma_r: float
    r0: float
    swaption_rmse_bps: Optional[float]
    max_swaption_error_bps: Optional[float]
    converged: bool
    notes: str
    is_placeholder: bool
    lineage: DataLineageRecord

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["lineage"] = self.lineage.to_dict()
        return d

    @classmethod
    def from_calibration_result(
        cls,
        market: str,
        result: CalibrationResult,
        lineage: DataLineageRecord,
    ) -> "MarketCalibrationSummary":
        converged = "converged=True" in (result.notes or "")
        return cls(
            market=market,
            calibration_date=result.calibration_date.isoformat(),
            a=result.a,
            sigma_r=result.sigma_r,
            r0=result.r0,
            swaption_rmse_bps=result.swaption_rmse_bps,
            max_swaption_error_bps=result.max_swaption_error_bps,
            converged=converged,
            notes=result.notes or "",
            is_placeholder=result.is_placeholder,
            lineage=lineage,
        )


# ---------------------------------------------------------------------------
# 2. Full report container
# ---------------------------------------------------------------------------

@dataclass
class Phase13CalibrationReport:
    """Complete Phase 13 HW1F calibration report for CNY and HKD.

    Attributes
    ----------
    run_timestamp : str
        ISO 8601 UTC timestamp of this run.
    cny : MarketCalibrationSummary
        CNY calibration results.
    hkd : MarketCalibrationSummary
        HKD calibration results.
    gate_g02 : ProductionGateStatus
        G-02 gate evaluation result.
    gate_g12 : ProductionGateStatus
        G-12 gate evaluation result.
    change_record_id : str
        ID of the ChangeRecord logged in GovernanceStore.
    markdown_report : str
        Human-readable markdown summary.
    """
    run_timestamp: str
    cny: MarketCalibrationSummary
    hkd: MarketCalibrationSummary
    gate_g02: ProductionGateStatus
    gate_g12: ProductionGateStatus
    change_record_id: str
    markdown_report: str = field(default="", repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_timestamp": self.run_timestamp,
            "cny": self.cny.to_dict(),
            "hkd": self.hkd.to_dict(),
            "gate_g02": self.gate_g02.to_dict(),
            "gate_g12": self.gate_g12.to_dict(),
            "change_record_id": self.change_record_id,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def gates_all_pass(self) -> bool:
        return self.gate_g02.status == "PASS" and self.gate_g12.status == "PASS"


# ---------------------------------------------------------------------------
# 3. Core calibration runner
# ---------------------------------------------------------------------------

def _calibrate_one_market(
    loader: LiveSwaptionDataLoader,
) -> tuple[MarketCalibrationSummary, DataLineageRecord]:
    """Load data and run HW1F calibration for one market.

    Returns
    -------
    summary : MarketCalibrationSummary
    lineage : DataLineageRecord
    """
    inputs, lineage = loader.load()
    calibrator = HullWhiteCalibrator(inputs)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result: CalibrationResult = calibrator.calibrate()
    # Append any calibration warnings to notes
    if caught:
        extra = "; ".join(str(w.message) for w in caught)
        result = CalibrationResult(
            calibration_date=result.calibration_date,
            a=result.a,
            sigma_r=result.sigma_r,
            lambda_r=result.lambda_r,
            r0=result.r0,
            swaption_fit_table=result.swaption_fit_table,
            swaption_rmse_bps=result.swaption_rmse_bps,
            max_swaption_error_bps=result.max_swaption_error_bps,
            notes=(result.notes or "") + " | WARNINGS: " + extra,
            is_placeholder=result.is_placeholder,
        )
    summary = MarketCalibrationSummary.from_calibration_result(
        loader.market, result, lineage
    )
    return summary, lineage


def _build_change_record(
    cny: MarketCalibrationSummary,
    hkd: MarketCalibrationSummary,
    gate_g02: ProductionGateStatus,
    gate_g12: ProductionGateStatus,
) -> ChangeRecord:
    """Create a ChangeRecord (MR-002) for the GovernanceStore."""
    return ChangeRecord.create(
        title="MR-002: HW1F parameters updated to market-calibrated values (CNY + HKD)",
        description=(
            "Phase 13 Task 1: Replaced educational HW1F placeholder parameters with "
            "market-calibrated values derived from representative CNY onshore IRS swaption "
            "surface and HKD HIBOR IRS swaption surface as of 2026-01-01. "
            "FileBasedSwaptionSource used; production deployment requires live API credentials. "
            f"G-02 gate: {gate_g02.status}. G-12 gate: {gate_g12.status}."
        ),
        change_type="assumption_change",
        affected_components=[
            "par_model_v2/calibration/market_data_source.py",
            "par_model_v2/calibration/phase13_hw1f_calibration.py",
            "par_model_v2/calibration/fixtures/cny_swaption_surface_20260101.json",
            "par_model_v2/calibration/fixtures/hkd_swaption_surface_20260101.json",
            "par_model_v2/stochastic/esg_process.py (HullWhiteParams)",
        ],
        standard_references=[
            "SOA ASOP 56 §3.4",
            "SOA ASOP 25 §3.3",
            "IA TAS M §3.5",
            "IA TAS M §3.6",
            "IFoA APS X2 §4.2",
        ],
        before_snapshot={
            "CNY_a": 0.10, "CNY_sigma_r": 0.012,
            "HKD_a": 0.10, "HKD_sigma_r": 0.012,
            "source": "educational placeholder",
        },
        after_snapshot={
            "CNY_a": round(cny.a, 6),
            "CNY_sigma_r": round(cny.sigma_r, 6),
            "CNY_r0": round(cny.r0, 6),
            "CNY_rmse_bps": round(cny.swaption_rmse_bps or 0, 3),
            "HKD_a": round(hkd.a, 6),
            "HKD_sigma_r": round(hkd.sigma_r, 6),
            "HKD_r0": round(hkd.r0, 6),
            "HKD_rmse_bps": round(hkd.swaption_rmse_bps or 0, 3),
            "source": "FileBasedSwaptionSource (educational fixture)",
        },
        impact_assessment=(
            "Replacing placeholder parameters with market-calibrated values will affect "
            "HW1F path distributions, discount factors, TVOG calculations, and ALM "
            "rebalancing decisions. CNY swaption RMSE and HKD swaption RMSE are reported "
            "for quantitative materiality assessment."
        ),
        quantitative_impact=(
            f"CNY swaption RMSE={cny.swaption_rmse_bps:.2f} bps; "
            f"HKD swaption RMSE={hkd.swaption_rmse_bps:.2f} bps. "
            "TVOG sensitivity to be quantified in Phase 13 Task 3."
        ) if (cny.swaption_rmse_bps is not None and hkd.swaption_rmse_bps is not None) else None,
        author="AutomatedModelDev_Phase13",
        phase="Phase 13: Production Readiness and Live Market Integration",
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )


def _build_markdown_report(
    report: Phase13CalibrationReport,
) -> str:
    """Render a markdown calibration report."""
    ts = report.run_timestamp[:19].replace("T", " ") + " UTC"
    g02_icon = "✅" if report.gate_g02.status == "PASS" else "❌"
    g12_icon = "✅" if report.gate_g12.status == "PASS" else "❌"

    def fmt_summary(s: MarketCalibrationSummary) -> str:
        conv = "✅ converged" if s.converged else "⚠️ did not converge"
        rmse_str = f"{s.swaption_rmse_bps:.2f} bps" if s.swaption_rmse_bps is not None else "N/A"
        max_err = f"{s.max_swaption_error_bps:.2f} bps" if s.max_swaption_error_bps is not None else "N/A"
        placeholder_str = "❌ placeholder" if s.is_placeholder else "✅ calibrated"
        return f"""
### {s.market} Results

| Parameter | Value |
|-----------|-------|
| Calibration date | {s.calibration_date} |
| Mean-reversion speed `a` | {s.a:.6f} |
| Short-rate volatility `σ_r` | {s.sigma_r:.6f} |
| Initial short rate `r₀` | {s.r0:.4f} ({s.r0*100:.2f}%) |
| Swaption RMSE | {rmse_str} |
| Max swaption error | {max_err} |
| Optimizer | {conv} |
| Parameter status | {placeholder_str} |
| Calibration notes | {s.notes[:200]} |

**Data Lineage (G-12)**

| Field | Value |
|-------|-------|
| Lineage ID | `{s.lineage.lineage_id}` |
| Source type | {s.lineage.source_type} |
| Source detail | `{s.lineage.source_detail[-60:]}` |
| Fixture version | {s.lineage.fixture_version} |
| Approved by | {s.lineage.approved_by} |
| SHA-256 | `{s.lineage.sha256_checksum[:32]}…` |
"""

    return f"""# Phase 13 HW1F Calibration Report
## CNY and HKD Swaption Surface — Live Market Data Integration

**Generated:** {ts}
**Phase:** Phase 13: Production Readiness and Live Market Integration
**Task:** Wire live CNY/HKD swaption data source and re-run HW1F calibration (G-02, G-12)

---

## Production Gate Status

| Gate | Description | Status | Evidence |
|------|-------------|--------|----------|
| G-02 | HW1F calibrated to market data | {g02_icon} {report.gate_g02.status} | {report.gate_g02.evidence[:120]} |
| G-12 | Calibration data lineage documented | {g12_icon} {report.gate_g12.status} | {report.gate_g12.evidence[:120]} |

**Overall gates pass:** {"YES ✅" if report.gates_all_pass() else "NO ❌"}

---

## Calibration Results
{fmt_summary(report.cny)}
{fmt_summary(report.hkd)}

---

## GovernanceStore Change Record

ChangeRecord ID: `{report.change_record_id}`
Status: DRAFT (submit for peer review via `ChangeRecord.submit_for_peer_review()`)
Peer reviewer: APS X2 Independent Reviewer
Assumption owner: Chief Actuary

---

## Standards Alignment

| Standard | Requirement | Status |
|----------|-------------|--------|
| SOA ASOP 56 §3.4 | Calibration methodology documented | ✅ Implemented |
| SOA ASOP 25 §3.3 | Credibility hierarchy for parameters | ✅ File fixture with provenance |
| IA TAS M §3.5 | Assumption sign-off workflow | ⏳ DRAFT — awaiting APS X2 peer review |
| IA TAS M §3.6 | Source-to-output traceability | ✅ DataLineageRecord attached |
| IFoA APS X2 §4.2 | Independent review of material changes | ⏳ Reviewer assigned, review pending |

---

## Limitations and Next Steps

1. **Live API integration pending:** File fixture is a representative educational proxy.
   Replace `FileBasedSwaptionSource` with a credentialled Bloomberg/CFETS connector
   and re-run calibration before any regulatory submission.
2. **Negative-rate robustness:** CNY `r₀` is above zero; the HW1F normal-vol Bachelier
   framework handles near-zero rates correctly but should be stress-tested at r₀ = 0.
3. **Sign-off required:** ChangeRecord MR-002 is in DRAFT. Submit for APS X2 peer review
   and Chief Actuary sign-off before promoting to production.
4. **G2++ upgrade path:** For HKD, consider upgrading to G2++ (two-factor) for better
   humped term-structure fit. Implementation available in `G2PlusRateProcess`.
5. **Next Phase 13 task:** Implement dynamic lapse function calibrated to HK PAR experience
   (G-04, G-11).

---

*PRODUCTION USE RESTRICTION: This report is based on educational fixture data and is not
suitable for regulatory reporting or commercial pricing without live-data re-calibration
and full sign-off per IA TAS M §3.5 and IFoA APS X2.*
"""


# ---------------------------------------------------------------------------
# 4. Main entry point
# ---------------------------------------------------------------------------

def run_phase13_hw1f_calibration(
    fixture_dir: Optional["str | Path"] = None,
    as_of_date: str = "20260101",
    governance_store: Optional[GovernanceStore] = None,
    report_output_path: Optional["str | Path"] = None,
) -> Phase13CalibrationReport:
    """Run Phase 13 HW1F calibration for CNY and HKD.

    Parameters
    ----------
    fixture_dir : str or Path, optional
        Directory containing swaption fixture JSON files.  Defaults to
        ``par_model_v2/calibration/fixtures/``.
    as_of_date : str
        Date suffix for fixture filename lookup, e.g. "20260101".
    governance_store : GovernanceStore, optional
        If provided, a ChangeRecord is added.  If None, a fresh store is
        created locally (not persisted).
    report_output_path : str or Path, optional
        If provided, write markdown report to this path.

    Returns
    -------
    Phase13CalibrationReport
        Full results including gate statuses, lineage records, and markdown.

    Raises
    ------
    RuntimeError
        If both CNY and HKD calibrations fail to produce non-placeholder results.
    """
    run_ts = datetime.now(timezone.utc).isoformat()

    # -- Step 1: Calibrate CNY --
    cny_loader = build_file_based_loader("CNY", fixture_dir=fixture_dir, as_of_date=as_of_date)
    cny_summary, cny_lineage = _calibrate_one_market(cny_loader)

    # -- Step 2: Calibrate HKD --
    hkd_loader = build_file_based_loader("HKD", fixture_dir=fixture_dir, as_of_date=as_of_date)
    hkd_summary, hkd_lineage = _calibrate_one_market(hkd_loader)

    # Sanity check: at least one market must succeed
    if cny_summary.is_placeholder and hkd_summary.is_placeholder:
        raise RuntimeError(
            "Both CNY and HKD calibrations returned placeholder results. "
            "Check fixture files and optimizer convergence."
        )

    # -- Step 3: Evaluate production gates --
    gate_g02 = evaluate_g02_gate(
        cny_result_is_placeholder=cny_summary.is_placeholder,
        cny_rmse_bps=cny_summary.swaption_rmse_bps,
        hkd_result_is_placeholder=hkd_summary.is_placeholder,
        hkd_rmse_bps=hkd_summary.swaption_rmse_bps,
    )
    gate_g12 = evaluate_g12_gate([cny_lineage, hkd_lineage])

    # -- Step 4: Log ChangeRecord --
    if governance_store is None:
        governance_store = GovernanceStore()
    cr = _build_change_record(cny_summary, hkd_summary, gate_g02, gate_g12)
    governance_store.add_change_record(cr)

    # -- Step 5: Assemble report --
    report = Phase13CalibrationReport(
        run_timestamp=run_ts,
        cny=cny_summary,
        hkd=hkd_summary,
        gate_g02=gate_g02,
        gate_g12=gate_g12,
        change_record_id=cr.record_id,
    )
    report.markdown_report = _build_markdown_report(report)

    # -- Step 6: Write report if path provided --
    if report_output_path is not None:
        report_path = Path(report_output_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report.markdown_report, encoding="utf-8")
        # Also write JSON companion
        json_path = report_path.with_suffix(".json")
        json_path.write_text(report.to_json(), encoding="utf-8")

    return report


# ---------------------------------------------------------------------------
# 5. CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    output_path = Path(__file__).parents[2] / "docs" / "PHASE13_HW1F_CALIBRATION_REPORT.md"
    print(f"Running Phase 13 HW1F calibration → {output_path}", flush=True)
    rpt = run_phase13_hw1f_calibration(report_output_path=output_path)
    print(f"CNY: a={rpt.cny.a:.6f}, sigma_r={rpt.cny.sigma_r:.6f}, RMSE={rpt.cny.swaption_rmse_bps:.2f}bps")
    print(f"HKD: a={rpt.hkd.a:.6f}, sigma_r={rpt.hkd.sigma_r:.6f}, RMSE={rpt.hkd.swaption_rmse_bps:.2f}bps")
    print(f"G-02: {rpt.gate_g02.status} | G-12: {rpt.gate_g12.status}")
    print(f"ChangeRecord: {rpt.change_record_id}")
    sys.exit(0 if rpt.gates_all_pass() else 1)
