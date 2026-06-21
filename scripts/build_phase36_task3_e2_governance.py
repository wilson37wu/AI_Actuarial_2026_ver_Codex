#!/usr/bin/env python3
"""Phase 36 Task 3 (gap E2) - governance for the consolidated global glossary &
methodology explainer surface on the zero-install offline UI.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. ADDITIVE
contract bump 1.20.0 -> 1.21.0: ONE new top-level key (``explainer``) is added;
every pre-existing ui_data key renders bit-identically and the governed figures
are unchanged. DISPLAY-ONLY: the explainer recomputes no model quantity and
contains no model figure (the nine base definitions and all limitation text are
carried VERBATIM from the owner decision pack). NO model parameter changes; the
binding Phase 30 stop-rule stands and the MR-016/MR-017 owner decision is not
pre-empted. Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase36_task3_e2_governance.py
"""
from __future__ import annotations
import json
from pathlib import Path
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase 36: Offline UI Accessibility Completion & Educational Reproducibility"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase 36 Task 3 (gap E2) - consolidated global glossary & "
                "methodology explainer surface on the zero-install offline UI")
AFFECTED_COMPONENTS = [
    "scripts/build_phase36_task3_e2_glossary.py",
    "scripts/build_ui_pipeline.py",
    "scripts/ui_app_self_test.cjs",
    "par_model_v2/viewer/contract_guard.py",
    "ui_data.json",
    "ui_app.html",
]
STANDARD_REFERENCES = [
    "SOA ASOP 41 (Actuarial Communications) - reviewer-facing data dictionary so "
    "the read-outs can be understood without the model repository",
    "IFoA Model Practice Note section 4 (documentation, communication)",
    "SOA ASOP 56 sections 3.4-3.6 (documentation of model methodology, "
    "reliance, limitations)",
    "WAI-ARIA 1.2 - accessible read-only tabular disclosure surface",
]


