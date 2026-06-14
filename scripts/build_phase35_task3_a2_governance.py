#!/usr/bin/env python3
"""Phase 35 Task 3 (gap A2) - governance for the per-section cryptographic
content digest + in-browser tamper-evident verifier on the zero-install offline
UI.

Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry recording the
ADDITIVE contract bump 1.19.0 -> 1.20.0 (per-section SHA-256 section_digests +
root_digest + digest_algo added INSIDE contract_manifest; no new top-level key)
and the in-browser verifier. Idempotent.

NO model parameter changes; the binding Phase 30 stop-rule stands; the
MR-016/MR-017 owner decision is not pre-empted. A content digest is not a model
figure; every governed read-out renders bit-identically.

Run:  PYTHONPATH=. python3 scripts/build_phase35_task3_a2_governance.py
"""
from __future__ import annotations
import json
from pathlib import Path
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase 35: Offline UI Accessibility & Evidence-Integrity Deepening"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase 35 Task 3 (gap A2) - per-section SHA-256 content digest + "
                "in-browser tamper-evident verifier on the zero-install offline UI")
AFFECTED_COMPONENTS = [
    "scripts/build_phase35_task3_a2_digests.py",
    "scripts/ui_app_self_test.cjs",
    "ui_data.json",
    "ui_app.html",
]
STANDARD_REFERENCES = [
    "SOA ASOP 41 s3.2 (clear and complete communication of actuarial findings)",
    "SOA ASOP 23 (data quality / integrity of model inputs and outputs)",
    "FIPS 180-4 (SHA-256 secure hash standard)",
    "Model risk governance - evidence tamper-evidence / reproducibility",
]


