#!/usr/bin/env python3
"""Phase PKG Task 2 (Option B) - unittest wrapper around the offline
vendored-wheels bootstrap structural gate. Stdlib only (no engine import)."""
from __future__ import annotations
import ast
import importlib.util
import os
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
BOOTSTRAP = os.path.join(REPO, "packaging", "offline_bootstrap.py")
VENDOR = os.path.join(REPO, "scripts", "vendor_wheels.py")
GATE = os.path.join(REPO, "scripts", "build_phase_pkg_task2b_validate.py")
README = os.path.join(REPO, "packaging", "OPTION_B_README.md")
EVIDENCE = os.path.join(REPO, "docs", "validation",
                        "PHASE_PKG_TASK2B_OFFLINE_WHEELHOUSE.json")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestOptionBOfflineWheelhouse(unittest.TestCase):
    def test_bootstrap_present_and_parses(self):
        self.assertTrue(os.path.exists(BOOTSTRAP))
        ast.parse(open(BOOTSTRAP, encoding="utf-8").read())

    def test_vendor_present_and_parses(self):
        self.assertTrue(os.path.exists(VENDOR))
        ast.parse(open(VENDOR, encoding="utf-8").read())

    def test_bootstrap_self_test_ok(self):
        bs = _load(BOOTSTRAP, "offline_bootstrap")
        self.assertTrue(bs.self_test()["ok"])

    def test_plan_forces_no_index_no_remote(self):
        bs = _load(BOOTSTRAP, "offline_bootstrap")
        argv = bs.plan_install(bs.DEFAULT_WHEELHOUSE, bs.DEFAULT_VENV)
        self.assertIn("--no-index", argv)
        self.assertIn("--find-links", argv)
        self.assertNotIn("--index-url", argv)
        joined = " ".join(argv)
        self.assertNotIn("http://", joined)
        self.assertNotIn("https://", joined)

    def test_vendor_print_argv_is_pip_download(self):
        v = _load(VENDOR, "vendor_wheels")
        argv = v.build_pip_download_argv(v.DEFAULT_DEST, v.DEFAULT_REQS)
        self.assertIn("download", argv)
        self.assertIn("-r", argv)
        self.assertIn(":all:", argv)

    def test_docs_present(self):
        self.assertTrue(os.path.exists(README))
        self.assertTrue(os.path.exists(EVIDENCE))

    def test_structural_gate_passes(self):
        gate = _load(GATE, "pkg_task2b_validate")
        checks = gate._checks()
        failed = [n for n, c, _ in checks if not c]
        self.assertEqual(failed, [], "gate failures: %s" % failed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
