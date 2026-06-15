#!/usr/bin/env python3
"""Phase IGUI Task 5 - evidence builder for the ESG / economic-scenario input domain.

Runs the Task-5 acceptance gate + the in-process localhost self-test and writes
the evidence pack (docs/validation/PHASE_IGUI_TASK5_ESG.{json,md}) plus a
machine-readable self-test record (scripts/_phase_igui_task5_selftests.json).
Pure reporting - imports only stdlib + the Task-5 core module + the loader.

Run:  PYTHONPATH=.:scripts python3 scripts/build_phase_igui_task5_esg.py
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

from par_model_v2.viewer.igui_esg import (  # noqa: E402
    DOC_ID, DOC_VERSION, GOVERNED_HEADLINE, GOVERNED_ESG_FROZEN, FROZEN_COPULA_STRUCTURE,
    SCHEMA_VERSION, UI_APP_SHA256, GROUP_ORDER, esg_to_model_inputs, default_esg,
    normalize_esg, validate_task5_gate,
)
import load_user_inputs  # noqa: E402
import run_gui  # noqa: E402

VAL_DIR = os.path.join(_REPO, "docs", "validation")


def main() -> int:
    gate = validate_task5_gate(_REPO)
    selftest_ok = (run_gui.self_test(os.path.join(
        _REPO, "outputs", "_igui_task5_selftest_model_inputs.json")) == 0)

    typed, _ = normalize_esg(default_esg())
    frag = esg_to_model_inputs(typed, generated_at="1970-01-01T00:00:00+00:00")
    loader_errs = load_user_inputs.validate_esg_dict(frag)

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "doc_id": DOC_ID, "doc_version": DOC_VERSION, "generated_at": now,
        "task": "Phase IGUI Task 5 - ESG / economic scenarios (stop-rule-bounded, owner-gated)",
        "domain": "D4_esg_economic",
        "governed_headline": GOVERNED_HEADLINE,
        "schema_version": SCHEMA_VERSION,
        "ui_app_sha256_frozen": UI_APP_SHA256,
        "frozen_copula_structure": FROZEN_COPULA_STRUCTURE,
        "esg_groups": list(GROUP_ORDER),
        "governed_esg_readback": dict(GOVERNED_ESG_FROZEN),
        "capabilities": [
            "ESG / economic-scenario calibration surfaced as a READ-ONLY provenance echo "
            "(G2++/HW short-rate, equity GBM, credit-spread & liquidity-premium processes, "
            "and the FROZEN dependence structure: single-df t-copula df 2.9451 + grouped-t "
            "block dfs 37.866 / 8.506)",
            "STOP-RULE GUARD (Phase 30): the dependence copula structure is pinned to "
            "'single_t_grouped_FROZEN'; the loader rejects any payload naming a different "
            "structure (in the echo or smuggled as a top-level key), so the GUI can never "
            "introduce a new copula-structure candidate; MR-016/MR-017 not pre-empted",
            "settable inputs are bounded, owner-gated PROVENANCE/metadata only (market-data "
            "valuation date & sources, scenario-set label, documented scenario count, and "
            "calibration TARGETS: 10y rate / equity vol / credit spread); none feed the "
            "frozen engine",
            "loader-side validate_esg_dict round-trip (additive, no openpyxl)",
        ],
        "new_runner_routes": ["GET /esg", "POST /validate_esg", "POST /save_esg"],
        "loader_validator": "validate_esg_dict (additive, no openpyxl)",
        "loader_validation_of_defaults": loader_errs,
        "example_model_inputs_fragment": frag,
        "gate": gate,
        "self_test_ok": selftest_ok,
        "new_third_party_runtime_deps": 0,
        "outbound_network_calls": 0,
    }
    os.makedirs(VAL_DIR, exist_ok=True)
    jpath = os.path.join(VAL_DIR, "PHASE_IGUI_TASK5_ESG.json")
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    with open(jpath, encoding="utf-8") as fh:
        json.load(fh)  # re-parse guard

    lines = []
    lines.append("# %s (v%s)\n" % (DOC_ID, DOC_VERSION))
    lines.append("**Task:** Phase IGUI Task 5 - ESG / economic scenarios (stop-rule-bounded, owner-gated)  ")
    lines.append("**Domain:** D4_esg_economic  ")
    lines.append("**Generated:** %s\n" % now)
    lines.append("## Acceptance gate\n")
    lines.append("- gate ok: **%s** (%d checks)" % (gate["ok"], gate["n_checks"]))
    lines.append("- new third-party runtime deps: **0**")
    lines.append("- outbound network calls: **0**")
    lines.append("- localhost self-test ok: **%s**" % selftest_ok)
    lines.append("- RESULTS UI (ui_app.html) byte-unchanged: **%s** (sha256 `%s`)"
                 % (gate["checks"].get("ui_app_byte_unchanged"), UI_APP_SHA256))
    lines.append("- governed headline carried bit-for-bit: **%s**\n" % GOVERNED_HEADLINE)
    lines.append("## Stop-rule (Phase 30) + owner-gating (read-only echo)\n")
    lines.append("- dependence copula structure pinned to **`%s`** (loader rejects any other)" % FROZEN_COPULA_STRUCTURE)
    for k, v in GOVERNED_ESG_FROZEN.items():
        lines.append("- `%s` = %s (read-only echo; override rejected by loader)" % (k, v))
    lines.append("\n## Settable provenance groups surfaced\n")
    for g in GROUP_ORDER:
        lines.append("- %s" % g)
    lines.append("\n## New localhost runner routes\n")
    for r in doc["new_runner_routes"]:
        lines.append("- `%s`" % r)
    lines.append("\n## Gate checks\n")
    for k, v in gate["checks"].items():
        lines.append("- %s %s" % ("PASS" if v else "FAIL", k))
    mpath = os.path.join(VAL_DIR, "PHASE_IGUI_TASK5_ESG.md")
    with open(mpath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    with open(os.path.join(_REPO, "scripts", "_phase_igui_task5_selftests.json"),
              "w", encoding="utf-8") as fh:
        json.dump({"gate_ok": gate["ok"], "gate_checks": gate["n_checks"],
                   "self_test_ok": selftest_ok, "loader_errs": loader_errs,
                   "generated_at": now}, fh, indent=1)

    print(json.dumps({"gate_ok": gate["ok"], "gate_checks": gate["n_checks"],
                      "self_test_ok": selftest_ok, "wrote": [jpath, mpath]}, indent=1))
    return 0 if (gate["ok"] and selftest_ok and not loader_errs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
