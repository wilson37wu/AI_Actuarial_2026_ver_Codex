#!/usr/bin/env python3
"""Phase IGUI Task 7 - evidence builder for end-to-end run + results handoff.

Runs the Task-7 acceptance gate (incl. a real end-to-end SMOKE run) + the
in-process localhost self-test and writes the evidence pack
(docs/validation/PHASE_IGUI_TASK7_RUN_EXECUTION.{json,md}). Pure reporting -
imports stdlib + the Task-7 core module + the Task-6 gating module + run_gui;
the model engine runs out of process behind scripts/run_model.py.

Run:  PYTHONPATH=.:scripts python3 scripts/build_phase_igui_task7_run_execution.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from par_model_v2.viewer.igui_run_execution import (  # noqa: E402
    DOC_ID, DOC_VERSION, AGG_REPORT_NAME, SUMMARY_NAME, SMOKE_OVERRIDES,
    GOVERNED_HEADLINE, SCHEMA_VERSION, UI_APP_SHA256, FROZEN_COPULA_STRUCTURE,
    execute_run, validate_task7_gate, _clean_gated_inputs,
)
import run_gui  # noqa: E402

VAL_DIR = os.path.join(_REPO, "docs", "validation")
NEW_ROUTES = ["GET /run-execution", "POST /execute"]


def main() -> int:
    gate = validate_task7_gate(_REPO, run_live=True)
    selftest_ok = (run_gui.self_test(os.path.join(
        _REPO, "outputs", "_igui_task7_selftest_model_inputs.json")) == 0)

    # one real end-to-end smoke run for the evidence pack
    tmp = tempfile.mkdtemp(prefix="igui7_evidence_")
    inp = os.path.join(tmp, "model_inputs.json")
    with open(inp, "w", encoding="utf-8") as fh:
        json.dump(_clean_gated_inputs(), fh, indent=1)
    res = execute_run(inp, os.path.join(tmp, "out"), smoke=True, repo_root=_REPO)
    headline = (res.get("headline") or {}) if res.get("ok") else {}

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "doc_id": DOC_ID, "doc_version": DOC_VERSION, "generated_at": now,
        "task": "Phase IGUI Task 7 - end-to-end run + results handoff (Phase IGUI MVP)",
        "domain": "D6_run_and_handoff",
        "governed_headline": GOVERNED_HEADLINE,
        "schema_version": SCHEMA_VERSION,
        "ui_app_sha256_frozen": UI_APP_SHA256,
        "frozen_copula_structure": FROZEN_COPULA_STRUCTURE,
        "end_to_end_flow": (
            "gated model_inputs.json (run_gate CLEARED, Task 6) -> scripts/run_model.py "
            "-> docs/validation/RUN_MODEL_AGGREGATION_REPORT.json + RUN_MODEL_SUMMARY.json "
            "-> offline RESULTS UI (ui_app.html) user_run contract"),
        "capabilities": [
            "GATE-GUARDED DRIVE: execute_run REFUSES to spawn the model unless the "
            "assembled model_inputs.json carries a Task-6 run_gate with decision CLEARED / "
            "run_permitted True AND the gate's reproducibility digest re-verifies against "
            "the live inputs (a gate lifted off a different/altered input set is rejected).",
            "OUT-OF-PROCESS ENGINE: drives scripts/run_model.py as a child process so the "
            "GUI/runner layer stays standard-library only (no numpy/scipy import); captures "
            "stdout/stderr as progress and surfaces run errors structurally.",
            "DIGEST CARRIED INTO OUTPUT PROVENANCE: a run_gate_provenance block (Task-6 "
            "reproducibility digest + decision + governed headline + frozen structure) is "
            "stamped onto both captured RUN_MODEL artifacts, so every result is traceable "
            "to the exact gated input set that authorised it.",
            "RESULTS HANDOFF: build_results_handoff shapes the SAME user_run contract the "
            "offline RESULTS UI already consumes (build_ui_data._build_user_run reads "
            "RUN_MODEL_SUMMARY.json + RUN_MODEL_AGGREGATION_REPORT.json verbatim); the "
            "zero-install ui_app.html is byte-unchanged.",
            "Self-contained run page (GET /run-execution): Run button DISABLED until the "
            "gate clears; live progress/errors from POST /execute; headline read-outs after "
            "a run; governed headline + frozen copula structure shown read-only. The "
            "MR-016/MR-017 owner decision is not pre-empted; NO model parameter change.",
        ],
        "new_runner_routes": NEW_ROUTES,
        "smoke_overrides": SMOKE_OVERRIDES,
        "live_smoke_run": {
            "ok": bool(res.get("ok")),
            "stage": res.get("stage"),
            "nested_scr": headline.get("nested_scr"),
            "copula_selected": headline.get("copula_selected"),
            "verdict": res.get("verdict"),
            "reproducibility_digest": res.get("reproducibility_digest"),
            "artifacts": [SUMMARY_NAME, AGG_REPORT_NAME],
            "disclosure": "smoke run - fast diagnostic, NOT a governed capital figure",
        },
        "gate": gate,
        "self_test_ok": selftest_ok,
        "new_third_party_runtime_deps": 0,
        "outbound_network_calls": 0,
    }
    os.makedirs(VAL_DIR, exist_ok=True)
    jpath = os.path.join(VAL_DIR, "PHASE_IGUI_TASK7_RUN_EXECUTION.json")
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=str)
    with open(jpath, encoding="utf-8") as fh:
        json.load(fh)  # re-parse guard

    lines = []
    lines.append("# %s (v%s)\n" % (DOC_ID, DOC_VERSION))
    lines.append("**Task:** Phase IGUI Task 7 - end-to-end run + results handoff (Phase IGUI MVP)  ")
    lines.append("**Domain:** D6_run_and_handoff  ")
    lines.append("**Generated:** %s\n" % now)
    lines.append("## Acceptance gate\n")
    lines.append("- gate ok: **%s** (%d/%d checks)" % (gate["ok"], gate["n_pass"], gate["n_checks"]))
    lines.append("- new third-party runtime deps: **0** (engine runs behind the run_model.py subprocess)")
    lines.append("- outbound network calls: **0**")
    lines.append("- localhost self-test ok: **%s**" % selftest_ok)
    lines.append("- RESULTS UI (ui_app.html) byte-unchanged: **%s** (sha256 `%s`)"
                 % (gate["checks"].get("ui_app_byte_unchanged"), UI_APP_SHA256))
    lines.append("- governed headline carried bit-for-bit: **%s**\n" % GOVERNED_HEADLINE)
    lines.append("## End-to-end flow\n")
    lines.append("```\n%s\n```\n" % doc["end_to_end_flow"])
    lines.append("## Live smoke run (this build)\n")
    lines.append("- ok: **%s** (stage `%s`)" % (res.get("ok"), res.get("stage")))
    lines.append("- nested SCR (smoke): `%s`" % headline.get("nested_scr"))
    lines.append("- selected copula (smoke): `%s`" % headline.get("copula_selected"))
    lines.append("- reproducibility digest carried into output: `%s`" % res.get("reproducibility_digest"))
    lines.append("- DISCLOSURE: a smoke run is a fast diagnostic, **not** a governed capital figure\n")
    lines.append("## Gate-guard\n")
    lines.append("A run is **refused** (nothing spawned) unless the Task-6 run gate is "
                 "**CLEARED** and its reproducibility digest re-verifies against the live "
                 "inputs. A missing / blocked / tampered gate writes no artifact.\n")
    lines.append("## Stop-rule (Phase 30) + owner-gating\n")
    lines.append("- dependence copula structure echoed read-only as **`%s`** (never altered here)" % FROZEN_COPULA_STRUCTURE)
    lines.append("- MR-016/MR-017 dependence decision remains entirely with the owner\n")
    lines.append("## New localhost runner routes\n")
    for r in NEW_ROUTES:
        lines.append("- `%s`" % r)
    lines.append("\n## Gate checks\n")
    for k, v in gate["checks"].items():
        lines.append("- %s %s" % ("PASS" if v else "FAIL", k))
    lines.append("")
    mpath = os.path.join(VAL_DIR, "PHASE_IGUI_TASK7_RUN_EXECUTION.md")
    with open(mpath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(json.dumps({"gate_ok": gate["ok"], "gate_checks": gate["n_checks"],
                      "live_run_ok": bool(res.get("ok")), "self_test_ok": selftest_ok,
                      "json": jpath, "md": mpath}, indent=1))
    return 0 if (gate["ok"] and selftest_ok and res.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
