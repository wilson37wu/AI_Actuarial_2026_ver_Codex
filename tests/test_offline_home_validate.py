"""Offline-UI option (g) - pytest/unittest collection of the standing, stdlib
structural gate for the shipped offline_home.html landing page.

Background: scripts/build_offline_home_validate.py is a pure-standard-library
(no numpy/scipy/jsdom/node) gate that re-asserts, against the SHIPPED
offline_home.html + ui_data.json, that the offline landing surface is
self-contained (zero external refs), links every offline view, that every card
href resolves to a file that exists on disk, and that the GOVERNED headline
figures render verbatim. It was runnable only on demand. This wrapper COLLECTS
it into the existing pytest suite so the guarantee is re-checked automatically on
every test run, with no governed-artifact, contract, or runtime-JS change.

Pure stdlib, so it runs in any CI lane (no engine dependency)."""
import importlib.util
import io
import json
import os
import unittest
from contextlib import redirect_stdout

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
GATE = os.path.join(REPO, "scripts", "build_offline_home_validate.py")


def _load_gate():
    spec = importlib.util.spec_from_file_location("offline_home_validate_gate", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestOfflineHomeValidateGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = _load_gate()
        # main() prints a JSON report to stdout and returns 0 (all green) / 1.
        buf = io.StringIO()
        with redirect_stdout(buf):
            cls.rc = cls.gate.main()
        cls.report = json.loads(buf.getvalue())

    def test_gate_script_present(self):
        self.assertTrue(os.path.isfile(GATE), "missing %s" % GATE)

    def test_main_returns_zero(self):
        # The single contractual assertion required by option (g).
        self.assertEqual(self.rc, 0, "offline_home gate failed: %s" % self.report.get("failed"))

    def test_report_is_green(self):
        self.assertTrue(self.report["ok"], "gate not ok: %s" % self.report["failed"])
        self.assertEqual(self.report["failed"], [], "gate failures: %s" % self.report["failed"])

    def test_all_checks_passed(self):
        # Every emitted check must pass (passed == checks), and there must be a
        # non-trivial number of checks (the gate currently emits >= 20).
        self.assertEqual(self.report["passed"], self.report["checks"])
        self.assertGreaterEqual(self.report["checks"], 20)


if __name__ == "__main__":
    unittest.main()
