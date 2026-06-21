#!/usr/bin/env python3
"""Phase IGUI Task 1 - emit the Actuarial Input & Run GUI DESIGN NOTE.

Writes the pre-registered design note (from
``par_model_v2.viewer.igui_input_run_gui``) and its Task-1 gate result to
``docs/validation/PHASE_IGUI_TASK1_DESIGN_NOTE.{json,md}``. Design-note ONLY -
no GUI code, no model-parameter change, no contract change this cycle.

Run:  PYTHONPATH=. python3 scripts/build_phase_igui_task1_design_note.py
"""
from __future__ import annotations

import json
from pathlib import Path

from par_model_v2.viewer.igui_input_run_gui import design_note, validate_design_note

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "docs" / "validation"
JSON_OUT = OUT_DIR / "PHASE_IGUI_TASK1_DESIGN_NOTE.json"
MD_OUT = OUT_DIR / "PHASE_IGUI_TASK1_DESIGN_NOTE.md"


def _md(note: dict, gate: dict) -> str:
    md = note["metadata"]
    base = note["baseline_audit"]
    arch = note["architecture_decision"]
    cov = note["input_schema_coverage_map"]
    L = []
    L.append(f"# {md['doc_id']} (v{md['doc_version']})")
    L.append("")
    L.append(f"**Phase:** {md['phase']}  ")
    L.append(f"**Task:** {md['task']}  ")
    L.append(f"**Classification:** {md['classification']}  ")
    L.append(f"**Measured baseline:** {base['measured_at_utc']} ({base['phase_status']})")
    L.append("")
    L.append("> " + md["directive"])
    L.append("")
    L.append("## Discipline (binding)")
    L.append("")
    L.append(f"- NO model parameter changes: **{md['no_model_parameter_changes']}**")
    L.append(f"- Phase 30 stop-rule honoured: **{md['stop_rule_honoured']}**")
    L.append(f"- MR-016/MR-017 owner decision not pre-empted: **{md['owner_decision_pending']}**")
    L.append(f"- RESULTS UI (ui_app.html) stays zero-install & unchanged: **{md['zero_install_results_ui_preserved']}**")
    L.append("")
    L.append("## Baseline audit (frozen cross-check targets)")
    L.append("")
    L.append(f"- {base['self_test_suites_total']} offline self-test suites, all ok:true, "
             f"**{base['self_test_checks_total']} checks**, 0 network / 0 JS errors")
    L.append(f"- contract **{base['contract_version']}**, {base['top_level_keys']} top-level keys, "
             f"{base['tab_count']} tabs, **0 external references**")
    L.append(f"- governance: {base['governance_store']['change_records']} ChangeRecords / "
             f"{base['governance_store']['audit_entries']} audit entries / "
             f"{base['governance_store']['risk_register']} risk items")
    L.append("")
    L.append("## (b) Architecture decision")
    L.append("")
    L.append(f"**Chosen: `{arch['chosen']}`.** {arch['trade_off']}")
    L.append("")
    for o in arch["options"]:
        L.append(f"### {o['id']} — {o['title']}")
        L.append(f"*Verdict:* {o['verdict']}")
        L.append("")
        L.append("Pros: " + "; ".join(o["pros"]))
        L.append("")
        L.append("Cons: " + "; ".join(o["cons"]))
        L.append("")
    L.append("## (c) Input-schema coverage map")
    L.append("")
    L.append(f"Integration chain: `{cov['integration_chain']}`")
    L.append("")
    L.append("| Domain | Current coverage | Target | Gap | Closes in |")
    L.append("|---|---|---|---|---|")
    for d in cov["domains"]:
        L.append("| {dom} | {cur} | {tgt} | {gap} | {tsk} |".format(
            dom=d["domain"],
            cur="<br>".join(d["current_coverage"]),
            tgt="<br>".join(d["target"]),
            gap="<br>".join(d["gap"]),
            tsk=d["task"]))
    L.append("")
    L.append("## Staged tasks (one input domain per cycle)")
    L.append("")
    for t in note["staged_tasks"]:
        L.append(f"### {t['task']} — {t['title']} (`{t['domain_id']}`)")
        for c in t["acceptance_criteria"]:
            L.append(f"- {c}")
        L.append("")
    L.append("## Execution plan")
    L.append("")
    L.append(note["execution_plan"]["ordering"])
    L.append("")
    L.append(f"Completion: {note['execution_plan']['completion']}")
    L.append("")
    L.append("## Task 1 gate")
    L.append("")
    L.append(f"**ok = {gate['ok']}**, {gate['n_checks']} checks.")
    L.append("")
    for k, v in gate["checks"].items():
        L.append(f"- {'PASS' if v else 'FAIL'} — {k}")
    L.append("")
    return "\n".join(L)


def main() -> int:
    note = design_note()
    gate = validate_design_note(note, repo_root=str(REPO))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"design_note": note, "task1_gate": gate}
    JSON_OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    MD_OUT.write_text(_md(note, gate), encoding="utf-8")
    # re-parse guard (mounted-FS corruption defence)
    json.loads(JSON_OUT.read_text(encoding="utf-8"))
    print(json.dumps({
        "json_out": str(JSON_OUT.relative_to(REPO)),
        "md_out": str(MD_OUT.relative_to(REPO)),
        "gate_ok": gate["ok"],
        "gate_n_checks": gate["n_checks"],
        "failed": [k for k, v in gate["checks"].items() if not v],
    }, indent=1))
    return 0 if gate["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
