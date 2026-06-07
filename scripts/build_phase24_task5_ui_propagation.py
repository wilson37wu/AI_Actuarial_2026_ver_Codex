#!/usr/bin/env python3
"""Phase 24 Task 5 — offline-UI propagation: evidence + governance refresh.

This is NOT a model calculation. It verifies that the offline UI
(`scripts/build_ui_data.py` -> `ui_data.json` v1.6.0 ADDITIVE + `ui_app.html`)
surfaces the Phase 24 additions — (a) the Task 2 joint-scenario
(action-after-aggregation) t-copula re-aggregation (joint t-SCR 31,001.8 vs
nested-with 33,117.8; saturation gap closed 22.54% -> 6.39%), (b) the Task 3
inner-path action dynamics (outer-node over-relief disclosed: nested SCR
39,290.9 -> 40,852.1, +4.0%; the inner-path basis is the more conservative,
more faithful with-actions basis), and (c) the Task 4 joint-action tail
diagnostics (capital-delta matrix; 99.5% tail 100.0% saturated; margin
bootstrap 95% CI [26,471, 33,637] containing the nested-with reference;
var-covar understatement refreshed 56.4%/53.5%) — as a first-class Joint
Actions (P24) panel. It re-runs the jsdom self-test (0 network / 0 JS
errors), opens an OWNER_REVIEW ChangeRecord, appends one governance audit
entry, verifies audit-chain integrity, and writes the Task 5 evidence report.
PHASE 24 COMPLETE once this report is persisted.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase24_task5_ui_propagation.py
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

PHASE = ("Phase 24: With-Actions Aggregation Consistency + Inner-Path "
         "Action Dynamics")
ACTOR = "AutomatedModelDev_Phase24"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_DATA = Path("ui_data.json")
UI_APP = Path("ui_app.html")
SELF_TEST = Path("scripts/ui_app_self_test.cjs")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE24_TASK5_UI_PROPAGATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE24_TASK5_UI_PROPAGATION_REPORT.md"
CHANGE_TITLE = (
    "Phase 24 Task 5 - offline-UI propagation of the joint-action + "
    "inner-path view"
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
    "Solvency II Art. 23 (future management actions - joint effect displayed)",
    "Solvency II Art. 234 (dependence justification - frozen-copula bootstrap "
    "displayed)",
]


def _close(x, target, tol=1.0):
    return isinstance(x, (int, float)) and abs(float(x) - target) <= tol


def check_ui_contract() -> dict:
    data = json.loads(UI_DATA.read_text(encoding="utf-8"))
    cap = data.get("capital", {})
    p24 = data.get("phase24", {})
    ja = p24.get("joint_action", {}) if isinstance(p24, dict) else {}
    ip = p24.get("inner_path", {}) if isinstance(p24, dict) else {}
    td = p24.get("tail_diagnostics", {}) if isinstance(p24, dict) else {}
    ipd = ip.get("outer_vs_inner_path_delta", {}) or {}
    dm = td.get("delta_matrix", {}) or {}
    bt = (td.get("bootstrap", {}) or {}).get("scr_with", {}) or {}
    fnd = td.get("diagnostic_findings", {}) or {}
    vc = td.get("var_covar_refresh", {}) or {}
    verdicts = data.get("verdicts", [])
    vnames = [str(v.get("name") or v.get("key", "")) for v in verdicts]

    def _v(name):
        return any(name in n for n in vnames)

    checks = {
        "contract_version": data.get("contract_version"),
        "contract_is_1_6_0": data.get("contract_version") == "1.6.0",
        "phase24_section_present": isinstance(p24, dict) and bool(p24),
        "joint_t_scr_31002": _close(ja.get("t_scr_joint"), 31001.8, 1.0),
        "joint_t_rel_error_6_39pct": _close(ja.get("t_rel_error_joint"),
                                            0.0639, 5e-4),
        "standalone_t_rel_error_22_54pct": _close(
            ja.get("t_rel_error_standalone_baseline"), 0.2254, 5e-4),
        "nested_scr_with_33118": _close(ja.get("nested_scr_with"),
                                        33117.8, 1.0),
        "gaussian_joint_scr_26267": _close(ja.get("gaussian_scr_joint"),
                                           26267.1, 1.0),
        "df_matched_2_9451": _close(ja.get("df_matched"), 2.9451, 1e-3),
        "task2_gates_4_pass": (isinstance(ja.get("gates"), dict)
                               and len(ja["gates"]) == 4
                               and all(v is True for v in
                                       ja["gates"].values())),
        "saturation_gap_closure_disclosed":
            "22.54% to 6.39%" in str(ja.get("saturation_gap_closure", "")),
        "inner_path_scr_outer_39291": _close(
            ipd.get("nested_scr_outer_node"), 39290.9, 1.0),
        "inner_path_scr_inner_40852": _close(
            ipd.get("nested_scr_inner_path"), 40852.1, 1.0),
        "inner_path_scr_delta_1561": _close(ipd.get("nested_scr_delta"),
                                            1561.2, 1.0),
        "inner_path_oos_r2_0_9984": _close(ip.get("oos_r2_with_actions"),
                                           0.99837, 1e-4),
        "inner_path_var_rel_err_0_40pct": _close(
            ip.get("var_rel_error_with_actions"), 0.00397, 5e-4),
        "task3_gates_5_pass": (isinstance(ip.get("gates"), dict)
                               and len(ip["gates"]) == 5
                               and all(v is True for v in
                                       ip["gates"].values())),
        "delta_matrix_4_benchmarks": (set(dm.keys()) >=
                                      {"nested", "t_copula", "gaussian",
                                       "var_covar"}),
        "confidence_sweep_5_rows": len(td.get("confidence_sweep", [])) == 5,
        "tail_saturation_100pct_at_995": _close(
            fnd.get("tail_saturation_share_at_995"), 1.0, 1e-9),
        "bootstrap_ci_lo_26471": _close(bt.get("ci_lo_95"), 26470.7, 1.0),
        "bootstrap_ci_hi_33637": _close(bt.get("ci_hi_95"), 33636.8, 1.0),
        "nested_with_inside_bootstrap_ci":
            fnd.get("nested_with_inside_bootstrap_ci") is True,
        "var_covar_understatement_56_4pct": _close(
            vc.get("understatement_vs_nested_with"), 0.5643, 5e-4),
        "var_covar_understatement_t_joint_53_5pct": _close(
            vc.get("understatement_vs_t_joint"), 0.5346, 5e-4),
        "task4_gates_3_pass": (isinstance(td.get("gates"), dict)
                               and len(td["gates"]) == 3
                               and all(v is True for v in
                                       td["gates"].values())),
        "capital_joint_action_scr": _close(
            cap.get("t_copula_scr_joint_action"), 31001.8, 1.0),
        "capital_inner_path_scr": _close(
            cap.get("nested_scr_with_inner_path"), 40852.1, 1.0),
        "joint_action_verdict_listed":
            _v("Joint-scenario action-after-aggregation t-copula"),
        "inner_path_verdict_listed":
            _v("Inner-path management-action dynamics"),
        "tail_diagnostics_verdict_listed":
            _v("Joint-action tail diagnostics"),
        "narrative_present": bool(str(p24.get("narrative", "")).strip()),
    }
    checks["all_passed"] = all(v is True for k, v in checks.items()
                               if k not in ("contract_version",))
    checks["headline_readouts"] = {
        "nested_scr_with": ja.get("nested_scr_with"),
        "t_scr_joint": ja.get("t_scr_joint"),
        "t_rel_error_joint": ja.get("t_rel_error_joint"),
        "t_rel_error_standalone_baseline":
            ja.get("t_rel_error_standalone_baseline"),
        "inner_path_scr_delta": ipd.get("nested_scr_delta"),
        "tail_saturation_at_995": fnd.get("tail_saturation_share_at_995"),
        "bootstrap_ci": [bt.get("ci_lo_95"), bt.get("ci_hi_95")],
        "df_matched": ja.get("df_matched"),
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
        "failed_checks": [k for k, v in out.get("checks", {}).items()
                          if v is False],
        "phase24_checks": {
            k: out.get("checks", {}).get(k)
            for k in ("phase24TabPresent", "p24Cards", "p24GateCrits",
                      "p24DeltaRows", "p24SweepRows", "p24InnerRows",
                      "p24BarRects", "jointActionScrPresent",
                      "saturationGapClosurePresent", "tailSaturationPresent",
                      "bootstrapCiPresent", "innerPathDeltaPresent",
                      "varCovarRefreshPresent", "jointActionVerdictPresent",
                      "innerPathVerdictPresent")
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
                "Phase 24 Task 5 propagated the with-actions aggregation-"
                "consistency results to the zero-install offline UI. "
                "scripts/build_ui_data.py (contract bumped ADDITIVELY to "
                "v1.6.0) now surfaces a first-class Joint Actions (P24) "
                "panel: (1) the Task 2 joint-scenario (action-after-"
                "aggregation) t-copula re-aggregation - joint t-SCR 31,001.8 "
                "vs nested-with 33,117.8, rel err 6.39% vs the 22.54% "
                "standalone-action baseline (saturation gap closed), rank "
                "invariance re-gated, 4/4 gates; (2) the Task 3 inner-path "
                "action dynamics - bonus cut on inner-path benefit cashflows "
                "(credit loss + analytic offsets non-cuttable), OOS R2 "
                "0.9984, VaR rel err 0.40%, and the DISCLOSED outer-node "
                "over-relief (nested SCR 39,290.9 -> 40,852.1, +4.0%; the "
                "inner-path basis is the more conservative, more faithful "
                "with-actions basis), 5/5 gates; and (3) the Task 4 joint-"
                "action tail diagnostics - the without -> with-standalone -> "
                "with-joint capital-delta matrix across all four benchmarks, "
                "the action-saturation profile (99.5% tail 100.0% saturated), "
                "the frozen-copula margin bootstrap (95% CI [26,471, 33,637] "
                "containing the nested-with reference), and the MR-010 "
                "var-covar refresh (56.4%/53.5%), 3/3 gates. viewer_data.json "
                "was rebuilt so governance reflects the live store. The UI "
                "performs no calculation; it consumes only already-produced "
                "model output JSONs."
            ),
            change_type="code_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "ui_contract": "1.5.0 (management-action panel on the "
                               "standalone-action basis only; no joint-action, "
                               "inner-path or tail-diagnostics view)",
            },
            after_snapshot={
                "ui_contract": "1.6.0 (additive)",
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
                "working (two Phase 23 test pins relaxed to a version floor - "
                "DISCLOSED forward-compat fix per repo convention). Completes "
                "the Phase 24 per-task offline-UI propagation requirement; "
                "PHASE 24 COMPLETE (Tasks 1-5)."
            ),
            quantitative_impact=(
                "UI now displays: joint-action t-SCR {tj:.0f} vs nested-with "
                "{nw:.0f} (rel err {tr:.2%} vs standalone baseline {sb:.2%}); "
                "inner-path SCR delta +{ipd:.0f} (+4.0%); 99.5% tail "
                "saturation {sat:.0%}; bootstrap 95% CI [{lo:.0f}, {hi:.0f}]; "
                "jsdom self-test ok with {nc} network calls and {je} JS "
                "errors over {n} checks."
            ).format(
                tj=hr["t_scr_joint"], nw=hr["nested_scr_with"],
                tr=hr["t_rel_error_joint"],
                sb=hr["t_rel_error_standalone_baseline"],
                ipd=hr["inner_path_scr_delta"],
                sat=hr["tail_saturation_at_995"],
                lo=hr["bootstrap_ci"][0], hi=hr["bootstrap_ci"][1],
                nc=st["network_calls"], je=st["js_errors"], n=st["n_checks"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "UI propagation verified by 31 contract checks + jsdom self-test "
            "(0 network / 0 JS errors); display-layer change only; the "
            "saturation-gap closure, outer-node over-relief and tail-"
            "saturation findings are carried into the display verbatim.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. PHASE 24 COMPLETE at the educational "
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
                event=("ChangeRecord opened (OWNER_REVIEW) - Phase 24 Task 5 "
                       "offline-UI propagation; PHASE 24 COMPLETE"),
                details={
                    "record_id": rec.record_id,
                    "ui_contract": "1.6.0",
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
        "task": "Phase 24 Task 5 - offline-UI propagation",
        "phase": PHASE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "phase24_status": "COMPLETE (Tasks 1-5)",
        "ui_contract_checks": ui,
        "self_test": st,
        "governance": {
            **gov,
            "audit_entries":
                f"{n_audit_before}->{len(store.audit_trail.all())}",
            "change_records":
                f"{n_change_before}->{len(store.change_records)}",
            "audit_integrity_verify_all": integrity,
        },
    }
    JSON_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    hr = ui["headline_readouts"]
    md = """# Phase 24 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** {now}
