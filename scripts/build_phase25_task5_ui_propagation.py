#!/usr/bin/env python3
"""Phase 25 Task 5 — offline-UI propagation: evidence + governance refresh.

This is NOT a model calculation. It verifies that the offline UI
(`scripts/build_ui_data.py` -> `ui_data.json` v1.7.0 ADDITIVE + `ui_app.html`)
surfaces the Phase 25 additions — (a) the Task 2 path-wise bonus declaration
in the nested truth (with-actions SCR 46,638.9 path-wise vs 40,852.1 horizon,
+14.17%; the path-wise basis relieves LESS — the more conservative read-out),
(b) the Task 3 matching path-wise proxy basis (smoothed-relief surface sigma
0.225 / alpha 0.7567 FIT-only; OOS R2 0.9978, VaR rel err 0.40%), and (c) the
Task 4 path-wise tail diagnostics (pathwise-vs-horizon capital-delta matrix
across all four benchmarks; 99.5% raw tail saturation 100% but mean smoothed
relief fraction 0.0811 < 0.12; frozen-copula margin bootstrap 95% CI
[35,793, 42,496] with the nested path-wise reference OUTSIDE the CI —
the 14.7% beyond-noise understatement that motivates the next-phase full
path-wise copula re-aggregation; MR-010/MR-014 refreshed, var-covar
understatement 69.1%) — as a first-class Path-wise Actions (P25) panel.
It re-runs the jsdom self-test (0 network / 0 JS errors), opens an
OWNER_REVIEW ChangeRecord, appends one governance audit entry, verifies
audit-chain integrity, and writes the Task 5 evidence report.
PHASE 25 COMPLETE once this report is persisted.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase25_task5_ui_propagation.py
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

PHASE = ("Phase 25: Path-wise Management-Action Declaration + Matching "
         "Proxy Basis")
ACTOR = "AutomatedModelDev_Phase25"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_DATA = Path("ui_data.json")
UI_APP = Path("ui_app.html")
SELF_TEST = Path("scripts/ui_app_self_test.cjs")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE25_TASK5_UI_PROPAGATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE25_TASK5_UI_PROPAGATION_REPORT.md"
CHANGE_TITLE = (
    "Phase 25 Task 5 - offline-UI propagation of the path-wise action view"
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
    "Solvency II Art. 23 (future management actions - path-wise declaration "
    "displayed)",
    "Solvency II Art. 234 (dependence justification - frozen-copula bootstrap "
    "+ rank-invariance displayed)",
]


def _close(x, target, tol=1.0):
    return isinstance(x, (int, float)) and abs(float(x) - target) <= tol


def check_ui_contract() -> dict:
    data = json.loads(UI_DATA.read_text(encoding="utf-8"))
    cap = data.get("capital", {})
    p25 = data.get("phase25", {})
    dc = p25.get("declaration", {}) if isinstance(p25, dict) else {}
    px = p25.get("proxy_basis", {}) if isinstance(p25, dict) else {}
    td = p25.get("tail_diagnostics", {}) if isinstance(p25, dict) else {}
    dl = dc.get("pathwise_vs_horizon_delta", {}) or {}
    sf = px.get("surface", {}) or {}
    cd = px.get("cadence_sensitivity", {}) or {}
    dm = td.get("delta_matrix", {}) or {}
    bt = (td.get("bootstrap", {}) or {}).get("scr_pathwise", {}) or {}
    fnd = td.get("diagnostic_findings", {}) or {}
    vc = td.get("var_covar_refresh", {}) or {}
    trig = td.get("mr_refresh_trigger", {}) or {}
    verdicts = data.get("verdicts", [])
    vnames = [str(v.get("name") or v.get("key", "")) for v in verdicts]

    def _v(name):
        return any(name in n for n in vnames)

    def _scr(bench, basis):
        return ((dm.get(bench) or {}).get(basis) or {}).get("scr")

    checks = {
        "contract_version": data.get("contract_version"),
        "contract_is_1_7_0": data.get("contract_version") == "1.7.0",
        "phase25_section_present": isinstance(p25, dict) and bool(p25),
        "decl_scr_without_55561": _close(
            (dc.get("nested_capital_without") or {}).get("scr_proxy"),
            55561.2, 1.0),
        "decl_scr_horizon_40852": _close(
            (dc.get("nested_capital_with_horizon") or {}).get("scr_proxy"),
            40852.1, 1.0),
        "decl_scr_pathwise_46639": _close(
            (dc.get("nested_capital_with_pathwise") or {}).get("scr_proxy"),
            46638.9, 1.0),
        "decl_delta_5787": _close(dl.get("scr_delta"), 5786.8, 1.0),
        "decl_delta_rel_14_17pct": _close(
            dl.get("scr_delta_rel_to_horizon"), 0.141653, 5e-4),
        "action_share_41_4pct": _close(
            dc.get("pathwise_action_share"), 0.414039, 5e-4),
        "restoration_share_29_4pct": _close(
            dc.get("pathwise_restoration_share"), 0.293617, 5e-4),
        "task2_gates_6_pass": (isinstance(dc.get("gates"), dict)
                               and len(dc["gates"]) == 6
                               and all(v is True for v in
                                       dc["gates"].values())),
        "recognition_lag_interpretation_disclosed":
            "relieves LESS" in str(dc.get("interpretation", "")),
        "proxy_oos_r2_0_9978": _close(
            px.get("oos_r2_with_actions"), 0.997848, 1e-4),
        "proxy_var_rel_err_0_40pct": _close(
            px.get("var_rel_error_with_actions"), 0.004014, 5e-4),
        "proxy_scr_rel_err_1_16pct": _close(
            px.get("scr_rel_error_with_actions"), 0.011644, 5e-4),
        "surface_sigma_0_225": _close(sf.get("sigma"), 0.225, 1e-9),
        "surface_alpha_0_7567": _close(sf.get("alpha"), 0.756689, 1e-4),
        "cadence_ratio_1_136": _close(
            cd.get("annual_over_monthly_mean_ratio"), 1.135918, 1e-3),
        "task3_gates_5_pass": (isinstance(px.get("gates"), dict)
                               and len(px["gates"]) == 5
                               and all(v is True for v in
                                       px["gates"].values())),
        "delta_matrix_4_benchmarks": (set(dm.keys()) >=
                                      {"nested", "t_copula", "gaussian",
                                       "var_covar"}),
        "matrix_nested_pathwise_46639": _close(
            _scr("nested", "with_pathwise"), 46638.9, 1.0),
        "matrix_t_pathwise_39794": _close(
            _scr("t_copula", "with_pathwise"), 39794.3, 1.0),
        "matrix_gauss_pathwise_35210": _close(
            _scr("gaussian", "with_pathwise"), 35210.1, 1.0),
        "var_covar_no_pathwise_analogue_disclosed":
            _scr("var_covar", "with_pathwise") is None,
        "confidence_sweep_5_rows": len(td.get("confidence_sweep", [])) == 5,
        "tail_saturation_100pct_at_995": _close(
            fnd.get("tail_saturation_share_at_995"), 1.0, 1e-9),
        "smoothed_relief_fraction_0_0811_lt_cap": (
            _close(fnd.get("tail_mean_smoothed_relief_fraction_at_995"),
                   0.081148, 1e-3)
            and float(fnd.get("tail_mean_smoothed_relief_fraction_at_995")
                      or 1.0) < 0.12),
        "bootstrap_ci_lo_35793": _close(bt.get("ci_lo_95"), 35793.2, 1.0),
        "bootstrap_ci_hi_42496": _close(bt.get("ci_hi_95"), 42496.4, 1.0),
        "nested_pathwise_OUTSIDE_bootstrap_ci":
            fnd.get("nested_pathwise_inside_bootstrap_ci") is False,
        "reanchoring_understates_14_7pct": _close(
            fnd.get("t_pathwise_vs_nested_pathwise_rel_err"),
            0.146756, 5e-4),
        "var_covar_understatement_69_1pct": _close(
            vc.get("understatement_vs_nested_with_pathwise"),
            0.690628, 5e-4),
        "df_rematched_2_9451": _close(td.get("df_rematched"), 2.9451, 1e-3),
        "rho_frozen_lt_1e_12": (
            isinstance(td.get("rho_max_abs_diff_vs_archived"), (int, float))
            and float(td["rho_max_abs_diff_vs_archived"]) < 1e-12),
        "mr_refresh_trigger_met": trig.get("met") is True,
        "mr010_mr014_refreshed": (td.get("mr010_refreshed") is True
                                  and td.get("mr014_refreshed") is True),
        "task4_gates_4_pass": (isinstance(td.get("gates"), dict)
                               and len(td["gates"]) == 4
                               and all(v is True for v in
                                       td["gates"].values())),
        "capital_nested_scr_with_pathwise": _close(
            cap.get("nested_scr_with_pathwise"), 46638.9, 1.0),
        "capital_t_pathwise_readout": _close(
            cap.get("t_copula_scr_pathwise_readout"), 39794.3, 1.0),
        "decl_verdict_listed":
            _v("Path-wise bonus declaration in the nested truth"),
        "proxy_verdict_listed": _v("Matching path-wise proxy basis"),
        "tail_verdict_listed": _v("Path-wise tail diagnostics"),
        "narrative_present": bool(str(p25.get("narrative", "")).strip()),
    }
    checks["all_passed"] = all(v is True for k, v in checks.items()
                               if k not in ("contract_version",))
    checks["headline_readouts"] = {
        "nested_scr_without": (dc.get("nested_capital_without") or {})
        .get("scr_proxy"),
        "nested_scr_with_horizon": (dc.get("nested_capital_with_horizon")
                                    or {}).get("scr_proxy"),
        "nested_scr_with_pathwise": (dc.get("nested_capital_with_pathwise")
                                     or {}).get("scr_proxy"),
        "pathwise_minus_horizon_rel": dl.get("scr_delta_rel_to_horizon"),
        "restoration_share": dc.get("pathwise_restoration_share"),
        "oos_r2_pathwise": px.get("oos_r2_with_actions"),
        "var_covar_understatement": vc.get(
            "understatement_vs_nested_with_pathwise"),
        "bootstrap_ci": [bt.get("ci_lo_95"), bt.get("ci_hi_95")],
        "reanchoring_understatement": fnd.get(
            "t_pathwise_vs_nested_pathwise_rel_err"),
        "df_rematched": td.get("df_rematched"),
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
        "phase25_checks": {
            k: out.get("checks", {}).get(k)
            for k in ("phase25TabPresent", "p25Cards", "p25GateCrits",
                      "p25DeltaRows", "p25SweepRows", "p25ProxyRows",
                      "p25BarRects", "pathwiseScrPresent",
                      "pathwiseDeltaPresent", "pathwiseRelievesLessPresent",
                      "restorationSharePresent",
                      "varCovarPathwiseRefreshPresent",
                      "bootstrapOutsideCiPresent", "copulaFrozenPresent",
                      "pathwiseDeclVerdictPresent",
                      "pathwiseProxyVerdictPresent",
                      "pathwiseTailVerdictPresent")
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
                "Phase 25 Task 5 propagated the path-wise management-action "
                "results to the zero-install offline UI. "
                "scripts/build_ui_data.py (contract bumped ADDITIVELY to "
                "v1.7.0) now surfaces a first-class Path-wise Actions (P25) "
                "panel: (1) the Task 2 path-wise bonus declaration in the "
                "nested truth - per-time-step retained-bonus factor on the "
                "path-wise coverage proxy; with-actions SCR 46,638.9 "
                "(path-wise) vs 40,852.1 (horizon) = +14.17%; the path-wise "
                "basis relieves LESS (recognition-lag effect, two-sided) and "
                "is the more conservative, more faithful read-out; "
                "without-actions bit-identical; 6/6 gates; (2) the Task 3 "
                "matching path-wise proxy basis - smoothed-relief response "
                "surface (sigma 0.225, alpha 0.7567; FIT-only, leakage-free); "
                "OOS R2 0.9978, VaR rel err 0.40%, SCR rel err 1.16%; "
                "annual/monthly declaration-cadence sensitivity 1.136 "
                "disclosed; 5/5 gates; and (3) the Task 4 path-wise tail "
                "diagnostics - the without -> with-horizon -> with-path-wise "
                "capital-delta matrix across all four benchmarks (var-covar: "
                "no path-wise analogue, DISCLOSED), the saturation profile "
                "(raw cut saturates 100% of the 99.5% tail but mean smoothed "
                "relief fraction 0.0811 < 0.12 - restoration caps realised "
                "relief), the frozen-copula margin bootstrap (95% CI "
                "[35,793, 42,496]; the nested path-wise reference 46,638.9 "
                "sits OUTSIDE the CI - the analytic re-anchoring understates "
                "nested by 14.7% beyond noise, the quantified motivation for "
                "the next-phase full path-wise copula re-aggregation), and "
                "the MR-010/MR-014 refresh (var-covar understatement 69.1% "
                "vs nested path-wise); 4/4 gates. viewer_data.json was "
                "rebuilt so governance reflects the live store. The UI "
                "performs no calculation; it consumes only already-produced "
                "model output JSONs."
            ),
            change_type="code_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "ui_contract": "1.6.0 (joint-action/inner-path panel; no "
                               "path-wise declaration, delta-matrix or "
                               "tail-diagnostics view)",
            },
            after_snapshot={
                "ui_contract": "1.7.0 (additive)",
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
                "working (two Phase 24 test pins relaxed to a version floor - "
                "DISCLOSED forward-compat fix per repo convention). Completes "
                "the Phase 25 per-task offline-UI propagation requirement; "
                "PHASE 25 COMPLETE (Tasks 1-5)."
            ),
            quantitative_impact=(
                "UI now displays: nested with-actions SCR {pw:.0f} "
                "(path-wise) vs {hz:.0f} (horizon) = +{dr:.2%}; restoration "
                "share {rs:.1%}; proxy OOS R2 {r2:.4f} on the identical "
                "path-wise basis; var-covar understatement {vc:.1%} "
                "(MR-010); bootstrap 95% CI [{lo:.0f}, {hi:.0f}] with the "
                "nested path-wise reference OUTSIDE ({ru:.1%} beyond-noise "
                "understatement disclosed); jsdom self-test ok with {nc} "
                "network calls and {je} JS errors over {n} checks."
            ).format(
                pw=hr["nested_scr_with_pathwise"],
                hz=hr["nested_scr_with_horizon"],
                dr=hr["pathwise_minus_horizon_rel"],
                rs=hr["restoration_share"],
                r2=hr["oos_r2_pathwise"],
                vc=hr["var_covar_understatement"],
                lo=hr["bootstrap_ci"][0], hi=hr["bootstrap_ci"][1],
                ru=hr["reanchoring_understatement"],
                nc=st["network_calls"], je=st["js_errors"], n=st["n_checks"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "UI propagation verified by 40 contract checks + jsdom self-test "
            "(0 network / 0 JS errors); display-layer change only; the "
            "recognition-lag conservatism, the var-covar no-analogue "
            "disclosure and the OUTSIDE-CI re-anchoring understatement are "
            "carried into the display verbatim.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. PHASE 25 COMPLETE at the educational "
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
                event=("ChangeRecord opened (OWNER_REVIEW) - Phase 25 Task 5 "
                       "offline-UI propagation; PHASE 25 COMPLETE"),
                details={
                    "record_id": rec.record_id,
                    "ui_contract": "1.7.0",
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
        "task": "Phase 25 Task 5 - offline-UI propagation",
        "phase": PHASE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "phase25_status": "COMPLETE (Tasks 1-5)",
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
    md = """# Phase 25 Task 5 - Offline-UI Propagation Report

