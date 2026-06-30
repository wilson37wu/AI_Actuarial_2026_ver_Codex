"""Offline-UI gate (W91) - pytest collection of the standalone-payload
section-digest recompute parity guard.

Background: offline_home.html consumes the STANDALONE ui_data.json (and lets the
user drag-drop a different ui_data.json snapshot). Its 26 top-level section
payloads are covered by a contract_manifest carrying per-section SHA-256
section_digests + a root_digest. Prior gates left one gap UNcovered:

  * scripts/ui_app_selftest_nojsdom.cjs (W83/W84, 40 checks) recomputes the 26
    digests from the payload EMBEDDED in ui_app.html - not the standalone file.
  * tests/test_ui_data_contract_manifest_digest.py (W89) pins the manifest's
    root_digest + the contract_version section digest by VALUE; structure.py
    (W90) pins manifest STRUCTURE - neither recomputes a section payload->digest
    from the standalone file.
  * the several `test_embedded_payload_matches_standalone` tests compare only the
    contract_manifest sub-object (root_digest + section_digests map), plus at
    most one individual section - never all 26 standalone section payloads.
  * scripts/build_offline_home_validate.py "recomputes nothing" (renders the
    governed figures verbatim); scripts/offline_home_loader_parity.cjs compares
    rendered FIGURES, not digests.

So a standalone ui_data.json whose section PAYLOAD drifted while its manifest
digests stayed byte-identical would pass every existing gate. W91 closes that:
scripts/ui_data_section_digest_recompute_parity.cjs recomputes all 26
section_digests + the root_digest DIRECTLY FROM THE STANDALONE ui_data.json,
two independent ways - (A) the page's OWN authoritative embedded serialiser
(_ciCanon/_ciSha256/_ciSectionDigests, extracted from ui_app.html and run over
the standalone data; a pure-Python recompute is infeasible because the recipe
uses JS-native String(Number) formatting) and (B) an independent node:crypto
recompute - and asserts parity with that file's own contract_manifest plus the
GOVERNED root_digest pin.

This thin wrapper COLLECTS the node guard into the pytest suite - exactly as
tests/test_ui_app_selftest_nojsdom.py collects the embedded-payload guard - so
the standalone-payload invariant is re-checked on every test run, with NO
governed-artifact, contract, or runtime-JS change. The guard is jsdom-FREE
(node-stdlib only: fs/path/crypto/vm), so the suite SKIPS (not fails) only when
a `node` binary is absent - mirroring tests/test_ui_app_selftest_nojsdom.py.
"""
import json
import os
import shutil
import subprocess

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_GUARD = os.path.join(_REPO, "scripts", "ui_data_section_digest_recompute_parity.cjs")
_DATA = os.path.join(_REPO, "ui_data.json")
_APP = os.path.join(_REPO, "ui_app.html")

# Governed baseline: the W91 guard emits exactly this many checks. The wrapper
# asserts >= this so a silently gutted guard (fewer checks) is caught while
# future additive checks do not break the gate.
_BASELINE_CHECKS = 22


@pytest.fixture(scope="module")
def guard_report():
    """Shell `node scripts/ui_data_section_digest_recompute_parity.cjs` once and
    return its parsed stdout JSON report. SKIP (not fail) when node is
    unavailable. No NODE_PATH / node_modules needed - the guard is jsdom-FREE."""
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
    # Exit 0 == every invariant held; the guard prints a single JSON object to
    # stdout either way. A non-zero exit is a hard failure here.
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")
    return json.loads(result.stdout)


def test_guard_script_present():
    assert os.path.isfile(_GUARD), "missing %s" % _GUARD


def test_standalone_data_present():
    assert os.path.isfile(_DATA), "missing %s" % _DATA


def test_recipe_source_present():
    assert os.path.isfile(_APP), "missing %s" % _APP


def test_guard_report_is_green(guard_report):
    # The single contractual assertion the guard exists to make.
    assert guard_report["ok"] is True, "guard not ok: %s" % guard_report.get("failed")
    assert guard_report["failed"] == [], "guard failures: %s" % guard_report["failed"]
    assert guard_report["data_file"] == "ui_data.json"
    assert guard_report["recipe_file"] == "ui_app.html"


def test_guard_all_checks_passed(guard_report):
    # Every emitted check passes, and the guard emits at least its governed
    # baseline count (catches a silently weakened guard).
    assert guard_report["passed"] == guard_report["checks"]
    assert guard_report["checks"] >= _BASELINE_CHECKS


if __name__ == "__main__":
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-v"]))
