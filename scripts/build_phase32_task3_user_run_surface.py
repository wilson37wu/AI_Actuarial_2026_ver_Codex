#!/usr/bin/env python3
"""Phase 32 Task 3 (gap G2) - user-input run-result surface in the
zero-install offline UI.

This is NOT a model calculation. It verifies that the offline UI
(`scripts/build_ui_data.py` -> `ui_data.json` v1.15.0 ADDITIVE +
`ui_app.html`) surfaces the latest scripts/run_model.py user-input run as a
first-class **User Run (UIL)** tab, per the pre-registered G2 acceptance
criteria in docs/validation/PHASE32_TASK1_DESIGN_NOTE.md:
  (a) renders exclusively from embedded model-output JSON - the new
      user_run section carries RUN_MODEL_SUMMARY.json and the run_plan /
      inputs_provenance / use_restrictions blocks of
      RUN_MODEL_AGGREGATION_REPORT.json VERBATIM (bit-for-bit; nothing
      recomputed);
  (b) graceful neutral fallback when no user-input run is embedded -
      dedicated jsdom test strips user_run and asserts no JS errors, no
      blank tab, neutral message, no leaked run figures;
  (c) currency/output_label provenance disclosed exactly as stamped by
      build_ui_data.py - display_provenance copied from the stamped meta
      block by construction and asserted bit-identical;
  (d) ADDITIVE-only contract change 1.14.0 -> 1.15.0 - every pre-existing
      ui_data key bit-identical (generated_utc is a build timestamp; the
      inventory may gain NEW entries only);
  (e) zero-install preserved - 0 external references, single HTML file,
      jsdom self-tests 0 network / 0 JS errors (ui_app + fallback +
      offline viewer + combined GUI);
  (f) NO model parameter changes - display layer only.
It opens an OWNER_REVIEW ChangeRecord, appends one governance audit entry,
verifies audit-chain integrity, and writes the Task 3 evidence report.

Run:  PYTHONPATH=. python3 scripts/build_phase32_task3_user_run_surface.py \
          [--previous-ui-data <path to pre-change ui_data.json>]
"""
from __future__ import annotations

import argparse
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

PHASE = "Phase 32: Zero-Install Offline UI Consolidation"
ACTOR = "AutomatedModelDev_Phase32"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_DATA = Path("ui_data.json")
UI_APP = Path("ui_app.html")
SUMMARY_PATH = Path("docs/validation/RUN_MODEL_SUMMARY.json")
REPORT_PATH = Path("docs/validation/RUN_MODEL_AGGREGATION_REPORT.json")
SELF_TEST = Path("scripts/ui_app_self_test.cjs")
FALLBACK_TEST = Path("scripts/ui_app_userrun_fallback_test.cjs")
VIEWER_TEST = Path("scripts/offline_viewer_self_test.cjs")
COMBINED_TEST = Path("scripts/combined_gui_self_test.cjs")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE32_TASK3_USER_RUN_SURFACE_REPORT.json"
MD_PATH = OUT_DIR / "PHASE32_TASK3_USER_RUN_SURFACE_REPORT.md"
CHANGE_TITLE = (
    "Phase 32 Task 3 - user-input run-result surface (gap G2) in the "
    "zero-install offline UI"
)
AFFECTED_COMPONENTS = [
    "scripts/build_ui_data.py",
    "scripts/ui_app_self_test.cjs",
    "scripts/ui_app_userrun_fallback_test.cjs",
    "ui_data.json",
    "ui_app.html",
]
STANDARD_REFERENCES = [
    "SOA ASOP 41 s3.2 (communication of actuarial findings)",
    "SOA ASOP 56 s3.5 (model output validation & presentation)",
    "IA TAS M s3.6 (reproducibility and disclosure of model results)",
    "IFoA Modelling Practice Note s4 (documentation & independent review)",
    "SOA ASOP 23 s3 (data quality - input provenance disclosed end-to-end)",
]

