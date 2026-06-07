#!/usr/bin/env python3
"""
Phase 21 Task 3 build script — Liquidity-premium driver calibration + G-LIQ gate.

Idempotent: re-running recalibrates from the same fixture (deterministic) and
re-writes the same report. Governance persistence appends a NEW ChangeRecord /
audit entries only when --persist-governance is passed (run once per cycle).

Usage:
    PYTHONPATH=. python3 scripts/build_phase21_task3_liquidity.py [--persist-governance]
"""

from __future__ import annotations

import argparse
import sys

from par_model_v2.calibration.phase21_liquidity_calibration import (
    run_phase21_liquidity_calibration,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--persist-governance",
        action="store_true",
        help="Persist the ChangeRecord/audit entries to .claude-dev/GOVERNANCE_STORE.json",
    )
    parser.add_argument(
        "--store-path",
        default=".claude-dev/GOVERNANCE_STORE.json",
        help="Governance store path",
    )
    parser.add_argument("--docs-dir", default="docs/validation")
    args = parser.parse_args()

    report = run_phase21_liquidity_calibration(
        write_report=True,
        docs_dir=args.docs_dir,
        store_path=args.store_path,
        persist_governance=args.persist_governance,
    )

    s = report.summary
    print("Phase 21 Task 3 — Liquidity-premium driver calibration (G-LIQ)")
    print("  market               :", s.market)
    print("  kappa_l              : {:.4f} /yr (half-life {:.1f} yr)".format(s.kappa, s.half_life_years))
    print("  long-run premium (P) : {:.4f} ({:.0f} bp)".format(s.long_run_premium_p, s.long_run_premium_p * 1e4))
    print("  sigma_l              : {:.4f}".format(s.premium_vol))
    print("  lambda_l             : {:.4f}".format(s.market_price_of_liquidity_risk))
    print("  Feller ratio         : {:.2f} ({})".format(s.feller_ratio, "holds" if s.feller_ok else "violated"))
    print("  n_obs                :", s.n_obs)
    print("  G-LIQ                :", report.gate_gliq.status)
    print("  ChangeRecord         : {} ({})".format(report.change_record_id, report.change_record_status))
    print("  MR-011 / MR-012      : {} / {}".format(report.mr011_status, report.mr012_status))
    print("  governance persisted :", args.persist_governance)
    return 0 if report.gate_passes() else 1


if __name__ == "__main__":
    sys.exit(main())
