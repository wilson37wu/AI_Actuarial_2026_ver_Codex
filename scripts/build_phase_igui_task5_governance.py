#!/usr/bin/env python3
"""Phase IGUI Task 5 - governance for the ESG / economic-scenario input domain.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. This cycle lands
the fourth staged input domain of the owner-directed input+run GUI: the ESG /
economic-scenario calibration, surfaced STOP-RULE-BOUNDED. The governed ESG
calibration (G2++/HW short-rate, equity GBM, credit-spread & liquidity-premium
processes, and the FROZEN dependence structure: single-df t-copula df 2.9451 +
grouped-t block dfs 37.866 / 8.506) is a READ-ONLY provenance echo; the copula
STRUCTURE is pinned to 'single_t_grouped_FROZEN' and the loader rejects any other
value (the Phase 30 stop-rule guard). The only settable inputs are bounded,
owner-gated provenance/metadata (market data, scenario label, calibration
targets) that do NOT feed the engine. It adds NO third-party runtime dependency,
makes NO model parameter change, leaves the zero-install RESULTS UI (ui_app.html)
byte-unchanged, and does NOT pre-empt the MR-016/MR-017 owner decision. Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase_igui_task5_governance.py
"""
from __future__ import annotations

import json
from pathlib import Path

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase IGUI Task 5 - ESG / economic-scenario input domain (stop-rule-bounded, "
                "owner-gated) (par_model_v2/viewer/igui_esg.py; loader-side ESG validator)")
