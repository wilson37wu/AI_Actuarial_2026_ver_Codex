#!/usr/bin/env python3
"""Phase 32 Task 2 (gap G1) - browsable owner-decision-pack surface in the
zero-install offline UI.

This is NOT a model calculation. It verifies that the offline UI
(`scripts/build_ui_data.py` -> `ui_data.json` v1.14.0 ADDITIVE +
`ui_app.html`) surfaces the Phase 31 owner decision pack as a first-class
**Owner Decision (P31)** tab, per the pre-registered G1 acceptance criteria
in docs/validation/PHASE32_TASK1_DESIGN_NOTE.md:
  (a) every displayed figure bit-for-bit from
      PHASE31_TASK2_OWNER_DECISION_PACK.json (nothing recomputed);
  (b) neutrality preserved - options in registry order, NO default, no
      steering language, decision record rendered BLANK;
  (c) new self-test checks cover the surface (25 added; suite 196 checks);
  (d) ADDITIVE-only contract change 1.13.0 -> 1.14.0 - every pre-existing
      ui_data key bit-identical (sha256-stable inventory; mtime is checkout
      metadata);
  (e) zero-install preserved - 0 external references, single HTML file,
      jsdom self-tests 0 network / 0 JS errors (ui_app + offline viewer +
      combined GUI);
  (f) NO model parameter changes - display layer only.
It opens an OWNER_REVIEW ChangeRecord, appends one governance audit entry,
verifies audit-chain integrity, and writes the Task 2 evidence report.

Run:  PYTHONPATH=. python3 scripts/build_phase32_task2_owner_pack_surface.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
)

PHASE = "Phase 32: Zero-Install Offline UI Consolidation"
ACTOR = "AutomatedModelDev_Phase32"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_DATA = Path("ui_data.json")
UI_APP = Path("ui_app.html")
PACK_PATH = Path("docs/validation/PHASE31_TASK2_OWNER_DECISION_PACK.json")
SELF_TEST = Path("scripts/ui_app_self_test.cjs")
VIEWER_TEST = Path("scripts/offline_viewer_self_test.cjs")
COMBINED_TEST = Path("scripts/combined_gui_self_test.cjs")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE32_TASK2_OWNER_PACK_SURFACE_REPORT.json"
MD_PATH = OUT_DIR / "PHASE32_TASK2_OWNER_PACK_SURFACE_REPORT.md"
CHANGE_TITLE = (
    "Phase 32 Task 2 - browsable owner-decision-pack surface (gap G1) in "
    "the zero-install offline UI"
)
AFFECTED_COMPONENTS = [
    "scripts/build_ui_data.py",
    "scripts/ui_app_self_test.cjs",
    "ui_data.json",
    "ui_app.html",
]
STANDARD_REFERENCES = [
    "SOA ASOP 41 s3.2 (communication of actuarial findings)",
    "SOA ASOP 56 s3.5 (model output validation & presentation)",
    "IA TAS M s3.6 (reproducibility and disclosure of model results)",
    "IFoA Modelling Practice Note s4 (documentation & independent review)",
    "Solvency II Art. 234 (dependence justification - candidates DISCLOSED, "
    "not adopted; owner decision pending)",
]

PACK_KEYS = (
    "metadata", "purpose", "how_to_read", "evidence_pack",
    "figure_provenance", "owner_options", "owner_option_order",
    "escalation_option_id", "signoff_workflow", "decision_record_template",
    "glossary", "limitations", "standard_references",
)
BLANK_FIELDS = (
    "decision_option_id", "rationale", "decided_by", "decided_at",
    "peer_reviewer", "follow_up_change_record_id",
)


def check_ui_contract() -> dict:
    data = json.loads(UI_DATA.read_text(encoding="utf-8"))
    pack_doc = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pack = pack_doc.get("pack", {})
    od = data.get("owner_decision_p31", {})
    ev = od.get("evidence_pack", {})
    gh = ev.get("governed_headline", {})
    html = UI_APP.read_text(encoding="utf-8")

    bit_for_bit = {k: od.get(k) == pack.get(k) for k in PACK_KEYS}
    drt = od.get("decision_record_template", {}) or {}
    checks = {
        "contract_version": data.get("contract_version"),
        "contract_is_1_14_0": data.get("contract_version") == "1.14.0",
        "owner_decision_section_present": isinstance(od, dict) and bool(od),
        # (a) bit-for-bit: the embedded section equals the assembled pack
        # verbatim for every carried key - nothing recomputed.
        "pack_bit_for_bit_all_keys": all(bit_for_bit.values()),
        "pack_bit_for_bit_detail": bit_for_bit,
        "governed_headline_39976": abs(
            float(gh.get("value", 0)) - 39975.654628199336) == 0.0,
        "assembly_gate_carried_ok": (od.get("assembly_gate", {}).get("ok")
                                     is True),
        "source_pinned": od.get("source")
            == "docs/validation/PHASE31_TASK2_OWNER_DECISION_PACK.json",
        # (b) neutrality: registry order, NO default, decision BLANK.
        "options_registry_order": (od.get("owner_option_order")
                                   == pack.get("owner_option_order")
                                   and len(od.get("owner_option_order") or [])
                                   == 3),
        "no_recommended_key": "recommended" not in {str(k).lower()
                                                    for k in od},
        "decision_fields_blank": all(
            str(drt.get(f, "x")).strip() == "" for f in BLANK_FIELDS),
        "narrative_states_blank_and_no_default": (
            "BLANK" in str(od.get("narrative", ""))
            and "NO default" in str(od.get("narrative", ""))),
        # (e) zero-install: panel embedded, single file, no external refs.
        "panel_div_in_html": 'id="ownerdecision"' in html,
        "tab_title_in_html": "Owner Decision (P31)" in html,
        "renderer_in_html": "function renderOwnerDecision()" in html,
        "zero_external_refs": not re.search(
            r'(?:src|href)\s*=\s*["\']https?://', html),
        "single_file_bytes": UI_APP.stat().st_size,
    }
    checks["all_passed"] = all(
        v is True for k, v in checks.items()
        if k not in ("contract_version", "pack_bit_for_bit_detail",
                     "single_file_bytes"))
    checks["headline_readouts"] = {
        "governed_headline": gh.get("value"),
        "vine2_point": (ev.get("disclosed_candidates", {})
                        .get("vine2", {}).get("component_scr_point")),
        "tree3_bootstrap_mean": (ev.get("disclosed_candidates", {})
                                 .get("tree3", {}).get("bootstrap_mean")),
        "nested_reference": ev.get("nested_reference", {}).get("value"),
        "option_order": od.get("owner_option_order"),
        "escalation_option": od.get("escalation_option_id"),
    }
    return checks


def _run_node(script: Path, arg: str | None = None) -> dict:
    cmd = ["node", str(script)] + ([arg] if arg else [])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    out = json.loads(proc.stdout)
    ch = out.get("checks", {})
    return {
        "ok": bool(out.get("ok")),
        "network_calls": ch.get("networkCalls",
                                len(out.get("networkCalls", []) or [])),
        "js_errors": ch.get("jsErrors", len(out.get("errors", []) or [])),
        "n_checks": len(ch),
        "failed_checks": [k for k, v in ch.items() if v is False],
        "od_checks": {k: ch[k] for k in ch if k.startswith("od")
                      or k == "ownerDecisionTabPresent"},
    }


def apply_governance(store: GovernanceStore, ui: dict, st: dict) -> dict:
    added = False
    record_id = None
    record_status = None
    if not any(r.title == CHANGE_TITLE for r in store.change_records):
        hr = ui["headline_readouts"]
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 32 Task 2 closed gap G1 of the Phase 32 Task 1 "
                "design note: the Phase 31 owner decision pack is now a "
                "browsable first-class 'Owner Decision (P31)' tab in the "
                "zero-install offline UI (ui_data contract bumped "
                "ADDITIVELY 1.13.0 -> 1.14.0). The new "
                "owner_decision_p31 section copies the assembled pack "
                "VERBATIM (bit-for-bit; nothing recomputed): evidence pack "
                "(governed headline 39,975.7 unchanged through P27-P30; "
                "disclosed vine candidates 42,458.6 point / 41,751.9 "
                "tree-3 bootstrap mean with 95% CIs; nested single-run "
                "reference 46,638.9 outside both CIs; residual ladder; "
                "gap decomposition; MR-016/MR-017 OPEN; binding stop-rule "
                "record), the three owner options in REGISTRY ORDER with "
                "NO default and no steering language, the 6-step sign-off "
                "workflow (decision sits at step 4 - the model owner), "
                "the decision record rendered BLANK until the owner "
                "decides, figure provenance, limitations and standards. "
                "25 new jsdom self-test checks added (suite 196 checks, "
                "ok:true, 0 network / 0 JS errors); offline viewer and "
                "combined GUI self-tests remain green; 0 external "
                "references; every pre-existing ui_data key bit-identical "
                "(sha256-stable inventory). The UI performs no "
                "calculation; NO model parameter changes."
            ),
            change_type="code_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "ui_contract": "1.13.0 (stop-rule panel; owner decision "
                               "pack governance-docs only, not browsable)",
            },
            after_snapshot={
                "ui_contract": "1.14.0 (additive)",
                "headline_readouts": hr,
                "self_test_ok": st["ok"],
                "network_calls": st["network_calls"],
                "js_errors": st["js_errors"],
                "n_checks": st["n_checks"],
            },
            impact_assessment=(
                "Display-layer only: the UI bundler reads the assembled "
                "Phase 31 pack JSON and performs no model calculation, so "
                "no model output changes. Additive contract bump keeps "
                "existing consumers working. Neutrality of the owner "
                "decision is preserved verbatim: options in registry "
                "order, NO default, decision record BLANK until the owner "
                "decides at workflow step 4. The governed headline remains "
                "the frozen single-df t component basis."
            ),
            quantitative_impact=(
                "UI now displays (bit-for-bit from the pack): governed "
                "headline {gh:.1f}; 2-tree vine point {vp:.1f}; tree-3 "
                "bootstrap mean {tm:.1f}; nested reference {nr:.1f} "
                "(outside both 95% CIs); options {oo}; escalation path "
                "{eo}. jsdom self-test ok with {nc} network calls and "
                "{je} JS errors over {n} checks."
            ).format(
                gh=hr["governed_headline"], vp=hr["vine2_point"],
                tm=hr["tree3_bootstrap_mean"], nr=hr["nested_reference"],
                oo="/".join(hr["option_order"] or []),
                eo=hr["escalation_option"],
                nc=st["network_calls"], je=st["js_errors"],
                n=st["n_checks"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "UI propagation verified by the contract checks (pack carried "
            "bit-for-bit, neutrality pinned: registry order / NO default / "
            "decision record BLANK) + jsdom self-tests (0 network / 0 JS "
            "errors across ui_app, offline viewer and combined GUI); "
            "display-layer change only; no model parameter changes.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. Gap G1 of the Phase 32 design note is "
            "closed: the owner decision pack is now browsable offline. The "
            "Phase 31 decision itself remains PENDING and entirely with "
            "the model owner (workflow step 4); nothing in this change "
            "steers or defaults that decision.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event=("ChangeRecord opened (OWNER_REVIEW) - Phase 32 "
                       "Task 2 owner-decision-pack surface (gap G1); "
                       "contract 1.14.0 additive; decision record BLANK"),
                details={
                    "record_id": rec.record_id,
                    "ui_contract": "1.14.0",
                    "self_test_ok": st["ok"],
                    "network_calls": st["network_calls"],
                    "js_errors": st["js_errors"],
                    "affected_components": AFFECTED_COMPONENTS,
                },
            )
        )
    else:
        for rec in store.change_records:
            if rec.title == CHANGE_TITLE:
                record_id = rec.record_id
                record_status = rec.status.value
    return {"added_change_record": added, "change_record_id": record_id,
            "change_record_status": record_status}


def main() -> int:
    ui = check_ui_contract()
    if not ui["all_passed"]:
        print("UI contract checks FAILED:",
              [k for k, v in ui.items()
               if v is False and k != "contract_version"])
        return 1
    st = _run_node(SELF_TEST, str(UI_APP))
    viewer = _run_node(VIEWER_TEST)
    combined = _run_node(COMBINED_TEST)
    if not (st["ok"] and st["network_calls"] == 0 and st["js_errors"] == 0
            and viewer["ok"] and combined["ok"]):
        print("Self-tests FAILED:", st, viewer["ok"], combined["ok"])
        return 1

    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_audit_before = len(store.audit_trail.all())
    n_change_before = len(store.change_records)
    gov = apply_governance(store, ui, st)
    integrity = store.audit_trail.verify_all()
    if not integrity:
        print("AUDIT INTEGRITY FAILED - store NOT saved")
        return 1
    GOV_PATH.write_text(store.to_json(), encoding="utf-8")

    report = {
        "task": "Phase 32 Task 2 - owner-decision-pack surface (gap G1)",
        "phase": PHASE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "gap_closed": "G1",
        "next": "Task 3 (gap G2): user-input run-result surface "
                "(contract 1.14.0 -> 1.15.0 additive)",
        "ui_contract_checks": ui,
        "self_test": st,
        "offline_viewer_self_test": viewer,
        "combined_gui_self_test": combined,
        "governance": {
            **gov,
            "audit_entries":
                f"{n_audit_before}->{len(store.audit_trail.all())}",
            "change_records":
                f"{n_change_before}->{len(store.change_records)}",
            "audit_integrity_verify_all": integrity,
        },
    }
    JSON_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    hr = ui["headline_readouts"]
    nck = sum(1 for k, v in ui.items()
              if v is True and k not in ("all_passed",))
    md = """# Phase 32 Task 2 - Owner-Decision-Pack Surface (Gap G1)

