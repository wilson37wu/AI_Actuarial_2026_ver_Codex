"""Guard: every inline <script> served by the Input & Run GUI must be
syntactically valid JavaScript.

Regression for the 2026-07-03 GUI-5 incident: a collapsed backslash escape
(``\\n`` -> real newline inside a JS string literal) made the whole page
script fail to parse, so the Save & RUN button silently did nothing. The
page LOOKED right; only a JS syntax check catches this class of bug.

jsdom-free (matching the repo's guard precedent): ``node --check`` over
every inline script extracted from every rendered GUI page. A tokenising
pure-Python fallback was rejected: JS string grammar cannot be checked
reliably with regexes (apostrophes inside double-quoted literals), and a
guard that cries wolf gets deleted.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_REPO, os.path.join(_REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from par_model_v2.viewer.igui_assumptions import render_assumptions_html
from par_model_v2.viewer.igui_calibration import render_calibration_html
from par_model_v2.viewer.igui_cashflows import render_cashflows_html
from par_model_v2.viewer.igui_esg import render_esg_html
from par_model_v2.viewer.igui_model_points import render_model_points_html
from par_model_v2.viewer.igui_run_controls import render_form_html
from par_model_v2.viewer.igui_run_execution import render_run_html
from par_model_v2.viewer.igui_run_history import render_history_html
from par_model_v2.viewer.igui_stress import render_stress_html
from par_model_v2.viewer.igui_validation_gating import render_gate_html

PAGES = {
    "run_controls": render_form_html,
    "model_points": render_model_points_html,
    "assumptions": render_assumptions_html,
    "esg": render_esg_html,
    "run_gate": render_gate_html,
    "run_execution": render_run_html,
    "stress": render_stress_html,
    "calibration": render_calibration_html,
    "history": render_history_html,
    "cashflows": render_cashflows_html,
}

_SCRIPT_RE = re.compile(r"<script>(.*?)</script>", re.S)


def _scripts(name):
    page = PAGES[name]()
    blocks = _SCRIPT_RE.findall(page)
    assert blocks, "page %s has no inline script" % name
    return blocks


class TestNodePresent(unittest.TestCase):
    """The node syntax check below is the real guard; this test makes its
    absence LOUD instead of a silent skip in environments that ship node
    (the dev sandbox and the packaging env both do)."""

    def test_node_available_or_documented(self):
        if shutil.which("node") is None:  # pragma: no cover
            self.skipTest("node not on PATH - syntax guard not enforceable "
                          "here; it runs in the dev/packaging environments")


@unittest.skipUnless(shutil.which("node"), "node not on PATH")
class TestNodeSyntaxCheck(unittest.TestCase):
    def test_all_pages_parse(self):
        for name in PAGES:
            for i, block in enumerate(_scripts(name)):
                with tempfile.NamedTemporaryFile(
                        "w", suffix=".js", delete=False) as fh:
                    fh.write(block)
                    path = fh.name
                try:
                    proc = subprocess.run(
                        ["node", "--check", path],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(
                        proc.returncode, 0,
                        "page %s script #%d: %s" % (name, i, proc.stderr))
                finally:
                    os.unlink(path)


if __name__ == "__main__":
    unittest.main()