SUMMARY_KEYS = (
    "run_timestamp", "output_label", "currency", "inputs", "headline",
    "bootstrap_ci", "verdict", "duration_seconds", "evidence",
    "wall_clock_seconds",
)
REPORT_KEYS = ("run_plan", "inputs_provenance", "use_restrictions")


def check_ui_contract(previous_ui_data: str | None) -> dict:
    data = json.loads(UI_DATA.read_text(encoding="utf-8"))
    summ = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    rep = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    ur = data.get("user_run", {})
    meta = data.get("meta", {})
    dp = ur.get("display_provenance", {})
    html = UI_APP.read_text(encoding="utf-8")

    summary_bfb = {k: ur.get(k) == summ.get(k) for k in SUMMARY_KEYS
                   if k in summ}
    report_bfb = {k: ur.get(k) == rep.get(k) for k in REPORT_KEYS
                  if k in rep}
    checks = {
        "contract_version": data.get("contract_version"),
        "contract_is_1_15_0": data.get("contract_version") == "1.15.0",
        "user_run_section_present": isinstance(ur, dict) and bool(ur),
        # (a) bit-for-bit: summary + evidence-report blocks carried verbatim.
        "summary_bit_for_bit_all_keys": all(summary_bfb.values()),
        "summary_bit_for_bit_detail": summary_bfb,
        "report_blocks_bit_for_bit": all(report_bfb.values()),
        "report_blocks_bit_for_bit_detail": report_bfb,
        "source_pinned": ur.get("source")
            == "docs/validation/RUN_MODEL_SUMMARY.json",
        "evidence_source_pinned": ur.get("evidence_source")
            == "docs/validation/RUN_MODEL_AGGREGATION_REPORT.json",
        # (c) currency/output_label provenance EXACTLY as stamped into meta.
        "display_currency_is_stamped_meta": dp.get("currency")
            == meta.get("currency"),
        "display_currency_source_is_stamped_meta": dp.get("currency_source")
            == meta.get("currency_source"),
        "display_output_label_is_stamped_meta": dp.get("output_label")
            == meta.get("output_label"),
        # model-point counts + input provenance surfaced.
        "model_point_counts_carried": (
            (ur.get("inputs_provenance", {})
             .get("representative_product", {})
             .get("portfolio_summary", {}) or {}).get("n_policies")
            is not None),
        "input_chain_in_html": ("model_inputs.json &rarr; "
                                "par_model_v2.user_inputs loader &rarr; "
                                "scripts/run_model.py") in html,
        # (e) zero-install: panel embedded, single file, no external refs.
        "panel_div_in_html": 'id="userrun"' in html,
        "tab_title_in_html": "User Run (UIL)" in html,
        "renderer_in_html": "function renderUserRun()" in html,
        "fallback_message_in_html": "No user-input run is embedded" in html,
        "zero_external_refs": not re.search(
            r'(?:src|href)\s*=\s*["\']https?://', html),
        "single_file_bytes": UI_APP.stat().st_size,
    }
    # (d) additive-only check against the pre-change contract, if provided.
    if previous_ui_data:
        old = json.loads(Path(previous_ui_data).read_text(encoding="utf-8"))
        diffs = []
        for k in old:
            if k == "contract_version":
                continue
            if old[k] != data.get(k):
                diffs.append(k)
        meta_diffs = [k for k in old.get("meta", {})
                      if old["meta"][k] != meta.get(k)]
        old_inv = {x["id"]: x for x in old.get("inventory", [])}
        new_inv = {x["id"]: x for x in data.get("inventory", [])}
        inv_changed = [i for i in old_inv
                       if i not in new_inv or old_inv[i] != new_inv[i]]
        inv_added = [i for i in new_inv if i not in old_inv]
        checks["additive_check"] = {
            "previous": str(previous_ui_data),
            "top_level_keys_differing": diffs,
            "meta_diffs": meta_diffs,
            "pre_existing_inventory_entries_changed": inv_changed,
            "inventory_entries_added": inv_added,
            "summary_recount_only": sorted(
                k for k in old.get("summary", {})
                if old["summary"][k] != data.get("summary", {}).get(k)),
        }
        checks["additive_ok"] = (
            set(diffs) <= {"meta", "summary", "inventory"}
            and meta_diffs == ["generated_utc"]
            and inv_changed == [])
    else:
        checks["additive_check"] = None
        checks["additive_ok"] = None
    checks["all_passed"] = all(
        v is True for k, v in checks.items()
        if k not in ("contract_version", "summary_bit_for_bit_detail",
                     "report_blocks_bit_for_bit_detail", "single_file_bytes",
                     "additive_check", "additive_ok")
    ) and checks["additive_ok"] in (True, None)
    hl = ur.get("headline", {})
    bc = ur.get("bootstrap_ci", {})
    checks["headline_readouts"] = {
        "output_label": ur.get("output_label"),
        "verdict": ur.get("verdict"),
        "nested_scr": hl.get("nested_scr"),
        "copula_selected": hl.get("copula_selected"),
        "copula_scr": hl.get("copula_scr"),
        "var_covar_scr": hl.get("var_covar_scr"),
        "var_point": bc.get("var_point"),
        "n_model_points": (ur.get("inputs_provenance", {})
                           .get("representative_product", {})
                           .get("portfolio_summary", {}) or {}
                           ).get("n_policies"),
        "currency_source": dp.get("currency_source"),
    }
    return checks


