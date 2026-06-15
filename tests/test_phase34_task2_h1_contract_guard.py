"""Tests for Phase 34 Task 2 (gap H1) - data-contract guard + integrity panel.

The gate runs LIVE cross-checks on the rebuilt artifacts (ui_data.json +
ui_app.html), so it stays green against the post-H1 repo. Also asserts the
ADDITIVE-only contract bump (1.17.0 -> 1.18.0: contract_manifest is the only
new top-level key) and that the manifest is self-describing.
"""

import json
import os
import unittest

from par_model_v2.viewer.contract_guard import (
    DOC_ID,
    DOC_VERSION,
    EXPECTED_CONTRACT,
    EXPECTED_REQUIRED_KEYS,
    GOVERNED_HEADLINE,
    PRIOR_CONTRACT,
    validate_h1,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestContractGuardGate(unittest.TestCase):
    def test_gate_passes_against_repo(self):
        gate = validate_h1(REPO)
        self.assertTrue(gate["ok"], gate["checks"])
        self.assertGreaterEqual(gate["n_checks"], 20)

    def test_identity(self):
        self.assertEqual(DOC_ID, "PHASE34_TASK2_H1_CONTRACT_GUARD")
        self.assertEqual(DOC_VERSION, "1.0.0")
        self.assertEqual(PRIOR_CONTRACT, "1.21.0")
        self.assertEqual(EXPECTED_CONTRACT, "1.22.0")

    def test_gate_fails_when_manifest_missing(self):
        # Tamper a copy of ui_data.json (in-memory) by re-validating logic:
        # remove the manifest from the parsed payload and re-run the relevant
        # checks via a temporary repo dir.
        import tempfile, shutil
        with open(os.path.join(REPO, "ui_data.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        data.pop("contract_manifest", None)
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(REPO, "ui_app.html"), os.path.join(d, "ui_app.html"))
            with open(os.path.join(d, "ui_data.json"), "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            gate = validate_h1(d)
        self.assertFalse(gate["ok"])
        self.assertFalse(gate["checks"]["manifest_present"])


class TestManifestContent(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(REPO, "ui_data.json"), encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_contract_bumped_additively(self):
        self.assertEqual(self.data["contract_version"], EXPECTED_CONTRACT)
        new_keys = set(self.data.keys()) - set(EXPECTED_REQUIRED_KEYS)
        self.assertEqual(new_keys, {"contract_manifest"})

    def test_manifest_self_describing(self):
        man = self.data["contract_manifest"]
        self.assertEqual(man["expected_contract_version"], EXPECTED_CONTRACT)
        self.assertEqual(list(man["required_top_level_keys"]), EXPECTED_REQUIRED_KEYS)
        self.assertNotIn("contract_manifest", man["required_top_level_keys"])
        self.assertEqual(man["key_count"], len(man["required_top_level_keys"]))

    def test_every_required_key_present(self):
        man = self.data["contract_manifest"]
        for k in man["required_top_level_keys"]:
            self.assertIn(k, self.data)

    def test_governed_headline_preserved(self):
        self.assertIn(GOVERNED_HEADLINE, json.dumps(self.data))


if __name__ == "__main__":
    unittest.main()
