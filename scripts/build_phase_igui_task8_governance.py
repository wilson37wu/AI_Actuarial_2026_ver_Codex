#!/usr/bin/env python3
"""Phase IGUI Task 8 - governance for one-click offline packaging + own-run results refresh.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. This cycle lands the
D7_packaging_and_own_results layer: a single stdlib-only one-click launcher
(scripts/launch_offline_gui.py + OS double-click wrappers under launchers/) that starts
the input+run GUI on 127.0.0.1 and opens the browser, and an own-run results refresh
(par_model_v2/viewer/igui_results_refresh.py) that builds a USER copy of the offline
RESULTS UI (user_results/ui_app_user.html) from the user's own run_output via the
existing build_ui_data display layer - leaving the committed zero-install ui_app.html
byte-for-byte unchanged. Adds NO third-party runtime dependency, makes NO model
parameter change, honours the Phase 30 stop-rule, does not pre-empt MR-016/MR-017.
Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase_igui_task8_governance.py
"""
from __future__ import annotations

import json
from pathlib import Path

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase IGUI Task 8 - one-click offline packaging + own-run results refresh "
                "(scripts/launch_offline_gui.py; par_model_v2/viewer/igui_results_refresh.py)")
AFFECTED_COMPONENTS = [
    "scripts/launch_offline_gui.py",
    "launchers/Launch_Actuarial_GUI.bat",
    "launchers/Launch_Actuarial_GUI.command",
    "launchers/launch_actuarial_gui.sh",
    "launchers/README.md",
    "par_model_v2/viewer/igui_results_refresh.py",
    "scripts/run_gui.py",
    "scripts/build_phase_igui_task8_governance.py",
    "tests/test_phase_igui_task8_results_refresh.py",
]
STANDARD_REFERENCES = [
    "SOA ASOP 56 (Modeling) section 3.5 / 3.6 - model usability and controls: a "
    "non-technical user can supply inputs AND run the governed model from a single "
    "launcher without bespoke environment setup; the compute step still runs only "
    "behind the Task-6 gate via the Task-7 driver",
    "SOA ASOP 41 (Actuarial Communications) - the user's OWN run is surfaced VERBATIM "
    "(build_ui_data._build_user_run) into a USER copy of the offline results UI, with "
    "the run-gate reproducibility digest carried through; nothing is recomputed by the "
    "display layer",
    "SOA ASOP 23 (Data Quality) - the own-run refresh reads only the governed RUN_MODEL "
    "artifacts the run produced; the committed zero-install results template is never "
    "mutated (byte-identity asserted)",
]
SHA = "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65"