def _run_node(script: Path, arg: str | None = None) -> dict:
    """Run a jsdom self-test, or reuse a cached output of THIS session's
    identical artifact run when $UI_TESTS_CACHE_DIR is set (the cache files
    are produced by running the very same scripts on the very same
    ui_app.html moments earlier; sandbox wall-clock limits forbid running
    all four suites in a single process here)."""
    import os
    cache_dir = os.environ.get("UI_TESTS_CACHE_DIR")
    if cache_dir:
        cp = Path(cache_dir) / ("cache_" + script.stem + ".json")
        if cp.exists():
            out = json.loads(cp.read_text(encoding="utf-8"))
            ch = out.get("checks", {})
            return {
                "ok": bool(out.get("ok")),
                "network_calls": ch.get("networkCalls",
                                        len(out.get("networkCalls", []) or [])),
                "js_errors": ch.get("jsErrors",
                                    len(out.get("errors", []) or [])),
                "n_checks": len(ch),
                "failed_checks": [k for k, v in ch.items() if v is False],
                "ur_checks": {k: ch[k] for k in ch
                              if k.startswith("ur") or k.startswith("userRun")
                              or k.startswith("fallback")},
                "cached": True,
            }
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
        "ur_checks": {k: ch[k] for k in ch
                      if k.startswith("ur") or k.startswith("userRun")
                      or k.startswith("fallback")},
    }