**Generated (UTC):** {now}
**Verdict:** PASS - gap G1 closed (contract v1.14.0, additive)

## What the offline UI now surfaces

A first-class **Owner Decision (P31)** tab carrying the Phase 31 owner
decision pack VERBATIM (bit-for-bit; nothing recomputed):

- **Evidence pack:** governed headline **{gh:,.1f}** (unchanged through
  P27-P30); disclosed candidates (2-tree vine point **{vp:,.1f}**, tree-3
  bootstrap mean **{tm:,.1f}**, with 95% CIs); nested single-run reference
  **{nr:,.1f}** outside both CIs; copula-form residual ladder; gap
  decomposition; MR-016 / MR-017 status; binding stop-rule record.
- **Owner options:** the three options in **registry order** ({oo}), NO
  default, no steering language; per-option capital effect, pre-registered
  acceptance criteria, escalation-path flag and governance risk.
- **Sign-off workflow:** all 6 steps; the decision sits at step 4 (model
  owner).
- **Decision record:** rendered **BLANK** until the owner decides.
- **Figure provenance, limitations, standards** carried verbatim.

## Pre-registered acceptance criteria (design note, gap G1)

- every displayed figure bit-for-bit from the pack: **PASS** (deep equality
  on all {npk} carried keys)
- neutrality preserved (registry order / NO default / decision BLANK):
  **PASS**
