#!/usr/bin/env python3
"""Phase PKG Task 2 (Option B) - fully-OFFLINE vendored-wheels venv bootstrap.

Option B of docs/PHASE_IGUI_PACKAGING_OPTIONS_CARD.md: instead of shipping a
frozen binary (Option A) or asking the user to `pip install` from PyPI (Option C),
we vendor the EXACT pinned wheels into a local ``wheelhouse/`` and install them
into a throw-away virtual environment with **no network access at all**
(``pip install --no-index --find-links <wheelhouse>``). The user then has the
numpy/pandas/scipy COMPUTE engine without ever reaching the internet and without a
global install.

This module is **standard-library only** so it runs on a bare-Python machine. It
NEVER reaches the network: every install it plans is forced ``--no-index`` against
a local ``--find-links`` directory. The ONE step that does need the network -
harvesting the wheels into ``wheelhouse/`` - is a separate, owner/CI-run script
(``scripts/vendor_wheels.py``); it is deliberately NOT performed here.

Separation of layers (unchanged from the launcher):
  * Input GUI + validation/gating + offline RESULTS UI -> pure stdlib, need NOTHING.
  * COMPUTE engine (``scripts/run_model.py``)            -> numpy/pandas/scipy.
This bootstrap only provisions the second layer, fully offline.

CLI
    python3 packaging/offline_bootstrap.py --self-test        # offline guarantee gate
    python3 packaging/offline_bootstrap.py --plan-only        # print the pip argv, do nothing
    python3 packaging/offline_bootstrap.py --wheelhouse wheelhouse --venv .venv_engine

Exit 0 on success; non-zero on failure. ``--self-test`` proves the planned install
can never touch a remote index and exits WITHOUT creating a venv or installing.
"""
from __future__ import annotations

import argparse
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DEFAULT_WHEELHOUSE = os.path.join(REPO, "wheelhouse")
DEFAULT_VENV = os.path.join(REPO, ".venv_engine")
PINNED_REQUIREMENTS = os.path.join(REPO, "requirements-engine-lock.txt")
ENGINE_MODULES = ("numpy", "pandas", "scipy")


def plan_install(wheelhouse: str, venv_dir: str) -> list[str]:
    """Return the EXACT pip argv used to install the engine offline.

    The command is forced ``--no-index`` (never consult PyPI / any remote index)
    and ``--find-links <wheelhouse>`` (resolve only from the local vendored wheels),
    against the pinned ``requirements-engine-lock.txt``. The presence of
    ``--no-index`` is the offline guarantee that ``--self-test`` asserts.
    """
    py = os.path.join(venv_dir, "Scripts" if os.name == "nt" else "bin",
                      "python.exe" if os.name == "nt" else "python")
    return [
        py, "-m", "pip", "install",
        "--no-index",
        "--no-build-isolation",
        "--find-links", wheelhouse,
        "-r", PINNED_REQUIREMENTS,
    ]


def wheelhouse_status(wheelhouse: str) -> dict:
    """Report, WITHOUT installing, whether the local wheelhouse looks usable."""
    exists = os.path.isdir(wheelhouse)
    wheels = sorted(f for f in os.listdir(wheelhouse)) if exists else []
    whl = [w for w in wheels if w.endswith(".whl")]
    have = {m: any(w.lower().startswith(m + "-") for w in whl) for m in ENGINE_MODULES}
    return {
        "wheelhouse": wheelhouse,
        "exists": exists,
        "wheel_count": len(whl),
        "engine_wheels_present": have,
        "ready": exists and all(have.values()),
        "pinned_requirements": PINNED_REQUIREMENTS,
        "vendor_step": "scripts/vendor_wheels.py (owner/CI-run; the ONLY networked step)",
    }


def self_test() -> dict:
    """Prove the offline guarantee without creating a venv or installing anything.

    Asserts that the planned pip argv (a) forces ``--no-index``, (b) resolves only
    from a local ``--find-links`` directory, (c) targets the pinned requirements,
    and (d) contains no ``http(s)://`` / index-url token. Pure introspection.
    """
    checks: list[tuple[str, bool, str]] = []

    def chk(name: str, cond: bool, detail: str = "") -> None:
        checks.append((name, bool(cond), detail))

    argv = plan_install(DEFAULT_WHEELHOUSE, DEFAULT_VENV)
    joined = " ".join(argv)
    chk("forces_no_index", "--no-index" in argv)
    chk("uses_find_links", "--find-links" in argv)
    chk("targets_pinned_requirements", PINNED_REQUIREMENTS.endswith(
        "requirements-engine-lock.txt") and "-r" in argv)
    chk("no_remote_url_in_plan",
        ("http://" not in joined) and ("https://" not in joined))
    chk("no_index_url_flag", "--index-url" not in argv and "-i" not in argv)
    chk("stdlib_only_import", "scipy" not in sys.modules and "numpy" not in sys.modules)
    chk("pinned_requirements_referenced", os.path.basename(PINNED_REQUIREMENTS)
        == "requirements-engine-lock.txt")
    ok = all(c for _, c, _ in checks)
    return {"ok": ok, "checks": [{"name": n, "ok": c, "detail": d}
                                 for n, c, d in checks],
            "planned_pip_argv": argv}


def bootstrap(wheelhouse: str, venv_dir: str) -> int:
    """Create the venv and install the engine fully offline from the wheelhouse."""
    import subprocess
    import venv as _venv

    st = wheelhouse_status(wheelhouse)
    if not st["ready"]:
        sys.stderr.write(
            "wheelhouse not ready: %s\nRun scripts/vendor_wheels.py first (the one "
            "networked step) to populate it.\n" % st)
        return 2
    print("Creating virtual environment at %s ..." % venv_dir)
    _venv.EnvBuilder(with_pip=True, clear=False).create(venv_dir)
    argv = plan_install(wheelhouse, venv_dir)
    print("Installing pinned engine OFFLINE: %s" % " ".join(argv))
    rc = subprocess.call(argv)
    if rc != 0:
        sys.stderr.write("offline install failed (rc=%d)\n" % rc)
        return rc
    print("Engine installed offline. Activate the venv, then run the launcher.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline vendored-wheels engine bootstrap (Option B)")
    ap.add_argument("--wheelhouse", default=DEFAULT_WHEELHOUSE)
    ap.add_argument("--venv", default=DEFAULT_VENV)
    ap.add_argument("--self-test", action="store_true",
                    help="prove the offline guarantee and exit (no venv/install)")
    ap.add_argument("--plan-only", action="store_true",
                    help="print the pip argv and wheelhouse status, then exit")
    ap.add_argument("--status", action="store_true",
                    help="print wheelhouse status and exit")
    args = ap.parse_args(argv)

    if args.self_test:
        import json
        res = self_test()
        print(json.dumps(res, indent=1))
        return 0 if res["ok"] else 1
    if args.status:
        import json
        print(json.dumps(wheelhouse_status(args.wheelhouse), indent=1))
        return 0
    if args.plan_only:
        import json
        print(json.dumps({
            "wheelhouse_status": wheelhouse_status(args.wheelhouse),
            "planned_pip_argv": plan_install(args.wheelhouse, args.venv),
        }, indent=1))
        return 0
    return bootstrap(args.wheelhouse, args.venv)


if __name__ == "__main__":
    raise SystemExit(main())
