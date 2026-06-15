#!/usr/bin/env python3
"""Phase IGUI Task 7 - governance for end-to-end run + results handoff.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. This cycle lands
the D6_run_and_handoff layer: a gate-guarded end-to-end driver
(par_model_v2/viewer/igui_run_execution.py) that drives scripts/run_model.py from
a CLEARED Task-6 gated model_inputs.json, captures the output, carries the run-gate
reproducibility digest into the output provenance, and shapes the offline
RESULTS-UI user_run handoff. Adds NO third-party runtime dependency to the GUI
layer (the engine runs out of process), makes NO model parameter change, leaves
the zero-install RESULTS UI (ui_app.html) byte-unchanged, honours the Phase 30
stop-rule and does not pre-empt MR-016/MR-017. Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase_igui_task7_governance.py
"""
from __future__ import annotations

import json
from pathlib import Path

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase IGUI Task 7 - end-to-end run + results handoff "
                "(par_model_v2/viewer/igui_run_execution.py; drives scripts/run_model.py)")
AFFECTED_COMPONENTS = [
    "scripts/run_gui.py",
    "par_model_v2/viewer/igui_run_execution.py",
    "scripts/run_model.py",
    "scripts/build_phase_igui_task7_run_execution.py",
    "scripts/build_phase_igui_task7_governance.py",
    "tests/test_phase_igui_task7_run_execution.py",
    "docs/validation/PHASE_IGUI_TASK7_RUN_EXECUTION.json",
    "docs/validation/PHASE_IGUI_TASK7_RUN_EXECUTION.md",
]
STANDARD_REFERENCES = [
    "SOA ASOP 56 (Modeling) section 3.5 - controls that prevent a model run on an "
    "incomplete / unvalidated / un-provenanced input set: a run is REFUSED unless the "
    "assembled model_inputs.json carries a CLEARED Task-6 run gate whose reproducibility "
    "digest re-verifies against the live inputs",
    "SOA ASOP 41 (Actuarial Communications) - reproducible, auditable run provenance: the "
    "Task-6 run-gate reproducibility digest is carried VERBATIM into the output provenance "
    "(run_gate_provenance) stamped on every produced artifact",
    "SOA ASOP 23 (Data Quality) - the end-to-end driver consumes only the validated, "
    "gated model_inputs.json contract; the frozen seven-driver dependence is never "
    "user-settable",
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
            "Implemented Task 7 (the D6_run_and_handoff domain) of the owner-directed "
            "Phase IGUI input+run GUI - the Phase IGUI MVP, following Tasks 1-6. "
            "(1) END-TO-END DRIVER par_model_v2/viewer/igui_run_execution.py (STDLIB ONLY): "
            "verify_run_gate REFUSES to spawn the model unless the assembled "
            "model_inputs.json carries a Task-6 run_gate with decision CLEARED / "
            "run_permitted True, matching schema_version, every domain present+clean, AND a "
            "reproducibility digest that re-verifies against the live inputs (a gate lifted "
            "off a different/altered input set is rejected); execute_run then drives "
            "scripts/run_model.py AS A CHILD PROCESS (so the GUI/runner layer keeps ZERO "
            "third-party runtime deps while the numpy/scipy engine runs out of process), "
            "captures stdout/stderr as progress, reads back RUN_MODEL_SUMMARY.json + "
            "RUN_MODEL_AGGREGATION_REPORT.json, STAMPS a run_gate_provenance block (the "
            "Task-6 reproducibility digest + decision + governed headline + read-only frozen "
            "copula structure) onto both artifacts so every result is traceable to the gated "
            "input set that authorised it, and shapes the offline RESULTS-UI user_run "
            "handoff. build_results_handoff produces the SAME user_run contract the offline "
            "UI already consumes (scripts/build_ui_data._build_user_run reads those two "
            "artifacts VERBATIM). A self-contained run page (GET /run-execution) keeps the "
            "Run button DISABLED until the gate clears, surfaces live progress/errors and "
            "post-run headline read-outs, and echoes the governed headline + frozen "
            "structure read-only. (2) STDLIB LOCAL RUNNER scripts/run_gui.py: GET "
            "/run-execution (the run page), POST /execute (gate-guarded end-to-end run, "
            "writing RUN_MODEL_*.json into a dedicated run_output/ dir that NEVER clobbers "
            "governed docs/validation evidence). A run is BLOCKED until Task-6 clears it. "
            "Tests: 21 new unittest cases green (gate verification incl. missing/blocked/"
            "tampered, command builder, stdlib-only guard, self-contained page, refusal "
            "spawns nothing, a REAL end-to-end smoke run incl. digest-carried-into-"
            "provenance + user_run handoff + ui_app.html byte-unchanged after a run); the "
            "full Phase IGUI suite stays green (157 total). The Task-7 gate "
            "validate_task7_gate ok:true 19/19 checks (stdlib-only imports, localhost bind, "
            "prior pages intact, missing/cleared/tampered gate behaviour, live smoke run, "
            "digest carried into output, handoff shaped, blocked-gate-runs-nothing, "
            "ui_app.html byte-unchanged via frozen sha256). NO contract change; NO model "
            "parameter change; offline RESULTS UI byte-unchanged; stop-rule honoured; owner "
            "decision not pre-empted."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "phase": "Phase IGUI Task 6 (validation gating) complete",
            "igui_end_to_end_run": False,
            "results_handoff": False,
            "ui_contract": "1.21.0",
            "ui_app_sha256": "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65",
            "igui_unittests": 136,
        },
        after_snapshot={
            "igui_end_to_end_run": "igui_run_execution.execute_run + run_gui /run-execution /execute",
            "gate_guarded": "run REFUSED unless Task-6 gate CLEARED + digest re-verifies",
            "engine_out_of_process": "drives scripts/run_model.py as a child process",
            "igui_new_third_party_runtime_deps": 0,
            "digest_carried_into_output_provenance": "run_gate_provenance on both RUN_MODEL artifacts",
            "results_handoff": "user_run contract (build_ui_data._build_user_run consumes verbatim)",
            "run_output_dir": "run_output/ (never clobbers governed docs/validation evidence)",
            "task7_gate_ok": True,
            "task7_gate_checks": 19,
            "new_unittests": 21,
            "igui_unittests_total": 157,
            "ui_contract": "1.21.0 (unchanged)",
            "ui_app_sha256": "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65 (byte-unchanged)",
            "results_ui_zero_install_preserved": True,
            "headline_carried_bit_for_bit": "39975.654628199336",
            "phase_igui_mvp": "COMPLETE (inputs -> validation/gating -> end-to-end run -> offline RESULTS UI)",
        },
        impact_assessment=(
            "Additive end-to-end driver + two additive localhost runner routes. NO contract "
            "change, NO model parameter change; the offline RESULTS UI (ui_app.html) is "
            "byte-identical (frozen sha256 asserted by the Task-7 gate and re-asserted AFTER "
            "a live run). The GUI/runner layer stays standard-library only (the model engine "
            "runs out of process behind scripts/run_model.py); the runner stays "
            "localhost-bound and offline. A run can no longer proceed on an unvalidated / "
            "un-provenanced / tampered input set (gate-guarded), and every produced result "
            "carries the gate's reproducibility digest into its provenance. Pre-empts no "
            "owner decision (MR-016/MR-017 remains with the owner; Phase 30 stop-rule "
            "honoured - the frozen copula structure is echoed read-only)."
        ),
        quantitative_impact=(
            "No governed capital figure changed; the headline SCR 39,975.654628199336 is "
            "carried bit-for-bit. Contract unchanged at 1.21.0. Task-7 gate ok:true 19/19 "
            "checks (incl. a real end-to-end smoke run); 21 new unittests green; full Phase "
            "IGUI suite green (157); 0 new third-party runtime dependencies in the GUI/runner "
            "layer; 0 outbound network calls; 0 external page refs."
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: Task 7 lands the D6_run_and_handoff layer - a gate-guarded end-to-end "
        "driver (igui_run_execution.execute_run) that REFUSES to run unless the Task-6 gate "
        "is CLEARED and its reproducibility digest re-verifies against the live inputs, "
        "drives scripts/run_model.py out of process (GUI layer stays stdlib-only), carries "
        "the gate digest VERBATIM into the output provenance, and hands the result to the "
        "offline RESULTS UI via its existing user_run contract. ZERO new third-party runtime "
        "dependency in the GUI/runner layer; localhost-only / offline; offline RESULTS UI "
        "byte-unchanged (frozen sha256, re-asserted after a live run). 21 new unittests + "
        "Task-7 gate (19 checks, incl. a real smoke run) green; full Phase IGUI suite green "
        "(157). Headline 39,975.654628199336 carried bit-for-bit; NO contract change; NO "
        "model parameter change; stop-rule honoured.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. The input+run GUI is now an end-to-end MVP: after the "
        "inputs clear the Task-6 gate, the user presses Run and the GUI drives the governed "
        "model from the gated model_inputs.json, then hands the result to the existing "
        "offline RESULTS UI (byte-unchanged). A run is refused unless the gate permits it, "
        "and every result carries the gate's reproducibility digest into its provenance. "
        "This completes the Phase IGUI MVP (inputs -> validation/gating -> end-to-end run -> "
        "results). The MR-016/MR-017 dependence decision remains PENDING and entirely with "
        "the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase IGUI Task 7 end-to-end run + "
               "results handoff (igui_run_execution.py); gate-guarded drive of "
               "scripts/run_model.py; reproducibility digest carried into output provenance; "
               "offline RESULTS-UI user_run handoff; 0 new GUI-layer third-party deps; "
               "localhost-only/offline; ui_app.html byte-unchanged; NO contract change; NO "
               "model param change; Phase IGUI MVP complete"),
        details={"record_id": rec.record_id, "contract": "1.21.0 (unchanged)",
                 "task7_gate_checks": 19, "new_unittests": 21,
                 "new_third_party_runtime_deps": 0,
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
    json.loads(GOV_PATH.read_text(encoding="utf-8"))  # re-parse guard
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
