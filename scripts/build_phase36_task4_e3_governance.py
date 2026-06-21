#!/usr/bin/env python3
"""Phase 36 Task 4 (gap E3) - governance for the reproducibility evidence-pack
export on the zero-install offline UI.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry. Display layer /
JS only: NO contract change (ui_data.json and the embedded payload are
byte-identical, so the Phase 35 Task 3 per-section SHA-256 digests still verify),
NO model parameter changes. The binding Phase 30 stop-rule stands and the
MR-016/MR-017 owner decision is not pre-empted. Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase36_task4_e3_governance.py
"""
from __future__ import annotations
import json
from pathlib import Path
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase 36: Offline UI Accessibility Completion & Educational Reproducibility"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase 36 Task 4 (gap E3) - single reproducibility evidence-pack "
                "export on the zero-install offline UI")
AFFECTED_COMPONENTS = [
    "scripts/build_phase36_task4_e3_evidence_pack.py",
    "scripts/ui_app_self_test.cjs",
    "scripts/ui_app_evidence_pack_fallback_test.cjs",
    "tests/test_phase36_task4_e3_evidence_pack.py",
    "ui_app.html",
]
STANDARD_REFERENCES = [
    "SOA ASOP 41 (Actuarial Communications) - reproducible, self-describing "
    "reviewer-facing evidence of exactly what was displayed",
    "ASOP 56 (Modeling) section 3.6 / IA TAS M - model reproducibility and "
    "auditability of reported results",
    "FIPS 180-4 SHA-256 - per-section + root content digests carried in "
    "contract_manifest, independently recomputable offline",
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
            "Closed gap E3 of the Phase 36 design note: added ONE in-browser action "
            "(\"Reproducibility evidence pack\" toolbar button) that serialises the "
            "EXACT embedded ui_data payload bytes to a single downloaded file via the "
            "existing downloadText/downloadBlob Blob plumbing. The exported bytes are "
            "BYTE-IDENTICAL to the embedded payload (which already carries "
            "contract_manifest.section_digests + root_digest and the build/provenance "
            "stamp meta.generated_utc / source_files / contract_manifest.generated_by), "
            "so a reviewer receives independently digest-verifiable evidence of exactly "
            "what the UI displayed: they can recompute the per-section SHA-256 digests "
            "and match the manifest, or re-load the file in this same UI for the "
            "existing in-browser verifier to confirm INTEGRITY VERIFIED. The download "
            "filename carries the contract version + first 8 hex of the root digest as "
            "a human-visible provenance stamp. A note on the Integrity tab points "
            "reviewers to the action. DISPLAY LAYER ONLY: the export reuses the embedded "
            "snapshot and existing manifest and recomputes NO model figure (governed "
            "headline 39,975.654628199336 and every governed read-out render "
            "bit-for-bit). NO contract change (no new ui_data key; payload byte-identical "
            "so the Phase 35 Task 3 per-section SHA-256 digests still verify by "
            "construction). The export performs NO network call and uses NO storage API; "
            "it works under file://. Tests: 12 new ui_app self-test checks "
            "(%d -> %d, ok:true, 0 network / 0 JS errors) plus a NEW dedicated jsdom "
            "fallback test (ui_app_evidence_pack_fallback_test.cjs) that captures the "
            "exported bytes and proves byte-identity, the provenance-stamped filename, "
            "no-storage / no-network, and digest-verifiability through the EXISTING "
            "in-browser verifier (re-embed -> INTEGRITY VERIFIED, root match, 0 altered "
            "rows), and a version-pinned pytest (14 cases). All nine offline self-tests "
            "remain ok:true (522 total checks). Zero-install preserved (0 external refs, "
            "single self-contained file:// HTML). NO model parameter changes; binding "
            "stop-rule honoured; owner decision not pre-empted."
            % (ui_before, ui_after)
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "ui_contract": "1.21.0",
            "evidence_exports": "per-section CSV + chart PNG + CSV/JSON read-out bundles",
            "byte_identical_payload_export": False,
            "ui_app_self_test_checks": ui_before,
            "offline_self_tests": 8,
            "offline_self_test_total_checks": 498,
        },
        after_snapshot={
            "ui_contract": "1.21.0 (unchanged - display/JS only, payload byte-identical)",
            "evidence_pack_action": "btnEvidencePack -> exportEvidencePack() -> exact embedded ui_data bytes",
            "export_filename": "reproducibility_evidence_pack_v<contract>_<root8>.json",
            "byte_identical_to_embedded": True,
            "digest_verifiable_by_existing_verifier": True,
            "headline_carried_bit_for_bit": "39975.654628199336",
            "payload_byte_identical": True,
            "a2_digests_still_verify": True,
            "network_or_storage_used": False,
            "ui_app_self_test_checks": ui_after,
            "offline_self_tests": 9,
            "offline_self_test_total_checks": 522,
        },
        impact_assessment=(
            "Display / JS layer only. NO contract change; the embedded payload is "
            "byte-identical so every governed read-out (and the Phase 35 Task 3 "
            "content digests) is bit-identical. The export serialises the embedded "
            "snapshot verbatim and recomputes nothing, so the MR-016/MR-017 decision "
            "is not pre-empted. A hash is not a model figure. Zero-install invariants "
            "preserved (0 external refs, single self-contained HTML, no storage API, "
            "file:// safe)."
        ),
        quantitative_impact=(
            "No governed capital figure changed. Contract unchanged at 1.21.0 "
            "(display/JS only; payload byte-identical). ui_app self-test %d -> %d "
            "checks ok:true 0/0; all 9 offline self-tests green (498 -> 522 total "
            "checks). External refs remain 0." % (ui_before, ui_after)
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: display/JS only, NO contract change (no new ui_data key; embedded "
        "payload byte-identical; A2 per-section SHA-256 digests still verify "
        "in-browser). The export hands the EXACT embedded ui_data bytes to the "
        "existing Blob plumbing; the dedicated jsdom fallback test captures the "
        "download and proves byte-identity to the embedded payload, the "
        "provenance-stamped filename, no network / no storage, and digest "
        "verifiability through the EXISTING in-browser verifier (re-embed -> "
        "INTEGRITY VERIFIED, root match, 0 altered rows). Governed headline "
        "39,975.654628199336 carried exactly; ui_app self-test 405 checks ok:true "
        "0/0 plus 8 other offline suites green (522 total); 0 external refs; no "
        "model parameter changes.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Gap E3 of the Phase 36 design note is closed: a "
        "single 'Reproducibility evidence pack' export now lets a reviewer download "
        "the exact, byte-identical, digest-verifiable ui_data payload the UI "
        "displayed, offline and file:// safe. DISPLAY / JS ONLY - the MR-016/MR-017 "
        "dependence decision remains PENDING and entirely with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase 36 Task 4 reproducibility "
               "evidence-pack export (gap E3); NO contract change (payload "
               "byte-identical); exported bytes byte-identical & digest-verifiable; "
               "owner decision not pre-empted"),
        details={"record_id": rec.record_id, "contract": "1.21.0 (unchanged)",
                 "export_action": "btnEvidencePack",
                 "ui_app_self_test_checks": ui_after,
                 "offline_self_test_total_checks": 522,
                 "affected_components": AFFECTED_COMPONENTS}))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main() -> int:
    data = json.load(open("ui_data.json", encoding="utf-8"))
    assert data["contract_version"] == "1.21.0", "expected contract 1.21.0 (unchanged)"
    html = open("ui_app.html", encoding="utf-8").read()
    assert 'id="btnEvidencePack"' in html, "evidence-pack button not present in ui_app.html"
    assert "function exportEvidencePack(" in html, "exportEvidencePack() not present"
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_chg, n_aud = len(store.change_records), len(store.audit_trail.all())
    res = apply(store, ui_before=393, ui_after=405)
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
