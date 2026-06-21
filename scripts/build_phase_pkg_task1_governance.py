#!/usr/bin/env python3
"""Phase PKG Task 1 - governance for the Option-A frozen-binary build
infrastructure. Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry.

Build-infrastructure / authoring-only / decision-neutral: adds a PyInstaller spec,
a manual/tag-gated CI release matrix, a stdlib structural gate + unittest, and
packaging docs. NO model parameter change, NO UI contract change, ui_app.html
byte-unchanged (sha256 d82c65ec...), governed headline 39,975.654628199336
unchanged, Phase 30 stop-rule honoured, MR-016/MR-017 not pre-empted. Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase_pkg_task1_governance.py
"""
from __future__ import annotations
import json
from pathlib import Path
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase PKG: No-prerequisite packaging (owner-decision card Option A)"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase PKG Task 1 - Option-A frozen-binary build infrastructure "
                "(PyInstaller spec + CI release matrix + gate, authoring-only)")
AFFECTED_COMPONENTS = [
    "packaging/actuarial_gui.spec",
    ".github/workflows/release.yml",
    "scripts/build_phase_pkg_task1_validate.py",
    "tests/test_phase_pkg_task1_build_infra.py",
    "packaging/README.md",
    "docs/validation/PHASE_PKG_TASK1_BUILD_INFRA.json",
]
STANDARD_REFERENCES = [
    "PyInstaller manual - spec files, collect_all hooks, onefile vs onedir, "
    "scipy/numpy hidden-import collection",
    "SOA ASOP 56 s.3.4-3.6 - model implementation documentation and reproducibility "
    "(pinning the numerical stack into the release artifact)",
    "SOA ASOP 41 (Actuarial Communications) - reviewer-facing build/offline "
    "provenance",
    "docs/PHASE_IGUI_PACKAGING_OPTIONS_CARD.md - Option A recommendation",
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
            "Authored the build recipe that freezes the one-click offline launcher "
            "(scripts/launch_offline_gui.py) plus the numpy/pandas/scipy compute "
            "engine into a single self-contained per-OS executable, closing the "
            "last prerequisite the launcher discloses (the /execute COMPUTE step). "
            "(1) packaging/actuarial_gui.spec: PyInstaller onefile spec; bundles the "
            "engine + verbatim ui_app.html, ui_data.json, production_run/, the "
            ".claude-dev/GOVERNANCE_STORE.json read-only echo and "
            "requirements-engine-lock.txt; console=True; upx=False (AV-safety); "
            "codesign_identity=None (signing is an owner/infra decision). "
            "(2) .github/workflows/release.yml: ubuntu/windows/macos matrix gated to "
            "workflow_dispatch + v* tags ONLY (NO branch-push trigger, so adding it "
            "changes no day-to-day behaviour and auto-publishes nothing); installs "
            "the pinned engine + pyinstaller==6.11.1, runs the structural gate, "
            "builds, smoke-tests the binary with --self-test (asserting host "
            "127.0.0.1 and engine_ready), uploads per-OS artifacts and on a tag "
            "publishes a GitHub Release. (3) scripts/build_phase_pkg_task1_validate.py "
            "stdlib-only structural gate (25 checks, also the CI pre-build step) + "
            "tests/test_phase_pkg_task1_build_infra.py unittest wrapper (9 green). "
            "(4) packaging/README.md + docs/validation/PHASE_PKG_TASK1_BUILD_INFRA.* "
            "documentation. AUTHORING-ONLY: no build runs in the dev sandbox (no "
            "toolchain/network); the CI matrix performs the per-OS build. "
            "DECISION-NEUTRAL: this implements the card's RECOMMENDED Option A "
            "without foreclosing Option B (vendored wheels) or Option C (run from "
            "source, which stays fully supported). NO model parameter change; NO UI "
            "contract change; committed zero-install RESULTS UI ui_app.html "
            "byte-unchanged (sha256 d82c65ec...); governed headline "
            "39,975.654628199336 unchanged; Phase 30 stop-rule honoured; MR-016/"
            "MR-017 dependence decision not pre-empted."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "packaging_build_infra_present": False,
            "compute_step_needs_preinstall": True,
            "ui_app_html_sha256": "d82c65ecc7f7130a07b34d55c9500e93e23dd71626d18c3002c4e0777bd1fee6",
            "governed_headline": "39975.654628199336",
        },
        after_snapshot={
            "packaging_build_infra_present": True,
            "spec_targets_offline_launcher": True,
            "ci_matrix_os": ["ubuntu-latest", "windows-latest", "macos-latest"],
            "ci_trigger": "workflow_dispatch + v* tag only (no branch push)",
            "structural_gate_checks": 25,
            "unittest_cases": 9,
            "engine_pin": {"numpy": "1.26.4", "pandas": "2.2.3", "scipy": "1.13.1"},
            "build_runs_in_sandbox": False,
            "ui_app_html_sha256": "d82c65ecc7f7130a07b34d55c9500e93e23dd71626d18c3002c4e0777bd1fee6",
            "ui_app_html_byte_unchanged": True,
            "governed_headline": "39975.654628199336",
            "model_parameter_change": False,
            "ui_contract_change": False,
        },
        impact_assessment=(
            "Build-infrastructure only. No runtime model/UI code is modified; the "
            "frozen binary merely wraps the existing launcher and binds 127.0.0.1 "
            "with no outbound call, so the offline guarantee is unchanged. The CI "
            "workflow cannot run on a normal push (manual/tag gated), so it adds no "
            "surprise behaviour and the owner's A/B/C packaging choice is not "
            "pre-empted. Pinning the numerical stack into the artifact strengthens "
            "the governed-headline reproducibility story."
        ),
        quantitative_impact=(
            "No governed figure changed (headline 39,975.654628199336 unchanged; "
            "ui_app.html byte-unchanged sha256 d82c65ec...). No contract change. "
            "Structural gate 25/25 ok:true; unittest 9/9 green."
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified authoring-only/decision-neutral: spec parses (ast) and targets "
        "scripts/launch_offline_gui.py; CI workflow parses (yaml), is manual/tag "
        "gated with NO branch-push trigger, 3-OS matrix, runs the gate, builds the "
        "spec and smoke-tests the binary with --self-test (host 127.0.0.1 + "
        "engine_ready). ui_app.html byte-unchanged (sha256 d82c65ec...); governed "
        "headline 39,975.654628199336 present/unchanged; no model parameter or "
        "contract change. Structural gate 25/25; unittest 9/9.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Authored the RECOMMENDED Option-A frozen-binary "
        "build recipe (PyInstaller spec + manual/tag-gated CI release matrix + "
        "stdlib gate + docs) so a non-technical user can eventually run inputs AND "
        "compute with nothing pre-installed. Nothing is built or published by this "
        "change; Options B/C are not foreclosed. To produce binaries: run the "
        "'package-release' workflow from the Actions tab or push a v* tag. Residual "
        "owner/infra decisions: code-signing certificate, publish channel.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase PKG Task 1 Option-A "
               "frozen-binary build infrastructure; authoring-only/decision-neutral; "
               "no model/UI/contract change; governed headline bit-identical"),
        details={"record_id": rec.record_id,
                 "affected_components": AFFECTED_COMPONENTS,
                 "ci_trigger": "workflow_dispatch + v* tag only",
                 "structural_gate_checks": 25,
                 "unittest_cases": 9,
                 "ui_app_byte_unchanged": True,
                 "headline_bit_identical": "39975.654628199336",
                 "model_parameter_change": False}))
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
    print(json.dumps({
        "governance": res,
        "change_records": "%d -> %d" % (n_chg, len(store.change_records)),
        "audit_entries": "%d -> %d" % (n_aud, len(store.audit_trail.all())),
        "audit_integrity_ok": store.audit_trail.verify_all(),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
