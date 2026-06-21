#!/usr/bin/env python3
"""Phase IGUI Task 6 - evidence builder for validation surfacing + governance gating.

Runs the Task-6 acceptance gate + the in-process localhost self-test and writes the
evidence pack (docs/validation/PHASE_IGUI_TASK6_VALIDATION_GATING.{json,md}). Pure
reporting - imports only stdlib + the Task-6 core module + the loader + run_gui.

Run:  PYTHONPATH=.:scripts python3 scripts/build_phase_igui_task6_validation_gating.py
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

from par_model_v2.viewer.igui_validation_gating import (  # noqa: E402
    DOC_ID, DOC_VERSION, GOVERNED_HEADLINE, SCHEMA_VERSION, UI_APP_SHA256,
    FROZEN_COPULA_STRUCTURE, DOMAINS, DOMAIN_LABELS, aggregate_validation,
    build_run_gate, run_reproducibility_digest, validate_task6_gate,
    _clean_assembled_inputs,
)
import load_user_inputs  # noqa: E402
import run_gui  # noqa: E402

VAL_DIR = os.path.join(_REPO, "docs", "validation")


def main() -> int:
    gate = validate_task6_gate(_REPO)
    selftest_ok = (run_gui.self_test(os.path.join(
        _REPO, "outputs", "_igui_task6_selftest_model_inputs.json")) == 0)

    clean = _clean_assembled_inputs()
    v_clean = aggregate_validation(clean, load_user_inputs)
    gate_clean = build_run_gate(clean, v_clean, now="1970-01-01T00:00:00+00:00")

    incomplete = json.loads(json.dumps(clean))
    incomplete.pop("esg", None)
    v_bad = aggregate_validation(incomplete, load_user_inputs)
    gate_bad = build_run_gate(incomplete, v_bad, now="1970-01-01T00:00:00+00:00")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "doc_id": DOC_ID, "doc_version": DOC_VERSION, "generated_at": now,
        "task": "Phase IGUI Task 6 - validation surfacing + governance gating before run",
        "domain": "D5_validation_gating",
        "governed_headline": GOVERNED_HEADLINE,
        "schema_version": SCHEMA_VERSION,
        "ui_app_sha256_frozen": UI_APP_SHA256,
        "frozen_copula_structure": FROZEN_COPULA_STRUCTURE,
        "domains_gated": [{"id": d, "label": DOMAIN_LABELS[d]} for d in DOMAINS],
        "capabilities": [
            "AGGREGATE loader-side validator scripts/load_user_inputs.validate_assembled_inputs: "
            "routes the WHOLE assembled model_inputs.json through every per-domain dict "
            "validator (run controls, model points, assumptions, ESG) and returns a "
            "per-domain {present, ok, errors} summary + overall verdict; a domain that "
            "has not been saved is reported missing so an INCOMPLETE set can never clear.",
            "VALIDATION SURFACING: a self-contained gate page (GET /run-gate) renders "
            "per-domain PASS/FAIL with every fail-loud loader issue; it POSTs /preflight "
            "(read-only aggregate validation) on load.",
            "GOVERNANCE GATING: the Run action is BLOCKED until ALL domains are present "
            "and clean; POST /run records a governance run-gate (ChangeRecord-style "
            "provenance: decision CLEARED/BLOCKED, per-domain summary, blocking issues, "
            "governed headline + read-only frozen copula structure) plus a deterministic "
            "run-level reproducibility digest into model_inputs.json. A BLOCKED gate "
            "writes nothing.",
            "Records readiness only; model execution + results handoff are Task 7. The "
            "Phase 30 stop-rule is honoured (frozen structure echoed read-only); the "
            "MR-016/MR-017 owner decision is not pre-empted.",
        ],
        "new_runner_routes": ["GET /run-gate", "POST /preflight", "POST /run"],
        "loader_validator": "validate_assembled_inputs (additive, no openpyxl)",
        "example_clean_gate": gate_clean,
        "example_blocked_gate": gate_bad,
        "clean_inputs_digest": run_reproducibility_digest(clean),
        "gate": gate,
        "self_test_ok": selftest_ok,
        "new_third_party_runtime_deps": 0,
        "outbound_network_calls": 0,
    }
    os.makedirs(VAL_DIR, exist_ok=True)
    jpath = os.path.join(VAL_DIR, "PHASE_IGUI_TASK6_VALIDATION_GATING.json")
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    with open(jpath, encoding="utf-8") as fh:
        json.load(fh)  # re-parse guard

    lines = []
    lines.append("# %s (v%s)\n" % (DOC_ID, DOC_VERSION))
    lines.append("**Task:** Phase IGUI Task 6 - validation surfacing + governance gating before run  ")
    lines.append("**Domain:** D5_validation_gating  ")
    lines.append("**Generated:** %s\n" % now)
    lines.append("## Acceptance gate\n")
    lines.append("- gate ok: **%s** (%d/%d checks)" % (gate["ok"], gate["n_pass"], gate["n_checks"]))
    lines.append("- new third-party runtime deps: **0**")
    lines.append("- outbound network calls: **0**")
    lines.append("- localhost self-test ok: **%s**" % selftest_ok)
    lines.append("- RESULTS UI (ui_app.html) byte-unchanged: **%s** (sha256 `%s`)"
                 % (gate["checks"].get("ui_app_byte_unchanged"), UI_APP_SHA256))
    lines.append("- governed headline carried bit-for-bit: **%s**\n" % GOVERNED_HEADLINE)
    lines.append("## What the gate does\n")
    lines.append("The Run action is **BLOCKED** until the assembled `model_inputs.json` is "
                 "present and clean across **all** input domains:\n")
    for d in DOMAINS:
        lines.append("- **%s** (`%s`)" % (DOMAIN_LABELS[d], d))
    lines.append("\nValidation is surfaced through the REAL loader "
                 "(`validate_assembled_inputs`), so the GUI shows exactly what would be "
                 "rejected. On clearing, a governance run-gate + a run-level reproducibility "
                 "digest are recorded before any run. Execution + results handoff are Task 7.\n")
    lines.append("## Stop-rule (Phase 30) + owner-gating\n")
    lines.append("- dependence copula structure echoed read-only as **`%s`** (never altered here)" % FROZEN_COPULA_STRUCTURE)
    lines.append("- MR-016/MR-017 dependence decision remains entirely with the owner\n")
    lines.append("## Example cleared run-gate (deterministic digest)\n")
    lines.append("```json")
    lines.append(json.dumps({k: gate_clean[k] for k in
                             ("decision", "run_permitted", "reproducibility_digest",
                              "frozen_copula_structure", "governed_headline",
                              "n_blocking_issues")}, indent=1))
    lines.append("```\n")
    lines.append("## New localhost runner routes\n")
    for r in ["GET /run-gate", "POST /preflight", "POST /run"]:
        lines.append("- `%s`" % r)
    lines.append("\n## Gate checks\n")
    for k, v in gate["checks"].items():
        lines.append("- %s %s" % ("PASS" if v else "FAIL", k))
    lines.append("")
    mpath = os.path.join(VAL_DIR, "PHASE_IGUI_TASK6_VALIDATION_GATING.md")
    with open(mpath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(json.dumps({"gate_ok": gate["ok"], "gate_checks": gate["n_checks"],
                      "self_test_ok": selftest_ok, "json": jpath, "md": mpath}, indent=1))
    return 0 if (gate["ok"] and selftest_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