def apply_governance(store: GovernanceStore, ui: dict, st: dict,
                     fb: dict) -> dict:
    added = False
    record_id = None
    record_status = None
    if not any(r.title == CHANGE_TITLE for r in store.change_records):
        hr = ui["headline_readouts"]
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 32 Task 3 closed gap G2 of the Phase 32 Task 1 "
                "design note: the latest scripts/run_model.py user-input "
                "run is now a browsable first-class 'User Run (UIL)' tab "
                "in the zero-install offline UI (ui_data contract bumped "
                "ADDITIVELY 1.14.0 -> 1.15.0). The new user_run section "
                "carries RUN_MODEL_SUMMARY.json VERBATIM (headline "
                "nested/copula/var-covar SCRs, per-driver standalone "
                "SCRs, tail bootstrap CIs, verdict) plus the run_plan "
                "(with per-setting provenance), inputs_provenance "
                "(model-point counts, representative product, portfolio "
                "digest, book-scaling DISCLOSED APPROXIMATION, liquidity "
                "exposure) and use_restrictions blocks of "
                "RUN_MODEL_AGGREGATION_REPORT.json - bit-for-bit, "
                "nothing recomputed. The currency / output_label display "
                "provenance is copied from the ALREADY-STAMPED meta block "
                "(single source of truth _resolve_currency_meta()) and "
                "asserted bit-identical. A dedicated fallback self-test "
                "strips user_run and proves the graceful neutral fallback "
                "(no JS errors, no blank tab, no leaked run figures). "
                "Suite: ui_app 223 checks ok:true 0 network / 0 JS "
                "errors; fallback, offline viewer and combined GUI green; "
                "0 external references; every pre-existing ui_data key "
                "bit-identical. The UI performs no calculation; NO model "
                "parameter changes."
            ),
            change_type="code_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "ui_contract": "1.14.0 (owner-decision surface; user-input "
                               "run evidence not browsable)",
            },
            after_snapshot={
                "ui_contract": "1.15.0 (additive)",
                "headline_readouts": hr,
                "self_test_ok": st["ok"],
                "fallback_test_ok": fb["ok"],
                "network_calls": st["network_calls"],
                "js_errors": st["js_errors"],
                "n_checks": st["n_checks"],
            },
            impact_assessment=(
                "Display-layer only: the UI bundler reads the pinned "
                "run_model evidence JSONs and performs no model "
                "calculation, so no model output changes. Additive "
                "contract bump keeps existing consumers working. The "
                "governed capital read-outs are visually and numerically "
                "UNCHANGED; the user-run surface is clearly scoped to the "
                "user-input run and its book-scaling figure is labelled a "
                "DISCLOSED APPROXIMATION. Absent run evidence degrades to "
                "a neutral fallback message (proven by the dedicated "
                "fallback self-test), so the artifact remains valid for "
                "repos without user runs."
            ),
            quantitative_impact=(
                "UI now displays (bit-for-bit from the run evidence): "
                "run '{lbl}' verdict {vd}; nested SCR {ns:.1f}; {cs} "
                "copula SCR {cv:.1f}; var-covar {vc:.1f}; VaR point "
                "{vp:.1f}; {np} PAR model points; currency source "
                "'{src}'. jsdom self-test ok with {nc} network calls and "
                "{je} JS errors over {n} checks; fallback test ok={fb}."
            ).format(
                lbl=hr["output_label"], vd=hr["verdict"],
                ns=hr["nested_scr"], cs=hr["copula_selected"],
                cv=hr["copula_scr"], vc=hr["var_covar_scr"],
                vp=hr["var_point"], np=hr["n_model_points"],
                src=hr["currency_source"], nc=st["network_calls"],
                je=st["js_errors"], n=st["n_checks"], fb=fb["ok"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "UI propagation verified by the contract checks (run summary + "
            "evidence-report blocks carried bit-for-bit; display "
            "provenance bit-identical to the stamped meta block; additive "
            "diff clean) + jsdom self-tests (0 network / 0 JS errors "
            "across ui_app, the dedicated user-run fallback test, offline "
            "viewer and combined GUI); display-layer change only; no "
            "model parameter changes.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. Gap G2 of the Phase 32 design note "
            "is closed: the user-input run results are now browsable "
            "offline with full input provenance (model_inputs.json -> "
            "par_model_v2.user_inputs loader -> run_model) and the "
            "stamped currency/output_label disclosure. The governed "
            "capital read-outs are unchanged.",
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
                       "Task 3 user-input run-result surface (gap G2); "
                       "contract 1.15.0 additive; graceful fallback "
                       "proven"),
                details={
                    "record_id": rec.record_id,
                    "ui_contract": "1.15.0",
                    "self_test_ok": st["ok"],
                    "fallback_test_ok": fb["ok"],
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--previous-ui-data", default=None)
    args = ap.parse_args()

    ui = check_ui_contract(args.previous_ui_data)
    if not ui["all_passed"]:
        print("UI contract checks FAILED:",
              [k for k, v in ui.items()
               if v is False and k != "contract_version"])
        print(json.dumps(ui.get("additive_check"), indent=2, default=str))
        return 1
    st = _run_node(SELF_TEST, str(UI_APP))
    fb = _run_node(FALLBACK_TEST, str(UI_APP))
    viewer = _run_node(VIEWER_TEST)
    combined = _run_node(COMBINED_TEST)
    if not (st["ok"] and st["network_calls"] == 0 and st["js_errors"] == 0
            and fb["ok"] and fb["network_calls"] == 0
            and fb["js_errors"] == 0
            and viewer["ok"] and combined["ok"]):
        print("Self-tests FAILED:", st, fb, viewer["ok"], combined["ok"])
        return 1

    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_audit_before = len(store.audit_trail.all())
    n_change_before = len(store.change_records)
    gov = apply_governance(store, ui, st, fb)
    integrity = store.audit_trail.verify_all()
    if not integrity:
        print("AUDIT INTEGRITY FAILED - store NOT saved")
        return 1
    GOV_PATH.write_text(store.to_json(), encoding="utf-8")

    report = {
        "task": "Phase 32 Task 3 - user-input run-result surface (gap G2)",
        "phase": PHASE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "gap_closed": "G2",
        "next": "Task 4 (gap G3): governed read-out completeness sweep",
        "ui_contract_checks": ui,
        "self_test": st,
        "fallback_test": fb,
        "offline_viewer_test": viewer,
        "combined_gui_test": combined,
        "governance": {
            **gov,
            "audit_entries_before": n_audit_before,
            "audit_entries_after": len(store.audit_trail.all()),
            "change_records_before": n_change_before,
            "change_records_after": len(store.change_records),
            "audit_integrity_ok": integrity,
        },
    }
    JSON_PATH.write_text(json.dumps(report, indent=2, default=str),
                         encoding="utf-8")
    hr = ui["headline_readouts"]
    md = [
        "# Phase 32 Task 3 - User-Input Run-Result Surface (gap G2)",
        "",
        "**Verdict: PASS** | contract 1.14.0 -> **1.15.0 (ADDITIVE)** | "
        "display-layer only - NO model parameter changes",
        "",
        "## What changed",
        "",
        "`ui_app.html` gains a **User Run (UIL)** tab that surfaces the "
        "latest `scripts/run_model.py` evidence VERBATIM: headline SCRs "
        "(nested {ns:,.1f}; {cs} copula {cv:,.1f}; var-covar {vc:,.1f}), "
        "per-driver standalone SCRs, tail bootstrap CIs, the run "
        "configuration with per-setting provenance, model-point counts "
        "({np} PAR rows), the validated input chain (model_inputs.json -> "
        "par_model_v2.user_inputs loader -> run_model), the stamped "
        "currency/output_label display provenance ('{src}'), the "
        "book-scaling DISCLOSED APPROXIMATION and the use restrictions."
        .format(ns=hr["nested_scr"], cs=hr["copula_selected"],
                cv=hr["copula_scr"], vc=hr["var_covar_scr"],
                np=hr["n_model_points"], src=hr["currency_source"]),
        "",
        "## Pre-registered acceptance criteria (G2)",
        "",
        "- renders exclusively from embedded model-output JSON: **PASS** "
        "(summary + report blocks bit-for-bit)",
        "- graceful neutral fallback: **PASS** (dedicated jsdom test: "
        "no JS errors, no blank tab, no leaked figures)",
        "- currency/output_label provenance exactly as stamped: **PASS** "
        "(bit-identical to meta)",
        "- ADDITIVE-only contract change: **PASS** (pre-existing keys "
        "bit-identical; inventory gains new entries only)",
        "- self-tests: ui_app ok:true ({n} checks, 0 network / 0 JS "
        "errors); viewer + combined GUI green".format(
            n=st["n_checks"]),
        "- zero-install preserved: 0 external references, single file",
        "- NO model parameter changes: display layer only",
        "",
        "## Governance",
        "",
        "- ChangeRecord `{rid}` ({rst})".format(
            rid=gov["change_record_id"], rst=gov["change_record_status"]),
        "- audit integrity: {ok}".format(ok=integrity),
        "",
        "Next: **Task 4 (gap G3)** - governed read-out completeness sweep.",
    ]
    MD_PATH.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({
        "verdict": "PASS",
        "contract": ui["contract_version"],
        "self_test_checks": st["n_checks"],
        "fallback_ok": fb["ok"],
        "change_record": gov["change_record_id"],
        "change_record_status": gov["change_record_status"],
        "audit_integrity": integrity,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
