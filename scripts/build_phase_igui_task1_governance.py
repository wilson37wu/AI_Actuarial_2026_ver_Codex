#!/usr/bin/env python3
"""Phase IGUI Task 1 - governance for the Actuarial Input & Run GUI design note.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. Pure
``governance_change``: design-note ONLY - NO GUI code, NO contract change, NO
model parameter changes. The Phase 30 stop-rule stands and the MR-016/MR-017
owner decision is not pre-empted. Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase_igui_task1_governance.py
"""
from __future__ import annotations

import json
from pathlib import Path

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase IGUI Task 1 - Actuarial Input & Run GUI design note "
                "(architecture decision + input-schema coverage map + acceptance criteria)")
AFFECTED_COMPONENTS = [
    "par_model_v2/viewer/igui_input_run_gui.py",
    "scripts/build_phase_igui_task1_design_note.py",
    "scripts/build_phase_igui_task1_governance.py",
    "tests/test_phase_igui_task1_design_note.py",
    "docs/validation/PHASE_IGUI_TASK1_DESIGN_NOTE.json",
    "docs/validation/PHASE_IGUI_TASK1_DESIGN_NOTE.md",
]
STANDARD_REFERENCES = [
    "SOA ASOP 56 (Modeling) section 3.2 / 3.5 - model inputs, intended use, and "
    "the educational-use restriction pending credentialled data + independent review",
    "SOA ASOP 23 (Data Quality) - input completeness / consistency / range "
    "validation gating before a run is permitted",
    "SOA ASOP 41 (Actuarial Communications) - reproducible, auditable run "
    "provenance and a self-describing input contract",
]


