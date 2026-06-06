#!/usr/bin/env python3
"""
Phase 19 Task 5 build script — OU lapse behavioural-index calibration (idempotent).

Loads the canonical GovernanceStore, runs the lapse behavioural-index
calibration, persists the store (APPROVED ChangeRecord + PARAM_CHANGE audit +
MR-003 / MR-011 MITIGATED), and writes the calibration report under
docs/validation/.

Idempotent: if the store already carries an OU_lapse_behaviour_params[HK_PAR]
PARAM_CHANGE entry, the script reports the existing state and exits without
mutating the store (so re-runs do not append duplicate entries).

Run:
    PYTHONPATH=/var/tmp/pylibs:.  python3 scripts/build_phase19_task5_calibration.py
"""

from __future__ import annotations

import os
import sys

from par_model_v2.governance.audit_trail import EntryType, GovernanceStore
from par_model_v2.calibration.phase19_lapse_calibration import run_phase19_lapse_calibration

STORE_PATH = ".claude-dev/GOVERNANCE_STORE.json"
PARAM_NAME = "OU_lapse_behaviour_params[HK_PAR]"


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
        print("IDEMPOTENT: OU lapse behavioural-index calibration already recorded; no mutation.")
        for rid in ("MR-003", "MR-011"):
            try:
                mr = store.risk_register.get(rid).mitigation_status.value
            except KeyError:
                mr = "NOT_FOUND"
            print("{} status: {}".format(rid, mr))
        return 0

    before_audit = len(store.audit_trail.all())
    before_changes = len(store.change_records)

    report = run_phase19_lapse_calibration(
        governance_store=store,
        store_path=STORE_PATH,
        write_report=True,
        docs_dir="docs/validation",
        persist_governance=True,
    )

    print("=== Phase 19 Task 5 — OU lapse behavioural-index calibration ===")
    print("Gate G-LAPSE     : {}".format(report.gate_glapse.status))
    print("ChangeRecord     : {} ({})".format(report.change_record_id[:12], report.change_record_status))
    print("MR-003           : {}".format(report.mr003_status))
    print("MR-011           : {}".format(report.mr011_status))
    s = report.summary
    print("kappa_b          : {:.4f} /yr (half-life {:.1f} yr)".format(s.kappa, s.half_life_years))
    print("long_run_level   : {:.4f} (A/E {:.3f})".format(s.long_run_level, s.long_run_ae))
    print("behaviour_vol    : {:.4f}".format(s.behaviour_vol))
    print("stationary_std   : {:.4f}".format(s.stationary_std))
    print("audit entries    : {} -> {}".format(before_audit, len(store.audit_trail.all())))
    print("change records   : {} -> {}".format(before_changes, len(store.change_records)))
    print("audit integrity  : {}".format(store.audit_trail.verify_all()))
    print("report written   : docs/validation/PHASE19_LAPSE_CALIBRATION_REPORT.(md|json)")
    return 0 if report.gate_passes() and store.audit_trail.verify_all() else 1


if __name__ == "__main__":
    sys.exit(main())
