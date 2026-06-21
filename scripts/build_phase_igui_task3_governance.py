#!/usr/bin/env python3
"""Phase IGUI Task 3 - governance for model points + in-force ingest.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. This cycle lands
the second staged input domain of the owner-directed input+run GUI: interactive
add/edit/delete of PAR + GMMB model-point rows, a CSV/JSON in-force upload path
mapping to the Portfolio schema, balance-sheet asset rows + stated-total
reconciliation, and a DISCLOSED (non-governed) book-scaling preview that echoes
what scripts/run_model.resolve_product reports. It adds NO third-party runtime
dependency, makes NO model parameter change, and leaves the zero-install RESULTS
UI (ui_app.html) byte-unchanged. The Phase 30 stop-rule stands and the
MR-016/MR-017 owner decision is not pre-empted. Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase_igui_task3_governance.py
"""
from __future__ import annotations

import json
from pathlib import Path

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase IGUI Task 3 - model points + in-force ingest "
                "(par_model_v2/viewer/igui_model_points.py; loader-side portfolio validator)")
AFFECTED_COMPONENTS = [
    "par_model_v2/viewer/igui_model_points.py",
    "scripts/run_gui.py",
    "scripts/load_user_inputs.py",
    "scripts/build_phase_igui_task3_governance.py",
    "scripts/build_phase_igui_task3_model_points.py",
    "tests/test_phase_igui_task3_model_points.py",
    "docs/validation/PHASE_IGUI_TASK3_MODEL_POINTS.json",
    "docs/validation/PHASE_IGUI_TASK3_MODEL_POINTS.md",
]
STANDARD_REFERENCES = [
    "SOA ASOP 23 (Data Quality) - model-point completeness / consistency / range "
    "validation and in-force data ingest mapped to the canonical Portfolio schema, "
    "validated fail-loud through the loader before a run is permitted",
    "SOA ASOP 56 (Modeling) section 3.2 / 3.5 - model inputs, intended use, and the "
    "educational-use restriction pending credentialled data + independent review; the "
    "book-scaling preview is DISCLOSED as a non-governed approximation",
    "SOA ASOP 41 (Actuarial Communications) - balance-sheet reconciliation and "
    "scaling/booking disclosure surfaced to the user before they run the model",
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
            "Implemented Task 3 (the D2_policy_model_points domain) of the owner-directed "
            "Phase IGUI input+run GUI, following Task 1 (design note) and Task 2 (run "
            "controls). (1) MODEL-POINT CORE par_model_v2/viewer/igui_model_points.py "
            "(stdlib only): a declarative editable model-point row spec (the eight "
            "Portfolio columns - product type / issue age / gender / term / sum assured / "
            "annual premium / policy count / vested bonus), normalisation of a raw GUI row "
            "list (fail-loud per row+field), a balance-sheet normaliser + reconciler that "
            "sums the asset rows and checks them against the user's stated total with the "
            "SAME tolerance the Excel parser uses, a DISCLOSED non-governed book-scaling "
            "preview computed exactly as scripts/run_model.resolve_product reports it "
            "(inforce-weighted representative PAR point + linear scale factor; GMMB rows "
            "disclosed by count), a CSV/JSON in-force ingest that maps flexible "
            "column/key names onto the canonical Portfolio schema, and a builder to the "
            "model_inputs.json {portfolio, balance_sheet, totals} sub-schema. (2) RUNNER "
            "scripts/run_gui.py: serves a SELF-CONTAINED model-points page (interactive "
            "add/edit/delete rows, an in-force file-ingest control, and a live "
            "reconciliation + book-scaling panel; zero external references) at "
            "GET /model-points and exposes POST /validate_portfolio, /save_portfolio, "
            "/reconcile, /ingest; the existing run-controls page + endpoints are unchanged "
            "and the model_inputs.json merge preserves the Task-2 {currency, run_settings}. "
            "(3) LOADER ROUND-TRIP: added a purely additive "
            "scripts/load_user_inputs.validate_portfolio_dict that validates the "
            "{portfolio, balance_sheet} fragment with the SAME rules as parse_portfolio / "
            "parse_balance_sheet (no openpyxl); the GUI round-trips EVERY payload through it "
            "fail-loud before a write/run. The Excel template path is unchanged. Tests: 24 "
            "new unittest cases green (row add/edit/delete normalisation, reconciliation incl. "
            "mismatch, book-scaling weights, CSV+JSON ingest incl. alias mapping + rejection, "
            "loader round-trip incl. bad-product / cash-dividend-bonus / GMMB-only / "
            "balance-mismatch rejections, self-contained page, ui_app byte-unchanged, and a "
            "localhost endpoint round-trip). IGUI Task-1 (24) and Task-2 (21) suites stay "
            "green. Task-3 gate validate_task3_gate ok:true 30 checks. Also repaired a "
            "latent truncation in scripts/run_gui.py (main()'s final 'return 0' had been "
            "corrupted to a bare name 'retur' by an earlier in-place write). NO contract "
            "change; NO model parameter change; offline RESULTS UI byte-unchanged; "
            "stop-rule honoured; owner decision not pre-empted."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "phase": "Phase IGUI Task 2 complete (run controls + stdlib local runner)",
            "igui_model_points_module": False,
            "loader_portfolio_validator": False,
            "run_gui_routes": ["/", "/healthz", "/validate", "/save"],
            "ui_contract": "1.21.0",
            "ui_app_sha256": "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65",
        },
        after_snapshot={
            "igui_model_points_module": "par_model_v2/viewer/igui_model_points.py (stdlib only)",
            "igui_new_third_party_runtime_deps": 0,
            "loader_portfolio_validator": "validate_portfolio_dict (additive, no openpyxl)",
            "run_gui_routes": ["/", "/model-points", "/healthz", "/validate", "/save",
                               "/validate_portfolio", "/save_portfolio", "/reconcile", "/ingest"],
            "capabilities": [
                "interactive add/edit/delete of PAR + GMMB model-point rows",
                "CSV/JSON in-force upload mapped to the Portfolio schema (flexible headers)",
                "balance-sheet asset rows + stated-total reconciliation (parser tolerance)",
                "DISCLOSED non-governed book-scaling preview (echoes run_model.resolve_product)"],
            "task3_gate_ok": True,
            "task3_gate_checks": 30,
            "new_unittests": 24,
            "igui_task1_unittests_still_green": 24,
            "igui_task2_unittests_still_green": 21,
            "run_gui_truncation_repaired": True,
            "ui_contract": "1.21.0 (unchanged)",
            "ui_app_sha256": "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65 (byte-unchanged)",
            "results_ui_zero_install_preserved": True,
            "headline_carried_bit_for_bit": "39975.654628199336",
        },
        impact_assessment=(
            "Additive GUI input domain + an additive loader-side validator. NO contract "
            "change, NO model parameter change; the offline RESULTS UI (ui_app.html) is "
            "byte-identical (frozen sha256 asserted by the Task-3 gate). The runner is "
            "localhost-bound and offline; the book-scaling figure is a DISCLOSED "
            "approximation echoing the orchestrator, not a governed result, and pre-empts "
            "no owner decision (MR-016/MR-017 remains with the owner; Phase 30 stop-rule "
            "honoured)."
        ),
        quantitative_impact=(
            "No governed capital figure changed; the headline SCR 39,975.654628199336 is "
            "carried bit-for-bit. Contract unchanged at 1.21.0. Task-3 gate ok:true 30 "
            "checks; 24 new unittests green; IGUI Task-1 (24) + Task-2 (21) suites still "
            "green; 0 new third-party runtime dependencies; 0 outbound network calls; 0 "
            "external refs."
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: Task 3 lands the model-point input domain (interactive add/edit/delete "
        "of PAR + GMMB rows, CSV/JSON in-force ingest to the Portfolio schema, "
        "balance-sheet reconciliation, and a DISCLOSED book-scaling preview) plus an "
        "additive loader-side validate_portfolio_dict. ZERO new third-party runtime "
        "dependency; the runner stays 127.0.0.1-bound and offline; every payload "
        "round-trips fail-loud through the loader before a write; offline RESULTS UI "
        "byte-unchanged (frozen sha256). 24 new unittests + Task-3 gate (30 checks) green; "
        "IGUI Task-1 (24) + Task-2 (21) suites green. Headline carried bit-for-bit; NO "
        "contract change; NO model parameter change; stop-rule honoured.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. The input+run GUI now collects the policy/model-point "
        "data domain: the user can add/edit/delete PAR + GMMB model points, upload an "
        "in-force CSV/JSON, see backing-asset reconciliation and a disclosed book-scaling "
        "preview, all validated through the real loader before any run. Next cycle = Task 4 "
        "(assumptions, owner-gated). The MR-016/MR-017 dependence decision remains PENDING "
        "and entirely with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase IGUI Task 3 model points + "
               "in-force ingest (par_model_v2/viewer/igui_model_points.py); additive "
               "loader-side validate_portfolio_dict; 0 new third-party deps; "
               "localhost-only/offline; ui_app.html byte-unchanged; NO contract change; "
               "NO model parameter change"),
        details={"record_id": rec.record_id, "contract": "1.21.0 (unchanged)",
                 "task3_gate_checks": 30, "new_unittests": 24,
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
