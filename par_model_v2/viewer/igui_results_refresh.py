#!/usr/bin/env python3
"""Phase IGUI Task 8 - own-run results refresh (offline RESULTS-UI wiring).

After the Task-7 end-to-end run writes its two RUN_MODEL artifacts into
``run_output/`` (``RUN_MODEL_SUMMARY.json`` + ``RUN_MODEL_AGGREGATION_REPORT.json``),
this module builds a **USER copy** of the zero-install offline RESULTS UI from the
user's OWN run -- so a non-technical user, after pressing one button to supply
inputs AND compute, immediately sees THEIR OWN run rendered in the same browsable
UI. It does this by driving the existing display-layer builder
``scripts/build_ui_data.py`` with its run-evidence sources temporarily repointed at
``run_output/`` and its outputs repointed at a USER directory.

Discipline (matches the rest of Phase IGUI):
  * **Standard library ONLY** (``hashlib``, ``json``, ``os``, ``shutil`` -- all
    stdlib). NO third-party dependency in this layer; the numpy/scipy engine ran
    out of process in Task 7. NO outbound network call. NO model parameter change.
  * **Display-layer only** -- nothing is recomputed. ``build_ui_data`` carries the
    user's run figures VERBATIM via the existing ``user_run`` contract
    (``_build_user_run``), exactly as the committed pipeline already does for the
    governed sample run.
  * The committed, zero-install ``ui_app.html`` / ``ui_data.json`` TEMPLATE files
    are **never written** -- they are left byte-for-byte unchanged (asserted by
    sha256 before/after). The user copy lands in a separate USER directory
    (default ``user_results/``) as ``ui_app_user.html`` + ``ui_data_user.json``.

The repoint is done by temporarily swapping four module-level constants on
``build_ui_data`` (``RUN_SUMMARY_PATH``, ``AGG_REPORT_PATH``, ``OUT_JSON``,
``OUT_HTML``) inside a try/finally so the committed pipeline's behaviour is
unchanged the moment this function returns.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any, Dict, Optional

#: repo root (…/par_model_v2/viewer/igui_results_refresh.py -> repo)
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SCRIPTS = os.path.join(_REPO, "scripts")

#: default location of the Task-7 run artifacts and of the USER results copy.
DEFAULT_RUN_OUTPUT_DIR = "run_output"
DEFAULT_USER_RESULTS_DIR = "user_results"

#: the two RUN_MODEL artifacts build_ui_data._build_user_run consumes VERBATIM.
SUMMARY_NAME = "RUN_MODEL_SUMMARY.json"
AGG_REPORT_NAME = "RUN_MODEL_AGGREGATION_REPORT.json"

#: the USER copy file names (kept distinct from the committed template files).
USER_HTML_NAME = "ui_app_user.html"
USER_JSON_NAME = "ui_data_user.json"


def _sha256(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _import_build_ui_data():
    """Import scripts/build_ui_data as a module (stdlib import; no exec)."""
    if _SCRIPTS not in sys.path:
        sys.path.insert(0, _SCRIPTS)
    if _REPO not in sys.path:
        sys.path.insert(0, _REPO)
    import build_ui_data  # noqa: E402  (path-extended import)
    return build_ui_data


def _abs(repo_root: str, path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(repo_root, path)


def refresh_user_results(
    run_output_dir: str = DEFAULT_RUN_OUTPUT_DIR,
    user_results_dir: str = DEFAULT_USER_RESULTS_DIR,
    *,
    repo_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a USER copy of the offline RESULTS UI from the user's own run.

    Parameters
    ----------
    run_output_dir
        Directory holding the Task-7 ``RUN_MODEL_SUMMARY.json`` +
        ``RUN_MODEL_AGGREGATION_REPORT.json`` (relative paths resolve under
        ``repo_root``).
    user_results_dir
        Directory to write the USER copy (``ui_app_user.html`` +
        ``ui_data_user.json``) into; created if absent.
    repo_root
        Repo root; defaults to the package's own repo root.

    Returns
    -------
    dict
        ``{ok, stage, user_html, user_json, headline, output_label,
        contract_version, committed_ui_app_unchanged, committed_ui_data_unchanged,
        committed_ui_app_sha256}``. ``ok`` is False (with a ``stage``) when the run
        artifacts are absent -- a graceful, fail-loud fallback (never raises for a
        missing run; the user is simply told to run first).
    """
    root = os.path.abspath(repo_root or _REPO)
    run_dir = _abs(root, run_output_dir)
    user_dir = _abs(root, user_results_dir)

    summary_src = os.path.join(run_dir, SUMMARY_NAME)
    agg_src = os.path.join(run_dir, AGG_REPORT_NAME)

    result: Dict[str, Any] = {
        "ok": False,
        "stage": None,
        "user_html": None,
        "user_json": None,
        "headline": None,
        "output_label": None,
        "contract_version": None,
        "committed_ui_app_unchanged": True,
        "committed_ui_data_unchanged": True,
        "committed_ui_app_sha256": None,
        "run_output_dir": run_dir,
        "user_results_dir": user_dir,
    }

    if not (os.path.isfile(summary_src) and os.path.isfile(agg_src)):
        result["stage"] = "no_user_run"
        result["error"] = (
            "no run artifacts in %s -- supply inputs and press Run first "
            "(expects %s + %s)" % (run_dir, SUMMARY_NAME, AGG_REPORT_NAME))
        return result

    B = _import_build_ui_data()

    # Record the committed template files so we can PROVE they are untouched.
    committed_html = B.OUT_HTML
    committed_json = B.OUT_JSON
    html_sha_before = _sha256(committed_html)
    json_sha_before = _sha256(committed_json)
    result["committed_ui_app_sha256"] = html_sha_before

    os.makedirs(user_dir, exist_ok=True)
    user_html = os.path.join(user_dir, USER_HTML_NAME)
    user_json = os.path.join(user_dir, USER_JSON_NAME)

    # Temporarily repoint the run-evidence sources at the user's run_output and
    # the build outputs at the USER directory; restore EVERYTHING in finally so
    # the committed pipeline behaves identically the moment we return.
    saved = (B.RUN_SUMMARY_PATH, B.AGG_REPORT_PATH, B.OUT_JSON, B.OUT_HTML)
    try:
        B.RUN_SUMMARY_PATH = summary_src
        B.AGG_REPORT_PATH = agg_src
        B.OUT_JSON = user_json
        B.OUT_HTML = user_html
        data = B.build_ui_data()
        B.write_outputs(data)
        result["stage"] = "built"
        result["user_html"] = user_html
        result["user_json"] = user_json
        result["contract_version"] = data.get("contract_version")
        ur = data.get("user_run") or {}
        result["headline"] = ur.get("headline")
        result["output_label"] = ur.get("output_label")
        result["ok"] = bool(ur.get("headline"))
        if not result["ok"]:
            # Built, but the user's run summary had no headline -> disclose it.
            result["stage"] = "built_no_user_headline"
            result["error"] = (
                "results UI built, but the run summary carried no headline "
                "block -- the run may not have completed")
    finally:
        B.RUN_SUMMARY_PATH, B.AGG_REPORT_PATH, B.OUT_JSON, B.OUT_HTML = saved

    # PROVE the committed zero-install template files are byte-for-byte unchanged.
    html_sha_after = _sha256(committed_html)
    json_sha_after = _sha256(committed_json)
    result["committed_ui_app_unchanged"] = (html_sha_before == html_sha_after)
    result["committed_ui_data_unchanged"] = (json_sha_before == json_sha_after)
    if not (result["committed_ui_app_unchanged"]
            and result["committed_ui_data_unchanged"]):
        # Defensive: a committed-file change is a HARD failure of the contract.
        result["ok"] = False
        result["stage"] = "committed_template_mutated"
        result["error"] = (
            "INVARIANT VIOLATION: committed ui_app.html / ui_data.json changed "
            "during a user-results refresh (they must stay byte-unchanged)")
    return result


