#!/usr/bin/env python3
"""Phase 22 Task 5 — offline-UI propagation: evidence + governance refresh.

This is NOT a model calculation. It verifies that the offline UI
(`scripts/build_ui_data.py` -> `ui_data.json` v1.4.0 + `ui_app.html`)
surfaces the Phase 22 additions — (a) the Task 1 six-driver OOS remediation
PASS (replacing the displayed honest PARTIAL), (b) the Task 2 seven-driver
OOS validation PASS, (c) the Task 3 G-LIQX calibrated liquidity exposure
notional + 7x7 couplings as a first-class calibration panel, and (d) the
Task 4 calibrated aggregation/tail read-outs — re-runs the jsdom self-test
(0 network / 0 JS errors), opens an OWNER_REVIEW ChangeRecord, appends one
governance audit entry, verifies audit-chain integrity, and writes the
Task 5 evidence report. PHASE 22 COMPLETE once this report is persisted.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase22_task5_ui_propagation.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
)

PHASE = "Phase 22: Proxy Hardening + Seven-Driver OOS Validation"
ACTOR = "AutomatedModelDev_Phase22"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_DATA = Path("ui_data.json")
UI_APP = Path("ui_app.html")
SELF_TEST = Path("scripts/ui_app_self_test.cjs")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE22_TASK5_UI_PROPAGATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE22_TASK5_UI_PROPAGATION_REPORT.md"
CHANGE_TITLE = (
    "Phase 22 Task 5 - offline-UI propagation of the calibrated seven-driver view"
)
AFFECTED_COMPONENTS = [
    "scripts/build_ui_data.py",
    "scripts/ui_app_self_test.cjs",
    "ui_data.json",
    "ui_app.html",
    "viewer_data.json",
]
STANDARD_REFERENCES = [
    "SOA ASOP 41 s3.2 (communication of actuarial findings)",
    "SOA ASOP 56 s3.5 (model output validation & presentation)",
    "IA TAS M s3.6 (reproducibility and disclosure of model results)",
]


def check_ui_contract() -> dict:
    data = json.loads(UI_DATA.read_text(encoding="utf-8"))
    cap = data.get("capital", {})
    cal = data.get("calibrations", [])
    tail = data.get("tail", {})
    verdicts = data.get("verdicts", [])
    drivers = [r.get("driver", "") for r in cal]
    vnames = [str(v.get("name") or v.get("key", "")) for v in verdicts]
    vtexts = " | ".join(str(v.get("verdict", "")) for v in verdicts)
    notional = cap.get("liquidity_exposure_notional")

    checks = {
        "contract_version": data.get("contract_version"),
        "contract_is_1_4_0": data.get("contract_version") == "1.4.0",
        "n_drivers_seven": cap.get("n_drivers") == 7,
        "aggregation_source_phase22": "PHASE22_TASK4" in str(cap.get("aggregation_source", "")),
        "liquidity_inputs_calibrated_flag": cap.get("liquidity_inputs_calibrated") is True,
        "calibrated_notional_22000": (isinstance(notional, (int, float))
                                      and abs(notional - 22000.0) < 1.0),
        "calibrated_vs_placeholder_panel": isinstance(cap.get("calibrated_vs_placeholder"), dict),
        "liquidity_scr_calibrated_45": (isinstance(cap.get("liquidity_scr"), (int, float))
                                        and abs(cap["liquidity_scr"] - 45.0533) < 0.1),
        "var_covar_scr_present": isinstance(cap.get("var_covar_scr"), (int, float)),
        "copula_scr_present": isinstance(cap.get("copula_scr"), (int, float)),
        "nested_scr_present": isinstance(cap.get("nested_scr"), (int, float)),
        "gliqx_calibration_record": any("G-LIQX" in str(r.get("gate_id", "")) for r in cal),
        "gliqx_not_placeholder": any("G-LIQX" in str(r.get("gate_id", ""))
                                     and r.get("is_placeholder") is False for r in cal),
        "tail_source_phase22": "PHASE22_TASK4" in str(tail.get("source", "")),
        "tail_converged": tail.get("converged") is True,
        "oos_remediated_pass_listed": any("REMEDIATED, Phase 22 Task 1" in n for n in vnames),
        "no_stale_six_driver_partial": not any(
            "PARTIAL" in str(v.get("verdict", "")) and "Six-driver" in str(v.get("name", ""))
            for v in verdicts),
        "seven_driver_oos_pass_listed": any("Seven-driver OOS proxy validation" in n
                                            for n in vnames),
        "gliqx_verdict_listed": any("G-LIQX" in n for n in vnames),
        "calibrated_aggregation_listed": any("G-LIQX-CALIBRATED" in n for n in vnames),
        "headline_aggregation_calibrated": "G-LIQX-CALIBRATED" in vtexts,
    }
    checks["all_passed"] = all(v is True for k, v in checks.items()
                               if k not in ("contract_version",))
    checks["capital_readouts"] = {
        "liquidity_scr": cap.get("liquidity_scr"),
        "liquidity_exposure_notional": notional,
        "var_covar_scr": cap.get("var_covar_scr"),
        "copula_scr": cap.get("copula_scr"),
        "nested_scr": cap.get("nested_scr"),
        "selected_copula": cap.get("selected_copula"),
    }
    return checks


def run_self_test() -> dict:
    proc = subprocess.run(
        ["node", str(SELF_TEST), str(UI_APP)],
        capture_output=True, text=True, timeout=120,
    )
    out = json.loads(proc.stdout)
    return {
        "ok": bool(out.get("ok")),
        "network_calls": out.get("checks", {}).get("networkCalls"),
        "js_errors": out.get("checks", {}).get("jsErrors"),
        "n_checks": len(out.get("checks", {})),
        "failed_checks": [k for k, v in out.get("checks", {}).items() if v is False],
        "phase22_checks": {
            k: out.get("checks", {}).get(k)
            for k in ("gliqxPanelPresent", "oosRemediatedPresent",
                      "sevenDriverOosPassPresent", "calibratedLiquidityPresent",
                      "sevenDriverVerdictPresent", "driverBars")
        },
    }


def apply_governance(store: GovernanceStore, ui: dict, st: dict) -> dict:
    added = False
    record_id = None
    record_status = None
    if not any(r.title == CHANGE_TITLE for r in store.change_records):
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 22 Task 5 propagated the Phase 22 hardening results to the "
                "zero-install offline UI. scripts/build_ui_data.py (contract bumped "
                "additively to v1.4.0) now surfaces: (1) the Task 1 six-driver OOS "
                "remediation PASS (OOS R2=0.9985) replacing the previously displayed "
                "honest PARTIAL; (2) the Task 2 seven-driver OOS proxy validation "
                "PASS (R2=0.9985; VaR/ES/SCR rel err 0.51%/0.18%/1.26%); (3) the "
                "Task 3 G-LIQX calibrated liquidity exposure notional (22,000, "
                "replacing the 30,000 placeholder) and 7x7 couplings as a "
                "first-class calibration-explorer panel with criteria + coupling "
                "bars; and (4) the Task 4 calibrated aggregation/tail read-outs "
                "(liquidity SCR 45.1, var-covar 28,991, gaussian copula 41,604, "
                "nested 48,707, MR-010 understatement 40.5% re-confirmed) with "
                "the calibrated-vs-placeholder deltas embedded. viewer_data.json "
                "was rebuilt so governance reflects the live store (32 change "
                "records). The UI performs no calculation; it consumes only "
                "already-produced model output JSONs."
            ),
            change_type="code_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "ui_contract": "1.3.0 (placeholder liquidity inputs; six-driver "
                               "OOS PARTIAL displayed; Phase 21 aggregation numbers)",
                "headline_verdicts": "Phase 21 Task 4 placeholder-input wording",
            },
            after_snapshot={
                "ui_contract": "1.4.0 (additive)",
                "capital_readouts": ui["capital_readouts"],
                "self_test_ok": st["ok"],
                "network_calls": st["network_calls"],
                "js_errors": st["js_errors"],
            },
            impact_assessment=(
                "Display-layer only: the UI bundler reads validation-report JSONs "
                "and performs no model calculation, so no model output changes. "
                "Additive contract bump keeps existing consumers working. Completes "
                "the Phase 22 per-task offline-UI propagation requirement; "
                "PHASE 22 COMPLETE."
            ),
            quantitative_impact=(
                "UI now displays: calibrated liquidity SCR {liq:.1f} (was 63.5 "
                "placeholder); exposure notional {notional:.0f}; var-covar {vc:.0f} "
                "vs nested {nest:.0f}; copula {cop:.0f} ({sel}); jsdom self-test ok "
                "with {nc} network calls and {je} JS errors over {n} checks."
            ).format(
                liq=ui["capital_readouts"]["liquidity_scr"],
                notional=ui["capital_readouts"]["liquidity_exposure_notional"],
                vc=ui["capital_readouts"]["var_covar_scr"],
                nest=ui["capital_readouts"]["nested_scr"],
                cop=ui["capital_readouts"]["copula_scr"],
                sel=ui["capital_readouts"]["selected_copula"],
                nc=st["network_calls"], je=st["js_errors"], n=st["n_checks"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "UI propagation verified by contract checks + jsdom self-test (0 network "
            "/ 0 JS errors); display-layer change only.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. PHASE 22 COMPLETE at the educational level; "
            "production sign-off remains withheld pending credentialled-data "
            "calibration and independent APS X2 review.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event=("ChangeRecord opened (OWNER_REVIEW) - Phase 22 Task 5 "
                       "offline-UI propagation; PHASE 22 COMPLETE"),
                details={
                    "record_id": rec.record_id,
                    "ui_contract": "1.4.0",
                    "self_test_ok": st["ok"],
                    "network_calls": st["network_calls"],
                    "js_errors": st["js_errors"],
                    "affected_components": AFFECTED_COMPONENTS,
                },
            )
        )
    else:
        for rec in store.change_records:
            if rec.title == CHANGE_TITLE:
                record_id = rec.record_id
                record_status = rec.status.value
    return {"added_change_record": added, "change_record_id": record_id,
            "change_record_status": record_status}


def main() -> int:
    ui = check_ui_contract()
    if not ui["all_passed"]:
        print("UI contract checks FAILED:",
              [k for k, v in ui.items() if v is False])
        return 1
    st = run_self_test()
    if not (st["ok"] and st["network_calls"] == 0 and st["js_errors"] == 0):
        print("Self-test FAILED:", st)
        return 1

    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_audit_before = len(store.audit_trail.all())
    n_change_before = len(store.change_records)
    gov = apply_governance(store, ui, st)
    integrity = store.audit_trail.verify_all()
    if not integrity:
        print("AUDIT INTEGRITY FAILED - store NOT saved")
        return 1
    GOV_PATH.write_text(store.to_json(), encoding="utf-8")

    report = {
        "task": "Phase 22 Task 5 - offline-UI propagation",
        "phase": PHASE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "phase22_status": "COMPLETE (Tasks 1-5)",
        "ui_contract_checks": ui,
        "self_test": st,
        "governance": {
            **gov,
            "audit_entries": f"{n_audit_before}->{len(store.audit_trail.all())}",
            "change_records": f"{n_change_before}->{len(store.change_records)}",
            "audit_integrity_verify_all": integrity,
        },
    }
    JSON_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = """# Phase 22 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** {now}