**Generated (UTC):** {now}
**Verdict:** PASS - **PHASE 25 COMPLETE (Tasks 1-5)**

## What the offline UI now surfaces (contract v1.7.0, additive)

A first-class **Path-wise Actions (P25)** panel:

- **Path-wise bonus declaration in the nested truth (Task 2):** per-time-step
  retained-bonus factor on the path-wise coverage proxy (carve-outs
  preserved; without-actions bit-identical) - with-actions SCR {pw:,.0f}
  (path-wise) vs {hz:,.0f} (horizon basis) = **+{dr:.2%}**; the path-wise
  basis relieves LESS (recognition-lag effect, two-sided) and is the more
  conservative, more faithful read-out; action share 41.4%, cut-then-restore
  share {rs:.1%}; 6/6 pre-registered gates.
- **Matching path-wise proxy basis (Task 3):** smoothed-relief response
  surface (sigma 0.225, alpha 0.7567; FIT-only, leakage-free): OOS R2
  {r2:.4f}, VaR rel err 0.40%, SCR rel err 1.16% on the IDENTICAL path-wise
  action basis; annual/monthly declaration-cadence sensitivity 1.136
  disclosed; 5/5 gates.
- **Path-wise tail diagnostics (Task 4):** the without -> with-horizon ->
  with-path-wise capital-delta matrix across all four benchmarks (var-covar:
  no path-wise analogue, DISCLOSED); the raw cut saturates 100% of the 99.5%
  tail but the mean smoothed relief fraction is 0.0811 < 0.12 (restoration
  caps realised relief); the frozen-copula margin bootstrap (95% CI
  [{lo:,.0f}, {hi:,.0f}]) with the nested path-wise reference **OUTSIDE the
  CI** - the analytic re-anchoring understates nested by {ru:.1%} beyond
  noise, the quantified motivation for the next-phase full path-wise copula
  re-aggregation; MR-010/MR-014 refreshed (var-covar understatement
  {vc:.1%}); rank invariance re-gated (df {df:.4f}, copula FROZEN); 4/4
  gates.