**Verdict:** PASS - **PHASE 24 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.6.0, additive)

A first-class **Joint Actions (P24)** panel:

- **Joint-scenario action-after-aggregation (Task 2):** the governed bonus-cut
  rule applied ONCE to the t({df}) joint liability - joint t-SCR {tj:,.0f} vs
  nested-with {nw:,.0f} (rel err {tr:.2%} vs the 22.54% standalone-action
  baseline; **saturation gap closed**); the joint action only relieves; rank
  invariance re-gated; 4/4 pre-registered gates.
- **Inner-path action dynamics (Task 3):** bonus cut on INNER-PATH benefit
  cashflows (credit loss + analytic FX/liquidity offsets non-cuttable); OOS R2
  0.9984, VaR rel err 0.40%; **outer-node over-relief disclosed** - nested SCR
  39,290.9 -> 40,852.1 (+{ipd:,.0f}, +4.0%); the inner-path basis is the more
  conservative, more faithful with-actions basis; 5/5 gates.
- **Joint-action tail diagnostics (Task 4):** the without -> with-standalone ->
  with-joint capital-delta matrix across all four benchmarks; the
  action-saturation profile (99.5% tail **{sat:.0%} saturated** - max relief
  everywhere capital is measured); the frozen-copula margin bootstrap (95% CI
  [{lo:,.0f}, {hi:,.0f}] **containing the nested-with reference**; n_obs=160
  noise quantified); the MR-010 var-covar refresh (56.4% vs nested-with /
  53.5% vs t-joint); 3/3 gates.
