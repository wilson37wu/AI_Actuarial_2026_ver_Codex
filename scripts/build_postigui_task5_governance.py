#!/usr/bin/env python3
"""Post-Phase-IGUI Task 5 (MR-VR-1) - governance for the inner-path
variance-reduction efficiency panel on the zero-install offline UI.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. ADDITIVE
contract bump 1.21.0 -> 1.22.0: ONE new top-level ``ui_data`` key
(``postigui_vr``) is added and a read-only "Variance Reduction (MR-VR-1)" tab/
panel surfaces the governed Task-4 study. DISPLAY-ONLY: every figure is carried
bit-for-bit from docs/validation/POSTIGUI_TASK4_VARIANCE_REDUCTION.json; nothing
is recomputed. Every pre-existing ui_data key renders bit-identically; the A2
per-section SHA-256 digests were recomputed (new postigui_vr section digested,
root recomputed) so the in-browser verifier still agrees. Variance reduction is
a NUMERICAL efficiency change (admissible under the binding Phase 30 stop-rule);
NO model parameter changes; the governed headline 39,975.654628199336 is
unchanged and the MR-016/MR-017 dependence decision is not pre-empted.
Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_postigui_task5_governance.py
"""
from __future__ import annotations
import json
from pathlib import Path
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Post-Phase-IGUI: Stochastic-model efficiency candidates (MR-VR-1)"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Post-Phase-IGUI Task 5 - inner-path variance-reduction "
                "(MR-VR-1) efficiency panel on the zero-install offline UI")
