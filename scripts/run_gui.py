#!/usr/bin/env python3
"""Phase IGUI Task 2 - Actuarial Input & Run GUI: stdlib local runner.

A **standard-library-only** local runner for the owner-directed input+run GUI.
It serves a self-contained run-controls page on ``127.0.0.1`` and:

  * ``GET  /``         -> the run-controls form (zero external references);
  * ``GET  /healthz``  -> ``{"ok": true, ...}`` liveness;
  * ``POST /validate`` -> normalise the payload + run it through the REAL loader
                          validator (``scripts/load_user_inputs.validate_run_controls_dict``),
                          fail-loud, returning every issue;
  * ``POST /save``     -> validate, then (only if clean) write/merge the run
                          controls into ``model_inputs.json`` in the loader's
                          ``{currency, run_settings}`` sub-schema, re-parsing the
                          file as a corruption guard.

Discipline: NO third-party dependency (``http.server``, ``json``, ``webbrowser``
- all standard library); binds 127.0.0.1 ONLY; makes NO outbound network call;
NO model parameter change. This is Task 2 (run controls + scaffolding); model
points / assumptions / ESG / end-to-end run land in later staged tasks. The
zero-install RESULTS UI (``ui_app.html``) is untouched.

Usage:
    PYTHONPATH=. python3 scripts/run_gui.py            # opens the form in a browser
    PYTHONPATH=. python3 scripts/run_gui.py --no-browser --port 8765
    PYTHONPATH=. python3 scripts/run_gui.py --self-test # in-process localhost round-trip
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# repo root on path so we can import the core module + the loader validator
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
_SCRIPTS = os.path.join(_REPO, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from par_model_v2.viewer.igui_run_controls import (  # noqa: E402
    normalize_run_controls,
    render_form_html,
    run_controls_to_model_inputs,
)
from par_model_v2.viewer.igui_model_points import (  # noqa: E402  (Task 3)
    book_scaling_disclosure,
    ingest_inforce,
    normalize_balance_sheet,
    normalize_model_points,
    portfolio_to_model_inputs,
    reconcile_balance_sheet,
    render_model_points_html,
)
from par_model_v2.viewer.igui_assumptions import (  # noqa: E402  (Task 4)
    default_assumptions,
    normalize_assumptions,
    assumptions_to_model_inputs,
    render_assumptions_html,
)
from par_model_v2.viewer.igui_esg import (  # noqa: E402  (Task 5)
    default_esg,
    normalize_esg,
    esg_to_model_inputs,
    render_esg_html,
)
from par_model_v2.viewer.igui_validation_gating import (  # noqa: E402  (Task 6)
    render_gate_html,
    aggregate_validation,
    build_run_gate,
)
from par_model_v2.viewer.igui_run_execution import (  # noqa: E402  (Task 7)
    render_run_html,
    execute_run,
)
from par_model_v2.viewer.igui_job_manager import JobManager  # noqa: E402  (GUI-1)
from par_model_v2.viewer.igui_stress import (  # noqa: E402  (GUI-2)
    asset_stress_report,
    catalogue_for,
    read_base_headline,
    render_stress_html,
    run_stress,
)
from par_model_v2.viewer.igui_calibration import (  # noqa: E402  (GUI-3)
    calibration_catalogue,
    market_data_status,
    render_calibration_html,
    run_calibration,
)
from par_model_v2.viewer.igui_run_history import (  # noqa: E402  (GUI-4)
    compare_runs,
    get_run,
    load_registry,
    render_history_html,
)
from par_model_v2.viewer.igui_path_detail import (  # noqa: E402  (GD-1)
    build_path_detail_response,
    render_paths_html,
)
from par_model_v2.viewer.igui_cashflows import (  # noqa: E402  (CF-3)
    build_cashflow_response,
    render_cashflows_html,
)
from par_model_v2.viewer.igui_drilldown import (  # noqa: E402  (GD-2)
    build_drilldown_response,
    render_drilldown_html,
)
from par_model_v2.viewer.igui_decomposition import (  # noqa: E402  (GD-3)
    build_decomposition_response,
    render_decomposition_html,
)
from par_model_v2.viewer.igui_portfolio_builder import (  # noqa: E402  (PC-1)
    build_construction_defaults,
    build_construction_response,
    render_portfolio_html,
)
from par_model_v2.viewer.igui_results_refresh import (  # noqa: E402  (Task 8)
    refresh_user_results,
    DEFAULT_USER_RESULTS_DIR,
    USER_HTML_NAME,
    USER_JSON_NAME,
)

HOST = "127.0.0.1"  # localhost ONLY (never a wildcard bind); no outbound network

#: Where the Task-7 end-to-end run writes its RUN_MODEL_*.json artifacts. A
#: dedicated dir (NOT docs/validation) so a user run never clobbers governed
#: evidence; the offline RESULTS UI is refreshed by pointing build_ui_data here.
RUN_OUTPUT_DIR = "run_output"

#: Phase IGUI Task 8 - where the own-run refresh writes the USER copy of the
#: offline RESULTS UI (separate from the committed zero-install ui_app.html).
USER_RESULTS_DIR = DEFAULT_USER_RESULTS_DIR

_NO_USER_RESULTS_HTML = (
    "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
    "<title>Your results</title></head><body style=\"font-family:sans-serif;max-width:40rem;margin:3rem auto\">"
    "<h1>No run yet</h1><p>Supply your inputs, clear the run gate, and press "
    "<b>Run the model end-to-end</b>. Your own results then appear here.</p>"
    "<p><a href=\"/run-execution\">Go to the run page</a></p></body></html>")


def _loader_validate(model_inputs_fragment):
    """Round-trip the GUI payload through the REAL loader's dict validator."""
    import load_user_inputs  # scripts/load_user_inputs.py (stdlib import path)
    return load_user_inputs.validate_run_controls_dict(model_inputs_fragment)


