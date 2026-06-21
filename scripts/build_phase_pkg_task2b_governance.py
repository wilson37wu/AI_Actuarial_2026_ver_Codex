#!/usr/bin/env python3
"""Phase PKG Task 2 (Option B) - governance for the offline vendored-wheels venv
bootstrap. Opens ONE ChangeRecord (left in OWNER_REVIEW) + an audit entry.

Build-infrastructure / authoring-only / decision-neutral. Adds a stdlib offline
bootstrap (pip --no-index --find-links wheelhouse), a networked wheel-harvest
wrapper (owner/CI run), a structural gate + unittest, and Option-B docs. NO model
parameter change, NO UI contract change, ui_app.html byte-unchanged
(sha256 d82c65ec...), governed headline 39,975.654628199336 unchanged, Phase 30
stop-rule honoured, MR-016/MR-017 not pre-empted. Idempotent.

Run:  PYTHONPATH=. python3 scripts/build_phase_pkg_task2b_governance.py
"""
from __future__ import annotations
import json
from pathlib import Path
from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase PKG: No-prerequisite packaging (owner-decision card Option B)"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
CHANGE_TITLE = ("Phase PKG Task 2 (Option B) - offline vendored-wheels venv bootstrap "
                "(pip --no-index --find-links) + networked harvest wrapper, authoring-only")