AFFECTED_COMPONENTS = [
    "scripts/build_postigui_task5_vr_panel.py",
    "scripts/build_ui_pipeline.py",
    "scripts/ui_app_self_test.cjs",
    "par_model_v2/viewer/contract_guard.py",
    "tests/test_postigui_task5_vr_panel.py",
    "ui_data.json",
    "ui_app.html",
]
STANDARD_REFERENCES = [
    "Glasserman, Monte Carlo Methods in Financial Engineering (2004) - "
    "antithetic variates, common random numbers, quasi-Monte Carlo variance "
    "reduction and work-normalised efficiency",
    "L'Ecuyer (2018) Randomized Quasi-Monte Carlo - RQMC effective-sample-size "
    "and convergence",
    "SOA ASOP 56 sections 3.4-3.6 (documentation of model methodology, numerical "
    "method, reliance and limitations)",
    "SOA ASOP 41 (Actuarial Communications) - reviewer-facing efficiency "
    "read-out so the variance-reduction evidence is auditable without the model "
    "repository",
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
            "Surfaced the governed MR-VR-1 inner-path variance-reduction study "
            "(Post-Phase-IGUI Task 4) as a read-only 'Variance Reduction "
            "(MR-VR-1)' tab/panel on the zero-install offline UI. (1) ui_data.json "
            "gained ONE new top-level key 'postigui_vr' (additive contract bump "
            "1.21.0 -> 1.22.0): the four techniques (crude / antithetic / CRN / "
            "Sobol-RQMC), the work-normalised VR ratios with 95%% CIs (antithetic "
            "1.882x, CRN 18.93x, Sobol-RQMC 2241.11x; antithetic and the two "
            "useful levers dispositioned vs the 1.5x bar), the effective-sample-"
            "size per technique, the inner-path counts n* for target SE_rel=1%%, "
            "the unbiasedness panel (all estimators within 0.5%% of the analytic / "
            "crude reference), the antithetic-at-99.5%% INEFFECTIVE disclosure "
            "(work-normalised ratio 1.314x, 95%% CI below the 1.5x bar, the same "
            "qualitative finding as the recorded outer-basis precedents 0.72x / "
            "0.78x), the governed-headline invariance, and the adoption-"
            "materiality verdict. (2) DISPLAY-ONLY: every figure is copied bit-for-"
            "bit from docs/validation/POSTIGUI_TASK4_VARIANCE_REDUCTION.json "
            "(study digest cc0c2fea...); nothing is recomputed in the layer or in "
            "the browser. (3) The governed headline 39,975.654628199336 is "
            "BIT-IDENTICAL before/after and is not relabelled; the indicated "
            "adoption dSCR (-1.38e-05 rel) is IMMATERIAL and REPORTED, NOT applied "
            "- the production estimator and headline stay frozen. (4) The Phase 35 "
            "Task 3 (A2) per-section SHA-256 digests were recomputed with the EXACT "
            "embedded JS (new 'postigui_vr' section digested; root digest "
            "recomputed) so the in-browser verifier still agrees byte-for-byte; "
            "the H1 contract guard + the build pipeline were advanced additively to "
            "1.22.0 (postigui_vr appended to required-keys; key_count 24 -> 25). "
            "(5) Tests: +16 ui_app self-test checks (%d -> %d, ok:true, 0 network "
            "/ 0 JS errors; tabCount 19 -> 20) covering the panel render, the "
            "ratio/ESS/n* tables, the bit-for-bit carry-through, the antithetic-"
            "99.5%% ineffective disclosure, the reported-not-applied adoption "
            "verdict, the headline invariance, the section digest and contract "
            "1.22.0; new pure-Python suite tests/test_postigui_task5_vr_panel.py "
            "(13 checks); offline_viewer (11) and combined_gui (27) self-tests "
            "remain ok:true. Zero-install preserved (0 external refs, single "
            "self-contained file:// HTML, no storage API). Variance reduction is a "
            "numerical-efficiency change admissible under the Phase 30 stop-rule; "
            "NO model parameter changes; owner decision not pre-empted." % (
                ui_before, ui_after)
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "ui_contract": "1.21.0",
            "vr_study_surfaced_offline": False,
            "top_level_keys": 24,
            "ui_app_self_test_checks": ui_before,
            "ui_app_tab_count": 19,
        },
        after_snapshot={
            "ui_contract": "1.22.0 (additive: +1 top-level key 'postigui_vr')",
            "vr_study_surfaced_offline": True,
            "top_level_keys": 25,
            "figures_carried_bit_for_bit": True,
            "vr_study_digest": "cc0c2fea2bf9b86db75f6239a9ba6e3e0a1577a1e1290e24ce13732eb0c0f0d7",
            "headline_bit_identical": "39975.654628199336",
            "indicated_dscr_rel": -1.380833590586369e-05,
            "adoption_applied": False,
            "antithetic_995_useful": False,
            "preexisting_keys_bit_identical": True,
            "a2_digests_recompute_and_verify": True,
            "network_or_storage_used": False,
            "ui_app_self_test_checks": ui_after,
            "ui_app_tab_count": 20,
        },
        impact_assessment=(
            "Display layer + additive data-contract only. The new 'postigui_vr' "
            "key is the sole addition; every pre-existing key (and its A2 content "
            "digest) is bit-identical, the panel carries no recomputation, the "
            "governed headline is unchanged and the variance-reduced estimator is "
            "disclosed/not adopted, so the MR-016/MR-017 dependence decision and "
            "the production headline are not pre-empted. Zero-install invariants "
            "preserved (0 external refs, single self-contained HTML, no storage "
            "API, file:// safe). Variance reduction is a numerical-efficiency "
            "change, admissible under the binding Phase 30 stop-rule."
        ),
        quantitative_impact=(
            "No governed capital figure changed (headline 39,975.654628199336 "
            "bit-identical; indicated adoption dSCR -1.38e-05 rel, immaterial, not "
            "applied). Contract 1.21.0 -> 1.22.0 (additive; +1 top-level key). "
            "ui_app self-test %d -> %d checks ok:true 0/0; offline_viewer 11 + "
            "combined_gui 27 green. External refs remain 0." % (ui_before, ui_after)
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: ADDITIVE contract bump 1.21.0 -> 1.22.0 adding ONLY the "
        "'postigui_vr' key; every pre-existing ui_data key bit-identical (A2 "
        "per-section SHA-256 digests recompute and still verify in-browser; new "
        "postigui_vr section digested, root recomputed). All VR figures carried "
        "bit-for-bit from the governed Task-4 report; the panel is display-only "
        "and recomputes nothing; governed headline 39,975.654628199336 carried "
        "exactly and not relabelled; antithetic-99.5% disclosed ineffective; "
        "adoption reported-not-applied. ui_app self-test 421 checks ok:true 0/0 "
        "(tabCount 20) plus offline_viewer 11 + combined_gui 27 green; 13 new "
        "pure-Python checks; pipeline chain validates to 1.22.0; 0 external refs; "
        "no model parameter changes.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. The offline UI now carries a read-only 'Variance "
        "Reduction (MR-VR-1)' efficiency panel (work-normalised VR ratios + CIs, "
        "effective sample size, target-SE inner-path counts n*, unbiasedness, and "
        "the antithetic-99.5% ineffective disclosure), display-only and additive. "
        "Variance reduction is a numerical-efficiency change under the Phase 30 "
        "stop-rule; the governed estimator/headline stay FROZEN and the MR-016/"
        "MR-017 dependence decision remains entirely with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Post-Phase-IGUI Task 5 "
               "MR-VR-1 variance-reduction efficiency panel; ADDITIVE contract "
               "1.21.0 -> 1.22.0 (+postigui_vr key); governed figures bit-"
               "identical; variance reduction is efficiency-only; owner decision "
               "not pre-empted"),
        details={"record_id": rec.record_id, "contract": "1.21.0 -> 1.22.0",
                 "new_top_level_key": "postigui_vr",
                 "vr_techniques": 4,
                 "headline_bit_identical": "39975.654628199336",
                 "adoption_applied": False,
                 "ui_app_self_test_checks": ui_after,
                 "ui_app_tab_count": 20,
                 "affected_components": AFFECTED_COMPONENTS}))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main() -> int:
    data = json.load(open("ui_data.json", encoding="utf-8"))
    assert data["contract_version"] == "1.22.0", "expected contract 1.22.0"
    assert "postigui_vr" in data, "postigui_vr key not present in ui_data.json"
    html = open("ui_app.html", encoding="utf-8").read()
    assert "function renderVrPanel(" in html, "renderVrPanel not present in ui_app.html"
    assert '["vrpanel","Variance Reduction (MR-VR-1)"]' in html, "vr tab not present"
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_chg, n_aud = len(store.change_records), len(store.audit_trail.all())
    res = apply(store, ui_before=405, ui_after=421)
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
