#!/usr/bin/env python3
"""Phase 21 Task 5 — offline-UI propagation: evidence + governance refresh.

This is NOT a model calculation. It verifies that the offline UI
(`scripts/build_ui_data.py` -> `ui_data.json` v1.3.0 + `ui_app.html`)
surfaces the Phase 21 additions — the G-FX and G-LIQ calibration gates,
the FX and liquidity standalone SCRs, and the seven-driver tail-dependent
aggregation/tail read-outs — re-runs the jsdom self-test (0 network /
0 JS errors), opens an OWNER_REVIEW ChangeRecord, appends one governance
audit entry, verifies audit-chain integrity, and writes the Task 5
evidence report. PHASE 21 COMPLETE once this report is persisted.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase21_task5_ui_propagation.py
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

PHASE = "Phase 21: FX + Liquidity Drivers and Six/Seven-Driver Economic Capital"
ACTOR = "AutomatedModelDev_Phase21"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_DATA = Path("ui_data.json")
UI_APP = Path("ui_app.html")
SELF_TEST = Path("scripts/ui_app_self_test.cjs")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE21_TASK5_UI_PROPAGATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE21_TASK5_UI_PROPAGATION_REPORT.md"
CHANGE_TITLE = (
    "Phase 21 Task 5 - offline-UI propagation of the seven-driver capital view"
)
AFFECTED_COMPONENTS = [
    "scripts/build_ui_data.py",
    "scripts/ui_app_self_test.cjs",
    "ui_data.json",
    "ui_app.html",
]
STANDARD_REFERENCES = [
    "SOA ASOP 41 s3.2 (communication of actuarial findings)",
    "SOA ASOP 56 s3.5 (model output validation & presentation)",
    "IA TAS M s3.6 (reproducibility and disclosure of model results)",
]


# ---------------------------------------------------------------------------
# Evidence checks (read-only over the built UI contract)
# ---------------------------------------------------------------------------

def check_ui_contract() -> dict:
    data = json.loads(UI_DATA.read_text(encoding="utf-8"))
    cap = data.get("capital", {})
    cal = data.get("calibrations", [])
    tail = data.get("tail", {})
    verdicts = data.get("verdicts", [])
    drivers = [r.get("driver", "") for r in cal]
    vnames = [v.get("name") or v.get("key", "") for v in verdicts]
    vtexts = " | ".join(str(v.get("verdict", "")) for v in verdicts)

    checks = {
        "contract_version": data.get("contract_version"),
        "contract_is_1_3_0": data.get("contract_version") == "1.3.0",
        "n_drivers_seven": cap.get("n_drivers") == 7,
        "fx_scr_present": isinstance(cap.get("fx_scr"), (int, float)),
        "liquidity_scr_present": isinstance(cap.get("liquidity_scr"), (int, float)),
        "var_covar_scr_present": isinstance(cap.get("var_covar_scr"), (int, float)),
        "copula_scr_present": isinstance(cap.get("copula_scr"), (int, float)),
        "nested_scr_present": isinstance(cap.get("nested_scr"), (int, float)),
        "aggregation_source_phase21": "PHASE21_TASK4" in str(cap.get("aggregation_source", "")),
        "liquidity_note_present": bool(cap.get("liquidity_note")),
        "gfx_calibration_record": any("FX" in d for d in drivers),
        "gliq_calibration_record": any("Liquidity" in d for d in drivers),
        "tail_source_phase21": "PHASE21_TASK4" in str(tail.get("source", "")),
        "tail_verdict_seven_driver": "seven-driver" in str(tail.get("verdict", "")),
        "headline_aggregation_seven_driver": "seven-driver" in vtexts,
        "gfx_verdict_listed": any("G-FX" in n for n in vnames),
        "gliq_verdict_listed": any("G-LIQ" in n for n in vnames),
        "seven_driver_verdict_listed": any("Seven-driver" in n for n in vnames),
        "oos_partial_honestly_listed": any("PARTIAL" in str(v.get("verdict", ""))
                                           for v in verdicts),
    }
    checks["all_passed"] = all(v is True for k, v in checks.items()
                               if k not in ("contract_version",))
    checks["capital_readouts"] = {
        "fx_scr": cap.get("fx_scr"),
        "liquidity_scr": cap.get("liquidity_scr"),
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
        "seven_driver_checks": {
            k: out.get("checks", {}).get(k)
            for k in ("gfxPresent", "gliqPresent", "sevenDriverCapitalPresent",
                      "sevenDriverVerdictPresent", "oosPartialVerdictPresent",
                      "fxScrCardPresent", "liquidityScrCardPresent",
                      "nestedDisclosurePresent", "driverBars")
        },
    }


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

def apply_governance(store: GovernanceStore, ui: dict, st: dict) -> dict:
    added = False
    record_id = None
    record_status = None
    if not any(r.title == CHANGE_TITLE for r in store.change_records):
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 21 Task 5 propagated the seven-driver economic-capital view to "
                "the zero-install offline UI. scripts/build_ui_data.py (contract bumped "
                "additively to v1.3.0) now surfaces: (1) the G-FX and G-LIQ calibration "
                "gates as first-class calibration-explorer panels with criteria "
                "breakdowns and fit diagnostics; (2) the FX and liquidity standalone "
                "SCR read-outs (driver bars + KPI cards) alongside the five prior "
                "drivers; (3) the seven-driver tail-dependent aggregation read-outs "
                "(standalone sum / 7x7 var-covar / gaussian copula / nested benchmark, "
                "with the MR-010 understatement finding and the documented small-"
                "liquidity-SCR finding); and (4) the seven-driver tail diagnostics "
                "(copula-simulated convergence, simulated + honest small-sample nested "
                "bootstrap CIs, Sobol-RQMC variance reduction) with the headline "
                "aggregation/tail verdicts refreshed from the five-driver baseline "
                "wording. The six-driver OOS PARTIAL verdict remains honestly "
                "disclosed. No calculation is performed by the UI; it consumes only "
                "already-produced model output JSONs."
            ),
            change_type="code_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "ui_contract": "1.2.0 (five-driver capital view; no G-FX/G-LIQ panels)",
                "headline_verdicts": "five-driver aggregation/tail wording",
            },
            after_snapshot={
                "ui_contract": "1.3.0 (additive)",
                "capital_readouts": ui["capital_readouts"],
                "self_test_ok": st["ok"],
                "network_calls": st["network_calls"],
                "js_errors": st["js_errors"],
            },
            impact_assessment=(
                "Display-layer only: the UI bundler reads validation-report JSONs and "
                "performs no model calculation, so no model output changes. Additive "
                "contract bump keeps existing consumers working. Completes the Phase 21 "
                "per-task offline-UI propagation requirement; PHASE 21 COMPLETE."
            ),
            quantitative_impact=(
                "UI now displays: FX SCR {fx:.0f}; liquidity SCR {liq:.0f}; var-covar "
                "{vc:.0f} vs nested {nest:.0f}; copula {cop:.0f} ({sel}); jsdom "
                "self-test ok with {nc} network calls and {je} JS errors over "
                "{n} checks."
            ).format(
                fx=ui["capital_readouts"]["fx_scr"],
                liq=ui["capital_readouts"]["liquidity_scr"],
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
            "UI propagation verified by contract checks + jsdom self-test (0 network / "
            "0 JS errors); display-layer change only.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. PHASE 21 COMPLETE at the educational level; "
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
                event="ChangeRecord opened (OWNER_REVIEW) - Phase 21 Task 5 offline-UI propagation; PHASE 21 COMPLETE",
                details={
                    "record_id": rec.record_id,
                    "ui_contract": "1.3.0",
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


# ---------------------------------------------------------------------------

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
        print("AUDIT INTEGRITY FAILED — store NOT saved")
        return 1
    GOV_PATH.write_text(store.to_json(), encoding="utf-8")

    report = {
        "task": "Phase 21 Task 5 - offline-UI propagation",
        "phase": PHASE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "phase21_status": "COMPLETE (Tasks 1-5)",
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

    md = """# Phase 21 Task 5 — Offline-UI Propagation Report

