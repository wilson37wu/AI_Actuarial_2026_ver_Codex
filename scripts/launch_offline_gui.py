#!/usr/bin/env python3
"""Phase IGUI Task 8 - ONE-CLICK offline launcher for the Actuarial Input & Run GUI.

A single, **standard-library-only** entry point a non-technical user can run
(double-click via the OS wrappers, or ``python3 scripts/launch_offline_gui.py``)
that:

  1. puts the repo on ``sys.path`` (so no install / ``pip`` / ``PYTHONPATH`` setup
     is needed),
  2. starts the local input+run GUI (``scripts/run_gui.py``) bound to
     ``127.0.0.1`` ONLY (never a wildcard; no outbound network),
  3. opens the default browser at the GUI,
  4. reports, up front, whether the numpy/scipy **model engine** is importable --
     because the GUI + the offline RESULTS UI are pure stdlib, but the *compute*
     step (``/execute`` -> ``scripts/run_model.py``) needs the engine. The launcher
     never installs anything; it just tells the user what they have.

After the user supplies inputs and presses Run, the runner refreshes a USER copy
of the offline RESULTS UI (``user_results/ui_app_user.html``) from that run and
exposes it at ``/my-results`` -- the committed zero-install ``ui_app.html`` is
left byte-for-byte unchanged.

Packaging note (reasonable autonomous choice, documented): a fully self-contained
*frozen binary* (PyInstaller) or *vendored wheels* would remove even the Python
prerequisite, but building one needs offline build tooling/network that this
sandboxed dev cycle deliberately avoids. The launcher therefore targets the
**zero-configuration** experience on a machine that already has Python 3.8+ (the
common case): no install, no env vars, one command, one button. Engine presence
is detected and disclosed rather than auto-installed.
"""
from __future__ import annotations

import argparse
import os
import socket
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_REPO, "scripts")


def _ensure_path() -> None:
    for p in (_REPO, _SCRIPTS):
        if p not in sys.path:
            sys.path.insert(0, p)


def engine_status() -> dict:
    """Report whether the out-of-process model engine deps are importable.

    The GUI/runner/RESULTS-UI layers never import these; only the compute child
    (``scripts/run_model.py``) does. We import-probe WITHOUT requiring them so the
    launcher works for input entry + browsing even on a bare-Python machine.
    """
    have = {}
    for mod in ("numpy", "scipy"):
        try:
            __import__(mod)
            have[mod] = True
        except Exception:
            have[mod] = False
    return {"engine_ready": all(have.values()), "modules": have}


def _free_port(preferred: int) -> int:
    """Return ``preferred`` if bindable on localhost, else an OS-assigned free port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", preferred))
        s.close()
        return preferred
    except OSError:
        s.close()
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.bind(("127.0.0.1", 0))
        port = s2.getsockname()[1]
        s2.close()
        return port


def build_launch_plan(port: int = 8765, out: str = "model_inputs.json") -> dict:
    """Resolve the launch parameters WITHOUT starting a server (unit-testable)."""
    _ensure_path()
    resolved = _free_port(port)
    return {
        "host": "127.0.0.1",
        "port": resolved,
        "url": "http://127.0.0.1:%d/" % resolved,
        "out_path": out if os.path.isabs(out) else os.path.join(_REPO, out),
        "engine": engine_status(),
        "repo": _REPO,
    }


def launch(port: int = 8765, out: str = "model_inputs.json",
           open_browser: bool = True) -> int:
    _ensure_path()
    import run_gui  # the stdlib local runner (Task 2-7)

    plan = build_launch_plan(port, out)
    srv = run_gui.make_server(plan["port"], plan["out_path"])
    host, real_port = srv.server_address
    url = "http://%s:%d/" % (host, real_port)

    print("=" * 64)
    print(" Actuarial Input & Run GUI  --  one-click offline launcher")
    print("=" * 64)
    print(" Open in your browser:   %s" % url)
    print(" Input pages:            run controls / model points / assumptions /")
    print("                         ESG / validation gate / end-to-end run")
    print(" Your own results:       %smy-results  (after you press Run)" % url)
    eng = plan["engine"]
    if eng["engine_ready"]:
        print(" Model engine:           READY (numpy + scipy present) -- you can")
        print("                         supply inputs AND compute end-to-end.")
    else:
        missing = ", ".join(m for m, ok in eng["modules"].items() if not ok)
        print(" Model engine:           input entry + browsing work now; the COMPUTE")
        print("                         step needs: %s" % missing)
        print("                         (install once: pip install numpy scipy)")
    print(" Localhost only, fully offline. Press Ctrl+C to stop.")
    print("=" * 64)

    if open_browser:
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8765,
                    help="preferred localhost port (auto-falls-back if busy)")
    ap.add_argument("--out", default="model_inputs.json",
                    help="model_inputs.json path the GUI writes")
    ap.add_argument("--no-browser", action="store_true",
                    help="do not open a browser (server still starts)")
    ap.add_argument("--self-test", action="store_true",
                    help="resolve the launch plan + engine status; start nothing")
    a = ap.parse_args(argv)
    if a.self_test:
        import json
        plan = build_launch_plan(a.port, a.out)
        ok = (plan["host"] == "127.0.0.1" and isinstance(plan["port"], int)
              and plan["url"].startswith("http://127.0.0.1:")
              and "engine" in plan)
        plan["self_test_ok"] = bool(ok)
        print(json.dumps(plan, indent=1))
        return 0 if ok else 1
    return launch(a.port, a.out, open_browser=not a.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
