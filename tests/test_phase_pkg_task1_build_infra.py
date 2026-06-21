"""Phase PKG Task 1 - pytest/unittest wrapper around the stdlib structural gate
for the Option-A frozen-binary build infrastructure. Pure standard library (no
numpy/scipy), so it runs in any CI lane."""
import importlib.util
import os
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
GATE = os.path.join(REPO, "scripts", "build_phase_pkg_task1_validate.py")


def _load_gate():
    spec = importlib.util.spec_from_file_location("pkg_task1_gate", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPhasePkgTask1BuildInfra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = _load_gate()
        cls.results = cls.gate._checks()
        cls.by_name = {n: (c, d) for n, c, d in cls.results}

    def test_gate_overall_green(self):
        failed = [n for n, c, _ in self.results if not c]
        self.assertEqual(failed, [], "structural gate failures: %s" % failed)

    def test_spec_present_and_parses(self):
        self.assertTrue(self.by_name["spec_present"][0])
        self.assertTrue(self.by_name["spec_parses"][0])

    def test_spec_targets_offline_launcher(self):
        self.assertTrue(self.by_name["spec_targets_launcher"][0])

    def test_workflow_is_manual_or_tag_only(self):
        self.assertTrue(self.by_name["workflow_manual_dispatch"][0])
        self.assertTrue(self.by_name["workflow_tag_trigger"][0])
        self.assertTrue(self.by_name["workflow_no_branch_push_trigger"][0])

    def test_workflow_three_os_matrix(self):
        self.assertTrue(self.by_name["workflow_three_os_matrix"][0])

    def test_workflow_smoke_tests_binary(self):
        self.assertTrue(self.by_name["workflow_smoke_tests_binary"][0])

    def test_ui_app_byte_unchanged(self):
        self.assertTrue(self.by_name["ui_app_byte_unchanged"][0])

    def test_governed_headline_present(self):
        self.assertTrue(self.by_name["governed_headline_present"][0])

    def test_docs_present(self):
        self.assertTrue(self.by_name["packaging_readme_present"][0])
        self.assertTrue(self.by_name["design_note_present"][0])


if __name__ == "__main__":
    unittest.main()
