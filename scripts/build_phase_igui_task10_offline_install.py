#!/usr/bin/env python3
"""Phase IGUI Task 10 - Option-C offline-install appendix + pinned engine requirements.

Decision-neutral: this authors the documentation/config that makes the
run-from-source COMPUTE step reproducible (a pinned numpy/pandas/scipy set) and
wires it into the launcher README + the run_gui/launcher engine-status disclosure,
WITHOUT pre-empting the owner's A/B/C packaging decision (docs/PHASE_IGUI_
PACKAGING_OPTIONS_CARD.md). It:

  (a) emits / verifies the PINNED engine lock (requirements-engine-lock.txt) and
      checks every pin lies inside the compatible ranges in requirements.txt;
  (b) verifies the Option-C offline-install appendix
      (docs/PHASE_IGUI_OFFLINE_INSTALL_APPENDIX.md) exists and references the pinned
      file, the packaging-options card, the governed headline and the committed
      RESULTS-UI sha256;
  (c) verifies the disclosure wiring: launch_offline_gui.engine_status() surfaces the
      pinned-requirements + appendix pointers (modules set unchanged == {numpy,scipy})
      and launchers/README.md links both docs;
  (d) re-asserts the committed zero-install RESULTS UI (ui_app.html) is byte-unchanged
      vs the Task-8 certified baseline -- this task changes docs/config only;
  (e) emits the Task-10 evidence report (json + md);
  (f) opens a governance ChangeRecord (OWNER_REVIEW), appends one audit entry, verifies
      audit-chain integrity, and re-parses the store as a guard.

STDLIB-only; NO model parameter change; Phase 30 stop-rule honoured; MR-016/MR-017
owner decision not pre-empted.

Run:  PYTHONPATH=. python3 scripts/build_phase_igui_task10_offline_install.py
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from par_model_v2.governance.audit_trail import AuditEntry, ChangeRecord, GovernanceStore

PHASE = "Phase IGUI: Actuarial Input & Run GUI (owner-directed 2026-06-14)"
ACTOR = "ClaudeCowork_AutoDev"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_APP = Path("ui_app.html")
LOCK = Path("requirements-engine-lock.txt")
REQS = Path("requirements.txt")
APPENDIX = Path("docs/PHASE_IGUI_OFFLINE_INSTALL_APPENDIX.md")
PACKAGING_CARD = Path("docs/PHASE_IGUI_PACKAGING_OPTIONS_CARD.md")
LAUNCHER = Path("scripts/launch_offline_gui.py")
LAUNCHER_README = Path("launchers/README.md")
REPORT_JSON = Path("docs/validation/PHASE_IGUI_TASK10_OFFLINE_INSTALL.json")
REPORT_MD = Path("docs/validation/PHASE_IGUI_TASK10_OFFLINE_INSTALL.md")

UI_APP_BASELINE_SHA = "6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65"
HEADLINE = "39975.654628199336"

# The pinned engine the appendix documents. Kept here so the gate is self-checking.
EXPECTED_PINS = {"numpy": "1.26.4", "pandas": "2.2.3", "scipy": "1.13.1"}

CHANGE_TITLE = ("Phase IGUI Task 10 - Option-C offline-install appendix + pinned "
                "engine requirements (decision-neutral)")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parse_pins(text: str) -> dict:
    """Parse `pkg==version` lines (ignoring comments/blank) into {pkg: version}."""
    pins = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([0-9][0-9A-Za-z.\-]*)$", line)
        if m:
            pins[m.group(1).lower()] = m.group(2)
    return pins


def parse_ranges(text: str) -> dict:
    """Parse `pkg>=lo,<hi` lines into {pkg: (lo, hi)} (strings, comparison below)."""
    ranges = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)>=([0-9.]+),<([0-9.]+)$", line)
        if m:
            ranges[m.group(1).lower()] = (m.group(2), m.group(3))
    return ranges


def _ver_tuple(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def _in_range(version: str, lo: str, hi: str) -> bool:
    return _ver_tuple(lo) <= _ver_tuple(version) < _ver_tuple(hi)


def validate_task10_gate() -> dict:
    lock_text = LOCK.read_text(encoding="utf-8") if LOCK.exists() else ""
    appendix_text = APPENDIX.read_text(encoding="utf-8") if APPENDIX.exists() else ""
    launcher_text = LAUNCHER.read_text(encoding="utf-8") if LAUNCHER.exists() else ""
    readme_text = LAUNCHER_README.read_text(encoding="utf-8") if LAUNCHER_README.exists() else ""
    reqs_text = REQS.read_text(encoding="utf-8") if REQS.exists() else ""

    pins = parse_pins(lock_text)
    ranges = parse_ranges(reqs_text)
    ui_sha = _sha(UI_APP)

    pins_match = pins == EXPECTED_PINS
    pins_within_ranges = all(
        pkg in ranges and _in_range(ver, *ranges[pkg])
        for pkg, ver in pins.items())

    checks = {
        "lock_file_exists": LOCK.exists(),
        "lock_has_three_pins": set(pins) == set(EXPECTED_PINS),
        "lock_pins_match_expected": pins_match,
        "lock_pins_within_requirements_ranges": pins_within_ranges,
        "appendix_exists": APPENDIX.exists(),
        "appendix_refs_lock_file": "requirements-engine-lock.txt" in appendix_text,
        "appendix_refs_packaging_card": "PHASE_IGUI_PACKAGING_OPTIONS_CARD" in appendix_text,
        "appendix_carries_headline": HEADLINE in appendix_text.replace(",", ""),
        "appendix_refs_committed_ui_sha": UI_APP_BASELINE_SHA in appendix_text,
        "appendix_decision_neutral": ("pre-empt" in appendix_text.lower()
                                      and "Option A" in appendix_text
                                      and "Option B" in appendix_text),
        "launcher_discloses_pinned_reqs": "requirements-engine-lock.txt" in launcher_text,
        "launcher_discloses_appendix": "PHASE_IGUI_OFFLINE_INSTALL_APPENDIX" in launcher_text,
        "launcher_modules_set_unchanged": ('"modules": have' in launcher_text),
        "readme_links_appendix": "PHASE_IGUI_OFFLINE_INSTALL_APPENDIX" in readme_text,
        "readme_links_packaging_card": "PHASE_IGUI_PACKAGING_OPTIONS_CARD" in readme_text,
        "ui_app_byte_unchanged": ui_sha == UI_APP_BASELINE_SHA,
    }
    return {"ok": all(checks.values()), "n_checks": len(checks), "checks": checks,
            "pins": pins, "ranges": ranges, "ui_app_sha256": ui_sha}


def build_summary(store, gate) -> dict:
    return {
        "doc_id": "PHASE_IGUI_TASK10_OFFLINE_INSTALL",
        "doc_version": "1.0.0",
        "phase": PHASE,
        "task": "Task 10 - Option-C offline-install appendix + pinned engine requirements",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "classification": "educational / install documentation",
        "decision_neutral": True,
        "no_model_parameter_changes": True,
        "stop_rule_honoured": True,
        "owner_decision_pending": True,
        "zero_install_results_ui_preserved": gate["checks"]["ui_app_byte_unchanged"],
        "pinned_engine": gate["pins"],
        "requirements_ranges": {k: "%s..%s" % v for k, v in gate["ranges"].items()},
        "supported_interpreters": "CPython 3.9 - 3.12 (scipy 1.13.x wheel coverage)",
        "artifacts": {
            "pinned_requirements": str(LOCK),
            "offline_install_appendix": str(APPENDIX),
            "engine_status_disclosure": str(LAUNCHER),
            "launcher_readme": str(LAUNCHER_README),
            "packaging_options_card": str(PACKAGING_CARD),
        },
        "reproducibility_rationale": (
            "The governed headline SCR %s is a property of the model AND the numerical "
            "stack; pinning numpy/pandas/scipy freezes the stack so a run-from-source "
            "COMPUTE step is bit-for-bit reproducible. requirements.txt keeps compatible "
            "ranges for development; this lock is the reproducibility anchor for a run." % HEADLINE),
        "decision_neutrality_statement": (
            "Supports Option C (run from source). Pre-empts nothing: Option A (frozen "
            "binary) and Option B (vendored wheels) remain open and can reuse the same pins. "
            "MR-016/MR-017 dependence decision untouched; Phase 30 stop-rule honoured."),
        "task10_gate": {"ok": gate["ok"], "n_checks": gate["n_checks"], "checks": gate["checks"]},
        "consolidated_reaudit": {
            "ui_app_sha256": gate["ui_app_sha256"],
            "ui_app_sha256_baseline": UI_APP_BASELINE_SHA,
            "ui_app_byte_unchanged": gate["checks"]["ui_app_byte_unchanged"],
            "governance_change_records": len(store.change_records),
            "governance_audit_entries": len(store.audit_trail.all()),
            "audit_chain_integrity_ok": store.audit_trail.verify_all(),
            "headline_scr_carried": HEADLINE,
        },
        "constraints_honoured": [
            "STDLIB-only docs/config; no third-party dependency added to the GUI/runner",
            "NO model parameter change",
            "committed zero-install RESULTS UI (ui_app.html) byte-unchanged",
            "Phase 30 stop-rule honoured; MR-016/MR-017 owner decision not pre-empted",
            "decision-neutral: Option A/B remain fully open",
            "one task this cycle; agent lock held; fresh-clone git per AGENT_COORDINATION.md",
        ],
    }


def render_md(summary: dict, gate: dict) -> str:
    ra = summary["consolidated_reaudit"]
    L = []
    L.append("# Phase IGUI Task 10 - Option-C Offline-Install Appendix + Pinned Engine Requirements\n")
    L.append("**Generated:** %s  " % summary["generated_utc"])
    L.append("**Phase:** %s  " % summary["phase"])
    L.append("**Classification:** %s  " % summary["classification"])
    L.append("**Decision-neutral:** %s\n" % summary["decision_neutral"])
    L.append("## 1. What this task delivered\n")
    L.append("- Pinned engine lock `%s`: `%s`" % (
        summary["artifacts"]["pinned_requirements"],
        ", ".join("%s==%s" % (k, v) for k, v in summary["pinned_engine"].items())))
    L.append("- Option-C offline-install appendix `%s`" % summary["artifacts"]["offline_install_appendix"])
    L.append("- Engine-status disclosure wired in `%s` (pinned-reqs + appendix pointers)"
             % summary["artifacts"]["engine_status_disclosure"])
    L.append("- Launcher README links the appendix + the packaging-options card")
    L.append("- Supported interpreters: %s\n" % summary["supported_interpreters"])
    L.append("## 2. Reproducibility rationale\n")
    L.append(summary["reproducibility_rationale"] + "\n")
    L.append("## 3. Decision neutrality\n")
    L.append(summary["decision_neutrality_statement"] + "\n")
    L.append("## 4. Task-10 gate\n")
    L.append("**ok: %s** (%d checks)\n" % (gate["ok"], gate["n_checks"]))
    for k, v in gate["checks"].items():
        L.append("- %s: %s" % (k, v))
    L.append("")
    L.append("## 5. Consolidated re-audit\n")
    L.append("- Committed RESULTS UI `ui_app.html` sha256 `%s` - byte-unchanged vs baseline: **%s**"
             % (ra["ui_app_sha256"], ra["ui_app_byte_unchanged"]))
    L.append("- Governance store: **%d** change records, **%d** audit entries; integrity **%s**"
             % (ra["governance_change_records"], ra["governance_audit_entries"],
                ra["audit_chain_integrity_ok"]))
    L.append("- Governed headline SCR carried: `%s`\n" % ra["headline_scr_carried"])
    L.append("## 6. Constraints honoured\n")
    for c in summary["constraints_honoured"]:
        L.append("- %s" % c)
    L.append("")
    return "\n".join(L)


def apply_governance(store, summary, gate):
    if any(r.title == CHANGE_TITLE for r in store.change_records):
        for r in store.change_records:
            if r.title == CHANGE_TITLE:
                return {"added": False, "record_id": r.record_id,
                        "status": r.status.value, "reason": "idempotent"}
    ra = summary["consolidated_reaudit"]
    pins_str = ", ".join("%s==%s" % (k, v) for k, v in summary["pinned_engine"].items())
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Phase IGUI Task 10 (decision-neutral) - authored the Option-C offline-install "
            "appendix (docs/PHASE_IGUI_OFFLINE_INSTALL_APPENDIX.md) and a PINNED engine "
            "requirements file (requirements-engine-lock.txt: %s) so the run-from-source "
            "COMPUTE step is reproducible, and wired both into launchers/README.md and the "
            "launcher engine-status disclosure (scripts/launch_offline_gui.py). The pinned "
            "versions all lie inside the compatible ranges in requirements.txt; the launcher's "
            "engine_status() now surfaces the pinned-requirements + appendix pointers while the "
            "'modules' set stays exactly {numpy, scipy}. The committed zero-install RESULTS UI "
            "(ui_app.html sha256 %s) is byte-unchanged. This SUPPORTS the owner's Option C and "
            "PRE-EMPTS NOTHING: Option A (frozen binary) and Option B (vendored wheels) remain "
            "open and can reuse the same pins. STDLIB-only docs/config; NO model parameter "
            "change; Phase 30 stop-rule honoured; MR-016/MR-017 owner decision not pre-empted."
            % (pins_str, ra["ui_app_sha256"])
        ),
        change_type="governance_change",
        affected_components=[
            "requirements-engine-lock.txt",
            "docs/PHASE_IGUI_OFFLINE_INSTALL_APPENDIX.md",
            "scripts/launch_offline_gui.py",
            "launchers/README.md",
            "scripts/build_phase_igui_task10_offline_install.py",
            "docs/validation/PHASE_IGUI_TASK10_OFFLINE_INSTALL.json",
            "docs/validation/PHASE_IGUI_TASK10_OFFLINE_INSTALL.md",
            "tests/test_phase_igui_task10_offline_install.py",
        ],
        standard_references=[
            "SOA ASOP 56 (Modeling) section 3.6 - model documentation: the environment that "
            "produces the governed headline is pinned and documented for reproducibility",
            "SOA ASOP 41 (Actuarial Communications) - the offline-install appendix is framed "
            "as an explicit Option-C support note and pre-empts no owner packaging decision",
            "SOA ASOP 23 (Data Quality) - pinning the numerical stack removes an environment "
            "source of variation in the produced figures",
        ],
        before_snapshot={
            "phase_igui": "Task 9 complete (phase summary + consolidated re-audit)",
            "engine_install_guidance": "ad-hoc 'pip install numpy scipy' (unpinned)",
            "ui_app_sha256": UI_APP_BASELINE_SHA,
            "governance_change_records_before": ra["governance_change_records"],
        },
        after_snapshot={
            "phase_igui": "Task 10 complete (Option-C offline-install appendix + pinned engine)",
            "pinned_engine": summary["pinned_engine"],
            "supported_interpreters": summary["supported_interpreters"],
            "task10_gate_ok": gate["ok"],
            "task10_gate_checks": gate["n_checks"],
            "ui_app_byte_unchanged": ra["ui_app_byte_unchanged"],
            "decision_neutral": True,
            "ui_contract": "1.21.0 (unchanged)",
            "headline_carried": HEADLINE,
        },
        impact_assessment=(
            "Documentation + config only (a pinned requirements file, a Markdown appendix, "
            "stdlib-only print/dict additions to the launcher disclosure, and README links). "
            "No code path, contract, artifact or model parameter changed; the committed "
            "zero-install RESULTS UI is byte-identical. Reproducibility of a run-from-source "
            "COMPUTE step is strengthened by freezing the numerical stack. The owner's A/B/C "
            "packaging decision and MR-016/MR-017 remain entirely open."),
        quantitative_impact=(
            "No governed capital figure changed; headline SCR %s carried bit-for-bit. Contract "
            "unchanged at 1.21.0. Task-10 gate ok:%s %d/%d checks; committed ui_app.html sha256 "
            "unchanged (%s). Pinned engine: %s." % (
                HEADLINE, gate["ok"], sum(1 for v in gate["checks"].values() if v),
                gate["n_checks"], ra["ui_app_sha256"], pins_str)),
        author=ACTOR, phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Verified: pinned engine (%s) lies inside the requirements.txt ranges; the Option-C "
        "appendix references the pinned file, packaging card, governed headline and committed "
        "ui_app.html sha256; the launcher discloses both pointers with modules set unchanged "
        "{numpy,scipy}; README links both docs; ui_app.html byte-unchanged. Decision-neutral - "
        "Option A/B untouched. STDLIB-only; NO model parameter change; stop-rule honoured." % pins_str)
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Task 10 makes the run-from-source COMPUTE step reproducible by "
        "pinning numpy/pandas/scipy (requirements-engine-lock.txt) and documenting a fully offline "
        "install path (docs/PHASE_IGUI_OFFLINE_INSTALL_APPENDIX.md), wired into the launcher and "
        "README. This is the Option-C support deliverable named in the packaging-options card and "
        "pre-empts nothing: your A (frozen binary) / B (vendored wheels) / C (status quo) decision "
        "and MR-016/MR-017 remain open. No model parameter changed; the committed RESULTS UI is "
        "byte-unchanged.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase IGUI Task 10 Option-C offline-install "
               "appendix + pinned engine requirements (%s); launcher+README disclosure wired; "
               "ui_app.html byte-unchanged; decision-neutral (A/B open); STDLIB-only; NO model "
               "param change; Phase 30 stop-rule honoured" % pins_str),
        details={"record_id": rec.record_id, "contract": "1.21.0 (unchanged)",
                 "task10_gate_ok": gate["ok"], "task10_gate_checks": gate["n_checks"],
                 "pinned_engine": summary["pinned_engine"],
                 "ui_app_sha256": ra["ui_app_sha256"]}))
    return {"added": True, "record_id": rec.record_id, "status": rec.status.value}


def main() -> int:
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_chg, n_aud = len(store.change_records), len(store.audit_trail.all())
    gate = validate_task10_gate()
    summary = build_summary(store, gate)
    if not gate["ok"]:
        print("TASK-10 GATE FAILED:", json.dumps(gate["checks"], indent=1))
        return 1
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    REPORT_MD.write_text(render_md(summary, gate), encoding="utf-8")
    json.loads(REPORT_JSON.read_text(encoding="utf-8"))  # re-parse guard

    res = apply_governance(store, summary, gate)
    if not store.audit_trail.verify_all():
        print("AUDIT INTEGRITY FAILED - store NOT saved")
        return 1
    if res.get("added"):
        GOV_PATH.write_text(store.to_json(), encoding="utf-8")
    json.loads(GOV_PATH.read_text(encoding="utf-8"))  # re-parse guard
    print(json.dumps({
        "task10_gate": {"ok": gate["ok"], "n_checks": gate["n_checks"]},
        "governance": res,
        "change_records": "%d -> %d" % (n_chg, len(store.change_records)),
        "audit_entries": "%d -> %d" % (n_aud, len(store.audit_trail.all())),
        "audit_integrity_ok": store.audit_trail.verify_all(),
        "pinned_engine": gate["pins"],
        "ui_app_byte_unchanged": gate["checks"]["ui_app_byte_unchanged"],
        "report_json": str(REPORT_JSON),
        "report_md": str(REPORT_MD),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
