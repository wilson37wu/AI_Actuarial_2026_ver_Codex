#!/bin/sh
# Phase IGUI Task 8 - one-click offline launcher (Linux).
# Starts the local Actuarial Input & Run GUI on 127.0.0.1 and opens your browser.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR" || exit 1
if command -v python3 >/dev/null 2>&1; then exec python3 scripts/launch_offline_gui.py "$@"; fi
if command -v python  >/dev/null 2>&1; then exec python  scripts/launch_offline_gui.py "$@"; fi
echo "Python 3.8+ not found. Install it and retry."
