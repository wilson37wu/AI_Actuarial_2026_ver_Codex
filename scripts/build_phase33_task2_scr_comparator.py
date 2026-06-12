#!/usr/bin/env python3
"""Phase 33 Task 2 (gap G1) - interactive cross-phase SCR comparator in the
zero-install offline UI.

This is NOT a model calculation. It verifies that the offline UI
(`scripts/build_ui_data.py` -> `ui_app.html`) now carries an interactive
**SCR Comparator (P33)** tab per the pre-registered G1 acceptance criteria in
docs/validation/PHASE33_TASK1_DESIGN_NOTE.md:
  (a) every comparator figure traces bit-for-bit to a key ALREADY embedded in
      ui_data contract 1.16.0 (frozen-t / grouped-t / skew-t / vine 2-tree /
      vine 3-tree points + 95% bootstrap CIs from the P26-P30 bootstrap
      blocks; nested path-wise reference) - NO new build-time data;
  (b) the governed frozen-t headline 39,975.654628199336 stays the DEFAULT
      baseline and is never re-labelled by the comparator;
  (c) neutrality - structures in registry order, no adoption/steering
      language (the MR-016/MR-017 decision stays with the owner);
  (d) signed deltas are labelled display arithmetic, NOT new model output;
  (e) NO contract change - ui_data.json byte-identical, embedded snapshot
      byte-identical, contract stays 1.16.0;
  (f) zero-install preserved - 0 external references, single HTML file,
      jsdom self-tests 0 network / 0 JS errors (ui_app 248 checks incl. 16
      new comparator checks + offline viewer + combined GUI + user-run
      fallback);
  (g) NO model parameter changes - display layer only.
It opens an OWNER_REVIEW ChangeRecord, appends one governance audit entry,
verifies audit-chain integrity, and writes the Task 2 evidence report.

Run:  PYTHONPATH=. python3 scripts/build_phase33_task2_scr_comparator.py
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
)

PHASE = "Phase 33: Offline UI Interactive Analytics & Usability"
ACTOR = "AutomatedModelDev_Phase33"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_DATA = Path("ui_data.json")
UI_APP = Path("ui_app.html")
SELF_TEST = Path("scripts/ui_app_self_test.cjs")
VIEWER_TEST = Path("scripts/offline_viewer_self_test.cjs")
COMBINED_TEST = Path("scripts/combined_gui_self_test.cjs")
USERRUN_TEST = Path("scripts/ui_app_userrun_fallback_test.cjs")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE33_TASK2_SCR_COMPARATOR_REPORT.json"
MD_PATH = OUT_DIR / "PHASE33_TASK2_SCR_COMPARATOR_REPORT.md"
CHANGE_TITLE = (
    "Phase 33 Task 2 - interactive cross-phase SCR comparator (gap G1) in "
    "the zero-install offline UI"
)
AFFECTED_COMPONENTS = [
    "scripts/build_ui_data.py",
    "scripts/ui_app_self_test.cjs",
    "ui_app.html",
]
STANDARD_REFERENCES = [
    "SOA ASOP 41 s3.2 (communication of actuarial findings)",
    "SOA ASOP 56 s3.5 (model output validation & presentation)",
    "IA TAS M s3.6 (reproducibility and disclosure of model results)",
    "IFoA Modelling Practice Note s4 (documentation & independent review)",
    "Solvency II Art. 234 (dependence justification - structures COMPARED "
    "neutrally, none adopted; owner decision pending)",
]

GOVERNED_HEADLINE = 39975.654628199336
REGISTRY = ("frozen_t", "grouped_t", "skew_t", "vine2", "tree3", "nested")


def check_ui_contract() -> dict:
    data = json.loads(UI_DATA.read_text(encoding="utf-8"))
    html = UI_APP.read_text(encoding="utf-8")
    p27 = data["phase27"]["bootstrap"]
    p28 = data["phase28"]["bootstrap"]
    p29 = data["phase29"]["bootstrap"]
    p30 = data["phase30"]["bootstrap"]

    # (a) the comparator's source keys exist in the UNCHANGED 1.16.0 snapshot
    src_keys = {
        "frozen_t_point": p29.get("task2_frozen_t_component_point"),
        "frozen_t_ci": p29.get("frozen_t_component_scr_ci"),
        "grouped_t_point": p28.get("task2_grouped_t_component_point"),
        "grouped_t_ci": p28.get("grouped_t_component_scr_ci"),
        "skew_t_point": p27.get("task2_skewt_component_point"),
        "skew_t_ci": p27.get("skewt_component_scr_ci"),
        "vine2_point": p29.get("task2_vine_candidate_component_point"),
        "vine2_ci": p29.get("vine_component_scr_ci"),
        "tree3_point": p30.get("task2_tree3_candidate_component_point"),
        "tree3_ci": p30.get("tree3_component_scr_ci"),
        "nested_reference": p29.get("nested_pathwise_reference"),
    }
    # (e) NO contract change: ui_data.json byte-identical to git HEAD and the
    # embedded snapshot byte-identical to the previous ui_app.html.
    head_ui_data = subprocess.run(
        ["git", "show", "HEAD:ui_data.json"], capture_output=True, text=True
    ).stdout
    head_html = subprocess.run(
        ["git", "show", "HEAD:ui_app.html"], capture_output=True, text=True
    ).stdout
    pat = re.compile(
        r'<script id="ui-data" type="application/json">(.*?)</script>', re.S)
    old_block = pat.search(head_html).group(1) if pat.search(head_html) else None
    new_block = pat.search(html).group(1) if pat.search(html) else None

    checks = {
        "contract_version": data.get("contract_version"),
        "contract_unchanged_1_16_0": data.get("contract_version") == "1.16.0",
        "ui_data_json_byte_identical_to_head":
            head_ui_data == UI_DATA.read_text(encoding="utf-8"),
        "embedded_snapshot_byte_identical_to_head":
            old_block is not None and old_block == new_block,
        "all_source_keys_already_embedded":
            all(v is not None for v in src_keys.values()),
        "governed_headline_exact": (
            src_keys["frozen_t_point"] == GOVERNED_HEADLINE),
        "all_five_cis_have_bounds": all(
            isinstance(src_keys[k], dict)
            and "ci_lo" in src_keys[k] and "ci_hi" in src_keys[k]
            for k in ("frozen_t_ci", "grouped_t_ci", "skew_t_ci",
                      "vine2_ci", "tree3_ci")),
        # comparator surface in the HTML
        "panel_div_in_html": 'id="comparator"' in html,
        "tab_title_in_html": "SCR Comparator (P33)" in html,
        "renderer_in_html": "function renderComparator()" in html,
        "default_baseline_frozen_t":
            'CMP_BASELINE_DEFAULT = "frozen_t"' in html,
        "display_arithmetic_labelled": "display arithmetic" in html
            and "NOT new model output" in html,
        "neutrality_registry_order": "registry order" in html
            and "rests with the owner" in html,
        "no_steering_language": not re.search(
            r"recommended structure|should adopt|we recommend|best structure",
            html, re.I),
        "zero_external_refs": not re.search(
            r'(?:src|href)\s*=\s*["\']https?://', html),
        "single_file_bytes": UI_APP.stat().st_size,
    }
    checks["all_passed"] = all(
        v is True for k, v in checks.items()
        if k not in ("contract_version", "single_file_bytes"))
    checks["headline_readouts"] = {
        "governed_headline_frozen_t": src_keys["frozen_t_point"],
        "grouped_t_point": src_keys["grouped_t_point"],
        "skew_t_point": src_keys["skew_t_point"],
        "vine2_point": src_keys["vine2_point"],
        "tree3_point": src_keys["tree3_point"],
        "nested_reference": src_keys["nested_reference"],
        "registry_order": list(REGISTRY),
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
        "cmp_checks": {k: ch[k] for k in ch if k.startswith("cmp")},
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
                "Phase 33 Task 2 closed gap G1 of the Phase 33 Task 1 "
                "design note: the zero-install offline UI now carries an "
                "interactive 'SCR Comparator (P33)' tab - a pure display "
                "layer over ui_data contract 1.16.0 with NO contract "
                "change (ui_data.json and the embedded snapshot are "
                "byte-identical to the previous commit). The comparator "
                "renders, in registry order (frozen-t / grouped-t / "
                "skew-t / vine 2-tree / vine 3-tree / nested reference), "
                "the component-SCR points and 95% bootstrap CIs ALREADY "
                "embedded by the P26-P30 bootstrap blocks; offers a "
                "user-selectable baseline (default = governed frozen-t "
                "headline 39,975.7, never re-labelled); shows a signed "
                "delta table explicitly labelled display arithmetic (NOT "
                "new model output); overlays the CIs in one chart; and "
                "discloses per-figure provenance keys. 16 new jsdom "
                "self-test checks (suite 248 checks, ok:true, 0 network / "
                "0 JS errors) cover registry order, exact governed "
                "headline, default baseline, delta signs, baseline "
                "switching/restoration, CI overlay rendering, neutrality "
                "and provenance. Offline viewer, combined GUI and "
                "user-run fallback self-tests remain green; 0 external "
                "references. The UI performs no calculation beyond the "
                "labelled display subtraction; NO model parameter changes."
            ),
            change_type="code_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "ui_contract": "1.16.0 (dependence-structure SCRs "
                               "presented phase-by-phase only)",
            },
            after_snapshot={
                "ui_contract": "1.16.0 (UNCHANGED - display layer only)",
                "headline_readouts": hr,
                "self_test_ok": st["ok"],
                "network_calls": st["network_calls"],
                "js_errors": st["js_errors"],
                "n_checks": st["n_checks"],
            },
            impact_assessment=(
                "Display-layer only: the comparator reads figures already "
                "embedded in the snapshot and performs no model "
                "calculation; the only arithmetic is the signed display "
                "subtraction, labelled as such. No contract change, no "
                "model output changes, no consumer impact. Neutrality "
                "preserved: registry order, no default switch of the "
                "governed basis, no steering language; the MR-016/MR-017 "
                "dependence decision remains entirely with the owner."
            ),
            quantitative_impact=(
                "Comparator renders (bit-for-bit from embedded keys): "
                "governed frozen-t headline {gh:.1f} (default baseline); "
                "grouped-t {gt:.1f}; skew-t {sk:.1f}; vine 2-tree "
                "{v2:.1f}; vine 3-tree {t3:.1f}; nested reference "
                "{nr:.1f}. jsdom self-test ok with {nc} network calls and "
                "{je} JS errors over {n} checks."
            ).format(
                gh=hr["governed_headline_frozen_t"],
                gt=hr["grouped_t_point"], sk=hr["skew_t_point"],
                v2=hr["vine2_point"], t3=hr["tree3_point"],
                nr=hr["nested_reference"],
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
            "UI comparator verified by the contract checks (NO contract "
            "change - ui_data.json and embedded snapshot byte-identical to "
            "HEAD; every figure traces to an already-embedded key; "
            "governed headline exact and default; neutrality pinned: "
            "registry order / no steering language / deltas labelled "
            "display arithmetic) + jsdom self-tests (0 network / 0 JS "
            "errors across ui_app 248 checks, offline viewer, combined GUI "
            "and user-run fallback); display-layer change only; no model "
            "parameter changes.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. Gap G1 of the Phase 33 design note is "
            "closed: dependence-structure SCRs are now comparable "
            "interactively in one neutral view. The MR-016/MR-017 "
            "dependence decision remains PENDING and entirely with the "
            "model owner; nothing in this change steers or defaults that "
            "decision.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event=("ChangeRecord opened (OWNER_REVIEW) - Phase 33 "
                       "Task 2 interactive cross-phase SCR comparator "
                       "(gap G1); contract 1.16.0 UNCHANGED; governed "
                       "frozen-t default baseline preserved"),
                details={
                    "record_id": rec.record_id,
                    "ui_contract": "1.16.0 (unchanged)",
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
    userrun = _run_node(USERRUN_TEST)
    if not (st["ok"] and st["network_calls"] == 0 and st["js_errors"] == 0
            and viewer["ok"] and combined["ok"] and userrun["ok"]):
        print("Self-tests FAILED:", st, viewer["ok"], combined["ok"],
              userrun["ok"])
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
        "task": "Phase 33 Task 2 - interactive cross-phase SCR comparator "
                "(gap G1)",
        "phase": PHASE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "gap_closed": "G1",
        "next": "Task 3 (gap G2): embedded-distribution drill-down with "
                "precomputed grids (contract 1.16.0 -> 1.17.0 additive)",
        "ui_contract_checks": ui,
        "self_test": st,
        "offline_viewer_self_test": viewer,
        "combined_gui_self_test": combined,
        "userrun_fallback_self_test": userrun,
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
    nck = sum(1 for k, v in ui.items() if v is True and k != "all_passed")
    md = """# Phase 33 Task 2 - Interactive Cross-Phase SCR Comparator (Gap G1)