AFFECTED_COMPONENTS = [
    "par_model_v2/viewer/igui_esg.py",
    "scripts/run_gui.py",
    "scripts/load_user_inputs.py",
    "scripts/build_phase_igui_task5_governance.py",
    "scripts/build_phase_igui_task5_esg.py",
    "tests/test_phase_igui_task5_esg.py",
    "docs/validation/PHASE_IGUI_TASK5_ESG.json",
    "docs/validation/PHASE_IGUI_TASK5_ESG.md",
]
STANDARD_REFERENCES = [
    "SOA ASOP 56 (Modeling) section 3.2 / 3.5 - model inputs vs governed parameters: "
    "the economic-scenario calibration and the dependence structure (copula df, grouped-t "
    "dfs, Sigma) stay a READ-ONLY governed echo; ESG inputs are additive provenance/metadata "
    "and do not alter the frozen stochastic basis (stop-rule-bounded, owner-gated)",
    "Phase 30 dependence stop-rule - NO new copula-structure candidates: the copula structure "
    "is pinned to the frozen single-df-t / grouped-t basis; the loader rejects any payload "
    "naming a different structure, so the GUI cannot introduce a new candidate; MR-016/MR-017 "
    "remains entirely with the owner",
    "SOA ASOP 41 (Actuarial Communications) - the governed/frozen ESG basis is disclosed "
    "read-only alongside the user-editable market-data & calibration-target provenance; the "
    "educational-use restriction (credentialled, market-consistent calibration + independent "
    "review) is unchanged",
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
            "Implemented Task 5 (the D4_esg_economic domain) of the owner-directed Phase "
            "IGUI input+run GUI, following Task 1 (design note), Task 2 (run controls), "
            "Task 3 (model points) and Task 4 (assumptions). (1) ESG CORE "
            "par_model_v2/viewer/igui_esg.py (stdlib only): a declarative, grouped spec of "
            "the SETTABLE ESG-provenance inputs - market data (valuation date, yield-curve "
            "source, equity-index reference), scenario set (label + documented scenario "
            "count) and calibration TARGETS (market 10y rate, equity vol, credit spread, "
            "basis note) - with fail-loud normalisation (per-field; incl. an ISO-date "
            "validator) and a builder to the model_inputs.json {esg} sub-schema. (2) "
            "STOP-RULE / OWNER-GATING: the governed ESG calibration (G2++/HW short-rate "
            "mean_reversion_x 0.10 / y 0.35 / vol_x 0.010 / vol_y 0.006 / long_run 0.025, "
            "equity vol 0.22 / div 0.025 / ERP 0.045 / rate-equity corr -0.15, credit "
            "reversion 0.30 / long_run 0.015, liquidity reversion 0.60 / long_run 0.006) and "
            "the FROZEN dependence structure (copula df 2.9451, grouped-t df_nonfin 37.866, "
            "df_fin 8.506, structure 'single_t_grouped_FROZEN') are a READ-ONLY provenance "
            "echo; esg_to_model_inputs ALWAYS re-attaches the governed values (discarding any "
            "user-supplied echo) and the loader REJECTS any override; the copula STRUCTURE is "
            "pinned and any other value - in the echo OR smuggled as a top-level esg key - is "
            "rejected (the Phase 30 stop-rule guard), so a GUI payload can never change a "
            "governed parameter or introduce a new copula-structure candidate. (3) RUNNER "
            "scripts/run_gui.py: serves a SELF-CONTAINED ESG page (grouped settable inputs + "
            "read-only governed basis + an on-page stop-rule banner; zero external references) "
            "at GET /esg and exposes POST /validate_esg, /save_esg; the prior pages/endpoints "
            "are unchanged and the model_inputs.json merge preserves the prior {currency, "
            "run_settings, portfolio, balance_sheet, assumptions}. (4) LOADER ROUND-TRIP: "
            "added a purely additive scripts/load_user_inputs.validate_esg_dict that validates "
            "the {esg} fragment (settable bounds, required text, ISO date) and enforces the "
            "read-only governed echo + the stop-rule structure pin; the Excel template path is "
            "unchanged. Tests: 24 new unittest cases green (spec/group coverage, default + "
            "string normalisation, bad-number/bad-date rejection, loader round-trip incl. "
            "out-of-bounds / empty-text / direct frozen-override / unknown-frozen-key "
            "rejections, the stop-rule guard for a new structure in the echo AND smuggled "
            "top-level, owner-gating echo re-attach, self-contained page, ui_app byte-unchanged, "
            "and a localhost endpoint round-trip). IGUI Task-1 (24) + Task-2 (21) + Task-3 (24) "
            "+ Task-4 (21) suites stay green (114 IGUI tests total). Task-5 gate "
            "validate_task5_gate ok:true 27 checks. NO contract change; NO model parameter "
            "change; offline RESULTS UI byte-unchanged; stop-rule honoured; owner decision not "
            "pre-empted."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "phase": "Phase IGUI Task 4 complete (assumptions, owner-gated)",
            "igui_esg_module": False,
            "loader_esg_validator": False,
            "run_gui_routes": ["/", "/model-points", "/assumptions", "/healthz", "/validate",
                               "/save", "/validate_portfolio", "/save_portfolio", "/reconcile",
                               "/ingest", "/validate_assumptions", "/save_assumptions"],
            "ui_contract": "1.21.0",
            "ui_app_sha256": "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65",
        },
        after_snapshot={
            "igui_esg_module": "par_model_v2/viewer/igui_esg.py (stdlib only)",
            "igui_new_third_party_runtime_deps": 0,
            "loader_esg_validator": "validate_esg_dict (additive, no openpyxl)",
            "run_gui_routes": ["/", "/model-points", "/assumptions", "/esg", "/healthz",
                               "/validate", "/save", "/validate_portfolio", "/save_portfolio",
                               "/reconcile", "/ingest", "/validate_assumptions",
                               "/save_assumptions", "/validate_esg", "/save_esg"],
            "esg_groups": ["Market Data", "Scenario Set", "Calibration Targets"],
            "stop_rule_owner_gating": {
                "frozen_copula_structure": "single_t_grouped_FROZEN",
                "governed_esg_readonly_keys": 18,
                "override_neutralised_by_builder": True,
                "override_rejected_by_loader": True,
                "new_structure_candidate_rejected": True,
                "mr_016_017_pre_empted": False,
            },
            "task5_gate_ok": True,
            "task5_gate_checks": 27,
            "new_unittests": 24,
            "igui_tests_total_green": 114,
            "ui_contract": "1.21.0 (unchanged)",
            "ui_app_sha256": "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65 (byte-unchanged)",
            "results_ui_zero_install_preserved": True,
            "headline_carried_bit_for_bit": "39975.654628199336",
        },
        impact_assessment=(
            "Additive GUI input domain + an additive loader-side validator. NO contract "
            "change, NO model parameter change; the offline RESULTS UI (ui_app.html) is "
            "byte-identical (frozen sha256 asserted by the Task-5 gate). The runner is "
            "localhost-bound and offline. STOP-RULE + OWNER-GATING hold by construction: the "
            "governed ESG calibration is a read-only echo the builder always re-attaches and "
            "the loader rejects any override of, and the copula structure is pinned so no new "
            "dependence-structure candidate can be introduced from the GUI. Pre-empts no owner "
            "decision (MR-016/MR-017 remains with the owner; Phase 30 stop-rule honoured)."
        ),
        quantitative_impact=(
            "No governed capital figure changed; the headline SCR 39,975.654628199336 is "
            "carried bit-for-bit. Copula df 2.9451 / grouped-t dfs 37.866 & 8.506 and the "
            "marginal-process calibration stay frozen and read-only; copula structure pinned "
            "to single_t_grouped_FROZEN. Contract unchanged at 1.21.0. Task-5 gate ok:true 27 "
            "checks; 24 new unittests green; IGUI Task-1..4 suites still green (114 total); 0 "
            "new third-party runtime dependencies; 0 outbound network calls; 0 external refs."
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: Task 5 lands the ESG / economic-scenario input domain (market-data & "
        "scenario provenance + calibration targets) plus an additive loader-side "
        "validate_esg_dict. STOP-RULE + OWNER-GATING hold: the governed ESG calibration and "
        "the dependence structure are read-only - the builder re-attaches the governed echo, "
        "the loader rejects any override, and the copula structure is pinned so no new "
        "candidate can be introduced; the frozen stochastic basis is unchanged. ZERO new "
        "third-party runtime dependency; the runner stays 127.0.0.1-bound and offline; every "
        "payload round-trips fail-loud through the loader before a write; offline RESULTS UI "
        "byte-unchanged (frozen sha256). 24 new unittests + Task-5 gate (27 checks) green; "
        "IGUI Task-1..4 suites green (114 total). Headline carried bit-for-bit; NO contract "
        "change; NO model parameter change; stop-rule honoured.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. The input+run GUI now surfaces the ESG / economic-scenario "
        "domain: the user sees the governed calibration (rate / equity / credit / liquidity "
        "and the frozen dependence structure) read-only and can record the market-data and "
        "calibration-target provenance around it, all validated through the real loader "
        "before any run, while the governed parameters and copula structure can never be "
        "changed from the GUI (Phase 30 stop-rule enforced). Next cycle = Task 6 (validation "
        "surfacing + governance gating before run). The MR-016/MR-017 dependence decision "
        "remains PENDING and entirely with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase IGUI Task 5 ESG / economic "
               "scenarios (stop-rule-bounded, owner-gated) (par_model_v2/viewer/igui_esg.py); "
               "additive loader-side validate_esg_dict; governed ESG calibration + frozen "
               "copula structure read-only (override neutralised + rejected; new-structure "
               "candidate rejected); 0 new third-party deps; localhost-only/offline; "
               "ui_app.html byte-unchanged; NO contract change; NO model parameter change"),
        details={"record_id": rec.record_id, "contract": "1.21.0 (unchanged)",
                 "task5_gate_checks": 27, "new_unittests": 24,
                 "new_third_party_runtime_deps": 0,
                 "frozen_copula_structure": "single_t_grouped_FROZEN",
                 "governed_esg_readonly_keys": 18,
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
