#!/usr/bin/env python3
"""Phase IGUI Task 4 - governance for the assumptions input domain (owner-gated).

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. This cycle lands
the third staged input domain of the owner-directed input+run GUI: the full
valuation assumption set (mortality base+improvement, lapse/surrender incl.
dynamic policyholder behaviour, expenses, premiums, discount/yield curve,
bonus/crediting & declaration strategy, management-action rules, reinsurance, and
the SCR confidence / benefit share), each round-tripped fail-loud through an
additive loader-side validate_assumptions_dict. OWNER-GATING is the binding
property: the governed/frozen dependence parameters (copula df, grouped-t dfs)
are READ-ONLY echoes - the builder always re-attaches the governed values and the
loader rejects any override, so a GUI payload can never change a governed model
parameter. It adds NO third-party runtime dependency, makes NO model parameter
change, and leaves the zero-install RESULTS UI (ui_app.html) byte-unchanged. The
Phase 30 stop-rule stands and the MR-016/MR-017 owner decision is not pre-empted.
Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase_igui_task4_governance.py
"""
from __future__ import annotations

import json
from pathlib import Path

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase IGUI Task 4 - assumptions input domain (owner-gated) "
                "(par_model_v2/viewer/igui_assumptions.py; loader-side assumptions validator)")