AFFECTED_COMPONENTS = [
    "packaging/offline_bootstrap.py",
    "scripts/vendor_wheels.py",
    "scripts/build_phase_pkg_task2b_validate.py",
    "tests/test_phase_pkg_task2b_offline_wheelhouse.py",
    "packaging/OPTION_B_README.md",
    "docs/validation/PHASE_PKG_TASK2B_OFFLINE_WHEELHOUSE.json",
]
STANDARD_REFERENCES = [
    "pip user guide - --no-index / --find-links offline installs; pip download for "
    "wheelhouse harvesting (--only-binary, --platform, --python-version)",
    "SOA ASOP 56 s.3.4-3.6 - model implementation reproducibility (pinning the "
    "numerical stack into the distributed wheels)",
    "SOA ASOP 41 (Actuarial Communications) - reviewer-facing build/offline provenance",
    "docs/PHASE_IGUI_PACKAGING_OPTIONS_CARD.md - Option B (vendored wheels)",
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
            "Authored Option B of the packaging card: a fully-OFFLINE install of the "
            "numpy/pandas/scipy COMPUTE engine, removing the network + global-install "
            "prerequisite without a frozen binary. (1) packaging/offline_bootstrap.py "
            "(stdlib): creates a throw-away venv and installs the pinned engine with "
            "'pip install --no-index --no-build-isolation --find-links wheelhouse -r "
            "requirements-engine-lock.txt'; --no-index is the offline guarantee; modes "
            "--status/--plan-only/--self-test; never reaches the network and imports no "
            "engine module. (2) scripts/vendor_wheels.py (stdlib): the SINGLE networked "
            "step - a thin 'pip download --only-binary :all:' wrapper with "
            "--platform/--python-version passthrough for a cross-OS CI matrix and a "
            "--print-argv no-network mode; run ONCE by an owner/CI, NOT in the dev "
            "sandbox. (3) scripts/build_phase_pkg_task2b_validate.py stdlib structural "
            "gate (20/20 ok:true; loads the bootstrap module and asserts the planned "
            "argv forces --no-index/--find-links/pinned-reqs with no remote URL, runs "
            "its --self-test, checks the vendor wrapper + docs, and re-asserts "
            "ui_app.html byte-unchanged + governed headline present) + "
            "tests/test_phase_pkg_task2b_offline_wheelhouse.py (7 green). "
            "(4) packaging/OPTION_B_README.md + docs/validation/"
            "PHASE_PKG_TASK2B_OFFLINE_WHEELHOUSE.* documentation. AUTHORING-ONLY: no "
            "wheels are vendored in-repo and nothing is installed/built in the sandbox "
            "(no network); the harvest is the owner/CI step, mirroring Option A's CI "
            "build. DECISION-NEUTRAL: completes the A/B/C menu without foreclosing "
            "Option A (frozen binary) or Option C (run from source). Needs NO owner "
            "input (no code-signing cert, no publish channel). NO model parameter "
            "change; NO UI contract change; committed zero-install RESULTS UI "
            "ui_app.html byte-unchanged (sha256 d82c65ec...); governed headline "
            "39,975.654628199336 unchanged; Phase 30 stop-rule honoured; MR-016/MR-017 "
            "dependence decision not pre-empted."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "option_b_present": False,
            "compute_step_needs_network_or_global_install": True,
            "ui_app_html_sha256": "d82c65ecc7f7130a07b34d55c9500e93e23dd71626d18c3002c4e0777bd1fee6",
            "governed_headline": "39975.654628199336",
        },
        after_snapshot={
            "option_b_present": True,
            "offline_mechanism": "pip install --no-index --find-links wheelhouse -r requirements-engine-lock.txt",
            "networked_step": "scripts/vendor_wheels.py (pip download), owner/CI-run only",
            "wheels_vendored_in_repo": False,
            "structural_gate_checks": 20,
            "unittest_cases": 7,
            "self_test_ok": True,
            "engine_pin": {"numpy": "1.26.4", "pandas": "2.2.3", "scipy": "1.13.1"},
            "build_runs_in_sandbox": False,
            "owner_inputs_required": "none",
            "ui_app_html_sha256": "d82c65ecc7f7130a07b34d55c9500e93e23dd71626d18c3002c4e0777bd1fee6",
            "ui_app_html_byte_unchanged": True,
            "governed_headline": "39975.654628199336",
            "model_parameter_change": False,
            "ui_contract_change": False,
        },
        impact_assessment=(
            "Build-infrastructure only. No runtime model/UI code is modified. The "
            "offline bootstrap forces pip --no-index so it can never consult a remote "
            "index; the only networked step (vendor_wheels.py) is an explicit, "
            "owner/CI-run harvest. Decision-neutral: completes the owner's A/B/C "
            "packaging menu (B needs no cert/publish input) without pre-empting the "
            "A/C choice. Pinning the wheels strengthens the governed-headline "
            "reproducibility story (numbers reproduce bit-for-bit on a matching "
            "interpreter)."
        ),
        quantitative_impact=(
            "No governed figure changed (headline 39,975.654628199336 unchanged; "
            "ui_app.html byte-unchanged sha256 d82c65ec...). No contract change. "
            "Offline self-test ok:true; structural gate 20/20 ok:true; unittest 7/7."
        ),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified authoring-only/decision-neutral: offline_bootstrap.py loads, plans a "
        "pip install that forces --no-index + local --find-links against the pinned "
        "requirements with no remote URL/index flag, and its --self-test returns "
        "ok:true; vendor_wheels.py is a pip-download wrapper (--print-argv no-network); "
        "structural gate 20/20; unittest 7/7. ui_app.html byte-unchanged "
        "(sha256 d82c65ec...); governed headline 39,975.654628199336 present/unchanged; "
        "no model parameter or contract change.")
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Authored Option B (vendored-wheels offline install): "
        "the COMPUTE engine installs from a local wheelhouse with pip --no-index - no "
        "network, no global install, no frozen binary. Needs NO owner input (unlike "
        "Option A's cert/publish). To use: run scripts/vendor_wheels.py ONCE on a "
        "networked machine to populate wheelhouse/, ship it alongside, then users run "
        "packaging/offline_bootstrap.py fully offline. Options A and C remain open.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase PKG Task 2 Option-B offline "
               "vendored-wheels venv bootstrap; authoring-only/decision-neutral; no "
               "model/UI/contract change; governed headline bit-identical"),
        details={"record_id": rec.record_id,
                 "affected_components": AFFECTED_COMPONENTS,
                 "offline_mechanism": "pip --no-index --find-links wheelhouse",
                 "structural_gate_checks": 20,
                 "unittest_cases": 7,
                 "owner_inputs_required": "none",
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