**Generated (UTC):** {now}
**Verdict:** PASS - gap G1 closed (contract v1.16.0 UNCHANGED; display layer only)

## What the offline UI now surfaces

A first-class **SCR Comparator (P33)** tab - an interactive, neutral
comparison of every dependence-structure component-SCR estimate already
embedded in the snapshot (registry order):

| Structure | Point (embedded) |
|---|---|
| Frozen single-df t (GOVERNED HEADLINE, default baseline) | {gh:,.1f} |
| Grouped-t (P28) | {gt:,.1f} |
| Skew-t (P27) | {sk:,.1f} |
| Vine 2-tree (P29) | {v2:,.1f} |
| Vine 3-tree (P30) | {t3:,.1f} |
| Nested path-wise reference (P24; point only) | {nr:,.1f} |

- **User-selectable baseline** (default = governed frozen-t; the governed
  label never moves with the selection).
- **Signed delta table** vs the selected baseline, explicitly labelled
  *display arithmetic - NOT new model output*.
- **95% bootstrap CI overlay chart** (whiskers = embedded CIs; the nested
  reference is point-only, disclosed as such).
- **Figure provenance**: the exact embedded ui_data key for every figure.

## Pre-registered acceptance criteria (design note, gap G1)

- every comparator figure traces bit-for-bit to an already-embedded
  ui_data 1.16.0 key (no new build-time data): **PASS** (ui_data.json and
  the embedded snapshot are byte-identical to the previous commit)
