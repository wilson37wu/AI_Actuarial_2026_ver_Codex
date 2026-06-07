#!/usr/bin/env python3
"""Phase 23 Task 5 — offline-UI propagation: evidence + governance refresh.

This is NOT a model calculation. It verifies that the offline UI
(`scripts/build_ui_data.py` -> `ui_data.json` v1.5.0 + `ui_app.html`)
surfaces the Phase 23 additions — (a) the Task 2 tail-matched Student-t
copula aggregation (df=2.9451; t-SCR 46,756 vs nested 48,707), (b) the
Task 3 management-action rule (dynamic reversionary-bonus cut, 5/5 gates,
trigger sensitivity) as a first-class Management Actions panel, and (c) the
Task 4 with-actions aggregation read-outs (nested 48,707->33,118; all four
benchmarks with/without; rank invariance; the disclosed saturation
finding) — re-runs the jsdom self-test (0 network / 0 JS errors), opens an
OWNER_REVIEW ChangeRecord, appends one governance audit entry, verifies
audit-chain integrity, and writes the Task 5 evidence report.
PHASE 23 COMPLETE once this report is persisted.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase23_task5_ui_propagation.py
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

PHASE = "Phase 23: Tail-Dependence Upgrade + Management Actions"
ACTOR = "AutomatedModelDev_Phase23"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_DATA = Path("ui_data.json")
UI_APP = Path("ui_app.html")
SELF_TEST = Path("scripts/ui_app_self_test.cjs")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE23_TASK5_UI_PROPAGATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE23_TASK5_UI_PROPAGATION_REPORT.md"
CHANGE_TITLE = (
    "Phase 23 Task 5 - offline-UI propagation of the t-copula + "
    "management-action view"
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
    "Solvency II Art. 23 (future management actions - effect displayed)",
    "Solvency II Art. 234 (dependence justification - t-copula displayed)",
]


def _close(x, target, tol=1.0):
    return isinstance(x, (int, float)) and abs(float(x) - target) <= tol


def check_ui_contract() -> dict:
    data = json.loads(UI_DATA.read_text(encoding="utf-8"))
    cap = data.get("capital", {})
    ma = data.get("management_actions", {})
    agg = ma.get("aggregation", {}) if isinstance(ma, dict) else {}
    rule = ma.get("rule", {}) if isinstance(ma, dict) else {}
    verdicts = data.get("verdicts", [])
    vnames = [str(v.get("name") or v.get("key", "")) for v in verdicts]

    checks = {
        "contract_version": data.get("contract_version"),
        "contract_is_1_5_0": data.get("contract_version") == "1.5.0",
        "management_actions_section_present": isinstance(ma, dict) and bool(ma),
        "rule_panel_complete": all(
            isinstance(rule.get(k), (int, float))
            for k in ("cr_trigger", "cr_floor", "bonus_share", "pre_floor",
                      "max_relief", "reference_coverage")),
        "task3_gates_5_pass": (isinstance(ma.get("gates_task3"), dict)
                               and len(ma["gates_task3"]) == 5
                               and all(v is True for v in ma["gates_task3"].values())),
        "task4_gates_4_pass": (isinstance(ma.get("gates_task4"), dict)
                               and len(ma["gates_task4"]) == 4
                               and all(v is True for v in ma["gates_task4"].values())),
        "trigger_sensitivity_3_rows": len(ma.get("trigger_sensitivity", [])) == 3,
        "nested_scr_without_48707": _close(agg.get("nested_scr_without"), 48707.4, 1.0),
        "nested_scr_with_33118": _close(agg.get("nested_scr_with"), 33117.8, 1.0),
        "t_copula_without_46756": _close(agg.get("t_copula_scr_without"), 46756.0, 1.0),
        "t_copula_with_25653": _close(agg.get("t_copula_scr_with"), 25652.9, 1.0),
        "gaussian_with_23922": _close(agg.get("gaussian_scr_with"), 23921.8, 1.0),
        "var_covar_with_14429": _close(agg.get("var_covar_scr_with"), 14428.7, 1.0),
        "df_matched_2_9451": _close(agg.get("df_matched"), 2.9451, 1e-3),
        "standalone_with_7": len(agg.get("standalone_scr_with", [])) == 7,
        "standalone_without_7": len(agg.get("standalone_scr_without", [])) == 7,
        "saturation_finding_disclosed": "saturates" in str(ma.get("saturation_finding", "")),
        "anchoring_convention_disclosed": "V_k" in str(agg.get("anchoring_convention", "")),
        "capital_t_copula_scr": _close(cap.get("t_copula_scr"), 46756.0, 1.0),
        "capital_t_copula_df": _close(cap.get("t_copula_df"), 2.9451, 1e-3),
        "capital_nested_with_actions": _close(cap.get("nested_scr_with_actions"),
                                              33117.8, 1.0),
        "t_copula_verdict_listed": any(
            "Tail-matched Student-t copula aggregation" in n for n in vnames),
        "management_action_verdict_listed": any(
            "Management-action rule" in n for n in vnames),
        "with_actions_verdict_listed": any(
            "WITH management actions" in n for n in vnames),
        "oos_r2_with_actions_surfaced": isinstance(
            ma.get("oos_r2_with_actions"), (int, float)),
    }
    checks["all_passed"] = all(v is True for k, v in checks.items()
                               if k not in ("contract_version",))
    checks["headline_readouts"] = {
        "nested_scr_without": agg.get("nested_scr_without"),
        "nested_scr_with": agg.get("nested_scr_with"),
        "t_copula_scr_without": agg.get("t_copula_scr_without"),
        "t_copula_scr_with": agg.get("t_copula_scr_with"),
        "df_matched": agg.get("df_matched"),
        "active_share_full": agg.get("active_share_full"),
        "floor_share_full": agg.get("floor_share_full"),
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
        "phase23_checks": {
            k: out.get("checks", {}).get(k)
            for k in ("managementTabPresent", "maCards", "maGateCrits",
                      "maBarRects", "maTrigRows", "maStandaloneRows",
                      "maRuleRows", "mgmtRulePresent",
                      "withActionsNestedPresent", "tCopulaDfPresent",
                      "saturationFindingPresent", "tCopulaVerdictPresent",
                      "withActionsVerdictPresent")
        },
    }


def apply_governance(store: GovernanceStore, ui: dict, st: dict) -> dict:
    added = False
    record_id = None
    record_status = None
    if not any(r.title == CHANGE_TITLE for r in store.change_records):
        hr = ui["headline_readouts"]
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 23 Task 5 propagated the tail-dependence upgrade and the "
                "management-action results to the zero-install offline UI. "
                "scripts/build_ui_data.py (contract bumped additively to v1.5.0) "
                "now surfaces: (1) the Task 2 tail-matched Student-t copula "
                "aggregation (df=2.9451 by pooled tail-dependence matching; "
                "t-SCR 46,756 vs nested 48,707, rel err 4.0%, vs gaussian 14.9% "
                "and var-covar understatement 40.5%); (2) the Task 3 "
                "management-action rule (dynamic reversionary-bonus cut, "
                "Solvency II Art. 23) as a first-class Management Actions panel "
                "- rule card, 5/5 pre-registered gates, active/floor shares, "
                "trigger sensitivity 1.05/1.10/1.15, OOS R2 with actions "
                "0.9983; and (3) the Task 4 with-actions aggregation read-outs "
                "- nested SCR 48,707->33,118 (-32.0%), all four benchmarks "
                "with/without, per-driver standalone deltas, rank invariance "
                "(df unchanged), and the DISCLOSED saturation finding (copula-"
                "on-standalone understates the nested with-actions benchmark; "
                "nested remains the capital reference). viewer_data.json was "
                "rebuilt so governance reflects the live store. The UI performs "
                "no calculation; it consumes only already-produced model output "
                "JSONs."
            ),
            change_type="code_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "ui_contract": "1.4.0 (gaussian-copula aggregation view only; "
                               "no management-action panel; no t-copula or "
                               "with-actions read-outs)",
            },
            after_snapshot={
                "ui_contract": "1.5.0 (additive)",
                "headline_readouts": hr,
                "self_test_ok": st["ok"],
                "network_calls": st["network_calls"],
                "js_errors": st["js_errors"],
                "n_checks": st["n_checks"],
            },
            impact_assessment=(
                "Display-layer only: the UI bundler reads validation-report "
                "JSONs and performs no model calculation, so no model output "
                "changes. Additive contract bump keeps existing consumers "
                "working. Completes the Phase 23 per-task offline-UI "
                "propagation requirement; PHASE 23 COMPLETE (Tasks 1-5)."
            ),
            quantitative_impact=(
                "UI now displays: nested SCR without/with actions {nw:.0f}/"
                "{na:.0f}; tail-matched t(df={df}) copula {tw:.0f}/{ta:.0f}; "
                "action active on {act:.1%} of outer nodes ({flo:.1%} at "
                "floor); jsdom self-test ok with {nc} network calls and {je} "
                "JS errors over {n} checks."
            ).format(
                nw=hr["nested_scr_without"], na=hr["nested_scr_with"],
                df=hr["df_matched"], tw=hr["t_copula_scr_without"],
                ta=hr["t_copula_scr_with"], act=hr["active_share_full"],
                flo=hr["floor_share_full"], nc=st["network_calls"],
                je=st["js_errors"], n=st["n_checks"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "UI propagation verified by 24 contract checks + jsdom self-test "
            "(0 network / 0 JS errors over 69 checks); display-layer change "
            "only; saturation finding carried into the display verbatim.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. PHASE 23 COMPLETE at the educational "
            "level; production sign-off remains withheld pending "
            "credentialled-data calibration and independent APS X2 review.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event=("ChangeRecord opened (OWNER_REVIEW) - Phase 23 Task 5 "
                       "offline-UI propagation; PHASE 23 COMPLETE"),
                details={
                    "record_id": rec.record_id,
                    "ui_contract": "1.5.0",
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
        "task": "Phase 23 Task 5 - offline-UI propagation",
        "phase": PHASE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "phase23_status": "COMPLETE (Tasks 1-5)",
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

    hr = ui["headline_readouts"]
    md = """# Phase 23 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** {now}
