#!/usr/bin/env python3
"""Phase IGUI Task 6 - governance for validation surfacing + governance gating.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. This cycle lands
the D5_validation_gating layer (aggregate loader validator + self-contained gate
page + run-gate provenance/digest); it adds NO third-party runtime dependency,
makes NO model parameter change, leaves the zero-install RESULTS UI (ui_app.html)
byte-unchanged, honours the Phase 30 stop-rule and does not pre-empt MR-016/MR-017.
Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase_igui_task6_governance.py
"""
from __future__ import annotations

import json
from pathlib import Path

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase IGUI Task 6 - validation surfacing + governance gating before run "
                "(par_model_v2/viewer/igui_validation_gating.py; loader-side aggregate validator)")
AFFECTED_COMPONENTS = [
    "scripts/run_gui.py",
    "par_model_v2/viewer/igui_validation_gating.py",
    "scripts/load_user_inputs.py",
    "scripts/build_phase_igui_task6_validation_gating.py",
    "scripts/build_phase_igui_task6_governance.py",
    "tests/test_phase_igui_task6_validation_gating.py",
    "docs/validation/PHASE_IGUI_TASK6_VALIDATION_GATING.json",
    "docs/validation/PHASE_IGUI_TASK6_VALIDATION_GATING.md",
]
STANDARD_REFERENCES = [
    "SOA ASOP 23 (Data Quality) - input completeness / consistency / range "
    "validation gating BEFORE a run is permitted; the whole assembled model_inputs "
    "is validated fail-loud across all domains and the run is blocked until clean",
    "SOA ASOP 56 (Modeling) section 3.5 - controls that prevent a model run on an "
    "incomplete / unvalidated input set",
    "SOA ASOP 41 (Actuarial Communications) - reproducible, auditable run provenance "
    "(a governance run-gate ChangeRecord-style record + a deterministic run-level "
    "reproducibility digest recorded before each run)",
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
            "Implemented Task 6 (the D5_validation_gating domain) of the owner-directed "
            "Phase IGUI input+run GUI, following Tasks 1-5. (1) AGGREGATE LOADER VALIDATOR "
            "scripts/load_user_inputs.validate_assembled_inputs (purely additive, no "
            "openpyxl): routes the WHOLE assembled model_inputs.json through every "
            "per-domain dict validator (run controls, model points, assumptions, ESG) and "
            "returns a per-domain {present, ok, errors} summary + an overall verdict; a "
            "domain that has not been saved yet is reported missing so an INCOMPLETE input "
            "set can never clear. (2) GATING CORE par_model_v2/viewer/igui_validation_gating.py "
            "(stdlib only): aggregate_validation (delegates to the loader - single source "
            "of truth), a deterministic run-level reproducibility digest "
            "(run_reproducibility_digest, sha256 over canonical inputs with volatile keys "
            "stripped), build_run_gate (a ChangeRecord-style provenance record: decision "
            "CLEARED only when every domain is present AND clean else BLOCKED, per-domain "
            "summary, flat blocking-issue list, governed headline + READ-ONLY frozen copula "
            "structure echo), and a SELF-CONTAINED gate page (zero external references). "
            "(3) STDLIB LOCAL RUNNER scripts/run_gui.py: GET /run-gate (the gate page), "
            "POST /preflight (read-only aggregate validation surfacing), POST /run (records "
            "the governance run-gate + digest into model_inputs.json IFF all domains clean; "
            "a BLOCKED gate writes nothing). The Run action is BLOCKED until clean across "
            "ALL domains. This SURFACES validation and RECORDS the gate; it does NOT execute "
            "the model (end-to-end run + results handoff is Task 7). Tests: 22 new unittest "
            "cases green (aggregate validator incl. missing-domain / invalid-field, digest "
            "determinism / sensitivity / timestamp-invariance, CLEARED vs BLOCKED gate, "
            "self-contained page, ui_app.html byte-unchanged, and a localhost round-trip "
            "GET /run-gate + POST /preflight + POST /run incl. the blocked-when-incomplete "
            "path); the full Phase IGUI suite stays green (136 total). The Task-6 gate "
            "validate_task6_gate ok:true 27/27 checks (stdlib-only imports, localhost bind, "
            "loader aggregate-validator presence + schema lock-step, clean-clears / "
            "incomplete-blocks / invalid-surfaces live behaviour, digest properties, "
            "self-contained page that blocks Run by default, ui_app.html byte-unchanged via "
            "frozen sha256). NO contract change; NO model parameter change; offline RESULTS "
            "UI byte-unchanged; stop-rule honoured; owner decision not pre-empted."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "phase": "Phase IGUI Task 5 (ESG) complete",
            "loader_aggregate_validator": False,
            "igui_run_gate": False,
            "ui_contract": "1.21.0",
            "ui_app_sha256": "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65",
            "igui_unittests": 114,
        },
        after_snapshot={
            "loader_aggregate_validator": "validate_assembled_inputs (additive, no openpyxl)",
            "igui_new_third_party_runtime_deps": 0,
            "igui_run_gate": "igui_validation_gating.py + run_gui /run-gate /preflight /run",
            "run_gate_records": ["decision(CLEARED|BLOCKED)", "per_domain_summary",
                                 "blocking_issues", "run_reproducibility_digest",
                                 "governed_headline", "frozen_copula_structure(read-only)"],
            "run_blocked_until_all_domains_clean": True,
            "task6_gate_ok": True,
            "task6_gate_checks": 27,
            "new_unittests": 22,
            "igui_unittests_total": 136,
            "ui_contract": "1.21.0 (unchanged)",
            "ui_app_sha256": "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65 (byte-unchanged)",
            "results_ui_zero_install_preserved": True,
            "headline_carried_bit_for_bit": "39975.654628199336",
        },
        impact_assessment=(
            "Additive gating layer + an additive loader-side aggregate validator. NO "
            "contract change, NO model parameter change; the offline RESULTS UI "
            "(ui_app.html) is byte-identical (frozen sha256 asserted by the Task-6 gate). "
            "The runner stays localhost-bound and offline; it computes no model figure and "
            "pre-empts no owner decision (MR-016/MR-017 remains with the owner; Phase 30 "
            "stop-rule honoured - the frozen copula structure is echoed read-only). The "
            "gate strengthens controls: a run can no longer proceed on an incomplete / "
            "invalid / un-provenanced input set."
        ),
        quantitative_impact=(
            "No governed capital figure changed; the headline SCR 39,975.654628199336 is "
            "carried bit-for-bit. Contract unchanged at 1.21.0. Task-6 gate ok:true 27/27 "
            "checks; 22 new unittests green; full Phase IGUI suite green (136); 0 new "
            "third-party runtime dependencies; 0 outbound network calls; 0 external refs."
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: Task 6 lands the D5_validation_gating layer - an additive loader-side "
        "aggregate validator (validate_assembled_inputs) routing the whole assembled "
        "model_inputs.json through every per-domain validator, a self-contained gate page "
        "surfacing per-domain PASS/FAIL with every fail-loud issue, and a governance "
        "run-gate (CLEARED only when all domains are present and clean) that records a "
        "ChangeRecord-style provenance object + a deterministic run-level reproducibility "
        "digest before any run. ZERO new third-party runtime dependency; localhost-only / "
        "offline; offline RESULTS UI byte-unchanged (frozen sha256). 22 new unittests + "
        "Task-6 gate (27 checks) green; full Phase IGUI suite green (136). Headline "
        "39,975.654628199336 carried bit-for-bit; NO contract change; NO model parameter "
        "change; stop-rule honoured; the gate records readiness only (execution = Task 7).")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. The input+run GUI now BLOCKS the Run action until the "
        "assembled model_inputs.json is present and clean across run controls, model "
        "points, assumptions and ESG, surfacing every loader issue; on clearing it records "
        "a governance run-gate + a reproducibility digest. Next cycle = Task 7 (end-to-end "
        "run + results handoff to the offline UI), which is the Phase IGUI MVP. The "
        "MR-016/MR-017 dependence decision remains PENDING and entirely with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase IGUI Task 6 validation surfacing "
               "+ governance gating (igui_validation_gating.py); additive loader-side "
               "validate_assembled_inputs; run BLOCKED until all domains clean; run-gate "
               "provenance + reproducibility digest; 0 new third-party deps; localhost-only/"
               "offline; ui_app.html byte-unchanged; NO contract change; NO model param change"),
        details={"record_id": rec.record_id, "contract": "1.21.0 (unchanged)",
                 "task6_gate_checks": 27, "new_unittests": 22,
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