def apply(store):
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        for r in store.change_records:
            if r.title == CHANGE_TITLE:
                return {"added": False, "record_id": r.record_id,
                        "status": r.status.value, "reason": "idempotent"}
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Pre-registered the design note for the owner-directed Phase IGUI "
            "workstream: a GUI to enter every actuarial / data input typical of a "
            "valuation process AND run the stochastic model end-to-end (GUI inputs -> "
            "model_inputs.json -> scripts/load_user_inputs.py + scripts/run_model.py -> "
            "scripts/build_ui_data.py -> ui_data.json -> existing offline RESULTS UI "
            "ui_app.html). (a) ARCHITECTURE DECISION: chose the stdlib-only local "
            "runner (L2) over a pure-browser writer (L1, rejected - cannot run the "
            "model) and a frozen binary bundle (L3, deferred - non-reproducible per-OS "
            "build infra). L2 adds ZERO new third-party runtime dependency (the model "
            "already requires Python + numpy/pandas/scipy; the GUI server/UI layer is "
            "Python standard library only), binds 127.0.0.1, makes no outbound network "
            "call, and reuses the existing loader + orchestrator verbatim; the owner "
            "relaxed zero-install for THIS input+run front end ONLY and the offline "
            "RESULTS UI stays zero-install and byte-unchanged. (b) INPUT-SCHEMA COVERAGE "
            "MAP across six domains (run controls, policy/model-point data, assumptions, "
            "ESG/economic-scenario inputs, validation/governance gating, integration), "
            "marking what the current Phase-UIL Excel template + scripts/load_user_inputs.py "
            "already accept (Currency / Balance Sheet / Portfolio / Assumptions / Run "
            "Settings tabs) vs the GAP to the owner's full target, each gap assigned to "
            "one staged task. (c) PRE-REGISTERED ACCEPTANCE CRITERIA per staged task "
            "(Task 2 run controls -> Task 3 model points -> Task 4 assumptions -> Task 5 "
            "ESG -> Task 6 validation/gating -> Task 7 end-to-end run + results handoff = "
            "Phase IGUI MVP) plus a Task-1 gate (validate_design_note, 35 checks) that "
            "mixes structural checks with LIVE repo cross-checks (9 self-tests green / "
            "522 checks, 0 external refs, contract floor 1.21.0, tab/governance floors, "
            "loader + orchestrator present). Design-note ONLY this cycle: NO GUI code, "
            "NO contract change, NO model parameter changes; stop-rule honoured; owner "
            "decision not pre-empted. Tests: 24 unittest cases green; Task-1 gate ok:true "
            "35 checks."
        ),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "phase": "PHASE 36 COMPLETE",
            "igui_design_note": False,
            "ui_contract": "1.21.0",
            "offline_self_tests": 9,
            "offline_self_test_total_checks": 522,
        },
        after_snapshot={
            "igui_design_note": True,
            "igui_architecture_chosen": "L2_stdlib_local_runner",
            "igui_new_third_party_runtime_deps": 0,
            "igui_coverage_domains": 6,
            "igui_staged_tasks": 6,
            "task1_gate_ok": True,
            "task1_gate_checks": 35,
            "ui_contract": "1.21.0 (unchanged - design note only)",
            "results_ui_zero_install_preserved": True,
            "headline_carried_bit_for_bit": "39975.654628199336",
            "offline_self_tests": 9,
            "offline_self_test_total_checks": 522,
        },
        impact_assessment=(
            "Documentation / governance only. NO GUI code, NO contract change, NO "
            "model parameter changes; the offline RESULTS UI is byte-unchanged and the "
            "nine offline self-tests stay green. The note pre-registers an architecture "
            "and acceptance criteria; it computes no model figure and pre-empts no owner "
            "decision (MR-016/MR-017 remains entirely with the owner; Phase 30 stop-rule "
            "honoured)."
        ),
        quantitative_impact=(
            "No governed capital figure changed. Contract unchanged at 1.21.0 "
            "(design-note only). Task-1 gate ok:true 35 checks; 24 unittest cases green; "
            "all 9 offline self-tests remain green (522 checks); 0 external refs."
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: design-note only. Architecture L2 (stdlib local runner) chosen and "
        "justified against L1/L3; ZERO new third-party runtime dependency; offline "
        "RESULTS UI byte-unchanged; coverage map spans six input domains mapped to "
        "current-vs-gap with one staged task each; acceptance criteria pre-registered; "
        "Task-1 gate ok:true 35 checks (structural + live repo cross-checks); 24 "
        "unittest cases green. Governed headline 39,975.654628199336 carried bit-for-bit; "
        "NO contract change; NO model parameter changes; stop-rule honoured.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Phase IGUI is launched design-note-first: the input+run "
        "GUI will use a stdlib-only local runner (no new install beyond the Python the "
        "model already needs), drive the existing loader/orchestrator, and hand results "
        "to the unchanged zero-install RESULTS UI. Next cycle = Task 2 (run controls + "
        "runner scaffolding). The MR-016/MR-017 dependence decision remains PENDING and "
        "entirely with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase IGUI Task 1 design note "
               "(architecture L2 stdlib local runner; 6-domain input coverage map; "
               "acceptance criteria + Task-1 gate); NO contract change; NO model "
               "parameter changes; owner decision not pre-empted"),
        details={"record_id": rec.record_id, "contract": "1.21.0 (unchanged)",
                 "architecture": "L2_stdlib_local_runner",
                 "task1_gate_checks": 35,
                 "affected_components": AFFECTED_COMPONENTS}))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main() -> int:
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_chg, n_aud = len(store.change_records), len(store.audit_trail.all())
    res = apply(store)
    if not store.audit_trail.verify_all():
        print("AUDIT INTEGRITY FAILED - store NOT saved")
        return 1
    if res.get("added"):
        GOV_PATH.write_text(store.to_json(), encoding="utf-8")
    # re-parse guard
    json.loads(GOV_PATH.read_text(encoding="utf-8"))
    print(json.dumps({
        "governance": res,
        "change_records": "%d -> %d" % (n_chg, len(store.change_records)),
        "audit_entries": "%d -> %d" % (n_aud, len(store.audit_trail.all())),
        "risk_register": len(store.risk_register.all()) if hasattr(store.risk_register, "all") else "n/a",
        "audit_integrity_ok": store.audit_trail.verify_all(),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
