#!/usr/bin/env python3
"""Phase 35 Task 4 (gap A3) - governance for the one-page printable model-card
cover on the zero-install offline UI.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. Presentation /
print only: NO contract change (ui_data.json and the embedded payload are
byte-identical, so the Phase 35 Task 3 (gap A2) per-section SHA-256 digests still
verify), NO model parameter changes. The binding Phase 30 stop-rule stands and
the MR-016/MR-017 owner decision is not pre-empted (the model card renders the
decision field BLANK). Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase35_task4_a3_governance.py
"""
from __future__ import annotations
import json
from pathlib import Path
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase 35: Offline UI Accessibility & Evidence-Integrity Deepening"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase 35 Task 4 (gap A3) - one-page printable model-card cover "
                "on the zero-install offline UI")
AFFECTED_COMPONENTS = [
    "scripts/build_phase35_task4_a3_modelcard.py",
    "scripts/ui_app_self_test.cjs",
    "ui_app.html",
]
STANDARD_REFERENCES = [
    "SOA ASOP 41 (Actuarial Communications) - concise model identity / scope / "
    "limitations disclosure on a single reviewer-facing page",
    "SOA ASOP 56 s3.5 / s4 (model limitations and intended-use disclosure)",
    "Model risk governance - reproducible, provenance-stamped reporting surface",
]


def apply(store: GovernanceStore, ui_checks_before: int, ui_checks_after: int) -> dict:
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        for r in store.change_records:
            if r.title == CHANGE_TITLE:
                return {"added": False, "record_id": r.record_id,
                        "status": r.status.value, "reason": "idempotent"}
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Closed gap A3 of the Phase 35 design note: a one-page, ASOP-41-style "
            "printable MODEL CARD cover for the zero-install offline UI. Phase 33 "
            "G3 added a sign-off print cover and Phase 34 H3 a print-all pack, but "
            "there was no SINGLE-PAGE model card for a reviewer who wants one page. "
            "(1) ui_app.html gained a print-only .modelcardcover surface + "
            "renderModelCardCover() that assembles, BIT-FOR-BIT from the embedded "
            "snapshot, the model identity (PAR Fund Stochastic ALM & TVOG v0.2.0, "
            "EDUCATIONAL ONLY classification), scope, the governed component SCR "
            "headline carried EXACTLY (39,975.654628199336) and never re-labelled "
            "(the governed label is carried verbatim), the top limitations, the "
            "Phase 30 binding stop-rule status (applied; dependence-FORM escalation "
            "ended; MR-016/MR-017 KEEP_OPEN), a BLANK owner-decision field, and a "
            "provenance stamp (contract version + build stamp). Nothing is "
            "recomputed. (2) A compact one-page @media print block + the existing "
            "html.printall toggle reveal the cover for printing; it is hidden on "
            "screen. (3) NO contract change: ui_data.json and the embedded payload "
            "are byte-identical, so the Phase 35 Task 3 (gap A2) per-section "
            "SHA-256 digests still verify in the browser by construction. (4) "
            "Tests: 10 new ui_app self-test checks (%d -> %d, ok:true, 0 network / "
            "0 JS errors) covering cover presence, model identity, scope, the "
            "bit-for-bit headline (exact string + never-relabelled governed "
            "label), the three limitations, the Phase 30 stop-rule line, the BLANK "
            "owner-decision field, the provenance stamp, and the one-page print "
            "CSS. All eight offline self-tests remain ok:true 0/0. Zero-install "
            "preserved (0 external refs, single self-contained HTML). NO model "
            "parameter changes; binding stop-rule honoured; owner decision not "
            "pre-empted." % (ui_checks_before, ui_checks_after)
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "ui_contract": "1.20.0",
            "one_page_model_card_cover": False,
            "reviewer_print_surfaces": "G3 sign-off cover + H3 print-all pack",
            "ui_app_self_test_checks": ui_checks_before,
            "offline_self_tests": 8,
        },
        after_snapshot={
            "ui_contract": "1.20.0 (unchanged - presentation/print only)",
            "one_page_model_card_cover": True,
            "headline_carried_bit_for_bit": "39975.654628199336",
            "owner_decision_field": "BLANK (MR-016/MR-017 not pre-empted)",
            "provenance_stamped": True,
            "payload_byte_identical": True,
            "a2_digests_still_verify": True,
            "network_or_storage_used": False,
            "ui_app_self_test_checks": ui_checks_after,
            "offline_self_tests": 8,
        },
        impact_assessment=(
            "Display / print-layer pass only. NO contract change; the embedded "
            "payload is byte-identical so every governed read-out (and the Phase "
            "35 Task 3 content digests) is bit-identical. The model card recomputes "
            "nothing - it carries the governed frozen-t headline verbatim - and "
            "renders the owner-decision field BLANK, so the MR-016/MR-017 decision "
            "is not pre-empted. Zero-install invariants preserved (0 external refs, "
            "single self-contained HTML, no storage API)."
        ),
        quantitative_impact=(
            "No governed capital figure changed. Contract unchanged at 1.20.0 "
            "(presentation/print only; payload byte-identical). ui_app self-test "
            "%d -> %d checks ok:true 0/0; all 8 offline self-tests green. External "
            "refs remain 0." % (ui_checks_before, ui_checks_after)
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: presentation/print only, NO contract change (ui_data.json + "
        "embedded payload byte-identical; A2 per-section SHA-256 digests still "
        "verify); the model card is assembled bit-for-bit from the embedded "
        "snapshot and recomputes nothing; governed headline 39,975.654628199336 "
        "carried exactly and never re-labelled; owner-decision field BLANK; "
        "ui_app self-test 368 checks ok:true 0/0 plus 7 other offline suites "
        "green; 0 external refs; no network / no storage API; no model parameter "
        "changes.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Gap A3 of the Phase 35 design note is closed: the "
        "offline UI now prints a single-page ASOP-41-style model card (identity, "
        "scope, governed headline, top limitations, Phase 30 stop-rule status, "
        "provenance stamp) with the owner-decision field BLANK. PRESENTATION / "
        "PRINT ONLY - the MR-016/MR-017 dependence decision remains PENDING and "
        "entirely with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase 35 Task 4 one-page "
               "printable model-card cover (gap A3); NO contract change "
               "(payload byte-identical); governed figures bit-identical; owner "
               "decision not pre-empted"),
        details={"record_id": rec.record_id, "contract": "1.20.0 (unchanged)",
                 "one_page_model_card_cover": True,
                 "ui_app_self_test_checks": ui_checks_after,
                 "affected_components": AFFECTED_COMPONENTS}))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main() -> int:
    data = json.load(open("ui_data.json", encoding="utf-8"))
    assert data["contract_version"] == "1.20.0", "expected contract 1.20.0 (unchanged)"
    html = open("ui_app.html", encoding="utf-8").read()
    assert "function renderModelCardCover(" in html, "model-card cover not present in ui_app.html"
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_chg, n_aud = len(store.change_records), len(store.audit_trail.all())
    res = apply(store, ui_checks_before=358, ui_checks_after=368)
    if not store.audit_trail.verify_all():
        print("AUDIT INTEGRITY FAILED - store NOT saved")
        return 1
    if res.get("added"):
        GOV_PATH.write_text(store.to_json(), encoding="utf-8")
    print(json.dumps({
        "governance": res,
        "change_records": "%d -> %d" % (n_chg, len(store.change_records)),
        "audit_entries": "%d -> %d" % (n_aud, len(store.audit_trail.all())),
        "audit_integrity_ok": store.audit_trail.verify_all(),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
