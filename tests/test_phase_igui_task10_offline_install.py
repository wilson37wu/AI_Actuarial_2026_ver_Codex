#!/usr/bin/env python3
"""Phase IGUI Task 10 - unit gate for the Option-C offline-install appendix + pinned
engine requirements. STDLIB-only; reads committed artifacts; does NOT mutate the
governance store (governance application is exercised idempotently on an in-memory
copy)."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
_SCRIPTS = os.path.join(_REPO, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import build_phase_igui_task10_offline_install as T10  # noqa: E402
from par_model_v2.governance.audit_trail import GovernanceStore  # noqa: E402


class TestPinnedRequirements(unittest.TestCase):
    def test_lock_file_exists(self):
        self.assertTrue(T10.LOCK.exists())

    def test_pins_parse_to_expected(self):
        pins = T10.parse_pins(T10.LOCK.read_text(encoding="utf-8"))
        self.assertEqual(pins, T10.EXPECTED_PINS)

    def test_pins_within_requirements_ranges(self):
        pins = T10.parse_pins(T10.LOCK.read_text(encoding="utf-8"))
        ranges = T10.parse_ranges(T10.REQS.read_text(encoding="utf-8"))
        for pkg, ver in pins.items():
            self.assertIn(pkg, ranges, pkg)
            lo, hi = ranges[pkg]
            self.assertTrue(T10._in_range(ver, lo, hi),
                            "%s==%s not in [%s,%s)" % (pkg, ver, lo, hi))

    def test_range_parser_rejects_pins(self):
        # a pin line must not be misread as a range
        self.assertEqual(T10.parse_ranges("numpy==1.26.4\n"), {})

    def test_in_range_boundaries(self):
        self.assertTrue(T10._in_range("1.26.4", "1.26", "3.0"))
        self.assertFalse(T10._in_range("3.0.0", "1.26", "3.0"))   # upper exclusive
        self.assertTrue(T10._in_range("1.26.0", "1.26", "3.0"))    # lower inclusive


class TestAppendix(unittest.TestCase):
    def setUp(self):
        self.text = T10.APPENDIX.read_text(encoding="utf-8")

    def test_exists_and_refs_lock(self):
        self.assertIn("requirements-engine-lock.txt", self.text)

    def test_refs_packaging_card_and_is_decision_neutral(self):
        self.assertIn("PHASE_IGUI_PACKAGING_OPTIONS_CARD", self.text)
        self.assertIn("pre-empt", self.text.lower())
        self.assertIn("Option A", self.text)
        self.assertIn("Option B", self.text)

    def test_carries_headline_and_committed_ui_sha(self):
        self.assertIn(T10.HEADLINE, self.text.replace(",", ""))
        self.assertIn(T10.UI_APP_BASELINE_SHA, self.text)

    def test_no_stray_non_ascii(self):
        self.text.encode("ascii")  # raises if any non-ascii crept in


class TestDisclosureWiring(unittest.TestCase):
    def test_launcher_discloses_pinned_reqs_and_appendix(self):
        s = T10.LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("requirements-engine-lock.txt", s)
        self.assertIn("PHASE_IGUI_OFFLINE_INSTALL_APPENDIX", s)

    def test_engine_status_modules_set_unchanged(self):
        import launch_offline_gui as L
        st = L.engine_status()
        self.assertEqual(set(st["modules"]), {"numpy", "scipy"})
        # new pointers present, decision-actionable
        self.assertEqual(st["pinned_requirements"], "requirements-engine-lock.txt")
        self.assertIn("PHASE_IGUI_OFFLINE_INSTALL_APPENDIX", st["install_appendix"])
        self.assertIn("requirements-engine-lock.txt", st["compute_install_hint"])

    def test_launch_plan_still_localhost(self):
        import launch_offline_gui as L
        plan = L.build_launch_plan(0, "model_inputs.json")
        self.assertEqual(plan["host"], "127.0.0.1")
        self.assertIn("numpy", plan["engine"]["modules"])

    def test_readme_links_both_docs(self):
        s = T10.LAUNCHER_README.read_text(encoding="utf-8")
        self.assertIn("PHASE_IGUI_OFFLINE_INSTALL_APPENDIX", s)
        self.assertIn("PHASE_IGUI_PACKAGING_OPTIONS_CARD", s)


class TestGate(unittest.TestCase):
    def test_gate_passes(self):
        gate = T10.validate_task10_gate()
        self.assertTrue(gate["ok"], json.dumps(gate["checks"], indent=1))
        self.assertGreaterEqual(gate["n_checks"], 16)

    def test_ui_app_byte_unchanged(self):
        gate = T10.validate_task10_gate()
        self.assertTrue(gate["checks"]["ui_app_byte_unchanged"])


class TestGovernanceIdempotent(unittest.TestCase):
    """Exercise apply_governance on an IN-MEMORY store copy (never writes the file)."""
    def test_apply_then_idempotent(self):
        store = GovernanceStore.from_json(T10.GOV_PATH.read_text(encoding="utf-8"))
        gate = T10.validate_task10_gate()
        summary = T10.build_summary(store, gate)
        before = len(store.change_records)
        r1 = T10.apply_governance(store, summary, gate)
        # either freshly added here, or already present from the committed cycle
        if r1.get("added"):
            self.assertEqual(len(store.change_records), before + 1)
            self.assertTrue(store.audit_trail.verify_all())
        r2 = T10.apply_governance(store, summary, gate)
        self.assertFalse(r2["added"])
        self.assertEqual(r2.get("reason"), "idempotent")


if __name__ == "__main__":
    unittest.main()