- Headline verdicts extended with the three Phase 25 PASS verdicts; additive
  capital read-outs (`nested_scr_with_pathwise`,
  `t_copula_scr_pathwise_readout`); `viewer_data.json` rebuilt so governance
  reflects the live store (48 change records pre-Task 5).

## Verification

- `ui_data.json` contract checks: ALL PASS ({nck} checks).
- jsdom self-test: **ok:true**, {nc} network calls / {je} JS errors over
  {nst} checks (17 new Phase 25 checks incl. panel cards, delta-matrix /
  tail-profile / proxy-basis tables, gate grids, pathwise-vs-horizon bars).
- DISCLOSED forward-compat fix: two Phase 24 Task 5 test pins on contract
  "1.6.0" relaxed to a version floor (additive bumps are the repo
  convention).

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
        pw=hr["nested_scr_with_pathwise"], hz=hr["nested_scr_with_horizon"],
        dr=hr["pathwise_minus_horizon_rel"], rs=hr["restoration_share"],
        r2=hr["oos_r2_pathwise"], vc=hr["var_covar_understatement"],
        lo=hr["bootstrap_ci"][0], hi=hr["bootstrap_ci"][1],
        ru=hr["reanchoring_understatement"], df=hr["df_rematched"],
        nck=sum(1 for v in ui.values() if v is True),
        nc=st["network_calls"], je=st["js_errors"], nst=st["n_checks"],
        crid=gov["change_record_id"], crstatus=gov["change_record_status"],
        aud=report["governance"]["audit_entries"],
        chg=report["governance"]["change_records"],
        integ=integrity,
    )
    MD_PATH.write_text(md, encoding="utf-8")

    print(json.dumps({
        "verdict": "PASS", "phase25": "COMPLETE",
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