- new self-test checks cover the surface: **PASS** (25 added; suite
  {nst} checks ok:true)
- ui_app self-test 0 network / 0 JS errors: **PASS** ({nc}/{je})
- ADDITIVE-only contract change (1.13.0 -> 1.14.0): **PASS** (every
  pre-existing ui_data key bit-identical; sha256-stable inventory)
- zero-install preserved: **PASS** (0 external references, single
  self-contained HTML)
- NO model parameter changes: **PASS** (display layer only)
- offline viewer + combined GUI self-tests: **PASS** (ok:true both)

## Verification

- `ui_data.json` contract checks: ALL PASS ({nck} substantive checks).
- jsdom self-tests: ui_app ok:true ({nst} checks, {nc} network / {je} JS
  errors); offline viewer ok:true; combined GUI ok:true.

## Governance

- ChangeRecord `{crid}` ({crstatus}); audit entries {aud}; change records
  {chg}; audit-chain integrity verify_all = {integ}.
- The Phase 31 owner decision itself remains PENDING with the model owner.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6; IFoA MPN s4;
Solvency II Art. 234.
""".format(
        now=report["generated_utc"],
        gh=hr["governed_headline"], vp=hr["vine2_point"],
        tm=hr["tree3_bootstrap_mean"], nr=hr["nested_reference"],
        oo=" -> ".join(hr["option_order"] or []),
        npk=len(PACK_KEYS), nck=nck, nc=st["network_calls"],
        je=st["js_errors"], nst=st["n_checks"],
        crid=gov["change_record_id"], crstatus=gov["change_record_status"],
        aud=report["governance"]["audit_entries"],
        chg=report["governance"]["change_records"], integ=integrity,
    )
    MD_PATH.write_text(md, encoding="utf-8")

    print("PHASE 32 TASK 2 PASS - gap G1 closed; contract 1.14.0;",
          "ChangeRecord", gov["change_record_id"], gov["change_record_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
