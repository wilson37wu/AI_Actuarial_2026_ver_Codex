#!/usr/bin/env python3
"""Phase IGUI Task 2 - governance for the run-controls + stdlib local runner.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. This cycle
lands GUI scaffolding code (the stdlib local runner + run-controls core +
loader-side dict validator), so the change_type is ``feature_addition``; it adds
NO third-party runtime dependency, makes NO model parameter change, and leaves
the zero-install RESULTS UI (ui_app.html) byte-unchanged. The Phase 30 stop-rule
stands and the MR-016/MR-017 owner decision is not pre-empted. Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase_igui_task2_governance.py
"""
from __future__ import annotations

import json
from pathlib import Path

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase IGUI Task 2 - run controls + stdlib local-runner scaffolding "
                "(scripts/run_gui.py; loader-side run-controls validator)")
AFFECTED_COMPONENTS = [
    "scripts/run_gui.py",
    "par_model_v2/viewer/igui_run_controls.py",
    "scripts/load_user_inputs.py",
    "scripts/build_phase_igui_task2_run_controls.py",
    "scripts/build_phase_igui_task2_governance.py",
    "tests/test_phase_igui_task2_run_controls.py",
    "docs/validation/PHASE_IGUI_TASK2_RUN_CONTROLS.json",
    "docs/validation/PHASE_IGUI_TASK2_RUN_CONTROLS.md",
]
STANDARD_REFERENCES = [
    "SOA ASOP 56 (Modeling) section 3.2 / 3.5 - model inputs, intended use, and "
    "the educational-use restriction pending credentialled data + independent review",
    "SOA ASOP 23 (Data Quality) - input completeness / consistency / range "
    "validation gating before a run is permitted (run-controls fragment validated "
    "fail-loud through the loader)",
    "SOA ASOP 41 (Actuarial Communications) - reproducible, auditable run "
    "provenance (per-run reproducibility digest) and a self-describing input contract",
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
            "Implemented Task 2 (the D1_run_controls domain) of the owner-directed "
            "Phase IGUI input+run GUI, following the Task-1 design note. (1) STDLIB "
            "LOCAL RUNNER scripts/run_gui.py: a standard-library-only http.server "
            "(ThreadingHTTPServer) bound to 127.0.0.1 that serves a SELF-CONTAINED "
            "run-controls page (zero external references) and exposes GET / , "
            "GET /healthz , POST /validate , POST /save. It adds NO third-party runtime "
            "dependency (http.server / json / webbrowser - all standard library; the "
            "model itself already requires numpy/pandas/scipy) and makes NO outbound "
            "network call. (2) RUN-CONTROLS CORE par_model_v2/viewer/igui_run_controls.py: "
            "a declarative run-control field spec (valuation date; currency code/symbol/"
            "scale/thousands/market label; explicit OUTER and INNER scenarios; n_sim; "
            "bootstrap replicates; projection HORIZON and explicit projection STEP; seed; "
            "output label), normalisation of a raw form payload, a builder to the "
            "model_inputs.json {currency, run_settings} sub-schema, and a deterministic "
            "per-run reproducibility digest (sha256 over the canonical run controls) - "
            "closing the Task-1 gaps for valuation date, explicit step, explicit outer/"
            "inner split, and a surfaced per-run digest. (3) LOADER ROUND-TRIP: added a "
            "purely additive scripts/load_user_inputs.validate_run_controls_dict that "
            "validates the {currency, run_settings} fragment with the SAME rules as the "
            "Excel template parsers (no openpyxl needed); the GUI round-trips EVERY "
            "payload through it fail-loud before a write/run is permitted. The Excel "
            "template path is unchanged. Tests: 21 new unittest cases green (normalisation, "
            "loader round-trip incl. rejection cases, self-contained form, a real "
            "localhost GET/POST round-trip, and a Task-2 acceptance gate); the Task-1 "
            "suite stays green (24). The Task-2 gate validate_task2_gate ok:true 21 checks "
            "(stdlib-only imports, localhost bind, loader-validator presence + enum/schema "
            "lock-step, digest determinism, form headline + zero external refs, ui_app.html "
            "byte-unchanged via frozen sha256, governance floors). NO contract change; NO "
            "model parameter change; offline RESULTS UI byte-unchanged; stop-rule honoured; "
            "owner decision not pre-empted."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "phase": "Phase IGUI Task 1 design note complete",
            "igui_run_gui": False,
            "loader_run_controls_validator": False,
            "ui_contract": "1.21.0",
            "ui_app_sha256": "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65",
            "offline_self_tests": 9,
            "offline_self_test_total_checks": 522,
        },
        after_snapshot={
            "igui_run_gui": "scripts/run_gui.py (stdlib http.server, 127.0.0.1, offline)",
            "igui_new_third_party_runtime_deps": 0,
            "loader_run_controls_validator": "validate_run_controls_dict (additive, no openpyxl)",
            "run_controls_collected": [
                "valuation_date", "currency(code/symbol/scale/thousands/market_label)",
                "n_outer", "n_inner", "n_sim", "bootstrap_replicates",
                "horizon_months", "step_months", "seed", "output_label"],
            "per_run_reproducibility_digest": True,
            "task2_gate_ok": True,
            "task2_gate_checks": 21,
            "new_unittests": 21,
            "task1_unittests_still_green": 24,
            "ui_contract": "1.21.0 (unchanged)",
            "ui_app_sha256": "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65 (byte-unchanged)",
            "results_ui_zero_install_preserved": True,
            "headline_carried_bit_for_bit": "39975.654628199336",
            "offline_self_tests": 9,
            "offline_self_test_total_checks": 522,
        },
        impact_assessment=(
            "Additive GUI scaffolding + an additive loader-side validator. NO contract "
            "change, NO model parameter change; the offline RESULTS UI (ui_app.html) is "
            "byte-identical (frozen sha256 asserted by the Task-2 gate) and the nine "
            "offline self-tests are unaffected. The runner is localhost-bound and offline; "
            "it computes no model figure and pre-empts no owner decision (MR-016/MR-017 "
            "remains with the owner; Phase 30 stop-rule honoured)."
        ),
        quantitative_impact=(
            "No governed capital figure changed; the headline SCR 39,975.654628199336 is "
            "carried bit-for-bit. Contract unchanged at 1.21.0. Task-2 gate ok:true 21 "
            "checks; 21 new unittests green; Task-1 suite still green (24); 0 new "
            "third-party runtime dependencies; 0 outbound network calls; 0 external refs."
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: Task 2 lands the stdlib local runner + run-controls core + an additive "
        "loader-side dict validator. ZERO new third-party runtime dependency; the runner "
        "binds 127.0.0.1 and makes no outbound network call; every GUI payload round-trips "
        "fail-loud through scripts/load_user_inputs.validate_run_controls_dict before a "
        "write; per-run reproducibility digest emitted; offline RESULTS UI byte-unchanged "
        "(frozen sha256). 21 new unittests + Task-2 gate (21 checks) green; Task-1 suite "
        "green (24). Headline 39,975.654628199336 carried bit-for-bit; NO contract change; "
        "NO model parameter change; stop-rule honoured.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. The input+run GUI now collects run controls (valuation "
        "date, currency, explicit outer/inner scenarios, projection horizon & step, seed, "
        "output label) and writes them into the loader's model_inputs.json schema, "
        "validated through the real loader before any run. Next cycle = Task 3 (model "
        "points + in-force ingest). The MR-016/MR-017 dependence decision remains PENDING "
        "and entirely with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase IGUI Task 2 run controls + "
               "stdlib local runner (scripts/run_gui.py); additive loader-side "
               "validate_run_controls_dict; 0 new third-party deps; localhost-only/offline; "
               "ui_app.html byte-unchanged; NO contract change; NO model parameter change"),
        details={"record_id": rec.record_id, "contract": "1.21.0 (unchanged)",
                 "task2_gate_checks": 21, "new_unittests": 21,
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
     