"""Offline-UI gate (W84) - pytest collection of the jsdom-FREE ui_app self-test.

Background: scripts/ui_app_selftest_nojsdom.cjs (added W83) is a jsdom-FREE,
node-stdlib-only (fs/path/crypto/vm; zero third-party deps) companion guard for
the shipped ui_app.html. It asserts the governance-critical, DOM-independent
invariants of ui_app.html - (1) zero external references in the executable
HTML/CSS/JS surface, (2) the embedded ui_data payload carries the GOVERNED
contract version 1.23.0 and headline 39975.654628199336, (3) all 21 governed
panel anchor ids are present and the panel count matches baseline, and (4)
dual-path content-integrity (the page's own embedded SHA-256 + section-digest
helpers reproduce the build-time contract_manifest, cross-checked by an
independent node:crypto recompute). Layout/click assertions intentionally stay
in the jsdom path (scripts/ui_app_self_test.cjs, owner/CI-gated).

That guard was runnable only on demand. This thin wrapper COLLECTS it into the
pytest suite - exactly as tests/test_offline_home_validate.py collects the
stdlib structural gate - so the ui_app.html invariants are re-checked
automatically on every test run, with NO governed-artifact, contract, or
runtime-JS change. Because the guard is jsdom-FREE it runs in the offline
auto-cycle sandbox (no node_modules required); the only environmental
prerequisite is a `node` binary, so the suite SKIPS (not fails) when node is
absent - the stdlib Python gates still provide coverage in that lane. The
node-subprocess + skip-when-absent shape mirrors tests/test_offline_viewer.py.
"""
import json
import os
import shutil
import subprocess

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_GUARD = os.path.join(_REPO, "scripts", "ui_app_selftest_nojsdom.cjs")
_TARGET = os.path.join(_REPO, "ui_app.html")

# Governed baseline: the W83 guard emits exactly this many checks. The wrapper
# asserts >= this so a silently gutted guard (fewer checks) is caught while
# future additive checks do not break the gate.
_BASELINE_CHECKS = 40


@pytest.fixture(scope="module")
def guard_report():
    """Shell `node scripts/ui_app_selftest_nojsdom.cjs` once and return its
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
    # stdout either way. A non-zero exit is a hard failure here (unlike the
    # jsdom path, this guard has no optional-dependency escape hatch).
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")
    return json.loads(result.stdout)


def test_guard_script_present():
    assert os.path.isfile(_GUARD), "missing %s" % _GUARD


def test_target_html_present():
    assert os.path.isfile(_TARGET), "missing %s" % _TARGET


def test_guard_report_is_green(guard_report):
    # The single contractual assertion the guard exists to make.
    assert guard_report["ok"] is True, "guard not ok: %s" % guard_report.get("failed")
    assert guard_report["failed"] == [], "guard failures: %s" % guard_report["failed"]
    assert guard_report["file"] == "ui_app.html"


def test_guard_all_checks_passed(guard_report):
    # Every emitted check passes, and the guard emits at least its governed
    # baseline count (catches a silently weakened guard).
    assert guard_report["passed"] == guard_report["checks"]
    assert guard_report["checks"] >= _BASELINE_CHECKS


if __name__ == "__main__":
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-v"]))