def build_response(payload, *, out_path=None, do_write=False):
    """Pure request handler: payload -> validation (+ optional write) -> result."""
    typed, norm_errors = normalize_run_controls(payload)
    if norm_errors:
        return {"ok": False, "stage": "normalise", "errors": norm_errors}
    fragment = run_controls_to_model_inputs(typed)
    loader_errors = _loader_validate(fragment)
    if loader_errors:
        return {"ok": False, "stage": "loader_validation", "errors": loader_errors}
    result = {"ok": True, "stage": "validated", "model_inputs": fragment,
              "reproducibility_digest": fragment["run_settings"]["reproducibility_digest"]}
    if do_write and out_path:
        merged = _merge_into_model_inputs(out_path, fragment)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=1)
        with open(out_path, "r", encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard: never hand a corrupt file downstream
        result["written"] = os.path.abspath(out_path)
        result["model_inputs"] = merged
    return result


def _merge_into_model_inputs(out_path, fragment):
    """Merge run controls into an existing model_inputs.json (preserving any
    portfolio/balance_sheet/assumptions a later task added) or start a new one."""
    base = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as fh:
                base = json.load(fh)
        except (OSError, json.JSONDecodeError):
            base = {}
    base["schema_version"] = fragment["schema_version"]
    base["generated_at"] = fragment["generated_at"]
    base.setdefault("source", fragment["source"])
    base["currency"] = fragment["currency"]
    base["run_settings"] = fragment["run_settings"]
    return base


def _loader_validate_portfolio(fragment):
    """Round-trip a portfolio fragment through the REAL loader's dict validator."""
    import load_user_inputs  # scripts/load_user_inputs.py
    return load_user_inputs.validate_portfolio_dict(fragment)


def build_portfolio_response(payload, *, out_path=None, do_write=False):
    """Pure handler for the Task-3 model-points domain: payload -> typed rows +
    balance sheet -> loader validation (+ optional merge-write) -> result."""
    rows_in = payload.get("portfolio") if isinstance(payload, dict) else None
    bs_in = payload.get("balance_sheet") if isinstance(payload, dict) else None
    typed_rows, row_errs = normalize_model_points(rows_in)
    typed_bs, bs_errs = normalize_balance_sheet(bs_in if bs_in is not None else {})
    if row_errs or bs_errs:
        return {"ok": False, "stage": "normalise", "errors": row_errs + bs_errs}
    fragment = portfolio_to_model_inputs(typed_rows, typed_bs)
    loader_errors = _loader_validate_portfolio(fragment)
    if loader_errors:
        return {"ok": False, "stage": "loader_validation", "errors": loader_errors}
    result = {
        "ok": True, "stage": "validated",
        "model_inputs": {"portfolio": fragment["portfolio"],
                         "balance_sheet": fragment["balance_sheet"],
                         "totals": fragment["totals"]},
        "reconcile": reconcile_balance_sheet(typed_bs),
        "book_scaling": book_scaling_disclosure(typed_rows),
    }
    if do_write and out_path:
        merged = _merge_portfolio_into_model_inputs(out_path, fragment)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=1)
        with open(out_path, "r", encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard: never hand a corrupt file downstream
        result["written"] = os.path.abspath(out_path)
        result["model_inputs"] = merged
    return result


def _merge_portfolio_into_model_inputs(out_path, fragment):
    """Merge portfolio + balance_sheet + totals into an existing
    model_inputs.json (preserving currency / run_settings a prior task wrote)."""
    base = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as fh:
                base = json.load(fh)
        except (OSError, json.JSONDecodeError):
            base = {}
    base["schema_version"] = fragment["schema_version"]
    base["generated_at"] = fragment["generated_at"]
    base.setdefault("source", fragment["source"])
    base["portfolio"] = fragment["portfolio"]
    base["balance_sheet"] = fragment["balance_sheet"]
    base["totals"] = fragment["totals"]
    return base


def build_reconcile_response(payload):
    """Pure handler for the live reconciliation + book-scaling preview (no write,
    no hard validation - it is a best-effort echo as the user edits)."""
    rows_in = payload.get("portfolio") if isinstance(payload, dict) else None
    bs_in = payload.get("balance_sheet") if isinstance(payload, dict) else None
    typed_rows, _ = normalize_model_points(rows_in)
    typed_bs, _ = normalize_balance_sheet(bs_in if bs_in is not None else {})
    return {"ok": True,
            "reconcile": reconcile_balance_sheet(typed_bs),
            "book_scaling": book_scaling_disclosure(typed_rows)}


def build_ingest_response(payload):
    """Pure handler for an uploaded in-force file -> canonical Portfolio rows."""
    text = payload.get("text") if isinstance(payload, dict) else None
    fmt = (payload.get("format") if isinstance(payload, dict) else None) or "auto"
    rows, errs = ingest_inforce(text or "", fmt)
    if errs:
        return {"ok": False, "errors": errs, "rows": rows}
    return {"ok": True, "rows": rows, "n": len(rows)}


def _loader_validate_assumptions(fragment):
    """Round-trip an assumptions fragment through the REAL loader's dict validator."""
    import load_user_inputs  # scripts/load_user_inputs.py
    return load_user_inputs.validate_assumptions_dict(fragment)


def build_assumptions_response(payload, *, out_path=None, do_write=False):
    """Pure handler for the Task-4 assumptions domain (owner-gated): payload ->
    typed assumptions -> loader validation (+ optional merge-write) -> result.
    The governed/frozen dependence echo is attached read-only and any override
    is rejected by the loader validator."""
    a_in = payload.get("assumptions") if isinstance(payload, dict) else None
    typed, norm_errors = normalize_assumptions(a_in if a_in is not None else {})
    if norm_errors:
        return {"ok": False, "stage": "normalise", "errors": norm_errors}
    fragment = assumptions_to_model_inputs(typed)
    loader_errors = _loader_validate_assumptions(fragment)
    if loader_errors:
        return {"ok": False, "stage": "loader_validation", "errors": loader_errors}
    result = {"ok": True, "stage": "validated",
              "model_inputs": {"assumptions": fragment["assumptions"]}}
    if do_write and out_path:
        merged = _merge_assumptions_into_model_inputs(out_path, fragment)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=1)
        with open(out_path, "r", encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard: never hand a corrupt file downstream
        result["written"] = os.path.abspath(out_path)
        result["model_inputs"] = merged
    return result


def _merge_assumptions_into_model_inputs(out_path, fragment):
    """Merge the assumptions block into an existing model_inputs.json (preserving
    currency / run_settings / portfolio / balance_sheet a prior task wrote)."""
    base = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as fh:
                base = json.load(fh)
        except (OSError, json.JSONDecodeError):
            base = {}
    base["schema_version"] = fragment["schema_version"]
    base["generated_at"] = fragment["generated_at"]
    base.setdefault("source", fragment["source"])
    base["assumptions"] = fragment["assumptions"]
    return base


def _loader_validate_esg(fragment):
    """Round-trip an ESG fragment through the REAL loader's dict validator."""
    import load_user_inputs  # scripts/load_user_inputs.py
    return load_user_inputs.validate_esg_dict(fragment)


def build_esg_response(payload, *, out_path=None, do_write=False):
    """Pure handler for the Task-5 ESG domain (stop-rule-bounded, owner-gated):
    payload -> typed provenance -> loader validation (+ optional merge-write) ->
    result. The governed/frozen ESG calibration echo + pinned copula structure are
    attached read-only; the loader rejects any override or new-structure candidate."""
    e_in = payload.get("esg") if isinstance(payload, dict) else None
    typed, norm_errors = normalize_esg(e_in if e_in is not None else {})
    if norm_errors:
        return {"ok": False, "stage": "normalise", "errors": norm_errors}
    fragment = esg_to_model_inputs(typed)
    loader_errors = _loader_validate_esg(fragment)
    if loader_errors:
        return {"ok": False, "stage": "loader_validation", "errors": loader_errors}
    result = {"ok": True, "stage": "validated",
              "model_inputs": {"esg": fragment["esg"]}}
    if do_write and out_path:
        merged = _merge_esg_into_model_inputs(out_path, fragment)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=1)
        with open(out_path, "r", encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard: never hand a corrupt file downstream
        result["written"] = os.path.abspath(out_path)
        result["model_inputs"] = merged
    return result


def _merge_esg_into_model_inputs(out_path, fragment):
    """Merge the esg block into an existing model_inputs.json (preserving currency /
    run_settings / portfolio / balance_sheet / assumptions a prior task wrote)."""
    base = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as fh:
                base = json.load(fh)
        except (OSError, json.JSONDecodeError):
            base = {}
    base["schema_version"] = fragment["schema_version"]
    base["generated_at"] = fragment["generated_at"]
    base.setdefault("source", fragment["source"])
    base["esg"] = fragment["esg"]
    return base


def _read_model_inputs(out_path):
    """Best-effort read of the assembled model_inputs.json (empty dict if absent
    or unreadable - the aggregate validator then reports every domain missing)."""
    if out_path and os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def build_preflight_response(out_path):
    """Read-only aggregate validation of the assembled model_inputs.json across ALL
    domains (run controls, model points, assumptions, ESG), routed through the REAL
    loader. No write; surfaces every issue for the gate page."""
    import load_user_inputs  # scripts/load_user_inputs.py
    return aggregate_validation(_read_model_inputs(out_path), load_user_inputs)


def build_run_gate_response(out_path, *, do_write=False):
    """The Task-6 RUN GATE: aggregate-validate the assembled inputs; if-and-only-if
    every domain is present AND clean, record a governance gate (ChangeRecord-style
    provenance) + a run-level reproducibility digest into model_inputs.json. A
    BLOCKED gate writes nothing. This records readiness only; it does NOT execute
    the model (that is Task 7)."""
    import load_user_inputs  # scripts/load_user_inputs.py
    mi = _read_model_inputs(out_path)
    validation = aggregate_validation(mi, load_user_inputs)
    gate = build_run_gate(mi, validation)
    if not validation.get("ok"):
        return {"ok": False, "stage": "run_gate_blocked",
                "validation": validation, "run_gate": gate}
    result = {"ok": True, "stage": "run_gate_cleared",
              "validation": validation, "run_gate": gate}
    if do_write and out_path and os.path.exists(out_path):
        mi["run_gate"] = gate
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(mi, fh, indent=1)
        with open(out_path, "r", encoding="utf-8") as fh:
            json.load(fh)  # re-parse guard: never hand a corrupt file downstream
        result["written"] = os.path.abspath(out_path)
    return result


def build_save_run_response(payload, out_path, job_manager,
                            run_output_dir=RUN_OUTPUT_DIR):
    """GUI-5 (owner request 2026-07-03): ONE-CLICK 'Save & run' from the Run
    Controls page. Orchestrates the existing governed steps server-side -
    nothing is bypassed:

      1. validate + SAVE the posted run controls (same as POST /save);
      2. optionally AUTO-FILL any missing input domain (model points /
         assumptions / ESG) with the documented governed defaults, through
         the SAME builders/validators the dedicated pages use;
      3. re-run the Task-6 RUN GATE over the assembled file (digest bound to
         the exact bytes); a BLOCKED gate refuses the run and reports every
         blocking issue;
      4. submit the run as a GUI-1 async job -> the page polls /jobs/<id>.

    The gate is never skipped: /execute-async -> execute_run re-verifies it
    before spawning the engine."""
    payload = payload or {}
    smoke = bool(payload.get("smoke", True))
    autofill = bool(payload.get("autofill", True))
    # (1) save the run controls exactly as POST /save does
    saved = build_response(payload, out_path=out_path, do_write=True)
    if not saved.get("ok"):
        saved["stage"] = "save_failed"
        return saved
    # (2) governed-default auto-fill for ABSENT domains only
    autofilled = []
    if autofill:
        mi = _read_model_inputs(out_path)
        if not mi.get("portfolio") or not mi.get("balance_sheet"):
            from par_model_v2.viewer.igui_model_points import (
                default_balance_sheet, default_model_points)
            r = build_portfolio_response(
                {"portfolio": default_model_points(),
                 "balance_sheet": default_balance_sheet()},
                out_path=out_path, do_write=True)
            if r.get("ok"):
                autofilled.append("model_points+balance_sheet")
        mi = _read_model_inputs(out_path)
        if not mi.get("assumptions"):
            from par_model_v2.viewer.igui_assumptions import default_assumptions
            r = build_assumptions_response(
                {"assumptions": default_assumptions()},
                out_path=out_path, do_write=True)
            if r.get("ok"):
                autofilled.append("assumptions")
        mi = _read_model_inputs(out_path)
        if not mi.get("esg"):
            from par_model_v2.viewer.igui_esg import default_esg
            r = build_esg_response({"esg": default_esg()},
                                   out_path=out_path, do_write=True)
            if r.get("ok"):
                autofilled.append("esg")
    # (3) the Task-6 run gate (writes the gate + digest only when CLEARED)
    gate_res = build_run_gate_response(out_path, do_write=True)
    if not gate_res.get("ok"):
        gate = gate_res.get("run_gate") or {}
        return {"ok": False, "stage": "run_gate_blocked",
                "autofilled": autofilled,
                "blocking_issues": gate.get("blocking_issues") or [],
                "domains": gate.get("domains") or {},
                "hint": ("complete the listed sections (Model Points / "
                         "Assumptions / ESG pages) or enable auto-fill, "
                         "then press Run again")}
    # (4) submit the async run (GUI-1 job; engine re-verifies the gate)
    if job_manager is None:
        return {"ok": False, "stage": "no_job_manager",
                "errors": ["no job manager bound"]}
    sub = job_manager.submit(smoke=smoke)
    if not sub.get("ok"):
        sub["stage"] = "job_refused"
        sub["autofilled"] = autofilled
        return sub
    return {"ok": True, "stage": "run_submitted", "job_id": sub["job_id"],
            "smoke": smoke, "autofilled": autofilled,
            "gate": {"decision": (gate_res.get("run_gate") or {}).get("decision"),
                     "reproducibility_digest":
                         (gate_res.get("run_gate") or {}).get("reproducibility_digest")}}


def build_execute_response(out_path, *, payload=None, run_output_dir=RUN_OUTPUT_DIR):
    """The Task-7 END-TO-END RUN: verify the assembled model_inputs.json carries a
    CLEARED Task-6 run gate, then drive scripts/run_model.py from it, capture the
    output, carry the run-gate reproducibility digest into the output provenance,
    and shape the offline RESULTS-UI handoff. A run is REFUSED (nothing spawned)
    unless the gate permits it. ``smoke`` (default True from the GUI) selects the
    fast diagnostic config. The zero-install RESULTS UI (ui_app.html) is untouched."""
    smoke = True
    if isinstance(payload, dict) and "smoke" in payload:
        smoke = bool(payload["smoke"])
    repo_root = _REPO
    out_dir = (run_output_dir if os.path.isabs(run_output_dir)
               else os.path.join(repo_root, run_output_dir))
    res = execute_run(out_path, out_dir, smoke=smoke, repo_root=repo_root)
    # Phase IGUI Task 8: on a successful run, refresh a USER copy of the
    # offline RESULTS UI from THIS run's run_output so the user sees their
    # OWN run -- never touching the committed zero-install ui_app.html. The
    # refresh is best-effort: a refresh hiccup must NEVER fail the run.
    if isinstance(res, dict) and res.get('ok'):
        try:
            ref = refresh_user_results(out_dir,
                                       os.path.join(repo_root, USER_RESULTS_DIR),
                                       repo_root=repo_root)
            res['user_results'] = {
                'ok': bool(ref.get('ok')),
                'stage': ref.get('stage'),
                'view_url': '/my-results' if ref.get('ok') else None,
                'user_html': ref.get('user_html'),
                'user_json': ref.get('user_json'),
                'committed_ui_app_unchanged':
                    ref.get('committed_ui_app_unchanged'),
                'contract_version': ref.get('contract_version'),
            }
        except Exception as exc:  # never break the run on a refresh issue
            res['user_results'] = {'ok': False, 'stage': 'refresh_error',
                                   'error': str(exc)}
    return res


def _with_nav(html, active_path):
    """PC-1c: inject the shared navigation bar right after <body> on every
    console page (single change point - pages stay individually
    self-contained; the byte-pinned ui_app.html / my-results copy is NEVER
    touched by this: it is served through a different handler path)."""
    from par_model_v2.viewer.igui_portfolio_builder import nav_html
    marker = "<body>"
    i = html.find(marker)
    if i < 0:
        return html
    j = i + len(marker)
    return html[:j] + nav_html(active_path) + html[j:]


class _Handler(BaseHTTPRequestHandler):
    server_version = "IGUIRunGui/1.0"
    out_path = "model_inputs.json"
    job_manager = None  # bound per-server in make_server (GUI-1)

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, _with_nav(render_form_html(), "/"), "text/html")
        elif self.path in ("/model-points", "/model-points.html"):
            self._send(200, _with_nav(render_model_points_html(), "/model-points"), "text/html")
        elif self.path in ("/assumptions", "/assumptions.html"):
            self._send(200, _with_nav(render_assumptions_html(), "/assumptions"), "text/html")
        elif self.path in ("/esg", "/esg.html"):
            self._send(200, _with_nav(render_esg_html(), "/esg"), "text/html")
        elif self.path in ("/run-gate", "/run-gate.html"):
            self._send(200, _with_nav(render_gate_html(), "/run-gate"), "text/html")
        elif self.path in ("/stress", "/stress.html"):
            self._send(200, _with_nav(render_stress_html(), "/stress"), ctype="text/html")
        elif self.path == "/stress-catalogue":
            mi = None
            try:
                if os.path.exists(self.out_path):
                    with open(self.out_path, encoding="utf-8") as fh:
                        mi = json.load(fh)
            except (OSError, json.JSONDecodeError):
                mi = None
            out_root = os.path.join(_REPO, RUN_OUTPUT_DIR)
            self._send(200, json.dumps({
                "ok": True, "catalogue": catalogue_for(mi),
                "base_available": read_base_headline(out_root) is not None}))
        elif self.path == "/asset-stress":
            self._send(200, json.dumps(asset_stress_report()))
        elif self.path in ("/calibration", "/calibration.html"):
            self._send(200, _with_nav(render_calibration_html(), "/calibration"), "text/html")
        elif self.path == "/calibration-catalogue":
            self._send(200, json.dumps({
                "ok": True, "catalogue": calibration_catalogue()}))
        elif self.path == "/market-data-status":
            self._send(200, json.dumps(market_data_status(), default=str))
        elif self.path in ("/portfolio", "/portfolio.html"):
            self._send(200, _with_nav(render_portfolio_html(), "/portfolio"), "text/html")
        elif self.path == "/portfolio-defaults":
            self._send(200, json.dumps(
                build_construction_defaults(self.out_path), default=str))
        elif self.path in ("/cashflows", "/cashflows.html"):
            self._send(200, _with_nav(render_cashflows_html(), "/cashflows"), "text/html")
        elif self.path == "/cashflow-data":
            res = build_cashflow_response(
                self.out_path, os.path.join(_REPO, RUN_OUTPUT_DIR))
            self._send(200 if res.get("ok") else 422,
                       json.dumps(res, default=str))
        elif self.path in ("/drilldown", "/drilldown.html"):
            self._send(200, _with_nav(render_drilldown_html(), "/drilldown"),
                       "text/html")
        elif self.path == "/drilldown-data":
            res = build_drilldown_response(
                self.out_path, os.path.join(_REPO, RUN_OUTPUT_DIR))
            self._send(200 if res.get("ok") else 422,
                       json.dumps(res, default=str))
        elif self.path in ("/decomposition", "/decomposition.html"):
            self._send(200, _with_nav(render_decomposition_html(),
                                      "/decomposition"), "text/html")
        elif self.path == "/decomposition-data":
            res = build_decomposition_response(
                os.path.join(_REPO, RUN_OUTPUT_DIR))
            self._send(200 if res.get("ok") else 422,
                       json.dumps(res, default=str))
        elif self.path in ("/paths", "/paths.html"):
            self._send(200, _with_nav(render_paths_html(), "/paths"), "text/html")
        elif self.path == "/path-data":
            res = build_path_detail_response(
                self.out_path, os.path.join(_REPO, RUN_OUTPUT_DIR))
            self._send(200 if res.get("ok") else 422,
                       json.dumps(res, default=str))
        elif self.path in ("/history", "/history.html"):
            self._send(200, _with_nav(render_history_html(), "/history"), "text/html")
        elif self.path == "/runs":
            self._send(200, json.dumps(
                load_registry(self._jobs_dir()), default=str))
        elif self.path.startswith("/runs/"):
            rid = self.path.split("/runs/", 1)[1].split("?")[0]
            import urllib.parse as _up
            got = get_run(self._jobs_dir(), _up.unquote(rid))
            self._send(200 if got.get("ok") else 404,
                       json.dumps(got, default=str))
        elif self.path.startswith("/compare-runs"):
            import urllib.parse as _up
            q = _up.parse_qs(_up.urlparse(self.path).query)
            a = (q.get("a") or [None])[0]
            b = (q.get("b") or [None])[0]
            if not a or not b:
                self._send(422, json.dumps(
                    {"ok": False, "error": "query params a and b required"}))
            else:
                got = compare_runs(self._jobs_dir(), a, b)
                self._send(200 if got.get("ok") else 404,
                           json.dumps(got, default=str))
        elif self.path == "/jobs":
            if self.job_manager is None:
                self._send(503, json.dumps({"ok": False, "error": "no job manager"}))
            else:
                self._send(200, json.dumps(self.job_manager.list_jobs()))
        elif self.path.startswith("/jobs/"):
            if self.job_manager is None:
                self._send(503, json.dumps({"ok": False, "error": "no job manager"}))
            else:
                jid = self.path.split("/jobs/", 1)[1].split("?")[0]
                st = self.job_manager.status(jid)
                self._send(200 if st.get("ok") else 404, json.dumps(st))
        elif self.path in ("/run-execution", "/run-execution.html"):
            self._send(200, _with_nav(render_run_html(), "/run-execution"), "text/html")
        elif self.path in ("/my-results", "/my-results.html"):
            self._serve_user_results_html()
        elif self.path == "/my-results.json":
            self._serve_user_results_json()
        elif self.path == "/healthz":
            self._send(200, json.dumps({"ok": True, "host": HOST,
                                        "task": "Phase IGUI Task 6 validation gating"}))
        else:
            self._send(404, json.dumps({"ok": False, "error": "not found"}))

    def _jobs_dir(self):
        return os.path.join(_REPO, RUN_OUTPUT_DIR, "jobs")

    def _user_results_path(self, name):
        return os.path.join(_REPO, USER_RESULTS_DIR, name)

    def _serve_user_results_html(self):
        path = self._user_results_path(USER_HTML_NAME)
        if os.path.isfile(path):
            with open(path, 'rb') as fh:
                self._send(200, fh.read(), 'text/html')
        else:
            self._send(200, _NO_USER_RESULTS_HTML, 'text/html')

    def _serve_user_results_json(self):
        path = self._user_results_path(USER_JSON_NAME)
        if os.path.isfile(path):
            with open(path, 'rb') as fh:
                self._send(200, fh.read(), 'application/json')
        else:
            self._send(404, json.dumps({'ok': False,
                'error': 'no user run yet -- supply inputs and press Run'}))

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}"), None
        except json.JSONDecodeError as exc:
            return None, str(exc)

    _POST_ROUTES = ("/validate", "/save", "/validate_portfolio", "/save_portfolio",
                    "/reconcile", "/ingest", "/validate_assumptions", "/save_assumptions",
                    "/validate_esg", "/save_esg", "/preflight", "/run", "/execute",
                    "/execute-async", "/run-stress", "/run-calibration", "/save-run",
                    "/validate_construction", "/save_construction")

    def do_POST(self):
        if self.path not in self._POST_ROUTES:
            self._send(404, json.dumps({"ok": False, "error": "not found"}))
            return
        payload, err = self._read_json()
        if err is not None:
            self._send(400, json.dumps({"ok": False, "errors": ["bad JSON: " + err]}))
            return
        try:
            if self.path in ("/validate", "/save"):
                res = build_response(payload, out_path=self.out_path,
                                     do_write=(self.path == "/save"))
            elif self.path in ("/validate_portfolio", "/save_portfolio"):
                res = build_portfolio_response(
                    payload, out_path=self.out_path,
                    do_write=(self.path == "/save_portfolio"))
            elif self.path in ("/validate_assumptions", "/save_assumptions"):
                res = build_assumptions_response(
                    payload, out_path=self.out_path,
                    do_write=(self.path == "/save_assumptions"))
            elif self.path in ("/validate_esg", "/save_esg"):
                res = build_esg_response(
                    payload, out_path=self.out_path,
                    do_write=(self.path == "/save_esg"))
            elif self.path == "/preflight":
                res = build_preflight_response(self.out_path)
            elif self.path == "/run":
                res = build_run_gate_response(self.out_path, do_write=True)
            elif self.path == "/execute":
                res = build_execute_response(self.out_path, payload=payload)
            elif self.path == "/run-stress":
                if self.job_manager is None:
                    res = {"ok": False, "errors": ["no job manager bound"]}
                else:
                    stress_id = (payload or {}).get("stress_id")
                    smoke = bool((payload or {}).get("smoke", True))
                    if not stress_id:
                        res = {"ok": False, "errors": ["stress_id required"]}
                    else:
                        inputs_path = self.out_path
                        out_root = os.path.join(_REPO, RUN_OUTPUT_DIR)
                        res = self.job_manager.submit(
                            smoke=smoke,
                            runner=(lambda smk, _sid=stress_id, _inp=inputs_path,
                                    _root=out_root: run_stress(
                                        _inp, _sid, _root, smoke=smk,
                                        repo_root=_REPO)),
                            meta={"kind": "stress", "stress_id": stress_id})
            elif self.path in ("/validate_construction", "/save_construction"):
                res = build_construction_response(
                    payload, self.out_path,
                    do_write=(self.path == "/save_construction"))
            elif self.path == "/save-run":
                res = build_save_run_response(payload, self.out_path,
                                              self.job_manager)
            elif self.path == "/run-calibration":
                if self.job_manager is None:
                    res = {"ok": False, "errors": ["no job manager bound"]}
                else:
                    cal_id = (payload or {}).get("calibration_id")
                    if not cal_id:
                        res = {"ok": False, "errors": ["calibration_id required"]}
                    else:
                        out_root = os.path.join(_REPO, RUN_OUTPUT_DIR)
                        res = self.job_manager.submit(
                            smoke=True,
                            runner=(lambda smk, _cid=cal_id, _root=out_root:
                                    run_calibration(_cid, _root)),
                            meta={"kind": "calibration",
                                  "calibration_id": cal_id})
            elif self.path == "/execute-async":
                if self.job_manager is None:
                    res = {"ok": False, "errors": ["no job manager bound"]}
                else:
                    smoke = True
                    if isinstance(payload, dict) and "smoke" in payload:
                        smoke = bool(payload["smoke"])
                    res = self.job_manager.submit(smoke=smoke)
            elif self.path == "/reconcile":
                res = build_reconcile_response(payload)
            else:  # /ingest
                res = build_ingest_response(payload)
        except Exception as exc:  # never leak a stack trace to the page
            self._send(500, json.dumps({"ok": False, "errors": ["runner error: %s" % exc]}))
            return
        self._send(200 if res.get("ok") else 422, json.dumps(res))

    def log_message(self, fmt, *args):  # quiet by default
        if os.environ.get("IGUI_VERBOSE"):
            super().log_message(fmt, *args)