def apply(store):
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        for r in store.change_records:
            if r.title == CHANGE_TITLE:
                return {"added": False, "record_id": r.record_id,
                        "status": r.status.value, "reason": "idempotent"}
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Implemented Task 8 (the D7_packaging_and_own_results domain) of the "
            "owner-directed Phase IGUI input+run GUI, following the Task-7 MVP. "
            "(1) ONE-CLICK OFFLINE LAUNCHER scripts/launch_offline_gui.py (STDLIB ONLY): a "
            "single entry point (with OS double-click wrappers under launchers/ for Windows "
            ".bat / macOS .command / Linux .sh) that puts the repo on sys.path so NO install "
            "/ pip / PYTHONPATH setup is needed, picks a free localhost port (falling back "
            "from the default if busy), starts the existing stdlib runner scripts/run_gui.py "
            "bound to 127.0.0.1 ONLY, opens the default browser, and discloses up front "
            "whether the out-of-process numpy/scipy model engine is importable (the GUI + "
            "offline RESULTS UI are pure stdlib; only the /execute compute child needs the "
            "engine) - it never installs anything, it reports. build_launch_plan / "
            "engine_status are unit-testable and --self-test resolves the plan WITHOUT "
            "binding a server. (2) OWN-RUN RESULTS REFRESH par_model_v2/viewer/"
            "igui_results_refresh.py (STDLIB ONLY, DISPLAY LAYER): refresh_user_results "
            "drives the existing scripts/build_ui_data display builder with its run-evidence "
            "sources temporarily repointed at the user's run_output/ and its outputs "
            "repointed at a USER directory, producing user_results/ui_app_user.html + "
            "ui_data_user.json that carry the user's OWN run VERBATIM via the existing "
            "user_run contract - then RESTORES every build_ui_data constant in a finally so "
            "the committed pipeline is unchanged. The committed zero-install ui_app.html / "
            "ui_data.json are NEVER written and are asserted byte-for-byte unchanged "
            "(sha256 before/after); a committed-template mutation is a HARD failure. "
            "(3) RUNNER WIRING scripts/run_gui.py: on a SUCCESSFUL /execute run the runner "
            "best-effort refreshes the USER copy (a refresh hiccup NEVER fails the run) and "
            "exposes it at GET /my-results (+ /my-results.json), with a graceful "
            "self-contained placeholder until a run exists. Tests: 8 new unittest cases "
            "green (verbatim-headline USER copy, self-contained/offline USER html, graceful "
            "no-run fallback, committed-template byte-unchanged invariant, the 13-check "
            "Task-8 gate, launcher plan/engine-status/self-test-starts-no-server); run_gui "
            "--self-test green incl. the new /my-results routes. NO contract change; NO "
            "model parameter change; offline RESULTS UI template byte-unchanged; stop-rule "
            "honoured; owner decision not pre-empted."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "phase": "Phase IGUI Task 7 (end-to-end run + results handoff) complete - MVP",
            "one_click_launcher": False,
            "own_run_results_refresh": False,
            "ui_contract": "1.21.0",
            "ui_app_sha256": SHA,
            "igui_unittests": 157,
        },
        after_snapshot={
            "one_click_launcher": "scripts/launch_offline_gui.py + launchers/* (stdlib only)",
            "launcher_binds": "127.0.0.1 only; free-port fallback; opens browser; offline",
            "engine_disclosure": "engine_status() reports numpy/scipy presence; never auto-installs",
            "own_run_results_refresh": "igui_results_refresh.refresh_user_results -> user_results/ui_app_user.html",
            "results_refresh_layer": "display only (build_ui_data); user run carried VERBATIM via user_run",
            "committed_template_writes": 0,
            "committed_ui_app_byte_unchanged": True,
            "runner_routes_added": "/my-results, /my-results.json (post-run USER copy)",
            "igui_new_third_party_runtime_deps": 0,
            "task8_gate_ok": True,
            "task8_gate_checks": 13,
            "new_unittests": 8,
            "igui_unittests_total": 165,
            "ui_contract": "1.21.0 (unchanged)",
            "ui_app_sha256": SHA + " (byte-unchanged)",
            "results_ui_zero_install_preserved": True,
            "headline_carried_bit_for_bit": "39975.654628199336",
            "phase_igui": "MVP + one-click packaging + own-run results view",
        },
        impact_assessment=(
            "Additive launcher + additive display-layer refresh module + two additive "
            "localhost runner routes. NO contract change, NO model parameter change; the "
            "committed offline RESULTS UI (ui_app.html / ui_data.json) is byte-identical "
            "(sha256 asserted before/after every refresh and by the Task-8 gate). The "
            "user's own run is rendered into a SEPARATE user_results/ copy via the existing "
            "verbatim user_run contract - nothing is recomputed by the display layer. The "
            "launcher and refresh layers stay standard-library only (the model engine still "
            "runs out of process behind the Task-6 gate + Task-7 driver); the runner stays "
            "localhost-bound and offline. A non-technical user can now press one button to "
            "supply inputs AND compute, then immediately browse THEIR OWN results. Pre-empts "
            "no owner decision (MR-016/MR-017 remains with the owner; Phase 30 stop-rule "
            "honoured)."
        ),
        quantitative_impact=(
            "No governed capital figure changed; the headline SCR 39,975.654628199336 is "
            "carried bit-for-bit into the USER copy. Contract unchanged at 1.21.0. Task-8 "
            "gate ok:true 13/13 checks; 8 new unittests green; 0 new third-party runtime "
            "dependencies; 0 outbound network calls; 0 external page refs in the USER html; "
            "committed ui_app.html sha256 unchanged (" + SHA + ")."
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: Task 8 lands D7_packaging_and_own_results - a single stdlib-only "
        "one-click launcher (scripts/launch_offline_gui.py + OS wrappers) that starts the "
        "input+run GUI on 127.0.0.1 and opens the browser with NO install/env setup, and an "
        "own-run results refresh (igui_results_refresh.refresh_user_results) that builds a "
        "USER copy of the offline RESULTS UI from the user's run_output via the existing "
        "build_ui_data display layer, carrying the run VERBATIM through the user_run "
        "contract and RESTORING every build_ui_data constant afterwards. The committed "
        "zero-install ui_app.html / ui_data.json are NEVER written and are asserted "
        "byte-for-byte unchanged (sha256). ZERO new third-party runtime deps; "
        "localhost-only / offline; 8 new unittests + the 13-check Task-8 gate green; run_gui "
        "--self-test green incl. the new /my-results routes. Headline 39,975.654628199336 "
        "carried bit-for-bit; NO contract change; NO model parameter change; stop-rule "
        "honoured.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. The input+run GUI is now one-click and self-serving: a "
        "non-technical user runs a single launcher (no install/env setup; localhost-only, "
        "offline), supplies inputs, clears the gate, presses Run, and immediately browses "
        "THEIR OWN run in the offline results UI at /my-results. The committed zero-install "
        "results template is left byte-for-byte unchanged - the user's run is rendered into "
        "a separate user_results copy. The compute step still requires the numpy/scipy "
        "engine (disclosed by the launcher); a fully self-contained frozen binary / vendored "
        "wheels is noted as the next packaging step but needs offline build tooling not "
        "available in this dev cycle. The MR-016/MR-017 dependence decision remains PENDING "
        "and entirely with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase IGUI Task 8 one-click offline "
               "packaging + own-run results refresh (launch_offline_gui.py; "
               "igui_results_refresh.py); stdlib-only launcher binds 127.0.0.1 + opens "
               "browser; USER copy of offline RESULTS UI built from run_output via "
               "build_ui_data (user_run verbatim); committed ui_app.html byte-unchanged; "
               "0 new GUI-layer third-party deps; NO contract change; NO model param change; "
               "Phase 30 stop-rule honoured"),
        details={"record_id": rec.record_id, "contract": "1.21.0 (unchanged)",
                 "task8_gate_checks": 13, "new_unittests": 8,
                 "new_third_party_runtime_deps": 0,
                 "ui_app_sha256": SHA,
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
        "audit_integrity_ok": store.audit_trail.verify_all(),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
