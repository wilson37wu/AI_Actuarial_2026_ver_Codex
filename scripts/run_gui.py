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
        elif self.path == "/healthz":
            self._send(200, json.dumps({"ok": True, "host": HOST,
                                        "task": "Phase IGUI Task 2 run controls"}))
        else:
            self._send(404, json.dumps({"ok": False, "error": "not found"}))

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}"), None
        except json.JSONDecodeError as exc:
            return None, str(exc)

    def do_POST(self):
        if self.path not in ("/validate", "/save"):
            self._send(404, json.dumps({"ok": False, "error": "not found"}))
            return
        payload, err = self._read_json()
        if err is not None:
            self._send(400, json.dumps({"ok": False, "errors": ["bad JSON: " + err]}))
            return
        try:
            res = build_response(payload, out_path=self.out_path,
                                 do_write=(self.path == "/save"))
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
    print("Actuarial Input & Run GUI (Phase IGUI Task 2) serving at %s" % url)
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
    retur