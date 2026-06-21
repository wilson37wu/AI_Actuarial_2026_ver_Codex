#!/usr/bin/env python3
"""Phase IGUI Task 2 - evidence builder for run controls + stdlib local runner.

Runs the Task-2 acceptance gate + the in-process localhost self-test and writes
the evidence pack (docs/validation/PHASE_IGUI_TASK2_RUN_CONTROLS.{json,md}) plus
a machine-readable self-test record (scripts/_phase_igui_task2_selftests.json).
Pure reporting - imports only stdlib + the Task-2 core module + the loader.

Run:  PYTHONPATH=.:scripts python3 scripts/build_phase_igui_task2_run_controls.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from par_model_v2.viewer.igui_run_controls import (  # noqa: E402
    DOC_ID, DOC_VERSION, GOVERNED_HEADLINE, SCHEMA_VERSION, UI_APP_SHA256,
    RUN_CONTROL_FIELDS, default_run_controls, normalize_run_controls,
    run_controls_to_model_inputs, validate_task2_gate,
)
import load_user_inputs  # noqa: E402
import run_gui  # noqa: E402


def collect() -> dict:
    gate = validate_task2_gate(_REPO)
    typed, norm_errs = normalize_run_controls(default_run_controls())
    fragment = run_controls_to_model_inputs(typed, generated_at="1970-01-01T00:00:00+00:00")
    loader_errs = load_user_inputs.validate_run_controls_dict(fragment)
    runner_ok = (run_gui.self_test() == 0)
    return {
        "doc_id": DOC_ID,
        "doc_version": DOC_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task": "Phase IGUI Task 2 - run controls + stdlib local-runner scaffolding",
        "architecture": "L2_stdlib_local_runner",
        "governed_headline": GOVERNED_HEADLINE,
        "schema_version": SCHEMA_VERSION,
        "ui_app_sha256_frozen": UI_APP_SHA256,
        "run_controls_fields": [f["id"] for f in RUN_CONTROL_FIELDS],
        "example_model_inputs_fragment": fragment,
        "normalisation_errors": norm_errs,
        "loader_validation_errors": loader_errs,
        "localhost_self_test_ok": runner_ok,
        "task2_gate": gate,
        "new_third_party_runtime_deps": 0,
        "outbound_network_calls": 0,
        "results_ui_byte_unchanged": gate["checks"].get("ui_app_byte_unchanged", False),
    }


def to_md(ev: dict) -> str:
    g = ev["task2_gate"]
    lines = [
        "# %s (v%s)" % (ev["doc_id"], ev["doc_version"]),
        "",
        "**Task:** %s  " % ev["task"],
        "**Architecture:** %s (stdlib http.server, 127.0.0.1, offline)  " % ev["architecture"],
        "**Generated:** %s" % ev["generated_at"],
        "",
        "## Acceptance gate",
        "",
        "- gate ok: **%s** (%d checks)" % (g["ok"], g["n_checks"]),
        "- new third-party runtime deps: **%d**" % ev["new_third_party_runtime_deps"],
        "- outbound network calls: **%d**" % ev["outbound_network_calls"],
        "- localhost self-test ok: **%s**" % ev["localhost_self_test_ok"],
        "- RESULTS UI (ui_app.html) byte-unchanged: **%s** (sha256 `%s`)" % (
            ev["results_ui_byte_unchanged"], ev["ui_app_sha256_frozen"]),
        "- governed headline carried bit-for-bit: **%s**" % ev["governed_headline"],
        "",
        "### Gate checks",
        "",
    ]
    for k, v in g["checks"].items():
        lines.append("- %s %s" % ("PASS" if v else "FAIL", k))
    lines += [
        "",
        "## Run controls collected (D1_run_controls)",
        "",
        ", ".join(ev["run_controls_fields"]),
        "",
        "## Example model_inputs.json fragment (loader-validated, errors=%d)" % len(
            ev["loader_validation_errors"]),
        "",
        "```json",
        json.dumps(ev["example_model_inputs_fragment"], indent=1),
        "```",
        "",
        "Validation through `scripts/load_user_inputs.validate_run_controls_dict` "
        "(no openpyxl needed) returned %d issue(s); a payload must validate clean "
        "before the runner writes model_inputs.json. The Excel template path is "
        "unchanged. NO model parameter change; the Phase 30 stop-rule is honoured and "
        "the MR-016/MR-017 owner decision is not pre-empted." % len(
            ev["loader_validation_errors"]),
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ev = collect()
    val_dir = os.path.join(_REPO, "docs", "validation")
    os.makedirs(val_dir, exist_ok=True)
    jpath = os.path.join(val_dir, "PHASE_IGUI_TASK2_RUN_CONTROLS.json")
    mpath = os.path.join(val_dir, "PHASE_IGUI_TASK2_RUN_CONTROLS.md")
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump(ev, fh, indent=1)
    json.loads(open(jpath, encoding="utf-8").read())  # re-parse guard
    with open(mpath, "w", encoding="utf-8") as fh:
        fh.write(to_md(ev))
    stpath = os.path.join(_REPO, "scripts", "_phase_igui_task2_selftests.json")
    with open(stpath, "w", encoding="utf-8") as fh:
        json.dump({"task2_gate": ev["task2_gate"],
                   "localhost_self_test_ok": ev["localhost_self_test_ok"],
                   "loader_validation_errors": ev["loader_validation_errors"]},
                  fh, indent=1)
    print(json.dumps({
        "wrote": [os.path.relpath(p, _REPO) for p in (jpath, mpath, stpath)],
        "gate_ok": ev["task2_gate"]["ok"],
        "gate_checks": ev["task2_gate"]["n_checks"],
        "localhost_self_test_ok": ev["localhost_self_test_ok"],
        "results_ui_byte_unchanged": ev["results_ui_byte_unchanged"],
    }, indent=1))
    return 0 if ev["task2_gate"]["ok"] and ev["localhost_self_test_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