AFFECTED_COMPONENTS = [
    "par_model_v2/viewer/igui_assumptions.py",
    "scripts/run_gui.py",
    "scripts/load_user_inputs.py",
    "scripts/build_phase_igui_task4_governance.py",
    "scripts/build_phase_igui_task4_assumptions.py",
    "tests/test_phase_igui_task4_assumptions.py",
    "docs/validation/PHASE_IGUI_TASK4_ASSUMPTIONS.json",
    "docs/validation/PHASE_IGUI_TASK4_ASSUMPTIONS.md",
]
STANDARD_REFERENCES = [
    "SOA ASOP 52 / IFRS 17 / HKRBC - economic & demographic assumptions "
    "(mortality base + improvement, lapse/surrender incl. dynamic policyholder "
    "behaviour, expenses, premiums, discount/yield curve, bonus declaration, "
    "management actions, reinsurance) surfaced for user entry and validated fail-loud",
    "SOA ASOP 56 (Modeling) section 3.2 / 3.5 - model inputs vs governed parameters: "
    "the dependence structure (copula df, grouped-t dfs, Sigma) stays a READ-ONLY "
    "governed echo; assumption inputs are additive metadata and do not alter the "
    "frozen stochastic basis (owner-gated)",
    "SOA ASOP 41 (Actuarial Communications) - the governed/frozen basis is disclosed "
    "read-only alongside the user-editable assumptions; the educational-use restriction "
    "(credentialled assumptions + independent review) is unchanged",
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
            "Implemented Task 4 (the D3_assumptions domain) of the owner-directed Phase "
            "IGUI input+run GUI, following Task 1 (design note), Task 2 (run controls) and "
            "Task 3 (model points). (1) ASSUMPTIONS CORE "
            "par_model_v2/viewer/igui_assumptions.py (stdlib only): a declarative, grouped "
            "spec of every editable valuation assumption - mortality (base table + "
            "multiplier + annual improvement + floor), lapse/surrender (base lapse + "
            "surrender + dynamic-lapse beta + ITM threshold), expenses (per-policy / "
            "%-premium / inflation), premiums (frequency + indexation), discount (flat rate "
            "OR tenor/rate yield curve), bonus & crediting (declaration strategy + "
            "reversionary + terminal + smoothing), management-action rules (relief sigma / "
            "alpha + dynamic-rule toggle), reinsurance (type + quota share + retention) and "
            "the SCR confidence / benefit share - with normalisation (fail-loud per field), "
            "a discount-curve normaliser, and a builder to the model_inputs.json "
            "{assumptions} sub-schema. (2) OWNER-GATING: the governed/frozen dependence "
            "parameters (copula df 2.9451, grouped-t df_nonfin 37.866, df_fin 8.506) are a "
            "READ-ONLY provenance echo - assumptions_to_model_inputs ALWAYS re-attaches the "
            "governed values (discarding any user-supplied echo) and the loader REJECTS any "
            "override, so a GUI payload can never change a governed model parameter; Sigma / "
            "df / margins stay bit-frozen. (3) RUNNER scripts/run_gui.py: serves a "
            "SELF-CONTAINED assumptions page (grouped inputs + read-only governed basis; "
            "zero external references) at GET /assumptions and exposes POST "
            "/validate_assumptions, /save_assumptions; the run-controls + model-points pages "
            "and endpoints are unchanged and the model_inputs.json merge preserves the prior "
            "{currency, run_settings, portfolio, balance_sheet}. (4) LOADER ROUND-TRIP: "
            "added a purely additive scripts/load_user_inputs.validate_assumptions_dict that "
            "validates the {assumptions} fragment (bounds, enums, bool, discount curve) and "
            "enforces the read-only governed echo; the Excel template path is unchanged. "
            "Tests: 21 new unittest cases green (spec/group coverage, default + string "
            "normalisation, bad-number/bad-choice rejection, curve normaliser, loader "
            "round-trip incl. out-of-bounds / negative-expense / curve-mode / direct "
            "frozen-override / unknown-frozen-key rejections, owner-gating echo re-attach, "
            "self-contained page, ui_app byte-unchanged, and a localhost endpoint "
            "round-trip). IGUI Task-1 (24) + Task-2 (21) + Task-3 (24) suites stay green. "
            "Task-4 gate validate_task4_gate ok:true 25 checks. NO contract change; NO model "
            "parameter change; offline RESULTS UI byte-unchanged; stop-rule honoured; owner "
            "decision not pre-empted."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "phase": "Phase IGUI Task 3 complete (model points + in-force ingest)",
            "igui_assumptions_module": False,
            "loader_assumptions_validator": False,
            "run_gui_routes": ["/", "/model-points", "/healthz", "/validate", "/save",
                               "/validate_portfolio", "/save_portfolio", "/reconcile", "/ingest"],
            "ui_contract": "1.21.0",
            "ui_app_sha256": "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65",
        },
        after_snapshot={
            "igui_assumptions_module": "par_model_v2/viewer/igui_assumptions.py (stdlib only)",
            "igui_new_third_party_runtime_deps": 0,
            "loader_assumptions_validator": "validate_assumptions_dict (additive, no openpyxl)",
            "run_gui_routes": ["/", "/model-points", "/assumptions", "/healthz", "/validate",
                               "/save", "/validate_portfolio", "/save_portfolio", "/reconcile",
                               "/ingest", "/validate_assumptions", "/save_assumptions"],
            "assumption_groups": ["Mortality", "Lapse & Surrender", "Expenses", "Premiums",
                                  "Discount / Yield", "Bonus & Crediting", "Management Action",
                                  "Reinsurance", "Risk"],
            "owner_gating": {
                "governed_frozen_readonly": {"copula_df_single_t": 2.9451,
                                             "grouped_t_df_nonfin": 37.866,
                                             "grouped_t_df_fin": 8.506},
                "override_neutralised_by_builder": True,
                "override_rejected_by_loader": True,
            },
            "task4_gate_ok": True,
            "task4_gate_checks": 25,
            "new_unittests": 21,
            "igui_task1_unittests_still_green": 24,
            "igui_task2_unittests_still_green": 21,
            "igui_task3_unittests_still_green": 24,
            "ui_contract": "1.21.0 (unchanged)",
            "ui_app_sha256": "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65 (byte-unchanged)",
            "results_ui_zero_install_preserved": True,
            "headline_carried_bit_for_bit": "39975.654628199336",
        },
        impact_assessment=(
            "Additive GUI input domain + an additive loader-side validator. NO contract "
            "change, NO model parameter change; the offline RESULTS UI (ui_app.html) is "
            "byte-identical (frozen sha256 asserted by the Task-4 gate). The runner is "
            "localhost-bound and offline. OWNER-GATING holds by construction: the governed "
            "dependence parameters are a read-only echo that the builder always re-attaches "
            "and the loader rejects any override of, so surfacing assumption inputs cannot "
            "change the frozen stochastic basis. Pre-empts no owner decision (MR-016/MR-017 "
            "remains with the owner; Phase 30 stop-rule honoured)."
        ),
        quantitative_impact=(
            "No governed capital figure changed; the headline SCR 39,975.654628199336 is "
            "carried bit-for-bit. Copula df 2.9451 / grouped-t dfs 37.866 & 8.506 stay "
            "frozen and read-only. Contract unchanged at 1.21.0. Task-4 gate ok:true 25 "
            "checks; 21 new unittests green; IGUI Task-1 (24) + Task-2 (21) + Task-3 (24) "
            "suites still green; 0 new third-party runtime dependencies; 0 outbound network "
            "calls; 0 external refs."
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: Task 4 lands the assumptions input domain (mortality base+improvement, "
        "lapse/surrender incl. dynamic behaviour, expenses, premiums, discount/yield curve, "
        "bonus declaration, management actions, reinsurance, SCR confidence/benefit share) "
        "plus an additive loader-side validate_assumptions_dict. OWNER-GATING holds: the "
        "governed dependence parameters (copula df, grouped-t dfs) are read-only - the "
        "builder re-attaches the governed echo and the loader rejects any override; the "
        "frozen stochastic basis is unchanged. ZERO new third-party runtime dependency; the "
        "runner stays 127.0.0.1-bound and offline; every payload round-trips fail-loud "
        "through the loader before a write; offline RESULTS UI byte-unchanged (frozen "
        "sha256). 21 new unittests + Task-4 gate (25 checks) green; IGUI Task-1 (24) + "
        "Task-2 (21) + Task-3 (24) suites green. Headline carried bit-for-bit; NO contract "
        "change; NO model parameter change; stop-rule honoured.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. The input+run GUI now collects the full assumptions "
        "domain: the user can enter mortality (base + improvement), lapse/surrender incl. "
        "dynamic policyholder behaviour, expenses, premiums, discount rate / yield curve, "
        "bonus/crediting & declaration strategy, management-action rules and reinsurance, "
        "all validated through the real loader before any run, while the governed/frozen "
        "dependence parameters are shown read-only and can never be changed from the GUI. "
        "Next cycle = Task 5 (ESG / economic-scenario inputs, stop-rule-bounded). The "
        "MR-016/MR-017 dependence decision remains PENDING and entirely with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase IGUI Task 4 assumptions "
               "(owner-gated) (par_model_v2/viewer/igui_assumptions.py); additive "
               "loader-side validate_assumptions_dict; governed/frozen dependence "
               "parameters read-only (override neutralised + rejected); 0 new third-party "
               "deps; localhost-only/offline; ui_app.html byte-unchanged; NO contract "
               "change; NO model parameter change"),
        details={"record_id": rec.record_id, "contract": "1.21.0 (unchanged)",
                 "task4_gate_checks": 25, "new_unittests": 21,
                 "new_third_party_runtime_deps": 0,
                 "governed_frozen_readonly": {"copula_df_single_t": 2.9451,
                                              "grouped_t_df_nonfin": 37.866,
                                              "grouped_t_df_fin": 8.506},
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
