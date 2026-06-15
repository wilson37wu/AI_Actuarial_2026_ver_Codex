#!/usr/bin/env python3
"""Phase PKG Task 2 (Option B) - vendor the pinned engine wheels into wheelhouse/.

This is the SINGLE networked step of Option B (offline vendored-wheels install).
An owner or a CI job runs it ONCE on a networked machine to harvest the exact
pinned wheels (numpy/pandas/scipy + transitive deps) for the target platform(s)
into a local ``wheelhouse/`` directory. Thereafter packaging/offline_bootstrap.py
installs them with ``--no-index`` - no further network, ever.

It is standard-library only and a THIN, auditable wrapper over ``pip download``;
it never imports the engine and changes no model artifact. It is deliberately NOT
run inside the autonomous dev sandbox (which has no outbound network), mirroring
the way Option A's per-OS binary is built in CI, not in-cycle.

Typical use (run on a networked machine with the SAME OS/python as the target):
    python3 scripts/vendor_wheels.py
    python3 scripts/vendor_wheels.py --dest wheelhouse --requirements requirements-engine-lock.txt

Cross-platform harvest (one wheelhouse per target) - see --platform/--python-version
passthrough, which forwards pip's own flags so a CI matrix can build mac/win/linux
wheelhouses from one runner.
"""
from __future__ import annotations

import argparse
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DEFAULT_DEST = os.path.join(REPO, "wheelhouse")
DEFAULT_REQS = os.path.join(REPO, "requirements-engine-lock.txt")


def build_pip_download_argv(dest: str, requirements: str,
                            platform: str | None = None,
                            python_version: str | None = None,
                            only_binary: bool = True) -> list[str]:
    """Return the EXACT ``pip download`` argv used to populate the wheelhouse."""
    argv = [sys.executable, "-m", "pip", "download",
            "-r", requirements, "-d", dest]
    if only_binary:
        # wheels only -> a pure --no-index install later (no source builds offline)
        argv += ["--only-binary", ":all:"]
    if platform:
        argv += ["--platform", platform]
    if python_version:
        argv += ["--python-version", python_version]
    return argv


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Vendor pinned engine wheels (Option B; networked)")
    ap.add_argument("--dest", default=DEFAULT_DEST)
    ap.add_argument("--requirements", default=DEFAULT_REQS)
    ap.add_argument("--platform", default=None,
                    help="pip --platform tag, e.g. manylinux2014_x86_64 / win_amd64 / macosx_11_0_arm64")
    ap.add_argument("--python-version", default=None, help="pip --python-version, e.g. 312")
    ap.add_argument("--allow-sdist", action="store_true",
                    help="permit source distributions (default: wheels only)")
    ap.add_argument("--print-argv", action="store_true",
                    help="print the pip download argv and exit (no network) - used by the gate")
    args = ap.parse_args(argv)

    pip_argv = build_pip_download_argv(
        args.dest, args.requirements, args.platform, args.python_version,
        only_binary=not args.allow_sdist)

    if args.print_argv:
        import json
        print(json.dumps({"pip_download_argv": pip_argv,
                          "dest": args.dest,
                          "requirements": args.requirements}, indent=1))
        return 0

    os.makedirs(args.dest, exist_ok=True)
    print("Vendoring wheels (NETWORKED): %s" % " ".join(pip_argv))
    import subprocess
    rc = subprocess.call(pip_argv)
    if rc != 0:
        sys.stderr.write("pip download failed (rc=%d)\n" % rc)
        return rc
    print("Wheelhouse populated at %s. Now run packaging/offline_bootstrap.py "
          "fully offline." % args.dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