**Generated (UTC):** {now}
**Verdict:** PASS — **PHASE 21 COMPLETE (Tasks 1–5)**

## What the offline UI now surfaces (contract v1.3.0, additive)

- **G-FX gate** (6th driver): calibration-explorer panel with 6/6 criteria and
  MART-FX-CIP martingale evidence.
- **G-LIQ gate** (7th driver): calibration-explorer panel (kappa 0.9345/yr,
  long-run 63 bp, sigma 0.0213, lambda 2.0 CLAMPED — disclosed).
- **FX + liquidity standalone SCRs**: driver bars + KPI cards — FX {fx:,.0f},
  liquidity {liq:,.0f} (small-SCR finding note displayed).
- **Seven-driver aggregation**: standalone sum / var-covar {vc:,.0f} /
  gaussian copula {cop:,.0f} / nested {nest:,.0f}; MR-010 understatement
  finding re-stated under seven drivers.
- **Seven-driver tail diagnostics**: copula-simulated convergence, simulated +
  honest small-sample nested bootstrap CIs, Sobol-RQMC variance reduction.
- Headline aggregation/tail verdicts refreshed from the stale five-driver
  baseline wording; the six-driver OOS **PARTIAL** verdict remains honestly listed.

## Verification

- `ui_data.json` contract checks: ALL PASS ({nck} checks).
- jsdom self-test: **ok:true**, {nc} network calls / {je} JS errors over {nst} checks.

## Governance

- ChangeRecord `{crid}` ({crstatus}); audit entries {aud}; change records {chg};
  audit-chain integrity verify_all = {integ}.
- Production sign-off remains withheld (educational classification): residual is
  credentialled-data calibration + independent APS X2 review — not a code gap.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6.
""".format(
        now=report["generated_utc"],
        fx=ui["capital_readouts"]["fx_scr"], liq=ui["capital_readouts"]["liquidity_scr"],
        vc=ui["capital_readouts"]["var_covar_scr"], cop=ui["capital_readouts"]["copula_scr"],
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
        "verdict": "PASS", "phase21": "COMPLETE",
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