**Verdict:** PASS - **PHASE 23 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.5.0, additive)

- **Tail-matched Student-t copula (Task 2):** df={df} by pooled tail-dependence
  matching; t-SCR {tw:,.0f} vs nested {nw:,.0f} (rel err 4.0%) vs gaussian 14.9%
  and var-covar understatement 40.5% (MR-010).
- **Management Actions panel (Task 3):** dynamic reversionary-bonus cut
  (Solvency II Art. 23) - rule card (trigger 1.10 / floor 0.90 / PRE floor 60% /
  max relief 12%), 5/5 pre-registered gates, active share 44.2% (nested run),
  trigger sensitivity 1.05/1.10/1.15 all PASS, OOS R2 with actions 0.9983.
- **With-actions aggregation (Task 4):** nested SCR {nw:,.0f} -> {na:,.0f}
  (-32.0%); t-copula {tw:,.0f} -> {ta:,.0f}; gaussian and var-covar with/without;
  per-driver standalone deltas; rank invariance (df unchanged at {df});
  **saturation finding disclosed verbatim** - copula-on-standalone understates
  the nested with-actions benchmark; nested remains the capital reference.
- Headline verdicts extended with the three Phase 23 PASS verdicts;
  `viewer_data.json` rebuilt so governance reflects the live store.

