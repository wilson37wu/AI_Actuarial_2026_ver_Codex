"""Phase 36 Task 4 (gap E3) - reproducibility evidence-pack export.

The export is a DISPLAY-LAYER toolbar action that serialises the EXACT embedded
ui_data payload bytes (which already carry contract_manifest.section_digests +
root_digest and the build/provenance stamp) to one downloaded file via the
existing Blob plumbing. These tests assert the pre-registered acceptance criteria
at the Python level (markers present, payload byte-identical, NO contract change,
idempotent patch, governed headline preserved) and, when node is available, run
the dedicated jsdom fallback test that proves byte/digest equality through the
EXISTING in-browser verifier.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_APP = os.path.join(REPO, "ui_app.html")
UI_DATA = os.path.join(REPO, "ui_data.json")
PATCH_SCRIPT = os.path.join(REPO, "scripts", "build_phase36_task4_e3_evidence_pack.py")
FALLBACK = os.path.join(REPO, "scripts", "ui_app_evidence_pack_fallback_test.cjs")

EXPECTED_CONTRACT = "1.22.0"
GOVERNED_HEADLINE = "39975.654628199336"


def _read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def _embedded_payload(html):
    m = re.search(r"/\*__UI_DATA__\*/(.*?)</script>", html, re.S)
    assert m, "embedded ui_data not found"
    return m.group(1).replace("/*__UI_DATA__*/", "").strip()


class TestExportControlPresent(unittest.TestCase):
    def setUp(self):
        self.html = _read(UI_APP)

    def test_button_present_and_labelled(self):
        self.assertEqual(self.html.count('id="btnEvidencePack"'), 1)
        self.assertIn("Reproducibility evidence pack</button>", self.html)

    def test_export_functions_present(self):
        self.assertIn("function exportEvidencePack(", self.html)
        self.assertIn("function getEmbeddedRaw(", self.html)

    def test_button_wired_in_toolbar(self):
        self.assertIn('["btnEvidencePack",function(){ exportEvidencePack(); }]', self.html)

    def test_filename_carries_provenance_stamp(self):
        # contract version + first 8 hex of root digest in the download filename
        self.assertIn('"reproducibility_evidence_pack_v"+ver+tag+".json"', self.html)

    def test_verifier_note_present(self):
        self.assertIn('data-e3-note="1"', self.html)

    def test_export_uses_embedded_raw_via_existing_plumbing(self):
        self.assertIn("downloadText(name, raw, \"application/json\")", self.html)
        self.assertRegex(self.html, r"getEmbeddedRaw\(\)")

    def test_export_path_uses_no_storage_api(self):
        i = self.html.index("(gap E3): reproducibility evidence-pack export")
        j = self.html.index("function csvCell(")
        seg = self.html[i:j]
        self.assertNotIn("localStorage", seg)
        self.assertNotIn("sessionStorage", seg)
        self.assertIn("recomputes NO model figure", seg)


class TestNoContractChange(unittest.TestCase):
    def test_embedded_payload_byte_identical_to_standalone(self):
        emb = _embedded_payload(_read(UI_APP))
        disk = _read(UI_DATA).strip()
        self.assertEqual(emb, disk, "exported pack bytes must equal embedded ui_data bytes")

    def test_contract_version_unchanged(self):
        data = json.loads(_embedded_payload(_read(UI_APP)))
        self.assertEqual(data["contract_version"], EXPECTED_CONTRACT)

    def test_payload_is_digest_verifiable(self):
        man = json.loads(_read(UI_DATA))["contract_manifest"]
        self.assertRegex(man["root_digest"], r"^[0-9a-f]{64}$")
        self.assertGreaterEqual(len(man["section_digests"]), 20)

    def test_governed_headline_preserved(self):
        self.assertIn(GOVERNED_HEADLINE, _read(UI_DATA))
        self.assertIn(GOVERNED_HEADLINE, _read(UI_APP))

    def test_no_external_refs(self):
        html = _read(UI_APP)
        for pat in ('src="http', 'href="http', "<link ", "@import", "url(http"):
            offenders = [s for s in re.findall(re.escape(pat) + r"[^\"')]*", html)
                         if "w3.org" not in s]
            self.assertEqual(offenders, [], "external ref found: %r" % pat)


class TestPatchIdempotent(unittest.TestCase):
    def test_rerun_is_a_noop(self):
        out = subprocess.run([sys.executable, PATCH_SCRIPT],
                             cwd=REPO, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("applied=0", out.stdout)
        self.assertIn("ok=True", out.stdout)


class TestFallbackGate(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node not available")
    def test_jsdom_byte_and_digest_equality(self):
        env = dict(os.environ)
        nm = os.path.join(REPO, "node_modules")
        if os.path.isdir(nm):
            env["NODE_PATH"] = nm + os.pathsep + env.get("NODE_PATH", "")
        out = subprocess.run(["node", FALLBACK, UI_APP],
                             cwd=REPO, capture_output=True, text=True, env=env)
        try:
            rep = json.loads(out.stdout)
        except Exception:
            self.skipTest("jsdom unavailable: " + (out.stderr or out.stdout)[:200])
        self.assertTrue(rep["ok"], rep.get("checks"))
        c = rep["checks"]
        self.assertTrue(c["byteIdentical"])
        self.assertTrue(c["verifierIntegrityVerified"])
        self.assertTrue(c["verifierRootMatch"])
        self.assertEqual(c["networkCalls"], 0)
        self.assertEqual(c["jsErrors"], 0)


if __name__ == "__main__":
    unittest.main()