**Verdict:** PASS - **PHASE 22 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.4.0, additive)

- **Six-driver OOS remediation (Task 1):** the displayed honest PARTIAL verdict is
  replaced by the REMEDIATED PASS (OOS R2=0.9985, max |rel err| 2.02%).
- **Seven-driver OOS validation (Task 2):** new PASS verdict (R2=0.9985,
  VaR/ES/SCR rel err 0.51%/0.18%/1.26%, liquidity offset exact, leakage-free).
- **G-LIQX calibration panel (Task 3):** exposure notional {notional:,.0f}
  (placeholder 30,000 retired), six estimated couplings with recovery-tolerance
  bars, 6/6 criteria, lineage-checksummed fixture, is_placeholder=false.
- **Calibrated aggregation (Task 4):** liquidity SCR {liq:,.1f} (was 63.5);
  var-covar {vc:,.0f} vs nested {nest:,.0f} (MR-010 understatement re-confirmed);
  gaussian copula {cop:,.0f}; calibrated-vs-placeholder deltas embedded;
  tail diagnostics re-run CONVERGED.
- Headline aggregation/tail verdicts now carry the G-LIQX-CALIBRATED wording;
  `viewer_data.json` rebuilt so governance reflects the live store.

## Verification

- `ui_data.json` contract checks: ALL PASS ({nck} checks).
- jsdom self-test: **ok:true**, {nc} network calls / {je} JS errors over {nst} checks.