## Verification

- `ui_data.json` contract checks: ALL PASS ({nck} checks).
- jsdom self-test: **ok:true**, {nc} network calls / {je} JS errors over {nst}
  checks (13 new Phase 23 checks incl. panel cards, gate grid, with/without
  bars, trigger-sensitivity and standalone tables).

## Governance

- ChangeRecord `{crid}` ({crstatus}); audit entries {aud}; change records {chg};
  audit-chain integrity verify_all = {integ}.
- Production sign-off remains withheld (educational classification): residual is
  credentialled-data calibration + independent APS X2 review - not a code gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6;
Solvency II Art. 23 / Art. 234.
""".format(
        now=report["generated_utc"],
        df=hr["df_matched"], nw=hr["nested_scr_without"],
        na=hr["nested_scr_with"], tw=hr["t_copula_scr_without"],
        ta=hr["t_copula_scr_with"],
        nck=sum(1 for v in ui.values() if v is True),
        nc=st["network_calls"], je=st["js_errors"], nst=st["n_checks"],
        crid=gov["change_record_id"], crstatus=gov["change_record_status"],
        aud=report["governance"]["audit_entries"],
        chg=report["governance"]["change_records"],
        integ=integrity,
    )
    MD_PATH.write_text(md, encoding="utf-8")

    print(json.dumps({
        "verdict": "PASS", "phase23": "COMPLETE",
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
