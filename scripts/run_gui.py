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

HOST = "127.0.0.1"  # localhost ONLY (never a wildcard bind); no outbound network


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


class _Handler(BaseHTTPRequestHandler):
    server_version = "IGUIRunGui/1.0"
    out_path = "model_inputs.json"

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
            self._send(200, render_form_html(), "text/html")
        elif self.path in ("/model-points", "/model-points.html"):
            self._send(200, render_model_points_html(), "text/html")
        elif self.path in ("/assumptions", "/assumptions.html"):
            self._send(200, render_assumptions_html(), "text/html")
        elif self.path in ("/esg", "/esg.html"):
            self._send(200, render_esg_html(), "text/html")
        elif self.path == "/healthz":
            self._send(200, json.dumps({"ok": True, "host": HOST,
                                        "task": "Phase IGUI Task 5 ESG"}))
        else:
            self._send(404, json.dumps({"ok": False, "error": "not found"}))

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}"), None
        except json.JSONDecodeError as exc:
            return None, str(exc)

    _POST_ROUTES = ("/validate", "/save", "/validate_portfolio", "/save_portfolio",
                    "/reconcile", "/ingest", "/validate_assumptions", "/save_assumptions",
                    "/validate_esg", "/save_esg")

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
    handler = type("_BoundHandler", (_Handler,), {"out_path": out_path})
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
    print("Actuarial Input & Run GUI (Phase IGUI Task 5) serving at %s" % url)
    print("  - run controls: %s" % url)
    print("  - model points + in-force: %smodel-points" % url)
    print("  - assumptions (owner-gated): %sassumptions" % url)
    print("  - economic scenarios / ESG (stop-rule-bounded): %sesg" % url)
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