def apply(store: GovernanceStore, root_digest: str, n_sections: int,
          ui_checks: int) -> dict:
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        for r in store.change_records:
            if r.title == CHANGE_TITLE:
                return {"added": False, "record_id": r.record_id,
                        "status": r.status.value, "reason": "idempotent"}
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Closed gap A2 of the Phase 35 design note: per-section cryptographic "
            "content digests + an in-browser tamper-evident verifier. Phase 34 "
            "Task 2 (gap H1) proved required data SECTIONS are PRESENT and the "
            "contract version matches, but could not detect whether the CONTENT "
            "of a section had been altered; A2 closes that. (1) "
            "scripts/build_phase35_task3_a2_digests.py computes, at build time, a "
            "SHA-256 over a canonical serialisation of every top-level section "
            "(every key except contract_manifest) and a root_digest over the "
            "canonical sorted section-digest map, written INSIDE contract_manifest "
            "as section_digests + root_digest + digest_algo='sha256' - NO new "
            "top-level key; every pre-existing ui_data key renders bit-identically. "
            "(2) The contract bumps 1.19.0 -> 1.20.0 (manifest-schema addition). "
            "(3) The build-time digests are produced by EXECUTING THE SAME "
            "canonical+SHA-256 JS that is embedded in the page (run in Node), so "
            "the browser recompute agrees byte-for-byte by construction - no "
            "Python/JS float-formatting divergence is possible. (4) ui_app.html "
            "gained a self-contained pure-JS SHA-256 + canonical serialiser and "
            "renderIntegrityVerifierHtml(): on load the Integrity (H1) panel "
            "RECOMPUTES the section digests in the browser from the embedded "
            "payload (NO network, NO storage API, works under file://) and renders "
            "a verified/altered table + an overall INTEGRITY VERIFIED / CONTENT "
            "ALTERED badge. It recomputes a content DIGEST, not a model figure. "
            "(5) Tests: 8 new ui_app self-test checks (350 -> 358, ok:true, 0 "
            "network / 0 JS errors) covering the embedded digests, full-section "
            "coverage, the rendered verifier table, and - because jsdom executes "
            "the pure-JS SHA-256 - that the in-browser recompute genuinely matches "
            "the embedded digests; a separate tamper test confirms a mutated "
            "section flips the badge to CONTENT ALTERED. All eight offline "
            "self-tests remain ok:true 0/0. Zero-install preserved (0 external "
            "refs). NO model parameter changes; binding stop-rule honoured; owner "
            "decision not pre-empted."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "ui_contract": "1.19.0",
            "content_digests": False,
            "integrity_scope": "section PRESENCE + contract version only (H1)",
            "ui_app_self_test_checks": 350,
            "offline_self_tests": 8,
        },
        after_snapshot={
            "ui_contract": "1.20.0",
            "content_digests": True,
            "digest_algo": "sha256",
            "sections_digested": n_sections,
            "root_digest": root_digest,
            "integrity_scope": "section PRESENCE + per-section CONTENT tamper-evidence",
            "in_browser_recompute": True,
            "network_or_storage_used": False,
            "ui_app_self_test_checks": ui_checks,
            "offline_self_tests": 8,
        },
        impact_assessment=(
            "Evidence-integrity / display-layer pass only. ADDITIVE contract "
            "change (manifest digest fields); the verifier recomputes a content "
            "digest, not any model figure, and the governed frozen-t headline and "
            "every other governed read-out are bit-identical. The MR-016/MR-017 "
            "dependence decision is not pre-empted. Zero-install invariants "
            "preserved (0 external refs, single self-contained HTML, no storage "
            "API)."
        ),
        quantitative_impact=(
            "No governed capital figure changed. Contract 1.19.0 -> 1.20.0 "
            "(additive contract_manifest.section_digests/root_digest/digest_algo). "
            "%d sections digested (SHA-256); root_digest %s. In-browser recompute "
            "matches the embedded digests; tamper test flips the badge. ui_app "
            "self-test 350 -> %d checks ok:true 0/0; all 8 offline self-tests "
            "green. External refs remain 0."
            % (n_sections, root_digest[:16] + "...", ui_checks)
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: additive contract 1.19.0 -> 1.20.0 (per-section SHA-256 "
        "section_digests + root_digest + digest_algo inside contract_manifest; no "
        "new top-level key; pre-existing keys bit-identical); build digests "
        "produced by the SAME canonical+SHA-256 JS the browser runs (Node), so "
        "in-browser recompute matches by construction; pure-JS SHA-256 passes the "
        "NIST 'abc' + empty-string vectors; jsdom recompute all-verified and a "
        "tamper test flips the badge to CONTENT ALTERED; ui_app self-test 358 "
        "checks ok:true 0/0 plus 7 other offline suites green; 0 external refs; "
        "no network / no storage API; no model parameter changes.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Gap A2 of the Phase 35 design note is closed: the "
        "offline UI now carries a build-time SHA-256 digest of every data section "
        "and recomputes those digests IN THE BROWSER (no network, no storage) to "
        "prove the embedded content is unaltered, rendered as a verified/altered "
        "table + badge in the Integrity panel. EVIDENCE-INTEGRITY / PRESENTATION "
        "ONLY - the MR-016/MR-017 dependence decision remains PENDING and entirely "
        "with the owner.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase 35 Task 3 per-section "
               "SHA-256 content digest + in-browser tamper-evident verifier (gap "
               "A2); additive contract 1.19.0 -> 1.20.0 (manifest digest fields); "
               "governed figures bit-identical"),
        details={"record_id": rec.record_id, "contract": "1.19.0->1.20.0",
                 "sections_digested": n_sections, "root_digest": root_digest,
                 "ui_app_self_test_checks": ui_checks,
                 "affected_components": AFFECTED_COMPONENTS}))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main() -> int:
    data = json.load(open("ui_data.json", encoding="utf-8"))
    man = data["contract_manifest"]
    root_digest = man["root_digest"]
    n_sections = len(man["section_digests"])
    assert data["contract_version"] == "1.20.0", "expected contract 1.20.0"
    assert man["digest_algo"] == "sha256"
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_chg, n_aud = len(store.change_records), len(store.audit_trail.all())
    res = apply(store, root_digest, n_sections, ui_checks=358)
    if not store.audit_trail.verify_all():
        print("AUDIT INTEGRITY FAILED - store NOT saved")
        return 1
    if res.get("added"):
        GOV_PATH.write_text(store.to_json(), encoding="utf-8")
    print(json.dumps({
        "governance": res,
        "change_records": f"{n_chg} -> {len(store.change_records)}",
        "audit_entries": f"{n_aud} -> {len(store.audit_trail.all())}",
        "audit_integrity_ok": store.audit_trail.verify_all(),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