## Governance

- ChangeRecord `{crid}` ({crstatus}); audit entries {aud}; change records {chg};
  audit-chain integrity verify_all = {integ}.
- Production sign-off remains withheld (educational classification): residual is
  credentialled-data calibration + independent APS X2 review - not a code gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6.
""".format(
        now=report["generated_utc"],
        notional=ui["capital_readouts"]["liquidity_exposure_notional"],
        liq=ui["capital_readouts"]["liquidity_scr"],
        vc=ui["capital_readouts"]["var_covar_scr"],
        cop=ui["capital_readouts"]["copula_scr"],
        nest=ui["capital_readouts"]["nested_scr"],
        nck=sum(1 for v in ui.values() if v is True),
        nc=st["network_calls"], je=st["js_errors"], nst=st["n_checks"],
        crid=gov["change_record_id"], crstatus=gov["change_record_status"],
        aud=report["governance"]["audit_entries"],
        chg=report["governance"]["change_records"],
        integ=integrity,
    )
    MD_PATH.write_text(md, encoding="utf-8")

    print(json.dumps({
        "verdict": "PASS", "phase22": "COMPLETE",
        "change_record_id": gov["change_record_id"],
        "change_record_status": gov["change_record_status"],
        "audit": report["governance"]["audit_entries"],
        "changes": report["governance"]["change_records"],
        "integrity": integrity,
        "reports": [str(JSON_PATH), str(MD_PATH)],
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
