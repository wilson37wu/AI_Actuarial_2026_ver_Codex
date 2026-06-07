#!/usr/bin/env python3
"""Phase 22 Task 3 build — liquidity exposure-notional + coupling calibration (G-LIQX).

Runs the full calibration pipeline against the LIVE governance store, writes
``docs/validation/PHASE22_TASK3_LIQUIDITY_EXPOSURE_REPORT.{json,md}`` and
``docs/LIQUIDITY_EXPOSURE_COUPLING_CARD.md``, and persists the store.
Fast (no nested simulation) — fits a single sandbox wall.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from par_model_v2.calibration.phase22_liquidity_exposure_calibration import (  # noqa: E402
    run_phase22_liquidity_exposure_calibration,
)


def main() -> int:
    report = run_phase22_liquidity_exposure_calibration(
        store_path=str(ROOT / ".claude-dev" / "GOVERNANCE_STORE.json"),
        task4_report_path=ROOT / "docs" / "validation" / "PHASE21_TASK4_AGGREGATION_REPORT.json",
        write_report=True,
        docs_dir=str(ROOT / "docs" / "validation"),
        persist_governance=True,
    )
    card = ROOT / "docs" / "LIQUIDITY_EXPOSURE_COUPLING_CARD.md"
    card.write_text(report["markdown"], encoding="utf-8")

    g = report["gate_gliqx"]
    print("G-LIQX:", g["status"])
    print("exposure_notional:", report["exposure"]["exposure_notional"])
    print("estimated_couplings:", json.dumps(report["estimated_couplings"]))
    print("criteria:", json.dumps(report["criteria"]))
    print("change_record:", report["change_record_id"], report["change_record_status"])
    print("MR-011:", report["mr011_status"], "| MR-012:", report["mr012_status"])
    print("audit integrity:", report["audit_integrity_ok"],
          "| change records:", report["change_records_total"])
    return 0 if g["status"] == "PASS" and report["audit_integrity_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