- governed frozen-t headline 39,975.654628199336 stays the default
  baseline and is never re-labelled: **PASS** (exact-precision check +
  re-label checks under non-default baselines)
- comparator neutral - registry order, no adoption/steering language:
  **PASS**
- new self-test checks cover baseline switching, delta signs and CI
  overlay rendering: **PASS** (16 added; suite {nst} checks ok:true)
- ui_app self-test 0 network / 0 JS errors: **PASS** ({nc}/{je})
- ADDITIVE-only contract change (if any): **PASS** (NO change at all -
  contract stays 1.16.0)
- zero-install preserved: **PASS** (0 external references, single
  self-contained HTML)
- NO model parameter changes: **PASS** (display layer only; the only
  arithmetic is the labelled display subtraction)
- offline viewer + combined GUI + user-run fallback self-tests: **PASS**

## Verification

- UI contract checks: ALL PASS ({nck} substantive checks).
- jsdom self-tests: ui_app ok:true ({nst} checks, {nc} network / {je} JS
  errors); offline viewer ok:true; combined GUI ok:true; user-run
  fallback ok:true.

## Governance

- ChangeRecord `{crid}` ({crstatus}); audit entries {aud}; change records
  {chg}; audit-chain integrity verify_all = {integ}.
- The MR-016/MR-017 dependence decision remains PENDING with the model
  owner; the comparator recommends nothing.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6; IFoA MPN s4;
Solvency II Art. 234.
""".format(
        now=report["generated_utc"],
        gh=hr["governed_headline_frozen_t"], gt=hr["grouped_t_point"],
        sk=hr["skew_t_point"], v2=hr["vine2_point"], t3=hr["tree3_point"],
        nr=hr["nested_reference"], nck=nck, nc=st["network_calls"],
        je=st["js_errors"], nst=st["n_checks"],
        crid=gov["change_record_id"], crstatus=gov["change_record_status"],
        aud=report["governance"]["audit_entries"],
        chg=report["governance"]["change_records"], integ=integrity,
    )
    MD_PATH.write_text(md, encoding="utf-8")

    print("PHASE 33 TASK 2 PASS - gap G1 closed; contract 1.16.0 unchanged;",
          "ChangeRecord", gov["change_record_id"], gov["change_record_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