- Headline verdicts extended with the three Phase 24 PASS verdicts; additive
  capital read-outs (`t_copula_scr_joint_action`,
  `nested_scr_with_inner_path`); `viewer_data.json` rebuilt so governance
  reflects the live store (43 change records pre-Task 5).

## Verification

- `ui_data.json` contract checks: ALL PASS ({nck} checks).
- jsdom self-test: **ok:true**, {nc} network calls / {je} JS errors over {nst}
  checks (15 new Phase 24 checks incl. panel cards, delta-matrix /
  saturation-sweep / inner-path tables, gate grids, joint-vs-standalone bars).
- DISCLOSED forward-compat fix: two Phase 23 Task 5 test pins on contract
  "1.5.0" relaxed to a version floor (additive bumps are the repo convention).

## Governance

- ChangeRecord `{crid}` ({crstatus}); audit entries {aud}; change records
  {chg}; audit-chain integrity verify_all = {integ}.
- Production sign-off remains withheld (educational classification): residual
  is credentialled-data calibration + independent APS X2 review - not a code
  gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6;
Solvency II Art. 23 / Art. 234.
""".format(
        now=report["generated_utc"],
        df=hr["df_matched"], tj=hr["t_scr_joint"], nw=hr["nested_scr_with"],
        tr=hr["t_rel_error_joint"], ipd=hr["inner_path_scr_delta"],
        sat=hr["tail_saturation_at_995"],
        lo=hr["bootstrap_ci"][0], hi=hr["bootstrap_ci"][1],
        nck=sum(1 for v in ui.values() if v is True),
        nc=st["network_calls"], je=st["js_errors"], nst=st["n_checks"],
        crid=gov["change_record_id"], crstatus=gov["change_record_status"],
        aud=report["governance"]["audit_entries"],
        chg=report["governance"]["change_records"],
        integ=integrity,
    )
    MD_PATH.write_text(md, encoding="utf-8")

    print(json.dumps({
        "verdict": "PASS", "phase24": "COMPLETE",
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