def make_server(port=0, out_path="model_inputs.json"):
    manager = JobManager(
        runner=lambda smoke: build_execute_response(out_path,
                                                    payload={"smoke": smoke}),
        persist_dir=os.path.join(_REPO, RUN_OUTPUT_DIR, "jobs"),
    )
    handler = type("_BoundHandler", (_Handler,),
                   {"out_path": out_path, "job_manager": manager})
    return ThreadingHTTPServer((HOST, port), handler)


def self_test(out_path=None) -> int:
    """In-process localhost round-trip: GET / , POST /validate , POST /save."""
    import tempfile
    import urllib.request
    import urllib.error
    tmp = out_path or os.path.join(tempfile.mkdtemp(prefix="igui_"), "model_inputs.json")
    srv = make_server(0, tmp)
    host, port = srv.server_address
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    ok = True
    try:
        base = "http://%s:%d" % (host, port)
        with urllib.request.urlopen(base + "/", timeout=5) as r:
            html = r.read().decode("utf-8")
            ok &= (r.status == 200 and "Run Controls" in html and "39,975.654628199336" in html)
        from par_model_v2.viewer.igui_run_controls import default_run_controls
        body = json.dumps(default_run_controls()).encode("utf-8")
        req = urllib.request.Request(base + "/validate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            ok &= bool(j.get("ok")) and j["model_inputs"]["run_settings"]["reproducibility_digest"].startswith("sha256:")
        req = urllib.request.Request(base + "/save", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            ok &= bool(j.get("ok")) and os.path.exists(tmp)
        with open(tmp, encoding="utf-8") as fh:
            saved = json.load(fh)
        ok &= ("run_settings" in saved and "currency" in saved)

        # --- Task 3: model-points page + portfolio endpoints round-trip ---
        with urllib.request.urlopen(base + "/model-points", timeout=5) as r:
            mp = r.read().decode("utf-8")
            ok &= (r.status == 200 and "Model Points" in mp and "39,975.654628199336" in mp)
        from par_model_v2.viewer.igui_model_points import (
            default_balance_sheet, default_model_points)
        pbody = json.dumps({"portfolio": default_model_points(),
                            "balance_sheet": default_balance_sheet()}).encode("utf-8")
        req = urllib.request.Request(base + "/validate_portfolio", data=pbody,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            ok &= bool(j.get("ok")) and j["reconcile"]["reconciles"] is True
        req = urllib.request.Request(base + "/save_portfolio", data=pbody,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            ok &= bool(j.get("ok"))
        with open(tmp, encoding="utf-8") as fh:
            saved = json.load(fh)
        ok &= ("portfolio" in saved and "balance_sheet" in saved
               and "run_settings" in saved)  # merge preserved Task-2 controls
        ibody = json.dumps({"text": "Product,Age,Sex,Term,FaceValue,Premium,Count,Bonus\n"
                                    "HKCD_PAR_2026,45,M,20,100000,5000,1000,0\n",
                            "format": "auto"}).encode("utf-8")
        req = urllib.request.Request(base + "/ingest", data=ibody,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            ok &= bool(j.get("ok")) and j["n"] == 1

        # --- Task 4: assumptions page + endpoints round-trip (owner-gated) ---
        with urllib.request.urlopen(base + "/assumptions", timeout=5) as r:
            ap = r.read().decode("utf-8")
            ok &= (r.status == 200 and "Assumptions" in ap and "39,975.654628199336" in ap
                   and "copula_df_single_t" in ap and "readonly" in ap)
        from par_model_v2.viewer.igui_assumptions import default_assumptions
        abody = json.dumps({"assumptions": default_assumptions()}).encode("utf-8")
        req = urllib.request.Request(base + "/validate_assumptions", data=abody,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            ok &= bool(j.get("ok")) and "mortality" in j["model_inputs"]["assumptions"]
        # owner-gating: a payload that tries to override a frozen df is NEUTRALISED -
        # the server re-attaches the governed echo, so the returned/validated value
        # is always the governed constant (a GUI payload can never change it).
        tampered = {"assumptions": default_assumptions()}
        tampered["assumptions"]["governed_frozen_readback"] = {"copula_df_single_t": 9.999}
        treq = urllib.request.Request(base + "/validate_assumptions",
                                      data=json.dumps(tampered).encode("utf-8"),
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(treq, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            echo = j["model_inputs"]["assumptions"]["governed_frozen_readback"]
            ok &= (bool(j.get("ok")) and echo.get("copula_df_single_t") == 2.9451)
        req = urllib.request.Request(base + "/save_assumptions", data=abody,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            ok &= bool(j.get("ok"))
        with open(tmp, encoding="utf-8") as fh:
            saved = json.load(fh)
        ok &= ("assumptions" in saved and "portfolio" in saved
               and "run_settings" in saved)  # merge preserved Task-2 + Task-3

        # --- Task 5: ESG page + endpoints round-trip (stop-rule-bounded, owner-gated) ---
        with urllib.request.urlopen(base + "/esg", timeout=5) as r:
            ep = r.read().decode("utf-8")
            ok &= (r.status == 200 and "ESG" in ep and "39,975.654628199336" in ep
                   and "copula_df_single_t" in ep and "readonly" in ep
                   and "single_t_grouped_FROZEN" in ep)
        from par_model_v2.viewer.igui_esg import default_esg
        ebody = json.dumps({"esg": default_esg()}).encode("utf-8")
        req = urllib.request.Request(base + "/validate_esg", data=ebody,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            ok &= bool(j.get("ok")) and "market_data" in j["model_inputs"]["esg"]
        # owner-gating: a payload that tries to override a frozen calibration is
        # NEUTRALISED - the server re-attaches the governed echo + frozen structure.
        tampered = {"esg": default_esg()}
        tampered["esg"]["governed_esg_readback"] = {
            "equity.equity_vol": 9.999,
            "dependence.copula_structure": "vine_candidate"}
        treq = urllib.request.Request(base + "/validate_esg",
                                      data=json.dumps(tampered).encode("utf-8"),
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(treq, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            echo = j["model_inputs"]["esg"]["governed_esg_readback"]
            ok &= (bool(j.get("ok")) and echo.get("equity.equity_vol") == 0.22
                   and echo.get("dependence.copula_structure") == "single_t_grouped_FROZEN")
        req = urllib.request.Request(base + "/save_esg", data=ebody,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            ok &= bool(j.get("ok"))
        with open(tmp, encoding="utf-8") as fh:
            saved = json.load(fh)
        ok &= ("esg" in saved and "assumptions" in saved and "portfolio" in saved
               and "run_settings" in saved)  # merge preserved Tasks 2-4

        # --- Task 6: validation gating page + preflight/run endpoints ---
        with urllib.request.urlopen(base + "/run-gate", timeout=5) as r:
            gp = r.read().decode("utf-8")
            ok &= (r.status == 200 and "Run Gate" in gp and "39,975.654628199336" in gp
                   and "single_t_grouped_FROZEN" in gp and 'id="btn-run" disabled' in gp)
        # the fully-populated tmp (all four domains saved above) must CLEAR
        preq = urllib.request.Request(base + "/preflight", data=b"{}",
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(preq, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            ok &= bool(j.get("ok")) and all(
                j["domains"][d]["ok"] for d in
                ("run_controls", "model_points", "assumptions", "esg"))
        # /run records the gate + digest into model_inputs.json
        rreq = urllib.request.Request(base + "/run", data=b"{}",
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(rreq, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            ok &= (bool(j.get("ok")) and j["run_gate"]["decision"] == "CLEARED"
                   and j["run_gate"]["reproducibility_digest"].startswith("sha256:"))
        with open(tmp, encoding="utf-8") as fh:
            saved = json.load(fh)
        ok &= ("run_gate" in saved and saved["run_gate"]["run_permitted"] is True)

        # --- Task 7: end-to-end run page + execute-route guard (no model spawn) ---
        with urllib.request.urlopen(base + "/run-execution", timeout=5) as r:
            rp = r.read().decode("utf-8")
            ok &= (r.status == 200 and "Run the model end-to-end" in rp
                   and "39,975.654628199336" in rp
                   and 'id="btn-run" type="button" disabled' in rp)
        # --- Task 8: user-results routes serve a graceful placeholder until
        # a run exists (full build is covered by the Task-8 unit suite +
        # validate_task8_gate, which avoid a heavy in-process model spawn). ---
        with urllib.request.urlopen(base + "/my-results", timeout=5) as r:
            mr = r.read().decode("utf-8")
            ok &= (r.status == 200 and "No run yet" in mr)
        try:
            with urllib.request.urlopen(base + "/my-results.json", timeout=5) as r:
                ok &= False  # should have 404'd without a user run
        except urllib.error.HTTPError as he:
            ok &= (he.code == 404)
        # /execute against an UNGATED input must REFUSE (spawn nothing). Use a
        # throwaway path with no run_gate so the chain is provably gate-guarded.
        import tempfile as _tf
        ungated = os.path.join(_tf.mkdtemp(prefix="igui7_"), "model_inputs.json")
        with open(ungated, "w", encoding="utf-8") as fh:
            json.dump({"schema_version": "1.0.0"}, fh)
        gsrv = make_server(0, ungated)
        ghost, gport = gsrv.server_address
        gth = threading.Thread(target=gsrv.serve_forever, daemon=True)
        gth.start()
        try:
            ereq = urllib.request.Request("http://%s:%d/execute" % (ghost, gport),
                                          data=b'{"smoke": true}',
                                          headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(ereq, timeout=10) as r:
                    je = json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as he:
                je = json.loads(he.read().decode("utf-8"))
            ok &= (je.get("ok") is False and je.get("stage") == "run_gate_not_cleared")
        finally:
            gsrv.shutdown()
            gsrv.server_close()
    finally:
        srv.shutdown()
        srv.server_close()
    print(json.dumps({"self_test_ok": bool(ok), "host": host, "out": tmp}, indent=1))
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8765, help="localhost port (default 8765)")
    ap.add_argument("--out", default="model_inputs.json", help="model_inputs.json path")
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser")
    ap.add_argument("--self-test", action="store_true", help="in-process localhost round-trip")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    srv = make_server(args.port, args.out)
    host, port = srv.server_address
    url = "http://%s:%d/" % (host, port)
    print("Actuarial Input & Run GUI (Phase IGUI Task 6) serving at %s" % url)
    print("  - run controls: %s" % url)
    print("  - model points + in-force: %smodel-points" % url)
    print("  - assumptions (owner-gated): %sassumptions" % url)
    print("  - economic scenarios / ESG (stop-rule-bounded): %sesg" % url)
    print("  - validation & run gate: %srun-gate" % url)
    print("  - localhost only, offline; writes %s on Save." % os.path.abspath(args.out))
    if not args.no_browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        srv.shutdown()
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())