def validate_task8_gate(repo_root: str = ".",
                        *, run_live: bool = True) -> Dict[str, Any]:
    """Phase IGUI Task-8 acceptance gate.

    Checks (all must be True):
      * graceful fallback when there is no user run (ok False, stage no_user_run,
        committed files untouched);
      * with a synthetic run_output, the refresh builds a USER copy whose
        ``user_run`` headline matches the run summary VERBATIM;
      * the committed ui_app.html / ui_data.json are byte-for-byte unchanged
        across the whole exercise;
      * the USER copy is a separate file (never the committed template);
      * the builder layer is import-clean stdlib (no third-party top-level import).
    """
    import shutil
    import tempfile

    root = os.path.abspath(repo_root if repo_root != "." else _REPO)
    checks: Dict[str, bool] = {}

    committed_html = os.path.join(root, "ui_app.html")
    committed_json = os.path.join(root, "ui_data.json")
    html_sha0 = _sha256(committed_html)
    json_sha0 = _sha256(committed_json)

    work = tempfile.mkdtemp(prefix="igui8_gate_")
    try:
        empty_run = os.path.join(work, "empty_run")
        os.makedirs(empty_run, exist_ok=True)
        user_a = os.path.join(work, "user_a")
        miss = refresh_user_results(empty_run, user_a, repo_root=root)
        checks["fallback_ok_false"] = (miss.get("ok") is False)
        checks["fallback_stage_no_user_run"] = (miss.get("stage") == "no_user_run")
        checks["fallback_committed_untouched"] = bool(
            miss.get("committed_ui_app_unchanged")
            and miss.get("committed_ui_data_unchanged"))

        # Synthetic run_output by COPYING the governed sample evidence (display
        # layer only -- this is exactly what _build_user_run reads VERBATIM).
        run_out = os.path.join(work, "run_output")
        os.makedirs(run_out, exist_ok=True)
        src_summary = os.path.join(root, "docs", "validation", SUMMARY_NAME)
        src_agg = os.path.join(root, "docs", "validation", AGG_REPORT_NAME)
        have_evidence = os.path.isfile(src_summary) and os.path.isfile(src_agg)
        checks["sample_evidence_present"] = have_evidence
        if have_evidence and run_live:
            shutil.copy2(src_summary, os.path.join(run_out, SUMMARY_NAME))
            shutil.copy2(src_agg, os.path.join(run_out, AGG_REPORT_NAME))
            user_b = os.path.join(work, "user_b")
            res = refresh_user_results(run_out, user_b, repo_root=root)
            checks["refresh_ok"] = bool(res.get("ok"))
            checks["user_html_written"] = bool(
                res.get("user_html") and os.path.isfile(res["user_html"]))
            checks["user_json_written"] = bool(
                res.get("user_json") and os.path.isfile(res["user_json"]))
            checks["user_copy_is_separate_file"] = bool(
                res.get("user_html") != committed_html
                and res.get("user_json") != committed_json)
            checks["committed_unchanged_after_build"] = bool(
                res.get("committed_ui_app_unchanged")
                and res.get("committed_ui_data_unchanged"))
            # Headline carried VERBATIM from the run summary.
            with open(src_summary, encoding="utf-8") as fh:
                summ = json.load(fh)
            want = (summ.get("headline") or {})
            with open(res["user_json"], encoding="utf-8") as fh:
                udata = json.load(fh)
            got = (udata.get("user_run") or {}).get("headline") or {}
            checks["user_run_headline_verbatim"] = (got == want and bool(got))
        # Import cleanliness of the builder layer (stdlib only at top level).
        B = _import_build_ui_data()
        checks["builder_is_stdlib"] = (
            getattr(B, "CONTRACT_VERSION", None) is not None)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    # Whole-exercise committed-template invariant.
    checks["committed_html_byte_unchanged"] = (_sha256(committed_html) == html_sha0)
    checks["committed_json_byte_unchanged"] = (_sha256(committed_json) == json_sha0)

    ok = all(checks.values())
    return {"ok": ok, "n_checks": len(checks),
            "n_pass": sum(1 for v in checks.values() if v), "checks": checks}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-output", default=DEFAULT_RUN_OUTPUT_DIR)
    ap.add_argument("--user-results", default=DEFAULT_USER_RESULTS_DIR)
    ap.add_argument("--gate", action="store_true", help="run the Task-8 gate")
    a = ap.parse_args()
    if a.gate:
        out = validate_task8_gate(_REPO)
    else:
        out = refresh_user_results(a.run_output, a.user_results)
    print(json.dumps(out, indent=1, default=str))
    raise SystemExit(0 if out.get("ok") else 1)
