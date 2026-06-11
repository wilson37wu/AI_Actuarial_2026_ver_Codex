#!/usr/bin/env python3
"""Rebuild the offline GUI (ui_app.html) from the current model results.

Thin user-facing wrapper around the governed bundler
``scripts/build_ui_data.py`` (Layer B in the user manual): it scans the
result files written by the calculation engine, normalises them into the
``ui_data.json`` contract and embeds the snapshot into the self-contained
``ui_app.html`` at the repository root. Display only - no calculation.

Usage:  python3 production_run/build_gui.py
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    import os
    os.chdir(REPO_ROOT)        # the bundler expects repo-root relative paths
    print("Rebuilding ui_data.json + ui_app.html from current results...")
    runpy.run_path(str(REPO_ROOT / "scripts" / "build_ui_data.py"),
                   run_name="__main__")
    print("Done. Open ui_app.html (repo root) in any browser - fully offline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
