#!/usr/bin/env python3
"""Phase 36 Task 2 (gap E1) - governance for live-region status announcements
(WCAG 2.1 AA SC 4.1.3) on the zero-install offline UI.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. Presentation /
ARIA / JS only: NO contract change (ui_data.json and the embedded payload are
byte-identical, so the Phase 35 Task 3 per-section SHA-256 digests still verify),
NO model parameter changes. The binding Phase 30 stop-rule stands and the
MR-016/MR-017 owner decision is not pre-empted. Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase36_task2_e1_governance.py
"""
from __future__ import annotations
import json
from pathlib import Path
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase 36: Offline UI Accessibility Completion & Educational Reproducibility"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase 36 Task 2 (gap E1) - live-region status announcements "
                "(WCAG 2.1 AA SC 4.1.3) on the zero-install offline UI")
AFFECTED_COMPONENTS = [
    "scripts/build_phase36_task2_e1_live_regions.py",
    "scripts/ui_app_self_test.cjs",
    "ui_app.html",
]
STANDARD_REFERENCES = [
    "WCAG 2.1 AA Success Criterion 4.1.3 Status Messages - programmatic "
    "announcement of dynamic state changes via a polite live region",
    "WAI-ARIA 1.2 - role=status / aria-live=polite / aria-atomic live regions",
    "SOA ASOP 41 (Actuarial Communications) - accessible reviewer-facing "
    "disclosure surface",
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
            "Closed gap E1 of the Phase 36 design note: completed the dynamic half "
            "of WCAG 2.1 AA on the zero-install offline UI. Before, aria-live was "
            "present only on the (visible) contract-mismatch banner; dynamic state "
            "changes produced no programmatic announcement. (1) ui_app.html gained "
            "ONE visually-hidden polite sr-only live region (#srlive, role=status, "
            "aria-live=polite, aria-atomic) and an announce() helper. (2) Four "
            "dynamic surfaces now route a concise text update through it: tab "
            "activation (active tab name; on the Integrity tab also the verify "
            "outcome), global search (result count 'N results for ...'), the "
            "Distribution Explorer slider (its percentile/read-out), and the "
            "content-integrity verifier (verified / content-altered). (3) The "
            "inline distribution read-out (#dx-readout) lost its own aria-live so "
            "#srlive is the single dedicated announcer (no double-speak); the "
            "separate visible contract-mismatch banner is unchanged. Announcements "
            "DESCRIBE already-on-screen state only - the announce path recomputes "
            "NO model figure (governed headline 39,975.654628199336 and every "
            "governed read-out render bit-for-bit). Polite, never assertive (no "
            "interruption); focus never stolen; sr-only and never visible. (4) NO "
            "contract change: ui_data.json and the embedded payload are "
            "byte-identical, so the Phase 35 Task 3 (gap A2) per-section SHA-256 "
            "digests still verify in-browser by construction. (5) Tests: 10 new "
            "ui_app self-test checks (%d -> %d, ok:true, 0 network / 0 JS errors) "
            "covering the single-region presence/role/polite attrs, no-assertive, "
            "the announce() helper, and all four wiring points, plus that the "
            "governed headline stays bit-for-bit and #dx-readout is no longer its "
            "own live region. All eight offline self-tests remain ok:true "
            "(483 total checks). Zero-install preserved (0 external refs, single "
            "self-contained file:// HTML, no storage API). NO model parameter "
            "changes; binding stop-rule honoured; owner decision not pre-empted."
            % (ui_before, ui_after)
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "ui_contract": "1.20.0",
            "live_region_surfaces": "1 (visible contract-mismatch banner only)",
            "dynamic_announcements": False,
            "ui_app_self_test_checks": ui_before,
            "offline_self_tests": 8,
            "offline_self_test_total_checks": 473,
        },
        after_snapshot={
            "ui_contract": "1.20.0 (unchanged - ARIA/JS/presentation only)",
            "dedicated_polite_live_region": "#srlive (sr-only, role=status, aria-live=polite)",
            "wired_surfaces": ["tab_activation", "search_result_count",
                               "distribution_slider_readout", "integrity_verify_result"],
            "assertive_live_region_used": False,
            "headline_carried_bit_for_bit": "39975.654628199336",
            "payload_byte_identical": True,
            "a2_digests_still_verify": True,
            "network_or_storage_used": False,
            "ui_app_self_test_checks": ui_after,
            "offline_self_tests": 8,
            "offline_self_test_total_checks": 483,
        },
        impact_assessment=(
            "Display / ARIA / JS layer only. NO contract change; the embedded "
            "payload is byte-identical so every governed read-out (and the Phase 35 "
            "Task 3 content digests) is bit-identical. The live region announces "
            "already-on-screen state and recomputes nothing, so the MR-016/MR-017 "
            "decision is not pre-empted. Zero-install invariants preserved (0 "
            "external refs, single self-contained HTML, no storage API, file:// "
            "safe)."
        ),
        quantitative_impact=(
            "No governed capital figure changed. Contract unchanged at 1.20.0 "
            "(ARIA/JS only; payload byte-identical). ui_app self-test %d -> %d "
            "checks ok:true 0/0; all 8 offline self-tests green (473 -> 483 total "
            "checks). External refs remain 0." % (ui_before, ui_after)
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: ARIA/JS/presentation only, NO contract change (ui_data.json + "
        "embedded payload byte-identical; A2 per-section SHA-256 digests still "
        "verify in-browser); ONE polite sr-only live region routes tab/search/"
        "slider/integrity state changes; announcements describe on-screen state "
        "and recompute nothing; governed headline 39,975.654628199336 carried "
        "exactly; never assertive; ui_app self-test 378 checks ok:true 0/0 plus "
        "7 other offline suites green (483 total); 0 external refs; no network / "
        "no storage API; no model parameter changes.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Gap E1 of the Phase 36 design note is closed: the "
        "offline UI now announces dynamic state changes (tab, search-result count, "
        "distribution slider read-out, integrity verify result) through one polite "
        "sr-only live region, completing WCAG 2.1 AA SC 4.1.3. PRESENTATION / ARIA "
        "ONLY - the MR-016/MR-017 dependence decision remains PENDING and entirely "
        "with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase 36 Task 2 live-region "
               "status announcements (gap E1, WCAG 2.1 AA SC 4.1.3); NO contract "
               "change (payload byte-identical); governed figures bit-identical; "
               "owner decision not pre-empted"),
        details={"record_id": rec.record_id, "contract": "1.20.0 (unchanged)",
                 "dedicated_live_region": "#srlive",
                 "ui_app_self_test_checks": ui_after,
                 "offline_self_test_total_checks": 483,
                 "affected_components": AFFECTED_COMPONENTS}))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main() -> int:
    data = json.load(open("ui_data.json", encoding="utf-8"))
    assert data["contract_version"] == "1.20.0", "expected contract 1.20.0 (unchanged)"
    html = open("ui_app.html", encoding="utf-8").read()
    assert 'id="srlive"' in html, "live region not present in ui_app.html"
    assert "function announce(" in html, "announce() not present in ui_app.html"
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_chg, n_aud = len(store.change_records), len(store.audit_trail.all())
    res = apply(store, ui_before=368, ui_after=378)
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
