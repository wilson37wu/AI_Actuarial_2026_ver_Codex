#!/usr/bin/env python3
"""Phase IGUI Task 3 - evidence builder for model points + in-force ingest.

Runs the Task-3 acceptance gate + the in-process localhost self-test and writes
the evidence pack (docs/validation/PHASE_IGUI_TASK3_MODEL_POINTS.{json,md}) plus
a machine-readable self-test record (scripts/_phase_igui_task3_selftests.json).
Pure reporting - imports only stdlib + the Task-3 core module + the loader.

Run:  PYTHONPATH=.:scripts python3 scripts/build_phase_igui_task3_model_points.py
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

from par_model_v2.viewer.igui_model_points import (  # noqa: E402
    DOC_ID, DOC_VERSION, GOVERNED_HEADLINE, SCHEMA_VERSION, UI_APP_SHA256,
    MODEL_POINT_KEYS, book_scaling_disclosure, default_balance_sheet,
    default_model_points, ingest_inforce, normalize_balance_sheet,
    normalize_model_points, portfolio_to_model_inputs, reconcile_balance_sheet,
    validate_task3_gate,
)
import load_user_inputs  # noqa: E402
import run_gui  # noqa: E402

VAL_DIR = os.path.join(_REPO, "docs", "validation")


def main() -> int:
    gate = validate_task3_gate(_REPO)
    selftest_ok = (run_gui.self_test(os.path.join(
        _REPO, "outputs", "_igui_task3_selftest_model_inputs.json")) == 0)

    rows, _ = normalize_model_points(default_model_points())
    bs, _ = normalize_balance_sheet(default_balance_sheet())
    frag = portfolio_to_model_inputs(rows, bs, generated_at="1970-01-01T00:00:00+00:00")
    loader_errs = load_user_inputs.validate_portfolio_dict(frag)
    recon = reconcile_balance_sheet(bs)
    book = book_scaling_disclosure(rows)

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "doc_id": DOC_ID, "doc_version": DOC_VERSION, "generated_at": now,
        "task": "Phase IGUI Task 3 - model points + in-force ingest",
        "domain": "D2_policy_model_points",
        "governed_headline": GOVERNED_HEADLINE,
        "schema_version": SCHEMA_VERSION,
        "ui_app_sha256_frozen": UI_APP_SHA256,
        "model_point_keys": list(MODEL_POINT_KEYS),
        "capabilities": [
            "interactive add/edit/delete of PAR + GMMB model-point rows",
            "CSV/JSON in-force upload mapped to the Portfolio schema (flexible headers)",
            "balance-sheet asset rows + stated-total reconciliation (parser tolerance)",
            "DISCLOSED non-governed book-scaling preview (echoes run_model.resolve_product)",
        ],
        "new_runner_routes": ["GET /model-points", "POST /validate_portfolio",
                              "POST /save_portfolio", "POST /reconcile", "POST /ingest"],
        "loader_validator": "validate_portfolio_dict (additive, no openpyxl)",
        "loader_validation_of_defaults": loader_errs,
        "reconciliation_of_defaults": recon,
        "book_scaling_disclosure_of_defaults": book,
        "example_model_inputs_fragment": frag,
        "gate": gate,
        "self_test_ok": selftest_ok,
        "new_third_party_runtime_deps": 0,
        "outbound_network_calls": 0,
    }
    os.makedirs(VAL_DIR, exist_ok=True)
    jpath = os.path.join(VAL_DIR, "PHASE_IGUI_TASK3_MODEL_POINTS.json")
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    with open(jpath, encoding="utf-8") as fh:
        json.load(fh)  # re-parse guard

    lines = []
    lines.append("# %s (v%s)\n" % (DOC_ID, DOC_VERSION))
    lines.append("**Task:** Phase IGUI Task 3 - model points + in-force ingest  ")
    lines.append("**Domain:** D2_policy_model_points  ")
    lines.append("**Generated:** %s\n" % now)
    lines.append("## Acceptance gate\n")
    lines.append("- gate ok: **%s** (%d checks)" % (gate["ok"], gate["n_checks"]))
    lines.append("- new third-party runtime deps: **0**")
    lines.append("- outbound network calls: **0**")
    lines.append("- localhost self-test ok: **%s**" % selftest_ok)
    lines.append("- RESULTS UI (ui_app.html) byte-unchanged: **%s** (sha256 `%s`)"
                 % (gate["checks"].get("ui_app_byte_unchanged"), UI_APP_SHA256))
    lines.append("- governed headline carried bit-for-bit: **%s**\n" % GOVERNED_HEADLINE)
    lines.append("## Capabilities this cycle\n")
    for c in doc["capabilities"]:
        lines.append("- %s" % c)
    lines.append("\n## New localhost runner routes\n")
    for r in doc["new_runner_routes"]:
        lines.append("- `%s`" % r)
    lines.append("\n## Reconciliation (defaults)\n")
    lines.append("- sum of asset rows: %s" % recon["sum_of_asset_rows"])
    lines.append("- stated total: %s" % recon["stated_total_backing_asset_mv"])
    lines.append("- reconciles: **%s**" % recon["reconciles"])
    lines.append("- illiquid share: %s\n" % recon["illiquid_share"])
    lines.append("## Disclosed book-scaling preview (defaults, NON-GOVERNED)\n")
    bk = book["book_scaling"]
    lines.append("- PAR rows: %s ; GMMB rows disclosed: %s" % (book["par_rows"], book["gmmb_rows_disclosed"]))
    lines.append("- policy count total: %s" % bk["policy_count_total"])
    lines.append("- representative sum assured: %s" % bk["representative_sum_assured"])
    lines.append("- linear scale factor: %s\n" % bk["linear_scale_factor"])
    lines.append("## Gate checks\n")
    for k, v in gate["checks"].items():
        lines.append("- %s %s" % ("PASS" if v else "FAIL", k))
    mpath = os.path.join(VAL_DIR, "PHASE_IGUI_TASK3_MODEL_POINTS.md")
    with open(mpath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    with open(os.path.join(_REPO, "scripts", "_phase_igui_task3_selftests.json"),
              "w", encoding="utf-8") as fh:
        json.dump({"gate_ok": gate["ok"], "gate_checks": gate["n_checks"],
                   "self_test_ok": selftest_ok, "loader_errs": loader_errs,
                   "generated_at": now}, fh, indent=1)

    print(json.dumps({"gate_ok": gate["ok"], "gate_checks": gate["n_checks"],
                      "self_test_ok": selftest_ok, "wrote": [jpath, mpath]}, indent=1))
    return 0 if (gate["ok"] and selftest_ok and not loader_errs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
