"""Offline-UI gate (W85) - pytest collection of the jsdom-FREE offline_home loader-parity guard.

Background: scripts/offline_home_loader_parity.cjs is a jsdom-FREE,
node-stdlib-only (fs/path; zero third-party deps) guard that proves the
in-page JS figure-extraction ("loader") path baked into the shipped
offline_home.html reproduces the GOVERNED figures the Python builder
(scripts/build_offline_home.py LOADER_JS) emits by default, when both read the
same ui_data.json. It re-derives every headline/capital/summary figure in JS,
compares each against the value baked into the built HTML's `.fv` spans, and
pins the governed headline (39,975.65). It is the offline_home counterpart to
the ui_app guard collected in W84.

That guard was runnable only on demand. This thin wrapper COLLECTS it into the
pytest suite - exactly as tests/test_ui_app_selftest_nojsdom.py (W84) collects
the ui_app guard and tests/test_offline_home_validate.py collects the stdlib
structural gate - so the offline_home loader-parity invariant is re-checked
automatically on every test run, with NO governed-artifact, contract, or
runtime-JS change. Because the guard is jsdom-FREE it runs in the offline
auto-cycle sandbox (no node_modules required); the only environmental
prerequisite is a `node` binary, so the suite SKIPS (not fails) when node is
absent - the stdlib Python gates still provide coverage in that lane. The
node-subprocess + skip-when-absent shape mirrors tests/test_offline_viewer.py
and tests/test_ui_app_selftest_nojsdom.py.
"""
import json
import os
import shutil
import subprocess

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_GUARD = os.path.join(_REPO, "scripts", "offline_home_loader_parity.cjs")
_TARGET = os.path.join(_REPO, "offline_home.html")
_DATA = os.path.join(_REPO, "ui_data.json")

# Governed baseline: the guard emits exactly this many checks
# (1 "baked has >=8 figure values" + 8 per-figure JS==baked + 1 governed
# headline present = 10). The wrapper asserts >= this so a silently gutted
# guard (fewer checks) is caught while future additive checks do not break the
# gate.
_BASELINE_CHECKS = 10


@pytest.fixture(scope="module")
def guard_report():
    """Shell `node scripts/offline_home_loader_parity.cjs` once and return its
    parsed stdout JSON report. SKIP (not fail) when node is unavailable. No
    NODE_PATH / node_modules needed - the guard is jsdom-FREE (node-stdlib
    only), which is the whole point of this companion gate."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available")
    result = subprocess.run(
        [node, _GUARD],
        cwd=_REPO,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    # Exit 0 == all invariants held; the guard prints a single JSON object to
    # stdout either way. A non-zero exit is a hard failure here (this guard has
    # no optional-dependency escape hatch).
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")
    return json.loads(result.stdout)


def test_guard_script_present():
    assert os.path.isfile(_GUARD), "missing %s" % _GUARD


def test_target_html_present():
    assert os.path.isfile(_TARGET), "missing %s" % _TARGET


def test_data_payload_present():
    # The guard cross-reads ui_data.json (the JS-extraction source of truth);
    # without it the parity check is vacuous.
    assert os.path.isfile(_DATA), "missing %s" % _DATA


def test_guard_report_is_green(guard_report):
    # The single contractual assertion the guard exists to make: the in-page
    # JS loader reproduces every governed baked figure (failed list empty).
    assert guard_report["ok"] is True, "guard not ok: %s" % guard_report.get("failed")
    assert guard_report["failed"] == [], "guard failures: %s" % guard_report["failed"]


def test_guard_all_checks_passed(guard_report):
    # Every emitted check passes, and the guard emits at least its governed
    # baseline count (catches a silently weakened guard).
    assert guard_report["passed"] == guard_report["checks"]
    assert guard_report["checks"] >= _BASELINE_CHECKS


if __name__ == "__main__":
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-v"]))
