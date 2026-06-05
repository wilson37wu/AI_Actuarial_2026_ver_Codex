#!/usr/bin/env python3
"""
Phase 18 Task 2 build script — CIR++ credit-spread calibration (idempotent).

Loads the canonical GovernanceStore, runs the CIR++ credit-spread calibration,
persists the store (APPROVED ChangeRecord + PARAM_CHANGE audit + MR-012
MITIGATED), and writes the calibration report under docs/validation/.

Idempotent: if the store already carries a CIR_credit_spread_params[CNY]
PARAM_CHANGE entry, the script reports the existing state and exits without
mutating the store (so re-runs do not append duplicate entries).

Run:
    PYTHONPATH=/var/tmp/pylibs:.  python3 scripts/build_phase18_task2_calibration.py
"""

from __future__ import annotations

import os
import sys

from par_model_v2.governance.audit_trail import EntryType, GovernanceStore
from par_model_v2.calibration.phase18_cir_calibration import run_phase18_cir_calibration

STORE_PATH = ".claude-dev/GOVERNANCE_STORE.json"
PARAM_NAME = "CIR_credit_spread_params[CNY]"


def _already_done(store: GovernanceStore) -> bool:
    return any(
        e.details.get("parameter_name") == PARAM_NAME
        for e in store.audit_trail.filter_by_type(EntryType.PARAM_CHANGE)
    )


def main() -> int:
    if not os.path.exists(STORE_PATH):
        print("ERROR: governance store not found at {}".format(STORE_PATH))
        return 2
    store = GovernanceStore.from_json(open(STORE_PATH, encoding="utf-8").read())

    if _already_done(store):
        print("IDEMPOTENT: CIR++ credit-spread calibration already recorded; no mutation.")
        try:
            mr = store.risk_register.get("MR-012").mitigation_status.value
        except KeyError:
            mr = "NOT_FOUND"
        print("MR-012 status: {}".format(mr))
        return 0

    before_audit = len(store.audit_trail.all())
    before_changes = len(store.change_records)

    report = run_phase18_cir_calibration(
        governance_store=store,
        store_path=STORE_PATH,
        write_report=True,
        docs_dir="docs/validation",
        persist_governance=True,
    )

    print("=== Phase 18 Task 2 — CIR++ credit-spread calibration ===")
    print("Gate G-CR        : {}".format(report.gate_gcr.status))
    print("ChangeRecord     : {} ({})".format(report.change_record_id[:12], report.change_record_status))
    print("MR-012           : {}".format(report.mr012_status))
    s = report.summary
    print("kappa            : {:.4f} /yr".format(s.kappa))
    print("long_run_spread  : {:.4f} ({:.0f} bp)".format(s.long_run_spread_p, s.long_run_spread_p * 1e4))
    print("spread_vol sigma : {:.4f}".format(s.spread_vol))
    print("lambda_s         : {:.4f}".format(s.market_price_of_credit_risk))
    print("Feller holds     : {}".format(s.feller_ok))
    print("audit entries    : {} -> {}".format(before_audit, len(store.audit_trail.all())))
    print("change records   : {} -> {}".format(before_changes, len(store.change_records)))
    print("audit integrity  : {}".format(store.audit_trail.verify_all()))
    print("report written   : docs/validation/PHASE18_CIR_CALIBRATION_REPORT.(md|json)")
    return 0 if report.gate_passes() and store.audit_trail.verify_all() else 1


if __name__ == "__main__":
    sys.exit(main())
