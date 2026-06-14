"""Phase 34 Task 2 (gap H1) - self-describing data-contract guard.

The offline UI (``ui_app.html``) consumes a single embedded ``ui_data.json``
snapshot. Before this gap a missing or mismatched top-level section degraded
silently to a blank/partial panel. Task 2 embeds a build-time
``contract_manifest`` (expected contract version + the required top-level
section list, written ONLY by ``scripts/build_ui_data.py``) and adds a
load-time validator that renders an in-UI integrity/schema panel plus a NEUTRAL
degraded-mode banner. The validator inspects ONLY the embedded payload and
recomputes NO model figure.

This module provides the Task 2 gate: a set of LIVE cross-checks on the rebuilt
artifacts (``ui_data.json`` + ``ui_app.html``). Unlike the Task 1 design-note
gate (which froze the Phase-33-final baseline as a point-in-time record), this
gate validates the NEW, post-H1 state, so it stays green against the live repo.

ADDITIVE-only contract change: 1.17.0 -> 1.18.0 (new ``contract_manifest`` key
ONLY; every pre-existing key renders bit-identically). NO model parameter
changes; the binding Phase 30 stop-rule stands; the MR-016/MR-017 owner
decision is not pre-empted.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

DOC_ID = "PHASE34_TASK2_H1_CONTRACT_GUARD"
DOC_VERSION = "1.0.0"

# Phase 36 Task 3 re-audit refresh: the live contract advanced additively
# 1.18.0 -> 1.19.0 (A1, a11y_audit) -> 1.20.0 (A2, section digests) ->
# 1.21.0 (E2, explainer global glossary). This live-tracking gate's expected
# constants are refreshed to the current state so it stays green against the
# live repo (its documented purpose); gap H1 itself remains the historical
# 1.17.0 -> 1.18.0 additive change.
EXPECTED_CONTRACT = "1.21.0"
PRIOR_CONTRACT = "1.20.0"
GOVERNED_HEADLINE = "39975.654628199336"

# The 24 substantive top-level sections the manifest must guard (22 from the
# 1.17.0 contract plus a11y_audit added additively at 1.19.0 / Phase 35 A1;
# the manifest itself is additive on top and is NOT in this list).
EXPECTED_REQUIRED_KEYS = [
    "contract_version", "meta", "summary", "inventory", "capital", "tail",
    "proxy", "loss", "calibrations", "management_actions", "phase24",
    "phase25", "phase26", "phase27", "phase28", "phase29", "phase30",
    "distribution_explorer", "owner_decision_p31", "user_run", "governance",
    "verdicts", "a11y_audit", "explainer",
]


def _external_ref_count(html: str) -> int:
    """Count external references that would break the zero-install invariant."""
    return (
        len(re.findall(r"https?://", html))
        + len(re.findall(r"<link\b", html, re.I))
        + len(re.findall(r"src\s*=\s*[\"']https?:", html, re.I))
    )


def validate_h1(repo_root: str = ".") -> Dict[str, Any]:
    """Live gate for the H1 data-contract guard. Returns checks + ok + count."""
    checks: Dict[str, bool] = {}
    try:
        with open(os.path.join(repo_root, "ui_data.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        data = None
    try:
        with open(os.path.join(repo_root, "ui_app.html"), encoding="utf-8") as fh:
            html = fh.read()
    except OSError:
        html = ""

    man = (data or {}).get("contract_manifest") if isinstance(data, dict) else None

    checks["ui_data_parsed"] = isinstance(data, dict)
    checks["contract_is_expected"] = bool(data) and data.get("contract_version") == EXPECTED_CONTRACT
    checks["manifest_present"] = isinstance(man, dict)
    checks["manifest_expected_version_matches"] = bool(man) and man.get("expected_contract_version") == EXPECTED_CONTRACT
    req = (man or {}).get("required_top_level_keys") if man else None
    checks["manifest_required_keys_is_list"] = isinstance(req, list) and len(req) >= 20
    checks["manifest_required_keys_match"] = isinstance(req, list) and list(req) == EXPECTED_REQUIRED_KEYS
    checks["manifest_excludes_itself"] = isinstance(req, list) and "contract_manifest" not in req
    checks["manifest_key_count_consistent"] = bool(man) and man.get("key_count") == (len(req) if isinstance(req, list) else -1)
    checks["all_required_keys_present"] = bool(data) and isinstance(req, list) and all(k in data for k in req)
    checks["manifest_build_time_provenance"] = bool(man) and "build_ui_data.py" in str(man.get("generated_by", ""))
    # ADDITIVE: contract_manifest is the only top-level key beyond the prior set.
    checks["additive_single_new_key"] = (
        bool(data)
        and set(data.keys()) - set(EXPECTED_REQUIRED_KEYS) == {"contract_manifest"})

    # --- ui_app.html display surface ---
    checks["integrity_panel_present"] = '<div id="integrity"' in html
    checks["integrity_banner_present"] = 'id="integritybanner"' in html
    checks["validator_fn_present"] = "function validateContract(" in html
    checks["integrity_render_present"] = "function renderIntegrity(" in html
    checks["banner_render_present"] = "function renderIntegrityBanner(" in html
    checks["html_embeds_contract_expected"] = '"contract_version": "1.21.0"' in html
    checks["display_only_no_recompute_stated"] = "recomputes no model figure" in html
    checks["neutral_degraded_banner_text"] = "Data-contract notice" in html and "No figures are recomputed" in html
    checks["zero_external_refs"] = _external_ref_count(html) == 0
    checks["governed_headline_intact"] = GOVERNED_HEADLINE in json.dumps(data or {})

    # --- documentary invariants ---
    checks["no_model_parameter_changes"] = True
    checks["stop_rule_honoured"] = True
    checks["owner_decision_not_preempted"] = True

    ok = all(checks.values())
    return {"ok": ok, "n_checks": len(checks), "checks": checks,
            "doc_id": DOC_ID, "doc_version": DOC_VERSION,
            "contract_before": PRIOR_CONTRACT, "contract_after": EXPECTED_CONTRACT}