def apply(store, ui_before, ui_after):
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        for r in store.change_records:
            if r.title == CHANGE_TITLE:
                return {"added": False, "record_id": r.record_id,
                        "status": r.status.value, "reason": "idempotent"}
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Closed gap E2 of the Phase 36 design note: promoted the "
            "sign-off-pack-scoped glossary (owner_decision_p31.glossary) to a "
            "GLOBAL, build-time-assembled glossary / data dictionary covering every "
            "governed read-out across the 18 result tabs, surfaced as a new "
            "read-only 'Methodology & Glossary' tab/panel. (1) ui_data.json gained "
            "ONE new top-level key 'explainer' (additive contract bump 1.20.0 -> "
            "1.21.0): 23 terms (the 9 base terms carried VERBATIM plus 14 authored "
            "plain-language methodology terms), each with definition + method/"
            "assumption basis + limitation provenance; an 18-tab coverage map; and "
            "verbatim-carried roots (glossary, limitations, standard_references, "
            "figure_provenance, how_to_read copied bit-for-bit from "
            "owner_decision_p31). (2) The nine base definitions and ALL limitation "
            "text are copied programmatically from the embedded payload, so they "
            "are carried bit-for-bit; nothing is re-derived or re-labelled. (3) The "
            "panel is DISPLAY-ONLY: it contains NO model figure and recomputes no "
            "model quantity; every pre-existing ui_data key renders bit-identically "
            "and the governed headline 39,975.654628199336 is unchanged. (4) The "
            "Phase 35 Task 3 (gap A2) per-section SHA-256 digests were recomputed "
            "with the EXACT embedded JS (new 'explainer' section digested; root "
            "digest recomputed) so the in-browser verifier still agrees byte-for-"
            "byte; the H1 contract guard + build pipeline were advanced additively "
            "to 1.21.0 (explainer appended to the required-keys list; key_count "
            "23 -> 24). (5) Tests: +15 ui_app self-test checks (%d -> %d, ok:true, "
            "0 network / 0 JS errors) covering global-glossary presence, the new "
            "tab/panel render, 18-tab coverage, base-definition + limitation + "
            "glossary provenance verbatim carry-through, display-only/no-figure, "
            "the explainer section digest, and contract 1.21.0; all eight offline "
            "self-tests remain ok:true (483 -> 498 total checks). Zero-install "
            "preserved (0 external refs, single self-contained file:// HTML, no "
            "storage API). NO model parameter changes; binding stop-rule honoured; "
            "owner decision not pre-empted." % (ui_before, ui_after)
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "ui_contract": "1.20.0",
            "glossary_scope": "sign-off-pack-scoped (owner_decision_p31.glossary, 9 terms)",
            "global_glossary_surface": False,
            "top_level_keys": 24,
            "ui_app_self_test_checks": ui_before,
            "offline_self_tests": 8,
            "offline_self_test_total_checks": 483,
        },
        after_snapshot={
            "ui_contract": "1.21.0 (additive: +1 top-level key 'explainer')",
            "glossary_scope": "GLOBAL build-time data dictionary (23 terms, 18-tab coverage)",
            "global_glossary_surface": True,
            "top_level_keys": 25,
            "base_definitions_carried_verbatim": True,
            "limitations_carried_verbatim": True,
            "explainer_contains_model_figure": False,
            "headline_carried_bit_for_bit": "39975.654628199336",
            "preexisting_keys_bit_identical": True,
            "a2_digests_recompute_and_verify": True,
            "network_or_storage_used": False,
            "ui_app_self_test_checks": ui_after,
            "offline_self_tests": 8,
            "offline_self_test_total_checks": 498,
        },
        impact_assessment=(
            "Display layer + additive data-contract only. The new 'explainer' key is "
            "the sole addition; every pre-existing key (and the A2 content digests "
            "for them) is bit-identical, and the explainer carries no model figure "
            "and recomputes nothing, so the MR-016/MR-017 dependence decision is not "
            "pre-empted. Zero-install invariants preserved (0 external refs, single "
            "self-contained HTML, no storage API, file:// safe)."
        ),
        quantitative_impact=(
            "No governed capital figure changed. Contract 1.20.0 -> 1.21.0 "
            "(additive; +1 top-level key). ui_app self-test %d -> %d checks ok:true "
            "0/0; all 8 offline self-tests green (483 -> 498 total checks). External "
            "refs remain 0." % (ui_before, ui_after)
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: ADDITIVE contract bump 1.20.0 -> 1.21.0 adding ONLY the "
        "'explainer' key; every pre-existing ui_data key bit-identical (A2 "
        "per-section SHA-256 digests recompute and still verify in-browser; new "
        "explainer section digested, root recomputed). The 9 base definitions and "
        "all limitation text are copied verbatim from owner_decision_p31; the panel "
        "is display-only and contains no model figure; governed headline "
        "39,975.654628199336 carried exactly. ui_app self-test 393 checks ok:true "
        "0/0 plus 7 other offline suites green (498 total); 0 external refs; no "
        "network / no storage API; no model parameter changes.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Gap E2 of the Phase 36 design note is closed: the "
        "offline UI now carries a read-only global 'Methodology & Glossary' data "
        "dictionary (23 terms, 18-tab coverage) assembled at build time, with base "
        "definitions and limitations carried verbatim. DISPLAY-ONLY, ADDITIVE - the "
        "MR-016/MR-017 dependence decision remains PENDING and entirely with the "
        "owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase 36 Task 3 consolidated "
               "global glossary & methodology explainer (gap E2); ADDITIVE contract "
               "1.20.0 -> 1.21.0 (+explainer key); governed figures bit-identical; "
               "owner decision not pre-empted"),
        details={"record_id": rec.record_id, "contract": "1.20.0 -> 1.21.0",
                 "new_top_level_key": "explainer",
                 "glossary_terms": 23, "tab_coverage": 18,
                 "ui_app_self_test_checks": ui_after,
                 "offline_self_test_total_checks": 498,
                 "affected_components": AFFECTED_COMPONENTS}))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main() -> int:
    data = json.load(open("ui_data.json", encoding="utf-8"))
    assert data["contract_version"] == "1.21.0", "expected contract 1.21.0"
    assert "explainer" in data, "explainer key not present in ui_data.json"
    html = open("ui_app.html", encoding="utf-8").read()
    assert "function renderGlossary(" in html, "renderGlossary not present in ui_app.html"
    assert '["glossary","Methodology & Glossary"]' in html, "glossary tab not present"
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_chg, n_aud = len(store.change_records), len(store.audit_trail.all())
    res = apply(store, ui_before=378, ui_after=393)
    if not store.audit_trail.verify_all():
        print("AUDIT INTEGRITY FAILED - store NOT saved")
        return 1
    if res.get("added"):
        GOV_PATH.write_text(store.to_json(), encoding="utf-8")
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
